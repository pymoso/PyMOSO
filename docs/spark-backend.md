# Running PyMOSO on Spark, and from a notebook

Phase 4 of the 2.0.0 work. This document is both the record of what
was measured and decided, and — until the README is rewritten — the
only user-facing description of the Spark backend and the `notebook`
extra.

All measurements: 2026-10-12, AMD Ryzen 5 5600X3D (6 cores, 12
threads), Python 3.14 unless noted, pyspark 4.2.0, MRG32k3a. Mostly
single runs. **Every Spark figure here is from one machine** — Spark's
`local` and `local-cluster` modes — and is therefore a lower bound on
what a real cluster costs per job.

## Using it

```python
from pymoso.backends.spark import SparkBackend
from pymoso.chnutils import solve, testsolve

backend = SparkBackend(spark)      # the session a notebook already has

# Independent sample paths: one Spark task per path.
results, end_seed = testsolve(MyTester, RPERLE, x0, isp=200, budget=5000, backend=backend)

# One solve(), its replications spread over the cluster.
# Read "When replication-level dispatch pays" first.
solution, end_seed = solve(MyProblem, RPERLE, x0, budget=5000, simpar=16, backend=backend)
```

Results are identical to the same call without `backend=`.

- **Install.** On Databricks, or any cluster that provides Spark:
  `pymoso[notebook]` (pymoso plus cloudpickle), on the driver and the
  executors. Do **not** install `pymoso[spark]` there — it pulls
  PyPI's pyspark (480 MB) over the runtime's own. `pymoso[spark]` is
  for opening a session on a laptop.
- **The same pymoso everywhere.** Every task checks that the pymoso
  running it is the version that sent it and raises `VersionMismatch`
  otherwise. Spark itself requires the same Python minor version on
  driver and executors.
- **`testsolve`** sends every path as a task; `proc` is refused,
  because the cluster decides how many run at once.
- **`solve`** needs `simpar` of at least 2: the number of tasks each
  of the solver's requests for replications is cut into.
- **No CLI flag.** A Spark session is an object in a Python process;
  the backend is library-only.

Without Spark, the `notebook` extra alone makes `simpar=N` and
`proc=N` work with classes defined in notebook cells, on the local
worker pool.

## When replication-level dispatch pays

**It is slower than plain `solve()` unless one replication costs
roughly 100 ms or more, and it tops out near 3-5x however large the
cluster is.**

Every request a solver makes to the oracle becomes one Spark job, and
a Spark job has a fixed cost that a local worker pool does not:

| | `local[6]` | `local-cluster`, 6 executor JVMs |
|---|---|---|
| Session start | 2.9 s | 3.4 s |
| First job (cold Python workers) | 0.9 s | 1.1 s |
| One job, 1 task | 60 ms | 68 ms |
| One job, 12 tasks | 115 ms | 126 ms |
| Each further task, at volume | ~8 ms | ~8 ms |

Over Spark Connect, 12 no-op tasks took 192 ms.

RPERLE on `ProbExpensiveBi` at four costs, six workers, one run each
(a scratch prototype of this backend, before it was built):

| One replication | Local pool, `simpar=6` | Spark, 6 tasks per request | Spark jobs | ms per job |
|---|---|---|---|---|
| 4.4 ms | 3.10x | **0.46x** | 152 | 79 |
| 13 ms | 3.30x | **0.95x** | 73 | 84 |
| 110 ms | 3.53x | 3.05x | 43 | 166 |
| 0.5 s | 3.41x | 3.24x | 25 | 654 |

The ceiling is not Spark's. An RA solver asks for a handful of
replications and waits for the answer; with *infinite* workers the
batched bounds in `docs/simpar-ceiling.md` are 5.5x to 11.5x, and
35-46% of an RA run's replications are requested one point at a time
by necessity. Two hundred cores buy at most that.

Three things say this to a user who did not read this page: the
`pymoso.backends.spark` module docstring; the error `solve()` raises
for a remote backend without a `simpar`; and `SlowDispatchWarning`,
raised once during a run when the backend's dispatch time exceeds the
time its tasks spent working — that is, when the same work run in
place would have finished sooner.

For sample paths none of this applies. Twelve paths, RSPLINE:

