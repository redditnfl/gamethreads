from datetime import timedelta, datetime
from pprint import pprint
from urllib.request import urlopen
import urllib
import ujson
import pendulum
from sqlalchemy import func
from sqlalchemy.sql import exists
from sqlalchemy.orm import aliased
from sgqlc.operation import Operation

#from . import nflteams, nflcom, espn, nfllive, schedule, sites
from . import espn, sites, nflteams

from nflapi import NFL, shield
from nflapi.shield import OrderByDirection, WeekOrderBy

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
    nfl = NFL('gamethread/boxscore')
    
    def lap(self):
        session = self.Session()
        # Should probably get all at once
        # Make sure all games get a final update, even after they are completed
        for game in self.unarchived_games().join(Game.nfl_game).filter(NFLGame.state != GS_PENDING).filter(NFLGame.game_detail_id != None):
            self.logger.debug("Updating boxscore for %r", game)
            gamedata, created = get_or_create(session, NFLGameData, game=game)
            if gamedata.final:
                self.logger.debug("Game %r is final, skipping", game)
                continue
            json = self.get_json(game.nfl_game.game_detail_id)
            if not json:
                self.logger.debug("No data found for %r, skipping", game)
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

    def get_json(self, game_detail_id):
        if not game_detail_id:
            return
        try:
            op = Operation(shield.Viewer)
            gd = op.viewer.league.game_detail(id=game_detail_id)
            gd.home_points_q1()
            gd.home_points_q2()
            gd.home_points_q3()
            gd.home_points_q4()
            gd.home_points_total()
            gd.home_points_overtime()
            gd.home_points_overtime_total()
            gd.visitor_points_q1()
            gd.visitor_points_q2()
            gd.visitor_points_q3()
            gd.visitor_points_q4()
            gd.visitor_points_total()
            gd.visitor_points_overtime()
            gd.visitor_points_overtime_total()
            #gd.game_injuries()
            gd.scoring_summaries()
            gd.coin_toss_results()
            #gd.live_home_team_game_stats()
            #gd.live_home_player_game_stats()
            #gd.live_visitor_team_game_stats()
            #gd.live_visitor_player_game_stats()
            result, json = self.nfl.shield.query(op, return_json=True)
            json = json['data']['viewer']['league']['gameDetail']
            return json
        except Exception as e:
            self.logger.exception("Error getting boxscore for %s", game_detail_id)
            

class NFLTeamDataUpdater(GameThreadThread):
    interval = timedelta(minutes=30)
    setup = True # Indicates that we want to be run once before threads are started
    nfl = NFL('gamethread/teamdata')

    def lap(self):
        session = self.Session()
        teams = session.query(NFLTeam)
        records = self.get_records()
        for team in teams.all():
            try:
                record = records.get(team.id, None)
                if record and record != (team.record_won, team.record_lost, team.record_tied):
                    self.logger.info("Updating record for %r to %r", team, record)
                    team.record = record
            except Exception as e:
                self.logger.exception("Error updating record for %r", team)
        session.commit()

    def get_records(self):
        # Grab all record objects for the latest week
        # That should be the current records, if I'm not mistaken
        week = self.nfl.schedule.current_week()
        standings = self.nfl.football.standings_by_week(week.season_value, week.season_type, week.week_value).weeks[0].standings
        return {r.team.id: (r.overall.wins, r.overall.losses, r.overall.ties) for r in standings} 


class NFLGameStateUpdater(GameThreadThread):
    interval = timedelta(minutes=15)
    active_interval = timedelta(seconds=30)
    setup = True
    nfl = NFL('gamethread/gamestate')

    def get_game_detail_ids(self, ids):
        return [(game_id, self.nfl.game.game_detail_id_for_id(game_id)) for game_id in ids]

    def lap(self):
        session = self.Session()
        games = self.unarchived_games().filter(NFLGame.game_detail_id == None)
        lut = {game.game_id: game for game in games}
        for game_id, gdi in self.get_game_detail_ids([game.game_id for game in games]):
            lut[game_id].game_detail_id = gdi

        games = self.unarchived_games().join(Game.nfl_game, full=True).filter(NFLGame.game_detail_id != None)
        lut = {game.nfl_game.game_detail_id: game for game in games}
        ids = lut.keys()
        for gd in self.get_game_details(ids):
            if not hasattr(gd, 'id'):
                # Sometimes we know the id of objects that don't exist (??)
                continue
            game = lut[gd.id]
            nflgame = game.nfl_game
            nflgame.home_score = gd.home_points_total
            nflgame.away_score = gd.visitor_points_total
            old = nflgame.state
            new = self.state(gd.phase, gd.period)
            nflgame.state = new
            if old != new:
                self.logger.info("New state for %r -> %s", nflgame, new)
                self.generate_events(game, old, new, session)
            if new in GS_FINAL:
                nflgame.seconds_left = None
            else:
                nflgame.clock = gd.game_clock
            nflgame.updated_utc = now()
        
        session.commit()
        new_int = decide_sleep(session, NFLGame, self.active_interval, self.interval) 
        session.close()
        if new_int:
            self.logger.debug("Shortened sleep: %s", new_int)
            return new_int

    def state(self, phase, period):
        if phase == shield.Phase.INGAME:
            return [GS_Q1, GS_Q2, GS_Q3, GS_Q4, GS_OT, GS_OT][period-1]
            pass
        mapping = {
                shield.Phase.PREGAME: GS_PENDING,
                shield.Phase.HALFTIME: GS_HT,
                shield.Phase.SUSPENDED: GS_SUSPENDED,
                shield.Phase.FINAL: GS_F,
                shield.Phase.FINAL_OVERTIME: GS_FO,
                }
        return mapping[phase]

    def get_game_details(self, ids):
        if len(ids) == 0:
            return []
        op = Operation(shield.Viewer)
        gd = op.viewer.league.game_details_by_ids(ids=ids)
        gd.id()
        gd.game_clock()
        gd.home_points_q1()
        gd.home_points_q2()
        gd.home_points_q3()
        gd.home_points_q4()
        gd.home_points_total()
        gd.home_points_overtime()
        gd.home_points_overtime_total()
        gd.visitor_points_q1()
        gd.visitor_points_q2()
        gd.visitor_points_q3()
        gd.visitor_points_q4()
        gd.visitor_points_total()
        gd.visitor_points_overtime()
        gd.visitor_points_overtime_total()
        gd.period()
        gd.phase()

        result = self.nfl.shield.query(op)
        return result.viewer.league.game_details_by_ids

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
    

