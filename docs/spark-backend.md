# Running PyMOSO on Spark, and from a notebook

Phase 4 of the 2.0.0 work. This document is both the record of what
was measured and decided, and — until the README is rewritten — the
only user-facing description of the Spark backend and the `notebook`
extra.

Local measurements: 2026-10-12, AMD Ryzen 5 5600X3D (6 cores, 12
threads), Python 3.14 unless noted, pyspark 4.2.0, MRG32k3a. Mostly
single runs, on one machine — Spark's `local` and `local-cluster`
modes. Cluster measurements: three runs on Databricks, 2026-10-13,
in "On a real cluster" below, which is where the claims about
identity across machines and about break-even now rest.

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

**It is slower than plain `solve()` for cheap replications, and it
tops out at a few times faster however large the cluster is.** On
three Databricks clusters (below): at 20-30 ms per replication it
lost or broke even (0.4x to 1.0x); at 85-110 ms it won by 1.7x to
2.9x; at 0.4-0.5 s by 3.6x to 4.4x; at 1.5-1.7 s by 4x to 6x.
"Roughly 100 ms or more" remains the rule to give a user: below it
the outcome depended on the cluster.

The rest of this section is the local measurement that prediction
was first made from.

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

Two things say this to a user who did not read this page: the
`pymoso.backends.spark` module docstring, and the error `solve()`
raises for a remote backend without a `simpar`. Nothing says it
during a run. Whether a cluster pays for a particular simulation is
for the user to measure, on purpose:

```python
from pymoso import dispatch_cost
print(dispatch_cost(MyProblem, (30, 30), replications=8, parts=8, backend=backend))
```

runs one request of that size in place and as tasks on the backend,
and prints how long each took and whether the results were identical.
It measures wall time on both sides, so tasks crowding each other
count against the backend and not for it. It measures one request at
one point, costs several times the work it measures, and offers no
verdict; `pymoso/backends/measure.py` says what the numbers do and do
not mean. Called at a few replication costs it produces, for a user's
own problem and cluster, the kind of table the next section has.

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

## On a real cluster

Three runs on Azure Databricks, 2026-10-13, of
`docs/databricks/pymoso_dbx_notebook.py` -- one notebook that probes
the hardware, checks identity, sweeps sample paths and probes the
replication-level break-even, and prints one checksummed block.
Nothing could be exported from the cluster: each block was read off
the screen and typed by hand, then checked with
`docs/databricks/dbx_kit.py verify`. The three blocks are reproduced
at the end of this section and kept in `docs/databricks/results/`.

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Runtime | DBR 17.3, Spark 4.0.0 | DBR 16.4, Spark 3.5.2 | DBR 17.3, Spark 4.0.0 |
| Node type | Standard_D8s_v3 | Standard_D16s_v3 | Standard_D8s_v3 |
| Session | classic, `sparkContext` present | classic | classic |
| Executor hosts reached by the probe | 1 | 1 | 3 |
| Python worker processes reached | 8 | 16 | 24 |
| Python, libc | 3.12.3, glibc 2.39 | 3.12.3, glibc 2.39 | 3.12.3, glibc 2.39 |
| Driver CPU | Xeon Platinum 8171M | Xeon Platinum 8370C | Xeon E5-2673 v4 |
| Executor CPU | Xeon Platinum 8370C | Xeon Platinum 8370C | Xeon Platinum 8370C |
| cloudpickle on the runtime | 3.0.0 | 2.2.1 | 3.0.0 |
| Checks against local known-good values | 26 of 26 | 27 of 27 | 28 of 28 |

**Transcription.** Runs 2 and 3 verified as typed. Run 1's file had
four mistyped characters, all on environment lines (`kit =1`,
`Standard_DBx_v3`, `glibc=2.39`, `aff=B`); each was flagged by its
own line check. The corrected lines (`kit=1`, `Standard_D8s_v3`,
`glibc-2.39`, `aff=8`) reproduce their typed check codes and the
block's `SUM`, and no other candidate node name did. The text below
is the corrected, verified block. None of the four touched a hash or
a measurement.

