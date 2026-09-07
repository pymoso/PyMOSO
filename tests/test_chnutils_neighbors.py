"""
Unit tests for get_nbors/get_setnbors, derived from the code's own
stated definition (a box of candidate integer points around x, kept if
their Euclidean distance to x is <= r and they are not x itself) --
computed by hand for each case, not by running get_nbors and copying
its output.

get_nbors(x, r) = { p in Z^q : edist(x, p) <= r, p != x }
"""
from math import sqrt

from pymoso.chnutils import get_nbors, get_setnbors


# ---------------------------------------------------------------------------
# Radius 0: the box collapses to {x} itself, which is then excluded.
# Empty, for any x, any dimension.
# ---------------------------------------------------------------------------

def test_radius_zero_is_empty():
    assert get_nbors((0,), 0) == set()
    assert get_nbors((3, -2), 0) == set()
    assert get_nbors((1, 1, 1), 0) == set()


# ---------------------------------------------------------------------------
# Radius 1, dimension 1: the two adjacent integers.
# ---------------------------------------------------------------------------

def test_radius_one_dimension_one():
    assert get_nbors((5,), 1) == {(4,), (6,)}
    assert get_nbors((0,), 1) == {(-1,), (1,)}


# ---------------------------------------------------------------------------
# Radius 1, dimension 3: only the 6 face neighbors (distance exactly 1)
# survive -- edge neighbors (two coords changed) are at distance
# sqrt(2) > 1, corner neighbors (three coords changed) at sqrt(3) > 1.
# ---------------------------------------------------------------------------

def test_radius_one_dimension_three_is_six_face_neighbors():
    expected = {
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1),
    }
    assert get_nbors((0, 0, 0), 1) == expected
    assert len(expected) == 6
    # sanity-check the excluded edge/corner points really are farther
    # than 1 -- confirms the *reason* they're excluded, not just that
    # they are
    assert sqrt(1 ** 2 + 1 ** 2 + 0 ** 2) > 1
    assert sqrt(1 ** 2 + 1 ** 2 + 1 ** 2) > 1


def test_radius_one_dimension_three_offset_center():
    """Same shape, translated -- confirms the result is relative to x,
    not absolute to the origin."""
    expected = {
        (3, 3, 4), (1, 3, 4),
        (2, 4, 4), (2, 2, 4),
        (2, 3, 5), (2, 3, 3),
    }
    assert get_nbors((2, 3, 4), 1) == expected


# ---------------------------------------------------------------------------
# Non-integer radius: r=1.5 in 2 dimensions includes the diagonal
# neighbors (distance sqrt(2) =~ 1.414 <= 1.5), unlike r=1, which
# excludes them (sqrt(2) > 1). This is the clearest demonstration of
# non-integer radius actually changing the result.
# ---------------------------------------------------------------------------

def test_radius_1_5_includes_diagonals_in_2d_unlike_radius_1():
    r1 = get_nbors((0, 0), 1)
    r15 = get_nbors((0, 0), 1.5)
    assert r1 == {(1, 0), (-1, 0), (0, 1), (0, -1)}  # 4 face neighbors only
    assert r15 == {
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    }  # all 8 -- diagonals now included
    assert r1 < r15  # proper subset


def test_radius_1_5_in_one_dimension_same_as_radius_1():
    """In 1D there's no diagonal to gain, and the next integer out is
    at distance 2, still excluded by r=1.5 -- so 1.5 behaves like 1
    here, unlike in 2D+."""
    assert get_nbors((0,), 1.5) == get_nbors((0,), 1) == {(-1,), (1,)}


# ---------------------------------------------------------------------------
# x is never included in its own neighborhood, at any radius (the
# `or x == x1` branch in the code's own filter, independent of
# distance). The README's object-reference table doesn't say this
# explicitly ("Return: Set of tuples which are the neighbors.") --
# consistent with ordinary use of "neighbor", but worth confirming
# precisely since the doc doesn't state it.
# ---------------------------------------------------------------------------

def test_x_itself_is_never_a_neighbor_of_itself():
    for r in (0, 1, 1.5, 2, 5):
        for x in ((0,), (3, -2), (1, 1, 1)):
            assert x not in get_nbors(x, r)


# ---------------------------------------------------------------------------
# get_setnbors: union of get_nbors over the set, minus the set itself
# (the "exclusive" neighborhood, per its own docstring).
# ---------------------------------------------------------------------------

def test_setnbors_radius_zero_is_empty():
    assert get_setnbors({(0,), (5,), (2, 2)}, 0) == set()


def test_setnbors_excludes_members_that_are_neighbors_of_each_other():
    """(0,) and (1,) are each other's neighbors at r=1; get_setnbors
    must not report either as a neighbor of the set, only the true
    boundary points (-1,) and (2,)."""
    assert get_setnbors({(0,), (1,)}, 1) == {(-1,), (2,)}


def test_setnbors_of_a_contiguous_run():
    assert get_setnbors({(0,), (1,), (2,)}, 1) == {(-1,), (3,)}


def test_setnbors_of_a_single_point_matches_get_nbors():
    """With one member, the "exclusive" neighborhood is just its
    ordinary neighborhood (nothing in the set to subtract but itself,
    which get_nbors never included anyway)."""
    assert get_setnbors({(5,)}, 1) == get_nbors((5,), 1)


def test_setnbors_empty_set_is_empty():
    assert get_setnbors(set(), 1) == set()
