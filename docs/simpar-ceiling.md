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
   - **on a two-dimensional bi-objective problem without `--crn`,
     35-38% of all replications are requested one point at a time by
     necessity** (`ne()`'s first-improvement search and `spli()`'s
     line search), and no batching can reach them. (RPERLE; up to 46%
     for the other RA solvers.)
   - **that figure is a non-CRN number. Do not quote it for `--crn`.**
     The one `--crn` run surveyed had a sequential share of 18%
     against 35-46% without. That is one run, and `--crn` was not
     benchmarked at all: no `--crn` speedup in this document is
     measured, only that one bound computed.

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
  entry 14. Now the one remaining lever for cheap simulations.]
  [Landed in Phase 7 step 3 (2026-10-17): a general MRG jump is now 20-70 µs on 3.14 (`docs/hit-cost-baseline.md`, "After the cheaper jump"); this document's sweeps were re-run on 2026-11-23, "After the cheaper jump (Phase 7 step 3)", below.] Precomputed matrix powers would shorten
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
point's.** That run, and every figure in the table below, is without
`--crn`; the `--crn` share is lower and is described after the table.
Across the benchmark workloads below the figure is
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

So there are two sequential shares, and only one of them is
established: **35-46% without `--crn`** (eight runs, three solvers,
three problems) and **18% with it** (one run, one solver, one problem,
one budget, bound computed and nothing timed). Anything said about
`--simpar` under `--crn` on the strength of this document is an
extrapolation from that single run.

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

### The Light tier at high worker counts: a piece cap, measured and declined

The before/after table shows the Light tier slower after this phase
at 6 and 12 workers on Python 3.14 (1.71x -> 1.53x, 1.64x -> 1.27x).
The pool cuts each executor call into as many pieces as it has
workers, and each piece pays its own jump to its starting offset:
about 0.7 ms here, against a 0.46 ms replication. The obvious remedy
is to cap the pieces so that each carries enough work to outweigh its
own overhead. **That policy was proposed, measured, and not built.**
The data and the reasons follow, so that it is not proposed again
without new evidence.

Speedup over serial with the pieces per call capped. Python 3.14,
6 physical cores, median of five, workers started outside the timed
region. The rightmost entry in each row is what the pool does.

| Tier | Workers | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 12 |
|---|---|---|---|---|---|---|---|---|---|
| Light 1-D | 6 | 0.93x | 1.31x | 1.54x | 1.59x | 1.69x | 1.64x | | |
| Light 1-D | 12 | 0.95x | 1.31x | 1.52x | 1.63x | 1.69x | 1.63x | 1.45x | 1.42x |
| Light 2-D | 6 | 0.97x | 1.57x | 1.87x | 2.11x | 2.12x | 2.28x | | |
| Light 2-D | 12 | 0.97x | 1.57x | 1.88x | 2.12x | 2.18x | 2.27x | 1.92x | 1.96x |
| Moderate 1-D | 6 | 0.98x | 1.63x | 2.13x | 2.59x | 2.69x | 2.86x | | |
| Moderate 1-D | 12 | 0.99x | 1.62x | 2.15x | 2.54x | 2.68x | 2.93x | 2.96x | 3.05x |

What it shows:

- **At 6 workers there is nothing for a cap to fix.** Six pieces is at
  or near the best in every tier (Light 1-D: 1.64x against 1.69x at
  five, inside run-to-run noise).
- **At 12 workers a cap helps the Light tiers only**: past six pieces,
  which is this machine's physical core count, they lose 10-15%.
  Moderate keeps gaining up to 12.
- The policy as proposed -- pieces = replications x time per
  replication / overhead per piece, from times the workers measure,
  limited by the worker count -- would give Light 1-D about five
  pieces and leave Moderate and Heavy alone. It has no margin
  (requiring twice the overhead gives two or three pieces, 1.3-1.5x,
  worse than no policy) and it would give Light 2-D's larger calls
  seven or eight pieces, where the table shows 1.92x against 2.27x.

Why it was declined:

1. It does not address the figure that prompted it. The 6-worker drop
   cannot be recovered by any cap.
2. What it buys is 12 workers on 6 cores for cheap replications, in
   part -- the tier where parallelism helps least.
3. It costs a self-tuning dispatch policy: how a call is cut would
   depend on timings, which makes dispatch harder to reason about and
   to test, for a number that may not be real (below).

**The overhead itself is the problem.** A piece's 0.7 ms is the jump,
and it is larger than the 0.46 ms replication it precedes. No choice
of piece count changes that ratio; it only chooses how many times to
pay it. The cheaper general jump (`docs/rng-interface-design.md` §11
entry 14) attacks it directly, and if it lands the cheap-replication
case may need no policy at all. That makes entry 14 a
better-motivated candidate than it was; re-run this sweep after it,
before considering a cap again. [Landed in Phase 7 step 3 (2026-10-17): a general MRG jump is now 20-70 µs on 3.14 (`docs/hit-cost-baseline.md`, "After the cheaper jump"). Re-run 2026-11-23 ("After the cheaper
jump (Phase 7 step 3)", below): a piece now costs about 35 µs against a
0.46 ms replication, and the data does not support a cap.]

**Unresolved, and not to be dropped: whether the 6-worker Light 1-D
figure is noise or has another cause is not established.** The
evidence is inconsistent. The before/after sweep measured 1.71x ->
1.53x. An earlier cap experiment in this phase measured 1.52x at six
pieces and 1.70x at four. The sweep above, the same experiment run
again, measured 1.64x at six and 1.59x at four. Run-to-run variation
on this tier is at least that large, so the regression may not exist;
equally, nothing here rules out a real cost of the pool backend at 6
workers that a cap does not touch. Settling it needs repeated
interleaved before/after runs (the pre-pool code is commit `c19dc9d`),
not one more sweep. The 12-worker figure (1.64x -> 1.27x, and
1.42-1.52x in both cap experiments) is consistent and is taken as
real.

**Update, end of Phase 4: the evidence now favours noise.** Two runs
of the same code, on an idle machine, gave 1.59x and 1.78x for this
cell ("Baselines at the end of Phase 4", below). That spread
straddles both figures that opened the question, 1.53x and 1.71x: one
run of the current code landed above the "before" number. So the
regression is most likely not there. The interleaved before-and-after
comparison this paragraph asked for was never run, and that is the
only thing that would settle it; what there is now is two more
samples and a spread wide enough to explain the original difference
without a cause.

**Settled 2026-11-23: the drop was real, and the paragraph above was
wrong.** The interleaved comparison it asked for was run (`c19dc9d`
against `6877979`, "After the cheaper jump (Phase 7 step 3)", below):
the pool made this cell 8-10% slower, less than the spread between
two single runs, which is how two runs could straddle it. The cheaper
jump more than recovered it.

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

## After the backend seam and the Spark backend (Phase 4)

Phase 4 put a backend between these features and their pool, added a
remote one, and replaced `get_nbors`. Nothing on the local path was
meant to get slower. This section answers whether anything did, and
then records the baselines as they stand at the end of the phase.

### Nothing on the local path changed

The first re-run of the three benchmark scripts was made while the
machine was doing other work (one core held at about 90% by an
unrelated process) and was discarded: code Phase 4 does not touch
measured 10-14% slow. In its place the commit before Phase 4
(`24c4f5f`) was run against the Phase 4 tree directly -- the same
five measurements, seven rounds each, alternating which went first,
on that same busy machine. Medians; a ratio above 1 means Phase 4 is
slower.

| Measurement | Python 3.14: before, after, ratio | Python 3.10: before, after, ratio |
|---|---|---|
| `hit(x, m=8)`, `crn=True`, a new point each call | 312 µs, 300 µs, 0.96 | 431 µs, 438 µs, 1.02 |
| `hit(x, m=8)`, `crn=False` | 1,669 µs, 1,601 µs, 0.96 | 2,138 µs, 2,169 µs, 1.01 |
| serial `solve`, RPERLE on ProbTPA, budget 5,000 | 1.096 s, 1.107 s, 1.01 | 1.435 s, 1.463 s, 1.02 |
| `simpar=6`, RPERLE on ProbExpensiveBiModerate, budget 600 | 1.298 s, 1.318 s, 1.02 | 1.612 s, 1.621 s, 1.01 |
| `proc=6`, 12 Moderate paths | 0.692 s, 0.690 s, 1.00 | 0.860 s, 0.865 s, 1.01 |

Every ratio is within 4% of 1 and inside the spread of its own seven
runs. (That comparison predates the `get_nbors` change, which is not
on any of these paths in one or two dimensions to a measurable
degree: the refreshed figures below include it and agree with Phase
3's.)

### Baselines at the end of Phase 4

Refreshed 2026-10-13 on the same machine (AMD Ryzen 5 5600X3D, 6
cores, 12 threads) with nothing else running: load average under 0.1
when the runs began. Each script was run twice on each Python and
**both runs are shown**, so the spread is visible rather than
described. These replace the Phase 3 tables above as the figures to
compare later work against. Every structural figure -- calls, points
per call, the sequential share, every bound -- reproduced exactly.

`python docs/bench_simpar_ceiling.py`, the two-dimensional tiers
(RPERLE), where batching can be observed:

| Workload | Workers | `g()` per replication | Bound, one `hit()` at a time | Bound, batched | Observed, one point at a time (two runs) | Observed, batched (two runs) |
|---|---|---|---|---|---|---|
| Light, 2-D, Python 3.14 | 6 | 0.47 ms | 4.38x | 5.04x | 1.74x, 1.75x | 2.26x, 2.18x |
| Light, 2-D, Python 3.14 | 12 | 0.47 ms | 6.38x | 8.23x | 1.52x, 1.51x | 1.98x, 1.94x |
| Moderate, 2-D, Python 3.14 | 6 | 4.54 ms | 4.16x | 4.88x | 3.09x, 3.15x | 3.49x, 3.74x |
| Moderate, 2-D, Python 3.14 | 12 | 4.54 ms | 4.16x | 6.32x | 3.08x, 3.11x | 3.48x, 3.60x |
| Heavy, 2-D, Python 3.14 | 6 | 13.54 ms | 3.22x | 4.24x | 2.92x, 2.90x | 3.58x, 3.71x |
| Heavy, 2-D, Python 3.14 | 12 | 13.54 ms | 3.22x | 5.10x | 2.89x, 2.89x | 3.76x, 3.70x |
| Light, 2-D, Python 3.10 | 6 | 0.57 ms | 4.38x | 5.04x | 1.66x, 1.58x | 2.30x, 2.20x |
| Light, 2-D, Python 3.10 | 12 | 0.57 ms | 6.38x | 8.23x | 1.57x, 1.50x | 2.06x, 1.98x |
| Moderate, 2-D, Python 3.10 | 6 | 5.46 ms | 4.16x | 4.88x | 3.12x, 3.14x | 3.51x, 3.69x |
| Moderate, 2-D, Python 3.10 | 12 | 5.46 ms | 4.16x | 6.32x | 3.14x, 3.12x | 3.63x, 3.68x |
| Heavy, 2-D, Python 3.10 | 6 | 16.51 ms | 3.22x | 4.24x | 2.90x, 2.84x | 3.59x, 3.71x |
| Heavy, 2-D, Python 3.10 | 12 | 16.51 ms | 3.22x | 5.10x | 2.89x, 2.88x | 3.67x, 3.70x |

`python docs/bench_parallel_dispatch.py sweep`, `--simpar`, the
one-dimensional tiers (RSPLINE; batching plays no part). Serial run,
3.14 / 3.10: Light 0.35 s / 0.45 s; Moderate 1.00 s / 1.23 s; Heavy 1.22 s / 1.51 s.

| Tier | Workers | Python 3.14 (two runs) | Python 3.10 (two runs) |
|---|---|---|---|
| Light | 2 | 1.11x, 1.11x | 1.37x, 1.36x |
| Light | 4 | 1.63x, 1.59x | 1.68x, 1.69x |
| Light | 6 | 1.59x, 1.78x | 1.61x, 1.52x |
| Light | 8 | 1.44x, 1.43x | 1.45x, 1.42x |
| Light | 12 | 1.44x, 1.29x | 1.42x, 1.49x |
| Moderate | 2 | 1.63x, 1.64x | 1.67x, 1.67x |
| Moderate | 4 | 2.51x, 2.52x | 2.64x, 2.65x |
| Moderate | 6 | 2.85x, 3.02x | 2.53x, 2.93x |
| Moderate | 8 | 2.92x, 2.86x | 2.81x, 2.81x |
| Moderate | 12 | 2.85x, 2.82x | 2.86x, 2.81x |
| Heavy | 2 | 1.62x, 1.63x | 1.66x, 1.67x |
| Heavy | 4 | 2.86x, 2.84x | 2.97x, 2.90x |
| Heavy | 6 | 3.14x, 3.12x | 3.14x, 3.16x |
| Heavy | 8 | 3.09x, 3.13x | 3.18x, 3.20x |
| Heavy | 12 | 3.11x, 3.10x | 3.17x, 3.17x |

The same sweep, `--proc`, 12 sample paths. Serial run, 3.14 / 3.10:
Light 1.04 s / 1.33 s; Moderate 2.94 s / 3.61 s; Heavy 3.09 s / 3.73 s.

| Tier | Workers | Python 3.14 (two runs) | Python 3.10 (two runs) |
|---|---|---|---|
| Light | 2 | 1.94x, 1.93x | 1.97x, 1.95x |
| Light | 4 | 3.75x, 3.76x | 3.68x, 3.83x |
| Light | 6 | 4.87x, 4.88x | 5.37x, 5.50x |
| Light | 8 | 4.93x, 5.38x | 5.42x, 5.38x |
| Light | 12 | 5.30x, 5.27x | 5.55x, 5.93x |
| Moderate | 2 | 1.95x, 1.96x | 1.97x, 1.95x |
| Moderate | 4 | 3.83x, 3.86x | 3.86x, 3.86x |
| Moderate | 6 | 5.53x, 5.39x | 5.38x, 5.59x |
| Moderate | 8 | 5.52x, 5.63x | 5.67x, 5.43x |
| Moderate | 12 | 5.86x, 5.82x | 5.78x, 5.77x |
| Heavy | 2 | 1.95x, 1.94x | 1.97x, 1.97x |
| Heavy | 4 | 3.85x, 3.81x | 3.87x, 3.86x |
| Heavy | 6 | 5.52x, 5.63x | 5.45x, 5.43x |
| Heavy | 8 | 5.49x, 5.49x | 5.53x, 5.47x |
| Heavy | 12 | 6.00x, 5.99x | 5.94x, 5.77x |

A serial `hit()`: `docs/hit-cost-baseline.md`, "At the end of Phase
4".

What these say against Phase 3's tables:

- **The same, within the spread.** Batched at 6 workers on 3.14:
  Light 2.26x and 2.18x (2.23x recorded), Moderate 3.49x and 3.74x
  (3.71x), Heavy 3.58x and 3.71x (3.50x).
- **Two runs of one cell differ by up to about 10%,** as Phase 3
  said: Moderate 2-D at 6 workers gave 3.49x and 3.74x; Moderate 1-D
  at 6 workers on 3.10 gave 2.53x and 2.93x.
- **On the open question of the Light 1-D tier at 6 workers** (above:
  1.71x before the pool, 1.53x after, noise or real?): these two runs
  gave 1.59x and 1.78x on 3.14 for that cell, straddling both of the
  figures that prompted the question. The evidence now favours noise.
  The interleaved before-and-after comparison that section asked for
  was never run. [Run 2026-11-23: the drop was real, 8-10%, and the
  cheaper jump more than recovered it. "After the cheaper jump (Phase
  7 step 3)", below.]
- The 12-worker Light figures (1.44x and 1.29x on 3.14) remain below
  the 6-worker ones, as recorded.

Sending replications to a cluster has its own break-even, far from
anything in this document, and it has been measured on real
clusters: `docs/spark-backend.md`, "On a real cluster". That section
also has the sample-path scaling numbers; they are not repeated here.
One thing there bears on this document: at `simpar=6` the cluster
runs reached 3.7-4.7x against batched bounds of 4.6-4.9 once a
replication was expensive, so the bound computed from a solver's call
pattern held on hardware it was not derived on.

## After the cheaper jump (Phase 7 step 3)

Phase 7 step 3 cut the MRG family's general jump from about 1.6 ms to
20-70 µs on Python 3.14 (`docs/hit-cost-baseline.md`, "After the
cheaper jump"). The Light-tier figures above predate it. This section
re-runs the Phase 4 sweep at `402e512` and asks what the jump did to
the speedup ratio.

Three hypotheses were stated before the run:

- **H1, the ratio improves.** Each piece paid its own jump, so the
  penalty fell mostly on `--simpar`.
- **H2, the ratio worsens.** Serial paid the jump too. If it was a
  large share of serial time, the numerator shrinks as well, and the
  costs that did not get cheaper (pipe and pickling) become the floor.
- **H3, roughly unchanged.** The bound is the solver's call pattern,
  and a cheaper jump cannot raise it.

The data supports **H1**. H2's mechanism is real: serial Light time
fell by 29%. But parallel time fell by 48-54%, and the pipe and
pickling costs are small (below). H3 does not describe the Light
tiers, which sit at 37-64% of their bound. It does describe Moderate
and Heavy in one dimension, at 85-94%, and those did not change.

Written predictions and the raw output of every run are kept outside
the repository, with the rest of the session's scratch material. They
are not needed to read this section.

### The workloads changed between Phase 4 and here

Phase 7's algorithm fixes (relaxation, SPLI, SPLINE; CLAUDE.md, "Fixed
on this branch") changed what R-SPLINE and R-PERLE do with the same
budget. So **the figures below are not the Phase 4 workloads re-timed**:

| Workload | `hit()` calls, Phase 4 -> now | Sequential by necessity, Phase 4 -> now |
|---|---|---|
| Light, 2-D (RPERLE, budget 3,000) | 484 -> 362 | 35.1% -> 55.0% |
| Moderate, 2-D (budget 1,000) | 264 -> 212 | 35.3% -> 50.6% |
| Heavy, 2-D (budget 400) | 125 -> 115 | 35.7% -> 48.0% |
| Light / Moderate / Heavy, 1-D (RSPLINE, `x0 = (97,)`) | 66 / 42 / 24 -> 98 / 58 / 28 | 33.3% -> 57.1% / 60.1% / 60.7% |

Only a pair of commits with identical output isolates the jump.
`30bfa68` -> `27961b8` is that pair, and it is reported below, after
the baselines.

### Baselines on 2026-11-23

Same machine (AMD Ryzen 5 5600X3D, 6 cores, 12 threads), MRG32k3a.
Load average was 0.15 when the runs began. It rose to 1.8-2.9 during
them; `top` between runs showed the machine 98% idle, so the load was
the benchmarks' own worker processes. Each script was run twice on
each Python, unmodified, and **both runs are shown**.

`python docs/bench_simpar_ceiling.py`, the two-dimensional tiers:

| Workload | Workers | `g()` per replication | Bound, one `hit()` at a time | Bound, batched | Observed, one point at a time (two runs) | Observed, batched (two runs) |
|---|---|---|---|---|---|---|
| Light, 2-D, Python 3.14 | 6 | 0.47 ms | 4.72x | 4.98x | 2.89x, 2.84x | 3.17x, 3.12x |
| Light, 2-D, Python 3.14 | 12 | 0.47 ms | 6.88x | 7.87x | 3.08x, 3.22x | 3.46x, 3.28x |
| Moderate, 2-D, Python 3.14 | 6 | 4.50 ms | 4.03x | 4.42x | 3.45x, 3.54x | 3.74x, 3.57x |
| Moderate, 2-D, Python 3.14 | 12 | 4.50 ms | 4.96x | 6.15x | 3.67x, 3.82x | 4.01x, 3.99x |
| Heavy, 2-D, Python 3.14 | 6 | 13.43 ms | 3.71x | 4.15x | 3.49x, 3.52x | 3.77x, 3.55x |
| Heavy, 2-D, Python 3.14 | 12 | 13.43 ms | 3.71x | 4.91x | 3.51x, 3.50x | 3.92x, 3.86x |
| Light, 2-D, Python 3.10 | 6 | 0.55 ms | 4.72x | 4.98x | 3.30x, 3.25x | 3.24x, 3.23x |
| Light, 2-D, Python 3.10 | 12 | 0.55 ms | 6.88x | 7.87x | 3.40x, 3.37x | 3.58x, 3.50x |
| Moderate, 2-D, Python 3.10 | 6 | 5.32 ms | 4.03x | 4.42x | 3.60x, 3.66x | 3.84x, 3.67x |
| Moderate, 2-D, Python 3.10 | 12 | 5.32 ms | 4.96x | 6.15x | 3.88x, 3.87x | 4.12x, 4.06x |
| Heavy, 2-D, Python 3.10 | 6 | 15.88 ms | 3.71x | 4.15x | 3.56x, 3.50x | 3.63x, 3.75x |
| Heavy, 2-D, Python 3.10 | 12 | 15.88 ms | 3.71x | 4.91x | 3.56x, 3.47x | 3.97x, 3.85x |

With infinite workers the batched bounds are 10.75x, 6.66x and 5.08x.

`python docs/bench_parallel_dispatch.py sweep`, `--simpar`, the
one-dimensional tiers (RSPLINE, `x0 = (50,)`; batching plays no part).
Sequential by necessity in this configuration: 56.3%, 57.1% and 60.7%.
Bounds at 6 / 12 workers: Light 4.33x / 5.73x, Moderate 3.81x / 3.81x,
Heavy 3.00x / 3.00x. Serial run, 3.14 (two runs) / 3.10 (two runs):
Light 0.26 s, 0.25 s / 0.31 s, 0.31 s; Moderate 0.98 s, 0.97 s / 1.16
s, 1.18 s; Heavy 1.13 s, 1.12 s / 1.35 s, 1.36 s.

| Tier | Workers | Python 3.14 (two runs) | Python 3.10 (two runs) |
|---|---|---|---|
| Light | 2 | 1.13x, 1.10x | 1.68x, 1.65x |
| Light | 4 | 2.28x, 2.13x | 2.69x, 2.56x |
| Light | 6 | 2.19x, 2.38x | 2.60x, 2.43x |
| Light | 8 | 2.14x, 2.09x | 2.77x, 2.75x |
| Light | 12 | 2.05x, 2.08x | 2.88x, 2.92x |
| Moderate | 2 | 1.60x, 1.63x | 1.69x, 1.66x |
| Moderate | 4 | 2.75x, 2.75x | 2.88x, 2.88x |
| Moderate | 6 | 3.20x, 3.26x | 3.41x, 3.31x |
| Moderate | 8 | 3.13x, 3.16x | 3.30x, 3.43x |
| Moderate | 12 | 3.16x, 3.07x | 3.31x, 3.41x |
| Heavy | 2 | 1.46x, 1.42x | 1.50x, 1.48x |
| Heavy | 4 | 2.78x, 2.83x | 2.94x, 2.86x |
| Heavy | 6 | 2.81x, 2.79x | 2.91x, 2.84x |
| Heavy | 8 | 2.72x, 2.78x | 2.91x, 2.83x |
| Heavy | 12 | 2.76x, 2.79x | 2.85x, 2.82x |

The 3.14 Light figure at 2 workers is low because that is the first
parallel cell of the run, and on 3.14 the first pool a process opens
costs an extra 40-120 ms ("The first pool on Python 3.14", below).
The same effect gave 1.11x in Phase 4.

The same sweep, `--proc`, 12 sample paths. Serial run, 3.14 (two
runs) / 3.10 (two runs): Light 0.49 s, 0.48 s / 0.58 s, 0.59 s;
Moderate 3.23 s, 3.24 s / 3.83 s, 3.90 s; Heavy 2.89 s, 2.91 s / 3.41
s, 3.51 s. The Light paths are half Phase 4's length (1.04 s serially
then), so fixed costs weigh more.

| Tier | Workers | Python 3.14 (two runs) | Python 3.10 (two runs) |
|---|---|---|---|
| Light | 2 | 1.88x, 1.83x | 1.95x, 1.93x |
| Light | 4 | 3.50x, 3.44x | 3.79x, 3.80x |
| Light | 6 | 3.95x, 4.48x | 4.68x, 4.57x |
| Light | 8 | 4.83x, 4.72x | 3.68x, 4.86x |
| Light | 12 | 4.24x, 3.82x | 5.47x, 5.56x |
| Moderate | 2 | 1.94x, 1.92x | 1.97x, 1.98x |
| Moderate | 4 | 3.80x, 3.80x | 3.83x, 3.83x |
| Moderate | 6 | 5.62x, 5.20x | 4.98x, 5.56x |
| Moderate | 8 | 5.38x, 5.40x | 5.45x, 5.64x |
| Moderate | 12 | 5.85x, 5.77x | 5.73x, 5.86x |
| Heavy | 2 | 1.95x, 1.95x | 1.98x, 1.99x |
| Heavy | 4 | 3.79x, 3.82x | 3.85x, 3.78x |
| Heavy | 6 | 5.68x, 5.54x | 5.72x, 5.65x |
| Heavy | 8 | 5.55x, 5.54x | 5.49x, 5.56x |
| Heavy | 12 | 5.85x, 5.81x | 5.81x, 5.91x |

The Light tier on 3.14 at 12 workers (4.24x, 3.82x) is well below
3.10's (5.47x, 5.56x). That is not explained. The first-pool cost is
paid once per process, and it lands on an earlier cell of the sweep.

### What a replication and a piece cost now

Serial cost per replication on 3.14, from the runs above: Light 0.48
ms, of which `g()` is 0.46 ms; Moderate 4.5 ms; Heavy 13.5 ms. In a
serial Light 2-D run the framework adds about 18 µs per replication,
and coordinate time is 2% of the run. At `30bfa68`, just before the
cheaper jump, it was 29% (0.63 s of 2.12 s).

**The per-piece overhead was measured directly**, not inferred from
the ratio. Every executor call of a serial Light run was recorded and
replayed in three ways:

- through a fresh `SerialExecutor` per worker, timing `streams()` on
  the pieces `split_blocks` makes, which is the worker-side jump;
- through the real `WorkerPool` with a task that returns a correctly
  shaped result and does no work, which is pipe and pickling;
- through the pool with a task that only turns coordinates into
  streams, which is the two together.

Python 3.14, HEAD against `30bfa68`. The jump rows are one replay;
the pool rows are medians of three, per tier and worker count:

| Cost | HEAD | `30bfa68` |
|---|---|---|
| Worker-side jump, per extra piece | 10-21 µs | 1,214-1,312 µs |
| Pipe and pickling, fixed per call | 34-39 µs | 36-40 µs |
| Pipe and pickling, per extra piece | 13-16 µs | 13-15 µs |
| Both, through the pool, per Light 2-D call (6 / 12 workers) | 154 / 181 µs | 1,862 / 2,543 µs |
| Opening a pool of 6 / 12 workers (warm process) | 5-6 / 9-10 ms | 6 / 10-11 ms |

The jump per piece at `30bfa68` is larger than the 0.7 ms this
document used for it earlier. Pipe and pickling did not change and are
small next to a 0.46 ms replication, so **the new floor that H2
predicted does not appear at this tier.** A piece now costs 25-35 µs
in all.

### The jump alone: `30bfa68` against `27961b8`

`27961b8` is the cheaper jump and nothing else, with bit-identical
output. The two were interleaved with HEAD in seven rounds, rotating
which ran first. Every cell is a fresh process: a warm-up serial run,
then one timed run. Python 3.14, medians, with the range over the
seven rounds.

| Light 2-D (RPERLE, budget 3,000) | `30bfa68` | `27961b8` | HEAD |
|---|---|---|---|
| Serial | 2.122 s | 1.507 s (-29%) | 1.444 s |
| 6 workers | 1.000 s, 2.12x [2.06-2.42] | 0.522 s (-48%), 2.89x [2.64-3.02] | 0.498 s, 2.90x [2.68-3.05] |
| 12 workers | 1.164 s, 1.82x [1.80-2.10] | 0.540 s (-54%), 2.79x [2.68-2.84] | 0.514 s, 2.81x [2.76-2.90] |

| Light 1-D (RSPLINE, budget 500, `x0 = (50,)`) | `30bfa68` | `27961b8` | HEAD |
|---|---|---|---|
| Serial | 0.368 s | 0.259 s (-30%) | 0.252 s |
| 6 workers | 1.38x [1.27-1.43] | 1.60x [1.49-1.69] | 1.57x [1.49-1.65] |
| 12 workers | 1.16x [1.07-1.21] | 1.45x [1.43-1.52] | 1.48x [1.43-1.49] |

Both numerator and denominator shrank, and the denominator shrank
more. The ratio did not move between `27961b8` and HEAD, despite
Phase 7's changes to the workload. These ratios are lower than the
sweep's because each cell is its process's first pool (next section).
The cost is the same in every column, so the comparison across
columns holds.

### The first pool on Python 3.14

Four `--simpar=6` runs of the Light 1-D tier in one process, after a
serial warm-up:

| Tree | First | Second | Third | Fourth |
|---|---|---|---|---|
| HEAD, Python 3.14 | 0.161 s | 0.120 s | 0.107 s | 0.121 s |
| `27961b8`, Python 3.14 | 0.214 s | 0.088 s | 0.099 s | 0.107 s |
| HEAD, Python 3.10 (fork) | 0.123 s | 0.107 s | 0.116 s | 0.103 s |

On 3.14, which starts workers through a fork server on Linux, the
first pool a process opens costs an extra 40-120 ms. On 3.10 under
fork the first run is at most 20 ms slower, within the spread of the
others. **A `pymoso solve --simpar` invocation is
one process and pays it once.** The sweeps above pay it in their first
parallel cell. It was measured on Linux only, with `solve()`;
`testsolve()`'s first pool was not measured separately.

### The 6-worker drop after the pool, settled

The question left open in Phase 3 and judged "most likely noise" at
the end of Phase 4 ("The Light tier at high worker counts", above) was
whether the pool made the Light 1-D tier slower at 6 workers. The
interleaved comparison it asked for, `c19dc9d` (the last commit before
the pool) against `6877979` (`--simpar` on the pool), Python 3.14:

| Light 1-D | `c19dc9d` | `6877979` |
|---|---|---|
| Fresh process (first pool), 6 workers, 7 rounds | 1.35x [1.30-1.36] | 1.21x [1.17-1.33] |
| Fresh process (first pool), 12 workers, 7 rounds | 1.30x [1.29-1.33] | 1.09x [1.08-1.16] |
| Warm process, 6 workers, 15 samples | 1.73x [1.59-1.81] | 1.59x [1.40-1.80] |
| Warm process, 12 workers, 15 samples | 1.64x [1.60-1.70] | 1.37x [1.20-1.48] |

**The drop was real: 8-10% at 6 workers.** In 6 of 7 fresh rounds the
pool fell below the old mechanism's minimum. The warm samples overlap,
nine of fifteen, which is why two runs could straddle the difference.
At 12 workers the ranges do not overlap at all. The cheaper jump more
than recovered both. On one unchanged workload, the pool went from
1.38x to 1.60x at 6 workers and from 1.16x to 1.45x at 12. `c19dc9d`
runs a different Light workload (507 calls against 545), so its
absolute times are not compared with the later trees.

### The 12-worker regression

On the Light 2-D tier it is gone: 12 workers beat 6 on both Pythons.
**On the Light 1-D tier on Python 3.14 it persists**: 2.05x and 2.08x
at 12 workers against 2.19x and 2.38x at 6, 6% and 13% slower, which
is 8 and 15 ms per run. Measured costs account for about 7 ms of that.
Opening twelve workers instead of six costs about 4 ms, and the extra
piece per call, at about 30 µs over 93 calls, about 3 ms. **The rest
is open.** Python 3.10 does not show it: 2.88x and 2.92x at 12 against
2.60x and 2.43x at 6. In `bench_simpar_ceiling.py`'s own 1-D Light
configuration (`x0 = (97,)`), 12 workers gave -7% and +3% against 6.

### The diagnostic, and why it is not a bound

`1/(s + (1 - s)/W)`, with `s` the sequential-by-necessity share,
treats those replications as strictly serial. They are not. Each
`ne()` or `spli()` call hands over one point, but that point's `m`
replications still split across workers. **Observed speedup exceeds
this formula in all 16 cells measured, by 1.4x to 2.4x.** It is
listed here because it was the stated diagnostic; the bound this
document uses ("Bound, batched") is the valid one.

| Workload | `s` | Workers | `1/(s + (1-s)/W)` | Bound, batched | Observed (3.14, two runs) | Observed / bound |
|---|---|---|---|---|---|---|
| Light 1-D | 0.571 | 6 | 1.56x | 4.32x | 2.27x, 2.03x | 53%, 47% |
| Light 1-D | 0.571 | 12 | 1.65x | 5.64x | 2.11x, 2.09x | 37%, 37% |
| Moderate 1-D | 0.601 | 6 | 1.50x | 3.67x | 3.24x, 3.13x | 88%, 85% |
| Heavy 1-D | 0.607 | 6 | 1.49x | 3.00x | 2.81x, 2.79x | 94%, 93% |
| Light 2-D | 0.550 | 6 | 1.60x | 4.98x | 3.17x, 3.12x | 64%, 63% |
| Light 2-D | 0.550 | 12 | 1.70x | 7.87x | 3.46x, 3.28x | 44%, 42% |
| Moderate 2-D | 0.506 | 6 | 1.70x | 4.42x | 3.74x, 3.57x | 85%, 81% |
| Moderate 2-D | 0.506 | 12 | 1.83x | 6.15x | 4.01x, 3.99x | 65%, 65% |
| Heavy 2-D | 0.480 | 6 | 1.76x | 4.15x | 3.77x, 3.55x | 91%, 86% |
| Heavy 2-D | 0.480 | 12 | 1.91x | 4.91x | 3.92x, 3.86x | 80%, 79% |

(The 1-D rows are `bench_simpar_ceiling.py`'s, `x0 = (97,)`, batched.
The six cells not shown, 2 and 4 workers and 12 for Moderate and Heavy
1-D, also exceed the formula.)

### What is not understood

- **About 0.4 ms per executor call in the Light 2-D tier is
  unaccounted for.** At 6 workers, the batched bound for the
  simulation work, plus the solver's own serial work, plus the dispatch
  cost measured above, predicts about 4.1-4.2x. Observed is 3.1x, and
  the difference over 279 calls is 0.37-0.41 ms each. Nothing here
  measures where it goes. **The ceiling for cheap simulations is not
  understood**, and the bound minus measured dispatch overstates what
  the Light tier gets.
- **The sequential share rose between `30bfa68` and HEAD, untraced.**
  This is the survey from "Where a solver submits several points"
  above, re-run with the same configuration in both trees (`x0 = (30,
  30)` for ProbTPA and ProbTPB, `(0, 0, 0)` for ProbTPC; seed
  `(12345,)*6`; no `--crn`):

  | Run | `30bfa68` | HEAD |
  |---|---|---|
  | RPERLE, ProbTPA, budget 1,000 | 35.3% | 50.6% |
  | RPERLE, ProbTPA, budget 10,000 | 38.6% | 51.3% |
  | RPERLE, ProbTPB, budget 10,000 | 42.5% | 46.8% |
  | RPERLE, ProbTPC, budget 3,000 | 41.2% | 48.6% |
  | RMINRLE, ProbTPA, budget 1,000 / 10,000 | 38.1% / 45.6% | 43.8% / 46.3% |
  | RPE, ProbTPA, budget 1,000 / 10,000 | 44.8% / 41.1% | 49.4% / 52.8% |

  `30bfa68` reproduces Phase 3's figures in seven of eight runs. The
  eighth, ProbTPC, used a different `x0` here (Phase 3 recorded
  34.8%). So **the range is now 44-53%, not 35-46%.** The commits in
  between include Phase 7's algorithm fixes. An untested hypothesis:
  SPLI going to the nearest integer point (audit finding 4) and
  stopping at an infeasible point (finding 5) change the line search's
  call pattern directly. That has not been bisected and is not
  established as the cause.
- **The Light 1-D 12-worker gap on Python 3.14**, of which measured
  costs explain about 7 ms of 8-15 ms ("The 12-worker regression",
  above).
- **The 3.14 Light `--proc` figure at 12 workers** (3.82x and 4.24x
  against 5.47x and 5.56x on 3.10).

### The piece cap, with the new data

It is still not supported. A piece costs at most about 35 µs against a 0.46
ms replication, so a cap that admits a piece only when its work
outweighs its overhead would cap nothing. The three reasons it was
declined, answered with this data:

1. *It could not fix 6 workers.* That drop was real, and the cheaper
   jump has already recovered it.
2. *It would only partly fix 12.* The Light 2-D tier now gains from 12
   workers. The one remaining 12-worker loss, Light 1-D on 3.14, is
   mostly not per-piece cost: about 3 ms of 8-15 ms.
3. *It makes dispatch depend on timings.* That is unchanged.

## What would raise the ceiling now

- **Speculative prefetch of the sequential part**
  (`docs/rng-interface-design.md` §11 entry 15): idle workers simulate
  what `ne()` or the line search will ask for next. It is the only
  thing that can move the bound, and it was declined for Phase 3
  because something outside the solver would have to know the solver's
  next move. Start by measuring how often the obvious guesses are
  right.
- **A cheaper jump** (§11 entry 14), for cheap simulations only. Now
  the one candidate with a measurement behind it: a piece cap was
  tried instead and declined (above), because the per-piece overhead
  is the jump and only a cheaper jump reduces it. [Landed in Phase 7 step 3 (2026-10-17): a general MRG jump is now 20-70 µs on 3.14 (`docs/hit-cost-baseline.md`, "After the cheaper jump"). Measured on 2026-11-23: it raised the Light tiers' speedup at 6 and 12 workers ("After the cheaper jump (Phase 7 step 3)", above).]
- **Converting the two example solvers to `hit_many`.** Both evaluate
  long unconditional lists of points and would batch far better than
  the RA solvers. Not measured.
- **Running a solver's independent searches concurrently** -- the
  per-objective `spline()` calls in `get_min`, the per-epsilon chains
  in `pe`. They do not depend on one another's results, only on a
  shared cache. This needs solver logic restructured as concurrent
  tasks, and is not measured.
- More physical cores, for the Moderate and Heavy tiers: at 12 workers
  on 6 cores the observed speedup stops following the bound.
