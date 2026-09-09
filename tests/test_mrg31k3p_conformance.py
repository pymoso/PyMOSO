"""
docs/rng-interface-design.md §12 step 5: the §7 conformance suite run
against MRG31k3p -- the interface's first real test against a generator
other than MRG32k3a. Unlike tests/test_prng_conformance.py (written
before the real interface existed, against a deliberately narrow "thin"
stand-in), this file targets MRG31k3p's own real, arbitrary-coordinate
jump_seed_n directly -- step 2's generalized-jump machinery already
exists, so there is no need for a thin scaffold here.

Every numeric reference below is derived independently for MRG31k3p, not
ported from tests/test_prng_conformance.py's own MRG32k3a-specific
values -- same discipline as pymoso/prng/mrg31k3p.py itself (see that
module's docstring for the sourcing account: L'Ecuyer's own SSJ library,
cross-checked two independent ways, plus an exact-linear-algebra proof
against SSJ's own published one-step jump matrices, done separately from
this file).

Two §7 items are not re-tested here, deliberately, not by oversight:
- Item 4 (bsm monotonicity) is already covered by
  tests/test_prng_conformance.py's own test_bsm_monotonicity: bsm() is a
  pure function of u (§3.3), shared verbatim by both generators
  (pymoso/prng/mrg31k3p.py imports it directly from mrg32k3a.py, not a
  copy), so nothing about MRG31k3p specifically could make that test
  meaningfully different here.
- Item 7 (bit-identical migration proof) doesn't apply: MRG31k3p has no
  "old stateful walk" to compare against -- it's new code, not a
  migration.
"""
import multiprocessing

import pytest

from pymoso.prng.mrg31k3p import (
    MRG31k3p, jump_seed_n, mrg31m1, mrg31m2, get_next_prnstream, jump_substream,
)
from pymoso.prng.mrg32k3a import REPL_STRIDE

pytestmark = pytest.mark.timeout(60)

DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)
SEEDS = [
    DEFAULT_SEED,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 987654321, 408598527, 219826182, 277969500),
]


def stream_at(seed, coordinate):
    """MRG31k3p's own real stream_at: `coordinate` is an arbitrary
    non-negative int, reached via jump_seed_n's generalized jump --
    not a narrow stand-in, since the general machinery already exists
    (step 2, mrg_common.py, reused unchanged for this generator)."""
    if coordinate < 0:
        raise ValueError("coordinate must be non-negative")
    prn = MRG31k3p(jump_seed_n(seed, coordinate))
    return prn


# ---------------------------------------------------------------------------
# Reusable checks -- same shape as tests/test_prng_conformance.py's own,
# restated here (not imported) so this file has no collection-order
# dependency on that one and stays self-contained the same way.
# ---------------------------------------------------------------------------

def check_determinism(stream_at_fn, seed, coordinate, n_draws=5):
    draws1 = [stream_at_fn(seed, coordinate).random() for _ in range(n_draws)]
    draws2 = [stream_at_fn(seed, coordinate).random() for _ in range(n_draws)]
    assert draws1 == draws2, (
        f"stream_at({seed}, {coordinate}) produced different draws across "
        f"two independent calls: {draws1} != {draws2}"
    )


def check_distinctness(stream_at_fn, seed, coordinates, n_draws=5):
    firsts = {}
    states = {}
    for c in coordinates:
        s = stream_at_fn(seed, c)
        firsts[c] = s.random()
        states[c] = s.get_seed()
    coords = list(coordinates)
    for i, ci in enumerate(coords):
        for cj in coords[i + 1:]:
            assert firsts[ci] != firsts[cj], (
                f"coordinates {ci} and {cj} share a first draw under seed {seed}"
            )
            assert states[ci] != states[cj], (
                f"coordinates {ci} and {cj} land on the same state under seed {seed}"
            )


