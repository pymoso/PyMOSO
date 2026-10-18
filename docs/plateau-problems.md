# Plateau problems: what the SPLINE family does when the true gradient is zero

Phase 7, step 6 (`docs/phase7-plan.md`). Integer capacity thresholds,
where an objective is flat until a threshold is crossed, are common in
staffing, batching and inventory. On such a plateau the true
pseudo-gradient is zero. This is the first of the pathological
structures, built and measured.

Tables are generated: `docs/plateau-problems-tables.md`, by
`python docs/bench_plateau.py report` from
`scratch/phase7/plateau_runs.jsonl` and `plateau_describe.json`. The
script's docstring has the commands. **Everything here is measured**
unless it says it is reasoning. Runs are counted, not timed.

## The headline: noise turns a plateau into a random walk, and CRN turns it into a stall

SPLI stops only when PLI's pseudo-gradient is exactly zero, and PLI
builds it from differences of *estimated* values. On a plateau the
true differences are zero; the estimated ones are not.

- **Without CRN (the default), the pseudo-gradient is never exactly
  zero:** 0% of PLI calls in every configuration. PLI returns a random
  direction, and the line search's doubling steps accept a step whenever
  the noise favours it. At width 10 and radius 1, R-SPLINE's SPLI made
  28 moves that lowered the true objective and 812 that lowered only its
  estimate (sums over 20 seeds); NE made 2 and 435, and every one of
  those 435 was to another point of the same cell, a true tie. The
  multi-objective solvers look the same (R-PERLE: SPLI 67 / 1,368, NE 15
  / 964). The search does not stall: it random-walks with long steps,
  and crosses into a better cell only occasionally (a median of 2-4
  cells visited at width 10).
- **With CRN, equal true values give exactly equal estimates,** so the
  pseudo-gradient is exactly zero on 65-92% of PLI calls on the plateaus
  (none on the control), and no move is ever accepted on noise alone.
  The search stalls: a median of 0 cells visited, and quality identical
  at 1,000, 5,000 and 20,000 simulations in every plateau configuration.

**Neither outcome is the correct one.** At radius 1 neither reaches the
optimum on plateaus 10 or 20 wide. The random walk makes slow true
progress (R-SPLINE on 5-wide plateaus is back to the control's quality
by 20,000 simulations); the stall makes none. Which is preferable
depends on what the user wanted. On the control, without plateaus, CRN
is the better arm (R-PERLE reaches the efficient frontier by 5,000
simulations with it, not by 20,000 without).

## The problem and its known answer

`scratch/phase7/plateau.py` (kept in scratch/; whether it belongs in
`pymoso/problems/` is a decision for after 2.0). On {0..59}^2, cut into
W x W cells, W in {1, 5, 10, 20}. Each objective is one of the two
isotropic quadratics of the barrier problem (centred at (15, 30) and
(45, 30)) taken at the centre of the point's cell, so every point of a
cell has exactly the same true value. W = 1 is the matched control: the
same functions at each point. Additive Gaussian noise, sigma 1; starts
uniform on the box.

**The known answer, checked.** The efficient set E (the optimal cells'
points, all tied), certification at any radius, and the descriptor
below come from enumerating the box on the true means. The exact
certificate is the one validated in step 5b; `bench_plateau.py verify`
holds it to PyMOSO's own (as `RLESolver.rle` applies it, on exact values
with zero standard errors) on the plateaus, where ties are everywhere:
568 of 568 sets agree, 206 of them certified. `bench_plateau.py
mutations` shows the check detects five wrong certificates, including
the two that turn on ties (strict instead of weak domination; ties
counted as domination), which step 5b's first harness missed. The
harness was wrong once more before it was right here: its "known not
certified" set was E less one point, which on a plateau is still
certified (the point's tied neighbours in E weakly dominate it); it is
now E less one of its cells.

**A property of the problem alone, not of any solver** (by enumeration,
3,600 points): how many single points are certified traps, sets of one
point PyMOSO's certificate would accept, at each radius.

| width | efficient points | certified single points at r = 1 / 2 / 3 / 6 / 10 |
|---|---|---|
| 1 (control) | 31 | 0 / 0 / 0 / 0 / 0 |
| 5 | 175 | 2,107 / 988 / 378 / 0 / 0 |
| 10 | 400 | 2,860 / 2,200 / 1,620 / 480 / 0 |
| 20 | 1,200 | 3,248 / 2,912 / 2,592 / 1,728 / 800 |

The tables also give first-objective local minima (the traps of a
single-objective search) and ties between cells: none on the plateaus
in both objectives; 1,740 pairs on the control, from its mirror
symmetry about y = 30. Anyone reproducing the experiment's difficulty
can reproduce this table without running a solver.

## Does a larger radius help? Without CRN, decisively; with CRN, not

Width 10, radii 3 and 6 against radius 1, 20 seeds, budget 20,000;
quality against the control on the same seed.

- **Without CRN, radius 6 reaches the optimum.** R-SPLINE's median gap
  is 0 by 1,000 simulations; R-PERLE, R-PE and R-MinRLE reach a median
  Hausdorff distance of 0 by 20,000, better than their own control
  (no plateaus, radius 1) in 16, 11 and 17 of 20 seeds. Radius 3 helps
  part of the way (R-SPLINE 0 by 5,000; the others about 50 at 20,000,
  against 88-90 at radius 1).
- **With CRN, radius 6 does not rescue the search.** R-SPLINE's median
  gap is 15.5 (38.5 at radius 1); the others 88 (127 at radius 1). The
  mechanism, measured: with CRN no move within a cell is ever accepted,
  so one move across a boundary leaves the point at the near edge of
  its new cell, and the next better cell is out of reach. For R-SPLINE
  at radius 6, every final point under CRN is either at the optimum (3
  of 20) or 7 to 10 from the nearest strictly better point (17 of 20),
  beyond the radius; without CRN all 20 end at the optimum.

So the random walk is what makes the radius work: noise-accepted moves
within a plateau carry the point across it until a boundary is within
the radius. The pseudo-gradient contributes almost nothing either way.

## ExampleBnBSolver: it cannot run at these budgets

One arm of the in-tree MOPBnB port, labelled as a non-local sampler
only: its subregions are scattered samples, not regions, so it is not
partition-and-bound (`docs/mocompass-mopbnb-known-issues.md`, item 0),
and nothing here says anything about partition-and-bound.

It does not finish. Its second iteration's replication count is set
from the smallest gap between estimates and is not bounded by the
budget (item 2b there): with a budget of 20,000 it asked for 56,450
replications per point on the control (median), 160,813 on 5-wide
plateaus, 867,950 on 10-wide and 91,626,291 on 20-wide. A run was
stopped once its next request would take it past 50 times its budget:
6 of 20 control runs finished, 1 of 20 on 5-wide plateaus, none on the
wider ones. Whether a non-local sampler copes with plateaus is not
answered by this solver.

## Against the prediction stated in advance

"The plateau defeats both PLI and the line search, so the SPLINE family
stalls where it starts and a larger radius does not help."

- **Defeats PLI and the line search: confirmed.** Moves that lower the
  true value are a few percent of SPLI's on the plateaus; under CRN the
  pseudo-gradient is exactly zero most of the time.
- **Stalls where it starts: true only with CRN.** Without it the search
  random-walks with long steps, mostly within cells, sometimes across.
- **A larger radius does not help: true only with CRN.** Without it,
  radius 6 reaches the optimum on 10-wide plateaus, because the random
  walk brings a boundary within reach.
