# Where CRN fails: synchronization

Phase 7, step 6b (`docs/phase7-plan.md`). CRN reduces
Var(g(x) - g(y)) = Var g(x) + Var g(y) - 2 Cov(g(x), g(y)), and helps
only as far as the covariance is positive. The first candidate failure
is synchronization: neighbouring points that consume different numbers
of variates, so the same random number is used for different purposes.
This document measures that case directly, as the correlation between
neighbouring points' replications, and then what it costs the solvers.

Tables are generated: `docs/crn-failure-tables.md`, by
`python docs/bench_crn.py report` from `scratch/phase7/crn_covariance.json`
and `scratch/phase7/crn_runs.jsonl`.
The script's docstring has the commands. **Everything here is measured**
unless it says it is reasoning. Correlations and counts, not timings.

## Three facts about PyMOSO's CRN, from the code

1. **Every replication starts in step.** Under `--crn`, replication j
   of every point starts at the same position of the iteration's
   stream (`oracle.py`, `_block_for`: stream = iteration, offset =
   j * 2^76). A draw-count difference can desynchronize only the rest
   of that one replication.
2. **What matters is a draw count that differs between neighbours, not
   a variable one.** `BSProb` draws a random number of arrivals, but
   that number does not depend on x. Measured: its draw counts differ in
   99% of replication pairs without CRN and in none with it.
3. **CRN does not link consecutive RA iterations.** The CRN stream is
   the iteration number, so iteration v's sample path is independent of
   iteration v-1's with or without CRN. This answers the plan's question
   of whether a CRN failure also erodes the warm start's value. It
   cannot, because there is nothing across iterations for CRN to lose.
   What CRN does affect is the comparisons *within* an iteration: SPLI,
   NE and certification.

## The headline: desynchronization degrades CRN; it does not switch it off

On the inventory twins (below), over all 758 neighbour pairs of the box,
with 1,000 replications per point:

| | correlation, holding / shortage (median) | variance ratio, holding / shortage (median) |
|---|---|---|
| `SyncFixed`, CRN (synchronized) | 1.00 / 0.99 | 0.004 / 0.011 |
| `SyncVar`, CRN (draw count depends on x) | 0.91 / 0.94 | 0.092 / 0.056 |
| `CycFixed`, CRN (synchronized) | 1.00 / 0.99 | 0.003 / 0.015 |
| `CycRare`, CRN (a fixed cycle plus a rare x-dependent draw) | 0.59 / 0.75 | 0.41 / 0.26 |
| any twin, without CRN | 0.00 / 0.00 | 1.00 / 1.00 |

The variance ratio is Var(g(x) - g(y)) / (Var g(x) + Var g(y)): 1 for
independent sampling, below 1 where CRN helps.
- **`SyncVar`:** desynchronization makes the difference's variance
  about 23 times larger on holding and 5 times on shortage than
  synchronized CRN gives. It is still 11 to 18 times smaller than
  without CRN.
- **`CycRare`:** most of CRN's benefit is gone. The difference's
  variance is over 100 times what synchronized CRN gives on holding
  (17 times on shortage), and only 2.4 and 3.9 times below
  independent sampling.
- Every pair has a correlation interval above zero with CRN, in every
  twin.

**Prediction refuted:** "correlation collapses to near zero where draw
counts differ." Draw counts differ in about half of `SyncVar`'s
replication pairs, and the correlation is 0.91. Even on `CycRare`,
built to be the bad case, it falls to 0.59, not to zero; at T = 300,
0.52.

**My own prediction, refuted too.** I predicted the correlation would
fall roughly in proportion to the share of a replication completed
before the counts part. The T sweep says otherwise. With T = 300
periods, the two points' cumulative draw counts are equal for only 7%
of a replication on average, yet the correlation is 0.87 (holding) and
0.94 (shortage), about what it is at T = 30 (53% equal). From T = 30 on,
the correlation stops falling.

## Why: the draws re-align by themselves