def check_exact_matrix_power(stream_at_fn, seed, coordinate):
    got = stream_at_fn(seed, coordinate).get_seed()
    exact = _exact_jump_n(seed, coordinate)
    assert got == exact, (
        f"stream_at({seed}, {coordinate}) landed on {got}, expected the exact "
        f"{coordinate}-step reference {exact}"
    )


# ---------------------------------------------------------------------------
# Item 1: determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("coordinate", [0, 1, 5, 100, 2 ** 76, 2 ** 127])
def test_determinism(seed, coordinate):
    check_determinism(stream_at, seed, coordinate)


# ---------------------------------------------------------------------------
# Item 2: distinctness / non-overlap, including adjacent coordinates and
# the two cached exponents
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_distinctness_across_a_coordinate_battery(seed):
    check_distinctness(
        stream_at, seed,
        [0, 1, 2, 3, 4, 5, 100, 101, 1000, 2 ** 76, 2 ** 76 + 1, 2 ** 127],
    )


# ---------------------------------------------------------------------------
# Item 3: exact-integer brute-force jump validation, MRG31k3p's own
# coefficients -- independent of pymoso/prng/mrg31k3p.py's own
# mat_pow_mod call (a separate, simple nested-list implementation here,
# not mrg_common.py's), and independent of tests/test_prng_conformance.py
# (restated, not imported).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("coordinate", [0, 1, 2, 3, 5, 76, 127, 2 ** 20])
def test_stream_at_matches_exact_matrix_power(seed, coordinate):
    check_exact_matrix_power(stream_at, seed, coordinate)


def test_cached_exponents_match_the_general_path():
    """REPL_STRIDE/ITER_STRIDE (pymoso/prng/mrg31k3p.py's two cached
    exponents) must agree with jump_seed_n's own general computation --
    the same "cache is an optimization, not a second code path with its
    own chance to drift" property step 2's own commit established for
    MRG32k3a, checked directly here rather than assumed to transfer."""
    seed = DEFAULT_SEED
    for coordinate in (2 ** 76, 2 ** 127):
        check_exact_matrix_power(stream_at, seed, coordinate)


# ---- independent exact reference (arbitrary-precision int, plain nested
# lists -- not mrg_common.py). Coefficients restated directly from
# pymoso/prng/mrg31k3p.py's own module docstring/sourcing, which is
# itself independently cross-checked two ways (bit-shift decode +
# exact-linear-algebra conjugation against SSJ's own published jump
# matrices) -- this reference exists to catch an *implementation* bug
# in jump_seed_n's own binary-exponentiation code, not a wrong-constant
# bug (already ruled out separately). ----

_M1MAT = [[0, 1, 0], [0, 0, 1], [129, 4194304, 0]]
_M2MAT = [[0, 1, 0], [0, 0, 1], [32769, 0, 32768]]


def _mat_mult(a, b, mod):
    n, p, k = len(a), len(b[0]), len(b)
    c = [[0] * p for _ in range(n)]
    for i in range(n):
        for j in range(p):
            c[i][j] = sum(a[i][l] * b[l][j] for l in range(k)) % mod
    return c


def _mat_pow(a, n, mod):
    size = len(a)
    r = [[1 if i == j else 0 for j in range(size)] for i in range(size)]
    base = a
    while n > 0:
        if n & 1:
            r = _mat_mult(r, base, mod)
        base = _mat_mult(base, base, mod)
        n >>= 1
    return r


def _exact_jump_n(seed, n):
    x10, x11, x12, x20, x21, x22 = seed
    v1 = [[x10], [x11], [x12]]
    v2 = [[x20], [x21], [x22]]
    p1 = _mat_pow(_M1MAT, n, mrg31m1)
    p2 = _mat_pow(_M2MAT, n, mrg31m2)
    nv1 = _mat_mult(p1, v1, mrg31m1)
    nv2 = _mat_mult(p2, v2, mrg31m2)
    return (nv1[0][0], nv1[1][0], nv1[2][0], nv2[0][0], nv2[1][0], nv2[2][0])


# ---------------------------------------------------------------------------
# Item 5: getrandbits unbiasedness smoke test
# ---------------------------------------------------------------------------

