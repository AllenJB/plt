import argparse
from datetime import datetime
import logging
import os
from pprint import pformat
import smtplib
import sys
from email.message import EmailMessage
from gmusicapi import Mobileclient
from gmusicapi.utils import utils
import pymysql.cursors
import config


def convert_timestamp(timestamp: str) -> str:
    """Convert a timestamp (string, with ms) to a MySQL datetime value"""
    return datetime.utcfromtimestamp(int(timestamp) / 1000000).strftime("%Y-%m-%d %H:%M:%S")


def fetch_uploaded_tracks(gpm, cursor, logger):
    uploaded_tracks = gpm.get_all_songs()

    current_album_id = None
    last_album_id = None
    last_artist_ids = None
    i_track = 0

    for pltrack in uploaded_tracks:
        i_track += 1
        if ((i_track - 1) % 50 == 0) or (i_track == len(uploaded_tracks)):
            logger.info("User Uploaded: " + str(i_track) + " of " + str(len(uploaded_tracks)))

        if pltrack.get("year", None) == 0:
            pltrack["year"] = None

        sql = """
            INSERT INTO `gpm_tracks`
            (`gpm_trackid`, `gpm_albumid`, `artist`, `composer`, `disc_number`, `duration_millis`, 
                `est_size`,`explicit_type`, `genre`, `kind`, `nid`, `play_count`, `storeid`, `title`, 
                `track_purchaseable`, `track_subscribable`, `track_num`, `track_type`, `year`, `rating`)
            VALUES (%(gpmTrackId)s, %(gpmAlbumId)s, %(artist)s, %(composer)s, %(discNum)s, %(durationMillis)s, 
                %(estSize)s, %(explicitType)s, %(genre)s, %(kind)s, %(nid)s, %(playCount)s, %(storeId)s, %(title)s,
                %(purchaseable)s, %(subscribable)s, %(trackNum)s, %(trackType)s, %(year)s, %(rating)s)
            ON DUPLICATE KEY UPDATE
                `trackid` = LAST_INSERT_ID(`trackid`), `artist` = %(artist)s, `composer` = %(composer)s, 
                `duration_millis` = %(durationMillis)s, `genre` = %(genre)s, `play_count` = %(playCount)s, 
                `title` = %(title)s, `rating` = %(rating)s
        """
        track_record = {
            "gpmTrackId": pltrack["id"],
            "gpmAlbumId": pltrack.get("albumId", None),
            "artist": pltrack["artist"],
            "composer": pltrack.get("composer", None),
            "discNum": pltrack["discNumber"],
            "durationMillis": pltrack["durationMillis"],
            "estSize": pltrack["estimatedSize"],
            "explicitType": None,
            "genre": pltrack.get("genre", None),
            "kind": pltrack["kind"],
            "nid": pltrack.get("nid", None),
            "playCount": pltrack.get("playCount", 0),
            "storeId": None,
            "title": pltrack["title"],
            "purchaseable": False,
            "subscribable": False,
            "trackNum": pltrack["trackNumber"],
            "trackType": None,
            "year": pltrack.get("year", None),
            "rating": pltrack.get("rating", None),
        }
        cursor.execute(sql, track_record)
        track_id = cursor.lastrowid

        # UPSERT album
        if (pltrack.get("albumId", None) is not None) and (pltrack["albumId"] != last_album_id):
            last_album_id = pltrack["albumId"]

            sql = """
                INSERT INTO `gpm_albums` (`gpm_albumid`, `album_purchaseable`, `album`, `album_artist`)
                VALUES (%(gpmAlbumId)s, %(purchaseable)s, %(album)s, %(artist)s)
                ON DUPLICATE KEY UPDATE `albumid` = LAST_INSERT_ID(`albumid`),
                    `album` = %(album)s, `album_artist` = %(artist)s
            """
            album_record = {
                "gpmAlbumId": pltrack["albumId"],
                "album": pltrack["album"],
                "purchaseable": False,
                "artist": pltrack["albumArtist"],
            }
            cursor.execute(sql, album_record)
            current_album_id = cursor.lastrowid

            # UPSERT album art
            if pltrack.get("albumArtRef", None) is not None:
                for album_art in pltrack["albumArtRef"]:
                    sql = """
                        INSERT INTO `gpm_album_art` (`albumid`, `aspect_ratio`, `autogen`, `kind`, `url`)
                        VALUES (%(albumId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
                        ON DUPLICATE KEY UPDATE `url` = %(url)s
                    """
                    artist_art_record = {
                        "albumId": current_album_id,
                        "aspectRatio": album_art.get("aspectRatio", 0),
                        "autogen": album_art.get("autogen", False),
                        "kind": album_art["kind"],
                        "url": album_art["url"],
                    }
                    cursor.execute(sql, artist_art_record)

        # UPSERT artist(s)
        # This happens for "Various Artists"
        if pltrack.get("artistId", None) is None:
            last_artist_ids = None
            continue

        if pltrack["artistId"] == last_artist_ids:
            continue

        last_artist_ids = pltrack["artistId"]

        for gpm_artist_id in pltrack["artistId"]:
            sql = """
                INSERT INTO `gpm_artists` (`gpm_artistid`, `artist`)
                VALUES (%(gpmArtistId)s, %(artist)s)
                ON DUPLICATE KEY UPDATE  `artistid` = LAST_INSERT_ID(`artistid`), 
                    `artist` = %(artist)s
            """
            artist_record = {
                "gpmArtistId": gpm_artist_id,
                "artist": pltrack["artist"],
            }
            cursor.execute(sql, artist_record)
            artist_id = cursor.lastrowid

            # UPSERT artist art
            if pltrack.get("artistArtRef", None) is not None:
                for artistArt in pltrack["artistArtRef"]:
                    sql = """
                        INSERT INTO `gpm_artist_art` (`artistid`, `aspect_ratio`, `autogen`, `kind`, `url`)
                        VALUES (%(artistId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
                        ON DUPLICATE KEY UPDATE `url` = %(url)s
                    """
                    artist_art_record = {
                        "artistId": artist_id,
                        "aspectRatio": artistArt.get("aspectRatio", 0),
                        "autogen": artistArt.get("autogen", False),
                        "kind": artistArt["kind"],
                        "url": artistArt["url"],
                    }
                    cursor.execute(sql, artist_art_record)

            # UPSERT track artist(s)
            sql = """
                INSERT INTO `gpm_track_artists` (`trackid`, `albumid`, `artistid`)
                VALUES (%(trackId)s, %(albumId)s, %(artistId)s)
                ON DUPLICATE KEY UPDATE `trackid` = %(trackId)s
            """
            track_artist_record = {
                "trackId": track_id,
                "artistId": artist_id,
                "albumId": current_album_id,
            }
            cursor.execute(sql, track_artist_record)

    logger.info("User Uploaded: " + str(i_track) + " of " + str(len(uploaded_tracks)))


