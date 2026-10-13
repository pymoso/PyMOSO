# What bounds `--simpar`

**This document corrects the ceiling story twice. Read both before
proposing any work on `--simpar`'s speed.**

1. *Dispatch overhead is not the ceiling* (Phase 2, below). The
   dispatch baseline (`docs/parallel-dispatch-baseline.md`) shows
   `--simpar` topping out near 2.5-3x on a 6-core machine and calls
   dispatch "unbatched: one job per replication", which reads as though
   per-job overhead were the limit. It is not. Parallelism was confined
   to one `hit()` call, a handful of replications.
2. *Removing that confinement is worth much less than correction 1
   implied* (Phase 3, [the second correction](#the-second-correction-what-batching-can-and-cannot-reach)).
   Batching across `hit()` calls was built. It can only combine points
   that a solver estimates before looking at any result, and:
   - **on a one-dimensional problem there are never two such points,
     so the benchmark this document was built on cannot observe
     batching at all**;
   - **on a two-dimensional bi-objective problem, 35-38% of all
     replications are requested one point at a time by necessity**
     (`ne()`'s first-improvement search and `spli()`'s line search),
     and no batching can reach them. (RPERLE; up to 46% for the other
     RA solvers; 18% in the one `--crn` run measured.)

   The ceiling is a property of the algorithms' call pattern. The
   executor cannot raise it further without reaching into solver
   logic.

## The first correction: dispatch is not the ceiling

Measured before the executor work, the ceiling had two causes, and
dispatch overhead was neither:

1. **Parallelism is confined to one `hit()` call.** A solver calls
   `hit(x, m)` for one point at a time and waits for it. Only that
   call's `m` replications can run concurrently, and `m` is small.
2. **Each `hit()` pays a serial coordinate jump in the parent**
   (`stream_at`, ~1.5-2 ms; `docs/hit-cost-baseline.md`). This matters
   only when a replication is cheap.

The conclusion drawn at the time was that the justification for the
next phase was **batching across `hit()` calls** -- submitting several
points at once -- not reducing per-job dispatch cost. The first half of
that held; the second correction is about the rest.

Absolute timings, not enforced by the test suite. The script that
produced the two tables in this part, `docs/bench_simpar_ceiling.py`,
has since been rewritten for the second correction and no longer
prints them in this form (it cannot time the parent's coordinate work
separately, because the parent no longer does any). Measured 2026-10-12 on an AMD
Ryzen 5 5600X3D (6 cores, 12 threads), MRG32k3a, RSPLINE, the same
three cost tiers and budgets as the dispatch baseline's `--simpar`
sweep, before the executor interface landed.

## The three tiers at 6 workers

| Tier | `g()` per replication | Replications per `hit()` | `stream_at` share of the serial run | Observed speedup | Bound: intra-hit parallelism + serial `stream_at` | Bound: intra-hit parallelism alone | Same, infinite workers |
|---|---|---|---|---|---|---|---|
| Light, Python 3.14 | 0.46 ms | 7.7 | 37% | 1.66x | 1.99x | 4.57x | 7.68x |
| Moderate, Python 3.14 | 4.43 ms | 4.9 | 9% | 2.86x | 3.18x | 4.00x | 4.86x |
| Heavy, Python 3.14 | 13.2 ms | 3.6 | 4% | 2.79x | 3.29x | 3.62x | 3.62x |
| Light, Python 3.10 | 0.56 ms | 7.7 | 38% | 1.65x | 1.95x | 4.57x | 7.68x |
| Moderate, Python 3.10 | 5.23 ms | 4.9 | 10% | 2.83x | 3.12x | 4.00x | 4.86x |
| Heavy, Python 3.10 | 15.7 ms | 3.6 | 4% | 2.89x | 3.25x | 3.62x | 3.62x |

How to read the bounds. "Intra-hit parallelism alone" is the best
speedup of the simulation work if replications may only run alongside
others from the same `hit()` call: each call of `m` replications takes
`ceil(m / workers)` replication-times, summed over the run's actual
calls. It is a property of the solver's call pattern, not of the
machine. The next column adds the parent's measured `stream_at` time
as a serial term.

## What the numbers say

- **Per-job dispatch is negligible.** All queue sends in a run total
  0.2-1.2 ms. The gap between the observed speedup and the bound is
  0.03-0.17 s per run: scheduling, result collection, and six workers
  on six physical cores.
- **The Heavy tier cannot exceed 3.62x with any number of workers.**
  Its runs average 3.6 replications per `hit()`. No dispatch
  improvement changes that.
- **`stream_at` is the binding term only for cheap simulations.** It
  takes the Light tier from a possible 4.57x to 1.99x, and barely
  touches Heavy (3.62x to 3.29x).
- **The bound is not specific to this benchmark's small budgets.**
  RPERLE on ProbTPA at budget 10,000 makes 709 `hit()` calls averaging
  14.7 replications: 5.2x at 6 workers, 14.7x with infinite workers.
  Larger than here because RA sample sizes grow with iteration, but
  still fixed by the call pattern.

## What would raise the ceiling

Written before Phase 3; what became of each is noted in brackets.

- **Cross-hit batching.** [Done, Phase 3. Worth less than this
  paragraph suggests -- see the second correction.] Since the RNG redesign, a replication's
  stream depends only on its coordinate, not on the order points are
  visited in, so replications for different points can be submitted
  together without changing any result. The executor interface takes a
  list of blocks for this reason. What is missing is a caller that
  submits more than one point at a time -- a solver-side change.
- **Moving the jump out of the parent.** [Done, Phase 3: the pool's
  workers compute the stream. It did not lift the Light tier -- see
  "The Light tier got slower at high worker counts" below.] If a backend computes the
  stream from `(root, stream, offset)` in the worker, the ~1.5 ms per
  `hit()` parallelises with the simulation. This is the Light tier's
  37%.
- **A cheaper jump.** [Not done; `docs/rng-interface-design.md` §11
  entry 14. Now the one remaining lever for cheap simulations.] Precomputed matrix powers would shorten
  `stream_at` itself. Golden-neutral and separable; carried as a
  candidate for the batching phase, where its value changes anyway.

## After the executor interface (Phase 2)

Same script, after `Oracle.hit()` moved onto `pymoso/executor.py`. The
script now times everything that turns a block's coordinate into
streams (`SerialExecutor.streams`: both jumps and the per-replication
advances), which is slightly more than the `stream_at` timer above
covered.

| Tier | Coordinate share of the serial run | Observed at 6 workers | Bound: intra-hit + serial coordinates | Bound: intra-hit alone |
|---|---|---|---|---|
| Light, Python 3.14 | 24% (was 37%) | 1.72x | 2.63x | 4.57x |
| Moderate, Python 3.14 | 5% (was 9%) | 2.81x | 3.53x | 4.00x |
| Heavy, Python 3.14 | 2% (was 4%) | 2.94x | 3.46x | 3.62x |
| Light, Python 3.10 | 25% (was 38%) | 1.70x | 2.59x | 4.57x |
| Moderate, Python 3.10 | 6% (was 10%) | 2.75x | 3.49x | 4.00x |
| Heavy, Python 3.10 | 3% (was 4%) | 2.98x | 3.43x | 3.62x |

The serial coordinate term shrank (see docs/hit-cost-baseline.md for
why), which lifts the second bound. The observed speedups barely moved
and the intra-hit bound did not move at all: `--simpar` itself is
unchanged in this phase, and the call pattern is the solver's. The
conclusion stands, more strongly -- what remains between observed and
possible is the confinement to one `hit()` call.

## The second correction: what batching can and cannot reach

Phase 3 added `Oracle.hit_many` and `RASolver.estimate_many`, and a
pool backend that divides *all* the replications of one executor call
among the workers (`executor.PoolExecutor`). So the question stopped
being "how many replications does one `hit()` have" and became "how
many replications does a solver submit before it needs an answer".

That was measured before anything was designed, by recording every
call a solver makes to the executor and which solver routine made it.

### Where a solver submits several points, and where it cannot

RPERLE on ProbTPA, budget 10,000 (797 `hit()` calls, 10,299
replications), by the routine that reached the oracle:

| Routine | Executor calls | Points per call, mean | max | Share of all replications | Can it batch? |
|---|---|---|---|---|---|
| `upsample` (from `pe`, `get_min`, `rle`, `remove_nlwep`) | 73 | 4.78 | 13 | 43.9% | yes: the whole set is estimated whatever the results |
| `pli` (the simplex) | 82 | 1.71 | 2 | 17.1% | yes: `dim + 1` vertices, less those already estimated |
| `get_ncn` (deleted neighbourhood) | 6 | 1.83 | 3 | 0.5% | yes |
| `ne` (neighbourhood search) | 177 | 1.00 | 1 | 23.4% | **no**: returns at the first improving neighbour |
| `spli` (line search) | 120 | 1.00 | 1 | 15.1% | **no**: each step depends on the last result |
| **sequential by necessity (`ne` + `spli`)** | | | | **38.5%** | |

**38.5% of that run's replications cannot be combined with any other
point's.** Across the benchmark workloads below the figure is
35.1-35.7%. Without `--crn` it stayed between 35% and 46% in every run
surveyed:

| Run (no `--crn`) | Sequential by necessity |
|---|---|
| RPERLE, ProbTPA, budget 1,000 | 35.3% |
| RPERLE, ProbTPA, budget 10,000 | 38.5% |
| RPERLE, ProbTPB, budget 10,000 | 42.5% |
| RPERLE, ProbTPC (3-D), budget 3,000 | 34.8% |
| RMINRLE, ProbTPA, budget 1,000 / 10,000 | 38.2% / 45.6% |
| RPE, ProbTPA, budget 1,000 / 10,000 | 44.8% / 41.1% |

It is a structural property of the R-SPLINE search these solvers
share, not of a problem or a budget. The one `--crn` run surveyed
(RPERLE, ProbTPA, budget 10,000) is different: 18.4%, because under
CRN the run does far more `upsample` and `get_ncn` work (71% of its
replications, in calls averaging 9-10 points), and its batched bound
at infinite workers is 28.9x against 9.4x. `--crn` runs were not
benchmarked in this phase.

And without `--crn` the routines that can batch do not carry much: a
batching call averages 1.5-2 points.

The bound on speedup, same method as the first correction's tables
(each group of `n` replications that may run together takes
`ceil(n / workers)` replication-times):

| RPERLE on ProbTPA | 6 workers | 12 workers | infinite workers |
|---|---|---|---|
| budget 1,000: one `hit()` at a time -> batched | 4.16x -> 4.88x | 4.16x -> 6.32x | 4.16x -> 7.23x |
| budget 10,000: one `hit()` at a time -> batched | 5.09x -> 5.49x | 8.28x -> 9.69x | 12.9x -> 22.5x |

Batching matters most when sample sizes are small relative to the
worker count: at budget 10,000 a single `hit()` already carries 12.9
replications and fills six workers on its own.

### The original benchmark cannot observe batching

Stated plainly, because a benchmark that cannot see the change it is
used to judge misleads whoever reads it next: **every table in the
first correction, and every `--simpar` table in
`docs/parallel-dispatch-baseline.md`, comes from RSPLINE on the
one-dimensional `ProbExpensive`. On that workload batching changes
nothing, and cannot.** Each RA iteration makes exactly three `hit()`
calls -- one from `upsample` (the single warm-start point), one from
`pli` (a simplex of two vertices, one of which is always the point
just estimated), one from `ne` -- and each carries one point. Its
batched bound equals its intra-hit bound at every worker count. The
Heavy tier's 3.62x is unchanged by this phase and will be unchanged by
any executor work at all.
`tests/test_batching.py::test_a_one_dimensional_problem_never_has_two_points_to_submit`
holds that down.

That is why `ProbExpensiveBi` was added
(`pymoso/problems/probexpensive.py`): ProbTPA's two-dimensional,
two-objective distribution with ProbExpensive's tunable burn, at the
same three cost tiers, solved with RPERLE. It is the smallest workload
on which batching can be seen. It is not registered in
`pymoso.problems`.

## After the worker pool and batching (Phase 3)

`python docs/bench_simpar_ceiling.py`, kept runnable by
`tests/test_benchmark_scripts.py` (a smoke test; it asserts no
timings). Measured 2026-10-12 on the same machine (AMD Ryzen 5 5600X3D,
6 cores, 12 threads), MRG32k3a. Each observed figure is one run after
one warm-up, and repeat runs of the same cell differ by 5-10%; read
differences smaller than that as noise.

### The workloads

| Workload | Solver | Budget | `hit()` calls | Replications per `hit()` | Points per executor call | Replications per executor call | Sequential by necessity |
|---|---|---|---|---|---|---|---|
| Light, 1-D | RSPLINE | 500 | 66 | 7.7 | 1.00 | 7.7 | 33.3% |
| Moderate, 1-D | RSPLINE | 200 | 42 | 4.9 | 1.00 | 4.9 | 33.3% |
| Heavy, 1-D | RSPLINE | 80 | 24 | 3.6 | 1.00 | 3.6 | 33.3% |
| Light, 2-D | RPERLE | 3000 | 484 | 6.4 | 1.80 | 11.5 | 35.1% |
| Moderate, 2-D | RPERLE | 1000 | 264 | 4.2 | 1.74 | 7.2 | 35.3% |
| Heavy, 2-D | RPERLE | 400 | 125 | 3.2 | 1.71 | 5.5 | 35.7% |

(The 1-D rows' 33.3% is `ne`'s one call in three; the other two calls
are batchable in principle and have one point each.)

### What batching buys where it can be observed

"One point at a time" is the same code with `estimate_many` replaced by
the loop it replaced, so the two observed columns differ in batching
and nothing else.

| Workload | Workers | `g()` per replication | Bound, one `hit()` at a time | Bound, batched | Observed, one point at a time | Observed, batched |
|---|---|---|---|---|---|---|
| Light, 2-D, Python 3.14 | 6 | 0.46 ms | 4.38x | 5.04x | 1.68x | 2.23x |
| Light, 2-D, Python 3.14 | 12 | | 6.38x | 8.23x | 1.55x | 2.06x |
| Moderate, 2-D, Python 3.14 | 6 | 4.42 ms | 4.16x | 4.88x | 2.96x | 3.71x |
| Moderate, 2-D, Python 3.14 | 12 | | 4.16x | 6.32x | 3.01x | 3.53x |
| Heavy, 2-D, Python 3.14 | 6 | 13.2 ms | 3.22x | 4.24x | 2.85x | 3.50x |
| Heavy, 2-D, Python 3.14 | 12 | | 3.22x | 5.10x | 2.83x | 3.61x |
| Light, 2-D, Python 3.10 | 6 | 0.56 ms | 4.38x | 5.04x | 1.74x | 2.25x |
| Light, 2-D, Python 3.10 | 12 | | 6.38x | 8.23x | 1.53x | 2.04x |
| Moderate, 2-D, Python 3.10 | 6 | 5.45 ms | 4.16x | 4.88x | 3.08x | 3.61x |
| Moderate, 2-D, Python 3.10 | 12 | | 4.16x | 6.32x | 2.96x | 3.69x |
| Heavy, 2-D, Python 3.10 | 6 | 16.4 ms | 3.22x | 4.24x | 2.91x | 3.50x |
| Heavy, 2-D, Python 3.10 | 12 | | 3.22x | 5.10x | 2.90x | 3.69x |

With infinite workers the batched bounds are 11.5x, 7.23x and 5.52x
(from 6.38x, 4.16x and 3.22x).

- **Batching is real and modest.** At 6 workers it takes the Moderate
  and Heavy tiers from about 2.9-3.0x to 3.5-3.7x: roughly a fifth
  less wall time.
- **Observed sits 20-30% under the batched bound at 6 workers** for
  Moderate and Heavy, and does not improve at 12, although the bound
  does. This machine has six physical cores.
- **The Light tier is still bounded by the coordinate jump,** not by
  the call pattern: 2.2x against a bound of 5.0x.

### The original one-dimensional tiers, before and after

From `docs/bench_parallel_dispatch.py`'s `--simpar` sweep, run before
and after this phase. "Before" is `Oracle.set_simpar`'s own
`Process`/`Queue` workers; "after" is the pool backend. Batching plays
no part in these rows.

| Tier | Workers | Python 3.14, before -> after | Python 3.10, before -> after |
|---|---|---|---|
| Light | 4 | 1.62x -> 1.67x | 1.59x -> 1.71x |
| Light | 6 | 1.71x -> 1.53x | 1.62x -> 1.67x |
| Light | 12 | 1.64x -> 1.27x | 1.67x -> 1.46x |
| Moderate | 4 | 2.48x -> 2.58x | 2.48x -> 2.60x |
| Moderate | 6 | 2.80x -> 2.65x | 2.83x -> 2.84x |
| Moderate | 12 | 2.73x -> 2.96x | 2.88x -> 2.98x |
| Heavy | 4 | 2.59x -> 2.76x | 2.76x -> 2.92x |
| Heavy | 6 | 2.80x -> 2.98x | 2.90x -> 3.37x |
| Heavy | 12 | 2.72x -> 3.12x | 3.01x -> 3.14x |

Moderate and Heavy are where they were, a little better if anything,
against unchanged bounds of 4.00x and 3.62x. As predicted above.

### The Light tier got slower at high worker counts

A regression, reported rather than tuned away. The pool cuts each
executor call into as many pieces as it has workers, and each piece
pays its own jump to its starting offset (about 0.7 ms here, against
a 0.46 ms replication). For a 7.7-replication block that stops paying
off before the worker count is reached. Measured directly, Light 1-D,
Python 3.14, median of five, with the number of pieces capped:

| Workers | Pieces per call at most | Speedup |
|---|---|---|
| 6 | 2 | 1.35x |
| 6 | 4 | 1.70x |
| 6 | 6 (what the pool does) | 1.52x |
| 12 | 4 | 1.69x |
| 12 | 6 | 1.80x |
| 12 | 12 (what the pool does) | 1.52x |

So for a simulation cheaper than the jump, fewer pieces than workers is
faster, and the pool does not know that. Two honest options, neither
taken in this phase: a cheaper jump (`docs/rng-interface-design.md`
§11 entry 14), which removes the cause; or choosing the piece count
from measured jump and simulation times, which treats the symptom.
Moving the jump into the workers was expected to lift this tier (a
quarter of its serial run is coordinate time); it did not, because the
replaced mechanism made one jump per `hit()` and the pool makes one
per piece.

### `--proc`

Same sweep, 12 sample paths, one task per path before and after. The
change is the mechanism (`multiprocessing.Pool` shipping live Oracles
-> the pool shipping `PathJob`s), not the granularity.

| Tier | Workers | Python 3.14, before -> after | Python 3.10, before -> after |
|---|---|---|---|
| Light | 6 | 4.78x -> 5.02x | 4.66x -> 5.18x |
| Light | 12 | 4.72x -> 5.80x | 4.21x -> 5.94x |
| Moderate | 6 | 5.43x -> 4.79x | 5.45x -> 5.64x |
| Moderate | 12 | 5.59x -> 5.87x | 5.43x -> 5.89x |
| Heavy | 6 | 5.38x -> 5.58x | 5.52x -> 5.65x |
| Heavy | 12 | 5.56x -> 5.93x | 5.42x -> 5.73x |

Unchanged in substance: it plateaus at the six physical cores, as
before. (The one lower cell, Moderate at 6 on 3.14, is a single run of
0.61 s against 0.54 s; its neighbours at 4, 8 and 12 workers are all
slightly better than before.)

### A serial `hit()` costs what it did

`docs/bench_hit_cost.py`, microseconds per call, before -> after:

| Call | Python 3.14 | Python 3.10 |
|---|---|---|
| `hit(x, m=1)`, crn=True | 19 -> 20 | 34 -> 35 |
| `hit(x, m=8)`, crn=True | 138 -> 138 | 217 -> 217 |
| `hit(x, m=1)`, crn=False | 737 -> 757 | 988 -> 1,021 |
| `hit(x, m=64)`, crn=False | 1,588 -> 1,618 | 2,320 -> 2,357 |

Two to three percent on the default branch, from `hit()` now building
its block and aggregating its result in separate steps so that
`hit_many` can share them. The base-stream cache that keeps `--crn`
cheap is intact.

## What would raise the ceiling now

- **Speculative prefetch of the sequential part**
  (`docs/rng-interface-design.md` §11 entry 15): idle workers simulate
  what `ne()` or the line search will ask for next. It is the only
  thing that can move the bound, and it was declined for Phase 3
  because something outside the solver would have to know the solver's
  next move. Start by measuring how often the obvious guesses are
  right.
- **A cheaper jump** (§11 entry 14), for cheap simulations only.
- **Converting MOCOMPASS and MOPBnB to `hit_many`.** Both evaluate
  long unconditional lists of points and would batch far better than
  the RA solvers. Not measured.
- **Running a solver's independent searches concurrently** -- the
  per-objective `spline()` calls in `get_min`, the per-epsilon chains
  in `pe`. They do not depend on one another's results, only on a
  shared cache. This needs solver logic restructured as concurrent
  tasks, and is not measured.
- More physical cores, for the Moderate and Heavy tiers: at 12 workers
  on 6 cores the observed speedup stops following the bound.
