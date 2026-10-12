"""
testsolve()'s stream layout: the x0, solver and oracle roles live in
separate, bounded zones, and no path's streams depend on how many paths
were requested.

Two distinct defects, both observed failing here before the fix
(KNOWN_ISSUES.md issue 10):

1. Seed sharing. The oracle role's root was whatever the last solver
   stream's seed happened to be, so path 0's oracle stream and the last
   path's solver stream started at the same position -- with --isp=1,
   the same path's own solver and oracle.

2. Dependence on --isp. That root sat at stream `isp`, so every path's
   oracle streams moved when the number of paths changed. Extending a
   study from 100 sample paths to 200 changed the results of the first
   100.
"""
import pytest

from pymoso import chnutils
from pymoso.chnutils import get_testsolve_prnstreams, testsolve
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.prng import base as prng_base
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

ALL_BACKENDS = [mrg32k3a, mrg31k3p, philox4x32]
IDS = [b.__name__.rsplit(".", 1)[-1] for b in ALL_BACKENDS]
backends = pytest.mark.parametrize("backend", ALL_BACKENDS, ids=IDS)


def _first_draws(backend, isp):
    """The first value each role's stream produces, for a fresh layout:
    equal exactly when two streams start at the same position."""
    orcs, sols, xprn, _next, _root = get_testsolve_prnstreams(isp, backend.DEFAULT_SEED, backend)
    return {
        "x0": xprn.random(),
        "solver": [s.random() for s in sols],
        "oracle": [prng_base.ensure_random_compatible(o).random() for o in orcs],
    }


# ---------------------------------------------------------------------------
# 1. Seed sharing
# ---------------------------------------------------------------------------

@backends
@pytest.mark.parametrize("isp", [1, 2, 5])
def test_no_two_role_streams_start_at_the_same_position(backend, isp):
    d = _first_draws(backend, isp)
    everything = [d["x0"]] + d["solver"] + d["oracle"]
    assert len(set(everything)) == len(everything) == 1 + 2 * isp


@backends
def test_single_path_solver_and_oracle_do_not_share_a_seed(backend):
    """The default --isp=1 case: one path, whose own solver and oracle
    streams used to be the same stream."""
    d = _first_draws(backend, 1)
    assert d["solver"][0] != d["oracle"][0]


# ---------------------------------------------------------------------------
# 2. Dependence on --isp
# ---------------------------------------------------------------------------

@backends
def test_a_paths_streams_do_not_depend_on_how_many_paths_were_requested(backend):
    small = _first_draws(backend, 2)
    large = _first_draws(backend, 5)
    assert large["x0"] == small["x0"]
    assert large["solver"][:2] == small["solver"]
    assert large["oracle"][:2] == small["oracle"]


def test_extending_a_study_leaves_the_existing_paths_results_unchanged():
    """End to end, the way testsolve() is actually used: run 2 sample
    paths, then run 3. The first two must be the same runs."""
    kwargs = dict(budget=300, seed=(12345,) * 6, crn=False, proc=1)
    two, _ = testsolve(TPATester, RPERLE, (40, 40), isp=2, **kwargs)
    three, _ = testsolve(TPATester, RPERLE, (40, 40), isp=3, **kwargs)
    for t in range(2):
        assert three[t]['itersoln'] == two[t]['itersoln']
        assert three[t]['simcalls'] == two[t]['simcalls']
        assert three[t]['oracle_high_water_mark'] == two[t]['oracle_high_water_mark']


# ---------------------------------------------------------------------------
# The zones, stated directly
# ---------------------------------------------------------------------------

@backends
def test_roles_sit_in_their_own_zones(backend):
    """Slot 0 holds x0 (stream 0) and the solver streams (1 + t); oracle
    path t owns slot t + 1."""
    isp = 3
    orcs, sols, xprn, next_seed, orc_root = get_testsolve_prnstreams(isp, backend.DEFAULT_SEED, backend)
    seed = backend.DEFAULT_SEED
    span = backend.ISP_STREAM_SPAN

    def at(stream):
        return backend.stream_at(seed, stream, 0)

    def first(stream_obj):
        return prng_base.ensure_random_compatible(stream_obj).random()

    assert xprn.random() == first(at(0))
    assert [s.random() for s in sols] == [first(at(1 + t)) for t in range(isp)]
    assert [first(o) for o in orcs] == [first(at((t + 1) * span)) for t in range(isp)]
    assert orc_root == at(span).root_seed()
    assert next_seed == at((isp + 1) * span).root_seed()


# ---------------------------------------------------------------------------
# Boundaries raise, at setup, before anything runs
# ---------------------------------------------------------------------------

@backends
def test_more_paths_than_the_layout_holds_raises_immediately(backend):
    assert backend.ISP_MAX_PATHS >= 10_000
    get_testsolve_prnstreams(3, backend.DEFAULT_SEED, backend)          # ordinary
    with pytest.raises(prng_base.IspOverflow):
        get_testsolve_prnstreams(backend.ISP_MAX_PATHS + 1, backend.DEFAULT_SEED, backend)


@backends
def test_isp_ceiling_is_what_the_slot_grid_and_the_generator_allow(backend):
    """Two limits: slot 0 has ISP_STREAM_SPAN - 1 solver streams, and
    slots 1..isp must fit in the streams the generator can address."""
    by_solver_zone = backend.ISP_STREAM_SPAN - 1
    by_generator = backend.STREAM_CAPACITY // backend.ISP_STREAM_SPAN - 1
    assert backend.ISP_MAX_PATHS == min(by_solver_zone, by_generator)


def test_mrg31k3p_has_the_tightest_path_ceiling_of_the_three():
    """Its period (~2**185, against MRG32k3a's ~2**191) is what bounds
    the layout: just under 2**26 slots."""
    assert mrg31k3p.ISP_MAX_PATHS < mrg32k3a.ISP_MAX_PATHS
    assert mrg31k3p.ISP_MAX_PATHS < philox4x32.ISP_MAX_PATHS
    assert 2 ** 25 < mrg31k3p.ISP_MAX_PATHS < 2 ** 26


class _OverdrawnStream:
    """Stands in for a solver stream that reports having drawn more
    than one whole stream holds."""

    def __init__(self, count):
        self._count = count

    def raw_consumed(self):
        return self._count


@backends
def test_a_role_stream_that_overran_its_stream_raises(backend):
    chnutils.check_role_draws(_OverdrawnStream(backend.OFFSET_CAPACITY), backend, 'solver')   # exactly full: fine
    with pytest.raises(prng_base.RoleDrawOverflow):
        chnutils.check_role_draws(_OverdrawnStream(backend.OFFSET_CAPACITY + 1), backend, 'solver')


def test_role_draw_check_runs_at_the_end_of_a_real_path(monkeypatch):
    """isp_run checks its solver stream when the solver returns."""
    seen = []
    real = chnutils.check_role_draws
    monkeypatch.setattr(chnutils, 'check_role_draws', lambda *a: (seen.append(a[2]), real(*a))[1])
    from pymoso.chnutils import solve
    from pymoso.problems.probtpa import ProbTPA
    solve(ProbTPA, RPERLE, (40, 40), budget=200, seed=(12345,) * 6)
    assert seen == ['solver']
