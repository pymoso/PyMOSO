# R-PE's coverage error as betaeps varies: reference figures

Phase 7, re-measured 2026-11-16 on `6844210`. That is the code with
every audit fix that touches R-PE (`docs/algorithm-audit.md`): the
three from step 7 -- the preprint's relaxation, se · m^(1/2 − β)
(finding 2), PE's traceback reading the constrained objective's
intervals (finding 1), random tie-breaks between the objectives
(finding 7) -- and, since, findings 8, 9, 10, 14, 3, 5 and 4, with
`KNOWN_ISSUES.md` issue 17's fixes (floats added left to right; the
oracle's mean and variance computed exactly). These are the reference
figures for that code. They replace the tables of 2026-10-21, which
were computed after step 7 and before the later fixes; "Which fixes
moved the figures", below, connects the two. `docs/relaxation-sweep.md`
is the earlier study on the old code; its conclusion, that the
published β study matches the old arithmetic, is consistent with the
published figures, not established. It is kept as a record.

Regenerate with `python docs/bench_beta_sweep.py 100 6 1` (with CRN)
and `python docs/bench_beta_sweep.py 100 6 0` (without).
`tests/test_benchmark_scripts.py` checks only that the script runs. If
planning a re-run, note that on a 12-thread machine, two jobs side by
side with six workers each, a job took about 2.5 hours on Python 3.14
and 3.6 hours on 3.10.

**The tables are identical on Python 3.10 and 3.14.** All four jobs
were run on both, and all 6,000 per-run metrics are identical. They
also equal, to the three decimals printed, the tables the same code
gave before the oracle's exact mean and variance (`6844210`), so that
change moved nothing here. Across platforms they were not run; the
platform measurement (`KNOWN_ISSUES.md` issue 17) ran R-PE at this
budget, four paths per problem and CRN setting, on Linux, Windows
and macOS on both architectures, with the
same results everywhere and margins of 4 x 10^10 or more. So the
tables should reproduce there.

## Method

