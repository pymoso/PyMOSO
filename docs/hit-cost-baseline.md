# hit() cost baseline

Before-picture for the executor rework, alongside
`docs/parallel-dispatch-baseline.md`. That file times whole
`--simpar`/`--proc` runs; this one times a single `Oracle.hit()` call in
one process, with a `g()` that draws one value and does nothing else, so
what remains is the framework's own cost of reaching a coordinate.

Absolute timings, not enforced by the test suite. Regenerate with
`python docs/bench_hit_cost.py`. Regenerating is a manual step, but
the script is kept runnable: `tests/test_benchmark_scripts.py` imports
it and runs it on a trivial workload (asserting only that it
completes, never a time). That test exists because removing
`Oracle.crn_advance()` once broke this script unnoticed, and
`docs/bench_parallel_dispatch.py` had been broken for longer still.
Measured 2026-10-12 on an AMD Ryzen 5
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

**"Default `hit()` halved" is a statement about this benchmark's
point, not a general result.** The saving scales with the bit length of
the coordinate's offset, and the benchmark's point happens to have a
short one. It was also not a goal of the phase; it is a side effect of
where the cache now sits.

Before, a default-branch `hit()` made one jump from the root straight
to its coordinate: an exponent of about 130 bits
(`stream*2**127 + offset`). Now the executor reaches every coordinate
in two steps -- the stream's base, cached, then `advance(offset)` --
so the per-call jump is by the offset alone. Binary exponentiation
costs in proportion to the exponent's bit length, so the per-call cost
went from "about 130 bits" to "however many bits the offset has".

| Point | Offset bit length | Per-call jump vs before | Status |
|---|---|---|---|
| `(3,)`, dim 1 (this benchmark) | about 55 | about half | **measured** (the table above) |
| a ProbTPA point such as `(40, 40)`, dim 2 | about 96 | about three quarters | *estimate from bit length, not measured* |
| a point whose code fills the 75-bit field | about 127 | essentially unchanged | *estimate from bit length, not measured* |

The offset is the point's code shifted above the visit and replication
fields (52 bits for the MRG family), so its length is roughly
`52 + (bits of the point code)`: small points in few dimensions are
cheap, and the cost rises toward the old figure as the code grows. A
hashed point (one too large for the exact code) always fills the
field. Anyone quoting a speedup for a particular problem should
measure that problem.

Every stream reached is bit-identical to before (the jump composition
law), and no golden moved.

This is not the "cheaper general jump" carried as a Phase 3 candidate
(docs/rng-interface-design.md §11, entry 14) -- that one would shorten
the exponentiation itself -- but it does reduce what that candidate
has left to gain on small points.

## At the end of Phase 4 (refreshed 2026-10-13)

`python docs/bench_hit_cost.py`, twice on each Python, on the same
machine with nothing else running (load average under 0.1 at the
start). Both runs are shown. These are the figures to compare later
work against; the tables above are the history of how they got here.
(Superseded for the MRG family's jumps and default-branch `hit()` by
"After the cheaper jump (Phase 7 step 3)", below.)

| operation | Python 3.10.22 (µs), two runs | Python 3.14.8 (µs), two runs |
|---|---|---|
| `stream_at(root, stream, 0)` | 2,024, 2,007 | 1,569, 1,558 |
| `stream_at(root, stream, point offset)` | 2,103, 2,089 | 1,632, 1,621 |
| `Stream.advance(REPL_STRIDE)` | 13, 13 | 7, 7 |
| `Stream.advance(REPL_RESERVE_STRIDE)` | 13, 13 | 7, 7 |
| `hit(x, m=1), crn=True` | 36, 35 | 19, 19 |
| `hit(x, m=8), crn=True` | 217, 221 | 137, 137 |
| `hit(x, m=64), crn=True` | 1,374, 1,383 | 878, 888 |
| `hit(x, m=1), crn=False` | 995, 971 | 743, 746 |
| `hit(x, m=8), crn=False` | 1,180, 1,162 | 862, 868 |
| `hit(x, m=64), crn=False` | 2,333, 2,318 | 1,594, 1,623 |

Unchanged from Phase 3 within the spread of two runs: a serial `hit()`
costs what it did before the backend seam, the by-value transport and
the direct `get_nbors`, none of which is on this path.


