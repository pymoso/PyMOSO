"""
RLESolver.get_ncn does the work its definition needs, and gives the
answer it always gave (docs/phase7-plan.md, step 2).

`reference_get_ncn` below is the implementation before Phase 7, kept
verbatim as the reference. Do not "tidy" it: it is what the current
`get_ncn` is held to, answer for answer and in the same order (solvers
iterate the returned set, so insertion order is part of the answer;
see tests/test_get_nbors_equivalence.py).

The work is counted, never timed.
"""
import random

import pytest

from pymoso import chnbase
from pymoso.chnbase import does_dominate, does_strict_dominate, does_weak_dominate
from pymoso.moso import get_nbors, get_setnbors
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rminrle import RMINRLE


def reference_get_ncn(self, mcS):
    # initialize the non-conforming neighborhood
    ncn = set()
    #nisdom = set()
    d = self.num_obj
    r = self.nbor_rad
    dr = range(d)
    delN = get_setnbors(mcS, r)
    delzero = tuple(0 for i in dr)
    # defintion 9 (a) -- check for strict domination in the deleted nbors
    # Every deleted neighbour is estimated whatever the results
    # are, so they are estimated together.
    pairs = [(s, x) for s in mcS for x in get_nbors(s, r) - mcS]
    estimates = self.estimate_many([x for s, x in pairs])
    for (s, x), (isfeas, fx, sex) in zip(pairs, estimates):
        fs = self.gbar[s]
        ses = self.sehat[s]
        #dels = tuple(self.calc_delta(ses[i]) for i in dr)
        if isfeas:
            #delx = tuple(self.calc_delta(sex[i]) for i in dr)
            if does_strict_dominate(fx, fs, delzero, delzero):
                ncn |= {x}
            # if does_strict_dominate(fs, fx, delzero, delzero):
            #     nisdom |= {x}
    # definition 9 (b) initialization
    candidates = list(delN - ncn)
    for x, (isfeas, fx, sex) in zip(candidates, self.estimate_many(candidates)):
        if isfeas:
            # definition 9 (b) (i) initialization
            notweakdom = True
            # definition 9 (b) (ii) initialization
            notrelaxdom = True
            # definition 9 (b) (iii) initialization
            wouldnotchange = True
            doesweakdom = False
            # set the relaxation of the neighbor
            delx = tuple(self.calc_delta(sex[i]) for i in dr)
            for s in mcS:
                fs = self.gbar[s]
                ses = self.sehat[s]
                if does_weak_dominate(fx, fs, delzero, delzero):
                    doesweakdom = True
            for s in mcS:
                fs = self.gbar[s]
                ses = self.sehat[s]
                # set the relaxation of the LES candidate member
                dels = tuple(self.calc_delta(ses[i]) for i in dr)
                # definition 9 (b) (i)
                if does_weak_dominate(fs, fx, delzero, delzero):
                    notweakdom = False
                # definition 9 (b) (ii)
                if does_dominate(fx, fs, delzero, delzero) and does_weak_dominate(fs, fx, dels, delx):
                    notrelaxdom = False
                # definition 9 (b) (iii)
                if does_weak_dominate(fs, fx, dels, delx) or does_weak_dominate(fx, fs, delx, dels):
                    wouldnotchange = False
            # definition 9 (b)
            if notweakdom and notrelaxdom and (doesweakdom or wouldnotchange):
                ncn |= {x}
    return ncn


def _solver(m):
    orc = ProbTPA(mrg32k3a.stream_at(mrg32k3a.DEFAULT_SEED, 1, 0))
    orc.set_crnflag(False)
    orc.set_simpar(1)
    solver = RMINRLE(orc, sprn=None, x0=(5, 5))
    solver.m = m
    solver.gbar = {}
    solver.sehat = {}
    return solver


def _sets(count):
    """Sets of points in ProbTPA's domain, some touching its edge so
    that some neighbours are infeasible."""
    rng = random.Random(20261016)
    for k in range(count):
        size = rng.randint(1, 8)
        lo = 0 if k % 3 == 0 else 20
        yield {(rng.randint(lo, lo + 12), rng.randint(lo, lo + 12)) for _ in range(size)}


def _with_mcS(solver, mcS):
    """mcS's own estimates, as an RA iteration would hold them."""
    solver.estimate_many(sorted(mcS))
    return {x for x in mcS if x in solver.gbar}


def test_get_ncn_gives_the_reference_answer_in_the_reference_order():
    compared = 0
    for k, points in enumerate(_sets(40)):
        solver = _solver(m=4 + k % 5)
        mcS = _with_mcS(solver, points)
        if not mcS:
            continue
        got = solver.get_ncn(mcS)
        # Every feasible neighbour is now in gbar, and the infeasible
        # ones are infeasible by position, so the reference sees the
        # same estimates.
        want = reference_get_ncn(solver, mcS)
        assert list(got) == list(want), (k, sorted(mcS))
        compared += 1
    assert compared >= 35


def test_each_relaxation_is_computed_once_per_point(monkeypatch):
    """calc_delta once per objective for each member of mcS and each
    feasible candidate; it used to be once per member per candidate."""
    calls = []
    real = chnbase.RLESolver.calc_delta
    monkeypatch.setattr(chnbase.RLESolver, 'calc_delta',
                        lambda self, se: calls.append(se) or real(self, se))
    checked = 0
    for points in _sets(20):
        solver = _solver(m=5)
        mcS = _with_mcS(solver, points)
        if len(mcS) < 2:
            continue
        candidates = [x for x in get_setnbors(mcS, solver.nbor_rad)]
        solver.estimate_many(candidates)
        feasible = [x for x in candidates if x in solver.gbar]
        calls.clear()
        solver.get_ncn(mcS)
        assert calls, 'the substitute was never reached'
        assert len(calls) <= (len(mcS) + len(feasible)) * solver.num_obj
        checked += 1
    assert checked >= 10
