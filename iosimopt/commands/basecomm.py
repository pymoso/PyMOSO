"""The base command."""
import os
import pathlib
import time
import collections
from datetime import date
from math import ceil
from .. import mprun
from .. import solvers
from .. import orclib
from .. import mrg32k3a as mrg
from .. import testcases
import json
import pickle


def get_seeds():
    package_dir = os.path.dirname(os.path.abspath(__file__))
    orcseedfile = os.path.join(package_dir, '../../', 'prnseeds/orcseeds.pkl')
    solseedfile = os.path.join(package_dir, '../../', 'prnseeds/solseeds.pkl')
    xorseedfile = os.path.join(package_dir, '../../', 'prnseeds/xorseeds.pkl')
    orcseeds = mprun.get_seedstreams(orcseedfile)
    solseeds = mprun.get_seedstreams(solseedfile)
    xorseeds = mprun.get_seedstreams(xorseedfile)
    return orcseeds, solseeds, xorseeds


def get_x0(orc, xprn):
    orc0 = orc(xprn)
    feas = orc0.get_feasspace()
    startd = dict()
    endd = dict()
    for dim in feas:
        sta = []
        end = []
        for interval in feas[dim]:
            sta.append(interval[0])
            end.append(interval[1])
        startd[dim] = min(sta)
        endd[dim] = max(end)
    x0 = []
    for dim in range(orc0.dim):
        xq = xprn.sample(range(startd[dim], endd[dim]), 1)[0]
        x0.append(xq)
    x0 = tuple(x0)
    return x0


def gen_humanfile(name, probn, solvn, budget, runtime, trials, param, vals):
    today = date.today()
    tstr = today.strftime("%A %d. %B %Y")
    timestr = time.strftime('%X')
    dnames = ('Name', 'Problem', 'Algorithm', 'Budget', 'Trials', 'Run time', 'Day', 'Time', 'Params', 'Param Values')
    ddate = (name, probn, solvn, budget, trials, runtime, tstr, timestr, param, vals)
    ddict = collections.OrderedDict(zip(dnames, ddate))
    return ddict


def save_files(name, humantxt, rundat, pltd=None, alg=None):
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = name + '.txt'
    pref = ''
    if alg:
        pref = alg + '_'
    rundatn = pref + name + '.pkl'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        json.dump(humantxt, f1, indent=4, separators=(',', ': '))
    rundpth = os.path.join(name, rundatn)
    with open(rundpth, 'wb') as f2:
        pickle.dump(rundat, f2)
    if pltd:
        pltn = pref + name + '_plt.pkl'
        pltpth = os.path.join(name, pltn)
        with open(pltpth, 'wb') as f3:
            pickle.dump(pltd, f3)


def gen_pltdat(dat, trials, incr, budget, tp):
    joblst = []
    for t in range(trials):
        tup = (dat[t], incr, budget, tp)
        joblst.append(tup)
    pltdat = mprun.par_pltdat(joblst, budget, incr)
    return pltdat


class BaseComm(object):
    """A base command."""

    def __init__(self, options, *args, **kwargs):
        self.options = options
        self.args = args
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError('You must implement the run() method yourself!')
