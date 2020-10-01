# PlayList Tracker

## Google Play Music

Set of scripts for monitoring and managing my GPM playlists.

GPM deletes tracks from playlists and there's no way to find out what tracks
were deleted, therefore I implement my own change tracking via `gpm-fetch.py`.

Additionally I have collections that span several playlists due to their size
and the GPM playlist track limit (1000 tracks). `gpm-rpg.py` creates a playlist
made up of a random selection from this collection. `gpm-rp-cascade.py`
cascades deletions from the randomly generated lists back to the source lists.

## YouTube Music

Monitors playlists for removed / unavailable tracks.

The web interface provides the facility to search for tracks in your playlists and remove the selected track from one
or all playlists.

Since YTM provides for larger playlists, the scripts for generating a random selection playlist have not been migrated.

## Requirements

* MySQL 5.7+
* Python 3.6+

## Initial Setup

Initialize MySQL database using `schema.sql`

Copy `config.example.py` to `config.py` and amend as necessary.

```bash
pipenv install
pipenv run python3 gpm-auth.py
```

### Google Play Music

```bash
pipenv run python3 gpm-auth.py
```

#### Example crontab

```
# mn hr  dom mon dow  cmd
@daily      cd ${HOME}/projects/plt/; pipenv run python3 gpm-fetch.py
0  4 1 * *  cd ${HOME}/projects/plt/; pipenv run python3 gpm-rpg.py
15 4 * * *  cd ${HOME}/projects/plt/; pipenv run python3 gpm-rp-cascade.py
# Run fetch again to record the new playlist and cascaded changes
30 4 * * *  cd ${HOME}/projects/plt/; pipenv run python3 gpm-fetch.py
```

### YouTube Music

Unfortunately the official YouTube API does not work well with YouTube Music content. Uploaded (and many GPM migrated)
tracks always appear as private without details even when fully authenticated. This means we have to use an "unofficial"
API based on the web interface, which currently does not provide proper OAuth authentication.

To set up authentication follow the [ytmusicapi setup instructions](https://ytmusicapi.readthedocs.io/en/latest/setup.html)
to obtain the authentication headers and paste them into the setup script when prompted:

```bash
pipenv run python3 -m ytm.setup
```

#### Example crontab

```bash
# mn hr  dom mon dow  cmd
@daily                cd ${HOME}/projects/plt; pipenv run python3 -m ytm.fetch 
```
