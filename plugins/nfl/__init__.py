import pytz
from . import const
from . import threads
from . import gamefinder
from gamethreads.util import NotReadyException

def make_context(game, config):
    """Create the context to be passed into the template render - also for the post expression"""
    tz = pytz.timezone(config['timezone'])
    nfl_game = game.nfl_game
    if nfl_game is None:
        raise NotReadyException("Game %s does not have an nfl_game" % game)
    nfl_game.local_tz = tz
    for event in game.nfl_events:
        event.local_tz = tz
    return {
            'game': nfl_game,
            'kickoff': nfl_game.kickoff_utc.astimezone(tz),
            'events': {event.event: event for event in game.nfl_events},
            'events_list': game.nfl_events,
            'boxscore': game.nfl_data,
            'const': {s: getattr(const, s) for s in dir(const) if not s.startswith('_')},
            'lines': {line.book: line for line in game.nfl_lines},
            }
