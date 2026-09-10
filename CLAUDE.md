# PyMOSO

Python package for multi-objective simulation optimization. Originally a
PhD output (Cooper & Hunter 2018), now being modernized on the
`pymoso-migration` branch, currently unpushed.

## Canonical repository

github.com/pymoso/PyMOSO — remote `origin` in this checkout. Both
READMEs are nearly identical to HunterResearch/PyMOSO's stale fork
(13 commits behind), so check the remote, not the content. The
`dangerzone` branch is superseded by master. This file is tracked in git
as of 2026-09-10 (previously gitignored, so it existed on one disk
only). Edits to it are commits now.

**Remote names are non-default here, deliberately, as of 2026-09-10.**
`origin` used to point at HunterResearch/PyMOSO (the stale fork); it is
now renamed `stale-fork`, and the remote that used to be named `pymoso`
(github.com/pymoso/PyMOSO, canonical) is now `origin`, with
`remote.pushDefault` also set to `origin` explicitly. Done while
preparing the 1.1.0 release: `release-1.1.0` had no upstream tracking
configured, and a reflexively-typed `git push -u origin ...` on it (or
on any future branch) would have landed on the stale fork — a release
tag pushed to the wrong repository is a mess to undo. If a fresh clone
or session ever sees `origin` pointing at HunterResearch/PyMOSO again,
that's the old layout; this checkout's `git remote -v` is
authoritative, not this note.

Version history is inconsistent upstream: `pymoso/master` installed as
`1.0.7` while PyPI had `1.0.8`, so the released wheel corresponds to no
commit. See "Version boundary: 1.1.0 released, this branch at 2.0.0
development" below for this project's own version history. Don't
assume git HEAD and the installed package agree; check both when
behavior is in question.

## Version boundary: 1.1.0 released, this branch at 2.0.0 development

**1.1.0 was released from `release-1.1.0`, branched at `b637a3e`**
(`pymoso-migration`'s own history — §12 step 6c-completion, giving
Philox its own offset-assembly budget). Everything through that commit
is 1.1.0; everything on `pymoso-migration` after it, including this
commit, is 2.0.0 development. `pymoso/__init__.py` on this branch now
reads `2.0.0.dev0` accordingly.

What makes the line major, not minor: the `--seed` CLI syntax change
(one comma-separated token, replacing the old six-space-separated-value
form — a documented, user-visible break) and `Oracle.bump()`'s outright
removal (a documented public-API break, no compatibility shim) both
landed after `b637a3e`, so neither shipped in 1.1.0. The solver-facing
`crn_*` surface's removal is decided (see "Settled RNG design" below)
but **not yet landed** — still listed under "Known open items" above —
so it isn't itself evidence for the boundary yet, only the direction
this line is headed in.

