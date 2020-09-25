import argparse
import locale
import logging
import sys
from pprint import pformat
from ytmusicapi import YTMusic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--listId", help="Playlist ID", nargs=1, required=True)
    parser.add_argument("-v", "--videoId", help="Video ID", nargs=1, required=True)
    parser.add_argument("-s", "--setVideoId", help="Set Video ID", nargs=1, required=True)
    args = parser.parse_args()

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    log_hnd_screen = logging.StreamHandler(stream=sys.stdout)
    log_hnd_screen.setLevel(logging.DEBUG)
    log_hnd_screen.setFormatter(log_formatter)
    logger.addHandler(log_hnd_screen)

    ytmusic = YTMusic('ytm_auth.json')

    locale.setlocale(locale.LC_ALL, 'en_GB')

    list_id = args.listId[0]
    set_video_id = args.setVideoId[0]
    video_id = args.videoId[0]

    logger.info("Playlist: " + list_id)
    logger.info("SetVideoID: "+ set_video_id)
    logger.info("VideoID: "+ video_id)

    playlistItem = {
        "videoId": video_id,
        "setVideoId": set_video_id,
    }
    status = ytmusic.remove_playlist_items(playlistId=list_id, videos=[playlistItem])
    logger.info(pformat(status))


main()
exit()