> **Do not quote the `x` column of the `R` lines in the blocks
> below.** It is the time the tasks spent working divided by the wall
> time, both measured on the cluster. When tasks crowd each other
> each one takes longer, and `x` counts that slowdown as work done.
> At `simpar=32` it overstates the speedup by up to 1.6 times: it
> prints 9.55 and 9.80 where the wall times give 6.1 and 6.2. Use the
> table under "Replications inside one `solve()`", which does not have
> the problem. The `x` in the `S` lines is a different quantity
> (measured against one path running alone) and is sound.

### Corrections to how these results were first read

Two readings of these blocks were made, acted on, and then withdrawn.
They are recorded because both were natural readings, and the next
reader will be tempted by the same ones.

1. **"A 1.7 s replication nearly saturates its bound: 9.55x against
   10.04."** This was the maintainer's summary of run 3's last row,
   given as an instruction for what this document should say. It took
   the block's `x` at face value. The wall time gives 6.1x. The fault
   is the measure, not the reader: the notebook printed a column
   labelled `x` next to one labelled `bound` without saying that `x`
   was work over wall time, and the person who commissioned the
   measurement was misled by it within a day. The kit's design is
   what should have prevented that, and did not.
2. **"Bit-identity across two CPU generations, hosts=3."** True, but
   not of the executors, which is how it was first put. Within every
   run all executors were one CPU model (`cpus=1`). The two
   generations are the driver against the executors. That is still a
   real cross-machine comparison -- the driver computes the same
   probe and the same whole runs -- and the comparison with the
   machine the known-good values came from adds a third CPU family, a
   second glibc and a second Python. But "executors of different
   hardware agreed with each other" is not something these runs show.

A third reading needed no correction but is easy to make: `hosts=`
describes the moment of the probe, not the timings after it (below).

### What the runs establish

- **Bit-identity across machines.** This was the open correctness
  question: variates go through the platform's maths library, and
  until these runs everything had been computed on one host. In every
  run, every probe task on every executor produced the same floats
  (`hashes=1 of=128`, for pymoso's own generators and for the maths
  library function by function), identical to the driver's and to
  the values computed beforehand on an AMD Ryzen with glibc 2.41 and
  Python 3.14. Six whole runs through `SparkBackend` -- sample paths,
  a built-in tester, replications with and without CRN, Philox, and a
  problem that uses the maths library -- matched the same run on the
  driver and the local values. So did every sweep line (up to 64
  paths, 33,621 simulations) and every replication-level run.

  Precisely what was different between the machines that agreed:
  driver and executors were different CPU generations in runs 1 and 3
  (Skylake-generation 8171M and Broadwell E5-2673 v4 against Ice Lake
  8370C); run 3 spread tasks over three executor hosts; and the
  cluster as a whole (Intel, glibc 2.39, Python 3.12) differs from
  the machine the known-good values came from (AMD, glibc 2.41,
  Python 3.14). What was *not* different: within each run every
  executor was the same CPU model (`cpus=1`), and everything was
  x86-64 Linux with glibc.
- **Spark 3.5.2 as well as 4.0.0,** on a real runtime.
- **The version check** raised `VersionMismatch`, by name, from an
  executor.
- **The installed tree was the expected one** on the driver and on
  every executor (`tree_ok=PASS`), so the comparisons above are
  between the same code.
- **By-value transport on a real runtime's own cloudpickle** (2.2.1
  and 3.0.0): the notebook's problem, tester and solver classes are
  all defined in the notebook.

### Two cautions that apply to every timing below

**The clusters autoscaled, and the control to turn that off was
greyed out.** In run 3 the worker count was seen to drift down toward
one during the sweep and to be back at three by the 500,000-unit
replication rows; a warm-up job had been used to bring the nodes up
beforehand. So run 3's sweep understates what a stable three-node
cluster would do, and its replication rows were not all measured on
the same number of workers. **Read run 3's scaling numbers as a lower
bound, not as a scaling measurement.**

