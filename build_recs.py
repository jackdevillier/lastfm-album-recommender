'''
BUILDING THE GRAPH:
a) make sure the data is up to date. pull most recent scrobbles
b) Starting the graph:
    - the graph will exist as 2 python dicts:
        - reference dict: stores the albums already listened to. the album title is the key and an object containing scrobbles, recent plays, and loved status is the value
        - candidate dict: stores the albums not listened to. the album title is the key and an array of albums in the reference dict is the value one can pull the 
    - we want to store preexisting info to minimize the amount of API calls
    i) pulling the left side of the graph from local storage: update the weighted scores of each album. this means checking for play count, recency, loved score. add new listened albums to the graph
    ii) pulling the right
c)

BRAINBLAST AREA:

tables I have to make:
- cached unfamiliar tracks to their albums
- graph tables (ref and cand and ref_cand junction)

similar album fetch steps:
    - get song from similar tracks API call
    - check scrobble table for song
    - if not there, check unfamiliar track table
    - if not there use the get_track_info endpoint
        - log track and its album in the unfamiliar tracks table
    
    - when the album is found and does not exist in ref table:
        - create a new row in cand for the album with all necessary info

scoring steps:
- take playcount of each reference album, normalize and log transform it, run against love stat (1.5x multiplier), and recency (0.2-1.4x multiplier)
- take highest played song off the album (or something) and take some user-specified amount of similar songs from that song
- each similar (candidate) album will have a similarity score to the reference album. this will be stored in the edge between the albums (see below for my mad ramblings about sim score)
- each candidate album will take each of its reference albums and calculate a boosted average ()
    - edge_score = min(1, avg_similarity_score * (1 + boost_factor * (hit_count - 1)))


sim score changes when two songs of the same album are recommended from two songs from the ref album. maybe track the amount of new "hits" between two albums and take the average of all of the similarity scores
- counter: to prioritize "hits", reward the candidate album with higher score based on the amount of hits it has
boost_multiplier = 1 + boost_factor * min(hit_count - 1, max_hits_considered=5)

checked flag: since similar songs is "objective" and rather immutable in the eyes of last.fm, we can "check off" a track in the scrobbles table? needs to 

'''
import sqlite3
import os
from dotenv import load_dotenv
from pylastfmapi.client import LastFM
from scrobble_puller import pull_scrobbles
import datetime
import json
import math
import bisect
import random

def open_lastfm_client() -> LastFM:
    load_dotenv(".env")
    return LastFM(os.getenv('USER_AGENT'), os.getenv("API_KEY"))

sql_queries = {
    'get_top_track':            """SELECT artist_name, track_name, COUNT(*) as plays
                                    FROM scrobbles
                                    WHERE album_name = ?
                                    AND artist_name = ?
                                    GROUP BY artist_name, track_name
                                    ORDER BY plays DESC
                                    LIMIT 1""",
    'find_album_scrobbles':     """SELECT DISTINCT album_name
                                    FROM scrobbles
                                    WHERE track_name = ?
                                    AND artist_name = ?""",
    'find_album_cache':         """SELECT DISTINCT album_name
                                    FROM similar_cache
                                    WHERE track_name = ?
                                    AND artist_name = ?""",
    'insert_to_cache':          """INSERT OR IGNORE 
                                    INTO similar_cache (track_name, artist_name, album_name)
                                    VALUES (?, ?, ?)""",
    'remove_from_cache':        """DELETE FROM similar_cache
                                    WHERE track_name = ?
                                    AND artist_name = ?
                                    AND album_name = ?""",
    'albums_by_plays':          """SELECT album_name, artist_name, COUNT(*) as play_count, MAX(date) as last_scrobbled
                                    FROM scrobbles
                                    WHERE play_count > 4
                                    GROUP BY album_name
                                    ORDER BY play_count DESC""",
    'untracked_tracks':         """SELECT DISTINCT s.artist_name, s.track_name
                                    FROM scrobbles s
                                    LEFT JOIN ref_cache rc
                                        ON s.artist_name = rc.artist_name AND s.track_name = rc.track_name
                                    WHERE rc.id IS NULL;""",
    'untracked_albums':         """SELECT DISTINCT s.artist_name, s.album_name
                                    FROM scrobbles s
                                    LEFT JOIN ref r
                                        ON s.artist_name = r.artist_name AND s.album_name = r.album_name
                                    WHERE r.id IS NULL""",
    'clean_cand':               """DELETE FROM cand
                                    WHERE id IN (
                                        SELECT DISTINCT c2.id FROM cand c2
                                        INNER JOIN scrobbles s
                                            ON s.artist_name = c2.artist_name AND s.album_name = c2.album_name);""",
    'clean_cand_cache':         """DELETE FROM cand
                                    WHERE id IN (
                                        SELECT DISTINCT c2.id FROM cand c2
                                        INNER JOIN scrobbles s
                                            ON s.artist_name = c2.artist_name AND s.album_name = c2.album_name);""",
}

