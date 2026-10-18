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
  **Settled (2026-10-17): it cannot, by construction from
  bit-identity.** `get_endseed` computes the end seed with `stream_at`,
  which reaches the same `jump_seed_n`; a jump returning the same tuple
  for every exponent cannot move it. That was argued before building;
  bit-identity was then tested per exponent, and the end seed confirmed
  by the goldens, the 39 counted runs and a direct test (step 3). It
  rests on bit-identity, not on a general "the streams are unchanged".
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
  **Corrected 2026-10-17.** The finding is narrower than written. The
  failure is always the warm start: a point the previous iteration
  returned, having estimated it feasible, which comes back infeasible.
  Checked directly on the five observed failures (R-MinRLE from
  (6, 20); R-SPLINE from (8, 20) and (6, 20)): each failing point was in
  the space on every replication and was refused only by
  `RandomEdgeBi`'s coin. And in 84 runs on problems that decide
  feasibility from x (all four solvers, five problems, three seeds),
  all 3,490 warm-start points had been estimated feasible by the
  iteration that returned them. So nothing in the warm-start path is
  defective; the errors are the solvers meeting a `g()` whose verdict
  depends on its random numbers. What follows is decided below.
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
- ~~It shares its record with KNOWN_ISSUES issue 18's check
  (`FeasibilityChanged`).~~ **Withdrawn 2026-10-17** with the check
  itself (next bullet). The cache has no record to share.
