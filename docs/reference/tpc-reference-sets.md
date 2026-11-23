# Test Problem C's reference sets

`TPCTester.soln` is the 516 N_1-local weakly efficient sets (LWESs) of the
dissertation's Online Appendix E, as decision points. They were converted
once from `lescombos.pkl`, which sits beside this file and, like
`exples.pkl`, came from a PyMOSO ancestor. This document records what the
two files are, how they relate to what PyMOSO shipped, and what they do and
do not establish. Measured 2026-11-18; the scripts are not in the
repository.

## The two files

The provenance and hashes are in [README.md](README.md).

**`lescombos.pkl`**
- A set of 516 frozensets of integer 3-tuples.
- All 516 are distinct as point sets.
- Between them they hold 73 distinct points, in 4,273 point instances.
- The appendix's numbers are "516 unique N_1-LWES's" containing "just 73 points".

**`exples.pkl`**
- A list of 516 sets of float pairs: the images of those point sets under the ancestor's deterministic oracle.
- They are 66 distinct sets, holding 43 distinct images.
- This is the shape `TPCTester.soln` shipped in until 2.0.

**The mirror arithmetic closes exactly.** ProbTPC's objectives are symmetric under (x1, x2, x3) → (x3, x2, x1). The 73 points are 13 self-mirrored points (a, b, a) and 30 mirror pairs. That predicts 13 + 30 = 43 distinct images, which is what `exples.pkl` has. No point is missing its mirror.

## The integer-to-original mapping is 0.5·k

The integer coordinates used are -3, -2, 0, 5, 6 and 9.

**Under 0.5·k** they are -1.5, -1.0, 0.0, 2.5, 3.0 and 4.5. This is `tpctester.true_g`'s `x/df` with `df = 2`.

**Under -5 + 0.5·k** they would be -6.5, -6.0, -5.0, -2.5, -2.0 and -0.5. Three of those lie outside the dissertation's feasible set, which is {-5, -4.5, ..., 5} in each coordinate.

**Decisively, the images match:**
- `lescombos.pkl` imaged by today's `true_g` gives the same 516 image sets as `exples.pkl`, as a multiset, to 1e-9.
- 58 of the 73 points' images are bit-identical to an `exples.pkl` image, and the rest are within 1.8e-15.
- The 0.5·k mapping puts 2.5 and -1.5 among the coordinates. Those are the coordinates of the 6 stored images that no expression tried reproduces bit for bit. That they come from another machine's C library is the likeliest explanation; it has not been tested.

## The collapse from points to images

Under the images, the 516 point sets fall into the 66 distinct image sets. Each of the 516 has the image set of exactly one of the 66.

Point sets per image set:

| point sets | image sets with that many |
|---|---|
| 1 | 11 |
| 3 | 19 |
| 5 | 9 |
| 7 | 2 |
| 9 | 11 |
| 15 | 7 |
| 17 | 1 |
| 21 | 2 |
| 27 | 3 |
| 45 | 1 |

## The definitions, and the predicate tested here

The dissertation's definitions of an LWEP and an LWES, verbatim from Chapter 3:

> A point $\mathbf{x}^\mathrm{w}\in\mathcal{X}$ is an *$\mathcal{N}_a$-local weakly efficient point* (LWEP) if
> 1. $\nexists\mathbf{x}\in \mathcal{N}_a(\mathbf{x}^\mathrm{w})\cap\mathcal{X}$ such that $\mathbf{g}(\mathbf{x}) < \mathbf{g}(\mathbf{x}^\mathrm{w})$; or equivalently, if
> 2. $\forall\mathbf{x}\in \mathcal{N}_a(\mathbf{x}^\mathrm{w})\cap\mathcal{X},$ $\mathbf{g}(\mathbf{x}) \not< \mathbf{g}(\mathbf{x}^\mathrm{w})$, that is, $\exists k\in\{1,\dots,d\}$ such that $g_{k}(\mathbf{x}^\mathrm{w})\leq g_{k}(\mathbf{x})$.

> A set $\mathcal{L}^\mathrm{w}\subseteq\mathcal{X},|\mathcal{L}^\mathrm{w}|\geq 1,$ is an *$\mathcal{N}_a$-local weakly efficient set* (LWES) if
> (a) $\forall\mathbf{x}^\mathrm{w}\in\mathcal{L}^\mathrm{w},$ $\mathbf{x}^\mathrm{w}$ is an $\mathcal{N}_a$-LWEP, and
> (b) no points in $\mathbf{g}(\mathcal{L}^\mathrm{w})$ strictly dominate other points in $\mathbf{g}(\mathcal{L}^\mathrm{w})$, and
> (c) $\forall\mathbf{x}\in\mathcal{N}'_a(\mathcal{L}^\mathrm{w})\cap\mathcal{X}$, $\exists\mathbf{x}^\mathrm{w}\in\mathcal{L}^\mathrm{w}$ such that $\mathbf{g}(\mathbf{x}^\mathrm{w})\leqq \mathbf{g}(\mathbf{x})$.

**The notation, from the same chapters:**
- $\mathcal{N}_a(\mathbf{x})$ is the lattice points within distance $a$ of $\mathbf{x}$. The neighbourhood of a set is the union of its points' neighbourhoods.
- $\mathcal{N}'_a(\mathcal{A}) = \mathcal{N}_a(\mathcal{A})\setminus\mathcal{A}$ is the deleted neighbourhood (Chapter 3).
- $<$ is strict dominance: smaller in every objective.
- $\leqq$ is weak dominance: no larger in any objective (Chapter 1).