'''
go through ref table and update the playcount of each album/row
'''

def get_similar_albums(ref_track: str, ref_artist: str, num_hits: int, fm: LastFM, con: sqlite3.Connection, db: sqlite3.Cursor) -> list[str]:
    # call similar tracks endpoint
    similar_tracks = fm.get_track_similar(ref_track, ref_artist, amount=20)

    res = []
    count = 0
    for track in similar_tracks:
        if count < num_hits:
            track_name = track['name']
            track_sim = track['match']
            track_artist = track['artist']['name']

            print(f"Current track: {track_name} by {track_artist}")

            # check if track is in scrobbles
            db.execute(sql_queries['find_album_scrobbles'], (track_name, track_artist,))
            scrobbled_track = db.fetchall()
            if len(scrobbled_track) > 0:
                # we have already listened to this album (or at least the track on that album. we can revisit this feature later)

                # TODO: remove track from similar track cache
                db.execute(sql_queries['remove_from_cache'], (track_name, track_artist, scrobbled_track[0][0]))
                continue

            # check if track is in unfamiliar cache
            db.execute(sql_queries['find_album_cache'], (track_name, track_artist,))
            cached_tracks = db.fetchall()
            if len(cached_tracks) > 0:
                # track is in unfamiliar cache.
                res.append(cached_tracks[0][0])
            else:
                # track is not in cached track table. call get_track_info endpoint and get album
                track = fm.get_track_info(track_name, track_artist)
                res.append(track['album']['title'])
                # update unfamiliar tracks cache
                db.execute(sql_queries['insert_to_cache'], (track_name, track_artist, track['album']['title']))
            count += 1
        else:
            break
    con.commit()
    return res

def build_recs(fm: LastFM, con: sqlite3.Connection, db: sqlite3.Cursor):
    # check state for whether we need to generate a new album
    latest_pull_date = ""
    try:
        with open("state.json", 'r') as fd:
            latest_pull_date = datetime.date.fromisoformat(json.load(fd)['latest_pull'])
    except FileNotFoundError:
        # create new datetime
        latest_pull_date = datetime.date.today() - datetime.timedelta(days=365)
        with open("state.json", 'x') as fd:
            fd.write(json.dumps({"latest_pull": latest_pull_date.isoformat()}))
    new_enddate = pull_scrobbles(latest_pull_date, fm, con, db)

    # TODO: update cand and cand_cache for albums that have now been listened to, in order to remove them from the rec list
    db.execute(sql_queries['clean_cand'])
    db.execute(sql_queries['clean_cand_cache'])

    # get playcounts, latest date for calculations
    db.execute(sql_queries['albums_by_plays'])
    scrobbled_albums = db.fetchall()

    # create weights for each album based on PC and recency
    if len(scrobbled_albums) == 0:
        print("No scrobbles in scrobble table.")
        exit()

    # log transform the max playcount so we can run it against every other playcount and normalize them on a fairer scale
    lt_max_pcount = math.log(scrobbled_albums[0][2] + 1)

    # key pattern: ["album|artist"]: user_weight 
    weights = {}

    for album in scrobbled_albums:
        pcount = album[2]

        # log transform and normalize playcount
        lt_pcount = math.log(pcount + 1)
        norm_pcount = lt_pcount / lt_max_pcount

        # pull date
        last_played_date = datetime.date.fromisoformat(album[3])
        days_since = (datetime.date.today() - last_played_date).days

        # date multiplier (A * exp(-k * (x - 1)) + C), A = 1.2, C = 0.2:
        # no threshold: do nothing (no recency multiplier)
        # 90-day threshold: k = 0.0045558
        # 30-day threshold: k = 0.0138
        # 14-day threshold: k = 0.0312
        #  7-day threshold: k = 0.0675 (default)
        recency_multiplier = 1.2 * math.exp(-0.0675 * (days_since - 1)) + 0.2

        # compute and store in weights hash
        final_weight = norm_pcount * recency_multiplier
        weights[f'{album[0]}|{album[1]}'] = final_weight


    # add new albums 
    db.execute(sql_queries['untracked_albums'])
    untracked_albums = db.fetchall()
    for album in untracked_albums:
        db.execute(sql_queries["INSERT OR IGNORE INTO ref (artist_name, album_name) VALUES (?, ?)"], (album[0], album[1]))

    # process all untracked tracks into ref_cache and their respective albums in ref
    db.execute(sql_queries['untracked_tracks'])
    untracked_tracks = db.fetchall()
    for track in untracked_tracks:

        # cand table gets built in here
        get_similar_albums(rand_album[1], rand_album[0], num_hits=5)
        break

    con.commit()
        



    # given a user specified amount of new tracks to add to the graph, run down each track and figure out the amount of 

    # outcome: write new rec list to a json file (recs.json)

    return


def main():
    fm = open_lastfm_client()
    con = sqlite3.connect("lastfm_data.db")
    db = con.cursor()

    build_recs(fm, con, db)



if __name__ == "__main__":
    main()
