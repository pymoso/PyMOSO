"""
Regression coverage for docs/rng-interface-design.md's §12 step
6c-completion: the point/visit/replication *packing* offset_within_
iteration performs is generator-agnostic, but the bit-width *budget*
it packs into is not -- it is a property of the selected generator's
own capacity.

Before this step, pymoso.prng.philox4x32 had no point_width/
offset_within_iteration of its own -- the only assembly available was
pymoso.prng.base's, sized to MRG-family's 127-bit budget (point 75 +
visit 6 + repl-count 32 + repl-reserve 14, matching ITER_STRIDE=2**127).
A point large enough to need close to base.py's own 75-bit point
budget, but still safely under it, silently exceeds Philox's own,
smaller 118-bit OFFSET_CAPACITY once packed -- and nothing catches it:
philox4x32.stream_at's own bounds check is against COUNTER_BITS
(2**128, the raw hardware limit), not OFFSET_CAPACITY, which until this
step was a documented constant nothing actually enforced.
test_shared_base_budget_silently_exceeds_philox_own_capacity below
demonstrates this using only code that predates this step -- no
exception anywhere, which is the defect, not a confusing one.

test_philox_scoped_point_overflow_is_named_and_caught_at_assembly is
the actual regression gate: observed failing before this step landed
(philox4x32 had no point_width/offset_within_iteration to import at
all), it now confirms the identical oversized point is rejected by
Philox's own, correctly-scoped PointCodeOverflow, at assembly time,
before stream_at ever sees it.

NOT covered here, and not this step's own scope (see philox4x32.py's
own module comment above POINT_BITS): nothing in chnbase.py calls
philox4x32.point_width/offset_within_iteration yet -- Oracle's own
coordinate assembly still calls pymoso.prng.base's unconditionally,
with no generator-selection argument at all. This step proves the
mechanism is correct in isolation; §12 step 6b is what wires a selected
generator through Oracle's own internals so this budget is actually
honored on a real solve()/testsolve() run.
"""
import pytest

from pymoso.prng import base as prng_base
from pymoso.prng import philox4x32


# A dim=1 point whose zigzag encoding is 2**73: fits comfortably under
# base.py's own 75-bit point budget (limit 2**75) but not under
# Philox's own 72-bit one (limit 2**72) -- checked directly against
# both limits below, not a boundary picked to just barely trip either
# check by luck.
_OVERSIZED_X = (2 ** 72,)


def test_shared_base_budget_silently_exceeds_philox_own_capacity():
    """The defect this step exists to fix: base.py's own checks pass
    (the point fits its 75-bit budget), the resulting offset exceeds
    Philox's own declared 118-bit OFFSET_CAPACITY, and nothing catches
    it -- stream_at's own bounds check is against COUNTER_BITS
    (2**128), not OFFSET_CAPACITY. Confirmed directly: stream_at
    accepts the oversized offset with no error at all."""
    W = prng_base.point_width(1)
    assert W == 75
    offset = prng_base.offset_within_iteration(_OVERSIZED_X, 0, 0, W)
    assert offset >= philox4x32.OFFSET_CAPACITY
    assert offset < (1 << philox4x32.COUNTER_BITS)
    philox4x32.stream_at((0, 0), 0, offset)  # must NOT raise -- that's the defect


def test_philox_scoped_point_overflow_is_named_and_caught_at_assembly():
    """The fix: Philox's own point_width/offset_within_iteration, using
    its own 72-bit point budget, reject the identical point at
    assembly time with the correctly-scoped, named exception -- before
    stream_at (or anything else) ever sees it."""
    W = philox4x32.point_width(1)
    assert W == 72
    with pytest.raises(prng_base.PointCodeOverflow):
        philox4x32.offset_within_iteration(_OVERSIZED_X, 0, 0, W)


def test_philox_scoped_realistic_point_fits():
    """A BSProb-scale point (dim=9, the tightest built-in problem)
    through Philox's own offset assembly produces an offset stream_at
    accepts without raising -- confirms the fix doesn't just relabel
    the failure, ordinary use actually fits the tighter budget, with
    the same per-component width BSProb already gets under base.py's
    own (wider) budget."""
    x = (3, -2, 5, 0, 1, -4, 2, 3, -1)
    assert len(x) == 9
    W = philox4x32.point_width(len(x))
    assert W == 8  # 72 // 9, same as base.py's 75 // 9 -- BSProb's own W is unchanged
    offset = philox4x32.offset_within_iteration(x, 0, 0, W)
    assert offset < philox4x32.OFFSET_CAPACITY
    philox4x32.stream_at((0, 0), 0, offset)  # must not raise


def test_default_offset_within_iteration_unchanged():
    """base.offset_within_iteration's default behavior (no generator-
    scoped kwargs given) must stay byte-identical after generalizing it
    to accept per-generator bit widths -- no existing (MRG-only) caller
    may move. Computed independently here, not by calling the function
    against itself."""
    x = (4, 14)
    visit, replication = 0, 3
    W = prng_base.point_width(len(x))
    assert W == 75 // 2
    expected = (
        prng_base.point_code(x, W) * (1 << (6 + 32 + 14))
        + visit * (1 << (32 + 14))
        + replication * (1 << 14)
    )
    assert prng_base.offset_within_iteration(x, visit, replication, W) == expected