def fetch_playlist_tracks(gpm, cursor, logger, only_list_id):
    plcontents = gpm.get_all_user_playlist_contents()

    seen_deleted = 0
    pl_keys = []
    plentry_keys = []
    pltrack_keys = []

    last_artist_ids = None
    last_album_id = None

    album_id = None
    for pl in plcontents:
        if (only_list_id is not None) and (pl["id"] != only_list_id):
            logger.debug("Skipping list: " + pl["id"] + ": " + pl["name"])
            continue

        for key in pl.keys():
            if key not in pl_keys:
                pl_keys.append(key)

        upsert_playlist(pl, cursor)
        i_track = 0

        for plentry in pl["tracks"]:
            for key in plentry.keys():
                if key not in plentry_keys:
                    plentry_keys.append(key)

            i_track += 1
            if ((i_track - 1) % 50 == 0) or (i_track == len(pl["tracks"])):
                logger.info(pl["name"] + ": " + str(i_track) + " of " + str(len(pl["tracks"])))

            # UPSERT playlist_entries
            if plentry["deleted"]:
                # entry will be deleted along with any omitted ones at the end of the script
                seen_deleted += 1
                continue

            # UPSERT track
            upsert_playlist_entry(plentry, pl, cursor)

            if plentry.get("track", None) is None:
                # If we already know this track, skip the error message
                sql = """
                    SELECT * FROM gpm_tracks WHERE gpm_trackid = %(trackId)s
                """
                params = {
                    "trackId": plentry["trackId"]
                }
                cursor.execute(sql, params)
                existingentries = cursor.fetchall()
                if len(existingentries) < 1:
                    logger.error("No track data")
                    logger.error(pformat(plentry))
                else:
                    logger.debug("No track data (track known)")
                    logger.debug(pformat(plentry))

                continue

            if plentry["track"]["title"] is None:
                logger.error("Track with NULL track title")
                logger.error(pformat(plentry))

            pltrack = plentry["track"]
            for key in pltrack.keys():
                if key not in pltrack_keys:
                    pltrack_keys.append(key)

            track_id = upsert_track(pltrack, plentry, cursor)

            # UPSERT album
            if pltrack["albumId"] != last_album_id:
                last_album_id = pltrack["albumId"]
                album_id = upsert_album(pltrack, cursor)

            # UPSERT artist(s)
            # This happens for "Various Artists"
            if pltrack.get("artistId", None) is None:
                last_artist_ids = None
                continue

            if pltrack["artistId"] == last_artist_ids:
                continue

            last_artist_ids = pltrack["artistId"]
            upsert_artists(pltrack, track_id, album_id, cursor)

    logger.debug("pl keys: " + ", ".join(pl_keys))
    logger.debug("plentry keys: " + ", ".join(plentry_keys))
    logger.debug("pltrack keys: " + ", ".join(pltrack_keys))
    logger.info("seen deleted entries: " + str(seen_deleted))


