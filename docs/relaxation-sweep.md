# Which relaxation arithmetic produced the preprint's beta study

Phase 7, after step 7 (2026-10-19). A follow-up to
`docs/algorithm-audit.md` finding 2. Regenerate with
`python docs/bench_beta_sweep.py 100 6 1` (with CRN) and
`python docs/bench_beta_sweep.py 100 6 0` (without); each took about
100 minutes with six workers on this machine.
`tests/test_benchmark_scripts.py` checks only that it runs.

## The question

The shipped relaxation is `se / m**beta`; the preprint's (Optimization
Online 2018/06/6649, version of 2019-06-20, §3.2) is
se · m^(1/2 - β). They differ by exactly 1/2 in β at every sample size:
**preprint β = shipped β + 1/2.** §9.3 reports R-PE's coverage error on
Problems T_A and T_C as β_ε varies (Figures 10 and 12, left panels;
1,000 runs, t = 0.4 × 10^6, CRN across β), with a "sweet spot" for β_ε
in (0.2, 0.4) on T_A. If the experiments ran the shipped arithmetic,
the published axis is shipped β; if the preprint's, it is shipped
β + 1/2. Sweeping the shipped code over both ranges and comparing with
the figures says which.

## Method

R-PE, `testsolve` with random x0 from the testers, 100 runs per β,
budget 0.4 × 10^6, shipped β from -0.4 to 1.0 in steps of 0.1 (preprint
β 0.1 to 1.5, the published axis). One seed for every β, so each run
has the same x0 and, since streams are coordinate-derived, the same
random numbers at each (point, iteration) under every β. The metric is
the tester's: the Hausdorff distance from the true images of the run's
final solution to the true efficient set (T_A), or the least such
distance over the local efficient sets (T_C), as in the figures'
y-axes. Measured on Python 3.14 only.

## Without CRN the experiment is not reproduced

The first sweep ran with PyMOSO's default, no CRN. On T_A every median
was 3.7 to 4.3, about five times the published level, and nearly flat
in β; on T_C the error rose only at shipped β ≤ -0.2. The preprint's
listings run "with CRN" (audit finding 16). With CRN the level matches
the figures, so the comparison below uses CRN. The non-CRN table is
at the end; it is a result in its own right (without CRN, R-PE on T_A
at this budget is insensitive to β_ε and much worse), not a reading of
the preprint.

## With CRN (100 runs per β)

```
Problem TA: dH at the end of the run, quantiles over 100 runs
  shipped beta  preprint beta    q0.25    median    q0.75    q0.90
          -0.4            0.1    1.315     1.637    1.930    2.134
          -0.3            0.2    1.315     1.637    1.930    2.134
          -0.2            0.3    1.315     1.637    1.867    2.134
          -0.1            0.4    1.326     1.672    1.867    2.134
           0.0            0.5    1.242     1.503    1.720    1.854
           0.1            0.6    0.841     0.988    1.117    1.282
           0.2            0.7    0.521     0.626    0.768    1.051
           0.3            0.8    0.390     0.442    0.628    0.841   <- least median
           0.4            0.9    0.354     0.442    0.663    0.852
           0.5            1.0    0.371     0.518    0.679    0.951
           0.6            1.1    0.390     0.442    0.841    1.057
           0.7            1.2    0.390     0.526    0.841    1.105
           0.8            1.3    0.362     0.442    0.761    1.051
           0.9            1.4    0.362     0.548    0.761    1.057
           1.0            1.5    0.371     0.552    0.841    1.309
Problem TC: dH at the end of the run, quantiles over 100 runs
  shipped beta  preprint beta    q0.25    median    q0.75    q0.90
          -0.4            0.1    2.158     3.319    4.130    4.419
          -0.3            0.2    1.817     2.714    3.683    4.130
          -0.2            0.3    1.727     1.817    2.258    3.104
          -0.1            0.4    1.508     1.780    1.817    1.817
           0.0            0.5    0.646     1.043    1.817    1.817
           0.1            0.6    0.488     0.646    0.646    0.646   <- least median
           0.2            0.7    0.646     0.646    0.646    0.646
           0.3            0.8    0.488     0.646    0.646    0.646
           0.4            0.9    0.646     0.646    0.646    0.646
           0.5            1.0    0.646     0.646    0.646    0.646
           0.6            1.1    0.646     0.646    0.646    0.646
           0.7            1.2    0.646     0.646    0.646    0.646
           0.8            1.3    0.646     0.646    0.646    0.646
           0.9            1.4    0.606     0.646    0.646    0.646
           1.0            1.5    0.606     0.646    0.646    0.646
```

## The published figures, read by eye

Estimates, read from the rendered preprint pages (Figures 10 and 12,
left panels), so good to about 0.1:

