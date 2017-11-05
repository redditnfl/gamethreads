from datetime import timedelta
from urllib.request import urlopen
import ujson
from sqlalchemy import func
from sqlalchemy.sql import exists

from . import nflteams, nflcom, espn, nfllive, schedule

from gamethreads.util import get_or_create, now
from gamethreads import GameThreadThread
from .const import *

import pytz
UTC = pytz.utc

GAMETYPE = 'nfl'

# TODO: Gather data like stadium, broadcaster and betting line
# TODO: Gather weather forecasts

def decide_sleep(session, NFLGame, active_interval, interval):
    # If we have active games, update sooner
    any_playing = session.query(exists().where(NFLGame.state.in_(GS_PLAYING))).scalar()
    if any_playing:
        return active_interval
    # If a game is starting soon (or should have started), update sooner
    upcoming = session.query(func.min(NFLGame.kickoff_utc).label("min_kickoff")).filter(NFLGame.state == GS_PENDING)
    first_start = upcoming.one().min_kickoff
    if first_start is None:
        return interval
    if first_start < (now() + interval):
        return max(first_start - now(), active_interval)


class NFLBoxscoreUpdater(GameThreadThread):
    interval = timedelta(minutes=15)
    active_interval = timedelta(minutes=5)
    
    def lap(self):
        session = self.Session()
        for game in self.active_games().filter(self.models.nfl.NFLGame.state.in_(GS_PLAYING + GS_FINAL)):
            self.logger.info("Updating boxscore for %r", game)
            gamedata, created = get_or_create(session, self.models.nfl.NFLGameData, game=game)
            if created:
                session.add(gamedata)
            json = self.get_json(game.game_id)
            if json and 'drives' in json:
                del(json['drives'])
            gamedata.content = json
        session.commit()

        new_int = decide_sleep(session, self.models.nfl.NFLGame, self.active_interval, self.interval)
        session.close()
        if new_int:
            self.logger.debug("Shortened sleep: %s", new_int)
            return new_int

    def get_json(self, eid):
        fmt = 'http://www.nfl.com/liveupdate/game-center/{eid}/{eid}_gtd.json'
        url = fmt.format(eid=eid)
        try:
            return ujson.load(urlopen(url))[eid]
        except Exception as e:
            self.logger.exception("Error getting boxscore")
            

class NFLTeamDataUpdater(GameThreadThread):
    interval = timedelta(minutes=30)
    setup = True

    def lap(self):
        session = self.Session()
        teams = session.query(self.models.nfl.NFLTeam)
        for team in teams.all():
            record = nflcom.get_record(team.id)
            if record != (team.record_won, team.record_lost, team.record_tied):
                self.logger.info("Updating record for %s to %r", team, record)
                team.record = record
        session.commit()


class NFLGameStateUpdater(GameThreadThread):
    interval = timedelta(minutes=15)
    active_interval = timedelta(seconds=30)

    def lap(self):
        session = self.Session()
        live_games = nfllive.get_games()['games']
        if live_games is None or len(live_games) == 0:
            self.logger.warning("No games found. Skipping")
            return
