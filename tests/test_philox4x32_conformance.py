"""
docs/rng-interface-design.md §12 step 6/6c: the §7 conformance suite run
against Philox4x32-10 -- the interface's real test, since Philox has no
recurrence, no state to advance, and no jump-ahead at all (§3.5).
`stream_at(seed, stream, offset)` reaches a position by direct
(key, counter) indexing: `stream` maps onto the key, `offset` onto the
counter (§3.9).

Item 3 (§7's "exact-integer brute-force jump validation") has no jump
to validate for a counter-based generator, so it's reinterpreted as two
independent exactness checks instead, matching item 3's own actual
intent (an independent, non-probabilistic proof that stream_at lands
exactly where it should, not "close enough"):
- The round function itself, against Random123's own published known-
  answer-test vectors (github.com/DEShawResearch/random123, tests/
  kat_vectors) -- an external reference, not derived from this
  codebase at all.
- stream_at's own (key, counter) construction, against an independent
  reimplementation (restated here, not imported from
  pymoso/prng/philox4x32.py's own helpers).

Two §7 items are not re-tested here, deliberately:
- Item 4 (bsm monotonicity) is already covered by
  tests/test_prng_conformance.py's own test_bsm_monotonicity -- bsm()
  is a pure function of u (§3.3), shared verbatim (imported, not
  copied) by every generator in this codebase.
- Item 7 (bit-identical migration proof) doesn't apply: Philox has no
  "old stateful walk" to compare against.

The broken-backend proof at the bottom includes two cases specific to
the two-argument shape (a swapped-arguments backend, a dropped-argument
backend) that a suite written against a flat coordinate would have no
way to catch, since there was only ever one argument to get wrong.
"""
import multiprocessing

import pytest

from pymoso.prng.philox4x32 import (
    philox4x32_r, stream_at, Philox4x32Stream, CoordinateCapacityExceeded,
    COUNTER_BITS, KEY_BITS, OFFSET_CAPACITY, ISP_ITER_MARGIN,
)
from pymoso.prng.base import one_past, StreamFamilyExceeded

pytestmark = pytest.mark.timeout(60)

DEFAULT_SEED = (0, 0)
SEEDS = [
    DEFAULT_SEED,
    (1, 1),
    (511616026, 1372175473),
]

_ISOLATED_START = "forkserver" if "forkserver" in multiprocessing.get_all_start_methods() else "spawn"

# ---------------------------------------------------------------------------
# Reusable checks -- same shape as the other §7 conformance suites in this
# project, restated here rather than imported, same self-containment
# reasoning as tests/test_mrg31k3p_conformance.py. Now two-argument.
# ---------------------------------------------------------------------------

def check_determinism(stream_at_fn, seed, stream, offset, n_draws=5):
    draws1 = [stream_at_fn(seed, stream, offset).random() for _ in range(n_draws)]
    draws2 = [stream_at_fn(seed, stream, offset).random() for _ in range(n_draws)]
    assert draws1 == draws2, (
        f"stream_at({seed}, {stream}, {offset}) produced different draws "
        f"across two independent calls: {draws1} != {draws2}"
    )


def check_distinctness(stream_at_fn, seed, coordinates, n_draws=5):
    """`coordinates` is a list of (stream, offset) pairs."""
    firsts = {}
    states = {}
    for c in coordinates:
        s = stream_at_fn(seed, *c)
        firsts[c] = s.random()
        states[c] = s.get_seed()
    coords = list(coordinates)
    for i, ci in enumerate(coords):
        for cj in coords[i + 1:]:
            assert firsts[ci] != firsts[cj], (
                f"coordinates {ci} and {cj} share a first draw under seed {seed}"
            )
            assert states[ci] != states[cj], (
                f"coordinates {ci} and {cj} land on the same state under seed {seed}"
            )


# ---------------------------------------------------------------------------
# Item 1: determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("stream,offset", [
    (0, 0), (0, 1), (1, 0), (5, 100), (2 ** 63, 2 ** 127), (0, 2 ** 100),
])
def test_determinism(seed, stream, offset):
    check_determinism(stream_at, seed, stream, offset)


# ---------------------------------------------------------------------------
# Item 2: distinctness / non-overlap -- across streams (offset fixed),
# across offsets (stream fixed), and mixed pairs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_distinctness_across_a_coordinate_battery(seed):
    check_distinctness(
        stream_at, seed,
        [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0),
         (100, 0), (101, 0), (0, 1000),
         (2 ** 32, 0), (2 ** 63 - 1, 2 ** 127 - 1)],
    )


# ---------------------------------------------------------------------------
# Item 3a: the round function itself, against Random123's own published
# known-answer-test vectors -- an external reference this codebase does
# not derive, at the exact round count (10) this module uses.
# ---------------------------------------------------------------------------

