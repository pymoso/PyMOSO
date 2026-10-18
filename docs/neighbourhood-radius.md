# Neighbourhood radius: what a larger one buys and costs

Phase 7, step 5b (`docs/phase7-plan.md`). The `radius` solver parameter
(default 1) sets the neighbourhood every RA solver searches (NE) and
certifies (`get_ncn`, `remove_nlwep`) against: the lattice points within
Euclidean distance r (`moso.get_nbors`). Two questions: does a radius
above 1 win where it should, on a problem built so that it can; and does
the implementation scale acceptably with radius.

Tables are generated: `docs/neighbourhood-radius-tables.md`, by
`python docs/bench_radius.py report` from `scratch/phase7/radius_runs.jsonl`
and `scratch/phase7/radius_nbors_1.json` (a second timing run,
`radius_nbors_2.json`, agrees within 3%). The script's docstring has
the commands. **Everything here is measured** unless it says it is
reasoning. Runs are counted, not timed, except where a line says
otherwise.

## The subject: a barrier problem with a known answer

`scratch/phase7/barrier.py` (kept in scratch/; whether it belongs in
`pymoso/problems/` is a decision for after 2.0). On the box {0..50}^2,
two isotropic quadratics whose efficient set E is the eleven lattice
points between (20, 25) and (30, 25). Around E, a square annulus t
cells thick costs 1,000 more on both objectives. Outside it, the
non-dominated set T is a trap. Crossing the annulus needs a coordinate
to change by t + 1, so T is certified at radius r exactly when r <= t.
`Barrier1` and `Barrier2` are t = 1 and t = 2. Additive Gaussian noise,
sigma 1; starts drawn uniformly from outside the annulus.

**The known answer, checked.** E, T and every set's certification come
from enumerating the box on the true means: a set is certified at r if
it is mutually non-dominated and every feasible neighbour outside it is
weakly dominated by a member. `bench_radius.py verify` holds that to
PyMOSO's own certificate as `RLESolver.rle` applies it (a set that is
its own non-dominated subset, and `get_ncn` on the exact values with
zero standard errors finding nothing): 1,840 of 1,840 sets agree, 743 of
them certified, on the barriers at radii 1-5 and on random 6x6 tables of
small integers, where ties are common. Four wrong versions of the exact
check (strict instead of weak domination, the radius ignored, no
non-dominated test, neighbours outside the box counted) each make it
fail. It first failed on a set that was not mutually non-dominated: the
harness had modelled PyMOSO's certificate as `remove_nlwep` plus
`get_ncn`, but `rle` gives `get_ncn` only `get_nondom`'s output, and
`remove_nlwep` is applied to the non-conforming neighbours, not to the
set being certified.

E is certified at every radius; T at radius 1 only for t = 1, at radii
1 and 2 for t = 2.

## Finding: the line search crosses a one-cell barrier at radius 1

The trap holds for certification, not for the search. SPLINE's line
search (SPLI) moves along a pseudo-gradient in steps not confined to a
neighbourhood, and jumps a one-cell annulus: at radius 1, measured over
20 seeds, 15 of 20 R-SPLINE runs and 15 of 20 R-PERLE runs on `Barrier1`
ended inside it, every crossing made by SPLI and none by NE. A two-cell
annulus holds: 2 of 20 R-SPLINE runs and none of R-PERLE's crossed. So a
barrier one step wide, the case the plan proposed, does not trap these
solvers; `Barrier2` is the real test, and radius 3 the first that should
escape it.

## Does a radius above the barrier's thickness win? Yes, decisively

20 seeds per configuration, budget 20,000, quality at matched counted
simulations against radius 1 on the same seed (Hausdorff distance to the
true frontier; for R-SPLINE the gap to the true minimum of the first
objective).

- **`Barrier2`, radius 3 and above:** the returned set is inside the
  annulus in every run (median share 100%, against 0% at radii 1 and 2),
  and quality is better than radius 1 in **20 of 20 seeds at 5,000 and
  at 20,000 simulations, for R-PERLE, R-PE and R-MinRLE at every radius
  from 3 to 5**; R-SPLINE 18-19 of 20 (median gap 0.1 against 10).
