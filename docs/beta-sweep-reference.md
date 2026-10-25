# R-PE's coverage error as betaeps varies: reference figures

Phase 7, after step 7 (2026-10-21). Measured on the code with the three
fixes from `docs/algorithm-audit.md`: the relaxation is the preprint's,
se · m^(1/2 − β) (finding 2), PE's traceback reads the constrained
objective's intervals (finding 1), and PE breaks ties between the
objectives randomly (finding 7). These are the reference figures for
that code. `docs/relaxation-sweep.md` is the earlier study on the old
code, whose conclusion is withdrawn; it is kept as a record and is not
a reference.

Regenerate with `python docs/bench_beta_sweep.py 100 6 1` (with CRN)
and `python docs/bench_beta_sweep.py 100 6 0` (without).
`tests/test_benchmark_scripts.py` checks only that the script runs.
The two runs went side by side on a 12-core machine, six workers
each, and each took about 2.5 hours; that is for planning a re-run,
not a finding. The script fixes the seed, so a re-run on the same
Python should give the same tables. That is inferred, not checked by
a second run, and on another Python version the last bit of a variate
can differ (`KNOWN_ISSUES.md` issue 17). Issue 17 was fixed on 2026-10-24: every Python
now gives 3.10's variates. These tables were computed before that, on
3.14, so a re-run on the fixed code may differ from them; the re-sweep
replaces them.

## Method

