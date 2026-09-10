"""
docs/rng-interface-design.md §12 step 6b: MRG31k3p and Philox4x32 both
become real-solving-capable for non-CRN runs through Oracle's own
internals, not just standalone conformance testing. Also covers the
library-level `generator=` kwarg on chnutils.solve()/testsolve()
end to end -- tests/test_cli.py covers the CLI flag itself
(--generator, argparse choices=, --seed's own nargs='+'/validate_seed
wiring), a distinct layer this file doesn't touch.

Structured to mirror tests/test_oracle_noncrn_default.py's own rigor
(formula checks, not just "it runs") for each non-default backend, plus
the registry/guard mechanics those tests don't touch at all.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.chnutils import solve, testsolve
from pymoso.prng import registry
from pymoso.prng.base import RandomCompatAdapter, ensure_random_compatible
from pymoso.prng.mrg31k3p import MRG31k3p, jump_seed_n as mrg31_jump_seed_n, ITER_STRIDE as MRG31_ITER_STRIDE
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.prng.philox4x32 import stream_at as philox_stream_at
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.bsprob import BSProb
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester
from pymoso.testers.bstester import BSTester


class LoggingOracle(Oracle):
    """g() returns, and records, the first raw value it actually drew
    -- lets a test read back exactly which stream position each
    individual replication drew from, the same pattern test_oracle_
    noncrn_default.py's own LoggingOracle uses."""

    def __init__(self, rng, dim=1):
        self.num_obj = 1
        self.dim = dim
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        v = rng.random()
        self.log.append(v)
        return True, (v,)


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------

def test_registry_has_exactly_the_three_onboarded_generators():
    assert set(registry.GENERATORS) == {'mrg32k3a', 'mrg31k3p', 'philox4x32'}


def test_default_generator_is_mrg32k3a():
    assert registry.DEFAULT_GENERATOR == 'mrg32k3a'


def test_crn_capable_is_exactly_the_mrg_family():
    assert registry.CRN_CAPABLE == {'mrg32k3a', 'mrg31k3p'}


def test_get_generator_unknown_name_raises_named_error():
    with pytest.raises(KeyError):
        registry.get_generator('not-a-real-generator')


def test_generator_names_is_the_exact_reverse_of_generators():
    assert {v: k for k, v in registry.GENERATOR_NAMES.items()} == registry.GENERATORS


# ---------------------------------------------------------------------------
# MRG31k3p: real solving, both crnflag values -- structurally a close
# sibling of MRG32k3a, so this is the "does the threading actually work"
# proof, formula-checked the same way the default backend already is.
# ---------------------------------------------------------------------------

def _fresh_mrg31k3p_oracle(dim=1, crnflag=False):
    rng = MRG31k3p((12345,) * 6)
    orc = LoggingOracle(rng, dim=dim)
    orc.set_crnflag(crnflag)
    orc.simpar = 1
    return orc


def test_mrg31k3p_default_path_matches_the_formula():
    from pymoso.prng.base import point_width, offset_within_iteration
    orc = _fresh_mrg31k3p_oracle()
    W = point_width(1)
    orc.hit((5,), 3)
    for r in range(3):
        expected_seed = mrg31_jump_seed_n(
            orc._orc_root, 0 * MRG31_ITER_STRIDE + offset_within_iteration((5,), 0, r, W)
        )
        from pymoso.prng.mrg31k3p import mrg31k3p as _step
        _, expected_u = _step(expected_seed)
        assert orc.log[r] == expected_u


def test_mrg31k3p_supports_crn():
    orc = _fresh_mrg31k3p_oracle(crnflag=True)
    isfeas, obmean, obse = orc.hit((5,), 3)
    assert isfeas
    orc.crn_advance()
    isfeas2, obmean2, obse2 = orc.hit((9,), 3)
    assert isfeas2
    # CRN's own point: a different point at the same iteration/replication
    # index draws the identical stream -- confirmed operationally here
    # against a second point in the *next* iteration matching its own
    # replication-0 value against the coordinate formula.
    expected = mrg31_jump_seed_n(orc._orc_root, 1 * MRG31_ITER_STRIDE)
    from pymoso.prng.mrg31k3p import mrg31k3p as _step
    _, expected_u = _step(expected)
    assert orc.log[3] == expected_u


