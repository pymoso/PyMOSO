"""
What a point may be, and that it is the same with and without --crn.

The contract. A point is a tuple of numbers, and the oracle decides
whether it is feasible. The framework's own part is to give the point
a random-number stream, which without --crn means encoding the point
into a coordinate; with --crn the point is not encoded at all. So the
two modes used to differ for anything but a Python int: a numpy
integer overflowed inside the encoding, a float -- 30.0 as much as
30.5 -- failed deep in the generator's jump, and all of them ran under
--crn.

Now:
- a whole-valued number of any numeric type is the integer it equals:
  30.0, numpy.int64(30) and Fraction(30) are the point 30, on the
  same streams;
- any other real number is encoded by its exact value and handed to
  the oracle, which decides (ProbTPA says no; an oracle that allows
  half-integers may say yes);
- a point that cannot be encoded at all -- nan, an infinity, something
  that is not a number -- is reported infeasible, in both modes,
  without being simulated. Not a crash.

Integer points are encoded exactly as before, so nothing existing
moves; the golden suite holds that.
"""
import math
from fractions import Fraction

import pytest

from pymoso.chnbase import Oracle
from pymoso.chnutils import solve, testsolve
from pymoso.prng import base as prng_base
from pymoso.prng import registry
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

pytestmark = pytest.mark.timeout(120)

GENERATORS = sorted(registry.GENERATORS)
MODES = [(name, crn) for name in GENERATORS for crn in (False, True)]
SEED = (12345,) * 6


class Anywhere(Oracle):
    """Feasible wherever it is asked, and counts the asking."""
    calls = 0

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        type(self).calls += 1
        return True, (float(x[0]) + rng.random(), float(x[1]) + rng.random())


class Draws(Anywhere):
    """The objectives are the draws alone, so that results can be told
    apart at points too large for a float to carry the noise."""

    def g(self, x, rng):
        return True, (rng.random(), rng.random())


def oracle(name, crn, cls=Anywhere):
    mod = registry.GENERATORS[name]
    orc = cls(mod.stream_at(mod.DEFAULT_SEED, 1, 0))
    orc.set_crnflag(crn)
    return orc


def hit(name, crn, x, m=4):
    return oracle(name, crn).hit(x, m)


def _thirty():
    points = [(30.0, 30.0), (30, 30.0), (Fraction(30), Fraction(60, 2)), (29 + True, 30)]
    try:
        import numpy
    except ImportError:
        return points
    return points + [
        (numpy.int64(30), numpy.int64(30)), (numpy.int32(30), numpy.int16(30)),
        (numpy.float64(30.0), numpy.float32(30.0)), tuple(numpy.array([30, 30])),
    ]


@pytest.mark.parametrize("name,crn", MODES)
@pytest.mark.parametrize("x", _thirty(), ids=repr)
def test_a_whole_number_of_any_numeric_type_is_the_integer_it_equals(name, crn, x):
    assert hit(name, crn, x) == hit(name, crn, (30, 30))


@pytest.mark.parametrize("name,crn", MODES)
def test_a_point_that_is_not_whole_is_simulated_if_the_oracle_allows_it(name, crn):
    isfeas, mean, _ = hit(name, crn, (30.5, 30))
    assert isfeas is True and 30.5 <= mean[0] <= 31.5
    assert hit(name, crn, (30.5, 30)) == (isfeas, mean, _)              # and reproducibly
    assert hit(name, crn, (Fraction(61, 2), 30.0)) == (isfeas, mean, _)   # the same value is the same point


@pytest.mark.parametrize("name", GENERATORS)
def test_without_crn_distinct_points_have_distinct_streams_whole_or_not(name):
    noise = {x: tuple(m - float(c) for m, c in zip(hit(name, False, x)[1], x))
             for x in [(30, 30), (31, 30), (30.5, 30), (30.25, 30), (30, 30.5)]}
    assert len({tuple(round(v, 12) for v in values) for values in noise.values()}) == len(noise)


def _unencodable():
    return [(math.nan, 30), (30, math.inf), (-math.inf, 30), ("30", 30), (None, 30), ([30], 30), (30 + 0j, 30)]


@pytest.mark.parametrize("name,crn", MODES)
@pytest.mark.parametrize("x", _unencodable(), ids=repr)
def test_a_point_that_cannot_be_encoded_is_infeasible_and_is_not_simulated(name, crn, x):
    orc = oracle(name, crn)
    before = Anywhere.calls
    assert orc.hit(x, 4) == (False, [], [])
    assert Anywhere.calls == before
    assert orc.get_high_water_mark() is None                # and it touched no stream


@pytest.mark.parametrize("name,crn", MODES)
def test_an_unencodable_point_among_others_does_not_disturb_them(name, crn):
    good = [((30, 30), 3), ((31.0, 30), 3)]
    expected = oracle(name, crn).hit_many(good)
    mixed = oracle(name, crn).hit_many([good[0], ((math.nan, 1), 3), good[1], (("x", 1), 2)])
    assert mixed == [expected[0], (False, [], []), expected[1], (False, [], [])]