R-PE, `testsolve` with each tester's random x0, 100 runs per β,
budget t = 0.4 × 10^6, β from 0.1 to 1.5 in steps of 0.1 (the
preprint's axis, §9.3, Figures 10 and 12, left panels). Every β uses
the same seed, `(12345,)*6`, so each run has the same x0 and, since
streams are coordinate-derived, the same random numbers at each
(point, iteration) under every β. The metric is the tester's: the
Hausdorff distance from the true images of the run's final solution to
the true efficient set (T_A), or the least such distance over the
local efficient sets (T_C). Quantiles are order statistics at q(n − 1),
interpolated. Python 3.14 only. The preprint used 1,000 runs; these
use 100.

## With CRN

```
Problem TA: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    1.284     1.596    1.846    2.257
           0.2    1.282     1.588    1.847    2.152
           0.3    1.316     1.623    1.846    2.124
           0.4    1.316     1.630    1.847    2.122
           0.5    1.263     1.453    1.712    1.852
           0.6    0.746     0.858    1.006    1.282
           0.7    0.439     0.559    0.761    1.051
           0.8    0.390     0.442    0.620    0.761
           0.9    0.360     0.410    0.628    0.841   <- least median
           1.0    0.385     0.552    0.761    0.954
           1.1    0.390     0.442    0.761    1.051
           1.2    0.385     0.442    0.781    1.051
           1.3    0.362     0.442    0.761    1.057
           1.4    0.362     0.552    0.761    1.105
           1.5    0.362     0.535    0.781    1.293
Problem TC: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    2.230     3.582    4.130    4.419
           0.2    1.867     2.684    4.130    4.432
           0.3    1.780     2.006    2.329    3.319
           0.4    1.101     1.780    1.817    1.817
           0.5    0.646     1.101    1.817    1.817
           0.6    0.646     0.646    0.646    1.817   <- least median
           0.7    0.488     0.646    0.646    0.646
           0.8    0.646     0.646    0.646    0.646
           0.9    0.646     0.646    0.646    0.646
           1.0    0.646     0.646    0.646    0.646
           1.1    0.646     0.646    0.646    0.646
           1.2    0.646     0.646    0.646    0.646
           1.3    0.646     0.646    0.646    0.646
           1.4    0.646     0.646    0.646    0.646
           1.5    0.646     0.646    0.646    0.646
```

The "least median" marker picks the first of any ties: on T_C every β
from 0.6 up has median 0.646.

## Without CRN (PyMOSO's default)

```
Problem TA: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    3.387     3.921    4.706    5.406
           0.2    3.308     4.068    4.800    5.336
           0.3    3.321     4.115    4.641    5.406
           0.4    3.263     3.922    4.913    5.406
           0.5    3.111     4.071    4.590    5.345
           0.6    3.515     4.071    4.686    5.615
           0.7    3.485     3.921    4.584    5.422
           0.8    3.231     3.896    4.307    5.012   <- least median
           0.9    3.262     3.896    4.472    5.296
           1.0    3.531     3.978    4.490    5.150
           1.1    3.349     3.937    4.375    4.794
           1.2    3.401     4.070    4.548    5.518
           1.3    3.737     4.349    4.838    5.518
           1.4    3.450     4.012    4.440    5.008
           1.5    3.206     3.937    4.569    5.241
Problem TC: dH at the end of the run, quantiles over 100 runs
          beta    q0.25    median    q0.75    q0.90
           0.1    3.384     3.683    4.419    5.663
           0.2    3.384     3.683    4.203    5.663
           0.3    2.083     2.258    3.258    3.683
           0.4    1.780     1.817    2.186    2.684
           0.5    1.780     1.817    2.279    2.684
           0.6    1.485     1.780    2.211    2.684   <- least median
           0.7    1.474     1.780    2.191    2.716
           0.8    1.485     1.780    1.974    2.684
           0.9    1.470     1.780    1.904    2.684
           1.0    1.474     1.780    2.092    2.700
           1.1    1.482     1.780    2.180    2.684
           1.2    1.474     1.780    2.279    3.701
           1.3    1.500     1.798    2.384    2.691
           1.4    1.511     1.780    2.223    2.774
           1.5    1.474     1.780    2.211    2.684
```

## What the tables say (measured, these runs)

- **T_A without CRN, the default: the median coverage error is 3.9 to
  4.35 at every β, flat in β, against 0.41 at best with CRN.** This
  is the corrected solver, so the number is the method's without CRN
  on this problem at this budget, not a symptom of the three defects.
  The earlier study measured 3.7 to 4.3 on the old code; the fixes
  did not change it. This is the step-8 item in `docs/phase7-plan.md`.
- **T_C without CRN: the median settles at 1.78 from β = 0.6 up,
  against 0.646 with CRN.** Better than T_A, still nearly three times
  worse than with CRN.
- **With CRN, T_A is worst and flat from 0.1 to 0.5 (medians 1.45 to
  1.63), falls steeply from 0.5 to 0.8, and from 0.8 to 1.5 has
  medians of 0.41 to 0.44 (at 0.8, 0.9 and 1.1 to 1.3) or 0.53 to
  0.55 (at 1.0, 1.4 and 1.5).**
  The default, 0.5, is the last β before the fall: its median is 1.45,
  about 3.5 times the least.
- **With CRN, T_C falls from 3.58 at 0.1 to 0.646 at 0.6 and stays
  there to 1.5.** At the default its median is 1.10.

## Against the earlier study (inferred)

Under the old formula, old β = new β − 1/2, so the old CRN table's
"preprint beta" column should line up with this one. It does in shape:
the same plateau, the same fall, at the same place. On T_A the
medians differ most at the fall (0.6: 0.858 here, 0.988 there; 0.7:
0.559 against 0.626) and by up to 0.08 elsewhere; on T_C by up to
0.26, at 0.1 (3.582 against 3.319), and not at all from 0.6 up.
The traceback and tie-break fixes, which also changed every R-PE run
(`tests/golden/README.md`), are the likely cause. They were not
separated from the formula change, so this is inferred.

## Against the published figures (read by eye)

The published curves, read from Figures 10 and 12 to about 0.1
(`docs/relaxation-sweep.md` has the table), have T_A least, at a
median of about 0.7, for β in (0.2, 0.4), rising to about 1.25 at 1.0
and 1.6 at 1.5. On the corrected code T_A is at its worst over
(0.2, 0.4) and least at 0.8 to 1.3. The figures came from earlier code
that is outside this repository and out of scope
(`docs/algorithm-audit.md`, finding 2), so this is a difference
between that code and this one, recorded and not explained. It is not
evidence about the formula, which is decided.

## What this leaves open

The default β = 0.5 sits at the top of the fall on both problems with
CRN. Whether these figures bear on the default, the published
"(0.2, 0.4)" guidance, or the README's examples is a decision, not
something this sweep settles: it covers one solver, two problems, one
budget and 100 runs.