## After the cheaper jump (Phase 7 step 3, 2026-10-17)

The MRG family's general jump now applies one cached power A^(2^k)
per set bit of the exponent to the seed (`mrg_common.PowerTable`),
instead of squaring its way up the exponent's whole bit length on every
call. This is rng-interface-design.md §11 entry 14. **These are the
figures to compare later work against.**

**The profile that chose it** (measured, Python 3.14.8,
`scratch/phase7/jump_profile.py`; raw output `jump_parts.json` and
`jump_runs.jsonl` beside it). A general jump was 2 x (bit length + set
bits) 3x3 matrix products mod m, and those products were 95-97% of it
(the count times the unit cost reproduces the measured jump within
2-5%). The squarings, which depend only on the exponent's bit length,
were 76-95%; the multiplies 1-20%. Real exponents are long and sparse:
in eight real runs the median general exponent had 60-119 bits and 3-9
set, with about 52 trailing zeros (the point code sits above the visit,
replication and reserve fields). Within one 3x3 product, 69% was
interpreter overhead (`int()` casts, a generator, list building) and
31% the arithmetic itself. MRG31k3p measured the same as MRG32k3a,
within 6% everywhere: its sparse multipliers appear only in the
one-step matrix, A^(2^k) has full-size entries, and both moduli give
products below 2^64. The cost was the number of products, not either
generator's arithmetic.

**Before and after**, `python docs/bench_hit_cost.py mrg32k3a` and
`... mrg31k3p` (the generator argument and the 75-bit row were added in
this step), each run on the old and new code alternately, twice, both
Pythons. One-minute load was 1.37-1.42 throughout, not the 0.1 of the
Phase 4 refresh, from a source outside this work that did not go away;
the "before" figures agree with the Phase 4 refresh within 2-3%
(1,601-1,603 against 1,558-1,569 for `stream_at(root, stream, 0)` on
3.14), which bounds what the load added. Microseconds per call, both
runs shown.

MRG32k3a:

| operation | 3.10 before | 3.10 after | 3.14 before | 3.14 after |
|---|---|---|---|---|
| `stream_at(root, stream, 0)` | 2,096, 2,031 | 30, 30 | 1,603, 1,601 | 21, 21 |
| `stream_at(root, stream, point offset)` | 2,154, 2,126 | 39, 40 | 1,675, 1,675 | 29, 29 |
| `stream_at(root, stream, 75-bit point offset)` | 2,579, 2,555 | 84, 84 | 1,998, 1,993 | 66, 67 |
| `Stream.advance(REPL_STRIDE)` | 14, 14 | 13, 14 | 8, 8 | 7, 7 |
| `Stream.advance(REPL_RESERVE_STRIDE)` | 14, 13 | 13, 14 | 7, 7 | 7, 7 |
| `hit(x, m=1), crn=True` | 37, 37 | 22, 22 | 21, 21 | 13, 13 |
| `hit(x, m=8), crn=True` | 224, 227 | 214, 213 | 146, 143 | 137, 135 |
| `hit(x, m=64), crn=True` | 1,435, 1,426 | 1,401, 1,413 | 923, 915 | 912, 915 |
| `hit(x, m=1), crn=False` | 1,019, 1,033 | 46, 46 | 760, 756 | 31, 31 |
| `hit(x, m=8), crn=False` | 1,205, 1,212 | 235, 236 | 884, 883 | 154, 155 |
| `hit(x, m=64), crn=False` | 2,389, 2,395 | 1,411, 1,413 | 1,639, 1,689 | 919, 914 |

MRG31k3p (not measured here before this step):

