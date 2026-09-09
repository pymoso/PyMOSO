"""
docs/rng-interface-design.md §12 step 3: Oracle's CRN-protocol
replacement (§4). Two checks the golden suite doesn't directly provide
(§8.1's own gap analysis):

- §7 item 7, the bit-identical migration proof: for a battery of
  (iteration, replication) coordinates, the CRN branch's actual stream
  -- produced by real hit()/bump()/crn_advance() calls -- equals
  jump_seed_n(root, iteration*ITER_STRIDE + replication*REPL_STRIDE)
  computed directly (§2's formula). This is the concrete, checked claim
  behind "CRN stays bit-identical," not an assumption riding on §2's
  proof alone.

- §7.1 item 10, order-independence, run against *this step's own code*
  and confirmed still failing: step 3 deliberately keeps the old
  order-dependent walk for crnflag=False (the temporary compatibility
  encoding, §3.4's note), so a point's draw still depends on which
  other points were visited first this iteration -- exactly the defect
  §2 names. xfail(strict=True): once step 4b switches the default
  crnflag=False coordinate to offset_within_iteration/point_code, this
  starts passing, and strict=True turns that into a loud failure here
  (XPASS) as a forcing function to update this file, rather than a
  silent, unnoticed fix.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import MRG32k3a, jump_seed_n

ROOT = (12345, 12345, 12345, 12345, 12345, 12345)
REPL_STRIDE = 2 ** 76
ITER_STRIDE = 2 ** 127


class SeedRecordingOracle(Oracle):
    """g() returns the first seed component it was actually handed,
    as a float (so hit()'s mean()/variance() calls -- expecting
    numbers -- work unmodified) -- lets a test read back exactly which
    stream position g() drew from, without needing a real simulation."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        return True, (float(rng.get_seed()[0]),)


def _expected_seed0(coordinate):
    return float(jump_seed_n(ROOT, coordinate)[0])


# ---------------------------------------------------------------------------
# §7 item 7: bit-identical migration proof (CRN branch)
# ---------------------------------------------------------------------------

def _fresh_crn_oracle():
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = SeedRecordingOracle(rng)
    orc.set_crnflag(True)
    orc.simpar = 1
    return orc


def test_crn_replication_0_at_iteration_0_matches_the_root_directly():
    orc = _fresh_crn_oracle()
    isfeas, obs = orc.bump((1,), 1)
    assert obs[0][0] == _expected_seed0(0)


@pytest.mark.parametrize("m", [1, 3, 5])
def test_crn_every_replication_within_one_iteration_matches_the_coordinate_formula(m):
    """iteration k's replication r must land at k*ITER_STRIDE +
    r*REPL_STRIDE (§2), for several m, checked against every
    replication returned, not just the mean."""
    orc = _fresh_crn_oracle()
    isfeas, obs = orc.bump((7,), m)
    for r in range(m):
        assert obs[r][0] == _expected_seed0(0 * ITER_STRIDE + r * REPL_STRIDE)


def test_crn_advance_moves_to_the_next_iteration_baseline_exactly():
    """crn_advance() (iteration k -> k+1) must land exactly at
    (k+1)*ITER_STRIDE, checked across several successive iterations,
    each time via a fresh point's replication 0."""
    orc = _fresh_crn_oracle()
    for k in range(1, 6):
        orc.crn_advance()
        isfeas, obs = orc.bump((k,), 1)
        assert obs[0][0] == _expected_seed0(k * ITER_STRIDE)


def test_crn_different_points_in_the_same_iteration_share_the_same_replication_streams():
    """The actual point of CRN, checked operationally: two different
    points visited in the same iteration draw identical values at each
    replication index -- both equal the coordinate formula, and
    therefore each other."""
    orc = _fresh_crn_oracle()
    orc.crn_advance()
    isfeas_a, obs_a = orc.bump((11,), 4)
    isfeas_b, obs_b = orc.bump((22,), 4)
    assert [v[0] for v in obs_a] == [v[0] for v in obs_b]
    for r in range(4):
        assert obs_a[r][0] == _expected_seed0(1 * ITER_STRIDE + r * REPL_STRIDE)


def test_crn_multiple_iterations_and_replications_all_match_the_formula():
    """A fuller battery: several iterations, several replications each,
    every single value checked against the formula directly -- the
    concrete evidence behind "CRN stays bit-identical through the
    coordinate-mechanism swap" (§8), not an assumption."""
    orc = _fresh_crn_oracle()
    for k in range(5):
        if k > 0:
            orc.crn_advance()
        m = k + 1
        isfeas, obs = orc.bump((100 + k,), m)
        for r in range(m):
            assert obs[r][0] == _expected_seed0(k * ITER_STRIDE + r * REPL_STRIDE), (
                f"iteration {k}, replication {r}"
            )


# ---------------------------------------------------------------------------
# §7.1 item 10: order-independence -- confirmed still failing at step 3
# ---------------------------------------------------------------------------

def _run_in_order(order):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = SeedRecordingOracle(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    results = {}
    for x in order:
        isfeas, obmean, obse = orc.hit(x, 1)
        results[x] = obmean[0]
    return results


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Expected to fail at step 3: crnflag=False deliberately keeps the "
        "old order-dependent compatibility encoding (docs/rng-interface-"
        "design.md §3.4's note) until step 4b switches the default "
        "coordinate to offset_within_iteration/point_code. strict=True: a "
        "silent pass here means step 4b landed without updating this test."
    ),
)
def test_order_independence_within_one_iteration_crnflag_false():
    point_a, point_b = (1,), (2,)
    forward = _run_in_order([point_a, point_b])
    backward = _run_in_order([point_b, point_a])
    assert forward[point_a] == backward[point_a]
    assert forward[point_b] == backward[point_b]
