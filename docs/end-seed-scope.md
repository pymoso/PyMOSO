# What the golden "end seed" does and does not verify

Found while implementing `getrandbits()` on `MRG32k3a` (see
KNOWN_ISSUES.md's getrandbits entry): the end-seed baselines in
`tests/test_golden.py` were being treated, in at least one place, as a
general correctness check on "what pymoso computes." They are not.
This note pins down exactly what they check, audits every prior fix on
this branch against that narrower scope, and identifies the one place
a stronger claim than that was actually made.

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
| Silent stream overlap past `MAX_RI` (issue 3) | `test_max_ri.py` asserts `RuntimeError` is/isn't raised, via `monkeypatch.setattr(chnbase, 'MAX_RI', ...)` | No |
| Bare `except:`/`sys.exit()` (issue 4) | `test_error_handling.py` asserts real exception types and chaining (`__cause__`) | No |
| Infeasible-`x0` reporting (issue 5) | `test_infeasible_x0.py` asserts `ValueError` message content per solver | No |
| docopt silent mis-parsing (issue 6) | `test_cli_characterization.py` (frozen docopt behavior) + `test_cli.py`/`test_cli_validation.py` (live parser contract) — argument-parsing logic, orthogonal to RNG consumption entirely | No |
| `chnutils.solve`/`testsolve` kwarg defaults (issue 7) | `test_kwarg_defaults.py` asserts the constants directly against argparse's own defaults. Its two `test_golden.py` companions (`test_library_*_end_seed_matches_baseline`) both pass explicit `x0`/`ranx0=False`, so neither exercises `choice`/`sample` — unaffected by the blind spot even though they do compare end seeds | No |

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

## Aside: two `docs/` references to files that don't exist on this branch

`test_jump_ahead.py`, `test_max_ri.py`, and `test_infeasible_x0.py` all
cite `docs/phase2a-verification.md` for the original defect
characterizations; `CLAUDE.md` cites `docs/phase3-architecture-stocktake.md`
for "current status." Neither file exists in this branch's `docs/` —
both were committed only on the earlier fork's history
(`e273e14`, "Commit outstanding phase 2a/3 artifacts before migrating
to pymoso/master") and weren't carried over when this project rebased
onto github.com/pymoso/PyMOSO. Noted here since it surfaced during this
audit; not otherwise related to end-seed scope, and not fixed as part
of this change.
