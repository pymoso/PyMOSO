# PyMOSO

Python package for multi-objective simulation optimization. Originally a
PhD output (Cooper & Hunter 2018), now being modernized on the `dev-2.0`
branch, checked out at `/srv/projects/PyMOSO` and pushed to `origin`.
Phases 0-7 are complete; what remains is the 2.0.0 release itself.

## Canonical repository

github.com/pymoso/PyMOSO — remote `origin` in this checkout.
HunterResearch/PyMOSO was a stale snapshot and is now archived; the
`stale-fork` remote that pointed at it was removed in Phase 0 of the
2.0.0 work. `remote.pushDefault` is set to `origin` explicitly. This
file is tracked in git; edits to it are commits.

1.1.0 is released on PyPI from the `release-1.1.0` branch and tagged
`v1.1.0`. `master` is `v1.1.0` plus five CI and test-only commits
(2026-09-22, Windows/macOS CI); no `release-1.1.0` branch is on
GitHub. Decided in Phase 6: `dev-2.0` becomes the default branch and
`master` stays where it is as the 1.1.0 record -- no merge. Version history before that is
inconsistent upstream: `pymoso/master` installed as `1.0.7` while PyPI
had `1.0.8`, so that released wheel corresponds to no commit — the
INFORMS archival snapshot (github.com/INFORMSJoC/2019.0902) is 1.0.8
plus an uncommitted version bump.

## Version boundary: 1.1.0 released, this branch at 2.0.0 development

1.1.0 was released from `release-1.1.0`, branched at `b637a3e`.
Everything after that commit on this branch is 2.0.0 development;
`pymoso/__init__.py` reads `2.0.0.dev0`.

What makes the line major: the `--seed` CLI syntax change (one
comma-separated token, replacing six space-separated values),
`Oracle.bump()`'s removal, the solver-facing `crn_*` surface's
removal, and (Phase 7) **the relaxation formula fix, which changes what
a `betaeps`/`betadel` value a user already sets actually means** — all
landed after `b637a3e`, none shipped in 1.1.0.

The two branches differ in content, not just version. `release-1.1.0`
excludes the two example solvers entirely; this branch has them committed.
Don't assume a diff between them is only the commits between them.

`KNOWN_ISSUES.md` numbering: Phase 0 remapped this branch's citations
to match the file's own headings, which already used release
numbering for issues 1-9. Numbers diverge from 13 on — this branch has
14 = `bump()` removal, 15 = `--simpar` exception hang (deliberately out
of sequence, do not renumber); release has 14 = the example solvers'
exclusion. Nine citations to a dropped old issue 2 still dangle on both
branches. Don't merge `KNOWN_ISSUES.md` textually between branches.

## Critical context

- **The relaxation formula changed and it is silent: 2.0's `beta = 1.0`
  reproduces 1.1.0's `beta = 0.5`.** See the Phase 7 section below. A
  1.x user who sets `betaeps` or `betadel` and upgrades gets different
  results with no error and no warning. Nothing else in the release has
  that property — the audit fixes, `testsolve`'s stream layout and the
  one-dimensional search limit also change results silently, but none of
  them changes the meaning of a value the user supplies.
- **`TPxTester.soln` holds decision points, not objective images, and
  `soln_images` is new (Phase 7).** Images are computed at metric time
  so that both sides of the comparison use identical arithmetic; a run
  that finds the whole reference set now scores exactly 0 rather than
  ~1e-15. A subclass that replaces `soln` or `true_g` must recompute
  `soln_images`. T_C's reference is the published collection of 516
  N_1-LWESs, committed as a Python literal — see the Phase 7 section.
- **The end seed's scope changed in step 8 — the older "allocation
  schedule only" warning is superseded.** It now reflects the run's
  actual consumption via a computed high-water mark, so it
  distinguishes runs that previously reported identical values. It
  still does not fingerprint *which* values were drawn: a change to
  replication-level consumption can leave every golden green, verified
  the hard way when `getrandbits()` demonstrably changed which `x0`
  values `choice()` picks and 0 of 10 goldens moved.
  Consumption-sensitive coverage lives in
  `tests/test_rng_consumption.py` (a recording RNG) and
  `tests/test_solution_sensitivity.py`. `docs/end-seed-scope.md` has
  been corrected twice as the thing it describes changed underneath it
  — read it rather than assuming either version. **It now carries nine
  instances, the ninth being measurement and analysis scripts rather
  than tests:** a script's label and what it computes can diverge the
  same way a test's name and its assertion can.
- Golden baselines in `tests/golden/` have been deliberately
  regenerated several times: after the jump-ahead fix, after step 4b's
  non-CRN cutover, after the replication-spacing collision fix, after
  both stages of step 8's endseed rework, and after Phase 1's
  `testsolve` role-layout fix. NEVER regenerate or edit them without
  being asked. Superseded values are preserved in
  `tests/golden/README.md` with the reason for each move.
- The RNG fix changes numerical output deliberately: end seeds and
  per-run solution values from 1.x will not reproduce bit-for-bit. This
  is an implementation fix, not a correction to the published
  convergence theory. See `KNOWN_ISSUES.md` issue 1.
- README code blocks are generated from files under `pymoso/examples/`,
  and tests assert byte-identity. Files are the source of truth; edit
  the file and regenerate, never the README block directly. Same for
  the CLI help and `listitems` blocks, generated from live parser
  output.
- Docstring style differs from `release-1.1.0`'s. Leave it alone —
  converting would collide with the byte-identity assertions.
- **`docs/reference/` holds prior-work provenance, and nothing in the
  package loads any of it at run time.** Two 2018 pickles for T_C
  (`lescombos.pkl`, `exples.pkl`) and the two seed pools
  (`orcseeds.pkl`, `solseeds.pkl`, each with a plain-text form that
  round-trips). Its `README.md` has every SHA-256, the reversed
  (oldest-first) mrg32k3a state convention and the chain structure.
  Read the text forms, not the pickles.
  `tests/test_reference_files_not_shipped.py` keeps them out of the
  sdist and wheel; its docstring names what that check does not catch.
- **The 2018 experiment code lives at `/srv/projects/old_rperle-2018/`,
  outside the repo, and is NEVER executed, imported, ported or fixed.**
  It is a referent. It was hand-edited between experiments — functions
  commented in and out, numbers changed — so its state is evidence of
  what the algorithms did and NOT of how any published experiment was
  configured. It is also already preserved in a private lab-org GitHub
  repository, so it is not at risk here.

## Fixed on this branch

Jump-ahead float precision loss (exact integer arithmetic, permanent
brute-force tests); bare `except:` swallowing tracebacks; library code
calling `sys.exit()` instead of raising; missing kwarg defaults in
`chnutils.solve`/`testsolve` (the documented library API had never
worked); infeasible-`x0` reporting; `--simpar` worker leak on the error
path (Oracle is a context manager now); docopt replaced with argparse,
zero runtime dependencies; ten documentation defects in example code;
multi-file custom problems failing to load (`sys.path` never included
the user file's directory — broken in every released version);
source-bundle transport so `--simpar` works under forkserver; CPython
`random.Random` internals removed, runs 3.10-3.14.

**Phase 7's algorithm fixes,** all from `docs/algorithm-audit.md` and
all changing numerical output: the relaxation formula (finding 2, the
big one, below); PE's traceback reading the wrong objective's intervals
(1); PE's LWEP filter applied to the wrong set (3, with the `{x0}` step
left alone by decision); SPLI's line search flooring instead of
rounding (4); SPLI not stopping at an infeasible point (5); PE breaking
objective ties deterministically (7); `get_biparetos` dropping exact
ties, now `get_nondom` (8); `b_nu`'s `(dim - 1)` factor giving 0 at
d = 1 (9, fixed at d = 1 only — see the Phase 7 section); `sys.exit` on
three or more objectives (10, with the objective count itself left to
the user by decision); SPLINE stopping at `n >= b` rather than `n > b`
(14). Also in Phase 7: `ProbTPC`'s neighbour enumeration cost, the
cheaper MRG jump (step 3), `ProbTPB`'s objective order reversed to
match the paper's `g1` (linear) and `g2` (front), and `pe`'s silent
filtering of an infeasible warm start replaced by a `WarmStartInfeasible`
invariant — a warm start cannot be infeasible for these algorithms, so
filtering hid a bug rather than handling a case.

