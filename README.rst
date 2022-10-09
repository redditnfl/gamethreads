#####
Setup
#####

Install gamethreads and dependencies with pip, e.g. in a virtualenv::

    pip install -e git+git@github.com:redditnfl/gamethreads.git#egg=gamethreads

Register the app as a personal use script on https://www.reddit.com/prefs/apps/

*************
Configuration
*************

Configuring the Gamethreads system is done through Subreddit Wiki pages.

You need at least three pages setup:

- ``<subreddit_name>/wiki/gamethreads/root_config``
- ``<subreddit_name>/wiki/gamethreads/config``
- ``<subreddit_name>/wiki/gamethreads/templates/<teamplate_name>``

Root config
===========

The page ``/gamethreads/root_config`` should be formatted as YAML and contain
the base setup for the Gamethreads system. The system can run on multiple
subreddits. The root config contains only information about which subreddits
are active as well as which gamethread types are supported (currently only
'nfl' exists).

Example::

    subreddits:
      - 'subreddit_name'
    types:
      - 'nfl'

Subreddit config
================

For any subreddit, you must setup the page ``/gamethreads/config``. This
page is also YAML-formatted. Example::

    timezone: 'US/Eastern'
    threads:
      -
        id: gamethread
        template: gamethread
        post_condition: kickoff - (120 * minutes)

The two elements ``timezone`` and ``threads`` are mandatory.

Threads are configured with an id string (must be unique), a template name and a post condition.

Post conditions
---------------

Post conditions are Jinja2 expressions that are evaluated with the full context of the game at regular intervals. The
expression should return either a datetime or a boolean. If it returns a boolean, the thread will be posted when the
boolean is true. If a datetime is returned, the thread will be posted if the returned time lies in the past.

Templates
=========

Templates are stored in reddit's wiki system under the ``/gamethreads/templates``. They are rendered using Jinja2,
and must output the markdown you want posted. The loader is generic which means includes and any other Jinja2 feature
should work.

The first line of output will be used as the thread title.

The template context contains some base data, plus extra context data from the plugin (again, only nfl is available).

Base data:

.. code-block:: python

    {
        'minutes': timedelta(minutes=1),
        'hours': timedelta(hours=1),
        'days': timedelta(days=1),
        'base_game': Game,
        'thread': Thread or None,
        'now': pytz.utc.localize(datetime.utcnow())
    }

NFL data:

.. code-block:: python

    {
        'game': NFLGame,
        'kickoff': NFLGame.kickoff_utc.astimezone(tz),
        'events': {event.event: event for event in game.nfl_events},
        'events_list': Game.NFLGameEvent[],
        'data': NFLGameData,
        'const': {s: getattr(const, s) for s in dir(const) if not s.startswith('_')},
        'lines': {line.book: line for line in game.nfl_lines},
        'forecast': NFLForecast,
    }

******************
Running "manually"
******************

Create a praw.ini with the necessary information::

    [gamethread]
    client_id = 
    client_secret = 
    user_agent = gamethreads/1.0
    username = 
    password = 

Alternatively you can generate a refresh\_token, e.g. using the `example
script <https://praw.readthedocs.io/en/latest/tutorials/refresh_token.html#refresh-token>`__
from the PRAW docs.

You can also use the `redditauth` script::

    redditauth --redirect_uri http://localhost:8080 --client_id ABC --client_secret DEF read,submit,edit,wikiread


***************************
Running with docker-compose
***************************

First, create .env alongside docker-compose.yml. It must have at least the
following contents::

    SUB=rasherdk
    WEBPORT=8080
    praw_redirect_uri=http://localhost:8080
    praw_client_id=C-4A_fPkicP0WTZ374htoA
    praw_client_secret=U-rXr58Acikz8gogFy85Hiwawu-NVw
    POSTGRES_PASSWORD=secretdbpassword

Next, create the database, obtain a refresh token and run the server::

    $ docker-compose --env-file .env --profile init run initdb
    $ docker-compose --env-file .env --profile redditauth run --service-ports --rm redditauth
    # Update .env with obtained refresh token
    $ docker-compose --env-file .env --profile prod up

If you wish to use the preview service, add the `preview` profile::

    $ docker-compose --env-file .env --profile prod --profile preview up
