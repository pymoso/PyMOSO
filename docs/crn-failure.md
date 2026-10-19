# Where CRN fails: synchronization, and the covariance's sign

Phase 7, step 6b (`docs/phase7-plan.md`). CRN reduces
Var(g(x) - g(y)) = Var g(x) + Var g(y) - 2 Cov(g(x), g(y)), and helps
only as far as the covariance is positive. The first candidate failure
is synchronization: neighbouring points that consume different numbers
of variates, so the same random number is used for different purposes.
This document measures that case directly, as the correlation between
neighbouring points' replications, and then what it costs the solvers.
The second half asks whether any structure makes the covariance
negative: a routing threshold, a conservation constraint, and an
antithetic construction.

Tables are generated: `docs/crn-failure-tables.md`, by
`python docs/bench_crn.py report` from `scratch/phase7/crn_covariance.json`
and `scratch/phase7/crn_runs.jsonl`; and `docs/crn-sign-tables.md`, by
`python docs/bench_crn_sign.py report` from
`scratch/phase7/crn_sign_covariance.json` and
`scratch/phase7/crn_sign_runs.jsonl`.
The scripts' docstrings have the commands. **Everything here is measured**
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
differs from `SyncVar` is a race between two rates, **measured** along
the sweep's pairs (the sweep table's "part" and "rejoin" columns): of
periods in role, the share followed by one out of role, and of periods
out of role, the share followed by one back in.

| T = 300 | part, per period | rejoin, per period | in role, predicted from the two | in role, measured |
|---|---|---|---|---|
| `SyncVar` | 0.048 | 0.117 | 71% | 73% |
| `CycRare` | 0.099 | 0.054 | 35% | 37% |

- **How often neighbours part.** `CycRare`'s neighbours part about once
  in ten periods (Q is drawn on D1 = x1 at one point and D1 = x1 + 1 at
  the other), `SyncVar`'s about once in twenty.
- **How fast they rejoin.** `CycRare`, about once in nineteen periods:
  it can re-couple only on a period whose demand equals the stock level
  exactly. `SyncVar`, about once in nine on these pairs. Its pattern
  depends on the draw's value whenever a stockout is possible, so its
  rate depends on x: a first look at four other pairs gave 0.053 for
  `SyncVar` and 0.051 for `CycRare`. That `CycRare`'s rate does not
  move with x and `SyncVar`'s does is what the mechanism predicts; the
  dependence on x itself is reasoning from two samples of pairs.
- **The two rates account for the share in role.** A two-state chain
  with those rates settles within 2 points of the measured share at
  T = 300. At T = 30 the measured share is higher (80% and 52%
  against 72% and 38%), because every replication starts in role.

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
quality. **For a user: synchronize if you can, and use CRN either way.**
Drawing a variate every period whether or not it is needed (`CycFixed`'s
discarded Q) bought back the whole loss here; turning CRN off helped
on none of the four twins.

## The sign of the covariance: threshold, conservation, antithetic

Three more problems, each synchronized (every point draws the same
variates in the same roles), so that only the shape of a point's
response to its draws sets the covariance. Every period is i.i.d.,
so a replication's correlation between two points equals one
period's at any number of periods, and each pair's correlation is
known exactly (`scratch/phase7/crnsign.py`). The measured correlations
were held to those values pair by pair.

| exact, under CRN, median (min) | objective 1 | objective 2 |
|---|---|---|
| `Route`, threshold axis | 0.81 (0.51) | 0.77 (0.20) |
| `Route`, capacity axis | 0.98 (0.68) | 0.99 (0.75) |
| `Split`, axis pairs | 0.99 (0.69) | 0.99 (0.69) |
| `Split`, swap pairs (x + e1, x + e2) | 0.98 (-0.05) | 0.98 (-0.05) |
| `Antithetic`, axis pairs | -0.85 (-1.00) | -0.80 (-0.94) |
| `Antithetic`, swap pairs | 0.99 (0.00) | 0.98 (0.00) |

- **`Route`, the threshold case.** Customers draw a routing level
  (server A below the threshold x1, else B) and then a service time,
  shared after the branch. Positive at every pair (measured median 0.88
  and 0.89; variance ratio 0.13 and 0.12). The customers that change
  server at x + e1 keep their service time, and that shared draw moves
  both points the same way whichever server is costlier. **This is
  structural, not a weakness of this model:** it is the same Chebyshev
  argument that predicted it. A shared uniform choosing a branch is a
  monotone coupling, and every draw after the branch is shared too.
  The correlation is lowest where the step moves customers across a
  capacity (overflow 0.51 at x1 = 8 to 9 with capacity 9) or sends the
  first customers to A (idle + transfer 0.20 at x1 = 0), **not near a
  balanced allocation, as I predicted.**
- **`Split`, the conservation case.** A fixed total demand of 20 split
  between two substitutes by one shared preference draw. Exact only:
  the enumeration is the answer and a simulation would add only noise.
  No axis pair is negative (smallest 0.69); 2 of 400 swap pairs are, at
  -0.05. **My prediction, that it would go negative near the balanced
  stocking point, is refuted, and was refuted before anything was
  built.** The split makes the two products respond in opposite
  directions at the same point; CRN compares one objective at two
  neighbouring points, and there each product's cost is a V-shaped
  function of the draw whose corner moves by one demand level per
  step. The two responses disagree only within that one level.
