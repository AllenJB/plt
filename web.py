import pymysql.cursors
import config
from flask import Flask, flash, g, render_template, redirect, request, url_for
from ytmusicapi import YTMusic

app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "home.html",
    )


@app.route("/gpm")
def gpm():
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


@app.route("/ytm/deleted")
def ytm_deleted():
    cursor = db_connect()

    sql = """
        SELECT ytm_playlist_entries.entry_name, ytm_playlist_entries.duration, ytm_playlist_entries.artist_name,
            ytm_playlist_entries.ytm_playlistid, ytm_playlists.playlist_title,
            ytm_playlist_entries.dt_plt_deleted,
            ytm_playlist_entries.album_name
        FROM ytm_playlist_entries
        LEFT JOIN ytm_playlists ON ytm_playlist_entries.ytm_playlistid = ytm_playlists.ytm_playlistid
        WHERE ytm_playlist_entries.deleted = 1
            AND ytm_playlists.deleted = 0
            AND ytm_playlist_entries.dt_plt_deleted > DATE_SUB(NOW(), INTERVAL 3 MONTH)
        ORDER BY ytm_playlist_entries.dt_plt_deleted DESC, ytm_playlist_entries.artist_name ASC
    """
    cursor.execute(sql)
    recently_deleted = cursor.fetchall()

    return render_template(
        "ytm/removals.html",
        recently_deleted=recently_deleted,
    )


@app.route("/ytm/plsearch", methods=["GET", "POST"])
def ytm_plsearch():
    cursor = db_connect()
    ytmusic = YTMusic('ytm_auth.json')

    term = request.form.get("term")

    recently_played = None
    results = None
    if term is None:
        recently_played = ytmusic.get_history()
        recently_played = ytm_attach_playlists(recently_played, cursor)
    else:
        sql = """
            SELECT DISTINCT ytm_playlist_entries.entry_name, ytm_playlist_entries.duration, 
                ytm_playlist_entries.artist_name, ytm_playlist_entries.album_name,
                ytm_playlist_entries.ytm_videoid AS videoId
            FROM ytm_playlist_entries
            LEFT JOIN ytm_playlists ON ytm_playlist_entries.ytm_playlistid = ytm_playlists.ytm_playlistid
            WHERE ytm_playlist_entries.deleted = 0
                AND ytm_playlists.deleted = 0
                AND (
                    ytm_playlist_entries.entry_name LIKE CONCAT('%%', %(term)s, '%%')
                    OR ytm_playlist_entries.artist_name LIKE CONCAT('%%', %(term)s, '%%')
                    OR ytm_playlist_entries.album_name LIKE CONCAT('%%', %(term)s, '%%')
                )
            ORDER BY ytm_playlist_entries.artist_name ASC, 
                ytm_playlist_entries.entry_name ASC, 
                ytm_playlist_entries.album_name ASC
        """
        params = {
            "term": term,
        }
        cursor.execute(sql, params)
        results = cursor.fetchall()
        results = ytm_attach_playlists(results, cursor)

    return render_template(
        "ytm/plsearch.html",
        history=recently_played,
        results=results,
        term=term,
        ytm_list_artist_names=ytm_list_artist_names
    )


@app.route("/ytm/remove")
def ytm_remove():
    playlistid = request.args.get("playlistId")
    videoid = request.args.get("videoId")
    set_videoid = request.args.get("setVideoId")

    if playlistid is None:
        flash("Missing playlistid", "error")
        return redirect(url_for("ytm_plsearch"))

    ytmusic = YTMusic('ytm_auth.json')

    cursor = db_connect()

    successCount = 0
    failedCount = 0
    lastFailedMsg = None
    if playlistid == "ALL":
        if videoid is None:
            flash("Missing videoid", "error")
            return redirect(url_for("ytm_plsearch"))

        sql = """
            SELECT DISTINCT entry_name, album_name, artist_name
            FROM ytm_playlist_entries
            WHERE ytm_videoid = %(videoId)s
                AND deleted = 0
            LIMIT 1 
        """
        params = {
            "videoId": videoid,
        }
        cursor.execute(sql, params)
        track = cursor.fetchone()

        sql = """
        SELECT DISTINCT ytm_set_videoid
            FROM ytm_playlist_entries
            WHERE ytm_playlistid = %(playlistId)s
                AND ytm_videoid = %(videoId)s
                AND deleted = 0
        """
        params = {
            "playlistId": playlistid,
            "videoId": videoid,
        }
        cursor.execute(sql, params)
        entries = cursor.fetchall()

        for plentry in entries:
            playlist_item = {
                "setVideoId": plentry["ytm_set_videoid"],
            }
            status = ytmusic.remove_playlist_items(playlistId=playlistid, videos=[playlist_item])
            if status != "STATUS_SUCCEEDED":
                failedCount += 1
                lastFailedMsg = status
            else:
                successCount += 1

        playlist_desc = str(successCount) + " playlists"
    else:
        if set_videoid is None:
            flash("Missing set_videoid", "error")
            return redirect(url_for("ytm_plsearch"))

        sql = """
            SELECT DISTINCT entry_name, album_name, artist_name, playlist_title
            FROM ytm_playlist_entries
            LEFT JOIN ytm_playlists ON ytm_playlist_entries.ytm_playlistid = ytm_playlists.playlistid
            WHERE ytm_set_videoid = %(setVideoId)s
                AND ytm_playlist_entries.deleted = 0
                AND ytm_playlists.deleted = 0
            LIMIT 1 
        """
        params = {
            "setVideoId": set_videoid,
        }
        cursor.execute(sql, params)
        track = cursor.fetchone()
        playlist_desc = track["playlist_title"]

        playlist_item = {
            "setVideoId": set_videoid,
        }
        status = ytmusic.remove_playlist_items(playlistId=playlistid, videos=[playlist_item])
        if status != "STATUS_SUCCEEDED":
            failedCount += 1
            lastFailedMsg = status
        else:
            successCount += 1

    if failedCount > 0:
        flash("Failed to remove track from " + str(failedCount) + " playlists. Last response: " + lastFailedMsg, "error")
    if successCount > 0:
        flash(
            "Track removed: " + track["entry_name"] + " by " + track["artist_name"] + " from " + playlist_desc,
            "success"
        )
    return redirect(url_for("ytm_plsearch"))


def ytm_attach_playlists(tracks, cursor):
    for track in tracks:
        if track["videoId"] is None:
            track["playlists"] = []
            continue

        sql = """
            SELECT DISTINCT ytm_playlist_entries.ytm_playlistid, ytm_playlists.playlist_title,
                ytm_playlist_entries.ytm_set_videoid
            FROM ytm_playlist_entries
            LEFT JOIN ytm_playlists ON ytm_playlist_entries.ytm_playlistid = ytm_playlists.ytm_playlistid
            WHERE ytm_playlist_entries.deleted = 0
                AND ytm_playlists.deleted = 0
                AND ytm_videoid = %(videoId)s
            ORDER BY ytm_playlists.playlist_title ASC
        """
        params = {
            "videoId": track["videoId"]
        }
        cursor.execute(sql, params)
        track["playlists"] = cursor.fetchall()

    return tracks


def ytm_list_artist_names(track):
    if track["artists"] is None:
        return ""

    artist_names = []
    for artistEntry in track["artists"]:
        artist_names.append(artistEntry["name"])

    return "\n".join(artist_names)


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
                 'ONLY_FULL_GROUP_BY', 'NO_ENGINE_SUBSTITUTION']
    sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sql_modes) + "'"
    cursor.execute(sql)
    return cursor
