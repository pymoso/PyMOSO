# Known Issues

This document records defects found in PyMOSO during the 2.0
modernization effort. Work began against a fork based on PyPI 1.0.4;
it has since moved onto the canonical repository,
github.com/pymoso/PyMOSO (currently versioned 1.0.7 in
`pymoso/__init__.py`, though PyPI ships 1.0.8 — the two don't
necessarily agree). Each issue below states which versions it affects
and its status specifically on this branch.

Issues are grouped by whether they affect a version anyone is known to
have used. PyMOSO had no known users prior to 1.0.8: versions 1.0.0
through 1.0.7 were development releases pushed to PyPI while the paper
(Cooper & Hunter 2018) was in progress, and users arrived only after
the preprint was archived, which was after 1.0.8 shipped. Download
statistics from that period aren't reconstructible, so this document
says "no known users prior to 1.0.8," not "no users" — a deliberately
weaker claim that costs nothing here.

Every entry below in the first section was re-verified directly
against a real PyPI 1.0.8 install (`.venv-py38`, CPython 3.8), not
reasoned from the 1.0.4 wheel most of this project's early
investigation used or from reading the diff.

If you have used PyMOSO 1.0.8 or later in work leading to publication,
please read issue 1. It affects the numerical output of individual
runs, not the convergence theory the algorithms are proven against.

---

## Affects released, used versions (1.0.8 and later)

### 1. Incorrect pseudo-random stream jump-ahead

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** high — alters the numerical
output of individual runs. Does not affect the convergence theory the
algorithms are proven against; see "What this means" below.

**Verified against 1.0.8:** `pymoso solve --budget=1000 ProbTPA RPERLE
40 40` on a real 1.0.8 install reports ending seed
`738848768 2094673920 3003824128 304680960 1844190720 1414365184` —
all six components divisible by 256, the exact fingerprint described
below.

**Independently re-verified against the paper's own peer-reviewed
archive:** `github.com/INFORMSJoC/2019.0902` — confirmed by diff to be
`a38e27d` (one of these 13 commits) plus a mechanical MIT-license-header
addition and a version bump to `1.0.8`, nothing functionally different
(see "Archival cross-check" near the end of this file). Installed from
that repository on real Python 3.6.15 (the version the paper targets,
`python_requires='>=3.6.0'`) and re-ran the same command: identical
divisible-by-256 end seed. This settles what "a real 1.0.8 install" was
actually running — not an opaque wheel of unclear provenance, but this
exact, citable, peer-reviewed snapshot.

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
reported end seed are, in practice, always divisible by 256.

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

