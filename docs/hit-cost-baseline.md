# hit() cost baseline

Before-picture for the executor rework, alongside
`docs/parallel-dispatch-baseline.md`. That file times whole
`--simpar`/`--proc` runs; this one times a single `Oracle.hit()` call in
one process, with a `g()` that draws one value and does nothing else, so
what remains is the framework's own cost of reaching a coordinate.

Absolute timings, not enforced by the test suite. Regenerate with
`python docs/bench_hit_cost.py`. **Regenerating is a manual step and
nothing verifies the script still runs**: no test imports or executes
it, so an API change can break it silently. That has already happened
once -- removing `Oracle.crn_advance()` broke it, and it was noticed
only because the next timing run failed. It is in the same category as
`scratch/` and `docs/bench_parallel_dispatch.py`: run it before
trusting it, and expect to repair it. Measured 2026-10-12 on an AMD Ryzen 5
5600X3D (6 cores, 12 threads), MRG32k3a, before §12 step 9 (CRN-branch
convergence) of `docs/rng-interface-design.md`.

| operation | Python 3.10.22 (µs) | Python 3.14.8 (µs) |
|---|---|---|
| `stream_at(root, stream, 0)` | 1,992 | 1,559 |
| `stream_at(root, stream, point offset)` | 2,060 | 1,624 |
| `Stream.advance(REPL_STRIDE)` | 13 | 7 |
| `Stream.advance(REPL_RESERVE_STRIDE)` | 13 | 7 |
| `hit(x, m=1)`, `crn=True` | 24 | 19 |
| `hit(x, m=8)`, `crn=True` | 206 | 157 |
| `hit(x, m=64)`, `crn=True` | 1,378 | 1,090 |
| `hit(x, m=1)`, `crn=False` | 2,173 | 1,647 |
| `hit(x, m=8)`, `crn=False` | 2,353 | 1,790 |
| `hit(x, m=64)`, `crn=False` | 3,485 | 2,505 |

## What the numbers say

**The default path pays about 1.5-2 ms per `hit()` call before any
simulation runs, and almost all of it is one `stream_at` call.**
`crn=False` is the default on every run. Each `hit()` computes its
block's starting coordinate from the Oracle's root with a general
jump-ahead: a binary exponentiation over a 3x3 matrix pair, at an
exponent well over 100 bits. That is `stream_at`'s whole cost, and it is
the same whether the offset is zero or a full point code. Everything
after it is cheap: each further replication is one cached-matrix
`advance()` (7-13 µs) plus `g()` and the statistics, about 15-20 µs per
replication in total.

**The cost is per call, not per replication.** `hit(x, 64)` costs about
1.5x `hit(x, 1)`. A solver that takes many small `hit()` calls pays the
fixed cost each time; one that takes few large ones barely notices it.

**The CRN path does not pay it.** It keeps the current iteration's
baseline seed and only ever takes cached jumps from it, so `hit(x, 1)`
is ~20 µs -- roughly 80x cheaper per call than the default path. This is
why §12 step 9 keeps a cached per-iteration baseline when it converges
the CRN branch onto `_hit_via_coordinate` (see that step's own entry):
routing CRN through a fresh `stream_at` per call would hand it the
default path's cost.

## Relevance to `--simpar` and to the executor design

This cost is serial. Under `--simpar` the parent process computes every
replication's seed itself and queues only `(x, seed)` to the workers, so
the `stream_at` call sits in the part of each `hit()` that no worker
count can shorten. `docs/parallel-dispatch-baseline.md` records
`--simpar` topping out at roughly 2.5-3x on this machine.

How much of that ceiling this accounts for is **not measured here**. It
depends on the ratio of this fixed cost to the simulation work in a
typical `hit()` call for the benchmark problems (replication cost times
replications per call), and those runs were not profiled. It is a
candidate explanation alongside per-job dispatch overhead, and the two
should be separated by profiling before the batching design assumes
either.

What is established: any design that batches replications across
`hit()` calls, or that reaches a point's coordinate more cheaply than a
full jump from the root (for example, one jump to the iteration's
baseline, cached, then a shorter jump by the offset alone), has up to
~1.5 ms per `hit()` call available to recover on the default path.

## After the executor interface (Phase 2)

`Oracle.hit()` now describes its work as a `ReplicationBlock` and a
`SerialExecutor` runs it (`pymoso/executor.py`). Same script, same
machine, same day:

| operation | Python 3.10.22 (µs) | Python 3.14.8 (µs) |
|---|---|---|
| `hit(x, m=1)`, `crn=True` | 34 | 19 |
| `hit(x, m=8)`, `crn=True` | 219 | 138 |
| `hit(x, m=64)`, `crn=True` | 1,389 | 889 |
| `hit(x, m=1)`, `crn=False` | 1,029 | 744 |
| `hit(x, m=8)`, `crn=False` | 1,210 | 864 |
| `hit(x, m=64)`, `crn=False` | 2,365 | 1,614 |

**CRN is unchanged**, as intended: the per-iteration cache moved from
`Oracle` into the executor (one cached base stream per
`(root, stream)`).

**The default path roughly halved in this benchmark, and that was not
a goal of the phase.** It is a side effect of where the cache now
sits. Before, a default-branch `hit()` made one jump from the root
straight to its coordinate -- an exponent of about 130 bits
(`stream*2**127 + offset`). Now the executor reaches every coordinate
in two steps: the stream's base, cached, then `advance(offset)`. The
per-call jump is therefore by the offset alone, and binary
exponentiation costs in proportion to the exponent's bit length. The
benchmark's point `(3,)` in one dimension has a ~55-bit offset. The
saving is point-dependent: a two-dimensional ProbTPA point has a
~96-bit offset and saves about a quarter; a point whose code fills the
field saves almost nothing. Every stream reached is bit-identical to
before (the jump composition law), and no golden moved.

This is not the "cheaper general jump" carried as a Phase 3 candidate
(docs/rng-interface-design.md §11, entry 14) -- that one would shorten
the exponentiation itself -- but it does reduce what that candidate
has left to gain on small points.
