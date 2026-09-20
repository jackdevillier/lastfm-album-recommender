import sqlite3
from pathlib import Path

file_path = Path("lastfm_data.db")
file_path.touch(exist_ok=True)

con = sqlite3.connect("lastfm_data.db")

cur = con.cursor()

'''
TABLE DESCRIPTIONS:
scrobbles: tracks every scrobble, pulled from the Last.fm API.

Bipartite graph tables:
ref: holds the left side of the bipartite graph, tracking albums that the user has already listened to and their relevant metrics needed to calculate weights for candidate albums
cand: holds the right side of the bipartite graph, tracking albums that the user has not listened to but are similar to various reference albums.
ref_cand: junction table that links ref albums to cand albums, keeping metrics on the similarity score between the two albums.

"Cache" tables:
ref_cache: track albums that have already been checked for similar tracks. prevents "double hits" from one track to another when calculating similar scores
cand_cache: keeps candidate track-to-album relations so we don't have to keep using Last.fm API resources to determine the album of a similar track.

'''

sql_queries = [ 
    """CREATE TABLE IF NOT EXISTS scrobbles (
            id INTEGER PRIMARY KEY, 
            artist_name TEXT NOT NULL, 
            track_name TEXT NOT NULL,
            album_name TEXT,
            mbid TEXT,
            loved BIT,
            date DATE, 
            time TEXT,
            UNIQUE(date, time, artist_name, track_name)
        );""",
    """CREATE TABLE IF NOT EXISTS ref (
            id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL, 
            album_name TEXT,
            loved BIT,
            latest_scrobble_date DATE,
            UNIQUE(artist_name, album_name)
        );""",
    """CREATE TABLE IF NOT EXISTS cand (
            id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL,
            album_name TEXT,
            UNIQUE(artist_name, album_name)
        );""",
    """CREATE TABLE IF NOT EXISTS ref_cand (
            ref_id INTEGER,
            cand_id INTEGER,
            sim_sum FLOAT,
            num_hits INTEGER,
            FOREIGN KEY(ref_id) REFERENCES ref(id), 
            FOREIGN KEY(cand_id) REFERENCES cand(id)
        );""",
    """CREATE TABLE IF NOT EXISTS cand_cache (
            track_name TEXT NOT NULL,
            artist_name TEXT NOT NULL,
            album_name TEXT,
            UNIQUE(artist_name, track_name, album_name)
        );""",
    """CREATE TABLE IF NOT EXISTS ref_cache (
            track_name TEXT NOT NULL,
            artist_name TEXT NOT NULL,
            album_name TEXT,
            unique(track_name, artist_name)
        );"""
]

# cur.execute("DROP TABLE scrobbles")
# cur.execute("DROP TABLE ref")
# cur.execute("DROP TABLE cand")
# cur.execute("DROP TABLE ref_cand")
# cur.execute("DROP TABLE ref_cache")
# cur.execute("DROP TABLE cand_cache")

for query in sql_queries:
    cur.execute(query)