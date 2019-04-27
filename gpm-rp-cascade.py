from gmusicapi import Mobileclient
from gmusicapi.utils import utils
import argparse
import logging
import pymysql.cursors
import sys
import config

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")

args = parser.parse_args()

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

logHndFile = logging.FileHandler(
    filename=config.log["dir"] + "gpm_rp-cascade.log",
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
            'ONLY_FULL_GROUP_BY', 'NO_AUTO_CREATE_USER', 'NO_ENGINE_SUBSTITUTION']
sql = "SET time_zone='+00:00', sql_mode='" + ",".join(sqlModes) + "'"
cursor.execute(sql)

# Find entries deleted from "BG Rand" playlists
sql = """
    SELECT `gpm_playlist_entries`.`dt_deleted`, `gpm_trackid`
    FROM `gpm_playlist_entries`
    JOIN `gpm_playlists` USING (`gpm_playlistid`)
    WHERE `gpm_playlist_entries`.`deleted` = 1
        AND `gpm_playlists`.`name` LIKE 'BG Rand %'
        AND `gpm_playlists`.`deleted` = 0
"""
cursor.execute(sql)
deletedTracks = cursor.fetchall()

# Foreach deleted entry, check if it's undeleted in any of the source playlists
# If so, delete it
for row in deletedTracks:
    trackId = row[0]
    sql = """
        SELECT `gpm_entryid`
        FROM `gpm_playlist_entries`
        JOIN `gpm_playlists` USING (`gpm_playlistid`)
        WHERE `gpm_playlists`.`deleted` = 0
            AND `gpm_playlists`.`name` LIKE 'Background %'
            AND `gpm_playlist_entries`.`deleted` = 0
    """
    cursor.execute(sql)
    otherListEntries = cursor.fetchall()

    if len(otherListEntries) < 1:
        continue

    logger.info("Deleted track " + trackId + " was found in another playlist... deleting")
    otherEntryIds = []
    for otherRow in otherListEntries:
        otherEntryIds.append(otherRow[0])
    gpm.remove_entries_from_playlist(otherEntryIds)

logger.info("DONE!")
