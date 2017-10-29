#!/usr/bin/env python 
from pprint import pprint
import importlib
from datetime import timedelta, datetime
import logging
import threading
import time

from requests.exceptions import HTTPError
from jinja2.sandbox import SandboxedEnvironment
from praw import Reddit
import pytz

from RedditUtils4.SubredditCustomConfig import SubredditCustomConfig

import models
from models import *
from util import get_or_create, now, make_safe, RedditWikiLoader, signal_handler

UTC = pytz.utc

class GameThreadThread(threading.Thread):
    staying_alive = True #Ah ah ah ah
    wait_step = timedelta(seconds=2)

    def __init__(self, *args, Session = None, logger = None, **kwargs):
        super().__init__(name=self.__class__.__name__)
        self.logger = logger or logging.getLogger(type(self).__name__)
        self.Session = Session
        self.models = models
        self.game_type = kwargs.get('game_type')

    def run(self):
        self.logger.info("%s starting", self.name)
        while self.staying_alive:
            try:
                start_time = now()
                interval_override = self.lap()
                self.logger.debug("Lap took %s", now() - start_time)
                if interval_override:
                    sleep_until = now() + interval_override
                else:
                    sleep_until = now() + self.interval
                self.logger.info("Lap done - time to rest until %s", sleep_until)
                while self.staying_alive and sleep_until > (now() + self.wait_step):
                    time.sleep(self.wait_step.seconds)
                if self.staying_alive:
                    # Sleep the last bit
                    time.sleep((sleep_until - now()).seconds)
            except Exception as e:
                self.logger.exception("Exception in thread work")
        self.logger.info("%s ending", self.name)

    def lap(self):
        self.logger.info("%s says hey there", self.name)

    def terminate(self):
        self.logger.warning("%s shutting down", self.name)
        self.Session.remove()
        self.staying_alive = False

    def active_games(self):
        return self.games().filter(self.models.Game.state == self.models.Game.ACTIVE)

    def unarchived_games(self):
        return self.games().filter(self.models.Game.state != self.models.Game.ARCHIVED)

    def games(self):
        games = self.Session().query(self.models.Game)
        if self.game_type is None:
            return games
        return games.filter(self.models.Game.game_type == self.game_type)


