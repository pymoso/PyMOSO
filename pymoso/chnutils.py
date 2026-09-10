#!/usr/bin/env python
"""
Provide supporting functions for solving MOSO problems, implementing
MOSO algorithms, and computing metrics.

Listing
--------------
solve
testsolve
get_testsolve_prnstreams
get_solv_prnstreams
do_work
combine_runs
isp_run
par_runs
gen_metric
par_diff
does_weak_dominate
does_dominate
does_strict_dominate
is_lep
is_lwep
get_biparetos
front
get_nondom
get_nbors
argsort
get_setnbors
enorm
perturb
edist
dxB
dAB
dH
"""

from itertools import product, filterfalse
from math import ceil, floor, sqrt
import multiprocessing as mp
from statistics import mean, variance
from .prng.mrg32k3a import (
    MRG32k3a, get_next_prnstream, jump_seed_n, stream_at,
    ISP_STRIDE, ISP_ITER_MARGIN, ITER_STRIDE, SYNC_ZONE_STREAM_START,
)
from .prng.base import one_past

# MAX_RI (a reserved 200-RA-iteration substream window per independent
# sample path, and the RuntimeError RASolver.rasolve raised past it) is
# removed as of docs/rng-interface-design.md §12 step 4b: each path's
# oracle stream is now computed directly from `isp` via ISP_STRIDE
# (get_testsolve_prnstreams below), so there is no reservation to
# overrun and nothing left to guard. See KNOWN_ISSUES.md issue 3 for the
# defect this originally fixed, and its current status note.

# Defaults for solve()/testsolve()'s keyword arguments, matching the CLI's
# documented values (pymoso/cli.py's --budget/--simpar/--isp/--proc
# [default: ...] annotations and commands/solve.py's/testsolve.py's own
# seed fallback). Defined here, not in commands/basecomm.py, because
# basecomm.py already imports chnutils -- the reverse import would be
# circular. The CLI layer imports these same names for its own Python-
# level defaults instead of hardcoding a second copy; tests/test_kwarg_
# defaults.py additionally checks the values against argparse's own
# parsed defaults directly, so a change to either side that isn't
# mirrored in the other is caught rather than silently drifting.
DEFAULT_BUDGET = 200
DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)
DEFAULT_SIMPAR = 1
DEFAULT_ISP = 1
DEFAULT_PROC = 1
DEFAULT_CRN = False
DEFAULT_RANX0 = False

def solve(problem, solver, x0, **kwargs):
    """
    Uses a specified MOSO algorithm to solve a MOSO problem.

    Parameters
    ----------
    problem : chnbase.Oracle class
    solver : chnbase.MOSOSolver class
    x0 : tuple of int
        Feasible starting point for the algorithms
    kwargs : dict

    Returns
    -------
    tuple
        Length is 2, first item is a set of feasible points and second
        is a tuple of int of length 6
    """

    budget = kwargs.pop('budget', DEFAULT_BUDGET)
    seed = kwargs.pop('seed', DEFAULT_SEED)
    simpar = kwargs.pop('simpar', DEFAULT_SIMPAR)
    crn = kwargs.pop('crn', DEFAULT_CRN)
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    ## generate all prn streams
    solvstream = MRG32k3a(seed)
    orcstream = get_next_prnstream(seed, crn)
    orcstream, solvstream = get_solv_prnstreams(seed, crn)
    ## generate the experiment list
    paramlst = [('solvprn', solvstream), ('x0', x0), ]
    orc = problem(orcstream)
    orc.set_crnflag(crn)
    ## create arguments for (unknown) optional named parameters
    if paramtups:
        paramlst.extend(paramtups)
    paramargs = dict(paramlst)
    with orc.set_simpar(simpar):
        res = isp_run(solver, budget, orc, **paramargs)
    lastnu = len(res['itersoln']) - 1
    return res['itersoln'][lastnu], res['endseed']