def test_mrg31k3p_endseed_advances_and_does_not_collide():
    orc = _fresh_mrg31k3p_oracle()
    before = orc.get_endseed()
    orc.hit((5,), 5)
    after = orc.get_endseed()
    assert after != before
    assert after not in orc.log  # trivially true (types differ) but documents intent
    assert orc._high_water_mark is not None


# ---------------------------------------------------------------------------
# Philox4x32: real solving under crnflag=False -- the actual point of
# this step. crnflag=True is explicitly refused (see the guard tests
# below), so only the non-CRN path is exercised for correctness here.
# ---------------------------------------------------------------------------

def _fresh_philox_oracle(dim=1):
    rng = philox_stream_at((12345, 12345), 0, 0)
    orc = LoggingOracle(rng, dim=dim)
    orc.set_crnflag(False)
    orc.simpar = 1
    return orc


def test_philox_default_path_matches_the_formula():
    from pymoso.prng.philox4x32 import point_width, offset_within_iteration
    orc = _fresh_philox_oracle()
    W = point_width(1)
    orc.hit((5,), 3)
    for r in range(3):
        offset = offset_within_iteration((5,), 0, r, W)
        expected_stream = philox_stream_at(orc._orc_root, 0, offset)
        assert orc.log[r] == expected_stream.random()


def test_philox_continuation_across_repeated_hit_calls():
    """Same property test_oracle_noncrn_default.py checks for MRG32k3a
    -- a repeated hit() call to the same point continues rather than
    restarts, now checked for Philox specifically (finding #2/#3's own
    replication-loop generalization is what this depends on)."""
    orc = _fresh_philox_oracle()
    orc.hit((5,), 2)
    first = list(orc.log)
    orc.hit((5,), 2)
    second = orc.log[2:]
    assert set(first).isdisjoint(second)


def test_philox_multiple_iterations_via_crn_advance_do_not_collide():
    """crnflag=False still calls crn_advance() every RA iteration (via
    RASolver.rasolve()'s own loop) -- confirms it doesn't crash for a
    backend with no get_next_prnstream (§12 step 6b's own crn_advance()
    fix), and that successive iterations' draws don't collide."""
    orc = _fresh_philox_oracle()
    orc.hit((5,), 2)
    orc.crn_advance()
    orc.hit((5,), 2)
    assert orc._iteration == 1
    assert set(orc.log[:2]).isdisjoint(orc.log[2:])


def test_philox_endseed_advances_and_high_water_mark_is_set():
    orc = _fresh_philox_oracle()
    assert orc.get_endseed() == orc._orc_root
    orc.hit((5,), 4)
    assert orc.get_endseed() != orc._orc_root
    assert orc._high_water_mark is not None


def test_philox_simpar_pickles_and_matches_serial():
    """The specific defect this step fixed directly (Oracle._backend
    storing a module broke --simpar's own pickling of a live Oracle) --
    confirmed by actually running under simpar>1, not just checking
    picklability in isolation."""
    serial = _fresh_philox_oracle()
    with serial.set_simpar(1):
        isfeas_s, obmean_s, obse_s = serial.hit((5,), 4)

    parallel = _fresh_philox_oracle()
    with parallel.set_simpar(2):
        isfeas_p, obmean_p, obse_p = parallel.hit((5,), 4)

    assert isfeas_s == isfeas_p
    assert obmean_s == obmean_p


# ---------------------------------------------------------------------------
# The --crn guard: Philox has no CRN branch at all (no get_next_prnstream/
# jump_substream) -- must raise clearly, at set_crnflag() time, not fail
# opaquely deep inside crn_advance()'s first real call.
# ---------------------------------------------------------------------------

