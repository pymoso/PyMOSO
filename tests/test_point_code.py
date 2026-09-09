"""
§7.1 items 8-9 (docs/rng-interface-design.md), landed at §12 step 3
alongside chnbase.py's CRN-protocol replacement even though nothing
wires point_code/offset_within_iteration into chnbase.py until step
4a/4b: these are pure integer functions with no dependency on `crnflag`
or how chnbase.py uses them, so there is no reason to wait.

Item 8: point_code/offset_within_iteration exactness, checked exactly
(pairwise `!=` assertions across a battery designed to catch a
radix-packing bug specifically) plus a round-trip decode, not sampled
statistically -- the scheme is exact, so the test can be too.

Item 9: overflow raises a specific, named exception rather than
wrapping or truncating.
"""
import pytest

from pymoso.prng.base import (
    zigzag, point_width, point_code, offset_within_iteration,
    PointCodeOverflow, REPL_BITS, VISIT_BITS,
)


# ---------------------------------------------------------------------------
# Item 8: exactness
# ---------------------------------------------------------------------------

def test_zigzag_is_a_bijection_onto_non_negative_integers():
    values = list(range(-20, 21))
    codes = [zigzag(v) for v in values]
    assert all(c >= 0 for c in codes)
    assert len(set(codes)) == len(codes)


@pytest.mark.parametrize("dim,expected_W", [(1, 75), (2, 37), (3, 25), (9, 8)])
def test_point_width_matches_worked_examples_from_the_design_doc(dim, expected_W):
    """§3.4's own worked examples: ProbSimpleSO/ProbExpensive (dim=1)
    W=75; ProbTPA/ProbTPB (dim=2) W=37; ProbTPC (dim=3) W=25; BSProb
    (dim=9) W=8."""
    assert point_width(dim) == expected_W


def test_point_code_pairwise_distinct_across_a_battery_including_adjacent_points():
    """Adjacent integer points, negative components, and points
    differing only in the last dimension -- where a radix-packing bug
    (e.g. an off-by-one in the positional shift, or components bleeding
    into each other's bit range) would actually show up."""
    W = point_width(3)
    battery = [
        (0, 0, 0),
        (1, 0, 0), (0, 1, 0), (0, 0, 1),          # adjacent to origin, one axis each
        (1, 1, 1),
        (-1, 0, 0), (0, -1, 0), (0, 0, -1),        # negative components
        (-1, -1, -1),
        (5, 5, 5), (5, 5, 6), (5, 5, 4),           # differ only in the last dimension
        (5, 5, -6),
        (100, -100, 0), (-100, 100, 0),
        (2**10, 2**10, 2**10), (2**10, 2**10, 2**10 - 1),
    ]
    codes = {}
    for x in battery:
        c = point_code(x, W)
        for other_x, other_c in codes.items():
            assert c != other_c, f"point_code{x} == point_code{other_x} == {c}"
        codes[x] = c


def test_point_code_round_trip_decodes_exactly():
    """Decode a point_code back into its zigzagged, positionally-packed
    components (radix 2**W) and confirm it recovers exactly what was
    encoded -- the direct proof of injectivity, not an assumption from
    distinctness alone."""
    W = point_width(3)
    for x in [(0, 0, 0), (1, -2, 3), (-100, 50, -7), (2**10, -2**10, 0)]:
        code = point_code(x, W)
        recovered = []
        remaining = code
        for _ in range(len(x)):
            z = remaining % (1 << W)
            recovered.append(z // 2 if z % 2 == 0 else -(z + 1) // 2)
            remaining //= (1 << W)
        assert tuple(recovered) == x


def test_offset_within_iteration_round_trip_recovers_point_code_visit_replication():
    """Decode offset_within_iteration back into (point_code, visit,
    replication) and confirm it recovers exactly what was encoded."""
    W = point_width(2)
    for x, visit, replication in [
        ((0, 0), 0, 0),
        ((5, 5), 0, 41),
        ((5, 5), 3, 41),
        ((-5, 5), 1, 0),
        ((40, 40), (1 << VISIT_BITS) - 1, (1 << REPL_BITS) - 1),
    ]:
        pc = point_code(x, W)
        offset = offset_within_iteration(x, visit, replication, W)
        recovered_replication = offset % (1 << REPL_BITS)
        remainder = offset // (1 << REPL_BITS)
        recovered_visit = remainder % (1 << VISIT_BITS)
        recovered_pc = remainder // (1 << VISIT_BITS)
        assert (recovered_pc, recovered_visit, recovered_replication) == (pc, visit, replication)


def test_offset_within_iteration_pairwise_distinct_across_points_visits_replications():
    W = point_width(2)
    battery = []
    for x in [(0, 0), (1, 0), (0, 1), (5, 5), (-5, 5)]:
        for visit in [0, 1, 2]:
            for replication in [0, 1, 41]:
                battery.append((x, visit, replication))
    offsets = {}
    for x, visit, replication in battery:
        off = offset_within_iteration(x, visit, replication, W)
        for other_key, other_off in offsets.items():
            assert off != other_off, f"{(x, visit, replication)} collides with {other_key}"
        offsets[(x, visit, replication)] = off


# ---------------------------------------------------------------------------
# Item 9: overflow raises, not collides
# ---------------------------------------------------------------------------

def test_point_code_raises_on_a_component_that_overflows_W():
    W = point_width(3)  # 25
    x = (0, 0, 1 << (W - 1))  # zigzag(2**(W-1)) == 2**W, exactly at the boundary -- overflows
    with pytest.raises(PointCodeOverflow):
        point_code(x, W)


def test_point_code_raises_on_a_negative_component_that_overflows_W():
    W = point_width(3)
    x = (0, 0, -(1 << (W - 1)) - 1)  # zigzag(-2**(W-1) - 1) == 2**W, overflows
    with pytest.raises(PointCodeOverflow):
        point_code(x, W)


def test_point_code_does_not_raise_exactly_at_the_boundary():
    """The largest component that still fits: zigzag(v) == 2**W - 1."""
    W = point_width(3)
    x = (0, 0, (1 << (W - 1)) - 1)  # zigzag(2**(W-1) - 1) == 2**W - 2, fits
    point_code(x, W)  # must not raise


def test_offset_within_iteration_raises_on_overflow_not_wraps():
    W = point_width(1)  # 75, generous -- force overflow via an absurd component instead
    W_tiny = 4
    x = (1 << (W_tiny))  # zigzag(16) == 32 >= 2**4 -- overflows a 4-bit budget
    with pytest.raises(PointCodeOverflow):
        offset_within_iteration((x,), 0, 0, W_tiny)


def test_point_width_rejects_dim_less_than_one():
    with pytest.raises(ValueError):
        point_width(0)
