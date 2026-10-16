# Phase 7 plan: runtime, complexity, and algorithmic completeness

Written 2026-10-16 to close the many-objective measurement thread. This
is the document a fresh session reads to start Phase 7. It records the
scope, the order and what is already known, so that none of it depends
on a chat session.

**Revised 2026-10-16, after step 1's bi-objective profile**
(`docs/biobjective-profile.md`). The profile reordered the phase; the
revisions are marked "Revised" where they land, and the original text
is kept where a later reader would otherwise re-derive it. Done so
far: the subprocess-tree guard (commit `518cad2`) and step 1's
bi-objective profile (`5527f60`).

## Decisions

- **Phase 7 does not gate 2.0, except step 8** (decided 2026-10-16).
  None of the defects found is a correctness bug, and the performance
  work in steps 2 and 3 is immaterial at realistic simulation cost for
  the bi-objective solvers (step 1). Step 8 still gates 2.0: the
  performance guidance drafted for the README is wrong as it stands,
  and the profile makes that case stronger. The drafts attributed the
  cost to dominance comparison. Measured, it is simulation at
  realistic cost, and neighbourhood estimation at many objectives.
  The drafts were wrong in different directions (appendix).
- **Infeasible re-simulation (step 1b) is pursued as its own step,
  with its own sign-off**, not folded into step 2: it is the only
  finding with leverage at realistic cost, and it is not
  result-preserving by construction (it can move the end seed, though
  no measured run's did: step 1b).
- **The end seed is still recomputed every RA iteration, by
  decision.** `rasolve` calls `Oracle.get_endseed()` each iteration
  and only the last value is used. It is at most 1.8% of a Light-tier
  run and negligible above that. Removing it would change when a
  stream-family overflow raises, and could break an out-of-tree solver
  that reads `self.endseed` mid-run. Do not re-propose it as a step-2
  fix.
- **NE stays first-improvement by default** (step 5, revised). The
  difference from the MATLAB goes into step 7's audit as a
  discrepancy. If a best-improvement toggle is built, it is for
  comparison, default off.

## Open decisions (the maintainer's)
- **How much of the pathological-problem work (steps 6 and 6b)
  belongs here, and how much in its own research track?** It is the
  most interesting output, and the least like the rest of the phase.
- **Does the jump optimization (step 3) change end seeds?** It should
  not: the same streams, computed faster. Confirm before building, not
  after (`docs/end-seed-scope.md` before assuming either way).
- **Does step 2 exist beyond `get_nondom`?** It depends on the
  `get_ncn` early-exit ratio at three or more objectives, which step 1
  measures next.

## First task, before anything is measured: the subprocess-tree guard

Every test that starts a fresh interpreter does so with `-I`
(`tests/_pymoso_cli.py`'s `pymoso_argv`, and direct
`[sys.executable, "-I", ...]` calls). `-I` ignores PYTHONPATH and the
current directory, so the subprocess imports the *installed* pymoso,
while the test process imports whatever is first on its own
`sys.path`. When the two differ -- a second worktree sharing
`.venv-dev`'s editable install of `/srv/projects/PyMOSO`, or
`python -m pytest` run from another checkout -- a suite run silently
tests two trees. Seen in the `many-objective` worktree: 7 failures
from the main checkout's staged solver rename, and every other `-I`
test passing against code that was not under test (the public-surface
cycle check, the dependency boundary, the remote, by-value and Spark
tests, all CLI tests).

**Done (commit `518cad2`, `tests/conftest.py`).** It was seen
stopping every split set up deliberately: an export of the tree run
from its own directory and via PYTHONPATH from elsewhere, on both
venvs; the `many-objective` tree at `d959c34`; and no pymoso installed
at all. On `d959c34` without the guard, the split gave exactly the 7
known failures; that tree installed into its own venv gave 1313
passed, 0 failed, so the 7 came from the split and nothing else. It
passes in the main checkout on both venvs, on extras, and in CI's
`clean-clone` job (the run on `5527f60`, every job but the five
Windows `test` cells green). The Windows failures are attributed, not
read: the logs need a GitHub login. The new benchmark smoke test
called Unix-only `os.getloadavg()`, and removing it locally fails that
test the same way. Fixed in the next commit; the next Windows run
confirms or refutes it. What was proposed, kept for the record: at session start (`conftest.py`,
`pytest_configure`), compare the in-process `pymoso.__file__` with
`[sys.executable, "-I", "-c", "import pymoso; print(pymoso.__file__)"]`,
and stop with a usage error naming both paths. It must be seen failing
in a worktree before it lands, and seen passing in the main checkout
on both venvs and in CI's `clean-clone` job. Rejected alternative:
passing PYTHONPATH to the subprocess, which undoes what `-I` is for
(KNOWN_ISSUES issue 9).

**It comes first because Phase 7 measures**, and measurements made in
a worktree would inherit the problem. The full finding is in
`.git/manyobj/finding-subprocess-tree.md`. That file is local to this
machine: `.git/` is not pushed, so the summary above is the durable
copy. `docs/end-seed-scope.md` records it as the fifth instance of
its pattern.

## Where the evidence is

- **The many-objective measurements:** branch `many-objective`, commit
  `d959c34`, worktree `/srv/projects/PyMOSO-manyobj`. Not merged into
  dev-2.0. Read it with `git show many-objective:docs/many-objective-baseline.md`.
  The tables are `docs/many-objective-tables.md` there, regenerated by
  `docs/bench_many_objective.py`; the raw runs are in
  `scratch/manyobj/results/`.
  What it established, in brief (every M >= 3 result is RMINRLE's):
  - **The cost model.** RMINRLE's time in `get_ncn` is
    k(M) * (sum over iterations of |S|^2), where |S| is the returned set.
    k varies 1-5% within each of 8 configurations (240 runs), does not
    depend on the lattice, and falls only from 48 to 17 us between
    M = 2 and M = 6. Its predicate calls are c * sum |S|^2.
  - RMINRLE targets the whole efficient set; above two or three
    objectives that does not finish at any affordable budget.
    Precision 0.9 was reached in 0 of 180 runs above M = 2.
  - About 40% of simulations are asked for by `get_ncn` at every M, and
    neighbourhood work is about 90% of simulations at M >= 3. `g()`
    calls not counted in `simcalls` (infeasible neighbours) reach 1.76x
    the counted simulations at M = 6.
- **The `get_nondom` defect:** the draft KNOWN_ISSUES entry is
  `scratch/manyobj/known-issue-get_nondom.md` on `many-objective`
  (`git show many-objective:scratch/manyobj/known-issue-get_nondom.md`).
  By earlier decision, the KNOWN_ISSUES entry goes onto dev-2.0 after
  2.0.0 ships, as its own change.
- **Nagaraj's 2014 MATLAB R-SPLINE:** `docs/RSPLINE.m` (untracked at
  the time of writing, so commit it with this plan). Line numbers
  below refer to that file.
- **The jump's cost:** `docs/hit-cost-baseline.md` (`stream_at` about
  1.56 ms on 3.14, MRG32k3a) and `docs/numpy-findings.md` (78-86% of a
  cheap serial run on the MRG family is the jump; numpy cannot do it
  exactly). Philox's jump is already about 1.1 us.