def testsolve(tester, solver, x0, **kwargs):
    """
    Tests a MOSO algorithm on a MOSO problem.

    Parameters
    ----------
    problem : chnbase.Oracle class
    solver : chnbase.MOSOSolver class
    x0 : tuple of int
        Feasible starting point for the algorithms
    kwargs : dict

    Returns
    -------
    res : dict
        Keys must include 'itersoln', 'simcalls'
    endseed : tuple of int
        The mrg32k3a seed representing the next seed which generates
        an independent stream.
    """

    budget = kwargs.pop('budget', DEFAULT_BUDGET)
    seed = kwargs.pop('seed', DEFAULT_SEED)
    isp = kwargs.pop('isp', DEFAULT_ISP)
    proc = kwargs.pop('proc', DEFAULT_PROC)
    ranx0 = kwargs.pop('ranx0', DEFAULT_RANX0)
    crn = kwargs.pop('crn', DEFAULT_CRN)
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    orcstreams, solvstreams, x0stream, endseed, orc_root = get_testsolve_prnstreams(isp, seed, crn)
    joblist = []
    currtest = tester()
    orclst = []
    for i in range(isp):
        if ranx0:
            x0 = currtest.get_ranx0(x0stream)
        paramlst = [('solvprn', solvstreams[i]), ('x0', x0), ]
        orc = currtest.ranorc(orcstreams[i])
        orc.set_crnflag(crn)
        orc.set_simpar(1)
        orclst.append(orc)
        ## create arguments for (unknown) optional named parameters
        if paramtups:
            paramlst.extend(paramtups)
        paramargs = dict(paramlst)
        mainparms = (solver, budget, orc)
        joblist.append((mainparms, paramargs))
    res = par_runs(joblist, proc)
    for o in orclst:
        o.mp_cleanup()
    # docs/rng-interface-design.md §12 step 8 stage 2 / §12 step 6c: the
    # real endseed, aggregated across every isp path's own oracle-role
    # high-water mark (crossing the --proc worker boundary via each
    # path's own result dict -- see Oracle.get_high_water_mark()'s
    # docstring for why a dict field, not the orc objects here, which
    # under --proc/--simpar never ran in this process at all).
    #
    # Path t's own Oracle stream is relative to `orc_root + t*ISP_STRIDE`
    # (get_testsolve_prnstreams's own construction); since
    # ISP_STRIDE == ISP_ITER_MARGIN*ITER_STRIDE exactly, path t's own
    # (oracle_stream, oracle_offset) composes additively into the shared
    # root's own stream units: t*ISP_ITER_MARGIN + oracle_stream,
    # oracle_offset unchanged -- the same composition Oracle.get_endseed()
    # itself relies on, one level up. Reduces to exactly the same flat
    # value the pre-split code computed (t*ISP_STRIDE + oracle_flat), so
    # this is a relabeling here too, not new arithmetic.
    #
    # The "+1 with carry" (base.one_past) happens once, at the very end,
    # against the *winning* path's own raw oracle_stream/family capacity
    # -- not against the combined value -- for the same reason
    # Oracle.get_endseed() itself carries against its own local stream:
    # the family boundary (ISP_ITER_MARGIN, or unbounded in the sync
    # zone) is a property of that one Oracle's own coordinate space, not
    # of the combined isp-relative value.
    touches = []
    for t in range(isp):
        hwm = res[t]['oracle_high_water_mark']
        if hwm is None:
            continue
        oracle_stream, oracle_offset = hwm
        touches.append((t * ISP_ITER_MARGIN + oracle_stream, oracle_offset, t, oracle_stream))
    if not touches:
        endseed = orc_root
    else:
        _, offset, t, oracle_stream = max(touches)
        family_capacity = ISP_ITER_MARGIN if oracle_stream < SYNC_ZONE_STREAM_START else None
        carried_stream, carried_offset = one_past(
            oracle_stream, offset, offset_capacity=ITER_STRIDE, stream_family_capacity=family_capacity
        )
        overall_stream = t * ISP_ITER_MARGIN + carried_stream
        endseed = stream_at(orc_root, overall_stream, carried_offset).get_seed()
    return res, endseed


