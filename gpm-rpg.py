from datetime import datetime
from gmusicapi import Mobileclient
from gmusicapi.utils import utils
from pprint import pprint
import argparse
import logging
import pymysql.cursors
import sys
import time
import config

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
parser.add_argument("--replace", help="Replace playlist if it already exists", action="store_true")
args = parser.parse_args()

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

logHndFile = logging.FileHandler(
    filename=config.log["dir"] + "gpm_rpg.log",
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
            'ONLY_FULL_GROUP_BY', 'NO_ENGINE_SUBSTITUTION']
sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sqlModes) + "'"
cursor.execute(sql)

sql = """
    SELECT `gpm_trackid`
    FROM (SELECT `gpm_playlist_entries`.gpm_trackid, `gpm_tracks`.title, `gpm_tracks`.artist, `gpm_tracks`.`year`, 
        `gpm_albums`.`album`, `gpm_albums`.`album_artist`
    FROM `gpm_playlist_entries`
    JOIN `gpm_playlists` USING (`gpm_playlistid`)
    JOIN `gpm_tracks` USING (`gpm_trackid`)
    JOIN `gpm_albums` USING (`gpm_albumid`)
    WHERE `gpm_playlists`.`name` LIKE 'Background %'
        AND `gpm_playlists`.`deleted` = 0
        AND `gpm_playlist_entries`.`deleted` = 0
    ORDER BY RAND()
    LIMIT 950) AS `t`
    ORDER BY `album_artist` ASC, `year` ASC, `album` ASC, `title` ASC
"""
cursor.execute(sql)
trackRows = cursor.fetchall()

playlistName = "BG Rand " + datetime.now().strftime("%Y-%m %B")

# Check if the playlist exists
# If it does, abort unless --replace is specified, in which case delete the old list
playlists = gpm.get_all_playlists()
for playlist in playlists:
    if playlist["deleted"]:
        continue
    if playlist["name"] == playlistName:
        if args.replace:
            logger.info("Deleting existing playlist")
            gpm.delete_playlist(playlist["id"])
        else:
            logger.error("Playlist already exists: " + playlistName)
            exit(1)

logger.info("Creating playlist: " + playlistName)
playlistId = gpm.create_playlist(playlistName, description="Autogenerated by RPG", public=False)

logger.info("Adding " + str(len(trackRows)) + " tracks to playlist")

trackIds = []
for row in trackRows:
    trackIds.append(row[0])

    if len(trackIds) >= 50:
        gpm.add_songs_to_playlist(playlist_id=playlistId, song_ids=trackIds)
        trackIds = []
        logger.debug("Added 50 tracks to playlist")
        time.sleep(10)


if len(trackIds) > 0:
    gpm.add_songs_to_playlist(playlist_id=playlistId, song_ids=trackIds)
    logger.debug("Added remaining " + str(len(trackIds)) + " tracks to playlist")

logger.info("DONE!")
db.close()
