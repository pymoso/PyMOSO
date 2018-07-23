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


def combine_runs(rundicts):
    """combines the output results of many runs into a single dictionary"""
    rundatdict = dict()
    for i, st in enumerate(rundicts):
        keys = list(st.keys())
        rundatdict[i] = dict()
        for k in keys:
            rundatdict[i][k] = st[k]
    return rundatdict


def run(boovsolver, budget, orc, **kwargs):
    exists_solvprn = kwargs.get('solvprn', False)
    if exists_solvprn:
        solvprn = kwargs.get('solvprn', None)
        kwargs['sprn'] = solvprn
        del kwargs['solvprn']
    solver = boovsolver(orc, **kwargs)
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
