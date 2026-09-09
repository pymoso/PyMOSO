"""
docs/rng-interface-design.md §12 step 8, stage 1: direct coverage of
Oracle.get_endseed() -- the oracle-role-only coordinate high-water
mark, replacing crn_advance()'s own call-count-only endseed reporting.

The property that matters, and the one every test below actually
checks: get_endseed() must not collide with any raw value a run's own
hit()/bump() calls actually drew. It would be easy to get the boundary
wrong in a way that still "looks" plausible -- one past the *start* of
the last replication touched, rather than one past its *reserved
end* -- since both produce a valid-looking seed and neither is
detectable by inspection. test_endseed_does_not_collide_with_any_
touched_coordinate_offset_branch below demonstrates that exact
off-by-one concretely: computed directly, the wrong formula's seed is
shown to equal the last replication's own first drawn value.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import (
    MRG32k3a, jump_seed_n, ITER_STRIDE, REPL_STRIDE, REPL_RESERVE_STRIDE,
    SYNC_ROLE_OFFSET, SYNC_STRIDE,
)
from pymoso.prng.base import point_width, offset_within_iteration, REPL_RESERVE_BITS

ROOT = (12345, 12345, 12345, 12345, 12345, 12345)


class SimpleOracle(Oracle):
    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        super().__init__(rng)

    def g(self, x, rng):
        return True, (rng.get_seed()[0],)


def _fresh_oracle(dim=1, crnflag=False):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = SimpleOracle(rng, dim=dim)
    orc.set_crnflag(crnflag)
    orc.simpar = 1
    return orc


# ---------------------------------------------------------------------------
# Untouched Oracle: nothing drawn, endseed is _orc_root itself.
# ---------------------------------------------------------------------------

def test_untouched_oracle_endseed_is_orc_root():
    orc = _fresh_oracle()
    assert orc.get_endseed() == orc._orc_root


# ---------------------------------------------------------------------------
# The off-by-one this file exists to catch, on the branch that
# introduced REPL_RESERVE_BITS: one-past-the-last-replication's-START
# is not the same as one-past-its-RESERVED-END, and the wrong one lands
# inside a value that replication actually drew.
# ---------------------------------------------------------------------------

def test_endseed_does_not_collide_with_any_touched_coordinate_offset_branch():
    reserve = 1 << REPL_RESERVE_BITS

    class FillingOracle(Oracle):
        def __init__(self, rng):
            self.num_obj = 1
            self.dim = 1
            self.log = []
            super().__init__(rng)

        def g(self, x, rng):
            vals = [rng.random() for _ in range(reserve)]
            self.log.append(vals)
            return True, (vals[0],)

    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = FillingOracle(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    orc.hit((5,), 2)  # two replications, each filling its reserve exactly

    all_drawn = set(orc.log[0]) | set(orc.log[1])
    endseed = orc.get_endseed()
    endstream = MRG32k3a(endseed)
    endstream.set_class_cache(False)
    assert endstream.random() not in all_drawn

    # Demonstrate the specific off-by-one: "one past the last
    # replication's start" (base + (m-1)*reserve) instead of "one past
    # its end" (base + m*reserve) -- computed directly, not via
    # get_endseed(), to show what the wrong formula would have produced.
    W = point_width(1)
    base = 0 * ITER_STRIDE + offset_within_iteration((5,), 0, 0, W)
    wrong_endseed = jump_seed_n(orc._orc_root, base + 1 * reserve)
    wrong_stream = MRG32k3a(wrong_endseed)
    wrong_stream.set_class_cache(False)
    assert wrong_stream.random() == orc.log[1][0]  # exactly replication 1's own first draw
    assert wrong_endseed != endseed


# ---------------------------------------------------------------------------
# Formula checks, one per branch that updates the high-water mark.
# ---------------------------------------------------------------------------

def test_endseed_matches_the_formula_offset_branch():
    orc = _fresh_oracle(dim=1, crnflag=False)
    W = point_width(1)
    orc.hit((5,), 3)
    base = 0 * ITER_STRIDE + offset_within_iteration((5,), 0, 0, W)
    expected = jump_seed_n(orc._orc_root, base + 3 * REPL_RESERVE_STRIDE)
    assert orc.get_endseed() == expected


def test_endseed_matches_the_formula_crn_branch():
    orc = _fresh_oracle(dim=1, crnflag=True)
    orc.hit((5,), 4)
    expected = jump_seed_n(orc._orc_root, 0 * ITER_STRIDE + 4 * REPL_STRIDE)
    assert orc.get_endseed() == expected
    assert orc.get_endseed() == orc._next_seed  # the two mechanisms agree, as designed


def test_endseed_matches_the_formula_sync_branch():
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.hit((5,), 2, sync=7)
    expected = jump_seed_n(orc._orc_root, SYNC_ROLE_OFFSET + 7 * SYNC_STRIDE + 2 * REPL_STRIDE)
    assert orc.get_endseed() == expected


def test_endseed_matches_the_formula_visit_branch():
    orc = _fresh_oracle(dim=1, crnflag=False)
    W = point_width(1)
    orc.hit((5,), 2, visit=3)
    base = 0 * ITER_STRIDE + offset_within_iteration((5,), 3, 0, W)
    expected = jump_seed_n(orc._orc_root, base + 2 * REPL_RESERVE_STRIDE)
    assert orc.get_endseed() == expected


# ---------------------------------------------------------------------------
# Monotonicity: the high-water mark never moves backward, across
# multiple calls, multiple points, and crn_advance().
# ---------------------------------------------------------------------------

def test_endseed_is_monotonic_across_multiple_hits_same_iteration():
    """The high-water mark must never move backward, regardless of
    which point is hit next -- checked directly against the raw
    tracker, across a sequence including a continuation call (the same
    point hit twice) whose own coordinate is smaller than the
    intervening point's block."""
    orc = _fresh_oracle(dim=1, crnflag=False)
    marks = []
    orc.hit((5,), 2)
    marks.append(orc._high_water_mark)
    orc.hit((9,), 2)
    marks.append(orc._high_water_mark)
    orc.hit((5,), 1)  # continuation -- its own coordinate is smaller
    marks.append(orc._high_water_mark)
    assert marks == sorted(marks)
    assert marks[0] > 0


