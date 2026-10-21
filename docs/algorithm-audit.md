# Algorithmic completeness audit: R-SPLINE, R-PERLE, R-PE, R-MinRLE

Phase 7, step 7 (`docs/phase7-plan.md`). The algorithms as published,
read against the code on `dev-2.0`, for steps, safeguards, tolerances
and orderings present in one and not the other, in both directions.
**This is a list to work through, not a set of fixes.** Nothing here
has been changed. MOCOMPASS and MOPBnB are out of scope
(`docs/mocompass-mopbnb-known-issues.md`).

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
| 1 | PE's traceback reads the epsilon intervals of the wrong objective | R-PERLE, R-PE | defect | measured |
| 2 | The relaxation is se / m^β; the preprint's is se · m^(1/2 - β) | R-PERLE, R-PE, R-MinRLE | defect (decided); fixed | read |
| 3 | PE's LWEP filter is applied to the wrong set and then undone | R-PERLE, R-PE | defect | measured |
| 4 | SPLI's line search floors instead of rounding to nearest | all four | defect | read |
| 5 | SPLI does not stop at an infeasible line-search point | all four | defect | read |
| 6 | Under an epsilon constraint, PLI's gradient uses vertices that violate it | R-PERLE, R-PE | unknown | read |
| 7 | PE breaks ties between objectives deterministically, not randomly | R-PERLE, R-PE | defect | measured |
| 8 | `get_biparetos` drops exactly tied points | R-PERLE, R-PE | defect | measured |
| 9 | The search limit has a factor (dim - 1) and is 0 in one dimension | all four | defect at d = 1; unknown otherwise | read |
| 10 | R-PERLE and R-PE run on three or more objectives without a word | R-PERLE, R-PE | defect | measured |
| 11 | Min adds SPLINE's trajectories to its output | R-PERLE, R-PE, R-MinRLE | unknown | read |
| 12 | R-MinRLE may start a minimizer's search from x0 | R-MinRLE | unknown | read |
| 13 | PE's traceback step when the standard error is 0 is an absolute 1e-6 | R-PERLE, R-PE | implementation necessity, with a hazard | read; the float limit computed |
| 14 | SPLINE stops at `n >= b`, not `n > b` | all four | defect (minor) | read |
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

### 2. The relaxation's scale: se / m^β against se · m^(1/2 - β)

**Defect, decided by the authors (2026-10-19), and fixed: the
preprint is the source of truth.** The code now computes
`se * m**(1/2 - beta)` (`tests/test_relaxation.py`). What follows is the
finding as written, then the measurement that came after it.