def upsert_playlist(pl, cursor):
    sql = """
        INSERT INTO `gpm_playlists`
        (`gpm_playlistid`, `dt_created`, `dt_modified`, `deleted`, `dt_recent`, `access_controlled`, `kind`, 
            `name`, `description`, `owner_name`, `share_token`, `type`, `processed`)
        VALUES (%(gpmid)s, %(dtCreated)s, %(dtModified)s, %(deleted)s, %(dtRecent)s, %(accessControlled)s, %(kind)s,
            %(name)s, %(description)s, %(ownerName)s, %(shareToken)s, %(type)s, 1)
        ON DUPLICATE KEY UPDATE `playlistid` = LAST_INSERT_ID(`playlistid`),
          `name` = %(name)s, `description` = %(description)s, 
          `dt_modified` = %(dtModified)s, `dt_recent` = %(dtRecent)s, `deleted` = %(deleted)s,
          `processed` = 1
    """
    pl_record = {
        "gpmid": pl["id"],
        "dtCreated": convert_timestamp(pl["creationTimestamp"]),
        "dtModified": convert_timestamp(pl["lastModifiedTimestamp"]),
        "deleted": pl["deleted"],
        "dtRecent": convert_timestamp(pl["recentTimestamp"]),
        "accessControlled": pl["accessControlled"],
        "kind": pl["kind"],
        "name": pl["name"],
        "ownerName": pl["ownerName"],
        "shareToken": pl["shareToken"],
        "type": pl["type"],
        "description": pl.get("description", None),
    }
    cursor.execute(sql, pl_record)


def upsert_playlist_entry(plentry, pl, cursor):
    sql = """
        INSERT INTO `gpm_playlist_entries`
        (`gpm_entryid`, `dt_created`, `dt_modified`, `absolute_position`, `clientid`, `kind`, 
            `gpm_playlistid`, `source`, `gpm_trackid`, `processed`)
        VALUES (%(entryId)s, %(dtCreated)s, %(dtModified)s, %(absolutePos)s, %(clientId)s, %(kind)s, 
            %(gpmPlaylistId)s, %(source)s, %(gpmTrackId)s, 1)
        ON DUPLICATE KEY UPDATE
            `entryid` = LAST_INSERT_ID(`entryid`), 
            `dt_created` = %(dtCreated)s, `dt_modified` = %(dtModified)s, `deleted` = 0, `processed` = 1
    """
    entry_record = {
        "entryId": plentry["id"],
        "absolutePos": plentry["absolutePosition"],
        "dtCreated": convert_timestamp(plentry["creationTimestamp"]),
        "dtModified": convert_timestamp(plentry["lastModifiedTimestamp"]),
        "clientId": plentry["clientId"],
        "kind": plentry["kind"],
        "gpmPlaylistId": pl["id"],
        "source": plentry["source"],
        "gpmTrackId": plentry["trackId"],
    }
    cursor.execute(sql, entry_record)


