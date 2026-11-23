# Algorithmic completeness audit: R-SPLINE, R-PERLE, R-PE, R-MinRLE

Phase 7, step 7 (`docs/phase7-plan.md`). The algorithms as published,
read against the code on `dev-2.0`, for steps, safeguards, tolerances
and orderings present in one and not the other, in both directions.
**This is a list to work through, not a set of fixes.** Nothing here
has been changed. MOCOMPASS and MOPBnB are out of scope
(`docs/example-solvers.md`).

## What was read

- **R-SPLINE:** Wang, Pasupathy and Schmeiser, ACM TOMACS 23(3),
  Article 17, July 2013 (the published paper,
  `/srv/projects/papers/2013wanpassch.pdf`). Algorithms 1-4 and the
  NE paragraph of §3.2, §5 (asymptotics) and §6 (implementation).
- **R-PERLE, R-PE and R-MinRLE:** Cooper, Hunter and Nagaraj, the
  Optimization Online preprint (2018/06/6649), the version of
  2019-06-20, updated after refereeing. The algorithms did not change
  in review (the maintainer, 2026-10-19). Algorithms 1-6,
  Definitions 1-8, §8.1's assumptions and §9.1's parameters. The
  dissertation's chapter 3 (`/srv/pu_diss/tex/ch3.tex`) was used only
  to read the LaTeX of a formula, and agrees where checked.
- **The MATLAB R-SPLINE:** `docs/RSPLINE.m` (Nagaraj, November 2014),
  as a second reference for R-SPLINE only.
- **The code:** `pymoso/chnbase.py` (`RASolver`, `RLESolver`),
  `pymoso/moso.py`, and `pymoso/solvers/` (`rspline.py`, `rperle.py`,
  `rpe.py`, `rminrle.py`), at commit `2166375`.

**Read or inferred.** Every entry says which. "Read" means the
listing or text was compared line by line with the code. "Measured"
means a check ran; those are `docs/audit_checks.py`, which runs
R-PERLE's `pe` copied verbatim with counters beside the shipped solver
and requires identical results (15 runs: ProbTPA, ProbTPB and ProbTPC
at budget 3,000, seeds 1-5, no CRN). "Inferred" means reasoned from
code and not run.

**Classes,** as the brief defines them: a **defect** (wrong against
the algorithm as published); a **deliberate divergence** (a stated
reason, and whether it is recorded); an **omission in the paper** (a
condition the results need that the paper does not state); **unknown**
(the paper is silent or ambiguous, or I cannot tell which side is
intended).

## Summary

| # | Finding | Algorithms | Class | Evidence |
|---|---|---|---|---|
| 1 | PE's traceback reads the epsilon intervals of the wrong objective | R-PERLE, R-PE | defect; fixed | measured |
| 2 | The relaxation is se / m^β; the preprint's is se · m^(1/2 - β) | R-PERLE, R-PE, R-MinRLE | defect (decided), inherited from the 2018 code; fixed | read; the 2018 code read |
| 2b | The published x-axis counts estimate calls × m, not simulations | R-PERLE, R-PE, R-MinRLE (not MO-COMPASS) | published axis mislabelled; PyMOSO counts simulations since 2018 | read; scale illustrated, not measured for the published runs |
| 2c | T_C's published quantile figure, against the code | R-PERLE | plateau and upper quartile explained; overshoot frequency not | measured, 100 runs |
| 3 | PE's LWEP filter is applied to the wrong set and then undone | R-PERLE, R-PE | defect; fixed | measured |
| 4 | SPLI's line search floors instead of rounding to nearest | all four | defect; fixed | read; occurrences counted |
| 5 | SPLI does not stop at an infeasible line-search point | all four | defect; fixed | read |
| 6 | Under an epsilon constraint, PLI's gradient uses vertices that violate it | R-PERLE, R-PE | unknown | read |
| 7 | PE breaks ties between objectives deterministically, not randomly | R-PERLE, R-PE | defect; fixed | measured |
| 8 | `get_biparetos` drops exactly tied points | R-PERLE, R-PE | defect; fixed | measured |
| 9 | The search limit has a factor (dim - 1) and is 0 in one dimension | all four | defect at d = 1, fixed; above d = 2 a design decision, reason recorded | read; the effect measured on one golden |
| 10 | R-PERLE and R-PE run on three or more objectives without a word | R-PERLE, R-PE | the `sys.exit()` fixed; the objective count left to the user, by decision | measured |
| 11 | Min adds SPLINE's trajectories to its output | R-PERLE, R-PE, R-MinRLE | unknown | read |
| 12 | R-MinRLE may start a minimizer's search from x0 | R-MinRLE | unknown | read |
| 13 | PE's traceback step when the standard error is 0 is an absolute 1e-6 | R-PERLE, R-PE | implementation necessity, with a hazard | read; the float limit computed |
| 14 | SPLINE stops at `n >= b`, not `n > b` | all four | defect (minor); fixed | read; occurrences counted |
| 15 | SPLI charges a full simplex whatever it cost | all four | unknown | read |
| 16 | The listings say "with CRN"; PyMOSO defaults to no CRN | all four | deliberate, recorded | read |
| 17 | The MATLAB's tolerances and caps are in neither the paper nor PyMOSO | R-SPLINE | unknown | read |

