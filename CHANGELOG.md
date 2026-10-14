# Changelog

## 2.0.0

**Upgrading from 1.1.0? The changes you may have to make are in the
first section below.** Upgrading from 1.0.x: read the 1.1.0 section
too; numerical results changed there.

### What breaks, and what to change

- **The install commands in 1.1.0's README now install 2.0.**
  `python -m pip install pymoso` installs the latest release, now
  2.0.0. `python -m pip install "git+https://github.com/pymoso/PyMOSO.git"`
  installs the
  repository's default branch, which is now 2.0 development, not
  1.1.0 -- newer than the latest release and less tested. To stay on
  1.x, run `python -m pip install "pymoso<2"`, or pin the repository
  install to the tag:
  `python -m pip install "git+https://github.com/pymoso/PyMOSO.git@v1.1.0"`.
- **`--seed` takes one comma-separated token.** `--seed 1 2 3 4 5 6`
  becomes `--seed 1,2,3,4,5,6`. The space-separated form was
  `nargs=6`, which could not accept the 2-integer Philox seed;
  `nargs='+'` was tried and swallowed the positional arguments after
  it. The count is checked against the selected generator.
- **`Oracle.bump(x, m)` is removed.** Use `hit(x, m)`, which returns
  the aggregated `(isfeas, obmean, obse)`. Raw per-replication values
  are not available through any public method. `KNOWN_ISSUES.md`
  issue 14.
- **`Oracle.crn_advance()` is removed.** In a custom `MOSOSolver`,
  delete the call. Advancing the iteration is the framework's job
  (`RASolver` does it); a solver that is not an `RASolver` has no
  iterations to advance. The README's table of six other `crn_*`
  methods described methods 1.1.0 no longer had.
- **An unknown solver parameter raises `TypeError`,** naming it and
  listing the parameters the solver takes. It was silently ignored, so
  a misspelling ran with the default. A custom solver that calls
  `super().__init__(orc, **kwargs)` *before* removing its own
  parameters from `kwargs` now raises; remove them first, as every
  built-in solver does, and declare them in `PARAMS` (below).
- **A solver parameter must be a real number,** and is passed to the
  solver as a float, as before. A numeric string (`"2"`) or a
  `Decimal` used to be converted and now raises `TypeError` naming the
  parameter.
- **`x0` is checked at the call.** It is converted to a tuple, so a
  list works; a starting point of the wrong dimension, or containing
  something that is not a number, raises before any simulation.
  Numbers pass through unchanged.
- **A class defined in a notebook cell, a REPL or inside a function,**
  used with `simpar` or `proc` above 1, worked only under the `fork`
  start method. It now raises
  `ValueError` under every start method unless the `notebook` extra is
  installed (`pip install "pymoso[notebook]"`), with which it works
  everywhere.
- **Names no longer importable from `pymoso.chnbase`.** None was
  documented there; each was an import `chnbase` happened to make. All
  but three still exist where they are defined:
  - from `pymoso.prng.mrg32k3a`: `MRG32k3a`, `bsm`, `stream_at`,
    `jump_seed_n`, `get_next_prnstream`, `jump_substream`,
    `ITER_STRIDE`, `REPL_STRIDE`, `REPL_RESERVE_STRIDE`,
    `ISP_ITER_MARGIN`, `SYNC_STRIDE`, `SYNC_ROLE_OFFSET`,
    `SYNC_ZONE_STREAM_START`;
  - from `pymoso.prng.base`: `ReplicationDrawOverflow`,
    `REPL_RESERVE_BITS`, `offset_within_iteration`, `point_width`,
    `one_past`;
  - from `pymoso.executor`: `build_transport_descriptor`,
    `reconstruct_transport_descriptor`;
  - `get_biparetos`: from `pymoso.chnutils`, where it is documented;
  - the standard library: `inspect`, `os`, `sys`, `types`,
    `multiprocessing.Process` and `Queue`, `statistics.mean` and
    `variance`, `math.sqrt`;
  - removed: `mp_worker` and `mp_replicate` (below).