def get_testsolve_prnstreams(num_trials, iseed, crn):
    """
    Create the set of random number stream generators with which to test
    a MOSO algorithm.

    Parameters
    ----------
    num_trials : int
        Number of independent sample paths of Oracles to test an
        algorithm
    iseed : tuple of int
        Starting seed from which to create the generators
    crn : bool
        Indicate whether CRN is on or off

    Returns
    -------
    orcprn_lst : list of prng.MRG32k3a objects
    solprn_lst : list of prng.MRG32k3a objects
    xprn : prng.MRG32k3a object
    iseed : tuple of int
        The reservation-based "next isp slot" seed -- kept for callers
        that only need a cheap, always-available independent seed and
        don't need it to reflect actual consumption. testsolve()'s own
        reported endseed no longer uses this value as of docs/rng-
        interface-design.md §12 step 8 stage 2 -- it's recomputed from
        each path's real high-water mark after solving, using orc_root
        below.
    orc_root : tuple of int
        The oracle role's own root seed, shared across every path
        (path t's own root is `stream_at(orc_root, t*ISP_ITER_MARGIN, 0)`,
        §12 step 6c -- the same position `jump_seed_n(orc_root,
        t*ISP_STRIDE)` always reached).
        Exposed so a caller can combine per-path high-water marks
        (Oracle.get_high_water_mark()) into one real endseed after
        solving -- see testsolve()'s own use of this.

    Notes
    -----
    Each path's oracle stream is computed directly from `isp` via
    ISP_STRIDE (docs/rng-interface-design.md §6/§12 step 4b) -- no
    per-path reservation walk (formerly MAX_RI-sized) exists to overrun,
    so deriving path 5's stream costs the same O(log(index)) matrix-
    power work whether path 5 is requested first, last, or alone,
    regardless of how many iterations any other path used.
    """
    xprn = MRG32k3a(iseed)
    orcprn_lst = []
    solprn_lst = []
    for t in range(num_trials):
        solprn = get_next_prnstream(iseed, False)
        iseed = solprn.get_seed()
        solprn_lst.append(solprn)
    # `iseed` here (post-solprn loop) is the oracle role's own root --
    # solver-role and oracle-role streams stay structurally separated,
    # unchanged from before this step.
    orc_root = iseed
    for t in range(num_trials):
        # §12 step 6c: stream_at(orc_root, t*ISP_ITER_MARGIN, 0), not a
        # raw jump_seed_n(orc_root, t*ISP_STRIDE) call -- a relabeling
        # of the exact same arithmetic (ISP_STRIDE ==
        # ISP_ITER_MARGIN*ITER_STRIDE exactly, so
        # t*ISP_ITER_MARGIN*ITER_STRIDE + 0 == t*ISP_STRIDE), not new
        # arithmetic; confirmed directly, not assumed.
        orcprn = stream_at(orc_root, t * ISP_ITER_MARGIN, 0)
        orcprn.set_class_cache(crn)
        orcprn_lst.append(orcprn)
    # The next independent stream past every path actually reserved --
    # path `num_trials` would be the next one derived by this same
    # formula, so its seed is the natural "next" value to report,
    # matching this function's pre-existing "next independent seed"
    # contract without needing a live walk to compute it.
    iseed = jump_seed_n(orc_root, num_trials * ISP_STRIDE)
    return orcprn_lst, solprn_lst, xprn, iseed, orc_root


def get_solv_prnstreams(iseed, crn):
    """
    Create a random number stream for the algorithm to use and an
    independent one to do simulations.

    Parameters
    ----------
    iseed : tuple of int
        Starting seed to create the generators
    crn : bool
        Indicates whether CRN will be used

    Returns
    -------
    orcstream : prng.MRG32k3a object
    solvstream : prng.MRG32k3a object
    """
    solvstream = MRG32k3a(iseed)
    orcstream = get_next_prnstream(iseed, crn)
    return orcstream, solvstream


def do_work(func, args, kwargs=None):
    """
    Wrap a function with arguments and return the result for
    multiprocessing routines.

    Parameters
    ----------
    func
        Function to be called in multiprocessing
    args : tuple
        Positional arguments to 'func'
    kwargs : dict
        Keyword arguments to 'func'

    Returns
    -------
    result
        Output of 'func(args, kwargs)'
    """
    # needed for use in the Python parallelization functions (e.g. apply_async)
    # ¯\_(ツ)_/¯
    if kwargs:
        result = func(*args, **kwargs)
    else:
        result = func(*args)
    return result


def combine_runs(runsets):
    """
    Combine the output results of many runs into a single dictionary.

    Parameters
    ----------
    runsets : list
        Outputs of multiple calls to 'chnbase.MOSOSolver.solve'

    Returns
    -------
    rundatdict : dict
    """
    rundatdict = dict()
    for i, st in enumerate(runsets):
        rundatdict[i] = st
    return rundatdict


