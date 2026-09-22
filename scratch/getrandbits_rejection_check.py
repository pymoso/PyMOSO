import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')
from pymoso.prng.mrg32k3a import MRG32k3a, mrgm1i

# --- Exact theoretical rejection probability, per k -------------------------
# No simulation needed: t and the rejection probability are deterministic
# functions of mrgm1i and k (exact bigint arithmetic).
def theoretical(k):
    target = 1 << k
    span = 1
    t = 0
    while span < target:
        span *= mrgm1i
        t += 1
    usable = (span // target) * target
    reject_prob = (span - usable) / span
    return t, reject_prob

print("k : digits(t) : exact reject probability")
for k in [1, 6, 7, 8, 16, 24, 31, 32, 33, 48, 63, 64, 128]:
    t, p = theoretical(k)
    print(f"{k:4d} : {t:2d} : {p:.6e}")

# --- Instrumented getrandbits: count real calls/rejects -------------------
stats = {}

def instrumented(self, k):
    st = stats.setdefault(k, {'calls': 0, 'rejects': 0})
    target = 1 << k
    while True:
        st['calls'] += 1
        span = 1
        digits = 0
        while span < target:
            digits = digits*mrgm1i + (self._next_raw() - 1)
            span *= mrgm1i
        usable = (span // target) * target
        if digits < usable:
            return digits % target
        st['rejects'] += 1

MRG32k3a._orig_getrandbits = MRG32k3a.getrandbits
MRG32k3a.getrandbits = instrumented

# 1) The actual golden scenario: testsolve_tpa (isp=4, budget=1000) -- this
#    is the real call volume the golden case produces (k=6, via TPATester's
#    rng.choice(range(0,51)) for ranx0 plus whatever the solver itself draws).
from pymoso.chnutils import testsolve
from pymoso.testers.tpatester import TPATester
from pymoso.solvers.rperle import RPERLE

res, end_seed = testsolve(
    TPATester, RPERLE, (40, 40),
    budget=1000, seed=(12345,)*6, isp=4, proc=1, crn=False, ranx0=False,
)
print()
print("after real testsolve_tpa scenario (ranx0=False):", stats)

# 2) Same, but with ranx0=True so get_ranx0 -> rng.choice(range(0,51)) fires
#    per independent sample path too.
stats.clear()
res, end_seed = testsolve(
    TPATester, RPERLE, (40, 40),
    budget=1000, seed=(12345,)*6, isp=4, proc=1, crn=False, ranx0=True,
)
print("after real testsolve_tpa scenario (ranx0=True): ", stats)

# 3) A larger synthetic stress run at k=6 and k=8 (the two k values this
#    codebase's testers actually reach: range(0,51) and range(-100,101)) to
#    get an observed count at higher volume than a single real solve pass
#    produces alone.
stats.clear()
rng = MRG32k3a((12345,)*6)
N = 5_000_000
for _ in range(N):
    rng.getrandbits(6)
for _ in range(N):
    rng.getrandbits(8)
print(f"after {N:,} synthetic getrandbits(6) + {N:,} getrandbits(8) calls:", stats)
