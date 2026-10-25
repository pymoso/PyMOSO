"""
Floats are added left to right, so a seed gives the same numbers on
every Python version (KNOWN_ISSUES.md issue 17).

Python 3.12 changed the built-in sum() of floats to carry a
compensation term. bsm, the inverse-normal approximation behind every
generator's normalvariate, added its terms with sum(), so on 3.12 and
later about 40% of normal variates differed from 3.10's and 3.11's in
the last bit or two. The expected values here were computed on 3.10,
whose sum() adds left to right; on 3.10 and 3.11 these tests cannot
fail, so it is CI's 3.12-3.14 cells that check them.
"""
import ast
import hashlib
import pathlib

import pytest

from pymoso.moso import edist, enorm, sum_left_to_right
from pymoso.prng import mrg32k3a, registry
from pymoso.prng.base import ensure_random_compatible
from pymoso.solvers import mopbnb

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pymoso"

# (u, bsm(u)) on 3.10, for uniforms whose bsm differed on 3.14: four
# from the centre of the approximation and four from the tails
BSM_310 = [
    ('0x1.a6d566678d634p-1', '0x1.e031c222ec4b1p-1'),
    ('0x1.c5e5e7c0cacc6p-3', '-0x1.888ceb1f86869p-1'),
    ('0x1.ec5012a0010f3p-2', '-0x1.8af0f19dbd1e2p-5'),
    ('0x1.6c17e397d368fp-2', '-0x1.7b3db8d411972p-2'),
    ('0x1.17cb2c035513dp-5', '-0x1.d2adb41842ac3p+0'),
    ('0x1.ddee37da518d7p-1', '0x1.808671270cc93p+0'),
    ('0x1.08035ad682b9dp-9', '-0x1.701e2405103cfp+1'),
    ('0x1.3b088adff6f0ep-4', '-0x1.6d1833fc34847p+0'),
]

# sha256 of the hex of 20,000 normalvariate(0, 1) draws from
# stream_at((12345,)*6, 0, 0), on 3.10
NORMALS_310 = {
    'mrg31k3p': 'eb9640c737632f2da78e106f3e2ef676516f26c21db6108a01e1f3ec9adccfb0',
    'mrg32k3a': 'b0f1eaee3110fc280e91ce78e329efee80b93b46ecddb7d74de8881dd9a2338c',
    'philox4x32': '4790fbf21c223f08929392a1e1b21ec2f8a654b1d565117ba1129d97ec4a01c0',
}


@pytest.mark.parametrize("bsm", [mrg32k3a.bsm, mopbnb.bsm], ids=["prng", "mopbnb"])
@pytest.mark.parametrize("u, z", BSM_310)
def test_bsm_gives_3_10s_bits(bsm, u, z):
    assert bsm(float.fromhex(u)).hex() == z


@pytest.mark.parametrize("name", sorted(NORMALS_310))
def test_normal_variates_are_3_10s(name):
    rng = ensure_random_compatible(registry.get_generator(name).stream_at((12345,) * 6, 0, 0))
    digest = hashlib.sha256(''.join(rng.normalvariate(0, 1).hex() for _ in range(20000)).encode())
    assert digest.hexdigest() == NORMALS_310[name]


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
        lines = path.read_text().splitlines()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum":
                found.add((path.relative_to(PACKAGE).as_posix(), lines[node.lineno - 1].strip()))
    assert found == INTEGER_SUMS