def isp_run(boovsolver, budget, orc, **kwargs):
    """
    Solve multiple sample paths of a problem using the same algorithm.

    Parameters
    ----------
    boovsolver : chnbase.MOSOSolver class
    budget : int
    orc : chnbase.Oracle object
    kwargs : dict

    Returns
    -------
    mydat : dict
        Output of a 'chnbase.MOSOSolver.solve' call
    """
    exists_solvprn = kwargs.get('solvprn', False)
    if exists_solvprn:
        solvprn = kwargs.get('solvprn', None)
        kwargs['sprn'] = solvprn
        del kwargs['solvprn']
    solver = boovsolver(orc, **kwargs)
    mydat = solver.solve(budget)
    return mydat


def par_runs(joblst, num_proc=1):
    """
    Solve many problems in parallel.

    Parameters
    ----------
    joblist : list of tuple
        Each tuple is length 2. 'tuple[0]' is tuple of positional
        arguments, 'tuple[1]' is dict of keyword arguments.
    num_proc : int
        Number of processes to use in parallel. Default is 1.

    Returns
    -------
    runtots : dict
        Contains the results of every chnbase.MOSOSOlver.solve call
    """
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
    """
    Generate metrics for a sample path run.

    Parameters
    ----------
    rundat : dict
        Ouput of a chnbase.MOSOSolver.solve call
    tester
        Instantiated object such that 'tester.metric' is callable

    Returns
    -------
    met_data : dict
        keys are iteration number, values are tuples of iteration
        number, number of calls, and metric values.
    """
    met_data = {}
    for nu in rundat['itersoln']:
        les_nu = rundat['itersoln'][nu]
        calls_nu = rundat['simcalls'][nu]
        met_nu = tester.metric(les_nu)
        met_data[nu] = (nu, calls_nu, met_nu)
    return met_data


def par_diff(rundata, tester, num_proc):
    """
    Compute metrics in parallel.

    Parameters
    ----------
    rundat : dict
        Ouput of a chnbase.MOSOSolver.solve call
    tester
        Instantiated object such that 'tester.metric' is callable
    num_proc : int
        Number of processes to use

    Returns
    -------
    hddict : dict
        keys are the isp number and values are the metric data
    """
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
    """
    Returns true if 'g1' weakly dominates 'g2' with the given relaxation

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    is_dom : bool

    Examples
    --------
    >>> does_weak_dominate((1, 2), (2, 3), (0, 0), (0, 0))
    True
    >>> does_weak_dominate((2, 3), (1, 2), (0, 0), (0, 0))
    False
    """
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    return is_dom


def does_dominate(g1, g2, delta1, delta2):
    """
    Returns true if g1 dominates g2 with the given relaxation.

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    is_dom : bool

    Examples
    --------
    >>> does_dominate((1, 2), (2, 3), (0, 0), (0, 0))
    True
    >>> does_dominate((1, 2), (1, 2), (0, 0), (0, 0))
    False
    """
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
    """
    Returns true if g1 strictly dominates g2 with the given relaxation.

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    bool

    Examples
    --------
    >>> does_strict_dominate((1, 1), (2, 2), (0, 0), (0, 0))
    True
    >>> does_strict_dominate((1, 2), (2, 2), (0, 0), (0, 0))
    False
    """
    dim = len(g1)
    is_sdom = True
    for i in range(dim):
        if g2[i] + delta2[i] <= g1[i] - delta1[i]:
            is_sdom = False
    return is_sdom


