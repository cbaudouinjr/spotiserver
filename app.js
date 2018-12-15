var express = require('express');
var logger = require('morgan');
var SpotifyWebAPI = require('spotify-web-api-node');
var config = require("./config");

var app = express();
var spotify_client = new SpotifyWebAPI({
  clientid : config.clientID,
  clientSecret  : config.clientSecret,
  redirectUri : config.redirectURI
    }
);

app.use(logger('dev'));

app.post('/request', function (req, res) {
  var track_name = req.query.trackName;
  var artist = req.query.artist;

});


module.exports = app;
