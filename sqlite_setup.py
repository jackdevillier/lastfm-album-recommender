import sqlite3
from pathlib import Path

file_path = Path("lastfm_data.db")
file_path.touch(exist_ok=True)

con = sqlite3.connect("lastfm_data.db")

cur = con.cursor()

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
    """CREATE TABLE IF NOT EXISTS similar_cache (
            track_name TEXT NOT NULL,
            artist_name TEXT NOT NULL,
            album_name TEXT,
            UNIQUE(artist_name, track_name, album_name)
        );"""
]

# cur.execute("DROP TABLE scrobbles")
# cur.execute("DROP TABLE ref")
# cur.execute("DROP TABLE cand")
# cur.execute("DROP TABLE ref_cand")
# cur.execute("DROP TABLE similar_cache")

for query in sql_queries:
    cur.execute(query)