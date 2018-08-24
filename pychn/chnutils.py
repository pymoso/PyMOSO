#!/usr/bin/env python
from itertools import product, filterfalse
from math import ceil, floor, sqrt
import multiprocessing as mp
from statistics import mean, variance


def solve(problem, solver, x0, **kwargs):
    budget = kwargs.get('budget', 50000)
    default_seed = (12345, 12345, 12345, 12345, 12345, 12345)
    seed = kwargs.get('seed', default_seed)
    radius = kwargs.get('radius', 1)
    simpar = kwargs.get('simpar', 1)
    del kwargs['budget']
    del kwargs['seed']
    del kwargs['radius']
    del kwargs['simpar']
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(vals[i]))
        paramtups.append(ptup)
    ## generate all prn streams
    orcstream, solvstream = get_solv_prnstreams(seed)
    ## generate the experiment list
    paramlst = [('solvprn', solvstream), ('x0', x0), ('nbor_rad', radius), ]
    orc = problem(orcstream)
    orc.simpar = simpar
    ## create arguments for (unknown) optional named parameters
    if paramtups:
        paramlst.extend(paramtups)
    paramargs = dict(paramlst)
    res = isp_run(solver, budget, orc, **paramargs)
    return res


def testsolve(tester, solver, x0, **kwargs):
    pass


def get_solv_prnstreams(iseed):
    from .prng.mrg32k3a import MRG32k3a, get_next_prnstream
    orcstream = MRG32k3a(iseed)
    solvstream = get_next_prnstream(iseed)
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


def combine_runs(rundicts):
    """Combine the output results of many runs into a single dictionary."""
    rundatdict = dict()
    for i, st in enumerate(rundicts):
        keys = list(st.keys())
        rundatdict[i] = dict()
        for k in keys:
            rundatdict[i][k] = st[k]
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


def get_x0(orc0, xprn):
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


def feas2set(feasdict):
    dimlstdict = dict()
    for d in feasdict:
        tuplst = feasdict[d]
        dimlstdict[d] = []
        for interval in feasdict[d]:
            dimlstdict[d].extend(list(range(interval[0], interval[1])))
    dimlst = [dimlstdict[d] for d in feasdict]
    mcX = product(*dimlst)
    return mcX


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
    if g2[0] == g1[0] and g2[1] == g1[1]:
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


def get_les(edict):
    """returns a collection of les"""
    lessets = set()
    lepset = set()
    feasset = set(edict.keys())
    # first get all leps
    print('..... finding LEPs .....')
    for x in edict:
        if is_lep(x, edict):
            lepset |= {x}
    print('..... found ', len(lepset), ' LEPs! .....')
    # crawl from each to form the les
    pts_vis = set()
    print('..... constructing LESs .....')
    while lepset - pts_vis:
        leplst = list(lepset - pts_vis)
        #print('remaining LEPs: ', len(leplst))
        x = leplst[0]
        les = {x}
        pts_vis |= {x}
        nbors = get_setnbors(les) & feasset
        tmp = {x: edict[x] for x in nbors | les}
        ncn = get_biparetos(tmp) & nbors
        no_repeats = True
        while ncn:
            pts_vis |= ncn & lepset
            les |= ncn
            #tmp = {x: edict[x] for x in les}
            #les = get_biparetos(tmp)
            nbors = get_setnbors(les) & feasset
            if nbors & pts_vis:
                no_repeats = False
            pts_vis |= nbors & lepset
            tmp = {x: edict[x] for x in nbors | les}
            nond = get_biparetos(tmp)
            ncn = nond & nbors
        tmp = {x: edict[x] for x in les}
        les = get_biparetos(tmp)
        lessets.add(frozenset(les))
    print('..... found ', len(lessets), ' disjoint LESs! .....')
    return lessets


def get_lwes(edict):
    """returns a collection of lwes"""
    lessets = set()
    lepset = set()
    feasset = set(edict.keys())
    # first get all leps
    print('.....finding LWEPs.....')
    for x in edict:
        if is_lwep(x, edict):
            lepset |= {x}
    print('.....found ', len(lepset), ' LWEPs!.....')
    # crawl from each to form the les
    pts_vis = set()
    print('.....constructing LWESs.....')
    while lepset - pts_vis:
        leplst = list(lepset - pts_vis)
        #print('remaining LEPs: ', len(leplst))
        x = leplst[0]
        les = {x}
        pts_vis |= {x}
        nbors = get_setnbors(les) & feasset
        tmp = {x: edict[x] for x in nbors | les}
        ncn = remove_strict_dom(tmp) & nbors
        no_repeats = True
        while ncn:
            pts_vis |= ncn & lepset
            les |= ncn
            #tmp = {x: edict[x] for x in les}
            #les = get_biparetos(tmp)
            nbors = get_setnbors(les) & feasset - les
            if nbors & pts_vis:
                no_repeats = False
            pts_vis |= nbors & lepset
            tmp = {x: edict[x] for x in nbors | les}
            nond = remove_strict_dom(tmp)
            ncn = nond & nbors - les
        tmp = {x: edict[x] for x in les}
        les = remove_strict_dom(tmp)
        lessets.add(frozenset(les))
    print('.....found ', len(lessets), ' disjoint LWESs!.....')
    print('.....Done!.....')
    return lessets


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
