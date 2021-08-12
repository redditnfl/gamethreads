from bs4 import BeautifulSoup
import requests
import re

LINES_URL = 'http://www.espn.com/nfl/lines'

espnteams = {
        'WSH': 'WAS',
        'LAR': 'LA',
}


def get_lines():
    """Gets lines for the current week"""
    soup = BeautifulSoup(requests.get(LINES_URL).content, 'html5lib')
    lines = {}
    away, home = None, None
    for game in soup.select("tbody.Table__TBODY"):
        data = {}
        for side, team_row in zip(['away', 'home'], game.select("tr")):
            tds = team_row.find_all('td')
            espn_abbr = tds[0].select("a")[0]["href"].split('/')[5].upper()
            team = espnteams.get(espn_abbr, espn_abbr)
            line_data = tds[2].string.strip()
            data[side] = [team, line_data]
        away = data['away']
        home = data['home']
        if away[1].startswith('-'):
            spread = away[1].replace('-', '+')
            total = home[1]
        else:
            spread = home[1]
            total = away[1]
        lines[(home[0], away[0])] = {
                'espn': (spread, total),
                'Caesars': (spread, total), # It's not. I think. Laziness.
                }
    return lines


if __name__ == "__main__":
    import sys
    from pprint import pprint
    pprint(getattr(sys.modules[__name__], sys.argv[1])(*sys.argv[2:]))