**Misaligned on purpose.** Take one point against itself: replication j
at x, against x simulated from the same stream advanced by k raw draws.
That is a misalignment from the first draw with no x-dependence at all.
Holding correlations, x = (9, 9), T = 300:

| k | 0 | 1 | 2 | 3 | 4 | 8 | 100 | 1,000 | 2,000 |
|---|---|---|---|---|---|---|---|---|---|
| `SyncFixed` | 1.00 | -0.01 | 1.00 | -0.01 | 1.00 | 0.99 | 0.92 | 0.19 | -0.01 |
| `SyncVar` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.88 | -0.03 | 0.00 |

- **`SyncVar` re-aligns.** Its pattern of draws depends on their
  values: a demand, then a cost only on a stockout. Two readers of the
  same stream that start out of step soon both read the same uniform as
  a period's first demand, and stay in step from there, offset in
  time. The outputs are averages over periods, so a time offset hardly
  matters. Measured in the sweep: at T = 300, 73% of periods start on
  the same raw draw at both points (the "in role" column), against 7%
  with equal counts. This is reasoning backed by the shift table, not a
  proof.
- **`SyncFixed` does not re-align.** Its pattern is a fixed cycle of
  four draws a period. An odd misalignment makes demands read the
  costs' uniforms for the rest of the replication, and holding's
  correlation goes to -0.01. An even one swaps the two items, which are
  symmetric at (9, 9), so nothing is lost.
- **Large misalignments decorrelate both.** At 1,000 or more raw draws
  the two readers share few or none of the same uniforms: at (9, 9)
  and T = 300, a `SyncFixed` replication uses 1,200 raw draws and a
  `SyncVar` one about 900. `SyncFixed`'s 0.19 at k = 1,000 is about
  its 200 draws of overlap.

So "everything after the divergence is effectively independent" holds
for a fixed cyclic pattern of draws that is shifted for good, and not
for a value-dependent pattern, which re-couples. The twin built to
*avoid* desynchronization is the one that fails completely if it is
ever shifted.

## The bad case: a fixed cycle with a rare x-dependent draw

`CycRare` and `CycFixed` were built after the measurements above, to
find the structure where the correlation does collapse. Each period
draws each item's demand D and expediting cost P, a fixed cycle, plus a
reorder-delay cost Q when D == x exactly (the item ends the period with
nothing). `CycRare` draws Q only then; `CycFixed` always draws it and
discards it otherwise. Neighbours x and x + e1 draw Q on different
demands (D1 = x1 against D1 = x1 + 1), so they part about once in ten
periods.

**Measured:** correlation 0.59 / 0.75 under CRN over the whole box;
0.52 / 0.72 at T = 300, where only 37% of periods start on the same
draw at both points (`SyncVar`: 73%).

**Why, as measured and then reasoned.** `CycRare` re-aligns too, given
time: a point against itself shifted by 1 to 8 raw draws keeps a
correlation of 0.98 or more at T = 300. `CycFixed`, shifted by 1, 2,
4, 8 or 100 raw draws, loses it (holding -0.02 to 0.01); a shift of 3
only swaps the two items. What
differs from `SyncVar` is the balance between two rates, which is
reasoning from the in-role column, not separately measured:
- **How often neighbours part.** `CycRare`'s neighbours part on
  different demand values about once in ten periods, against once in
  twenty for `SyncVar`.
- **How fast they re-couple.** `SyncVar`'s pattern depends on the
  draw's value about half the time (a stockout or not), so two readers
  out of step come back together within a few periods. `CycRare`'s
  depends on it only when D equals the stock level exactly, one period
  in twenty, so a misalignment lasts many periods.

So the stated mechanism holds where re-coupling is slow compared with
parting: a mostly fixed cycle of draws with a rare value-dependent
extra one. That is the shape of a queue that draws an arrival and a
service time per customer and occasionally something else, such as a
routing draw when a buffer is full.

## What it costs the solvers

