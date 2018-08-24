#!/usr/bin/env python
from ..problems import probtpc, probtruetpc
import pickle
import os


class TPCTester(object):
    def __init__(self):
        self.ranorc = probtpc.ProbTPC
        self.true_g = probtruetpc.ProbTrueTPC().g
        self.tname = 'TPC'
        self.soln = soln


tpcfn = 'exples.pkl'
package_dir = os.path.dirname(os.path.abspath(__file__))
abs_path = os.path.join(package_dir, tpcfn)
with open(abs_path, 'rb') as h:
    soln = pickle.load(h)