def test_encode_point_gives_integers_the_codes_they_always_had():
    """The pin on golden-neutrality at the level of one function: for
    integer points nothing about the code changed, exact or hashed."""
    for x in [(0,), (30, 30), (-7, 0, 11), (10 ** 9, 5), (2 ** 70, -3)]:
        code, hashed = prng_base.encode_point(x)
        assert type(code) is int
        W = prng_base.point_width(len(x))
        try:
            assert (code, hashed) == (prng_base.point_code(x, W), False)
        except prng_base.PointCodeOverflow:
            assert hashed is True
        assert prng_base.encode_point(tuple(float(v) for v in x)) == (code, hashed)


@pytest.mark.parametrize("name", GENERATORS)
def test_plain_python_integers_of_any_size_simulate_without_crn(name):
    """Established when the numpy failure was diagnosed, and kept: its
    message was "Python int too large to convert to C long", which
    reads as a limit on the coordinate. It was not. The same values
    as plain Python ints always worked in the default mode, at every
    magnitude; what overflowed was a numpy scalar that the point code
    had become. Large-component problems were never broken."""
    values = [30, 2 ** 31 - 1, 2 ** 31, 2 ** 32, 2 ** 62, 2 ** 63 - 1, 2 ** 63, 2 ** 64, 2 ** 70, 2 ** 127,
              10 ** 30, -(2 ** 63), -(2 ** 63) - 1, -(10 ** 30)]
    for v in values:
        for x in ((v, 5), (5, v), (v, v)):
            orc = oracle(name, False, Draws)
            first, again = orc.hit(x, 3), orc.hit(x, 3)
            assert first[0] is True and first != again      # simulated, and continued on fresh draws
            assert oracle(name, False, Draws).hit(x, 3) == first    # reproducibly


def test_a_numpy_integer_too_big_for_the_exact_code_is_still_its_integer():
    numpy = pytest.importorskip("numpy")
    for value in (2 ** 40, 2 ** 62, -(2 ** 62)):
        for name in GENERATORS:
            assert hit(name, False, (numpy.int64(value), 5)) == hit(name, False, (value, 5))


@pytest.mark.parametrize("name", GENERATORS)
def test_floats_that_print_alike_but_differ_in_the_last_bit_are_different_points(name):
    """A non-whole component is the exact fraction of its binary
    value. 0.1 + 0.2 is not 0.3, as a dict key or as a point."""
    a, b = 0.1 + 0.2, 0.3
    assert a != b and Fraction(a) != Fraction(b)
    assert prng_base.canonical_point((b, 1)) == ((Fraction(5404319552844595, 18014398509481984), 1), False)
    assert prng_base.encode_point((a, 1)) != prng_base.encode_point((b, 1))
    noise_a = hit(name, False, (a, 1))[1][1]
    noise_b = hit(name, False, (b, 1))[1][1]
    assert noise_a != noise_b                               # second objective is 1 + a draw: different streams
    assert hit(name, False, (0.5, 1)) == hit(name, False, (Fraction(1, 2), 1))     # an exact half is one point


def test_point_not_encodable_says_which_component():
    with pytest.raises(prng_base.PointNotEncodable, match="nan"):
        prng_base.encode_point((30, math.nan))


# ---------------------------------------------------------------------------
# What a user sees
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crn", [False, True])
@pytest.mark.parametrize("x0", [(30.0, 30.0)] + _thirty()[4:5] + _thirty()[7:8], ids=repr)
def test_solve_from_a_float_or_numpy_starting_point_is_solve_from_the_integer_point(crn, x0):
    expected = solve(ProbTPA, RPERLE, (30, 30), budget=300, seed=SEED, crn=crn)
    assert solve(ProbTPA, RPERLE, x0, budget=300, seed=SEED, crn=crn) == expected
    expected = testsolve(TPATester, RPERLE, (30, 30), budget=150, seed=SEED, isp=2, crn=crn)
    assert testsolve(TPATester, RPERLE, x0, budget=150, seed=SEED, isp=2, crn=crn) == expected


@pytest.mark.parametrize("crn", [False, True])
def test_on_two_worker_processes_too(crn):
    expected = solve(ProbTPA, RPERLE, (30, 30), budget=300, seed=SEED, crn=crn)
    assert solve(ProbTPA, RPERLE, (30.0, 30.0), budget=300, seed=SEED, crn=crn, simpar=2) == expected


@pytest.mark.parametrize("crn", [False, True])
@pytest.mark.parametrize("x0", [(30.5, 30), (math.nan, 30)], ids=repr)
def test_a_starting_point_the_problem_does_not_allow_is_reported_infeasible_either_way(crn, x0):
    """ProbTPA's points are integers in a box. 30.5 reaches its g(),
    which says no; nan never gets that far. The user is told the same
    thing in both modes."""
    with pytest.raises(ValueError, match="infeasible"):
        solve(ProbTPA, RPERLE, x0, budget=100, seed=SEED, crn=crn)
