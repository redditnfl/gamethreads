from datetime import timedelta, datetime
from urllib.request import urlopen
import urllib
import ujson
from sqlalchemy import func
from sqlalchemy.sql import exists

from . import nflteams, nflcom, espn, nfllive, schedule, sites

from ...util import get_or_create, now
from ...basethread import GameThreadThread
from ...models import Game

from .const import *
from .models import *

from yr.libyr import Yr
import pytz
UTC = pytz.utc

GAMETYPE = 'nfl'


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
    active_interval = timedelta(minutes=2)
    
    def lap(self):
        session = self.Session()
        # Make sure all games get a final update, even after they are completed
        for game in self.unarchived_games().join(Game.nfl_game).filter(NFLGame.state != GS_PENDING):
            self.logger.info("Updating boxscore for %r", game)
            gamedata, created = get_or_create(session, NFLGameData, game=game)
            json = self.get_json(game.game_id)
            if not json:
                continue
            if 'drives' in json:
                del(json['drives'])
            gamedata.content = json
            if game.nfl_game.state in GS_FINAL:
                self.logger.info("Game %r is final. No more boxscore updates", game)
                gamedata.final = True
        session.commit()

        new_int = decide_sleep(session, NFLGame, self.active_interval, self.interval)
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
            self.logger.exception("Error getting boxscore for %s", eid)
            

class NFLTeamDataUpdater(GameThreadThread):
    interval = timedelta(minutes=30)

    def lap(self):
        session = self.Session()
        teams = session.query(NFLTeam)
        for team in teams.all():
            try:
                if team.id in ['AFC', 'NFC', 'APR', 'NPR']:
                    continue
                record = nflcom.get_record(team.id)
                if record != (team.record_won, team.record_lost, team.record_tied):
                    self.logger.info("Updating record for %s to %r", team, record)
                    team.record = record
            except Exception as e:
                self.logger.exception("Error updating record for %r", team)
        session.commit()


class NFLGameStateUpdater(GameThreadThread):
    interval = timedelta(minutes=15)
    active_interval = timedelta(seconds=30)
    setup = True

    def lap(self):
        session = self.Session()
#        live_games = nfllive.get_games()['games']
#        if live_games is None or len(live_games) == 0:
#            self.logger.warning("No games found. Skipping")
#            return
#, url='http://rasher.dk/tmp/ss.xml'

        prop_map = {
                'state':('q',None),
                'home_id':('home',None),
                'away_id':('away',None),
                'clock':('clock',lambda s: '--:--' if s == '' else s),
                'home_score':('home_score',int),
                'away_score':('away_score',int),
#                'kickoff_utc':('time_tz',lambda t: t.astimezone(UTC)),
                }

        lookahead = timedelta(hours=24)
        cutoff = now() + lookahead
        games = self.unarchived_games()
        for active_game in games:
            boxscore = self.get_json(active_game.game_id)
            if not boxscore:
                self.logger.warning("Could not get boxscore for %s", active_game.game_id)
                continue
            game_state = {
                    'eid': active_game.game_id,
                    'q': nfllive.q(boxscore['qtr']),
                    'home': boxscore['home']['abbr'],
                    'away': boxscore['away']['abbr'],
                    'clock': boxscore['clock'],
                    'home_score': boxscore['home']['score']['T'],
                    'away_score': boxscore['away']['score']['T'],
                    }

            self.logger.debug("Updating state for %s", game_state['eid'])
#            if game_state['eid'] not in games:
#                self.logger.warning("Parent Game object not found for eid=%s, skipping", game_state['eid'])
#                self.logger.debug("Active games: %r", games)
#                continue
            if 'TBD' in (game_state['home'], game_state['away']):
                self.logger.warning("Game participants still TBD for eid=%s, skipping", game_state['eid'])
                continue
#            active_game = games[game_state['eid']]
            game, created = get_or_create(session, NFLGame, game=active_game, eid=game_state['eid'])
#            if created:
#                game.kickoff_utc = game_state['time_tz'].astimezone(UTC)
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
        new_int = decide_sleep(session, NFLGame, self.active_interval, self.interval) 
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
            event, created = get_or_create(session, NFLGameEvent, game=game, event=event, datetime_utc=dt)

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
    
    def get_json(self, eid):
        """Copy-pasted, eek"""
        fmt = 'http://www.nfl.com/liveupdate/game-center/{eid}/{eid}_gtd.json'
        url = fmt.format(eid=eid)
        try:
            return ujson.load(urlopen(url))[eid]
        except urllib.error.HTTPError as e:
            self.logger.info("Could not get boxscore for %s - not started?", eid)
        except Exception as e:
            self.logger.exception("Error getting boxscore for %s", eid)

