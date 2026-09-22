#!/usr/bin/env python
"""
Task 5: direct exercise of Oracle.bump(), compared against Oracle.hit().

Checks:
  - return shape of bump() matches its docstring
  - bump()'s raw per-replication observations, independently aggregated,
    match hit()'s aggregated mean/se exactly (same rng, same crn state)
  - num_calls accounting: does bump() touch self.num_calls / self.gbar /
    self.sehat itself, the way RASolver.estimate() does after calling hit()?
  - CRN interaction: does bump() honor crnflag/crn_check the same way hit()
    does?
  - simpar: does bump() have a parallel branch like hit() does?
"""
import sys
from statistics import mean, variance
from math import sqrt
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.problems.probtpa import ProbTPA

seed = (12345, 12345, 12345, 12345, 12345, 12345)


def fresh_orc(crn):
    MRG32k3a.set_class_cache(crn)
    rng = MRG32k3a(seed)
    orc = ProbTPA(rng)
    orc.set_crnflag(crn)
    return orc


print("=== 1. Return shape ===")
orc = fresh_orc(False)
isfeas, obs = orc.bump((40, 40), 5)
print(f"  isfeas={isfeas} (type {type(isfeas).__name__})")
print(f"  obs={obs}")
print(f"  type(obs)={type(obs).__name__}, len(obs)={len(obs)}, "
      f"type(obs[0])={type(obs[0]).__name__}, len(obs[0])={len(obs[0])}")
print()

print("=== 2. bump()'s raw obs, hand-aggregated, vs hit()'s obmean/obse (same starting rng state) ===")
for crn in (False, True):
    for m in (1, 2, 5, 13):
        orc_bump = fresh_orc(crn)
        isfeas_b, obs = orc_bump.bump((40, 40), m)

        orc_hit = fresh_orc(crn)
        isfeas_h, obmean, obse = orc_hit.hit((40, 40), m)

        d = len(obs[0])
        hand_mean = tuple(mean([obs[i][k] for i in range(m)]) for k in range(d))
        if m > 1:
            hand_var = [variance([obs[i][k] for i in range(m)], hand_mean[k]) for k in range(d)]
            hand_se = tuple(sqrt(v / m) for v in hand_var)
        else:
            hand_se = tuple(0 for _ in range(d))

        match_feas = isfeas_b == isfeas_h
        match_mean = hand_mean == obmean
        match_se = hand_se == obse
        print(f"  crn={crn!s:5} m={m:>3}: feas match={match_feas}  mean match={match_mean}  se match={match_se}")
        if not (match_feas and match_mean and match_se):
            print(f"    bump-derived: feas={isfeas_b} mean={hand_mean} se={hand_se}")
            print(f"    hit()       : feas={isfeas_h} mean={obmean} se={obse}")

        # also confirm bump and hit consume/advance rng identically (same
        # post-call rng state), since both should call crn_nextobs() once
        # per replication then crn_check()
        same_end_state = orc_bump.rng.getstate() == orc_hit.rng.getstate()
        print(f"      post-call rng state match: {same_end_state}")
print()

print("=== 3. num_calls / gbar / sehat accounting ===")
orc = fresh_orc(False)
has_num_calls_before = hasattr(orc, 'num_calls')
print(f"  Oracle has a num_calls attribute at all: {has_num_calls_before}")
orc.bump((40, 40), 5)
has_num_calls_after = hasattr(orc, 'num_calls')
has_gbar = hasattr(orc, 'gbar')
has_sehat = hasattr(orc, 'sehat')
print(f"  after bump(): has num_calls={has_num_calls_after}, has gbar={has_gbar}, has sehat={has_sehat}")
print("  (num_calls/gbar/sehat are RASolver attributes, not Oracle attributes; "
      "bump(), like hit(), never touches them -- it is the *caller*'s job, "
      "the way RASolver.estimate() does after calling orc.hit(), to do so.)")
print()

print("=== 4. simpar / parallel branch ===")
orc = fresh_orc(False)
orc.simpar = 4
import time
t0 = time.time()
isfeas, obs = orc.bump((40, 40), 20)
t1 = time.time()
print(f"  orc.simpar=4 set; bump(x, 20) still returns {len(obs)} raw obs in {t1-t0:.4f}s")
import inspect
src = inspect.getsource(orc.bump)
print(f"  'mp.Pool' or 'simpar' referenced inside bump() source: "
      f"{'mp.Pool' in src or 'self.simpar' in src}")
print("  (confirms bump() has NO parallel branch -- it always runs serially, "
      "silently ignoring self.simpar, unlike hit() which branches into a "
      "mp.Pool path when self.simpar > 1 and m > 1.)")
