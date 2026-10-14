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
get_path_prnstreams
combine_runs
isp_run
PathJob
run_path
run_paths
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

import numbers
import random
from .moso import (
    does_weak_dominate, does_dominate, does_strict_dominate, is_lep, is_lwep,
    get_biparetos, front, get_nondom, get_nbors, argsort, get_setnbors,
    enorm, perturb, edist, dxB, dAB, dh,
)
from .layout import (
    get_testsolve_prnstreams, _testsolve_roots, get_path_prnstreams,
    get_solv_prnstreams, check_role_draws, _testsolve_endseed,
)
from .paths import (
    combine_runs, isp_run, PathJob, run_path, run_paths, gen_metric, par_diff,
)
from .prng import registry

# MAX_RI (a reserved 200-RA-iteration substream window per independent
# sample path, and the RuntimeError RASolver.rasolve raised past it) is
# removed as of docs/rng-interface-design.md §12 step 4b: each path's
# oracle stream is now computed directly from `isp` via ISP_STRIDE
# (get_testsolve_prnstreams below), so there is no reservation to
# overrun and nothing left to guard. See KNOWN_ISSUES.md issue 2 for the
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
DEFAULT_GENERATOR = registry.DEFAULT_GENERATOR
# Sourced from the default generator's own module (§3.7: each
# generator's default seed is a per-generator constant), not a second
# literal copy -- mrg32k3a.DEFAULT_SEED and this name must never drift
# apart, so there's exactly one place the value lives.
DEFAULT_SEED = registry.GENERATORS[DEFAULT_GENERATOR].DEFAULT_SEED
DEFAULT_SIMPAR = 1
DEFAULT_ISP = 1
DEFAULT_PROC = 1
DEFAULT_CRN = False
DEFAULT_RANX0 = False

def starting_point(x0, dim):
    """
    A caller's starting point as a tuple of the right length, or an
    error at the call that says what is wrong with it.

    The CLI has always turned its own x0 into a tuple and checked its
    length (commands/solve.py); the library took whatever it was
    given, and a list failed deep inside a solver with "cannot use
    'list' as a set element".

    The components are not changed. Any real number is let through as
    it is -- an int, a float, a numpy scalar -- and the oracle decides
    whether the point is feasible (chnbase.Oracle's docstring says
    what a point may be). Only things that are not numbers at all are
    refused here.

    Parameters
    ----------
    x0 : sequence of numbers
    dim : int
        The problem's dimension.

    Returns
    -------
    tuple
        The components of `x0`, unchanged.

    Raises
    ------
    TypeError
        `x0` is not a sequence of numbers.
    ValueError
        `x0` has the wrong number of components.
    """
    if isinstance(x0, (str, bytes)):
        raise TypeError('x0 must be a sequence of numbers, such as (30, 30); got the string {0!r}.'.format(x0))
    try:
        point = tuple(x0)
    except TypeError:
        raise TypeError('x0 must be a sequence of numbers, such as (30, 30); got {0!r}.'.format(x0)) from None
    for component in point:
        if not isinstance(component, numbers.Real):
            raise TypeError(
                'every component of x0 must be a number; got {0!r} in x0={1!r}.'.format(component, x0)
            )
    if len(point) != dim:
        raise ValueError(
            'x0 must have {0} component{1}, one per dimension of the problem; '
            'got {2}: x0={3!r}.'.format(dim, '' if dim == 1 else 's', len(point), x0)
        )
    return point


def solver_params(kwargs):
    """
    The keyword arguments solve() and testsolve() did not take for
    themselves, as the solver's parameters: `(name, float)` pairs.

    Every parameter has always been passed through `float()`, and
    still is, so a number reaches a solver exactly as it did. What
    changed is what happens to something that is not a number: it is
    refused here, by name. It used to fail as `could not convert
    string to float: 'x'`, with no word of which keyword -- or, for a
    string such as "2", to be converted without comment.

    Parameters
    ----------
    kwargs : dict

    Returns
    -------
    list of (str, float)

    Raises
    ------
    TypeError
        A value is not a real number.
    """
    params = []
    for name, value in kwargs.items():
        if not isinstance(value, numbers.Real):
            raise TypeError(
                'solver parameter {0}={1!r} is not a number. Solver parameters '
                'are numbers; each is passed to the solver as a float.'.format(name, value)
            )
        params.append((name, float(value)))
    return params