**The two branches genuinely differ in content, not just version
number.** `release-1.1.0` excludes MOCOMPASS/MOPBnB entirely (deferred
to 2.0.0 as a deliberate decision — see that branch's `KNOWN_ISSUES.md`
issue 13); `pymoso-migration` has them committed
(`pymoso/solvers/mocompass.py`/`mopbnb.py`, `tests/test_mocompass_mopbnb_compat.py`
— `fbc0fdf`, "Add MOCOMPASS and MOPBnB solvers (previously
untracked)"; see "Known open items" above). Don't assume a diff between
the two branches is only the commits between them; `release-1.1.0`
also lacks files this branch has, and citations to
`test_mocompass_mopbnb_compat.py` that are valid here (e.g.
`tests/test_oracle_noncrn_default.py`'s own docstring) are dangling
references on `release-1.1.0` — checked and fixed there specifically,
not assumed to carry over.

`docs/rng-interface-design.md` carries the same boundary note at its
own head, step-by-step.

## Critical context

  `choice()` picks, and 0 of 10 goldens moved. Consumption-sensitive
  coverage lives in `tests/test_rng_consumption.py` (a recording RNG)
  and `tests/test_solution_sensitivity.py`. See `docs/end-seed-scope.md`.
- Golden baselines in `tests/golden/` were captured from `pymoso/master`
  on CPython 3.10 and have since been deliberately regenerated several
  times: after the jump-ahead fix, after step 4b's non-CRN cutover,
  after the replication-spacing collision fix, and after both stages of
  step 8's endseed rework. NEVER regenerate or edit them without being
  asked. Superseded values are preserved in `tests/golden/README.md`
  with the reason for each move.
- The RNG fix changes numerical output deliberately: end seeds and
  per-run solution values from 1.x will not reproduce bit-for-bit. This
  is an implementation fix, not a correction to the published
  convergence theory. See `KNOWN_ISSUES.md` issue 1.
- README code blocks are generated from files under `pymoso/examples/`,
  and tests assert byte-identity. Files are the source of truth; edit the
  file and regenerate, never the README block directly. Same for the CLI
  help and `listitems` blocks, generated from live parser output.
- Docstring style differs from the earlier fork (`old-work`), which had a
  numpy conversion this branch deliberately does not. Leave it alone —
  converting would collide with the byte-identity assertions.
- **The end seed's scope changed in step 8 — the older "allocation
  schedule only" warning is superseded.** It now reflects the run's
  actual consumption via a computed high-water mark, so it distinguishes
  runs that previously reported identical values. It still does not
  fingerprint *which* values were drawn: a change to replication-level
  consumption can leave every golden green, verified the hard way when
  `getrandbits()` demonstrably changed which `x0` values `choice()`
  picks and 0 of 10 goldens moved. Consumption-sensitive coverage lives
  in `tests/test_rng_consumption.py` (a recording RNG) and
  `tests/test_solution_sensitivity.py`. `docs/end-seed-scope.md` has
  been corrected twice as the thing it describes changed underneath it —
  read it rather than assuming either version.

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
testers'/problems'/MOCOMPASS-MOPBnB's own `choice`/`expovariate`/
`sample` calls need the full `random.Random` surface Philox's own
Stream deliberately doesn't provide (`RandomCompatAdapter`, §3.6,
finally wired in via `pymoso.prng.base.ensure_random_compatible`, a
no-op for the MRG family); and `RandomCompatAdapter` itself didn't
pickle, hanging `--proc` runs (a forkserver-pickling-error hang,
KNOWN_ISSUES.md issue 9's own failure class, new cause) until given a
`__reduce__`. Default path (no `--generator` given) unaffected
throughout — confirmed directly, full suite green on both venvs, no
golden moved.

`Oracle.bump()` removed outright (step 6b, landing ahead of the rest of
that step): no in-tree callers, no test coverage beyond pinning its own
leftover behavior, duplicated `hit()`'s replication loop. Migration for
an out-of-tree caller: `hit()` with the same arguments returns
aggregated stats; raw per-replication access returns with the executor
rework. See `KNOWN_ISSUES.md` issue 13.

Two defects found and fixed within that work, both introduced by it and
never released: a replication-spacing collision (step 4b packed
replication with stride 1, so replications shared draws — `obse` was
computed over non-independent samples), and the carry-rule proof that
surfaced `SYNC_ROLE_OFFSET > ISP_STRIDE`, meaning `sync=` and multi-path
`testsolve()` were never compatible.

## Known open items

- **`testsolve`'s `--proc` path** ships fully-constructed, seeded Oracle
  instances rather than class references, so the source-bundle fix does
  NOT transfer to it. Broken under forkserver on 3.14, with xfail tests
  in place. Reconstructing a live object with RNG state is a different
  problem from reconstructing a class — this is executor-rework
  territory, not a point fix. See `docs/forkserver-hang.md` and
  `KNOWN_ISSUES.md` issue 9.
- `--proc` also uses `Pool` unconditionally, even at `--proc=1`, so the
  serial path isn't actually serial and inherits parallel failure modes.
- Dispatch granularity: `--simpar` dispatches one job per replication and
  tops out at ~2.5-3x speedup regardless of worker count; `--proc`
  dispatches per ISP and reaches ~5x, plateauing at 6 physical cores on
  the benchmark machine. Numbers and method in
  `docs/parallel-dispatch-baseline.md`. Batching is the fix.
- Multiprocessing lifecycle bugs keep surfacing — the `--simpar` error-path
  leak, orphaned workers on external kill, the forkserver transport gap,
  `--proc`'s unconditional `Pool`, and `RandomCompatAdapter`'s pickling
  hang. That's an argument about the design, not the instances.
- `hit()` returns `obse` as a list when `m==1` and a tuple otherwise.
- `chnbase.py` and `chnutils.py` remain undecomposed — deliberately
  deferred until the executor rework reveals the real seams.
- MOCOMPASS and MOPBnB (real `MOSOSolver`s from prior work, written
  against roughly the 1.0.8 API) are now in-tree,
  `pymoso/solvers/mocompass.py`/`mopbnb.py` — role decided: shipped,
  compatibility-only examples. Brought in with three compatibility
  fixes (a Python 3.11+ `random.sample()` incompatibility, a
  library-hostile `sys.exit()` on missing params, a `--crn` refusal —
  both solvers previously called `orc.crn_advance()` in a way that
  silently corrupted `--crn`, confirmed empirically), and now refuse
  `--crn` outright rather than carry that corruption forward. Their
  algorithmic correctness against the source papers has NOT been
  reviewed — that's separate, future work. Known algorithmic issues
  (MOCOMPASS's `product()` full-box materialization; MOPBnB's
  `update_gbar` `sehat` recompute bug; MOCOMPASS's `self.seeds`
  cross-point aliasing, distinct from the deliberate synchronization
  policy it implements) are tracked in
  `docs/mocompass-mopbnb-known-issues.md`, not this file — that
  document's own scope note explains why (caveats in new example code,
  not framework defects across released versions, the frame this file
  and `KNOWN_ISSUES.md` both use).
