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

import copy
import numbers
import random
from dataclasses import dataclass
from .executor import ClassRef
from .moso import (
    does_weak_dominate, does_dominate, does_strict_dominate, is_lep, is_lwep,
    get_biparetos, front, get_nondom, get_nbors, argsort, get_setnbors,
    enorm, perturb, edist, dxB, dAB, dh,
)
from .layout import (
    get_testsolve_prnstreams, _testsolve_roots, get_path_prnstreams,
    get_solv_prnstreams, check_role_draws,
)
from .pool import LocalBackend
from .prng import registry
from .prng.base import one_past

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
    # docs/rng-interface-design.md §12 step 8 stage 2 / §12 step 6c: the
    # real endseed, aggregated across every isp path's own oracle-role
    # high-water mark (crossing the --proc worker boundary via each
    # path's own result dict -- see Oracle.get_high_water_mark()'s
    # docstring for why a dict field: under --proc the Oracle that ran
    # a path lived in a worker and never existed in this process).
    #
    # Path t's own Oracle stream is relative to `orc_root + t*ISP_STRIDE`
    # (get_testsolve_prnstreams's own construction); since
    # ISP_STRIDE == ISP_STREAM_SPAN*ITER_STRIDE exactly, path t's own
    # (oracle_stream, oracle_offset) composes additively into the shared
    # root's own stream units: t*ISP_STREAM_SPAN + oracle_stream,
    # oracle_offset unchanged -- the same composition Oracle.get_endseed()
    # itself relies on, one level up. Reduces to exactly the same flat
    # value the pre-split code computed (t*ISP_STRIDE + oracle_flat), so
    # this is a relabeling here too, not new arithmetic.
    #
    # The "+1 with carry" (base.one_past) happens once, at the very end,
    # against the *winning* path's own raw oracle_stream/family capacity
    # -- not against the combined value -- for the same reason
    # Oracle.get_endseed() itself carries against its own local stream:
    # the family boundary (ISP_ITER_MARGIN in the default zone,
    # ISP_STREAM_SPAN in the sync zone) is a property of that one Oracle's own coordinate space, not
    # of the combined isp-relative value.
    touches = []
    for t in range(isp):
        hwm = res[t]['oracle_high_water_mark']
        if hwm is None:
            continue
        oracle_stream, oracle_offset = hwm
        touches.append((t * backend.ISP_STREAM_SPAN + oracle_stream, oracle_offset, t, oracle_stream))
    if not touches:
        endseed = orc_root
    else:
        _, offset, t, oracle_stream = max(touches)
        family_capacity = backend.ISP_ITER_MARGIN if oracle_stream < backend.SYNC_ZONE_STREAM_START else backend.ISP_STREAM_SPAN
        carried_stream, carried_offset = one_past(
            oracle_stream, offset, offset_capacity=backend.OFFSET_CAPACITY, stream_family_capacity=family_capacity
        )
        overall_stream = t * backend.ISP_STREAM_SPAN + carried_stream
        endseed = backend.stream_at(orc_root, overall_stream, carried_offset).get_seed()
    return res, endseed


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
    sprn = kwargs.get('sprn')
    solver = boovsolver(orc, **kwargs)
    mydat = solver.solve(budget)
    # The solver role's own boundary (KNOWN_ISSUES.md issue 10): checked
    # here, where the path ran -- under --proc that is a worker process,
    # and the stream's count never reaches the parent.
    if sprn is not None and getattr(orc, '_backend_name', None) is not None:
        check_role_draws(sprn, orc._backend, 'solver')
    return mydat


@dataclass(frozen=True)
class PathJob:
    """
    One independent sample path of a testsolve() run, as data: enough
    for any process that has the tester and solver classes to run it
    and get the same result.

    Attributes
    ----------
    path : int
        The path's index. With `seed` it fixes the path's oracle and
        solver streams (get_path_prnstreams).
    x0 : tuple of int
    budget : int
    seed : tuple of int
        The run's starting seed, not the path's.
    generator : str
        A registered generator name.
    crn : bool
    params : tuple of (str, float)
        Solver parameters.
    """
    path: int
    x0: tuple
    budget: int
    seed: tuple
    generator: str
    crn: bool
    params: tuple = ()


