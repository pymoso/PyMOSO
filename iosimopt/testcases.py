#!/usr/bin/env python
from . import orclib as ol
from .simoptutils import *
from .solnsets import tp1asoln, tp1bsoln, tp3soln, tp2par


class TP1aTester(object):
    def __init__(self):
        self.ranorc = ol.TP1a
        self.detorc = ol.TrueTP1a()
        self.tname = 'TP1a'
        self.soln = tp1asoln


class TP1bTester(object):
    def __init__(self):
        self.ranorc = ol.TP1b
        self.detorc = ol.TrueTP1b()
        self.tname = 'TP1b'
        self.soln = tp1bsoln


class TP2aTester(object):
    def __init__(self):
        self.ranorc = ol.TP2
        self.detorc = ol.TrueTP2()
        self.tname = 'TP2a'
        self.soln = tp2par


class TP2bTester(object):
    def __init__(self):
        self.ranorc = ol.TP2LowVar
        self.detorc = ol.TrueTP2LowVar()
        self.tname = 'TP2b'
        self.soln = tp2bsoln


class TP3Tester(object):
    def __init__(self):
        self.ranorc = ol.TP3
        self.detorc = ol.TrueTP3()
        self.tname = 'TP3'
        self.soln = tp3soln
