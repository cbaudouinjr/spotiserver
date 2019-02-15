# spotiserver

A server-side application that is capable of DJing your party through requests
and it's own music choices.

## Purpose

This application is built with a hackathon-sized event in mind. Spotiserver
solves the issue of receiving a mass number of requests at a large venue.

## Features

- Add tracks to a Spotify playlist
- Take requests from a third-party source via an endpoint
- Chooses music to add to playlist to add variety
- Prevents one attendee from spamming request list

## Configuration

Copy `config.ini.example` to `config.ini` in the root directory of this
repository and edit all the values as needed. This configuration file is
formatted using [Tom's Obvious, Minimal Language][toml].

You will need a client id and client secret from Spotify, which you can
retrieve from their [developer dashboard][spotify].

## Setup

Before continuing, make sure you have [Python 3][python] and `pip3` installed.

If you need to have several different versions of Python installed, it is
recommend that you use [pyenv][pyenv].

Below are several options for installing the Python packages that this
repository depends on. Use `pipenv` or `virtualenv` if you have multiple Python
projects on a single computer.

### Option 1: The simple way

*All commands in this section should be run in the root directory of this
project using your favorite shell*

Install dependencies for the current user only:

```bash
python3 -m pip install --user -r requirements.txt
```

### Option 2: Isolated Python Environment (virtualenv)

*All commands in this section should be run in the root directory of this
project using your favorite shell*

Install virtualenv:

```bash
python3 -m pip install --user virtualenv
```

Create environment (in env directory) that uses Python 3:

```bash
virtualenv -p python3 env
```

Run the following to enter the created environment:

```bash
source env/bin/activate
```

Now, you can proceed with Option 1 without worrying about package conflicts.

### Option 3: Pipenv

[Pipenv][pipenv] combines both `virtualenv` and `pip` into a single tool.
However, it is still fairly new and as a result, not recommended unless you
know what you are doing.

*All commands in this section should be run in the root directory of this
project*

```bash
# install pipenv
python3 -m pip install --user pipenv
# create environment
pipenv install -r requirements.txt
# enter the environment
pipenv shell
```

## Development

All development work will live on the develop branch. Spotiserver is currently
in the early stages of development and when ready will be merged into master.


[spotify]: https://developer.spotify.com/dashboard/
[toml]: https://github.com/toml-lang/toml