## Scope

PyMOSO offers reference implementations of R-PERLE, R-MinRLE and
R-SPLINE.
- **In scope:** improving their complexity without changing what they
  compute.
- **Out of scope:** changing what they compute, unless the change is
  behind an opt-in parameter that says so.

Every such parameter is declared in the solver's `PARAMS`, so that it
reaches the generated parameter table (`tests/test_readme_param_table.py`,
defaults and descriptions in `tests/_solver_param_docs.py`).

## Steps, in this order

### 1. Measurement

- The many-objective sweep is done (above).
- **Outstanding: profile R-PERLE and R-SPLINE at two objectives with a
  realistic oracle cost.** The 94%-in-`get_ncn` figure is RMINRLE at
  M = 6 on a cheap problem. It may not describe the algorithms people
  actually use. In the same sweep RMINRLE at M = 2 spent 96% of its
  time simulating and 2.9% in `get_ncn`. Use `ProbExpensive`/
  `ProbExpensiveBi` tiers for the cost (CLAUDE.md, Testing).
- **Generalize the redundancy counting that found the `get_nondom`
  defect.** For each hot function, derive from the algorithm what it
  requires (calls, comparisons, simulations), count what the code does
  with a wrapper on the name the caller reads, and compare. The
  `get_nondom` analysis predicted n(n-1)/2 and the counter refuted it.
  The derivation is a hypothesis, and the counter is the test.

**Revised: the bi-objective profile is done** (`docs/biobjective-profile.md`,
regenerated by `docs/bench_biobjective_profile.py`). R-PERLE, R-MinRLE
and R-SPLINE, budget 10,000, MRG32k3a and Philox, the `ProbExpensive`
tiers. What it changed, in short:
- **At realistic cost, simulation is the run:** 97-99% at Moderate,
  over 99% at Heavy (MRG32k3a), measured to within 1.4% by 36 real
  tier runs against the model.
- **Dominance work is irrelevant at two objectives:** `get_ncn`,
  `remove_nlwep` and `is_lwep` together at most 0.07% of a Light-tier
  run, `get_nondom` at most 0.01%. The 94% figure is many-objective
  only.
- **The MRG jump matters only for cheap simulations:** 5-19% at
  Light, under 2.5% at Moderate, under 1% at Heavy. Philox already
  removes it.