def _chi_square_stat(counts, expected):
    return sum((c - expected) ** 2 / expected for c in counts)


def _generous_chi_square_threshold(df):
    return df + 6 * (2 * df) ** 0.5


@pytest.mark.parametrize("k,n_draws", [(4, 32000), (8, 128000)])
def test_getrandbits_unbiasedness_smoke_test(k, n_draws):
    rng = MRG31k3p(DEFAULT_SEED)
    n_buckets = 1 << k
    counts = [0] * n_buckets
    for _ in range(n_draws):
        counts[rng.getrandbits(k)] += 1
    expected = n_draws / n_buckets
    stat = _chi_square_stat(counts, expected)
    threshold = _generous_chi_square_threshold(n_buckets - 1)
    assert stat < threshold, (
        f"getrandbits({k}) chi-square statistic {stat:.1f} exceeds the "
        f"generous smoke-test threshold {threshold:.1f} over {n_draws} draws "
        f"into {n_buckets} buckets"
    )


# ---------------------------------------------------------------------------
# Item 6: cross-process reproducibility under forkserver
# ---------------------------------------------------------------------------

def _worker_stream_draws(seed, coordinate, n_draws, queue):
    s = stream_at(seed, coordinate)
    draws = [s.random() for _ in range(n_draws)]
    queue.put((s.get_seed(), draws))


def test_cross_process_reproducibility_under_forkserver():
    seed = DEFAULT_SEED
    coordinate = 3
    n_draws = 5
    ctx = multiprocessing.get_context("forkserver")
    q = ctx.Queue()
    p = ctx.Process(target=_worker_stream_draws, args=(seed, coordinate, n_draws, q))
    p.start()
    try:
        child_seed, child_draws = q.get(timeout=30)
    finally:
        p.join(timeout=30)
    parent_stream = stream_at(seed, coordinate)
    parent_draws = [parent_stream.random() for _ in range(n_draws)]
    assert child_seed == parent_stream.get_seed()
    assert child_draws == parent_draws


# ---------------------------------------------------------------------------
# get_next_prnstream/jump_substream -- thin wrappers, checked against
# jump_seed_n directly (same relationship mrg32k3a.py's own versions have).
# ---------------------------------------------------------------------------

def test_get_next_prnstream_matches_jump_seed_n_at_iter_stride():
    seed = DEFAULT_SEED
    prn = get_next_prnstream(seed)
    assert prn.get_seed() == jump_seed_n(seed, 2 ** 127)


def test_jump_substream_matches_jump_seed_n_at_repl_stride():
    seed = DEFAULT_SEED
    prn = MRG31k3p(seed)
    jump_substream(prn)
    assert prn.get_seed() == jump_seed_n(seed, REPL_STRIDE)


# ---------------------------------------------------------------------------
# Proof the checks above have teeth against THIS generator specifically
# -- the working agreement's "a detector never seen detecting isn't
# proven to work," re-verified here rather than assumed to carry over
# from tests/test_prng_conformance.py's own MRG32k3a-specific proof.
# ---------------------------------------------------------------------------

def _broken_stream_at_wrong_jump_size(seed, coordinate):
    """Reuses the 2**127 jump where the general jump_seed_n should be
    used -- targets check_exact_matrix_power."""
    prn = MRG31k3p(jump_seed_n(seed, 2 ** 127))
    return prn


def _broken_stream_at_ignores_coordinate(seed, coordinate):
    """`coordinate` silently ignored -- targets check_distinctness."""
    prn = MRG31k3p(seed)
    return prn


def test_conformance_checks_detect_a_broken_backend():
    seed = DEFAULT_SEED
    with pytest.raises(AssertionError):
        check_exact_matrix_power(_broken_stream_at_wrong_jump_size, seed, coordinate=2)
    with pytest.raises(AssertionError):
        check_distinctness(_broken_stream_at_ignores_coordinate, seed, [0, 1, 2])