**The predicate tested** for every count in this document (the 516 checked, the 119,392 and the 118,876) is the set-level definition, all three parts (a), (b) and (c), as quoted:
- **(a)** no feasible N_1-neighbour of any member strictly dominates it;
- **(b)** no member strictly dominates another;
- **(c)** every feasible point of the set's deleted N_1-neighbourhood is weakly dominated by some member.

Values within 1e-12 are treated as equal. Part (a) alone, the pointwise condition that each member is an LWEP, is not what was counted.

**512 LWEPs against 73 members is expected, not a discrepancy.**
- Being an LWEP is pointwise: a point is compared only with its own neighbours.
- Membership of an LWES adds the set-level conditions (b) and (c) over everything the set's neighbourhood reaches. An LWEP can fail them in every set that contains it.
- The dissertation says so itself, in Chapter 3 near its definitions: "under our definitions, there may exist $\mathcal{N}_a$-LWEP's that do not belong to an $\mathcal{N}_a$-LWES". The appendix closes the same way: "Recall that there are 512 $\mathcal{N}_1$-LWEP's, so not all $\mathcal{N}_1$-LWEP's are members of an $\mathcal{N}_1$-LWES."
- **Measured:** 512 of the 9,261 feasible points are N_1-LWEPs under today's `true_g`, which is the appendix's count. 73 of them are members of the published sets.

## What the appendix says, and what the procedure finds

The appendix (the dissertation's Online Appendix E) opens with its aim and closes its count procedurally:

> To calculate the collection of all possible $\mathcal{N}_1$-LWES's in Problem $T_C$, we first locate all $\mathcal{N}_1$-LWEP's; we find 512. ... The total number of unique $\mathcal{N}_1$-LWES's found in this manner, up to level-8, was 516.

The body defines the metric over all N_1-LWESs, $\mathfrak{W}_1$, and computes it over the 516:

> we use the local weakly coverage error as our solution quality metric, which we define as $\min_{\mathcal{L}\in\mathfrak{W}_1} H(\mathbf{g}(\hat{\mathcal{A}}(t)), \mathbf{g}(\mathcal{L}))$ ... calculated across a collection of 516 unique $\mathcal{N}_1$-LWES's

The count is what the union procedure reached ("found in this manner"). What follows says how that relates to the stated aim.

**Every one of the 516 is an N_1-LWES.** It was checked against the dissertation's definition under today's `true_g`, with values within 1e-12 treated as equal. 486 of the 516 are also N_1-local efficient sets (LESs).

**They are not every LWES as a point set.**

| point sets with the images of one of the 66 | count | among the 516 | not among them |
|---|---|---|---|
| LWESs | 119,392 | 516 | 118,876 |
| LESs | 856 | 486 | 370 |

An example of an LWES that is not in the 516 is {(0, 0, 0), (0, 9, 9), (9, 0, 0)}. It passes the definition exactly, with no tolerance. The smallest published set containing it adds (0, 0, 9).

**Mirror pairs explain most of the excess.**
- A point and its mirror are never N_1-neighbours, and they share an image. So which member of a pair a set holds is close to free.
- The published collection is not closed under mirroring the whole set.
- 352 of the 516 hold both members of some pair, and the rest hold one.
- The procedure finds "the smallest complete" LWES from each LWEP and then takes unions. It reaches some of these choices and not others.

## The 66 representatives used before this

Before the 516 were available, `TPCTester.soln` was rebuilt from the shipped images. Each image set was stored as every feasible point whose image is in it, which is the mirror-closed preimage. That version was never committed. It differs from the published sets as follows:

- **63 of the 66 are themselves among the 516.**
- **3 are neither one of the 516 nor the union of their group.** Each is a valid LWES that the published collection does not contain.
  - Each contains every published set with its images, plus (9, -3, -3), (9, -2, -3) and (9, -2, -2).
  - Those points are the mirrors of points in those groups' published sets, but no published set of those groups holds them.
  - The three have 11, 9 and 11 points. Their groups have 3, 1 and 3 published sets, of at most 8, 6 and 8 points.

## Why all of this leaves the metric alone

**The metric depends only on images:** the Hausdorff distance to the nearest reference image set. So only the 66 distinct image sets matter, not which point sets stand behind them.

**Measured:** over the 9,709 T_C solution sets in the R-PERLE runs at budget 4 × 10^6, the 516 and the 66 representatives gave bit-identical metric values.

**What changed against 1.1.0:**
- The reference images used to be the ancestor's floats, from `exples.pkl`. Now they are today's `true_g` on the points, computed when the tester is made.
- So full coverage measures exactly 0. Before, a run covering a set that holds one of the 7 images that differ from `true_g` scored about 1e-15.
- Over those runs, 38 values moved, by at most 8.9e-16, and 16 became exactly 0.

## What is not established

**Image-level completeness, which is what the metric needs: whether every N_1-LWES of ProbTPC has one of these 66 image sets.**
- The 118,876 extra LWESs cannot speak to it. They were found by searching only point sets with the 66 known image sets, so by construction they have those images.
- An LWES with a different image set would need a search over point sets built from all 512 LWEPs. None was attempted: done naively it means subsets of 512 points, and a search that uses the problem's structure has not been designed.
- Neither the appendix's procedure nor anything here shows that no such set exists.

**T_C's reference is therefore the published object, verified point set by point set against the definition, but its completeness rests on the appendix's procedure.**

**T_A's and T_B's references are in a different position:**
- T_A's is proved exactly. It is the global efficient set, checked in integer arithmetic.
- T_B's is proved by hand.
- Both are in `tests/test_tester_reference_sets.py`.

