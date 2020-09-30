import argparse
import config
import locale
import logging
import os
import pymysql.cursors
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pprint import pformat
from ytmusicapi import YTMusic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("-l", "--listId", help="Playlist ID", nargs=1)
    args = parser.parse_args()

    locale.setlocale(locale.LC_ALL, 'en_GB')

    logger = init_log(config.log["dir"] + "ytm_fetch/", args)
    db, cursor = init_db(config.db)

    ytmusic = YTMusic('ytm_auth.json')

    sql = "UPDATE `ytm_playlists` SET `processed` = 0 WHERE 1=1"
    cursor.execute(sql)

    sql = """
        UPDATE `ytm_playlist_entries` 
        SET `processed` = 0,
            `prev_unavailable` = `unavailable` 
        WHERE 1=1
    """
    cursor.execute(sql)

    sql = """
        UPDATE `ytm_playlist_entries_unavailable` 
        SET `processed` = 0
        WHERE 1=1
    """
    cursor.execute(sql)

    only_list_id = None
    if args.listId is None:
        logger.info("No list id given - fetching all playlists")
        fetch_all_playlists(ytmusic, cursor, logger)
    else:
        only_list_id = args.listId[0]
        logger.info("Fetching tracks for playlist: " + only_list_id)
        fetch_playlist(ytmusic, cursor, logger, only_list_id)

    if only_list_id is None:
        delete_unprocessed_playlists(cursor, logger)

    notify_deleted(config.smtp, cursor, logger)

    if only_list_id is None:
        delete_unprocessed_playlist_entries(cursor, logger)

    db.close()


def init_log(logpath: str, args):
    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    log_hnd_screen = logging.StreamHandler(stream=sys.stdout)
    log_hnd_screen.setLevel(logging.ERROR)
    if args.verbose:
        log_hnd_screen.setLevel(logging.DEBUG)
    log_hnd_screen.setFormatter(log_formatter)
    logger.addHandler(log_hnd_screen)

    if not os.path.exists(logpath):
        os.mkdir(logpath)

    log_hnd_file = logging.FileHandler(
        filename=logpath + datetime.now().strftime("%Y-%m-%d_%H%M") + ".log",
        mode="w",
        encoding="utf-8",
    )
    log_hnd_file.setLevel(logging.DEBUG)
    log_hnd_file.setFormatter(log_formatter)
    logger.addHandler(log_hnd_file)
    return logger


