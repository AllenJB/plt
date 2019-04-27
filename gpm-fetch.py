from datetime import datetime
from gmusicapi import Mobileclient
from gmusicapi.utils import utils
from pprint import pprint
import argparse
import logging
import pymysql.cursors
import sys
import config


def convert_timestamp(timestamp: str) -> str:
    """Convert a timestamp (string, with ms) to a MySQL datetime value"""
    return datetime.utcfromtimestamp(int(timestamp) / 1000000).strftime("%Y-%m-%d %H:%M:%S")


parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
args = parser.parse_args()

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

logHndFile = logging.FileHandler(
    filename=config.log["dir"] + "gpm_fetch.log",
    mode="w"
)
logHndFile.setLevel(logging.DEBUG)
logHndFile.setFormatter(logFormatter)
logger.addHandler(logHndFile)

logHndScreen = logging.StreamHandler(stream=sys.stdout)
logHndScreen.setLevel(logging.ERROR)
if args.verbose:
    logHndScreen.setLevel(logging.DEBUG)
logHndScreen.setFormatter(logFormatter)
logger.addHandler(logHndScreen)

logger.info("gmusicapi log: " + utils.log_filepath)

gpm = Mobileclient()
gpm.oauth_login(Mobileclient.FROM_MAC_ADDRESS)

if not gpm.is_authenticated():
    logger.error("Login failed")
    exit()

# lists = gpm.get_all_playlists()
# print (len(lists), " playlists found")
# pprint(lists)

# Connect to MySQL
# Mark all playlist entries as unprocessed
db = pymysql.connect(
    host=config.db["hostname"],
    user=config.db["username"],
    password=config.db["password"],
    db=config.db["database"],
    autocommit=True
)

cursor = db.cursor()

sqlModes = ['ERROR_FOR_DIVISION_BY_ZERO', 'NO_ZERO_DATE', 'NO_ZERO_IN_DATE', 'STRICT_ALL_TABLES',
            'ONLY_FULL_GROUP_BY', 'NO_AUTO_CREATE_USER', 'NO_ENGINE_SUBSTITUTION']
sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sqlModes) + "'"
cursor.execute(sql)

sql = "UPDATE `gpm_playlist_entries` SET `processed` = 0 WHERE 1=1"
cursor.execute(sql)

# Process playlists & entries
plcontents = gpm.get_all_user_playlist_contents()
# pprint(plcontents)

seenDeleted = 0
plKeys = []
plentryKeys = []
pltrackKeys = []

lastArtistIds = None
lastAlbumId = None

