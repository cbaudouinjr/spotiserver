import logging
import configparser
import math

import spotipy
import itertools
import threading
import time
import random
from heapq import *
from flask import Flask, request, Response
from spotipy import util

is_running = False
taking_requests = True
request_map = {}
request_list = []
listener_request_count = {}
played_songs = {}
total_requests = 0

counter = itertools.count()
REMOVED = '<removed-track>'

ACCEPTED = 202
NOT_ACCEPTED = 406
DISABLED = 407
EXPLICIT = 405
NOT_FOUND = 404
ERROR = 500

REQUEST_THRESHOLD = 0.5

logging.basicConfig(level=logging.INFO)
logging.log(level=logging.INFO, msg="Spotiserver is ready.")

config = configparser.RawConfigParser()
config.read('config.ini')
client_id = config['SPOTIFY']['CLIENT_ID']
client_secret = config['SPOTIFY']['CLIENT_SECRET']
oauth_scope = config['SPOTIFY']['OAUTH_SCOPE']
oauth_redirect = config['SPOTIFY']['OAUTH_REDIRECT']
username = config['SPOTIFY']['SPOTIFY_USERNAME']
playlist = config['SPOTIFY']['SPOTIFY_PLAYLIST_ID']
recommended_playlist_username = config['SPOTIFY']['RECOMMENDED_PLAYLIST_USERNAME']
recommended_playlist_id = config['SPOTIFY']['RECOMMENDED_PLAYLIST_ID']
block_explicit = config['SPOTIFY']['BLOCK_EXPLICIT']

app = Flask(__name__)

token = None


@app.route('/')
def process_request():
    if is_running and taking_requests:

        global total_requests, token

        token = util.prompt_for_user_token(username, oauth_scope, client_id, client_secret, oauth_redirect)
        sp = spotipy.Spotify(auth=token)
        if token:
            listener = request.args['listener']

            # Does listener own less than 50% of all requests?
            if not _listener_request_below_total_threshold(listener):
                logging.log(level=logging.INFO, msg="Too many requests made by " + request.args['listener'])
                return Response(status=NOT_ACCEPTED)

            # Does the track exist?
            track = _find_track_in_spotify(sp)
            if track is None:
                logging.log(level=logging.INFO, msg="No tracks found for: " + request.args['track'])
                return Response(status=NOT_FOUND)

            # Does listener own less than 50% of votes for the track?
            if not _listener_can_upvote_song(listener, track):
                logging.log(level=logging.INFO, msg="Too many votes made by " + request.args['listener'])
                return Response(status=NOT_ACCEPTED)

            # Are we watching for explicit tracks? If so, is this track explicit?
            if block_explicit and _track_is_explicit(track):
                logging.log(level=logging.INFO, msg="Not adding: " + request.args['track'] + ", flagged as explicit")
                return Response(status=EXPLICIT)

            # We're good! We can accept the track
            _accept_track(track, listener)
            logging.log(level=logging.INFO, msg="Received track: " + track['name'] + " to the request list")
            return Response(status=ACCEPTED)
    else:
        return Response(status=DISABLED)


def _listener_request_below_total_threshold(listener):
    if listener in listener_request_count:
        requests = listener_request_count[listener]
        percent_of_total_requests = requests/total_requests

        if percent_of_total_requests > REQUEST_THRESHOLD:
            return False

        return True
    else:
        # New listener
        return True


def _listener_can_upvote_song(listener, track):
    dict_track = request_map.get(track['id'])

    if dict_track is not None:
        track_requesters = dict_track[3]
        if listener in track_requesters:
            listener_requests_for_track = request_map[track['id']][3][listener]
            total_requests_for_track = request_map[track['id']][0]

            if abs(listener_requests_for_track / total_requests_for_track) >= REQUEST_THRESHOLD:
                return False

    return True


def _find_track_in_spotify(sp):
    track = request.args['track']
    query = 'track:' + track
    if 'artist' in request.args:
        artist = request.args['artist']
        query = query + ' AND artist:' + artist
    search_results = sp.search(query, 10, type='track')
    tracks_found_from_search = search_results['tracks']['items']
    if len(tracks_found_from_search) > 0:
        requested_track = tracks_found_from_search[0]
        return requested_track
    else:
        return None


def _track_is_explicit(track):
    explicit = track['explicit']

    if explicit:
        return True

    return False


@app.route('/start')
def start_app():
    global is_running

    logging.log(level=logging.INFO, msg="Received start signal; Spotiserver running")
    is_running = True
    return Response(status=ACCEPTED)


