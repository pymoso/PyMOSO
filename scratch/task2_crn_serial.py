#!/usr/bin/env python
"""
Task 2 continued: since --simpar>1 crashes unconditionally (see
task2_simpar_crash.txt / the transcript), the "does simpar>1+crn produce
correct results" question can't be evaluated for the parallel case at all --
there IS no result, correct or otherwise. So: is CRN itself correct in the
only path that actually executes (simpar=1)?

Build an oracle whose g() reveals the rng stream position it drew from (by
returning the raw uniform draw itself as the "objective"), so a CRN
violation (two different candidate points, evaluated in the same RA
iteration, drawing from different stream positions) is directly observable.
"""
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')
from pymoso.chnbase import Oracle
from pymoso.prng.mrg32k3a import MRG32k3a

seed = (12345, 12345, 12345, 12345, 12345, 12345)


class StreamRevealingOracle(Oracle):
    num_obj = 1
    dim = 1

    def g(self, x, rng):
        # objective value *is* the raw draw + a component tied to x so we
        # can see whether the SAME draw is reused across different x's
        u = rng.random()
        return True, (u,)


def make_orc(crn):
    MRG32k3a.set_class_cache(crn)
    orc = StreamRevealingOracle(MRG32k3a(seed))
    orc.set_crnflag(crn)
    orc.simpar = 1
    return orc


print("=== CRN correctness check (serial, simpar=1) ===")
print("Under CRN: evaluating two DIFFERENT points x1, x2 in the SAME RA")
print("iteration should draw from the IDENTICAL rng stream position (i.e.")
print("produce the SAME raw uniform draw as their first replication),")
print("because crn_check() rewinds to crnold_state after each hit().")
print()

for crn in (False, True):
    orc = make_orc(crn)
    # simulate what one RA iteration looks like: multiple estimate()-style
    # hit() calls at different x, all before crn_advance() is called.
    isfeas1, mean1, se1 = orc.hit((1,), 3)
    isfeas2, mean2, se2 = orc.hit((2,), 3)
    isfeas3, mean3, se3 = orc.hit((3,), 3)
    print(f"crn={crn!s:5}: hit(x=1,m=3) mean={mean1}")
    print(f"          hit(x=2,m=3) mean={mean2}")
    print(f"          hit(x=3,m=3) mean={mean3}")
    same_under_crn = mean1 == mean2 == mean3
    print(f"          all three points got IDENTICAL draws: {same_under_crn}  "
          f"{'<-- correct: this is what CRN means' if crn else '<-- correct: no CRN, draws should differ'}")
    print()

print("=== Now the next RA iteration (after crn_advance()) should give a")
print("=== NEW common baseline under CRN, different from the previous one.")
for crn in (False, True):
    orc = make_orc(crn)
    isfeas1, mean1, se1 = orc.hit((1,), 3)
    orc.crn_advance()
    isfeas2, mean2, se2 = orc.hit((1,), 3)
    print(f"crn={crn!s:5}: iter1 hit(x=1) mean={mean1}, iter2 hit(x=1) mean={mean2}, "
          f"changed={mean1 != mean2}")
