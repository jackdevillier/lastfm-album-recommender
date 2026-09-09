import sqlite3
from pathlib import Path

file_path = Path("lastfm_data.db")
file_path.touch(exist_ok=True)

con = sqlite3.connect("lastfm_data.db")

cur = con.cursor()

sql_statements = [ 
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
]
cur.execute("DROP TABLE scrobbles")
cur.execute(sql_statements[0])
