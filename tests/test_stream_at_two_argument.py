"""
docs/rng-interface-design.md §12 step 6c: stream_at(seed, stream, offset)
for the MRG family (MRG32k3a, MRG31k3p) -- confirms the two-argument
shape is a relabeling of existing arithmetic, not new arithmetic:
stream_at(seed, stream, offset) must equal jump_seed_n(seed,
stream*ITER_STRIDE + offset) exactly, for every input checked, not
merely "look equivalent." This is the concrete evidence behind "no
existing golden moves" -- if this file didn't pass, chnbase.py's own
migration (which relies on this equivalence) would silently change
behavior.

Also re-runs the §7 determinism/distinctness battery against both
generators' new stream_at directly (not proxied through the old flat
jump_seed_n calls), and re-verifies the broken-backend proof has teeth
against the two-argument shape specifically -- a suite written against
one flat coordinate has no way to catch a swapped-arguments or
dropped-argument bug, since there was only ever one argument to get
wrong before.
"""
import pytest

from pymoso.prng import mrg32k3a
from pymoso.prng import mrg31k3p

DEFAULT_SEED_6 = (12345, 12345, 12345, 12345, 12345, 12345)
SEEDS_6 = [
    DEFAULT_SEED_6,
    (1, 1, 1, 1, 1, 1),
    (511616026, 1372175473, 2158288731, 4085985277, 2198261820, 2779695000),
]

GENERATORS = [
    ("mrg32k3a", mrg32k3a),
    ("mrg31k3p", mrg31k3p),
]


# ---------------------------------------------------------------------------
# The relabeling proof: stream_at must equal the flat jump_seed_n call
# it replaces, exactly, at every input checked.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
@pytest.mark.parametrize("seed", SEEDS_6)
@pytest.mark.parametrize("stream,offset", [
    (0, 0), (0, 1), (1, 0), (1, 1), (5, 100), (100, 5),
    (2 ** 16, 2 ** 100), (2 ** 32 - 1, mrg32k3a.ITER_STRIDE - 1),
])
def test_stream_at_matches_the_flat_jump_seed_n_call_it_replaces(name, mod, seed, stream, offset):
    got_seed = mod.stream_at(seed, stream, offset).get_seed()
    expected_seed = mod.jump_seed_n(seed, stream * mod.ITER_STRIDE + offset)
    assert got_seed == expected_seed, (
        f"{name}.stream_at({seed}, {stream}, {offset}) = {got_seed}, "
        f"expected exactly jump_seed_n(seed, {stream}*ITER_STRIDE+{offset}) "
        f"= {expected_seed}"
    )


# ---------------------------------------------------------------------------
# §7 items 1-2, against the real stream_at directly.
# ---------------------------------------------------------------------------

def check_determinism(stream_at_fn, seed, stream, offset, n_draws=5):
    draws1 = [stream_at_fn(seed, stream, offset).random() for _ in range(n_draws)]
    draws2 = [stream_at_fn(seed, stream, offset).random() for _ in range(n_draws)]
    assert draws1 == draws2


def check_distinctness(stream_at_fn, seed, coordinates, n_draws=5):
    firsts, states = {}, {}
    for c in coordinates:
        s = stream_at_fn(seed, *c)
        s.set_class_cache(False)
        firsts[c] = s.random()
        states[c] = s.get_seed()
    coords = list(coordinates)
    for i, ci in enumerate(coords):
        for cj in coords[i + 1:]:
            assert firsts[ci] != firsts[cj], f"{ci} and {cj} share a first draw"
            assert states[ci] != states[cj], f"{ci} and {cj} land on the same state"


@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
def test_determinism(name, mod):
    for seed in SEEDS_6:
        for stream, offset in [(0, 0), (1, 5), (100, 2 ** 40)]:
            check_determinism(mod.stream_at, seed, stream, offset)


@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
def test_distinctness_across_a_coordinate_battery(name, mod):
    for seed in SEEDS_6:
        check_distinctness(
            mod.stream_at, seed,
            [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (0, 2), (5, 5), (5, 6)],
        )


# ---------------------------------------------------------------------------
# Broken-backend proof, specific to the two-argument shape: a suite
# written against one flat coordinate has no way to catch these.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
def test_conformance_checks_detect_swapped_arguments(name, mod):
    def broken_stream_at(seed, stream, offset):
        return mod.stream_at(seed, offset, stream)  # swapped

    real = mod.stream_at(DEFAULT_SEED_6, 3, 7).get_seed()
    broken = broken_stream_at(DEFAULT_SEED_6, 3, 7).get_seed()
    assert real != broken


@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
def test_conformance_checks_detect_a_dropped_offset(name, mod):
    def broken_stream_at(seed, stream, offset):
        return mod.stream_at(seed, stream, 0)  # offset silently ignored

    with pytest.raises(AssertionError):
        check_distinctness(broken_stream_at, DEFAULT_SEED_6, [(5, 0), (5, 1), (5, 2)])


@pytest.mark.parametrize("name,mod", GENERATORS, ids=[g[0] for g in GENERATORS])
def test_conformance_checks_detect_a_dropped_stream(name, mod):
    def broken_stream_at(seed, stream, offset):
        return mod.stream_at(seed, 0, offset)  # stream silently ignored

    with pytest.raises(AssertionError):
        check_distinctness(broken_stream_at, DEFAULT_SEED_6, [(0, 5), (1, 5), (2, 5)])