def init_db(dbconfig):
    # Connect to MySQL
    # Mark all playlist entries as unprocessed
    db = pymysql.connect(
        host=dbconfig["hostname"],
        user=dbconfig["username"],
        password=dbconfig["password"],
        db=dbconfig["database"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

    cursor = db.cursor()

    sql_modes = ['ERROR_FOR_DIVISION_BY_ZERO', 'NO_ZERO_DATE', 'NO_ZERO_IN_DATE', 'STRICT_ALL_TABLES',
                 'ONLY_FULL_GROUP_BY', 'NO_ENGINE_SUBSTITUTION']
    sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sql_modes) + "'"
    cursor.execute(sql)
    return db, cursor


def fetch_all_playlists(ytmusic, cursor, logger):
    playlists = ytmusic.get_library_playlists()

    for pl in playlists:
        if pl["playlistId"] == "LM":
            continue
        logger.info("processing playlist: " + pl["playlistId"] + " :: " + pl["title"])
        fetch_playlist(ytmusic, cursor, logger, pl["playlistId"])


def fetch_playlist(ytmusic, cursor, logger, playlistid: str):
    pldata = ytmusic.get_playlist(playlistid, 50000)

    pldata_keys = []
    for key in pldata.keys():
        if key not in pldata_keys:
            pldata_keys.append(key)

    logger.debug("pldata keys: " + ", ".join(pldata_keys))

    upsert_playlist(pldata, cursor)

    pltrack_keys = []
    for pltrack in pldata["tracks"]:
        for key in pltrack.keys():
            if key not in pltrack_keys:
                pltrack_keys.append(key)

        upsert_playlist_entry(pldata["id"], pltrack, cursor, logger)

    logger.debug("pltrack keys: " + ", ".join(pltrack_keys))


def upsert_playlist(plentry, cursor):
    sql = """
        INSERT INTO `ytm_playlists`
        (`ytm_playlistid`, `dt_plt_created`, `playlist_title`, `track_count`, `processed`)
        VALUES (%(ytmid)s, NOW(), %(name)s, %(trackCount)s, 1)
        ON DUPLICATE KEY UPDATE
            `playlistid` = LAST_INSERT_ID(`playlistid`),
            `deleted` = 0,
            `processed` = 1,
            `playlist_title` = %(name)s,
            `track_count` = %(trackCount)s
    """
    pl_record = {
        "ytmid": plentry["id"],
        "name": plentry["title"],
        "trackCount": plentry["trackCount"],
    }
    cursor.execute(sql, pl_record)


def upsert_playlist_entry(ytm_playlist_id, plentry, cursor, logger):
    if 'setVideoId' not in plentry:
        logger.warning("Missing setVideoId for entry in playlist id " + ytm_playlist_id)
        logger.warning(pformat(plentry))
        upsert_playlist_entry_unavailable(ytm_playlist_id, plentry, cursor, logger)
        return

    artist_names = []
    if plentry["artists"] is not None:
        for artistEntry in plentry["artists"]:
            artist_names.append(artistEntry["name"])
    else:
        logger.debug("No artist data")
        logger.debug(pformat(plentry))

    unavailable = (plentry["videoId"] is None)

    if plentry["duration"] is not None:
        parts = plentry["duration"].split(":")
        if len(parts) == 1:
            plentry["duration"] = "00:00" + plentry["duration"]
        elif len(parts) == 2:
            plentry["duration"] = "00:" + plentry["duration"]

    album_name = None
    if plentry["album"] is None:
        logger.warning("No album data")
        logger.warning(pformat(plentry))
    else:
        album_name = plentry["album"]["name"]

    sql = """
        INSERT INTO `ytm_playlist_entries`
        (`ytm_playlistid`, `ytm_set_videoid`, `ytm_videoid`, `dt_plt_created`, 
            `artist_name`, `album_name`, `entry_name`, `duration`, `unavailable`, `processed`)
        VALUES (%(ytmplid)s, %(setVideoId)s, %(videoId)s, NOW(), 
            %(artistName)s, %(albumName)s, %(entryName)s, %(duration)s, %(unavailable)s, 1)
        ON DUPLICATE KEY UPDATE
         `entryid` = LAST_INSERT_ID(`entryid`),
         `deleted` = 0,
         `processed` = 1,
         `ytm_videoid` = %(videoId)s,
         `artist_name` = %(artistName)s,
         `album_name` = %(albumName)s,
         `entry_name` = %(entryName)s,
         `duration` = %(duration)s,
         `unavailable` = %(unavailable)s
    """
    plentry_record = {
        "ytmplid": ytm_playlist_id,
        "setVideoId": plentry["setVideoId"],
        "videoId": plentry["videoId"],
        "artistName": "|".join(artist_names),
        "albumName": album_name,
        "entryName": plentry["title"],
        "duration": plentry["duration"],
        "unavailable": unavailable,
    }
    cursor.execute(sql, plentry_record)

    upsert_playlist_video(plentry, cursor)


def upsert_playlist_entry_unavailable(ytm_playlist_id, plentry, cursor, logger):
    artist_names = []
    if plentry["artists"] is not None:
        for artistEntry in plentry["artists"]:
            artist_names.append(artistEntry["name"])
    else:
        logger.debug("No artist data")
        logger.debug(pformat(plentry))

    album_name = None
    if plentry["album"] is None:
        logger.warning("No album data")
        logger.warning(pformat(plentry))
    else:
        album_name = plentry["album"]["name"]

    if plentry["duration"] is not None:
        parts = plentry["duration"].split(":")
        if len(parts) == 1:
            plentry["duration"] = "00:00" + plentry["duration"]
        elif len(parts) == 2:
            plentry["duration"] = "00:" + plentry["duration"]

    sql = """
        INSERT INTO `ytm_playlist_entries_unavailable`
        (`ytm_playlistid`, `dt_plt_created`, 
            `artist_name`, `album_name`, `entry_name`, `duration`, `processed`)
        VALUES (%(ytmplid)s, NOW(), 
            %(artistName)s, %(albumName)s, %(entryName)s, %(duration)s, 1)
        ON DUPLICATE KEY UPDATE
         `uentryid` = LAST_INSERT_ID(`uentryid`),
         `deleted` = 0,
         `processed` = 1,
         `artist_name` = %(artistName)s,
         `album_name` = %(albumName)s,
         `entry_name` = %(entryName)s,
         `duration` = %(duration)s
    """
    plentry_record = {
        "ytmplid": ytm_playlist_id,
        "artistName": "|".join(artist_names),
        "albumName": album_name,
        "entryName": plentry["title"],
        "duration": plentry["duration"],
    }
    cursor.execute(sql, plentry_record)


def upsert_playlist_video(plentry, cursor):
    if plentry["videoId"] is None:
        return

    sql = """
        INSERT INTO `ytm_videos`
        (`ytm_videoid`, `video_title`, `duration`, `like_status`)
        VALUES (%(videoId)s, %(title)s, %(duration)s, %(likeStatus)s)
        ON DUPLICATE KEY UPDATE
            `vid` = LAST_INSERT_ID(`vid`),
            `video_title` = %(title)s,
            `duration` = %(duration)s,
            `like_status` = %(likeStatus)s
    """
    video_record = {
        "videoId": plentry["videoId"],
        "title": plentry["title"],
        "duration": plentry["duration"],
        "likeStatus": plentry["likeStatus"],
    }
    cursor.execute(sql, video_record)
    videoid = cursor.lastrowid

    upsert_playlist_video_artists(videoid, plentry["artists"], cursor)
    upsert_playlist_video_album(videoid, plentry["album"], cursor)


def upsert_playlist_video_artists(videoid, artists, cursor):
    if artists is None:
        return

    # Theoretically the artist id linked to a video could change
    # TODO Handle deleting links between artists and videos (and deleting artists) when artist (channel) changes
    for artist in artists:
        if artist["id"] is None:
            continue

        sql = """
            INSERT INTO `ytm_artists`
                (`ytm_channelid`, `artist_name`)
                VALUES (%(channelId)s, %(name)s)
            ON DUPLICATE KEY UPDATE
                `artistid` = LAST_INSERT_ID(`artistid`),
                `artist_name` = %(name)s
        """
        artist_record = {
            "channelId": artist["id"],
            "name": artist["name"],
        }
        cursor.execute(sql, artist_record)
        artistid = cursor.lastrowid

        sql = """
            INSERT INTO `ytm_video_artists`
                (`videoid`, `artistid`)
                VALUES (%(videoId)s, %(artistId)s)
            ON DUPLICATE KEY UPDATE
                `linkid` = LAST_INSERT_ID(`linkid`)
        """
        link_record = {
            "videoId": videoid,
            "artistId": artistid,
        }
        cursor.execute(sql, link_record)


def upsert_playlist_video_album(videoid, album, cursor):
    if album is None:
        return

    sql = """
        INSERT INTO `ytm_albums`
            (`ytm_browseid`, `album_name`)
            VALUES (%(browseId)s, %(albumName)s)
        ON DUPLICATE KEY UPDATE
            `albumid` = LAST_INSERT_ID(`albumid`),
            `album_name` = %(albumName)s
    """
    album_record = {
        "browseId": album["id"],
        "albumName": album["name"],
    }
    cursor.execute(sql, album_record)
    albumid = cursor.lastrowid

    sql = """
        INSERT INTO `ytm_video_albums`
            (`videoid`, `albumid`)
            VALUES (%(videoId)s, %(albumId)s)
        ON DUPLICATE KEY UPDATE
            `linkid` = LAST_INSERT_ID(`linkid`)
    """
    link_record = {
        "videoId": videoid,
        "albumId": albumid,
    }
    cursor.execute(sql, link_record)


def notify_deleted(smtp_config, cursor, logger):
    sql = """
        SELECT ytm_playlist_entries.artist_name, ytm_playlist_entries.album_name, ytm_playlist_entries.entry_name,
            ytm_playlist_entries.duration, ytm_playlist_entries.unavailable, ytm_playlist_entries.prev_unavailable,
            ytm_playlists.playlist_title
        FROM ytm_playlist_entries
        LEFT JOIN ytm_playlists ON ytm_playlist_entries.ytm_playlistid = ytm_playlists.ytm_playlistid
        WHERE (
            (
                ytm_playlist_entries.deleted = 0
                AND ytm_playlist_entries.processed = 0
            )
            OR (
                ytm_playlist_entries.unavailable = 1
                AND ytm_playlist_entries.prev_unavailable = 0
            )
        )
        AND ytm_playlists.deleted = 0
        AND ytm_playlists.playlist_title NOT LIKE '%BG Rand%'
    """
    cursor.execute(sql)
    deleted_entries = cursor.fetchall()

    if len(deleted_entries) == 0:
        logger.info("No deleted entries found - no email sent")
        return

    html_content = """
        <html><body><p>Deleted Playlist Entries:</p>
        <table>
        <thead>
        <tr>
            <th class="title">Track Title</th>
            <th class="artist">Track Artist</th>
            <th class="duration number">Duration</th>
            <th class="playlist_name">Playlist</th>
            <th class="unavailable">Unavailable</th>
        </tr>
        </thead>
        <tbody>
    """

    for trackEntry in deleted_entries:
        html_content += """
            <tr>
                <td class="title">{entry_name}<br />{album_name}</td>
                <td class="artist">{artist_name}</td>
                <td class="duration number">{duration}</td>
                <td class="playlist_name">{playlist_title}</td>
                <td class="unavailable">{prev_unavailable} => {unavailable}</td>
            </tr>
        """.format(**trackEntry)

    html_content += "</tbody></table><p>---EOM---</p></body></html>"

    msg = EmailMessage()
    msg['Subject'] = 'PLT: YTM Playlist Entry Deletions'
    msg['From'] = 'lister@allenjb.me.uk'
    msg['To'] = 'plt@allenjb.me.uk'
    msg.set_content("See HTML version")
    msg.add_alternative(html_content, subtype='html')

    s = smtplib.SMTP(host=smtp_config["host"], port=smtp_config["port"])
    s.login(user=smtp_config["username"], password=smtp_config["password"])
    s.send_message(msg)
    s.quit()


def delete_unprocessed_playlists(cursor, logger):
    sql = """
        UPDATE `ytm_playlists`
        SET `deleted` = 1, `dt_plt_deleted` = NOW()
        WHERE `processed` = 0
            AND `deleted` = 0
    """
    deleted = cursor.execute(sql)
    logger.info("deleted playlists: " + str(deleted))


def delete_unprocessed_playlist_entries(cursor, logger):
    sql = """
        UPDATE `ytm_playlist_entries`
        SET `deleted` = 1, `dt_plt_deleted` = NOW()
        WHERE `processed` = 0
            AND `deleted` = 0
    """
    deleted = cursor.execute(sql)
    logger.info("deleted playlist entries: " + str(deleted))

    sql = """
        UPDATE `ytm_playlist_entries_unavailable`
        SET `deleted` = 1, `dt_plt_deleted` = NOW()
        WHERE `processed` = 0
            AND `deleted` = 0
    """
    deleted = cursor.execute(sql)
    logger.info("deleted unavailable playlist entries: " + str(deleted))


main()
exit()
