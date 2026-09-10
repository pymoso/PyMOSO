"""
Portable correctness assertions for --simpar/--proc dispatch, run
against problems.probexpensive.ProbExpensiveModerate (see
test_expensive_oracle.py) so dispatch overhead doesn't dominate what's
being measured -- everything else in the suite is cheap enough that it
would.

Absolute timings are deliberately NOT asserted anywhere in this file
(see docs/parallel-dispatch-baseline.md for those, captured outside the
test suite as a committed artifact). What's asserted instead:

- total simulation calls identical regardless of worker count
- results identical across worker counts, fixed seed
- number of jobs dispatched -- the direct measure of batching. Today
  that's 1 job per replication for --simpar (chnbase.Oracle.hit's
  parallel branch puts one (x, seed) per replication onto req_q) and 1
  job per independent sample path for --proc (chnutils.par_runs calls
  apply_async once per joblist entry, and joblist has exactly `isp`
  entries) -- confirmed empirically below, not just read off the
  source, so this is a real "before" number for the executor rework to
  diff against.
- one loose ratio guard (parallel wall time vs. serial) to catch a
  pathological regression -- generous enough to survive a shared,
  possibly-contended CI runner; this is not a performance claim.

Job counts are instrumented by monkeypatching the same constructor
production code calls (chnbase.Queue, chnutils.mp.Pool) rather than
guessing from source, the same swap-the-constructor pattern
tests/test_rng_consumption.py uses for RecordingMRG32k3a. A naive
composition-wrapper wound up not being safe to use for the Queue side
of that -- see make_counting_queue's docstring for why (it hung under
the 'forkserver' start method) -- hence the module-level timeout below,
matching test_simpar_worker_lifecycle.py/test_multifile_transport.py's
existing convention of bounding tests that touch multiprocessing so a
regression fails fast instead of hanging CI.
"""
import time

import pytest

from pymoso import chnbase as chnbase_module
from pymoso import chnutils as chnutils_module
from pymoso.chnutils import get_solv_prnstreams, isp_run, testsolve
from pymoso.prng import mrg32k3a as mrg32k3a_backend
from pymoso.problems.probexpensive import ProbExpensiveModerate
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.expensivetester import ExpensiveTester

pytestmark = pytest.mark.timeout(90)

SEED = (12345,) * 6
X0 = (50,)
BUDGET = 100


def run_solve(simpar, budget=BUDGET, seed=SEED):
    """
    Like chnutils.solve(), but via isp_run directly so the full resdict
    (simcalls, not just the final solution/endseed) is available to
    assert on.
    """
    orcstream, solvstream = get_solv_prnstreams(seed, mrg32k3a_backend)
    orc = ProbExpensiveModerate(orcstream)
    orc.set_crnflag(False)
    with orc.set_simpar(simpar):
        res = isp_run(RSPLINE, budget, orc, sprn=solvstream, x0=X0)
    lastnu = max(res['itersoln'])
    return res['itersoln'][lastnu], res['simcalls'][lastnu], res['endseed']


def make_counting_queue(counter, real_queue_factory, *args, **kwargs):
    """
    Build a real multiprocessing Queue (not a wrapper class) and rebind
    its .put instance attribute to count calls before delegating.

    This has to be the genuine Queue object, not a composition wrapper:
    chnbase.Oracle.set_simpar hands req_q/res_q to Process(...,
    args=(self.req_q, self.res_q, ...)), and under the 'forkserver'
    start method (3.14's default, unlike 'fork' on 3.10-3.13) those
    args cross a real pickling boundary. Queue has its own registered
    reducer for that; an arbitrary user-defined wrapper class holding a
    Queue by composition does not, and hangs rather than erroring
    cleanly. The instance-level .put override only needs to be visible
    parent-side anyway: chnbase.py's Oracle.hit() calls req_q.put()
    from the caller's own process, never from inside a worker (only
    .get() runs there), so it doesn't matter that the override wouldn't
    survive being unpickled into a worker.
    """
    q = real_queue_factory(*args, **kwargs)
    real_put = q.put

    def counting_put(*a, **kw):
        counter['n'] += 1
        return real_put(*a, **kw)

    q.put = counting_put
    return q