R-PE, `testsolve` with each tester's random x0, 100 runs per β,
budget t = 0.4 × 10^6, β from 0.1 to 1.5 in steps of 0.1 (the
preprint's axis, §9.3, Figures 10 and 12, left panels). Every β uses
the same seed, `(12345,)*6`, so each run has the same x0 and, since
streams are coordinate-derived, the same random numbers at each
(point, iteration) under every β; run i under one β and run i under
another are a paired comparison. The metric is the tester's: the
Hausdorff distance from the true images of the run's final solution to
the true efficient set (T_A), or the least such distance over the
local efficient sets (T_C). Quantiles are order statistics at q(n − 1),
interpolated. Python 3.10 and 3.14. The preprint used 1,000 runs;
these use 100.

## With CRN

```
Problem TA: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    2.282     2.777    3.049    3.188
           0.2    2.304     2.733    3.044    3.192
           0.3    2.282     2.775    3.043    3.182
           0.4    2.038     2.311    2.639    2.827
           0.5    1.088     1.310    1.667    1.912
           0.6    0.707     0.761    0.867    1.118
           0.7    0.426     0.514    0.620    0.765
           0.8    0.390     0.456    0.761    0.847
           0.9    0.362     0.410    0.620    0.761   <- least median
           1.0    0.362     0.410    0.580    0.796
           1.1    0.390     0.552    0.761    0.951
           1.2    0.390     0.518    0.841    1.057
           1.3    0.362     0.502    0.761    1.051
           1.4    0.383     0.442    0.761    1.051
           1.5    0.362     0.442    0.841    1.105
Problem TC: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    2.006     2.995    4.130    4.419
           0.2    1.780     2.396    3.581    4.130
           0.3    1.727     1.817    2.684    3.384
           0.4    1.101     1.727    2.006    3.319
           0.5    1.101     1.727    2.006    3.319
           0.6    0.000     0.646    0.779    1.214
           0.7    0.000     0.244    0.651    0.779
           0.8    0.000     0.488    0.646    0.779
           0.9    0.000     0.488    0.646    0.779
           1.0    0.000     0.567    0.646    0.779
           1.1    0.000     0.488    0.646    0.779
           1.2    0.000     0.244    0.646    0.779
           1.3    0.000     0.488    0.646    0.779
           1.4    0.000     0.567    0.646    0.646
           1.5    0.000     0.052    0.646    0.779   <- least median
```

The "least median" marker picks the first of any ties: on T_A, β 0.9
and 1.0 both have 0.410. On T_C from β 0.7 up the median is a poor
guide: 44 to 50 of the 100 runs reach a distance of exactly 0 at
each of those β, so the median falls between 0 and the next run's
value, and 0.052 at 1.5 is not meaningfully better than 0.244 at 0.7.
The mean is 0.34 to 0.38 at every β from 0.7 to 1.5 (0.60 at 0.6,
1.62 at 0.5). β 0.4 and 0.5 have the same quantiles on T_C; 43 of
their 100 runs are identical.

## Without CRN (PyMOSO's default)

```
Problem TA: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    3.068     3.454    4.100    5.041   <- least median
           0.2    3.125     3.820    4.544    5.112
           0.3    3.021     3.819    4.550    5.099
           0.4    3.108     3.843    4.543    4.866
           0.5    3.058     3.755    4.223    4.777
           0.6    3.161     3.814    4.381    4.928
           0.7    2.722     3.814    4.184    4.901
           0.8    3.073     3.780    4.444    4.698
           0.9    2.730     3.665    4.308    4.916
           1.0    3.326     3.835    4.438    4.795
           1.1    2.856     3.746    4.308    4.796
           1.2    3.000     3.704    4.074    4.793
           1.3    3.366     3.794    4.184    5.148
           1.4    3.298     3.805    4.292    4.814
           1.5    3.290     3.922    4.330    4.726
Problem TC: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    4.419     5.580    5.663    5.663
           0.2    3.683     5.663    5.663    5.663
           0.3    1.882     2.258    3.319    3.683
           0.4    1.780     1.877    2.431    3.319
           0.5    1.780     1.847    2.258    3.319
           0.6    1.474     1.780    2.156    2.685   <- least median
           0.7    1.474     1.780    2.135    2.684
           0.8    1.474     1.780    2.180    3.341
           0.9    1.429     1.780    1.884    2.747
           1.0    1.473     1.780    1.884    2.275
           1.1    1.482     1.780    1.930    2.686
           1.2    1.474     1.780    1.984    2.445
           1.3    1.472     1.780    1.947    2.669
           1.4    1.339     1.780    1.899    2.341
           1.5    1.485     1.780    1.908    2.684
```

No run without CRN reaches 0 on either problem.

## What the tables say (measured, these runs)

- **T_A without CRN, the default: the median coverage error is 3.45
  to 3.92 at every β, flat in β, against 0.41 at best with CRN.**
  Paired with the default, every other β is better in 43 to 54 of the
  100 runs: on this problem without CRN, β does not matter. The fixes
  since step 7 lowered it a little (3.9 to 4.35 before); the
  conclusion of step 7, that this is the method's behaviour without
  CRN at this budget and not a defect's, stands.
- **T_C without CRN: very poor at β 0.1 and 0.2 (medians 5.58 and
  5.66), then 1.85 at the default and 1.78 at every β from 0.6 up,**
  against medians of 0.05 to 0.57 with CRN over the same range.
  Paired with the default, each β from 0.6 to 1.5 is better in 55 to
  64 runs and worse in 30 to 41.
- **With CRN, T_A is worst and flat from 0.1 to 0.3 (medians 2.73 to
  2.78), falls from 0.4 to 0.7, and from 0.7 to 1.5 has medians of
  0.41 to 0.55,** least at 0.9 and 1.0.
- **With CRN, T_C falls from 3.00 at 0.1 to 1.73 at 0.4 and 0.5, then
  drops at 0.6;** from 0.7 to 1.5 about half the runs reach 0 and the
  mean is 0.34 to 0.38.

## The default, β = 0.5

The default stays 0.5, by decision. These figures say it is not the
best setting for these two problems at this budget:

- **With CRN it sits at the top of the fall on both problems.**
  Paired run by run, β = 0.7 is better than 0.5 in 100 of the 100 T_A
  runs, and in 87 of the T_C runs (4 worse, 9 the same). Every β from
  0.6 to 1.5 is better than 0.5 in 90 to 100 T_A runs and 74 to 87
  T_C runs. On T_A the default's median is 1.31 against 0.41 at best;
  on T_C 1.73, against a mean of 0.34 to 0.38 from 0.7 up.
- **Without CRN it hardly matters on T_A** (above), and on T_C β of
  0.6 or more is modestly better (1.78 against 1.85 in the median).
- **The low end is the worst place with CRN,** on both problems,
  which includes the published "(0.2, 0.4)" guidance (below): β 0.1
  to 0.3 is worse than the default in 95 or 96 of the T_A runs and
  50 to 78 of the T_C runs.

What this does not establish: one solver, two problems, one budget,
one seed and 100 runs. It is not evidence about a user's problem, and
not a recommendation of any other value; it says where these two test
problems put the default.

## Returned-set sizes: the default against β = 1.0 (measured, 2026-11-19)

The tables above are R-PE's coverage error. This section is the other
visible effect of β: how many points R-PERLE returns. It compares the
default (betaeps = betadel = 0.5) with both at 1.0. The 1.0 setting is
2.0's equivalent of 1.1.0's default (`docs/algorithm-audit.md`, finding 2).

R-PERLE, budget 4 x 10^6, CRN, seed `12345,...` x 6. The runs are
paired: run i starts at the same point in both. The table gives points
in each run's last returned set at or below 4 x 10^6.

| problem | runs | default: min, quartiles, max | β = 1.0: min, quartiles, max | β = 1.0 larger / same / smaller |
|---|---|---|---|---|
| T_A | 10 | 13, 14 / 15 / 15, 19 | 48, 49 / 50 / 50, 57 | 10 / 0 / 0 |
| T_B | 10 | 26, 30 / 41 / 46, 49 | 26, 50 / 51 / 51, 54 | 9 / 1 / 0 |
| T_C | 100 | 3, 6 / 7 / 9, 10 | 3, 6 / 9 / 14, 16 | 64 / 19 / 17 |

On T_A and T_B the larger sets cover the front more completely. On T_C
some are larger because they carry a point off the front
(`docs/algorithm-audit.md`, finding 2c).

What this does not establish: one solver, three problems, one budget
and seed. T_A and T_B have 10 runs each. The runs and the script
are not in the repository. They ran on PyMOSO 0da761c and 52053c6,
whose R-PERLE is the same as 2.0's.

## Which fixes moved the figures (measured, 2026-10-28)

A sweep on the tree after each fix, run on 2026-10-28 (Python 3.10;
the last tree also on 3.14, identical in all 6,000 metrics). Its
output files were not kept, and the record of its analysis is not in
this repository; the last tree's tables are the ones above. Findings 8, 9 and 10 changed
nothing: the tree after finding 9 reproduced the 2026-10-21 tables,
all 60 rows to three decimals.

| After finding | T_A, CRN, β 0.5 | T_A, CRN, least | T_C, CRN, β 0.5 | T_C, CRN, least | T_A, no CRN, medians | T_C, no CRN, least |
|---|---|---|---|---|---|---|
| 9 (and 8, 10) | 1.453 | 0.410 at 0.9 | 1.101 | 0.646 at 0.6 | 3.90 to 4.35 | 1.780 |
| 14 | 1.438 | 0.410 at 0.9 | 0.908 | 0.646 at 0.6 | 3.87 to 4.28 | 1.780 |
| 3 | 1.325 | 0.410 at 0.9 | 0.651 | 0.646 at 0.6 | 3.66 to 4.11 | 1.697 |
| 5 | 1.389 | 0.410 at 0.9 | 0.646 | 0.646 at 0.5 | 3.58 to 4.00 | 1.635 |
| 4 (current) | 1.310 | 0.410 at 0.9 | 1.727 | 0.052 at 1.5 | 3.45 to 3.92 | 1.780 |

Medians of 100 runs; differences of a few hundredths are within
noise. The paired counts (run i on one tree against run i on the
next, all 15 β pooled, 1,500 pairs) are the better evidence:

- **Finding 14 (SPLINE's stop) barely matters:** 1,310 of 1,500 T_A
  runs and 1,379 T_C runs with CRN are unchanged.
- **Finding 3 (PE's LWEP filter) is the large change on T_A with
  CRN:** 821 runs worse, 515 better. The median at β 0.1 to 0.3 goes
  from about 1.6 to about 2.8; at 0.5 and above it improves slightly;
  the least, 0.410 at 0.9, does not move. Without CRN it makes T_C
  worse at low β (median 3.68 to 5.58 at 0.1).
- **Finding 5 (SPLI's infeasible return):** small effects either way.
- **Finding 4 (SPLI's nearest-integer line search) reshapes T_C with
  CRN:** 632 better, 481 worse. From β 0.6 up, runs reaching 0
  appear for the first time; at the default, 70 of 100 runs are
  worse and the median goes from 0.646 to 1.727. It is what moved the
  default off T_C's good region.

## Against the published figures (read by eye)

The published curves, read from Figures 10 and 12 to about 0.1
(`docs/relaxation-sweep.md` has the table), have T_A least, at a
median of about 0.7, for β in (0.2, 0.4), rising to about 1.25 at 1.0
and 1.6 at 1.5. On the current code with CRN, T_A is at its worst
over 0.1 to 0.3 (medians 2.73 to 2.78) and least at 0.9 and 1.0.
Which code produced the figures cannot be established from this
repository, so this is a difference between the published runs and
these, recorded and not explained. It is not evidence about the
formula, which is decided.

## What this leaves open

Whether the README's description of `betaeps`, or the guidance step 8
writes, should say where these problems put the default is a decision,
not something this sweep settles. The sweep covers one solver, two
problems, one budget and 100 runs.