def is_lep(x, r, gdict):
    """
    Return true if x is a LEP

    Parameters
    ----------
    x : tuple of int
        Feasible point
    r : float
        Radius for which to consider neighbors
    gdict : dict
        Objective values for every neighbor of 'x'

    Returns
    -------
    bool
    """
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
    """
    Return true if x is a LWEP

    Parameters
    ----------
    x : tuple of int
        Feasible point
    r : float
        Radius for which to consider neighbors
    gdict : dict
        Objective values for every neighbor of 'x'

    Returns
    -------
    bool
    domset : set of tuple of int
        Set of points which strictly dominate 'x'
    """
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
    """
    Generate the non-dominated points of a set with two objectives.

    Parameters
    ----------
    edict : dict
        Keys are feasible points (tuples of int), values are objective
         values (tuples of float) of length 2

    Returns
    -------
    plist : set of tuple of int
        Set of non-dominated points
    """
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
    """
    Recursively generate the non-dominated set.

    Parameters
    ----------
    points : list of tuple of int
    objs : list of tuple of float
        Objective values of points

    Returns
    -------
    Tpts : list of tuple of int
    Tobjs : list of tuple of float
    """
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
    """
    Generate the non-dominated points of a set.

    Parameters
    ----------
    edict : dict
        Keys are feasible points (tuples of int), values are objective
         values (tuples of float)

    Returns
    -------
    set
        Set of non-dominated points

    Examples
    --------
    >>> sorted(get_nondom({(0, 0): (1, 5), (1, 0): (3, 3), (2, 0): (5, 1)}))
    [(0, 0), (1, 0), (2, 0)]
    >>> get_nondom({(0, 0): (1, 1), (1, 0): (2, 2)})
    {(0, 0)}
    """
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


def get_nbors(x, r=1):
    """
    Find all neighbors of a point.

    Parameters
    ----------
    x : tuple of int
        A point
    r : int
        radius of the neighborhood

    Returns
    -------
    set of tuple of int
        The neighborhood of 'x'

    Examples
    --------
    >>> sorted(get_nbors((0,), 1))
    [(-1,), (1,)]
    """
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
    nbors = set(filterfalse(edist_filter, boxpts))
    return set(nbors)


def argsort(seq):
    """
    Generate the sorted arguments of a collection of values

    Parameters
    ----------
    seq : dict

    Returns
    -------
    list
        list of keys sorted by value
    """
    return sorted(range(len(seq)), key=seq.__getitem__)


def get_setnbors(mcs, r):
    """
    Generate the exclusive neighborhood of a set.

    Parameters
    ----------
    mcs : set of tuple of int
        Set of points
    r : float
        Radius of neighborhood

    Returns
    -------
    set of tuple of int
        The exclusive neighborhood

    Examples
    --------
    >>> sorted(get_setnbors({(0,), (1,)}, 1))
    [(-1,), (2,)]
    """
    set_nbors = set()
    for x in mcs:
        set_nbors |= get_nbors(x, r)
    return set_nbors - mcs


def enorm(x):
    """
    Compute the norm of a vector.

    Parameters
    ----------
    x : tuple of numbers

    Returns
    -------
    float
    """
    q = len(x)
    return sqrt(sum([pow(x[i], 2) for i in range(q)]))


def perturb(x, prn):
    """
    Randomly perturb an integer point.

    Parameters
    ----------
    x : tuple of int
        Point to be perturbed
    prn : prng.MRG32k3a object

    Returns
    -------
    tuple of float
        The perturbed point
    """
    q = len(x)
    return tuple(x[i] + 0.3*(prn.random() - 0.5) for i in range(q))


def edist(x1,x2):
    """
    Compute Euclidean distance between two vectors.

    Parameters
    ----------
    x1 : tuple of numbers
    x2 : tuple of numbers

    Returns
    -------
    float

    Examples
    --------
    >>> edist((0, 0), (3, 4))
    5.0
    """
    q = len(x1)
    return sqrt(sum([pow(x1[i] - x2[i], 2) for i in range(q)]))


def dxB(x, B):
    """
    Compute distance from a point to a set.

    Parameters
    ----------
    x : tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    dmin : float
    """
    dmin = float('inf')
    for b in B:
        dxb = edist(x, b)
        if dxb < dmin:
            dmin = dxb
    return dmin


def dAB(A, B):
    """
    Compute distance from a set to another set.

    Parameters
    ----------
    A : set of tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    dmax : float
    """
    dmax = float('-inf')
    for a in A:
        daB = dxB(a, B)
        if daB > dmax:
            dmax = daB
    return dmax


def dh(A, B):
    """
    Compute the Hausdorf distance between two sets.

    Parameters
    ----------
    A : set of tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    float
        The Hausdorf distance

    Examples
    --------
    >>> dh({(0, 0)}, {(3, 4)})
    5.0
    >>> dh({(0, 0)}, {(0, 0)})
    0.0
    """
    return max(dAB(A, B), dAB(B, A))