def solve(problem, solver, x0, **kwargs):
    """
    Uses a specified MOSO algorithm to solve a MOSO problem.

    Parameters
    ----------
    problem : chnbase.Oracle class
    solver : chnbase.MOSOSolver class
    x0 : sequence of numbers
        Feasible starting point for the algorithms: one number per
        dimension of the problem. A whole number of any numeric type
        (30, 30.0, a numpy integer) is the same point; the problem's
        own g() decides whether the point is feasible.
    kwargs : dict
        `budget`, `generator`, `seed`, `simpar`, `crn` and `backend`
        (where `simpar` worker processes run; `pool.LocalBackend`
        describes what a backend is) are taken from here. Everything
        else is passed to the solver as a parameter.

    Returns
    -------
    tuple
        Length is 2, first item is a set of feasible points and second
        is a tuple of int of length 6 for the default generator (whatever
        shape the selected `generator` returns for its own seed otherwise)
    """

    budget = kwargs.pop('budget', DEFAULT_BUDGET)
    generator = kwargs.pop('generator', DEFAULT_GENERATOR)
    backend = registry.get_generator(generator)
    seed = kwargs.pop('seed', backend.DEFAULT_SEED)
    simpar = kwargs.pop('simpar', DEFAULT_SIMPAR)
    crn = kwargs.pop('crn', DEFAULT_CRN)
    pool_backend = kwargs.pop('backend', None)
    if getattr(pool_backend, 'remote', False) and simpar < 2:
        raise ValueError(
            'solve() was given a remote backend and simpar={0}. With a remote '
            'backend, simpar is the number of tasks each of the solver\'s '
            'requests for replications is divided into, and it has to be at '
            'least 2. Before choosing one: sending replications to a cluster '
            'is slower than running them here unless one replication costs '
            'roughly 100 ms or more (docs/spark-backend.md).'.format(simpar)
        )
    paramtups = solver_params(kwargs)
    ## generate all prn streams
    orcstream, solvstream = get_solv_prnstreams(seed, backend)
    orc = problem(orcstream)
    x0 = starting_point(x0, orc.dim)
    ## generate the experiment list
    paramlst = [('solvprn', solvstream), ('x0', x0), ]
    orc.set_crnflag(crn)
    ## create arguments for (unknown) optional named parameters
    if paramtups:
        paramlst.extend(paramtups)
    paramargs = dict(paramlst)
    with orc.set_simpar(simpar, backend=pool_backend):
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
    x0 : sequence of numbers
        Feasible starting point for the algorithms, as for solve().
    kwargs : dict
        `budget`, `generator`, `seed`, `isp`, `proc`, `ranx0`, `crn`
        and `backend` (where `proc` worker processes run;
        `pool.LocalBackend` describes what a backend is) are taken
        from here. Everything else is passed to the solver as a
        parameter.

    Returns
    -------
    res : dict
        Keys must include 'itersoln', 'simcalls'
    endseed : tuple of int
        The mrg32k3a seed representing the next seed which generates
        an independent stream.
    """

    budget = kwargs.pop('budget', DEFAULT_BUDGET)
    generator = kwargs.pop('generator', DEFAULT_GENERATOR)
    backend = registry.get_generator(generator)
    seed = kwargs.pop('seed', backend.DEFAULT_SEED)
    isp = kwargs.pop('isp', DEFAULT_ISP)
    proc = kwargs.pop('proc', DEFAULT_PROC)
    ranx0 = kwargs.pop('ranx0', DEFAULT_RANX0)
    crn = kwargs.pop('crn', DEFAULT_CRN)
    pool_backend = kwargs.pop('backend', None)
    if getattr(pool_backend, 'remote', False) and proc != DEFAULT_PROC:
        raise ValueError(
            'testsolve() was given a remote backend and proc={0}. proc is the '
            'number of worker processes on this machine; a remote backend '
            'runs every sample path as a task of its own and decides for '
            'itself how many run at once. Leave proc out.'.format(proc)
        )
    paramtups = solver_params(kwargs)
    x0stream, orc_root = _testsolve_roots(isp, seed, backend)
    currtest = tester()
    if not ranx0:
        # The dimension is read from a throwaway instance, as the CLI
        # reads it; no stream of the run is touched.
        x0 = starting_point(x0, currtest.ranorc(random.Random()).dim)
    # A path is described as data (PathJob) and built where it runs:
    # nothing live -- no Oracle, no stream -- crosses a process
    # boundary. Random starting points are the one thing a path cannot
    # rebuild for itself: they are drawn here, in path order, from one
    # shared stream, so path t's depends on the t draws before it.
    jobs = []
    for i in range(isp):
        if ranx0:
            x0 = currtest.get_ranx0(x0stream)
        jobs.append(PathJob(
            path=i, x0=x0, budget=budget, seed=seed, generator=generator, crn=crn, params=tuple(paramtups),
        ))
    check_role_draws(x0stream, backend, 'x0')
    res = run_paths(tester, solver, jobs, proc, tester_instance=currtest, backend=pool_backend)
    endseed = _testsolve_endseed(res, isp, orc_root, backend)
    return res, endseed
