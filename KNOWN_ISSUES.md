# Known Issues

This document records defects found in PyMOSO during the 2.0
modernization effort. Work began against a fork based on PyPI 1.0.4;
it has since moved onto the canonical repository,
github.com/pymoso/PyMOSO (currently versioned 1.0.7 in
`pymoso/__init__.py`, though PyPI ships 1.0.8 — the two don't
necessarily agree). Each issue below states which versions it affects
and its status specifically on this branch.

If you have used PyMOSO in work leading to publication, please read
issue 1.

---

## 1. Incorrect pseudo-random stream jump-ahead

**Affects:** all 1.x versions, including the canonical repository's
current master. **Severity:** high — affects numerical results.

### What is wrong

PyMOSO's `mrg32k3a` module advances between pseudo-random streams by
matrix multiplication modulo m1 and m2. That multiplication is performed
in floating point (`mat333mult`). Intermediate row sums reach roughly
2^62 to 2^63, well beyond the 53 bits of integer precision a float64
holds exactly, so the low bits are rounded away before the modular
reduction is applied.

The consequence is that `jump_substream` and `get_next_prnstream` do not
land 2^76 and 2^127 steps ahead as intended. They land near those
positions, with an error that compounds across successive jumps.

The defect is visible in PyMOSO's own output: the six components of the
reported end seed are, in practice, always divisible by 256.

### Scope

The single-step generator is **not** affected. Every individual
simulation replication draws from a correct MRG32k3a stream; this was
verified exactly against brute-force stepping over the full seed range.

The defect is confined to the jump-ahead path. In practice this means:

- The first stream created from a user-supplied seed is correct.
- Every subsequent jump — that is, every `crn_advance()` call, and
  therefore every retrospective approximation iteration after the first,
  and every independent sample path beyond the first — begins at a
  position other than the intended one.

A separate, unrelated change on the canonical repository
(`dfd2a30`, "set rng cache with object methods instead of class
methods") touches how the generator/bsm caches are stored, not the
jump-ahead arithmetic itself; `mat333mult`/`mat311mod` are confirmed
byte-identical to the version this was originally found against (see
`docs/upstream-simpar.md`).

### What this means for results

The stream positions used after the first jump are not the positions the
convergence theory assumes. The affected quantity is the *independence
guarantee* between streams, not the quality of the underlying generator.

We are not currently able to state how large an effect this has on any
particular published result, and we do not want to overstate or
understate it. What can be said:

- Values drawn remain valid MRG32k3a output; they are not degenerate or
  patterned.
- Streams intended to be far apart are still far apart, but not by the
  exact reserved distance, so the guarantee of non-overlap does not
  strictly hold.
- Results will not reproduce bit-for-bit across a fix.

Researchers with published results that depend on stream independence
may wish to re-run and compare.

### Status

Confirmed present on this branch (github.com/pymoso/PyMOSO's master, not
just the earlier fork it was first found against). A fix using exact
integer arithmetic is queued as part of this migration but has not
landed as of this commit; see later commits in this migration for the
fix and the resulting golden baseline recapture.

---

## 2. `--simpar` (parallel simulation replications)

**Affects:** every published 1.x version through at least PyPI 1.0.4.
**Not affected:** github.com/pymoso/PyMOSO's current master.
**Severity:** was high (documented feature entirely non-functional);
now informational.

### History

`Oracle.hit`'s parallel branch called `get_next_prnstream` with one
argument where the function requires two. Any invocation with
`--simpar` of 2 or greater raised `TypeError` on essentially the first
estimate call, and a chain of bare `except:` clauses masked it behind a
generic "Unable to simulate" message with no traceback. This was
confirmed directly against a genuine install of the published PyPI
1.0.4 wheel: `--simpar=2` reproduces the identical crash there.

**Correction to an earlier version of this entry:** it previously
stated `--simpar` "has never worked in any published version." That
claim was based only on 1.0.4 and this fork's own history; it did not
hold once checked against the canonical repository's actual current
state. PyPI's published 1.0.8 (and github.com/pymoso/PyMOSO's master,
commit `917bf06`, "improved multiprocessing for --simpar option") runs
`--simpar=2` successfully — confirmed empirically against a fresh
worktree of that commit, not merely by reading the diff.

