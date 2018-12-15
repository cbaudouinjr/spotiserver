var express = require('express');
var logger = require('morgan');
var SpotifyWebAPI = require('spotify-web-api-node');
var config = require("./config");
var stdin = process.stdin;

var spotify_authorization_base_url = "https://accounts.spotify.com/authorize";

var app = express();
var spotify_client = new SpotifyWebAPI({
  clientid : config.clientID,
  clientSecret  : config.clientSecret,
  redirectUri : config.redirectURI
    }
);

app.use(logger('dev'));

// Perform Spotify API authentication with OAuth
// Spotiserver was designed for operating systems with no GUI, however, this is easily adaptable with a redirect.
if(!spotify_client.getAccessToken()){
  console.log("Welcome to Spotiserver!\n");
  console.log("We need you to grant Spotiserver access to Spotify.");
  console.log("Please go to this link in your web browser: " +
      spotify_authorization_base_url +
      "?response_type=code" +
      "&client_id=" + config.clientID +
      "&scope=" + config.scope +
      "&redirect_uri=" + config.redirectURI + "\n");
  console.log("Paste the authorization code below. (data after code=)");
  stdin.on('data', function (data) {
    spotify_client.setAccessToken(data);

    if(spotify_client.getAccessToken()){
      console.log("\nAuthorization successful, let's get this party started.")
    }
  })
}

app.post('/request', function (req, res) {
  var track_name = req.query.trackName;
  var artist = req.query.artist;

});

app.get('/votes', function (req, res) {
  // Send the current list of songs and their rank
});

app.post('/admin', function (req, res) {
  // Process admin commands
});

module.exports = app;
