#!/usr/bin/env python
from pychn.testproblems import *
from pychn.solvers import *
from math import floor, sqrt
import multiprocessing as mp
from .chnutils import dh, dAB
from .prng.mrg32k3a import MRG32k3a
import pickle
from statistics import mean, variance


def do_work(func, args, kwargs=None):
    """Wrapper a function with arguments and return the result."""
    # needed for use in the Python parallelization functions (e.g. apply_async)
    # ¯\_(ツ)_/¯
    if kwargs:
        result = func(*args, **kwargs)
    else:
        result = func(*args)
    return result


def combine_runs(rundicts):
    """Combine the output results of many runs into a single dictionary."""
    rundatdict = dict()
    for i, st in enumerate(rundicts):
        keys = list(st.keys())
        rundatdict[i] = dict()
        for k in keys:
            rundatdict[i][k] = st[k]
    return rundatdict


def run(boovsolver, budget, orc, **kwargs):
    """Solve a problem with the given budget."""
    exists_solvprn = kwargs.get('solvprn', False)
    if exists_solvprn:
        solvprn = kwargs.get('solvprn', None)
        kwargs['sprn'] = solvprn
        del kwargs['solvprn']
    solver = boovsolver(orc, **kwargs)
    mydat = solver.solve(budget)
    return mydat


def par_runs(joblst, num_proc=None):
    """Solve many problems in parallel."""
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


def gen_hdd(rdata, increment, budget, tc):
    """Generate hausdorf distance from real solution to generated solution."""
    hddict = {}
    ABdict = {}
    BAdict = {}
    nudict = {}
    max_nu1 = len(rdata['phat'])
    for nc in range(0, budget + increment, increment):
        mynu1 = 0
        nu1 = 0
        calls1 = 0
        while mynu1 < max_nu1 and calls1 <= nc:
            calls1 = rdata['simcalls'][nu1]
            if calls1 <= nc:
                nu1 = mynu1
            mynu1 += 1
        phat1 = rdata['phat'][nu1]
        ehat1 = []
        for p1 in phat1:
            ehat1.append(tc.detorc.g(p1))
        hdminlst = []
        ABminlst = []
        BAminlst = []
        for solnset in tc.soln:
            hdminlst.append(dh(ehat1, solnset))
            ABminlst.append(dAB(ehat1, solnset))
            BAminlst.append(dAB(solnset, ehat1))
        hd = min(hdminlst)
        ab = min(ABminlst)
        ba = min(BAminlst)
        hddict[nc] = hd
        ABdict[nc] = ab
        BAdict[nc] = ba
        nudict[nc] = nu1
    return {'hd': hddict, 'nu': nudict, 'AB': ABdict, 'BA': BAdict}


def par_diff(joblist, num_proc=None):
    """Generate Hausdorf distances in parallel."""
    if not num_proc:
        NUM_PROCESSES = mp.cpu_count()
    else:
        NUM_PROCESSES = num_proc
    hddict = dict()
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = [(gen_hdd, (e)) for e in joblist]
        app_rd = [p.apply_async(do_work, job) for job in worklist]
        for i, r in enumerate(app_rd):
            myitem = r.get()
            hddict[i] = myitem
    return hddict


def gen_qdata(num_exp, increment, budget, qdat):
    """Generate a dictionary of quantile data of hausdorf dist for plotting."""
    dat = ['hd', 'AB', 'BA',]
    nuk = 'nu'
    nudict = dict()
    meandict = dict()
    sedict = dict()
    hausdict = dict()
    tpbdict = dict()
    myruns = range(num_exp)
    v = 0
    iy05 = floor(num_exp*0.05)
    iy2 = floor(num_exp*0.25)
    iy5 = floor(num_exp*0.5)
    iy8 = floor(num_exp*0.75)
    iy95 = floor(num_exp*0.95)
    qlst = [iy05, iy2, iy5, iy8, iy95]
    mykeys = ['X', 'Y05', 'Y25', 'Y50', 'Y75', 'Y95']
    X = []
    myvals = dict()
    for d in dat:
        Y05 = []
        Y25 = []
        Y50 = []
        Y75 = []
        Y95 = []
        myvals[d] = [X, Y05, Y25, Y50, Y75, Y95]
    num_vals = 5
    for ncalls in range(0, budget + increment, increment):
        X.append(ncalls)
        for d in dat:
            hlst1 = [qdat[i][d][ncalls] for i in myruns]
            hlst1.sort()
            for val in range(1, num_vals + 1):
                myvals[d][val].append(hlst1[qlst[val - 1]])
        allnus = sum([qdat[i][nuk][ncalls] for i in myruns])
        nudict[ncalls] = allnus/num_exp
        hausdict[ncalls] = hlst1.sort()
        meanlst = [qdat[i]['hd'][ncalls] for i in myruns]
        callmean = mean(meanlst)
        meandict[ncalls] = callmean
        if len(meanlst) > 1:
            callvar = variance(meanlst, callmean)
        else:
            callvar = 0
        sedict[ncalls] = sqrt(callvar)/sqrt(num_exp)
    datdict = dict()
    for d in dat:
        mydict = dict(zip(mykeys, myvals[d]))
        datdict[d] = mydict
    datdict['hauslst'] = hausdict
    datdict['nu'] = nudict
    datdict['mean'] = meandict
    datdict['se'] = sedict
    return datdict
