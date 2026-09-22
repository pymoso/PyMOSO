#!/usr/bin/env python
"""
Task 3b: What happens when an ISP's RA-iteration count exceeds max_RI=200?
Demonstrate concretely whether/where two ISPs' RNG streams overlap.

get_testsolve_prnstreams reserves, per ISP t: 1 jump to create orcprn_lst[t],
then `max_RI` (=200) further discarded 2^127-jumps, before creating
orcprn_lst[t+1]. That's the "200 iterations of headroom" per ISP.

Oracle.crn_advance() (chnbase.py:1066-1079), called once per RA iteration by
RASolver.rasolve (chnbase.py:212), does exactly `self.simpar` such 2^127
jumps per call (simpar=1 for testsolve, since testsolve never sets it).

So: does the state of ISP 0's Oracle.rng, after exactly N calls to
crn_advance(), coincide with ISP 1's starting orcprn seed for some N <= 200
(or bigger)? We check empirically instead of just deriving it on paper.
"""
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.chnutils import get_testsolve_prnstreams
from pymoso.chnbase import Oracle

seed = (12345, 12345, 12345, 12345, 12345, 12345)
orcprn_lst, solprn_lst, xprn, endseed = get_testsolve_prnstreams(3, seed, False)

print("ISP 0 starting seed:", orcprn_lst[0].get_seed())
print("ISP 1 starting seed:", orcprn_lst[1].get_seed())
print("ISP 2 starting seed:", orcprn_lst[2].get_seed())
print()

# Simulate ISP 0's Oracle running many RA iterations (simpar=1, crn=False,
# exactly as RASolver.rasolve would drive it via self.orc.crn_advance()).
orc0 = Oracle(orcprn_lst[0])
orc0.set_crnflag(False)
orc0.simpar = 1

target1 = orcprn_lst[1].get_seed()
target2 = orcprn_lst[2].get_seed()
hit_at = {}
for n in range(1, 402):
    orc0.crn_advance()
    seed_now = orc0.rng.get_seed()
    if seed_now == target1 and 'isp1' not in hit_at:
        hit_at['isp1'] = n
    if seed_now == target2 and 'isp2' not in hit_at:
        hit_at['isp2'] = n
    if n in (198, 199, 200, 201, 202, 400, 401):
        print(f"after {n:>3} RA iterations (crn_advance calls), ISP0 rng seed = {seed_now}")

print()
if 'isp1' in hit_at:
    print(f"CONFIRMED OVERLAP: after exactly {hit_at['isp1']} RA iterations, "
          f"ISP 0's rng state becomes IDENTICAL to ISP 1's starting seed.")
else:
    print("No exact coincidence with ISP 1's starting seed found in 401 iterations.")
if 'isp2' in hit_at:
    print(f"CONFIRMED OVERLAP: after exactly {hit_at['isp2']} RA iterations, "
          f"ISP 0's rng state becomes IDENTICAL to ISP 2's starting seed.")
