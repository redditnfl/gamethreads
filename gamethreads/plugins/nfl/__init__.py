import pytz
from . import const
from . import threads
from . import gamefinder
from . import nflteams
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
    # Fix teams in scoring summary
    scoring = []
    if game.nfl_data and game.nfl_data.content and 'scrsummary' in game.nfl_data.content:
        scoring = {int(drive_id): drive for drive_id, drive in game.nfl_data.content['scrsummary'].items()}
        for drive_id in scoring:
            team_id = scoring[drive_id]['team']
            team = nflteams.get_team(team_id)
            scoring[drive_id]['team'] = team

    return {
            'game': nfl_game,
            'kickoff': nfl_game.kickoff_utc.astimezone(tz),
            'events': {event.event: event for event in game.nfl_events},
            'events_list': game.nfl_events,
            'boxscore': game.nfl_data,
            'const': {s: getattr(const, s) for s in dir(const) if not s.startswith('_')},
            'lines': {line.book: line for line in game.nfl_lines},
            'forecast': game.nfl_forecast,
            'scoring': scoring,
            }
