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


def test_get_biparetos_keeps_exactly_tied_points():
    """Two equal vectors do not dominate each other, so both belong in
    the non-dominated set. get_biparetos kept only one of a group of
    exactly tied points until 2.0 (docs/algorithm-audit.md, finding 8):
    its sweep moved on only at a strict improvement in the second
    objective. This test asserted that behaviour, as a finding, before
    the fix."""
    edict = {
        (0, 0): (1, 5),
        (1, 0): (1, 5),   # duplicate of (0,0)
        (2, 0): (5, 1),
    }
    correct = {(0, 0), (1, 0), (2, 0)}
    assert get_nondom(edict) == correct
    assert get_biparetos(edict) == correct


def test_get_biparetos_keeps_ties_anywhere_and_drops_tied_dominated_points():
    edict = {
        (0,): (0, 9), (1,): (0, 9), (2,): (0, 9),   # a tie of three, first
        (3,): (4, 4), (4,): (4, 4),                 # a tie in the middle
        (5,): (9, 0), (6,): (9, 0),                 # a tie last
        (7,): (5, 5), (8,): (5, 5),                 # tied, and dominated by (4, 4)
    }
    expected = {(0,), (1,), (2,), (3,), (4,), (5,), (6,)}
    assert get_nondom(edict) == expected
    assert get_biparetos(edict) == expected


def test_get_biparetos_agrees_with_get_nondom_on_random_ties():
    import random
    rng = random.Random(8)
    for _ in range(2000):
        n = rng.randint(1, 12)
        edict = {(i,): (rng.randint(0, 3), rng.randint(0, 3)) for i in range(n)}
        assert get_biparetos(edict) == get_nondom(edict), edict


def _get_biparetos_before_2_0(edict):
    # verbatim, before finding 8's fix; the reference for the order
    # below. Do not tidy.
    from pymoso.moso import argsort
    pts = list(edict.keys())
    vals = list(edict.values())
    sind = argsort(vals)
    g2 = 1
    dlen = len(pts)
    plist = set()
    if dlen > 1:
        i = 0
        j = 0
        while j < dlen:
            is_pareto = False
            bkey = pts[sind[i]]
            plist |= {bkey}
            j = i + 1
            while not is_pareto and j < dlen:
                newp = pts[sind[j]]
                if edict[bkey][g2] > edict[newp][g2]:
                    is_pareto = True
                    i = j
                else:
                    j += 1
    else:
        plist |= set(pts)
    return plist


def test_get_biparetos_without_ties_is_unchanged_element_and_order():
    """Solvers iterate the returned set, and the order of a set of
    tuples depends on how it was built, so without a tie the fix must
    build it exactly as before."""
    import random
    rng = random.Random(9)
    for _ in range(2000):
        n = rng.randint(1, 30)
        vals = rng.sample([(a, b) for a in range(20) for b in range(20)], n)
        edict = {(rng.randint(-50, 50), rng.randint(-50, 50), i): v for i, v in enumerate(vals)}
        assert list(get_biparetos(edict)) == list(_get_biparetos_before_2_0(edict)), edict
