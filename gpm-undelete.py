import os
from datetime import datetime
from gmusicapi import Mobileclient
from gmusicapi.utils import utils
import argparse
import logging
import pymysql.cursors
import sys
import config


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
parser.add_argument("-p", "--playlist", help="Playlist ID to undelete tracks from (required)", required=True)
parser.add_argument("-d", "--date", help="Undelete tracks deleted after this date/time", required=True,
                    type=valid_date)
args = parser.parse_args()

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

logpath = config.log["dir"] + "gpm_undelete/"
if not os.path.exists(logpath):
    os.mkdir(logpath)

logHndFile = logging.FileHandler(
    filename=logpath + datetime.now().strftime("%Y-%m-%d_%H%M") + ".log",
    mode="w",
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

playlistId = args.playlist
dtStrRevert = args.date

# Parameters: playlist id, date to revert to
sql = """
    SELECT gpm_trackid 
    FROM gpm_playlist_entries
    WHERE gpm_playlistid = %(playlistId)s
        AND `dt_deleted` > %(dtRevert)s
"""
params = {
    "playlistId": playlistId,
    "dtRevert": dtStrRevert,
}
cursor.execute(sql, params)
deletedTracks = cursor.fetchall()

logger.info("Undeleting " + str(len(deletedTracks)) + " tracks")

trackIdsToAdd = []
for row in deletedTracks:
    trackId = row[0]
    trackIdsToAdd.append(row[0])

    if len(trackIdsToAdd) >= 50:
        gpm.add_songs_to_playlist(playlist_id=playlistId, song_ids=trackIdsToAdd)
        trackIdsToAdd = []

if len(trackIdsToAdd) >= 0:
    gpm.add_songs_to_playlist(playlist_id=playlistId, song_ids=trackIdsToAdd)
    trackIdsToAdd = []

logger.info("DONE!")
db.close()