| β on the published axis | T_A q0.25 / median / q0.75 | T_C q0.25 / median / q0.75 |
|---|---|---|
| 0.1 | 1.0 / 1.15 / 1.35 | 1.0 / 1.05 / 2.3 |
| 0.2-0.4 | 0.55 / 0.7 / 0.9 (the minimum) | 0.55-0.65 / 0.65 / 0.65-0.75 |
| 1.0 | 0.8 / 1.25 / 2.0 | 0.65 / 0.65 / 0.8 |
| 1.5 | 1.0 / 1.6 / 2.55 | 0.65 / 0.65 / 1.1 |

## The comparison

**Read as shipped β (the old arithmetic), the left side and the
minimum match:**
- T_A: our median is 0.99 at 0.1, 0.63 at 0.2, and least at 0.3-0.4
  (0.44); the published curve falls from about 1.15 at 0.1 to its
  minimum in (0.2, 0.4).
- T_C: the published plateau, 0.65, is the value our runs settle on
  (0.646), from shipped 0.1 up. The published left edge (median about
  1.05, q0.75 about 2.3 at 0.1) resembles our shipped 0.0 (1.04, 1.82),
  one grid step to the left.

**Read as preprint β, nothing matches:**
- T_A: the published sweet spot, preprint 0.2-0.4, is shipped -0.3 to
  -0.1, where our medians are 1.64-1.67, on a flat plateau, more than
  twice the published minimum. Our minimum would sit at preprint
  0.8-0.9, where the published curve is already rising.
- T_C: preprint 0.1-0.3 is shipped -0.4 to -0.2, medians 3.3, 2.7 and
  1.8 against the published 1.05, 0.65 and 0.65.

**Not matched under either reading: T_A's right side.** The published
median rises steadily above 0.4, to about 1.25 at 1.0 and 1.6 at 1.5;
ours stays at 0.44-0.55 up to shipped 1.0 (preprint 1.5). The same is
true of T_C's upper quartile, which rises in the figure and stays at
0.646 in ours. This is a difference between our runs and the
published ones that neither arithmetic explains. Unknown: candidates
are differences between the 2018 code and today's that are not
supposed to change behaviour, the 1,000 runs against 100, and how the
figures define Â(t); none was tested.

**Conclusion (measured, with the right-side caveat):** the published
β study is consistent with the shipped arithmetic, se / m^β, and
inconsistent with the preprint's formula. If so, the published β
values, including the defaults and the (0.2, 0.4) sweet spot, are in
the code's parameterization, and the preprint's §3.2 formula misstates
what was run. That is consistent with the history: the formula has
been `se/pow(m, beta)` with se = σ̂/√m since the first commit
(`a024c09`, 2018-05-08), which already held experiment and plotting
code.

## Without CRN (100 runs per β)

The "preprint beta" column of this run's log was printed with the
wrong sign (shipped - 1/2); corrected here, the data are unaffected.

```
Problem TA: dH at the end of the run, quantiles over 100 runs
  shipped beta  preprint beta    q0.25    median    q0.75    q0.90
          -0.4            0.1    3.582     4.184    4.787    5.174
          -0.3            0.2    3.639     4.189    4.871    5.480
          -0.2            0.3    3.560     4.184    4.862    5.413
          -0.1            0.4    3.525     4.173    4.838    5.293
           0.0            0.5    3.489     3.937    4.747    5.530
           0.1            0.6    3.230     3.941    4.695    5.404
           0.2            0.7    3.070     3.738    4.629    5.175   <- least median
           0.3            0.8    3.531     4.093    4.652    5.185
           0.4            0.9    3.635     4.286    4.747    5.381
           0.5            1.0    3.420     3.953    4.544    5.044
           0.6            1.1    3.523     4.046    4.544    5.241
           0.7            1.2    3.285     3.922    4.438    5.404
           0.8            1.3    3.361     4.046    4.699    5.517
           0.9            1.4    3.565     4.070    4.543    5.241
           1.0            1.5    3.585     4.036    4.569    5.120
Problem TC: dH at the end of the run, quantiles over 100 runs
  shipped beta  preprint beta    q0.25    median    q0.75    q0.90
          -0.4            0.1    3.384     3.585    4.419    5.663
          -0.3            0.2    3.319     3.683    4.419    5.663
          -0.2            0.3    2.083     2.276    3.046    3.683
          -0.1            0.4    1.780     1.877    2.279    2.995
           0.0            0.5    1.780     1.817    2.180    2.684
           0.1            0.6    1.482     1.780    1.917    2.684
           0.2            0.7    1.482     1.780    1.878    2.684
           0.3            0.8    1.474     1.780    2.151    2.684
           0.4            0.9    1.474     1.780    2.026    2.684
           0.5            1.0    1.500     1.780    2.125    2.684
           0.6            1.1    1.516     1.780    2.110    2.684
           0.7            1.2    1.482     1.780    2.281    3.396
           0.8            1.3    1.509     1.780    2.180    2.684
           0.9            1.4    1.600     1.780    2.009    2.684
           1.0            1.5    1.473     1.742    1.953    2.684   <- least median
```
