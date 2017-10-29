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

WEEK = timedelta(days=7)

# Tuesday of the first week with games in each season. Day after labor day
STARTDAYS = [
        date(2014, 9, 2),
        date(2015, 9, 8),
        date(2016, 9, 6),
        date(2017, 9, 5),
        date(2018, 9, 4),
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
    def __init__(self, date, home, away, tv, eid, site):
        self.date = date
        self.home = home
        self.away = away
        self.tv = tv
        self.eid = eid
        self.site = site

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

    return Game(eid=eid, tv=tv, date=None, home=None, away=None, site=None)

def tz_for_site(site):
    EST = pytz.timezone('US/Eastern')
    CST = pytz.timezone('US/Central')
    PST = pytz.timezone('US/Pacific')
    MST_NODST = pytz.timezone('US/Arizona') # No DST
    MST = pytz.timezone('America/Denver')
    GMT = pytz.timezone('Europe/London')
    sites = {
            'Gillette Stadium': EST,
            'Georgia Dome': EST,
            'Mercedes-Benz Stadium': EST,
            'AT&T Stadium': CST,
            'Arrowhead Stadium': CST,
            'Lambeau Field': CST,
            'NRG Stadium': CST,
            'CenturyLink Field': PST,
            'New Era Field': EST,
            'Nissan Stadium': CST,
            'Lincoln Financial Field': EST,
            'Hard Rock Stadium': EST,
            'EverBank Field': EST,
            'Lucas Oil Stadium': EST,
            'Bank of America Stadium': EST,
            'FirstEnergy Stadium': EST,
            'Ford Field': EST,
            'Levi\'s Stadium': PST,
            u'Levi\'s® Stadium': PST,
            'Raymond James Stadium': EST,
            'Los Angeles Memorial Coliseum': PST,
            'MetLife Stadium': EST,
            'Soldier Field': CST,
            'M&T Bank Stadium': EST,
            'Paul Brown Stadium': EST,
            'U.S. Bank Stadium': CST,
            'University of Phoenix Stadium': MST_NODST,
            'Qualcomm Stadium': PST,
            'StubHub Center': PST,
            'Sports Authority Field at Mile High': MST,
            'FedExField': EST,
            'Oakland Coliseum': PST,
            'Mercedes-Benz Superdome': CST,
            'Heinz Field': EST,

            'Estadio Azteca': pytz.timezone('America/Mexico_City'),
            'Wembley Stadium': GMT,
            'Twickenham Stadium': GMT,
            'Tom Benson Hall of Fame Stadium': EST,
            'Camping World Stadium': EST,
            }
    if site in sites:
        return sites[site]
    else:
        raise Exception("Unknown site: " + site)

def parse_schedule(data):
    soup = BeautifulSoup(data, "html5lib")
    games = {}

    # Grabs most info
    for div in soup.find_all("div", class_="schedules-list-content"):
        eid = div['data-gameid']
        site = div['data-site']
        date_str = eid[0:8] + 'T' + div['data-localtime']
        date_naive = datetime.strptime(date_str, '%Y%m%dT%H:%M:%S')
        date = tz_for_site(site).localize(date_naive)
        game = Game(eid=eid, date=date, site=site, home=get_team(div['data-home-abbr']), away=get_team(div['data-away-abbr']), tv=None)
        games[game.eid] = game

    for li in soup.find_all("li", class_='schedules-list-matchup'):
        game = parse_game(li)
        if game.eid in games:
            games[game.eid]._replace(tv=game.tv)
    return sorted(games.values(), key=lambda g: g.eid)

def get_url(season, game_type, week):
    return "http://www.nfl.com/schedules/{season}/{game_type}{week}".format(season=season, game_type=game_type, week=week if week else '')

def get_schedule(season, game_type, week):
    url = get_url(season, game_type, week)
    schedule = parse_schedule(requests.get(url).content)
    return schedule

if __name__ == "__main__":
    import doctest
    import sys
    from pprint import pprint
    doctest.testmod()
    if len(sys.argv) == 4:
        pprint(get_schedule(*sys.argv[1:]))
    else:
        pprint(get_schedule(*get_week(datetime.now().date())))
