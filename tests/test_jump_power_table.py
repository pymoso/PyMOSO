"""
The MRG family's general jump applies one cached power A**(2**k) per set
bit of the exponent, instead of squaring its way up the exponent's whole
bit length on every call (docs/phase7-plan.md, step 3). The same
positions, computed with less work: exact integer arithmetic, and the
powers of one matrix commute, so the result is identical by
construction. That is checked here, not assumed.

`reference_jump_seed_n` below is the implementation before Phase 7,
kept verbatim (module-qualified) as the reference. Do not "tidy" it.

The work is counted, never timed.
"""
import random
import subprocess
import sys
import textwrap

import pytest

from pymoso.prng import mrg_common, mrg31k3p, mrg32k3a

GENERATORS = {
    'mrg32k3a': (mrg32k3a, mrg32k3a.mrgm1i, mrg32k3a.mrgm2i),
    'mrg31k3p': (mrg31k3p, mrg31k3p.mrg31m1, mrg31k3p.mrg31m2),
}


def reference_jump_seed_n(mod, m1, m2, seed, n):
    assert(len(seed) == 6)
    s1 = seed[0:3]
    s2 = seed[3:6]
    if n == mod.REPL_RESERVE_STRIDE:
        p1, p2 = mod._jump_replreserve_p1, mod._jump_replreserve_p2
    elif n == mod.REPL_STRIDE:
        p1, p2 = mod._jump76_p1, mod._jump76_p2
    elif n == mod.ITER_STRIDE:
        p1, p2 = mod._jump127_p1, mod._jump127_p2
    elif n > 0 and n & (n - 1) == 0:
        p1, p2 = mod._jump_power_of_two(n)
    else:
        ns1 = mrg_common.jump_n(s1, mod._m1_step, n, m1)
        ns2 = mrg_common.jump_n(s2, mod._m2_step, n, m2)
        return tuple(ns1 + ns2)
    ns1 = mrg_common.mat311mod(mrg_common.mat333mult(p1, s1), m1)
    ns2 = mrg_common.mat311mod(mrg_common.mat333mult(p2, s2), m2)
    return tuple(ns1 + ns2)


def _exponents(mod):
    rng = random.Random(20261017)
    ns = [0, 1, 2, 3, 5, 7, mod.REPL_RESERVE_STRIDE + 1, mod.REPL_STRIDE - 1,
          mod.ITER_STRIDE + 1, 3 * mod.ITER_STRIDE]
    ns += [(1 << k) - 1 for k in range(2, 260, 7)]
    ns += [rng.getrandbits(rng.randint(1, 260)) for _ in range(400)]
    # the default branch's offsets: code << 52 | visit << 46 | replication << 14
    ns += [rng.getrandbits(rng.randint(1, 75)) << 52 | rng.getrandbits(6) << 46
           | rng.getrandbits(32) << 14 for _ in range(300)]
    # stream_at(root, stream, offset), streams up to the layout's
    ns += [rng.getrandbits(58) * mod.ITER_STRIDE + rng.getrandbits(127) for _ in range(100)]
    return ns


