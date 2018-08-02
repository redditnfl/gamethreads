from bs4 import BeautifulSoup
import requests

TEAM_URL = 'http://www.nfl.com/teams/profile?team={0}'

def get_record(team_id):
    """Get a team's record as (won,lost,tied)"""
    soup = BeautifulSoup(requests.get(TEAM_URL.format(team_id)).content, 'html5lib')
    record_str = soup.find('p', 'team-overall-ranking').span.string.strip()[1:-1]
    return tuple(map(lambda s: int(s) if s.isdigit() else 0, record_str.split('-')))

if __name__ == "__main__":
    import sys
    from pprint import pprint
    pprint(getattr(sys.modules[__name__], sys.argv[1])(*sys.argv[2:]))