- **Names no longer importable from `pymoso.chnutils`.** Every
  documented function is still there. Gone:
  - from `pymoso.prng.mrg32k3a`: `MRG32k3a`, `stream_at`,
    `jump_seed_n`, `get_next_prnstream`, `ITER_STRIDE`, `ISP_STRIDE`,
    `ISP_ITER_MARGIN`, `SYNC_ZONE_STREAM_START`;
  - from `pymoso.prng.base`: `one_past`;
  - the standard library: `multiprocessing` (bound as `mp`),
    `itertools.product` and `filterfalse`, `statistics.mean` and
    `variance`, `math.ceil`, `floor` and `sqrt`;
  - removed: `par_runs` and `do_work` (below).
- **Removed with the old worker processes:** `chnbase.mp_worker`,
  `chnbase.mp_replicate`, `chnutils.par_runs`, `chnutils.do_work`, and
  `Oracle`'s `req_q`, `res_q` and `proc` attributes. `set_simpar()`
  and `mp_cleanup()` remain, and `par_diff()` keeps its signature.
- **`pymoso.prng.mrg32k3a.ISP_MAX_MARGIN` is removed;**
  `ISP_MAX_PATHS` is the number of sample paths the layout holds.

### Numerical results

- **`solve()` gives the same results as 1.1.0** for the same problem,
  solver, seed and options, with the default generator.
- **`testsolve()` does not.** In 1.1.0, the first sample path's oracle
  stream and the last path's solver stream started from the same seed
  (`KNOWN_ISSUES.md` issue 10). Every role of every path now has a
  stream of its own, so every `testsolve()` result and end seed
  differs from 1.1.0's.
- **Results do not depend on `simpar`, `proc` or the backend.** The
  same call gives the same numbers serially, on any number of local
  processes, and on Spark.
- **Results can differ in the last bit between Python 3.11 and 3.12**
  (`KNOWN_ISSUES.md` issue 17), as they could in 1.1.0. Not fixed: the
  fix would change results on 3.12 and later.

### A limit that was there in 1.1.0, now documented and adjustable

Without common random numbers, one replication of `g` may make at most
16,384 uniform draws (most methods of `rng` use one per call). One
more raises `ReplicationDrawOverflow` instead of drawing from the next
replication's numbers. This has been so since 1.1.0, which did not say
so; its README promised 2^76.

An oracle whose `g` needs more now says so on its class:
`replication_draws = 2**20`, any power of two up to 2^40. The room
comes out of the code a point's random numbers are computed from, so
points with large or many components fall back to a hashed code
sooner; at 2^40, a two-dimensional point is coded exactly only up to
about 8.4 million a component. A hashed collision raises
`PointCodeCollision`. Setting it changes that oracle's random numbers;
leaving it alone changes nothing. With `--crn`, replications are 2^76
draws apart (more with `philox4x32`), as before.

### Added

- **Three generators, selectable:** `--generator` on the CLI and
  `generator=` in `solve()` and `testsolve()`: `mrg32k3a` (the
  default), `mrg31k3p` and `philox4x32`. The two others were in the
  1.1.0 source but not selectable. A Philox seed is two integers.
  Every generator supports `--crn`.
- **`PARAMS`, for solver authors.** A solver lists the names of its
  parameters in a class attribute `PARAMS`;
  `pymoso.chnbase.accepted_params(cls)` merges them up the class
  hierarchy, and `reject_unknown_params(solver, leftover)` is what a
  solver not derived from `RASolver` calls after taking its own. A
  solver that declares `PARAMS` has its parameters named in errors.
  The README's table of parameters is now generated from the built-in
  solvers' declarations and checked against their defaults.
- **`backend=` on `solve()`, `testsolve()` and `par_diff()`,** and a
  Spark backend, `pymoso.backends.spark.SparkBackend`: sample paths,
  or one run's replications, as Spark tasks. Replications only pay on
  a cluster when one costs roughly 100 ms or more.
  `docs/spark-backend.md` has the measurements, and what identical
  results across machines has and has not been shown for.