albumId = None
for pl in plcontents:
    for key in pl.keys():
        if key not in plKeys:
            plKeys.append(key)

    # plDump = pl.copy()
    # plDump["tracks"] = False
    # pprint(plDump)

    sql = """
        INSERT INTO `gpm_playlists`
        (`gpm_playlistid`, `dt_created`, `dt_modified`, `deleted`, `dt_recent`, `access_controlled`, `kind`, 
            `name`, `description`, `owner_name`, `share_token`, `type`)
        VALUES (%(gpmid)s, %(dtCreated)s, %(dtModified)s, %(deleted)s, %(dtRecent)s, %(accessControlled)s, %(kind)s,
            %(name)s, %(description)s, %(ownerName)s, %(shareToken)s, %(type)s)
        ON DUPLICATE KEY UPDATE `playlistid` = LAST_INSERT_ID(`playlistid`),
          `name` = %(name)s, `description` = %(description)s, 
          `dt_modified` = %(dtModified)s, `dt_recent` = %(dtRecent)s, `deleted` = %(deleted)s
    """
    plRecord = {
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
    # pprint(plRecord)
    cursor.execute(sql, plRecord)
    plId = cursor.lastrowid
    iTrack = 0

    for plentry in pl["tracks"]:
        for key in plentry.keys():
            if key not in plentryKeys:
                plentryKeys.append(key)

        iTrack += 1
        if ((iTrack - 1) % 50 == 0) or (iTrack == len(pl["tracks"])):
            logger.info(pl["name"] + ": " + str(iTrack) + " of " + str(len(pl["tracks"])))

        # pprint(plentry)
        # UPSERT playlist_entries
        if plentry["deleted"]:
            # entry will be deleted along with any omitted ones at the end of the script
            seenDeleted += 1
            continue

        # UPSERT track
        sql = """
            INSERT INTO `gpm_playlist_entries`
            (`gpm_entryid`, `dt_created`, `dt_modified`, `absolute_position`, `clientid`, `kind`, 
                `gpm_playlistid`, `source`, `gpm_trackid`, `processed`)
            VALUES (%(entryId)s, %(dtCreated)s, %(dtModified)s, %(absolutePos)s, %(clientId)s, %(kind)s, 
                %(gpmPlaylistId)s, %(source)s, %(gpmTrackId)s, 1)
            ON DUPLICATE KEY UPDATE
                `entryid` = LAST_INSERT_ID(`entryid`), 
                `dt_created` = %(dtCreated)s, `dt_modified` = %(dtModified)s, `processed` = 1
        """
        entryRecord = {
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
        cursor.execute(sql, entryRecord)

        if plentry.get("track", None) is None:
            continue

        pltrack = plentry["track"]
        for key in pltrack.keys():
            if key not in pltrackKeys:
                pltrackKeys.append(key)

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
        trackRecord = {
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
            "year": pltrack["year"],
            "rating": pltrack.get("rating", None),
        }
        cursor.execute(sql, trackRecord)
        trackId = cursor.lastrowid

        # UPSERT album
        if pltrack["albumId"] != lastAlbumId:
            lastAlbumId = pltrack["albumId"]

            sql = """
                INSERT INTO `gpm_albums` (`gpm_albumid`, `album_purchaseable`, `album`, `album_artist`)
                VALUES (%(gpmAlbumId)s, %(purchaseable)s, %(album)s, %(artist)s)
                ON DUPLICATE KEY UPDATE `albumid` = LAST_INSERT_ID(`albumid`),
                    `album` = %(album)s, `album_artist` = %(artist)s
            """
            albumRecord = {
                "gpmAlbumId": pltrack["albumId"],
                "album": pltrack["album"],
                "purchaseable": pltrack["albumAvailableForPurchase"],
                "artist": pltrack["albumArtist"],
            }
            cursor.execute(sql, albumRecord)
            albumId = cursor.lastrowid

            # UPSERT album art
            for albumArt in pltrack["albumArtRef"]:
                sql = """
                    INSERT INTO `gpm_album_art` (`albumid`, `aspect_ratio`, `autogen`, `kind`, `url`)
                    VALUES (%(albumId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
                    ON DUPLICATE KEY UPDATE `url` = %(url)s
                """
                artistArtRecord = {
                    "albumId": albumId,
                    "aspectRatio": albumArt["aspectRatio"],
                    "autogen": albumArt["autogen"],
                    "kind": albumArt["kind"],
                    "url": albumArt["url"],
                }
                cursor.execute(sql, artistArtRecord)

        # UPSERT artist(s)
        # This happens for "Various Artists"
        if pltrack.get("artistId", None) is None:
            lastArtistIds = None
            continue

        if pltrack["artistId"] == lastArtistIds:
            continue

        lastArtistIds = pltrack["artistId"]

        for gpmArtistId in pltrack["artistId"]:
            sql = """
                INSERT INTO `gpm_artists` (`gpm_artistid`, `artist`)
                VALUES (%(gpmArtistId)s, %(artist)s)
                ON DUPLICATE KEY UPDATE  `artistid` = LAST_INSERT_ID(`artistid`), 
                    `artist` = %(artist)s
            """
            artistRecord = {
                "gpmArtistId": gpmArtistId,
                "artist": pltrack["artist"],
            }
            cursor.execute(sql, artistRecord)
            artistId = cursor.lastrowid

            # UPSERT artist art
            if pltrack.get("artistArtRef", None) is not None:
                for artistArt in pltrack["artistArtRef"]:
                    sql = """
                        INSERT INTO `gpm_artist_art` (`artistid`, `aspect_ratio`, `autogen`, `kind`, `url`)
                        VALUES (%(artistId)s, %(aspectRatio)s, %(autogen)s, %(kind)s, %(url)s)
                        ON DUPLICATE KEY UPDATE `url` = %(url)s
                    """
                    artistArtRecord = {
                        "artistId": artistId,
                        "aspectRatio": artistArt["aspectRatio"],
                        "autogen": artistArt["autogen"],
                        "kind": artistArt["kind"],
                        "url": artistArt["url"],
                    }
                    cursor.execute(sql, artistArtRecord)

            # UPSERT track artist(s)
            sql = """
                INSERT INTO `gpm_track_artists` (`trackid`, `albumid`, `artistid`)
                VALUES (%(trackId)s, %(albumId)s, %(artistId)s)
                ON DUPLICATE KEY UPDATE `trackid` = %(trackId)s
            """
            trackArtistRecord = {
                "trackId": trackId,
                "artistId": artistId,
                "albumId": albumId,
            }
            cursor.execute(sql, trackArtistRecord)

logger.debug("pl keys: " + ", ".join(plKeys))

logger.debug("plentry keys: " + ", ".join(plentryKeys))

logger.debug("pltrack keys: " + ", ".join(pltrackKeys))

logger.info("seen deleted entries: " + str(seenDeleted))

# Mark all unprocessed entries as deleted
sql = """
    UPDATE `gpm_playlist_entries` SET `deleted` = 1, `dt_deleted` = NOW()
    WHERE `processed` = 0
        AND `deleted` = 0
"""
deleted = cursor.execute(sql)
logger.info("deleted playlist entries: " + str(deleted))

db.close()
