import pytz
from datetime import datetime
def now():
    return pytz.utc.localize(datetime.utcnow())
    

# http://stackoverflow.com/questions/2546207 
import sqlalchemy
def get_or_create(session,
                      model,
                      create_method='',
                      create_method_kwargs=None,
                      **kwargs):
    try:
        return session.query(model).filter_by(**kwargs).one(), False
    except sqlalchemy.orm.exc.NoResultFound:
        kwargs.update(create_method_kwargs or {})
        created = getattr(model, create_method, model)(**kwargs)
        try:
            session.add(created)
            session.flush()
            return created, True
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            return session.query(model).filter_by(**kwargs).one(), False

# http://victorlin.me/posts/2012/08/26/good-logging-practice-in-python
import logging.config
import yaml
import os
def setup_logging(
            default_path='logging.yaml', 
            default_level=logging.INFO,
            env_key='LOG_CFG'
        ):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

# TODO: Well this isn't very safe!
# Make it recursively use __dict__
def make_safe(model):
    return model

from jinja2 import BaseLoader, TemplateNotFound
import re
import sys
from datetime import timedelta
class RedditWikiLoader(BaseLoader):
    def __init__(self, subreddit, root, ttl=timedelta(seconds=0)):
        self.sub = subreddit
        self.root = re.sub('(^/*|/*$)', '', root) # Remove pre and postfix slashes
        self.ttl = ttl

    def get_source(self, environment, template):
        path = "%s/%s" % (self.root, template)
        try:
            wp = self.sub.wiki[path]
        except Exception as e:
            raise TemplateNotFound(template)
        evict = now() + self.ttl
        return wp.content_md, None, lambda: evict > now()

    def list_templates(self):
        found = set()
        for page in self.sub.wiki:
            print(page)
            print(repr(dir(page)))
            if page.startswith(self.root):
                found.add(page.replace(self.root, '', 1))
        return found

class NotReadyException(Exception):
    pass