- **`Antithetic`, artificial on purpose.** `SyncFixed`, reading every
  uniform u as 1 - u at points with x1 + x2 odd. Every axis neighbour
  has the other parity, so the coupling is reversed; swap pairs share a
  parity and keep `SyncFixed`'s. Marginals identical to `SyncFixed`'s
  (checked; and at even points the outputs are `SyncFixed`'s,
  replication for replication). Measured: correlation -0.85 and -0.79,
  **variance ratio 1.85 and 1.79**: CRN nearly doubles the variance of a
  neighbour difference against independent sampling.

**So a negative covariance between neighbours needs the draws to change
role between them.** If neighbours use the same draws in the same roles,
their responses are nearly the same function of the draws, and the
covariance is positive; a threshold, a routing decision and a
conservation constraint do not change that. Desynchronization changes
roles, and goes to about zero (the shift table), not below. Only the
deliberate construction went negative.

**What it costs the solvers** (R-PERLE, R-PE, R-MinRLE; 20 seeds,
budget 20,000; `SyncFixed` rerun with the same seeds, and its 120 runs
reproduce the earlier ones exactly):
- **`Antithetic` against its twin, the control passes:** default arm,
  `Antithetic` worse than `SyncFixed` on the same seed in 5-11 of 20.
  Under CRN, worse in 14-15 of 20.
- **But CRN is not worse than the default arm on `Antithetic`.** R-PE
  and R-PERLE: better on 15 of 20 seeds at 20,000 (median 0.21 against
  2.7-3.0), and slightly better at 5,000 (11-13 better, 5-7 worse;
  medians 3.4-3.5 against 3.7-3.8).
  R-MinRLE: even (9 better, 10 worse; median 2.83 against 1.93). My
  reasoning, not measured: a solver compares neighbours with each
  other as well as with x, and those comparisons (x + e1 against
  x + e2) share a parity and keep a correlation of about 0.99.
- **`Route`:** CRN better than default in 10-12 of 20 seeds at 20,000,
  worse in 4-6 (medians 0.14-0.20 against 0.29-0.31); mixed at 5,000.

So even the artificial reversal, applied to every axis pair, did not
make CRN lose to the default arm on more seeds than it won, for any
solver; R-MinRLE's median is worse under CRN, on an even split of
seeds. The guidance stands.

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
- **The sign problems** (`scratch/phase7/crnsign.py`,
  `bench_crn_sign.py`). Route's closed-form means are exact fractions
  by enumeration (19 efficient points, one tie), checked against the
  simulation without CRN (largest |z| 2.38); `bench_crn_sign.py verify`
  holds its exact certificate to PyMOSO's on 717 of 717 sets (377
  certified). Every measured pair, in both arms, is within 4.5 standard
  errors of its exact correlation (Fisher z; a jackknife error, because
  a normal-theory one put `SyncFixed`'s largest |z| at 4.1; the
  normal-theory error only where the jackknife is undefined, one pair).
  `bench_crn_sign.py mutations` catches all 14 wrong versions tried:
  replications paired off by one, default coordinates in the CRN arm,
  correlation pooled across objectives (each on Route and on
  Antithetic); Antithetic's exact correlation with the cost and its flip
  taken as independent, and without the flip; Route's closed form with
  the threshold at R <= x1; and the five wrong certificates, of which
  Route alone catches three (strict domination, no non-dominated test,
  outside neighbours) and the random tables the other two (ties, the
  radius), Route having one tie and no radius-dependent set.
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
- **"Threshold structure gives a genuinely negative covariance":
  refuted, by the Chebyshev argument in advance and by `Route` after.**
  Positive at every pair. Mine, that it dips near the balanced
  allocation: wrong about where; it dips at capacity boundaries.
- **Mine, "a split between substitutes goes negative near the balanced
  stocking point": refuted by exact enumeration, before building.**
- **The rates' race, inferred in part 2:** confirmed by measuring the
  two rates; the in-role share they predict is within 2 points.

## How often the apparatus was wrong

Six times in this step, plus one prediction of mine, each caught by a
check or by a contradiction between two measurements before any
conclusion rested on it. That is the reason to trust what survived.
Counted are errors that would have produced a wrong number or a false
alarm; crashes are not.
1. **The certificate check could not see a radius-ignoring
   certificate** on the sync problem, which has no radius-dependent
   set. Found by its mutation passing; random tie-rich tables added.
2. **A covariance run used an older script** (a background process
   started before an edit). Noticed, killed and rerun.
3. **Equal draw counts as the measure of synchronization.** The shift
   experiment contradicted it; "in role" replaced it.
4. **The solver control table's columns were swapped**, so a passing
   control read as a failed one. The raw values contradicted the
   table.
5. **The rates prototype aligned periods by index,** which measures
   "in step", and gave a rejoin rate of 0.001. It contradicted the
   sweep's 73% in role.
6. **The sign measurement's gate was wrong for this data:** a
   normal-theory error, too small for heavy-tailed correlations near 1
   (`SyncFixed` reached |z| = 4.1 on a correct measurement), and then a
   jackknife undefined at a correlation within one replication of 1,
   which stopped a run on a correct pair. Both false alarms, not false
   passes.
And **`Split`'s prediction**, an error of reasoning rather than of the
apparatus, caught the same way: by an exact check, before anything was
built on it.