- **The largest redundancy is simulation, not comparison:** from a
  boundary start, 14-22% of all `g()` calls re-simulate a point already
  found infeasible in the same iteration (step 1b).

**At three or more objectives: measured 2026-10-16, before step 2 was
scoped.** At two objectives part (b) does about three times the
predicate work an early exit would need for the same `ncn` (4,617
against 1,576 calls), and it does not matter there. At many objectives
`get_ncn` is the cost, so the question was whether the excess is large
there. RMINRLE on the many-objective baseline's lattice DTLZ2 (L = 4,
sigma 0.05, Philox), budget 30,000, three seeds per M, 15 runs;
`scratch/phase7/` has the script, the raw runs and a README. The
early-exit shadow reached the same `ncn` as the real code on every
call of every run. Load 0.41 at the start, about 1.0 during (the job
itself).

| M | mean \|S\| | (b) predicates done / needed | `calc_delta` done / needed | `get_ncn` share of run (time mode) |
|---|---|---|---|---|
| 2 | 9 | 2.6x | 10x | 6-8% |
| 3 | 39-46 | 2.3-2.4x | 45-55x | 29-35% |
| 4 | 101-117 | 2.1x | 146-167x | 58-63% |
| 5 | 227-251 | 1.8-1.9x | 347-383x | 79-80% |
| 6 | 276-332 | 1.6-1.8x | 445-546x | 82-86% |

Counts are **measured**. Part (a) is already at its requirement (under
0.5% excess).

**The excess that grows with M is not the predicates: it is
`calc_delta`.** Part (b) recomputes each member's relaxation `dels`
for every candidate, |S| x |candidates| x M calls where
(|S| + |candidates|) x M suffice, and |S| is what grows with M. The
predicate excess shrinks as M grows.

**What it would save (estimated, not measured):** counts times unit
costs from a microbenchmark on this machine (`calc_delta` about 135-190
ns, a predicate about 155 ns), against each run's uninstrumented wall
time. Computing `dels` once per member and once per candidate: about
10% of the run at M = 3, 21% at M = 4, 28-32% at M = 5-6. An early exit
in part (b): about 15% at M = 3 to 12% at M = 6 (the M = 3 unit cost
is the least reliable). On this cheap problem, so both shares fall as
simulation cost rises. But `get_ncn` grows as sum |S|^2 and simulation
does not, so at M = 6 it stays comparable to Light-tier simulation
(about 26 s of Light-tier burn for these runs' 59k simulations, against
about 28 s of `get_ncn`). This is a modelled comparison, not a run.

**So step 2 exists, at three or more objectives, and its first item is
`calc_delta`, not the early exit.** Both are result-preserving by
construction (the same floats from the same expressions; the same
`ncn`, by the shadow), to be proved again on the real change.

### 1b. Infeasible points simulated again within an iteration

Added after step 1. **Not result-preserving: its own step, with its
own sign-off, never folded into step 2.** It is rng-interface-design.md
§11 entry 13, deferred until now.

From a start on the boundary the efficient set touches, 14-22% of all
`g()` calls (2,000-3,500 per run at budget 10,000) repeat a point
already found infeasible in the same iteration. Most come from
`get_ncn`: a deleted neighbour shared by several members of S is asked
for once per member, and again by part (b). `ne`, `pli` and `upsample`
add the rest. In `ProbExpensive*` an infeasible `g()` skips the burn,
so there the repeat costs only the jump; a problem that learns
infeasibility only by simulating pays the whole replication.

(This paragraph first said that each repeat "moves the high-water
mark, so the end seed moves". That was reasoning, never measured, and
it is wrong as a general statement; see below.)

**First, before any design:** establish whether the re-simulation is
inherent to what certification requires, or an artifact of not
carrying infeasibility across calls within an iteration. That decides
whether this is a cache or a redesign. Report that before designing.

**Answered 2026-10-16: an artifact, so a cache.** Reported to the
maintainer; nothing designed or built.
- **Why it is not inherent.** Certification (the ALES and LWEP
  tests) is a statement about one iteration's sample-path problem.
  A feasible point is estimated once per iteration (`gbar`) and every
  later question reads that estimate. An infeasible point is asked
  again only because `estimate()` stores feasible outcomes and
  nothing else. Nothing in the certification asks for a second
  opinion on feasibility.
- **Measured with a shadow** (`scratch/phase7/infeas_cache.py`): an
  in-process record of oracle-infeasible points, kept per iteration,
  that answers a repeat without simulating. Nothing in `pymoso/`
  changed. 42 runs: RPERLE, RMINRLE and RSPLINE from the boundary start
  on `ProbExpensiveBi`, RPERLE on ProbTPB from (0, 0), and RMINRLE on
  lattice DTLZ2 at M = 3 and 4, both generators, three seeds each. The
  rows labelled "RPERLE TPA" are the BiEdge rows again, because
  `ProbExpensiveBi` at burn 0 is ProbTPA's `g()`. **In all 42 the
  solution, every iteration's set, the end seed and `simcalls` were
  identical**, while `g()` calls fell 11-44% (0-1% for RSPLINE).
