"""The base command."""
import os
import pathlib
import time
import collections
from datetime import date
from math import ceil
from .. import mprun
from .. import solvers
from .. import problems
from .. import prng
from .. import testproblems
from json import dumps, loads, JSONEncoder, JSONDecoder, dump
import pickle


def jsonset(o):
    if isinstance(o, set):
        return list(o)
    return o.__dict__


def check_expname(name):
    if not os.path.isdir(name):
        return False
    fn = name + '/' + name + '.txt'
    fpath = pathlib.Path(fn)
    if not fpath.is_file():
        return False
    with open(fn, 'r') as f1:
        datstr = json.load(f1)
    return datstr


def get_solv_prnstreams(iseed):
    orcstream = prng.mrg32k3a.MRG32k3a(iseed)
    solvstream = prng.mrg32k3a.get_next_prnstream(iseed)
    return orcstream, solvstream


def get_prnstreams(num_trials, iseed):
    xprn = prng.mrg32k3a.MRG32k3a(iseed)
    orcprn_lst = []
    solprn_lst = []
    for t in range(num_trials):
        orcprn = prng.mrg32k3a.get_next_prnstream(iseed)
        orcprn_lst.append(orcprn)
        iseed = orcprn._current_seed
        solprn = prng.mrg32k3a.get_next_prnstream(iseed)
        solprn_lst.append(solprn)
        iseed = solprn._current_seed
    return orcprn_lst, solprn_lst, xprn


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


def gen_humanfile(name, probn, solvn, budget, runtime, param, vals):
    today = date.today()
    tstr = today.strftime("%A %d. %B %Y")
    timestr = time.strftime('%X')
    dnames = ('Name', 'Problem', 'Algorithm', 'Budget', 'Run time', 'Day', 'Time', 'Params', 'Param Values')
    ddate = (name, probn, solvn, budget, runtime, tstr, timestr, param, vals)
    ddict = collections.OrderedDict(zip(dnames, ddate))
    return ddict


def save_files(name, humantxt, rundat, pltd=None, alg=None):
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = name + '.txt'
    pref = ''
    if alg:
        pref = alg + '_'
    rundatn = pref + name + '.txt'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        dump(humantxt, f1, indent=4, separators=(',', ': '))
    rundpth = os.path.join(name, rundatn)
    j = dumps(rundat, default=jsonset)
    with open(rundpth, 'w') as f2:
        dump(j, f2, indent=4, separators=(',', ': '))
    if pltd:
        pltn = pref + name + '_plt.txt'
        pltpth = os.path.join(name, pltn)
        j = dumps(pltdat, default=jsonset)
        with open(pltpth, 'w') as f3:
            dump(j, f3, indent=4, separators=(',', ': '))


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