def run_path(state, job):
    """
    Run one sample path. Called in the process that runs the path: a
    pool worker, or the caller's own when there is one process.

    Parameters
    ----------
    state : (tester instance, solver class)
    job : PathJob

    Returns
    -------
    dict
        Output of a 'chnbase.MOSOSolver.solve' call
    """
    tester, solver = state
    backend = registry.get_generator(job.generator)
    orcstream, solvstream = get_path_prnstreams(job.path, job.seed, backend)
    orc = tester.ranorc(orcstream)
    orc.set_crnflag(job.crn)
    paramargs = dict([('solvprn', solvstream), ('x0', job.x0)] + list(job.params))
    with orc.set_simpar(1):
        return isp_run(solver, job.budget, orc, **paramargs)


def _open_path_worker(tester_ref, solver_ref):
    """A path worker's state: the tester, instantiated once, and the
    solver class -- each rebuilt from its transportable form."""
    return tester_ref.load()(), solver_ref.load()


def run_paths(tester, solver, jobs, num_proc=1, tester_instance=None, backend=None):
    """
    Run sample paths, `num_proc` at a time.

    With `num_proc` of 1 the paths run in this process, one after
    another, and no worker process exists. Above 1 they run on a
    pool from `backend` (`pool.WorkerPool` by default), one task per
    path; the tester and solver
    classes are sent to each worker once (`executor.ClassRef` -- so a
    class loaded from a user-supplied file travels as a source bundle,
    under every start method), and each task is a `PathJob`.

    Parameters
    ----------
    tester : class
    solver : chnbase.MOSOSolver class
    jobs : list of PathJob
    num_proc : int
        Number of processes to use in parallel. Default is 1.
    tester_instance : object or None
        An existing instance of `tester` to use when running in this
        process.
    backend : backend or None
        Where the worker processes are (`pool.LocalBackend` describes
        what a backend is). Defaults to this machine. A remote backend
        is sent every path as a task, whatever `num_proc` is.

    Returns
    -------
    runtots : dict
        Contains the results of every chnbase.MOSOSOlver.solve call,
        keyed by position in `jobs`.

    Raises
    ------
    ValueError
        `num_proc` is above 1 and `tester` or `solver` cannot be sent
        to a worker process (executor.ClassRef).
    """
    if backend is None:
        backend = LocalBackend()
    workers = len(jobs) if backend.remote else min(num_proc, len(jobs))
    if workers <= 1 and not (backend.remote and jobs):
        state = (tester_instance if tester_instance is not None else tester(), solver)
        return combine_runs([run_path(state, job) for job in jobs])
    refs = (ClassRef(tester, remote=backend.remote), ClassRef(solver, remote=backend.remote))
    with backend.pool(workers, _open_path_worker, refs) as pool:
        return combine_runs(pool.run([(run_path, (job,)) for job in jobs]))


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


def _open_metric_worker(tester_ref):
    return tester_ref.load()()


def _metric_task(tester, rundat):
    return gen_metric(rundat, tester)


def par_diff(rundata, tester, num_proc, backend=None):
    """
    Compute metrics, `num_proc` sample paths at a time.

    With `num_proc` of 1 they are computed in this process, each from
    a copy of its path's data (a `metric` may consume the sets it is
    given). Above 1 they run on a pool from `backend`
    (`pool.WorkerPool` by default); each worker builds its own
    instance of the tester's class.

    Parameters
    ----------
    rundat : dict
        Ouput of a chnbase.MOSOSolver.solve call
    tester
        Instantiated object such that 'tester.metric' is callable
    num_proc : int
        Number of processes to use
    backend : backend or None
        Where the worker processes are (`pool.LocalBackend` describes
        what a backend is). Defaults to this machine. A remote backend
        is sent every path's metrics as a task, whatever `num_proc`
        is.

    Returns
    -------
    hddict : dict
        keys are the isp number and values are the metric data
    """
    num_isp = len(rundata)
    if backend is None:
        backend = LocalBackend()
    workers = num_isp if backend.remote else min(num_proc, num_isp)
    if workers <= 1 and not (backend.remote and num_isp):
        return {i: gen_metric(copy.deepcopy(rundata[i]), tester) for i in range(num_isp)}
    with backend.pool(workers, _open_metric_worker, (ClassRef(type(tester), remote=backend.remote),)) as pool:
        metrics = pool.run([(_metric_task, (rundata[i],)) for i in range(num_isp)])
    return dict(enumerate(metrics))
