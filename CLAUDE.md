# PyMOSO

Python package for multi-objective simulation optimization. Originally a
PhD output (Cooper & Hunter 2018), now being modernized on the `dev-2.0`
branch, checked out at `/srv/projects/PyMOSO` and pushed to `origin`.

## Canonical repository

github.com/pymoso/PyMOSO — remote `origin` in this checkout.
HunterResearch/PyMOSO was a stale snapshot and is now archived; the
`stale-fork` remote that pointed at it was removed in Phase 0 of the
2.0.0 work. `remote.pushDefault` is set to `origin` explicitly. This
file is tracked in git; edits to it are commits.

1.1.0 is released on PyPI from the `release-1.1.0` branch and tagged
`v1.1.0`, with `master` pointing at it. Version history before that is
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
`Oracle.bump()`'s removal, and the solver-facing `crn_*` surface's
removal — all landed after `b637a3e`, none shipped in 1.1.0.

The two branches differ in content, not just version. `release-1.1.0`
excludes MOCOMPASS/MOPBnB entirely; this branch has them committed.
Don't assume a diff between them is only the commits between them.

`KNOWN_ISSUES.md` numbering: Phase 0 remapped this branch's citations
to match the file's own headings, which already used release
numbering for issues 1-9. Numbers diverge from 13 on — this branch has
14 = `bump()` removal, 15 = `--simpar` exception hang (deliberately out
of sequence, do not renumber); release has 14 = MOCOMPASS/MOPBnB
exclusion. Nine citations to a dropped old issue 2 still dangle on both
branches. Don't merge `KNOWN_ISSUES.md` textually between branches.

## Critical context

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
  — read it rather than assuming either version.
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

## Known open items

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
  drop (1.71x -> 1.53x) may be noise: later runs gave 1.52x and 1.64x
  for the same configuration, and no piece cap improves on six pieces
  there. Whether it is noise or has another cause is NOT settled; it
  needs repeated interleaved before/after runs. A measurement-driven
  cap was proposed and not built -- it cannot fix 6 workers, only
  partly fixes 12, and makes dispatch timing-dependent. The sweep and
  the reasons are in `docs/simpar-ceiling.md`; do not re-propose it
  without new data. The overhead itself is the problem, so the
  cheaper jump (rng-interface-design.md §11 entry 14) is the
  better-motivated fix. Moderate and Heavy are unaffected.
- **Behaviour change to record in the CHANGELOG (Phase 6), and it
  matters for Phase 4's notebook audience:** `testsolve(proc>1)` with a
  tester or solver class defined in a notebook cell, a REPL or inside
  a function worked under fork and now raises `ValueError` under every
  start method. `proc=1` still works. The remedy is a cloudpickle
  `ClassRef`, as an optional extra; not built.
- **API removed in Phase 3, also for the CHANGELOG:**
  `chnbase.mp_worker`, `chnbase.mp_replicate`, `chnutils.par_runs`,
  `chnutils.do_work`, and `Oracle`'s `req_q`/`res_q`/`proc`
  attributes. `Oracle.set_simpar()`/`mp_cleanup()` are kept, as the
  owner of the Oracle's executor. `par_diff()` keeps its signature.
- `hit()` returns `obse` as a list when `m==1` and a tuple otherwise.
- `chnbase.py` and `chnutils.py` remain undecomposed — deliberately
  deferred until the executor rework reveals the real seams.
- MOCOMPASS and MOPBnB (real `MOSOSolver`s from prior work, written
  against roughly the 1.0.8 API) are now in-tree,
  `pymoso/solvers/mocompass.py`/`mopbnb.py` — role decided: shipped,
  compatibility-only examples. Brought in with three compatibility
  fixes (a Python 3.11+ `random.sample()` incompatibility, a
  library-hostile `sys.exit()` on missing params, a `--crn` refusal —
  under `--crn` every `hit()` either solver makes replays from the
  same baseline, confirmed empirically), and refuse `--crn` outright
  rather than carry that corruption forward. The refusal is not
  temporary plumbing: the `orc.crn_advance()` call both made at the end
  of `solve()` has been deleted along with the method, and the replay
  remains, because it comes from a `MOSOSolver` having no RA iteration
  to advance. What `--crn` should mean for such a solver is
  rng-interface-design.md §11 open question 11. Their
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
  and its `Oracle` method table still lists `crn_advance()` and five
  other `crn_*` methods. **None of them exist any more**: the
  solver-facing `crn_*` surface is removed (`Oracle._advance_iteration()`
  is framework-internal). The README template and table are now
  wrong, not merely inadvisable; they go in the Phase 6 README rewrite,
  with the `python setup.py bdist_wheel` install line.
- `crn_advance()`'s removal is a deliberate 2.0 API change, so it is
  recorded for the CHANGELOG (Phase 6), not in `KNOWN_ISSUES.md`, which
  is for defects. `KNOWN_ISSUES.md` issue 14 (`bump()` removal) is the
  same kind of entry and is inconsistent with that rule; left in place
  for now, to be settled together with this one when the CHANGELOG is
  written. Migration text for both: `bump(x, m)` -> `hit(x, m)`;
  `orc.crn_advance()` in a custom `MOSOSolver` -> delete the line.
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
  touching it. No golden moved.
  `--crn` and `sync=` now also work under Philox, with strides derived
  from its own budget (`REPL_STRIDE = 2^88`, one sync value per key) --
  not MRG's `2^76`, which was the first draft and the second time a
  Philox constant nearly inherited an MRG-specific value (see the end
  of §12 step 9). Every registered generator supports both `crnflag`
  values. The README's `--generator` prose still says Philox does not
  support `--crn`; that sentence is wrong now and goes in the Phase 6
  README rewrite (the generated CLI-help block is already current).
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
  **Not yet:** a cloudpickle `ClassRef` for notebook-defined classes,
  and Spark.
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
  `SometimesInfeasible` case is the detector. §11 entry 13 would
  remove the need.
- MOCOMPASS and MOPBnB still call `hit()` in loops and were not
  converted to `hit_many`.
- Deferred, with reasons, in rng-interface-design.md §11: per-point
  CRN continuation (11: not invisible to RA solvers), unifying
  `solve()`/`testsolve()` layouts (12: buys the executor nothing),
  remembering infeasible points within an iteration (13: a performance
  finding in its own right), a cheaper general jump (14: Phase 3).

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
