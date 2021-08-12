#!/usr/bin/env python
import json
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean, Text
from sqlalchemy.orm import relationship, backref

GAME_PENDING = 'pending'
GAME_ACTIVE = 'active'
GAME_CLOSED = 'closed'
GAME_ARCHIVED = 'archived'
GAME_STATES = [GAME_PENDING, GAME_ACTIVE, GAME_CLOSED, GAME_ARCHIVED]

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class Game(Base):
    __tablename__ = 'game'
    PENDING = GAME_PENDING
    ACTIVE = GAME_ACTIVE
    CLOSED = GAME_CLOSED
    ARCHIVED = GAME_ARCHIVED

    id = Column(Integer, primary_key=True) 
    game_id = Column(String, unique=True)
    game_type = Column(String)
    state = Column(Enum(*GAME_STATES, name='STATE'))
    state_changed_utc = Column(DateTime(timezone=True))


    def __repr__(self):
        return "<Game(game_id={0.game_id},game_type={0.game_type})>".format(self)


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    config_json = Column(String)
    config_updated_utc = Column(DateTime(timezone=True))

    @property
    def config(self):
        return json.loads(self.config_json) if self.config_json else None

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value)


class Subreddit(Base):
    __tablename__ = 'subreddit'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    config_json = Column(String)
    config_updated_utc = Column(DateTime(timezone=True))

    def __repr__(self):
        return "<Subreddit(id=%d, name=%s)>" % (self.id, self.name)

    @property
    def config(self):
        return json.loads(self.config_json) if self.config_json else None

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value)


class Thread(Base):
    __tablename__ = 'thread'

    id = Column(Integer, primary_key=True)
    thread_type = Column(String)
    thread_id = Column(String, unique=True)
    sub_id = Column(Integer, ForeignKey('subreddit.id'))
    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship("Game", backref=backref('threads', order_by=id))
    sub = relationship("Subreddit", backref=backref('threads', order_by=id))
    posted_utc = Column(DateTime(timezone=True))
    updated_utc = Column(DateTime(timezone=True))
    final = Column(Boolean, default=False)
    url = Column(String)
    body = Column(Text)

    def __repr__(self):
        return "<Thread(id={0.id}, thread_id={0.thread_id})>".format(self)


def main():
    import sys
    if len(sys.argv) <= 1 or sys.argv[1] not in ('create_all', 'drop_all'):
        print("Usage: %s create_all|drop_all" % sys.argv[0])
        sys.exit(1)

    import sqlalchemy
    from sqlalchemy.orm import sessionmaker
    import os
    engine = sqlalchemy.create_engine('postgresql+psycopg2://{0[PGUSER]}:{0[PGPASSWORD]}@{0[PGHOST]}:{0[PGPORT]}/{0[PGDATABASE]}'.format(os.environ), echo=True)
    session = sessionmaker(bind=engine)
    cmd = sys.argv[1]
    if cmd == 'create_all':
        from . import plugins
        Base.metadata.create_all(engine)
    elif cmd == 'drop_all':
        # Thank you univerio https://stackoverflow.com/a/38679457
        from sqlalchemy.schema import DropTable
        from sqlalchemy.ext.compiler import compiles
        from . import plugins

        @compiles(DropTable, "postgresql")
        def _compile_drop_table(element, compiler, **kwargs):
            return compiler.visit_drop_table(element) + " CASCADE"

        Base.metadata.drop_all(engine)


if __name__ == "__main__":
    main()