class CountingPool:
    """
    Wraps a real multiprocessing Pool, counting .apply_async() calls --
    one per independent sample path dispatched by --proc. Unlike
    req_q/res_q above, a Pool object itself is never handed to a
    Process as an arg -- chnutils.par_runs creates and uses it entirely
    parent-side (Pool manages its own worker processes internally) -- so
    it never crosses a pickling boundary and a composition wrapper is
    fine here.
    """

    def __init__(self, counter, real_pool_factory, *args, **kwargs):
        self._pool = real_pool_factory(*args, **kwargs)
        self._counter = counter

    def apply_async(self, *args, **kwargs):
        self._counter['n'] += 1
        return self._pool.apply_async(*args, **kwargs)

    def __enter__(self):
        self._pool.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self._pool.__exit__(*exc_info)

    def __getattr__(self, name):
        return getattr(self._pool, name)


@pytest.fixture
def count_simpar_jobs(monkeypatch):
    counter = {'n': 0}
    real_queue_factory = chnbase_module.Queue
    monkeypatch.setattr(
        chnbase_module, 'Queue',
        lambda *a, **kw: make_counting_queue(counter, real_queue_factory, *a, **kw),
    )
    return counter


@pytest.fixture
def count_proc_jobs(monkeypatch):
    counter = {'n': 0}
    real_pool_factory = chnutils_module.mp.Pool
    monkeypatch.setattr(
        chnutils_module.mp, 'Pool',
        lambda *a, **kw: CountingPool(counter, real_pool_factory, *a, **kw),
    )
    return counter


# ---------------------------------------------------------------------------
# --simpar (solve()): num_calls, results, and job counts across worker counts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("simpar", [1, 2, 4])
def test_simpar_num_calls_and_results_match_serial(simpar):
    serial_soln, serial_calls, serial_endseed = run_solve(simpar=1)
    soln, calls, endseed = run_solve(simpar=simpar)
    assert calls == serial_calls, "total simulation calls must not depend on worker count"
    assert soln == serial_soln
    assert endseed == serial_endseed


@pytest.mark.parametrize("simpar", [2, 4])
def test_simpar_dispatches_one_job_per_replication(simpar, count_simpar_jobs):
    _, calls, _ = run_solve(simpar=simpar)
    assert count_simpar_jobs['n'] == calls, (
        f"--simpar dispatched {count_simpar_jobs['n']} jobs for {calls} simulation calls -- "
        "expected exactly one job per replication (today's unbatched dispatch; "
        "see docs/upstream-simpar.md)."
    )


# ---------------------------------------------------------------------------
# --proc (testsolve()): num_calls, results, and job counts across worker counts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("proc", [1, 2])
def test_proc_num_calls_and_results_match_serial(proc):
    kwargs = dict(budget=BUDGET, seed=SEED, isp=2, crn=False)
    serial_res, serial_endseed = testsolve(ExpensiveTester, RSPLINE, X0, proc=1, **kwargs)
    res, endseed = testsolve(ExpensiveTester, RSPLINE, X0, proc=proc, **kwargs)
    for path in serial_res:
        serial_lastnu = max(serial_res[path]['simcalls'])
        lastnu = max(res[path]['simcalls'])
        assert res[path]['simcalls'][lastnu] == serial_res[path]['simcalls'][serial_lastnu]
    assert res == serial_res
    assert endseed == serial_endseed


@pytest.mark.parametrize("proc", [1, 2])
def test_proc_dispatches_one_job_per_independent_sample_path(proc, count_proc_jobs):
    isp = 3
    testsolve(ExpensiveTester, RSPLINE, X0, budget=BUDGET, seed=SEED, isp=isp, proc=proc, crn=False)
    assert count_proc_jobs['n'] == isp, (
        f"--proc dispatched {count_proc_jobs['n']} jobs for isp={isp} -- expected exactly "
        "one job per independent sample path, regardless of proc (today's dispatch "
        "granularity; chnutils.par_runs)."
    )


# ---------------------------------------------------------------------------
# Loose pathological-regression guard -- not a performance claim. See
# docs/parallel-dispatch-baseline.md for actual timings.
# ---------------------------------------------------------------------------

MAX_PARALLEL_TO_SERIAL_RATIO = 15


def test_simpar_is_not_pathologically_slower_than_serial():
    budget = 200
    t0 = time.perf_counter()
    run_solve(simpar=1, budget=budget)
    serial_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    run_solve(simpar=4, budget=budget)
    parallel_time = time.perf_counter() - t0

    assert parallel_time < MAX_PARALLEL_TO_SERIAL_RATIO * serial_time, (
        f"--simpar=4 took {parallel_time:.2f}s vs. {serial_time:.2f}s serial -- "
        f"more than {MAX_PARALLEL_TO_SERIAL_RATIO}x slower suggests dispatch is "
        "badly broken, not just imperfectly batched (KNOWN_ISSUES.md notes ~2x "
        "slower than serial at a CHEAP oracle; this is an expensive one)."
    )
