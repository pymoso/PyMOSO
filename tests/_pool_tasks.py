"""Top-level functions for tests/test_worker_pool.py's workers. In a
module of their own so that a worker started by spawn or forkserver can
import them by name."""
import os
import time


def make_state(label):
    return {"label": label, "pid": os.getpid(), "calls": 0}


def failing_initializer():
    raise LookupError("no such thing to initialise")


def echo(state, value):
    state["calls"] += 1
    return value, state["label"]


def pid(state):
    return os.getpid()


def slow_echo(state, value, seconds):
    time.sleep(seconds)
    return value


def raise_after(state, value, seconds):
    time.sleep(seconds)
    raise ZeroDivisionError("boom at {0}".format(value))


class Unpicklable(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.handle = lambda: None


def raise_unpicklable(state):
    raise Unpicklable("cannot travel")


def return_unpicklable(state):
    return lambda: None


def die(state, code):
    os._exit(code)
