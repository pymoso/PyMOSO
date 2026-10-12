# What bounds `--simpar`

**Read this with `docs/parallel-dispatch-baseline.md`. It corrects the
conclusion that file invites.** That baseline shows `--simpar` topping
out near 2.5-3x on a 6-core machine and describes dispatch as
"unbatched: one job per replication", which reads as though per-job
dispatch overhead is the ceiling. It is not. Measured here, the ceiling
has two causes, and dispatch overhead is neither:

1. **Parallelism is confined to one `hit()` call.** A solver calls
   `hit(x, m)` for one point at a time and waits for it. Only that
   call's `m` replications can run concurrently, and `m` is small.
2. **Each `hit()` pays a serial coordinate jump in the parent**
   (`stream_at`, ~1.5-2 ms; `docs/hit-cost-baseline.md`). This matters
   only when a replication is cheap.

Consequence for the executor work: the justification for the next
phase is **batching across `hit()` calls** -- submitting several points
at once -- not reducing per-job dispatch cost.

Absolute timings, not enforced by the test suite. Regenerate with
`python docs/bench_simpar_ceiling.py`, which
`tests/test_benchmark_scripts.py` keeps runnable (a smoke test on a
trivial workload; it asserts no timings). Measured 2026-10-12 on an AMD
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

- **Cross-hit batching.** Since the RNG redesign, a replication's
  stream depends only on its coordinate, not on the order points are
  visited in, so replications for different points can be submitted
  together without changing any result. The executor interface takes a
  list of blocks for this reason. What is missing is a caller that
  submits more than one point at a time -- a solver-side change.
- **Moving the jump out of the parent.** If a backend computes the
  stream from `(root, stream, offset)` in the worker, the ~1.5 ms per
  `hit()` parallelises with the simulation. This is the Light tier's
  37%.
- **A cheaper jump.** Precomputed matrix powers would shorten
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
