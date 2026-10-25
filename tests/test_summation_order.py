"""
Floats are added left to right, so a seed gives the same numbers on
every Python version (KNOWN_ISSUES.md issue 17).

Python 3.12 changed the built-in sum() of floats to carry a
compensation term. bsm, the inverse-normal approximation behind every
generator's normalvariate, added its terms with sum(), so on 3.12 and
later about 40% of normal variates differed from 3.10's and 3.11's in
the last bit or two.

bsm is checked against a copy of itself here that adds with a plain
loop, on the same platform, not against recorded bits: bsm also calls
log and pow, which come from the platform's C library and differ
between Linux, macOS and Windows, so recorded values hold on one
platform only (this test's first version recorded them, and failed on
macOS and Windows).
On 3.10 and 3.11 sum() adds left to right too, so these tests cannot
fail there; CI's 3.12 and later cells are where they check.
"""
import ast
import pathlib
from math import log

import pytest

from pymoso.moso import edist, enorm, sum_left_to_right
from pymoso.prng import mrg32k3a, registry
from pymoso.prng.base import ensure_random_compatible
from pymoso.solvers import mopbnb

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pymoso"
SEED = (12345,) * 6
DRAWS = 20000


def _added(terms):
    total = 0
    for t in terms:
        total = total + t
    return total


def _reference_bsm(u):
    """bsm as shipped, with every sum a plain left-to-right loop"""
    a, b, c = mrg32k3a.bsma, mrg32k3a.bsmb, mrg32k3a.bsmc
    y = u - 0.5
    if abs(y) < 0.42:
        r = pow(y, 2)
        r2 = pow(r, 2)
        r3 = pow(r, 3)
        r4 = pow(r, 4)
        asum = _added([a[0], a[1]*r, a[2]*r2, a[3]*r3])
        bsum = _added([1, b[0]*r, b[1]*r2, b[2]*r3, b[3]*r4])
        return y*(asum/bsum)
    if y < 0.0:
        signum = -1
        r = u
    else:
        signum = 1
        r = 1 - u
    s = log(-log(r))
    powers = [pow(s, k) for k in range(2, 9)]
    return signum*_added([c[0], c[1]*s] + [c[k + 2]*powers[k] for k in range(7)])


def _stream(name):
    return ensure_random_compatible(registry.get_generator(name).stream_at(SEED, 0, 0))


def test_the_reference_sees_the_central_and_tail_branches():
    rng = _stream('mrg32k3a')
    us = [rng.random() for _ in range(DRAWS)]
    tails = sum(1 for u in us if abs(u - 0.5) >= 0.42)
    assert 0 < tails < DRAWS


@pytest.mark.parametrize("bsm", [mrg32k3a.bsm, mopbnb.bsm], ids=["prng", "mopbnb"])
def test_bsm_adds_left_to_right(bsm):
    rng = _stream('mrg32k3a')
    us = [rng.random() for _ in range(DRAWS)]
    assert [bsm(u).hex() for u in us] == [_reference_bsm(u).hex() for u in us]


@pytest.mark.parametrize("name", sorted(registry.GENERATORS))
def test_normal_variates_are_bsm_of_one_uniform_added_left_to_right(name):
    rng, uniforms = _stream(name), _stream(name)
    drawn = [rng.normalvariate(0, 1).hex() for _ in range(DRAWS)]
    assert drawn == [_reference_bsm(uniforms.random()).hex() for _ in range(DRAWS)]


def test_sum_left_to_right_does_not_compensate():
    # 3.12's sum() gives 1.0 here; left to right, 1e16 + 1.0 rounds to 1e16
    assert sum_left_to_right([1e16, 1.0, -1e16]) == 0.0
    assert sum_left_to_right([]) == 0
    assert sum_left_to_right([1, 2, 3]) == 6


def test_enorm_and_edist_add_left_to_right():
    # 1e16 + 1 + 1 is 1e16 left to right and 1e16 + 2 compensated, whose
    # square roots are different floats
    assert enorm((1e8, 1.0, 1.0)) == 1e8
    assert edist((1e8, 1.0, 1.0), (0, 0, 0)) == 1e8


# sum() calls left in the package, each over integers only
INTEGER_SUMS = {
    ("executor.py", "total = sum(block.count for block in blocks)"),
    ("prng/mrg_common.py", "res[i] = sum([int(a[i][j])*int(b[j]) for j in r3])"),
    ("prng/mrg_common.py", "res[i][j] = sum(int(a[i][k]) * int(b[k][j]) for k in r3) % modi"),
}


def test_the_package_calls_sum_only_on_integers():
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        lines = path.read_text(encoding='utf-8').splitlines()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum":
                found.add((path.relative_to(PACKAGE).as_posix(), lines[node.lineno - 1].strip()))
    assert found == INTEGER_SUMS