- ~~Random feasibility is refused with a clear error.~~ **Withdrawn
  2026-10-17, and KNOWN_ISSUES issue 18 with it.** The check was built
  and never committed: a whole-run record of every point's verdict,
  raising `FeasibilityChanged` on any flip. It was the wrong mechanism.
  A verdict that flips within or across iterations is sampling noise,
  and nothing in these algorithms asks for a point's feasibility twice
  in a way that matters except the warm start. The warm start's
  feasibility is inherited from the iteration that returned it, not
  estimated, so for the algorithms whose sample-path problems are
  unconstrained in the oracle's sense (the RLE family and R-SPLINE),
  an infeasible warm start cannot happen when `g()` decides
  feasibility from x. **Decided instead:**
  - `WarmStartInfeasible`, raised where those solvers already
    re-estimate the warm start. Its message gives the likelier cause
    first (a `g()` whose feasibility depends on its random numbers,
    which these solvers do not support) and a defect in PyMOSO second.
    Not raised by `RASolver`: an algorithm with random constraints
    could legitimately meet an infeasible warm start. KNOWN_ISSUES
    issue 19 is what it fixes.
  - `pe`'s filter of its warm start (R-PE, R-PERLE) is removed, so
    those two solvers raise like the others instead of silently
    dropping the point. Reported before building.
  - Random constraints are real in these algorithms only inside
    R-PERLE's epsilon-constraint sub-problems (`estimate`'s `con`),
    which never touch the oracle's verdict.

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
  **Done (step 2c).** `front()` captures the top front's length before
  the merge. The comparisons it skips are always False: nothing
  `front()` returns is dominated by anything earlier in its own output
  (each half by induction; an appended point is dominated by no top
  point, and the points appended before it precede it in the bottom
  half's own output). The proof is in the code comment.
  `tests/test_get_nondom_work.py` keeps the old `front` verbatim and
  holds the new one to it, answer and order, on 400 random sets (ties,
  equal vectors, nan; sorted as `get_nondom` sorts them and unsorted),
  and checks that property directly on every `front()` output at every
  level of the recursion, so the result does not rest on the argument
  alone. Two exact counts: 16 mutually non-dominated points take
  n(n-1)/2 = 120 comparisons (the previous code made 164), and a set
  with domination takes 10 (previously 11); both failed first. A bound
  one too small is caught by every test, the invariant check included;
  dropping the short-circuit, which only costs work, by the second
  count. On the 39 counted runs, with `step2_record.py` extended to
  digest every `get_nondom` call's input and answer, every run was
  identical to the record after step 2b, and every other counter
  unchanged. `does_dominate` calls inside `get_nondom`: 7.0% fewer on
  the RPERLE bi-objective runs and 6.9% on RMINRLE's, inside step 1's
  6-11%; 22% fewer at M = 2 on lattice DTLZ2, 30-32% at M = 3-6 (step
  1 did not measure these). No golden moved.
- **`get_ncn` part (b) recomputes each member's relaxation for every
  candidate** (step 1): `calc_delta` 10x the calls needed at M = 2,
  45-546x at M = 3-6. Computing `dels` once per member is the largest
  saving found at many objectives (estimated 10-32% of a cheap-problem
  run). Same floats from the same expressions, so result-preserving by
  construction.
  **Done (step 2a).** `get_ncn` computes each member's relaxation once.
  `tests/test_get_ncn_work.py` keeps the old `get_ncn` verbatim and
  holds the new one to it, answer and order, on 40 sets; it counts
  `calc_delta`. It was seen failing before the change (72 calls where
  30 suffice), and seen catching a plausible wrong version (one
  objective's standard error used for all). On the 39 counted runs
  (`scratch/phase7/step2_record.py`: lattice DTLZ2 at M = 2-6, and
  the bi-objective configurations, both generators), every run was
  identical before and after: solution, end seed, simcalls, and
  every `get_ncn` call's input and answer, in sequence. The same
  wrong version made 3 of 3 of those runs differ. `calc_delta` calls
  at M = 6, seed 1: 77,854,344 before, 142,644 after, which is exactly
  the requirement step 1 derived. Predicate counts are unchanged. No
  golden moved. The claim, precisely: not "results unchanged" but the
  same expressions, evaluated fewer times. That is why it lands
  without a golden regeneration.
- **`get_ncn` part (b) without an early exit** (step 1): predicate
  calls 1.6-2.6x what an early exit needs, the ratio falling as M
  grows (estimated 12-19% of a cheap-problem run at M >= 3). A shadow
  computation reached the same `ncn` on every call of every run.
  **Done (step 2b).** The shadow's early exit, as measured: part (a)
  skips a pair whose point is already in `ncn`; part (b) stops at the
  first member that rules a candidate out by (i) or (ii), looks for a
  weakly dominated member only until it finds one, and evaluates (iii)
  only until then. The predicates are pure, so only each condition's
  final value matters. On the 39 counted runs every run was identical
  to the record after step 2a (solution, end seed, simcalls, every
  `get_ncn` call's input and answer), with predicate calls down 2.48x
  at M = 2, 2.34x at M = 3, 2.07x at M = 4, 1.89x at M = 5 and 1.71x
  at M = 6, and 2.3-2.5x on the bi-objective runs; `calc_delta`
  unchanged. Inside step 1's measured 1.6-2.6x, on different runs.
  `tests/test_get_ncn_work.py` plants estimates for which the work is
  exact (34 predicate calls; the previous code made 320). Two wrong
  exits (stopping once x weakly dominates a member; dropping (ii)) are
  caught by the reference test and by the counted runs (2 and 3 of 3
  runs at M = 3 differ); dropping (a)'s skip, which only costs work, by
  the count. No golden moved.

**Step 2 measured end to end (2026-10-17), at `30bfa68`.** Steps 2a,
2b and 2c together; they were not measured separately.

- *The many-objective sweep.* Its own driver, harness and problem,
  unchanged (`docs/bench_many_objective.py` and `scratch/manyobj/` from
  `many-objective` at `d959c34`, extracted, not copied into this
  branch): 240 runs, the same configurations, seeds, interleaved order,
  generator (Philox) and Python (3.14.8). Every run reproduced its
  original exactly in every untimed field the driver's own rerun check
  compares (solutions, simulations, `g()` calls, every iteration's
  visited-set analysis), except `region_calls['estimate']`, higher by
  exactly one per iteration after the first in every run: issue 19's
  warm-start check in R-MinRLE's `accel`, an `estimate_many` of points
  already estimated, which runs no simulations. 29 runs met a
  one-minute load above 1.8, in two windows from outside this work
  (13:55, 15:22-15:50); they were rerun with the driver's `retime` and
  merged with `quiet`, each rerun reproducing its original. Merged:
  highest load 1.76, CPU over wall at most 1.000. Compared with the
  original's merged runs, run for run (same seed). Medians, measured:

  | L | M | arm | R | before (s) | after (s) | saved | paired range | `get_ncn` own time (s) | `get_ncn` share before |
  |---|---|---|---|---|---|---|---|---|---|
  | 4 | 2 | A | 20 | 6.8 | 6.6 | 3% | -1 to 9% | 0.2 -> 0.1 | 3% |
  | 4 | 2 | B | 20 | 6.8 | 6.6 | 3% | 1 to 9% | 0.2 -> 0.1 | 3% |
  | 4 | 3 | A | 20 | 13.0 | 10.1 | 22% | 21 to 24% | 3.9 -> 1.1 | 30% |
  | 4 | 3 | B | 20 | 12.8 | 10.1 | 21% | 17 to 24% | 3.6 -> 1.0 | 28% |
  | 4 | 4 | A | 20 | 57.2 | 23.4 | 59% | 57 to 61% | 44.3 -> 10.4 | 77% |
  | 4 | 4 | B | 20 | 59.5 | 24.1 | 60% | 58 to 61% | 45.5 -> 10.6 | 77% |
  | 4 | 5 | A | 20 | 257.0 | 78.7 | 69% | 68 to 70% | 232.4 -> 56.0 | 90% |
  | 4 | 5 | B | 20 | 253.1 | 76.5 | 70% | 69 to 71% | 231.0 -> 56.0 | 91% |
  | 4 | 6 | A | 10 | 557.4 | 169.1 | 70% | 69 to 71% | 524.7 -> 140.0 | 94% |
  | 4 | 6 | B | 10 | 589.6 | 182.4 | 69% | 69 to 71% | 556.2 -> 152.9 | 94% |
  | 6 | 2 | A | 10 | 7.2 | 6.9 | 4% | 2 to 5% | 0.3 -> 0.1 | 4% |
  | 6 | 2 | B | 10 | 7.1 | 6.8 | 4% | -4 to 5% | 0.3 -> 0.1 | 4% |
  | 6 | 3 | A | 10 | 18.4 | 12.0 | 35% | 32 to 37% | 8.7 -> 2.2 | 47% |
  | 6 | 3 | B | 10 | 17.2 | 11.3 | 34% | 31 to 36% | 7.9 -> 2.0 | 46% |
  | 6 | 4 | A | 10 | 113.0 | 39.4 | 65% | 63 to 66% | 98.0 -> 24.4 | 86% |
  | 6 | 4 | B | 10 | 102.9 | 36.0 | 65% | 64 to 66% | 88.6 -> 22.0 | 86% |

  The whole sweep: 28,483 s of run time before, 9,605 s after (66%
  less). `get_ncn`'s own time fell 3.5-4.3x; `get_nondom`'s 34-37%.
  At M = 6 `get_ncn` is still 83% of the run (140 of 169 s): it is
  still what bounds many-objective runs, now by its quadratic size
  rather than by repeated work. The instrumented runs' wall times are
  the harness's (time mode), as in the original.
- *Step 1's own 15 runs* (budget 30,000, uninstrumented, `ncn_many.py`
  `plain` mode), rerun twice on the current code, 15 of 15 identical
  to `ncn_many_30k.jsonl` (solution, simulations, iterations, end seed,
  every iteration's |S|). Saved, by seed, both passes within a point:
  M = 2 4-8%; M = 3 21-31%; M = 4 43-48%; M = 5 56-59%; M = 6 57-61%.
- *Against step 1's estimates:* those were 10-32% (2a) and 12-19% (2b)
  of exactly these runs, about 25% together at M = 3, 35% at M = 4 and
  40-44% at M = 5-6. M = 3 is inside the estimate; at M = 4-6 the
  measured saving is larger by 10-17 points. The estimate costed only
  the `calc_delta` and predicate calls removed, at microbenchmark unit
  cost; the removed work also built a tuple per member per candidate
  and looked up `gbar`/`sehat` for it. That this accounts for the
  difference is likely and not measured. The sweep's larger savings
  (budget 300,000) follow from `get_ncn` being a larger share there
  (77-94% at M = 4-6, against step 1's 58-86%).
- Absolute times are this machine's (AMD Ryzen 5 5600X3D); the files
  are `scratch/phase7/manyobj_*_after_step2.*` and
  `ncn_many_30k_after_step2.jsonl` (scratch/phase7/README.md).

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

**Done (2026-10-17).** The profile answered the decisive question: the
3x3 matrix products were 95-97% of a general jump, and the squarings
alone, which depend only on the exponent's bit length, 76-95%; the
per-product arithmetic was 31% of each product and interpreter
overhead the rest, a factor of 3 against the chain's 10-100. Real
exponents are long and sparse (median 60-119 bits, 3-9 set). MRG31k3p
costs the same as MRG32k3a within 6%: the cost is the number of
products, not either generator's arithmetic, so both were in scope and
one change covers both. Candidate 2 (the stream factor) already
existed as the executor's base-stream cache; what each block still paid
was the offset's jump, which candidate 1 removes.

Built: candidate 1, with each set bit's power applied to the seed
vector rather than multiplied into a running matrix
(`mrg_common.PowerTable`, the general branch of each generator's
`jump_seed_n`; the cached strides and powers of two keep their paths).
The tables are built on first use and extended when a longer exponent
arrives; a worker builds its own (inherited under `fork`), about 1.7 ms
once. Bit-identical by construction (exact integer arithmetic; powers
of one matrix commute) and by test: `tests/test_jump_power_table.py`
holds it to the previous `jump_seed_n`, kept verbatim, on thousands of
exponents per generator; counts one matrix-vector product per set bit
(the previous code failed it); pins the table's growth, including that
an extension replaces the list rather than appending to it in place (a
reader on another thread never sees a partial one); and checks a fresh
interpreter builds nothing until its first general jump. Four
mutations (bit index off by one, swapped moduli, growth in place, the
wrong square) are each caught. The exact-integer and brute-force jump
tests pass unchanged. No golden moved; the 39 counted runs are
identical.

Measured (docs/hit-cost-baseline.md, "After the cheaper jump"): a
general jump 29-76x cheaper, a default-branch `hit(x, m=1)` 22-25x, on
both generators and both Pythons; cheap serial runs 5.8-6.9x faster,
BSProb 1.1x. Not re-measured: `--simpar`'s per-piece overhead, which
this was partly aimed at (docs/simpar-ceiling.md), and the
many-objective sweep (Philox, unaffected).

**What to look at next, recorded here as asked:** a default-branch
`hit(x, m)` is now one general jump (20-70 µs) plus m - 1 replication
advances at about 7 µs each, and of those 7 µs about 3.9 are
constructing the `Stream` (a `random.Random` subclass) and about 3 the
cached-matrix arithmetic. At m = 8 the advances already outweigh the
jump. The next cost on this path is Stream construction, not
arithmetic. Not proposed, only located.

**A conclusion that now rests on superseded numbers (flagged
2026-10-17, not to re-run mid-phase):** the `--simpar` sweep in
`docs/simpar-ceiling.md`, and with it Phase 4's decision to decline a
piece-count cap. That decision rested on a per-piece overhead of about
0.7 ms, against a 0.46 ms Light-tier replication, and that overhead was
the jump, which is now 29-76x cheaper. The cap question may have a
different answer, and the Light tier's slowdown at 12 workers a
different cause or none. Re-run the sweep before relying on either
conclusion, or on CLAUDE.md's "do not re-propose it without new data":
the new data is this step.

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

**Done (2026-10-17): `quadratic`, default 0, after step 5's
`bestimprove`.** Built as specified: the MATLAB's convexity tolerance,
its `int32()` (half away from zero, saturating, NaN to 0), the guard
that makes a failing coordinate 0 rather than the centre's (commented
as deliberate fidelity), one combined candidate evaluated even when it
repeats a point, and PyMOSO's strict `<` for the comparison (step 7's
audit has why). Radius 1 only; another radius is refused at
construction. On `RASolver`, so all four RA solvers take it, through
both paths to `ne`. `tests/test_ne_quadratic.py`: the cast's and the
fit's edge cases, and planted estimates in `ne`; ten mutations each
caught (one, the candidate winning ties, only after a tie test was
added). Off, no golden moved.

**The interaction with step 5, found before building:** under
first-improvement the candidate is formed only when no neighbour
improved, and then y1 >= y2 and y3 >= y2 force a >= |b|, so each vertex
is within half a step of the centre: the candidate is the centre except
at exact ties. Measured: in all 260 runs with the candidate alone,
results are identical to the reference, and every golden passes with
its default flipped. It is useful only with `bestimprove=1`.

**Measured** (`docs/ne-quadratic.md`; tables generated by
`docs/bench_ne_quadratic.py`; 13 solver-problem pairs, four cells, 20
seeds, budget 5,000; counts, not timings): with best-improvement the
candidate is a new point in only 4-10% of NE calls, and 2-18% of the
feasible new ones are taken (69% on ProbSimpleSO, an exact parabola).
SPLINE averages 1.2-1.6 NE rounds per call, so there are few
iterations to save. Quality at matched simulations shows no consistent
gain on ProbTPA, ProbTPB or ProbTPC for either toggle; the clear gain
is R-SPLINE on ProbSimpleSO. The expectation that it would help most on
the smooth TP problems is not borne out. SPLINE's nominal budget charge
is 1.4-2.0 times its counted simulations (finding 3 of step 7's audit,
measured). The measurement's first run, against the R-SPLINE with x0
re-estimation, exposed that change as a regression (step 7); the
tables are from after its reversion.

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

**Done (2026-10-17): `bestimprove`, default 0.** A parameter on
`RASolver`, so all four RA solvers take it, through both paths to `ne`
(step 7's audit). With it on, `ne` scans every neighbour against the
running best, in the same order, and keeps the first of equal bests;
at radius above 1 it scans the whole neighbourhood. The comparison
stays PyMOSO's strict `<` (step 7's audit has why). Off, nothing
changes: no golden moved, and with the default flipped four of them
fail. `tests/test_ne_best_improvement.py` plants estimates whose answer
is known under each rule; it failed before the change, and five wrong
versions (each early return kept, the general branch's break kept,
ties taking the last, the default on) are each caught. It goes first
because step 4 has nothing to work with without it (step 4).

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

**Settled: no provably safe pruning exists** (reasoning, approved). A
neighbour's part in certification depends only on its own estimate,
which a black-box oracle gives only by simulating it; points already
evaluated say nothing about it. For any neighbour there are estimates
that put it in the non-conforming neighbourhood (one strictly dominating
every member) and estimates that rule it out (one a member weakly
dominates), so skipping any can change the certified set, whatever the
order. The same holds for `remove_nlwep` and best-improvement NE;
first-improvement NE is order-dependent by construction. The one saving
already exists: overlapping neighbourhoods are unioned and `gbar`
returns a point already estimated this iteration. Anything more needs
structure the oracle does not give (a Lipschitz bound, monotonicity): a
different algorithm. No step-2 fix.

**Done (2026-10-17): measured** (`docs/neighbourhood-radius.md`; tables
by `docs/bench_radius.py`; barrier problem `scratch/phase7/barrier.py`).
- **The known answer:** an annulus t cells thick around the true
  efficient set E traps a set T that is certified at radius r exactly
  when r <= t, by enumeration on the true means; the exact check agrees
  with PyMOSO's own certificate on 1,840 of 1,840 sets (743 certified),
  and four wrong versions of it are each caught.
- **Finding: SPLINE's line search jumps a one-cell barrier at radius 1**
  (15 of 20 runs for R-SPLINE and for R-PERLE, every crossing by SPLI,
  none by NE); a two-cell one holds. The barrier the plan proposed, one
  step wide, does not trap these solvers.
- **Radius pays past a barrier the line search cannot jump:** on the
  two-cell barrier, radius 3 and above beat radius 1 in 20 of 20 seeds
  at 5,000 and 20,000 simulations for R-PERLE, R-PE and R-MinRLE (18-19
  for R-SPLINE); radius 2 is still trapped.
- **Scaling, dimensions 1-3:** construction is about 0.65 µs per point
  at every radius (timed), at most 9% of a run; estimation grows with
  the neighbourhood and is the cost; no run reached the 50x guard (most
  3.5x its budget), and a large radius shows as slower first iterations
  (at radius 5, 34-35 of 80 barrier runs had no iteration by 1,000
  simulations). Higher dimension not measured.
- **The control** (the built-in problems): no consistent effect at any
  radius.
- **Against the prediction:** "prohibitively expensive" refuted at
  dimensions 1-3; "buys nothing on the test problems" confirmed; "pays
  on the barrier" confirmed only once the barrier is thicker than the
  line search's reach.

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

**Found 2026-10-17, from the detour through random feasibility:**
- **x0 re-estimation: built, measured, reverted (2026-10-17).** R-PE
  and R-PERLE (`pe`: `upsample(aold | {x0})`) and R-MinRLE (`get_min`
  upsamples `mcS | {x0}`) re-estimate x0 every iteration and keep it as
  a candidate; R-SPLINE's warm start is the previous minimizer alone.
  The other three start an objective's search from x0, because its
  fresh estimate is better, in 1-8 of 11-15 iterations on ProbTPA at
  budget 1,000 (three seeds). R-SPLINE was made to match: re-estimate
  x0 every iteration and start from the better of x0 and the warm start
  (commit `00c3dea`, approved on the convergence argument; its golden
  moved, 1,023 to 1,009 simcalls, same solution). **Step 4's
  measurement then showed it a regression, and it was reverted, golden
  included** (the golden is back at its earlier value;
  `tests/golden/README.md`). `tests/test_rspline_warm_start.py` holds
  R-SPLINE to the reverted behaviour; it failed on the commit-4 code.

  Measured (`scratch/phase7/rspline_x0_measure.py`, output beside it;
  20 seeds, starts drawn by each tester, budget 5,000; gap between the
  true first objective of R-SPLINE's solution and the true minimum,
  median, then seeds better / same / worse with x0 re-estimation than
  without):

  | problem | at | with | without | better / same / worse |
  |---|---|---|---|---|
  | ProbTPA | 1,000 | 2.89 | 3.04 | 12 / 0 / 8 |
  | ProbTPA | 2,500 | 3.99 | 2.60 | 5 / 0 / 15 |
  | ProbTPA | 5,000 | 4.16 | 2.53 | 4 / 0 / 16 |
  | ProbTPB | 1,000 | 1.70 | 1.60 | 5 / 5 / 10 |
  | ProbTPB | 2,500 | 1.76 | 1.62 | 6 / 7 / 7 |
  | ProbTPB | 5,000 | 1.74 | 1.64 | 4 / 6 / 10 |
  | ProbTPC | 1,000 | 8.94 | 8.43 | 9 / 1 / 10 |
  | ProbTPC | 2,500 | 7.97 | 6.40 | 7 / 0 / 13 |
  | ProbTPC | 5,000 | 7.55 | 4.22 | 7 / 0 / 13 |
  | ProbSimpleSO | 1,000 | 30.50 | 0.50 | 0 / 5 / 15 |
  | ProbSimpleSO | 2,500 | 0.00 | 0.00 | 0 / 13 / 7 |
  | ProbSimpleSO | 5,000 | 0.00 | 0.00 | 0 / 16 / 4 |

  Two mechanisms, both measured. x0 and the warm start were estimated
  together, fresh, at the iteration's sample size, so the comparison was
  fair in sample size and equally noisy on both sides:

  | problem | iterations after the first | warm start not x0 | restarted from x0 | of those, warm start truly better |
  |---|---|---|---|---|
  | ProbTPA | 683 | 585 | 247 (42%) | 139 (56%) |
  | ProbTPB | 692 | 546 | 221 (40%) | 81 (37%) |
  | ProbTPC | 596 | 531 | 209 (39%) | 116 (56%) |
  | ProbSimpleSO | 840 | 840 | 0 | 0 |

  - **Noise-driven restarts** (the TP problems): about 40% of the
    iterations that had a choice restarted from x0, and in 37-56% of
    those the warm start given up was truly better. Each restart
    discards the progress since x0, and SPLINE's per-iteration budget
    is too small to recover it. **This is why R-SPLINE got worse with
    more budget on ProbTPA** (median gap 2.89 at 1,000 simulations, 4.16
    at 5,000): its runs wander near their start instead of reaching the
    minimum at (20, 10).
  - **The estimation cost** (everywhere, and the only mechanism on
    ProbSimpleSO, where x0 was never chosen): `m` simulations every
    iteration for x0, so fewer iterations within the budget.

  The framing, by decision: the convergence condition is real and
  asymptotic -- as sample sizes grow the comparison becomes reliable --
  but at finite budgets it is noise-dominated, so implementing it
  naively pays an asymptotic cost for no finite-budget benefit. The
  approval was on the theoretical argument, and the measurement says the
  argument does not apply at practical budgets. Whether the same rule
  costs R-PE, R-PERLE and R-MinRLE is not measured.

  **Speculative, not work:** a restart that requires x0 to be better by
  some margin, rather than merely better, would keep the asymptotic
  property without firing on noise. Nobody has tried it, and it is a
  different change from the one measured.
- **The finite-variance condition.** The R-SPLINE paper omits it too.
  A requirement on the user's oracle, not on the implementation.
- **`pe`'s silent filter of the warm start.** `upsample` returns the
  feasible subset, and `pe` replaces its warm start with it before
  anything else looks at it, so R-PE and R-PERLE could never report an
  infeasible warm start. **Removed.** Across the whole suite it had
  dropped 12 points (2,043 calls in 107 processes), every one an
  infeasible x0 in iteration 1 that a test passed on purpose and that
  `get_min` then reported anyway; never a warm-start point. It had been
  load-bearing for nothing but turning one clear error into another.
- **`sys.exit()` in library code: one inherited defect in two places.**
  `rperle.py` and `rpe.py` exit the process when the problem is not
  bi-objective (the same block in `pe`). R-PE inherited it from
  R-PERLE, which is how it survived Phase 2's sweep. Nothing else
  outside `pymoso/cli.py` and `pymoso/commands/` calls `sys.exit()`;
  `chnbase.py` has three more, all in commented-out code.
- **`RLESolver.spsolve` re-wraps every exception from `accel` that is
  not a `ValueError` as "Unable to run accel()".** That is the
  hide-the-error pattern again: `WarmStartInfeasible` needed a
  passthrough to get out intact, and the wrapper will do the same to
  the next deliberate error. On the list, not fixed now.
- **`rle` filters its input too.** `rle` replaces the set `accel`
  returned with its feasible subset (`upsample(mcS | {x0})`). For the
  built-in solvers every point `accel` returns was estimated feasible
  in the same iteration, so it never drops anything; for a user's
  `accel` it could. Recorded, not scheduled.

**Found 2026-10-17, preparing steps 4 and 5:**
- **NE's comparison has no tolerance.** PyMOSO's `ne` moves to a
  neighbour on a strict `<`; the MATLAB on `+ 0.00005 <` (lines 250,
  266, 298). Kept, by decision, and used for the quadratic candidate
  too (step 4). The reason is not only consistency: the 0.00005 stands
  in for a relaxation. R-PERLE and R-MinRLE compare with the real
  relaxation machinery (`calc_delta`, the relaxed dominance of
  `get_ncn`); the MATLAB R-SPLINE had none, and used a constant in its
  place. PyMOSO's `ne` has that machinery available, so carrying the
  constant over would import a workaround for a problem this code does
  not have.
- **`ne` charges SPLINE's budget for neighbours that cost nothing.** It
  adds `m` for every feasible neighbour, including one already in
  `gbar`, which `estimate` returns without simulating. The MATLAB has
  no cache, so its count is its real use; PyMOSO's is nominal. This
  biases SPLINE's count *up*, so SPLINE stops sooner and simulates
  less: it works against the overshoot of KNOWN_ISSUES.md issue 16,
  not toward it (that overshoot comes from the budget being checked
  only between RA iterations, and from `get_ncn`'s neighbourhood
  estimates, which SPLINE's budget does not cover). A bias the other
  way exists too: a neighbour that proves infeasible has its
  replications run and charged to nothing (issue 16's last paragraph,
  rng-interface-design.md §11 entry 13). The net is measured, not
  argued, in step 4's measurement (nominal against real per SPLINE
  call).
- **Four solvers reach `ne`, by two paths.** `RASolver.get_min` calls
  `spline` (R-PE, R-PERLE, R-MinRLE), and so do R-PE's and R-PERLE's
  `pe` and R-SPLINE's `spsolve`. A solver parameter on `RASolver`
  reaches every one; `tests/test_ne_best_improvement.py` checks each
  path sees it.
- **The MATLAB's NE is radius 1 only.**

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

**Write what an `Oracle` must guarantee deliberately, as one section,
rather than letting it accrete.** Phase 7 found three requirements
nothing states, in two days: that the oracle's estimators are strongly
consistent; that the objectives have finite variance; and, for the RLE
family and R-SPLINE, that whether a point is feasible depends on the
point alone. The point contract (Phase 4) and the per-replication draw
limit (Phase 6) are already stated, in `Oracle`'s docstring and the
README, and belong in the same place.

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
  All three done (2026-10-17), each identical on the counted runs.
  Measured together end to end the same day (step 2, "Step 2
  measured end to end"): 21-35% of a run saved at M = 3, 59-70% at
  M = 4-6, on the many-objective sweep's own 240 runs.
- ~~Random feasibility: refused and documented.~~ Withdrawn
  2026-10-17 (step 1b's decisions). In its place, in this order:
  issue 18 withdrawn with these plan entries; `WarmStartInfeasible`
  with issue 19; `pe`'s filter removed; R-SPLINE's x0 re-estimation
  with its golden (reverted later the same day, golden included, after
  step 4's measurement: step 7, "x0 re-estimation"); then step 2b.
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
