from pylastfmapi.client import LastFM
from pylastfmapi import exceptions
import time 
import datetime
from dotenv import load_dotenv
import os
import sys
import json
import math
import sqlite3

def pull_scrobbles(latest_pull_date, client: LastFM, con: sqlite3.Connection, cur: sqlite3.Cursor) -> datetime.date:
    load_dotenv(".env")
    USER_AGENT = os.getenv('USER_AGENT')
    API_KEY = os.getenv("API_KEY")
    client = LastFM(USER_AGENT, API_KEY)

    def fmt_recent_tracks(tracks: list[dict], day: datetime.date) -> list[dict]:
        res = []
        for track in tracks:
            if track.get('@attr') != None:
                continue
            t = {}
            t['artist_name'] = track['artist']['name']
            t['track_name'] = track['name']
            t['album_name'] = track['album']['#text']
            t['mbid'] = track['mbid']
            t['loved'] = track['loved']
            t['date'] = datetime.date.fromtimestamp(int(track['date']['uts'])).isoformat()
            t['time'] = track['date']['#text'].split(", ")[1]
            res.append(t)
        return res

    def pull_scrobbles_range(start: datetime.date, end: datetime.date, batch_size: int) -> bool:
        curr_day = start
        # with open("history.ndjson", 'a', encoding="utf-8") as fd:
        while curr_day < end:
            try:
                np = client.get_user_recent_tracks(user=USER_AGENT, 
                                                date_from=curr_day.isoformat(), 
                                                date_to=(curr_day + datetime.timedelta(days=min(7, (end - curr_day).days))).isoformat())
            except exceptions.RequestErrorException:
                fd.close()
                return pull_scrobbles_range(curr_day, end_date, math.ceil(batch_size / 2)) == True

            # prepare API data for storage
            formatted_tracks = fmt_recent_tracks(np, curr_day)
            for t in range(len(formatted_tracks) - 1, -1, -1):
                track = formatted_tracks[t]
                cur.execute("""INSERT OR IGNORE INTO scrobbles 
                                (artist_name, track_name, album_name, mbid, loved, date, time)
                                VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                            (track['artist_name'], track['track_name'], track['album_name'], track['mbid'], track['loved'], track['date'], track['time']))
            con.commit()
            curr_day += datetime.timedelta(days=min(7, (end - curr_day).days))
            time.sleep(0.3)

        return curr_day == end

    end_date = datetime.date.today()

    con = sqlite3.connect("lastfm_data.db")
    cur = con.cursor()

    assert pull_scrobbles_range(latest_pull_date, end_date, 7) == True

    con.commit()
    con.close()

    # update state file
    with open("state.json", 'w') as fd:
        fd.write(json.dumps({"latest_pull":end_date.isoformat()}))

    return end_date
