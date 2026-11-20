# Reconstructing the published R-PERLE experiments: a specification

What someone needs to reconstruct the dissertation's and papers'
R-PERLE experiments with PyMOSO 2.0, collected 2026-11-19. Each fact
says how it is known. **Measured** means computed from data or from
runs. **Read** means read from the 2018 experiment code (an archive
kept outside this repository and never executed). **Inferred** means
neither. Where this document points to the R-PERLE 4e6 run directory,
that is `/srv/projects/pymoso-runs/rperle-4e6/` on the maintainer's
machine, outside the repository.

The T_C reference sets and their provenance are in
[`docs/reference/`](reference/README.md) and
[`docs/reference/tpc-reference-sets.md`](reference/tpc-reference-sets.md),
and are not repeated here.

## 1. The seed pools

The 2018 driver reads two files, `orcseeds.pkl` and `solseeds.pkl`,
from `../prnseeds/`. They are in the 2018 archive, not in this
repository:

| file | SHA-256 |
|---|---|
| `orcseeds.pkl` | `c2237435b7835eda7ff8256694c2b4a9628d2bdb477913f8fc59423459552c14` |
| `solseeds.pkl` | `a3c1ff18ea425b87d6b1d49733a17818632679f6324f845250f4c154a2c54f0e` |

They name no globals (checked with `pickletools`). Load them with an
unpickler that refuses any; see the warning in
[`docs/reference/README.md`](reference/README.md).

**Measured** (`analysis/step8/seedpools.py` in the run directory; the
MRG32k3a recurrence matrices are written there from L'Ecuyer's
definition, not taken from either code base):
- Each file is a dict keyed 0 to 4,999, with 6-tuples of integers as
  values.
- All 10,000 are valid MRG32k3a states. All are distinct, and the two
  files share none.
- Consecutive seeds in both files are one fixed jump apart, the same
  jump in both: A^(2^77), where A is the one-step matrix with each
  component's triple stored oldest first, (x_{n-3}, x_{n-2}, x_{n-1}).
  Newest first, no A^(2^k) for k from 60 to 130 fits.
- `orcseeds[4999]` advanced one more jump is `solseeds[0]`. So the two
  files are one chain of 10,000 seeds: the oracle block first, the
  solver block second.
- **Inferred:** 2^77 is two of L'Ecuyer's substream spacings (2^76) and
  neither of his canonical constants (2^76 substream, 2^127 stream).
  That is consistent with the jump defect the author recalls. It is
  harmless: about 1.5 × 10^23 draws between consecutive seeds, against
  far fewer used by one run.

## 2. The driver's semantics (read, `mpmain.py`)

- **Seeds per run.** With `indepseeds=False`, run j of every scenario
  gets `orcseeds[j]` and `solseeds[j]`. So the multi-algorithm figures
  are a paired comparison, with common random numbers across
  algorithms. With `indepseeds=True`, runs take seeds from a running
  counter, `indepctr`, which advances on every run in either branch.
- **Starting points.** One `MRG32k3a((12345,)*6)` is created fresh at
  the start of each scenario and shared by that scenario's runs. Each
  run draws `xprn.sample(range(start, end), 1)[0]` per dimension, with
  the range from the deterministic oracle's `get_feasspace()`: −10 to
  10 for T_C. The 2018 generator class defines `random()` but not
  `getrandbits`, so integers come from Python's `random()`-based path.
  2.0's class defines `getrandbits`, so the same seed gives different
  starting points.
- **Grid.** `inc = 10000`: the curves are sampled at every 10,000 of
  the budget counter.
- **Which iteration a grid point shows.** For a budget point nc,
  `gen_hddata` takes the first iteration whose recorded count exceeds
  nc (or the last iteration), not the last at or below it. Its loop
  reads `simcalls[nu1]` and then sets `nu1` to the next index. Traced
  by hand on simcalls = [0, 100, 250, 400] with nc = 300, it selects
  iteration 3. Read, not run. **Its direction:** each grid point
  reports the solution of a later iteration than its budget paid for,
  so the published curves are optimistic and the true ones are slower
  still. It widens the timing gap of `docs/algorithm-audit.md`,
  finding 2c, rather than closing it.
- **Quantiles.** `floor(num_exp * q)` indexes the sorted values, for q
  = 0.05, 0.25, 0.5, 0.75 and 0.95. The figures plot 0.25, 0.5 and 0.75.
- **Metric.** The minimum over `tc.soln` of `dh(ehat, solnset)`, with
  `ehat` the returned points imaged by the deterministic oracle's `g`.
  In 2018 `soln` held image sets. 2.0's testers hold points and image
  them with `true_g` when the tester is made.

**Rewrite the analysis, do not port it.** The 2018 analysis path has
three defects, each read:
- `gen_hddata` reports a later iteration than the grid point paid for
  (above).
- `gen_qdata` stores `hausdict[ncalls] = hlst1.sort()`, which is
  `None`, so the output's `hauslst` holds nothing. The plotted
  quantiles do not use it.
- The budget is charged on cache hits (section 4).

A reconstruction computes its curves afresh from each run's
per-iteration solutions and simulation counts, with the iteration at or
below each grid point. It does not carry the 2018 functions over.

## 3. Configuration equivalences

