from bs4 import BeautifulSoup
import requests
import re

LINES_URL = 'http://www.espn.com/nfl/lines'

espnteams = {
        'Arizona': 'ARI',
        'Atlanta': 'ATL',
        'Baltimore': 'BAL',
        'Buffalo': 'BUF',
        'Carolina': 'CAR',
        'Bears': 'CHI',
        'Chicago': 'CHI',
        'Cincinnati': 'CIN',
        'Cleveland': 'CLE',
        'Dallas': 'DAL',
        'Denver': 'DEN',
        'Detroit': 'DET',
        'Green Bay': 'GB',
        'Houston': 'HOU',
        'Indianapolis': 'IND',
        'Jacksonville': 'JAX',
        'Kansas City': 'KC',
        'LA Chargers': 'LAC',
        'LA Rams': 'LA',
        'Miami': 'MIA',
        'Minnesota': 'MIN',
        'NY Giants': 'NYG',
        'NY Jets': 'NYJ',
        'New England': 'NE',
        'New Orleans': 'NO',
        'Oakland': 'OAK',
        'Philadelphia': 'PHI',
        'Pittsburgh': 'PIT',
        'San Francisco': 'SF',
        'Seattle': 'SEA',
        'Tampa Bay': 'TB',
        'Tennessee': 'TEN',
        'Washington': 'WAS',
}

def _extract_teams(s):
    m = re.match(r'(?P<away>.*) at (?P<home>.*) - .*', s)
    if m:
        home = espnteams[m.group('home')] if m.group('home') in espnteams else None
        away = espnteams[m.group('away')] if m.group('away') in espnteams else None
        if not home:
            print("        '%s': ''," % m.group('home'))
        if not away:
            print("        '%s': ''," % m.group('away'))
        return home, away

def _extract_lines(row, heads):
    provider = row.td.string.strip()
    i = 0
    spread = None
    total = None
    for td in row.find_all('td', recursive=False):
        head = heads[i]
        i += 1
        if td.string and td.string.strip().lower() == 'n/a':
            continue
        if head == 'TOTAL':
            total = td.table.tr.td.string.strip().lower().replace(' o/u', '')
        elif head == 'POINT SPREAD':
            if td.string and td.string.strip().lower() == 'even':
                spread = '0'
            else:
                spread = td.table.tr.td.find('br').next_sibling
    return provider, (spread, total)

def get_lines():
    """Gets lines for the current week"""
    soup = BeautifulSoup(requests.get(LINES_URL).content, 'html5lib')
    lines = {}
    away, home = None, None
    for row in soup.select("div#my-teams-table div.mod-content > table.tablehead > tbody > tr"):
        if 'stathead' in row['class']:
            away, home = _extract_teams(row.td.string)
            lines[(away, home)] = {}
        elif 'colhead' in row['class']:
            heads = tuple(map(lambda td: td.string.strip(), row.find_all('td')))
        elif 'oddrow' in row['class'] or 'evenrow' in row['class']:
            if 'colspan' in row.td.attrs:# and row.td['colspan'] == 6:
                continue
            provider, provider_lines = _extract_lines(row, heads)
            lines[(away, home)][provider] = provider_lines
    return lines

if __name__ == "__main__":
    import sys
    from pprint import pprint
    pprint(getattr(sys.modules[__name__], sys.argv[1])(*sys.argv[2:]))
