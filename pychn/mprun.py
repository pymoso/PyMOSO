#!/usr/bin/env python
from pychn.testproblems import *
from pychn.solvers import *
from math import floor
import multiprocessing as mp
from .chnutils import dh
from .prng.mrg32k3a import MRG32k3a
import pickle
from statistics import mean, variance


def do_work(func, args, kwargs):
    """wrapper to call a function with arguments and return the result"""
    # needed for use in the Python parallelization functions (e.g. apply_async)
    # ¯\_(ツ)_/¯
    result = func(*args, **kwargs)
    return result


def get_seedstreams(seedfilename):
    """return prn streams dictionary from pickle file"""
    with open(seedfilename, 'rb') as pklhandle:
        seeddict = pickle.load(pklhandle)
    return seeddict


def combine_runs(rundicts):
    """combines the output results of many runs into a single dictionary"""
    rundatdict = dict()
    for i, st in enumerate(rundicts):
        keys = list(st.keys())
        rundatdict[i] = dict()
        for k in keys:
            rundatdict[i][k] = st[k]
    return rundatdict


def run(boovsolver, budget, orc, orcprn, orcseed, **kwargs):
    orcprn_ob = orcprn(orcseed)
    solvseed = kwargs.get('solvseed', None)
    if solvseed:
        solvprn = kwargs.get('solvprn', None)
        solvprn_ob = solvprn(solvseed)
        kwargs['sprn'] = solvprn_ob
        del kwargs['solvseed']
        del kwargs['solvprn']
    orc_ob = orc(orcprn_ob)
    solver = boovsolver(orc_ob, **kwargs)
    mydat = solver.solve(budget)
    return mydat


def par_runs(joblst, num_proc=None):
    if not num_proc:
        NUM_PROCESSES = mp.cpu_count()
    else:
        NUM_PROCESSES = num_proc
    rundict = []
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = [(run, (e[0]), (e[1])) for e in joblst]
        app_rd = [p.apply_async(do_work, job) for job in worklist]
        for r in app_rd:
            myitem = r.get()
            rundict.append(myitem)
    runtots = combine_runs(rundict)
    return runtots
