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

from itertools import product, filterfalse
from math import ceil, floor, sqrt
import copy
from dataclasses import dataclass
from statistics import mean, variance
from .executor import ClassRef
from .pool import LocalBackend
from .prng import registry
from .prng.base import one_past, ensure_random_compatible, IspOverflow, RoleDrawOverflow

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
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    ## generate all prn streams
    orcstream, solvstream = get_solv_prnstreams(seed, backend)
    ## generate the experiment list
    paramlst = [('solvprn', solvstream), ('x0', x0), ]
    orc = problem(orcstream)
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
    x0 : tuple of int
        Feasible starting point for the algorithms
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
    paramtups = []
    for i, p in enumerate(kwargs):
        ptup = (p, float(kwargs[p]))
        paramtups.append(ptup)
    x0stream, orc_root = _testsolve_roots(isp, seed, backend)
    currtest = tester()
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


def get_testsolve_prnstreams(num_trials, iseed, backend):
    """
    Create the set of random number stream generators with which to test
    a MOSO algorithm.

    Parameters
    ----------
    num_trials : int
        Number of independent sample paths of Oracles to test an
        algorithm
    iseed : tuple of int
        Starting seed from which to create the generators, in the
        selected `backend`'s own shape (§3.7)
    backend : module
        The selected generator's own module (registry.get_generator),
        §12 step 6b -- was hardcoded to pymoso.prng.mrg32k3a before
        this step.

    Returns
    -------
    orcprn_lst : list of Stream objects
        Unwrapped -- each becomes a path's own Oracle.rng, and
        Oracle.set_crnflag()'s own backend_for_stream lookup needs the
        real backend instance.
    solprn_lst : list of random.Random
        Each wrapped with ensure_random_compatible if not already one
        -- handed to a path's solver as `sprn`/`solvprn` (§3.6).
    xprn : random.Random
        Wrapped with ensure_random_compatible if not already one --
        handed to a tester's own get_ranx0(rng) (§3.6).
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
        (path t's own root is `stream_at(orc_root, t*ISP_STREAM_SPAN, 0)`,
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

    Layout, in whole streams from `iseed` (KNOWN_ISSUES.md issue 10):

    - slot 0, stream 0: the x0 stream;
    - slot 0, stream 1 + t: path t's solver stream;
    - slot t + 1: path t's oracle slot (ISP_STREAM_SPAN streams --
      iterations below ISP_ITER_MARGIN, the sync zone above).

    No role's streams depend on `num_trials`, so path t is the same run
    whether 10 paths are requested or 1,000. Each zone has a boundary
    that raises: `num_trials` past the generator's own ISP_MAX_PATHS
    (IspOverflow, here); a solver or x0 stream drawing more than one
    stream holds (RoleDrawOverflow, check_role_draws); and the oracle
    slot's own iteration/sync/replication limits (chnbase.py).

    Raises
    ------
    IspOverflow
    """
    # Checked before anything is built: past ISP_MAX_PATHS the solver
    # zone (slot 0) or the generator's own stream capacity is exhausted.
    if num_trials > backend.ISP_MAX_PATHS:
        raise IspOverflow(
            '{0} independent sample paths requested, but the stream '
            'layout holds at most {1} under {2}. See KNOWN_ISSUES.md '
            'issue 10.'.format(num_trials, backend.ISP_MAX_PATHS, registry.GENERATOR_NAMES[backend])
        )
    root = iseed
    span = backend.ISP_STREAM_SPAN
    # Slot 0, stream 0: the x0 role. ensure_random_compatible: xprn is
    # handed straight to a tester's own get_ranx0(rng) (§3.6, "an
    # rng-shaped object") -- every built-in tester's get_ranx0 calls
    # rng.choice(...), which a raw Philox stream doesn't have.
    xprn = ensure_random_compatible(backend.stream_at(root, 0, 0))
    # Slot 0, streams 1..num_trials: the solver role, one stream per
    # path. Built by stepping one stream at a time from the root (a
    # cached jump for the MRG family) -- the same positions
    # stream_at(root, 1 + t, 0) names, without a full jump from the root
    # per path. Each list entry is wrapped for solver code (MOCOMPASS/
    # MOPBnB's own sprn.sample(...) calls, §3.6); the chain itself uses
    # the unwrapped stream's root_seed().
    solprn_lst = []
    step_seed = root
    for t in range(num_trials):
        solprn = backend.stream_at(step_seed, 1, 0)
        step_seed = solprn.root_seed()
        solprn_lst.append(ensure_random_compatible(solprn))
    # Slots 1..num_trials: the oracle role, path t in slot t + 1. Its
    # root is a fixed position -- the start of slot 1 -- not "wherever
    # the last solver stream ended up", which is what made path 0's
    # oracle stream coincide with the last path's solver stream, and
    # what made every path's oracle streams move whenever num_trials
    # changed (KNOWN_ISSUES.md issue 10, both parts).
    orc_root = backend.stream_at(root, span, 0).root_seed()
    orcprn_lst = [backend.stream_at(orc_root, t * span, 0) for t in range(num_trials)]
    # The next independent stream past every path actually reserved:
    # the start of the slot path `num_trials` would own.
    iseed = backend.stream_at(orc_root, num_trials * span, 0).root_seed()
    return orcprn_lst, solprn_lst, xprn, iseed, orc_root