R-PERLE, R-PE and R-MinRLE on the bi-objective twins; R-SPLINE on their
single-objective counterparts (holding plus shortage). CRN on and off,
20 seeds, budget 20,000, quality at matched counted simulations (the
Hausdorff distance between the true images of the returned set and of
the efficient set; R-SPLINE: the gap to the true minimum cost). The
tables have every checkpoint.

**The control passes.** Each pair's two default arms have identical
marginals, so the desynchronizing twin should be better than its
synchronized twin about as often as worse, same seed, default arm: at
20,000 simulations 7-15 better against 5-11 worse across the six
multi-objective comparisons. R-MinRLE on the sync pair, 15 against 5,
is the least balanced (about p = 0.04 two-sided, one of eight such
comparisons).

**Under CRN, desynchronization costs what the covariance predicts.**
Medians of the multi-objective solvers at 5,000 and 20,000 simulations,
CRN arm:

| | `SyncFixed` | `SyncVar` | `CycFixed` | `CycRare` |
|---|---|---|---|---|
| at 5,000 | 0.21-0.82 | 0.41 | 0.41 | 1.68-2.36 |
| at 20,000 | 0.21 | 0.21 | 0.21 | 0.41 |

- **`CycRare` is worse than `CycFixed` under CRN on the same seed in
  18-20 of 20 seeds** at 20,000, for each of the three solvers.
  `SyncVar` against `SyncFixed`: 11-16 of 20 worse, against 2-6 better
  and 2-4 the same.
- **CRN still beats the default arm on every twin**, `CycRare`
  included: better on 17-20 of 20 seeds at 20,000 simulations.
- **R-SPLINE says nothing here.** Its single-objective twins are too
  easy: the median gap is 0 or 0.25 from 500 simulations on, in both
  arms, and 0 on every twin by 5,000.
- CRN also lowers the simulations per RA iteration for the
  multi-objective solvers, by 8-15% on three of the twins and by 2-5%
  on `CycRare`.

So the guidance from these twins is "CRN helps less", not "CRN does
not help": even where the correlation falls to about 0.6, CRN is the
better arm, and only on the bad case is the loss visible in solution
quality.

## `randint` over a range that depends on x

`RandRange`: g = randint(0, 4 + x) + Z, 2,000 replications per point,
pairs (x, x + 1). `randint` rejects by value, so its draw count depends
on the draw and on the range.

- **Where the range's size crosses a power of two** (sizes 7 to 8, 15
  to 16, 31 to 32, 63 to 64: x = 2, 10, 26, 58), draw counts differ in
  50-54% of replications and the correlation falls to 0.41-0.48
  (variance ratio 0.52-0.60). Crossing a power of two changes how many
  bits `randint` asks for, so the same raw draw gives an unrelated
  value, and Z after it is misaligned when the counts differ.
- **Elsewhere,** the two ranges reject together except when the draw
  lands exactly on the boundary, so counts differ in 1-17% of
  replications (less as the range grows) and the correlation is 0.70
  to 0.98.
- **Without CRN,** the correlation is within 0.06 of zero at every x.

A user whose `g()` calls `randint`, `choice` or `randrange` over a
range that depends on x has a desynchronized CRN at particular points,
with no variable-length loop anywhere in the code.

## The built-in problems are synchronized

`ProbSimpleSO`, `ProbTPA`, `ProbTPB`, `ProbTPC` and `BSProb`: 10 points
each from the tester's `get_ranx0`, every axis pair, 500 replications.
Under CRN draw counts never differ, the correlation is 0.99-1.00 and
the variance ratio is at most 0.01 (medians). Without CRN the
correlation is within 0.02 of zero (medians). None of the in-tree
problems exercises this failure.

## The problems, and how the measurement was checked

`scratch/phase7/crnsync.py` (kept in scratch/).

