"""
docs/rng-interface-design.md §12 step 4b: direct, formula-based coverage
of the crnflag=False *default* path's cutover to offset_within_iteration/
point_code -- the specific gap identified before regenerating goldens
(§8.1's own "goldens can't verify what they encode" point, extended:
test_solution_sensitivity.py and test_mocompass_mopbnb_compat.py are
real, valuable integration checks, but both compare against baselines
that get regenerated to match whatever this step's code produces, so
neither is independent verification once that happens, and neither
directly isolates continuation from any other change).

Existing coverage this file does NOT duplicate:
- tests/test_oracle_coordinate_migration.py's order-independence test
  (item 10) already checks that two *different* points visited in
  either order get the same stream -- a property of the default path,
  but not the same claim as this file's continuation checks below,
  which are about *repeated* calls to the *same* point.
- tests/test_oracle_visit_sync.py checks the *opt-in* visit=/sync=
  paths exhaustively, but every one of those calls passes visit!=0 or
  sync=<int> explicitly -- none of them exercise hit()'s own default-
  path dispatch (visit=0, sync=None) or its continuation tracking
  (_replications_drawn), which lives in hit() itself, not in
  _hit_via_coordinate.

What's actually at stake: MOPBnB's own correctness depends on repeated
hit() calls to the same (iteration, x) getting fresh, non-overlapping
replications (§4.1) -- the property this file checks directly and
operationally, not just via an integration baseline that would still
pass if continuation were silently broken (e.g. always restarting at
replication 0): a serial-vs-parallel or serial-vs-proc consistency
check (tests/test_mocompass_mopbnb_compat.py's actual coverage) would
still hold even if both paths shared the identical bug.
"""
from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import MRG32k3a, jump_seed_n, ITER_STRIDE
from pymoso.prng.base import point_width, offset_within_iteration

ROOT = (12345, 12345, 12345, 12345, 12345, 12345)


class LoggingOracle(Oracle):
    """g() returns, and records, the first seed component it was
    actually handed, as a float -- lets a test read back exactly which
    stream position each individual replication drew from."""

    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        v = float(rng.get_seed()[0])
        self.log.append(v)
        return True, (v,)


def _fresh_oracle(dim=1):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = LoggingOracle(rng, dim=dim)
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


def _expected(orc, x, replication, W):
    coordinate = orc._iteration * ITER_STRIDE + offset_within_iteration(x, 0, replication, W)
    return float(jump_seed_n(orc._orc_root, coordinate)[0])


# ---------------------------------------------------------------------------
# The default path matches the offset_within_iteration formula directly,
# for a single hit() call -- the crnflag=False analog of test_oracle_
# coordinate_migration.py's CRN-branch formula checks.
# ---------------------------------------------------------------------------

def test_default_path_single_call_matches_the_formula():
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    orc.hit((5,), 3)
    assert orc.log == [_expected(orc, (5,), r, W) for r in range(3)]


def test_default_path_m_equals_one_matches_the_formula():
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    orc.hit((5,), 1)
    assert orc.log == [_expected(orc, (5,), 0, W)]


# ---------------------------------------------------------------------------
# Continuation: the specific property MOPBnB's correctness depends on
# (§4.1). A repeated hit() call to the same x, same iteration, must get
# the *next* contiguous block -- not restart at replication 0 (which
# would silently correlate "new" and "old" samples) and not skip ahead
# arbitrarily (which would silently waste coordinate space but is a much
# less dangerous failure than the restart case).
# ---------------------------------------------------------------------------

def test_repeated_hit_for_the_same_point_continues_rather_than_restarts():
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    orc.hit((5,), 3)          # replications 0, 1, 2
    first = list(orc.log)
    orc.hit((5,), 2)          # must continue at 3, 4 -- not restart at 0, 1
    second = orc.log[3:]
    assert first == [_expected(orc, (5,), r, W) for r in range(3)]
    assert second == [_expected(orc, (5,), r, W) for r in range(3, 5)]


