#!/usr/bin/env python
from ..problems import probtpc, probtruetpc
import pickle
import os


class TPCTester(object):
    def __init__(self):
        self.ranorc = probtpc.ProbTPC
        self.detorc = probtruetpc.ProbTrueTPC()
        self.tname = 'TPC'
        self.soln = soln


tpcfn = 'prnseeds/exples.pkl'
package_dir = os.path.dirname(os.path.abspath(__file__))
orcseedfile = os.path.join(package_dir, '../../', tpcfn)
with open(tpcfn, 'rb') as h:
    tpcsoln = pickle.load(h)