| operation | 3.10 before | 3.10 after | 3.14 before | 3.14 after |
|---|---|---|---|---|
| `stream_at(root, stream, 0)` | 1,994, 1,985 | 30, 31 | 1,527, 1,530 | 21, 21 |
| `stream_at(root, stream, point offset)` | 2,103, 2,069 | 39, 39 | 1,592, 1,594 | 28, 28 |
| `stream_at(root, stream, 75-bit point offset)` | 2,509, 2,452 | 79, 83 | 1,900, 1,906 | 65, 63 |
| `Stream.advance(REPL_STRIDE)` | 13, 13 | 13, 13 | 7, 7 | 7, 7 |
| `Stream.advance(REPL_RESERVE_STRIDE)` | 14, 13 | 13, 13 | 7, 7 | 7, 7 |
| `hit(x, m=1), crn=True` | 36, 37 | 21, 28 | 20, 21 | 13, 13 |
| `hit(x, m=8), crn=True` | 217, 217 | 204, 203 | 137, 138 | 129, 129 |
| `hit(x, m=64), crn=True` | 1,394, 1,384 | 1,362, 1,359 | 904, 893 | 877, 882 |
| `hit(x, m=1), crn=False` | 969, 975 | 44, 44 | 726, 724 | 31, 32 |
| `hit(x, m=8), crn=False` | 1,160, 1,186 | 232, 231 | 852, 847 | 154, 158 |
| `hit(x, m=64), crn=False` | 2,310, 2,325 | 1,382, 1,379 | 1,599, 1,599 | 903, 915 |

A general jump is 29-76x cheaper (the longest offsets gain least: cost
now follows set bits), and a default-branch `hit(x, m=1)` 22-25x. The
replication advance (`REPL_STRIDE`, `REPL_RESERVE_STRIDE`) took the
cached-matrix path before and still does, so it did not change; nor
does a CRN `hit()` with many replications, which is made of those.

**Whole runs** (measured, uninstrumented, 3.14,
`scratch/phase7/jump_runs_plain.py`, old and new alternately, twice;
load about 1.1-1.4): RSPLINE on ProbSimpleSO 5.8-6.0x faster, RPERLE
on ProbTPA 6.5-6.9x, RMINRLE on ProbTPC 6.6-6.8x, RSPLINE on BSProb
(dim 9, a costlier `g()`) 1.1x, on both generators; every run's
solution, simulations and end seed identical before and after. The
profile's estimate had been "roughly 5-6x" for the cheap runs.

**What a process pays to build the tables** (measured,
`scratch/phase7/jump_first_call.py`, the median of 15 fresh
interpreters each). The tables are built on first use, not at import,
and extended when a longer exponent arrives, so the first general jump
at a new bit length pays the squarings up to it. In a fresh process
the first `stream_at(root, 20, 0)` (132 bits) costs 1,654-1,763 µs on
3.14 and 2,152-2,227 µs on 3.10 -- about what every general jump cost
before -- and the next one 30-38 µs; a later, shorter exponent pays
nothing extra (a 75-bit offset's first advance 75-88 µs against 67-83
µs). Under `fork` a worker inherits whatever table its parent had
built; under `forkserver` and `spawn` it starts with an empty one and
pays that once (measured: the table length a worker starts with, each
start method, both Pythons). `WorkerPool` workers live for the whole
run, so it is once per worker per run.

**End seeds.** The end seed is computed with `stream_at`, which reaches
the same `jump_seed_n`, so with a jump that returns the same tuple for
every exponent it cannot move: settled by construction, from
bit-identity, not from a general claim that the streams are unchanged.
Bit-identity is tested per exponent against the previous code
(`tests/test_jump_power_table.py`, thousands of exponents per
generator, every bit position up to 259); confirmed three ways besides:
the goldens, which pin end seeds; the 39 counted runs, which record
them (`scratch/phase7/step3_after_jump.jsonl`, 39 of 39 identical to
the record after step 2c); and a test comparing `solve()`'s end seed
under the old and new jump, seen failing on a wrong jump of the stream
bits. Note what that last test can see: the end seed's own jump is
`(stream + 1) * 2^127` (Oracle.get_endseed, one_past), so it uses only
bits 127 and up; and no exponent a run makes sets bits 0-13 or, for a
non-negative point, bit 52 (zigzag codes are even). Mutations confined
to those bits leave every whole run unchanged. The per-exponent
comparison is the test of every bit.

**What is left on this path.** A default-branch `hit(x, m)` is now one
general jump (20-70 µs) plus m - 1 replication advances at ~7 µs each,
of which about 3 µs is the cached-matrix arithmetic and 3.9 µs
constructing the `Stream` (`jump_parts.json`: `cached_jump_us`,
`construct_stream_us`). At m = 8 the advances are already the larger
part. That reframes what to look at next: Stream construction, not
arithmetic (docs/phase7-plan.md, step 3).
