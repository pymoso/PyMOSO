"""
High-dimensional points: exact positional code when it fits, a hashed
code with collision detection when it does not.

point_code packs a point into POINT_BITS // dim bits per component. A
dim=20 problem gets 3 bits each (|x_i| <= 3) and anything larger raised
PointCodeOverflow, so such problems could not be solved at all without
--crn. No fixed layout fixes that: coordinates are taken modulo the
generator's period (~2**191), and an injective code for dim=20 with
16-bit components alone needs 320 bits.

So a point that does not fit is hashed into the same field, and the
Oracle records which point produced each code in the current iteration
and raises PointCodeCollision if two different points ever produce the
same one. The result is still "correct or raises", never silently
shared streams. Points that fit are coded exactly as before, so no
existing coordinate moves.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.chnutils import solve
from pymoso.prng import base as prng_base
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.solvers.rperle import RPERLE

ALL_BACKENDS = [mrg32k3a, mrg31k3p, philox4x32]
backends = pytest.mark.parametrize("backend", ALL_BACKENDS,
                                   ids=[b.__name__.rsplit(".", 1)[-1] for b in ALL_BACKENDS])


class WideOracle(Oracle):
    """dim-20 problem; g() logs the first value of the stream it is
    handed, so a test can tell which replications shared a position."""
    DIM = 20

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = self.DIM
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        u = rng.random()
        self.log.append(u)
        return True, (sum(abs(v) for v in x) + u, -x[0] + u)


def _oracle(backend, cls=WideOracle):
    orc = cls(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


BIG = tuple(1000 + i for i in range(20))          # far past 3 bits per component
BIG2 = tuple(2000 - i for i in range(20))


# ---------------------------------------------------------------------------
# The capability
# ---------------------------------------------------------------------------

@backends
def test_a_point_too_large_for_the_positional_code_can_be_simulated(backend):
    orc = _oracle(backend)
    isfeas, mean, se = orc.hit(BIG, 3)
    assert isfeas and len(orc.log) == 3 and len(set(orc.log)) == 3


@backends
def test_hashed_points_keep_every_property_the_exact_code_gives(backend):
    """Distinct points get distinct streams; the same point is
    reproducible, continues across calls, and does not depend on the
    order points are visited in."""
    a = _oracle(backend); a.hit(BIG, 2); a.hit(BIG2, 2); a.hit(BIG, 2)
    b = _oracle(backend); b.hit(BIG2, 2); b.hit(BIG, 4)
    big_a = a.log[0:2] + a.log[4:6]
    big2_a = a.log[2:4]
    assert len(set(a.log)) == 6
    assert b.log[0:2] == big2_a          # order-independent
    assert b.log[2:6] == big_a           # continuation == one longer call


def test_a_problem_whose_points_need_the_hash_solves_end_to_end(monkeypatch):
    """A real solve() in which every point is hashed. dim=3 with
    components near 10**9 (the exact code holds 25 bits each, about
    1.7e7) rather than dim=20. (When this was written the in-tree RA
    solvers could not run at dim=20 at all: get_nbors enumerated a
    3**dim box. It no longer does -- docs/rng-interface-design.md
    §3.4's correction -- but a small dimension keeps this test about
    the coordinate layer, and quick.)"""
    CENTRE = 10 ** 9
    hashed_points = set()
    real_encode = prng_base.encode_point

    def spying_encode(x, point_bits=prng_base.POINT_BITS):
        code, hashed = real_encode(x, point_bits)
        if hashed:
            hashed_points.add(tuple(x))
        return code, hashed

    monkeypatch.setattr(mrg32k3a, "encode_point", spying_encode)

    class FarAway(Oracle):
        def __init__(self, rng):
            self.num_obj = 2
            self.dim = 3
            super().__init__(rng)

        def g(self, x, rng):
            d = [v - CENTRE for v in x]
            if any(abs(v) > 50 for v in d):
                return False, (0.0, 0.0)
            u = rng.random()
            return True, (sum(abs(v) for v in d) + u, -d[0] + u)

    x0 = tuple([CENTRE + 30] * 3)
    res, end_seed = solve(FarAway, RPERLE, x0, budget=300, seed=(12345,) * 6)
    res2, end_seed2 = solve(FarAway, RPERLE, x0, budget=300, seed=(12345,) * 6)
    assert res and (res, end_seed) == (res2, end_seed2)
    assert len(hashed_points) > 100


# ---------------------------------------------------------------------------
# Nothing that fits moves
# ---------------------------------------------------------------------------

@backends
@pytest.mark.parametrize("x", [(0,), (5,), (-7, 3), (40, 40), (1, -2, 3), tuple(range(-4, 5))])
def test_points_that_fit_get_exactly_the_positional_code(backend, x):
    W = backend.point_width(len(x))
    assert backend.encode_point(x) == (prng_base.point_code(x, W), False)
    assert (backend.offset_from_point_code(backend.encode_point(x)[0], 2, 5)
            == backend.offset_within_iteration(x, 2, 5, W))


@backends
def test_hashed_codes_stay_inside_the_point_field(backend):
    limit = 1 << backend.POINT_BITS
    for x in (BIG, BIG2, tuple([10 ** 30] * 3), tuple(range(100))):
        code, hashed = backend.encode_point(x)
        assert hashed and 0 <= code < limit
        backend.offset_from_point_code(code, 0, 0)       # assembles without overflow
    assert backend.offset_from_point_code(limit - 1, 0, 0) < backend.OFFSET_CAPACITY


def test_the_hash_is_pinned_so_runs_reproduce_across_versions_and_platforms():
    """Not Python's hash(): a fixed blake2b over a canonical encoding.
    If this value ever changes, every hashed coordinate changes."""
    assert prng_base.hash_point(BIG, 75) == 0x716663D57AEFCB5F30
    assert prng_base.hash_point(BIG, 72) == prng_base.hash_point(BIG, 72)
    assert prng_base.hash_point((1, 2), 75) != prng_base.hash_point((12,), 75)
    assert prng_base.hash_point((1, -2), 75) != prng_base.hash_point((1, 2), 75)
    assert prng_base.hash_point((0, 0), 75) != prng_base.hash_point((0,), 75)


# ---------------------------------------------------------------------------
# Detection: correct or raises
# ---------------------------------------------------------------------------

@backends
def test_two_different_points_with_the_same_code_raise(backend, monkeypatch):
    monkeypatch.setattr(prng_base, "hash_point", lambda x, bits: 12345)
    orc = _oracle(backend)
    orc.hit(BIG, 1)
    orc.hit(BIG, 1)                                      # same point again: fine
    with pytest.raises(prng_base.PointCodeCollision):
        orc.hit(BIG2, 1)
    assert len(orc.log) == 2                             # nothing drawn for the colliding point


@backends
def test_a_hashed_point_colliding_with_an_exactly_coded_one_raises(backend, monkeypatch):
    small = tuple([1] * 20)                              # fits: exact code
    exact_code, hashed = backend.encode_point(small)
    assert not hashed
    monkeypatch.setattr(prng_base, "hash_point", lambda x, bits: exact_code)
    orc = _oracle(backend)
    orc.hit(small, 1)
    with pytest.raises(prng_base.PointCodeCollision):
        orc.hit(BIG, 1)
    # and in the other order
    orc = _oracle(backend)
    orc.hit(BIG, 1)
    with pytest.raises(prng_base.PointCodeCollision):
        orc.hit(small, 1)


@backends
def test_detection_covers_the_visit_path_too(backend, monkeypatch):
    monkeypatch.setattr(prng_base, "hash_point", lambda x, bits: 99)
    orc = _oracle(backend)
    orc.hit(BIG, 1, visit=2)
    with pytest.raises(prng_base.PointCodeCollision):
        orc.hit(BIG2, 1, visit=3)


@backends
def test_the_record_is_per_iteration(backend, monkeypatch):
    """A new iteration is a new stream, so the same code there is not a
    collision -- and the record must not grow across iterations."""
    monkeypatch.setattr(prng_base, "hash_point", lambda x, bits: 7)
    orc = _oracle(backend)
    orc.hit(BIG, 1)
    orc._advance_iteration()
    orc.hit(BIG2, 1)
    assert len(orc._point_codes) == 1


@backends
def test_crn_and_sync_carry_no_point_code_and_record_nothing(backend, monkeypatch):
    monkeypatch.setattr(prng_base, "hash_point", lambda x, bits: 7)
    orc = _oracle(backend)
    orc.hit(BIG, 1, sync=3)
    orc.hit(BIG2, 1, sync=3)
    crn = WideOracle(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    crn.set_crnflag(True)
    crn.simpar = 1
    crn.hit(BIG, 1)
    crn.hit(BIG2, 1)
    assert orc._point_codes == {} and crn._point_codes == {}
