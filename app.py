import logging
import configparser
import spotipy
import itertools
import threading
import time
from heapq import *
from flask import Flask, request, Response
from spotipy import util

request_map = {}
request_list = []
requesters = {}
total_requests = 0

counter = itertools.count()
REMOVED = '<removed-track>'
ACCEPTED = 202
NOT_ACCEPTED = 406
EXPLICIT = 405
NOT_FOUND = 404
ERROR = 500
REQUEST_THRESHOLD = 0.5

logging.basicConfig(level=logging.INFO)

config = configparser.RawConfigParser()
config.read('config.ini')
client_id = config['SPOTIFY']['CLIENT_ID']
client_secret = config['SPOTIFY']['CLIENT_SECRET']
oauth_scope = config['SPOTIFY']['OAUTH_SCOPE']
oauth_redirect = config['SPOTIFY']['OAUTH_REDIRECT']
username = config['SPOTIFY']['SPOTIFY_USERNAME']
playlist = config['SPOTIFY']['SPOTIFY_PLAYLIST_ID']
block_explicit = config['SPOTIFY']['BLOCK_EXPLICIT']

app = Flask(__name__)

token = None


@app.route('/')
def process_request():
    global total_requests, token

    token = util.prompt_for_user_token(username, oauth_scope, client_id, client_secret, oauth_redirect)
    sp = spotipy.Spotify(auth=token)
    if token:
        # listener most not own more than the requests_threshold percent of total requests
        listener = request.args['listener']
        if listener in requesters:
            listener_requests = requesters[listener]
            percent_of_total_requests = listener_requests/total_requests
            if percent_of_total_requests <= REQUEST_THRESHOLD:
                    track = request.args['track']
                    query = 'track:' + track
                    if 'artist' in request.args:
                        artist = request.args['artist']
                        query = query + ' AND artist:' + artist
                    search_results = sp.search(query, 10, type='track')
                    tracks_found_from_search = search_results['tracks']['items']
                    if len(tracks_found_from_search) > 0:
                        requested_track = tracks_found_from_search[0]
                        # listener must not own more than the requests_threshold percent of total requests for a
                        if requested_track['id'] in request_map:
                            track_requesters = request_map[requested_track['id']][3]
                            if listener in track_requesters:
                                # both track and listener exist
                                listener_requests_for_track = request_map[requested_track['id']][3][listener]
                            else:
                                # track exists but listener never requested it before
                                listener_requests_for_track = 0
                            total_requests_for_track = abs(request_map[requested_track['id']][0])
                            if listener_requests_for_track / total_requests_for_track <= REQUEST_THRESHOLD:
                                # listener may request the track to be played.
                                requesters[listener] += 1
                                return _request_track(tracks_found_from_search[0], listener)
                            else:
                                # too many requests right now for this listener
                                logging.log(level=logging.INFO,
                                            msg="Too many requests made by " + request.args['listener'])
                                return Response(status=NOT_ACCEPTED)
                        else:
                            # never requested track from a listener who's already requested a different track
                            # listener may request the track to be played.
                            requesters[listener] += 1
                            return _request_track(tracks_found_from_search[0], listener)
                    else:
                        # track not found
                        logging.log(level=logging.INFO, msg="No tracks found for: " + request.args['track'])
                        return Response(status=NOT_FOUND)
            else:
                # too many requests right now for this listener
                logging.log(level=logging.INFO, msg="Too many requests made by " + request.args['listener'])
                return Response(status=NOT_ACCEPTED)
        else:
            # new listener, they can request anything
            logging.log(level=logging.INFO, msg="New listener: " + listener)
            requesters[listener] = 1
            track = request.args['track']
            query = 'track:' + track
            if 'artist' in request.args:
                artist = request.args['artist']
                query = query + ' AND artist:' + artist
            search_results = sp.search(query, 10, type='track')
            tracks_found_from_search = search_results['tracks']['items']
            return _request_track(tracks_found_from_search[0], listener)
    else:
        # critical authentication error
        logging.log(level=logging.ERROR, msg="Spotify authentication failed!")
        return Response(status=ERROR)


def _request_track(track, listener):
    # check if track is explicit
    global total_requests, request_list, request_map
    track_is_explicit = track['explicit']
    track_requesters = {}

    if not track_is_explicit or not block_explicit:
        # A track's value is represented as [votes, count, trackID, {track_requesters}]
        track_id = track['id']
        existing_votes = 0  # existing votes for a track, if a new track, we default to zero
        if track['id'] in request_map:
            existing_votes = request_map.get(track_id)[0]
            track_requesters = request_map.get(track_id)[3]
            entry = request_map.pop(track_id)
            entry[-1] = REMOVED
        count = next(counter)
        if listener in track_requesters:
            track_requesters[listener] += 1
        else:
            track_requesters[listener] = 1
        # python uses a min-heap, workaround: negative numbers
        entry = [existing_votes - 1, count, track['id'], track_requesters]
        request_map[track_id] = entry
        total_requests += 1
        heappush(request_list, entry)
        logging.log(level=logging.INFO, msg="Added track: " + request.args['track'] + " to the request list")
        return Response(status=ACCEPTED)
    else:
        logging.log(level=logging.WARN, msg="Not adding song " + request.args['track'] + ": flagged as explicit")
        return Response(status=EXPLICIT)


def playlist_manager():
    while True:
        global token
        token = util.prompt_for_user_token(username, oauth_scope, client_id, client_secret, oauth_redirect)
        sp = spotipy.Spotify(auth=token)

        if request_list:
            song_to_play = request_list.pop()
            sp.user_playlist_add_tracks(username, playlist, [song_to_play[2]])
            logging.log(level=logging.INFO, msg="Added a track to the playlist")
        time.sleep(300)


playlist_manager_thread = threading.Thread(target=playlist_manager)
playlist_manager_thread.start()

if __name__ == '__main__':
    app.run()
