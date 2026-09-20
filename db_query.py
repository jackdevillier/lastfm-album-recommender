import pandas
import sqlite3

con = sqlite3.connect("lastfm_data.db")
cur = con.cursor()

print(pandas.read_sql_query("""SELECT artist_name, album_name, COUNT(*) as play_count, MAX(date) as last_scrobbled
                        FROM scrobbles 
                        GROUP BY artist_name, album_name 
                        HAVING play_count > 4
                        ORDER BY play_count DESC""", con))
# cur.execute("ALTER TABLE ref DROP COLUMN latest_scrobble_date")
# con.commit()
