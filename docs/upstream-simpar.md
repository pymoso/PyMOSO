# Upstream's reworked `--simpar`: a design document

Read from `pymoso/master` (canonical repo, github.com/pymoso/PyMOSO),
commit `917bf06` ("improved multiprocessing for --simpar option"), on
top of `dfd2a30` ("set rng cache with object methods instead of class
methods"). This is a description of a design to learn from for the
executor redesign, not a review of it — nothing here is a
recommendation to change it.

## What problem it replaces

The version we forked from (and every version before `917bf06`)
implemented `--simpar` by spinning up a fresh `multiprocessing.Pool`
inside every single `Oracle.hit()` call, and derived each worker's
stream by calling `get_next_prnstream(start_seed)` — missing the
required second argument, `TypeError` on the first call. `--simpar`
has never worked in any version before this rework (confirmed: the
same crash reproduces against a fresh install of the real PyPI 1.0.4
wheel). `917bf06` replaces that whole mechanism.

## The pieces

Two new module-level functions in `chnbase.py`:

```python
def mp_replicate(orccls, x, rngcls, seed):
    rng = rngcls(seed)
    orc = orccls(rng)
    orc.set_crnflag(False)
    isfeas, objvals = orc.g(x, rng)
    return isfeas, objvals

def mp_worker(input, output):
    for func, args in iter(input.get, 'STOP'):
        result = func(*args)
        output.put(result)
```

Two new `Oracle` methods:

```python
def set_simpar(self, simpar):
    self.simpar = simpar
    if self.simpar > 1:
        self.req_q = Queue()
        self.res_q = Queue()
        self.proc = []
        for i in range(self.simpar):
            p = Process(target=mp_worker, args=(self.req_q, self.res_q))
            p.start()
            self.proc.append(p)

def mp_cleanup(self):
    if self.simpar > 1:
        for p in self.proc:
            p.terminate()
            p.join()
```

`chnutils.solve()` calls `orc.set_simpar(simpar)` once, before handing
the oracle to the solver, and `orc.mp_cleanup()` once, after the whole
retrospective-approximation run finishes. `chnutils.testsolve()` does
the same per independent sample path, always with `set_simpar(1)` —
testsolve still doesn't expose `--simpar` at all, so this always takes
the non-parallel branch; nothing about that changed.

## Worker lifetime: a persistent pool, not one per call

This is the headline architectural change. The old design paid process
-spawn overhead on every `hit()` call — every point, every RA
iteration. The new design spawns `simpar` worker processes exactly
once per `solve()` invocation (`set_simpar`, called before the RA loop
starts) and tears them down exactly once at the end (`mp_cleanup`,
called after `isp_run` returns). The workers are generic: `mp_worker`
just pulls `(func, args)` off a shared `Queue` and calls `func(*args)`,
forever, until told to stop. Nothing about a worker is specific to a
particular point, iteration, or even oracle instance — the task itself
carries everything a worker needs.

One thing worth flagging precisely, not as a defect but as an
observation for whoever next touches this: `mp_worker`'s loop is built
to exit on a `'STOP'` sentinel (`iter(input.get, 'STOP')`), but
`mp_cleanup` never puts one — it calls `Process.terminate()` directly.
The sentinel-based graceful-stop path exists in the code but doesn't
appear to be exercised by the only caller that tears workers down.

## How seeds are derived and passed to workers

This is the part that actually fixes CRN/parallelism composability,
and it's a different shape than the old design entirely. The old
design tried to give each *worker* its own long-lived stream, jumped
2^127 apart (the same granularity as a full independent stream). The
new design gives each *replication* its own seed, and workers are
stateless — they don't own a stream at all, they're just handed one
seed and asked to produce one observation.

Inside `Oracle.hit(x, m)`, when `self.simpar > 1`:

```python
for i in mr:                                   # m times, i.e. once per replication
    orccls = type(self)
    rngcls = type(self.rng)
    cseed = self.rng.get_seed()
    proc_job = (mp_replicate, (orccls, x, rngcls, cseed))
    self.req_q.put(proc_job)
    self.crn_nextobs()
for i in mr:
    isfeasi, oval = self.res_q.get()            # blocks until a result is ready
    feas.append(isfeasi)
    objm.append(oval)
```

Compare to the non-parallel branch, a few lines below:

```python
for i in mr:
    isfeasi, oval = self.g(x, self.rng)
    feas.append(isfeasi)
    objm.append(oval)
    self.crn_nextobs()
```

The seed sequence is generated **identically** in both branches: each
replication's seed is `self.rng`'s current state at that point, and
`self.crn_nextobs()` — the same method the serial path already used —
advances `self.rng` to the next substream (a 2^76 jump from the
iteration's `crn_obsold` baseline) after each one. The only thing that
differs between serial and parallel is *where* `g(x, rng)` actually
runs: locally in the serial branch, inside a worker (via
`mp_replicate`, reconstructing a throwaway `Oracle` from `cseed`) in
the parallel branch. The set of `m` seeds handed out for a given
`hit(x, m)` call is exactly the same set, in exactly the same order,
regardless of `self.simpar`.

This is why it composes with CRN correctly where the old design didn't:
there is no second, independently-configured `Oracle` with its own
`crnflag` involved at all. `mp_replicate` does construct a throwaway
`Oracle(rng)` inside the worker, and does unconditionally call
`orc.set_crnflag(False)` on it — but that oracle only ever calls `g()`
once and returns; it never calls `crn_check`/`crn_advance`/`crn_nextobs`
itself, so its own `crnflag` is inert. All of the actual CRN state
machinery (`crn_obsold`, `crnold_state`, the rewind-and-jump pattern)
stays entirely on the *parent* process's `Oracle`, driven exactly as it
already was for the serial case. Parallelism only changes where one
arithmetic step of an already-fully-determined sequence happens to
execute.

## What crosses the process boundary

Exactly four values per replication, all trivially picklable: the
*class* of the oracle (`orccls`, e.g. `ProbTPA`, not an instance), the
point `x`, the *class* of the RNG (`rngcls`, e.g. `MRG32k3a`), and a
6-tuple seed (`cseed`). Nothing mutable, nothing shared, no live
oracle state, no queue/process handles. The worker reconstructs
everything it needs from those four values inside `mp_replicate` and
returns a plain `(bool, tuple)` pair. This is about as small a
process-boundary contract as this kind of design can have.

## How results are reassembled

The result-collection loop calls `self.res_q.get()` exactly `m` times
and appends whatever comes back, in *arrival* order — which need not
match *submission* order, since worker processes can finish out of
order relative to each other. This is safe here specifically because
what happens next is `mean`/`variance` over the `m` collected values:
both are order-independent aggregates, so a same-multiset-different-
order result list produces an identical `obmean`/`obse`. The design
relies on that — it would not be safe to reassemble into a
position-sensitive structure (e.g. "replication `i`'s value must be at
index `i`") without an explicit tag identifying which seed a result
came from, which `mp_replicate`'s return value does not carry.

## `crn_advance` also changed, independently of the above

Not part of the `--simpar` fix directly, but relevant to reading it
correctly: `crn_advance` no longer loops `self.simpar` times:

```python
# what we forked from:
def crn_advance(self):
    numjumps = self.simpar
    self.crn_reset()
    for i in range(numjumps):
        self.rng = get_next_prnstream(self.rng.get_seed(), self.crnflag)
    ...

# current upstream:
def crn_advance(self):
    self.crn_check()
    self.rng = get_next_prnstream(self.rng.get_seed(), self.crnflag)
    ...
```

It now jumps exactly once per RA iteration, unconditionally, regardless
of `simpar`. This makes sense given the seed-per-replication design
above: since parallelism no longer needs `simpar` separate reserved
2^127-streams (one per worker) per iteration, `crn_advance` doesn't
need to reserve that space either. One RA iteration still consumes
exactly one 2^127 jump, matching what `get_testsolve_prnstreams`'
`max_RI`-iteration reservation already assumes — that consistency
holds before and after this change only because `testsolve` always
calls `set_simpar(1)` and has never exposed `--simpar`, so this
particular interaction was never actually exercised either way.

## An unreachable-but-present artifact, noted for completeness

`chnutils.solve()` currently reads:

```python
solvstream = MRG32k3a(seed)
orcstream = get_next_prnstream(seed, crn)
orcstream, solvstream = get_solv_prnstreams(seed, crn)
```

The first two lines compute values that are immediately discarded —
the third line's call to `get_solv_prnstreams(seed, crn)` recomputes
both `orcstream` and `solvstream` the same way internally and
overwrites both names. Functionally inert (dead code), not a
correctness issue; noting it because a migration that touches this
function should know it's there and not mistake it for something load
-bearing.

## `bump()`: unchanged

`Oracle.bump(x, m)` is byte-for-byte the same as what we verified in
phase 2a: still purely serial (loops `self.g(x, self.rng)` directly, no
`self.simpar` branch, no queue, no worker dispatch at all), still calls
`crn_nextobs()` once per replication and `crn_check()` at the end,
still `sys.exit()`s on `m < 1` rather than raising. The multiprocessing
rework touched `hit()` extensively and left `bump()` completely alone.
For the out-of-tree `MOSOSolver` contract phase 2a documented (raw
per-replication observations, `simpar` never honored), that
documentation still describes upstream's `bump()` exactly. Anyone
depending on it is unaffected by this rework, including with respect
to the one gap already on record: `bump()` still won't parallelize
under `simpar > 1`, silently, same as before.

## Validation surface: what no longer needs the same justification

`Oracle.hit()`'s parallel branch no longer calls `mp.Pool` (or
anything else that would raise on a non-positive process count) —
`set_simpar` only creates workers inside `if self.simpar > 1:`, so a
`--simpar` of 0 or a negative number silently takes the *serial*
branch in `hit()` (`self.simpar > 1` is false either way) rather than
crashing. That specific failure mode — "non-positive value reaches
`mp.Pool` and raises an opaque error" — is gone for `--simpar`
specifically. It's still real for `--proc` (`chnutils.par_runs` is
untouched, still `mp.Pool(NUM_PROCESSES)` directly on the caller-given
value) and would still be real for `--simpar` if the value were
negative enough to matter in some other way this reading didn't turn
up. Relevant to the migration plan, not resolved here.

## Worker lifetime, part 2: exception safety (found and fixed during the CLI migration)

Everything above describes the design as upstream shipped it. One gap
in it surfaced concretely while migrating the CLI: `chnutils.solve()`
spawned `set_simpar`'s workers, then called `isp_run()`, then
`mp_cleanup()` — with no exception safety between the three. An
infeasible `x0` raises a `ValueError` out of `isp_run()`, skipping
`mp_cleanup()` entirely and leaking the non-daemon worker `Process`
objects; since they're blocked forever on `input.get()` inside
`mp_worker` with nothing left to send them `'STOP'`, Python's
multiprocessing `atexit` machinery hangs the whole CLI process trying
to join them at exit. Confirmed directly: `pymoso solve --simpar=4
--budget=10000 ProbTPA RPERLE 97 97` (an infeasible `x0` for `ProbTPA`)
hung for 57 minutes before being killed by hand.

Fixed on this branch (not upstream) by making `Oracle` a context
manager: `set_simpar` returns `self`, and `__exit__` unconditionally
calls `mp_cleanup()` without suppressing whatever exception triggered
it. `chnutils.solve()` now reads `with orc.set_simpar(simpar): res =
isp_run(...)`. See `tests/test_simpar_worker_lifecycle.py` for the
regression test (confirmed failing via a 30s timeout before the fix,
passing in ~0.1s after) and the commit that applied it for the full
reasoning, including why a context manager was chosen over a bare
try/finally: worker ownership as an explicit `Oracle` lifecycle is the
shape the executor rework will need generally, not just here.

## Worker lifetime, part 3: --simpar is slower than serial for a cheap oracle

Measured directly, not assumed, while investigating the hang above —
`ProbTPA`/`RPERLE`, `--budget=10000`, a feasible `x0`, wall-clock `Run
time` as reported by the CLI itself:

| `--simpar` | Run time |
|---|---|
| 1 (serial) | 0.99s |
| 2 | 2.48s |
| 4 | 2.09s |
| 8 | 2.09s |

Roughly 2x *slower* than serial, and — tellingly — flat across worker
counts rather than scaling with them. Grepped `chnbase.py`/`chnutils.py`
for any `sleep`/`poll`/`timeout` that might impose a fixed floor:
there is none. `mp_worker` is a bare blocking `input.get()`. The flat-
regardless-of-worker-count shape instead points to the dispatch
granularity: `Oracle.hit()`'s parallel branch submits exactly one
`(mp_replicate, args)` job per replication through `self.req_q`/
`self.res_q`, so the total number of `Queue.put`/`Queue.get` round
trips is set by the replication count (budget and `mconst`), not by
`simpar` — adding workers parallelizes across that fixed set of round
trips without shrinking it. For `ProbTPA.g()` — a couple of
`normalvariate` draws and some arithmetic — the per-task pickling and
IPC cost apparently exceeds the compute it's shipping off to another
process, so the fixed overhead dominates instead of being amortized.

This matches the README's own guidance almost exactly ("we only
recommend using the parallel simulation replications feature if
observations are sufficiently 'expensive' to compute, e.g. the
simulation takes a half second or more to generate a single
observation") — it just hadn't been measured end-to-end against a
cheap oracle before. Not a bug, and not fixed here: it's the concrete
motivating case for batched dispatch (submitting a worker's whole share
of a `hit()` call's replications as one task, not one task per
replication) in the executor rework — recorded for that work, not
addressed by this migration.