def _testsolve_roots(num_trials, iseed, backend):
    """
    What testsolve() itself needs from the stream layout
    (get_testsolve_prnstreams documents it): the x0 stream and the
    oracle role's root. Each path's own two streams are built where the
    path runs (get_path_prnstreams).

    Returns
    -------
    xprn : random.Random
    orc_root : tuple of int

    Raises
    ------
    IspOverflow
    """
    if num_trials > backend.ISP_MAX_PATHS:
        raise IspOverflow(
            '{0} independent sample paths requested, but the stream '
            'layout holds at most {1} under {2}. See KNOWN_ISSUES.md '
            'issue 10.'.format(num_trials, backend.ISP_MAX_PATHS, registry.GENERATOR_NAMES[backend])
        )
    xprn = ensure_random_compatible(backend.stream_at(iseed, 0, 0))
    orc_root = backend.stream_at(iseed, backend.ISP_STREAM_SPAN, 0).root_seed()
    return xprn, orc_root


def get_path_prnstreams(path, iseed, backend):
    """
    One sample path's two streams, computed from the run's seed and the
    path's index alone -- the same streams get_testsolve_prnstreams
    returns at that index, whatever the number of paths
    (tests/test_path_jobs.py holds the two together). This is what lets
    a worker process be told "path 5" rather than be sent path 5's
    live, seeded objects.

    Parameters
    ----------
    path : int
        Non-negative.
    iseed : tuple of int
        The run's starting seed, in the selected `backend`'s own shape.
    backend : module

    Returns
    -------
    orcstream : Stream object
        Unwrapped; becomes the path's Oracle.rng.
    solvstream : random.Random
        Handed to the path's solver.
    """
    orc_root = backend.stream_at(iseed, backend.ISP_STREAM_SPAN, 0).root_seed()
    orcstream = backend.stream_at(orc_root, path * backend.ISP_STREAM_SPAN, 0)
    solvstream = ensure_random_compatible(backend.stream_at(iseed, 1 + path, 0))
    return orcstream, solvstream


def get_solv_prnstreams(iseed, backend):
    """
    Create a random number stream for the algorithm to use and an
    independent one to do simulations.

    Parameters
    ----------
    iseed : tuple of int
        Starting seed to create the generators, in the selected
        `backend`'s own shape (§3.7)
    backend : module
        The selected generator's own module (registry.get_generator),
        §12 step 6b -- was hardcoded to pymoso.prng.mrg32k3a before
        this step.

    Returns
    -------
    orcstream : Stream object
        Unwrapped -- becomes the Oracle's own `self.rng`, and
        Oracle.set_crnflag()'s own backend_for_stream lookup needs the
        real backend instance, not an adapter.
    solvstream : random.Random
        Wrapped with ensure_random_compatible if the backend's own
        Stream isn't already one -- handed to the solver as `sprn`/
        `solvprn`, documented only as "an rng-shaped object" (§3.6);
        MOCOMPASS/MOPBnB's own `self.sprn.sample(...)` calls need the
        full surface, which a raw Philox stream doesn't have.
    """
    # §12 step 6b: stream_at(iseed, 0, 0)/stream_at(iseed, 1, 0), not
    # backend.MRG32k3a(iseed)/backend.get_next_prnstream(iseed) --
    # identical for the MRG family (confirmed directly: stream_at(seed,
    # 0, 0) == the class constructed directly on that seed, and
    # stream_at(seed, 1, 0) == get_next_prnstream(seed)), and stream_at
    # is the one operation every backend actually has (Philox has
    # neither a raw-seed constructor nor get_next_prnstream/jump-ahead
    # at all).
    solvstream = ensure_random_compatible(backend.stream_at(iseed, 0, 0))
    orcstream = backend.stream_at(iseed, 1, 0)
    return orcstream, solvstream


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


def check_role_draws(stream, backend, role):
    """
    Raise if a solver-role or x0-role stream drew more raw values than
    one stream holds -- that role's own zone boundary.

    Parameters
    ----------
    stream : object
        The stream the role drew from. Anything without a
        `raw_consumed()` method (a caller's own rng-shaped object) is
        not checked.
    backend : module
        The selected generator's own module.
    role : str
        'solver' or 'x0', for the message.

    Raises
    ------
    RoleDrawOverflow
    """
    raw_consumed = getattr(stream, 'raw_consumed', None)
    if raw_consumed is None:
        return
    drawn = raw_consumed()
    if drawn > backend.OFFSET_CAPACITY:
        raise RoleDrawOverflow(
            'the {0} stream drew {1} raw values, more than the {2} one '
            'stream holds -- it overran its own stream. See '
            'KNOWN_ISSUES.md issue 10.'.format(role, drawn, backend.OFFSET_CAPACITY)
        )


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
        what a backend is). Defaults to this machine.

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
    workers = min(num_proc, len(jobs))
    if workers <= 1:
        state = (tester_instance if tester_instance is not None else tester(), solver)
        return combine_runs([run_path(state, job) for job in jobs])
    if backend is None:
        backend = LocalBackend()
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
        what a backend is). Defaults to this machine.

    Returns
    -------
    hddict : dict
        keys are the isp number and values are the metric data
    """
    num_isp = len(rundata)
    workers = min(num_proc, num_isp)
    if workers <= 1:
        return {i: gen_metric(copy.deepcopy(rundata[i]), tester) for i in range(num_isp)}
    if backend is None:
        backend = LocalBackend()
    with backend.pool(workers, _open_metric_worker, (ClassRef(type(tester), remote=backend.remote),)) as pool:
        metrics = pool.run([(_metric_task, (rundata[i],)) for i in range(num_isp)])
    return dict(enumerate(metrics))


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
