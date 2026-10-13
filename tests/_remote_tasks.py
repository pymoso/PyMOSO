"""Initializers and tasks for tests/test_remote_backend.py. They run
in a fresh interpreter that is given this directory on its path."""
import os

INITIALIZED = 0


def counting_state(label):
    global INITIALIZED
    INITIALIZED += 1
    return {'label': label, 'initialized': INITIALIZED, 'pid': os.getpid()}


def report(state, value):
    return (state['label'], state['initialized'], value)


def failing_initializer():
    raise OSError('the initializer failed')


def fail_on_odd(state, value):
    if value % 2:
        raise KeyError('task {0} failed'.format(value))
    return value


def unpicklable_result(state, value):
    return lambda: value