| setting | 2018 code | PyMOSO 2.0 | how known |
|---|---|---|---|
| relaxation, PE and RLE | `se/pow(m, beta)`, `se` = σ̂/√m | `se * m**(0.5 - beta)` | read (`rperle.py` `fse`, `calc_delta`; `simbase.py` `hit`) |
| β | 0.5 (the dissertation's stated default) | 1.0 for both `betaeps` and `betadel` gives the 2018 relaxation | read; `docs/algorithm-audit.md`, finding 2 |
| m_ν | ⌈2 × 1.1^ν⌉ | ⌈2 × 1.1^ν⌉ | read |
| b_ν | ⌈8 × (d − 1) × 1.2^ν⌉ | the same (`max(d − 1, 1)`, equal for d ≥ 2) | read; the papers state ⌈8 × 1.2^ν⌉ (finding 9) |
| T_C draws per replication | 5 normals (`z1`-`z5`; `z4`, `z5` discarded) | 3 normals | read |
| normals | one uniform each, inverse CDF (`bsm`) | the same | read |
| CRN realization | the stream rewound to the iteration's base before every `hit` | coordinate addressing per (iteration, replication) | read; same concept, different variates |
| non-dominated filter | `get_biparetos`, keeps one of exactly tied points | `get_nondom`, keeps all | read; finding 8 |
| T_C feasible range | −10 to 10 per coordinate, x/2 | the same | read; `docs/reference/tpc-reference-sets.md` |

## 4. Budget accounting

**Read.** The 2018 `RPERLE.estimate` charges m on every estimate of a
feasible point, cache hits included. 2.0 charges only when it
simulates. So the published x-axis counts estimate calls × m, not
simulations. This applies to the R-PERLE family only (R-PERLE, R-PE,
R-MinRLE and their 2018 variants). MO-COMPASS's `update_gbar` charges
only the replications it runs.

**Measured, under 2.0's call pattern.** R-PERLE on T_C, budget 4e6,
CRN, β = 1.0, 100 paths. The ratio of the 2018 rule's count to
simulations was:
- at each path's end, a median of 5.34 and a range of 4.40 to 6.51;
- cumulatively, a median drifting from 4.9 at 10^5 simulations to 5.4
  at 4e6.

**The true 2018 ratio is not measured.** That would need the 2018 call
pattern, which means running the archive, and it is never run. The
detail is in `docs/algorithm-audit.md`, finding 2b.

## 5. What cannot be matched, and why

- **No run-for-run pairing.** The oracle streams differ (2018: the seed
  pools above with rewind-per-hit CRN; 2.0: coordinate streams). The
  draws per replication differ. The starting points come from different
  integer mappings. All comparison is distributional.
- **Which configuration produced each published figure.** `mpmain.py`
  was hand-edited between experiments: functions commented in and out,
  numbers changed. Its state now is not evidence of any one run's
  `num_exp`, budget, algorithms or parameters. Configure from the
  papers' stated values.
- **Six T_C reference images.** They do not reproduce bit for bit under
  any expression tried. The standing hypothesis is a different C
  library on the original hardware, which no longer exists
  (`docs/reference/tpc-reference-sets.md`).

## 6. The targets: Figure 9 (`TPC_cq.pdf`), read from its drawing commands

**Measured** (`analysis/tpc-stall/figure_tpc.py` and `reproduce.py` in
the run directory):
- The axes are linear. t runs 0 to 4 × 10^6 across x = 90.222 to
  759.822 pt. dH runs 0 to 7 across y = 74.476 to 462.556 pt, so 55.44 pt
  per unit; the scales come from the gridlines and tick labels.
- There are nine quantile curves, three per dash pattern: dotted
  (MO-COMPASS), dashed `[9.25 4]` (R-MinRLE) and solid (R-PERLE). One
  further 3-vertex dotted fragment at the top edge is not a curve.
- **The plateau value 0.43038** is (98.335981 − 74.475691) / 55.44, the y
  of the final vertices of R-PERLE's median and 0.75 curves. It equals
  the metric of one state: the complete global image set plus one point
  off the front, (−3, −3, −2) or its mirror.

R-PERLE's curves, each vertex as (t in units of 10^6, dH); t is
rounded to 0.01, and the paths run past the frame's right edge to
4.158:

- **0.25:** (0.01, 1.10082), (0.05, 1.10082), (0.06, 0.77913), (0.07,
  0.64559), (0.35, 0.64559), (0.36, 0.4877), (0.38, 0.4877), (0.39,
  0.43038), (0.46, 0.43038), (0.47, 0), (4.158, 0)
- **0.5:** (0.01, 1.81705), (0.02, 1.81705), (0.03, 1.77983), (0.04,
  1.69655), (0.05, 1.10082), (0.07, 1.10082), (0.08, 0.77913), (0.09,
  0.64559), (0.49, 0.64559), (0.5, 0.43038), (4.158, 0.43038)
- **0.75:** (0.01, 2.68379), (0.02, 2.2576), (0.03, 2.2576), (0.04,
  1.97912), (0.05, 1.77983), (0.06, 1.10082), (0.2, 1.10082), (0.21,
  0.77913), (0.39, 0.77913), (0.4, 0.64559), (0.41, 0.68813), (0.42,
  0.64559), (0.54, 0.64559), (0.55, 0.67495), (0.56, 0.77913), (0.57,
  0.64559), (0.89, 0.64559), (0.9, 0.43038), (4.158, 0.43038)

At 1, 2, 3 and 4 × 10^6:
- R-PERLE: 0 / 0.43038 / 0.43038 at every one.
- R-MinRLE: 0 / 0.4304 / 0.4304 at 1e6 and 4e6, and 0 / 0.3921 / 0.4304 at
  2e6 and 3e6.
- MO-COMPASS: 2.209 / 4.024 / 6.170 at 1e6, falling to 1.904 / 3.865 /
  5.894 at 4e6.

## 7. What is still unexplained

On T_C, how often runs end in the 0.43038 state: 27 of 100 in 2.0 at
β = 1.0, against at least half in the published figure. Five candidate
causes are listed in `docs/algorithm-audit.md`, finding 2c, and none
was ablated, by decision.