def upsert_track(pltrack, plentry, cursor):
    sql = """
        INSERT INTO `gpm_tracks`
        (`gpm_trackid`, `gpm_albumid`, `artist`, `composer`, `disc_number`, `duration_millis`, 
            `est_size`,`explicit_type`, `genre`, `kind`, `nid`, `play_count`, `storeid`, `title`, 
            `track_purchaseable`, `track_subscribable`, `track_num`, `track_type`, `year`, `rating`)
        VALUES (%(gpmTrackId)s, %(gpmAlbumId)s, %(artist)s, %(composer)s, %(discNum)s, %(durationMillis)s, 
            %(estSize)s, %(explicitType)s, %(genre)s, %(kind)s, %(nid)s, %(playCount)s, %(storeId)s, %(title)s,
            %(purchaseable)s, %(subscribable)s, %(trackNum)s, %(trackType)s, %(year)s, %(rating)s)
        ON DUPLICATE KEY UPDATE
            `trackid` = LAST_INSERT_ID(`trackid`), `artist` = %(artist)s, `composer` = %(composer)s, 
            `duration_millis` = %(durationMillis)s, `genre` = %(genre)s, `play_count` = %(playCount)s, 
            `title` = %(title)s, `rating` = %(rating)s
    """
    track_record = {
        "gpmTrackId": plentry["trackId"],
        "gpmAlbumId": pltrack["albumId"],
        "artist": pltrack["artist"],
        "composer": pltrack["composer"],
        "discNum": pltrack["discNumber"],
        "durationMillis": pltrack["durationMillis"],
        "estSize": pltrack["estimatedSize"],
        "explicitType": pltrack["explicitType"],
        "genre": pltrack.get("genre", None),
        "kind": pltrack["kind"],
        "nid": pltrack["nid"],
        "playCount": pltrack.get("playCount", 0),
        "storeId": pltrack["storeId"],
        "title": pltrack["title"],
        "purchaseable": pltrack["trackAvailableForPurchase"],
        "subscribable": pltrack["trackAvailableForSubscription"],
        "trackNum": pltrack["trackNumber"],
        "trackType": pltrack["trackType"],
        "year": pltrack.get("year", None),
        "rating": pltrack.get("rating", None),
    }
    cursor.execute(sql, track_record)
    return cursor.lastrowid


def upsert_album(pltrack, cursor):
    sql = """
        INSERT INTO `gpm_albums` (`gpm_albumid`, `album_purchaseable`, `album`, `album_artist`)
        VALUES (%(gpmAlbumId)s, %(purchaseable)s, %(album)s, %(artist)s)
        ON DUPLICATE KEY UPDATE `albumid` = LAST_INSERT_ID(`albumid`),
            `album` = %(album)s, `album_artist` = %(artist)s
    """
    album_record = {
        "gpmAlbumId": pltrack["albumId"],
        "album": pltrack["album"],
        "purchaseable": pltrack["albumAvailableForPurchase"],
        "artist": pltrack["albumArtist"],
    }
    cursor.execute(sql, album_record)
    album_id = cursor.lastrowid

    upsert_album_art(pltrack, album_id, cursor)
    return album_id


def upsert_album_art(pltrack, album_id, cursor):
    # UPSERT album art
    for albumArt in pltrack["albumArtRef"]:
        sql = """
            INSERT INTO `gpm_album_art` (`albumid`, `aspect_ratio`, `autogen`, `kind`, `url`)
            VALUES (%(albumId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
            ON DUPLICATE KEY UPDATE `url` = %(url)s
        """
        artist_art_record = {
            "albumId": album_id,
            "aspectRatio": albumArt["aspectRatio"],
            "autogen": albumArt["autogen"],
            "kind": albumArt["kind"],
            "url": albumArt["url"],
        }
        cursor.execute(sql, artist_art_record)