- **The inventory twins** (the cyclic twins are described above; their
  means add Q's mean on the one period in twenty that ends at zero, the
  same at every x, so the efficient set is the same). Two items, x in
  {0..19}^2. Each of T = 30
  periods, in one stream: item 1's demand D = floor(20u) (one raw draw);
  if D > x1 an expediting cost P ~ Exp(mean 10); then item 2. Objective
  1 is holding, objective 2 is shortage (4 per unit short, plus P), as
  per-period averages. `SyncVar` draws P only on a stockout, so x and
  x + e1 part in the first period with D1 = x1 + 1. `SyncFixed` always
  draws P and discards it when it is not needed. A replication's output
  at one point has the same distribution in both, so the true means,
  variances and known answer are identical; only the coupling differs.
  **Checked, not only argued:** without CRN, over 400 points and two
  objectives, the largest |z| of each twin's means against the closed
  form is 3.11 and 2.63; of the twins' means against each other 2.43;
  of their variances 2.98. For the cyclic twins: 2.96, 3.37, 2.72 and
  3.23.
- **The known answer.** Closed-form means in exact fractions, rounded
  once, so equal means are equal floats; the items are symmetric, so
  (a, b) and (b, a) tie in both objectives. The efficient set is the 58
  points with |x1 - x2| <= 1. `bench_crn.py verify` holds the exact
  certificate (step 5b's) to PyMOSO's own on zero-error values: 729 of
  729 sets agree, 390 certified. The known-uncertified set is E less a
  mirror pair: E less one point would still be covered by its tied
  mirror, the plateau harness's mistake. On this problem no set's
  certification depends on the radius, so the radius handling is
  exercised on random 6 x 6 tie-rich tables (as in step 5b). It is
  the known answer for the solver runs above.
- **The measurement, calibrated.** `Calib` and `CalibVar` have exact
  correlations: 1 and 1 under CRN; 0.5 and 0 for `CalibVar`, which
  discards (x1 + x2) % 2 draws between its two normals; 0 without CRN.
  `bench_crn.py calibrate` recovers all 1,440 pair-objective values
  within 4.5 standard errors.
- **Every check shown to detect** (`bench_crn.py mutations`):
  - **the measurement:** replications paired off by one, default
    coordinates in the CRN arm, correlation pooled across objectives,
    variance ratio inverted;
  - **the certificate:** strict domination for weak, ties counted as
    domination (both caught by the sync problem's own mirror ties, not
    only by the random tables), no non-dominated test, radius ignored
    (caught only by the random tables, as above), neighbours outside
    the box counted;
  - **the closed form:** a stockout at d >= x; the cyclic twins'
    means without Q's term.
- **The recorder was reached.** Every replication is recorded from
  `SerialExecutor.run`, and every point's count is checked against what
  was asked for. The sweep and shift experiments replay the recorded
  streams and check that the replay reproduces the recorded outputs.

## Against the predictions stated in advance

- **"The synchronization case shows correlation collapsing to near zero
  where draw counts differ, so CRN costs stream bookkeeping and buys
  nothing": refuted.** On `SyncVar` the correlation is 0.91 and 0.94,
  and CRN still cuts the difference's variance 11 to 18 times. On
  `CycRare`, the structure built to make it true, the correlation falls
  to 0.59 and 0.75, not to zero, and CRN is still the better arm for
  every solver. The mechanism stated, "everything after the divergence
  is effectively independent", is right for a fixed cycle shifted for
  good, and only partly right otherwise.
- **Mine, "correlation falls in proportion to the synchronized share":
  refuted.** Equal draw counts are the wrong measure of
  synchronization; draws used in the same role, at any offset, are the
  right one.
- **The threshold case** is not built. The prior argument stands as
  reasoning: a shared uniform choosing a branch is a monotone coupling,
  so a negative covariance needs outputs that move in opposite
  directions with the draw. A realistic routing model has a second
  difficulty: it also shares the draws that follow the branch (a
  service time, a demand), and those move both points the same way
  whichever branch is costlier. So the flip in the branch's direction
  should lower the correlation near where the branches' costs cross,
  not make it negative. A negative covariance needs a model whose
  response to its dominant shared draw changes sign between neighbours:
  a hedge, or a balance between two resources whose demands move in
  opposite directions. Which of these to build is a decision about
  realism, not yet made.
