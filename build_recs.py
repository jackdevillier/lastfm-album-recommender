'''
TODO: 
 - fix queries to reflect reengineered schema
 - 
'''
import sqlite3
import os
from dotenv import load_dotenv
from pylastfmapi.client import LastFM
from scrobble_puller import pull_scrobbles
import datetime
import json
import math

def open_lastfm_client() -> LastFM:
    load_dotenv(".env")
    return LastFM(os.getenv('USER_AGENT'), os.getenv("API_KEY"))

sql_queries = {
    'get_top_track':            """SELECT artist_name, track_name, COUNT(*) as plays
                                    FROM scrobble
                                    WHERE album_name = ?
                                    AND artist_name = ?
                                    GROUP BY artist_name, track_name
                                    ORDER BY plays DESC
                                    LIMIT 1""",
    'find_album_scrobbles':     """SELECT DISTINCT album_name
                                    FROM scrobble
                                    WHERE track_name = ?
                                    AND artist_name = ?""",
    'search_tracks':            """SELECT DISTINCT t.id, a.album_name, a.id
                                    FROM track t
                                    JOIN album a ON a.id = t.album_id
                                    WHERE t.track_name = ?
                                    AND a.artist_name = ?""",
    'albums_by_plays':          """SELECT album_name, artist_name, COUNT(*) as play_count, MAX(date) as last_scrobbled
                                    FROM scrobble
                                    WHERE play_count > 4
                                    GROUP BY album_name, artist_name
                                    ORDER BY play_count DESC""",
    'untracked_tracks':         """SELECT DISTINCT a.id, s.track_name
                                    FROM scrobble s
                                    LEFT JOIN album a
                                        ON s.artist_name = a.artist_name AND s.album_name = a.album_name
                                    LEFT JOIN track t
                                        ON a.id = t.album_id AND s.track_name = t.track_name
                                    WHERE t.id IS NULL
                                    AND (s.artist_name, s.album_name) IN (
                                        SELECT s1.artist_name, s1.album_name 
                                        FROM scrobble s1 
                                        GROUP BY s1.album_name, s1.artist_name 
                                        HAVING COUNT(*) > 4
                                    );""",
    'untracked_albums':         """SELECT DISTINCT s.artist_name, s.album_name
                                    FROM scrobble s
                                    LEFT JOIN album a
                                        ON s.artist_name = a.artist_name AND s.album_name = a.album_name
                                    WHERE a.id IS NULL
                                    AND (s.artist_name, s.album_name) IN (
                                        SELECT s1.artist_name, s1.album_name 
                                        FROM scrobble s1 
                                        GROUP BY s1.album_name, s1.artist_name 
                                        HAVING COUNT(*) > 4
                                    );""",
    'insert_track_edge':        """INSERT OR IGNORE
                                    INTO track_edge (ref_track_id, cand_track_id, sim_score)
                                    VALUES (?, ?, ?)""",
    'insert_album':             """INSERT OR IGNORE
                                    INTO album (artist_name, album_name)
                                    VALUES (?, ?, ?)""",
    'insert_album_edge':        """INSERT OR IGNORE
                                    INTO album_edge (ref_album_id, cand_album_id)
                                    VALUES (?, ?)""",
    'upsert_to_uaes':           """INSERT INTO user_album_edge_score (user_id, album_edge_id, sim_sum, num_hits)
                                    VALUES (?, ?, ?, 1)
                                    ON CONFLICT(user_id, album_edge_id)
                                        DO UPDATE SET 
                                            sim_sum = sim_sum + excluded.sim_sum, 
                                            num_hits = num_hits + 1""",
}


