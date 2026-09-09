import pandas
import sqlite3

con = sqlite3.connect("lastfm_data.db")
cur = con.cursor()

print(pandas.read_sql_query("""SELECT artist_name, album_name, COUNT(10) as play_count 
                        FROM scrobbles 
                        GROUP BY artist_name, album_name 
                        ORDER BY play_count DESC
                        LIMIT 50""", con))
