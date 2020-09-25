import argparse
import json
import locale
import logging
import sys
from pprint import pprint
from ytmusicapi import YTMusic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--listId", help="Playlist ID", nargs=1)
    args = parser.parse_args()

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    log_hnd_screen = logging.StreamHandler(stream=sys.stdout)
    log_hnd_screen.setLevel(logging.ERROR)
    log_hnd_screen.setFormatter(log_formatter)
    logger.addHandler(log_hnd_screen)

    ytmusic = YTMusic('ytm_auth.json')

    # loc = locale.getlocale()
    locale.setlocale(locale.LC_ALL, 'en_GB')

    only_list_id = None
    if args.listId is None:
        logger.info("No list id given - listing all playlists")
        list_playlists(ytmusic)
    else:
        only_list_id = args.listId[0]
        logger.info("Listing tracks for playlist: " + only_list_id)
        list_tracks(ytmusic, only_list_id)


def list_playlists(ytmusic):
    playlists = ytmusic.get_library_playlists()

    for pl in playlists:
        pprint(pl)
        print("")


def list_tracks(ytmusic, playlistid: str):
    pldata = ytmusic.get_playlist(playlistid, 10000)

    pldata_keys = []
    for key in pldata.keys():
        if key not in pldata_keys:
            pldata_keys.append(key)

    pltrack_keys = []
    for pltrack in pldata["tracks"]:
        for key in pltrack.keys():
            if key not in pltrack_keys:
                pltrack_keys.append(key)

    print(json.dumps(pldata))

    print("")

    print("pldata keys: " + ", ".join(pldata_keys))
    print("pltrack keys: " + ", ".join(pltrack_keys))
    print("reported track count: " + str(pldata["trackCount"]))
    print("actual track count: " + str(len(pldata["tracks"])))
    print("")


main()
exit()
