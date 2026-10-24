#!/usr/bin/env python
"""
The runtime checks behind docs/algorithm-audit.md (Phase 7 step 7). The
audit is reading; these are the places where reading was not enough.

    python docs/audit_checks.py            # all of them, as the audit reports them

- `pe_counts`: R-PERLE's `pe`, copied verbatim with counters added, run
  beside the shipped solver and required to give identical results.
  Counts how often the traceback, before finding 1 was fixed, read the
  epsilon intervals of the objective it does not constrain (`mcJ` left
  over from the last pass of the `for k` loop) and how often that would
  have changed the traceback's lower bound, along the fixed run,
  how often the counts of epsilon values tie, whether the epsilon-
  placement set ever differs from Min's output, how often PE Step 3
  falls back to Min's output, and the simulations spent in
  `remove_nlwep` on Min's output (on the previous solution until
  finding 3 was fixed).
- `probes`: `get_biparetos` on an exact tie; R-PERLE and R-PE on a
  three-objective and (in a subprocess, since until finding 10 was
  fixed it called sys.exit) a one-objective problem.

Counted, not timed. tests/test_benchmark_scripts.py only checks that it
runs.
"""
import collections
import subprocess
import sys

from pymoso.chnbase import Oracle, _check_warm_start
from pymoso.chnutils import solve
from pymoso.moso import get_biparetos, get_nondom
from pymoso.problems import probtpa, probtpb, probtpc
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE

PROBLEMS = (('ProbTPA', probtpa.ProbTPA, (5, 5)), ('ProbTPB', probtpb.ProbTPB, (5, 5)),
            ('ProbTPC', probtpc.ProbTPC, (5, 5, 5)))


def _audited(counts):
    class Audited(RPERLE):
        def pe(self, aold):
            # rperle.pe, verbatim but for the counts and a dict for each
            # objective's intervals, so the one the traceback uses can be
            # compared with the one it would use for its own objective
            start = self.num_calls
            aold = aold | {self.x0}
            self.upsample(aold)
            _check_warm_start(self, aold)
            mnumin = self.get_min(aold)
            before = self.num_calls
            lweps, _ = self.remove_nlwep(mnumin)
            counts['simulations in remove_nlwep(Min output)'] += self.num_calls - before
            a1new = lweps or mnumin
            counts['pe calls'] += 1
            counts['placement set equals Min output'] += a1new == mnumin
            counts['Step 3 fallback (no LWEP in Min output)'] += not lweps
            c0 = len(a1new)
            epslst, ck, Lk, J = {}, {}, {}, {}
            HI, LO = 1, 0
            for k in range(self.num_obj):
                kcon = 1 - k % 2
                sphat = sorted(a1new, key=lambda t: self.gbar[t][kcon])
                Lk[k] = self.gbar[sphat[0]][kcon] + self.fse(self.sehat[sphat[0]][kcon])
                mcJ = []
                for i in range(1, c0):
                    low_b = self.gbar[sphat[i]][kcon] - self.fse(self.sehat[sphat[i]][kcon])
                    hi_b = self.gbar[sphat[i]][kcon] + self.fse(self.sehat[sphat[i]][kcon])
                    mcJ.append((low_b, hi_b))
                J[k] = mcJ
                overlap = []
                for i1 in range(c0 - 1):
                    is_inJ = False
                    eps_c = mcJ[i1][LO]
                    for j in mcJ:
                        if eps_c > j[LO] and eps_c <= j[HI]:
                            is_inJ = True
                    overlap.append(is_inJ)
                epslst[k] = [mcJ[i][LO] for i in range(c0 - 1) if mcJ[i][LO] > Lk[k] and not overlap[i]]
                ck[k] = len(epslst[k])
            fewest = [k for k in range(self.num_obj) if ck[k] == min(ck.values())]
            k_opt = fewest[0] if len(fewest) == 1 else fewest[int(self.sprn.random()*len(fewest))]
            k_con = 1 - k_opt % 2
            counts['epsilon counts tied (broken by a draw since finding 7)'] += len(fewest) > 1
            # since the fix (finding 1) the traceback reads J[k_opt]; the
            # counts are of how often the code before the fix, which read
            # the last pass's J[num_obj - 1], would have had another bound
            prefix = J[self.num_obj - 1]
            L = Lk[k_opt]
            eps = sorted(epslst[k_opt])
            mcAeps = set()
            for ep in eps:
                counts['tracebacks'] += 1
                lmax = max([j[HI] for j in J[k_opt] if j[HI] < ep], default=float('-inf'))
                old = max([j[HI] for j in prefix if j[HI] < ep], default=float('-inf'))
                epL = max(lmax, L)
                if prefix is not J[k_opt]:
                    counts['tracebacks reading the other objective\'s intervals'] += 1
                    if max(old, L) != epL:
                        counts['... lower bound changed'] += 1
                        counts['... ... higher, so the traceback stops sooner' if max(old, L) > epL
                               else '... ... lower, so the traceback runs longer'] += 1
                epnew = ep
                mcA = set()
                mcT = set()
                while epL < epnew:
                    stpts = {x: self.gbar[x] for x in mnumin | mcT if self.gbar[x][k_con] <= epnew}
                    tbx0 = min(stpts, key=lambda t: self.gbar[t][k_opt])
                    mcTp, xst, fxst, sexst = self.spline(tbx0, epnew, k_opt, k_con)
                    mcA |= {xst}
                    mcT |= mcTp
                    back_dist = self.fse(sexst[k_con])
                    if back_dist == 0.0:
                        back_dist = 0.000001
                    epnew = fxst[k_con] - back_dist
                mcAeps |= mcA
            tmp = {x: self.gbar[x] for x in mcAeps | a1new}
            counts['simulations in pe'] += self.num_calls - start
            return get_biparetos(tmp)
    return Audited


