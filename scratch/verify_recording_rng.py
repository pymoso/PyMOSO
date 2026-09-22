import random
import pymoso.prng.mrg32k3a as mrg32k3a_module
import pymoso.chnutils as chnutils
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.chnutils import solve, testsolve
from pymoso.testers.tpatester import TPATester
from pymoso.solvers.rperle import RPERLE
from pymoso.problems.bsprob import BSProb

DRAWS = []

class RecordingMRG32k3a(MRG32k3a):
    def random(self):
        u = super().random()
        DRAWS.append(('random', u))
        return u

    def getrandbits(self, k):
        v = super().getrandbits(k)
        DRAWS.append(('getrandbits', k, v))
        return v


def patch():
    mrg32k3a_module.MRG32k3a = RecordingMRG32k3a
    chnutils.MRG32k3a = RecordingMRG32k3a


def unpatch():
    mrg32k3a_module.MRG32k3a = MRG32k3a
    chnutils.MRG32k3a = MRG32k3a


# --- 1) Confirm expovariate (BSProb.g) shows up as 'random' entries -------
patch()
DRAWS.clear()
res, end = solve(BSProb, RPERLE, (10, 20, 30, 40, 50, 60, 70, 80, 90), budget=60, seed=(12345,)*6, simpar=1, crn=False)
unpatch()
print(f"BSProb (uses expovariate) run: {len(DRAWS)} draws recorded, all 'random': {all(d[0]=='random' for d in DRAWS)}")
print("first 5:", DRAWS[:5])

# --- 2) Confirm getrandbits draws show up distinctly (TPATester ranx0) ----
patch()
DRAWS.clear()
res_new, end_new = testsolve(TPATester, RPERLE, (0,), budget=60, seed=(12345,)*6, isp=1, proc=1, crn=False, ranx0=True)
new_draws = list(DRAWS)
unpatch()
kinds_new = set(d[0] for d in new_draws)
print(f"\nTPATester ranx0=True (new/getrandbits) run: {len(new_draws)} draws, kinds={kinds_new}")
print("first 12:", new_draws[:12])

# --- 3) Same scenario, forced onto the OLD _randbelow_without_getrandbits
#        fallback -- prove the recorded sequence actually differs. -------
patch()
RecordingMRG32k3a._randbelow = random.Random._randbelow_without_getrandbits
DRAWS.clear()
res_old, end_old = testsolve(TPATester, RPERLE, (0,), budget=60, seed=(12345,)*6, isp=1, proc=1, crn=False, ranx0=True)
old_draws = list(DRAWS)
del RecordingMRG32k3a._randbelow
unpatch()
print(f"\nTPATester ranx0=True (OLD fallback) run: {len(old_draws)} draws")
print("first 12:", old_draws[:12])

print("\nSequences differ:", new_draws != old_draws)
print("end seeds equal (expected, unaffected):", end_new == end_old)