A separate, unrelated change on the canonical repository
(`dfd2a30`, "set rng cache with object methods instead of class
methods") touches how the generator/bsm caches are stored, not the
jump-ahead arithmetic itself; `mat333mult`/`mat311mod` are confirmed
byte-identical to the version this was originally found against (see
`docs/upstream-simpar.md`).

#### What this means

The convergence theorems for RPERLE/RMINRLE/RSPLINE/RPE are proofs about
the algorithms, assuming truly independent pseudo-random streams. They
are not empirical claims about what any particular piece of software's
PRNG actually does, and this defect does not touch them: nothing in the
published theory is invalidated by a bug in this implementation.

What the defect affects is numerical output — the specific solutions and
metric values a given run produced. The stream positions a 1.x run
actually used after the first jump are not the positions the theory's
independence assumption calls for, so a run's numbers do not necessarily
carry the guarantees the theory attaches to a run using truly independent
streams. That is a gap between this implementation and what the theory
assumes of it, not a defect in the theory itself.

We are not currently able to state how large an effect this has on any
particular reported number, and whether it materially changed any
published value is an empirical question this document does not settle.
We do not want to overstate or understate it. What can be said:

- The generator was producing valid MRG32k3a output throughout; values
  are not degenerate or patterned.
- Streams intended to be far apart are still far apart, but not by the
  exact reserved distance, so the guarantee of non-overlap does not
  strictly hold.
- Numerical output (end seeds, per-run solution and metric values) will
  not reproduce bit-for-bit across the fix.

Empirical studies whose contribution is a performance comparison —
rather than a theoretical result — may warrant re-running and comparing
against this fix.

#### Status

Confirmed present on this branch (github.com/pymoso/PyMOSO's master, not
just the earlier fork it was first found against). Fixed on this
branch using exact integer arithmetic (`mat333mult`/`mat311mod`); see
`tests/test_jump_ahead.py` for the brute-force/exact-matrix-power
equivalence tests that verify the fix independently of the golden
end-seed suite.

---

### 3. Silent stream overlap past the reserved iteration window

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** moderate — requires
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
order of 4x10^9 simulation calls at minimum. The risk arises with an
unusually small `mconst` combined with a very large budget.

**Status:** fixed on this branch. An earlier fix promoted
`chnutils.MAX_RI` to a module constant and made `RASolver.rasolve`
raise before starting any RA iteration beyond it; that guard was later
removed entirely (§12 step 4b) once `hit()`'s `crnflag=False` path
moved onto `point_code`/`offset_within_iteration` coordinates, which
are collision-free by construction rather than by an enforced ceiling
— there is no longer a reserved-window bound to overrun. Upstream still
uses a bare, unenforced local `max_RI = 200`.

---

### 4. Errors reported without tracebacks

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** moderate — obscures other
defects.

**Verified against 1.0.8:** `chnbase.py` (site-packages) still has
bare `except:` clauses (confirmed at two live call sites) and multiple
`sys.exit()` calls in library code.

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

### 5. Misleading error for an infeasible starting point

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** low.

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

### 6. Silent mis-parsing of `--seed` and `--param` on the command line

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master (still docopt-based). **Severity:**
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
completes a run with a wrong seed or starting point. This entry
previously said `pymoso/cli.py` was "still docopt-based here" — stale,
written in `39fe2b7` before the docopt→argparse migration landed and
never revisited after. `tests/test_cli_characterization.py` used to
keep the 1.x docopt behavior above as a frozen historical record, via a
live `docopt` import; deleted -- that import was an undeclared
test-time dependency (a clean clone's `pytest` run failed at collection
without `docopt` manually installed), and everything it demonstrated is
already recorded here, verified against a real PyPI 1.0.8 install,
which needs no such dependency.

---

### 7. `chnutils.solve`/`chnutils.testsolve`'s documented library usage has never worked

**Affects:** `chnutils.testsolve`'s `ranx0` gap affects all 1.x
versions, including this fork's original base. The broader
`budget`/`seed`/`simpar`/`isp`/`proc`/`crn` regression below is specific
to the canonical repository: confirmed broken on both its current
master (1.0.7) and PyPI's published 1.0.8, but *not* present at the
version this project originally forked from, where those kwargs already
had defaults. **Severity:** moderate — the CLI was unaffected in either
case, since it always passes every argument explicitly; only direct
library use was broken.

**Verified against 1.0.8:** `chnutils.py` (site-packages) pops
`budget`/`seed`/`simpar`/`crn` (in `solve`) and
`budget`/`seed`/`isp`/`proc`/`ranx0`/`crn` (in `testsolve`) with no
default value on any `kwargs.pop(...)` call. Independently re-verified
against the paper's own archival snapshot (`github.com/INFORMSJoC/
2019.0902`, confirmed `== a38e27d` plus a version bump — see "Archival
cross-check" near the end of this file) on real Python 3.6.15:
`chnutils.solve(ProbTPA, RPERLE, (4, 14))` raises `KeyError: 'budget'`,
exactly as described.

#### What is wrong

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

### 9. User-supplied problem/tester files hang `--simpar`/`--proc` on Python 3.14+

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master, on Python 3.14 or later. **Severity:**
high — indefinite hang, no error, on the documented way a user supplies
their own problem or tester.

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

**Status:** `solve()`/`--simpar` fixed on this branch (source-bundle
transport, `chnbase.py`) — see the commit implementing it for the
mechanism. `testsolve()`/`--proc` **not fixed**; still hangs on Python
3.14+, exactly as described above. Forcing `ctx =
get_context('fork')` would unblock this specific hang but is a
workaround, not a fix — forking a process holding threads or locks can
deadlock the child, which is precisely why CPython moved off `fork` as
the default; see `docs/forkserver-hang.md` for why this also needs to
be solved in a way that survives a worker not sharing the parent's
filesystem or process state at all (relevant to a longer-term
distributed-execution goal for this project).

---

### 10. `--simpar`/`--proc` worker processes leak if the parent is killed externally

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** moderate — requires an
external kill (not a normal Python exception) to trigger, but leaves
worker processes running indefinitely when it does.

**Verified against 1.0.8:** `chnbase.py`'s `Oracle.set_simpar`/
`mp_cleanup`/`__exit__` structure predates this branch's own fix for
the in-process error-path leak (see "Fixed on this branch" in
`CLAUDE.md`, and `tests/test_simpar_worker_lifecycle.py`) and is
otherwise unchanged in 1.0.8. This entry describes a different gap in
the same mechanism, present on both.

`Oracle.mp_cleanup()` (`terminate()`+`join()` on every worker process)
only runs via the `set_simpar` context manager's `__exit__`, which
Python only calls when the `with` block's frame unwinds — a normal
return, or a raised exception propagating through it. If the *parent*
process itself is killed externally (SIGKILL, SIGTERM to a process
group, a supervisor deciding a hung process should die — including
killing it in response to issue 9's hang), `__exit__` never runs, and
every worker process it spawned is orphaned, alive, and blocked
waiting on its input queue indefinitely. Observed directly while
investigating issue 9: worker/forkserver processes from an earlier
killed test run were still alive 45+ minutes later.

This is distinct from the already-fixed in-process error-path leak
(an infeasible `x0` raising `ValueError` inside the `with` block, which
`__exit__` *does* catch and clean up after — see "Fixed on this
branch" in `CLAUDE.md` and `tests/test_simpar_worker_lifecycle.py`).
That fix only covers exceptions the interpreter sees; it cannot cover
the process being killed out from under itself.

**Status:** not fixed. No Python-level exception-safety mechanism
(context manager, `atexit`, signal handler) can fully close this gap
for an unconditional external kill (`SIGKILL` cannot be caught at all);
a real fix likely needs the worker side to detect its parent has died
independently (e.g. checking the parent pid, or a heartbeat) rather
than relying solely on the parent-side cleanup path. Noted as the
fourth multiprocessing lifecycle finding in this project
(`docs/forkserver-hang.md`) — an argument for an executor rework, not
a fourth independent point fix.

---

### 11. A multi-file custom problem or tester fails to load at all

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master. **Severity:** high for anyone it applies
to — immediate crash, no workaround short of inlining everything into
one file — but scoped narrowly: only custom problem/tester files
supplied on the command line by path (`pymoso solve myproblem.py ...`,
`pymoso testsolve mytester.py ...`), not the four built-in problems/
testers (`ProbTPA`, `TPATester`, etc.), which are real installed
submodules and load normally regardless of this issue. Single process,
no `--simpar`/`--proc` involved — this is unrelated to issue 9.

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
`commands/testsolve.py`, or `cli.py`, on either version. Independently
re-verified against the paper's own archival snapshot
(`github.com/INFORMSJoC/2019.0902`, confirmed `== a38e27d` plus a
version bump — see "Archival cross-check" near the end of this file)
on real Python 3.6.15: the same fixture shape fails identically,
`ModuleNotFoundError: No module named 'helper'`.

**Status:** fixed on this branch. `commands/basecomm.py`'s
`load_user_module` inserts the user file's directory onto `sys.path`
before executing it and restores `sys.path` afterward; both
`commands/solve.py` and `commands/testsolve.py` load user files through
it. Confirmed directly, not assumed: the fixture this entry's own
"Verified against 1.0.8" section describes
(`scratch/multifile_cli_check/myproblem.py` importing a sibling
`helper.py`) now solves cleanly via `pymoso solve --budget=200
myproblem.py RPERLE 40`. This entry previously said "not fixed... this
has never worked" — stale, written in `9da11f2` before the `sys.path`
fix landed and never revisited after. See also
`tests/test_multifile_transport.py`.

---

### 14. `testsolve()`'s path-0 oracle stream and the last path's solver stream share a starting seed

**Affects:** confirmed on this branch's current code; **not** checked
against 1.0.8 or the canonical repository, unlike issue 11 above — the
shape of `get_testsolve_prnstreams`'s solver-stream derivation loop
(accumulate `iseed` by jumping `ITER_STRIDE` once per solver stream,
then use the final value directly as `orc_root`) looks like it predates
the RNG redesign rather than being introduced by it, but that is an
inference from reading the code, not a verified historical claim the
way issue 11's is. **Severity:** correctness — a real independence
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

**Status:** not fixed. §12 step 6b's own rewrite of `get_testsolve_
prnstreams` (generalizing it onto a selected backend) deliberately
reproduces this exact seed math byte-for-byte rather than fixing it
inline — a real fix moves `testsolve()`'s own `endseed` and downstream
solution sets (a golden-affecting change, needing its own sign-off and
regression test observed failing first, per the working agreement),
which is out of scope for a generator-selection change. Tracked here so
it isn't silently carried forward unrecorded.

---

### 15. `pymoso/examples/mytester.py` mixes tabs and spaces, blocking its own figure-replication command

**Affects:** all 1.x versions, including 1.0.8 and the canonical
repository's current master — confirmed present, byte-for-byte, in the
paper's own peer-reviewed archival snapshot (`github.com/INFORMSJoC/
2019.0902`; see "Archival cross-check" near the end of this file).
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
is what this entry now does. The INFORMS archive's README documents
`pymoso --isp=16 --proc=4 --metric testsolve mytester.py RPERLE` as
the exact command that reproduces Figures 6 and 7 of the published
paper, using the shipped `pymoso/examples/mytester.py` unmodified.
Confirmed directly on a clean install of the actual archive, real
Python 3.6.15: running that command exactly as documented raises this
`TabError` before doing anything else. The paper's own documented
figure-replication instructions do not work against the paper's own
archived code, for anyone running Python 3, out of the box.

**Status:** fixed on this branch (`f0d6f9c`), whitespace-only
(`git diff -w` empty). Migration for anyone working from the archive
directly: replace the leading tab on that one line with spaces
matching the surrounding indentation.

---

## Development-history only (pre-1.0.8, no known users)

### 2. `--simpar` (parallel simulation replications)

**Affects:** every published 1.x version through at least PyPI 1.0.4.
**Not affected:** PyPI 1.0.8 or github.com/pymoso/PyMOSO's current
master. **Severity:** was high (documented feature entirely
non-functional) at the time, but no known user was ever exposed to it
— see the "no known users prior to 1.0.8" note above. Informational
now.

**Verified against 1.0.8:** `pymoso solve --budget=1000 --simpar=2
ProbTPA RPERLE 40 40` exits 0 and reports the identical ending seed as
the equivalent serial (`--simpar=1`) run — matching the seed-assignment
design described below.

#### History

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
worktree of that commit, and again here directly against a real 1.0.8
install, not merely by reading the diff.

#### What changed upstream

Commit `917bf06` replaced the old per-`hit()`-call `multiprocessing.Pool`
with a persistent worker pool created once per `solve()` call
(`Oracle.set_simpar`/`mp_cleanup`), and gives each *replication* its own
seed (derived via the same `crn_nextobs()` substream-jump mechanism the
serial path already used) rather than trying to give each *worker* its
own long-lived stream. This is why it composes correctly with CRN where
the old design didn't: there's no second, independently-configured
`Oracle` with its own CRN state involved. Full architectural writeup in
`docs/upstream-simpar.md`.

#### Status

Resolved upstream, by `917bf06`, independently of this project's work —
not a fix produced here. Not present on this migration's base, nor on
1.0.8, as a result.

---

## Behavior changes introduced by this migration

These aren't defects inherited from some past pymoso version — they
don't affect 1.0.8 or any other released version at all, since the
mechanism they describe didn't exist before this branch. Listed here
because they change observable behavior relative to earlier commits on
this same branch, the same way an entry above changes it relative to
upstream.

### 8. `MRG32k3a.getrandbits()` changes stream consumption for `choice`/`sample`/`randrange`

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

### 12. The README's `MyRAAlg` template's failure mode changed, and became less legible

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
`testsolve`, see issue 3) happened to also stop this loop, after 201
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

Not fixed, and not a case of "someday": the actual fix is `MyRAAlg`
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

### 13. `Oracle.bump()` removed from the public API

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
available through any public method — that capability returns with the
executor rework (CLAUDE.md's "Still in flight"), which is expected to
expose unaggregated per-replication observations as its own return
shape rather than reintroduce `bump()`.

---

## Archival cross-check: the INFORMS Journal on Computing snapshot

Not a numbered issue — nothing here claims PyMOSO's own code is wrong.
This is a record of directly validating several claims above against
the paper's own permanent, citable, peer-reviewed record
(`github.com/INFORMSJoC/2019.0902`), rather than resting on a PyPI
install of otherwise-unknown provenance. Kept here because it settles
exactly what "1.0.8" is, and because one finding below (Figures 6/7)
belongs on the record regardless of whose defect it turns out to be.

**What the archive actually is.** It states it snapshots
`pymoso/PyMOSO@a38e27d` — one of the 13 commits already in this
project's own history, confirmed the third commit back from that
repository's current master, with only two commits after it and both
of those README-only (`git log a38e27d..origin/master`: `e9bac72`,
`72f43dc`, both "Update README.md", nothing else). Confirmed by diff,
not assumed: every one of the 23 `.py` files that differs between
`a38e27d` and the archive differs by exactly one hunk — a mechanical
MIT-license-header block INFORMS added at the top of each file,
nothing functional. `setup.py` is byte-identical
(`install_requires = ['docopt']`, `python_requires='>=3.6.0'`).
`LICENSE.txt` differs only in copyright attribution (adds Susan Hunter
as co-author). The README differs extensively above the paper's own
"Table of Contents" heading (INFORMS's citation/build/replication
front matter, plus one updated citation year), but the entire body
from that heading onward is byte-identical except one added blank
line — confirmed by hashing both bodies, not by eyeballing a diff.

**Version.** The archive's `pymoso/__init__.py` reads
`1.0.7 -> 1.0.8` relative to `a38e27d` — a one-line version bump,
nothing else changed. Searched all known history
(`git log --all -S"__version__ = '1.0.8'"`) and confirmed no commit in
`pymoso/PyMOSO`'s own git history ever set that string, anywhere. So
the precise claim is: **1.0.8 corresponds to no commit in
`pymoso/PyMOSO`'s git history, but it is real, peer-reviewed code** —
`a38e27d` plus this one-line bump, permanently archived and citable
(DOI `10.1287/ijoc.2019.0902.cd`). Every "verified against 1.0.8"
claim elsewhere in this document now has a precise, checkable referent
rather than an assumption about what some PyPI wheel contained.

**The ten documentation defects were published, not introduced
later.** Confirmed by the byte-identical-body finding above, directly,
not by inference: `RSPLNE` (the typo) and `ProbTPC RPERLE 31 21 11`
(the infeasible starting point) are both present verbatim in the
archive's README, at the same lines `a38e27d` has them. Since the
entire body is unchanged, every documentation defect traced to
`a38e27d` is present in the peer-reviewed archive. This hardens the
framing of those defects, not softens it: they are not an artifact of
reading an unpolished development branch — they are what INFORMS
Journal on Computing published.

**Tested on real Python 3.6.15** (`python:3.6-slim` in Docker;
building 3.6 from source on this project's own development machine
hits the OpenSSL 3.0 wall this note doesn't need to relitigate),
installed from a clean clone of the archive with no modification
beyond what's noted below.

- **Figure 4** (`pymoso solve --budget=10000 --simpar=4 myproblem.py
  RPERLE 97`): runs successfully and matches the published output
  exactly — `(2,)`, `(0,)`, `(1,)`. Also directly confirms `--simpar`
  works at this commit, as expected (`a38e27d` postdates `917bf06`'s
  multiprocessing rework — issue 2).
- **Figures 6 and 7** (`pymoso --isp=16 --proc=4 --metric testsolve
  mytester.py RPERLE`, every option preceding the subcommand while the
  usage block declares them after it): docopt accepts this ordering
  without complaint — consistent with issue 6's own finding that
  docopt matches by whole-command-line token satisfaction, not
  positional enforcement, so the ordering itself is not a defect. The
  command as shipped fails outright with the `TabError` issue 15
  documents. With that one line fixed, it runs successfully and
  deterministically (re-ran twice, byte-identical output; also ran
  with `--isp=1 --proc=1` to rule out a parallelism-dependent seed —
  byte-identical first-path trajectory, matching a direct reading of
  `get_testsolve_prnstreams`: the shared `x0stream` is seeded from the
  raw root seed before any per-trial loop runs, independent of `isp`)
  — but **does not match the published Figures 6 or 7**. The first
  solution-file entry is `{(-25,)}`, not `{(3,)}`; the trajectory that
  follows is a different, if equally coherent, RPERLE search path.
  Verified independently of the CLI that this is the correct,
  deterministic output of the shipped code, not a bug in how this was
  invoked: a bare `MRG32k3a((12345,)*6).choice(range(-100, 101))` —
  the exact first draw `mytester.py`'s `get_ranx0` makes — returns
  `-25` directly. This does not look like a PyMOSO code defect as far
  as this investigation can tell: `random()`/`choice()`/
  `normalvariate()` are all deterministic, version-stable computations
  here (`MRG32k3a` overrides only `random()`; `choice()`'s fallback
  path has been stable across CPython 3.x for a class that doesn't
  define `getrandbits()`), and Figure 4's exact match on the same
  install rules out an environment-wide explanation. The most likely
  account is that the README's documented replication command is not,
  in fact, what produced the published Figures 6/7 — the same class of
  documentation imprecision as the ten defects above, not a new one
  this project is asserting. Recorded here because it belongs on the
  record, not because it changes PyMOSO's own status on anything.
- **Library kwarg `KeyError`** (issue 7): reproduced exactly —
  `chnutils.solve(ProbTPA, RPERLE, (4, 14))` raises
  `KeyError: 'budget'`.
- **Multi-file custom problem loading** (issue 11): reproduced exactly
  — a problem file importing a sibling module fails with
  `ModuleNotFoundError: No module named 'helper'`.
- **Jump-ahead fingerprint** (issue 1): reproduced exactly —
  `pymoso solve --budget=1000 ProbTPA RPERLE 40 40`'s end seed is
  divisible by 256 in all six components.

---

## Reporting

Please open an issue at
https://github.com/pymoso/PyMOSO/issues.
