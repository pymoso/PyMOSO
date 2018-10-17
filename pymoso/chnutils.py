#!/usr/bin/env python
from itertools import product, filterfalse
from math import ceil, floor, sqrt
import multiprocessing as mp
from statistics import mean, variance
from .prng.mrg32k3a import MRG32k3a, get_next_prnstream

def solve(problem, solver, x0, **kwargs):
    budget = kwargs.pop('budget', 50000)
    default_seed = (12345, 12345, 12345, 12345, 12345, 12345)
    seed = kwargs.pop('seed', default_seed)
    simpar = kwargs.pop('simpar', 1)
    crn = kwargs.pop('crn', False)
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    ## generate all prn streams
    orcstream, solvstream = get_solv_prnstreams(seed)
    ## generate the experiment list
    paramlst = [('solvprn', solvstream), ('x0', x0), ]
    orc = problem(orcstream)
    orc.set_crnflag(crn)
    orc.simpar = simpar
    ## create arguments for (unknown) optional named parameters
    if paramtups:
        paramlst.extend(paramtups)
    paramargs = dict(paramlst)
    res = isp_run(solver, budget, orc, **paramargs)
    lastnu = len(res['itersoln']) - 1
    return res['itersoln'][lastnu], res['endseed']


def testsolve(tester, solver, x0, **kwargs):
    budget = kwargs.pop('budget', 50000)
    default_seed = (12345, 12345, 12345, 12345, 12345, 12345)
    seed = kwargs.pop('seed', default_seed)
    isp = kwargs.pop('isp', 1)
    proc = kwargs.pop('proc', 1)
    ranx0 = kwargs.pop('ranx0')
    crn = kwargs.pop('crn', False)
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    orcstreams, solvstreams, x0stream, endseed = get_testsolve_prnstreams(isp, seed)
    joblist = []
    currtest = tester()
    for i in range(isp):
        if ranx0:
            x0 = currtest.get_ranx0(x0stream)
        paramlst = [('solvprn', solvstreams[i]), ('x0', x0), ]
        orc = currtest.ranorc(orcstreams[i])
        orc.set_crnflag(crn)
        ## create arguments for (unknown) optional named parameters
        if paramtups:
            paramlst.extend(paramtups)
        paramargs = dict(paramlst)
        mainparms = (solver, budget, orc)
        joblist.append((mainparms, paramargs))
    res = par_runs(joblist, proc)
    return res, endseed


def get_testsolve_prnstreams(num_trials, iseed):
    xprn = MRG32k3a(iseed)
    max_RI = 200
    orcprn_lst = []
    solprn_lst = []
    for t in range(num_trials):
        solprn = get_next_prnstream(iseed)
        iseed = solprn.get_seed()
        solprn_lst.append(solprn)
    for t in range(num_trials):
        orcprn = get_next_prnstream(iseed)
        iseed = orcprn.get_seed()
        orcprn_lst.append(orcprn)
        for i in range(max_RI):
            newprn = get_next_prnstream(iseed)
            iseed = newprn.get_seed()
    return orcprn_lst, solprn_lst, xprn, iseed


def get_solv_prnstreams(iseed):
    solvstream = MRG32k3a(iseed)
    orcstream = get_next_prnstream(iseed)
    return orcstream, solvstream


def do_work(func, args, kwargs=None):
    """Wrapper a function with arguments and return the result."""
    # needed for use in the Python parallelization functions (e.g. apply_async)
    # ¯\_(ツ)_/¯
    if kwargs:
        result = func(*args, **kwargs)
    else:
        result = func(*args)
    return result


def combine_runs(runsets):
    """Combine the output results of many runs into a single dictionary."""
    rundatdict = dict()
    for i, st in enumerate(runsets):
        rundatdict[i] = st
    return rundatdict


def isp_run(boovsolver, budget, orc, **kwargs):
    """Solve a problem with the given budget."""
    exists_solvprn = kwargs.get('solvprn', False)
    if exists_solvprn:
        solvprn = kwargs.get('solvprn', None)
        kwargs['sprn'] = solvprn
        del kwargs['solvprn']
    solver = boovsolver(orc, **kwargs)
    mydat = solver.solve(budget)
    return mydat