class NFLTeamUpdater(GameThreadThread):
    interval = timedelta(hours=12)
    setup = True # Indicates that we want to be run once before threads are started

    def lap(self):
        session = self.Session()
        for short, info in nflteams.fullinfo.items():
            t, created = get_or_create(session, NFLTeam, id=short, city=info['city'], mascot=info['mascot'], subreddit=info['subreddit'].replace('/r/',''), twitter=info['twitter'])
            if created:
                self.logger.info("Adding team %r", t)
                session.add(t)
        session.commit()

class NFLLineUpdater(GameThreadThread):
    interval = timedelta(hours=1)
    setup = False

    def lap(self):
        session = self.Session()
        for (home, away), lines in espn.get_lines().items():
            nflgame = session.query(NFLGame).filter(NFLGame.home_id == home, NFLGame.away_id == away).order_by(NFLGame.kickoff_utc.desc()).first()
            if nflgame is None:
                self.logger.warning("No game found for %s@%s", away, home)
                continue
            for book, (spread, total) in lines.items():
                line, created = get_or_create(session, NFLLine, game=nflgame.game, book=book)
                line.spread = spread
                line.total = total
        session.commit()

class NFLScheduleInfoUpdater(GameThreadThread):
    interval = timedelta(hours=1)
    setup = True

    def lap(self):
        session = self.Session()
        season, game_type, week = schedule.get_week(now().date())
        for game in schedule.get_schedule(season, game_type, week):
            self.logger.debug("Updating schedule info for game %s", game.eid)
            if game.home is None or game.away is None:
                self.logger.warning("Game %s has None home or away, skipping", game.eid)
                continue
            basegame = session.query(Game).filter(Game.game_id == game.eid).one_or_none()
            if basegame is None:
                self.logger.info("Game %s does not exist, skipping", game.eid)
                continue
            nflgame, created = get_or_create(session, NFLGame, game=basegame, eid=basegame.game_id)
            if created:
                self.logger.info("Adding NFLGame for %s", game.eid)
                nflgame.home_score = 0
                nflgame.away_score = 0
                if game.date < now():
                    nflgame.state = GS_PENDING
                else:
                    nflgame.state = GS_UNKNOWN

            nflgame.home_id = game.home['short']
            nflgame.away_id = game.away['short']
            nflgame.season = season
            nflgame.game_type = game_type
            nflgame.week = week
            if game.tv: # TV info disappears after game has played
                nflgame.tv = game.tv
            nflgame.site = game.site
            nflgame.place = game.place
            if game.date:
                nflgame.kickoff_utc = game.date
            else:
                self.logger.warn("No kickoff for game %s", game.eid)
            if game.eid == '2018092311':
                game.date -= timedelta(hours=1)
        session.commit()

class NFLForecastUpdater(GameThreadThread):
    interval = timedelta(minutes=10)
    setup = False

    def lap(self):
        session = self.Session()
        for game in self.games().filter(Game.state == Game.PENDING):
            if not game.nfl_game or not game.nfl_game.site:
                self.logger.warning("Game %s has no NFLGame or site. Not getting weather", game)
                continue
            try:
                tz = sites.sites[game.nfl_game.site][0]
                forecast = self.get_forecast(game.nfl_game.place, game.nfl_game.kickoff_utc, tz)
                if forecast:
                    fm, created = get_or_create(session, NFLForecast, game=game)
                    fm.symbol_name = forecast['symbol']['@name']
                    fm.symbol_var = forecast['symbol']['@var']
                    fm.temp_c = forecast['temperature']['@value']
                    fm.pressure_hpa = forecast['pressure']['@value']
                    fm.windspeed_mps = forecast['windSpeed']['@mps']
                    fm.prec_mm = forecast['precipitation']['@value']
            except Exception as e:
                self.logger.exception("Error getting weather for %r", game.nfl_game)
        session.commit()

    def get_forecast(self, place, kickoff, tz):
        for forecast in Yr(location_name=place).forecast():
            forecast = self.localize_times(forecast, tz)
            if forecast['@from'] <= kickoff < forecast['@to']:
                self.logger.debug("Found weather %r", forecast)
                return forecast

    def localize_times(self, forecast, tz):
        def localize(ts, tz):
            ts = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
            return tz.localize(ts)
        forecast['@from'] = localize(forecast['@from'], tz)
        forecast['@to'] = localize(forecast['@to'], tz)
        return forecast


ALL = [
        NFLTeamUpdater,
        NFLBoxscoreUpdater,
        NFLGameStateUpdater,
        NFLTeamDataUpdater,
        NFLLineUpdater,
        NFLScheduleInfoUpdater,
        NFLForecastUpdater,
        ]
