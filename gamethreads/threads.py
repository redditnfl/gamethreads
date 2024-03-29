#!/usr/bin/env python 
from pprint import pprint
from datetime import timedelta, datetime
import logging
import threading
import time

import sqlalchemy
from sqlalchemy import or_
from requests.exceptions import HTTPError
from jinja2.sandbox import SandboxedEnvironment
from praw import Reddit
import pytz
import roman

from .SubredditCustomConfig import SubredditCustomConfig
from .models import *
from .util import get_or_create, now, make_safe, RedditWikiLoader, NotReadyException
from .basethread import GameThreadThread
from . import plugins

UTC = pytz.utc



class GameUpdater(GameThreadThread):
    interval = timedelta(minutes=5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def lap(self):
        session = self.Session()
        config = session.query(Config).all()[0].config

        # Archive games closed more than 4 days
        for game in session.query(Game).filter(Game.state == Game.CLOSED, Game.state_changed_utc < now() - timedelta(days=4)):
            self.logger.info("Archiving game %s", game)
            game.state = Game.ARCHIVED

        for game_type in config['types']:
            self.logger.debug("Finding new games for type %s", game_type)
            finder = getattr(plugins, game_type).gamefinder
            game_ids = finder.find_games()
            for game_id in game_ids:
                game, created = get_or_create(session, Game, game_type=game_type, game_id=game_id)
                if created:
                    self.logger.info("New game %r", game)
                    session.add(game)
            # Update states of pending and active games
            self.logger.debug("Updating games for type %s", game_type)
            for game in session.query(Game).filter(or_(Game.state.in_([Game.PENDING, Game.ACTIVE]), Game.state == None), Game.game_type == game_type):
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
    plugin = getattr(plugins, game.game_type)
    ctx = plugin.make_context(game, config)
    ctx['minutes'] = MINUTE
    ctx['hours'] = HOUR
    ctx['days'] = DAY
    ctx['base_game'] = game
    ctx['thread'] = thread
    ctx['now'] = now()
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
            self.envs[key] = SandboxedEnvironment(loader=RedditWikiLoader(sub, 'gamethreads/templates', timedelta(minutes=1)))
            self.envs[key].filters['to_roman'] = roman.toRoman
            self.envs[key].filters['from_roman'] = roman.fromRoman
        return self.envs[key]

    def render_thread(self, reddit_sub, sub, thread_config, game, thread = None):
        env = self._get_env(reddit_sub)
        template = env.get_template(thread_config['template'])
        ctx = make_context(game, sub.config, thread)
        title, body = map(lambda s: s.strip(), template.render(ctx).split("\n", 1))
        return title, body


class ThreadPoster(GameThreadThread):
    interval = timedelta(seconds=15)

    def __init__(self, *args, **kwargs):
        self.r = Reddit()
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
                    self.logger.exception("Could not render template %s with game %s", thread['template'], game)
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
                    self.logger.debug("Game already posted, skipping")
                    continue

                try:
                    ctx = make_context(game, sub.config)
                except NotReadyException as e:
                    self.logger.debug("Not ready to decide whether to post %s", game)
                    continue
                except Exception as e:
                    self.logger.exception("Error generating context for game %s", game)
                    continue
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
        self.r = Reddit()
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
                        self.logger.debug("Updating thread %s", thread)
                        submission = self.r.submission(id=thread.thread_id)
                        submission.edit(body)
                        thread.body = body
                        time.sleep(3)
                except Exception as e:
                    self.logger.exception("Updating submission %s failed", thread)
        self.session.commit()


class ConfigUpdater(GameThreadThread):
    # TODO: Add validation with pykwalify
    interval = timedelta(minutes=15)

    def __init__(self, root_sub, *args, **kwargs):
        self.r = Reddit()
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
            self.logger.debug("Updating config for %s", sr_name)
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
