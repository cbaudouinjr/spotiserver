#!/usr/bin/env false
import logging
from flask import Flask, request, Response, json, redirect, render_template
from flask_bootstrap import Bootstrap
from .party import PartyFoul

logger = logging.getLogger(__name__)
app = Flask(__name__)
Bootstrap(app)


@app.route('/')
def index():
    return render_template('profile.html')

@app.route('/webapp')
def webapp():
    return redirect('/auth')


@app.route('/auth')
def auth():
    return redirect(app.party.sp_oauth.get_authorize_url())


@app.route('/callback')
def callback():
    code = request.args['code']

    # retrieves all token information JSON from
    # https://accounts.spotify.com/api/token and stores them in the local cache
    # file
    app.party.sp_oauth.get_access_token(code)

    return Response(response=json.dumps({
        "ok": True,
        "message": "Successfully authenticated"
    }), status=200)


@app.route('/request')
def process_request():
    listener = request.args['listener']
    track = request.args['track']
    artist = request.args['artist']

    try:
        app.party.bouncer.request(listener, track, artist)
    except PartyFoul as e:
        logger.warning(str(e))
        return Response(response=json.dumps({
            "ok": False,
            "message": str(e)
        }), status=404)

    # success!
    logger.info("Request for track {} by guest {} succeeded".format(track, listener))
    return Response(response=json.dumps({
        "ok": True,
        "message": "Added request"
    }), status=200)
