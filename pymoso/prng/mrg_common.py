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
import operator


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


def matvec_mod(a, s, mod):
    """
    Multiply a 3x3 matrix by a 3-component seed part, mod `mod`, in
    exact Python integer arithmetic: mat311mod(mat333mult(a, s), mod)
    for entries that are already ints, written out (PowerTable.jump's
    inner step).

    Parameters
    ----------
    a : 3x3 sequence of int
    s : sequence of int, length 3
    mod : int

    Returns
    -------
    list of int
        3 entries, each in [0, mod).
    """
    s0, s1, s2 = s
    a0, a1, a2 = a
    return [(a0[0] * s0 + a0[1] * s1 + a0[2] * s2) % mod,
            (a1[0] * s0 + a1[1] * s1 + a1[2] * s2) % mod,
            (a2[0] * s0 + a2[1] * s1 + a2[2] * s2) % mod]


class PowerTable:
    """
    A**(2**k) mod `mod` for k = 0, 1, 2, ..., for one 3x3 matrix `a`,
    so that a jump of n steps is one matrix-vector product per set bit
    of n (`jump`), where jump_n squares its way up n's whole bit length
    on every call (docs/phase7-plan.md, step 3: the squarings were
    76-95% of a general jump, and real exponents are long and sparse).

    Built on first use and extended when a longer exponent arrives, so
    importing costs nothing and the first jump at a new bit length pays
    for the squarings up to it -- once per process: a worker builds its
    own (tests/test_jump_power_table.py).

    The same result as jump_n, exactly: integer arithmetic reduced mod
    `mod` at every step, and powers of one matrix commute, so applying
    them to the seed part one at a time, lowest first, gives a**n * s
    mod `mod`.

    Parameters
    ----------
    a : 3x3 sequence of int
        The one-step transition matrix.
    mod : int
    """

    def __init__(self, a, mod):
        self.mod = int(mod)
        self.powers = [[[int(v) % self.mod for v in row] for row in a]]

    def ensure(self, nbits):
        """The powers for k < `nbits`, extending the table if needed."""
        powers = self.powers
        if len(powers) < nbits:
            # Extended on a copy and replaced whole, never appended to in
            # place: a thread reading the old list never sees a partial
            # one, and two threads extending at once each build a correct
            # list.
            powers = list(powers)
            while len(powers) < nbits:
                powers.append(mat333sqmult_mod(powers[-1], powers[-1], self.mod))
            self.powers = powers
        return powers

    def jump(self, seed_part, n):
        """
        Advance a 3-component seed part `n` steps: jump_n(seed_part, a,
        n, mod), with the same result.

        Parameters
        ----------
        seed_part : sequence of int, length 3
        n : int
            Number of steps. Must be non-negative.

        Returns
        -------
        list of int
            3 entries, each in [0, mod).
        """
        n = operator.index(n)
        if n < 0:
            raise ValueError('exponent must be non-negative, got {0}'.format(n))
        mod = self.mod
        s = [int(v) % mod for v in seed_part]
        powers = self.ensure(n.bit_length())
        k = 0
        while n:
            if n & 1:
                s = matvec_mod(powers[k], s, mod)
            n >>= 1
            k += 1
        return s