Then the entries the plan had already collected, each rechecked
("The accumulated entries", below), and what PyMOSO does that the
papers do not describe ("In the other direction").

**Nothing here looks urgent enough to stop for.** None of it breaks a
run. Finding 1 is the one I would put first. It is in every R-PERLE
and R-PE run since at least October 2018 (it is in 1.1.0), and a fix
moves R-PERLE's and R-PE's goldens. Finding 2 is a question only the
authors can answer, and the answer decides whether the defaults mean
what the paper says they mean.

## The findings

### 1. PE's traceback reads the epsilon intervals of the wrong objective

**Defect. Measured.** PE Step 18 sets the traceback's lower bound from
the upper ends of the intervals on the constrained objective K^con:
ε^L_j = max(L_K*, max{ε^U_K*(i) : ε^U_K*(i) < ε_j}). In `pe`
(`rperle.py:83-112`), `mcJ` is rebuilt on each pass of `for k in
krange`, so after the loop it holds the intervals of the *last* `k`
(objective index 1, constraining objective index 0). Step 18's
`hi_blist` (`rperle.py:122`, `rpe.py:123`) reads that `mcJ` whatever
`k_opt` turned out to be. When `k_opt` is 0, which is also how a tie
resolves (finding 7), the bound comes from the other objective's
values.

Measured on the 15 runs: 181 of 211 tracebacks read the other
objective's intervals. In 63 of them the lower bound changed: 34
higher than its own, so the traceback stopped sooner, and 29 lower,
so it ran longer. The bound can never fall below L_K*, so the search
cannot run out of starting points; the effect is on which and how
many epsilon problems are solved.

R-PERLE's convergence rests on RLE, which certifies whatever PE hands
it, so its guarantees should be untouched (inferred). R-PE's
convergence proof (Theorem 2) is about PE as listed, so the code is
not the algorithm that theorem covers (read; not assessed further).
The same lines are in `v1.1.0` and at `a914c3e` (2018-10-30).

**Fixed (2026-10-19), after the relaxation (finding 2).** `pe` keeps
each objective's intervals and the traceback reads `k_opt`'s
(`tests/test_pe_traceback.py`, seen failing first). The counts above
were taken with the old relaxation, which placed three times as many
epsilon values. Against the corrected relaxation, counted along the
fixed runs (`docs/audit_checks.py`): of 66 tracebacks in 308 PE calls
(the same 15 runs), the code before the fix would have read the other
objective's intervals in 61 and had a different lower bound in 15 (4
higher, 11 lower). At budget 30,000 (three seeds per problem): 13 of
79, in 387 PE calls.

### 2. The relaxation's scale: se / m^β against se · m^(1/2 - β)

**Defect, inherited from the 2018 experiment code; decided by the
authors (2026-10-19) and fixed: the preprint is the source of truth.**
The code now computes `se * m**(1/2 - beta)` (`tests/test_relaxation.py`).

