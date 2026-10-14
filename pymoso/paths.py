#!/usr/bin/env python
"""
Run sample paths, and compute metrics on them, in this process or on
a pool.

A path of `testsolve` is described as data (`PathJob`) and built where
it runs. The functions a pool is handed -- `run_path`, `_metric_task`
and the two that open a worker -- travel to it as this module's name
and their own: renaming or moving one changes what a worker has to
import, and the pool tests run under every start method for that
reason. `pymoso.chnutils` offers the public ones under its own name.

Listing
--------------
combine_runs
isp_run
PathJob
run_path
run_paths
gen_metric
par_diff
"""
import copy
from dataclasses import dataclass
from .executor import ClassRef
from .layout import get_path_prnstreams, check_role_draws
from .pool import LocalBackend
from .prng import registry


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
    # testsolve() combines every path's high-water mark into the run's
    # end seed. The README's contract for a MOSOSolver's results names
    # three keys and not this one; the oracle the solver was handed
    # knows it, so a solver need not report it.
    mydat.setdefault('oracle_high_water_mark', orc.get_high_water_mark())
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
