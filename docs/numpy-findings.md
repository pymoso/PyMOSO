# numpy: measured, and not adopted

**Result, not a deferral.** Phase 4 was to consider vectorized
numerics now that `hit_many` produces batches. The profile says numpy
cannot touch what dominates, would change results where it could be
applied, and is unnecessary where the cost matters. The `numerics`
extra stays empty. Do not re-propose numpy for the framework's own
arithmetic without new data that contradicts a table below.

Measured 2026-10-12, AMD Ryzen 5 5600X3D, Python 3.14 (3.10 gives the
same shares within a point or two), numpy 2.5.4, serial RPERLE, after
Phase 3's batching.

## Where the time goes

Share of wall time in a serial run. "Coordinate to stream" is
`SerialExecutor.streams`: turning a block's `(root, stream, offset)`
into stream objects.

| Workload | Generator | Coordinate to stream | `g()` | Aggregate | Solver and other |
|---|---|---|---|---|---|
| ProbTPA, budget 10,000 | MRG32k3a | **78%** | 12% | 4% | 5% |
| ProbTPC (3-D), budget 3,000 | MRG32k3a | **86%** | 7% | 3% | 4% |
| ProbTPA, `--crn` | MRG32k3a | 32% | 37% | 15% | 15% |
| ProbTPC, `--crn` | MRG32k3a | 28% | 35% | 16% | 21% |
| ExpensiveBi Light (0.46 ms/rep) | MRG32k3a | 29% | 67% | 1% | 2% |
| ExpensiveBi Moderate (4.4 ms/rep) | MRG32k3a | 6% | 93% | 0.2% | 0.5% |
| ProbTPA | Philox | 5% | 46% | 23% | 25% |
| ProbTPC | Philox | 5% | 41% | 29% | 23% |
| ExpensiveBi Light | Philox | 0.3% | 96% | 2% | 2% |

MRG31k3p matches MRG32k3a throughout.

So the earlier statement — the jump dominates only for cheap
simulations — still holds after batching, and more starkly: for a
cheap problem on the default generator, 78-86% of a serial run is the
jump.

## Why numpy does not help

**The jump (78-86%).** It is the modular power of a 3x3 matrix, with
moduli just under 2^32 (`mrg_common.mat_pow_mod`; cProfile puts
essentially all of the time in `mat333sqmult_mod`). A product of two
residues needs 64 bits and a row sum of three needs 66. numpy's
integer arrays cannot do that exactly; object arrays can, and are
slower than the Python integers already in use. numpy has nothing to
offer the dominant term.

What does: a cheaper jump from precomputed powers
(`docs/rng-interface-design.md` §11 entry 14), which is pure-Python
work and out of Phase 4's scope. [Landed in Phase 7 step 3 (2026-10-17): a general MRG jump is now 20-70 µs on 3.14 (`docs/hit-cost-baseline.md`, "After the cheaper jump"); cheap serial runs
5.8-6.9x faster. The figures in this document are the code before it.]

**Philox already removes the cost.** Its position is a counter, so
`stream_at` costs 1.1 µs against 1.6 ms for the MRG family, and the
ProbTPA run above takes 0.26 s against 1.40 s. A user whose simulation
is cheap enough for the jump to matter can pass
`generator='philox4x32'` today.

**Aggregation (1-4%; 15-29% only where a run is already fast).**
`Oracle._aggregate` uses `statistics.mean` and `statistics.variance`.

| Sample size | `statistics` | numpy, from a list | Plain float loop | numpy result differs from `statistics` |
|---|---|---|---|---|
| 4 | 15.9 µs | 9.0 µs | 0.7 µs | in 56% of 2,000 samples |
| 8 | 18.9 µs | 8.9 µs | 0.9 µs | 54% |
| 16 | 33.3 µs | 9.0 µs | 1.4 µs | 57% |
| 64 | 78.1 µs | 9.9 µs | 4.8 µs | 58% |
| 1,000 | 783 µs | 31 µs | 69 µs | 60% |

Two things. `statistics` sums exactly and rounds once; numpy sums
floats pairwise. The results differ in the last bits more often than
not, so switching would **change solution values** — a deliberate,
golden-relevant change, for a term that is a few percent of a run.
And at the sample sizes RA solvers use (4 to 16), numpy's fixed
overhead makes it ten times *slower* than a plain float loop, which
would move the same bits for less. Neither is worth it.

**Solver logic.** 5% or less wherever a run is slow enough to matter.

## The one place numpy would pay

Bulk variate draws inside a user's `g()`.

| | Per draw |
|---|---|
| MRG32k3a / MRG31k3p `random()` | 4.3 µs |
| Philox-4x32 `random()` | 1.6 µs |
| numpy `Generator.random(100000)` | 0.003 µs |

A simulation that draws thousands of variates per replication spends
its time in those draws, and a vectorized draw is three orders of
magnitude cheaper. No built-in problem draws more than a handful.
Philox is the natural target: counter-based, 32-bit integer
arithmetic that numpy does exactly, so a bulk draw could be made
bit-identical to the scalar one.

Recorded as a candidate (`docs/rng-interface-design.md` §11 entry 16).
It would be an addition to the stream interface behind the `numerics`
extra, it would need a conformance test that bulk equals scalar, and
it should start from a user's simulation that actually needs it.
