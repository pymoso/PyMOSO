#!/usr/bin/env python
from . import orclib as ol
from .simoptutils import *
from .solnsets import tp1asoln, tp1bsoln, tp3soln, tp2par


class TPATester(object):
    def __init__(self):
        self.ranorc = ol.TP1
        self.detorc = ol.TrueTP1()
        self.tname = 'TPA'
        self.soln = tp1asoln


class TPBTester(object):
    def __init__(self):
        self.ranorc = ol.TP3
        self.detorc = ol.TrueTP3()
        self.tname = 'TPB'
        self.soln = tpbweak
        self.les = tpbles


class TPCTester(object):
    def __init__(self):
        self.ranorc = ol.TPCi
        self.detorc = ol.TrueTPCi()
        self.tname = 'TPC'
        self.soln = tpcsoln


class TPBiTester(object):
    def __init__(self):
        self.ranorc = ol.TPBi
        self.detorc = ol.TrueTP3()
        self.tname = 'TPB'
        self.soln = tpbweak
        self.les = tpbles
