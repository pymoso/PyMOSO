"""
Oracle's mean and variance are defined exactly, so a seed gives the same
estimates on every Python version (KNOWN_ISSUES.md issue 17).

statistics.variance(data, xbar) gave different last bits on 3.10 and
3.14: both sum exactly and round once, but 3.10 squared each deviation
with **, the C library's pow, and 3.14 multiplies. Oracle now computes
both statistics itself: each deviation and its square d * d rounded as
floats, the squares summed exactly, divided by n - 1 and rounded once;
the mean is the exact sum divided by n, rounded once. Nothing in that
depends on the Python version or the platform.

They are checked here against references written with Fraction, exact
rational arithmetic, on the same data, not against recorded bits. On
3.14 statistics.variance gives these values too, so a reversion to it
fails only where a version squares as 3.10 does (which versions:
KNOWN_ISSUES.md issue 17); statistics.mean has given them on every
version checked, so no reversion of the mean can fail here.
"""
import ast
import math
import pathlib
from decimal import Decimal
from fractions import Fraction

import pytest

from pymoso import oracle
from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import MRG32k3a

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pymoso"
SIZES = (2, 3, 5, 10, 30, 100)


def _reference_mean(data):
    return float(sum((Fraction(x) for x in data), Fraction(0)) / len(data))


def _reference_variance(data, xbar):
    squares = [(x - xbar) * (x - xbar) for x in data]
    return float(sum((Fraction(s) for s in squares), Fraction(0)) / (len(data) - 1))


def _samples(count=6000):
    # normals at many scales and offsets, from a fixed MRG32k3a stream
    rng = MRG32k3a((12345,) * 6)
    out = []
    for i in range(count):
        n = SIZES[i % len(SIZES)]
        scale = 10.0 ** rng.uniform(-6, 6)
        loc = (0.0, 1.0, 10.0, 1000.0, -50.0)[i % 5] * scale
        out.append([loc + rng.normalvariate(0, scale) for _ in range(n)])
    return out


SAMPLES = _samples()


def test_mean_is_the_exact_sum_rounded_once():
    assert [oracle._mean(xs).hex() for xs in SAMPLES] == [_reference_mean(xs).hex() for xs in SAMPLES]


def test_variance_sums_the_rounded_squares_exactly():
    means = [oracle._mean(xs) for xs in SAMPLES]
    got = [oracle._variance(xs, m).hex() for xs, m in zip(SAMPLES, means)]
    assert got == [_reference_variance(xs, m).hex() for xs, m in zip(SAMPLES, means)]


@pytest.mark.parametrize("data, mean, variance", [
    ([1, 3], 2, 2),                      # whole: int, as statistics gives
    ([2, 2], 2, 0),
    ([1, 2], 1.5, 0.5),
    ([True, False], 0.5, 0.5),
    ([1.0, math.inf], math.inf, math.nan),
    ([math.inf, -math.inf], math.nan, math.nan),
    ([1.0, math.nan], math.nan, math.nan),
    ([math.inf, math.inf], math.inf, math.nan),
    ([Decimal('1.5'), Decimal('2')], Decimal('1.75'), Decimal('0.125')),     # statistics, keeping the type
    ([Fraction(1, 3), Fraction(1, 2)], Fraction(5, 12), Fraction(1, 72)),
], ids=["ints whole", "ints zero", "ints half", "bools", "inf", "inf-inf", "nan", "inf inf",
        "Decimal", "Fraction"])
def test_types_and_non_finite_values_as_statistics_gives_them(data, mean, variance):
    def same(a, b):
        return type(a) is type(b) and (a == b or (a != a and b != b))
    m = oracle._mean(data)
    assert same(m, mean)
    assert same(oracle._variance(data, m), variance)


class _Recorder(Oracle):
    """one objective, a normal whose scale and offset the point sets, so
    the squares are rarely exact"""
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        self.seen = []
        super().__init__(rng)

    def g(self, x, rng):
        k = x[0]
        scale = 10.0 ** (k % 13 - 6)
        v = (0.0, 1.0, 10.0, 1000.0, -50.0)[k % 5] * scale + scale * rng.normalvariate(0, 1)
        self.seen.append(v)
        return True, (v,)


def test_hit_aggregates_with_them():
    orc = _Recorder(MRG32k3a((12345,) * 6))
    got, expected = [], []
    for k in range(3000):
        m = SIZES[k % len(SIZES)]
        orc.seen = []
        isfeas, obmean, obse = orc.hit((k,), m)
        assert isfeas and len(orc.seen) == m
        mu = _reference_mean(orc.seen)
        got.append((obmean[0].hex(), obse[0].hex()))
        expected.append((mu.hex(), math.sqrt(_reference_variance(orc.seen, mu) / m).hex()))
    assert got == expected


# statistics calls left in the package: Oracle's fallback for number
# types other than int and float, and a timing median
STATISTICS_USES = {
    ("oracle.py", "return statistics.mean(data)"),
    ("oracle.py", "return statistics.variance(data, xbar)"),
    ("backends/measure.py", "return statistics.median(self.job_seconds)"),
}


def test_the_package_takes_no_result_from_statistics():
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        text = path.read_text(encoding='utf-8')
        lines = text.splitlines()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module == "statistics":
                found.add((path.relative_to(PACKAGE).as_posix(), lines[node.lineno - 1].strip()))
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "statistics"):
                found.add((path.relative_to(PACKAGE).as_posix(), lines[node.lineno - 1].strip()))
    assert found == STATISTICS_USES