- **The detector was seen detecting.** A positive control with
  random feasibility (`RandomEdgeBi`: near x[0] = 0 a replication is
  infeasible with probability 0.03) differed in 5 of 6 solutions and
  6 of 6 iteration paths. Its first version, at probability 0.5, saw no
  difference: a block of m replications was then almost never
  feasible, so repeats never flipped. That version is not evidence of
  anything.
- **The full suite with the shadow on, `-I` subprocesses included**
  (a scratch venv loading it through a `.pth`): 1313 passed, 7 skipped.
  No golden moved. The 12 CLI end-seed goldens skipped 72 repeated
  blocks between them, logged with their pids, so the shadow was
  reached where it mattered.
- **Why the end seed did not move.** A block's offset packs the point
  code above the visit and the replication count
  (`prng.base.offset_from_point_code`). So the high-water mark is set
  by the largest point code touched in the final iteration. A cache
  moves the end seed only when that point is oracle-infeasible and is
  asked for more than once in that iteration. That is possible, so a
  cache is **not result-preserving by construction**, but it was seen
  0 times in the 42 runs and the 12 goldens. A repeat also counts
  towards `ReplicationOverflow` for that point, so a cache would delay
  that raise.
- **Under `--crn` a repeat replays the same replications**, so a cache
  changes nothing there at all.
- **With random feasibility the answer differs, and so does the
  premise.** There a repeat can flip a verdict. A cache would fix the
  verdict for the iteration, which is what a sample-path problem means.
  But the RA solvers already fail on such problems with or without a
  cache. A warm-start point that was feasible last iteration and comes
  back infeasible raises a bare `KeyError` from `get_min`
  (`self.gbar[t]`), reported as `RMINRLE: Unable to run accel().
  Message: (5, 22)`. Seen on the control at both probabilities, cache
  on and off. **This is a separate finding: the built-in solvers assume
  feasibility is a function of x, and the `Oracle` contract does not say
  so.** Not fixed, and not part of step 1b.
- **`tests/test_batching.py`'s `SometimesInfeasible` test does not
  detect a cache.** It passed with the shadow on. It compares
  `estimate_many` with `estimate` in a loop, and the shadow changes
  both alike. It detects `estimate_many` diverging from `estimate`,
  which is what it was written for. CLAUDE.md calls it "the detector"
  for a version that skips repeats. That holds only for an
  `estimate_many` that skips while `estimate` does not.

**Decided 2026-10-16:**
- **Step 1b keeps its full sign-off.** "No measured result moved" is
  weaker than "cannot move". It is a behaviour change that happens not
  to have bitten in 42 runs. If a golden moves when it is built, report
  that before regenerating anything.
- **The condition, so that nobody has to rely on the empirical
  result:** the cache moves the end seed exactly when the point it
  stops re-simulating holds the largest point code touched in the run's
  final iteration, and is asked for more than once in that iteration.
  Otherwise the high-water mark is set by another block and does not
  change. It also delays `ReplicationOverflow` for that point. Under
  `--crn` it changes nothing.
- **Its regression test counts blocks or `g()` calls.** Comparing
  results cannot see it (`docs/end-seed-scope.md`, the sixth instance).
- **It shares its record with KNOWN_ISSUES issue 18's check**
  (`FeasibilityChanged`), so that it cannot bypass it. Under the cache
  a point's first verdict in an iteration stands for that iteration;
  flips across iterations are still caught. The issue entry has the
  reasoning. Decided before the cache is built, so that building it
  does not silently weaken the check.
- **Random feasibility is refused with a clear error, and the
  assumption is documented.** It is tracked as its own KNOWN_ISSUES
  entry, independent of Phase 7, because it affects every version. The
  solvers depend on feasibility being a function of x alone. That is a
  constraint of the algorithms, and supporting random feasibility is a
  research question, not a fix.

### 2. Implementation defects

**Revised: lower priority for two objectives, and it exists for three
or more.** At two objectives nothing here is material at realistic
cost (step 1). At three or more, `get_ncn`'s recomputed relaxations and
its missing early exit are together an estimated 20-45% of a
cheap-problem run (step 1, "At three or more objectives").

Work the code does that the algorithm does not require. Results must
be identical, every fix provably result-preserving, and no golden may
move. Known so far:

- **The `get_nondom` merge defect.** `pymoso/moso.py:285` re-reads
  `len(Tpts)` while line 290 appends to it, giving about 3n^2/4
  dominance tests in the worst case instead of n(n-1)/2. The fix bounds
  the loop at the first half's length, which keeps `Tpts` order
  identical. A regression test can assert the call count.
  Confirmed in real runs by step 1: 6-11% more `does_dominate` calls
  than the bounded loop, at mean |S| 2.3-2.6. Real and small.