### What changed upstream

Commit `917bf06` replaced the old per-`hit()`-call `multiprocessing.Pool`
with a persistent worker pool created once per `solve()` call
(`Oracle.set_simpar`/`mp_cleanup`), and gives each *replication* its own
seed (derived via the same `crn_nextobs()` substream-jump mechanism the
serial path already used) rather than trying to give each *worker* its
own long-lived stream. This is why it composes correctly with CRN where
the old design didn't: there's no second, independently-configured
`Oracle` with its own CRN state involved. Full architectural writeup in
`docs/upstream-simpar.md`.

### Status

Resolved upstream, by `917bf06`, independently of this project's work —
not a fix produced here. Not present on this migration's base as a
result. See `docs/upstream-simpar.md` for the design.

---

## 3. Silent stream overlap past the reserved iteration window

**Affects:** all 1.x versions, including the canonical repository's
current master. **Severity:** moderate — requires non-default settings
to trigger.

`testsolve` pre-instantiates pseudo-random streams for each independent
sample path, reserving a fixed window of 200 retrospective
approximation iterations per path so that common random numbers and
parallelism compose. Nothing enforces this bound upstream.

If a solver exceeds 200 RA iterations, it walks into the next sample
path's reserved streams. This was demonstrated directly: after exactly
201 iterations, one sample path's generator state becomes bit-identical
to the next path's starting seed, and continues to overlap thereafter.
No warning or error is produced.

Under default settings this is unreachable in practice. Iteration
counts grow logarithmically in budget — a budget of 400,000 reaches
roughly 68 to 92 iterations — and reaching 200 would require on the
order of 4x10^9 simulation calls at minimum. The risk arises with an
unusually small `mconst` combined with a very large budget.

**Status:** fixed on this branch. `chnutils.MAX_RI` is now a promoted
module constant (upstream still uses a bare local `max_RI = 200`, never
enforced), and `RASolver.rasolve` raises before starting any RA
iteration beyond it.

---

## 4. Errors reported without tracebacks

**Affects:** all 1.x versions, including the canonical repository's
current master. **Severity:** moderate — obscures other defects.

Bare `except:` clauses in `chnbase.py` catch every exception, including
`KeyboardInterrupt` and `SystemExit`, report a generic message, and call
`sys.exit()`. Programming errors, invalid inputs, and interrupts are all
reported identically as a failure to simulate. This survived upstream's
`917bf06` multiprocessing rewrite unchanged — the bare excepts are still
present, in the same shape, just at different line numbers.

Library use is affected as well: prior to this migration's kwarg-
defaults fix (issue 7), `chnutils.solve`/`testsolve` couldn't even be
called minimally to observe this; once they can, they still exit the
process rather than raising, so callers embedding PyMOSO in their own
programs cannot handle errors.

Issue 2 went undetected for the lifetime of the project on 1.x as a
direct result of this issue.

**Status:** fixed on this branch. Specific exception types, real
tracebacks (via `raise ... from e`), and library code that raises
rather than exits.

---

## 5. Misleading error for an infeasible starting point

**Affects:** all 1.x versions, including the canonical repository's
current master. **Severity:** low.

Passing an infeasible `x0` produces an unhandled `KeyError` with a raw
traceback under `RPE`, and "Unable to run accel()" under `RPERLE` and
`RMINRLE`. The intended message — "Is x0 feasible?" — was guarded by an
`except ValueError` that the failing code path cannot reach (`get_min`
always includes `x0` in its input, so `min()` never raises `ValueError`
on an infeasible `x0`; the real failure is `KeyError`). `RSPLINE`
handles this case correctly on its own, independently.

**Status:** fixed on this branch. `RASolver.get_min` and
`RSPLINE.spsolve` now check feasibility directly and raise a real
`ValueError` naming `x0`; all four built-in solvers report the same
message.

---

## 6. Silent mis-parsing of `--seed` and `--param` on the command line