def pe_counts(seeds=range(1, 6), budget=3000, problems=PROBLEMS):
    """Counts over every run; raises if the copy and the shipped solver
    ever differ, in which case the counts would not describe it."""
    counts = collections.Counter()
    audited = _audited(counts)
    runs = 0
    for name, prob, x0 in problems:
        for seed in seeds:
            s = (seed,) * 6
            if solve(prob, RPERLE, x0, budget=budget, seed=s) != solve(prob, audited, x0, budget=budget, seed=s):
                raise AssertionError('the audited copy of pe differs from the shipped one: {0} seed {1}'.format(
                    name, seed))
            runs += 1
    counts['runs, each identical to the shipped R-PERLE'] = runs
    return counts


class _Three(Oracle):
    def __init__(self, rng):
        self.num_obj = 3
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not all(-10 <= v <= 10 for v in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, ((x[0] - 3) ** 2 + z, (x[1] + 2) ** 2 + z, (x[0] + x[1]) ** 2 + z)


_ONE = """
from pymoso.chnutils import solve
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.{0} import {1}
try:
    solve(ProbSimpleSO, {1}, (5,), budget=300, seed=(1,) * 6)
    print('ran')
except SystemExit:
    print('SystemExit')
except BaseException as e:
    print(type(e).__name__)
"""


def probes():
    out = {}
    tied = {(0,): (1.0, 2.0), (1,): (1.0, 2.0), (2,): (0.5, 3.0), (3,): (2.0, 1.0)}
    out['exact tie: get_biparetos keeps'] = sorted(get_biparetos(tied))
    out['exact tie: get_nondom keeps'] = sorted(get_nondom(tied))
    for cls in (RPERLE, RPE):
        try:
            solve(_Three, cls, (0, 0), budget=500, seed=(1,) * 6)
            out[cls.__name__ + ' on three objectives'] = 'ran'
        except Exception as e:
            out[cls.__name__ + ' on three objectives'] = type(e).__name__
        r = subprocess.run([sys.executable, '-c', _ONE.format(cls.__name__.lower(), cls.__name__)],
                           capture_output=True, text=True, timeout=600)
        out[cls.__name__ + ' on one objective'] = r.stdout.strip().splitlines()[-1]
    return out


if __name__ == '__main__':
    for k, v in sorted(pe_counts().items()):
        print('{0:55s} {1}'.format(k, v))
    for k, v in probes().items():
        print('{0:55s} {1}'.format(k, v))
