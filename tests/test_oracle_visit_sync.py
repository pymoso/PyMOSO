"""
docs/rng-interface-design.md §12 step 4a: Oracle.hit's opt-in `visit=`/
`sync=` parameters (§4.1/§4.3), and §7.1 items 11-12. Everything here
exercises the new, explicitly-invoked coordinate machinery directly --
nothing here is reachable through a default `hit(x, m)` call, and
tests/test_golden.py (unchanged, all 14 green) is the check that this
step didn't touch the default path at all.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import (
    MRG32k3a, jump_seed_n, ITER_STRIDE, REPL_STRIDE,
    ISP_STRIDE, ISP_ITER_MARGIN, SYNC_ROLE_OFFSET, SYNC_STRIDE,
)
from pymoso.prng.base import point_width, offset_within_iteration

ROOT = (12345, 12345, 12345, 12345, 12345, 12345)


class SeedRecordingOracle(Oracle):
    """g() returns the first seed component it was actually handed, as
    a float -- lets a test read back exactly which stream position g()
    drew from, without needing a real simulation. Same double as
    tests/test_oracle_coordinate_migration.py's, duplicated rather than
    imported so this file has no import-order dependency on that one."""

    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        super().__init__(rng)

    def g(self, x, rng):
        return True, (float(rng.get_seed()[0]),)


def _fresh_oracle(dim=1):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = SeedRecordingOracle(rng, dim=dim)
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


class LoggingOracle(Oracle):
    """Like SeedRecordingOracle, but also appends every individual g()
    call's seed to self.log -- needed to check *each* replication's
    coordinate within one multi-replication hit() call, since hit()
    itself only returns the mean across replications, not each one.
    Three separate m=1 hit() calls would not do: _hit_opt_in has no
    continuation tracking (deliberately, per §4.1 -- that's out of
    scope for this step), so each independent call recomputes
    replication 0, not 0/1/2 in sequence."""

    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        v = float(rng.get_seed()[0])
        self.log.append(v)
        return True, (v,)


def _fresh_logging_oracle(dim=1):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = LoggingOracle(rng, dim=dim)
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


# ---------------------------------------------------------------------------
# §7.1 item 11: no collision past the old MAX_RI ceiling
# ---------------------------------------------------------------------------

def test_iteration_and_replication_never_overflow_one_isp_stride_block():
    """The property that guarantees no collision between different isp
    values by construction: iteration*ITER_STRIDE + replication*
    REPL_STRIDE must stay strictly under ISP_STRIDE for every iteration
    ISP_ITER_MARGIN was sized to cover -- checked directly, not assumed,
    at the boundary and comfortably beyond the old MAX_RI=200."""
    max_replication = (1 << 32) - 1  # REPL_COUNT_BITS' own established headroom (base.py)
    for iteration in [0, 1, 200, 1_000, 1_000_000, ISP_ITER_MARGIN - 1]:
        remainder = iteration * ITER_STRIDE + max_replication * REPL_STRIDE
        assert remainder < ISP_STRIDE, f"iteration={iteration} overflows one ISP_STRIDE block"


def test_no_collision_between_isp_paths_at_iteration_counts_well_beyond_max_ri():
    """The positive replacement for what test_max_ri.py checked
    negatively (exceeding MAX_RI=200 raised): a direct battery of
    (isp, iteration, replication) coordinates, including iteration
    counts far past the old 200, asserted pairwise distinct across
    different isp values. No live dependency on get_testsolve_
    prnstreams -- this is the ISP_STRIDE-based formula those functions
    will use once step 4b wires it in (§6), exercised in isolation."""
    isp_values = [0, 1, 2, 100]
    iteration_values = [0, 1, 200, 201, 1_000, 1_000_000]
    replication_values = [0, 1, (1 << 32) - 1]

    def coordinate(isp, iteration, replication):
        return isp * ISP_STRIDE + iteration * ITER_STRIDE + replication * REPL_STRIDE

    seen = {}
    for isp in isp_values:
        for iteration in iteration_values:
            for replication in replication_values:
                c = coordinate(isp, iteration, replication)
                key = (isp, iteration, replication)
                for other_key, other_c in seen.items():
                    if other_key[0] != isp:
                        assert c != other_c, f"{key} collides with {other_key}"
                seen[key] = c


# ---------------------------------------------------------------------------
# §7.1 item 12: sync's coordinate space stays disjoint from the default's
# ---------------------------------------------------------------------------

def test_sync_role_offset_exceeds_any_default_path_coordinate():
    """The containment property that guarantees disjointness by
    construction (not merely making collision unlikely): the default
    path's own coordinate (isp*ISP_STRIDE + iteration*ITER_STRIDE +
    replication*REPL_STRIDE, isp omitted at step 4a -- deferred to 4b,
    see docs/rng-interface-design.md §12 step 4a's own note) never
    reaches SYNC_ROLE_OFFSET for any iteration/replication ISP_ITER_
    MARGIN/REPL_COUNT_BITS (base.py) were sized to cover."""
    max_replication = (1 << 32) - 1
    max_default_coordinate = (ISP_ITER_MARGIN - 1) * ITER_STRIDE + max_replication * REPL_STRIDE
    assert max_default_coordinate < SYNC_ROLE_OFFSET


def test_default_and_sync_coordinates_pairwise_distinct_across_a_battery():
    """Direct check, not just the containment property above: a battery
    of default-path coordinates (crn=True's own formula, and the crn=
    False target formula via offset_within_iteration) against a battery
    of sync-mode coordinates, asserted pairwise distinct."""
    W = point_width(2)

    default_coords = set()
    for iteration in [0, 1, 200, 1_000_000]:
        for replication in [0, 1, 41]:
            # crn=True's own formula
            default_coords.add(iteration * ITER_STRIDE + replication * REPL_STRIDE)
            # crn=False's target formula (offset_within_iteration)
            for x in [(0, 0), (5, 5), (-5, 5)]:
                for visit in [0, 1, 2]:
                    default_coords.add(
                        iteration * ITER_STRIDE + offset_within_iteration(x, visit, replication, W)
                    )

    sync_coords = set()
    for sync in [0, 1, 41, 10_000]:
        for replication in [0, 1, 41]:
            sync_coords.add(SYNC_ROLE_OFFSET + sync * SYNC_STRIDE + replication * REPL_STRIDE)

    assert default_coords.isdisjoint(sync_coords)


def test_two_points_same_sync_produce_identical_draws_for_every_replication_independent_of_order():
    """The specific property MOCOMPASS's port depends on (§4.3):
    two hit() calls for *different* x, same sync value, produce
    identical draws at every replication, independent of call order --
    the operational demonstration that computed coordinates give
    MOCOMPASS's intended cross-point sharing in full, which self.seeds
    never did beyond each checkpoint's first replication (§4.3,
    docs/mocompass-mopbnb-known-issues.md item 4)."""
    orc = _fresh_oracle(dim=2)
    isfeas_a, obs_a, se_a = orc.hit((1, 1), 4, sync=7)
    isfeas_b, obs_b, se_b = orc.hit((99, -3), 4, sync=7)
    assert obs_a == obs_b

    # reversed order, fresh Oracle: same result
    orc2 = _fresh_oracle(dim=2)
    isfeas_b2, obs_b2, se_b2 = orc2.hit((99, -3), 4, sync=7)
    isfeas_a2, obs_a2, se_a2 = orc2.hit((1, 1), 4, sync=7)
    assert obs_a2 == obs_a
    assert obs_b2 == obs_b


def test_sync_replications_match_the_formula_per_replication():
    """hit() only returns the mean/se, not each replication -- use
    LoggingOracle to check every individual replication's coordinate
    within one m=3 call, not just their mean."""
    orc = _fresh_logging_oracle(dim=1)
    isfeas, obs, se = orc.hit((5,), 3, sync=9)
    assert len(orc.log) == 3
    for r in range(3):
        expected = float(jump_seed_n(orc._orc_root, SYNC_ROLE_OFFSET + 9 * SYNC_STRIDE + r * REPL_STRIDE)[0])
        assert orc.log[r] == expected


def test_sync_and_nonzero_visit_together_raises():
    orc = _fresh_oracle(dim=1)
    with pytest.raises(ValueError):
        orc.hit((5,), 1, visit=1, sync=0)


def test_negative_sync_raises():
    orc = _fresh_oracle(dim=1)
    with pytest.raises(ValueError):
        orc.hit((5,), 1, sync=-1)


def test_negative_visit_raises():
    orc = _fresh_oracle(dim=1)
    with pytest.raises(ValueError):
        orc.hit((5,), 1, visit=-1)


# ---------------------------------------------------------------------------
# visit=: basic exactness (not named in items 11-12, but landed alongside
# sync in this step and deserves the same discipline as any other new,
# explicitly-invoked path -- CLAUDE.md's "no half-finished implementations").
# ---------------------------------------------------------------------------

def test_visit_matches_the_offset_within_iteration_formula():
    orc = _fresh_logging_oracle(dim=1)
    W = point_width(1)
    isfeas, obs, se = orc.hit((7,), 3, visit=2)
    assert len(orc.log) == 3
    for r in range(3):
        expected_coordinate = orc._iteration * ITER_STRIDE + offset_within_iteration((7,), 2, r, W)
        expected = float(jump_seed_n(orc._orc_root, expected_coordinate)[0])
        assert orc.log[r] == expected


def test_different_visits_for_the_same_point_do_not_collide():
    orc = _fresh_oracle(dim=1)
    isfeas0, obs0, se0 = orc.hit((7,), 1, visit=1)
    isfeas1, obs1, se1 = orc.hit((7,), 1, visit=2)
    assert obs0 != obs1


def test_visit_is_independent_of_which_point_or_call_order():
    """visit=k for point x is a pure function of (iteration, x, k,
    replication) -- calling it from a fresh Oracle at the same
    iteration reproduces the same draw, regardless of anything else
    that happened first."""
    orc_a = _fresh_oracle(dim=1)
    orc_a.hit((1,), 1)  # an unrelated default-path call first
    isfeas_a, obs_a, se_a = orc_a.hit((7,), 1, visit=3)

    orc_b = _fresh_oracle(dim=1)
    isfeas_b, obs_b, se_b = orc_b.hit((7,), 1, visit=3)

    assert obs_a == obs_b
