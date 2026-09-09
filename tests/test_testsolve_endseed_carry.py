"""
docs/rng-interface-design.md §12 step 6c: testsolve()'s own combined-
endseed carry (chnutils.py), exercised directly through the real
function -- not just through pymoso.prng.base.one_past in isolation
(tests/test_stream_offset_carry.py) or through Oracle.get_endseed()'s
own wiring (tests/test_oracle_endseed.py). This is a distinct call
site with its own family_capacity/offset_capacity choices (composing
isp*ISP_ITER_MARGIN with each path's own oracle_stream); a copy-paste
error here (e.g. the wrong constant) would not be caught by either of
those other two files.

par_runs is monkeypatched to return controlled per-path
oracle_high_water_mark values directly -- MRG32k3a's own
ISP_ITER_MARGIN=2**32 makes the raise unreachable through real solving,
the same reason tests/test_oracle_endseed.py's own boundary tests use
white-box state instead of millions of real iterations.
"""
import pytest

from pymoso import chnutils
from pymoso.chnutils import testsolve, get_testsolve_prnstreams
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester
from pymoso.prng.mrg32k3a import ITER_STRIDE, ISP_ITER_MARGIN, jump_seed_n
from pymoso.prng.base import StreamFamilyExceeded

SEED = (12345,) * 6


def _fake_par_runs_returning(hwm_per_path):
    """A stand-in for chnutils.par_runs: ignores the real joblist,
    returns one result dict per path with the given
    oracle_high_water_mark and otherwise-empty content -- enough for
    testsolve()'s own combination logic, which only reads that one key
    plus whatever it copies through untouched."""
    def fake(joblist, proc):
        return {t: {'itersoln': {}, 'simcalls': {}, 'endseed': None,
                     'oracle_high_water_mark': hwm_per_path[t]}
                for t in range(len(joblist))}
    return fake


def test_combined_endseed_matches_the_winning_paths_own_touch(monkeypatch):
    """Two paths, path 1 touching further than path 0 -- the combined
    endseed must reflect path 1's own (stream, offset), composed with
    its own isp offset (1*ISP_ITER_MARGIN), not path 0's."""
    hwm_per_path = {0: (3, 100), 1: (5, 200)}
    monkeypatch.setattr(chnutils, 'par_runs', _fake_par_runs_returning(hwm_per_path))
    _res, endseed = testsolve(TPATester, RPERLE, (40, 40), budget=1000, seed=SEED, isp=2, proc=1, crn=False)
    _orcstreams, _solvstreams, _x0stream, _iseed, orc_root = get_testsolve_prnstreams(2, SEED)
    expected_stream = 1 * ISP_ITER_MARGIN + 5
    expected = jump_seed_n(orc_root, expected_stream * ITER_STRIDE + 201)  # offset+1, no carry
    assert endseed == expected


def test_combined_endseed_carries_safely_within_a_paths_own_family(monkeypatch):
    hwm_per_path = {0: (0, 0), 1: (ISP_ITER_MARGIN - 2, ITER_STRIDE - 1)}
    monkeypatch.setattr(chnutils, 'par_runs', _fake_par_runs_returning(hwm_per_path))
    _res, endseed = testsolve(TPATester, RPERLE, (40, 40), budget=1000, seed=SEED, isp=2, proc=1, crn=False)
    _orcstreams, _solvstreams, _x0stream, _iseed, orc_root = get_testsolve_prnstreams(2, SEED)
    expected_stream = 1 * ISP_ITER_MARGIN + (ISP_ITER_MARGIN - 1)
    expected = jump_seed_n(orc_root, expected_stream * ITER_STRIDE)  # offset carried to 0
    assert endseed == expected


def test_combined_endseed_raises_at_a_paths_own_family_boundary(monkeypatch):
    """Path 1's own touch is at its own family boundary
    (ISP_ITER_MARGIN-1, ITER_STRIDE-1) -- one past it would carry into
    stream=ISP_ITER_MARGIN, spilling into what would be isp path 2's
    own reserved zone. Must raise, the same as Oracle.get_endseed()'s
    own boundary case."""
    hwm_per_path = {0: (0, 0), 1: (ISP_ITER_MARGIN - 1, ITER_STRIDE - 1)}
    monkeypatch.setattr(chnutils, 'par_runs', _fake_par_runs_returning(hwm_per_path))
    with pytest.raises(StreamFamilyExceeded):
        testsolve(TPATester, RPERLE, (40, 40), budget=1000, seed=SEED, isp=2, proc=1, crn=False)


def test_combined_endseed_falls_back_to_orc_root_when_no_path_touched_anything(monkeypatch):
    hwm_per_path = {0: None, 1: None}
    monkeypatch.setattr(chnutils, 'par_runs', _fake_par_runs_returning(hwm_per_path))
    _res, endseed = testsolve(TPATester, RPERLE, (40, 40), budget=1000, seed=SEED, isp=2, proc=1, crn=False)
    _orcstreams, _solvstreams, _x0stream, _iseed, orc_root = get_testsolve_prnstreams(2, SEED)
    assert endseed == orc_root
