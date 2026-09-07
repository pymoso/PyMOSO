"""
Unit tests for get_nondom, derived from the mathematical definition of
the non-dominated (Pareto) set: p is non-dominated in edict iff no
other point q in edict has an objective value that dominates p's,
using ordinary (unrelaxed) dominance. Expected sets below are
hand-derived from that definition against each dict's actual objective
values, not from running get_nondom and copying its output.

Also cross-checks get_biparetos -- a separate, bi-objective-specific
algorithm that should agree with get_nondom on any 2-objective input,
since both are computing the same mathematical object. Where they
disagree, that's reported as a finding, not silently reconciled.
"""
import pytest

from pymoso.chnutils import get_nondom, get_biparetos


# ---------------------------------------------------------------------------
# Empty and singleton -- the two trivial cases from the definition itself:
# the non-dominated set of the empty set is empty; a lone point is never
# dominated by anything, so it is always non-dominated.
# ---------------------------------------------------------------------------

def test_empty_input_disagrees_with_the_definition():
    """FINDING: the non-dominated set of the empty set is, by
    definition, the empty set -- there is no other point for anything
    to be dominated by. get_nondom does not return that: front(),
    get_nondom's recursive helper, has an `if cardP == 1: ... elif
    cardP > 1: ...` with no branch for cardP == 0, so it falls through
    and implicitly returns None; get_nondom then does
    `Mpts, Mobjs = front(...)`, which raises TypeError on that None.
    Asserting the actual (buggy) behavior here, not the correct one --
    see the phase 4 report.
    """
    with pytest.raises(TypeError):
        get_nondom({})


def test_singleton():
    assert get_nondom({(0, 0): (1, 2)}) == {(0, 0)}


def test_singleton_one_objective():
    assert get_nondom({(5,): (3,)}) == {(5,)}


# ---------------------------------------------------------------------------
# All points dominated by one -- the dominator survives, everything else
# is excluded regardless of the excluded points' relationships to each
# other.
# ---------------------------------------------------------------------------

def test_all_dominated_by_one():
    """(0,0)->(0,0) dominates all three of the others (which are
    themselves a mutually non-dominated anti-chain: (1,5),(3,3),(5,1)).
    Expected non-dominated set: just the dominator."""
    edict = {
        (0, 0): (0, 0),
        (1, 0): (1, 5),
        (2, 0): (3, 3),
        (3, 0): (5, 1),
    }
    assert get_nondom(edict) == {(0, 0)}


# ---------------------------------------------------------------------------
# All mutually non-dominated -- a proper anti-chain; every point survives.
# ---------------------------------------------------------------------------

def test_all_mutually_non_dominated():
    edict = {
        (0, 0): (1, 5),
        (1, 0): (2, 4),
        (2, 0): (3, 3),
        (3, 0): (4, 2),
        (4, 0): (5, 1),
    }
    assert get_nondom(edict) == set(edict.keys())


def test_all_mutually_non_dominated_three_objectives():
    """Unit-basis-vector anti-chain in 3 objectives: each point is
    better in exactly one objective and worse in the other two, so no
    pair is comparable."""
    edict = {
        (0, 0, 0): (1, 0, 0),
        (1, 0, 0): (0, 1, 0),
        (2, 0, 0): (0, 0, 1),
    }
    assert get_nondom(edict) == set(edict.keys())


# ---------------------------------------------------------------------------
# Duplicate objective values at distinct points -- dominance is over
# values, but the return is a set of points. Two distinct points with
# identical, otherwise-non-dominated values must BOTH survive: neither
# dominates the other (does_dominate requires strict improvement
# somewhere, which equal values never have), and nothing else dominates
# either of them.
# ---------------------------------------------------------------------------

def test_duplicate_values_both_survive_when_non_dominated():
    edict = {
        (0, 0): (1, 5),
        (1, 0): (1, 5),   # distinct point, identical value to (0,0)
        (2, 0): (5, 1),   # incomparable with both
    }
    assert get_nondom(edict) == {(0, 0), (1, 0), (2, 0)}


def test_duplicate_values_both_excluded_together_when_dominated():
    """Neither duplicate can be excluded while the other survives --
    they have the same value, so anything that dominates one dominates
    the other identically."""
    edict = {
        (0, 0): (1, 5),
        (1, 0): (1, 5),   # duplicate of (0,0)
        (2, 0): (0, 0),   # dominates both (0,0) and (1,0)
    }
    assert get_nondom(edict) == {(2, 0)}


def test_duplicate_values_one_objective():
    """Two points tied at the minimum in a single objective: both are
    non-dominated (tied, not dominated by each other), and both
    dominate the strictly worse third point."""
    edict = {(0,): (1,), (1,): (1,), (2,): (2,)}
    assert get_nondom(edict) == {(0,), (1,)}


def test_identical_objective_vector_is_the_same_as_duplicate_values():
    """Same case, stated the way the task frames it: points with
    identical objective vectors. Confirms get_nondom doesn't collapse
    them or arbitrarily drop one."""
    edict = {(10,): (7,), (20,): (7,), (30,): (7,)}
    # all three tied at the same single-objective value -> mutually
    # non-dominated -> all three survive
    assert get_nondom(edict) == {(10,), (20,), (30,)}


# ---------------------------------------------------------------------------
# get_biparetos cross-check: same mathematical object, different
# (bi-objective-specific) algorithm. Expected sets are the same
# hand-derived ones used for get_nondom above -- not derived from
# get_biparetos's own output.
# ---------------------------------------------------------------------------

def test_get_biparetos_agrees_with_get_nondom_on_antichain():
    edict = {
        (0, 0): (1, 5),
        (1, 0): (3, 3),
        (2, 0): (5, 1),
    }
    expected = {(0, 0), (1, 0), (2, 0)}
    assert get_nondom(edict) == expected
    assert get_biparetos(edict) == expected


def test_get_biparetos_agrees_with_get_nondom_on_dominated_set():
    edict = {
        (0, 0): (0, 0),
        (1, 0): (1, 5),
        (2, 0): (3, 3),
        (3, 0): (5, 1),
    }
    expected = {(0, 0)}
    assert get_nondom(edict) == expected
    assert get_biparetos(edict) == expected


def test_get_biparetos_empty_and_singleton():
    """Unlike get_nondom, get_biparetos handles the empty dict without
    raising (its dlen<=1 branch just returns set(pts))."""
    assert get_biparetos({}) == set()
    assert get_biparetos({(0, 0): (1, 2)}) == {(0, 0)}


def test_get_biparetos_disagrees_with_get_nondom_on_duplicate_values():
    """FINDING: get_biparetos silently drops all but one of a group of
    tied, mutually-non-dominated points. Its sweep only advances to a
    new candidate on a *strict* improvement in the second objective
    (`edict[bkey][1] > edict[newp][1]`); a tie never satisfies that, so
    the tied point is skipped -- never added to plist at all, since it
    also never becomes the new bkey. get_nondom does not have this
    problem (does_dominate correctly treats a tie as "does not
    dominate"). This disagrees with the mathematical definition (both
    tied, non-dominated points belong in the non-dominated set of
    points) and with get_nondom's own behavior on the identical input.
    Asserting the actual (buggy) behavior here, not the correct one --
    see the phase 4 report.
    """
    edict = {
        (0, 0): (1, 5),
        (1, 0): (1, 5),   # duplicate of (0,0)
        (2, 0): (5, 1),
    }
    correct = {(0, 0), (1, 0), (2, 0)}
    assert get_nondom(edict) == correct
    assert get_biparetos(edict) != correct
    assert len(get_biparetos(edict)) == 2  # drops exactly one of the tied pair
