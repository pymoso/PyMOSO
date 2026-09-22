#!/usr/bin/env python
"""
Task 1: Independent verification of MRG32k3a jump-ahead correctness.

Strategy:
  1. Implement the MRG32k3a recurrence and its jump-ahead-by-N in pure
     Python int arithmetic (arbitrary precision => exact by construction),
     derived directly from the recurrence definition:
         x1[n] = (mrga12*x1[n-1] - mrga13n*x1[n-2]) mod m1
         x2[n] = (mrga21*x2[n-1] - mrga23n*x2[n-3]) mod m2
     as a 3x3 companion-matrix recurrence per component, jump-by-N done by
     fast matrix exponentiation (mod m1, mod m2) using exact integers.
  2. Validate the exact jump-by-N implementation against brute-force
     single-stepping for N = 10^3, 10^4, 10^5.
  3. Compare the shipped jump_substream (claimed 2^76) and
     get_next_prnstream (claimed 2^127) against the exact jump-by-N.
"""
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.prng.mrg32k3a import (
    mrg32k3a, MRG32k3a, get_next_prnstream, jump_substream,
    mrga12, mrga13n, mrga21, mrga23n, mrgm1, mrgm2,
)

M1 = int(mrgm1)
M2 = int(mrgm2)
A12 = int(mrga12)
A13N = int(mrga13n)
A21 = int(mrga21)
A23N = int(mrga23n)

# ---- Exact integer single-step, derived directly from the recurrence ----
# state layout matches the seed tuple: (x1[n-2], x1[n-1], x1[n], x2[n-3], x2[n-2], x2[n-1])
# matches mrg32k3a()'s newseed = (seed[1], seed[2], new_x1, seed[4], seed[5], new_x2)

def exact_step(seed):
    x10, x11, x12, x20, x21, x22 = seed
    new_x1 = (A12 * x11 - A13N * x10) % M1
    new_x2 = (A21 * x22 - A23N * x20) % M2
    return (x11, x12, new_x1, x21, x22, new_x2)


def exact_step_n_bruteforce(seed, n):
    s = tuple(seed)
    for _ in range(n):
        s = exact_step(s)
    return s


# ---- Exact matrix-power jump-by-N, component 1 (mod M1) and component 2 (mod M2) ----
# From exact_step: new_x1 = A12*seed[1] - A13N*seed[0], where seed=(x1[n-3],x1[n-2],x1[n-1],...)
# i.e. x1[n] = A12*x1[n-2] - A13N*x1[n-3]  (lag-2 and lag-3 terms; NO lag-1 term)
# and  new_x2 = A21*seed[5] - A23N*seed[3]
# i.e. x2[n] = A21*x2[n-1] - A23N*x2[n-3]  (lag-1 and lag-3 terms; NO lag-2 term)
# This is the standard L'Ecuyer MRG32k3a combined-recurrence form.
#
# Companion matrix for x1, acting on column vec (x1[n-1], x1[n-2], x1[n-3]):
#   x1[n]   = 0*x1[n-1] + A12*x1[n-2] - A13N*x1[n-3]
#   x1[n-1] = x1[n-1]        (shift)
#   x1[n-2] = x1[n-2]        (shift)
#   [0     A12   -A13N]
#   [1      0      0  ]
#   [0      1      0  ]
#
# Companion matrix for x2, acting on column vec (x2[n-1], x2[n-2], x2[n-3]):
#   x2[n]   = A21*x2[n-1] + 0*x2[n-2] - A23N*x2[n-3]
#   [A21    0    -A23N]
#   [1      0      0  ]
#   [0      1      0  ]

M1mat = [[0, A12, -A13N],
         [1, 0, 0],
         [0, 1, 0]]

M2mat = [[A21, 0, -A23N],
         [1, 0, 0],
         [0, 1, 0]]


def mat_mult(A, B, mod):
    n = len(A)
    p = len(B[0])
    k = len(B)
    C = [[0] * p for _ in range(n)]
    for i in range(n):
        for j in range(p):
            s = 0
            for l in range(k):
                s += A[i][l] * B[l][j]
            C[i][j] = s % mod
    return C


def mat_pow(A, n, mod):
    size = len(A)
    # identity
    R = [[1 if i == j else 0 for j in range(size)] for i in range(size)]
    base = A
    while n > 0:
        if n & 1:
            R = mat_mult(R, base, mod)
        base = mat_mult(base, base, mod)
        n >>= 1
    return R


