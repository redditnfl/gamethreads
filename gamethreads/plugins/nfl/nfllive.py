#!/usr/bin/env python
# TODO: Consider using burntsushi's nflgame instead
import pytz
import os
import urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta
from xml.etree import cElementTree as ElementTree
from glob import glob
from os.path import getmtime

EASTERN = pytz.timezone('US/Eastern')

def realteam(short):
    replacements = {
            'ARZ':'ARI',
            'CLV':'CLE',
            'HST':'HOU',
            'SL' :'LA',
            'STL' :'LA',
            'SD' :'LAC',
            'JAC':'JAX',
            }
    if short in replacements:
        return replacements[short]
    return short

def q(q):
    qs = {
            'P': 'Not started',
            'Pregame': 'Not started',
            '1': 'Q1',
            '2': 'Q2',
            'H': 'Halftime',
            '3': 'Q3',
            '4': 'Q4',
            'F': 'Final',
            '5': 'OT',
            'FO': 'Final (OT)',
            }
    if q in qs:
        return qs[q]
    return q

def get_games(url = None):
    if url is None:
        url = 'http://www.nfl.com/liveupdate/scorestrip/postseason/ss.xml'
        url = 'http://www.nfl.com/liveupdate/scorestrip/ss.xml'
    data = urllib.request.urlopen(url)
    try:
        tree = ElementTree.parse(data)
    except ElementTree.ParseError as e:
        return
    games = {'qtr': 'Final', 'games': []}
    for g in [g.attrib for g in tree.find('gms').findall('g')]:
        start_notz = datetime(
            int(g['eid'][0:4]),
            int(g['eid'][4:6]),
            int(g['eid'][6:8]),
        )
        if 't' in g and g['t'] != 'TBD':
            start_notz += timedelta(
                  hours=int(g['t'].split(':')[0])+12,
                minutes=int(g['t'].split(':')[1])
            )
            if g['eid'] in ('2016100200','2016102300','2016103000', '2016112400', '2017102900', '2017112300'): # Morning games
                start_notz -= timedelta(hours=12)
        day = int(start_notz.strftime('%w'))
        hour = int(start_notz.strftime('%H'))
        game = {
            'eid': g['eid'],
            'time': start_notz,
            'time_tz': EASTERN.localize(start_notz),
            'home': realteam(g['h']),
            'away': realteam(g['v']),
            'home_score': g['hs'],
            'away_score': g['vs'],
            'q': q(g['q']),
            'clock': g['k'] if 'k' in g else '',
            }
        if 'k' in g or game['q'] in ('Not started', 'Halftime'):
            games['qtr'] = '1'
        games['games'].append(game)
    games['games'].sort(key = lambda x: x['time'])
    return games