Read. The preprint
defines f̂_k(x, β) := ŝe(Ḡ_k,n(x)) · n^(1/2 - β) with ŝe = σ̂/√n
(§3.2; the same in the dissertation, `ch3.tex:292-295`, and in the
introduction's statement of PE), so f̂ = σ̂ · n^(-β). That is both
PE's epsilon interval (β_ε) and RLE's completeness function (β_δ).
The code computes `se / m**beta` (`rperle.py:166-168` `fse`,
`chnbase.py:1327-1328` `calc_delta`), and `se` is the standard error
σ̂/√m (`oracle.py:884`). So the code's relaxation is σ̂ · m^(-1/2 - β),
smaller than the preprint's by a factor of √m: **PyMOSO's β = 1/2 is
the preprint's β = 1.** With the defaults, the preprint's interval is
one standard error; the code's is a standard error divided by √m.

Both formulas have been as they are since 2018 (`a914c3e`). If the
preprint's experiments, including §9.3's β study ("a sweet spot for
β_ε in (0.2, 0.4)"), were run with this code, then the published β
values are the code's, and it is the paper's formula that misstates
them. Convergence holds for any β in (0, ∞) under either convention,
so this is about what the parameter means and about efficiency, not
about correctness.

Measured afterwards, `docs/relaxation-sweep.md`: a sweep of the
shipped code against §9.3's figures matches the published β study
read as the code's β, and not read as the preprint's, except for a
right-hand rise in the figures that neither reading reproduces.

**Resolved: that sweep does not bear on the question.** The
published figures predate this repository. They were produced by
earlier code that was never committed; it exists, outside this
repository, and is deliberately out of scope. The first commit's
formula is what was written when the package was assembled
afterwards, and is where the error entered: s.e. · n^(1/2 - β)
translated into code whose `se` already carries the 1/√n, divided by
it again. So the sweep compared the figures with different code, which
also explains the right-hand rise it could not reproduce.

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

### 4. SPLI's line search floors instead of rounding to nearest

**Defect. Read.** Algorithm 4 Step 12: "Shift x1 to its nearest
integer solution" (and §6(iii): "the nearest single integer solution
for the line searches"). The MATLAB does that, `floor(x0(k) -
s*gamma(k) + 0.5)` (`RSPLINE.m:397`). The code floors without the
half (`chnbase.py:778`), so every line-search point is biased by up to
one unit towards negative infinity in each coordinate. SPLI is a
heuristic as far as convergence goes (§4.2's R-SPLINE(0) remark), so
this changes finite-time behaviour only.

### 5. SPLI does not stop at an infeasible line-search point

**Defect against the listing. Read.** Algorithm 4 Step 13: "if x1 is
infeasible return". In the code an infeasible point ends the line
search (`chnbase.py:786`), and then SPLI returns only if the line
search was short (`i <= 2`, `chnbase.py:789`). From the third step on
it starts a new gradient instead. Under an epsilon constraint,
"infeasible" includes violating it. Again finite-time behaviour only.

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

### 8. `get_biparetos` drops exactly tied points

**Defect (small). Measured.** PE's last step (Step 26) and Min's
remove dominated points. Under Definition 1 two equal vectors do not
dominate each other, so both stay. `get_nondom` keeps both;
`get_biparetos`, which `pe` uses (`rperle.py:72` and `150`), keeps
only one of a set of exactly equal vectors. For R-PE that is the
returned set. Exact ties need discrete outputs or symmetry under CRN
(the step 6b mirror ties are an example).

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

### 10. R-PERLE and R-PE on three or more objectives

**Defect. Measured.** PE is defined for d = 2. The "not bi-objective"
block (`rperle.py:85-93`, `rpe.py:86-94`) is reached only through an
`IndexError`, which happens at d = 1. At d = 3 both solvers run to
the end, measured: `kcon = 1 - k % 2` maps the third objective onto
the second's role, and `get_biparetos` compares two objectives only.

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
  and two additions.** The exits are now at `rperle.py:93` and
  `rpe.py:94` (the block starts at 85 and 86). They fire only at d = 1;
  d >= 3 runs silently (finding 10). R-PE's message says "RPERLE
  Error". Still no other `sys.exit()` outside `cli.py` and
  `commands/`; the three in `chnbase.py` are commented out (now lines
  1174, 1179 and 1189).
- **`RLESolver.spsolve` re-wraps exceptions: accurate**
  (`chnbase.py:1122-1144`).
- **`pe`'s filter, removed; anything else silently dropping: three
  more.**
  - `rle`'s `upsample` of its input: accurate, recorded.
  - `get_biparetos` drops exact ties (finding 8).
  - `pe`'s `remove_nlwep(aold)`: its result is computed and then
    effectively discarded (finding 3).
  - R-SPLINE on a multi-objective problem prints a warning to stdout
    and optimizes the first objective (`rspline.py:26-28`). It says
    so, but with `print`, not `warnings`.
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
  is the (dim - 1) factor and b = 0 at d = 1 (finding 9).
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
    does not state it.
- **`rng.advance()`: accurate.** `RandomCompatAdapter` has no
  `advance` (checked), and `SerialExecutor.run` reads `raw_consumed()`
  on the replication's own stream only (`executor.py:732-733`). A
  framework gap, not an algorithm discrepancy, as recorded.
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

Findings 6, 9 (above two dimensions), 11, 12, 15 and 17.

Finding 2 was settled by the authors after this was written: the
preprint's f̂ is the intended relaxation, and the code was fixed to
it. Two questions it raised are closed with it. How the preprint's
figures were produced: by earlier code, never committed, which exists
outside this repository and is out of scope; do not reopen this from
the repository's history. And why a sweep of this code did not
reproduce the figures' right-hand side: it is not the code that
produced them (`docs/relaxation-sweep.md`).
