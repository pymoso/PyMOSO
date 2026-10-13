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
- how work is dispatched -- the direct measure of batching. Both
  features run on pymoso/pool.py's WorkerPool. --simpar divides each
  executor call's replications into at most `simpar` chunks, one task
  per chunk, and every replication is run exactly once; --proc sends
  one task per independent sample path, and with --proc=1 starts no
  worker process at all. (Before the pool these were one job per
  replication on a raw Queue, and one job per path on a
  multiprocessing.Pool that was used even at --proc=1.)
- one loose ratio guard (parallel wall time vs. serial) to catch a
  pathological regression -- generous enough to survive a shared,
  possibly-contended CI runner; this is not a performance claim.

Dispatch is observed by wrapping WorkerPool.run, which runs in the
calling process. The module-level timeout matches
test_simpar_worker_lifecycle.py/test_multifile_transport.py's
convention of bounding tests that touch multiprocessing so a
regression fails fast instead of hanging CI.
"""
import time

import pytest

from pymoso import pool as pool_module
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


@pytest.fixture
def pool_runs(monkeypatch):
    """Every WorkerPool.run call made during the test, as its list of
    tasks; and every pool opened, as its worker count."""
    seen = {'runs': [], 'opened': []}
    real_run = pool_module.WorkerPool.run
    real_open = pool_module.WorkerPool.open

    def run(self, tasks):
        tasks = list(tasks)
        seen['runs'].append(tasks)
        return real_run(self, tasks)

    def open_(self):
        seen['opened'].append(self.workers)
        return real_open(self)

    monkeypatch.setattr(pool_module.WorkerPool, 'run', run)
    monkeypatch.setattr(pool_module.WorkerPool, 'open', open_)
    return seen


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
def test_simpar_dispatches_at_most_one_chunk_per_worker_and_every_replication_once(simpar, pool_runs):
    _, calls, _ = run_solve(simpar=simpar)
    assert pool_runs['opened'] == [simpar]
    assert pool_runs['runs'], "nothing was dispatched to the pool"
    replications = 0
    for tasks in pool_runs['runs']:
        assert 1 <= len(tasks) <= simpar
        sizes = [sum(block.count for block in chunk) for _, (chunk,) in tasks]
        assert max(sizes) - min(sizes) <= 1, "chunks should be as even as the replication count allows"
        replications += sum(sizes)
    assert replications == calls


def test_simpar_1_starts_no_worker_process(pool_runs):
    run_solve(simpar=1)
    assert pool_runs == {'runs': [], 'opened': []}


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


@pytest.mark.parametrize("proc", [2, 3])
def test_proc_dispatches_one_task_per_independent_sample_path(proc, pool_runs):
    isp = 3
    testsolve(ExpensiveTester, RSPLINE, X0, budget=BUDGET, seed=SEED, isp=isp, proc=proc, crn=False)
    assert pool_runs['opened'] == [proc]
    assert [len(tasks) for tasks in pool_runs['runs']] == [isp]


def test_proc_1_starts_no_worker_process(pool_runs):
    """The serial path is serial: no pool, so none of a pool's failure
    modes (CLAUDE.md: --proc used a Pool even at --proc=1)."""
    testsolve(ExpensiveTester, RSPLINE, X0, budget=BUDGET, seed=SEED, isp=3, proc=1, crn=False)
    assert pool_runs == {'runs': [], 'opened': []}


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
