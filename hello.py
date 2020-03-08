import pymysql.cursors
import config
from flask import Flask, g, render_template

app = Flask(__name__)


@app.route("/")
def hello():
    cursor = db_connect()

    sql = """
        SELECT gpm_tracks.title, gpm_tracks.track_type, gpm_tracks.duration_millis, gpm_tracks.artist,
            gpm_playlist_entries.gpm_playlistid, gpm_playlists.`name` AS `playlist_name`,
            gpm_playlist_entries.dt_deleted,
            gpm_albums.album, gpm_albums.album_artist
        FROM gpm_playlist_entries
        LEFT JOIN gpm_playlists ON gpm_playlist_entries.gpm_playlistid = gpm_playlists.gpm_playlistid
        LEFT JOIN gpm_tracks ON gpm_playlist_entries.gpm_trackid = gpm_tracks.gpm_trackid
        LEFT JOIN gpm_albums ON gpm_tracks.gpm_albumid = gpm_albums.gpm_albumid
        WHERE gpm_playlist_entries.deleted = 1
            AND gpm_playlists.deleted = 0
            AND gpm_playlists.`name` NOT LIKE 'BG Rand%'
            AND gpm_playlist_entries.dt_deleted > DATE_SUB(NOW(), INTERVAL 3 MONTH)
        ORDER BY gpm_playlist_entries.dt_deleted DESC, album_artist ASC
    """
    cursor.execute(sql)
    recently_deleted = cursor.fetchall()

    return render_template(
        "removals.html",
        recently_deleted=recently_deleted,
        convert_millis=convert_millis
    )


def convert_millis(millis):
    seconds = int((millis / 1000) % 60)
    minutes = int((millis / (1000 * 60)) % 60)
    hours = int((millis / (1000 * 60 * 60)) % 24)
    if hours >= 1:
        return "{0:02d}:{1:02d}:{2:02d}".format(hours, minutes, seconds)
    return "{1:d}:{2:02d}".format(hours, minutes, seconds)


def db_connect():
    # Connect to MySQL
    g.db = pymysql.connect(
        host=config.db["hostname"],
        user=config.db["username"],
        password=config.db["password"],
        db=config.db["database"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

    cursor = g.db.cursor()

    sql_modes = ['ERROR_FOR_DIVISION_BY_ZERO', 'NO_ZERO_DATE', 'NO_ZERO_IN_DATE', 'STRICT_ALL_TABLES',
                 'ONLY_FULL_GROUP_BY', 'NO_AUTO_CREATE_USER', 'NO_ENGINE_SUBSTITUTION']
    sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sql_modes) + "'"
    cursor.execute(sql)
    return cursor
