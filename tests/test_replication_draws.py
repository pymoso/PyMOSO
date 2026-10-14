"""
Oracle.replication_draws: the number of uniform draws one replication
of g() may make without common random numbers.

It is 16,384 for every generator unless a problem class says otherwise.
A larger value spaces replications further apart and takes the bits
from the point code, so large or many-component points fall back to a
hashed code sooner. The default changes nothing: every golden holds.
"""
import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.oracle import Oracle
from pymoso.prng import base as prng_base, mrg31k3p, mrg32k3a, registry
from pymoso.prng.base import ReplicationDrawOverflow
from pymoso.solvers.rspline import RSPLINE

from _reserve_problems import Draws, SmallDraws, WideDraws, WideDrawsOneTooMany, WideReserve

GENERATORS = sorted(registry.GENERATORS)


def _oracle(cls, name):
    backend = registry.GENERATORS[name]
    orc = cls(backend.stream_at(backend.DEFAULT_SEED, 1, 0))
    orc.set_crnflag(False)
    return orc


@pytest.mark.parametrize("name", GENERATORS)
def test_the_default_is_16384_draws_and_each_generators_own_reserve(name):
    backend = registry.GENERATORS[name]
    assert Oracle.replication_draws == 16384
    assert Oracle.replication_reserve_bits(backend) == backend.REPL_RESERVE_BITS
    assert (1 << backend.REPL_RESERVE_BITS) * backend.DRAWS_PER_OFFSET == 16384


@pytest.mark.parametrize("name", GENERATORS)
def test_a_larger_reserve_is_honoured_exactly(name):
    assert _oracle(WideDraws, name).hit((1, 1), 3)[0]
    with pytest.raises(ReplicationDrawOverflow, match="replication_draws"):
        _oracle(WideDrawsOneTooMany, name).hit((1, 1), 3)


@pytest.mark.parametrize("name", GENERATORS)
def test_replications_with_a_larger_reserve_do_not_share_draws(name):
    """The four replications start 2**16 draws apart, at four different
    values."""
    orc = _oracle(WideReserve, name)
    backend = registry.GENERATORS[name]
    root = orc.rng.root_seed()
    block = orc._plan_hit((3, 4), 4)                       # planned, not run
    assert block.stride == (1 << 16) // backend.DRAWS_PER_OFFSET
    starts = [backend.stream_at(root, block.stream, block.offset + i * block.stride) for i in range(4)]
    firsts = [s.random() for s in starts]
    assert len(set(firsts)) == 4


@pytest.mark.parametrize("name", GENERATORS)
def test_a_smaller_reserve_works_and_is_enforced(name):
    orc = _oracle(SmallDraws, name)
    assert orc.hit((1, 1), 3)[0]
    too_many = type("TooMany", (SmallDraws,), {"draws": 17})
    with pytest.raises(ReplicationDrawOverflow):
        _oracle(too_many, name).hit((1, 1), 3)


def test_the_bits_come_out_of_the_point_code(monkeypatch):
    """At 2**40 draws a two-dimensional point keeps 24 bits a component
    (MRG family): (2**22, 0) is exact and (2**23, 0) is hashed. At the
    default the latter is exact."""
    hashed = []
    real = prng_base.encode_point

    def spy(x, point_bits=prng_base.POINT_BITS):
        code, was_hashed = real(x, point_bits)
        hashed.append(was_hashed)
        return code, was_hashed

    monkeypatch.setattr(prng_base, "encode_point", spy)
    huge = type("Huge", (Draws,), {"replication_draws": 1 << 40, "draws": 1})
    for cls, x, expected in ((huge, (1 << 22, 0), False), (huge, (1 << 23, 0), True), (Draws, (1 << 23, 0), False)):
        hashed.clear()
        _oracle(cls, "mrg32k3a").hit(x, 1)
        assert hashed == [expected], (cls.__name__, x)


@pytest.mark.parametrize("value", [0, 3, 1000, (1 << 40) + 1, 1 << 41, 2.0, True, "16384", None])
def test_a_value_that_is_not_a_power_of_two_in_range_is_refused(value):
    bad = type("Bad", (Draws,), {"replication_draws": value})
    with pytest.raises(ValueError, match="replication_draws"):
        _oracle(bad, "mrg32k3a")


def test_philox_needs_at_least_four():
    """Its unit of offset is four draws."""
    two = type("Two", (Draws,), {"replication_draws": 2, "draws": 1})
    assert _oracle(two, "mrg32k3a").hit((1, 1), 1)[0] is True
    with pytest.raises(ValueError, match="from 4"):
        _oracle(two, "philox4x32")


def test_the_mrg_jump_for_another_stride_is_computed_once():
    """Without a cached jump each replication would cost a general
    matrix power (about 1.6 ms); a power-of-two stride is cached."""
    for module in (mrg32k3a, mrg31k3p):
        module._jump_power_of_two.cache_clear()
    for name in ("mrg32k3a", "mrg31k3p"):
        _oracle(WideReserve, name).hit((1, 1), 20)
    for module in (mrg32k3a, mrg31k3p):
        info = module._jump_power_of_two.cache_info()
        assert info.misses == 1 and info.hits >= 18, (module.__name__, info)


@pytest.mark.parametrize("simpar", [1, 2])
def test_a_larger_reserve_on_workers_is_the_serial_run(simpar):
    kwargs = dict(budget=300, seed=(12345,) * 6)
    assert solve(WideReserve, RSPLINE, (3, 3), simpar=simpar, **kwargs) == solve(WideReserve, RSPLINE, (3, 3), **kwargs)


def test_dispatch_cost_measures_the_problems_own_reserve():
    """It builds its own replications; a g() using more than the
    default reserve would overflow if it used the generator's."""
    from pymoso import dispatch_cost
    from pymoso.pool import LocalBackend
    report = dispatch_cost(WideDraws, (1, 1), replications=2, parts=2, backend=LocalBackend(), jobs=1)
    assert report.identical
