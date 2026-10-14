"""
The backend seam: where pooled work runs is chosen by one object, a
*backend* (`pool.LocalBackend` describes the protocol), and all three
users of a pool -- replication blocks (`--simpar`), sample paths
(`--proc`) and metric computation -- get their pool from it.

These tests use a backend that records what it is asked for and
otherwise is the local one, so they show the seam is the only route to
a pool and that going through it changes no result. A backend that
really runs work somewhere else is tested with that backend.
"""
import multiprocessing

import pytest

from pymoso import executor, paths
from pymoso.chnutils import par_diff, solve, testsolve
from pymoso.pool import LocalBackend, WorkerPool
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

pytestmark = pytest.mark.timeout(120)

SEED = (12345,) * 6
START_METHODS = multiprocessing.get_all_start_methods()


class RecordingPool:
    def __init__(self, pool, record):
        self._pool = pool
        self._record = record

    def open(self):
        self._pool.open()
        return self

    def run(self, tasks):
        tasks = list(tasks)
        self._record['tasks'].append(len(tasks))
        return self._pool.run(tasks)

    def close(self):
        self._pool.close()

    def __enter__(self):
        self._pool.__enter__()
        return self

    def __exit__(self, *exc):
        return self._pool.__exit__(*exc)


class RecordingBackend(LocalBackend):
    """The local backend, noting every pool it hands out."""

    def __init__(self, context=None):
        super().__init__(context)
        self.pools = []

    def pool(self, workers, initializer=None, initargs=()):
        record = {'workers': workers, 'initializer': initializer, 'tasks': []}
        self.pools.append(record)
        return RecordingPool(super().pool(workers, initializer, initargs), record)


def test_the_local_backend_hands_out_worker_pools():
    backend = LocalBackend()
    assert backend.remote is False
    pool = backend.pool(2)
    assert isinstance(pool, WorkerPool) and pool.workers == 2


@pytest.mark.parametrize("method", START_METHODS)
def test_solve_gets_its_simpar_pool_from_the_backend(method):
    backend = RecordingBackend(multiprocessing.get_context(method))
    kwargs = dict(budget=400, seed=SEED)
    expected = solve(ProbTPA, RPERLE, (40, 40), **kwargs)
    assert solve(ProbTPA, RPERLE, (40, 40), simpar=2, backend=backend, **kwargs) == expected
    assert len(backend.pools) == 1
    record = backend.pools[0]
    assert record['workers'] == 2 and record['initializer'] is executor._open_worker_executor
    assert record['tasks'] and max(record['tasks']) <= 2        # every executor call, cut into at most two pieces


@pytest.mark.parametrize("method", START_METHODS)
def test_testsolve_gets_its_path_pool_from_the_backend(method):
    backend = RecordingBackend(multiprocessing.get_context(method))
    kwargs = dict(budget=200, seed=SEED, isp=3)
    expected = testsolve(TPATester, RPERLE, (40, 40), **kwargs)
    assert testsolve(TPATester, RPERLE, (40, 40), proc=2, backend=backend, **kwargs) == expected
    assert [(r['workers'], r['initializer'], r['tasks']) for r in backend.pools] == [(2, paths._open_path_worker, [3])]


@pytest.mark.parametrize("method", START_METHODS)
def test_par_diff_gets_its_metric_pool_from_the_backend(method):
    backend = RecordingBackend(multiprocessing.get_context(method))
    res, _ = testsolve(TPATester, RPERLE, (40, 40), budget=200, seed=SEED, isp=3)
    tester = TPATester()
    expected = par_diff(res, tester, 1)
    assert par_diff(res, tester, 2, backend=backend) == expected
    assert [(r['workers'], r['initializer'], r['tasks']) for r in backend.pools] == [(2, paths._open_metric_worker, [3])]


def test_a_local_backend_is_not_asked_for_a_pool_when_one_process_will_do():
    backend = RecordingBackend()
    solve(ProbTPA, RPERLE, (40, 40), budget=200, seed=SEED, simpar=1, backend=backend)
    res, _ = testsolve(TPATester, RPERLE, (40, 40), budget=200, seed=SEED, isp=2, proc=1, backend=backend)
    par_diff(res, TPATester(), 1, backend=backend)
    assert backend.pools == []


def test_an_oracle_takes_a_backend_with_set_simpar():
    backend = RecordingBackend()
    orc = ProbTPA(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    orc.set_crnflag(False)
    serial = orc.hit((3, 4), 6)
    other = ProbTPA(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    other.set_crnflag(False)
    with other.set_simpar(3, backend=backend):
        assert other.hit((3, 4), 6) == serial
    assert [(r['workers'], r['tasks']) for r in backend.pools] == [(3, [3])]
