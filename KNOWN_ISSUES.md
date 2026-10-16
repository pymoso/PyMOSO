# Known Issues

This document records defects found in PyMOSO during the 2.0
modernization effort. Work began against a fork based on PyPI 1.0.4;
it has since moved onto the canonical repository,
github.com/pymoso/PyMOSO (versioned 1.0.7 in `pymoso/__init__.py`
when the work began, though PyPI shipped 1.0.8 — the two did not
agree). 1.1.0 has since been released from its own branch; this
document belongs to the 2.0.0 line. Each issue below states which versions it affects
and its status specifically on this branch.

Issues are grouped by whether they affect a version anyone is known to
have used. PyMOSO had no known users prior to 1.0.8: versions 1.0.0
through 1.0.7 were development releases pushed to PyPI while the paper
(Cooper & Hunter 2018) was in progress, and users arrived only after
the preprint was archived, which was after 1.0.8 shipped.
---

## Affects released, used versions (up to 1.0.8)

### 1. Incorrect pseudo-random stream jump-ahead

**Affects:** all 1.x versions.  **Severity:** high — alters the numerical
output of individual runs.

**Verified against 1.0.8:** `pymoso solve --budget=1000 ProbTPA RPERLE
40 40` on a real 1.0.8 install reports ending seed
`738848768 2094673920 3003824128 304680960 1844190720 1414365184` —
all six components divisible by 256, the exact fingerprint described
below.

#### What is wrong

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
reported end seed were, in practice, always divisible by 256.

#### Scope

The single-step generator is **not** affected. Every individual
simulation replication draws from a correct MRG32k3a stream; this was
verified exactly against brute-force stepping over the full seed range.

The defect is confined to the jump-ahead path. In practice this means:

- The first stream created from a user-supplied seed is correct.
- Every subsequent jump — that is, every `crn_advance()` call, and
  therefore every retrospective approximation iteration after the first,
  and every independent sample path beyond the first — begins at a
  position other than the intended one.

#### What this means

What the defect affects is numerical output — the specific solutions and
metric values a given run produced. 

- The generator was producing valid MRG32k3a output throughout; values
  are not degenerate or patterned.
- Streams intended to be far apart are still far apart, but not by the
  exact reserved distance, so the guarantee of non-overlap does not
  strictly hold.
- Numerical output (end seeds, per-run solution and metric values) will
  not reproduce bit-for-bit across the fix.

#### Status

Confirmed present on this branch (github.com/pymoso/PyMOSO's master, not
just the earlier fork it was first found against). Fixed on this
branch using exact integer arithmetic (`mat333mult`/`mat311mod`); see
`tests/test_jump_ahead.py` for the brute-force/exact-matrix-power
equivalence tests that verify the fix independently of the golden
end-seed suite.

---

### 2. Silent stream overlap past the reserved iteration window

**Affects:** all 1.0.x versions. **Severity:** moderate — requires
non-default settings to trigger.

**Verified against 1.0.8:** `chnutils.py` (site-packages) still has a
bare local `max_RI = 200` used only as a `range()` bound in
`get_testsolve_prnstreams`, with nothing checking a solver's actual RA
iteration count against it.

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
order of 4x10^9 simulation calls at minimum. The risk arises with a very
large budget.

