import logging
import configparser
import spotipy
import itertools
from heapq import *
from flask import Flask, request, Response
from spotipy import util

track_list = []
entry_finder = {}
listener_vote_count = {}  # used to track the number of votes per listener, prevents spam voting
counter = itertools.count()
REMOVED = '<removed-track>'

logging.basicConfig(level=logging.INFO)

config = configparser.RawConfigParser()
config.read('config.ini')

app = Flask(__name__)

client_id = config['SPOTIFY']['CLIENT_ID']
client_secret = config['SPOTIFY']['CLIENT_SECRET']
oauth_scope = config['SPOTIFY']['OAUTH_SCOPE']
oauth_redirect = config['SPOTIFY']['OAUTH_REDIRECT']
username = config['SPOTIFY']['SPOTIFY_USERNAME']
playlist = config['SPOTIFY']['SPOTIFY_PLAYLIST_ID']
token = util.prompt_for_user_token(username, oauth_scope, client_id, client_secret, oauth_redirect)

if(token):
    # start song picker thread here
    pass

@app.route('/')
def song_request():
    if token:
        sp = spotipy.Spotify(auth=token)
        track = request.args['track']
        query = 'track:' + track
        if 'artist' in request.args:
            artist = request.args['artist']
            query = query + ' AND artist:' + artist
        search_results = sp.search(query, 10, type='track')
        track_list_results = search_results['tracks']['items']
        if len(track_list_results) == 0:
            logging.log(level=logging.INFO, msg="No tracks found for: " + request.args['track'])
            return Response(status=404)
        track = track_list_results[0]

        # A track's value is represented as [votes, count, songID]
        existing_votes = 0
        if track['id'] in entry_finder:
            existing_votes = entry_finder.get(track['id'])[0]
            entry = entry_finder.pop(track['id'])
            entry[-1] = REMOVED
        count = next(counter)
        entry = [existing_votes - 1, count, track['id']] # python uses a min-heap, workaround: negative numbers
        entry_finder[track['id']] = entry

        heappush(track_list, entry)

        logging.log(level=logging.INFO, msg="Added vote for " + request.args['track'])

        return Response(status=202)


if __name__ == '__main__':
    app.run()