def exact_jump_n(seed, n):
    """Exact jump-ahead by n steps using matrix exponentiation mod m1/m2."""
    x10, x11, x12, x20, x21, x22 = seed
    # vector order (x1[curr], x1[curr-1], x1[curr-2]) with "curr" = x12 (the newest)
    v1 = [[x12], [x11], [x10]]
    v2 = [[x22], [x21], [x20]]
    P1 = mat_pow(M1mat, n, M1)
    P2 = mat_pow(M2mat, n, M2)
    nv1 = mat_mult(P1, v1, M1)
    nv2 = mat_mult(P2, v2, M2)
    # nv1 = (x1[curr+n], x1[curr+n-1], x1[curr+n-2])
    new_x12, new_x11, new_x10 = nv1[0][0], nv1[1][0], nv1[2][0]
    new_x22, new_x21, new_x20 = nv2[0][0], nv2[1][0], nv2[2][0]
    return (new_x10, new_x11, new_x12, new_x20, new_x21, new_x22)


def main():
    seed0 = (12345, 12345, 12345, 12345, 12345, 12345)

    print("=== Step 1: sanity-check exact_step against shipped mrg32k3a() ===")
    s = seed0
    for i in range(20):
        shipped_new, _u = mrg32k3a(tuple(float(x) for x in s))
        shipped_new_int = tuple(int(round(x)) for x in shipped_new)
        exact_new = exact_step(s)
        if shipped_new_int != exact_new:
            print(f"  MISMATCH at step {i}: shipped={shipped_new_int} exact={exact_new}")
            sys.exit(1)
        s = exact_new
    print("  OK: exact_step matches shipped mrg32k3a() for 20 steps (int-compared).")

    print()
    print("=== Step 2: validate exact_jump_n against brute-force stepping ===")
    for n in [10**3, 10**4, 10**5]:
        bf = exact_step_n_bruteforce(seed0, n)
        mp = exact_jump_n(seed0, n)
        status = "OK" if bf == mp else "MISMATCH"
        print(f"  n={n:>7}: brute_force={bf}")
        print(f"  n={n:>7}: matrix_power={mp}  -> {status}")
        if bf != mp:
            sys.exit(1)
    print("  OK: matrix-power jump-by-N is exact for N=10^3,10^4,10^5.")

    print()
    print("=== Step 3: compare shipped jump_substream (claimed 2^76) ===")
    exact_76 = exact_jump_n(seed0, 2**76)
    prn = MRG32k3a(seed0)
    jump_substream(prn)
    shipped_76 = prn.get_seed()
    print(f"  exact 2^76 jump   : {exact_76}")
    print(f"  shipped jump_substream: {shipped_76}")
    if exact_76 == shipped_76:
        print("  AGREE")
    else:
        print("  DIVERGE")
        diffs = [(a, b, a - b) for a, b in zip(exact_76, shipped_76)]
        print(f"  component diffs (exact - shipped): {diffs}")
        for a, b in zip(exact_76, shipped_76):
            if b != 0:
                print(f"    ratio check: exact % 256 = {a % 256}, shipped % 256 = {b % 256}, "
                      f"exact // 256 vs shipped // 256 diff = {a//256 - b//256}")

    print()
    print("=== Step 3b: compare shipped get_next_prnstream (claimed 2^127) ===")
    exact_127 = exact_jump_n(seed0, 2**127)
    prn2 = get_next_prnstream(seed0, False)
    shipped_127 = prn2.get_seed()
    print(f"  exact 2^127 jump   : {exact_127}")
    print(f"  shipped get_next_prnstream: {shipped_127}")
    if exact_127 == shipped_127:
        print("  AGREE")
    else:
        print("  DIVERGE")
        diffs = [(a, b, a - b) for a, b in zip(exact_127, shipped_127)]
        print(f"  component diffs (exact - shipped): {diffs}")
        for a, b in zip(exact_127, shipped_127):
            if b != 0:
                print(f"    ratio check: exact % 256 = {a % 256}, shipped % 256 = {b % 256}, "
                      f"exact // 256 vs shipped // 256 diff = {a//256 - b//256}")


if __name__ == '__main__':
    main()