def _seeds(m1, m2):
    return [(12345,) * 6, (1, 2, 3, 4, 5, 6), (m1 - 1, m1 - 2, 0, m2 - 1, 0, m2 - 3),
            (12345.0, 7.0, 1.0, 2.0, 3.0, 4.0)]      # floats were always int()-ed


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_every_jump_is_the_jump_it_always_was(gen):
    mod, m1, m2 = GENERATORS[gen]
    for seed in _seeds(m1, m2):
        for n in _exponents(mod):
            assert mod.jump_seed_n(seed, n) == reference_jump_seed_n(mod, m1, m2, seed, n), (seed, n)


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_stream_at_and_advance_are_unchanged(gen):
    mod, m1, m2 = GENERATORS[gen]
    rng = random.Random(5)
    for _ in range(50):
        stream, offset = rng.getrandbits(40), rng.getrandbits(126)
        flat = stream * mod.ITER_STRIDE + offset
        assert mod.stream_at((12345,) * 6, stream, offset).get_seed() == \
            reference_jump_seed_n(mod, m1, m2, (12345,) * 6, flat)
        base = mod.stream_at((12345,) * 6, stream, 0)
        assert base.advance(offset).get_seed() == \
            reference_jump_seed_n(mod, m1, m2, base.get_seed(), offset)


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_a_negative_or_non_integer_exponent_is_refused_as_before(gen):
    mod, m1, m2 = GENERATORS[gen]
    with pytest.raises(ValueError, match='non-negative'):
        mod.jump_seed_n((12345,) * 6, -3)
    with pytest.raises(TypeError):
        mod.jump_seed_n((12345,) * 6, 3.0)


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_a_general_jump_does_one_matrix_vector_product_per_set_bit(gen, monkeypatch):
    """Per half of the seed. The previous code made bit length + set bits
    3x3 matrix products per half instead."""
    mod, m1, m2 = GENERATORS[gen]
    calls = []
    real = mrg_common.matvec_mod
    monkeypatch.setattr(mrg_common, 'matvec_mod', lambda *a: (calls.append(1), real(*a))[1])
    for n in [0b101 << 52, (1 << 94) | (1 << 60) | (1 << 52) | 7, 20 * mod.ITER_STRIDE + 3, 12345]:
        calls.clear()
        mod.jump_seed_n((12345,) * 6, n)
        assert len(calls) == 2 * bin(n).count('1'), n


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_the_power_table_grows_only_as_far_as_an_exponent_needs(gen):
    mod, m1, _ = GENERATORS[gen]
    table = mrg_common.PowerTable(mod._m1_step, m1)
    assert len(table.powers) == 1                       # nothing squared yet
    seed = (12345, 2, 3)
    first = table.jump(seed, (1 << 59) | 1)
    assert len(table.powers) == 60
    before = table.powers
    table.jump(seed, (1 << 39) | 5)                     # shorter: no growth
    assert table.powers is before
    table.jump(seed, 1 << 129)                          # longer: extended
    assert len(table.powers) == 130
    assert table.powers[:60] == before                  # earlier powers kept
    assert before is not table.powers and len(before) == 60   # replaced, not grown in place
    for k in (0, 1, 7, 59, 60, 129):
        assert table.powers[k] == mrg_common.mat_pow_mod(mod._m1_step, 1 << k, m1), k
    assert table.jump(seed, (1 << 59) | 1) == first
    assert first == mrg_common.jump_n(seed, mod._m1_step, (1 << 59) | 1, m1)


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_a_fresh_interpreter_builds_nothing_until_the_first_general_jump(gen):
    """Import pays nothing; the first general jump extends both tables to
    its bit length; a worker process starts the same way (it imports the
    module afresh under forkserver and spawn)."""
    code = textwrap.dedent('''
        from pymoso.prng import {0} as mod
        t1, t2 = mod._powers1, mod._powers2
        print(len(t1.powers), len(t2.powers))
        mod.stream_at((12345,) * 6, 20, 0)
        print(len(t1.powers), len(t2.powers), (20 * mod.ITER_STRIDE).bit_length())
    ''').format(gen)
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True).stdout.split()
    assert out[:2] == ['1', '1']
    assert out[2] == out[3] == out[4]


@pytest.mark.parametrize("gen", sorted(GENERATORS))
def test_end_seeds_and_results_are_those_the_reference_jump_gives(gen, monkeypatch):
    """The end seed is computed with stream_at, which reaches the same
    jump_seed_n: with a jump that returns the same tuple for every
    exponent it cannot move. Settled by construction, from bit-identity;
    this runs both and compares.

    The end seed is the start of the stream after the run's last
    (Oracle.get_endseed, one_past), so its own jump uses only the bits
    from 127 up; a wrong jump below them moves the run's results but not
    its end seed (so does any jump error in bits 0-13 or in an even
    point code's lowest bit, which no run's exponent sets: offsets are
    code << 52 | visit << 46 | replication << 14, and a non-negative
    coordinate's zigzag code is even). That is why the per-exponent
    comparison above, not this, is the test of every bit."""
    from pymoso.chnutils import solve
    from pymoso.problems.probtpa import ProbTPA
    from pymoso.solvers.rperle import RPERLE
    mod, m1, m2 = GENERATORS[gen]
    current = solve(ProbTPA, RPERLE, (30, 30), budget=1500, seed=(12345,) * 6, generator=gen)
    used = []
    monkeypatch.setattr(mod, 'jump_seed_n',
                        lambda seed, n: (used.append(n), reference_jump_seed_n(mod, m1, m2, seed, n))[1])
    reference = solve(ProbTPA, RPERLE, (30, 30), budget=1500, seed=(12345,) * 6, generator=gen)
    assert any(n > 0 and n & (n - 1) for n in used)     # the reference's general path was reached
    assert current[1] == reference[1]                   # the end seed
    assert current == reference
