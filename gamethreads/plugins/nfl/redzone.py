import os
import sys
import time
import difflib
from datetime import datetime, timedelta

import pytz
from praw import Reddit
import sqlalchemy
from sqlalchemy.orm import sessionmaker

from .models import *

EST = pytz.timezone('US/Eastern')

MARKER_START = '######[](#start-box-score)'
MARKER_END = '######[](#end-box-score)'

def make_link(threads, key):
    if key in threads:
        return "[Link]({0.url})".format(threads.get(key))
    return ""

def my_replace(marker_start, marker_end, content, subject):
    replacement = "%s\n\n%s\n\n%s" % (marker_start, content, marker_end)
    return re.sub(r'(?ms)' + re.escape(marker_start) + '.*' + re.escape(marker_end), replacement, subject)

def print_diff(before, after, revision):
    revision = datetime.utcfromtimestamp(revision)
    now = datetime.utcnow().replace(microsecond=0)
    diff = ""
    for line in difflib.unified_diff(before.split("\n"), after.split("\n"), fromfile="before", tofile="after", n=2, lineterm="", fromfiledate=str(revision), tofiledate=str(now)):
        diff += line + "\n"
    print(diff)

def main():
    engine = sqlalchemy.create_engine('postgresql+psycopg2://{0[PGUSER]}:{0[PGPASSWORD]}@{0[PGHOST]}:{0[PGPORT]}/{0[PGDATABASE]}'.format(os.environ), echo = False)
    Session = sessionmaker(bind=engine)

    session = Session()
    day = EST.localize(datetime(2017, 12, 31))
    sub = 'nfl'
    nextday = day + timedelta(days=1)
    table  = "|          |   |    |   |          |   |                |                      |\n"
    table += "|:---------|--:|:--:|:--|---------:|--:|:--------------:|:--------------------:|\n"
    table += "| **Away** |   |    |   | **Home** |   | **Gamethread** | **Post Game Thread** |\n"
    for nflgame in session.query(NFLGame).filter(NFLGame.kickoff_utc > day, NFLGame.kickoff_utc <= nextday).order_by(NFLGame.kickoff_utc, NFLGame.eid):
        if nflgame.is_primetime:
            continue
        threads = {}
        for thread in nflgame.game.threads:
            if thread.sub.name == sub:
                threads[thread.thread_type] = thread
        table += "|[*{0.away.id}*](/r/{0.away.subreddit}) | {0.away_score} | at | {0.home_score} | [*{0.home.id}*](/r/{0.home.subreddit}) | {0.state} | {gt} | {pgt}|\n".format(nflgame, gt=make_link(threads, 'gamethread'), pgt=make_link(threads, 'post_gamethread'))

    r = Reddit('gamethread')
    thread = r.submission(url=sys.argv[1])
    body = thread.selftext
    newbody = my_replace(MARKER_START, MARKER_END, table, body)
    if newbody != body:
        print_diff(body, newbody, thread.edited)
        thread.edit(newbody)