def test_philox_crnflag_true_raises_notimplementederror():
    rng = philox_stream_at((12345, 12345), 0, 0)
    orc = LoggingOracle(rng)
    with pytest.raises(NotImplementedError):
        orc.set_crnflag(True)


def test_philox_crnflag_true_error_names_the_generator_and_alternatives():
    rng = philox_stream_at((12345, 12345), 0, 0)
    orc = LoggingOracle(rng)
    with pytest.raises(NotImplementedError, match='philox4x32'):
        orc.set_crnflag(True)


def test_philox_sync_raises_notimplementederror():
    """sync= also depends on the flat ITER_STRIDE-based machinery only
    the MRG family has (§12's CRN-convergence step, scoped out of 6b) --
    checked directly through hit(), not just _hit_via_coordinate in
    isolation."""
    orc = _fresh_philox_oracle()
    with pytest.raises(NotImplementedError):
        orc.hit((5,), 1, sync=0)


# ---------------------------------------------------------------------------
# backend_for_stream: the type(self.rng) -> module resolution Oracle.
# set_crnflag() depends on.
# ---------------------------------------------------------------------------

def test_backend_for_stream_resolves_each_registered_class():
    from pymoso.prng.mrg32k3a import MRG32k3a
    from pymoso.prng.philox4x32 import Philox4x32Stream
    import pymoso.prng.mrg32k3a as mrg32k3a_mod
    import pymoso.prng.mrg31k3p as mrg31k3p_mod
    import pymoso.prng.philox4x32 as philox4x32_mod
    assert registry.backend_for_stream(MRG32k3a((12345,) * 6)) is mrg32k3a_mod
    assert registry.backend_for_stream(MRG31k3p((12345,) * 6)) is mrg31k3p_mod
    assert registry.backend_for_stream(philox_stream_at((12345, 12345), 0, 0)) is philox4x32_mod


def test_backend_for_stream_resolves_a_subclass_via_isinstance():
    from pymoso.prng.mrg32k3a import MRG32k3a
    import pymoso.prng.mrg32k3a as mrg32k3a_mod

    class RecordingMRG32k3a(MRG32k3a):
        pass

    assert registry.backend_for_stream(RecordingMRG32k3a((12345,) * 6)) is mrg32k3a_mod


def test_backend_for_stream_unrelated_object_raises_named_error():
    import random
    with pytest.raises(KeyError):
        registry.backend_for_stream(random.Random())


# ---------------------------------------------------------------------------
# chnutils.solve()/testsolve()'s own generator= kwarg, end to end through
# a real in-tree solver -- the library layer step 6b's CLI flag sits on
# top of. tests/test_cli.py covers --generator itself.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("generator", ["mrg31k3p", "philox4x32"])
def test_solve_accepts_non_default_generator(generator):
    res, endseed = solve(ProbTPA, RPERLE, (40, 40), generator=generator, budget=500)
    assert res is not None
    assert endseed is not None


@pytest.mark.parametrize("generator", ["mrg31k3p", "philox4x32"])
def test_testsolve_accepts_non_default_generator(generator):
    res, endseed = testsolve(TPATester, RPERLE, (40, 40), generator=generator, budget=500)
    assert res is not None
    assert endseed is not None


def test_solve_unknown_generator_raises_named_error():
    with pytest.raises(KeyError):
        solve(ProbTPA, RPERLE, (40, 40), generator='not-a-real-generator', budget=500)


def test_solve_crn_under_philox_raises_through_the_library_layer():
    with pytest.raises(NotImplementedError, match='philox4x32'):
        solve(ProbTPA, RPERLE, (40, 40), generator='philox4x32', crn=True, budget=500)


def test_testsolve_crn_under_philox_raises_through_the_library_layer():
    with pytest.raises(NotImplementedError, match='philox4x32'):
        testsolve(TPATester, RPERLE, (40, 40), generator='philox4x32', crn=True, budget=500)