`hit()`'s `crnflag=False` path moved onto
point_code`/`offset_within_iteration` coordinates, which
are collision-free by construction rather than by an enforced ceiling
— there is no longer a reserved-window bound to overrun.

---

### 3. Errors reported without tracebacks

**Affects:** all 1.0.x versions. **Severity:** moderate — obscures other
defects.

**Verified against 1.0.8:** `chnbase.py` (site-packages) still has
bare `except:` clauses (confirmed at two live call sites) and multiple
`sys.exit()` calls in library code.

Bare `except:` clauses in `chnbase.py` catch every exception, including
`KeyboardInterrupt` and `SystemExit`, report a generic message, and call
`sys.exit()`. Programming errors, invalid inputs, and interrupts are all
reported identically as a failure to simulate.

Library use is affected as well: prior to this migration's kwarg-
defaults fix (issue 6), `chnutils.solve`/`testsolve` couldn't even be
called minimally to observe this; once they can, they still exit the
process rather than raising, so callers embedding PyMOSO in their own
programs cannot handle errors.

Issue 2 went undetected for the lifetime of the project on 1.x as a
direct result of this issue.

**Status:** fixed on this branch. Specific exception types, real
tracebacks (via `raise ... from e`), and library code that raises
rather than exits.

---

### 4. Misleading error for an infeasible starting point

**Affects:** all 1.0.x versions. **Severity:** low.

**Verified against 1.0.8:** `pymoso solve --budget=500 ProbTPA RPE 100
100` (infeasible: `ProbTPA` is feasible on `[0,50]^2`) raises an
unhandled `KeyError: (100, 100)` with a raw traceback; the same `x0`
under `RPERLE` reports `RPERLE Error: Unable to run accel(). Message:
(100, 100)`.

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

### 5. Silent mis-parsing of `--seed` and `--param` on the command line

**Affects:** all 1.0.x versions. **Severity:**
moderate — requires a user mistake to trigger (a wrong `--seed` value
count, or giving `--seed` and `--param` in an order no documented
example shows), but produces a completed, apparently-successful run
using a silently wrong seed and/or starting point when it does.

**Verified against 1.0.8:** `pymoso solve --budget=200 --seed 1 2 3 4
5 ProbTPA RPERLE 40 40` (5 seed values instead of 6) does not reject
the malformed `--seed`. docopt silently pulled `ProbTPA` into the seed
slot instead, confirmed by the resulting traceback:
`ValueError: invalid literal for int() with base 10: 'ProbTPA'` —
proof docopt handed the seed parser a token count matching what it
expected, not what was typed. A different malformed count can just as
easily land on valid integers throughout and produce no error at all,
per the mechanism below.

#### What is wrong

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

#### Status

Fixed on this branch. `pymoso/cli.py` is argparse-based; `--seed`
(`nargs=6`) and `--param` (`nargs=2`) are each validated for their own
fixed arity independent of the rest of the command line, closing the
total-token-count matching this entry describes. Confirmed directly,
not assumed: `--seed 1 2 3 4 5 ProbTPA RPERLE 40 40` (5 values) now
exits 2 with `error: argument --seed: invalid int value: 'ProbTPA'`;
`--param lb --seed 1 2 3 4 5 6 ...` (missing `--param` value) exits 2
with `error: argument --param: expected 2 arguments`. Neither silently
completes a run with a wrong seed or starting point.

---

### 6. `chnutils.solve`/`chnutils.testsolve`'s documented library usage
has never worked without additional code

**Affects:** `chnutils.testsolve`'s `ranx0` gap affects all 1.x
versions, including this fork's original base.
**Severity:** moderate — the CLI was unaffected in either
case, since it always passes every argument explicitly; only direct
library use was broken.

**Verified against 1.0.8:** `chnutils.py` (site-packages) pops
`budget`/`seed`/`simpar`/`crn` (in `solve`) and
`budget`/`seed`/`isp`/`proc`/`ranx0`/`crn` (in `testsolve`) with no
default value on any `kwargs.pop(...)` call.

#### What was wrong

`chnutils.solve(problem, solver, x0, **kwargs)` and
`chnutils.testsolve(tester, solver, x0, **kwargs)` pop every one of
their keyword arguments (`budget`, `seed`, `simpar`/`isp`+`proc`, `crn`,
and `testsolve`'s `ranx0`) with no default value. Every documented
example of calling either as a library function (README, "A `solve`
Example", "A `testsolve` Example") omits most or all of these, since
none are mentioned as required. Any such call raised `KeyError:
'budget'` immediately, before doing anything else.


#### Status

Fixed on this branch. Defaults are restored matching the CLI's own
documented values (`budget=200`, `seed=(12345,)*6`, `simpar=1`, `isp=1`,
`proc=1`, `crn=False`, `ranx0=False`), defined once in `chnutils.py`
(`DEFAULT_BUDGET` etc.) and referenced by the CLI layer's own Python-
level defaults rather than duplicated, so the two cannot drift apart
silently; `tests/test_kwarg_defaults.py` additionally checks the
constants directly against argparse's own parsed defaults (originally
checked against docopt's; rewritten as part of the docopt→argparse
migration, before which this line was stale). Calling
`solve`/`testsolve` exactly as the README shows now works without
needing an undocumented keyword argument.

---

### 7. User-supplied problem/tester files hang `--simpar`/`--proc` on Python 3.14+

**Affects:** all 1.x versions, including 1.0.8 and this branch. 

**Verified against 1.0.8:** `commands/solve.py` and
`commands/testsolve.py` both register a user's `<file>.py` into
`sys.modules['pymoso.problems.<name>']`/`sys.modules['pymoso.testers.<name>']`
purely in-process (`sys.modules[mod_name] = module`), with no real file
backing that name in the installed package — byte-identical to this
branch's mechanism. `Process`/`Pool` usage in `chnbase.py`/`chnutils.py`
is likewise unchanged. Full diagnosis, including a minimal
reproduction independent of pymoso, in `docs/forkserver-hang.md`.

`--simpar`/`--proc` dispatch simulation jobs through a
`multiprocessing.Queue`/`Pool`, carrying the problem/tester class by
reference. Unpickling that reference in a worker re-imports the
synthetic module name. Under `fork` (the default on Python 3.10-3.13),
the worker inherits the parent's `sys.modules` via copy-on-write and
this works. Under `forkserver` — **the new default on Linux as of
Python 3.14** — each worker starts fresh and the re-import genuinely
fails (`ModuleNotFoundError`). `multiprocessing` doesn't propagate a
crashed worker's exception to its parent, so the parent blocks forever
waiting for that worker's result. No error, no traceback, no exit —
just an indefinite hang.

Built-in problems/testers (`ProbTPA`, `TPATester`, etc.) are real,
properly-installed submodules and are not affected — only files passed
by path on the command line.

**`--simpar` and `--proc` are not the same fix, despite the shared
symptom.** They dispatch through structurally different mechanisms:

- `solve()`'s `--simpar` path (`Oracle.set_simpar`/`hit`, raw
  `Process`+`Queue`) sends one job per *replication*, each carrying the
  problem *class* (plus `x`, a seed) — reconstructing a class from
  source is tractable, and is what this branch's fix does (see below).
- `testsolve()`'s `--proc` path (`chnutils.par_runs`,
  `multiprocessing.Pool`) sends one job per *independent sample path*,
  each carrying a fully-constructed, **already-seeded `Oracle`
  instance** (live RNG state included), not a class reference.
  Reconstructing a *live object mid-computation* from transportable
  data is a different, harder problem than reconstructing a class from
  its source — the class fix does not extend to it. `tests/test_multifile_transport.py::test_multifile_problem_under_proc_matches_serial`
  documents this as reproducible (not suspected): `xfail`,
  conditional on Python 3.14+, confirmed actually firing there
  (30s timeout, not a hang eating the suite) before being marked as
  such.

**Status:** fixed on this branch, both halves.

- `solve()`/`--simpar`: source-bundle transport (`pymoso/executor.py`),
  as above.
- `testsolve()`/`--proc`: nothing live is sent to a worker any more. A
  sample path travels as data (`chnutils.PathJob`: the path's index,
  the run's seed, the generator's name, `x0`, the budget, the solver
  parameters) and the worker rebuilds the path's streams and its
  `Oracle` from that. The tester and solver *classes* are sent once per
  worker, as source bundles when they came from user-supplied files --
  a custom solver file is covered the same way a problem is. Metric
  computation (`--metric`, `chnutils.par_diff`) uses the same
  transport; it used to pickle a tester *instance*, and was a second
  place this hang occurred. With `--proc=1` (the default) no worker
  process is started at all.
- A worker that cannot load what it was sent now fails the run with
  that error when the pool opens; it cannot become a hang
  (`pymoso/pool.py`).

The paragraph above describing the `--proc` path as unfixed is kept as
the record of what was wrong.

What the five skipped tests turned out to be, checked by running each
against the code before the fix on Python 3.14 (forkserver):

| Test | Before the fix | What it exercises now |
|---|---|---|
| README example, `testsolve ... --crn --seed ... mytester.py RPERLE` | **passed** | one process, nothing transported |
| README example, `testsolve --metric mytester.py RPERLE` | hung, in the metric computation | one process, nothing transported |
| README example, `testsolve --crn --metric --isp=100 mytester.py RPERLE` | hung, in the metric computation | one process, nothing transported |
| README example, `testsolve --crn --metric --isp=100 --proc=20 mytester.py RPERLE` | hung, in the metric computation | paths and metrics on workers |
| `test_multifile_problem_under_proc_matches_serial` | hung, in the paths | paths and metrics on workers |

Two things follow. The first README example was never broken: it was
skipped by a `pytest.xfail()` call made before the command ran, so
nothing ever observed it. (`pymoso/examples/mytester.py` adds its own
directory to `sys.path`, which a forkserver worker inherits, so the
path's `Oracle` unpickled there; without `--metric` nothing else was
sent.) And two of the three README examples that did hang are fixed by
no longer using a pool for one process, not by transport. The
transport itself is exercised by the `--proc=20` example,
`tests/test_multifile_transport.py` (a multi-file problem and tester,
and a multi-file custom solver, on two workers, compared with the
serial run) and `tests/test_path_jobs.py` (every start method the
platform has).

**A behaviour change that comes with it.** `testsolve(..., proc=N)`
with `N > 1` and a tester or solver class that a worker cannot find by
name -- defined in a notebook cell, a REPL, or inside a function --
used to work under the `fork` start method (Linux, Python 3.13 and
earlier) and nowhere else. It now raises a `ValueError` naming the
class, under every start method, before any worker starts. `proc=1`
still works for such a class. Carrying a class like that to a worker
needs pickling by value (cloudpickle, as an optional extra), which is
not implemented.

*Since Phase 4:* implemented. With cloudpickle installed
(`pip install pymoso[notebook]`) such a class is sent by value and
`proc=N`/`simpar=N` work with it, under every start method. Without
cloudpickle the `ValueError` above is unchanged except that it names
the extra. docs/spark-backend.md.

Verified on Linux under `fork`, `forkserver` and `spawn`. macOS and
Windows are covered by the CI matrix only.

---

### 8. `--simpar`/`--proc` worker processes leak if the parent is killed externally

**Affects:** all 1.x versions. **Severity:** moderate — requires an
external kill (not a normal Python exception) to trigger, but leaves
worker processes running indefinitely when it does.

**Verified against 1.0.8:** `chnbase.py`'s `Oracle.set_simpar`/
`mp_cleanup`/`__exit__` structure predates this branch's own fix for
the in-process error-path leak and is
otherwise unchanged in 1.0.8.

`Oracle.mp_cleanup()` (`terminate()`+`join()` on every worker process)
only runs via the `set_simpar` context manager's `__exit__`, which
Python only calls when the `with` block's frame unwinds — a normal
return, or a raised exception propagating through it. If the *parent*
process itself is killed externally (SIGKILL, SIGTERM to a process
group, a supervisor deciding a hung process should die — including
killing it in response to issue 7's hang), `__exit__` never runs, and
every worker process it spawned is orphaned, alive, and blocked
waiting on its input queue indefinitely. Observed directly while
investigating issue 7: worker/forkserver processes from an earlier
killed test run were still alive 45+ minutes later.

This is distinct from the already-fixed in-process error-path leak.
That fix only covers exceptions the interpreter sees; it cannot cover
the process being killed out from under itself.

**Status:** fixed on this branch for an idle worker; bounded, not
eliminated, for a busy one.

No parent-side mechanism can close this gap (`SIGKILL` cannot be
caught), so the workers notice for themselves. Every worker belongs to
one pool (`pymoso/pool.py`) and blocks reading its own pipe from the
parent. When the parent dies, however it dies, the operating system
closes the parent's end and the worker reads end-of-file and exits.

- An idle worker exits at once.
- A worker in the middle of a task finishes that task first -- for
  `--simpar` its share of the current replications, for `--proc` the
  whole sample path it is running -- and exits when it fails to send
  the result. It is not interrupted. For a long `--proc` path that is
  a long time; the leak is now bounded by the work in hand rather than
  indefinite.

Under the `fork` start method this needed one more thing: a forked
worker inherits the parent's ends of every pipe open at the time,
including its own, which would hold them open after the parent's death.
Each worker closes them as its first act. Without that step the test
below fails under `fork` and passes under `forkserver` and `spawn`.

`tests/test_worker_pool.py::test_workers_exit_when_the_parent_is_killed`
kills a parent holding idle workers, and one holding busy workers,
under every start method the platform has. Verified on Linux (`fork`,
`forkserver`, `spawn`); macOS and Windows by the CI matrix only.

---

### 9. A multi-file custom problem or tester fails to load at all

**Affects:** all 1.0.x versions. **Severity:** high for anyone it applies
to — immediate crash, no workaround short of inlining everything into
one file — but scoped narrowly: only custom problem/tester files
supplied on the command line by path (`pymoso solve myproblem.py ...`,
`pymoso testsolve mytester.py ...`), not the four built-in problems/
testers (`ProbTPA`, `TPATester`, etc.), which are real installed
submodules and load normally regardless of this issue. Single process,
no `--simpar`/`--proc` involved — this is unrelated to issue 7.

**What is wrong:** `commands/solve.py`/`commands/testsolve.py` load a
user's file via `importlib.util.spec_from_file_location` +
`exec_module`, but never add that file's own directory to `sys.path`
first. If the file imports anything from a sibling module in the same
directory — the realistic shape for any nontrivial simulation, where
the objective computation is factored out rather than inlined — that
import fails immediately: `ModuleNotFoundError`, raw traceback, no
useful message pointing at the actual cause.

**Verified against 1.0.8:** a fixture (`myproblem.py` importing a
sibling `helper.py`, `scratch/multifile_cli_check/`) run via `pymoso
solve --budget=200 myproblem.py RPERLE 40`, from inside the fixture's
own directory (ruling out a cwd-on-`sys.path` explanation, not just
single-process/no-parallelism), fails identically on a real PyPI 1.0.8
install and on this branch: same `ModuleNotFoundError: No module named
'helper'`, same crash site (`commands/solve.py:47`,
`spec.loader.exec_module(module)`). Confirmed no alternate loading path
exists — `sys.path` is never touched anywhere in `commands/solve.py`,
`commands/testsolve.py`, or `cli.py`, on either version.

**Status:** fixed on this branch. `commands/basecomm.py`'s
`load_user_module` inserts the user file's directory onto `sys.path`
before executing it and restores `sys.path` afterward; both
`commands/solve.py` and `commands/testsolve.py` load user files through
it.

---

### 10. `testsolve()`'s path-0 oracle stream and the last path's solver stream share a starting seed

**Affects:** confirmed on this branch's current code; **not** checked
against 1.0.8 or the canonical repository, unlike issue 9 above — the
shape of `get_testsolve_prnstreams`'s solver-stream derivation loop
(accumulate `iseed` by jumping `ITER_STRIDE` once per solver stream,
then use the final value directly as `orc_root`) looks like it predates
the RNG redesign rather than being introduced by it, but that is an
inference from reading the code, not a verified historical claim the
way issue 9's is. **Severity:** correctness — a real independence
violation between two roles `--isp`/`testsolve()` is supposed to keep
independent, not just a labeling issue, though its practical effect on
any given run's reported solution depends on how much the affected
solver's own randomness actually influences its result.

**What is wrong:** `get_testsolve_prnstreams(num_trials, iseed, ...)`
builds each solver-role stream by repeatedly jumping `iseed` forward by
one `ITER_STRIDE` (`solprn = get_next_prnstream(iseed); iseed =
solprn.get_seed()`), then sets `orc_root = iseed` directly once the
loop ends. The last solver stream built (`solprn_lst[-1]`) and
`orc_root` therefore land at the *identical* position — and
`orcprn_lst[0] = stream_at(orc_root, 0, 0)` is a zero-jump from
`orc_root`, so it starts from that same raw seed too. Confirmed
directly, not inferred from reading the code alone:

```
orc_root:                    (2338701263, 1119171942, 2570676563, 317077452, 3194180850, 618832124)
solprn_lst[-1].get_seed():   (2338701263, 1119171942, 2570676563, 317077452, 3194180850, 618832124)
orcprn_lst[0].get_seed():    (2338701263, 1119171942, 2570676563, 317077452, 3194180850, 618832124)
```

`orcprn_lst[0]` becomes the *oracle*-role stream for `--isp` path 0
(simulation draws via `g()`); `solprn_lst[-1]` becomes the *solver*-role
stream for the *last* path (that solver's own algorithm-level
randomness — sampling, iteration order, whatever it draws beyond
simulation calls). Both are used in the same `testsolve()` run, by
different paths and different roles, from the identical starting point
— not the independence `--isp` paths are meant to have from each other,
found tracing the exact seed math ahead of §12 step 6b's own generic
(backend-agnostic) rewrite of this function, not by looking for bugs.
Unconditional: happens for any `num_trials >= 1`, not an edge case.

**A second, separate defect in the same function: every path's
results depended on `--isp`.** The oracle role's root was not a fixed
position; it was the seed the solver-stream loop happened to end on,
which is stream `isp` counted from the run's seed. So the oracle
streams of *every* path, path 0 included, moved whenever the number of
paths changed:

```
--isp=1   solver streams [1]            oracle root at stream 1
--isp=2   solver streams [1, 2]         oracle root at stream 2
--isp=4   solver streams [1, 2, 3, 4]   oracle root at stream 4
```

This is not the seed sharing above, and for most users it matters
more. Extending a study from 100 sample paths to 200 -- the ordinary
way `testsolve` is used -- silently changed the results of the first
100: the first 100 paths of the second run are not the first run's
paths. Nothing raised and nothing looked wrong; each run was internally
valid. Confirmed directly: `testsolve(..., isp=2)` and the first two
paths of `testsolve(..., isp=3)` returned different solution sets,
call counts and high-water marks
(`tests/test_testsolve_role_layout.py`, observed failing before the
fix). `solve()` was never affected by either defect -- it has one path
and builds its two streams separately.

**Status:** both fixed on this branch. `testsolve()`'s three roles now
live in separate, bounded zones on a fixed grid, in whole streams from
the run's seed:

- stream 0: the starting-point (`x0`) stream;
- stream 1 + *t*: path *t*'s solver stream;
- slot *t* + 1 (one slot is `ISP_STREAM_SPAN` streams): path *t*'s
  oracle streams.

No two roles share a position, and no position depends on `--isp`, so
path *t* is the same run however many paths are requested. Each zone
raises at its boundary instead of running into the next: `IspOverflow`
if more paths are requested than the selected generator's layout holds
(`mrg31k3p`'s ceiling, about 6.7e7 paths, is the tightest of the three,
a consequence of its shorter period), and `RoleDrawOverflow` if a
solver or `x0` stream draws more than one whole stream.

**The fix changes every `testsolve()` result.** Any `testsolve` output
from this branch before the fix does not reproduce after it -- both
defects were in where the oracle streams start, so correcting them
moves every path's simulation draws. `solve()` output is unchanged.

---

### 11. `pymoso/examples/mytester.py` mixes tabs and spaces, blocking its own figure-replication command

**Affects:** all 1.0.x versions. 
**Severity:** high for anyone following the paper's own instructions —
the file as shipped cannot be imported at all under Python 3, on any
version.

**What is wrong:** line 34 of `pymoso/examples/mytester.py`'s `metric`
method begins with a single literal tab character, while every
surrounding line in the same method (and file) uses spaces. Python 3
rejects mixed tab/space indentation within one block outright:
`TabError: inconsistent use of tabs and spaces in indentation`. Not a
runtime behavior difference or an edge case — the module fails to
import, full stop, before any of its own code runs.

Found by accident, not by design: this branch's own CI workflow was
the first thing to ever run `python -m compileall pymoso/` against
this codebase, which is what surfaced it (`f0d6f9c`). That commit's
own message calls it "not part of any planned migration step" and
doesn't cross-reference the paper's replication instructions — which
is what this entry now does.
**Status:** fixed on this branch (`f0d6f9c`), whitespace-only
(`git diff -w` empty). Migration for anyone working from the archive
directly: replace the leading tab on that one line with spaces
matching the surrounding indentation.

---

### 15. An exception in `g()` hangs `--simpar` instead of being reported

(**The number is deliberately out of sequence. Do not renumber.** This
entry belongs here, with the issues affecting released versions, but it
was found after entries 12-14 already had their numbers and were cited
by them throughout the code, tests and docs. Giving it the next number
in this section would have meant renumbering those three and every
citation of them -- the exact cleanup this file went through once
already. An entry's number is an identifier, not a position.)

**Affects:** all 1.x versions, including 1.1.0 (reproduced against the
`v1.1.0` tag) and this branch. **Severity:** high for anyone developing
a problem under `--simpar` -- a bug in their own code produces no
error at all.

**What is wrong:** with `--simpar` greater than 1, replications run in
worker processes. If a user's `g()` raises there -- any exception, for
any reason -- the worker dies with it. The worker loop
(`chnbase.mp_worker`) does not catch the exception or send anything
back, and the parent waits for that replication's result with no
timeout. The run hangs indefinitely: no message, no traceback, no
exit.

The same problem run without `--simpar` reports the error immediately.
Reproduced on Python 3.10 and 3.14 with a problem whose `g()` raises
`ZeroDivisionError` for some points:

```
--simpar=1   RuntimeError: Unable to simulate RaisingProb. Message: boom at (94,)   (immediately)
--simpar=2   no output; still running after 20 seconds, killed
```

This is broader than issue 7. That entry is about a worker failing to
*import* a user-supplied file under Python 3.14's `forkserver`; the
mechanism underneath (a dead worker's exception never reaches the
parent) is the same, but this needs no particular Python version, start
method or file layout -- only a `g()` that raises. It is independent of
issue 8 (workers leaking when the parent is killed), though a user who
kills a run hung this way will meet issue 8 next.

**Workaround:** develop and debug a problem without `--simpar`; turn it
on once `g()` is known not to raise. If a `--simpar` run stops making
progress, rerun it serially to see the error.

**Status:** fixed on this branch. `--simpar` runs on the process-pool
executor backend (`executor.PoolExecutor`, on `pymoso/pool.py`). A
worker catches whatever `g()` raises and sends it back; the caller
raises it as that exception, with the worker's traceback attached, so
`--simpar=2` reports exactly what `--simpar=1` does:

```
--simpar=1   RuntimeError: Unable to simulate RaisingProb. Message: boom at (94,)
--simpar=2   RuntimeError: Unable to simulate RaisingProb. Message: boom at (94,)
```

If replications of several points are running when one fails, the
error reported is the one a serial run would have met first. A worker
that dies outright (killed, a segfault in an extension) is detected
too, and reported as `pool.WorkerCrashed` rather than waited for.
`tests/test_simpar_worker_lifecycle.py`, observed hanging against the
code before the fix on Python 3.10 and 3.14.

---

### 16. `--budget` is checked only between RA iterations, so a run can simulate many times its budget

(Numbered after 15 for the reason given there: an entry's number is
an identifier, not a position.)

**Affects:** all 1.x versions, including 1.1.0 (the loop is unchanged
from the `v1.1.0` tag: `while self.num_calls < budget:` in
`RASolver.rasolve`; not re-measured there) and this branch. Every RA
solver: RPERLE, RMINRLE, RPE, RSPLINE. **Severity:** low in one or two
dimensions; high for anyone with an expensive simulation and more
than a few dimensions, because the simulation budget is the one
control they have over cost.

**What happens.** `rasolve` documents the budget as the "Total number
of calls allowed to orc.g across all iterations". It is not a limit. An
RA solver tests it once per retrospective-approximation iteration,
before starting the next one, and an iteration, once started, runs to
completion whatever it costs. The work in one iteration -- every
neighbour of every point in the current solution, at that iteration's
sample size -- grows with the dimension and with the size of the
solution set.

Counted by the solver's own `simcalls`, default generator:

| Problem | dim | Budget asked for | Simulations counted |
|---|---|---|---|
| ProbTPA, RPERLE | 2 | 100 / 1,000 / 10,000 | 186 / 1,099 / 10,299 |
| ProbTPC, RPERLE | 3 | 100 / 1,000 / 10,000 | 171 / 1,027 / 10,292 |
| BSProb, RPERLE | 9 | 100 / 1,000 / 10,000 | 660 / 3,681 / 12,673 |
| scratch quadratic, RPERLE | 20 | 1,000 | 9,546 |
| scratch quadratic, RPERLE | 50 | 1,000 | 473,901 |
| the same, Philox | 50 | 1,000 | 57,570 |

So a user who asks for 1,000 simulations of a 50-dimensional model
can get 474,000 -- and how many depends on the path the search takes,
which is why the last two rows differ by a factor of eight. At a
second per simulation that is five days in place of a quarter of an
hour, with no warning and nothing in the output to say why until the
run ends and `simcalls` is read.

The count also understates the work, separately: replications of a
point that turns out infeasible are run and not counted
(docs/rng-interface-design.md §11 entry 13).

**Why it was not noticed.** In the dimensions the built-in problems
have, the overshoot is a fraction of one iteration and looks like
rounding. And until Phase 4 the built-in solvers could not be run
much above nine dimensions at all, for an unrelated reason
(`get_nbors`; see the note below), so the regime where this matters
was unreachable.

**Not fixed.** It is the algorithms' own stopping rule, and changing
it changes results: stopping inside an iteration means returning a
solution from a partly estimated iteration, or discarding the
iteration and returning the previous one. Either is a decision about
the method, not a patch. What a user can do today: read
`simcalls` (the per-iteration counts in `testsolve`'s results) from a
cheap trial run before committing an expensive one.

**A related correction, recorded here so that it is found.** For most
of this branch's life the built-in solvers' limit of about nine
dimensions was described -- by the maintainer, repeatedly, in
`CLAUDE.md`, in docs/rng-interface-design.md §3.4 and in the brief for
Phase 4 -- as structural: the solvers enumerate neighbourhoods, so
high dimension would need a new solver. That was wrong, and had not
been measured. It was one helper's implementation: `chnutils.get_nbors`
built a `3**dim` box to return `2*dim` points. It is fixed, with
results unchanged (docs/rng-interface-design.md §3.4's correction;
docs/spark-backend.md, "High dimension";
tests/test_get_nbors_equivalence.py). Removing that wall is what
exposed this issue: it was always there, behind something that
stopped anyone reaching it.

---

### 17. Normal variates differ in the last bit between Python 3.11 and 3.12, so a seed does not reproduce across that boundary

**Affects:** every version on Python 3.12 or later, 1.1.0 included
(`bsm` is the same code at the `v1.1.0` tag), and this branch, with
all three generators -- they share one normal variate. **Severity:**
low in effect, as far as has been observed; real as a
reproducibility defect, because "same seed, same numbers" is what the
package promises.

**What happens.** `prng.mrg32k3a.bsm`, the inverse-normal
approximation behind `normalvariate`, adds the terms of its
polynomials with the built-in `sum()`. CPython 3.12 changed `sum()`
for floats: it now carries a compensation term, so that the result is
closer to the exact sum than adding left to right gives. The uniforms
are unaffected -- they are integer arithmetic. The normal variates
built from them are not: on one machine, from the same stream,
**8,153 of 20,000 normal variates differ between Python 3.11 and
Python 3.12**, each in its last bit or two (largest relative
difference 5.9e-16).

So a run on Python 3.12 or later is not bit-for-bit the run that
Python 3.10 or 3.11 gives from the same seed. The golden baselines
were captured on 3.10.

**What was observed, which is less than that implies -- and that is
itself worth knowing.** Every whole-run comparison made so far is
*identical* across Python 3.10, 3.11, 3.12, 3.13 and 3.14: the golden
suite, and each whole-run hash in the Databricks kit
(docs/databricks/) -- sample paths, replication-level solves with and
without CRN, Philox, 1,024 sample paths' results. The only thing that
moved was the kit's probe of raw variate values, which is how this
was found. A difference in the sixteenth significant digit of a
variate has to survive averaging over replications and then change
the outcome of a comparison between two estimates before a solver's
choice of point changes, and in these runs it never did. That is the
same story as the end seed (docs/end-seed-scope.md): the suite's
whole-run detectors do not see changes at this level, so their
agreement is not evidence that the numbers agree. It can move a
result; it has not been seen to.

**Not fixed.** The repair is small -- add the terms left to right,
explicitly, which is what Python up to 3.11 computes and what the
goldens record -- but it changes every normal variate that currently
differs on Python 3.12 and later, which is where most users now are.
That is a deliberate change to numerical output, to be made on
purpose and announced, not slipped in. Until then: results are
reproducible from a seed on one side of the 3.12 boundary, and not
across it.

Found building the Databricks kit, by computing its known-good
values under five Python versions before trusting them. A cluster's
driver and executors always run the same Python version (Spark
requires it), so this does not affect agreement within a run.

### 18. The RA solvers assume feasibility is a function of `x` alone, and say so only by crashing

**Affects:** every version with these solvers, as far as has been
read: `get_min` is the same at the `v1.1.0` tag and on this branch.
Seen on this branch only. **Severity:** a user whose `g()` decides
feasibility at random gets an unexplained crash, or, depending on
where the verdict flips, a run that silently breaks the algorithm's
assumptions.

**What happens.** `g()` returns a feasibility flag with every
replication, and the `Oracle` contract (its docstring) says only
that the oracle decides feasibility; the README's example decides it
from `x`, without saying it must. `Oracle.hit` calls a
block of replications feasible when every replication is. Nothing
says the answer must depend on `x` alone, and nothing checks it.

R-SPLINE, R-PERLE and R-MinRLE depend on it. A point estimated
feasible in one RA iteration is carried into the next as a warm start
and estimated again. If it comes back infeasible, `get_min` reads its
estimate anyway, and the run stops with a bare `KeyError` wrapped as,
for example, `RMINRLE: Unable to run accel(). Message: (5, 22)`. Seen
on a scratch problem where a replication near one edge is infeasible
with probability 0.03 or 0.01 (`scratch/phase7/infeas_cache.py`,
`RandomEdgeBi`). It happened with and without Phase 7's experimental
cache of infeasible points, so the cache is not the cause.

A flip the other way, infeasible then feasible, does not crash. It
means points were certified against neighbours whose feasibility
changed underneath them, which the algorithms' definitions do not
allow for.

**This is a constraint of the algorithms, not an implementation
limit.** Their sample-path problems take the feasible set as given.
Supporting feasibility that is itself random would be a research
question, not a fix.

**Status: open; fix designed and approved, not built.** Refuse such
a problem with a clear error, and document the assumption where the
`Oracle` contract is stated. The design:
- **In the RA solvers, not in `Oracle`.** The assumption is theirs.
  `RASolver.estimate` and `estimate_many` keep a whole-run record of
  each point's verdict and the iteration it came from. A flip raises
  `FeasibilityChanged` (a `ValueError`), naming the point, both
  verdicts and their iterations. Checking in `Oracle._aggregate` (a
  block whose replications disagree) was considered and declined: it
  would impose the assumption on MOCOMPASS, MOPBnB and direct `hit()`
  callers, who do not necessarily need it.
- **Both verdicts are recorded.** Infeasible points alone would not
  do: the crashing case is feasible-then-infeasible, and seeing it
  needs the earlier feasible verdict. Measured on existing runs
  (`scratch/phase7/feas_memory.py`): the largest, RMINRLE at M = 6
  and budget 100,000, saw 21k distinct feasible and 5.5k infeasible
  points, about 4.1 MB and 0.9 MB as sets, tuples included. Every
  other run tried held at most 1.6 MB (M = 6, budget 30,000),
  0.4 MB at M <= 3, and 9 KB for the two-objective runs. Distinct
  points over a run were about 1.2x the largest single iteration's
  `gbar` at M >= 4, because points recur across iterations.
- **Detection only sees a verdict that flips.** A problem whose
  feasibility is random but which never shows it to the solver is
  not caught. Neither is it harmed.
- **With Phase 7's infeasible-point cache (step 1b), if it lands,**
  the cache and this check share one record, so the cache cannot
  bypass the check. Within one iteration the first verdict then
  stands for the whole iteration, so a within-iteration flip is no
  longer observable. A cache hit is a verdict not re-simulated, and
  there is nothing to compare it with. Flips across iterations,
  including the warm-start re-estimate that crashes today, are still
  caught. This is a decision recorded in advance, not a limit found
  later.

Found 2026-10-16 in Phase 7 (`docs/phase7-plan.md`, step 1b), building
the positive control for the infeasible-point cache.

---

## Behavior changes introduced by this migration

These aren't defects inherited from some past pymoso version — they
don't affect 1.0.8 or any other released version at all, since the
mechanism they describe didn't exist before this branch. Listed here
because they change observable behavior relative to earlier commits on
this same branch, the same way an entry above changes it relative to
upstream.

### 12. `MRG32k3a.getrandbits()` changes stream consumption for `choice`/`sample`/`randrange`

**Affects:** this branch only, from the commit that added
`MRG32k3a.getrandbits()` onward. **Severity:** low — no result this
project's own regression suite reports as "correct" moves, but any
code path that calls `choice()`/`sample()`/`randrange()` on an
`MRG32k3a` instance now consumes its stream differently than it did
one commit earlier, and a downstream user comparing results against a
pre-getrandbits run will see different values.

#### What changed

Before this change, `MRG32k3a` defined `random()` but not
`getrandbits()`, so `random.Random.__init_subclass__` bound
`_randbelow` to `_randbelow_with_getrandbits`'s counterpart,
`_randbelow_without_getrandbits` — every `choice()`/`sample()`/
`randrange()` call drew one or more `.random()` floats and rejection-
sampled in `[0, 1)` space. `getrandbits()` is now implemented directly
(digit expansion in base `mrgm1i` with rejection — see the commit that
added it for the derivation), which `__init_subclass__` detects at
class-definition time and switches `_randbelow` to
`_randbelow_with_getrandbits` instead. Same semantic contract
(`choice`/`sample`/`randrange` still return correctly-distributed
values), different sequence of underlying stream draws to get there.

Concretely, this changes:

- Any tester's `get_ranx0` (`TPATester`, `TPBTester`, `TPCTester`,
  `SimpleSOTester`, `BSTester`, and `pymoso/examples/mytester.py`),
  which all pick a random starting point via `rng.choice(...)`.
  `--isp`/`testsolve` with no `<x>` given uses this path implicitly
  (see `docs/end-seed-scope.md`) — confirmed directly: the same seed
  under the old fallback and under `getrandbits()` pick different `x0`
  values (`(30, 43)` vs. `(44, 1)` for `TPATester`, same seed).
- Anything downstream of that different `x0` — a different search
  path, different per-iteration simulation counts, and potentially a
  different reported solution set, all confirmed to actually move for
  this specific case (see `tests/test_solution_sensitivity.py`).

Nothing else changes: `random()`, `normalvariate()`, and
`expovariate()` (used directly by `bsprob.py`'s `g()`) all route
through `random()` alone, untouched by this change, verified in
`tests/test_rng_consumption.py`.

#### Why the existing golden suite doesn't show this

`tests/test_golden.py`'s end-seed baselines fingerprint the
stream-*allocation* schedule (`get_next_prnstream`/`jump_substream`
call counts), not what any individual stream actually drew — see
`docs/end-seed-scope.md` for the full explanation, written while
investigating this exact change. All 10 existing golden cases,
including `testsolve_tpa` (which *does* reach `get_ranx0` via this
mechanism), are unaffected: 0 of 10 moved. This is not evidence the
change has no effect — `tests/test_rng_consumption.py` and
`tests/test_solution_sensitivity.py` were added specifically because
the existing suite is structurally blind to this class of change, and
both do detect it.

#### Status

Shipped on this branch. `getrandbits()`'s own correctness (unbiased
digit expansion, verified empirically at 5,000,000 trials with zero
rejections observed at the `k` values this codebase actually requests)
is not in question; this entry exists to record that its introduction
is an observable behavior change for any caller relying on exact
`choice`/`sample`/`randrange` output from a fixed seed, not a
regression to fix.

---

### 13. The README's `MyRAAlg` template's failure mode changed, and became less legible

**Affects:** this branch only, from the commit that removed
`RASolver.rasolve`'s `nu > MAX_RI` guard (docs/rng-interface-design.md
§12 step 4b, open question 9). **Severity:** low — `MyRAAlg`
(`pymoso/examples/myraalg.py`) is documented in the README as
illustrative only, deliberately non-terminating as written, not a
usable solver; nothing in this codebase's own test suite calls its
`solve()`/`rasolve()` to completion (checked directly, both before and
after this change — see "Status" below).

#### What changed

`MyRAAlg`'s `spsolve` never calls `self.estimate`, so `self.num_calls`
never advances and `RASolver.rasolve`'s `while self.num_calls < budget`
loop can never exit via budget exhaustion, for any budget. Before this
branch's RNG redesign, `rasolve`'s `nu > MAX_RI` guard (a check that
existed for an unrelated reason — stream-headroom reservation in
`testsolve`, see issue 2) happened to also stop this loop, after 201
fast, simulation-free iterations, with a clear `RuntimeError` naming
`MAX_RI`.

That guard is now removed entirely (its collision-avoidance reason no
longer exists once stream coordinates are computed directly rather than
reserved — see docs/rng-interface-design.md §6), and no replacement
runaway-loop guard was added: a solver that never progresses is a
defect in that solver, not something this layer should paper over with
an arbitrary iteration ceiling. With the guard gone, `MyRAAlg`'s `nu`
keeps incrementing until something else stops it — **not** an indefinite
hang, corrected here against the actual behavior rather than assumed in
advance: `RASolver.calc_b(nu) = ceil(bconst*(dim-1)*1.2**nu)` overflows
Python's float range around `nu≈3882` (`calc_m`'s own `1.1**nu` would
overflow later, around `nu≈7449`, but `calc_b` runs first each
iteration), and `ceil(float('inf'))` raises `OverflowError`. Confirmed
directly: `nu=3882`, reached in 0.03 seconds.

(Checked again in Phase 6, with `ProbTPA`: `nu=3882`, about 3 ms on
the current tree. With a one-dimensional problem such as the README's
`MyProblem`, `dim-1` is 0, the product never becomes infinite, and the
failure comes from `1.2**nu` itself one step later: `nu=3894`,
`OverflowError: (34, 'Numerical result out of range')`. Either way,
an `OverflowError` naming neither `MyRAAlg` nor the cause.)

So the concrete change is from one fast, clearly-labeled failure to a
different fast, unlabeled one:

| | Before | After |
|---|---|---|
| Exception | `RuntimeError` | `OverflowError` |
| Message | Names `MAX_RI`, explains the reservation-overrun risk, and how to proceed | `cannot convert float infinity to integer` — names neither `MyRAAlg` nor the real cause |
| Iterations reached | 201 | ~3882 |
| Time | Fast | Fast (0.03s, measured) |

Both terminate quickly; neither reaches a normal budget-exhausted stop
(the README's own "Template RA Solver" prose already says as much, and
was updated to describe the new failure rather than imply the process
hangs). The regression, such as it is, is legibility: a user who
actually copies this template and hits this case now gets a stack trace
pointing at `calc_b`'s arithmetic, with no indication `MyRAAlg`'s own
missing `self.estimate` call is the actual cause — worse than before,
where `MAX_RI`'s message at least named the mechanism that stopped it,
even though that mechanism's real purpose was unrelated (stream
reservation, not solver correctness).

#### Status

Not fixed. The actual fix is `MyRAAlg`
calling `self.estimate` as the README's own prose already says a real
implementation must — `MyRAAlg` is deliberately illustrative/non-
terminating, not something this entry proposes changing. Checked
directly against the tree as it stands, not assumed: no test in this
suite calls `MyRAAlg.solve()`/`rasolve()` to completion, before or after
this change — `tests/test_readme_examples.py::test_myraalg_spsolve_
runs_directly` calls `spsolve` directly (never enters `rasolve`'s loop)
and `test_algorithm_snippets_run_against_a_live_solver` `exec`s the
README's algorithm snippets directly against a solver instance (also
never calls `rasolve`); neither is affected by the guard's removal, and
neither would have caught a hang via `pytest-timeout` even if the
failure mode had turned out to be one. If a future test is ever added
that does call `MyRAAlg.solve()`/`rasolve()` to completion, it should
expect `OverflowError`, not a timeout, and can cite this entry.

---

### 14. `Oracle.bump()` removed from the public API

**Affects:** this branch only, from the commit that removed it (docs/
rng-interface-design.md §12 step 6b). **Severity:** low for this
codebase (no in-tree caller — confirmed directly, both real
`MOSOSolver`s, `RASolver`/`RLESolver` and MOCOMPASS/MOPBnB, use `hit()`)
but a real, documented-API removal: `bump()` is part of the object
reference the original paper (Cooper & Hunter 2018) describes, so an
out-of-tree solver written against that documentation, or against any
released version, may call it directly.

#### What changed

`Oracle.bump(x, m)` simulated `m` replications at `x` and returned
`(isfeas, obs)`, `obs` a list of the raw, per-replication objective
values — unaggregated, unlike `hit()`'s `(isfeas, obmean, obse)`. It
duplicated `hit()`'s own replication loop (a second, independently
maintained implementation of the same "replicate and aggregate" logic,
flagged as drift-risk in CLAUDE.md's working agreement well before this
removal), was never migrated to the coordinate-based mechanism `hit()`'s
`crnflag=False` path moved to at §12 step 4b (so a `crnflag=False`
caller would have kept observing the pre-4b order-dependent walk,
untouched since step 3), and had no test coverage beyond pinning that
specific leftover behavior and its own `m<1` precondition check.

#### Status

Removed, not deprecated — no compatibility shim, matching this
project's stated posture toward backwards-compatibility hacks.
Migration for anyone calling it out of tree: `hit(x, m)` with the same
arguments returns aggregated `(isfeas, obmean, obse)`; if raw
per-replication values are genuinely needed, they are not currently
available through any public method. 

---

## Reporting

Please open an issue at
https://github.com/pymoso/PyMOSO/issues.