- **Optional extras:** `notebook` (cloudpickle, for classes with no
  source file) and `spark` (pyspark, for a local Spark session; on
  Databricks install `notebook` instead). The core still depends on
  nothing.
- **`pymoso.dispatch_cost()`** times one request for replications in
  this process and on a backend and reports both. It runs only when
  called and gives no advice.
- **`Oracle.hit_many()` and `RASolver.estimate_many()`:** several
  points' replications handed to the worker processes at once.
- **MOCOMPASS and MOPBnB,** as compatibility-only example solvers.
  They have not been checked against the papers they implement
  (`docs/mocompass-mopbnb-known-issues.md`), and they refuse `--crn`.
- **The point contract.** A point is a tuple of numbers. A whole
  number of any numeric type is that integer: `30.0` and `30` are one
  point with the same random numbers. A point containing a `nan`, an
  infinity or a non-number is reported infeasible without calling
  `g()`, with or without `--crn`; 1.1.0 crashed on it without `--crn`.
- **A `MOSOSolver` sub-class receives `x0` and `sprn` without
  defining `__init__`.** `solve()` and `testsolve()` always pass both,
  and `MOSOSolver.__init__` took only the oracle, so a sub-class that
  did not take them itself failed with "unexpected keyword argument
  'x0'" -- in every released version, although the README said `x0`
  was available as `self.x0`. The base now takes both, sets them to
  `None` when they are not passed, and keeps a value a sub-class set
  before calling it, so solvers written the old way are unchanged. Any
  other leftover parameter raises `TypeError` naming it.
- **`hit()` on an `Oracle` used directly,** without `solve()` or
  `testsolve()`, works as if `set_crnflag(False)` had been called. It
  raised `KeyError: None`.

### Fixed

- **`testsolve --proc` hung on Python 3.14** with a problem or tester
  from a file, as 1.1.0 documented (`KNOWN_ISSUES.md` issue 7). A
  sample path now travels to a worker as data.
- **An exception in `g()` hung `--simpar`** (issue 15). It is now
  raised in the caller.
- **Worker processes outlived a killed parent** (issue 8). An idle
  worker now exits; a busy one finishes its task first.
- **Two `testsolve()` roles shared a seed** (issue 10; see above).
- **Large or high-dimensional points.** A point that did not fit the
  exact stream code raised `PointCodeOverflow`. It now falls back to a
  hashed code, and two points in one iteration that would share
  random numbers raise `PointCodeCollision` instead.
- **The built-in solvers in high dimension.** Finding a point's
  neighbours enumerated a box of `3**dim` points; it now builds the
  `2*dim` neighbours directly, in the same order, so results are
  unchanged. Above roughly ten dimensions this was a stall.
- **The README:** a table of `Oracle` methods that did not exist, a
  claim that Philox does not support `--crn`, the per-replication
  limit, the 200-iteration advice, the Python floor, the install
  steps, and more. Its factual claims now name the tests that
  establish them, and those it cannot are listed in
  `docs/unverified-claims.md`.

### Known issues

`KNOWN_ISSUES.md` has every open issue. In particular: `--budget` is
checked only between RA iterations, so a run can simulate several
times its budget (issue 16), and results can differ in the last bit
across Python 3.11 and 3.12 (issue 17).

## 1.1.0

**Upgrading from 1.0.8? Read this first: numerical results will not match.**

This release requires at least Python version 3.10 and is compatible with
subsequent versions. 

This release fixes an incorrect pseudo-random stream jump-ahead defect
present in versions up to 1.0.8. `mrg32k3a`'s
stream-advance matrix multiplication was done in floating point, losing
precision and landing streams near — not at — their intended positions,
with error compounding across successive jumps. Every individual
simulation replication draws from a correct stream; the defect was
confined to how streams were advanced between them,
but end seeds and per-run solution values from 1.0.x will not reproduce
bit-for-bit under 1.1.0, for any seed. See `KNOWN_ISSUES.md` issue 1
for the full mechanism and verification.

