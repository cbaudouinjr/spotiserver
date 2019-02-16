import logging
import coloredlogs
import configparser
import threading
from . import party
from . import server
import spotipy.oauth2

def validate_config(config):
    assert isinstance(config, dict)
    assert 'SPOTIFY' in config
    assert 'CLIENT_ID' in config['SPOTIFY']
    assert 'CLIENT_SECRET' in config['SPOTIFY']


def main():
    coloredlogs.install(level=logging.INFO)

    config = configparser.RawConfigParser()
    config.read('config.ini')
    client_id = config['SPOTIFY']['CLIENT_ID']
    client_secret = config['SPOTIFY']['CLIENT_SECRET']
    oauth_scope = config['SPOTIFY']['OAUTH_SCOPE']
    oauth_redirect = config['SPOTIFY']['OAUTH_REDIRECT']
    username = config['SPOTIFY']['SPOTIFY_USERNAME']
    playlist = config['SPOTIFY']['SPOTIFY_PLAYLIST_ID']
    block_explicit = config['SPOTIFY']['BLOCK_EXPLICIT']

    fyre = party.Party()
    fyre.bouncer = party.PercentBouncer(fyre)
    fyre.config = config

    fyre.sp_oauth = spotipy.oauth2.SpotifyOAuth(
        client_id=config['SPOTIFY']['CLIENT_ID'],
        client_secret=config['SPOTIFY']['CLIENT_SECRET'],
        redirect_uri=config['SPOTIFY']['OAUTH_REDIRECT'],
        state=None,
        scope=config['SPOTIFY']['OAUTH_SCOPE'],
        cache_path='.cache',
        proxies=None
    )

    fyre.dj = party.DJ(fyre)
    fyre.dj.username = username
    fyre.dj.playlist = playlist
    fyre.dj.block_explicit = block_explicit

    # tell the DJ to start mixing tracks
    threading.Thread(target=fyre.dj.mix).start()

    # start the Flask server to handle requests
    server.app.party = fyre
    server.app.run(host="0.0.0.0", port=5000)
