# NE's quadratic candidate and best-improvement scan

Phase 7, steps 4 and 5 (`docs/phase7-plan.md`). Two solver parameters,
both default 0, added for comparison against the reference:

- `bestimprove`: NE scans every neighbour and moves to the best,
  as the MATLAB R-SPLINE does (`docs/RSPLINE.m`, NE, lines 239-291),
  instead of to the first that improves, which is PyMOSO's rule and
  stays the default.
- `quadratic`: NE's quadratic candidate, from the same MATLAB (lines
  216-312). Along each axis the centre and its two neighbours give a
  parabola; where both neighbours are feasible and it is convex
  (`a - 0.00005 > 0`), the coordinate takes the vertex, cast as
  MATLAB's `int32()` casts. One candidate is assembled from all
  coordinates and evaluated after every neighbour, so certification is
  unchanged. Radius 1 only.

Every table is generated: `docs/ne-quadratic-tables.md`, by
`python docs/bench_ne_quadratic.py report` from the raw runs in
`scratch/phase7/ne_quadratic_runs.jsonl`. The script's docstring has
the commands. **Everything below is measured** unless it says it is
reasoning. Nothing is timed: these are counts of simulations, `g()`
calls and NE and SPLINE events, which do not depend on the machine.

## The design

Four cells: the reference, the candidate alone, best-improvement alone,
and both. Every built-in RA solver (R-SPLINE on the first objective;
R-PERLE, R-PE, R-MinRLE) on every built-in test problem it can solve
(ProbSimpleSO for R-SPLINE only; ProbTPA, ProbTPB, ProbTPC for all
four): 13 pairs, 20 seeds each, the same seeds and starts in every cell
(starts drawn by each problem's tester), budget 5,000, MRG32k3a,
non-CRN, serial. 1,040 runs.

The expensive tiers are not used: simulation is 97-99% of a run at
Moderate and over 99% at Heavy (step 1), so wall time there would only
confirm that call counts scale by cost per call.

**A run's total simulations are pinned near its budget,** so they
cannot show whether the candidate pays (every cell's run totals are
5,100-5,400 at budget 5,000). The deciding measure is quality at
matched counted simulations: the tester's metric (Hausdorff distance
to the true efficient frontier), or for R-SPLINE the gap between the
true first objective of its solution and the true minimum, at the last
RA iteration at or under 1,000, 2,500 and 5,000 simulations, compared
with the reference seed by seed.

## Why the candidate needs best-improvement

Reasoning first, then the measurement that checks it.

PyMOSO's `ne` returns at the first improving neighbour. The coordinate
that improved, and every coordinate after it, never has both neighbours
evaluated, so the candidate can be formed only when the scan completes,
which under first-improvement means no neighbour improved. That is the
NE call that ends SPLINE. Then y1 >= y2 and y3 >= y2, which forces
a >= |b|, so each vertex offset -b/2a is at most one half and rounds to
the centre, or to a neighbour already evaluated when y1 or y3 equals y2
exactly. The candidate is the centre except at exact ties (and at a
coordinate past the cast's guard, which becomes 0). The centre is in
`gbar`, so evaluating it again costs no simulation.

**Measured: the candidate alone changes nothing.** In all 260 runs of
that cell, results are identical to the reference: simulations, `g()`
calls and quality at every checkpoint (0 better / 20 same / 0 worse in
every row). The candidate was the centre in 92-100% of the NE calls
that formed one, a neighbour in 0-5%, a new point in at most 3%, and a
new point was never taken. With the parameter's default flipped to 1,
every golden still passes. So `quadratic` is useful only with
`bestimprove=1`, and step 5's parameter landed first.

## The candidate with best-improvement

- **It is rarely a new point.** It is the centre in 72-84% of NE calls
  and a neighbour in 7-20%; a new point in 4-10%. Most NE calls are the
  non-improving one that ends SPLINE, where the argument above applies
  under either scan.
- **A new candidate is rarely taken.** Of the feasible new ones, 2-18%
  beat every neighbour and were taken. The exception is R-SPLINE on
  ProbSimpleSO, 69%, whose objective is exactly a parabola.
- **SPLINE has little room to save iterations.** It averages 1.2-1.6 NE
  rounds per call in every cell (exactly 1.0 on one-dimensional
  ProbSimpleSO), and the candidate lowers that by at
  most about 0.15 (R-MinRLE on ProbTPC: 1.50 to 1.35; R-SPLINE on
  ProbTPC: 1.60 to 1.46). Simulations per SPLINE call stay within a few
  percent of the reference.
- **Quality at matched simulations: no consistent gain on ProbTPA,
  ProbTPB or ProbTPC,** for best-improvement alone or with the
  candidate, for any solver. Seed-by-seed counts are mixed and mostly
  within what 20 seeds can tell apart. Two lean one way without
  holding: R-PERLE on ProbTPC with both is better in 16 of 20 seeds at
  1,000 simulations and worse in 11 of 20 at 5,000; R-SPLINE on ProbTPB
  with both is better in 8-9 seeds and worse in 2-5 at every
  checkpoint, too few to call. The clear result is R-SPLINE on
  ProbSimpleSO: with both, better in 9 of 20 seeds at 1,000 simulations
  and worse in none.

**The expectation recorded in advance** was that the candidate would
do well on TPA, TPB and TPC, which are smooth and low-dimensional. It
does not. Measured reason: SPLINE rarely does more than one NE round, so
the fit runs mostly at the final NE call, where its vertex is the
centre; when it does produce a new point, that point rarely beats the
best neighbour at these sample sizes. The one problem where it helps is
the one whose objective is a parabola.

**Not built, noted as a candidate improvement:** the candidate is
evaluated even when it is the centre or a neighbour just evaluated, as
the MATLAB does. In PyMOSO that costs no simulation (the point is in
`gbar`) but is charged to SPLINE's budget.

## SPLINE's budget accounting

`ne` and `spli` charge SPLINE's budget `m` for every feasible point,
including points already in `gbar`, which cost nothing (step 7's
audit). Measured, per SPLINE call: the nominal charge is 1.4-2.0 times
the simulations counted in the reference cells, and up to 2.5 with the
candidate, which adds a charge for the cached centre. SPLINE therefore
stops well short of what its budget would really allow. The bias the
other way, replications of infeasible points that are run and charged
to nothing, is small on these problems: `g()` calls exceed counted
simulations by 0-6% per SPLINE call (the median per cell).

## R-SPLINE's rows are against R-SPLINE without x0 re-estimation

This measurement first ran against an R-SPLINE that re-estimated x0
every iteration (Phase 7 commit `00c3dea`). Its R-SPLINE rows exposed
that change as a regression, and it was reverted
(`docs/phase7-plan.md`, step 7, "x0 re-estimation";
`scratch/phase7/rspline_x0_measure.py`). The tables here were
regenerated after the reversion.