**The notebook counted hosts once, at the start.** The `hosts=` and
`workers=` in each block are what the probe reached before any timing
began. Nothing later in a block says how many workers existed at that
moment. That is a limitation of the kit, and with autoscaling on it
applies to all three runs: runs 1 and 2 were single-host at the probe
although the UI reported more nodes, and nothing in the blocks rules
out nodes having joined afterwards. (`E2 workers=1` is a
configuration tag and read 1 even in run 3; it should be ignored.)
Run 3 is the only run in which more than one executor host was
observed at all.

Timings are single runs.

### Sample paths

`x` is the speedup over running the same paths one after another on
an idle executor (`n` times the time one path took alone, over the
job's wall time).

| Paths | Run 1 (8 vCPU): wall, per path, x | Run 2 (16 vCPU) | Run 3 (3 hosts, 24 vCPU, autoscaling) |
|---|---|---|---|
| 1 | 9.0 s, 8.72 s, 1.0 | 8.5 s, 8.42 s, 1.0 | 9.0 s, 8.71 s, 1.0 |
| 2 | 8.9 s, 8.54 s, 2.0 | 8.5 s, 8.25 s, 2.0 | 8.7 s, 8.37 s, 2.0 |
| 4 | 11.0 s, 9.11 s, 3.2 | 10.6 s, 8.70 s, 3.2 | 11.3 s, 9.05 s, 3.1 |
| 8 | 22.2 s, 19.71 s, 3.1 | 11.1 s, 9.11 s, 6.0 | 11.3 s, 9.23 s, 6.1 |
| 16 | 41.5 s, 19.42 s, 3.4 | 21.8 s, 19.15 s, 6.2 | 15.8 s, 11.81 s, 8.8 |
| 32 | | 41.3 s, 18.91 s, 6.5 | 30.0 s, 17.32 s, 9.3 |
| 64 | | | 56.6 s, 18.39 s, 9.8 |

- **It scales with the number of paths until the hardware runs out,
  as independent tasks should.** There is no call-pattern bound here
  to compare with: the batched bounds in `docs/simpar-ceiling.md` are
  about replications inside one `solve()` and correspond to the
  `bound` column of the next table, not to this one.
- **The plateau is at about 0.4 of the vCPU count:** 3.4x on 8, 6.5x
  on 16, 9.8x on 24 (the last a lower bound). The reason is visible
  in the per-path time, which doubles the moment concurrent paths
  exceed half the vCPUs -- 9.1 s to 19.7 s between 4 and 8 paths in
  run 1, 9.1 s to 19.2 s between 8 and 16 in run 2. That is what two
  hardware threads sharing a core look like for a CPU-bound task. (An
  inference from the timings; the instance type's threading was not
  checked.) A vCPU count is not a core count for this workload.
- **One path costs 8.4-9.0 s there and 2.65 s on the laptop the kit
  was built on.** Per replication the cluster's cores were about
  three times slower for this pure-Python work, which is why the
  cost tiers below came out at 20 ms to 1.7 s where the local run of
  the same notebook had 7 ms to 0.5 s.

### Replications inside one `solve()`

Each tier at `simpar` 6 and 32. "Cost" is the measured time of one
replication at `simpar=6`. The speedup columns divide the work --
simulations actually run times that cost -- by the wall time of the
run's Spark jobs.

| Tier | Simulations run (budget asked) | Spark jobs | Run 1: cost, x at 6, x at 32 | Run 2 | Run 3 |
|---|---|---|---|---|---|
| 20,000 | 1,182 (1,000) | 190 | 28 ms, 0.74, 0.76 | 20 ms, 0.97, 0.98 | 21 ms, 0.47, 0.42 |
| 100,000 | 468 (300) | 50 | 112 ms, 2.59, 2.35 | 83 ms, 2.87, 2.93 | 84 ms, 1.78, 1.68 |
| 500,000 | 468 (300) | 50 | 538 ms, 3.94, 3.67 | 390 ms, 4.08, 4.41 | 548 ms, 3.68, 3.63 |
| 2,000,000 | 231 (100) | 20 | 1.60 s, 3.97, 6.20 | 1.54 s, 4.74, 5.32 | 1.71 s, 4.18, 6.12 |

Bounds allowed by the solver's call pattern, from the blocks: 4.15,
4.63, 4.63 and 4.91 at `simpar=6`; 5.88, 8.51, 8.51 and 10.04 at 32.

- **Cheap replications lose or break even.** At 20-28 ms, 0.42x to
  0.98x. One Spark job cost 130 ms in run 2 and 230-310 ms in runs 1
  and 3, against 63-92 ms on one machine, and the solver makes 190 of
  them.
- **From about 85 ms it wins:** 1.7x to 2.9x at 83-112 ms, 3.6x to
  4.4x at 0.4-0.5 s, 4x to 6x at 1.5-1.7 s. Break-even on these
  clusters lies between roughly 30 and 85 ms per replication; the
  runs do not locate it more closely than that.
- **`simpar=6` runs sat close to their bound once replications were
  expensive** (3.7-4.7 against 4.6-4.9). The ceiling there is the
  solver's call pattern, as predicted.
- **`simpar=32` bought nothing until replications cost over a
  second.** In the three cheaper tiers the wall time at 32 was
  between 7% shorter and 14% longer than at 6. At 1.5-1.7 s it was
  11% to 36% shorter.

**The `x` printed in the blocks overstates the speedup at
`simpar=32`, and should not be quoted.** The notebook computed `x` as
the time the tasks spent working divided by the wall time, both
measured on the cluster. When many tasks run at once on shared cores,
each replication takes longer -- `ms_rep` is 1.2 to 1.7 times higher
in the `simpar=32` row than in the `simpar=6` row of every tier -- and that
slowdown is counted as work done. Run 3's last row prints 9.55 against
a bound of 10.04; its wall time was 64.7 s for 231 replications that
cost 1.71 s each at `simpar=6`, which is 6.1x. Run 1's prints 9.80 on
a machine whose sample-path sweep never exceeded 3.4x. The table above
uses the `simpar=6` cost for both columns for that reason. It is
still not a clean measure: the `simpar=6` cost was itself measured
under some load, and in run 3 under a changing number of workers
(its 500,000 tier cost 548 ms against 390 ms on the same CPU model in
run 2).

(The `warn` column of the `R` lines records a run-time warning the
backend had when these runs were made. It compared the same two
quantities as `x`, shared its flaw -- it stayed silent in run 2 at
`simpar=32`, a run that was no faster than plain `solve()` -- and has
been removed. The column is kept because the blocks are reproduced
as they were typed.)

### Still untested

- **Serverless, and Spark Connect on Databricks.** All three runs
  were classic sessions with a `sparkContext`. That the backend's
  `range()`-and-UDF route works under Connect is established only
  against a local Connect server; that Databricks serverless and
  shared-access clusters are Connect is still from memory.
- **More than three executor hosts,** and any scaling curve on a
  cluster of known, fixed size.
- **Executors that are not x86-64,** a libc other than glibc, or
  executors of mixed CPU models within one run.
- **Python other than 3.12** on a cluster (3.10, 3.11 and 3.14 only
  locally).

### The blocks

Each line ends with a check on that line, and `SUM` covers the block.
`python docs/databricks/dbx_kit.py verify <file>` re-checks them and
every hash; `docs/databricks/README.md` explains the columns.

Run 1 -- DBR 17.3, Standard_D8s_v3, one executor host (with the four
transcription corrections described above):

```
E1 kit=1 dbr=17.3 spark=4.0.0 pyspark=4.0.0 mode=classic sc=yes ~0f
E2 node=Standard_D8s_v3 workers=1 exec_cores=? par=8 serverless=? ~18
D1 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=8 cp=3.0.0 ~30
D2 cpu=Intel(R)_Xeon(R)_Platinum_8171M_CPU_@_2.60GHz ~fe
D3 pymoso=2.0.0.dev0 tree=e7e4dc1b tree_ok=PASS ~04
D4 core=707b5a73 PASS libm=bd003174 PASS ~76
P1 tasks=128 hosts=1 workers=8 err=0 secs=18.0 ~83
P2 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=8 aff=8 ~a2
P3 cpus=1 cpu=Intel(R)_Xeon(R)_Platinum_8370C_CPU_@_2.80GHz ~2d
P4 pymoso=2.0.0.dev0 tree=e7e4dc1b trees=1 tree_ok=PASS cp=3.0.0 ~bc
ID core h=707b5a73 hashes=1 of=128 drv=PASS loc=PASS ~be
ID libm h=bd003174 hashes=1 of=128 drv=PASS loc=PASS ~b6
I paths h=38124230 drv=PASS loc=PASS ~da
I builtin h=23369797 drv=PASS loc=PASS ~6b
I repl h=e80f92d8 drv=PASS loc=PASS ~f1
I crn h=66b3450e drv=PASS loc=PASS ~1c
I philox h=93b7367b drv=PASS loc=PASS ~77
I libm h=cbc74a42 drv=PASS loc=PASS ~65
I version raised=VersionMismatch PASS ~8e
S units=20000 budget=400 | n wall_s task_s x sims h ok ~8d
S 1 9.0 8.72 1.0 519 f8f0015e P ~f2
S 2 8.9 8.54 2.0 1011 ff0c9928 P ~54
S 4 11.0 9.11 3.2 2130 d3e53114 P ~c4
S 8 22.2 19.71 3.1 4377 97932a35 P ~84
S 16 41.5 19.42 3.4 8394 9e8c26fd P ~03
S stop=plateau ~ed
R | units k ms_rep req sims jobs ms_job x bound warn h ok ~43
R 20000 6 28.1 1000 1182 190 237 0.74 4.15 Y 34fb189f P ~8c
R 20000 32 34.5 1000 1182 190 231 0.93 5.88 Y 34fb189f P ~9e
R 100000 6 112.0 300 468 50 404 2.59 4.63 n 9293efce P ~11
R 100000 32 151.9 300 468 50 447 3.18 8.51 n 9293efce P ~dc
R 500000 6 538.2 300 468 50 1280 3.93 4.63 n 9293efce P ~f0
R 500000 32 744.9 300 468 50 1371 5.09 8.51 n 9293efce P ~a0
R 2000000 6 1596.4 100 231 20 4650 3.97 4.91 n e80f92d8 P ~90
R 2000000 32 2525.9 100 231 20 2976 9.80 10.04 n e80f92d8 P ~62
Z secs=557 sections=env,probe,identity,sweep,repl ~1e
SUM 24623227 lines=36
```

Run 2 -- DBR 16.4 (Spark 3.5.2), Standard_D16s_v3, one executor host:

```
E1 kit=1 dbr=16.4 spark=3.5.2 pyspark=3.5.2 mode=classic sc=yes ~34
E2 node=Standard_D16s_v3 workers=1 exec_cores=? par=16 serverless=? ~bc
D1 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=16 cp=2.2.1 ~7d
D2 cpu=Intel(R)_Xeon(R)_Platinum_8370C_CPU_@_2.80GHz ~39
D3 pymoso=2.0.0.dev0 tree=e7e4dc1b tree_ok=PASS ~04
D4 core=707b5a73 PASS libm=bd003174 PASS ~76
P1 tasks=128 hosts=1 workers=16 err=0 secs=5.5 ~82
P2 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=16 aff=16 ~9a
P3 cpus=1 cpu=Intel(R)_Xeon(R)_Platinum_8370C_CPU_@_2.80GHz ~2d
P4 pymoso=2.0.0.dev0 tree=e7e4dc1b trees=1 tree_ok=PASS cp=2.2.1 ~cc
ID core h=707b5a73 hashes=1 of=128 drv=PASS loc=PASS ~be
ID libm h=bd003174 hashes=1 of=128 drv=PASS loc=PASS ~b6
I paths h=38124230 drv=PASS loc=PASS ~da
I builtin h=23369797 drv=PASS loc=PASS ~6b
I repl h=e80f92d8 drv=PASS loc=PASS ~f1
I crn h=66b3450e drv=PASS loc=PASS ~1c
I philox h=93b7367b drv=PASS loc=PASS ~77
I libm h=cbc74a42 drv=PASS loc=PASS ~65
I version raised=VersionMismatch PASS ~8e
S units=20000 budget=400 | n wall_s task_s x sims h ok ~8d
S 1 8.5 8.42 1.0 519 f8f0015e P ~ce
S 2 8.5 8.25 2.0 1011 ff0c9928 P ~70
S 4 10.6 8.70 3.2 2130 d3e53114 P ~cc
S 8 11.1 9.11 6.0 4377 97932a35 P ~29
S 16 21.8 19.15 6.2 8394 9e8c26fd P ~46
S 32 41.3 18.91 6.5 16665 b3a1c6e7 P ~08
S stop=plateau ~ed
R | units k ms_rep req sims jobs ms_job x bound warn h ok ~43
R 20000 6 20.4 1000 1182 190 131 0.97 4.15 Y 34fb189f P ~eb
R 20000 32 31.1 1000 1182 190 130 1.49 5.88 n 34fb189f P ~ba
R 100000 6 83.2 300 468 50 271 2.87 4.63 n 9293efce P ~49
R 100000 32 143.0 300 468 50 266 5.03 8.51 n 9293efce P ~4d
R 500000 6 390.4 300 468 50 896 4.08 4.63 n 9293efce P ~ef
R 500000 32 664.4 300 468 50 829 7.50 8.51 n 9293efce P ~f5
R 2000000 6 1541.1 100 231 20 3753 4.74 4.91 n e80f92d8 P ~ba
R 2000000 32 1835.2 100 231 20 3343 6.34 10.04 n e80f92d8 P ~c0
Z secs=427 sections=env,probe,identity,sweep,repl ~91
SUM 3b51d664 lines=37
```

Run 3 -- DBR 17.3, Standard_D8s_v3, three executor hosts, autoscaling:

```
E1 kit=1 dbr=17.3 spark=4.0.0 pyspark=4.0.0 mode=classic sc=yes ~0f
E2 node=Standard_D8s_v3 workers=1 exec_cores=? par=24 serverless=? ~90
D1 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=8 cp=3.0.0 ~30
D2 cpu=Intel(R)_Xeon(R)_CPU_E5-2673_v4_@_2.30GHz ~df
D3 pymoso=2.0.0.dev0 tree=e7e4dc1b tree_ok=PASS ~04
D4 core=707b5a73 PASS libm=bd003174 PASS ~76
P1 tasks=128 hosts=3 workers=24 err=0 secs=17.4 ~9a
P2 py=3.12.3 arch=x86_64 libc=glibc-2.39 cores=8 aff=8 ~a2
P3 cpus=1 cpu=Intel(R)_Xeon(R)_Platinum_8370C_CPU_@_2.80GHz ~2d
P4 pymoso=2.0.0.dev0 tree=e7e4dc1b trees=1 tree_ok=PASS cp=3.0.0 ~bc
ID core h=707b5a73 hashes=1 of=128 drv=PASS loc=PASS ~be
ID libm h=bd003174 hashes=1 of=128 drv=PASS loc=PASS ~b6
I paths h=38124230 drv=PASS loc=PASS ~da
I builtin h=23369797 drv=PASS loc=PASS ~6b
I repl h=e80f92d8 drv=PASS loc=PASS ~f1
I crn h=66b3450e drv=PASS loc=PASS ~1c
I philox h=93b7367b drv=PASS loc=PASS ~77
I libm h=cbc74a42 drv=PASS loc=PASS ~65
I version raised=VersionMismatch PASS ~8e
S units=20000 budget=400 | n wall_s task_s x sims h ok ~8d
S 1 9.0 8.71 1.0 519 f8f0015e P ~d1
S 2 8.7 8.37 2.0 1011 ff0c9928 P ~7b
S 4 11.3 9.05 3.1 2130 d3e53114 P ~b4
S 8 11.3 9.23 6.1 4377 97932a35 P ~df
S 16 15.8 11.81 8.8 8394 9e8c26fd P ~dc
S 32 30.0 17.32 9.3 16665 b3a1c6e7 P ~9b
S 64 56.6 18.39 9.8 33621 252eeae4 P ~0f
S stop=plateau ~ed
R | units k ms_rep req sims jobs ms_job x bound warn h ok ~43
R 20000 6 20.6 1000 1182 190 270 0.47 4.15 Y 34fb189f P ~90
R 20000 32 31.9 1000 1182 190 308 0.65 5.88 Y 34fb189f P ~d6
R 100000 6 84.2 300 468 50 443 1.78 4.63 n 9293efce P ~e8
R 100000 32 144.9 300 468 50 470 2.89 8.51 n 9293efce P ~f3
R 500000 6 547.7 300 468 50 1392 3.68 4.63 n 9293efce P ~cb
R 500000 32 753.1 300 468 50 1414 4.98 8.51 n 9293efce P ~40
R 2000000 6 1714.7 100 231 20 4734 4.18 4.91 n e80f92d8 P ~5f
R 2000000 32 2674.7 100 231 20 3236 9.55 10.04 n e80f92d8 P ~b9
Z secs=650 sections=env,probe,identity,sweep,repl ~fc
SUM 9a965c9e lines=38
```

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

- **The default generator's jump is the next wall.** [Landed in Phase 7 step 3 (2026-10-17): a general MRG jump is now 20-70 µs on 3.14 (`docs/hit-cost-baseline.md`, "After the cheaper jump").]
  1.5-2 ms per block, and the number of points a solver touches grows with
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
| Classic and Connect sessions | both, locally and in the CI `extras` job (first run 2026-10-13, both cells green, with all fifteen `test` cells and `clean-clone`) |
| Python 3.10 and 3.14 with pyspark 4.2.0 | the `extras` job |
| pyspark 3.5 (declared floor) | 3.5.9 locally with Python 3.11, classic; 3.5.2 on Databricks 16.4. Not under Connect |
| Executors on other hosts | **yes** -- three Databricks runs, one with three executor hosts ("On a real cluster") |
| A Databricks runtime | **yes**, classic sessions on DBR 16.4 and 17.3. **Not** serverless or shared-access |
| Driver, executors and the reference machine on different hardware | **yes, within x86-64 and glibc**: Broadwell and Skylake drivers against Ice Lake executors, and all of them against an AMD Ryzen on a different glibc and Python. Every float agreed. **Not** established: non-x86 executors, another libc, mixed CPU models among the executors of one run |
| Scale | three hosts, 24 vCPUs, on an autoscaling cluster. **Nothing larger, and no scaling curve on a cluster of fixed size** |

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

Four usability defects were found on the way and fixed before the
phase closed (`tests/test_library_arguments.py`):

1. An unknown solver parameter (`betaesp=0.4`) was silently ignored.
   It raises `TypeError`, naming it and listing the ones the solver
   takes.
2. A list `x0` failed with `cannot use 'list' as a set element`. Any
   sequence of numbers of the problem's dimension is accepted and
   becomes a tuple; the wrong length, or a component that is not a
   number, is refused at the call. Numbers are not converted or
   judged there. A point is a tuple of numbers and the oracle decides
   whether it is feasible, identically with and without `--crn`:
   `30.0` or a numpy integer is the point `30`; `30.5` goes to the
   problem's `g()`, which the built-in problems answer "infeasible";
   and a point that cannot be given a stream at all (nan, an
   infinity) is reported infeasible without being simulated. Before
   this, each of those raised an unrelated error without `--crn` and
   ran with it.
3. Every extra keyword went through `float()` and a bad one failed
   without naming the keyword. Numbers convert as before; anything
   else raises `TypeError` naming it.
4. The refusal for a class that cannot be sent to a worker ended
   "define it in a .py file". It leads with the `notebook` extra, and
   offers the file as the alternative outside a notebook.