def test_repeated_hit_draws_never_overlap_across_calls():
    """The concrete failure mode a broken continuation (always restart
    at 0) would produce: the second call's draws would be an exact
    prefix-match of the first call's. Checked as a set-disjointness
    property, independent of the formula check above, so a coincidental
    formula-matching bug that still happened to overlap wouldn't slip
    through either."""
    orc = _fresh_oracle(dim=1)
    orc.hit((5,), 4)
    first = set(orc.log)
    orc.hit((5,), 3)
    second = set(orc.log[4:])
    assert first.isdisjoint(second)


def test_continuation_is_per_point_not_global():
    """Two different points, each hit() twice, interleaved -- each
    point's own continuation counter must advance independently, not
    share one global counter across points (which would make point B's
    first call continue from point A's count instead of starting at 0)."""
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    orc.hit((5,), 2)   # x=5: replications 0,1
    orc.hit((9,), 2)   # x=9: replications 0,1 (its OWN count, not 2,3)
    orc.hit((5,), 1)   # x=5 again: replication 2 (continues from x=5's own count)

    x5_first = orc.log[0:2]
    x9_first = orc.log[2:4]
    x5_second = orc.log[4:5]

    assert x5_first == [_expected(orc, (5,), r, W) for r in range(2)]
    assert x9_first == [_expected(orc, (9,), r, W) for r in range(2)]
    assert x5_second == [_expected(orc, (5,), 2, W)]


# ---------------------------------------------------------------------------
# Continuation resets when the iteration advances (crn_advance()) -- a
# revisit to x in a *new* iteration starts fresh at replication 0 again,
# under that iteration's own ITER_STRIDE offset.
# ---------------------------------------------------------------------------

def test_continuation_resets_on_crn_advance():
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    orc.hit((5,), 3)               # iteration 0: replications 0,1,2
    orc.crn_advance()              # -> iteration 1
    orc.hit((5,), 2)                # iteration 1: replications 0,1 (NOT 3,4)
    second = orc.log[3:]
    assert second == [_expected(orc, (5,), r, W) for r in range(2)]


# ---------------------------------------------------------------------------
# Different points, direct formula check (item 10 already checks order-
# independence operationally; this checks the same default path against
# the formula directly, matching the rigor test_oracle_coordinate_
# migration.py gives the CRN branch).
# ---------------------------------------------------------------------------

def test_different_points_do_not_collide_and_match_the_formula():
    orc = _fresh_oracle(dim=2)
    W = point_width(2)
    orc.hit((1, 1), 2)
    orc.hit((99, -3), 2)
    a = orc.log[0:2]
    b = orc.log[2:4]
    assert a == [_expected(orc, (1, 1), r, W) for r in range(2)]
    assert b == [_expected(orc, (99, -3), r, W) for r in range(2)]
    assert set(a).isdisjoint(b)


# ---------------------------------------------------------------------------
# bump() is deliberately NOT cut over (its own docstring, chnbase.py) --
# pin that explicitly, so an accidental future change to bump() doesn't
# silently move behavior without a deliberate golden regeneration.
# ---------------------------------------------------------------------------

def test_bump_still_uses_the_old_mechanism_under_crnflag_false():
    """bump() still consumes rng/_next_seed directly (step 3's
    mechanism), not the coordinate-based default path -- confirmed by
    checking its result does NOT match the offset_within_iteration
    formula (it would, coincidentally, only if the old walk and the new
    formula agreed, which they don't beyond replication 0 from a fresh
    Oracle)."""
    orc = _fresh_oracle(dim=1)
    W = point_width(1)
    isfeas, obs = orc.bump((5,), 3)
    formula_predicted = [_expected(orc, (5,), r, W) for r in range(3)]
    assert [v[0] for v in obs] != formula_predicted