def upsert_artists(pltrack, track_id, album_id, cursor):
    for gpmArtistId in pltrack["artistId"]:
        sql = """
            INSERT INTO `gpm_artists` (`gpm_artistid`, `artist`)
            VALUES (%(gpmArtistId)s, %(artist)s)
            ON DUPLICATE KEY UPDATE  `artistid` = LAST_INSERT_ID(`artistid`), 
                `artist` = %(artist)s
        """
        artist_record = {
            "gpmArtistId": gpmArtistId,
            "artist": pltrack["artist"],
        }
        cursor.execute(sql, artist_record)
        artist_id = cursor.lastrowid

        # UPSERT artist art
        if pltrack.get("artistArtRef", None) is not None:
            for artistArt in pltrack["artistArtRef"]:
                sql = """
                    INSERT INTO `gpm_artist_art` (`artistid`, `aspect_ratio`, `autogen`, `kind`, `url`)
                    VALUES (%(artistId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
                    ON DUPLICATE KEY UPDATE `url` = %(url)s
                """
                artist_art_record = {
                    "artistId": artist_id,
                    "aspectRatio": artistArt["aspectRatio"],
                    "autogen": artistArt["autogen"],
                    "kind": artistArt["kind"],
                    "url": artistArt["url"],
                }
                cursor.execute(sql, artist_art_record)

        # UPSERT track artist(s)
        sql = """
            INSERT INTO `gpm_track_artists` (`trackid`, `albumid`, `artistid`)
            VALUES (%(trackId)s, %(albumId)s, %(artistId)s)
            ON DUPLICATE KEY UPDATE `trackid` = %(trackId)s
        """
        track_artist_record = {
            "trackId": track_id,
            "artistId": artist_id,
            "albumId": album_id,
        }
        cursor.execute(sql, track_artist_record)


def convert_millis(millis):
    seconds = int((millis / 1000) % 60)
    minutes = int((millis / (1000 * 60)) % 60)
    hours = int((millis / (1000 * 60 * 60)) % 24)
    if hours >= 1:
        return "{0:02d}:{1:02d}:{2:02d}".format(hours, minutes, seconds)
    return "{1:d}:{2:02d}".format(hours, minutes, seconds)


