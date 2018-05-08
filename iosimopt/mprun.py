#!/usr/bin/env python
from .testcases import *
from .solvers import *
from math import floor
import multiprocessing as mp
from .simoptutils import dh
from .mrg32k3a import MRG32k3a
import pickle
from statistics import mean, variance


def do_work(func, args):
    """wrapper to call a function with arguments and return the result"""
    # needed for use in the Python parallelization functions (e.g. apply_async)
    # ¯\_(ツ)_/¯
    result = func(*args)
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


def gen_qdata(num_exp, increment, budget, qdat):
    """generate a dictionary of quantile data of hausdorf dist for plotting"""
    dat = ['hd', 'AB', 'BA']
    nuk = 'nu'
    nudict = dict()
    meandict = dict()
    sedict = dict()
    myruns = range(num_exp)
    v = 0
    iy05 = floor(num_exp*0.05)
    iy2 = floor(num_exp*0.25)
    iy5 = floor(num_exp*0.5)
    iy8 = floor(num_exp*0.75)
    iy95 = floor(num_exp*0.95)
    qlst = [iy05, iy2, iy5, iy8, iy95]
    # so these key names should probably not be hardcoded.
    # for now manually ensure they match those in simplotting
    mykeys = ['X', 'Y105', 'Y12', 'Y15', 'Y18', 'Y195']
    X = []
    myvals = dict()
    for d in dat:
        Y105 = []
        Y12 = []
        Y15 = []
        Y18 = []
        Y195 = []
        myvals[d] = [X, Y105, Y12, Y15, Y18, Y195]
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
    datdict['nu'] = nudict
    datdict['mean'] = meandict
    datdict['se'] = sedict
    return datdict


def gen_hddata(rdata, increment, budget, tc):
    """generate hausdorf distances from real solution to generated solution"""
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
        hddict[nc] = min(hdminlst)
        ABdict[nc] = min(ABminlst)
        BAdict[nc] = min(BAminlst)
        nudict[nc] = nu1
    return {'hd': hddict, 'nu': nudict, 'AB': ABdict, 'BA': BAdict}


def run(boovsolver, budget, orc, orcprn, orcseed, solvprn=None, solvseed=None, x0=None, algparms=None):
    orcprn_ob = orcprn(orcseed)
    solvprn_ob = None
    if solvseed:
        solvprn_ob = solvprn(solvseed)
    orc_ob = orc(orcprn_ob)
    solver = boovsolver(orc_ob, solvprn_ob, x0, algparms)
    mydat = solver.solve(budget)
    return mydat


def par_runs(joblst, num_proc=None):
    if not num_proc:
        NUM_PROCESSES = mp.cpu_count()
    else:
        NUM_PROCESSES = num_proc
    rundict = []
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = [(run, (e)) for e in joblst]
        app_rd = [p.apply_async(do_work, job) for job in worklist]
        for r in app_rd:
            myitem = r.get()
            rundict.append(myitem)
    runtots = combine_runs(rundict)
    return runtots

def par_pltdat(joblst, budget, increment, num_proc=None):
    if not num_proc:
        NUM_PROCESSES = mp.cpu_count()
    else:
        NUM_PROCESSES = num_proc
    asd = {}
    hddict = {}
    pltdict = {}
    with mp.Pool(NUM_PROCESSES) as p:
        for i, task in enumerate(joblst):
            job = (gen_hddata, (task))
            asd[i] = p.apply_async(do_work, job)
        for i in range(len(joblst)):
            hddict[i] = asd[i].get()
    pltdict = gen_qdata(len(joblst), increment, budget, hddict)
    return pltdict