'''
go through ref table and update the playcount of each album/row. currently the assumption is that any ref track entering this function has not been tracked for simlar tracks before
'''
def get_similar_albums(ref_track: str, ref_artist: str, ref_album: str, ref_track_id: int, num_hits: int, fm: LastFM, con: sqlite3.Connection, db: sqlite3.Cursor) -> list[str]:
    # call similar tracks endpoint
    similar_tracks = fm.get_track_similar(ref_track, ref_artist)
    ref_album_id = db.execute("SELECT id FROM album WHERE artist_name = ? AND album_name = ?", (ref_artist, ref_album,))
    res = []
    count = 0

    # update album when there is a new album
    # update track when there is a new track (after a get_track_info call)
    # update album_edge when there is a new ref-to-cand album connection (does not mean that any new albums have to be added)
    # update user_album_edge_score when track_edge is updated
    # update track_edge for every time a new ref-to-cand track connection (does not mean that any new tracks have to be added)
    #  - this means that as long as the track isn't found in scrobbles then we need to update this and user_album_edge_score accordingly
    for track in similar_tracks:
        if count < num_hits:
            cand_track_name = track['name']
            cand_track_sim = track['match']
            cand_track_artist = track['artist']['name']

            print(f"Current track: {cand_track_name} by {cand_track_artist}")

            # we need to figure out the album of the cand track

            # check if track is in scrobbles, and return the album if so
            db.execute(sql_queries['find_album_scrobbles'], (cand_track_name, cand_track_artist,))
            scrobbled_track = db.fetchall()
            if len(scrobbled_track) > 0:
                # someone has already listened to this album. TODO: do logic on determining whether the current user has listened to the album and respond accordingly
                continue

            # check if in track table, and therefore the track's album
            db.execute(sql_queries['search_tracks'], (cand_track_name, cand_track_artist,))
            cached_tracks = db.fetchall()
            if len(cached_tracks) > 0:
                # track is in track we can also assume that the respective album is in album. insert new track_edge, update UAES with new sim_sum
                track_id = cached_tracks[0][0]
                album_name = cached_tracks[0][1]
                album_id = cached_tracks[0][2]
                # insert new relation into track_edge
                db.execute(sql_queries['insert_track_edge'], (ref_track_id, track_id, cand_track_sim))
                # try to insert new relation into album_edge: find id of cand and ref album (you have everything)
                db.execute(sql_queries['insert_album_edge'], (ref_album_id, album_id))
                album_edge_id = db.lastrowid
                if db.rowcount < 1:
                    db.execute("SELECT id FROM album_edge WHERE ref_album_id = ? AND cand_album_id = ?", (ref_album_id, album_id))
                    album_edge_id = db.fetchall()[0]
                db.execute(sql_queries['upsert_to_uaes'], (1, album_edge_id, cand_track_sim, 1))
            else:
                # track is not in track table. call get_track_info endpoint and get album, then update edges
                track = fm.get_track_info(cand_track_name, cand_track_artist)

                # TODO: check if album is in album table, add if not, then add track with album id

                # album_name = 
                # update cand cache UPDATE THIS DB CALL
                db.execute(sql_queries['insert_track'], (cand_track_name, track['album']['title']))
            count += 1
        else:
            break
    return res

def build_recs(fm: LastFM, con: sqlite3.Connection, db: sqlite3.Cursor):
    # check state for whether we need to update the graph
    latest_pull_date = None
    try:
        with open("state.json", 'r') as fd:
            latest_pull_date = datetime.date.fromisoformat(json.load(fd)['latest_pull'])
    except FileNotFoundError:
        # create new datetime
        latest_pull_date = datetime.date.today() - datetime.timedelta(days=365)
        with open("state.json", 'x') as fd:
            fd.write(json.dumps({"latest_pull": latest_pull_date.isoformat()}))

    if latest_pull_date == datetime.date.today():
        # special case where we just need to return the recommendations previously generated today
        return
    
    new_enddate = pull_scrobbles(latest_pull_date, fm, con, db)

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
        # k = 0.0675
        recency_multiplier = 1.2 * math.exp(-0.0675 * (days_since - 1)) + 0.2

        # compute and store in weights hash
        final_weight = norm_pcount * recency_multiplier
        weights[f'{album[0]}|{album[1]}'] = final_weight

    # process all untracked tracks into ref_cache and their respective albums in ref
    db.execute(sql_queries['untracked_albums'])
    untracked_albums = db.fetchall()
    for album in untracked_albums:
        # update album
        db.execute("INSERT OR IGNORE INTO album (artist_name, album_name) VALUES (?, ?)", (album[0], album[1]))

    db.execute(sql_queries['untracked_tracks'])
    untracked_tracks = db.fetchall()
    for track in untracked_tracks:
        # function updates album, album_edge, user_album_edge_score, track, and track_edge
        db.execute("INSERT OR IGNORE INTO track (track_name, album_id) VALUES (?, ?)", (track[1], track[0]))
        get_similar_albums(track[1], track[0], track[2], db.lastrowid, num_hits=5, fm=fm, con=con, db=db)
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