class NFLTeamUpdater(GameThreadThread):
    interval = timedelta(hours=12)
    setup = True # Indicates that we want to be run once before threads are started
    nfl = NFL('gamethread/team')

    def lap(self):
        session = self.Session()
        for team in self.get_teams():
            t, created = get_or_create(session, NFLTeam, id=team.id)
            t.abbreviation = team.abbreviation
            t.city = team.location
            t.mascot = team.nick_name
            t.fullname = team.full_name
            teaminfo = nflteams.get_team(t.abbreviation)
            if teaminfo:
                t.subreddit = teaminfo['subreddit'].replace('/r/', '')
            t.twitter = ''
            if created:
                self.logger.info("Adding team %r", t)
                session.add(t)

        session.commit()

    def get_teams(self):
        week = self.nfl.schedule.current_week()
        return self.nfl.football.teams_by_season(week.season_value).teams


class NFLLineUpdater(GameThreadThread):
    interval = timedelta(hours=1)
    setup = False

    def lap(self):
        session = self.Session()
        for (home, away), lines in espn.get_lines().items():
            ht = aliased(NFLTeam)
            at = aliased(NFLTeam)
            nflgame = session.query(NFLGame).join(ht, NFLGame.home).join(at, NFLGame.away).filter(ht.abbreviation == home, at.abbreviation == away).order_by(NFLGame.kickoff_utc.desc()).first()
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
    nfl = NFL('gamethread/schedule')

    def lap(self):
        session = self.Session()
        
        base_games = self.pending_games()
        ids = [game.game_id for game in self.pending_games()]
        
        for sg in self.get_games(ids):
            if not hasattr(sg, 'id'):
                continue
            base_game = session.query(Game).filter(Game.game_id == sg.id).one()
            nflgame, created = get_or_create(session, NFLGame, game=base_game, shieldid=sg.id)
            
            game = sg
            
            nflgame.home_id = game.home_team.id
            nflgame.away_id = game.away_team.id
            nflgame.season = game.season
            nflgame.season_type = game.season_type
            nflgame.week_type = game.week_type
            nflgame.week = game.week
            for ext in game.external_ids:
                if ext.source == 'gamedetail':
                    nflgame.game_detail_id = ext.id
            channels = set()
            for channel in game.broadcast_info.away_network_channels + game.broadcast_info.home_network_channels:
                channels.add(channel)
            nflgame.tv = ", ".join(channels)
            nflgame.site = game.venue.name
            if nflgame.site in sites.sites:
                nflgame.place = sites.sites[nflgame.site][1]
            else:
                raise Exception("Unknown site: %s" % nflgame.site)
            if game.time:
                nflgame.kickoff_utc = pendulum.parse(game.time).astimezone(pendulum.UTC)

            if created:
                self.logger.info("Adding NFLGame for %r", game)
                nflgame.home_score = 0
                nflgame.away_score = 0
                if nflgame.kickoff_utc > now():
                    nflgame.state = GS_PENDING
                else:
                    nflgame.state = GS_UNKNOWN
        
        session.commit()

    def get_games(self, ids):
        for game_id in ids:
            yield self.nfl.game.by_id(game_id)


class NFLForecastUpdater(GameThreadThread):
    interval = timedelta(minutes=10)
    setup = True #False

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
        #NFLTeamUpdater,
        NFLTeamDataUpdater,
        NFLScheduleInfoUpdater,
        NFLBoxscoreUpdater,
        NFLGameStateUpdater,
        #NFLForecastUpdater,
        NFLLineUpdater,
        ]