def par_runs(joblst, num_proc=1):
    """Solve many problems in parallel."""
    NUM_PROCESSES = num_proc
    rundict = []
    #print(joblst)
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = [(isp_run, (e[0]), (e[1])) for e in joblst]
        app_rd = [p.apply_async(do_work, job) for job in worklist]
        for r in app_rd:
            myitem = r.get()
            rundict.append(myitem)
    runtots = combine_runs(rundict)
    return runtots


def gen_metric(rundat, tester):
    """Generate metrics for a sample path run."""
    met_data = {}
    for nu in rundat['itersoln']:
        les_nu = rundat['itersoln'][nu]
        calls_nu = rundat['simcalls'][nu]
        met_nu = tester.metric(les_nu)
        met_data[nu] = (nu, calls_nu, met_nu)
    return met_data


def par_diff(rundata, tester, num_proc):
    """Generate Hausdorf distances in parallel."""
    NUM_PROCESSES = num_proc
    num_isp = len(rundata)
    joblist = []
    for i in range(num_isp):
        joblist.append((rundata[i], tester))
    hddict = dict()
    with mp.Pool(NUM_PROCESSES) as p:
        worklist = [(gen_metric, (e)) for e in joblist]
        app_rd = [p.apply_async(do_work, job) for job in worklist]
        for i, r in enumerate(app_rd):
            myitem = r.get()
            hddict[i] = myitem
    return hddict


def does_weak_dominate(g1, g2, delta1, delta2):
    """returns true if g1 weakly dominates g2 with the given relaxation"""
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    return is_dom


def does_dominate(g1, g2, delta1, delta2):
    """returns true if g1 dominates g2 with the given relaxation"""
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    if is_dom:
        is_equal = True
        for i in range(dim):
            if not g1[i] - delta1[i] == g2[i] + delta2[i]:
                is_equal = False
        if is_equal:
            is_dom = False
    return is_dom


def does_strict_dominate(g1, g2, delta1, delta2):
    """returns true if g1 strictly dominates g2 with the given relaxation"""
    dim = len(g1)
    is_sdom = True
    for i in range(dim):
        if g2[i] + delta2[i] <= g1[i] - delta1[i]:
            is_sdom = False
    return is_sdom


def is_lep(x, r, gdict):
    """return true if x is a LEP"""
    dim = len(x)
    nbors = get_nbors(x, r)
    dominated = False
    delz = [0]*dim
    fx = gdict[x]
    for n in nbors:
        if n in gdict:
            fn = gdict[n]
            if does_dominate(fn, fx, delz, delz):
                dominated = True
    return not dominated


def is_lwep(x, r, gdict):
    """return true if x is an LWEP"""
    dim = len(gdict[x])
    nbors = get_nbors(x, r)
    dominated = False
    delz = [0]*dim
    fx = gdict[x]
    domset = set()
    for n in nbors:
        if n in gdict:
            fn = gdict[n]
            if does_strict_dominate(fn, fx, delz, delz):
                dominated = True
                domset |= {n}
    return not dominated, domset


def get_biparetos(edict):
    """returns the non-dominated keys of a dictionary {x: (g1, g2)}"""
    pts = list(edict.keys())
    vals = list(edict.values())
    sind = argsort(vals)
    g2 = 1
    dlen = len(pts)
    plist = set()
    if dlen > 1:
        i = 0
        j = 0
        while j < dlen:
            is_pareto = False
            bkey = pts[sind[i]]
            plist |= {bkey}
            j = i + 1
            #print('i: ', i, ' j: ', j, ' bkey: ', bkey, ' len: ', dlen)
            while not is_pareto and j < dlen:
                newp = pts[sind[j]]
                if edict[bkey][g2] > edict[newp][g2]:
                    is_pareto = True
                    i = j
                else:
                    j += 1
    else:
        plist |= set(pts)
    return plist


