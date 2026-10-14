"""
An Oracle used directly, without solve() or testsolve() having called
set_crnflag(), behaves as if set_crnflag(False) had been called.

The flag already defaulted to False. What set_crnflag() also does --
fix the generator from the oracle's stream, and the root every
coordinate is computed from -- had not happened, so hit() on a fresh
instance failed with `KeyError: None`.
"""
import pytest

from pymoso.prng import registry
from pymoso.problems.probtpa import ProbTPA

GENERATORS = sorted(registry.GENERATORS)


def _fresh(name):
    backend = registry.GENERATORS[name]
    return ProbTPA(backend.stream_at(backend.DEFAULT_SEED, 1, 0))


def _flagged(name):
    orc = _fresh(name)
    orc.set_crnflag(False)
    return orc


@pytest.mark.parametrize("name", GENERATORS)
def test_hit_on_a_fresh_oracle_is_hit_after_set_crnflag_false(name):
    fresh, flagged = _fresh(name), _flagged(name)
    for x, m in (((40, 40), 5), ((41, 40), 3), ((40, 40), 2)):
        assert fresh.hit(x, m) == flagged.hit(x, m)
    assert fresh.get_endseed() == flagged.get_endseed()


@pytest.mark.parametrize("name", GENERATORS)
def test_hit_many_and_get_endseed_on_a_fresh_oracle(name):
    requests = [((40, 40), 4), ((39, 41), 4)]
    assert _fresh(name).hit_many(requests) == _flagged(name).hit_many(requests)
    assert _fresh(name).get_endseed() == _flagged(name).get_endseed()


def test_an_explicit_flag_is_not_overridden():
    orc = _fresh("mrg32k3a")
    orc.set_crnflag(True)
    first = orc.hit((40, 40), 5)
    assert orc.crnflag is True
    assert orc.hit((40, 40), 5) == first          # CRN: the same replications again