def test_endseed_advances_across_crn_advance_crn_branch():
    orc = _fresh_oracle(dim=1, crnflag=True)
    orc.hit((5,), 2)
    before = orc.get_endseed()
    orc.crn_advance()
    orc.hit((5,), 2)
    after = orc.get_endseed()
    assert after != before
    assert orc._high_water_mark > 0


def test_endseed_reset_by_set_crnflag():
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.hit((5,), 3)
    assert orc._high_water_mark > 0
    orc.set_crnflag(False)
    assert orc._high_water_mark == 0
    assert orc.get_endseed() == orc._orc_root


# ---------------------------------------------------------------------------
# bump()'s partial coverage (crnflag=True only, per its own docstring).
# ---------------------------------------------------------------------------

def test_bump_updates_endseed_under_crnflag_true():
    orc = _fresh_oracle(dim=1, crnflag=True)
    orc.bump((5,), 3)
    expected = jump_seed_n(orc._orc_root, 0 * ITER_STRIDE + 3 * REPL_STRIDE)
    assert orc.get_endseed() == expected


def test_bump_does_not_update_endseed_under_crnflag_false():
    """Documented gap (bump()'s own docstring): crnflag=False's bump()
    still uses the pre-4b order-dependent walk, which has no coordinate
    in the current scheme to report -- get_endseed() stays at whatever
    it was before the call."""
    orc = _fresh_oracle(dim=1, crnflag=False)
    before = orc.get_endseed()
    orc.bump((5,), 3)
    assert orc.get_endseed() == before
