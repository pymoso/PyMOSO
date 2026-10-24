"""
`rng.advance(d)` inside `g()`: a second generator `d` draws past `rng`.

The contract is the same on every generator: drawing from
`rng.advance(d)` gives what `rng` itself would give after `d` more
draws, and `rng` does not move. A draw is one `random()` call. Under
Philox `g()` receives a `RandomCompatAdapter`, whose stream counts in
counter positions of four draws; the adapter converts.

The last test records a gap rather than a guarantee: draws taken on an
advanced generator are not counted against `Oracle.replication_draws`.
"""
import pytest

from pymoso.oracle import Oracle
from pymoso.prng import registry
from pymoso.prng.base import ensure_random_compatible

GENERATORS = sorted(registry.GENERATORS)


def _rng(name, offset=0):
    """A generator as g() receives it."""
    backend = registry.GENERATORS[name]
    return ensure_random_compatible(backend.stream_at(backend.DEFAULT_SEED, 3, offset))


def _draws(rng, n):
    return [rng.random() for _ in range(n)]


@pytest.mark.parametrize("name", GENERATORS)
@pytest.mark.parametrize("drawn", [0, 1, 3, 4, 5])
@pytest.mark.parametrize("d", [0, 1, 2, 3, 4, 5, 7, 8, 17, 4 * 4096 + 3])
def test_advance_d_then_drawing_is_drawing_d_then_drawing(name, drawn, d):
    rng = _rng(name, 77)
    _draws(rng, drawn)
    ahead = rng.advance(d)
    reference = _rng(name, 77)
    _draws(reference, drawn + d)
    assert _draws(ahead, 9) == _draws(reference, 9)


@pytest.mark.parametrize("name", GENERATORS)
def test_advance_leaves_rng_where_it_was(name):
    rng = _rng(name)
    _draws(rng, 2)
    rng.advance(6)
    reference = _rng(name)
    _draws(reference, 2)
    assert _draws(rng, 9) == _draws(reference, 9)


@pytest.mark.parametrize("name", GENERATORS)
def test_an_advanced_generator_has_the_methods_of_random_random(name):
    ahead = _rng(name).advance(5)
    assert 0 <= ahead.uniform(0, 1) < 1
    assert ahead.choice([1, 2, 3]) in (1, 2, 3)


class _Purposes(Oracle):
    """One draw for arrivals from rng, one for service from rng.advance(1000)."""
    seen = []

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        service = rng.advance(1000)
        type(self).seen.append((_draws(rng, 1001), service.random()))
        return True, (0.0,)


@pytest.mark.parametrize("crn", [False, True])
@pytest.mark.parametrize("name", GENERATORS)
def test_advance_inside_g_on_every_generator(name, crn):
    backend = registry.GENERATORS[name]
    _Purposes.seen = []
    orc = _Purposes(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    orc.set_crnflag(crn)
    orc.set_simpar(1)
    orc.hit((2,), 3)
    assert len(_Purposes.seen) == 3
    for drawn, service in _Purposes.seen:
        assert service == drawn[1000]


class _PastTheReserve(Oracle):
    """Draws once, at replication_draws past its own start, on an advanced
    generator: the next replication's first draw."""
    seen = []

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        type(self).seen.append((rng.random(), rng.advance(self.replication_draws - 1).random()))
        return True, (0.0,)


@pytest.mark.parametrize("name", GENERATORS)
def test_the_reserve_check_does_not_see_draws_on_an_advanced_generator(name):
    """A gap, recorded: nothing raises, and replication 0's advanced draw
    is replication 1's first. Drawing that far on rng itself would raise
    ReplicationDrawOverflow (tests/test_replication_draws.py)."""
    backend = registry.GENERATORS[name]
    _PastTheReserve.seen = []
    orc = _PastTheReserve(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    orc.set_crnflag(False)
    orc.set_simpar(1)
    orc.hit((2,), 2)
    (first0, past0), (first1, _) = _PastTheReserve.seen
    assert past0 == first1