**Error handling.** Bare `except:` clauses that suppressed tracebacks
are gone — errors now report specific exception types with real
tracebacks. Library code that called `sys.exit()` on bad input now
raises instead, so library callers can catch it rather than having
their process killed. An infeasible starting point (`x0`) now reports
a clear `ValueError` naming it, instead of a misleading downstream
error. A `--simpar`/`--proc` worker-process leak on the error path is
fixed — `Oracle` is a context manager now, so worker cleanup runs even
when a run raises partway through. (One related leak — worker
processes orphaned if the *parent* process is killed externally, e.g.
`SIGKILL` — is not fixed; no Python-level mechanism can fully close
that gap. See `KNOWN_ISSUES.md` issue 8.)

**CLI rewritten on argparse; zero runtime dependencies.** `docopt` is
gone from the runtime path (`install_requires = []` — confirmed empty
at this release, and confirmed no other package appears in a fresh
install of either the editable checkout or the built wheel, on Python
3.10 and 3.14 alike). This also closes a real correctness defect
inherited from every prior version: `docopt` matched `--seed`/
`--param` values by total token count across the whole command line,
so a wrong `--seed` value count could silently borrow a neighboring
token — including the problem or solver name — and complete a run
using the wrong seed or starting point, with no error. `argparse`'s
per-option arity validation closes this: a malformed `--seed`/
`--param` now fails cleanly with a real error message and a non-zero
exit code. See `KNOWN_ISSUES.md` issue 5.

**Library API defaults that had never actually worked using illustrative examples.**
`chnutils.solve()`/`chnutils.testsolve()`, called exactly as the
README's documented examples show (omitting `budget`, `seed`,
`simpar`, etc.), raised `KeyError` immediately — every keyword
argument was popped with no default, on every version checked,
including this project's own original base. Defaults are restored and
centralized (`DEFAULT_BUDGET`, etc.), matching the CLI's own values, with
a test asserting the two can't drift apart.
Calling the library functions as documented now works. See
`KNOWN_ISSUES.md` issue 6.

**Multi-file custom problems/testers.** A user-supplied problem or
tester file that imports a sibling module in the same directory failed
immediately with `ModuleNotFoundError`, on every version checked, including 1.0.8 —
`sys.path` was never updated to include the file's own directory.
Fixed. See `KNOWN_ISSUES.md` issue 9.

**Python 3.10–3.14.** CPython `random.Random` internals this project
depended on directly were removed; the package now runs across the
full 3.10–3.14 range, tested on both ends (3.10 as the compatibility
floor, 3.14 as primary development).

**Known limitation on Python 3.14: `testsolve --proc` hangs with a
custom (file-supplied) problem or tester.** `forkserver` became the
default multiprocessing start method on Linux in 3.14; `solve
--simpar`'s dispatch mechanism was fixed to survive it (source-bundle
transport), but `testsolve --proc` ships a live, already-seeded
`Oracle` instance to each worker, which that fix doesn't cover — the
result is an indefinite hang, no error, specific to custom problem/
tester files supplied by path (built-in problems/testers are
unaffected). See `KNOWN_ISSUES.md` issue 7.

**MOCOMPASS and MOPBnB are not in this release.** They are not
shipped: bringing in-tree implementations of two other groups'
published algorithms, and reviewing their correctness against the
source papers, is deliberately deferred to 2.0.0 rather than falling
out incidentally from this release's version boundary. See
`KNOWN_ISSUES.md` issue 14.

**Documentation.** Documentation defects in example code are
fixed, plus one found separately: README code blocks, CLI help text, and the `listitems`
output are now generated from and tested byte-identical against live
source, so they can't drift silently. `docs/end-seed-scope.md` explains
precisely what a reported end seed does and does not guarantee (it
fingerprints the stream-allocation schedule, not what any stream
actually drew — a distinction with real consequences for anyone trying
to use it to detect a changed run). `docs/rng-interface-design.md`
ships as development documentation for the RNG redesign behind this
release's numerical fix; it now carries an explicit note that most of
what it describes is 2.0.0-era design work, not 1.1.0's shipped
behavior (see the note at its head).

For anything not listed above, including what remains open for a
future release, see `KNOWN_ISSUES.md` in full.