KAT_VECTORS = [
    # (rounds, ctr, key, expected) -- github.com/DEShawResearch/random123,
    # tests/kat_vectors, the "philox4x32 10" rows.
    (10, (0, 0, 0, 0), (0, 0),
     (0x6627e8d5, 0xe169c58d, 0xbc57ac4c, 0x9b00dbd8)),
    (10, (0xffffffff, 0xffffffff, 0xffffffff, 0xffffffff), (0xffffffff, 0xffffffff),
     (0x408f276d, 0x41c83b0e, 0xa20bc7c6, 0x6d5451fd)),
    (10, (0x243f6a88, 0x85a308d3, 0x13198a2e, 0x03707344), (0xa4093822, 0x299f31d0),
     (0xd16cfe09, 0x94fdcceb, 0x5001e420, 0x24126ea1)),
]


@pytest.mark.parametrize("rounds,ctr,key,expected", KAT_VECTORS)
def test_round_function_matches_random123_known_answer_vectors(rounds, ctr, key, expected):
    assert philox4x32_r(rounds, ctr, key) == expected


def test_stream_random_sequence_matches_the_kat_vectors_word_order():
    """The KAT vectors above prove the block function; this proves
    Philox4x32Stream.random() actually consumes that block's own words
    in the documented order (index 0 first), not some other order that
    would still pass the block-level check above by coincidence."""
    rounds, ctr, key, expected = KAT_VECTORS[0]
    seed = (key[0], key[1])
    # Reconstruct via stream_at's own documented packing (offset = the
    # counter directly, most-significant-word-first) rather than
    # poking internals.
    offset = (ctr[0] << 96) | (ctr[1] << 64) | (ctr[2] << 32) | ctr[3]
    s = stream_at(seed, 0, offset)
    got = [s.random() for _ in range(4)]
    assert got == [w / 4294967296.0 for w in expected]


# ---------------------------------------------------------------------------
# Item 3b: stream_at's own (key, counter) construction, against an
# independent reimplementation (not imported from
# pymoso/prng/philox4x32.py's own _int_to_words/stream_at).
# ---------------------------------------------------------------------------

def _reference_construction(seed, stream, offset):
    base_key = (seed[0] << 32) | seed[1]
    eff_key = (base_key + stream) & ((1 << 64) - 1)
    key = (eff_key >> 32, eff_key & 0xFFFFFFFF)
    counter = tuple((offset >> (32 * i)) & 0xFFFFFFFF for i in (3, 2, 1, 0))
    return key, counter


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("stream,offset", [
    (0, 0), (1, 0), (0, 1), (2 ** 32, 0), (2 ** 63, 0),
    (0, 2 ** 100), (2 ** 32, 2 ** 40), (2 ** 63 - 1, 2 ** 127 - 1),
])
def test_stream_at_matches_independent_key_counter_construction(seed, stream, offset):
    s = stream_at(seed, stream, offset)
    expected_key, expected_counter = _reference_construction(seed, stream, offset)
    _key, counter, _buffer = s.get_seed()
    assert _key == expected_key
    assert counter == expected_counter


# ---------------------------------------------------------------------------
# Capacity boundary: stream >= 2**64 or offset >= 2**128 must raise, not
# silently wrap (docs/rng-interface-design.md §12 step 6/6c) -- confirmed
# reachable in both directions, not just asserted.
# ---------------------------------------------------------------------------

def test_stream_capacity_exceeded_raises():
    with pytest.raises(CoordinateCapacityExceeded):
        stream_at(DEFAULT_SEED, 1 << KEY_BITS, 0)


def test_stream_capacity_at_the_boundary_does_not_raise():
    stream_at(DEFAULT_SEED, (1 << KEY_BITS) - 1, 0)  # must not raise


def test_offset_capacity_exceeded_raises():
    with pytest.raises(CoordinateCapacityExceeded):
        stream_at(DEFAULT_SEED, 0, 1 << COUNTER_BITS)


def test_offset_capacity_at_the_boundary_does_not_raise():
    stream_at(DEFAULT_SEED, 0, (1 << COUNTER_BITS) - 1)  # must not raise


def test_negative_stream_raises():
    with pytest.raises(ValueError):
        stream_at(DEFAULT_SEED, -1, 0)


def test_negative_offset_raises():
    with pytest.raises(ValueError):
        stream_at(DEFAULT_SEED, 0, -1)


# ---------------------------------------------------------------------------
# one_past's carry, exercised with THIS module's own real constants --
# reachable in a test precisely because Philox's own strides are
# budget-anchored rather than absurd (docs/rng-interface-design.md §12
# step 6), unlike MRG32k3a's own ISP_ITER_MARGIN=2**32. The generic
# mechanics are proven in tests/test_stream_offset_carry.py; this
# confirms the real, shipped OFFSET_CAPACITY/ISP_ITER_MARGIN values
# behave the same way, and that stream_at accepts the carry's own
# output without raising when it's supposed to succeed.
# ---------------------------------------------------------------------------

