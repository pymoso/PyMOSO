"""
Permanent regression tests for pymoso/prng/mrg_common.py's generalized,
arbitrary-exponent matrix-power jump (mat_pow_mod/jump_n) -- docs/rng-
interface-design.md §12 step 2.

tests/test_jump_ahead.py already proves the two fixed exponents
(2**76, 2**127) land correctly, and that coverage stays meaningful (it
still exercises jump_substream/get_next_prnstream end to end). It does
NOT exercise mat_pow_mod's binary exponentiation at any other exponent,
so a bug that only appears at some other bit pattern (an off-by-one in
the square-and-multiply loop, an odd/even handling mistake, incorrect
handling of n=0 or n=1) would pass every existing test. This file closes
that gap directly, checked at a battery of arbitrary exponents -- small
ones against literal brute-force single-stepping (independent of
mat_pow_mod), and large ones against an independent exact-matrix-power
reference (same technique test_jump_ahead.py uses, ported again here
rather than imported, so this file has no import-order dependency on
that one and no dependency on mrg_common.py's own mat_pow_mod either).

This is the arithmetic that had the original float-precision defect
(KNOWN_ISSUES.md issue 1) -- new code, same danger zone -- so it gets
the same brute-force discipline test_jump_ahead.py already applies, not
a lighter one.
"""
import random

import pytest

from pymoso.prng.mrg32k3a import (
    jump_seed_n, mrg32k3a, mrgm1, mrgm2, a1p76, a2p76, a1p127, a2p127,
)
from pymoso.prng.mrg_common import mat_pow_mod, jump_n

M1 = int(mrgm1)
M2 = int(mrgm2)

DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)
SEEDS = [
    DEFAULT_SEED,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 2158288731, 4085985277, 2198261820, 2779695000),
]


def brute_force_step_n(seed, n):
    """Advance the single-step generator n times, by direct repeated
    calls to mrg32k3a() -- independent of jump_seed_n/mat_pow_mod, same
    technique as test_jump_ahead.py's own brute_force_step_n."""
    s = tuple(float(x) for x in seed)
    for _ in range(n):
        s, _u = mrg32k3a(s)
    return tuple(int(round(v)) for v in s)


# Arbitrary exponents small enough for literal brute-force single-
# stepping: 0 and 1 (boundary cases), odd and even, non-power-of-2, and
# large enough (10**4-10**5) to actually exercise several rounds of
# square-and-multiply rather than just a handful of bits.
SMALL_ARBITRARY_EXPONENTS = [0, 1, 2, 3, 7, 13, 100, 12345, 10**4, 10**5]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", SMALL_ARBITRARY_EXPONENTS)
def test_jump_seed_n_matches_brute_force_at_arbitrary_small_exponents(seed, n):
    """The key check the fixed-exponent tests structurally cannot
    provide: jump_seed_n at exponents *other* than 2**76/2**127,
    checked against literal brute-force stepping, independent of
    mat_pow_mod's own logic."""
    got = jump_seed_n(seed, n)
    exact = brute_force_step_n(seed, n)
    assert got == exact


# ---- independent exact reference (arbitrary-precision int), ported
# again from tests/test_jump_ahead.py's technique -- deliberately not
# imported from that file or from pymoso.prng.mrg_common, so this
# reference has no dependency on the code it's checking. ----

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


@pytest.mark.parametrize("n", [10**3, 10**4, 10**5])
def test_independent_reference_matches_brute_force(n):
    """The independent reference itself, validated against brute-force
    single-stepping before it's trusted to check anything else -- same
    discipline as test_jump_ahead.py's own equivalence check."""
    seed = DEFAULT_SEED
    bf = brute_force_step_n(seed, n)
    mp = _exact_jump_n(seed, n)
    assert bf == mp


