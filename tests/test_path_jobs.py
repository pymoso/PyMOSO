"""
A testsolve() sample path as data (chnutils.PathJob), and --proc on the
one worker pool (KNOWN_ISSUES.md issue 7's --proc half).

Closing that issue meant no longer sending a worker anything live. What
is sent instead -- a path's index, the run's seed, the generator's
name, the tester and solver classes -- has to rebuild exactly the path
the parent used to build, which is what these tests hold down.
"""
import multiprocessing
import pickle
import sys

import pytest

from pymoso import chnutils
from pymoso.chnutils import (
    PathJob, get_path_prnstreams, get_testsolve_prnstreams, par_diff, run_path, run_paths, testsolve,
)
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.expensivetester import ExpensiveTester
from pymoso.testers.tpatester import TPATester

pytestmark = pytest.mark.timeout(120)

ALL = [("mrg32k3a", mrg32k3a), ("mrg31k3p", mrg31k3p), ("philox4x32", philox4x32)]
generators = pytest.mark.parametrize("name,backend", ALL, ids=[n for n, _ in ALL])


@generators
def test_a_paths_streams_are_a_function_of_seed_and_index_alone(name, backend):
    """get_path_prnstreams(t) is get_testsolve_prnstreams(n)[t] for any
    n: same oracle stream, same oracle root, same solver stream."""
    seed = backend.DEFAULT_SEED
    for num_trials in (1, 4):
        orcs, solvs, _x0, _next, _root = get_testsolve_prnstreams(num_trials, seed, backend)
        for t in range(num_trials):
            orc, solv = get_path_prnstreams(t, seed, backend)
            assert orc.get_seed() == orcs[t].get_seed()
            assert orc.root_seed() == orcs[t].root_seed()
            assert [solv.random() for _ in range(5)] == [solvs[t].random() for _ in range(5)]


def test_a_path_job_is_immutable_picklable_plain_data():
    job = PathJob(path=3, x0=(40, 40), budget=100, seed=(12345,) * 6, generator="mrg32k3a", crn=False,
                  params=(("betaeps", 0.4),))
    assert pickle.loads(pickle.dumps(job)) == job
    with pytest.raises(Exception):
        job.path = 4


@generators
@pytest.mark.parametrize("crn", [False, True])
def test_results_do_not_depend_on_the_number_of_processes(name, backend, crn):
    kwargs = dict(budget=300, seed=backend.DEFAULT_SEED, isp=3, crn=crn, generator=name, betaeps=0.4)
    serial = testsolve(TPATester, RPERLE, (40, 40), proc=1, **kwargs)
    assert testsolve(TPATester, RPERLE, (40, 40), proc=2, **kwargs) == serial
    assert testsolve(TPATester, RPERLE, (40, 40), proc=8, **kwargs) == serial


def test_random_starting_points_are_drawn_in_the_parent_in_path_order():
    kwargs = dict(budget=200, seed=(12345,) * 6, isp=3, crn=False, ranx0=True)
    serial = testsolve(TPATester, RPERLE, (0, 0), proc=1, **kwargs)
    assert testsolve(TPATester, RPERLE, (0, 0), proc=3, **kwargs) == serial
    starts = [next(iter(serial[0][t]['itersoln'][0])) for t in range(3)]
    assert len(set(starts)) == 3


def test_a_path_is_the_same_run_alone_or_among_others():
    """Path 2's job, run by itself in this process, is path 2 of a
    three-path run."""
    res, _ = testsolve(TPATester, RPERLE, (40, 40), budget=300, seed=(12345,) * 6, isp=3, proc=1, crn=False)
    job = PathJob(path=2, x0=(40, 40), budget=300, seed=(12345,) * 6, generator="mrg32k3a", crn=False)
    assert run_path((TPATester(), RPERLE), job) == res[2]


@pytest.mark.parametrize("method", multiprocessing.get_all_start_methods())
def test_paths_run_under_every_start_method(method, monkeypatch):
    kwargs = dict(budget=100, seed=(12345,) * 6, isp=2, crn=False)
    serial = testsolve(ExpensiveTester, RSPLINE, (50,), proc=1, **kwargs)
    monkeypatch.setattr(multiprocessing, "get_context", lambda m=None, _real=multiprocessing.get_context: _real(m or method))
    assert testsolve(ExpensiveTester, RSPLINE, (50,), proc=2, **kwargs) == serial


def test_an_exception_in_a_path_is_raised_in_the_caller():
    """An infeasible x0 is a ValueError from the solver. In a worker it
    used to depend on multiprocessing.Pool to come back; now it is the
    pool's own contract."""
    for proc in (1, 2):
        with pytest.raises(ValueError, match="infeasible"):
            testsolve(TPATester, RPERLE, (999, 999), budget=100, seed=(12345,) * 6, isp=2, proc=proc, crn=False)


def test_a_tester_that_cannot_be_transported_is_refused_only_when_it_would_have_to_be(monkeypatch):
    """A behaviour change, recorded: a tester defined where a worker
    cannot find it (here, inside a function; in practice a notebook
    cell) used to work with proc > 1 under the fork start method and
    nowhere else. Without cloudpickle it now raises under every start
    method, and still works with proc=1. With cloudpickle (the
    `notebook` extra) it travels by value:
    test_by_value_transport.py."""
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    class LocalTester(TPATester):
        pass

    kwargs = dict(budget=100, seed=(12345,) * 6, isp=2, crn=False)
    res, _ = testsolve(LocalTester, RPERLE, (40, 40), proc=1, **kwargs)
    assert len(res) == 2
    with pytest.raises(ValueError, match="cannot be sent to a worker process"):
        testsolve(LocalTester, RPERLE, (40, 40), proc=2, **kwargs)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_metrics_do_not_depend_on_the_number_of_processes_and_leave_the_results_alone():
    res, _ = testsolve(ExpensiveTester, RSPLINE, (50,), budget=100, seed=(12345,) * 6, isp=3, proc=1, crn=False)
    before = pickle.dumps(res)
    serial = par_diff(res, ExpensiveTester(), 1)
    # ExpensiveTester.metric pops from the set it is given: in one
    # process that must not reach the caller's results.
    assert pickle.dumps(res) == before
    assert par_diff(res, ExpensiveTester(), 3) == serial
    assert sorted(serial) == [0, 1, 2]


def test_run_paths_with_nothing_to_run():
    assert run_paths(TPATester, RPERLE, [], 4) == {}
