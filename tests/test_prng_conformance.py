"""
Step 1 of docs/rng-interface-design.md's §12 step list: the §7
conformance suite, written and run before any real generator-interface
code exists, against a thin `stream_at` wrapper built entirely from
today's `MRG32k3a` and its two fixed jumps (`get_next_prnstream`:
2**127, `jump_substream`: 2**76).

This file's `stream_at` is deliberately narrow, not the real §3.1
interface: `coordinate` is a non-negative int, and
`stream_at(seed, coordinate)` reaches the position `coordinate`
`jump_substream` (2**76) calls from `seed`. That is enough range to
write and meaningfully run every §7 item that applies at this step,
without inventing the final coordinate encoding early -- the real
`stream_at(base_seed, coordinate)` with its generalized, arbitrary-
exponent jump doesn't exist until step 2 (`mrg_common.py`), and the
`crn=False` branch's real per-point coordinate doesn't exist until
step 4.

Two §7 items don't apply yet, and are noted here rather than silently
skipped:
- Item 3 (exact-integer brute-force jump validation) is scoped to what
  this step's `stream_at` can do: validated against the same
  independent, arbitrary-precision reference `tests/test_jump_ahead.py`
  uses (ported here, not imported, so this file stays self-contained the
  same way that file is independent of `mat333mult`/`mat311mod`) for
  small coordinate multiples of 2**76.
- Item 7 (bit-identical migration proof) doesn't apply: it compares a
  coordinate-derived seed against the *old* stateful `crn_reset`/
  `crn_advance` walk, which requires `chnbase.py`'s real coordinate
  wiring (step 3) to exist on both sides of the comparison.

Per the working agreement ("a detector never seen detecting isn't proven
to work"), the checks below that meaningfully *can* be fooled by a wrong
implementation (determinism, distinctness, exact-jump matching) are
written as reusable functions taking a `stream_at`-shaped callable, so
each can be run both against the real thin wrapper (expected to pass,
the tests in the main body of this file) and against a deliberately
broken fake backend (expected to fail -- see
test_conformance_checks_detect_a_broken_backend at the bottom). That is
the concrete evidence this suite is meaningful before anything relies on
it, not merely an assumption that it would catch a real defect.
"""
import multiprocessing

import pytest

from pymoso.prng.mrg32k3a import (
    MRG32k3a, bsm, get_next_prnstream, jump_substream, mrgm1, mrgm2,
)

# Generous backstop for the whole file (the cross-process test under
# forkserver is the one that actually needs it; everything else here is
# fast) -- same convention as tests/test_multifile_transport.py.
pytestmark = pytest.mark.timeout(60)

M1 = int(mrgm1)
M2 = int(mrgm2)

DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)
SEEDS = [
    DEFAULT_SEED,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 2158288731, 4085985277, 2198261820, 2779695000),
]


def thin_stream_at(seed, coordinate):
    """This step's narrow stand-in for §3.1's stream_at: `coordinate`
    (a non-negative int) is the number of jump_substream (2**76) hops
    from `seed`. Returns an MRG32k3a instance -- already the §3.2
    Stream shape (random/getrandbits/normalvariate) via today's class,
    nothing new needed for this step."""
    if coordinate < 0:
        raise ValueError("coordinate must be non-negative")
    prn = MRG32k3a(seed)
    for _ in range(coordinate):
        jump_substream(prn)
    return prn


# ---------------------------------------------------------------------------
# Reusable checks -- each takes a stream_at-shaped callable so it can run
# against both the real thin wrapper (below) and the deliberately broken
# fake backend (bottom of file).
# ---------------------------------------------------------------------------

def check_determinism(stream_at, seed, coordinate, n_draws=5):
    """§7 item 1: stream_at(seed, idx) called twice, independently,
    produces identical draw sequences."""
    draws1 = [stream_at(seed, coordinate).random() for _ in range(n_draws)]
    draws2 = [stream_at(seed, coordinate).random() for _ in range(n_draws)]
    assert draws1 == draws2, (
        f"stream_at({seed}, {coordinate}) produced different draws across "
        f"two independent calls: {draws1} != {draws2}"
    )


def check_distinctness(stream_at, seed, coordinates, n_draws=5):
    """§7 item 2: for a battery of distinct coordinates (including
    adjacent ones), the first draw of each stream differs from every
    other's (sufficient to show no shared prefix -- if the first draw
    differs, no longer prefix can match either), and the streams' landed
    states differ pairwise."""
    firsts = {}
    states = {}
    for c in coordinates:
        s = stream_at(seed, c)
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


def check_exact_matrix_power(stream_at, seed, coordinate):
    """§7 item 3, scoped to this step's stream_at: coordinate `c` must
    land exactly `c * 2**76` steps from `seed`, checked against the
    independent exact-integer reference below (ported from
    tests/test_jump_ahead.py, not imported, so this file has no
    collection-order dependency on that one)."""
    got = stream_at(seed, coordinate).get_seed()
    exact = _exact_jump_n(seed, coordinate * (2 ** 76))
    assert got == exact, (
        f"stream_at({seed}, {coordinate}) landed on {got}, expected the exact "
        f"{coordinate}*2**76-step reference {exact}"
    )


# ---------------------------------------------------------------------------
# Item 1: determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("coordinate", [0, 1, 5, 100])
def test_determinism(seed, coordinate):
    check_determinism(thin_stream_at, seed, coordinate)


# ---------------------------------------------------------------------------
# Item 2: distinctness / non-overlap, including adjacent coordinates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_distinctness_across_a_coordinate_battery(seed):
    check_distinctness(thin_stream_at, seed, [0, 1, 2, 3, 4, 5, 100, 101, 1000])


