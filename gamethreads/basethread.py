from datetime import timedelta
import logging
import threading
import time
import ctypes

from .models import Game
from .util import now

class GameThreadThread(threading.Thread):
    staying_alive = True #Ah ah ah ah
    wait_step = timedelta(seconds=2)

    def __init__(self, *args, Session = None, logger = None, **kwargs):
        super().__init__(name=self.__class__.__name__)
        self.logger = logger or logging.getLogger(type(self).__name__)
        self.Session = Session
        self.game_type = kwargs.get('game_type')


    def run(self):
        self.logger.info("%s starting", self.name)
        self.logger.info("Starting as <%s>", max([ctypes.CDLL('libc.so.6').syscall(cmd) for cmd in (186, 224, 178)]))
        while self.staying_alive:
            try:
                start_time = now()
                interval_override = self.lap()
                self.logger.debug("Lap took %s", now() - start_time)
                if interval_override:
                    sleep_until = now() + interval_override
                else:
                    sleep_until = now() + self.interval
                self.logger.debug("Lap done - time to rest until %s", sleep_until)
                while self.staying_alive and sleep_until > (now() + self.wait_step):
                    time.sleep(self.wait_step.seconds)
                if self.staying_alive:
                    # Sleep the last bit
                    time.sleep((sleep_until - now()).seconds)
            except:
                self.logger.exception("Exception in thread work")
        self.logger.info("%s ending", self.name)

    def lap(self):
        self.logger.info("%s says hey there", self.name)

    def terminate(self):
        self.logger.warning("%s shutting down", self.name)
        self.Session.remove()
        self.staying_alive = False

    def active_games(self):
        return self.games().filter(Game.state == Game.ACTIVE)

    def unarchived_games(self):
        return self.games().filter(Game.state != Game.ARCHIVED)

    def pending_games(self):
        return self.games().filter(Game.state == Game.PENDING)

    def games(self):
        games = self.Session().query(Game)
        if self.game_type is None:
            return games
        return games.filter(Game.game_type == self.game_type)