class GameUpdater(GameThreadThread):
    interval = timedelta(minutes=5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def lap(self):
        session = self.Session()
        config = session.query(Config).all()[0].config
        for game_type in config['types']:
            self.logger.info("Finding new games for type %s", game_type)
            finder = importlib.import_module(game_type + '.gamefinder', package=__loader__.name)
            game_ids = finder.find_games()
            for game_id in game_ids:
                game, created = get_or_create(session, Game, game_type=game_type, game_id=game_id)
                if created:
                    self.logger.info("New game %r", game)
                    session.add(game)
            # TODO: archive games
            for game in session.query(Game).filter(Game.state == Game.CLOSED, Game.state_changed_utc < now() - timedelta(days=7)):
                game.state = Game.ARCHIVED
            # Update states
            self.logger.info("Updating games for type %s", game_type)
            for game in session.query(Game).filter(or_(Game.state != Game.CLOSED, Game.state == None), Game.game_type == game_type):
                self.logger.debug("Getting updated state for %r", game)
                before = game.state
                game = finder.update_state(game)
                if before != game.state:
                    self.logger.info("Updating state of %r to %s", game, game.state)
                    game.state_changed_utc = now()
        session.commit()


def make_context(game, config, thread = None):
    MINUTE = timedelta(minutes=1)
    HOUR = timedelta(hours=1)
    DAY = timedelta(days=1)
    generator = importlib.import_module(game.game_type, package=__loader__.name)
    ctx = generator.make_context(game, config)
    ctx['minutes'] = MINUTE
    ctx['hours'] = HOUR
    ctx['days'] = DAY
    ctx['base_game'] = game
    ctx['thread'] = thread
    return ctx


class Renderer:

    def __init__(self):
        self.envs = {}
        self.logger = logging.getLogger(type(self).__name__)

    def _get_env(self, sub):
        if not hasattr(self, 'envs'):
            self.envs = {}
        key = sub.display_name # Not sure using the sub itself would work
        if key not in self.envs:
            self.envs[key] = SandboxedEnvironment(loader=RedditWikiLoader(sub, 'gamethreads/templates'))
        return self.envs[key]

    def render_thread(self, reddit_sub, sub, thread_config, game, thread = None):
        env = self._get_env(reddit_sub)
        template = env.get_template(thread_config['template'])
        ctx = make_context(game, sub.config, thread)
        title, body = map(lambda s: s.strip(), template.render(ctx).split("\n", 1))
        #self.logger.debug("Thread title: %s", title)
        #self.logger.debug("Thread content: %s", body)
        return title, body


class ThreadPoster(GameThreadThread):
    interval = timedelta(seconds=30)

    def __init__(self, *args, **kwargs):
        self.r = Reddit('gamethread')
        self.renderer = Renderer()
        super().__init__(*args, **kwargs)

    def lap(self):
        self.session = self.Session()
        games = list(self.unarchived_games())
        for sub in self.session.query(Subreddit).all():
            needs_posted = self.needs_posted(sub, games)
            reddit_sub = self.r.subreddit(sub.name)
            for thread, game in needs_posted:
                submission = None
                try:
                    title, body = self.renderer.render_thread(reddit_sub, sub, thread, game)
                except Exception as e:
                    self.logger.exception("Could not render template %s", thread['template'])
                    continue
                self.logger.debug("Posting sub=<%s>, title=<%s>", sub, title)
                try:
                    submission = reddit_sub.submit(title, selftext=body, send_replies=False)
                    self.logger.info("Posted %s to %s for game %s", thread['template'], sub, game)
                    tm, _ = get_or_create(self.session, Thread, sub=sub, game=game, thread_type=thread['id'])
                    tm.url = submission.permalink
                    tm.posted_utc = now()
                    tm.thread_id = submission.id
                    tm.body = body
                except Exception as e:
                    self.logger.exception("Could not submit thread %s to %s", thread['template'], sub)
                    if submission is not None:
                        self.logger.warning("Submission could not be stored. Deleting to avoid orphaning")
                        submission.delete()
        self.session.commit()

    def already_posted(self, sub, thread, game):
        try:
            self.session.query(Thread).filter_by(sub=sub, game=game, thread_type=thread['id']).one()
            return True
        except sqlalchemy.orm.exc.NoResultFound:
            return False

    def needs_posted(self, sub, games):
        """Taking a subreddit object and list of games, decide which threads need to be posted"""
        env = SandboxedEnvironment()
        ret = []
        for thread in sub.config['threads']:
            self.logger.debug("Testing games against expression %s for sub %r", thread['post_condition'], sub)
            post_cond_fun = env.compile_expression(thread['post_condition'])
            for game in games:
                self.logger.debug("Testing %s for thread %s for %r", game, thread['id'], sub)
                if self.already_posted(sub, thread, game):
                    # This could prove expensive, but it's easy for now.
                    # Simple optimization: fetch all already_posted threads for non_archived games outside the loop
                    continue

                ctx = make_context(game, sub.config)
                post_decision = post_cond_fun(ctx)
                self.logger.debug("Decision for %r: %s", game, post_decision)
                needs_posted = False
                if isinstance(post_decision, datetime):
                    needs_posted = post_decision < now()
                elif isinstance(post_decision, bool):
                    needs_posted = post_decision
                else:
                    self.logger.warning("post_decision for %s in %s not datetime or bool: %r", thread['id'], sub, post_decision)
                if needs_posted:
                    self.logger.info("Posting thread %s for game %s in %s", thread['id'], game, sub)
                    ret.append((thread, game))
        return ret


class ThreadUpdater(GameThreadThread):
    interval = timedelta(minutes=3)

    def __init__(self, *args, **kwargs):
        self.r = Reddit('gamethread')
        self.renderer = Renderer()
        self.envs = {}
        super().__init__(*args, **kwargs)

    def lap(self):
        self.session = self.Session()
        for game in self.unarchived_games():
            for thread in game.threads:
                try:
                    self.logger.debug("Update %r", thread)
                    sub = thread.sub
                    reddit_sub = self.r.subreddit(sub.name)
                    thread_config = list(filter(lambda x: x['id'] == thread.thread_type, sub.config['threads']))[0]
                    title, body = self.renderer.render_thread(reddit_sub, sub, thread_config, game, thread)
                    if body != thread.body:
                        self.logger.info("Updating thread %s", thread)
                        submission = self.r.submission(id=thread.thread_id)
                        submission.edit(body)
                        thread.body = body
                except Exception as e:
                    self.logger.exception("Updating submission %s failed", thread)
        self.session.commit()


class ConfigUpdater(GameThreadThread):
    interval = timedelta(minutes=15)

    def __init__(self, root_sub, *args, **kwargs):
        self.r = Reddit('gamethread')
        self.root_sub = self.r.subreddit(root_sub)
        super().__init__(*args, **kwargs)

    def lap(self):
        root_config = SubredditCustomConfig(self.root_sub, 'gamethreads/root_config')
        self.save_root_config(self.root_sub, root_config.config)
        self.update_subreddits(set(root_config.get('subreddits')))

    def save_root_config(self, root_sub, root_config):
        session = self.Session()
        obj, created = get_or_create(session, Config, name=root_sub.display_name)
        if obj.config != root_config:
            session.add(obj)
            obj.config = root_config
            obj.config_updated_utc = now()
            self.logger.info("Save %s: %r", root_sub, root_config)
            session.commit()

    def update_subreddits(self, sr_names):
        for sr_name in sr_names:
            self.logger.info("Updating config for %s", sr_name)
            session = self.Session()
            obj, created = get_or_create(session, Subreddit, name=sr_name)
            sr = self.r.subreddit(sr_name)
            sr_config = SubredditCustomConfig(sr, 'gamethreads/config')
            if obj.config != sr_config.config:
                session.add(obj)
                obj.config = sr_config.config
                self.logger.info("Got updated config: %r", obj.config)
                obj.config_updated_utc = now()
            session.commit()

import sqlalchemy
from sqlalchemy import or_
from sqlalchemy.orm import sessionmaker, scoped_session
from util import setup_logging
import signal
import sys
import os
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
            typethreads = importlib.import_module(game_type + '.threads', package=__loader__.name)
            for t in typethreads.ALL:
                new = t(Session=session, models=models, game_type=game_type)
                if hasattr(new, 'setup') and new.setup:
                    self.logger.info("Running thread %r as setup", new)
                    new.lap()
                threads.append(new)
        self.logger.info("Starting threads")
        [t.start() for t in threads]
        self.logger.info("Exiting")

    def config(self):
        return self.session().query(Config).all()[0].config
    
if __name__ == "__main__":
    gt = Gamethreader()
    gt.main()