# ---------------------------------------------------------------------------
# Item 3: exact-integer brute-force jump validation (scoped to this step)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("coordinate", [0, 1, 2, 3, 5])
def test_stream_at_matches_exact_matrix_power(seed, coordinate):
    check_exact_matrix_power(thin_stream_at, seed, coordinate)


# ---- independent exact reference (arbitrary-precision int), ported from
# tests/test_jump_ahead.py -- same technique, kept local so this file has
# no import-order dependency on that one. ----

A12 = 1403580
A13N = 810728
A21 = 527612
A23N = 1370589

_M1MAT = [[0, A12, -A13N], [1, 0, 0], [0, 1, 0]]
_M2MAT = [[A21, 0, -A23N], [1, 0, 0], [0, 1, 0]]


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
    v1 = [[x12], [x11], [x10]]
    v2 = [[x22], [x21], [x20]]
    p1 = _mat_pow(_M1MAT, n, M1)
    p2 = _mat_pow(_M2MAT, n, M2)
    nv1 = _mat_mult(p1, v1, M1)
    nv2 = _mat_mult(p2, v2, M2)
    new_x12, new_x11, new_x10 = nv1[0][0], nv1[1][0], nv1[2][0]
    new_x22, new_x21, new_x20 = nv2[0][0], nv2[1][0], nv2[2][0]
    return (new_x10, new_x11, new_x12, new_x20, new_x21, new_x22)


# ---------------------------------------------------------------------------
# Item 4: monotonicity of the CRN-participating transform (bsm), a pure
# function of u -- no stream_at needed, per §3.3.
# ---------------------------------------------------------------------------

def test_bsm_monotonicity():
    us = [i / 10000 for i in range(1, 10000)]
    zs = [bsm(u) for u in us]
    non_decreasing = all(zs[i] <= zs[i + 1] for i in range(len(zs) - 1))
    assert non_decreasing, "bsm(u) is not non-decreasing in u over (0, 1)"


# ---------------------------------------------------------------------------
# Item 5: getrandbits unbiasedness smoke test (not TestU01-grade
# validation -- explicitly out of scope for this phase, per §7 item 5).
# ---------------------------------------------------------------------------

def _chi_square_stat(counts, expected):
    return sum((c - expected) ** 2 / expected for c in counts)


def _generous_chi_square_threshold(df):
    """Gaussian approximation to the chi-square distribution (valid at
    the largish df used below): mean + 6*std, astronomically unlikely to
    trip against a genuinely unbiased generator (~1e-9), while still
    catching a real, strong bias (e.g. getrandbits stuck near a
    constant). A smoke test's threshold, not a calibrated p-value."""
    return df + 6 * (2 * df) ** 0.5


@pytest.mark.parametrize("k,n_draws", [(4, 32000), (8, 128000)])
def test_getrandbits_unbiasedness_smoke_test(k, n_draws):
    rng = MRG32k3a(DEFAULT_SEED)
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
# Item 6: cross-process reproducibility, explicitly under forkserver
# (matching .venv-dev's default -- see docs/forkserver-hang.md for why
# fork's copy-on-write would paper over a real gap here).
# ---------------------------------------------------------------------------

def _worker_stream_draws(seed, coordinate, n_draws, queue):
    s = thin_stream_at(seed, coordinate)
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
    parent_stream = thin_stream_at(seed, coordinate)
    parent_draws = [parent_stream.random() for _ in range(n_draws)]
    assert child_seed == parent_stream.get_seed()
    assert child_draws == parent_draws


# ---------------------------------------------------------------------------
# Proof the checks above have teeth: run them against a deliberately
# broken fake backend and confirm they fail. Never used as a real
# backend -- exists only to satisfy the working agreement's "a detector
# never seen detecting isn't proven to work."
# ---------------------------------------------------------------------------

def _broken_stream_at_wrong_jump_size(seed, coordinate):
    """A plausible, realistic bug: reuses the 2**127 jump
    (get_next_prnstream) where the thin wrapper should use the 2**76 one
    (jump_substream) -- a mixed-up-matrix mistake. Distinct coordinates
    still land on distinct (just wrong) positions under this bug, so
    check_distinctness would NOT catch it -- this specifically targets
    check_exact_matrix_power, which compares against the true 2**76
    magnitude and would."""
    prn = MRG32k3a(seed)
    for _ in range(coordinate):
        prn = get_next_prnstream(prn.get_seed())
    return prn


def _broken_stream_at_ignores_coordinate(seed, coordinate):
    """A different, also-realistic bug (a dropped loop variable):
    `coordinate` is silently ignored, so every coordinate lands on the
    same, unjumped stream. Targets check_distinctness specifically."""
    return MRG32k3a(seed)


def test_conformance_checks_detect_a_broken_backend():
    """Proves the checks above have teeth by running them against
    deliberately broken backends and confirming they fail -- two
    different bugs, each caught by the check it specifically targets, per
    the working agreement's "a detector never seen detecting isn't proven
    to work." check_determinism isn't exercised here: tripping it needs a
    backend that is genuinely non-deterministic given identical inputs,
    which isn't a natural "wrong coordinate math" bug the way the two
    below are -- a deliberate scope choice, not an oversight."""
    seed = DEFAULT_SEED
    with pytest.raises(AssertionError):
        check_exact_matrix_power(_broken_stream_at_wrong_jump_size, seed, coordinate=2)
    with pytest.raises(AssertionError):
        check_distinctness(_broken_stream_at_ignores_coordinate, seed, [0, 1, 2])
