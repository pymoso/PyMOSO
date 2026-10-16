# What the golden "end seed" does and does not verify

Found while implementing `getrandbits()` on `MRG32k3a` (see
KNOWN_ISSUES.md's getrandbits entry): the end-seed baselines in
`tests/test_golden.py` were being treated, in at least one place, as a
general correctness check on "what pymoso computes." They are not, as
of when this was written. This note pins down exactly what they check,
audits every prior fix on this branch against that narrower scope, and
identifies the one place a stronger claim than that was actually made.

**Partially superseded by `docs/rng-interface-design.md` §12 step 8.**
This document's central claim -- "end seed fingerprints the stream-
allocation schedule... not... any `choice()`/`sample()`/`randrange()`-
driven decision" -- described `get_solv_prnstreams`/`get_testsolve_
prnstreams`'s schedule-only mechanism, accurately, at the time this was
written. `Oracle.get_endseed()` (step 8 stage 1, `solve()`'s own path)
and its `testsolve()` counterpart (stage 2) both replace that mechanism
with a real oracle-role coordinate high-water mark, so as of both
landing, an `endseed` **does** now reflect actual replication
consumption for both `solve()` and `testsolve()` -- including an
indirect sensitivity to `ranx0`/which `x0` a solver actually searched
from, confirmed directly in `tests/test_solution_sensitivity.py`'s own
`end_seed` assertion (it moved between stage 1 and stage 2, purely from
a `ranx0=True` vs `ranx0=False` difference, something the mechanism
this document describes could never have done). Still true, unchanged:
this remains oracle-role only (§8.2's own scoping) -- solver-role's own
draws (`solvprn`/`xprn`, and whatever `choice()`/`sample()` do with
them) are still not tracked or reflected, so the "does NOT fingerprint
a run's randomness" framing in `CLAUDE.md` is still correct in that
narrower, remaining sense: `endseed` is a stronger signal than before,
not a complete one. The rest of this document (the audit table, the
`tests/test_readme_cli_examples.py` correction, both asides) describes
the pre-step-8 mechanism and its own history accurately; read historic
sections below with that mechanism in mind, not the current one.

## What "end seed" is

`solve()`/`testsolve()` return `(result, endseed)`. `endseed` is the
final value of the `iseed` local variable threaded through
`get_solv_prnstreams`/`get_testsolve_prnstreams` (`chnutils.py`). Both
functions build it the same way: starting from the user's seed, call
`get_next_prnstream`/`jump_substream` a fixed number of times — once
per algorithm stream, once per independent sample path, once per
reserved RA iteration slot (`MAX_RI` of them, `testsolve` only) — and
`iseed` is whatever seed the last of those jump-ahead calls lands on.

That schedule (how many jump-ahead calls happen, in what order) is
fully determined by `isp`, `MAX_RI`, and `crn`, decided before a single
simulation replication runs. It does not read from, and is not
touched by, any oracle's or solver's actual random draws. Concretely:

- `get_testsolve_prnstreams` creates `xprn = MRG32k3a(iseed)` once, for
  `get_ranx0`, and never advances `iseed` from it. Whatever `xprn`
  consumes internally (0 calls, or many, however implemented) has zero
  effect on the returned `endseed`.
- Each oracle/solver stream created along the way is itself a fresh
  `MRG32k3a`, seeded once and then run for however many replications
  the algorithm actually performs — but `iseed` has already moved on to
  the *next* jump-ahead target before that stream does any simulating.
  `iseed`'s value never depends on how many `.random()` calls that
  stream ends up making.
- `--simpar`'s per-replication seeds come from `crn_nextobs()`, the
  same deterministic advance-by-one-fixed-amount mechanism, independent
  of `simpar`'s value (`docs/upstream-simpar.md`) — another jump-ahead
  schedule position, not a consumption-sensitive quantity.

So: **end seed fingerprints the stream-allocation schedule** — a
function of `isp`/`MAX_RI`/`crn`/`simpar`-derived call counts alone.
It does **not** fingerprint anything about what any individual stream
actually produced: not the solution returned, not the number of
replications an estimate actually ran, not which branch a solver took,
and not any `choice()`/`sample()`/`randrange()`-driven decision (e.g.
`get_ranx0`'s random starting point). Two runs can have identical end
seeds while having computed completely different answers.

`tests/golden/README.md` already says this correctly and modestly: "a
pure regression check on the RNG stream's final position -- it does
not (by itself) say anything about solution quality." The scope
problem is not in that file.

## Audit: did any prior fix rely on end-seed matching as its evidence?

Checked every fix in `KNOWN_ISSUES.md` and the golden suite's own two
"library-level" cases against what actually backs each one:

| Fix | Independent evidence | Rests on end-seed alone? |
|---|---|---|
| Jump-ahead precision loss (issue 1) | `test_jump_ahead.py`: brute-force single-step and independent exact-matrix-power references, built from `mrg32k3a()`'s own recurrence, entirely outside `mat333mult`/`mat311mod` | No |
| `--simpar` crash (issue 2, now resolved upstream) | `test_simpar_worker_lifecycle.py` checks process exit/timeout directly; `rperle_tpa_simpar2 == rperle_tpa` rests on `crn_nextobs()`'s deterministic per-replication seed assignment (`docs/upstream-simpar.md`), the same schedule-position category end-seed itself measures, not a consumption claim | No |
| Silent stream overlap past `MAX_RI` (issue 2) | `test_max_ri.py` asserted this at the time (removed along with `MAX_RI` itself, §12 step 4b: the reserved-window guard was replaced by `point_code`/`offset_within_iteration` collision-free-by-construction, not by a stronger check on the same guard). Current coverage: `tests/test_oracle_visit_sync.py`'s `test_iteration_and_replication_never_overflow_one_isp_stride_block`/`test_no_collision_between_isp_paths_at_iteration_counts_well_beyond_max_ri` | No |
| Bare `except:`/`sys.exit()` (issue 3) | `test_error_handling.py` asserts real exception types and chaining (`__cause__`) | No |
| Infeasible-`x0` reporting (issue 4) | `test_infeasible_x0.py` asserts `ValueError` message content per solver | No |
| docopt silent mis-parsing (issue 5) | `test_cli.py`/`test_cli_validation.py` (live parser contract) — argument-parsing logic, orthogonal to RNG consumption entirely. (`test_cli_characterization.py`'s frozen docopt behavior was independent evidence too, until it was deleted as an undeclared test-time dependency; see `KNOWN_ISSUES.md` issue 5.) | No |
| `chnutils.solve`/`testsolve` kwarg defaults (issue 6) | `test_kwarg_defaults.py` asserts the constants directly against argparse's own defaults. Its two `test_golden.py` companions (`test_library_*_end_seed_matches_baseline`) both pass explicit `x0`/`ranx0=False`, so neither exercises `choice`/`sample` — unaffected by the blind spot even though they do compare end seeds | No |

Every fix that mattered had a check that didn't go through end-seed
matching at all, or, in the `--simpar` case, went through a claim about
seed *assignment* rather than seed *consumption* — a distinction the
blind spot doesn't touch. **Nothing slipped through** among the fixes
this branch has made.

## The one place a stronger claim actually was made

`tests/test_readme_cli_examples.py`'s module docstring:

> This checks invocability only -- that the command parses and the run
> completes without error -- not correctness of the result. Correctness
> of what pymoso computes is what tests/test_golden.py's end-seed
> baselines are for; this file would not notice a wrong answer.

This overstates what end-seed baselines back, in two ways:

1. Only 8 of the 20+ concrete `pymoso ...` invocations parsed out of
   the README are in `test_golden.py`'s `CASES` at all. The rest have
   no correctness check anywhere — this file only asserts exit code 0.
2. Even for the 8 that are covered, "correctness" there means "lands
   on the same stream-schedule position," not "computed the same
   solution" — which is a much narrower property than the docstring's
   phrasing ("correctness of what pymoso computes") implies.

No evidence any actual regression was masked by this — it isn't
retroactively checkable, and every substantive fix on this branch had
independent coverage per the table above regardless. This is a
documentation-accuracy problem, not a known miss. Flagging it here
rather than editing it in the same pass as the getrandbits work; worth
a small standalone correction (weaken the claim to match what
end-seed matching actually establishes, and note the 8-of-20+ coverage
gap) whenever that file is next touched.

## Aside: two `docs/` references that didn't exist on this branch (fixed in a follow-up commit)

`test_jump_ahead.py`, `test_max_ri.py`, and `test_infeasible_x0.py` all
cite `docs/phase2a-verification.md` for the original defect
characterizations; `CLAUDE.md` cited `docs/phase3-architecture-stocktake.md`
for "current status." Neither file existed in this branch's `docs/` at
the time this note was first written — both were committed only on the
earlier fork's history (`old-work`, `e273e14`, "Commit outstanding phase
2a/3 artifacts before migrating to pymoso/master") and weren't carried
over when this project rebased onto github.com/pymoso/PyMOSO.

Resolved differently for each, on the theory that porting a stale
"current status" doc is worse than not having one, but porting a
historical discovery record that's still cited by number from live
tests is worth doing honestly:

- `docs/phase2a-verification.md` was ported from `old-work`, with a
  provenance header explaining its file/line references are to that
  fork's layout, and pointing each item at whatever currently
  re-verifies it on this branch (the permanent tests, and, for issue
  1, a direct 1.0.8 check).
- `docs/phase3-architecture-stocktake.md` was **not** ported —
  it predates the docopt/argparse redo, the README layers work, and the
  RNG fixes, so presenting it as "current status" would misinform
  rather than help. `CLAUDE.md`'s citation was corrected instead to say
  no single current-status document exists.

## A second instance of the same failure mode

Found while planning `docs/rng-interface-design.md`'s §12 step 8, in a
different test file: `tests/test_oracle_noncrn_default.py`'s
`LoggingOracle.g()` reads `rng.get_seed()[0]` and returns -- it never
calls `random()`/`normalvariate()`/`getrandbits()`, so it never
actually draws from the stream `hit()` hands it. That file's
disjointness assertions compare *starting coordinates* across
replications, which genuinely are distinct by construction (that's
what `offset_within_iteration` guarantees). What they were being read
as backing -- that replications don't collide -- is a claim about
*drawn values*, not starting coordinates, and nothing in that test
suite ever checked that.

It doesn't, for any real `g()`: `offset_within_iteration` packed
`replication` at stride 1 (no reserved margin), and every built-in
problem's `g()` draws more than one raw value per replication
(`ProbTPA`/`ProbTPB`/`ProbTPC`: 3 `normalvariate()` calls; `BSProb`:
~1000 `expovariate()` calls). Confirmed directly: replication 1's
first two draws were bit-identical to replication 0's second and third
-- two supposedly independent replications sharing 2 of 3 raw values.
Fixed by giving `replication` a real reserve
(`pymoso/prng/base.py`'s `REPL_RESERVE_BITS`, enforced at the call site
in `chnbase.py`'s `_hit_via_coordinate`, which raises
`ReplicationDrawOverflow` rather than silently overlapping if a `g()`
draws past its reserve) -- see `docs/rng-interface-design.md`'s §12
step 8 prerequisite writeup and `tests/test_replication_independence.py`,
whose `MultiDrawOracle` double calls `normalvariate()` for real and
checks disjointness of the *values drawn*, the property that actually
matters.

This is the same shape as this file's own finding, not a coincidence:
a test that is real, passes honestly, and asserts something true --
just not the thing its own coverage is being relied on for. Two
occurrences in the same body of RNG work is enough to name as a
pattern worth watching for generally, not just in these two files:
**a test double that doesn't exercise the mechanism under test proves
nothing about that mechanism**, however plausible its assertions read.
Concretely, for any future RNG-interface test: a stub `g()`/stream
handed to the code under test has to call the actual draw-producing
methods (`random`/`getrandbits`/`normalvariate`) if the test means to
say anything about what gets drawn -- reading positional/state
attributes instead (`get_seed()`, an `iseed` local, ...) only ever
proves something about scheduling, never about consumption.

## A third instance: a patch on a name nobody reads

Found while surveying for Phase 5 (the decomposition of `chnbase.py`
and `chnutils.py`), before it could happen rather than after.

`tests/test_get_nbors_equivalence.py` proves that the rewritten
`get_nbors` gives whole solver runs identical to the box enumeration it
replaced. It does so by running each solver twice, once with each
implementation patched in. There are two readers to reach: the solver
bases call `get_nbors` through the name `chnbase` imported, and
`get_setnbors` calls it through the name in its own module. So the
test patched two module attributes, `chnbase.get_nbors` and
`chnutils.get_nbors`.

A patch replaces a name in one module. It reaches a caller only if
that caller looks the name up *there*. When the helpers moved to
`pymoso/moso.py`, `get_setnbors` began reading `moso.get_nbors`, and
`chnutils.get_nbors` became a re-export that no code reads. A patch on
it still applies without complaint, to nothing.

Measured, with the helpers moved and the patches left where they were:
**every one of the file's 24 whole-run comparisons still passed, and
so did `test_insertion_order_is_what_keeps_results_the_same`, the
test's own "detector, shown detecting".** The comparisons were by then
partly comparing the new `get_nbors` with itself. How much had been
lost depends on the kind of error:

| a wrong `get_nbors` that... | runs that notice, both readers patched | solver bases only |
| --- | --- | --- |
| drops one neighbour | 24 of 24 | 17 of 24 |
| returns the same points in hashed order | 8 of 24 | 8 of 24 |
| returns the same points in reverse order | 10 of 24 | 10 of 24 |

So the existing detector could not have seen it: it uses a reordering,
and in these runs the `get_setnbors` path is not sensitive to order at
all. It is sensitive to content. The detector had been shown detecting
one kind of error through one of the two paths, and was being read as
covering the test.

Fixed in the commit that moved the helpers: the patches name `moso`
and `chnbase`, and `test_a_missing_neighbour_is_noticed_by_every_run`
requires a neighbourhood one point short to change all 8 radius-1
runs. With the patch left on `chnutils` it fails (4 of 8), which was
observed before the fix went in.

### The pattern, now three times

1. The end seed was read as checking what a run computes, and checked
   the allocation schedule.
2. `LoggingOracle` was read as showing replications do not collide,
   and never drew from its stream.
3. The whole-run comparison was about to be read as comparing two
   implementations, and compared one with itself along one path.

In each the test is real, passes honestly, and asserts something true.
What fails is the link between the test and the code it is believed to
exercise, and nothing in a green run shows that link. The second
instance gave the rule for test doubles. The general form, for whoever
writes tests here next:

- **A test that works by substitution -- a stub, a patch, a recording
  wrapper -- needs its own proof that the substitute was reached.**
  Break the thing substituted and watch the test fail. A patch that
  applies cleanly proves only that the name existed.
- **Patch the name the caller reads.** `from m import f` gives the
  importing module its own name for `f`. After any move, every
  `monkeypatch.setattr(module, name, ...)` in the suite is suspect:
  the attribute may still exist as a re-export, and the patch will
  succeed. Phase 5's survey listed these sites for exactly that
  reason.
- **A detector shown detecting one error has been shown detecting that
  error.** The reordering detector was sound and did not cover a
  missing point; the missing-point detector does not cover order. Say
  which error a detector was seen to catch, and through which path.

### The same hazard in the checking itself

A mutation check ("break it and watch the test fail") can also report
something other than what was run. In Phase 5 one did: three mutations
were applied to `pymoso/chnutils.py` in quick succession, each reverted
with `git checkout`, and the third reported the second's failure.
Python reuses a cached `.pyc` when the source's size and modification
time (to the second) match the ones recorded in it. `del front` and
`import os` are each ten bytes with their newline, and the edits fell
in the same second, so the interpreter ran the previous mutation's
bytecode against the new source.

The third mutation, rerun with caching off, did fail, and for its own
reason. But a mutation that *should* have passed would have "failed"
the same way, and a mutation the test could not see might have been
recorded as caught.

When editing and re-running quickly -- mutation checks, or swapping
file versions to test an earlier stage -- set
`PYTHONDONTWRITEBYTECODE=1` and delete `__pycache__` first. And read a
failure's message, not only that it failed: this was caught because
the assertion named `front`, which that mutation had not touched.

## A fourth and a fifth instance

**Fourth: a spy on a name `Oracle` no longer called.** When
`Oracle.replication_draws` landed (commit `5ffba8c`),
`tests/test_point_code_fallback.py`'s end-to-end test was spying on
`mrg32k3a.encode_point`, which `Oracle` had stopped calling. It is the
third instance's shape again: a substitute on a name nobody reads. It
differs in one way worth keeping. The test's own assertion ("more than
100 points hashed") counted what the spy saw, so it failed loudly
instead of passing on nothing. The spy now patches
`prng.base.encode_point`, the name `Oracle` reads. A test that asserts
the substitute was reached is the rule above, built into the test.

**Fifth, and the broadest: subprocess tests can test a different tree
from the rest of the suite.** Found 2026-10-16, running the suite in
the `many-objective` worktree. Every test that starts a fresh
interpreter does so with `-I`: `tests/_pymoso_cli.py`'s
`pymoso_argv`, and direct `[sys.executable, "-I", ...]` calls. `-I`
ignores PYTHONPATH and the current directory, by design (KNOWN_ISSUES
issue 9), so the subprocess imports the *installed* pymoso. The test
process imports whatever is first on its own `sys.path`. In a second
worktree sharing `.venv-dev`'s editable install, or under
`python -m pytest` from another checkout, those are two different
trees.

- **Seen:** 7 failures, from the main checkout's staged solver rename,
  reproduced on an untouched export of the same commit.
- **Not seen, and the point of recording it:** every other `-I` test in
  that run passed against code that was not under test. That includes
  the public-surface cycle check, the dependency boundary, the remote,
  by-value and Spark tests, and all CLI tests.

The previous four were one assertion or one file each. This one
covers every subprocess test at once, and nothing in a green run shows
it. The helper was not bypassed: it does exactly what its docstring
promises. The unchecked link is between "the installation" and "the
tree under test".

The finding, with the proposed guard, is in
`.git/manyobj/finding-subprocess-tree.md` (local to this machine; the
durable summary is in `docs/phase7-plan.md`). The guard compares the
in-process `pymoso.__file__` with the `-I` subprocess's at session
start, and stops on a mismatch. **It is Phase 7's first task, before
anything is measured in a worktree**, because measurements would
inherit the problem.