- **`get_ncn` part (b) recomputes each member's relaxation for every
  candidate** (step 1): `calc_delta` 10x the calls needed at M = 2,
  45-546x at M = 3-6. Computing `dels` once per member is the largest
  saving found at many objectives (estimated 10-32% of a cheap-problem
  run). Same floats from the same expressions, so result-preserving by
  construction.
- **`get_ncn` part (b) without an early exit** (step 1): predicate
  calls 1.6-2.6x what an early exit needs, the ratio falling as M
  grows (estimated 12-19% of a cheap-problem run at M >= 3). A shadow
  computation reached the same `ncn` on every call of every run.

Not a step-2 fix, by decision: the per-iteration end-seed
recomputation (Decisions, above).

### 3. The expensive jump

**Revised: lower priority.** At realistic cost the jump is under 2.5%
of a run (Moderate) and under 1% (Heavy). It is 10% of a run only when
`g()` costs 0.2-1 ms per replication, and 1% at 2.5-11 ms (modelled
from measured parts, step 1). Its benefit is already available by
choosing Philox (`--generator philox4x32`). It still matters for cheap
simulations on the MRG family, and for high dimension, where the
jump is most of the run (CLAUDE.md, the `get_nbors` correction).

`stream_at` at about 1.5 ms dominates serial runtime at higher
dimensions. This is the MRG family; Philox is already cheap.

**Profile first:** what fraction of the time is the exponentiation chain,
and what fraction the per-multiply arithmetic.

Two candidate optimizations:
- **Cache A^(2^k) mod m at import**, so that A^n is a product over the
  set bits of n rather than a full square-and-multiply chain.
- **Exploit the coordinate structure.** Coordinates are
  stream * STRIDE + offset with power-of-two strides, so
  (A^STRIDE)^stream is constant within an iteration and can be cached.
  Each call then pays only for the offset's bits.

**Considered and rejected: parallelizing the multiply.** Each step is
nine big-integer multiplies, sequentially dependent, far below dispatch
cost.

Related: rng-interface-design.md §11 entry 14 (a cheaper general jump).
On end seeds, see the open decision above.

### 4. The quadratic candidate in NE

Specified by Nagaraj's 2014 MATLAB R-SPLINE, `docs/RSPLINE.m`, function
`NE` (lines 216-312).

**The idea.** Enumeration already evaluates x +/- e_i for each
coordinate. With the centre, that is three points along each axis, a
parabola. Fit the vertex where the parabola is convex, assemble ONE
candidate from every coordinate's vertex, and evaluate it once: 2d+1
calls instead of 2d. Certification is unaffected. The payoff is fewer
SPLINE iterations.

**Details to preserve from the MATLAB:**
- **Convexity tolerance:** `a - 0.00005 > 0` (line 281), with
  `a = (y1+y3)/2 - y2` and `b = (y1-y3)/2` (lines 279-280).
- **Skip the fit when either neighbour was infeasible**
  (`count == 3`, line 278), so that boundary points fall back to
  plain enumeration.
- **Magnitude guard on the cast:** `abs(xqnew) < 2147483646.0`
  (line 287).
- **One combined candidate, not d separate ones.** Where no vertex
  was valid, take the centre's coordinate (`xqnew` starts as the
  centre's, line 275).
- **Rounding:** MATLAB's `int32()` (line 282) rounds half away from
  zero, unlike Python's `round()`, which rounds half to even.

**Two things the MATLAB does that the list above does not settle.**
These are observations, for the maintainer to decide on:
- **When the magnitude guard fails, the MATLAB does not use the
  centre's coordinate.** `ixquad` is initialized to zeros (line 230)
  and only written when the guard passes (line 288), so that coordinate
  of the candidate is 0. "The centre where no vertex was valid" covers
  the non-convex and infeasible cases only.
- **The candidate is evaluated even when it equals the centre** (no
  coordinate had a valid vertex) or a neighbour already evaluated
  (lines 293-294). That evaluation spends replications on nothing new.

**Comparison rule.** The candidate replaces the running best only if
`ixquadfn + 0.00005 < xnewfn` (line 298), the same strict tolerance as
the neighbours (lines 250, 266).

**The toggle.** Default off, for comparison against the reference.
It affects R-PERLE, R-MinRLE and R-SPLINE, all of which reach `ne`
through SPLINE.

**Measure:** how often the candidate is feasible, how often it beats
the best neighbour, SPLINE iterations to convergence, and total
simulation calls.

### 5. First-improvement NE

