import sqlite3
from pathlib import Path

file_path = Path("lastfm_data.db")
file_path.touch(exist_ok=True)

con = sqlite3.connect("lastfm_data.db")

cur = con.cursor()

'''
TABLE DESCRIPTIONS:
scrobbles: tracks every scrobble, pulled from the Last.fm API.

album tables:
album: holds every album, one off, with id
album_edge: holds relationship between reference and candidate album. many to many
user_album_edge_score


track tables:
track: holds every track, one off, with id and reference to relevant album that the track is on
track_edge: holds relationship between reference and candidate tracks. many to many


'''

sql_queries = [
    """CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            UNIQUE(username)
        );""",
    """CREATE TABLE IF NOT EXISTS tappedin (
            id INTEGER PRIMARY KEY,
            tapper_id INTEGER,
            tapped_id INTEGER,
            FOREIGN KEY(tapper_id) REFERENCES user(id) ON DELETE CASCADE, 
            FOREIGN KEY(tapped_id) REFERENCES user(id) ON DELETE CASCADE,
            UNIQUE(tapper_id, tapped_id),
            CHECK(tapper_id != tapped_id)
        );""",
    """CREATE TABLE IF NOT EXISTS scrobble (
            id INTEGER PRIMARY KEY, 
            user_id INTEGER,
            artist_name TEXT NOT NULL, 
            track_name TEXT NOT NULL,
            album_name TEXT,
            mbid TEXT,
            loved BIT,
            date DATE, 
            time TEXT,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE,
            UNIQUE(date, time, artist_name, track_name)
        );""",
    """CREATE TABLE IF NOT EXISTS album (
            id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL, 
            album_name TEXT,
            UNIQUE(artist_name, album_name)
        );""",
    """CREATE TABLE IF NOT EXISTS album_edge (
            id INTEGER PRIMARY KEY,
            ref_album_id INTEGER,
            cand_album_id INTEGER,
            FOREIGN KEY(ref_album_id) REFERENCES album(id) ON DELETE CASCADE, 
            FOREIGN KEY(cand_album_id) REFERENCES album(id) ON DELETE CASCADE,
            UNIQUE(ref_album_id, cand_album_id)
        );""",
    """CREATE TABLE IF NOT EXISTS user_album_edge_score (
            id INTEGER PRIMARY KEY,
            album_edge_id INTEGER,
            user_id INTEGER,
            sim_sum FLOAT,
            num_hits INTEGER,
            FOREIGN KEY(album_edge_id) REFERENCES album_edges(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
            UNIQUE(album_edge_id, user_id)
        );""",
    """CREATE TABLE IF NOT EXISTS track (
            id INTEGER PRIMARY KEY,
            album_id INTEGER,
            track_name TEXT NOT NULL,
            FOREIGN KEY(album_id) REFERENCES album(id) ON DELETE CASCADE,
            UNIQUE(album_id, track_name)
        );""",
    """CREATE TABLE IF NOT EXISTS track_edge (
            ref_track_id INTEGER,
            cand_track_id INTEGER,
            sim_score FLOAT NOT NULL,
            FOREIGN KEY(ref_track_id) REFERENCES track(id) ON DELETE CASCADE, 
            FOREIGN KEY(cand_track_id) REFERENCES track(id) ON DELETE CASCADE,
            UNIQUE(ref_track_id, cand_track_id)
        );"""
    
]



# cur.execute("DROP TABLE user")
# cur.execute("DROP TABLE tappedin")
# cur.execute("DROP TABLE scrobble")

# cur.execute("DROP TABLE album")
# cur.execute("DROP TABLE track")
# cur.execute("DROP TABLE album_edge")
# cur.execute("DROP TABLE track_edge")
# cur.execute("DROP TABLE user_album_edge_score")


for query in sql_queries:
    # print(query)
    cur.execute(query)

con.commit()
con.close()