| Tier | Local pool, 6 workers | Spark, 6 executors |
|---|---|---|
| Light (0.46 ms/replication) | 3.40x | 2.94x |
| Moderate (4.4 ms) | 5.19x | 4.03x |
| Heavy (13 ms) | 5.01x | 4.27x |

A path is long, independent and a few hundred bytes to send, and it
scales with the number of paths.

**Who each serves.** `testsolve` is algorithm testing: many paths, and
Spark suits it. A practitioner with one expensive simulation runs
`solve()` once, and replication-level dispatch is the only thing that
helps them — which is why it is offered despite the table above.

## High dimension: what a cluster does and does not change

**Corrected during Phase 4.** This section first recorded, as the
phase's brief did, that the built-in RA solvers are limited to about
nine dimensions by something structural -- they enumerate a `3**dim`
neighbourhood -- and that serving high-dimensional users would need a
new solver. That was wrong. It was one helper's implementation, it is
fixed, and what remains is different in kind.

### What was wrong

`chnutils.get_nbors(x, 1)` returns `2*dim` points: the points one
step away along one axis. It found them by generating the whole
`3**dim` box around `x` and filtering by distance. RPERLE at budget
300 took 0.6 s at dim 3, 17 s at dim 9, and did not return at dim 20.

It now builds the neighbourhood directly. One call:

| Radius | dim | Before | After | Points returned |
|---|---|---|---|---|
| 1 | 12 | 372 ms | 0.09 ms | 24 |
| 1 | 50 | not runnable | 1.2 ms | 100 |
| 2 | 9 | 1,193 ms | 4.1 ms | 2,868 |
| 2 | 20 | not runnable | 279 ms | 87,480 |
| 3 | 6 | 55 ms | 4.1 ms | 4,196 |
| 3 | 12 | not runnable | 1,482 ms | 959,800 |

**No result changed, and that took care.** The function returns a
set, solvers iterate over it, and a set's iteration order follows
from insertion order. The new code inserts in the order the box
enumeration did, so the set is the same element for element and
position for position: 1,066 random points across dims 1-12 and radii
0.5 to 3, and 96 whole solver runs (four RA solvers, four problems,
with and without `--crn`, radii 1 to 3), on Python 3.10 and 3.14. The
same neighbours inserted in reverse order changed 20 of those 96
runs; shuffled, 40. A simpler rewrite would have been a behaviour
change at radius above 1. `tests/test_get_nbors_equivalence.py` keeps
the old implementation as its reference.

### What is true now

**The built-in solvers no longer stall on neighbourhood enumeration.**
That is the whole claim. It is not "dim 20 works". RPERLE, budget
1,000, on a scratch bi-objective quadratic over `[-20, 20]^dim`:

| dim | Generator | Time | Simulations run | Share of time in the jump |
|---|---|---|---|---|
| 12 | MRG32k3a | 1.4 s | 2,418 | 95% |
| 20 | MRG32k3a | 5.0 s | 9,546 | 95% |
| 50 | MRG32k3a | 330 s | 473,901 | 95% |
| 20 | Philox | 0.3 s | 10,083 | -- |
| 50 | Philox | 2.4 s | 57,570 | -- |

(Single runs on a machine that was busy with other work.)

- **The default generator's jump is the next wall.** 1.5-2 ms per
  block, and the number of points a solver touches grows with
  dimension. `generator='philox4x32'` removes it. No backend does: it
  is per block, wherever the block runs.
- **The budget stops bounding the work** (KNOWN_ISSUES.md issue 16).
  It is checked between RA iterations and one iteration's work grows
  with dimension: a budget of 1,000 ran 10 times that at dim 20 and
  58 to 474 times that at dim 50. On an expensive simulation this is
  the thing a user will actually meet.
- **Radius above 1** is a large neighbourhood in high dimension, and
  every point in it is simulated.