**Revised: PyMOSO's `ne` is already first-improvement**
(`pymoso/chnbase.py`, `ne`, both the radius-1 branch and the general
one: it returns at the first neighbour that improves). The MATLAB is
best-improvement over all 2d neighbours. So the toggle this step would
build is **best-improvement**, for comparison against the reference,
**default off**. The default does not change: that would change
results. The difference is recorded in step 7's audit as a
discrepancy, not as a step-2 defect.

The guarantee point below also needs re-examining before anything is
built (reasoning, not measured): an NE that finds no improving
neighbour has examined every neighbour under either rule, so the
certificate at SPLINE's termination looks the same. What differs is
the path to it.

The original text, kept because it is what was planned:

A second toggle, independent of the first: stop at the first improving
neighbour.
- **Unlike step 4, this DOES change the guarantee.** Some neighbours
  go unexamined, so local efficiency is not certified.
- **The two toggles interact.** First-improvement leaves fewer vertices
  for the quadratic candidate, so the comparison has four cells, not
  three.
- **Confirm what PyMOSO's `ne` does now: best or first improving
  neighbour.** The MATLAB scans every neighbour against a running best
  (lines 239-291). A difference is a step-2 finding.

### 5b. Neighbourhood radius

Radius is a documented parameter, default 1, and effectively
unexercised. The `get_nbors` equivalence work covered radii 1-3 for
correctness (`tests/test_get_nbors_equivalence.py`; insertion order is
load-bearing, see CLAUDE.md), but nothing has measured what radius buys.

Measure across radii 1-5:
- neighbourhood size against returned points;
- `get_ncn` cost, which scales as neighbourhood size times set size
  (the cost model above has 2n where radius 1 is assumed), so radius 2
  may be unusable;
- whether a larger radius escapes local efficient sets that radius 1
  certifies;
- simulations per certified point.

**Possible algorithmic improvement.** At radius 2 and above, most
neighbours are dominated by points already evaluated, and an evaluation
order that prunes them could change the scaling. Determine whether
provably-safe pruning exists. If it does, it is a step-2 fix, not a
toggle.

### 6. Pathological test problems

Everything measured so far runs on problems where PLI's
pseudo-gradient works well, which is why SPLINE-family methods
dominate. Characterizing where they do not is the more valuable output,
and is publishable. Candidate structures, in order of industrial
plausibility:

- **Plateaus. Build this one first.** Integer capacity thresholds,
  where the objective is flat until a threshold is crossed, so the
  pseudo-gradient is zero and PLI has nothing to follow. Ubiquitous in
  staffing, batching and inventory. Defeats PLI structurally rather
  than probabilistically.
- **Barriers, for the radius work.** A local efficient set at radius 1
  that is not one at radius 2: the immediate neighbours are all worse,
  and something two steps away is better. For example, batch sizes
  where moving one unit breaks a packing constraint and two restores it.
- **Interaction-dominated objectives.** Dependence on products or
  minima rather than sums, so that simplex interpolation is a poor
  local model at any lattice resolution. For example, queueing networks
  in series.
- **Misleading local gradients.** Unit-step differences that point
  against the larger-scale trend.
- **Heteroscedastic noise near the optimum.**

**Design these BEFORE steps 4, 5 and 5b are measured**, or those
comparisons get rerun.

**Shared design question:** how to build an integer-ordered test
problem with a KNOWN efficient set at each radius. Without the true
answer, solution quality cannot be measured. The many-objective work's
lattice DTLZ2 (exact front, exact distance to it,
`scratch/manyobj/dtlz2_lattice.py` on `many-objective`) is one worked
example of the standard required.

**A connection worth testing.** Partition-and-bound does not need
local structure. If these problems defeat the SPLINE-family methods and
MOPBnB handles them, that is a concrete measured answer to when to use
the global solver, which nobody has published. (MOPBnB in-tree is
`ExampleBnBSolver`, unverified against its paper. See
`docs/mocompass-mopbnb-known-issues.md` before relying on it.)

### 6b. Where CRN fails

CRN reduces Var(g(x) - g(y)) = Var(x) + Var(y) - 2Cov(x, y). It helps
when the covariance is positive and HURTS when it is negative.
Candidates:

- **Synchronization failure, probably the most important.** CRN needs
  the same random numbers used for the same purpose at both points. If
  x and x+1 consume different NUMBERS of variates (a longer queue draws
  more service times), the streams desynchronize, and everything after
  that is effectively independent. The result is not "CRN hurts" but
  "CRN silently stops working." PyMOSO is particularly exposed, because
  `g()` can draw a variable number of variates per replication; that is
  why `Oracle.replication_draws` exists.
- **Threshold or routing structure.** A shared uniform picks a branch,
  and the boundary sits between x and x+1, so the same draw sends the
  two points' customers opposite ways.
- **Distribution mixes,** where the common draw means different things
  at different points.
- **Antithetic-like structure:** a monotone transformation that
  reverses sign across the decision space.