def front(points, objs):
    """Compute the non-dominated set via Kung et. al 1975."""
    cardP = len(points)
    if cardP == 1:
        return points, objs
    elif cardP > 1:
        nondom = set()
        halfind = int(cardP/2)
        Tpts, Tobjs = front(points[0:halfind], objs[0:halfind])
        Bpts, Bobjs = front(points[halfind:cardP], objs[halfind:cardP])
        brange = range(len(Bpts))
        for i in brange:
            pt = Bpts[i]
            gvals = Bobjs[i]
            delz = [0]*len(gvals)
            pt_nondom = True
            j = 0
            while j < len(Tpts) and pt_nondom:
                if does_dominate(Tobjs[j], gvals, delz, delz):
                    pt_nondom = False
                j += 1
            if pt_nondom:
                Tpts.append(pt)
                Tobjs.append(gvals)
        return Tpts, Tobjs


def get_nondom(edict):
    """Return the set of non-dominated feasible points."""
    pts = list(edict.keys())
    vals = list(edict.values())
    sind = argsort(vals)
    newpts = []
    newvals = []
    for i in range(len(pts)):
        newpts.append(pts[sind[i]])
        newvals.append(vals[sind[i]])
    Mpts, Mobjs = front(newpts, newvals)
    return set(Mpts)


def remove_strict_dom(edict):
    """returns the non-strictly-dominated keys of a dictionary {x: (g1, g2)}"""
    g1 = 0
    g2 = 1
    pars = get_biparetos(edict)
    pts = set(edict.keys())
    g1parmax = min(pars, key=lambda x: edict[x][g1])
    g2parmax = min(pars, key=lambda x: edict[x][g2])
    g1parval = edict[g1parmax][g1]
    g2parval = edict[g2parmax][g2]
    g1weak = [x for x in pts if edict[x][g1] == g1parval]
    g2weak = [x for x in pts if edict[x][g2] == g2parval]
    weaklies = pars | set(g1weak) | set(g2weak)
    return weaklies


def get_nbors(x, r=1):
    """Find all neighbors of point x within radius r."""
    # define a filter function for points too far away
    def edist_filter(x1):
        # also filter the input point
        if edist(x, x1) > r or x == x1:
            return True
    q = len(x)
    # generate all points in a box with sides length 2r around x
    bounds = []
    for i in range(q):
        a = int(ceil(x[i] - r))
        b = int(floor(x[i] + r))
        bounds.append(range(a, b+1))
    boxpts = product(*bounds)
    # remove those farther than r from x and return the list of neighbors
    nbors = filterfalse(edist_filter, boxpts)
    return set(nbors)


def argsort(seq):
    return sorted(range(len(seq)), key=seq.__getitem__)


def get_setnbors(mcs, r):
    """Generate the exclusive neighborhood of a set within radius r."""
    set_nbors = set()
    for x in mcs:
        set_nbors |= get_nbors(x, r)
    return set_nbors


def enorm(x):
    """compute the norm of a vector x"""
    q = len(x)
    return sqrt(sum([pow(x[i], 2) for i in range(q)]))


def perturb(x, prn):
    """ randomly perturb x, as in the R-SPLINE paper. See Wang et. al 2013"""
    q = len(x)
    u = prn.random()
    return tuple(x[i] + 0.3*(u - 0.5) for i in range(q))


def edist(x1,x2):
    """return Euclidean distance between 2 vectors"""
    q = len(x1)
    return sqrt(sum([pow(x1[i] - x2[i], 2) for i in range(q)]))


def dxB(x, B):
    """return distance from a point to a set"""
    dmin = float('inf')
    for b in B:
        dxb = edist(x, b)
        if dxb < dmin:
            dmin = dxb
    return dmin


def dAB(A, B):
    """return distance from set A to set B"""
    dmax = float('-inf')
    for a in A:
        daB = dxB(a, B)
        if daB > dmax:
            dmax = daB
    return dmax


def dh(A, B):
    """return the Hausdorf distance between sets A and B"""
    return max(dAB(A, B), dAB(B, A))