**Affects:** all 1.x versions, including the canonical repository's
current master (still docopt-based). **Severity:** moderate — requires
a user mistake to trigger (a wrong `--seed` value count, or giving
`--seed` and `--param` in an order no documented example shows), but
produces a completed, apparently-successful run using a silently wrong
seed and/or starting point when it does.

### What is wrong

The CLI's argument parser (docopt) matches positional and repeated-
option groups by total token count across the whole command line, not by
validating each option's own values independently. Concretely:

- `--seed` requires exactly 6 integers. Giving 5, 7, or 8 was not
  rejected as long as enough tokens remained overall: docopt silently
  borrowed a neighboring token — including the problem or solver name —
  into the seed, and shifted `<problem>`/`<solver>`/`<x>` into the wrong
  slots. No error was produced; the run completed normally, using a seed
  built in part from a token like `"ProbTPA"` and, depending on the
  shift, a different problem, solver, or starting point than the one
  actually typed.
- `--param <name> <value>` has the same fixed 2-slot shape. Omitting the
  value shifted everything after it by one slot the same way.
- Giving a `--param` group before a `--seed` group (an order no README
  example shows, though nothing documented it as invalid) caused docopt
  to assign tokens meant for `--param` into the seed instead.

None of these raised an error, printed a warning, or produced an exit
code different from a normal successful run.

### Status

Not fixed on this branch. An argparse-based CLI replacement (and the
CLI characterization tests documenting the exact 1.x behavior above)
were built against this fork's earlier base but are deferred pending
review before being re-applied against the canonical repository's CLI
(`pymoso/cli.py` is still docopt-based here, unchanged by any of the 13
upstream commits). This issue persists on this branch exactly as
characterized until that migration is decided and re-applied.

---

## 7. `chnutils.solve`/`chnutils.testsolve`'s documented library usage has never worked

**Affects:** `chnutils.testsolve`'s `ranx0` gap affects all 1.x
versions, including this fork's original base. The broader
`budget`/`seed`/`simpar`/`isp`/`proc`/`crn` regression below is specific
to the canonical repository: confirmed broken on both its current
master (1.0.7) and PyPI's published 1.0.8, but *not* present at the
version this project originally forked from, where those kwargs already
had defaults. **Severity:** moderate — the CLI was unaffected in either
case, since it always passes every argument explicitly; only direct
library use was broken.

### What is wrong

`chnutils.solve(problem, solver, x0, **kwargs)` and
`chnutils.testsolve(tester, solver, x0, **kwargs)` pop every one of
their keyword arguments (`budget`, `seed`, `simpar`/`isp`+`proc`, `crn`,
and `testsolve`'s `ranx0`) with no default value. Every documented
example of calling either as a library function (README, "A `solve`
Example", "A `testsolve` Example") omits most or all of these, since
none are mentioned as required. Any such call raised `KeyError:
'budget'` immediately, before doing anything else.

On the canonical repository, this is worse than it was on this
project's original fork: commit `917bf06` ("improved multiprocessing
for --simpar option") removed defaults from `budget`/`seed`/`isp`/
`proc`/`crn` that existed at the shared merge-base, as a side effect of
its otherwise-unrelated multiprocessing rework. `ranx0` never had a
default in any version checked. Neither gap is a CLI regression: the
CLI's own commands (`commands/solve.py`, `commands/testsolve.py`)
always compute and pass every one of these arguments explicitly, so the
documented library entry point was never actually exercised by the CLI,
the test suite, or (as far as this project's history shows) any real
caller.

### Status

Fixed on this branch. Defaults are restored matching the CLI's own
documented values (`budget=200`, `seed=(12345,)*6`, `simpar=1`, `isp=1`,
`proc=1`, `crn=False`, `ranx0=False`), defined once in `chnutils.py`
(`DEFAULT_BUDGET` etc.) and referenced by the CLI layer's own Python-
level defaults rather than duplicated, so the two cannot drift apart
silently; `tests/test_kwarg_defaults.py` additionally checks the
constants directly against docopt's own parsed defaults. Calling
`solve`/`testsolve` exactly as the README shows now works without
needing an undocumented keyword argument.

---

## Reporting

Please open an issue at
https://github.com/pymoso/PyMOSO/issues.
