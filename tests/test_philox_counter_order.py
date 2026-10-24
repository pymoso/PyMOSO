"""
Philox's draws stay inside the coordinate they were handed.

`stream_at(seed, stream, offset)` puts `offset` on the 128-bit counter,
most significant word first, and every reserve in the layout assumes
that drawing walks forward from there one counter position (four
words) at a time: a replication's 4,096 positions without CRN, 2**88
with it, a role's whole stream. Until Phase 7 the stream stepped the
counter's other end, word 0, so after four draws a stream continued as
the one at offset + 2**96: another point's coordinate, since bits 96-117
hold the top of the point code. These tests check the walk in counter
space, and its consequence on a real oracle with and without CRN.
"""
import pytest

from pymoso.oracle import Oracle
from pymoso.prng import philox4x32 as mod

SEED = mod.DEFAULT_SEED
WORD = 1 << 32


def _draws(stream, n):
    return [stream.random() for _ in range(n)]


@pytest.mark.parametrize("offset", [
    0, 12345, WORD - 1, WORD - 2, (1 << 64) - 1, (1 << 96) - 1,
    5 << 12, (3 << 46) | (7 << 12),       # a replication start, and a point's
])
@pytest.mark.parametrize("k", [1, 2, 3, 17])
def test_drawing_4k_words_lands_where_offset_plus_k_starts(offset, k):
    walked = mod.stream_at(SEED, 7, offset)
    _draws(walked, 4 * k)
    assert _draws(walked, 4) == _draws(mod.stream_at(SEED, 7, offset + k), 4)


def test_a_whole_replication_reserve_is_the_reserves_positions_in_order():
    start = 9 << mod.REPL_RESERVE_BITS
    walked = _draws(mod.stream_at(SEED, 2, start), 4 * mod.REPL_RESERVE_STRIDE)
    for i in range(0, mod.REPL_RESERVE_STRIDE, 511):
        assert walked[4 * i:4 * i + 4] == _draws(mod.stream_at(SEED, 2, start + i), 4), i


def test_advance_after_drawing_continues_from_the_walked_position():
    s = mod.stream_at(SEED, 4, 1000)
    _draws(s, 8)                     # two positions consumed
    assert _draws(s.advance(5), 4) == _draws(mod.stream_at(SEED, 4, 1007), 4)


class _Nine(Oracle):
    """Nine dimensions, so a component holds 8 bits of the point code
    and a step of 2 in component 6 is a step of 2**50 in it: where the
    old counter order sent a replication's fifth draw."""
    draws_at = {}

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 9
        super().__init__(rng)

    def g(self, x, rng):
        n = 16384 if not any(x) else 4
        type(self).draws_at.setdefault(x, []).append(tuple(rng.random() for _ in range(n)))
        return True, (0.0,)


def test_without_crn_no_nearby_point_draws_from_a_replications_reserve():
    _Nine.draws_at = {}
    orc = _Nine(mod.stream_at(SEED, 0, 0))
    orc.set_crnflag(False)
    orc.set_simpar(1)
    origin = (0,) * 9
    orc.hit(origin, 1)
    walked = _Nine.draws_at[origin][0]
    blocks = {walked[i:i + 4] for i in range(0, len(walked), 4)}
    shared = []
    for i in range(9):
        for v in range(-8, 9):
            if v:
                x = tuple(v if j == i else 0 for j in range(9))
                orc.hit(x, 1)
                if _Nine.draws_at[x][-1] in blocks:
                    shared.append(x)
    assert shared == []


def test_with_crn_a_replications_later_draws_are_not_another_replications():
    seen = []

    class Recording(Oracle):
        def __init__(self, rng):
            self.num_obj = 1
            self.dim = 1
            super().__init__(rng)

        def g(self, x, rng):
            seen.append(tuple(rng.random() for _ in range(8)))
            return True, (0.0,)

    orc = Recording(mod.stream_at(SEED, 0, 0))
    orc.set_crnflag(True)
    orc.set_simpar(1)
    orc.hit((0,), 257)
    # the old order: replication r's draws 5-8 were replication r+256's 1-4
    assert seen[0][4:8] != seen[256][0:4]
    firsts = {r[0:4] for r in seen}
    assert not any(r[4:8] in firsts for r in seen)