def par_exp(scenlst, num_exp, tp1, indepseeds, budget, paramlst1=None, paramlst2=None):
    """run experiments in parallel and generate hausdorf quantile plotting data"""
    print("..Initializing experiments -------------")
    NUM_PROCESSES = mp.cpu_count()
    inc = 10000
    orcseedfile = '../prnseeds/orcseeds.pkl'
    solseedfile = '../prnseeds/solseeds.pkl'
    orcseeds = get_seedstreams(orcseedfile)
    solseeds = get_seedstreams(solseedfile)
    xprn = MRG32k3a((12345, 12345, 12345, 12345, 12345, 12345))
    orc0 = tp1.detorc
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
    pref = '../ScenData/'
    num_scen = len(scenlst)
    nd = {n: [] for n in scenlst}
    indepctr = 0
    print("..Generating experiment list -------------")
    for s in scenlst:
        if paramlst1 and paramlst2:
            p1 = paramlst1[s]
            p2 = paramlst2[s]
        else:
            p1 = None
            p2 = None
        for j in range(num_exp):
            x0 = []
            for dim in range(orc0.dim):
                xq = xprn.sample(range(startd[dim], endd[dim]), 1)[0]
                x0.append(xq)
            x0 = tuple(x0)
            if not indepseeds:
                newtup = (scenlst[s], budget, tp1.ranorc, MRG32k3a, orcseeds[j], MRG32k3a, solseeds[j], x0, p1, p2)
            else:
                newtup = (scenlst[s], budget, tp1.ranorc, MRG32k3a, orcseeds[indepctr], MRG32k3a, solseeds[indepctr], x0, p1, p2)
            nd[s].append(newtup)
            indepctr += 1
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = dict()
        rundict = dict()
        runtots = dict()
        hddict = dict()
        pltdict = dict()
        app_rd = dict()
        app_rt = dict()
        app_pt = dict()
        app_qt = dict()
        num_rund = dict()
        print("..Performing experiment runs -------------")
        # async parallel loop -- perform experiments
        for s in nd:
            worklist[s] = [(run, (e)) for e in nd[s]]
            app_rd[s] = [p.apply_async(do_work, job) for job in worklist[s]]
        # blocking loop -- all above work must complete
        for s in nd:
            num_rund[s] = 0
            rundict[s] = []
            lctr = 0
            for r in app_rd[s]:
                myitem = r.get()
                rundict[s].append(myitem)
        print("..Combining runs and writing files -------------")
        #not parallel! the generated data can be too big to serialize
        for s in nd:
            runtots[s] = combine_runs(s, rundict[s])
        for s in nd:
            suff = '_'+tp1.tname+'_rundat.pkl'
            with open(pref+s+suff, 'wb') as h1:
                pickle.dump(runtots[s], h1)
        print("..Generating Hausdorf data -------------")
        # async parallel generate Hausdorf data
        for s in nd:
            app_pt[s] = dict()
            for exp in range(num_exp):
                job = (gen_hddata, (s, runtots[s][exp], inc, budget, tp1))
                app_pt[s][exp] = p.apply_async(do_work, job)
        print("..Generating and writing plot data files -------------")
        # blocking -- wait for Hausdorf data
        for s in nd:
            hddict[s] = dict()
            for exp in range(num_exp):
                hddict[s][exp] = app_pt[s][exp].get()
        # async parallel -- compute quntile data
        for s in nd:
            job = (gen_qdata, (num_exp, inc, budget, hddict[s]))
            app_qt[s] = p.apply_async(do_work, job)
        #blocking -- wait for quantile data and write plot files
        for s in nd:
            pltdict[s] = app_qt[s].get()
            suff = '_'+tp1.tname+'_pltdat.pkl'
            with open(pref+s+suff, 'wb') as h1:
                pickle.dump(pltdict[s], h1)
        print("....Done!...")


def main():
    num_exp = 1000
    budget = 5000000
    # num_splits = 25
    # stages = [int(budget*i/num_splits) for i in range(1, num_splits + 1)]
    # namelst = ['rpnb'+str(j) for j in stages]
    # slst = {name: rp for name in namelst}
    # paramlst = range(0, 21)
    # names = tuple('rpe'+str(paramlst[i]) for i in paramlst)
    # exps = tuple(RPE for i in paramlst)
    # slst = dict(zip(names, exps))
    # paramdict = dict(zip(names, paramlst))
    # names = ('rmin400', 'rmin401', 'rmin402', 'rmin403', 'rmin404', 'rmin405', 'rmin406', 'rmin407', 'rmin408', 'rmin409', 'rmin410', 'rmin411', 'rmin412', 'rmin413', 'rmin414', 'rmin415')
    # params1 = tuple(0.4 for name in names)
    # params2 = tuple(i/10 for i in range(len(names)))
    # slst = {name: RMINRLE for name in names}
    names = ('rrle', 'rp', 'moc', 'rmin', 'rpe')
    algs = (RRLE, rp, moc, RMINRLE, RPE)
    params1 = (0.4, 0.4, None, 0.4, 0.4)
    params2 = (0.9, 0.9, None, 0.9, 0.9)
    slst = dict(zip(names, algs))
    paramdict1 = dict(zip(names, params1))
    paramdict2 = dict(zip(names, params2))
    tp1 = TP1bTester()
    indepseeds = False
    par_exp(slst, num_exp, tp1, indepseeds, budget, paramdict1, paramdict2)


if __name__=='__main__':
    main()