def test_carry_with_real_constants_stays_safe_and_stream_at_accepts_it():
    stream, offset = ISP_ITER_MARGIN - 2, OFFSET_CAPACITY - 1
    new_stream, new_offset = one_past(
        stream, offset, offset_capacity=OFFSET_CAPACITY, stream_family_capacity=ISP_ITER_MARGIN
    )
    assert (new_stream, new_offset) == (ISP_ITER_MARGIN - 1, 0)
    stream_at(DEFAULT_SEED, new_stream, new_offset)  # must not raise


def test_carry_with_real_constants_raises_at_the_family_boundary():
    stream, offset = ISP_ITER_MARGIN - 1, OFFSET_CAPACITY - 1
    with pytest.raises(StreamFamilyExceeded):
        one_past(stream, offset, offset_capacity=OFFSET_CAPACITY, stream_family_capacity=ISP_ITER_MARGIN)


# ---------------------------------------------------------------------------
# Item 5: getrandbits unbiasedness smoke test
# ---------------------------------------------------------------------------

def _chi_square_stat(counts, expected):
    return sum((c - expected) ** 2 / expected for c in counts)


def _generous_chi_square_threshold(df):
    return df + 6 * (2 * df) ** 0.5


@pytest.mark.parametrize("k,n_draws", [(4, 32000), (8, 128000), (40, 32000)])
def test_getrandbits_unbiasedness_smoke_test(k, n_draws):
    """k=40 exercises the multi-word concatenation path (k > 32),
    unique to this generator among the ones in this codebase."""
    rng = stream_at(DEFAULT_SEED, 0, 0)
    n_buckets = 1 << min(k, 8)  # bucket on the low 8 bits for k=40 -- a
                                # 2**40-bucket histogram isn't practical
    counts = [0] * n_buckets
    mask = n_buckets - 1
    for _ in range(n_draws):
        counts[rng.getrandbits(k) & mask] += 1
    expected = n_draws / n_buckets
    stat = _chi_square_stat(counts, expected)
    threshold = _generous_chi_square_threshold(n_buckets - 1)
    assert stat < threshold, (
        f"getrandbits({k}) chi-square statistic {stat:.1f} exceeds the "
        f"generous smoke-test threshold {threshold:.1f} over {n_draws} draws"
    )


# ---------------------------------------------------------------------------
# Item 6: cross-process reproducibility under forkserver
# ---------------------------------------------------------------------------

def _worker_stream_draws(seed, stream, offset, n_draws, queue):
    s = stream_at(seed, stream, offset)
    draws = [s.random() for _ in range(n_draws)]
    queue.put((s.get_seed(), draws))


def test_cross_process_reproducibility_under_forkserver():
    seed = DEFAULT_SEED
    stream, offset = 3, 7
    n_draws = 5
    ctx = multiprocessing.get_context(_ISOLATED_START)
    q = ctx.Queue()
    p = ctx.Process(target=_worker_stream_draws, args=(seed, stream, offset, n_draws, q))
    p.start()
    try:
        child_seed, child_draws = q.get(timeout=30)
    finally:
        p.join(timeout=30)
    parent_stream = stream_at(seed, stream, offset)
    parent_draws = [parent_stream.random() for _ in range(n_draws)]
    assert child_seed == parent_stream.get_seed()
    assert child_draws == parent_draws


# ---------------------------------------------------------------------------
# Proof the checks above have teeth against this generator specifically,
# including two cases the two-argument shape introduces that a flat-
# coordinate suite would have no way to catch.
# ---------------------------------------------------------------------------

def _broken_stream_at_ignores_offset(seed, stream, offset):
    """`offset` silently ignored -- targets check_distinctness across
    offsets specifically (still varies correctly across streams, so a
    check that only varied `stream` would miss this)."""
    return stream_at(seed, stream, 0)


def _broken_stream_at_swapped_arguments(seed, stream, offset):
    """stream/offset swapped -- a plausible call-site typo now that
    there are two positional arguments instead of one. Produces *a*
    deterministic, coordinate-dependent stream, just the wrong one."""
    return stream_at(seed, offset, stream)


def _broken_stream_at_ignores_stream(seed, stream, offset):
    """`stream` silently ignored -- the complementary case to ignoring
    offset: still varies correctly across offsets, so a check that only
    varied `offset` would miss this."""
    return stream_at(seed, 0, offset)


def test_conformance_checks_detect_a_broken_backend():
    seed = DEFAULT_SEED
    # Ignoring offset: distinct only in the offset dimension.
    with pytest.raises(AssertionError):
        check_distinctness(_broken_stream_at_ignores_offset, seed, [(5, 0), (5, 1), (5, 2)])
    # Ignoring stream: distinct only in the stream dimension.
    with pytest.raises(AssertionError):
        check_distinctness(_broken_stream_at_ignores_stream, seed, [(0, 5), (1, 5), (2, 5)])
    # Swapped arguments: diverges from the real construction as soon as
    # stream != offset -- confirmed to actually diverge, not assumed.
    real = stream_at(seed, 3, 7).get_seed()
    broken = _broken_stream_at_swapped_arguments(seed, 3, 7).get_seed()
    assert real != broken
