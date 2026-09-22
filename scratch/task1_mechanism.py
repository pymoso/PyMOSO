#!/usr/bin/env python
"""
Task 1 continued: isolate exactly where float64 precision is lost inside
mat333mult / mat311mod (prng/mrg32k3a.py:273-316), for a realistic
(non-toy) seed, and explain the "divisible by 256" pattern.
"""
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')
from pymoso.prng.mrg32k3a import a1p127, mrgm1, mat333mult, mat311mod

seed_float = (511616026.0, 1372175473.0, 2158288731.0)  # a realistic post-jump seed component

# shipped float path, matching mat333mult exactly
res_float = mat333mult(a1p127, seed_float)
print("shipped mat333mult (float) row sums:", res_float)

# exact integer path: same matrix (cast to int), same seed, arbitrary precision
a1p127_int = [[int(v) for v in row] for row in a1p127]
seed_int = tuple(int(v) for v in seed_float)


def mat333mult_exact(a, b):
    r3 = range(3)
    return [sum(a[i][j] * b[j] for j in r3) for i in r3]


res_exact = mat333mult_exact(a1p127_int, seed_int)
print("exact   mat333mult (int)   row sums:", res_exact)
print("row-sum diffs (exact - shipped):", [e - f for e, f in zip(res_exact, res_float)])
print()

for i in range(3):
    magnitude = res_exact[i]
    # float64 has 52 explicit mantissa bits (53 significant); ULP at this
    # magnitude is 2**(exponent-52)
    import math
    exp = math.floor(math.log2(abs(magnitude)))
    ulp = 2 ** (exp - 52)
    print(f"row {i}: exact sum ~= {magnitude:.3e} (~2^{exp}), float64 ULP at this "
          f"magnitude = {ulp} (= 2^{exp-52})")

print()
print("Now push the same numbers through mat311mod (the modulo-reduction step) "
      "exactly as get_next_prnstream does:")
res_mod_float = mat311mod(res_float, mrgm1)
res_mod_exact = [int(r) % int(mrgm1) for r in res_exact]
print("shipped mat311mod (float):", res_mod_float)
print("exact   mod (int):        ", res_mod_exact)
print("diffs:", [e - f for e, f in zip(res_mod_exact, res_mod_float)])
print()
print("diffs mod 256:", [(e - f) % 256 for e, f in zip(res_mod_exact, res_mod_float)])
print("shipped values mod 256:  ", [f % 256 for f in res_mod_float])
