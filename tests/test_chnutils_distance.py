"""
Unit tests for edist and dh (and dxB/dAB, the one-sided building blocks
dh is defined in terms of), derived from the standard mathematical
definitions:

    edist(x1, x2) = sqrt(sum((x1_i - x2_i)^2))
    dxB(x, B)      = min_{b in B} edist(x, b)              (inf(.) := +inf for empty B)
    dAB(A, B)      = max_{a in A} dxB(a, B)                (sup(.) := -inf for empty A)
    dh(A, B)       = max(dAB(A, B), dAB(B, A))             -- the standard
                     (symmetric, two-sided) Hausdorff distance

dh is symmetric by construction (max is commutative), even though its
one-sided component dAB is not -- confirmed below with a concrete
asymmetric example, since dh(A,B) vs dh(B,A) is what the docs' metric
examples actually rely on.
"""
import math

from pymoso.chnutils import edist, dh, dxB, dAB


# ---------------------------------------------------------------------------
# edist: basic correctness and symmetry
# ---------------------------------------------------------------------------

def test_edist_3_4_5_triangle():
    assert edist((0, 0), (3, 4)) == 5.0


def test_edist_same_point_is_zero():
    assert edist((1, 2, 3), (1, 2, 3)) == 0.0


def test_edist_is_symmetric():
    x1, x2 = (1, 7), (-3, 2)
    assert edist(x1, x2) == edist(x2, x1)


def test_edist_one_dimension():
    assert edist((5,), (1,)) == 4.0


# ---------------------------------------------------------------------------
# dxB / dAB: the one-sided building blocks, including their empty-input
# conventions (inf(empty) = +inf, sup(empty) = -inf), which is what
# makes dh's own empty-set behavior what it is below.
# ---------------------------------------------------------------------------

def test_dxb_is_the_minimum_distance():
    assert dxB((0, 0), {(3, 0), (0, 4), (1, 1)}) == math.sqrt(2)


def test_dxb_of_empty_set_is_infinity():
    assert dxB((0, 0), set()) == float('inf')


def test_dab_is_the_max_of_the_mins():
    # A = {(0,0), (10,10)}, B = {(0,0)}
    # dxB((0,0), B) = 0; dxB((10,10), B) = sqrt(200)
    A = {(0, 0), (10, 10)}
    B = {(0, 0)}
    assert dAB(A, B) == math.sqrt(200)


def test_dab_of_empty_a_is_negative_infinity():
    assert dAB(set(), {(0, 0)}) == float('-inf')


def test_dab_of_nonempty_a_against_empty_b_is_infinity():
    assert dAB({(0, 0)}, set()) == float('inf')


# ---------------------------------------------------------------------------
# dh: identical sets, singletons, and the asymmetric-one-sided-but-
# symmetric-overall property.
# ---------------------------------------------------------------------------

def test_dh_identical_sets_is_zero():
    A = {(1, 2), (3, 4), (5, 6)}
    assert dh(A, A) == 0.0


def test_dh_singletons_is_edist_between_them():
    p1, p2 = (0, 0), (3, 4)
    assert dh({p1}, {p2}) == edist(p1, p2) == 5.0


def test_dh_is_symmetric_even_though_dab_is_not():
    """A subset of B: dAB(A,B)=0 (every point of A is in B), but
    dAB(B,A) is the distance from B's extra point to A, which is > 0.
    The one-sided distances disagree; dh must not, since it's defined
    as max(dAB(A,B), dAB(B,A)) -- swapping the arguments just swaps
    which term is which, and max is commutative."""
    A = {(0, 0)}
    B = {(0, 0), (10, 10)}
    d_ab = dAB(A, B)
    d_ba = dAB(B, A)
    assert d_ab != d_ba  # confirms the one-sided distances really are asymmetric
    assert d_ab == 0.0
    assert d_ba == math.sqrt(200)
    assert dh(A, B) == dh(B, A) == math.sqrt(200)


def test_dh_matches_standard_definition_on_a_hand_worked_example():
    """A = {(0,0), (4,0)}, B = {(2,0)}.
    dAB(A,B): dxB((0,0),B)=2, dxB((4,0),B)=2 -> max=2.
    dAB(B,A): dxB((2,0),A)=min(2,2)=2 -> max=2.
    dh(A,B) = max(2,2) = 2."""
    A = {(0, 0), (4, 0)}
    B = {(2, 0)}
    assert dh(A, B) == 2.0
    assert dh(B, A) == 2.0


# ---------------------------------------------------------------------------
# Empty sets. dh(nonempty, empty) = +inf in both orders (infinitely far,
# since one side has nothing to approximate the other with) -- follows
# directly from dAB's own empty-input conventions above. dh(empty, empty)
# is a genuinely ambiguous case: a common convention treats two empty
# sets as trivially identical (distance 0), but under this codebase's
# literal sup(empty)=-inf/inf(empty)=+inf conventions, dAB(empty,empty)
# is -inf regardless of the other argument, so dh(empty,empty) = -inf.
# Flagging this as a question rather than asserting either -inf or 0 is
# "the" right answer -- see the phase 4 report.
# ---------------------------------------------------------------------------

def test_dh_nonempty_vs_empty_is_positive_infinity():
    A = {(0, 0)}
    assert dh(A, set()) == float('inf')
    assert dh(set(), A) == float('inf')


def test_dh_both_empty_is_negative_infinity_not_zero():
    """Documenting current behavior, not endorsing it -- see module
    docstring. A number of Hausdorff-distance treatments define
    d(empty, empty) = 0 by convention; this implementation's cascading
    dAB convention gives -inf instead, because dAB(empty, *) is -inf
    unconditionally (the sup is over an empty index set)."""
    assert dh(set(), set()) == float('-inf')