The preprint defines f̂_k(x, β) := ŝe(Ḡ_k,n(x)) · n^(1/2 - β) with
ŝe = σ̂/√n (§3.2; the same in the dissertation, `ch3.tex:292-295`, and
in the introduction's statement of PE), so f̂ = σ̂ · n^(-β). That is
both PE's epsilon interval (β_ε) and RLE's completeness function
(β_δ). Until the fix, the code computed `se / m**beta` (`fse` in
`rperle.py`, `calc_delta` in `chnbase.py`), with `se` the standard error
σ̂/√m, so its relaxation was σ̂ · m^(-1/2 - β): smaller than the
preprint's by a factor of √m. **Under the old formula β = 1/2 was the
preprint's β = 1.** At the dissertation's stated defaults
(β_ε = β_δ = 1/2, "more than one standard error away"), the code
searched to a standard error divided by √m.

**Where it came from.** The code that produced the published figures
was read on 2026-11-19 (an archive of the 2018 experiment code, kept
outside this repository and never executed). Its `rperle.py` computes
both relaxations as `se/pow(m, beta)` (`fse` and `calc_delta`), and its
`Oracle.hit` returns `se` as `sqrt(variance)/sqrt(m)` (`simbase.py`).
So the defect was in the experiment code before this repository
existed. The first commit (`a914c3e`, 2018) inherited it; it was not
introduced when the package was assembled, as this finding's earlier
resolution said.

**What that means for the published results.** The dissertation's and
preprint's experiments ran with the old formula. Their stated β values
are values of the old convention: the published β = 1/2 is the
corrected code's β = 1. That is what `docs/relaxation-sweep.md`
measured (the published β study matched read as the old code's β), and
that reading stands. The sweep did not reproduce the figures'
right-hand rise. The 2018 code differs from the code it swept in more
than the relaxation (seen in the archive: its oracle for T_C draws five
normals a replication where this one draws three, and it filters
candidate sets with the tie-dropping `get_biparetos` of finding 8; it
was not compared further), so the rise is not attributed to anything
here.

Convergence holds for any β in (0, ∞) under either convention, so this
is about what the parameter means and about efficiency, not about
correctness. The authors' decision stands: the preprint's formula is
the intended one, and the corrected code is right. Reproducing a
published figure with the corrected code needs β raised by 1/2.

#### Why β = 1/2: the relaxation's rate (2026-11-19)

The default is a derivable value, not a best guess. The argument
rests on Pasupathy (2010), "On choosing parameters in
retrospective-approximation algorithms for stochastic root finding and
simulation optimization", *Operations Research* 58(4, Part 1 of 2):
889-901, doi:10.1287/opre.1090.0773. The maintainer checked the theorem,
section and page references below against the paper. The analogy
between δ and the paper's ε_k is an interpretation, and keeps its
caveat (below). The dissertation cites the same paper for the idea of
solving each sample-path problem only to a tolerance matched to the
estimation error (`ch3.tex:265`).

**The match.**
- The corrected relaxation at β = 1/2 is ŝe = σ̂/√m.
- That is the paper's §5.3 recommended error-tolerance sequence,
  ε_k = K/√m_k with K estimated from data (p. 897).
- The sample sizes m_ν = ⌈2 × 1.1^ν⌉ are its Table 1 linear growth,
  with the paper's own constant. Table 1 recommends linear growth alone
  when the inner procedure converges linearly (p. 897; Theorem 9, the
  same page).

**Pinned from both sides.**
- **Theorem 7 (p. 896), the lower side:** if ε_k² does not converge at least as
  fast as MSE(X*_k, x*), which goes as 1/m_k, then MSE(X_k)/MSE(X*_k)
  diverges. That needs m_k ε_k² bounded, which is β ≥ 1/2.
- **Theorem 8 (p. 896) and Figure 2 (p. 900), the upper side:** converging faster leaves
  the MSE rate unchanged, so β > 1/2 buys nothing and spends work.
- **So 1/2 is the one rate that is both sufficient and not wasteful.**

**The old formula in these terms.** se/m^β at β = 1/2 is ε_k ∝ 1/m_k.
That is Theorem 8's no-gain regime. It also breaks §5.2's own
recommendation that 0 < limsup ε_k √m_k < ∞ (p. 896), because there the
limsup is 0. The paper's introduction names the failure: wasted
computational effort from oversolving the sample-path problems (p. 890).

**Two caveats.**
- **δ is not literally ε.** δ is a relaxation inside a dominance test,
  not the distance between the retrospective and sample-path
  solutions. The match is of functional form and role, not an identity:
  an interpretation, not something the paper states.
- **The theory assumes independent sample paths.** The paper's §8(ii)
  (p. 900) notes that theory for correlated generation is "virtually
  nonexistent" for stochastic root-finding problems. This
  justification is therefore derived without CRN. It says nothing about
  the right rate under `--crn`.

### 2b. The published figures' x-axis counts estimate calls, not simulations

**Read, in the 2018 experiment code; PyMOSO has counted simulations
since 2018-10-30.** The 2018 code that produced the published figures
(the archive described in finding 2, read 2026-11-19, never executed)
charges the budget in `RPERLE.estimate`:

```python
        if x in self.gbar:
            ...                      # cached this iteration: no simulation
        else:
            isfeas, fx, vx = self.orc.hit(x, m)
            ...
        if isfeas:
            self.num_calls += m
```

The charge sits after the cache branch, so every estimate of a feasible
point costs m, whether or not it was simulated. R-PE and R-MinRLE are
subclasses there and charge the same way. MO-COMPASS does not: its
`update_gbar` charges the replications it actually runs. PyMOSO's first
commit had the 2018 rule. `a914c3e` (2018-10-30, "SPLINE bug, minor
restructuring") moved the charge into the branch that simulates, so
`num_calls` has counted simulations since.

**The finding: the axis label is wrong.** The published R-PERLE,
R-PE and R-MinRLE curves are labelled "total simulation effort, t".
They are plotted against estimate calls × m, which is at least the
number of simulations. So every cost on those axes is overstated, and
a figure comparing them with MO-COMPASS puts two counting conventions
on one axis. By how much, for the published runs, is not known.

**An illustration of scale, under this repository's implementation.**
Measured 2026-11-19 on R-PERLE, T_C, budget 4e6, CRN, betaeps = betadel
= 1.0 (the 2018 formula at the dissertation's β = 0.5, finding 2), 100
paths. The run had a second counter applying the 2018 rule to 2.0's own
estimate calls; the runs were identical to the uninstrumented ones.
**This applies 2018's charging rule to 2.0's call pattern. The 2018
code's own call pattern is not measured, because that code is not run.
Where the two differ (the findings fixed since, and the tie-dropping
`get_biparetos`), the 2018 ratio could be different. These numbers do
not measure how far the published figures overstate cost.**

| actual simulations | estimate calls × m / simulations, cumulative, median (q25-q75) | per iteration, median |
|---|---|---|
| 1e5 | 4.91 (4.76-5.10) | 5.10 |
| 5e5 | 5.19 (5.00-5.74) | 5.26 |
| 1e6 | 5.25 (5.05-5.91) | 5.16 |
| 2e6 | 5.32 (5.11-6.04) | 5.14 |
| 4e6 | 5.38 (5.09-6.17) | 5.15 |

At each path's last iteration it ranged from 4.40 to 6.51 (median
5.34). Under this implementation, a 2018-rule count of 4e6 is about
0.72e6 simulations (quartiles 0.66e6-0.77e6). The scripts and data
are in the R-PERLE 4e6 run directory, outside the repository
(`analysis/tpc-stall/stretch*.py`, `rperle_count.py`).

### 2c. Test Problem C's published quantile figure, against the code

The dissertation's Figure 9 (`TPC_cq.pdf`) shows R-PERLE's 0.25, 0.5
and 0.75 quantiles of the local weakly coverage error over 1,000 runs
on T_C. Its values were read from the PDF's drawing commands. At 4e6
they are 0 / 0.43038 / 0.43038, and the median and upper quartile sit at
0.43038 from about 0.5e6 and 0.9e6. The corrected code at its defaults
(100 runs) gives 0 / 0 / 0.6456.

**What the relaxation formula explains: the plateau's state and the
upper quartile's level.** 0.43038 is one specific state: the complete
global image set plus one spurious point, (-3,-3,-2) or its mirror.
The corrected code's plateau, 0.6456, is a different state: the global
set less (-2,-2,-2). RLE's relaxation lets it certify that set while
the relaxation exceeds the true gap to the nearest member. At the
objectives' population variances (computed, not sampled), that lasts
until m is about 13,600, beyond the plotted budget. The corrected code with β raised by 1/2,
which is the 2018 formula (finding 2), reaches the published state in
27 of 100 runs and holds the upper quartile at 0.43038 to 4e6.

**What the budget accounting explains: the upper quartile's timing,
approximately.** Re-plotted on the 2018 axis (finding 2b), the emulated
upper quartile settles at 0.43038 from 0.62e6, against the published
0.9e6, through the same sequence of values (1.101, 0.779, 0.646,
0.430). The accounting does not reconcile both quantiles:

- the lower quartile would need a factor of about 15.7 (0 reached at
  0.03e6 actual, against 0.47e6 published);
- the upper quartile would need about 7.5 (0.12e6 against 0.9e6);
- measured across 100 paths: 4.40 to 6.51, median 5.34.

No single factor reconciles both quantiles. Neither required value
falls inside the measured range: the upper quartile is close, and the
lower quartile is beyond it by more than a factor of two. The 2018
driver also reports each grid point with a later iteration's solution
than the point paid for (`docs/reconstruction-spec.md`, section 2).
That makes the published curves optimistic, and the true timing gap
wider than these factors.

**What is not accounted for: how often runs overshoot.** The published
median of 0.43038 means at least half of the 1,000 runs ended in the
spurious-point state or worse. The emulation has 27 of 100 there, and
62 at 0. If half were the true rate, 62 or more at 0 would occur about
1% of the time. Candidate causes, none established or claimed:

1. the oracle's draws: five normals a T_C replication in 2018, three
   here, so different variates under CRN;
2. the tie-dropping `get_biparetos` (finding 8);
3. the starting points: the same uniform distribution, but drawn by a
   different mapping and stream (2018's `sample` against 2.0's
   `choice`);
4. the CRN realization: 2018's rewind-per-hit scheme against 2.0's
   coordinate streams, and its oracle seeds from `orcseeds.pkl`;
5. the defects this audit found and fixed since, so far as the 2018
   code shares them (only finding 8 was confirmed in the archive; the
   others were not compared).

None was ablated, by decision. The run directory's
`analysis/tpc-stall/` holds the measurements: `figure_tpc.py`,
`reproduce.py`, `stretch_analysis.py` and their outputs.

### 3. PE's LWEP filter is applied to the wrong set, then undone

**Defect against the listing. Measured.** PE Step 2 removes the
non-LWEPs from Min's output: Â^w_n = RemoveNonLWEP(Â^0_n); Step 3
falls back to Â^0_n if none is left. The code applies
`remove_nlwep` to `aold` (the previous solution with x0), not to Min's
output, then takes `get_biparetos(mnumin | a0new) | mnumin`
(`rperle.py:68-72`). Measured: in all 293 PE calls the
epsilon-placement set equalled Min's output exactly. So the code
places epsilons from Min's output, LWEP or not, which the listing does
not, and the filter's only effect is its cost: 11,829 of PE's 44,853
counted simulations (26%). Some of those neighbour estimates are
reused later in the same iteration through the cache (by RLE in
R-PERLE), so the net waste is smaller; not measured. Step 3's
fallback has no counterpart, because the set can never be empty.

**Fixed (2026-10-24), as the listing:** `lweps = remove_nlwep(mnumin)`,
`a1new = lweps or mnumin`, and the traceback starts from Min's output
with SPLINE's trajectories (the listing's 𝒯 ∪ Â⁰), which the code
reached through `a1new` only while `a1new` was Min's output. The last
step, where the listing adds {x0}, is unchanged, by decision.
`tests/test_pe_lwep_filter.py`
(seen failing: the filter's set and the placement, 4 of 6; the
traceback start, 8 of 8 with only that line reverted). The case for
the fix is correctness, not cost: the filter still costs simulations,
now on a set that decides the placement. On the audit's 15 runs,
before and after (`docs/audit_checks.py`; different search paths, so
not a saving): 307 and 336 PE calls, 45,300 and 46,291 simulations in
PE, 12,259 in the filter on the previous solution and 4,069 on Min's
output. The placement set is a strict subset of Min's output in 45 of
336 calls, and the fallback fires once. Quality is unmeasured; the
re-sweep covers it.

### 4. SPLI's line search floors instead of rounding to nearest

**Defect. Read.** Algorithm 4 Step 12: "Shift x1 to its nearest
integer solution" (and §6(iii): "the nearest single integer solution
for the line searches"). The MATLAB does that, `floor(x0(k) -
s*gamma(k) + 0.5)` (`RSPLINE.m:397`). The code floors without the
half (`chnbase.py:778`), so every line-search point is biased by up to
one unit towards negative infinity in each coordinate. SPLI is a
heuristic as far as convergence goes (§4.2's R-SPLINE(0) remark), so
this changes finite-time behaviour only.

**Fixed (2026-10-24):** `floor(x + 0.5)`, the MATLAB's rule; Python's
`round()` would take halves to even. `tests/test_spli_nearest.py`
(seen failing, 3 of 3; with `round()` in place of the fix the half case
fails). Floor and nearest differed at 675 of 886 line-search points on
the audit's runs and five ProbSimpleSO runs, counted before findings 9,
14, 3 and 5 were fixed. Every golden R-PERLE, R-PE and
R-MinRLE case moved; R-SPLINE's, one-dimensional, did not, because a
step there is a whole number. `rperle_tpa_crn`'s solution moved with
its end seed unchanged (`tests/golden/README.md`).
`tests/test_warm_start.py`'s R-SPLINE whole run no longer met a
refused warm start from (8, 20) and starts from (8, 15). Quality is
unmeasured; the re-sweep covers it.

### 5. SPLI does not stop at an infeasible line-search point

**Defect against the listing. Read.** Algorithm 4 Step 13: "if x1 is
infeasible return". In the code an infeasible point ends the line
search (`chnbase.py:786`), and then SPLI returns only if the line
search was short (`i <= 2`, `chnbase.py:789`). From the third step on
it starts a new gradient instead. Under an epsilon constraint,
"infeasible" includes violating it. Again finite-time behaviour only.

**Fixed (2026-10-24):** the line search returns at an infeasible point,
as step 13 does. The point is still simulated to find it infeasible and
still not charged to n, as before. `tests/test_spli_infeasible.py`
(seen failing: the third-step case took a second gradient and visited
one more point). Of the goldens, the solutions of `rperle_tpa`,
`rpe_tpa`, `rperle_tpa_crn` and one path each of `testsolve_tpa` and
the `testsolve()` library case changed; no end seed did
(`tests/golden/README.md`). Quality is unmeasured; the re-sweep covers
it.

### 6. Under an epsilon constraint, PLI's gradient uses vertices that violate it

**Unknown. Read.** The preprint's SPLINE searches X̃, the set the
bound constraints G define, and refers to Wang et al. for SPLI and
PLI. There a vertex counts towards the gradient only "if x_i is
feasible", which on X̃ would mean satisfying the constraint, so a
violating vertex leaves the gradient undefined and SPLI stops. In
`pli` a vertex the oracle finds feasible counts towards `n`, `t`,
`gbat` and the gradient even when it violates the constraint; it is
only excluded from being the best vertex (`chnbase.py:684-699`). The
code's reading keeps a usable direction near the constraint, and is
defensible. Which was meant, the listing does not settle.

### 7. PE breaks ties between objectives deterministically

**Defect against the listing (minor). Measured.** PE Step 13 chooses
the objective with fewer epsilon values and "break[s] ties randomly".
`min(ck, key=...)` (`rperle.py:113`) always takes objective index 0.
Measured: the counts tied in 209 of 293 PE calls, so the code mostly
minimizes the first objective and constrains the second. Not assessed
for its effect on convergence; I would expect none (inferred).

**Fixed (2026-10-19), after findings 2 and 1.** A tie is broken by one
draw from the solver's stream (`sprn.random()`, the stream SPLI's
perturbations use), taken only when the counts tie, so a run with no
tie draws exactly what it did. A tie shifts every later draw on that
stream. `tests/test_pe_traceback.py`, seen failing first. With the
corrected relaxation the counts tie in 161 of 305 PE calls (the same
15 runs; `docs/audit_checks.py`).

### 8. `get_biparetos` drops exactly tied points

**Defect (small). Measured.** PE's last step (Step 26) and Min's
remove dominated points. Under Definition 1 two equal vectors do not
dominate each other, so both stay. `get_nondom` keeps both;
`get_biparetos`, which `pe` uses (`rperle.py:72` and `150`), keeps
only one of a set of exactly equal vectors. For R-PE that is the
returned set. Exact ties need discrete outputs or symmetry under CRN
(the step 6b mirror ties are an example).

**Fixed (2026-10-21), in `get_biparetos` itself,** so any caller gets
the corrected set: a point whose values equal the current
non-dominated point's is kept. Measured before the fix, on the audit's
15 runs: no call of the 610 in `pe` met a tie, so no golden was
expected to move. Without a tie the set is built exactly as before,
element and order (`tests/test_chnutils_nondom.py` keeps the old
function verbatim as the reference; that check was seen failing on a
correct set built in another order). The tie tests were seen failing
first.

### 9. The search limit: (dim - 1), and zero in one dimension

**Defect at d = 1; unknown at d > 2. Read.** The preprint sets
b_ν = ⌈8 × 1.2^ν⌉ (§9.1). The R-SPLINE paper gives no formula, but
requires "the positive-valued sequence {b_k} → ∞" (§3.2). The code's
`calc_b` is ⌈bconst × (dim - 1) × 1.2^ν⌉ (`chnbase.py:1004-1006`):
the papers' value at d = 2, larger above it, and **0 at d = 1**. At 0,
SPLINE stops after one SPLI and one NE in every iteration, and RLE's
and SPLI's limits are 0 too. The factor has been there since the
first commit (`a024c09`, 2018-05-08, as `8*(self.dim - 1)`); no reason
is recorded anywhere I found.

**Fixed at d = 1 (2026-10-24); d > 2 left open, by decision.** `calc_b`
uses max(dim - 1, 1), so b is the papers' value at d = 1 and d = 2.
`tests/test_search_limit.py` (seen failing: 11 calc_b cases at d = 1,
and no line-search step in a 1-D run). The golden `rspline_simpleso`,
`--budget=1000`: 29 iterations and 1,023 simulation calls with b = 0,
25 and 1,076 with b = 10, 12, 14, 17, ...; the solution `{(0,)}` both
times. Quality is unmeasured; the re-sweep covers it.

**Above d = 2: a design decision, with its reason recorded
(2026-11-19).** The dissertation states b_ν = ⌈8 × 1.2^ν⌉ for all
ν ≥ 1, with no dimension, for experiments that include T_C (d = 3).
The code, both PyMOSO's and the 2018 experiment code that produced the
published results (finding 2), uses ⌈8 × (d - 1) × 1.2^ν⌉, which is
⌈16 × 1.2^ν⌉ on T_C. The paper states 8; the code uses 8 × (d - 1).

The reason, from the author (K. Cooper, 2026-11-19): "we needed the
higher limit for T_C because spline searches were stalling out too
early with the extra dimension but no additional line search budget.
So we quickly came up with the formula you see in the code."

What b_ν is: neither convergence nor its rate needs it. It is an
implementation device that stops the whole budget being spent on one
unlucky sample path, so scaling it changes finite-sample behaviour and
nothing asymptotic. Pasupathy (2010) (the paper of finding 2's β
rationale; references checked against it by the maintainer)
corroborates this:
- The paper states its convergence conditions, C.1-C.3 (p. 894), on the
  sample-size and error-tolerance sequences only, and nothing like b_ν
  appears in them.
- Its count of points visited per iteration, N_k, is O_p(1) under
  polynomial convergence (§5, equation (2), p. 895), so a cap on it
  binds early and not asymptotically.

So this is not an open divergence. A user matching the papers' search
limit on a problem with d > 2 variables sets `bconst` to 8 / (d - 1).
Unchanged.

### 10. R-PERLE and R-PE on three or more objectives

**Defect. Measured.** PE is defined for d = 2. The "not bi-objective"
block (`rperle.py:85-93`, `rpe.py:86-94`) is reached only through an
`IndexError`, which happens at d = 1. At d = 3 both solvers run to
the end, measured: `kcon = 1 - k % 2` maps the third objective onto
the second's role, and `get_biparetos` compares two objectives only.

**Fixed (2026-10-21), by removing the block, not by a check.** The
maintainer's decision: PyMOSO does not police which algorithm a user
runs on which problem. The defect was library code exiting the
process, not the absent check. The `IndexError`/`sys.exit()` block,
and with it R-PE's message naming R-PERLE, is gone; on one objective
the `IndexError` reaches the caller, and three objectives run as
before. `tests/test_objective_count.py`, the one-objective case seen
failing first.

### 11. Min adds SPLINE's trajectories to its output

**Unknown. Read.** Min Step 5 returns RemoveDominated(Âold ∪ M_n ∪
{x0}). `get_min` returns the non-dominated points of the minimizers,
the input, x0 *and every point the SPLINE searches visited*
(`chnbase.py:468-475`). Those points are already estimated, so it
costs nothing. It is either a deliberate cheap enrichment or drift.

### 12. R-MinRLE may start a minimizer's search from x0

**Unknown. Read.** R-MinRLE calls Min(Â_ν-1) (Algorithm 6, Step 3).
PE calls Min(Âold ∪ {x0}) (PE Step 1). Min's starting point for
objective k is the best of its input, so in the listings x0 is a
starting candidate in PE and not in R-MinRLE. `get_min` always takes
the best of `mcS | {x0}` (`chnbase.py:470`), so R-MinRLE gets PE's
behaviour. Both listings include x0 in Min's output (Step 5), so the
difference is only where the search starts. It is likely an artefact
of one `get_min` serving both (inferred).

### 13. PE's traceback step when the standard error is 0

**Implementation necessity, with a hazard. Read; the float limit
computed.** Step 24 moves the constraint to Ḡ(X^w) - f̂(X^w). If f̂ is
0 (a deterministic objective, or zero sample variance), ε does not
move, and the listing loops forever re-solving the same problem. The
code substitutes 1e-6 (`rperle.py:143-145`), which the paper does not
mention. The constant is absolute: from 2^35 (about 3.4e10) up,
subtracting 1e-6 leaves a float unchanged (computed), so a
deterministic constrained objective of that size loops forever
(inferred; not run).

### 14. SPLINE stops at `n >= b`

**Defect (minor). Read.** Both papers stop SPLINE when the calls
*exceed* the limit ("n > b_k", R-SPLINE Algorithm 2 Step 7; "b* > b",
the preprint's Algorithm 4 Step 8). The code stops at `bp >= b`
(`chnbase.py:523`). With b = 0 (finding 9) the two agree on stopping
after one pass anyway.

**Fixed (2026-10-24):** `bp > b`. The calls land exactly on b in 5 of
1,085 SPLINE calls (the audit's runs and five ProbSimpleSO runs,
counted before finding 9's fix). `tests/test_spline_stop.py` (seen
failing: the two cases that land on b). Of the goldens, `rminrle_tpa`
and two of `testsolve_tpa`'s four paths changed; R-PERLE's, R-PE's and
R-SPLINE's runs and the `testsolve()` library case did not
(`tests/golden/README.md`). Quality is unmeasured; the re-sweep covers
it.

### 15. SPLI charges a full simplex whatever it cost

**Unknown. Read.** Algorithm 4 adds (d + 1) m_k after PLI only when
the gradient is defined (Steps 6-7), when every vertex was feasible.
The MATLAB charges the feasible vertices only (`npoints*mk`). The code
charges `m*(q + 1)` every time (`chnbase.py:765`), including vertices
that were infeasible or already in the cache. That count only drives
the limit b; the budget (`num_calls`) is counted separately and
exactly. A sibling of `ne`'s charging (below).

### 16. "with CRN"

**Deliberate divergence, recorded. Read.** R-PERLE's and R-MinRLE's
listings say "for ν = 1, 2, ... with CRN"; R-SPLINE §6(ii) says CRN is
used and helps. PyMOSO defaults to no CRN, by decision (CLAUDE.md,
"CRN is a framework facility for algorithm testing, offered to expert
users who opt in"). R-SPLINE §6(ii) also says what convergence needs:
that ĝ(x) be well defined within an iteration, "the value cannot
depend on how SPLINE reaches x". The per-iteration cache (`gbar`)
provides that for feasible points without CRN. Step 6b measured what
CRN buys and costs (`docs/crn-failure.md`).

### 17. The MATLAB's tolerances and caps

**Unknown, for PyMOSO. Read.** The R-SPLINE paper has no tolerances
and no caps beyond b_k. The MATLAB adds:
- **0.00005, eleven places.** NE's three comparisons (lines 250, 266,
  298; decided, below), the quadratic convexity guard (281; ported, in
  `_quadratic_coordinate`), SPLI's update from PLI (371), the zero-
  gradient check (387), the line search's acceptance (414, 417),
  PLI's best vertex (505), the weight sum (522), and the revert guard
  (206).
- **Caps:** at most 6 gradient estimates per SPLI (`jmax=5`) and 101
  line-search steps (`imax=100`).
- **Two departures from the paper inside the MATLAB itself.** The
  quick-stop test counts from 0 (`i <= 2` on a 0-based index), so it
  also stops after three steps where the paper stops after two. The
  zero-gradient check, `glength + 0.00005 <= 0`, can never be true for
  a norm, so a zero gradient goes on to divide by zero.
- **The line search accepts slightly worse points:** `ix1fn >=
  xbestfn + 0.00005` stops it, so a point up to 0.00005 worse is
  accepted and the search continues.

PyMOSO follows the paper on all of these: exact comparisons, no caps
but b. The NE decision's reasoning (the constant stands in for a
relaxation PyMOSO has) is specific to NE. For SPLI's comparisons
within one sample path, a tolerance would only trade tiny improvements
for simulations; nobody has decided it.

## The accumulated entries, rechecked

- **`sys.exit()` in rperle.py and rpe.py: accurate, with lines moved
  and two additions. Removed since (finding 10).** The exits are now at `rperle.py:93` and
  `rpe.py:94` (the block starts at 85 and 86). They fire only at d = 1;
  d >= 3 runs silently (finding 10). R-PE's message says "RPERLE
  Error". Still no other `sys.exit()` outside `cli.py` and
  `commands/`; the three in `chnbase.py` are commented out (now lines
  1174, 1179 and 1189).
- **`RLESolver.spsolve` re-wraps exceptions: accurate**
  (`chnbase.py:1122-1144`). **Removed since (2026-10-21):** whatever
  `accel()` raises reaches the caller as itself
  (`tests/test_error_handling.py`, seen failing first).
- **`pe`'s filter, removed; anything else silently dropping: three
  more.**
  - `rle`'s `upsample` of its input: accurate, recorded.
  - `get_biparetos` drops exact ties (finding 8; fixed).
  - `pe`'s `remove_nlwep(aold)`: its result is computed and then
    effectively discarded (finding 3).
  - R-SPLINE on a multi-objective problem prints a warning to stdout
    and optimizes the first objective (`rspline.py:26-28`). It says
    so, but with `print`, not `warnings`. **Removed since
    (2026-10-21), by decision:** the behaviour is documented in the
    README, so R-SPLINE runs silently, and a test now checks the
    README's claim (`tests/test_rspline_first_objective.py`).
  - `remove_nlwep`'s `upsample` of neighbours drops infeasible
    neighbours. That one is correct: they are not in X.
- **`ne`'s strict `<` against the MATLAB's `+ 0.00005 <`: accurate.**
  The paper has no tolerance either. PyMOSO matches the published
  algorithm here; it is the MATLAB that adds the constant.
- **The MATLAB's NE is radius 1 only: accurate** (±e_i only, lines
  231-290).
- **`ne`'s charging: accurate** (`chnbase.py:583-600`: `n += m` for
  every feasible neighbour, cached or not; nothing for an infeasible
  one, and `num_calls` does not count infeasible points either).
  Finding 15 is the same pattern in SPLI.
- **The MATLAB's `bk` caps SPLINE iterations, PyMOSO's `b` simulation
  calls: accurate, and the classification changes.** Both papers
  define b_k as a limit on oracle calls, so PyMOSO follows the papers
  and the MATLAB departs from them. What does depart from the papers
  is the (dim - 1) factor and b = 0 at d = 1 (finding 9; fixed at
  d = 1).
- **No counterpart to the revert-to-start guard: accurate, and
  inferred unnecessary.** The MATLAB needs it because its line search
  accepts points up to 0.00005 worse (finding 17), so SPLINE can end
  slightly worse than it began. The paper's SPLINE cannot end worse
  (Step 4 and NE only move to better points), and neither can
  PyMOSO's, whose comparisons are strict.
- **x0 re-estimation: accurate, and now read in the paper.** Theorem
  5.4's proof says "R-SPLINE guarantees to return solutions no worse
  than the given starting solution x0 for every P_k", and Algorithm 1
  does not provide that: it warm-starts from X*_k-1 alone. An omission
  in the paper, as recorded. For the R-PERLE family it is in the
  listings: PE Steps 1 and 26, Min Step 5, RLE Steps 1 and 14 all
  carry x0.
- **The finite-variance condition: inaccurate as worded; correct
  it.** Neither paper omits it.
  - **R-SPLINE:** Lemma 5.2 assumes sup σ²(z) < ∞, and Lemma 5.1's
    large-deviation condition is stronger. The theorems' hypothesis
    is Assumption 2, which those lemmas are sufficient conditions for.
  - **The preprint:** finite variance is Assumption 3, stated outright
    (§8.1), noted as implied by Lemma 2's conditions.
  - **What is true** is the plan's other sentence (its "write what an
    `Oracle` must guarantee" paragraph): PyMOSO's own documentation
    does not state it. **Stated since (2026-10-21),** in the README's
    requirements for `g` and in `Oracle`'s docstring; nothing checks it.
- **`rng.advance()`: accurate.** `RandomCompatAdapter` has no
  `advance` (checked), and `SerialExecutor.run` reads `raw_consumed()`
  on the replication's own stream only (`executor.py:732-733`). A
  framework gap, not an algorithm discrepancy, as recorded.
  **Since (2026-10-24):** the adapter has `advance`, in draws like the
  MRG family's, and the gap in the reserve check is documented rather
  than closed (phase7-plan.md, step 7, "Found 2026-10-18").
- **Best- against first-improvement, now a toggle: accurate, and the
  paper sanctions the default.** NE as described evaluates the whole
  neighbourhood and returns the best (§3.2). §6(iv) adds that "NE
  could be defined to return any better, rather than the best,
  solution in the neighborhood. The convergence proof would be
  unaffected." So first-improvement is a divergence from the listing
  that the paper itself allows. PyMOSO recorded no reason until
  Phase 7.

## In the other direction: what PyMOSO does that the papers do not

- **The per-iteration cache (`gbar`, `sehat`).** R-PERLE prescribes it
  (§4, §9.1). R-SPLINE §6(iii) says its experiments' code had *dropped*
  the cache that the original code had. **Deliberate, and recorded in
  the R-PERLE paper.** It changes oracle-call counts, not results.
- **`WarmStartInfeasible`.** The papers take feasibility as given by x;
  PyMOSO checks that a carried point is still feasible and raises.
  **An implementation necessity** for an oracle that decides
  feasibility; recorded (its docstring, and the plan).
- **`estimate_many` batching.** It must reproduce the one-at-a-time
  results exactly, and is tested to. **Implementation, no algorithmic
  content.**
- **The traceback's 1e-6** (finding 13), **Min's trajectories**
  (finding 11), **x0 in R-MinRLE's starts** (finding 12). Covered
  above.
- **`rle`'s `mcNd -= mcS`** (`chnbase.py:1195`), in no listing.
  **Inferred to be a no-op:** a point that strictly dominated a
  non-conforming point would dominate a member of S, and S is
  non-dominated. Harmless, if so.
- **Any radius,** with `quadratic` refused away from radius 1. Both
  papers allow N_a and default to a = 1. **Deliberate.**
- **The budget is checked only between RA iterations**
  (`chnbase.py:417`). The papers have no stopping rule.
  `KNOWN_ISSUES.md` issue 16 records the overshoot. **An
  implementation choice, recorded.**

## What I could not settle

Findings 6, 11, 12, 15 and 17. (Finding 9 above two dimensions was
here until its reason was recorded, 2026-11-19.)

Finding 2 was settled by the authors after this was written: the
preprint's f̂ is the intended relaxation, and the code was fixed to
it. How the published figures were produced is now known from the 2018
experiment code (read 2026-11-19, kept outside this repository): it
used the old formula, which this repository inherited (finding 2).
Why the sweep did not reproduce the figures' right-hand side remains
open; that code differs from what was swept in more than the
relaxation (`docs/relaxation-sweep.md`).
