#!/usr/bin/env python 
import threading
import logging
import signal
import sys
import os

import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session

from .util import setup_logging
from .threads import *

def signal_handler(signal, frame):
    print('SIGINT detected, terminating threads!')
    for t in threading.enumerate():
        if t != threading.main_thread():
            t.terminate()
    print('Waiting for threads to terminate')
    for t in threading.enumerate():
        if t != threading.main_thread():
            t.join()
    print('Threads terminated, exiting')

class Gamethreader:

    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(type(self).__name__)
        signal.signal(signal.SIGINT, signal_handler)
        engine = sqlalchemy.create_engine('postgresql+psycopg2://{0[PGUSER]}:{0[PGPASSWORD]}@{0[PGHOST]}:{0[PGPORT]}/{0[PGDATABASE]}'.format(os.environ), echo = False)
        session_factory = sessionmaker(bind=engine)
        self.session = scoped_session(session_factory)

    def main(self):
        session = self.session

        config_updater = ConfigUpdater(sys.argv[1], Session = session)
        # Update configs before doing anything
        config_updater.lap()
        threads = []
        threads.append(config_updater)
        threads.append(GameUpdater(Session = session))
        threads.append(ThreadPoster(Session = session))
        threads.append(ThreadUpdater(Session = session))

        for game_type in self.config()['types']:
            self.logger.info("Initiating threads for %s", game_type)
            typethreads = getattr(plugins, game_type).threads
            for t in typethreads.ALL:
                new = t(Session=session, game_type=game_type)
                if hasattr(new, 'setup') and new.setup:
                    self.logger.info("Running thread %r as setup", new)
                    new.lap()
                threads.append(new)
        self.logger.info("Starting threads")
        [t.start() for t in threads]
        self.logger.info("Exiting")

    def config(self):
        return self.session().query(Config).all()[0].config
    
def main():
    gt = Gamethreader()
    gt.main()
