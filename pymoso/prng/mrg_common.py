"""
Shared matrix-power jump-ahead machinery, extracted from
pymoso/prng/mrg32k3a.py's own mat333mult/mat311mod (kept here verbatim,
same behavior) plus a new arbitrary-exponent binary-exponentiation
routine (mat_pow_mod/jump_n) that generalizes the two fixed jumps
(jump_substream: 2**76, get_next_prnstream: 2**127) mrg32k3a.py's
generalized jump is built on into one arbitrary-exponent operation.

Exact Python integer arithmetic throughout, for the same reason
mat333mult/mat311mod already are exact: the row sums these matrices
reach (roughly 2^62-2^63) lose precision in float64's 53 exact bits --
see KNOWN_ISSUES.md issue 1, the defect this exactness fixes.

Generic to a 3x3 recurrence matrix and its own modulus, not hardcoded to
MRG32k3a's specific coefficients -- those (mrga12/mrga13n/mrga21/mrga23n,
mrgm1/mrgm2) stay in mrg32k3a.py, which is the only module that knows
what recurrence it's advancing. docs/rng-interface-design.md §9 proposes
MRG31k3p (a different-order recurrence, different coefficients, per
L'Ecuyer & Touzin 2000) reuse this same technique once it's onboarded;
this module is kept parameterized for that, not because a second caller
exists yet.
"""


def mat333mult(a, b):
    """
    Multiply a 3x3 matrix with a 3x1 matrix, in exact Python integer
    arithmetic. The row sums here reach roughly 2^62-2^63 (matrix
    elements and seed components are each up to ~2^32), which silently
    loses precision in float64 (53 bits of exact integer range); Python
    ints are arbitrary precision, so casting to int before multiplying
    is exact by construction. See docs/phase2a-verification.md, item 1.

    Parameters
    ----------
    a : tuple of tuple of float
        3x3 matrix
    b : tuple of tuple if float
        3x1 matrix

    Returns
    -------
    res : list of int
        3x1 matrix
    """
    res = [0, 0, 0]
    r3 = range(3)
    for i in r3:
        res[i] = sum([int(a[i][j])*int(b[j]) for j in r3])
    return res


def mat311mod(a, b):
    """
    Compute moduli of a 3x1 matrix, in exact Python integer arithmetic.
    Python's '/' between two ints is float true division, which would
    reintroduce the same precision loss mat333mult avoids if 'a' holds
    a large exact int; '%' on ints is exact.

    Parameters
    ----------
    a : tuple of float
        3x1 matrix
    b : float
        modulus

    Returns
    -------
    res : tuple of int
        3x1 matrix
    """
    res = [0, 0, 0]
    r3 = range(3)
    bi = int(b)
    for i in r3:
        res[i] = int(a[i]) % bi
    return res


def mat333sqmult_mod(a, b, mod):
    """
    Multiply two 3x3 matrices, mod-reduced at every entry, in exact
    Python integer arithmetic. The repeated-squaring building block for
    mat_pow_mod's binary exponentiation -- keeps every intermediate
    entry bounded by `mod` across O(log n) squarings, rather than
    growing without bound the way an unreduced power would.

    Parameters
    ----------
    a : 3x3 sequence of int
    b : 3x3 sequence of int
    mod : int

    Returns
    -------
    res : list of list of int
        3x3 matrix, every entry in [0, mod)
    """
    modi = int(mod)
    r3 = range(3)
    res = [[0, 0, 0] for _ in r3]
    for i in r3:
        for j in r3:
            res[i][j] = sum(int(a[i][k]) * int(b[k][j]) for k in r3) % modi
    return res


def mat_pow_mod(a, n, mod):
    """
    Compute a**n mod `mod` for a 3x3 matrix `a`, via binary
    exponentiation (square-and-multiply) -- O(log n) matrix
    multiplications regardless of how large `n` is, the same technique
    tests/test_jump_ahead.py's independent reference already
    demonstrates is tractable for validating the two fixed exponents;
    this is that technique promoted to shipped code, for an arbitrary
    exponent rather than two hardcoded ones.

    Parameters
    ----------
    a : 3x3 sequence of int
        The one-step transition matrix to raise to the n-th power.
    n : int
        Exponent. Must be non-negative.
    mod : int
        Modulus.

    Returns
    -------
    list of list of int
        a**n mod `mod`, a 3x3 matrix with every entry in [0, mod).
    """
    if n < 0:
        raise ValueError('exponent must be non-negative, got {0}'.format(n))
    modi = int(mod)
    result = [[1 if i == j else 0 for j in range(3)] for i in range(3)]
    base = [[int(v) % modi for v in row] for row in a]
    while n > 0:
        if n & 1:
            result = mat333sqmult_mod(result, base, modi)
        base = mat333sqmult_mod(base, base, modi)
        n >>= 1
    return result


def jump_n(seed_part, base_matrix, n, mod):
    """
    Advance a 3-component seed part `n` steps under `base_matrix`'s
    one-step recurrence, mod `mod`: the one generalized operation
    mrg32k3a.py's jump_substream/get_next_prnstream become thin wrappers
    around, at the two fixed exponents 2**76/2**127 -- see
    docs/rng-interface-design.md §3.4/§3.5 for why the public interface
    stops there (arbitrary-coordinate jumps are a later step's concern,
    not this module's).

    Parameters
    ----------
    seed_part : sequence of int, length 3
    base_matrix : 3x3 sequence of int
        The recurrence's own one-step transition matrix.
    n : int
        Number of steps. Must be non-negative.
    mod : int
        Modulus.

    Returns
    -------
    res : list of int
        3x1 matrix, the seed part advanced n steps, every entry in
        [0, mod).
    """
    power = mat_pow_mod(base_matrix, n, mod)
    return mat311mod(mat333mult(power, seed_part), mod)
