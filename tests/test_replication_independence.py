"""
A defect found while planning docs/rng-interface-design.md §12 step 8
(before any step-8 code was written): the crnflag=False default path's
replications are NOT independent whenever g() draws more than one raw
value, which is the common case (ProbTPA/ProbTPB/ProbTPC each draw 3
normalvariate()s; BSProb draws ~1000 expovariate()s per replication,
see below) -- not a hypothetical edge case.

Root cause: offset_within_iteration (pymoso/prng/base.py) packs
`replication` as its coordinate's lowest-order field with stride 1 --
replication i's starting coordinate is exactly one raw recurrence step
past replication i-1's. That was written under the stated assumption
("consecutive replications are exactly one raw recurrence step apart",
see chnbase.py's _hit_via_coordinate docstring, pre-fix) that a single
replication consumes exactly one raw draw. Nothing enforces that
assumption, and no built-in problem satisfies it. The result: if
replication i-1's g() call draws k > 1 raw values, its own consumption
runs into the coordinate positions reserved (with zero margin) for
replications i, i+1, ..., i+k-2 -- those replications then don't start
an independent stream, they start partway through replication i-1's
own draws.

Confirmed directly (see the design-doc writeup and commit message for
the reproduction): with ProbTPA's g() (3 normalvariate() calls, each
exactly one raw MRG32k3a step -- MRG32k3a.normalvariate() calls
random() once, mrg32k3a.py:502-523), replication 1's first two draws
were found to be bit-identical to replication 0's second and third
draws.

Why the existing coverage (tests/test_oracle_noncrn_default.py) didn't
catch this: every g() double in that file (LoggingOracle) reads
rng.get_seed()[0] and returns -- it never calls random()/normalvariate()/
getrandbits(), so it never actually draws from the stream it's handed.
The disjointness assertions there compare *starting coordinates* across
replications (genuinely distinct, by construction) rather than *drawn
values* -- they verify the property named (distinct starting points)
rather than the property that actually matters (no replication reads a
value another replication also read). This is the second instance of
that exact failure mode in the RNG work -- the first is
docs/end-seed-scope.md's finding that end-seed goldens don't fingerprint
a run's randomness at all. Recorded together in
docs/rng-interface-design.md's step 8 prerequisite writeup.

test_replications_do_not_share_raw_draws below is the fix's own
regression test: a double whose g() draws multiple raw values, checked
for cross-replication overlap directly on drawn values, not on starting
positions. Confirmed to fail against the pre-fix code (offset_within_
iteration's stride-1 replication packing) before the fix landed -- see
the commit history for this file.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.prng.base import (
    ReplicationDrawOverflow, ReplicationOverflow, VisitOverflow,
    offset_within_iteration, REPL_RESERVE_BITS, REPL_COUNT_BITS, VISIT_BITS,
)

ROOT = (12345, 12345, 12345, 12345, 12345, 12345)


class MultiDrawOracle(Oracle):
    """g() draws `draws_per_rep` raw values (default 3, matching
    ProbTPA's own draw count) and logs every one of them -- unlike
    test_oracle_noncrn_default.py's LoggingOracle, which never actually
    draws from the stream it's handed."""

    draws_per_rep = 3

    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        vals = [rng.normalvariate(0, 1) for _ in range(self.draws_per_rep)]
        self.log.append(tuple(vals))
        return True, (vals[0],)


def _fresh_oracle(dim=1, draws_per_rep=3):
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = MultiDrawOracle(rng, dim=dim)
    orc.draws_per_rep = draws_per_rep
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


def test_replications_do_not_share_raw_draws():
    """The concrete failure this file exists to catch: two different
    replications of the same point, under the crnflag=False default
    path, must never both read the same raw drawn value -- checked as
    set-disjointness over every raw value actually drawn (not over
    starting coordinates, which is what the pre-existing coverage
    checked and is not the property that matters)."""
    orc = _fresh_oracle(dim=1, draws_per_rep=3)
    orc.hit((5,), 4)
    seen = set()
    for replication_draws in orc.log:
        assert seen.isdisjoint(replication_draws), (
            'replication draws overlapped -- replications are not '
            'independent. All draws so far: {0}; this replication: '
            '{1}'.format(seen, replication_draws)
        )
        seen.update(replication_draws)


def test_replications_do_not_share_raw_draws_heavier_problem():
    """Same property, at BSProb's own scale (~1000 draws/replication,
    see docs/rng-interface-design.md's step 8 prerequisite writeup for
    where that figure comes from) -- confirms the fix's reserve
    actually covers the heaviest built-in problem, not just a small
    illustrative draws_per_rep."""
    orc = _fresh_oracle(dim=1, draws_per_rep=1000)
    orc.hit((5,), 3)
    seen = set()
    for replication_draws in orc.log:
        assert seen.isdisjoint(replication_draws)
        seen.update(replication_draws)


# ---------------------------------------------------------------------------
# The reserve is finite (2**REPL_RESERVE_BITS raw draws/replication) --
# exceeding it must raise, not silently overlap the next replication's
# block (the user's explicit choice: "I'd want the raise").
# ---------------------------------------------------------------------------

class OverflowOracle(Oracle):
    """g() draws far more than 2**REPL_RESERVE_BITS raw values."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        for _ in range((1 << REPL_RESERVE_BITS) + 1):
            rng.random()
        return True, (0.0,)


def test_exceeding_the_replication_reserve_raises():
    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = OverflowOracle(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    with pytest.raises(ReplicationDrawOverflow):
        orc.hit((1,), 2)


def test_exceeding_the_replication_reserve_by_exactly_the_reserve_does_not_raise():
    """Drawing exactly 2**REPL_RESERVE_BITS values fills the reserved
    block without touching the next replication's starting position --
    the boundary itself must not raise, only exceeding it."""
    class ExactOracle(Oracle):
        def __init__(self, rng):
            self.num_obj = 1
            self.dim = 1
            super().__init__(rng)

        def g(self, x, rng):
            for _ in range(1 << REPL_RESERVE_BITS):
                rng.random()
            return True, (0.0,)

    rng = MRG32k3a(ROOT)
    rng.set_class_cache(False)
    orc = ExactOracle(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    orc.hit((1,), 2)  # must not raise


# ---------------------------------------------------------------------------
# visit/replication bounds, unenforced before this fix (found in the same
# audit): exceeding them must raise rather than silently overflow into
# the neighboring field (point_code's own established posture, §3.4).
# ---------------------------------------------------------------------------

def test_visit_overflow_raises():
    with pytest.raises(VisitOverflow):
        offset_within_iteration((1,), 1 << VISIT_BITS, 0, W=8)


def test_visit_at_the_boundary_does_not_raise():
    offset_within_iteration((1,), (1 << VISIT_BITS) - 1, 0, W=8)  # must not raise


def test_replication_count_overflow_raises():
    with pytest.raises(ReplicationOverflow):
        offset_within_iteration((1,), 0, 1 << REPL_COUNT_BITS, W=8)


def test_replication_count_at_the_boundary_does_not_raise():
    offset_within_iteration((1,), 0, (1 << REPL_COUNT_BITS) - 1, W=8)  # must not raise


def test_visit_and_replication_overflow_do_not_collide_with_each_other():
    """A too-large replication must not silently read as a valid but
    wrong visit value, and vice versa -- each check is independent."""
    with pytest.raises(ReplicationOverflow):
        offset_within_iteration((1,), 5, 1 << REPL_COUNT_BITS, W=8)
    with pytest.raises(VisitOverflow):
        offset_within_iteration((1,), 1 << VISIT_BITS, 5, W=8)
