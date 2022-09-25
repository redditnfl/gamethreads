#!/usr/bin/env python
# TODO: This is generic enough that it should be extracted
import yaml
import os
import logging

WIKI_PATH = "customconfig"
PROGRAM = "SubedditCustomConfig"
AUTHOR = "rasherdk"
VERSION = "0.1"

def my_repr(obj):
    if isinstance(obj, praw.Reddit):
        return "Reddit Session for %r" % obj.user
    else:
        return repr(obj)

class SubredditCustomConfig():
    def __init__(self, subreddit, path = None):
        self.logger = logging.getLogger(type(self).__name__)
        self.sub = subreddit
        if path is None:
            path = WIKI_PATH
        self.path = path
        self.config = None
        self.refresh()

    def refresh(self, create_if_missing=True):
        try:
            page = self.sub.wiki[self.path]
            self.config = yaml.safe_load(page.content_md)
        except Exception as e:
            print(e)
            #if create_if_missing:
            #    self.logger.info("Page doesn't exist, creating")
            #    res = self.sub.edit_wiki_page(self.path, '')
            #    self.refresh(create_if_missing=False)
            #else:
            self.logger.warn("Page %s doesn't exist, giving up" % self.path)
            raise

    def get(self, path, default=None):
        subconfig = self.config
        self.logger.debug("Getting %s => ", path)
        i = 1
        for section in path.split('.'):
            i += 1
            if not subconfig or section not in subconfig:
                self.logger.debug("%r" % default)
                return default
            subconfig = subconfig[section]
        self.logger.debug("%r" % subconfig)
        return subconfig

    def __repr__(self):
        return "SubredditCustomConfig(subreddit=%r)" % self.sub

if __name__ == "__main__":
    from pprint import pprint
    import praw
    import sys
    r = praw.Reddit("subredditcustomconfig", user_agent="%s/%s by %s" % (PROGRAM, VERSION, AUTHOR))
    sub = r.subreddit(sys.argv[3])
    config = SubredditCustomConfig(sub)
    pprint(config.config)
    pprint(config.get('highlights.filters.allow_users'))
    pprint(config.get('highlights.dongs', 5))
    pprint(config.get('highlights.dongs'))