RNG redesign, steps 1-8 of `docs/rng-interface-design.md` §12, all
landed: conformance suite; `prng/base.py` protocol and
`prng/mrg_common.py` generalized matrix-power jump; `Oracle`'s CRN
protocol replaced with coordinate bookkeeping; `visit=`/`sync=`
mechanism; non-CRN default cutover with `MAX_RI` removed entirely;
`endseed` as a computed high-water-mark guarantee on both `solve()` and
`testsolve()`; MRG31k3p and Philox-4x32 onboarded; `stream_at` split
into `(stream, offset)`; step 6c-completion, giving Philox its own
118-bit offset-assembly budget (`point_width`/`offset_within_iteration`
now take the budget as a parameter, `philox4x32.py` supplies its own
72/4/30/12 figures) instead of silently reusing MRG-family's 127-bit
one, which `stream_at`'s own bounds check (against the raw 128-bit
counter, not the declared capacity) let through with no error at all.
Mechanism only at that point — step 6b (below) is what threaded a
selected backend through `chnbase.py::Oracle`'s own internals
(`_hit_via_coordinate`/`crn_advance`/`_advance_replication`/
`get_endseed`/`_touch_coordinate`, all previously hardcoded to
`.prng.mrg32k3a` at module scope) and `chnutils.solve()`/`testsolve()`'s
own `generator=` kwarg, making MRG31k3p and Philox both genuinely
usable for real, non-CRN solving — not just conformance testing.
Required three new Stream-protocol methods across all three backends
(`advance`/`raw_consumed`/`root_seed`) and a `Philox4x32Stream`
constructor change (`(key, counter)` as one argument, matching the MRG
family's own shape) so `--proc`'s worker reconstruction works
generically. `--crn`/`sync=` stay MRG-family-only, raising a named
`NotImplementedError` rather than reaching broken coordinate math — see
"Still in flight" below for the CRN-branch convergence that would close
that gap. `--seed` itself now takes one comma-separated token
(`--seed 1,2,3,4,5,6`), not the old space-separated form — `nargs='+'`
was tried first and found to swallow the required positional arguments
that follow it (docs/rng-interface-design.md §3.7's own correction
note has the full account); this is a visible CLI syntax change,
mirrored across the README/`EPILOG` examples. Two more bugs found
running real Philox scenarios end to end, not hypothetical: built-in
testers'/problems'/the example solvers' own `choice`/`expovariate`/
`sample` calls need the full `random.Random` surface Philox's own
Stream deliberately doesn't provide (`RandomCompatAdapter`, §3.6,
finally wired in via `pymoso.prng.base.ensure_random_compatible`, a
no-op for the MRG family); and `RandomCompatAdapter` itself didn't
pickle, hanging `--proc` runs (a forkserver-pickling-error hang,
KNOWN_ISSUES.md issue 7's own failure class, new cause) until given a
`__reduce__`. Default path (no `--generator` given) unaffected
throughout — confirmed directly, full suite green on both venvs, no
golden moved.

`Oracle.bump()` removed outright (step 6b, landing ahead of the rest of
that step): no in-tree callers, no test coverage beyond pinning its own
leftover behavior, duplicated `hit()`'s replication loop. Migration for
an out-of-tree caller: `hit()` with the same arguments returns
aggregated stats; raw per-replication access returns with the executor
rework. See `KNOWN_ISSUES.md` issue 14.

Two defects found and fixed within that work, both introduced by it and
never released: a replication-spacing collision (step 4b packed
replication with stride 1, so replications shared draws — `obse` was
computed over non-independent samples), and the carry-rule proof that
surfaced `SYNC_ROLE_OFFSET > ISP_STRIDE`, meaning `sync=` and multi-path
`testsolve()` were never compatible.

## Phase 7 (pre-release: runtime, algorithm audit, documentation)

Added as a pre-release prerequisite after Phase 6: runtime polishing,
runtime optimization, and a thorough algorithm complexity and
completeness check. Steps 1-8 are complete. `docs/phase7-plan.md` is
the plan, `docs/algorithm-audit.md` the findings.

### The relaxation formula

**`se/pow(m, beta)` became `se*pow(m, 0.5 - beta)`,** the preprint's
`delta = se_hat * n^(1/2 - beta)`. With `se` being `sigma_hat/sqrt(m)`,
the old form delivered `sigma_hat * m^(-1/2-beta)` and the new one
`sigma_hat * m^(-beta)`. **2.0's `beta = 1.0` reproduces 1.1.0's
`beta = 0.5`,** for both `betaeps` and `betadel`.

**The defect was inherited, not introduced here.** The 2018 experiment
code that produced the published figures has the same `se/pow(m, beta)`
in its `fse` and `calc_delta`, and its `Oracle.hit` returns
`sqrt(variance)/sqrt(m)`. PyMOSO carried it forward. The dissertation
states the intent that code violates: at `beta_eps = beta_delta = 0.5`
it says the search is for points "more than one standard error away",
which the old formula divides by a further `sqrt(m)`. Audit finding 2's
first resolution attributed the defect to PyMOSO's assembly and has
been rewritten; `docs/relaxation-sweep.md`'s 2026-10-19 withdrawal was
reinstated as a consequence.

**`beta = 0.5` is derivable, not a best guess.** Pasupathy (2010), "On
Choosing Parameters in Retrospective-Approximation Algorithms for
Stochastic Root Finding and Simulation Optimization", *Operations
Research* 58(4, Part 1 of 2), 889-901. The corrected relaxation at
`beta = 0.5` is `sigma_hat/sqrt(m)`, which is that paper's §5.3
recommended `eps_k = K/sqrt(m_k)` with `K` estimated from data, and
`m_nu = ceil(2*1.1^nu)` is its Table 1 linear growth with the paper's
own constant (both p. 897). Theorem 7 (p. 896) puts a floor at
`beta >= 0.5`: below it `MSE(X_k)/MSE(X*_k)` diverges. Theorem 8 and
Figure 2 (pp. 896, 900) say a faster-converging tolerance leaves the
MSE rate unchanged, so `beta > 0.5` is the no-gain regime the
introduction calls oversolving (p. 890). Conditions C.1-C.3 are p. 894;
§5.2's `0 < limsup eps_k*sqrt(m_k) < infinity` is p. 896. **Two caveats
that must travel with this:** `delta` is a relaxation inside a
dominance test, not literally `||X_k - X*_k||`, so the match is of
functional form and role, not an identity; and §8(ii) (p. 900) notes
the theory assumes i.i.d. sample paths, so none of it is derived in the
CRN setting.

**Measured consequence, and it is counter-intuitive: a tighter
relaxation returns LARGER sets.** At both betas 1.0 against the
default, median returned-set sizes were 50 against 15 on T_A, 51
against 41 on T_B, 9 against 7 on T_C.
`docs/beta-sweep-reference.md`, "Returned-set sizes". A threshold below
the noise floor treats sub-noise differences as real and pulls spurious
points in.

### The T_C reference sets

`TPxTester.soln` holds decision points; `soln_images` is new. T_C's
reference is the published collection of **516 unique N_1-LWESs
containing 73 distinct points**, from the 2018 `lescombos.pkl`,
converted once with a restricted unpickler and committed as a Python
literal. Construction images the 73 distinct points once for all 4,273
instances. `docs/reference/tpc-reference-sets.md` is the record.

What that document establishes, and what the tester's comment must keep
saying:

- The 516 image-collapse to 66 distinct image sets and 43 distinct
  images; one image set is the image of 45 different point sets. The
  metric depends only on the 66, which is why the choice of point
  representation is metric-neutral (verified bit-identical over 9,709
  solution sets).
- The integer-to-original coordinate mapping is `0.5*k`, not
  `-5 + 0.5*k`.
- **The 516 are not every N_1-LWES as point sets.** 119,392 point sets
  with the same image sets satisfy the set-level definition; the 516
  are what the appendix's level-1-through-8 union procedure reaches.
  Mirror pairs are never neighbours of each other, so which member a
  set holds is nearly free, and the published collection is not closed
  under mirroring. The appendix does not overclaim: it says "found in
  this manner".
- **512 N_1-LWEPs against 73 points in the sets is expected, not a
  discrepancy.** An LWEP is weakly efficient against its own
  neighbourhood only; an LWES must satisfy the set-level closure
  condition, so a point can be an LWEP and belong to no LWES. Today's
  `true_g` reproduces the appendix's 512 exactly, out of 9,261 feasible
  points.
- **Image-set completeness is not established and cannot be
  established from here.** Say so.
- Six T_C images from the 2018 work remain unreproducible. The standing
  hypothesis is a different libm on 2014-era hardware, and that machine
  is gone.

### What the published T_C figure actually shows (findings 2b, 2c)

Chased to verify algorithm correctness and to confirm 2.0 performs at
least as well as the 2018 figures, not to produce new plots. Both
purposes are satisfied. Closed by decision; **do not reopen the
ablation.**

- **The published x-axis counts estimate calls x m, not simulations
  (finding 2b).** The 2018 `estimate()` charges `m` on every call,
  cache hits included; 2.0 charges only when it simulates. Under 2.0's
  call pattern the ratio is median 5.34, range 4.40-6.51 across 100
  paths, drifting 4.9 to 5.4 with budget. **The true 2018 ratio is
  unmeasured**, because that code is never run, so no document may say
  the published figures overstate cost by 5.3x. It applies to the
  R-PERLE family only — MO-COMPASS's `update_gbar` charges only the
  replications it runs — so the figure puts two counting conventions on
  one axis, and the bias runs against R-PERLE, making the paper's own
  comparison conservative.
- **The plateau is the relaxation (finding 2c).** Published R-PERLE
  settles at 0.43038, which is the complete global image set plus one
  spurious off-front point; corrected 2.0 settles at 0.64559, the
  global set minus `(-2,-2,-2)`. Overshoot against undershoot, the
  two directions of the formula. The old-formula emulation reproduces
  the plateau state and the upper-quartile level, and the accounting
  explains the upper quartile's timing.
- **What is NOT explained:** the overshoot frequency, 27 of 100 against
  at least half published. Five candidate causes are listed in the
  audit and none was ablated, by decision. The lower quartile's timing
  would need a factor of about 15.7 and the upper about 7.5, against a
  measured range of 4.40-6.51, so no single accounting factor
  reconciles both.
- `(-2,-2,-2)` sitting outside a certified set is **designed
  behaviour**, not a defect: RLE certifies the sample-path ALES through
  the non-conforming neighbourhood, and the dissertation names `delta`
  the completeness function precisely because it permits neighbourhood
  points that violate the sample-path LWES definition. The point
  conforms by (b)(iii) until `m` passes about 13,600 (population
  variances), which a 4e6 budget never reaches.

### Reconstruction

`docs/reconstruction-spec.md` is everything needed to reproduce the
2018 experiments, captured while it was in hand. Seed-pool structure
(two dicts keyed 0..4999, one contiguous chain of 10,000 states, jump
`A^(2^77)`, oldest-first storage, 2^77 being two of L'Ecuyer's
substream spacings and neither canonical constant — the jump bug, and
harmless at ~1.5e23 draws between seeds); the driver's `indepseeds`
semantics, `x0` generation from `(12345,)*6` re-seeded per scenario,
`inc = 10000` and `floor(n*q)` quantile indexing; the configuration
equivalences; the budget accounting; Figure 9's extracted targets; and
what cannot be matched.

**A reconstruction rewrites the analysis rather than porting it.**
Three defects were found in that analysis path: `gen_hddata` picking
the first iteration whose count *exceeds* the grid point rather than
the last at or below it (so published curves are optimistic, which
widens the timing gap rather than closing it); `hausdict = hlst1.sort()`
storing `None`; and the cache-hit charge above.

**No run-for-run pairing with the published runs is possible.** End
seeds moved, draws per replication differ (five in 2018, three in 2.0 —
`z4` and `z5` were drawn and discarded), and the `x0` integer mapping
differs between the two `MRG32k3a` classes. All comparison is
distributional.

### The measurement run directory

`/srv/projects/pymoso-runs/rperle-4e6/` is **frozen at the `52053c6`
API** and recorded as such in its own README. Its scripts read `soln`
as images and are correct only under the pinned venv; they were not
retrofitted, because they record what was measured then.
`analysis/AUDIT.md` lists ten places where a script's label and what it
computes diverge, five of which bore on conclusions.

### Step 8: user-facing documentation

The README gained an oracle contract (what PyMOSO enforces, what it
assumes, and the consequence of breaking each), a "Configuring a run:
what was measured" section covering time and parallelism, CRN and
neighbourhood radius with every figure naming its source document, a
testers section for `soln`/`soln_images`, and the `beta` conversion
beside the parameter table. `KNOWN_ISSUES.md` opens with "Open in
2.0.0: does an issue affect you?". Every claim without a test is listed
in `docs/unverified-claims.md` with the document behind it.

**Register, for anything added later:** the audience is users, not
reviewers, and not necessarily developers. Guidance comes from a
measurement with the measurement named; where nothing was measured, say
nothing. Do not explain the convergence theory. Do not police what
algorithms users try on which problems, and do not present defaults as
tuned for the test problems.

## Known open items

- **`b_nu` above two decision variables is a design decision with a
  recorded reason, not a divergence to fix (finding 9).** The papers
  state `ceil(8*1.2^nu)`; the 2018 code and PyMOSO both use
  `8*(dim-1)*1.2^nu`, so they agree at d = 2 and differ above it —
  twice at d = 3, four times at d = 5. The author's account: "we needed
  the higher limit for T_C because spline searches were stalling out
  too early with the extra dimension but no additional line search
  budget. So we quickly came up with the formula you see in the code."
  `b_nu` is not required for convergence or for the convergence rate;
  it is an implementation artifact that keeps the whole budget from
  being spent on one unlucky sample path, so scaling it changes
  finite-sample behaviour and nothing asymptotic. Corroborated
  externally: Pasupathy (2010)'s conditions involve only the
  sample-size and error-tolerance sequences, and `N_k`, the points
  visited per iteration, is `O_p(1)` under polynomial convergence (§5,
  equation (2), p. 895). Users matching the papers set
  `bconst = 8/(d-1)`; that setting is read from `calc_b` and is not
  tested. Left unchanged.
- **Open in the audit and not resolvable from the papers:** 6 (PLI's
  gradient uses vertices violating the epsilon constraint), 11 (Min
  adds SPLINE's trajectories to its output), 12 (R-MinRLE may start a
  minimizer's search from `x0`), 15 (SPLI charges a full simplex
  whatever it cost — note this never touches `num_calls`; the budget
  gap is issue 16), 17 (the MATLAB's tolerances and caps). Finding 13
  (PE's traceback step of 1e-6 when the standard error is 0, vanishing
  at about 3.4e10) is documented as an implementation necessity with a
  hazard, computed and never observed, and is named in the oracle
  contract because a zero-variance oracle is what reaches it. Finding
  16 (the listings say "with CRN" while PyMOSO defaults to no CRN) is
  documented and deliberate.
- **`--budget` undercounts, two ways (issue 16):** replications of a
  point that turns out infeasible are run and never counted, and the
  budget overshoots. This is PyMOSO's own gap and is separate from
  finding 2b, which is about the 2018 code's axis.
- **Closed (Phase 3):** `testsolve`'s `--proc` path shipped live,
  seeded Oracle instances and hung under forkserver. A sample path is
  now data (`chnutils.PathJob`), rebuilt in the worker; tester and
  solver classes travel as `executor.ClassRef` (source bundle for user
  files). `--proc=1` and `--simpar=1` start no worker process at all.
  KNOWN_ISSUES.md issue 7 has the table of what each of the five old
  xfails actually was: one README example had never failed, and two
  went green from the in-process path rather than from transport.
- **Closed (Phase 3):** one worker lifecycle, `pymoso/pool.py`
  (`WorkerPool`), under `--simpar`, `--proc` and metric computation.
  `Process` plus one pipe per worker, not `ProcessPoolExecutor`
  (no public way to kill a worker mid-`g()` before 3.14) and not
  `multiprocessing.Pool` (waits forever on a dead worker). Exception in
  a worker (issue 15), dead worker, and killed parent (issue 8) are
  each handled and tested under fork, forkserver and spawn on Linux.
  Two things to know before touching it: everything sent to a worker
  is pickled even under fork, deliberately, so nothing works by
  inheritance on Linux and fails elsewhere; and a forked worker must
  close the parent's pipe ends it inherited (`_PARENT_ENDS`) or it
  never sees the parent die -- that one passes under forkserver and
  spawn and fails only under fork.
- **Follow-up, not built (polish on an error path; Phase 3 is
  closed):** when a task's result will not pickle, `WorkerPool.run`
  raises whatever CPython's pickle raised in the worker -- the type
  and the wording both differ by Python version, and the task is
  named only because CPython's message happens to quote it. The pool
  should name the task function in the error itself. Small change to
  `pymoso/pool.py`'s `_worker_main`; it makes the message ours, and
  only then may
  `test_an_exception_or_result_that_cannot_travel_is_still_reported`
  assert on it. Until then tests assert these errors by type
  (`CANNOT_PICKLE`) and structure, never by message -- a
  `match="pickle"` passed on 3.10, 3.11 and 3.14 and failed on 3.12
  and 3.13.
- **Issue 8 is bounded, not gone, for a busy worker:** a worker whose
  parent is killed finishes the task in hand before exiting. For a
  long `--proc` path that is the whole path.
- **macOS and Windows are verified by CI only.** Nothing in Phase 3
  was run on either locally; the parent-kill test's Windows liveness
  check (ctypes `OpenProcess`) in particular has never executed
  anywhere but a runner.
- Dispatch: `--simpar` divides every executor call's replications into
  at most `workers` even chunks; `--proc` sends one task per path.
  What bounds `--simpar` is the solver's call pattern, not dispatch --
  `docs/simpar-ceiling.md`, which now carries two corrections to that
  story and should be read before proposing any speedup work.
- **Cheap simulations at high worker counts: partly real, partly
  unestablished, and a piece cap was measured and declined.** The
  pool cuts every call into one piece per worker and each piece pays
  its own ~0.7 ms jump, against a 0.46 ms Light replication. At 12
  workers (6 cores) the Light tier is slower than before the pool
  (1.64x -> 1.27x on 3.14), consistently. At 6 workers the measured
  drop (1.71x -> 1.53x) is most likely noise: two runs of the same
  code on an idle machine at the end of Phase 4 gave 1.59x and 1.78x,
  straddling both figures, and no piece cap improves on six pieces
  there. The evidence favours noise; the interleaved before/after
  comparison that would settle it was never run. A measurement-driven
  cap was proposed and not built -- it cannot fix 6 workers, only
  partly fixes 12, and makes dispatch timing-dependent. The sweep and
  the reasons are in `docs/simpar-ceiling.md`; do not re-propose it
  without new data. The overhead itself is the problem, so the
  cheaper jump (rng-interface-design.md §11 entry 14) is the
  better-motivated fix. Moderate and Heavy are unaffected.
  **Phase 7 step 3 landed that jump** (20-70 µs on 3.14, from ~0.7-2
  ms; `docs/hit-cost-baseline.md`). The `--simpar` sweep has not been
  re-run, so the Light-tier figures above are the old code's, and the
  piece cap's decline rests on the 0.7 ms per-piece figure that step
  superseded (docs/phase7-plan.md, step 3).
- **Behaviour change to record in the CHANGELOG (Phase 6):**
  `testsolve(proc>1)` (and `simpar>1`) with a class defined in a
  notebook cell, a REPL or inside a function worked under fork, and
  since Phase 3 raises `ValueError` under every start method.
  **Closed for anyone with cloudpickle (Phase 4):** `pip install
  pymoso[notebook]` and such a class is sent by value. Without it the
  `ValueError` stands and names the extra. So the CHANGELOG entry is
  "needs the `notebook` extra", not "no longer works".
- **Closed (Phase 4): Spark, and notebook-defined classes.**
  `docs/spark-backend.md` is the record and, until the Phase 6 README
  rewrite, the only user documentation for either. What to know
  before touching it:
  - A *backend* (`pool.LocalBackend`) hands out the pool. The seam is
    the pool and not `Executor`, because sample paths never went
    through `Executor.run`. `solve`/`testsolve`/`par_diff` take
    `backend=`.
  - `pymoso/backends/remote.py` has no Spark in it and is tested in
    all fifteen cells with a fresh-interpreter backend;
    `backends/spark.py` is one method. It uses `spark.range()` and a
    UDF **because a Spark Connect session has no `sparkContext`**
    (verified locally). That Databricks serverless/shared clusters
    are Connect-only is from memory, NOT checked against a runtime.
  - `ClassRef` has three forms: by reference, source bundle, by value
    (cloudpickle). `remote=True` sends everything outside pymoso by
    value: "pickles in the parent" proves nothing about another
    machine, and that -- not a shared filesystem -- was the real gap.
    The source bundle ships text and never needed a shared
    filesystem; an earlier brief said otherwise.
  - **Replication-level dispatch to Spark (`solve(simpar=N,
    backend=)`) loses or breaks even on cheap replications and tops
    out at a few times faster.** Measured on three Databricks
    clusters: 0.4-1.0x at 20-28 ms per replication, 1.7-2.9x at
    83-112 ms, 3.6-4.4x at 0.4-0.5 s, 4-6x at 1.5-1.7 s. "Roughly
    100 ms or more" is still the rule given to users. `simpar` above
    6 gained nothing until a replication cost over a second. Offered
    because it is the only thing that helps a single `solve()`. Do
    not "optimize" it without re-reading `docs/simpar-ceiling.md`:
    the ceiling is the solver's call pattern, and the cluster runs at
    `simpar=6` sat just under their computed bounds.
  - **A backend does not judge whether dispatching was worth it, by
    decision.** A run-time warning for losing dispatch existed in the
    Phase 4 commits and was removed before release: it measured task
    work over wall time (the flaw behind the bogus 9.55x), stayed
    silent on the one cluster run it existed to catch, and second-
    guessed the user's compute decisions unasked. Do not re-add it or
    anything that runs work the user did not ask for in order to
    advise them. For the CHANGELOG (Phase 6): it never shipped, so
    its removal is not a user-facing change, but the Phase 4 commit
    messages mention it. A user-called measurement is the intended
    replacement (proposed, not built).
  - A task checks `pymoso.__version__` against the sender's;
    confirmed raising on a real cluster.
  - **Multi-host bit-identity is ESTABLISHED across hosts of one
    platform only: Linux, x86-64, glibc 2.39 and 2.41, which may be
    the same `log`/`pow` implementation.** Never across platforms:
    macOS and Windows produce different bits (KNOWN_ISSUES.md issue
    17, the test that failed there), so this result says nothing about
    them. Same *results* across platforms, not bits, is a separate
    measurement (2026-11-16, issue 17): four platform-architecture
    combinations, margins of 4e10 or more. (It was the open
    correctness question.) Three Databricks
    runs, 26/27/28 of 26/27/28 checks: every float identical across
    three executor hosts, between Broadwell and Skylake drivers and
    Ice Lake executors, and against this AMD machine on a different
    glibc and Python. **Still not verified:** non-x86 executors,
    another libc, mixed CPU models among one run's executors,
    serverless, Spark Connect on Databricks (all three runs were
    classic sessions; the Connect claim is still from memory), more
    than three hosts, and any scaling curve on a cluster of fixed
    size -- the clusters autoscaled, so the sample-path numbers
    (3.4x on 8 vCPUs, 6.5x on 16, 9.8x on 24) are lower bounds.
- **pyspark 3.5 (the declared floor) is verified in classic mode:**
  3.5.9 locally and 3.5.2 on Databricks 16.4. Not under Connect.
- **A source install has to build under the setuptools a user already
  has.** `pip install git+...` failed on a Databricks runtime: pip
  there builds without isolation, so `[build-system] requires` is
  ignored and an older setuptools rejected `license = "MIT"`. The
  license is now the table form and the floor is `setuptools>=61`
  (`tests/test_packaging.py`). Current setuptools warns that the
  table form ends 2027-02-18; switching back then brings the failure
  back for old environments, so it is a decision, not a tidy-up.
- **Two corrections to recorded decisions (Phase 4),** each noted
  where the original was written: by-value transport is a form of
  `ClassRef`, not a `ProblemHandle` subclass (that plan predates
  testers and solvers travelling); and cloudpickle is its own extra,
  `notebook`, which `spark` depends on, not part of `spark` only.
- **numpy was measured and not adopted -- a result, not a deferral.**
  `docs/numpy-findings.md`. 78-86% of a cheap serial run on the MRG
  family is the modular matrix jump, which numpy cannot do exactly;
  numpy aggregation differs from `statistics` in over half of samples,
  so it would move solution values, and is slower than a plain loop at
  RA sample sizes; Philox already makes the jump free (1.1 µs against
  1.6 ms; the MRG family's is 20-70 µs since Phase 7 step 3). The `numerics` extra is empty on purpose. The one candidate
  is bulk variate draws inside a user's `g()`
  (rng-interface-design.md §11 entry 16). Do not re-propose numpy for
  the framework's own arithmetic without data that contradicts that
  document.
- **Closed (Phase 4): four notebook usability defects,**
  `tests/test_library_arguments.py`. For the CHANGELOG, because each
  changes what a call does:
  - An unknown solver parameter raises `TypeError` naming it and
    listing the accepted ones (it was silently ignored).
    **A custom solver that calls `super().__init__(orc, **kwargs)`
    before reading its own parameters from kwargs now raises**; it
    must pop them first, as every built-in does.
  - **`PARAMS` is new public API for solver authors, and the
    CHANGELOG should present it as an addition, not only as the
    source of that break.** A solver class lists the parameter names
    it takes in a `PARAMS` tuple; `chnbase.accepted_params(cls)`
    merges them up the class hierarchy, and
    `chnbase.reject_unknown_params(self, kwargs)` is what a solver
    that does not derive from `RASolver` calls after taking its own.
    A custom solver that declares `PARAMS` gets its parameters named
    in the error, and (below) in any generated documentation.
  - `x0` is converted to a tuple and checked against the problem's
    dimension at the call (`chnutils.starting_point`). **Numbers pass
    through unchanged, by decision:** an integer-only rule and an
    auto-conversion of floats were each written and each withdrawn.
    Only non-numbers are refused there.
  - **The point contract (Phase 4, decided): a point is a tuple of
    numbers and the oracle decides feasibility, identically with and
    without `--crn`.** `prng.base.canonical_point` encodes a point by
    value: a whole number of any numeric type is its integer (so
    `30.0` and `numpy.int64(30)` share `30`'s streams); a non-whole
    number is hashed on its exact value and handed to `g()`; a point
    with a nan, an infinity or a non-number has no coordinate and
    `Oracle.hit` reports it infeasible without calling `g()`, in both
    modes. Before this the default mode crashed on every one of those
    (a numpy integer overflowed in the point code; a float failed in
    the generator's jump) while `--crn`, which never encodes the
    point, ran them. It was the numpy *type*, not magnitude: plain
    Python ints up to 10^30 were checked and always worked. Integer
    points encode exactly as before; no golden moved.
    `tests/test_point_types.py`. For the CHANGELOG. The contract is
    stated in `Oracle`'s docstring and, since Phase 7 step 8, in the
    README's oracle contract.
  - A solver parameter that is not a real number raises `TypeError`
    naming the keyword. Numbers still go through `float()` exactly as
    before. **A numeric string ("2") or a `Decimal` used to be
    converted and now raises.** Passing non-numbers through to custom
    solvers was deliberately left out: it is a feature, to be asked
    for.
  - The two transport refusals lead with the `notebook` extra.
- **`pymoso.dispatch_cost` (Phase 4), for the CHANGELOG as a new
  function.** `pymoso/backends/measure.py`. The user-called
  replacement for the removed warning: one request for replications
  timed in place and on a backend, wall time on both sides, the
  numbers and no verdict. Keep it that way -- no defaults for the
  request's size, no advice in its output (a test checks the printed
  form), nothing automatic. It is exported from the top level through
  a module `__getattr__` so the core still never imports `backends`
  at module scope.
- **Names no longer importable from `pymoso.chnbase` (Phase 5), for
  the CHANGELOG.** `Oracle` moved to `pymoso/oracle.py` and
  `chnbase` stopped binding what only `Oracle` used. None was ever
  documented on `chnbase` and nothing in the tree read them from
  there; they went deliberately, exceptions included, rather than
  being kept as re-exports of an accidental path. `chnbase.Oracle`
  itself is unchanged. Where each lives, and always did:
  - `pymoso.executor`: `ClassHandle`, `InProcessHandle`,
    `PoolExecutor`, `SerialExecutor`, `ReplicationBlock`.
  - `pymoso.prng.base`: `IterationOverflow`, `ReplicationOverflow`,
    `SyncOverflow`, `PointCodeCollision`, `PointNotEncodable`,
    `canonical_point`, `one_past`.
  - `pymoso.prng.registry` (the module, bound as `registry`).
  - The standard library: `statistics.mean`, `statistics.variance`,
    `math.sqrt`.
  - Also gone from `chnbase`, in a later commit of the same phase:
    `build_transport_descriptor` and `reconstruct_transport_descriptor`
    (`pymoso.executor`; a leftover of having been written in
    `chnbase`, pinned there by a test since Phase 2), and
    `get_biparetos`, which `chnbase` imported and never used
    (`pymoso.chnutils.get_biparetos`, as documented, or
    `pymoso.moso`).

  The one a user is most likely to meet is an `except
  chnbase.IterationOverflow` (or another of the four overflow
  exceptions): it becomes `pymoso.prng.base.IterationOverflow`.
  `tests/test_public_surface.py` holds what both modules still
  promise.

  **The same happened to `pymoso.chnutils`, for the same reason and
  by the same rule,** as its contents moved out. Every function it
  documented is still importable from it. What it no longer binds:
  - `pymoso.executor.ClassRef`, `pymoso.pool.LocalBackend`.
  - `pymoso.prng.base`: `IspOverflow`, `RoleDrawOverflow`,
    `ensure_random_compatible`, `one_past`.
  - The standard library: `copy`, `dataclasses.dataclass`,
    `itertools.product`, `itertools.filterfalse`, `statistics.mean`,
    `statistics.variance`, `math.ceil`, `math.floor`, `math.sqrt`.
  - Three private names tests used to reach through it, now in
    `pymoso.paths`: `_open_path_worker`, `_open_metric_worker`,
    `_metric_task`.
- **`pymoso/paths.py` was split from `chnutils.py` for the seam, not
  for import cost (Phase 5). Measured, so nobody re-derives it:**
  `import pymoso.paths` 28.1 ms, `import pymoso.chnutils` 26.9 ms,
  of which `pymoso.executor` is 26.3 ms either way; `chnutils`' own
  body is about 0.15 ms. A worker that loads a built-in tester or
  solver gains nothing measurable from not importing the entry
  points. "Workers import less" was offered as a reason for the split
  and withdrawn. If worker start-up cost ever matters, the thing to
  look at is `executor`'s imports (`inspect` alone is 5 ms).
- **API removed in Phase 3, also for the CHANGELOG:**
  `chnbase.mp_worker`, `chnbase.mp_replicate`, `chnutils.par_runs`,
  `chnutils.do_work`, and `Oracle`'s `req_q`/`res_q`/`proc`
  attributes. `Oracle.set_simpar()`/`mp_cleanup()` are kept, as the
  owner of the Oracle's executor. `par_diff()` keeps its signature.
- `hit()` returns `obse` as a list when `m==1` and a tuple otherwise.
- **Closed (Phase 5): `chnbase.py` and `chnutils.py` are decomposed**
  along the seams the executor work showed. Nothing documented broke:
  `pymoso.chnbase` and `pymoso.chnutils` are still the public import
  paths, by decision, and re-export what moved.
  - **Where things are.** `moso.py` (565 lines): the dominance,
    neighbourhood and distance helpers and all the doctests; depends
    on nothing. `oracle.py` (965): `Oracle`, whole -- its coordinate
    bookkeeping, executor ownership and aggregation share one
    object's state along one call chain, so it was not split
    further. `layout.py` (332): a run's streams from its seed, and
    `testsolve`'s end-seed aggregation (`_testsolve_endseed`, the one
    extraction of the phase). `paths.py` (265): `PathJob`, running
    paths and metrics here or on a pool. `chnbase.py` (1,120): the
    solver bases and the `PARAMS` helpers, in place. `chnutils.py`
    (314): `solve`, `testsolve`, their argument checks and defaults.
  - **Imports run one way:** `chnutils` -> `paths` -> `layout`;
    `chnbase` -> `moso`, `oracle`; `oracle` -> `executor`, `prng`.
    `chnbase` no longer imports `chnutils`. In-tree code imports from
    the defining module; the example files and the tests use the two
    documented paths on purpose.
  - **`tests/test_public_surface.py` is the contract.** It lists what
    each of the two modules promises and where each name is defined,
    and every other name they bind, and requires the lists to be
    exact. Adding or removing an import in either module fails it
    until the list is edited: that is intended. It also imports
    every module alone in a fresh interpreter, which is what catches
    a cycle that only a worker would hit.
  - **Five things cross process boundaries as `pymoso.paths.<name>`:**
    `run_path`, `_open_path_worker`, `_metric_task`,
    `_open_metric_worker`, `PathJob`. Plus `executor._run_blocks` and
    `executor._open_worker_executor`, which did not move. Renaming or
    moving any of them is a change to test under every start method
    and on the extras venv.
  - **A patch reaches a caller only through the name that caller
    reads.** `testsolve` reads `chnutils.run_paths` and
    `chnutils.check_role_draws`; `isp_run` reads
    `paths.check_role_draws`; `get_setnbors` reads `moso.get_nbors`;
    the solver bases read `chnbase.get_nbors`. The tests that patch
    these say so where they do it.
  - CI's doctest step names `pymoso/moso.py`.
  - What stopped being importable from the two modules is listed
    above, for the CHANGELOG.
  - Not done, and not planned: splitting `Oracle`, moving the solver
    bases out of `chnbase.py` (decided: they stay), a top-level
    `pymoso.solve`.
- **The example solvers,** `ExampleSearchSolver`
  (`pymoso/solvers/examplesearch.py`) and `ExampleBnBSolver`
  (`pymoso/solvers/examplebnb.py`): two `MOSOSolver`s from prior work,
  written against roughly the 1.0.8 API, shipped as **an implementation
  example only, not intended for serious solving or testing.** In prose
  they are "the example search-based solver" and "the example
  branch-based solver". **Nothing in the repository names or cites an
  algorithm they implement (decided 2026-11-23),** reversing Phase 6's
  decision to keep the module filenames, the file headers' citations and
  disclaimers, and the known-issues document's filename. Two exceptions
  by decision: the comparison curve in Cooper & Hunter's published figure
  keeps its name where that figure is described (this file's Phase 7
  section, `docs/algorithm-audit.md`, `docs/reconstruction-spec.md`), and
  `CHANGELOG.md`'s 1.1.0 section is a released record and is not edited.
  The `listitems` docstrings say "Do not use for serious solving or
  testing at this time." **Not described in the README, by decision:** no
  section, no usage prose, no claims about what they do. They still
  appear in the generated `listitems` block and parameter table, which
  stay literal output of the registered solvers -- do not filter them
  out; one sentence in the `listitems` section says why the listing has
  solvers the README does not describe. The golden cases were renamed
  with the solvers (values unchanged, proved by running under the new
  names first), and the golden README now uses the current case names
  throughout. Brought in with three compatibility fixes (a Python 3.11+
  `random.sample()` incompatibility, a library-hostile `sys.exit()` on
  missing params, a `--crn` refusal — under `--crn` every `hit()` either
  solver makes replays from the same baseline, confirmed empirically),
  and refuse `--crn` outright rather than carry that corruption forward.
  The refusal is not temporary plumbing: the `orc.crn_advance()` call
  both made at the end of `solve()` has been deleted along with the
  method, and the replay remains, because it comes from a `MOSOSolver`
  having no RA iteration to advance. What `--crn` should mean for such a
  solver is rng-interface-design.md §11 open question 11. Known defects
  (the search-based solver's full-box `product()` materialization, and
  its `self.seeds` aliasing: one checkpoint dict shared by every point,
  so one point's write can replace the checkpoint another point later
  resumes from; the branch-based solver's subregions
  that are not regions, its `update_gbar` `sehat` recompute bug and its
  unbounded replication requests) are tracked in `docs/example-solvers.md`,
  not this file — that document's own scope note explains why (caveats
  in example code, not framework defects across released versions, the
  frame this file and `KNOWN_ISSUES.md` both use). **The module paths
  cross process boundaries:** a by-reference `ClassRef` carries
  `pymoso.solvers.examplesearch`/`examplebnb` to workers, so moving either
  module again is a change to test under every start method and on the
  extras venv (the 2026-11-23 rename was).
- **Closed (Phase 6):** the README's `crn_*` table, the
  `crn_advance()` advice and the `setup.py` install line are gone.
  `bump()` and `crn_advance()` are in `CHANGELOG.md` with their
  migration. `KNOWN_ISSUES.md` issue 14 (`bump()`) stays where it is:
  the CHANGELOG cites it, and the file's numbering is not to change.
- **Closed (Phase 6): the parameter table is generated** from
  `PARAMS` (`tests/test_readme_param_table.py`); defaults and
  descriptions live in `tests/_solver_param_docs.py`, checked against
  the solvers by construction, not by attribute names. The `beta`
  descriptions there carry Phase 7's semantics note. What follows
  is the history.
  The README's "Table of Algorithm-Specific Parameters" was the one
  remaining solver-facing doc that wasn't test-enforced against live
  output (CLI help/`listitems` blocks are, via
  `tests/test_readme_help_text.py`'s "Layer 3" treatment) — it's
  hand-maintained prose nothing diffs against solvers' actual `__init__`
  kwargs. Bringing the example solvers in-tree added their params to it by
  hand, which only grows the gap. Follow-up: bring it under the same
  generated-and-diffed treatment as the CLI-help/`listitems` blocks,
  rather than leave it untracked indefinitely.
  **Phase 6 candidate, and now straightforward:** since Phase 4 every
  built-in solver declares its parameters in `PARAMS`, and a test
  holds each declaration to what the solver really accepts. The table
  can be generated from `chnbase.accepted_params` and diffed, with no
  introspection of `__init__`. It is the last solver-facing doc
  surface that nothing enforces; `PARAMS` is what closes it. (Names
  only: defaults and descriptions are not declared anywhere yet, and
  the table has both.)
- **Closed (rng-interface-design.md §12 step 9, MRG family):** there
  were two parallel implementations of replicate-and-aggregate --
  `hit()`'s CRN branch (incremental `rng`/`_next_seed` mutation) and
  `_hit_via_coordinate`. The CRN branch now routes through
  `_hit_via_coordinate` (`crn=True`), so there is one replication loop.
  `_next_seed`, `_iteration_baseline_seed` and `_advance_replication()`
  are gone; `crn_advance()` only increments `_iteration`; `hit()` never
  touches `Oracle.rng`. The per-iteration baseline stream is cached
  (`_crn_baseline_stream()`) -- that cache is what keeps a CRN `hit()`
  at ~20 µs instead of ~1.6 ms; see `docs/hit-cost-baseline.md` before
  touching it. (Since Phase 7 step 3 the jump it saves is ~21 µs, so
  the cache is worth about 2.6x, not 80x; it stays.) No golden moved.
  `--crn` and `sync=` now also work under Philox, with strides derived
  from its own budget (`REPL_STRIDE = 2^88`, one sync value per key) --
  not MRG's `2^76`, which was the first draft and the second time a
  Philox constant nearly inherited an MRG-specific value (see the end
  of §12 step 9). Every registered generator supports both `crnflag`
  values. (The README's claim that Philox does not support `--crn` was
  corrected in Phase 6.)
- **Closed:** `SYNC_ROLE_OFFSET` (2^175) exceeded `ISP_STRIDE` (2^159):
  a path's sync zone lay 2^16 slots above its own. The sync zone is now
  nested inside each isp path's slot (`SYNC_ZONE_STREAM_START` =
  `ISP_ITER_MARGIN`; `ISP_STREAM_SPAN` is the slot width), the sync
  coordinate is two-dimensional, and iteration, sync value and
  replication count each raise at their boundary
  (`IterationOverflow`, `SyncOverflow`, `ReplicationOverflow`). The MRG
  family halved its iteration headroom to 2^31 to do it (its slot
  width is pinned by goldens); Philox doubled its slot instead. No
  golden moved. `tests/test_sync_isp_nesting.py`.

  
## Settled RNG design (implemented)

The decisions below are landed, not pending. Full reasoning in
`docs/rng-interface-design.md`; this is the summary a fresh session needs.

- CPython's `random.Random` internals are gone. `MRG32k3a` and
  `MRG31k3p` still subclass `random.Random`, for its methods; Philox
  is composition (`RandomCompatAdapter`). (This line said "gone,
  composition not inheritance" until Phase 6; it was never true of
  the MRG family.) Pure Python,
  no new runtime dependencies. MRG32k3a remains the default for
  continuity with the papers; MRG31k3p and Philox-4x32 also implemented.
  The adapter backs `random`/`getrandbits`/`normalvariate` and what is
  built on them, not the state methods: a Philox stream cannot be
  checkpointed or reseeded, and `getstate()`/`setstate()` raise
  `StreamNotCheckpointable` and `seed()` raises `StreamNotReseedable`
  (`pymoso.prng.base`; the one `seed()` let through is
  `random.Random.__init__`'s, which unpickling runs). **This is
  deliberate, not unimplemented:** Philox's state, `(key, counter)`, is
  trivially saveable, but a position in this framework is reached by
  coordinate (`stream_at`), not by saving and restoring state, so the
  methods refuse rather than being left to write. `Oracle.rng` is never
  wrapped (`set_crnflag()` raises for an adapter), so under Philox it has
  no such methods at all.
- Streams are coordinate-derived, not jump-reached.
  `stream_at(seed, stream, offset)` computes position arithmetically.
  The interface does not expose jump-ahead; mechanism is per-generator.
  MRG maps both components onto one flat position, Philox onto key and
  counter.
- **Every coordinate constant is a chosen policy number, not a derived
  one.** `ITER_STRIDE` was inherited from L'Ecuyer's illustrative
  substream example (2^127), not from any PyMOSO requirement. They are
  now budget-anchored (10^9 ceiling) and adjustable. Each has a raise at
  its boundary — reachable in principle now that the strides are sized
  sensibly rather than absurdly, which is why the checks must be real.
- **CRN is a framework facility for algorithm testing, offered to expert
  users who opt in.** Algorithm designers should not think about it. The
  solver-facing `crn_*` surface is being removed, not deprecated:
  migration for custom solvers is "delete that line."
- Two distinct extension needs, found by tracing two `MOSOSolver`s
  written against the 1.0.8 API, before this redesign — corrected once
  already, worth keeping separate:
  - **Continuation** (the default): repeat `hit()` calls for a point get
    fresh non-overlapping replications with no solver-side state.
    `visit=0` means "continue," not "reset." Needed by any solver that
    revisits a point within an iteration and folds the new replications
    into a running mean and variance: a reset would average a repeated
    sample into itself, silently.
  - **Solver-controlled synchronization:** `sync=<int>` hands the
    synchronization axis to the solver, excluding point identity, so two
    points with the same `sync` compute the identical stream. Needed by a
    search-based solver that shares streams across points at equal
    cumulative sample effort, keyed on a per-point count of replications
    taken, which coincides with the framework's iteration-keyed
    `crn=True` only accidentally.
  Framework provides both mechanisms; the algorithm chooses the policy.
  Note that `sync=` would implement the example search-based solver's
  intended policy for the first time — its `getstate`/`setstate`
  checkpoints were honored for at most each checkpoint's first
  replication in the 1.0.8-era framework, and have had no effect on any
  result since step 4b's cutover on the default path (`18ab096`) and
  step 9 on the CRN path (`390ce4e`); under Philox the solver refuses to
  run — so porting it is a behavior change to that solver, not a
  refactor.
- Non-CRN mode is coordinate-computable and always was. Its contract is
  only preserved distributional properties plus determinism relative to
  the seed. The old order-dependent walk was an artifact of
  `crn_check()` no-opping, and a defect.
- `point_code` is a zigzag-plus-positional-radix bijection —
  collision-free by construction, not a hash. `W = POINT_BITS // dim`
  per Oracle. All built-in problems fit (BSProb tightest at dim=9,
  W=8). **Closed:** a point that does not fit used to raise
  `PointCodeOverflow`, a hard wall for high-dimensional custom
  problems. `Oracle.hit()` now uses `encode_point`: the exact code when
  the point fits (so nothing existing moves), otherwise a fixed blake2b
  hash into the same field, with `Oracle._record_point_code` raising
  `PointCodeCollision` if two points in one iteration ever share a
  code. "Correct or raises", not "probably distinct". The encoding
  cannot simply grow: coordinates are modulo the generator's period
  (rng-interface-design.md §3.4 addendum). Known limits of the check
  are listed in `_record_point_code`'s docstring.
- **"Coordinate ceiling removed" is not "dim 20 works."** The hashed
  fallback unblocks custom `MOSOSolver`s at any dimension and
  low-dimensional problems with large components. It does NOT make the
  built-in RA solvers usable in high dimension: `chnutils.get_nbors`
  enumerates a `3**dim` neighbourhood (RPERLE, budget 300: 0.6 s at
  dim=3, 5 s at dim=6, 17 s at dim=9, no return at dim=20 -- `3**20` is
  about 3.5 billion points). Structural, not a tuning problem; they
  stay practical to roughly dim=9.
  **Phase 4 scoping fact:** if distributed users bring high-dimensional
  problems, the built-in solvers will not serve them whatever the
  executor does. That needs a solver that does not enumerate
  neighbourhoods -- new algorithmic work, not executor work.
  **CORRECTION (Phase 4): both paragraphs above are wrong about the
  cause. Kept as written so the correction sits next to what it
  corrects.** The dim-9 ceiling was asserted to be structural and to
  need a new solver -- in this file, in rng-interface-design.md §3.4
  and in Phase 4's brief -- and was never measured. It was one
  helper's implementation: at radius 1 a neighbourhood is `2*dim`
  points and `get_nbors` built the `3**dim` box to find them.
  **Closed:** `get_nbors` now builds the neighbourhood directly, in
  the old insertion order, so the returned set is identical element
  for element and position for position; no golden moved.
  - **The insertion order is load-bearing.** Solvers iterate the set;
    the same points in another order moved results in 20-40 of 96
    whole runs at radius 2 and 3. `tests/test_get_nbors_equivalence.py`
    keeps the old implementation verbatim as the reference -- do not
    tidy it, and do not "simplify" `get_nbors` to `{x +/- e_i}`.
  - **The claim is "the built-in solvers no longer stall on
    neighbourhood enumeration", NOT "dim 20 works".** Behind it: the
    MRG jump is 95% of a high-dimensional run (RPERLE budget 1,000:
    5 s at dim 20, 330 s at dim 50; Philox 0.3 s and 2.4 s -- before
    Phase 7 step 3's cheaper jump, not re-measured since); the
    budget stops bounding the work (KNOWN_ISSUES.md issue 16); radius
    above 1 is genuinely large in high dimension; and solution quality
    there was checked on one easy quadratic only.

- **Phase 6 (documentation and release preparation), what a later
  session needs:**
  - `CHANGELOG.md` is the only migration path for 1.x users. Its lists
    of names no longer importable are computed against the v1.1.0 tag,
    not from the Phase 5 notes above, which were relative to the Phase
    4 tree. `solve()` gives 1.1.0's results for the same seed; only
    `testsolve()` moved (issue 10). **Phase 7 changed that:** the
    relaxation fix and the audit fixes move `solve()`'s results too,
    and the CHANGELOG's "what breaks" says so.
  - **The 16,384-draw per-replication limit shipped in 1.1.0,**
    undocumented. It is now `Oracle.replication_draws`, a class
    attribute (a power of two up to 2^40); the bits come out of the
    point code. Class attribute by decision: it belongs to `g()`, and
    workers rebuild the oracle from the class.
  - `MOSOSolver.__init__` takes `x0` and `sprn` (kept if a sub-class
    set them first) and refuses any other leftover, by decision.
    `isp_run` fills in `oracle_high_water_mark` for a solver that does
    not report it. An `Oracle` used directly initializes as if
    `set_crnflag(False)` on first `hit()`.
  - **README Layer 5:** factual claims carry `<!-- verified: ... -->`
    naming their tests (`tests/test_readme_claims.py` checks the tests
    exist). A new claim needs one, or an entry in
    `docs/unverified-claims.md`. Phase 7's measurement-based guidance
    has no test by nature, so it all lives in that file with the
    measurement document named.
  - **Release order, decided, in this sequence:** (1) the maintainer's
    prose pass; (2) bump to `2.0.0rc1`; (3) TestPyPI; (4) bump to
    `2.0.0`; (5) tag `v2.0.0` and push the tag; (6) switch GitHub's
    default branch to `dev-2.0`; (7) PyPI. Each bump is
    `.git/phase6/bump.py`, which sets the version and turns every
    relative link in the README into an absolute link to the `v2.0.0`
    tag (PyPI renders the README, where relative links break), and
    refuses to finish if a relative link it cannot rewrite remains.
    Those links resolve only once the tag is pushed, hence (5) before
    (7). **Do not switch the default branch early:** the README says
    the bare `pip install git+...` command installs 2.0 development,
    and 1.1.0's README on PyPI gives the same command, so until (6) the
    README is wrong and after it 1.x users get 2.0 (the CHANGELOG's
    first breaking-change entry says how to stay on 1.x).
    **Status as of 2026-11-20:** step (1) not done — Phase 7 step 8
    wrote a large amount of user-facing prose that has had no
    maintainer pass. Nothing after it has started. A GitHub release
    drafted from the CHANGELOG's 2.0.0 section follows (7); that
    heading still needs its date.

## Still in flight

- Executor rework. **Landed (Phases 2 and 3):** `pymoso/executor.py`
  and `pymoso/pool.py`. Work is a `ReplicationBlock` (point, root,
  `(stream, offset)`, stride, count); problems reach a backend only as
  a `ProblemHandle`; `Executor.open/run/close` is the one lifecycle,
  and `run` takes a list of blocks. `Oracle` computes coordinates and
  does the checks; the backend turns coordinates into streams and
  calls `g()`. Two backends: `SerialExecutor`, and `PoolExecutor`
  (`--simpar`), whose workers each hold a `SerialExecutor` -- so the
  base-stream cache that keeps `--crn` fast lives in each worker.
  `testsolve()` paths are a second job type on the same pool, not
  blocks. Goldens unchanged throughout.
  **Landed (Phase 4):** a by-value `ClassRef` and a Spark backend,
  both behind the backend seam -- see "Known open items".
- **Batching across `hit()` calls landed (Phase 3) and is worth less
  than Phase 2 predicted.** `Oracle.hit_many` and
  `RASolver.estimate_many`, used by `upsample`, `pli` and `get_ncn`.
  Measured (`docs/simpar-ceiling.md`): on a one-dimensional problem a
  solver never has two points to submit, so the original RSPLINE
  benchmark cannot observe batching at all -- `ProbExpensiveBi` (2-D,
  bi-objective, not registered in `pymoso.problems`) exists for that
  reason. Without `--crn`, 35-46% of an RA solver's replications
  (38% for RPERLE on ProbTPA at budget 10,000) come from `ne()` and
  the `spli()` line search, which choose each point from the last
  result and cannot be batched. The one `--crn` run surveyed was 18%;
  `--crn` was not benchmarked. That share, not dispatch and not the pool, is
  what holds the bound. The only thing that would move it is
  speculative prefetch (rng-interface-design.md §11 entry 15),
  declined for Phase 3 because it puts solver logic in the executor.
- `estimate_many` must reproduce the one-at-a-time loop exactly,
  including re-simulating an infeasible point each time it recurs
  (it does so in rounds). Whole-run tests and goldens do not catch a
  version that skips this -- verified by trying one -- because the end
  seed rarely depends on those blocks. `tests/test_batching.py`'s
  `SometimesInfeasible` case is the detector for that, and only for
  that: it compares `estimate_many` with `estimate` in a loop, so it
  catches the two diverging. **It does not detect repeat-skipping
  applied to both** (a cache in `estimate`, which `estimate_many`
  then matches): Phase 7 ran the whole suite with such a cache in
  every interpreter and it passed, goldens included
  (docs/end-seed-scope.md, the sixth instance). §11 entry 13 (Phase 7
  step 1b) would remove the need.
- The example solvers still call `hit()` in loops and were not
  converted to `hit_many`.
- Deferred, with reasons, in rng-interface-design.md §11: per-point
  CRN continuation (11: not invisible to RA solvers), unifying
  `solve()`/`testsolve()` layouts (12: buys the executor nothing),
  remembering infeasible points within an iteration (13: a performance
  finding in its own right). A cheaper general jump (14) landed in
  Phase 7 step 3 for the MRG family: one cached power per set bit
  (`mrg_common.PowerTable`), bit-identical, built lazily per process.

## After 2.0.0

Nothing here blocks the release. Recorded so it is not re-derived.

- **The example solvers' known defects fixed,** from
  `docs/example-solvers.md`. This is the first item: the reconstructed
  experiment below wants a credible comparator, and the example
  search-based solver is the in-tree candidate.
- **A full, reproducible reconstruction of the published experiments**
  for the Purdue-family algorithms, from `docs/reconstruction-spec.md`.
  Wants a serious cluster. Corrected plots are not themselves the
  goal — verification and a performance floor were, and both are met.
- **Report the paper's own efficiency measure,** `W_k ||X_k - x*||^2`
  (Pasupathy 2010, §6.1, p. 898), alongside the coverage curves. For
  the test problems `x*` is known, so this is cheap and it would put
  the plots into the framework the parameter choices are derived from.
- Deterministic black-box solvers; continuous solvers (ASTRO-DF, Kim &
  Ryu).
- The follow-ups already recorded above: naming the task in
  `WorkerPool.run`'s pickle error, re-running the `--simpar` sweep
  against Phase 7 step 3's jump, and §11 entry 13.

## Testing

- `ProbExpensive` (Light/Moderate/Heavy tiers) plus `ExpensiveTester`
  give a tunable per-replication cost for exercising parallel paths in
  the regime they're actually for. Cost is a class attribute, not a
  kwarg, because workers rebuild the Oracle from the class alone.
  `ProbExpensiveBi` is the 2-D, two-objective counterpart, for anything
  that needs several points submitted at once.
- Anything that starts worker processes is tested under every start
  method the platform has (`multiprocessing.get_all_start_methods()`),
  not just the default. Classes and functions a worker must import
  live in `tests/_*.py` helper modules, not in the test module.
- **A test that works by substitution needs proof the substitute was
  reached; and a mutation check needs bytecode caching off.** Three
  tests here have passed while no longer exercising what they were
  read as covering; the third was a `monkeypatch.setattr` on a module
  name that, after a move, nothing read. After moving a function,
  every patch of its name is suspect. And two same-length edits to a
  file within one second reuse the cached `.pyc`: a mutation check
  reported the previous mutation's failure. Set
  `PYTHONDONTWRITEBYTECODE=1` and clear `__pycache__` before mutation
  checks or stage swaps. `docs/end-seed-scope.md`, "A third instance".
- **`tests/test_reference_files_not_shipped.py` is deliberately weaker
  than inspecting a built sdist and wheel.** It checks that no `*.pkl`
  sits under `pymoso/`, that `MANIFEST.in` names nothing under `docs/`,
  and that `include-package-data` stays false; its docstring lists what
  that misses (a `global-include`, a new build backend, `package-data`
  entries, a change in setuptools' defaults). Recorded in
  `docs/end-seed-scope.md` as a known-weaker test written that way on
  purpose, not as a defect.
- Portable assertions (call counts, cross-worker-count result identity,
  job-dispatch counts) live in the suite. Absolute timings live in
  `docs/parallel-dispatch-baseline.md` as an artifact, never asserted on.
- **Current timing baselines: refreshed at the end of Phase 4**
  (2026-10-13, quiet machine, two runs of every figure shown).
  `docs/simpar-ceiling.md`, "Baselines at the end of Phase 4", and
  `docs/hit-cost-baseline.md`, "At the end of Phase 4". Compare later
  work against those, not against the Phase 3 tables.
  `docs/parallel-dispatch-baseline.md` is the pre-pool before-picture
  and stays that way. **Check `uptime` before benchmarking:** Phase
  4's first re-run was silently 10-14% slow because the machine was
  busy, and only code that had not changed gave it away.

## Environments

- `.venv-baseline` — CPython 3.10, editable install. Compatibility
  floor; multiprocessing defaults to `fork`.
- `.venv-dev` — CPython 3.14, editable install. Primary development
  environment; multiprocessing defaults to `forkserver`, which is where
  the executor work needs to be developed, not just eventually
  validated. This choice has already caught one bug that was invisible
  on 3.10.
- CI runs 3.10-3.14 on three operating systems, plus `clean-clone`
  and (Phase 4) `extras` on Linux at 3.10 and 3.14. Note: CI had never actually executed until
  recently — every "all green" before that was a local run. Don't
  assume a green history means a verified one.
- `.venv-extras` — CPython 3.14, editable install of
  `.[test,spark,spark-test]`, with a JRE unpacked at
  `.venv-extras/jre` (there is no system Java on this machine).
  Excluded via `.git/info/exclude` like the other two. Run it as
  `JAVA_HOME=$PWD/.venv-extras/jre
  PYMOSO_REQUIRE_EXTRAS=cloudpickle,pyspark,grpc
  .venv-extras/bin/python -m pytest tests/`. The other two venvs must
  stay extras-free: they are the local stand-in for "works with
  nothing optional installed".
- The optional-dependency boundary is enforced, not intended:
  `tests/test_dependency_boundary.py` (static and run-time) plus the
  CI `extras` job, in which a test that would skip for a missing
  extra or JVM fails instead (`tests/_extras.py`,
  `PYMOSO_REQUIRE_EXTRAS`). A new lazy import of a third-party module
  in the core has to be added to that test's allowlist by hand.
- Use `uv`, never plain pip. Never install into system Python.

## Working agreement

- Propose a plan before writing code. Wait for approval.
- Smallest change that solves the actual problem. Say so if a rewrite is
  genuinely better, but default to patching.
- Don't reformat code you weren't asked to touch.
- State assumptions. Say "I need to see X" rather than guessing.
- Run tests between changes, not at the end.
- If an acceptance criterion I gave conflicts with what the code needs,
  say so and stop. Don't reinterpret the criterion to make it pass.
- Whitespace-only changes must be provably whitespace-only (`git diff -w`
  empty). Anything substantive gets its own commit.
- Report findings before fixing them, unless the fix was pre-approved.
- A regression test must be observed failing before the fix lands. A
  detector never seen detecting isn't proven to work.
- **State what a measurement means before taking it.** Phase 7 ran on
  pre-stated predictions scored as hit or miss afterwards, which is
  what kept several wrong mechanisms from being retrofitted onto
  results that happened to fit.