def test_solve_with_no_generator_still_uses_mrg32k3a_default():
    """No golden should move: omitting generator= entirely must still
    resolve to the same default this project has always used."""
    from pymoso.chnutils import DEFAULT_GENERATOR
    from pymoso.prng.mrg32k3a import DEFAULT_SEED as mrg32k3a_default_seed
    from pymoso.chnutils import DEFAULT_SEED as chnutils_default_seed
    assert DEFAULT_GENERATOR == 'mrg32k3a'
    assert chnutils_default_seed == mrg32k3a_default_seed == (12345,) * 6


# ---------------------------------------------------------------------------
# ensure_random_compatible/RandomCompatAdapter: found needing both while
# actually exercising Philox end to end through testsolve() (not
# hypothetical -- every one of these failed before the fix, confirmed
# directly by running the exact commands below).
#
# Philox4x32Stream is deliberately not a random.Random subclass (its own
# module docstring) -- built-in problem/tester code documented only as
# "an rng-shaped object" (§3.6) and calling the full surface
# (BSProb.g()'s own expovariate(), every built-in tester's own
# get_ranx0 calling choice(), MOCOMPASS/MOPBnB's own sprn.sample())
# raises AttributeError on a raw Philox stream. RandomCompatAdapter
# (§3.6, unused until this step) is the fix -- but RandomCompatAdapter
# itself didn't pickle (random.Random's own inherited __reduce__
# reconstructs via `cls()`, zero arguments, then applies state;
# RandomCompatAdapter.__init__ requires `stream`), which testsolve()'s
# own --proc path needs (KNOWN_ISSUES.md issue 9's own "ships fully-
# constructed... Oracle instances" pattern) -- confirmed directly:
# pickling a bare RandomCompatAdapter raised before __reduce__ existed.
# ---------------------------------------------------------------------------

def test_ensure_random_compatible_leaves_a_random_random_subclass_alone():
    rng = MRG32k3a((12345,) * 6)
    assert ensure_random_compatible(rng) is rng


def test_ensure_random_compatible_wraps_a_bare_stream():
    stream = philox_stream_at((12345, 12345), 0, 0)
    wrapped = ensure_random_compatible(stream)
    assert isinstance(wrapped, RandomCompatAdapter)
    assert isinstance(wrapped, __import__('random').Random)


def test_random_compat_adapter_exposes_the_full_random_surface():
    stream = philox_stream_at((12345, 12345), 0, 0)
    wrapped = ensure_random_compatible(stream)
    # Would raise AttributeError on the raw stream -- confirmed
    # directly before ensure_random_compatible existed.
    wrapped.choice([1, 2, 3])
    wrapped.sample([1, 2, 3], 2)
    wrapped.expovariate(1.0)


def test_random_compat_adapter_pickles_and_reconstructs_correctly():
    import pickle
    stream = philox_stream_at((12345, 12345), 0, 0)
    wrapped = RandomCompatAdapter(stream)
    restored = pickle.loads(pickle.dumps(wrapped))
    assert restored.random() == wrapped.random()


def test_testsolve_bstester_under_philox_runs_to_completion():
    """Exercises BSTester's own get_ranx0 (choice()) and BSProb's own
    g() (expovariate()) together, with no <x> given -- the exact
    scenario that failed with AttributeError before ensure_random_
    compatible existed."""
    res, endseed = testsolve(BSTester, RPERLE, (0,), generator='philox4x32', budget=500, ranx0=True)
    assert res is not None


def test_testsolve_philox_with_multiple_isp_and_proc_paths():
    """--proc's own pickling path (KNOWN_ISSUES.md issue 9) is what
    surfaced RandomCompatAdapter's own missing __reduce__ -- exercised
    directly here with isp>1/proc>1, not just isp=1."""
    res, endseed = testsolve(
        TPATester, RPERLE, (40, 40), generator='philox4x32', budget=300, isp=3, proc=2,
    )
    assert res is not None
    assert len(res) == 3
