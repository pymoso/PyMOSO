"""
docs/rng-interface-design.md §12 step 6c: pymoso/prng/base.py's
one_past(stream, offset, offset_capacity, stream_family_capacity) --
§8.2's "one past the maximum coordinate touched," generalized from a
flat integer to a (stream, offset) pair.

The carry (offset+1 rolling into (stream+1, 0)) is the one place this
generalization could quietly weaken §8.2's guarantee: if stream+1
belongs to a different, already-allocated family (a different isp
path's own reserved iteration range, for instance), "one past the
maximum touched" would land in territory that isn't actually free.
Every test below exercises the carry directly -- not just the common
no-carry path -- including deliberately landing exactly on the family
boundary (must not raise) and one past it (must raise), the same
"detector must be observed working, not just assumed to" discipline
this project uses throughout. This is now practically exercisable with
small numbers precisely because Philox's own strides are budget-
anchored rather than absurd (docs/rng-interface-design.md §12 step 6) --
MRG32k3a's own ISP_ITER_MARGIN=2**32 makes the same boundary real but
impractical to reach in a test with real generator machinery.
"""
import pytest

from pymoso.prng.base import one_past, StreamFamilyExceeded


def test_no_carry_when_offset_has_room():
    assert one_past(5, 10, offset_capacity=100, stream_family_capacity=1000) == (5, 11)


def test_carry_lands_on_the_next_stream_at_offset_zero():
    assert one_past(5, 99, offset_capacity=100, stream_family_capacity=1000) == (6, 0)


def test_carry_at_the_family_boundary_does_not_raise():
    """stream=998 carrying to stream=999, with stream_family_capacity=1000
    (i.e. valid streams are 0..999) -- the carry target is still inside
    the family, so this must not raise."""
    assert one_past(998, 99, offset_capacity=100, stream_family_capacity=1000) == (999, 0)


def test_carry_past_the_family_boundary_raises():
    """stream=999 carrying to stream=1000, exceeding
    stream_family_capacity=1000 -- must raise, not silently return
    (1000, 0), which would land in whatever the next family owns."""
    with pytest.raises(StreamFamilyExceeded):
        one_past(999, 99, offset_capacity=100, stream_family_capacity=1000)


def test_carry_exactly_at_the_offset_boundary_still_carries():
    """offset_capacity=100 means valid offsets are 0..99; offset=98
    advancing to 99 does not carry (99 < 100); offset=99 advancing
    carries, since 99+1 == offset_capacity, not < it."""
    assert one_past(5, 98, offset_capacity=100, stream_family_capacity=1000) == (5, 99)
    assert one_past(5, 99, offset_capacity=100, stream_family_capacity=1000) == (6, 0)


def test_family_capacity_none_never_raises():
    """A caller can deliberately leave a family unbounded (MRG's own
    sync axis, which relies on remaining period headroom instead of an
    explicit family cap, §8.2) -- one_past must never raise in that
    case, at any stream value."""
    assert one_past(10 ** 18, 99, offset_capacity=100, stream_family_capacity=None) == (10 ** 18 + 1, 0)


def test_family_capacity_one_forces_every_carry_to_raise():
    """stream_family_capacity=1 means only stream=0 is ever valid --
    any carry (which always targets stream+1 >= 1) must raise."""
    with pytest.raises(StreamFamilyExceeded):
        one_past(0, 99, offset_capacity=100, stream_family_capacity=1)


def test_tuple_comparison_matches_flat_integer_comparison():
    """The property one_past's own use in get_endseed() (§8.2) depends
    on: comparing (stream, offset) pairs with Python's own tuple
    comparison must agree with comparing the equivalent flat integers
    (stream*STRIDE + offset), for every pair where offset < STRIDE --
    checked directly across a battery, not assumed from the shape of
    tuple comparison alone."""
    STRIDE = 1000
    pairs = [(0, 0), (0, 999), (1, 0), (1, 500), (2, 0), (0, 500), (1, 999)]
    for a in pairs:
        for b in pairs:
            flat_a = a[0] * STRIDE + a[1]
            flat_b = b[0] * STRIDE + b[1]
            assert (a < b) == (flat_a < flat_b), f"{a} vs {b} disagrees with flat comparison"
            assert (a > b) == (flat_a > flat_b), f"{a} vs {b} disagrees with flat comparison"
