#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import re
import sys
import random
import webbrowser
import argparse

from praw import Reddit


class HandleOneReturningUser(BaseHTTPRequestHandler):
    """Accept one request, retrieve a refresh token and shutdown the server"""
    def do_GET(self):
        params = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        expected_state = self.server._expected_state
        state = params.get('state', '-1')
        reddit = self.server._reddit
        
        if state != expected_state:
            code, msg = 400, 'State mismatch. Expected: {} Received: {}'.format(expected_state, state)
        elif 'error' in params:
            code, msg = 500, 'Error returned: {}'.format(params['error'])
        else:
            refresh_token = reddit.auth.authorize(params['code'])
            code = 200
            values = """
client_id={c.client_id}
client_secret={c.client_secret}
refresh_token={t}
""".strip().format(t=refresh_token, c=reddit.config)

            msg = """
Auth flow complete. Set the following environment variables:

{}

Or add the following to your praw.ini:

{}
""".format(re.sub(r'(?m)^', 'praw_', values), values)

        print(msg)
        self._my_response(code, msg.strip())
        self.server.shutdown()

    def log_request(self, *args, **kwargs):
        pass

    def _my_response(self, code, data):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(data.encode("UTF-8"))


def main():
    parser = argparse.ArgumentParser(description='Obtain an OAuth refresh token')
    parser.add_argument('scopes', help="Comma-delimited list of scopes (or 'all')")
    reddit_settings = ('redirect_uri', 'client_id', 'client_secret')
    for rs in reddit_settings:
        parser.add_argument('--%s' % rs)
    args = parser.parse_args()
    overrides = {k: getattr(args, k) for k in reddit_settings if getattr(args, k) is not None}

    reddit = Reddit(user_agent='obtain_token', **overrides)
    port = urlparse(reddit.config.redirect_uri).port
    
    scopes = args.scopes.lower().split(',')
    if 'all' in scopes:
        scopes = list(reddit.get('/api/v1/scopes').keys())

    state = str(random.randint(0, 65000))
    url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')
    try:
        webbrowser.get()
        webbrowser.open(url)
    except webbrowser.Error:
        print("Open in a browser: %s" % url)
        sys.stdout.flush()
    # Start a server for the user to return to
    httpd = ThreadingHTTPServer(('', port), HandleOneReturningUser)
    httpd._expected_state = state
    # The Reddit instance is thread unsafe - we'll probably get away with it
    httpd._reddit = reddit
    httpd.serve_forever()


if __name__ == "__main__":
    main()