@app.route('/autopilot')
def autopilot():
    global is_running, taking_requests

    if is_running:
        logging.log(level=logging.INFO, msg="Received autopilot signal; no longer accepting requests")
        taking_requests = False

    return Response(status=ACCEPTED)


@app.route('/resume')
def resume_requests():
    global is_running, taking_requests

    if is_running:
        logging.log(level=logging.INFO, msg="Received autopilot disable signal; accepting requests")
        taking_requests = True

    return Response(status=ACCEPTED)


@app.route('/stop')
def stop_app():
    global is_running

    logging.log(level=logging.INFO, msg="Received stop signal; Spotiserver stopped")
    is_running = False

    return Response(status=ACCEPTED)

def _accept_track(track, listener):
    global total_requests, request_list, request_map
    track_requesters = {}
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

    if listener in listener_request_count:
        listener_request_count[listener] += 1
    else:
        listener_request_count[listener] = 1

    # python uses a min-heap, workaround: negative numbers
    entry = [existing_votes - 1, count, track['id'], track_requesters, track['duration_ms']]
    request_map[track_id] = entry
    total_requests += 1
    heappush(request_list, entry)


# Gets track recommendations for a random song to pick if no requests are in queue
def _get_track_recommendations(sp):
    if recommended_playlist_id is "" or recommended_playlist_username is "":
        playlist_data = sp.user_playlist(user=username, playlist_id=playlist)
    else:
        logging.log(level=logging.INFO, msg="Taking seed from specific playlist")
        playlist_data = sp.user_playlist(user=recommended_playlist_username, playlist_id=recommended_playlist_id)
    track_list_dict = playlist_data['tracks']['items']
    track_list = []
    artist_list = []
    for i in range(0, 0):
        track_index = random.randint(0, len(track_list_dict) - 1)
        track_list.append(track_list_dict[track_index]['track']['id'])
    for i in range(0, 5):
        track_index = random.randint(0, len(track_list_dict) - 1)
        artist_list.append(track_list_dict[track_index]['track']['artists'][0]['id'])
    return sp.recommendations(seed_tracks=track_list, seed_artists=artist_list)


def _convert_miliseconds_to_seconds(miliseconds):
    seconds = (miliseconds/1000)
    seconds = int(math.ceil(seconds))
    return seconds


# Removes listener votes associated with a song
def _reset_listener_votes(track):
    global total_requests

    # Subtracts the number of listener's requests for a song from the total number of requests a listener has made
    # request_map[track][3] = requests made for a particular song
    for listener in request_map[track][3]:
        listener_votes = request_map[track][3][listener]
        listener_request_count[listener] -= listener_votes
        if listener_request_count[listener] == 0:
            listener_request_count.pop(listener)
        total_requests -= listener_votes


# Engine that manages the selection of tracks
def playlist_manager():
    first_pass = True
    while True:
        if is_running:
            global token
            token = util.prompt_for_user_token(username, oauth_scope, client_id, client_secret, oauth_redirect)
            sp = spotipy.Spotify(auth=token)

            if request_list and taking_requests:
                song_to_play = request_list.pop()
                length_of_song = _convert_miliseconds_to_seconds(song_to_play[4])
                sp.user_playlist_add_tracks(username, playlist, [song_to_play[2]])
                _reset_listener_votes(song_to_play[2])
                logging.log(level=logging.INFO, msg="Added a track to the playlist")
            else:
                # pick a song from the recommendations list seeded by our already played songs
                recommendations_list = _get_track_recommendations(sp)
                track_list = recommendations_list['tracks']
                track_index_to_pick = random.randint(0, len(track_list) - 1)
                track_to_add = track_list[track_index_to_pick]
                while track_to_add['explicit'] and block_explicit:
                    track_index_to_pick = random.randint(0, len(track_list) - 1)
                    track_to_add = track_list[track_index_to_pick]
                length_of_song = _convert_miliseconds_to_seconds(track_to_add['duration_ms'])
                sp.user_playlist_add_tracks(username, playlist, [track_to_add['id']])
                logging.log(level=logging.INFO, msg="Added track: " + track_to_add['name'] + " from recommendations")
            if not first_pass:
                time.sleep(20)  # keep time in sync
            time.sleep(length_of_song - 20)  # pick a new track when the last one is 1/4 over
            first_pass = False


playlist_manager_thread = threading.Thread(target=playlist_manager)
playlist_manager_thread.start()

if __name__ == '__main__':
    app.run()