- **From about dim 12** points of ordinary size no longer fit the
  exact point code and the hashed fallback is used ("correct or
  raises"; no collision was raised in any run here).

### Whether the answers are any good

On the one problem tried, yes. It is an easy one: two separable convex
quadratics with unit noise, started well off the front. The gap below
is 0 on the true Pareto segment and 3.33 at the starting point; points
that are efficient on the integer lattice sit at about 0.05-0.10,
which is where dim 3 converges.

| dim | Budget | RA iterations | Points returned | Median gap | Max gap |
|---|---|---|---|---|---|
| 3 | 100,000 | 44 | 10 | 0.049 | 0.095 |
| 12 | 100,000 | 10 | 37 | 0.053 | 0.128 |
| 20 | 100,000 | 4 | 58 | 0.054 | 0.095 |
| 50 | 100,000 | 2 | 29 | 0.093 | 0.095 |

RSPLINE on a single-objective quadratic reached the optimum exactly
at dim 20 with budget 10,000 and was one step from it at dim 50.

This shows the solvers are not useless in high dimension. It says
nothing about harder landscapes, and at dim 50 only two RA iterations
fit in 100,000 simulations. How well these algorithms search in high
dimension is not established.

### And a cluster

None of the above is in the simulation, so no backend changes any of
it: neighbourhoods are built by the solver on the driver, the jump is
paid per block wherever the block runs, and the budget check is the
solver's.

## Design

### One seam: the backend

`--simpar`, `--proc` and metric computation each used to construct a
`WorkerPool`. They now ask a *backend* for it (`pool.LocalBackend`
describes the protocol: a `remote` flag, and `pool(workers,
initializer, initargs)` returning something with `WorkerPool`'s
shape and `run` contract).

The seam is at the pool and not at `Executor`, because sample paths
have never gone through `Executor.run` — they are a second kind of job
on the same pool (`docs/rng-interface-design.md` §12 step 11). The
pool is what the two kinds of job share. Replication-level dispatch
needed nothing more: `PoolExecutor` takes its pool from the backend
too.

### `backends/remote.py`: the pool contract on bytes

A cluster offers no process to start, no per-worker hook and no
channel except "run this function on that input". `RemoteBackend`
rebuilds the pool contract on that:

- `run_task(init_payload, task_payload, version) -> bytes` runs on the
  worker. It builds the worker's state from the initializer the first
  time a process sees it, and keeps it (a pool's initializer, without
  a pool). It returns a task's exception as data.
- `RemotePool` pickles, dispatches, and raises the earliest task's
  exception as itself.
- A subclass implements `dispatch(init_payload, payloads)`.

None of it imports Spark, so it is tested in every CI cell by a
backend whose `dispatch` is a fresh isolated interpreter.

Exceptions are caught in the task for two reasons. Raw, a failure
reaches the driver as `pyspark...PythonException` and not as itself,
which breaks the `run` contract. And Spark retries a failed task, so
a deterministic error in a long path would be reached four times.

Retries and speculative copies are otherwise harmless, and this is
the RNG redesign paying off: a task computes its streams from the
coordinates it carries, so running it twice, or anywhere, gives the
same answer.

### `backends/spark.py`: `range()` and a UDF

`dispatch` is `spark.range(n, numPartitions=n)` — exactly one task
index per partition — and a plain Python UDF returning bytes.

This was not a matter of taste. **A Spark Connect session has no
`sparkContext`**: no `parallelize`, no RDDs, no broadcast variables.
Verified locally (`JVM_ATTRIBUTE_NOT_SUPPORTED`) and pinned by
`tests/test_spark_backend.py`. Spark Connect is what Databricks
serverless and shared-access clusters provide — **that part is from
memory and has not been checked against a Databricks runtime.** If it
is right, an RDD-based backend would not have run where most notebook
users are; the DataFrame route exists on both kinds of session.

`useArrow=False` keeps pandas and pyarrow out of the requirements.

Payloads ride in the UDF's closure, so each task receives all of
them. They are small, except `par_diff`'s, which carry each path's
results; a very large `isp` with large per-path results is the case to
watch.

### Transport: what reaches a worker

Three forms of `executor.ClassRef`:

| Form | Used for | Needs on the worker |
|---|---|---|
| By reference | pymoso's own classes; locally, anything a fresh process can import | the module, importable |
| Source bundle (text) | classes from a user's `.py` file given to the CLI | nothing |
| By value (cloudpickle) | classes with no source file; for a remote backend, everything not part of pymoso | cloudpickle, and the modules the class imports |

Two things found by measurement rather than assumed:

**The source bundle does not need a shared filesystem.** Phase 4's
brief said it did. `_build_source_bundle` reads the files in the
parent and ships their text; a handle was built, its directory
deleted, and the handle loaded in a fresh process in another
directory, where it simulated correctly. What a bundle does assume:
one flat directory; every `.py` in it is sent, wanted or not (on a
cluster that means unrelated source leaves the machine); and no data
files are sent.

**The real gap was by-reference classes that only the driver can
import.** `build_transport_descriptor` treated "pickles here" as
"transportable". With Spark executors on a second interpreter, a
class from a module on the driver's path failed there with
`ModuleNotFoundError`; registered by value with cloudpickle, it ran
and matched serial. Hence `remote=True`: only pymoso's own classes go
by reference.

What by-value transport does not fix:

- Modules the class imports travel by reference. They must be
  installed on the executors — pymoso included.
- Data files, open handles, locks, and anything referring to `spark`
  or `dbutils`. Such a class is refused in the parent, by name.
- A different Python minor version: cloudpickle ships bytecode.
- Sibling modules of a by-value module still go by reference.

### Two corrections to earlier decisions

- **By value is a form of `ClassRef`, not a `ProblemHandle` subclass**
  (as `docs/forkserver-hang.md`'s Phase 2 correction and
  `ProblemHandle`'s docstring had it). That plan was made when a
  problem was the only thing that travelled. Testers and solvers
  travel as `ClassRef`s; a by-value handle would have left a
  notebook's tester and solver unable to travel.
- **cloudpickle is its own extra, `notebook`, which `spark` depends
  on** — not part of `spark` only. It serves a case with no Spark in
  it (`simpar=2` in a laptop notebook), and on Databricks `spark` is
  the wrong thing to install.

### The dependency boundary

Core pymoso has no dependencies. Kept true by:

- `tests/test_dependency_boundary.py`, statically: no module outside
  `pymoso/backends/` imports anything at module scope but the standard
  library and pymoso, nor a backend module. Imports of third-party
  modules inside functions are an allowlist of one
  (`executor.py`, cloudpickle).
- The same file, at run time: `solve()` and `testsolve()` in an
  interpreter whose import system refuses numpy, cloudpickle and
  pyspark.
- CI: the fifteen-cell matrix and `clean-clone` install `.[test]`
  only. The `extras` job installs the extras and sets
  `PYMOSO_REQUIRE_EXTRAS`, under which a test that would skip for a
  missing dependency or JVM fails instead.

## What is and is not verified

| | How |
|---|---|
| A backend computes what no backend computes | whole results and end seeds compared, every CI cell (`tests/test_remote_backend.py`) and on real Spark (`tests/test_spark_backend.py`); each comparison shown failing against a backend that answers out of order |
| Payloads are self-contained | fresh isolated interpreter, other directory; Spark executors that provably cannot import the driver's modules |
| Classic and Connect sessions | both, locally and in the `extras` job |
| Python 3.10 and 3.14 with pyspark 4.2.0 | run by hand locally; the `extras` job has not run yet |
| pyspark 3.5 (declared floor) | **not tried** |
| Executors on another host | **no** — one machine throughout |
| A Databricks runtime | **no** — by hand, by someone with one |
| Driver and executors on different hardware or libm | **no**. Variates go through `math.log`; bit-identity across an x86 driver and ARM executors is not established. At path level each path runs wholly on one machine, so paths are self-consistent; at replication level one estimate can mix machines |
| Scale | **no** |

## Notebook use today

A real Jupyter kernel (Python 3.14, forkserver), problem, tester and
solver defined in cells:

| Call | Before Phase 4 | Now, with `pymoso[notebook]` |
|---|---|---|
| `solve(MyProblem, RPERLE, x0)` | works | works |
| `solve(..., simpar=2)` | `ValueError`: no locatable source | works |
| `testsolve(MyTester, ..., proc=1)` | works | works |
| `testsolve(..., proc=2)`, cell tester or solver | `ValueError` | works |
| `simpar=2` / `proc=2`, built-in classes | works | works |

Without cloudpickle the `ValueError` remains and names the extra.

Four usability defects were found on the way and are **not fixed
here**; they are to be proposed separately:

1. An unknown keyword (`nosuchparam=3`) is silently accepted.
2. A list `x0` fails with `cannot use 'list' as a set element`.
3. Every extra keyword is passed through `float()`.
4. The refusal message's remedy, "define it in a .py file", is the
   wrong advice on Databricks. (It now mentions the extra first, but
   still says that.)
