from gamethreads.util import now
from . import schedule
from .const import *

def find_games():
    """Find find all games occuring within a reasonable timeframe
    
    Return game ids"""
    games = schedule.get_schedule(*schedule.get_week(now().date()))
    return [game.eid for game in games]

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
