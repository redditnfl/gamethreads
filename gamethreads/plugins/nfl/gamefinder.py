from gamethreads.util import now
from .const import *
from sgqlc.operation import Operation

from nflapi import NFL, shield

def find_games():
    """Find find all games occuring within a reasonable timeframe
    
    Return game ids"""
    nfl = NFL('gamethread/finder')
    now = nfl.schedule.current_week()

    op = Operation(shield.Viewer)
    games = op.viewer.league.games_by_week(week_season_value=now.season_value, week_season_type=now.season_type, week_week_value=now.week_value)
    games.id()
    result = nfl.query(op)
    return [g.id for g in result.viewer.league.games_by_week]

def update_state(game):
    """Update the state of a game if necessary"""
    # Wait until we can look at nfl-specific state
    if game.state is None:
        game.state = game.PENDING
    if game.nfl_game is not None:
        if game.nfl_game.state == GS_PENDING:
            game.state = game.PENDING
        elif game.nfl_game.state in GS_PLAYING:
            game.state = game.ACTIVE
        elif game.nfl_game.state in GS_FINAL:
            game.state = game.CLOSED
    return game