**Measurable directly.** Estimate Cov(g(x), g(x+e_i)) across the
lattice with and without CRN, and compare it against draw counts per
replication. The prediction is that correlation collapses where draw
counts differ between neighbours. Probably three test problems,
because the guidance differs: "CRN will not help, do not pay for it"
versus "CRN will hurt."

**Why it matters beyond characterization.** RA's efficiency argument
assumes that the warm start from iteration v-1 is useful at v, and CRN
is part of what makes consecutive sample paths comparable. A problem
class where CRN fails may degrade the RA framework's advantage too.

### 7. Algorithmic completeness audit

The quadratic candidate was in a published implementation and not in
PyMOSO, which makes it a category, not a one-off. Read R-SPLINE (Wang,
Schmeiser and Pasupathy 2013), R-PERLE (Cooper, Hunter and Nagaraj
2020) and R-MinRLE against the code, for steps, safeguards and
tolerances present in one and not the other.

The MATLAB is a second reference for R-SPLINE:
- **Its 0.00005 tolerances throughout:** in NE (lines 250, 266, 281,
  298) and in SPLI (lines 371, 387, 414, 417, 505, 522).
- **Its termination conditions:** SPLINE stops when SPLI and NE return
  the same objective value, by exact equality (`xoldfn==xnewfn`, line
  199), or after `bk` iterations (line 168).
- **The guard that reverts to the starting solution:**
  `x0fn + 0.00005 <= xnewfn` (line 206; note `<=` here, against the
  strict `<` elsewhere).
- **It counts only feasible evaluations** in `ncalls` (lines 246-247,
  262-263, 296-297), the same accounting as PyMOSO's `simcalls`.

**Found already (step 1), to record in this audit:**
- **NE's improvement rule.** PyMOSO first-improvement, MATLAB
  best-improvement (step 5, revised). Not changing the default.
- **SPLINE's limit.** MATLAB's `bk` caps SPLINE iterations. PyMOSO's
  `b` caps simulation calls, as `bconst * (dim - 1) * 1.2^nu`, which is
  0 in one dimension, so a 1-D R-SPLINE does one SPLI+NE pass per RA
  iteration.
- **The revert-to-start guard** (line 206) has no counterpart in
  PyMOSO.

**Report discrepancies; do not fix them in this step.** Some will be
deliberate.

This step is reading, and can run alongside anything.

### 8. Consolidate and document

