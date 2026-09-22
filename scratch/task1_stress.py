#!/usr/bin/env python
"""
Task 1 continued: stress-test the jump-ahead across many seeds and chained
jumps, to see whether the shipped float-based jump-ahead ever diverges from
the exact integer jump-ahead, and to check the "components divisible by 256"
defect claim directly.
"""
import random
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.prng.mrg32k3a import MRG32k3a, get_next_prnstream, jump_substream
from task1_jumpahead import exact_jump_n, M1, M2

random.seed(2026)


def random_seed():
    return (
        random.randint(1, M1 - 1), random.randint(1, M1 - 1), random.randint(1, M1 - 1),
        random.randint(1, M2 - 1), random.randint(1, M2 - 1), random.randint(1, M2 - 1),
    )


def check_single_jumps(n_trials=200):
    mismatches_76 = 0
    mismatches_127 = 0
    div256_76 = 0
    div256_127 = 0
    for t in range(n_trials):
        seed = random_seed()
        exact76 = exact_jump_n(seed, 2**76)
        prn = MRG32k3a(seed)
        jump_substream(prn)
        shipped76 = prn.get_seed()
        if exact76 != shipped76:
            mismatches_76 += 1
            print(f"  [76]  seed={seed}")
            print(f"        exact  ={exact76}")
            print(f"        shipped={shipped76}")
        if all(v % 256 == 0 for v in shipped76):
            div256_76 += 1

        exact127 = exact_jump_n(seed, 2**127)
        prn2 = get_next_prnstream(seed, False)
        shipped127 = prn2.get_seed()
        if exact127 != shipped127:
            mismatches_127 += 1
            print(f"  [127] seed={seed}")
            print(f"        exact  ={exact127}")
            print(f"        shipped={shipped127}")
        if all(v % 256 == 0 for v in shipped127):
            div256_127 += 1
    print(f"single-jump trials: {n_trials}")
    print(f"  2^76  jump mismatches vs exact: {mismatches_76}/{n_trials}; all-components-div-by-256 count: {div256_76}")
    print(f"  2^127 jump mismatches vs exact: {mismatches_127}/{n_trials}; all-components-div-by-256 count: {div256_127}")


def check_chained_jumps(n_chain=50, n_trials=20):
    """Chain many 2^127 jumps (as crn_advance does, once per RA iteration per
    simpar worker) and many 2^76 jumps (as crn_nextobs does, once per
    replication), and compare the *cumulative* shipped state against the
    exact single jump by n_chain*2**127 / n_chain*2**76."""
    mismatches_76 = 0
    mismatches_127 = 0
    for t in range(n_trials):
        seed = random_seed()

        # chained 2^76 jumps
        prn = MRG32k3a(seed)
        for _ in range(n_chain):
            jump_substream(prn)
        shipped_chain_76 = prn.get_seed()
        exact_chain_76 = exact_jump_n(seed, n_chain * 2**76)
        if shipped_chain_76 != exact_chain_76:
            mismatches_76 += 1
            print(f"  [chain 76 x{n_chain}] seed={seed}")
            print(f"        exact  ={exact_chain_76}")
            print(f"        shipped={shipped_chain_76}")

        # chained 2^127 jumps
        s = seed
        for _ in range(n_chain):
            prn2 = get_next_prnstream(s, False)
            s = prn2.get_seed()
        shipped_chain_127 = s
        exact_chain_127 = exact_jump_n(seed, n_chain * 2**127)
        if shipped_chain_127 != exact_chain_127:
            mismatches_127 += 1
            print(f"  [chain 127 x{n_chain}] seed={seed}")
            print(f"        exact  ={exact_chain_127}")
            print(f"        shipped={shipped_chain_127}")

    print(f"chained-jump trials: {n_trials} chains of length {n_chain}")
    print(f"  2^76  chained mismatches vs exact: {mismatches_76}/{n_trials}")
    print(f"  2^127 chained mismatches vs exact: {mismatches_127}/{n_trials}")


def check_edge_seeds():
    """Edge cases: seed components at or near 0, 1, m-1."""
    edge_seeds = [
        (1, 1, 1, 1, 1, 1),
        (M1 - 1, M1 - 1, M1 - 1, M2 - 1, M2 - 1, M2 - 1),
        (1, M1 - 1, 1, M2 - 1, 1, M2 - 1),
        (12345,) * 6,
        (M1 - 1, 1, M1 - 1, 1, M2 - 1, 1),
    ]
    mismatches = 0
    for seed in edge_seeds:
        exact76 = exact_jump_n(seed, 2**76)
        prn = MRG32k3a(seed)
        jump_substream(prn)
        shipped76 = prn.get_seed()
        ok = exact76 == shipped76
        print(f"  seed={seed} -> 2^76 match: {ok}")
        if not ok:
            mismatches += 1
            print(f"    exact  ={exact76}")
            print(f"    shipped={shipped76}")
    print(f"edge-seed mismatches: {mismatches}/{len(edge_seeds)}")


if __name__ == '__main__':
    print("=== single jumps (200 random seeds) ===")
    check_single_jumps(200)
    print()
    print("=== chained jumps (20 trials x 50 chained jumps each) ===")
    check_chained_jumps(50, 20)
    print()
    print("=== edge seeds ===")
    check_edge_seeds()