def notify_deleted(smtp_config, cursor, logger):
    sql = """
        SELECT gpm_tracks.title, gpm_tracks.track_type, gpm_tracks.duration_millis, gpm_tracks.artist,
            gpm_playlist_entries.gpm_playlistid, gpm_playlists.`name` AS `playlist_name`,
            gpm_playlist_entries.dt_deleted,
            gpm_albums.album, gpm_albums.album_artist
        FROM gpm_playlist_entries
        LEFT JOIN gpm_playlists ON gpm_playlist_entries.gpm_playlistid = gpm_playlists.gpm_playlistid
        LEFT JOIN gpm_tracks ON gpm_playlist_entries.gpm_trackid = gpm_tracks.gpm_trackid
        LEFT JOIN gpm_albums ON gpm_tracks.gpm_albumid = gpm_albums.gpm_albumid
        WHERE gpm_playlist_entries.deleted = 0
            AND gpm_playlist_entries.processed = 0
            AND gpm_playlists.deleted = 0
            AND gpm_playlists.`name` NOT LIKE 'BG Rand%'
        ORDER BY album_artist ASC
    """
    cursor.execute(sql)
    deleted_entries = cursor.fetchall()

    if len(deleted_entries) == 0:
        return

    html_content = """
        <html><body><p>Deleted Playlist Entries:</p>
        <table>
        <thead>
        <tr>
            <th class="title">Track Title</th>
            <th class="artist">Track Artist</th>
            <th class="duration_millis number">Duration</th>
            <th class="track_type">Type</th>
            <th class="playlist_name">Playlist</th>
        </tr>
        </thead>
        <tbody>
    """

    for trackEntry in deleted_entries:
        if trackEntry["album_artist"] == trackEntry["artist"]:
            trackEntry["album_artist"] = ""

        trackEntry["duration"] = convert_millis(trackEntry["duration_millis"])

        html_content += """
            <tr>
                <td class="title">{title}<br />{album}</td>
                <td class="artist">
                    {artist}<br />
                    {album_artist}
                </td>
                <td class="duration_millis number">{duration}</td>
                <td class="type">{track_type}</td>
                <td class="playlist_name">{playlist_name}</td>
            </tr>
        """.format(**trackEntry)

    html_content += "</tbody></table><p>---EOM</p></body></html>"

    msg = EmailMessage()
    msg['Subject'] = 'GPM Playlist Entry Deletions'
    msg['From'] = 'lister@allenjb.me.uk'
    msg['To'] = 'gpm@allenjb.me.uk'
    msg.set_content("See HTML version")
    msg.add_alternative(html_content, subtype='html')

    s = smtplib.SMTP(host=smtp_config["host"], port=smtp_config["port"])
    s.login(user=smtp_config["username"], password=smtp_config["password"])
    s.send_message(msg)
    s.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("-l", "--listId", help="Playlist ID", nargs=1)
    args = parser.parse_args()

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    logpath = config.log["dir"] + "gpm_fetch/"
    if not os.path.exists(logpath):
        os.mkdir(logpath)

    log_hnd_file = logging.FileHandler(
        filename=logpath + datetime.now().strftime("%Y-%m-%d_%H%M") + ".log",
        mode="w",
    )
    log_hnd_file.setLevel(logging.DEBUG)
    log_hnd_file.setFormatter(log_formatter)
    logger.addHandler(log_hnd_file)

    log_hnd_screen = logging.StreamHandler(stream=sys.stdout)
    log_hnd_screen.setLevel(logging.ERROR)
    if args.verbose:
        log_hnd_screen.setLevel(logging.DEBUG)
    log_hnd_screen.setFormatter(log_formatter)
    logger.addHandler(log_hnd_screen)

    logger.info("gmusicapi log: " + utils.log_filepath)

    only_list_id = None
    if args.listId is not None:
        only_list_id = args.listId[0]
        logger.info("Only processing playlist id: " + only_list_id)

    gpm = Mobileclient()
    gpm.oauth_login(Mobileclient.FROM_MAC_ADDRESS)

    if not gpm.is_authenticated():
        logger.error("Login failed")
        exit()

    # Connect to MySQL
    # Mark all playlist entries as unprocessed
    db = pymysql.connect(
        host=config.db["hostname"],
        user=config.db["username"],
        password=config.db["password"],
        db=config.db["database"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

    cursor = db.cursor()

    sql_modes = ['ERROR_FOR_DIVISION_BY_ZERO', 'NO_ZERO_DATE', 'NO_ZERO_IN_DATE', 'STRICT_ALL_TABLES',
                 'ONLY_FULL_GROUP_BY', 'NO_AUTO_CREATE_USER', 'NO_ENGINE_SUBSTITUTION']
    sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sql_modes) + "'"
    cursor.execute(sql)

    sql = "UPDATE `gpm_playlists` SET `processed` = 0 WHERE 1=1"
    cursor.execute(sql)

    sql = "UPDATE `gpm_playlist_entries` SET `processed` = 0 WHERE 1=1"
    cursor.execute(sql)

    # Process uploaded tracks
    fetch_uploaded_tracks(gpm, cursor, logger)

    # Process playlists & entries
    fetch_playlist_tracks(gpm, cursor, logger, only_list_id)

    notify_deleted(config.smtp, cursor, logger)
    # Mark all unprocessed entries as deleted
    if only_list_id is None:
        sql = """
            UPDATE `gpm_playlists` SET `deleted` = 1, `dt_deleted` = NOW()
            WHERE `processed` = 0
                AND `deleted` = 0
        """
        deleted = cursor.execute(sql)
        logger.info("deleted playlists: " + str(deleted))

        sql = """
            UPDATE `gpm_playlist_entries` SET `deleted` = 1, `dt_deleted` = NOW()
            WHERE `processed` = 0
                AND `deleted` = 0
        """
        deleted = cursor.execute(sql)
        logger.info("deleted playlist entries: " + str(deleted))

    db.close()


main()
exit()
