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

'''
import sqlite3
import os
from dotenv import load_dotenv
from pylastfmapi.client import LastFM

load_dotenv(".env")
USER_AGENT = os.getenv('USER_AGENT')
API_KEY = os.getenv("API_KEY")
fm = LastFM(USER_AGENT, API_KEY)

con = sqlite3.connect("lastfm_data.db")
db = con.cursor()

ref_dict = {}
cand_dict = {}

sql_queries = {
    'get_top_track':            """SELECT artist_name, track_name, COUNT(*) as plays
                                    FROM scrobbles
                                    WHERE album_name = ?
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
                                    VALUES (?, ?, ?)"""}

# open graph storage files; TODO: handle file creation

# ref_dict file
# with open() as ref_fd:


# cand_dict file
# with open("") as cand_fd:

def pull_ref_table() -> dict:
    return None

def pull_cand_table() -> dict:
    return None

def pull_edge_table() -> dict:
    return None

def pull_graph_from_db() -> list[dict]:
    return None

def get_similar_albums(ref_album: str, num_albums: int) -> list[str]:
    # find the top played track from that album
    db.execute(sql_queries['get_top_track'], (ref_album,))
    top_track = db.fetchall()[0]
    
    # get similar tracks to that track
    similar_tracks = fm.get_track_similar(top_track[1], top_track[0], amount=10)

    res = []
    count = 0
    for track in similar_tracks:
        if count < num_albums:
            track_name = track['name']
            track_sim = track['match']
            track_artist = track['artist']['name']

            print(f"Current track: {track_name} by {track_artist}")

            # check if track is in scrobbles
            db.execute(sql_queries['find_album_scrobbles'], (track_name, track_artist,))
            if len(db.fetchall()) > 0:
                # we have already listened to this album (or at least the track on that album. we can revisit this feature later)
                continue

            # check if track is in unfamiliar cache
            db.execute(sql_queries['find_album_cache'], (track_name, track_artist,))
            cached_tracks = db.fetchall()
            if len(cached_tracks) > 0:
                # track is in unfamiliar cache.
                print(cached_tracks)
                res.append(cached_tracks[0][0])
            else:
                # track is not in cached track table. call get_track_info endpoint and get album
                track = fm.get_track_info(track_name, track_artist)
                res.append(track['album']['title'])
                # update unfamiliar tracks cache
                db.execute(sql_queries['insert_to_cache'], (track_name, track_artist, track['album']['title']))
                con.commit()
            count += 1
        else:
            break
    
    return res

def find_similar_album() -> str:
    return None

print(get_similar_albums("In Rainbows", 3))