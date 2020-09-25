import argparse
import config
import locale
import logging
import pymysql.cursors
import sys
from pprint import pformat
from ytmusicapi import YTMusic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--listId", help="Playlist ID", nargs=1, required=True)
    args = parser.parse_args()

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    log_hnd_screen = logging.StreamHandler(stream=sys.stdout)
    log_hnd_screen.setLevel(logging.DEBUG)
    log_hnd_screen.setFormatter(log_formatter)
    logger.addHandler(log_hnd_screen)

    db, cursor = init_db(config.db)

    ytmusic = YTMusic('ytm_auth.json')

    locale.setlocale(locale.LC_ALL, 'en_GB')

    list_id = args.listId[0]

    logger.info("Playlist: " + list_id)

    sql = """
        SELECT `ytm_playlist_entries`.`ytm_videoid`, `ytm_playlist_entries`.`ytm_set_videoid`
        FROM (
            SELECT `ytm_playlistid`, `ytm_videoid`
            FROM ytm_playlist_entries
            WHERE `ytm_playlistid` = %(playlistId)s
            GROUP BY `ytm_playlistid`, `ytm_videoid`
            HAVING COUNT(*) > 1
        ) AS `selected_entries`
        LEFT JOIN `ytm_playlist_entries` 
            ON `selected_entries`.`ytm_playlistid` = `ytm_playlist_entries`.`ytm_playlistid`
                AND `selected_entries`.`ytm_videoid` = `ytm_playlist_entries`.`ytm_videoid`
    """
    params = {
        "playlistId": list_id,
    }
    cursor.execute(sql, params)
    duplicate_entries = cursor.fetchall()

    if len(duplicate_entries) == 0:
        logger.info("No duplicate entries found")
        return

    last_videoid = None
    for playlist_entry in duplicate_entries:
        # Skip the first playlist entry
        if playlist_entry["ytm_videoid"] != last_videoid:
            last_videoid = playlist_entry["ytm_videoid"]
            continue

        remove_playlist_item(ytmusic, logger, list_id, playlist_entry["ytm_videoid"], playlist_entry["ytm_set_videoid"])

    logger.info("Done")
    db.close()


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


def remove_playlist_item(ytmusic, logger, playlistid, videoid, set_videoid):
    logger.info("SetVideoID: " + set_videoid + " :: VideoID: " + videoid)

    playlist_item = {
        "videoId": videoid,
        "setVideoId": set_videoid,
    }
    status = ytmusic.remove_playlist_items(playlistId=playlistid, videos=[playlist_item])
    logger.info(pformat(status))


main()
exit()
