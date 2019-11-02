#!/usr/bin/env python
"""
An NFL week runs from Tuesday (first day after last week's games) to Monday
"""
from datetime import date, timedelta, datetime
import math
from bs4 import BeautifulSoup
from collections import namedtuple
import requests
import pytz
from .nflteams import get_team
from .sites import sites

WEEK = timedelta(days=7)

# Tuesday of the first week with games in each season. Day after labor day
STARTDAYS = [
        date(2014, 9, 2),
        date(2015, 9, 8),
        date(2016, 9, 6),
        date(2017, 9, 5),
        date(2018, 9, 4),
        date(2019, 9, 5),
        ]

PRE = 'PRE'
REG = 'REG'
POST = 'POST'

#Game = namedtuple('Game', ['date', 'home', 'away', 'tv', 'eid', 'site'])
#def game_cmp(self, other):
#    if self.date != other.date:
#        return cmp(self.date, other.date)
#    else:
#        return cmp(self.eid, other.eid)
#Game.__cmp__ = game_cmp
class Game:
    def __init__(self, date, home, away, tv, eid, site, place):
        self.date = date
        self.home = home
        self.away = away
        self.tv = tv
        self.eid = eid
        self.site = site
        self.place = place

    def __lt__(self, other):
        if self.date != other.date:
            return self.date < other.date
        else:
            return self.eid < other.eid

    def _replace(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __str__(self):
        return "{0.away}@{0.home}".format(self)

    def __repr__(self):
        return "<Game home={0.home}, away={0.away}, eid={0.eid}>".format(self)

def get_week(for_date):
    """Return the NFL week for a specific date

    >>> get_week(date(2015, 2, 7))
    (2014, 'POST', None)
    >>> get_week(date(2016, 11, 20))
    (2016, 'REG', 11)
    >>> get_week(date(2016, 8, 7))
    (2016, 'PRE', 0)
    >>> get_week(date(2016, 5, 5))
    (None, None, None)
    >>> get_week(date(2017, 10, 26))
    (2017, 'REG', 8)

    """
    start = None
    for n in STARTDAYS:
        if n > (for_date + 5*WEEK):
            break
        start = n

    d = for_date - start
    w = 1 + math.floor(d.days / WEEK.days)
    t = None
    y = start.year

    if -4 <= w <= 0:
        t = PRE
        w += 4
    elif 1 <= w <= 17:
        t = REG
    elif 18 <= w <= 23:
        t = POST
        w = None
    else:
        w = None
        y = None
    
    return y, t, w

def parse_game(li):
    #away = li.select('span.team-name.away')[0].string
    #home = li.select('span.team-name.home')[0].string
    eid = li.find('div', class_='schedules-list-content')['data-gameid']
    try:
        tv = li.select('div.list-matchup-row-tv span')[0]['title']
        tv = tv.replace('NFL NETWORK', 'NFLN')
    except IndexError as e:
        tv = None

    return Game(eid=eid, tv=tv, date=None, home=None, away=None, site=None, place=None)

def parse_schedule(data):
    soup = BeautifulSoup(data, "html5lib")
    games = {}

    # Grabs most info
    for div in soup.find_all("div", class_="schedules-list-content"):
        eid = div['data-gameid']
        site = div['data-site']
        if site in sites:
            tz, place = sites[site]
        else:
            raise Exception("Unknown site %s" % site)
        if not div['data-localtime']:
            div['data-localtime'] = "20:00:01"
        date_str = eid[0:8] + 'T' + div['data-localtime']
        date_naive = datetime.strptime(date_str, '%Y%m%dT%H:%M:%S')
        date = tz.localize(date_naive)
        game = Game(eid=eid, date=date, site=site, home=get_team(div['data-home-abbr']), away=get_team(div['data-away-abbr']), tv=None, place=place)
        games[game.eid] = game

    for li in soup.find_all("li", class_='schedules-list-matchup'):
        game = parse_game(li)
        if game.eid in games:
            games[game.eid]._replace(tv=game.tv)
    return sorted(games.values(), key=lambda g: g.eid)

def get_url(season, game_type, week):
    return "http://www.nfl.com/schedules/{season}/{game_type}{week}".format(season=season, game_type=game_type, week='' if week is None else week)

def get_schedule(season, game_type, week):
    url = get_url(season, game_type, week)
    schedule = parse_schedule(requests.get(url).content)
    return schedule

def main():
    import doctest
    import sys
    from pprint import pprint
    doctest.testmod()
    if len(sys.argv) == 4:
        games = get_schedule(*sys.argv[1:])
    else:
        games = get_schedule(*get_week(datetime.now().date()))

    for game in games:
        print("{g.away[short]}@{g.home[short]} - {g.date}".format(g=game))
