from gmusicapi import Mobileclient
from pprint import pprint

gpm = Mobileclient()
gpm.oauth_login(Mobileclient.FROM_MAC_ADDRESS)
playlists = gpm.get_all_playlists()

for pl in playlists:
    pprint(pl)
    print("")
