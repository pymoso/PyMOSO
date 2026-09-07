"""
Unit tests for does_weak_dominate/does_dominate/does_strict_dominate,
derived directly from the mathematical definitions of (epsilon-relaxed)
Pareto dominance for minimization, per Cooper, Hunter & Nagaraj (2018),
not from running the functions to see what they return. Every expected
value below is hand-computed from:

    weak:   g1 weakly dominates g2   iff  g1[i] - d1[i] <= g2[i] + d2[i]  for all i
    ordinary: g1 dominates g2        iff  weak(g1, g2)  AND  NOT (g1[i]-d1[i] == g2[i]+d2[i] for all i)
    strict: g1 strictly dominates g2 iff  g1[i] - d1[i] <  g2[i] + d2[i]  for all i

If a test here ever needs to be "fixed" by running the code and copying
its output, that defeats the point of the file -- don't.
"""
from pymoso.chnutils import does_weak_dominate, does_dominate, does_strict_dominate

ZERO2 = (0, 0)
ZERO3 = (0, 0, 0)
ZERO1 = (0,)


# ---------------------------------------------------------------------------
# Identical points -- the reflexive/boundary case for all three predicates
# ---------------------------------------------------------------------------

def test_identical_points_weak_true_ordinary_false_strict_false():
    """g == g: weak dominance is reflexive (<=); ordinary dominance
    excludes full equality; strict dominance needs strict inequality
    everywhere, which equality never satisfies."""
    g = (3, 4)
    assert does_weak_dominate(g, g, ZERO2, ZERO2) is True
    assert does_dominate(g, g, ZERO2, ZERO2) is False
    assert does_strict_dominate(g, g, ZERO2, ZERO2) is False


def test_identical_points_1d_and_3d():
    assert does_weak_dominate((5,), (5,), ZERO1, ZERO1) is True
    assert does_dominate((5,), (5,), ZERO1, ZERO1) is False
    assert does_strict_dominate((5,), (5,), ZERO1, ZERO1) is False

    g = (1, 2, 3)
    assert does_weak_dominate(g, g, ZERO3, ZERO3) is True
    assert does_dominate(g, g, ZERO3, ZERO3) is False
    assert does_strict_dominate(g, g, ZERO3, ZERO3) is False


# ---------------------------------------------------------------------------
# Boundary: tied in some objectives, strictly better in others
# ---------------------------------------------------------------------------

def test_tied_in_one_objective_2d():
    """g1=(1,2) vs g2=(2,2): better in obj0, tied in obj1.
    weak: 1<=2 and 2<=2 -> True. ordinary: weak and not-all-equal
    (1!=2) -> True. strict: needs < in every objective; obj1 is tied
    (2 < 2 is False) -> False."""
    g1, g2 = (1, 2), (2, 2)
    assert does_weak_dominate(g1, g2, ZERO2, ZERO2) is True
    assert does_dominate(g1, g2, ZERO2, ZERO2) is True
    assert does_strict_dominate(g1, g2, ZERO2, ZERO2) is False


def test_tied_in_two_of_three_objectives():
    """g1=(1,2,3) vs g2=(1,2,4): tied in obj0,obj1, better in obj2."""
    g1, g2 = (1, 2, 3), (1, 2, 4)
    assert does_weak_dominate(g1, g2, ZERO3, ZERO3) is True
    assert does_dominate(g1, g2, ZERO3, ZERO3) is True
    assert does_strict_dominate(g1, g2, ZERO3, ZERO3) is False


# ---------------------------------------------------------------------------
# Full/strict domination and incomparable points
# ---------------------------------------------------------------------------

def test_full_domination_all_three_true():
    """g1 strictly better in every objective -> all three predicates True."""
    g1, g2 = (1, 1), (2, 2)
    assert does_weak_dominate(g1, g2, ZERO2, ZERO2) is True
    assert does_dominate(g1, g2, ZERO2, ZERO2) is True
    assert does_strict_dominate(g1, g2, ZERO2, ZERO2) is True

    g1, g2 = (1, 2, 3), (2, 3, 4)
    assert does_weak_dominate(g1, g2, ZERO3, ZERO3) is True
    assert does_dominate(g1, g2, ZERO3, ZERO3) is True
    assert does_strict_dominate(g1, g2, ZERO3, ZERO3) is True


def test_incomparable_points_all_three_false():
    """g1=(1,5) vs g2=(5,1): better in one objective, worse in the
    other -- neither weakly dominates the other (each fails at least
    one component), so ordinary and strict are false too."""
    g1, g2 = (1, 5), (5, 1)
    assert does_weak_dominate(g1, g2, ZERO2, ZERO2) is False
    assert does_dominate(g1, g2, ZERO2, ZERO2) is False
    assert does_strict_dominate(g1, g2, ZERO2, ZERO2) is False
    # symmetric: g2 doesn't dominate g1 either
    assert does_weak_dominate(g2, g1, ZERO2, ZERO2) is False


