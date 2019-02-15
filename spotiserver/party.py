#!/usr/bin/env false
import datetime
import logging
import configparser
import spotipy
import itertools
import threading
import time
import random
import heapq
from heapq import *
from spotipy import util

logger = logging.getLogger(__name__)

class PartyFoul(Exception):
    pass

class Track:

    def __init__(self, spotify_id):
        self.spotify_id = spotify_id
        self.requests = dict()
        self._time_created = time.time()
        self._time_updated = time.time()

    def vote(self, guest):
        count = self.requests.get(guest.key, 0)
        self.requests[guest.key] = count + 1
        self._time_updated = time.time()

    @property
    def votes(self):
        return sum(self.requests.values())

    def __str__(self):
        return self.spotify_id

    def __lt__(self, other):
        """
        Because we are using a min-heap queue, the 'smallest' track will be
        played first
        """
        if self.votes == other.votes:
            return self._time_created > other._time_created
        return self.votes > other.votes

class TrackRequest:

    def __init__(self, guest, track):
        self.guest = guest
        self.track = track


class Guest:

    def __init__(self, key):
        self.key = key
        self.requests = 0

    def __str__(self):
        return self.key


class DJ:

    def __init__(self, party):
        self.party = party
        self._sp = None
        # map of all tracks
        self.track_map = {}
        # queue of tracks that are about to play
        self.track_queue = []

    @property
    def sp(self):
        if isinstance(self._sp, spotipy.Spotify):
            return self._sp
        token_json = self.party.sp_oauth.get_cached_token()
        while not token_json:
            logger.error("DJ does not have a valid Spotify OAuth token!")
            token_json = self.party.sp_oauth.get_cached_token()
            time.sleep(10)
        if 'expires_at' in token_json:
            logger.warn("Access token expires at {} UTC.".format(datetime.datetime.utcfromtimestamp(token_json['expires_at']).isoformat()))
        token = token_json['access_token']
        self._sp = spotipy.client.Spotify(auth=token)
        return self._sp

    def remaining_playback(self):
        """
        Check how much time is remaining until the current track is done

        :return: seconds left in track, track id
        """
        playback = self.sp._get("me/player")

        if not playback:
            logger.error("Attempt to retrieve playback information from Spotify failed. This usually means that nothing is being played.")
            raise Exception

        if not playback.get("context", None):
            logger.error("The party host is not currently listening to a playlist. Please play the designated playlist.")
            raise Exception

        # check that the playback is as expected
        if playback['context']['type'] != 'playlist' or \
                playback['context']['uri'].split(':')[-1] != self.party.config['SPOTIFY']['SPOTIFY_PLAYLIST_ID']:
            logger.error("The spotify playback for the hosting user is not the designated playlist, {}.".format(playback['context']['href']))
            raise Exception

        # playback is correct
        logger.info("The party host is playing the correct playlist. All is well.")

        # calculate the remaining ms in the track
        remaining_ms = playback['item']['duration_ms'] - playback['progress_ms']
        logger.info("{}s left in current track".format(remaining_ms / 1000))
        return remaining_ms / 1000, playback['item']['id']

    def last_tracks(self, playlist_id, num=10):
        """
        Get the Spotify IDs of the last `num` tracks of the given playlist

        :rtype: str
        """
        assert num > 0
        tracks = self.sp.user_playlist_tracks(self.username, playlist_id=playlist_id, limit=num, offset=0)
        total = tracks["total"]
        if total > num:
            tracks = self.sp.user_playlist_tracks(self.username, playlist_id=playlist_id, limit=num, offset=max(0, total-num))
        return list(map(lambda t: t["track"]["id"], tracks["items"]))

    def recommend_tracks(self):
        """
        Ask Spotify to recommend tracks based on a random sampling of tracks
        from a pre-selected playlist

        :rtype: list
        """
        # select 5 random tracks from the given playlist to seed Spotify's
        # track generator
        playlist_data = self.sp.user_playlist(user=self.username, playlist_id=self.playlist)
        track_list_dict = playlist_data['tracks']['items']
        track_list = []
        for i in range(0, 5):
            track_index = random.randint(0, len(track_list_dict) - 1)
            track_list.append(track_list_dict[track_index]['track']['id'])

        # retrieve recommendations from Spotify
        recommendation_json = self.sp.recommendations(seed_tracks=track_list)
        recommendation_list = recommendation_json['tracks']
        assert isinstance(recommendation_list, list)
        return recommendation_list

    def recommend_track(self):
        """
        Returns a dictionary representing the JSON returned by the Spotify API

        :rtype: dict
        """
        track_list = self.recommend_tracks()
        # filter out explicit tracks
        if self.block_explicit:
            track_list = filter(lambda t: not t['explicit'], track_list)
        # pick a random recommended track
        return random.choice(track_list)

    def pick_track_id(self):
        # if the request queue is not empty, pick the song with the most votes
        if self.track_queue:
            track = heapq.heappop(self.track_queue)
            logger.info('Added track to playlist: {} from party guests'.format(track))
            # TODO reset track votes to zero, update voters, and total votes
            return track.spotify_id

        # if the request queue was empty, pick a song from the recommendations
        # list seeded by our already played songs
        track_json = self.recommend_track()
        logger.info("Added track to playlist: {} from Spotify recommendations".format(track_json['name']))
        return track_json['id']

    def pick_track(self):
        track_id = self.pick_track_id()
        self.sp.user_playlist_add_tracks(self.username, self.playlist, [track_id])

    def mix(self):
        self.pick_track()

        while True:
            try:
                remaining_sec, track_id = self.remaining_playback()

                # pick a new track if this is one of the last 5 tracks in the
                # playlist
                if track_id in self.last_tracks(self.playlist, num=5):
                    self.pick_track()

                # otherwise, sleep
                else:
                    logging.info("The current track is not one of the last 5 in the playlist; sleeping for {} seconds.".format(remaining_sec))
                    time.sleep(remaining_sec)

            except Exception:
                logging.exception("DJ caught error while mixing; sleeping 5 seconds.")
                time.sleep(5)

    def request(self, guest, title, artist=None):
        assert isinstance(guest, Guest)
        assert isinstance(title, str)
        # construct the query
        query = 'track:' + title
        if artist:
            query += ' AND artist:' + artist

        # search
        search_results = self.sp.search(query, 10, type='track')
        tracks_found_from_search = search_results['tracks']['items']
        if len(tracks_found_from_search) == 0:
            raise PartyFoul("No tracks found for {}".format(query))
        requested_track = tracks_found_from_search.pop()
        track_id = requested_track['id']

        # create the Track object if it doesn't exist
        if not track_id in self.track_map:
            self.track_map[track_id] = Track(track_id)

        # vote for the track
        self.track_map[track_id].vote(guest)
        logger.info("Guest {} voted for track {}".format(guest, track_id))

        # check if the track can be added to the queue
        track = self.track_map[track_id]
        if track.requests.get(guest.key, 0) <= max(1, track.votes * 0.5):
            heapq.heappush(self.track_queue, track)
            logger.info("Added track to queue: {}".format(track_id))

class Bouncer:

    def __init__(self, party):
        self.party = party
        self.total_requests = 0
        self.guests = dict()

    def add_guest(self, guest_key):
        if guest_key not in self.guests:
            self.guests[guest_key] = Guest(guest_key)
            logger.info("New guest: " + guest_key)

    def find_guest(self, guest_key):
        if guest_key not in self.guests:
            self.add_guest(guest_key)
        return self.guests[guest_key]

    def request(self, guest_key, title, artist):
        pass


class PercentBouncer(Bouncer):

    THRESHOLD = 0.5

    def request(self, guest_key, title, artist):
        guest = self.find_guest(guest_key)

        # check if the guest is "over the legal limit"
        percent_of_total_requests = guest.requests / max(self.total_requests, 10)
        if percent_of_total_requests > self.THRESHOLD:
            raise PartyFoul("Guest {} is over the limit.".format(guest_key))

        # pass the request to the DJ
        self.party.dj.request(guest, title, artist)

        # increment count of requests if this request was completed without
        # error
        self.total_requests += 1
        guest.requests += 1

class Party:
    """
    Vessel to contain all the necessary elements of a good party
    """
    __slots__ = ('bouncer', 'config', 'dj', 'sp_oauth')