# Exponents where literal brute-force stepping is infeasible: large,
# arbitrary (not just the two fixed 2**76/2**127 this codebase has
# always used), including values one step off a power of two -- exactly
# where an off-by-one in square-and-multiply's bit handling would show.
LARGE_ARBITRARY_EXPONENTS = [
    2**50,
    2**64,
    2**76 + 1,          # one step past the historical fixed exponent
    2**76 - 1,          # one step before it
    2**100,
    2**127 - 1,          # one step before the other historical exponent
    2**127 + 12345,
    2**150,
    2**200,
]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", LARGE_ARBITRARY_EXPONENTS)
def test_jump_seed_n_matches_independent_reference_at_large_arbitrary_exponents(seed, n):
    got = jump_seed_n(seed, n)
    exact = _exact_jump_n(seed, n)
    assert got == exact


# ---------------------------------------------------------------------------
# Regression pin: the generalized jump must still reproduce the four
# original, hand-transcribed matrices exactly at the two historical fixed
# exponents -- confirms the refactor (mrg32k3a.py step 2) didn't silently
# drift from the values jump_substream/get_next_prnstream shipped for
# years, not just that the new machinery is internally consistent.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_jump_n_reproduces_the_historical_a1p76_a2p76_matrices(seed):
    from pymoso.prng.mrg32k3a import _m1_step, _m2_step
    got1 = jump_n(seed[0:3], _m1_step, 2**76, M1)
    got2 = jump_n(seed[3:6], _m2_step, 2**76, M2)
    exact1 = [int(v) % M1 for v in [
        sum(int(a1p76[i][j]) * int(seed[0:3][j]) for j in range(3)) for i in range(3)
    ]]
    exact2 = [int(v) % M2 for v in [
        sum(int(a2p76[i][j]) * int(seed[3:6][j]) for j in range(3)) for i in range(3)
    ]]
    assert got1 == exact1
    assert got2 == exact2


@pytest.mark.parametrize("seed", SEEDS)
def test_jump_n_reproduces_the_historical_a1p127_a2p127_matrices(seed):
    from pymoso.prng.mrg32k3a import _m1_step, _m2_step
    got1 = jump_n(seed[0:3], _m1_step, 2**127, M1)
    got2 = jump_n(seed[3:6], _m2_step, 2**127, M2)
    exact1 = [int(v) % M1 for v in [
        sum(int(a1p127[i][j]) * int(seed[0:3][j]) for j in range(3)) for i in range(3)
    ]]
    exact2 = [int(v) % M2 for v in [
        sum(int(a2p127[i][j]) * int(seed[3:6][j]) for j in range(3)) for i in range(3)
    ]]
    assert got1 == exact1
    assert got2 == exact2


# ---------------------------------------------------------------------------
# mat_pow_mod boundary cases, directly (not through jump_seed_n): n=0
# must be the identity matrix, n=1 must be the base matrix itself, mod
# reduction.
# ---------------------------------------------------------------------------

def test_mat_pow_mod_zero_is_identity():
    a = [[2, 0, 1], [0, 3, 0], [1, 1, 1]]
    assert mat_pow_mod(a, 0, 1000) == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_mat_pow_mod_one_is_the_base_matrix_mod_reduced():
    a = [[2, 0, 1005], [0, 3, 0], [1, 1, 1]]
    assert mat_pow_mod(a, 1, 1000) == [[2, 0, 5], [0, 3, 0], [1, 1, 1]]


def test_mat_pow_mod_negative_exponent_raises():
    a = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    with pytest.raises(ValueError):
        mat_pow_mod(a, -1, 1000)


def test_mat_pow_mod_matches_brute_force_squaring_for_a_small_synthetic_matrix():
    """A synthetic, easy-to-hand-verify 3x3 matrix and modulus,
    independent of MRG32k3a's own coefficients -- confirms mat_pow_mod
    is a correct generic operation, not something that happens to work
    only for mrg32k3a.py's specific numbers."""
    a = [[1, 1, 0], [0, 1, 1], [1, 0, 1]]
    mod = 97
    for n in [0, 1, 2, 3, 5, 8, 13, 21, 100, 1000]:
        # brute force: multiply the matrix by itself n times, by hand
        result = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for _ in range(n):
            new_result = [[0, 0, 0] for _ in range(3)]
            for i in range(3):
                for j in range(3):
                    new_result[i][j] = sum(result[i][k] * a[k][j] for k in range(3)) % mod
            result = new_result
        assert mat_pow_mod(a, n, mod) == result, f"mismatch at n={n}"