def test_incomparable_in_three_objectives():
    """g1=(1,5,3) vs g2=(2,3,4): better in obj0 and obj2, worse in
    obj1 -- incomparable."""
    g1, g2 = (1, 5, 3), (2, 3, 4)
    assert does_weak_dominate(g1, g2, ZERO3, ZERO3) is False
    assert does_dominate(g1, g2, ZERO3, ZERO3) is False
    assert does_strict_dominate(g1, g2, ZERO3, ZERO3) is False


def test_single_objective_smaller_dominates_larger():
    """With one objective, weak dominance is just <=, ordinary is <,
    and strict is also < (they coincide when there's only one
    objective to be "all" of)."""
    assert does_weak_dominate((1,), (2,), ZERO1, ZERO1) is True
    assert does_dominate((1,), (2,), ZERO1, ZERO1) is True
    assert does_strict_dominate((1,), (2,), ZERO1, ZERO1) is True
    # and the reverse does not hold
    assert does_weak_dominate((2,), (1,), ZERO1, ZERO1) is False


# ---------------------------------------------------------------------------
# strict implies ordinary implies weak, for the same inputs
# ---------------------------------------------------------------------------

RELATIONSHIP_CASES = [
    ((1, 1), (2, 2)),      # full domination
    ((1, 2), (2, 2)),      # partial (tied in one objective)
    ((3, 3), (3, 3)),      # identical
    ((1, 5), (5, 1)),      # incomparable
    ((1, 2, 3), (2, 3, 4)),
    ((1,), (2,)),
    ((2,), (2,)),
]


def test_strict_implies_ordinary_implies_weak():
    for g1, g2 in RELATIONSHIP_CASES:
        d1 = d2 = tuple(0 for _ in g1)
        weak = does_weak_dominate(g1, g2, d1, d2)
        ordinary = does_dominate(g1, g2, d1, d2)
        strict = does_strict_dominate(g1, g2, d1, d2)
        if strict:
            assert ordinary, (g1, g2, "strict but not ordinary")
        if ordinary:
            assert weak, (g1, g2, "ordinary but not weak")


# ---------------------------------------------------------------------------
# Relaxation parameters: zero (already covered above), positive, and
# negative. calc_delta(se) = se / m**betadel in RLESolver is always
# non-negative for real (se>=0, m>0) inputs, so negative relaxation is
# not reachable through that call path -- but the function itself
# places no restriction on sign, so it's tested here for robustness.
# ---------------------------------------------------------------------------

def test_positive_relaxation_can_make_a_worse_point_weakly_dominate():
    """g1=(3,) is worse than g2=(2,) with no relaxation. Relaxing g1
    downward by 2 (pretending it could be as low as 1) is enough to
    make it weakly dominate: 2 + 0 < 1 is False, so is_dom stays True."""
    g1, g2 = (3,), (2,)
    assert does_weak_dominate(g1, g2, (0,), (0,)) is False
    assert does_weak_dominate(g1, g2, (2,), (0,)) is True


def test_negative_relaxation_tightens_not_reachable_via_calc_delta():
    """g1=(1,) ordinarily dominates g2=(2,) with no relaxation.
    Negative delta1 makes g1 - delta1 *larger* (subtracting a negative
    number), tightening the comparison against g1. A small negative
    delta1 isn't enough to flip it; a large enough one is.

    Not reachable in practice: RLESolver.calc_delta(se) = se / m**betadel
    is always >= 0 for real standard errors and positive sample sizes.
    """
    g1, g2 = (1,), (2,)
    assert does_weak_dominate(g1, g2, (0,), (0,)) is True
    assert does_weak_dominate(g1, g2, (-0.5,), (0,)) is True  # 1-(-0.5)=1.5 <= 2
    assert does_weak_dominate(g1, g2, (-1.5,), (0,)) is False  # 1-(-1.5)=2.5 > 2


def test_negative_relaxation_on_g2_also_tightens():
    """Symmetric to the above: negative delta2 makes g2 + delta2
    *smaller*, also tightening the comparison."""
    g1, g2 = (1,), (2,)
    assert does_weak_dominate(g1, g2, (0,), (0,)) is True
    assert does_weak_dominate(g1, g2, (0,), (-1.5,)) is False  # 2+(-1.5)=0.5 < 1


def test_zero_relaxation_is_the_unrelaxed_case():
    """Zero relaxation should reproduce plain (unrelaxed) dominance --
    a sanity check that (0,...,0) is truly a no-op, not just "small"."""
    for g1, g2 in RELATIONSHIP_CASES:
        d = tuple(0 for _ in g1)
        d_float = tuple(0.0 for _ in g1)
        assert does_weak_dominate(g1, g2, d, d) == does_weak_dominate(g1, g2, d_float, d_float)
        assert does_dominate(g1, g2, d, d) == does_dominate(g1, g2, d_float, d_float)
        assert does_strict_dominate(g1, g2, d, d) == does_strict_dominate(g1, g2, d_float, d_float)