#, url='http://rasher.dk/tmp/ss.xml'

        prop_map = {
                'state':('q',None),
                'home_id':('home',None),
                'away_id':('away',None),
                'clock':('clock',lambda s: '--:--' if s == '' else s),
                'home_score':('home_score',int),
                'away_score':('away_score',int),
                'kickoff_utc':('time_tz',lambda t: t.astimezone(UTC)),
                }

        games = dict([(game.game_id, game) for game in self.unarchived_games()])

        for game_state in live_games:
            self.logger.debug("Updating state for %s", game_state['eid'])
            if game_state['eid'] not in games:
                self.logger.warning("Parent Game object not found for eid=%s, skipping", game_state['eid'])
                self.logger.debug("Active games: %r", games)
                continue
            active_game = games[game_state['eid']]
            game, created = get_or_create(session, self.models.nfl.NFLGame, game=active_game, eid=game_state['eid'])
            if created:
                game.kickoff_utc = game_state['time_tz'].astimezone(UTC)
            updated = False
            for x, (y, f) in prop_map.items():
                new = game_state[y]
                old = game.__getattribute__(x)
                if f is not None:
                    new = f(new)
                if old != new:
                    game.__setattr__(x, new)
                    self.logger.debug("%s changed %s -> %s", x, old, new)
                    updated = True
                    if x == 'state':
                        self.logger.info("New state for %s", game_state['eid'])
                        self.generate_events(active_game, old, new, session)
            if updated:
                self.logger.debug("Game was updated %s", game_state['eid'])
                game.updated_utc = now()
        session.commit()
        new_int = decide_sleep(session, self.models.nfl.NFLGame, self.active_interval, self.interval) 
        session.close()
        if new_int:
            self.logger.debug("Shortened sleep: %s", new_int)
            return new_int

    def generate_events(self, game, from_gs, to_gs, session):
        self.logger.debug("State change %s -> %s for %s", from_gs, to_gs, game)
        now_ = now()
        for event in self.find_events(from_gs, to_gs):
            self.logger.info("Event %s for game %s", event, game)
            if event == EV_KICKOFF_SCHEDULED:
                dt = game.nfl_game.kickoff_utc
            else:
                dt = now_
            event, created = get_or_create(session, self.models.nfl.NFLGameEvent, game=game, event=event, datetime_utc=dt)

    def find_events(self, from_gs, to_gs):
        """Figure out which events must have happened to take us from one state to another"""
        transitions = GS_TRANSITIONS
        if to_gs in (GS_OT, GS_FO):
            transitions.update(GS_TRANSITIONS_OT)
        else:
            transitions.update(GS_TRANSITIONS_NORMAL)
        cur_gs = from_gs
        events = []
        while cur_gs != to_gs:
            found = False
            for (f,t), ev in transitions.items():
                if cur_gs == f:
                    events.append(ev)
                    cur_gs = t
                    found = True
                    break
            if not found:
                break
        if cur_gs != to_gs:
            events = []
        return events

class NFLTeamUpdater(GameThreadThread):
    interval = timedelta(hours=12)
    setup = True # Indicates that we want to be run once before threads are started

    def lap(self):
        session = self.Session()
        for short, info in nflteams.fullinfo.items():
            t, created = get_or_create(session, self.models.nfl.NFLTeam, id=short, city=info['city'], mascot=info['mascot'], subreddit=info['subreddit'].replace('/r/',''), twitter=info['twitter'])
            if created:
                self.logger.info("Adding team %r", t)
                session.add(t)
        session.commit()

class NFLLineUpdater(GameThreadThread):
    interval = timedelta(hours=1)

    def lap(self):
        session = self.Session()
        NFLGame = self.models.nfl.NFLGame
        for (home, away), lines in espn.get_lines().items():
            nflgame = session.query(NFLGame).filter(NFLGame.home_id == home, NFLGame.away_id == away).one_or_none()
            if nflgame is None:
                continue
            for book, (spread, total) in lines.items():
                line, created = get_or_create(session, self.models.nfl.NFLLine, game=nflgame.game, book=book)
                line.spread = spread
                line.total = total
        session.commit()

class NFLScheduleInfoUpdater(GameThreadThread):
    interval = timedelta(hours=1)
    setup = True

    def lap(self):
        session = self.Session()
        NFLGame = self.models.nfl.NFLGame
        season, game_type, week = schedule.get_week(now().date())
        for game in schedule.get_schedule(season, game_type, week):
            nflgame = session.query(NFLGame).filter(NFLGame.eid == game.eid).one_or_none()
            if nflgame is None:
                self.logger.debug("NFLGame missing for eid={0.eid}, skipping".format(game))
                continue
            nflgame.season = season
            nflgame.game_type = game_type
            nflgame.week = week
            if game.tv: # TV info disappears after game has played
                nflgame.tv = game.tv
            nflgame.site = game.site
            nflgame.place = game.place
        session.commit()


ALL = [
        NFLTeamUpdater,
        NFLBoxscoreUpdater,
        NFLGameStateUpdater,
        NFLTeamDataUpdater,
        NFLLineUpdater,
        NFLScheduleInfoUpdater,
        ]
