"""
Permanent regression tests: the jump-ahead (jump_substream /
get_next_prnstream) must land exactly where a brute-force,
single-step-at-a-time advance of the same number of steps lands. This is
the exact validation done in docs/phase2a-verification.md item 1 to
establish the defect, kept here so the fix (exact Python integer
arithmetic in mat333mult/mat311mod, prng/mrg32k3a.py) stays proven
correct rather than merely "looks right."

The brute-force reference here is intentionally independent of
mat333mult/mat311mod: it advances the MRG32k3a single-step generator
directly, one step at a time, using the exact same recurrence
(mrg32k3a()) that is confirmed untouched by the fix.
"""
import random

import pytest

from pymoso.prng.mrg32k3a import (
    MRG32k3a, get_next_prnstream, jump_substream, mrg32k3a, mrgm1, mrgm2,
)

M1 = int(mrgm1)
M2 = int(mrgm2)

DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)


def brute_force_step_n(seed, n):
    """Advance the single-step generator n times, by direct repeated
    calls to mrg32k3a() -- independent of the jump-ahead code path."""
    s = tuple(float(x) for x in seed)
    for _ in range(n):
        s, _u = mrg32k3a(s)
    return tuple(int(round(v)) for v in s)


@pytest.mark.parametrize("seed", [
    DEFAULT_SEED,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 2158288731, 4085985277, 2198261820, 2779695000),
    (3693674385 % M1, 4092891722 % M1, 440821893 % M1, 3797265612 % M2, 958999843 % M2, 3843167363 % M2),
])
def test_jump_substream_2_76_matches_exact_matrix_power(seed):
    """jump_substream (2^76) must match an independently-derived exact
    matrix-power jump of 2**76 steps, computed in arbitrary-precision
    Python ints from the same recurrence mrg32k3a() implements."""
    exact = _exact_jump_n(seed, 2**76)
    prn = MRG32k3a(seed)
    jump_substream(prn)
    assert prn.get_seed() == exact


@pytest.mark.parametrize("seed", [
    DEFAULT_SEED,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 2158288731, 4085985277, 2198261820, 2779695000),
])
def test_get_next_prnstream_2_127_matches_exact_matrix_power(seed):
    """get_next_prnstream (2^127) must match the same independent exact
    reference."""
    exact = _exact_jump_n(seed, 2**127)
    prn = get_next_prnstream(seed, False)
    assert prn.get_seed() == exact


def test_single_step_generator_matches_brute_force_over_2000_steps():
    """The plain single-step generator is untouched by the jump-ahead
    fix; confirm it stays exact over a long chain at realistic
    (non-toy) seed magnitudes."""
    random.seed(42)
    seed = (
        random.randint(1, M1 - 1), random.randint(1, M1 - 1), random.randint(1, M1 - 1),
        random.randint(1, M2 - 1), random.randint(1, M2 - 1), random.randint(1, M2 - 1),
    )
    got = brute_force_step_n(seed, 2000)
    exact = _exact_step_n(seed, 2000)
    assert got == exact


# ---- exact reference implementation (arbitrary-precision int), independent
# of prng/mrg32k3a.py's own mat333mult/mat311mod -- validated against
# brute force for N=10**3, 10**4, 10**5 before it was used to establish
# the defect (docs/phase2a-verification.md item 1). ----

A12 = 1403580
A13N = 810728
A21 = 527612
A23N = 1370589

_M1MAT = [[0, A12, -A13N], [1, 0, 0], [0, 1, 0]]
_M2MAT = [[A21, 0, -A23N], [1, 0, 0], [0, 1, 0]]


def _exact_step(seed):
    x10, x11, x12, x20, x21, x22 = seed
    new_x1 = (A12 * x11 - A13N * x10) % M1
    new_x2 = (A21 * x22 - A23N * x20) % M2
    return (x11, x12, new_x1, x21, x22, new_x2)


def _exact_step_n(seed, n):
    s = tuple(seed)
    for _ in range(n):
        s = _exact_step(s)
    return s


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


@pytest.mark.parametrize("n", [10**3, 10**4, 10**5])
def test_exact_matrix_power_matches_brute_force(n):
    """The exact reference implementation itself, validated against
    brute-force single-stepping -- this is the equivalence check from
    docs/phase2a-verification.md item 1, kept permanently."""
    seed = DEFAULT_SEED
    bf = _exact_step_n(seed, n)
    mp = _exact_jump_n(seed, n)
    assert bf == mp
