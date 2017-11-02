import json
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship, backref
from gamethreads import Base
from gamethreads.util import now
from . import const


class NFLTeam(Base):
    __tablename__ = 'nfl_team'

    id = Column(String(length=3), primary_key=True)
    city = Column(String)
    mascot = Column(String)
    subreddit = Column(String)
    twitter = Column(String)
    record_won = Column(Integer)
    record_lost = Column(Integer)
    record_tied = Column(Integer)
    record_updated_utc = Column(DateTime(timezone=True))

    @property
    def fullname(self):
        return "{0.city} {0.mascot}".format(self)

    @property
    def record_games(self):
        return self.record_won + self.record_lost + self.record_tied

    @property
    def games(self):
        return self.home_games + self.away_games

    @property
    def record(self):
        w, l, t = (self.record_won, self.record_lost, self.record_tied)
        # See if any games ended after the record was updated and add the result
        for game in self.games:
            for event in game.game.nfl_events:
                if event.event in const.GS_FINAL and event.datetime_utc > self.record_updated_utc:
                    if game.winner == self:
                        w += 1
                    elif game.loser == self:
                        l += 1
                    elif game.is_tie:
                        t += 1
        return w, l, t

    @record.setter
    def record(self, value):
        w,l,t = value
        self.record_won = w
        self.record_lost = l
        self.record_tied = t
        self.record_updated_utc = now()

    @property
    def formatted_record(self):
        w, l, t = self.record
        if t > 0:
            return "{0}-{1}-{2}".format(w, l, t)
        return "{0}-{1}".format(w, l)


    def __str__(self):
        return self.fullname

    def __repr__(self):
        return "<Team(id=%s, city=%s, mascot=%s>" % (self.id, self.city, self.mascot)

def sort_passing(x):
    return [x[key] for key in ('cmp', 'yds', 'att', 'tds')]

def sort_rushing(x):
    return [x[key] for key in ('yds', 'att', 'lng', 'tds')]

def sort_receiving(x):
    return [x[key] for key in ('yds', 'rec', 'lng', 'tds')]

def sort_yards(x):
    return x['yds']

class NFLGameData(Base):
    __tablename__ = 'nfl_game_data'

    id = Column(Integer, primary_key=True)
    datatype = Column(String(255))
    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship("Game", backref=backref('nfl_data', order_by=datatype, uselist=False), foreign_keys='NFLGameData.game_id', lazy='joined')
    content_json = Column(String)
    updated_utc = Column(DateTime(timezone=True))
    
    local_tz = None
    
    @property
    def updated(self):
        if self.local_tz is None:
            return self.updated_utc
        else:
            return self.updated_utc.astimezone(self.local_tz)
    
    @property
    def age(self):
        try:
            return now() - self.updated_utc
        except TypeError as e:
            return None

    @property
    def content(self):
        return json.loads(self.content_json) if self.content_json else None

    @content.setter
    def content(self, value):
        self.content_json = json.dumps(value)
        self.updated_utc = now()

    @property
    def performers(self):
        ret = {'home': {}, 'away': {}}
        js = self.content

        for who in 'home', 'away':
            for stat in ('passing', 'rushing', 'receiving'):
                if stat in js[who]['stats']:
                    ret[who][stat] = list(js[who]['stats'][stat].values())
                    ret[who][stat].sort(key = sort_yards, reverse=True)
                    ret[who][stat] = [dict(list(x.items()) + [('team', js[who]['abbr'])]) for x in ret[who][stat]]
                else:
                    ret[who][stat] = []
            ret[who]['passing'].sort(key = sort_passing, reverse=True)
            ret[who]['rushing'].sort(key = sort_rushing, reverse=True)
            ret[who]['receiving'].sort(key = sort_receiving, reverse=True)
        return ret

    def __repr__(self):
        return "<NFLGameData(id={0.id}, game={0.game}, datatype={0.datatype})>".format(self)


class NFLGameEvent(Base):

    __tablename__ = 'nfl_game_events'
    id = Column(Integer, primary_key=True)
    datetime_utc = Column(DateTime(timezone=True))
    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship("Game", backref=backref('nfl_events', order_by=datetime_utc), foreign_keys='NFLGameEvent.game_id', lazy='joined')
    event = Column(Enum(*const.EVENTS, name='NFL_EVENT'))
    
    local_tz = None
    
    @property
    def datetime(self):
        if self.local_tz is None:
            return self.datetime_utc
        else:
            return self.datetime_utc.astimezone(self.local_tz)

    def __repr__(self):
        return "<NFLGameEvent(game={0.game}, event={0.event}, datetime_utc={0.datetime_utc}>".format(self)

class NFLLine(Base):
    """Spread and total is relative to the home team"""
    __tablename__ = 'nfl_line'

    id = Column(Integer, primary_key=True)
    book = Column(String)
    spread = Column(String)
    total = Column(String)
    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship("Game", backref=backref('nfl_lines', order_by=book), foreign_keys='NFLLine.game_id', lazy='joined')


class NFLGame(Base):
    __tablename__ = 'nfl_game'

    id = Column(Integer, primary_key=True) 
    eid = Column(String, unique=True)
    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship("Game", backref=backref('nfl_game', uselist=False), foreign_keys='NFLGame.game_id', lazy='joined')
    home_id = Column(String(3), ForeignKey('nfl_team.id'))
    home = relationship("NFLTeam", backref=backref('home_games', order_by=eid), foreign_keys='NFLGame.home_id', lazy='joined')
    away_id = Column(String(3), ForeignKey('nfl_team.id'))
    away = relationship("NFLTeam", backref=backref('away_games', order_by=eid), foreign_keys='NFLGame.away_id', lazy='joined')
    home_score = Column(Integer)
    away_score = Column(Integer)
    seconds_left = Column(Integer, nullable=True)
    kickoff_utc = Column(DateTime(timezone=True))
    state = Column(Enum(*const.GS, name='NFL_GAME_STATE'))
    updated_utc = Column(DateTime(timezone=True))

    local_tz = None

    @property
    def kickoff(self):
        if self.local_tz is None:
            return self.kickoff_utc
        else:
            return self.kickoff_utc.astimezone(self.local_tz)

    @property
    def updated(self):
        if self.local_tz is None:
            return self.updated_utc
        else:
            return self.updated_utc.astimezone(self.local_tz)

    @property
    def winner(self):
        if self.is_tie:
            return None
        return self.home if self.home_score > self.away_score else self.away

    @property
    def loser(self):
        if self.is_tie:
            return None
        return self.home if self.home_score < self.away_score else self.away

    @property
    def is_tie(self):
        return self.home_score == self.away_score

    @property
    def age(self):
        try:
            return now() - self.updated_utc
        except TypeError as e:
            return None

    @property
    def clock(self):
        try:
            minutes = int(self.seconds_left/60)
            seconds = self.seconds_left % 60
            return "%02d:%02d" % (minutes, seconds)
        except (ValueError, TypeError) as e:
            return "--:--"

    @clock.setter
    def clock(self, value):
        try:
            minutes, seconds = value.split(':')
            self.seconds_left = int(minutes)*60+int(seconds)
        except (AttributeError, ValueError) as e:
            self.seconds_left = None

    def __repr__(self):
        return "<Game(eid=%s,home=%s,away=%s)>" % (self.eid, self.home, self.away)

    def __str__(self):
        return "{0.away.id} @ {0.home.id}".format(self)
