from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from gamethreads.models import Game
from gamethreads.plugins.nfl.models import NFLGame
from gamethreads.threads import make_context
from pprint import pprint, pformat
from markupsafe import escape
from jinja2.sandbox import SandboxedEnvironment
import traceback
import roman
import os

db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://{0[PGUSER]}:{0[POSTGRES_PASSWORD]}@{0[PGHOST]}:{0[PGPORT]}/{0[PGDATABASE]}'.format(os.environ)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

config = {'timezone': 'America/New_York'}

def get_game(game_id):
    game = db.session.execute(db.select(Game).join(NFLGame).filter(Game.game_id==str(game_id))).scalars().first()
    ctx = make_context(game, config)
    return game, ctx

@app.route('/')
def frontpage():
    games = db.session.execute(db.select(Game).join(NFLGame).order_by(NFLGame.kickoff_utc)).scalars()
    return render_template('index.html', games=games)

@app.route('/context/<uuid:game_id>')
def context(game_id):
    game, ctx = get_game(game_id)
    return escape(pformat(ctx))

@app.route('/render', methods=['POST'])
def render():
    game_id = request.form['game_id']
    tpl_str = request.form['tpl']
    game, ctx = get_game(game_id)
    env = SandboxedEnvironment()
    env.filters['to_roman'] = roman.toRoman
    env.filters['from_roman'] = roman.fromRoman
    try:
        tpl = env.from_string(tpl_str)
        response = tpl.render(ctx)
    except:
        response = traceback.format_exc()
    return escape(response)
