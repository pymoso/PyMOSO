__version__ = '2.0.0.dev0'
__author__ = 'Kyle Cooper'


def __getattr__(name):
    # Names offered at the top level without importing what defines
    # them until they are asked for: nothing in the core imports the
    # backends package at module scope
    # (tests/test_dependency_boundary.py).
    if name == 'dispatch_cost':
        from .backends.measure import dispatch_cost
        return dispatch_cost
    raise AttributeError('module {0!r} has no attribute {1!r}'.format(__name__, name))
