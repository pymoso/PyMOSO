"""
Consumption-sensitive regression tests: unlike tests/test_golden.py's end
seed (see docs/end-seed-scope.md -- it fingerprints the stream-allocation
schedule, not what any stream actually drew), these tests observe the
values MRG32k3a's public draw-producing methods actually return, so a
change like the getrandbits() addition (see KNOWN_ISSUES.md) is visible
here even where it is invisible to end-seed matching.

RecordingMRG32k3a below hooks exactly two methods: random() and
getrandbits(). That is a deliberate, verified claim, not an assumption --
every randomness-producing call this codebase actually makes (grepped
across pymoso/: random, choice, sample, normalvariate, expovariate) routes
through one of those two:

- choice()/sample() -> Random._randbelow (bound to
  _randbelow_with_getrandbits per random.Random.__init_subclass__, since
  MRG32k3a defines getrandbits) -> getrandbits(). Confirmed by
  test_get_ranx0_x0_and_stream_position_matches_baseline below actually
  recording 'getrandbits' entries, not just by reading __init_subclass__.
- normalvariate() (MRG32k3a's own override) and expovariate() (inherited
  from random.Random, checked on both Python 3.10 and 3.14 -- unchanged
  between them) each call self.random() exactly once per variate and
  nothing else. test_normalvariate_and_expovariate_route_through_random
  below confirms this empirically, in situ, through the actual Oracle.g()
  call paths that use each (ProbTPA and BSProb respectively), not just by
  reading CPython's source.

COVERAGE BOUNDARY, found while building this: this file's recorder sees
everything a solve()-based scenario draws (simpar=1 never touches a
Pool), but for testsolve() it only sees draws made in the parent
process, not draws made inside a pool worker. chnutils.testsolve()
always dispatches each independent sample path's actual replication
work through a multiprocessing.Pool (chnutils.par_runs) -- unconditionally,
not gated behind proc > 1, so even --proc=1 runs replications in a
worker process, not the caller's. A recorder monkeypatched into the
parent process cannot observe draws made inside that worker, regardless
of start method (fork's copy-on-write would carry the patch across;
spawn/forkserver's fresh re-import would not, and this environment
defaults to forkserver -- see the --proc=1 case below, which is why it
only checks parent-process work: stream creation and get_ranx0, not
TPATester.g()'s own draws). Recording testsolve()'s in-pool
replications, if ever wanted, needs a mechanism that survives the pool
boundary (e.g. a start method forced to 'fork', or per-worker patching
via the pool initializer) -- out of scope here. The ProbTPA/BSProb
checks below sidestep this entirely by calling Oracle.g() directly,
not through solve()/testsolve().
"""
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.chnutils import testsolve
from pymoso.testers.tpatester import TPATester
from pymoso.solvers.rperle import RPERLE
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.bsprob import BSProb
import pymoso.prng.mrg32k3a as mrg32k3a_module
import pymoso.chnutils as chnutils_module


class RecordingMRG32k3a(MRG32k3a):
    """MRG32k3a that appends every random()/getrandbits() return value to
    a shared list, so a test can inspect exactly what was drawn and in
    what order -- see the module docstring for why these two methods are
    the complete set of hook points this codebase needs."""

    def __init__(self, x=None, sink=None):
        self._sink = sink if sink is not None else []
        super().__init__(x)

    def random(self):
        u = super().random()
        self._sink.append(('random', u))
        return u

    def getrandbits(self, k):
        v = super().getrandbits(k)
        self._sink.append(('getrandbits', k, v))
        return v


# ---------------------------------------------------------------------------
# Candidate D, part 1: confirm the two hook points really do see everything
# -- normalvariate (ProbTPA.g) and expovariate (BSProb.g), called through
# the real Oracle.g() path, not a standalone call to the distribution
# method in isolation.
# ---------------------------------------------------------------------------

def test_normalvariate_and_expovariate_route_through_random():
    sink = []
    rng = RecordingMRG32k3a((1, 2, 3, 4, 5, 6), sink=sink)
    isfeas, obj = ProbTPA(rng).g((10, 10), rng)
    assert isfeas
    assert sink, "ProbTPA.g() drew nothing -- test is not exercising normalvariate"
    assert all(kind == 'random' for kind, *_ in sink), (
        "normalvariate produced a non-'random' entry -- it no longer routes "
        f"through random() alone: {sink}"
    )

    sink.clear()
    rng2 = RecordingMRG32k3a((1, 2, 3, 4, 5, 6), sink=sink)
    isfeas2, obj2 = BSProb(rng2).g((10, 20, 30, 40, 50, 60, 70, 80, 90), rng2)
    assert isfeas2
    assert len(sink) > 100, "BSProb.g() should draw many expovariate arrivals"
    assert all(kind == 'random' for kind, *_ in sink), (
        "expovariate produced a non-'random' entry -- it no longer routes "
        f"through random() alone (first 5: {sink[:5]})"
    )


# ---------------------------------------------------------------------------
# Candidate D, part 2: the actual consumption-sensitive regression. This is
# the getrandbits() path (choice(), via TPATester.get_ranx0), captured
# through testsolve()'s real, unmodified call sequence -- both
# construction sites (chnutils.MRG32k3a and prng.mrg32k3a.MRG32k3a; see
# get_testsolve_prnstreams and get_next_prnstream) are patched so every
# stream testsolve() creates in-process is a RecordingMRG32k3a.
#
# Verified this actually catches the getrandbits change before trusting
# it (a detector never observed detecting is not proven to work -- same
# discipline as tests/test_simpar_worker_lifecycle.py): forcing
# RecordingMRG32k3a._randbelow = random.Random._randbelow_without_getrandbits
# (the pre-getrandbits fallback) for this exact scenario recorded
# [('random', 0.12701112204657714), ('random', 0.3185275653967945)]
# instead of the getrandbits-based baseline below -- a different kind of
# entry, not just different values. Recorded here for the historical
# record; not a live check, per the same discipline.
# ---------------------------------------------------------------------------

def test_getrandbits_draw_sequence_matches_baseline(monkeypatch):
    sink = []

    def make(x=None):
        return RecordingMRG32k3a(x, sink=sink)

    monkeypatch.setattr(mrg32k3a_module, 'MRG32k3a', make)
    monkeypatch.setattr(chnutils_module, 'MRG32k3a', make)

    testsolve(
        TPATester, RPERLE, (0,),
        budget=60, seed=(12345,) * 6, isp=1, proc=1, crn=False, ranx0=True,
    )

    assert sink == [('getrandbits', 6, 44), ('getrandbits', 6, 1)]


# ---------------------------------------------------------------------------
# Candidate C: a narrow, cheap pin directly on the mechanism this bug
# touches -- no solver, no budget, one deterministic function call.
# ---------------------------------------------------------------------------

def test_get_ranx0_x0_and_stream_position_matches_baseline():
    xprn = MRG32k3a((12345,) * 6)
    x0 = TPATester().get_ranx0(xprn)
    assert x0 == (44, 1)
    assert xprn.get_seed() == (12345, 3023790853, 3023790853, 12345, 2478282264, 1655725443)