- The README's own `MyMOSOAlg`/`MOSOSolver`-authoring template still
  tells solver authors to "use (or wrap) `hit` and `crn_advance()`" —
  exactly the pattern that silently broke `--crn` for MOCOMPASS/MOPBnB.
  Not fixed: the actual fix is removing the solver-facing `crn_*`
  surface entirely (below), at which point the template needs rewriting
  too, not patching now.
- The README's "Table of Algorithm-Specific Parameters" is the one
  remaining solver-facing doc that isn't test-enforced against live
  output (CLI help/`listitems` blocks are, via
  `tests/test_readme_help_text.py`'s "Layer 3" treatment) — it's
  hand-maintained prose nothing diffs against solvers' actual `__init__`
  kwargs. Bringing MOCOMPASS/MOPBnB in-tree added their params to it by
  hand, which only grows the gap. Follow-up: bring it under the same
  generated-and-diffed treatment as the CLI-help/`listitems` blocks
  (live introspection of each registered solver's `__init__`, diffed
  against the table), rather than leave it untracked indefinitely.
- Two parallel implementations of replicate-and-aggregate now exist:
  `hit()`'s CRN branch (incremental, unmigrated) and `_hit_via_coordinate`
  (coordinate-derived). Proven equivalent by induction and
  one empirical test, which is exactly the shape that drifts —
  `_hit_opt_in` already diverged once on the `m==1` variance case.
  (A third, `bump()`, existed until step 6b removed it outright — no
  in-tree caller, so there was nothing for a unification to preserve;
  see "Fixed on this branch" and `KNOWN_ISSUES.md` issue 13.)
  **Reclassified, found preparing step 6b's own `--generator` wiring,
  now landed:** this was recorded purely as drift-risk; it is also a
  hard blocker. `hit()`'s CRN branch (`crn_advance()`/
  `_advance_replication()`) never moved off incremental `rng`/
  `_next_seed` mutation and the MRG-specific `get_next_prnstream`/
  `jump_substream` calls that back it — there is no coordinate concept
  for `--crn` to route through for any non-MRG generator at all.
  `--generator=philox4x32` combined with `--crn` now raises a clear,
  named `NotImplementedError` at `Oracle.set_crnflag()` time (mirroring
  MOCOMPASS/MOPBnB's own outright `--crn` refusal), and the limitation
  is documented in `--generator`'s own CLI help and the README, not
  only in the error a user hits — CRN is the framework facility for
  algorithm testing, so "Philox is supported" carries a real asterisk,
  said up front now. The unification itself (CRN-branch convergence)
  is still open — see "Still in flight."
- `SYNC_ROLE_OFFSET` (2^175) exceeds `ISP_STRIDE` (2^159), so `sync=`
  and multi-path `testsolve()` are incompatible. No in-tree caller
  exercises the combination today, but MOCOMPASS is the natural `sync=`
  user once ported and `testsolve` is how its competing numerics would
  be generated — this is one step away from being reached, not
  genuinely unreachable. Recorded at the constant's definition; should
  probably raise.

  
## Settled RNG design (implemented)

The decisions below are landed, not pending. Full reasoning in
`docs/rng-interface-design.md`; this is the summary a fresh session needs.

- `random.Random` is gone — composition, not inheritance. Pure Python,
  no new runtime dependencies. MRG32k3a remains the default for
  continuity with the papers; MRG31k3p and Philox-4x32 also implemented.
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
- Two distinct extension needs, found by tracing MOCOMPASS and MOPBnB —
  corrected once already, worth keeping separate:
  - **Continuation** (MOPBnB's need, the default): repeat `hit()` calls
    for a point get fresh non-overlapping replications with no
    solver-side state. `visit=0` means "continue," not "reset."
  - **Solver-controlled synchronization** (MOCOMPASS's need): `sync=<int>`
    hands the synchronization axis to the solver, excluding point
    identity, so two points with the same `sync` compute the identical
    stream. MOCOMPASS shares streams across points at equal cumulative
    sample-effort — a real MO-COMPASS policy, keyed on `nx[x]`, which
    coincides with the framework's iteration-keyed `crn=True` only
    accidentally.
  Framework provides both mechanisms; the algorithm chooses the policy.
  Note that `sync=` implements MOCOMPASS's intent for the first time —
  `crn_nextobs()` never honored its `setstate()` calls beyond a
  checkpoint's first replication, so porting it is a behavior change to
  that solver, not a refactor.
- Non-CRN mode is coordinate-computable and always was. Its contract is
  only preserved distributional properties plus determinism relative to
  the seed. The old order-dependent walk was an artifact of
  `crn_check()` no-opping, and a defect.
- `point_code` is a zigzag-plus-positional-radix bijection —
  collision-free by construction, not a hash. `W = POINT_BITS // dim`
  per Oracle; overflow raises. All built-in problems fit (BSProb
  tightest at dim=9, W=8). The scheme degrades with dimension and
  PyMOSO bounds dimension nowhere, so high-dimensional custom problems
  hit a hard wall — open whether the encoding should grow rather than
  partition a fixed budget.

## Still in flight

- CRN-branch convergence: unify `crn_advance()`/`_advance_replication()`/
  `hit()`'s own `crnflag=True` path onto `_hit_via_coordinate`'s
  stateless `Stream.advance()`-based mechanism, closing the `--crn`/
  `sync=` guard non-MRG generators hit today. Scoped out of step 6b
  deliberately (real, traced work — see docs/rng-interface-design.md
  §12, the step after step 8) — not attempted inline because it changes
  what `_next_seed`/`_iteration_baseline_seed` are, with several
  existing tests asserting on both directly.
- Executor rework: work expressed as data (points, sample sizes,
  explicit seeds), seeds as computed values rather than object state,
  pluggable backends (serial, process pool, Spark) behind one interface
  with one lifecycle.

## Testing

- `ProbExpensive` (Light/Moderate/Heavy tiers) plus `ExpensiveTester`
  give a tunable per-replication cost for exercising parallel paths in
  the regime they're actually for. Cost is a class attribute, not a
  kwarg, because workers rebuild the Oracle from the class alone.
- Portable assertions (call counts, cross-worker-count result identity,
  job-dispatch counts) live in the suite. Absolute timings live in
  `docs/parallel-dispatch-baseline.md` as an artifact, never asserted on.

## Environments

- `.venv-baseline` — CPython 3.10, editable install. Compatibility
  floor; multiprocessing defaults to `fork`.
- `.venv-dev` — CPython 3.14, editable install. Primary development
  environment; multiprocessing defaults to `forkserver`, which is where
  the executor work needs to be developed, not just eventually
  validated. This choice has already caught one bug that was invisible
  on 3.10.
- CI runs 3.10-3.14. Note: CI had never actually executed until
  recently — every "all green" before that was a local run. Don't
  assume a green history means a verified one.
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
