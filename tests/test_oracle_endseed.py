"""
docs/rng-interface-design.md §12 step 8, stage 1: direct coverage of
Oracle.get_endseed() -- the oracle-role-only coordinate high-water
mark, replacing crn_advance()'s own call-count-only endseed reporting.

The property that matters, and the one every test below actually
checks: get_endseed() must not collide with any raw value a run's own
hit() calls actually drew. It would be easy to get the boundary
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
    SYNC_ROLE_OFFSET, SYNC_STRIDE, ISP_ITER_MARGIN, SYNC_ZONE_STREAM_START,
)
from pymoso.prng.base import point_width, offset_within_iteration, REPL_RESERVE_BITS, StreamFamilyExceeded

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
    orc = FillingOracle(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    orc.hit((5,), 2)  # two replications, each filling its reserve exactly

    all_drawn = set(orc.log[0]) | set(orc.log[1])
    endseed = orc.get_endseed()
    endstream = MRG32k3a(endseed)
    assert endstream.random() not in all_drawn

    # Demonstrate the specific off-by-one: "one past the last
    # replication's start" (base + (m-1)*reserve) instead of "one past
    # its end" (base + m*reserve) -- computed directly, not via
    # get_endseed(), to show what the wrong formula would have produced.
    W = point_width(1)
    base = 0 * ITER_STRIDE + offset_within_iteration((5,), 0, 0, W)
    wrong_endseed = jump_seed_n(orc._orc_root, base + 1 * reserve)
    wrong_stream = MRG32k3a(wrong_endseed)
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
    assert marks[0] is not None


def test_endseed_advances_across_crn_advance_crn_branch():
    orc = _fresh_oracle(dim=1, crnflag=True)
    orc.hit((5,), 2)
    before = orc.get_endseed()
    orc.crn_advance()
    orc.hit((5,), 2)
    after = orc.get_endseed()
    assert after != before
    assert orc._high_water_mark is not None


def test_endseed_reset_by_set_crnflag():
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.hit((5,), 3)
    assert orc._high_water_mark is not None
    orc.set_crnflag(False)
    assert orc._high_water_mark is None
    assert orc.get_endseed() == orc._orc_root


# ---------------------------------------------------------------------------
# §12 step 6c: get_endseed()'s own carry, exercised through the real
# Oracle method, not just the standalone pymoso.prng.base.one_past
# (tests/test_stream_offset_carry.py) or Philox's own real constants
# (tests/test_philox4x32_conformance.py). MRG32k3a's own
# ISP_ITER_MARGIN=2**32 makes the raise practically unreachable through
# millions of real hit()/crn_advance() calls, so these set
# _high_water_mark directly (white-box) to the exact boundary a real
# run would eventually reach, rather than actually running that many
# iterations -- still a real exercise of get_endseed()'s own carry
# logic and its own choice of family_capacity, not just of one_past in
# isolation.
# ---------------------------------------------------------------------------

def test_get_endseed_carries_safely_within_the_default_zone_family():
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.set_crnflag(False)
    orc._high_water_mark = (ISP_ITER_MARGIN - 2, ITER_STRIDE - 1)
    expected = jump_seed_n(orc._orc_root, (ISP_ITER_MARGIN - 1) * ITER_STRIDE)
    assert orc.get_endseed() == expected


def test_get_endseed_raises_at_the_default_zone_family_boundary():
    """One past (ISP_ITER_MARGIN-1, ITER_STRIDE-1) would carry to
    stream=ISP_ITER_MARGIN, which is >= ISP_ITER_MARGIN -- exactly the
    boundary get_endseed() must catch rather than silently landing in
    what would be the next isp path's own reserved zone."""
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.set_crnflag(False)
    orc._high_water_mark = (ISP_ITER_MARGIN - 1, ITER_STRIDE - 1)
    with pytest.raises(StreamFamilyExceeded):
        orc.get_endseed()


def test_get_endseed_never_raises_in_the_sync_zone_at_any_reachable_stream():
    """The sync zone is deliberately left unbounded (§8.2's own
    documented posture) -- confirmed directly at a stream value far
    beyond anything ISP_ITER_MARGIN would allow in the default zone,
    not just at a small, unremarkable one."""
    orc = _fresh_oracle(dim=1, crnflag=False)
    orc.set_crnflag(False)
    huge_sync_stream = SYNC_ZONE_STREAM_START + 10 ** 15
    orc._high_water_mark = (huge_sync_stream, ITER_STRIDE - 1)
    expected = jump_seed_n(orc._orc_root, (huge_sync_stream + 1) * ITER_STRIDE)
    assert orc.get_endseed() == expected  # must not raise