The user-facing guidance from all of the above. It replaces the draft
performance sections (the maintainer's drafts, not in the repository
when this was written). Those were written before any of this was
measured, and they are wrong in at least one respect: they attribute
the cost to dominance comparison, when it is neighbourhood estimation
(the many-objective baseline's "Where the cost goes" section).

**Revised after step 1:** and at two objectives with realistic cost
it is neither. It is simulation, at 97-99% of the run
(`docs/biobjective-profile.md`). The guidance has to say which regime
each claim belongs to. **This step gates 2.0** (Decisions, above).

Record the toggles in `PARAMS`, so that they reach the generated
parameter table.

## Sequencing

**Revised after step 1:**
- Done: the guard, and step 1's bi-objective profile.
- Done and reported, nothing built: the `get_ncn` ratios at
  M >= 3 (step 1), and the certification question that opens step 1b.
- Decided: step 2 at M >= 3 is three commits, in this order:
  computing relaxations once, the early exit, then `get_nondom`. Each
  has the shadow-and-assert check and no golden movement. Before each
  of the first two lands, it must be observed giving identical results
  on the counted runs, not only passing goldens.
- Random feasibility: refused and documented, as its own change
  (step 1b's decisions).
- Steps 2 and 3 drop in priority. They remain golden-neutral and can
  land in any order, but at realistic cost neither changes much for
  two-objective users, and step 3's gain is already available through
  Philox.
- Step 1b is not golden-neutral and lands on its own sign-off.
- Step 8 gates 2.0; nothing else in the phase does.

The original order, for the record:
- The subprocess-tree guard comes first.
- Steps 1, 2 and 3 are golden-neutral, and can land in any order.
- Steps 6 and 6b precede 4, 5 and 5b, so that those comparisons run on
  both problem families.
- Step 7 is reading, and can run alongside anything.

## Working rules that apply throughout

From CLAUDE.md, repeated here because Phase 7 leans on them:
- **Goldens.** Never regenerate or edit them without being asked.
  Steps 2 and 3 move none.
- **Regression tests.** A regression test is seen failing before its
  fix lands, and a substitution test needs proof that the substitute
  was reached (`docs/end-seed-scope.md`, the pattern section).
- **Timing measurements:**
  - Run them on a quiet machine: check `uptime`, and record the load
    average before and after each run.
  - Interleave the runs wherever two things are compared.
  - Absolute timings go in a `docs/` artifact with a regenerating
    script, never into assertions.
- **Measured and estimated** are labelled as such, and actual
  simulation counts are reported, never requested budgets (KNOWN_ISSUES
  issue 16).
- **Bytecode caching:** set `PYTHONDONTWRITEBYTECODE=1` and clear
  `__pycache__` before any mutation check or stage swap.

---

## Appendix: superseded draft guidance

Step 8 replaces the performance guidance drafted before any of this was
measured. Those drafts were never committed, so they are preserved here for
reference. Do not copy them into the README — they are recorded so the
rewrite can see what was claimed and on what basis.

Annotations mark what the many-objective measurements confirmed, corrected
or left untested.

### Draft: performance with many decision variables

> The number of decision variables affects run time more than most other
> factors, and the effect is not gradual.
>
> | Dimensions | Behaviour                                      |
> | ---------- | ---------------------------------------------- |
> | 1-3        | fast                                           |
> | 6-9        | seconds                                        |
> | 12-20      | minutes, and growing quickly                   |
> | 50+        | hours on the default generator                 |
>
> Three things drive this.
>
> **More points get visited.** The solvers examine a neighbourhood around
> each iterate, and the neighbourhood grows with dimension.
>
> **The default generator gets expensive.** With `mrg32k3a`, positioning
> each replication's stream costs around 1.5 ms, paid once per block of
> replications. At dimension 20 and above it can be most of the run time.
> Use `--generator philox4x32` in high dimensions — about a microsecond
> rather than a millisecond.
>
> **The budget stops meaning what you expect.** `--budget` is checked
> between RA iterations, and one iteration's work grows with dimension. A
> requested 1,000 may run 1,100 simulations at dimension 2, around 3,700 at
> dimension 9, and hundreds of thousands at dimension 50.
>
> Practical guidance: up to about dimension 9 the built-in solvers are
> comfortable; from dimension 10 switch to `philox4x32` first; expect
> `--budget` to understate effort; parallelism divides the work, it does
> not reduce it.

**Status.** The dimension table came from one problem at one budget and was
flagged as approximate when written. Not retested. The budget-overshoot
claim is now better supported: the many-objective sweep requested 300k
simulations and counted 300k–468k, with uncounted `g()` calls reaching
1.76× the counted total at M = 6, of which 58–81% came from `get_ncn`.

### Draft: performance with many objectives

> Problems with more than three objectives are commonly called
> "many-objective," and the distinction is not cosmetic.
>
> The proportion of points that are non-dominated rises steeply. Studies in
> the deterministic literature find roughly 30% of a small sample
> non-dominated with two objectives, about 50% with three, over 70% with
> four, and over 90% with six or more.
>
> **The answer gets large.** The efficient set is the solution to your
> problem, and at many objectives most of the feasible region may qualify.
>
> **Estimation gets harder at the same time.** Deciding whether one point
> dominates another requires estimating both well enough to tell them
> apart, and at many objectives the points being compared are close
> together by construction.
>
> Practical guidance: with two objectives use `RPERLE`; with three,
> `RMINRLE` is what is available and should be workable; with four or more
> treat it as exploratory. Run a small budget first and look at how many
> points come back — the size of the returned set is the best early
> indicator of what a full run will cost. Do not use hypervolume as your
> metric at many objectives.

**Status.**

*Confirmed.* The returned-set size is the right early indicator — it is
literally the driver of the cost model, since `get_ncn` time is
k(M) × Σ|S|² over iterations.

*Corrected.* An earlier version of this draft attributed cost to
maintaining the non-dominated set at roughly n² comparisons. `get_nondom`
is about 2% of wall time; `get_ncn` is around 94% at M = 6. The quadratic
term is real but it belongs to neighbourhood estimation, not dominance
comparison. Roughly 40% of simulations go to `get_ncn` at every M, and
about 90% to neighbourhood work at M ≥ 3.

*Overstated.* "With three, `RMINRLE` should be workable" is too generous.
At M = 3 all 25 efficient points are found by 100k simulations, but
replications per point more than double between 100k and 300k while
precision stays flat at about 0.28. At M ≥ 4 the target is not reached at
300k. RMINRLE targets the whole efficient set, (L+1)^(M−1) points, so above
three objectives it is not converging slowly — it is attempting something
that does not finish at any affordable budget.

*Untested.* The hypothesis that stochastic error compounds the
many-objective difficulty beyond what the deterministic figures suggest.
Experiment 3b reached precision 0.9 in 0 of 180 runs above M = 2 and so
gives no scaling with M.

### Not drafted, and still unwritten

Guidance for `--simpar` and `--proc`, and for `dispatch_cost`. Drafts
existed in conversation only and are not preserved here; the cluster
measurements they were built on are in `docs/spark-backend.md` and
`docs/simpar-ceiling.md`, which is the durable record. Step 8 should write
these fresh from those documents.