- **`Barrier2`, radius 2:** no gain. Still trapped (0% inside), as the
  thickness predicts.
- **`Barrier1`, radius 2 and above:** no consistent gain, because radius
  1 already escapes through the line search (median 100% inside at every
  radius).

So radius pays exactly where the neighbourhood has to do what the line
search cannot: past a barrier the line search does not jump.

**Certified on the truth.** The tables also give the share of runs
whose returned set is certified on the true means at its own radius.
It is low (0-10% for the multi-objective solvers inside the annulus): a
returned set is an estimate at budget 20,000, not E itself. It is a
statement about convergence at this budget, not about the trap.

## Does the implementation scale with radius? Yes, at these dimensions

- **Construction is linear and cheap.** `moso.get_nbors` costs about
  0.65 µs per point returned at every radius and dimension measured
  (timed, twice, load 0.66): radius 5 in three dimensions, 514 points,
  in 335 µs, less than one estimate of one point at the cheapest
  replication (`hit(x, m=1)` is about 31 µs of framework time,
  `docs/hit-cost-baseline.md`). In the runs, constructing neighbourhoods
  is at most 9% of wall time (under timing wrappers; R-MinRLE on ProbTPC
  at radius 5), and 0-5% in most configurations.
- **Estimation is the cost, and it cannot be pruned.** Points estimated
  for certification grow with the neighbourhood: on `Barrier2`,
  R-MinRLE estimated 1,580 at radius 1 and 32,734 at radius 5 (medians).
  No evaluation order can skip any of them without being able to change
  the certified set (`docs/phase7-plan.md`, step 5b), so this is the
  price of the radius.
- **It shows as fewer RA iterations, not runaway runs.** No run reached
  the 50x guard; the most `g()` calls any run made was 3.5 times its
  budget, and medians are 1.0-2.0 times (KNOWN_ISSUES.md issue 16's
  overshoot, at these dimensions small). What a large radius costs is
  time to the first iterations: at radius 5, 34-35 of 80 barrier runs had
  not finished an RA iteration by 1,000 simulations, against none at
  radii 1-3. Simulations per returned point do not grow with radius: on
  `Barrier2`, 1,300-1,600 at radii 3-5 for the multi-objective solvers,
  against 2,000-4,700 at radii 1 and 2, where the trapped sets are
  smaller.

These are dimensions 1-3. The neighbourhood grows as r^d, so the same
radius in higher dimension multiplies every one of these costs
(87,480 points at radius 2 in dimension 20, `moso.get_nbors`); nothing
here measures that regime.

## The control: the built-in test problems

R-SPLINE on ProbSimpleSO, ProbTPA, ProbTPB and ProbTPC; R-PERLE, R-PE and
R-MinRLE on the three TP problems; 10 seeds. No consistent effect at any
radius: summed over these configurations, radii 2-5 against radius 1 at
20,000 simulations are better / same / worse in 58/14/58, 63/13/54,
51/12/67 and 57/13/60 seed-pairs. A larger radius costs more and buys
nothing measurable on them, as expected.

## Against the prediction stated in advance

"Radius 2 is prohibitively expensive on anything but very low
dimensions, and buys nothing on the existing test problems. The barrier
problem is where it should pay."

- **Prohibitively expensive: refuted for dimensions 1-3.** Every run
  finished, within 3.5x its budget (medians 1.0-2.0x); the cost is
  slower early iterations.
  Higher dimension is not measured here.
- **Buys nothing on the test problems: confirmed.**
- **Pays on the barrier: confirmed, with a correction.** It pays when the
  radius exceeds a barrier the line search cannot jump. A one-cell
  barrier is not one, so radius 2 buys nothing on `Barrier1`; on
  `Barrier2` radius 2 is still trapped and radius 3 wins in every seed.
