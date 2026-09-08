# Parallel dispatch baseline

Before-picture for the executor rework (see CLAUDE.md's "Known open
items"). Absolute timings only -- these are NOT enforced by the test
suite (tests/test_parallel_dispatch.py owns the portable,
worker-count-independent correctness assertions: identical results and
simulation-call counts across worker counts, and today's job-dispatch
counts). Regenerate with docs/bench_parallel_dispatch.py; do not
hand-edit the numbers below.

Both mechanisms are dispatched unbatched today: one job per replication
for `--simpar`, one job per independent sample path for `--proc`,
regardless of worker count (confirmed in
tests/test_parallel_dispatch.py). `--proc`'s job count is fixed by
`isp`, not `proc` -- each `--proc` table below fixes isp across its own
worker-count sweep (see its header and `isp` column), so workers beyond
isp have nothing to do; that's expected, not a bug. It's the same
reason the README's `--isp=20 --proc=10` and `--isp=100 --proc=20`
examples oversubscribe this specific 6-physical-/12-logical-core
machine (10 and 20 both exceed 12 logical threads, and 10 already
exceeds 6 physical cores) -- those numbers reflect contention on this
hardware, not anything inherent to `--proc` itself.

### Python 3.10.21

- Captured: 2026-09-08T16:11:04.664387+00:00
- Commit: `fe74ad6`
- Python: `3.10.21 (main, Sep  1 2026, 14:16:49) [Clang 22.1.3 ]`
- OS: BunsenLabs GNU/Linux 12 (Boron) (kernel `6.1.0-52-amd64`)
- CPU: AMD Ryzen 5 5600X3D 6-Core Processor -- 6 physical cores, 12 logical (2 threads/core), 2200.0000-4451.8359 MHz, 96 MiB (1 instance) L3
- Load average at capture (1/5/15m): `2.01 10.45 13.65 1/873 117238`
- `uptime`: `12:11:04 up 1 day,  7:12,  1 user,  load average: 2.01, 10.45, 13.65`
- `nvidia-smi`: `NVIDIA GeForce RTX 4070, 37 %, 541 MiB, 12282 MiB`

#### --simpar (solve)

**Light (~1.3ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 0.316 | 507 | 1.00x |
| 2 | 0.217 | 507 | 1.46x |
| 4 | 0.143 | 507 | 2.21x |
| 6 | 0.135 | 507 | 2.34x |
| 8 | 0.127 | 507 | 2.50x |
| 12 | 0.128 | 507 | 2.47x |

**Moderate (~13ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 1.212 | 204 | 1.00x |
| 2 | 0.696 | 204 | 1.74x |
| 4 | 0.438 | 204 | 2.77x |
| 6 | 0.408 | 204 | 2.97x |
| 8 | 0.413 | 204 | 2.93x |
| 12 | 0.437 | 204 | 2.77x |

**Heavy (~35ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 1.492 | 87 | 1.00x |
| 2 | 0.926 | 87 | 1.61x |
| 4 | 0.522 | 87 | 2.86x |
| 6 | 0.547 | 87 | 2.73x |
| 8 | 0.603 | 87 | 2.47x |
| 12 | 0.539 | 87 | 2.77x |

#### --proc (testsolve, isp=12 fixed)

**Light (~1.3ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 0.700 | 1044 | 1.00x | 12 |
| 2 | 0.383 | 1044 | 1.83x | 12 |
| 4 | 0.226 | 1044 | 3.10x | 12 |
| 6 | 0.180 | 1044 | 3.90x | 12 |
| 8 | 0.215 | 1044 | 3.26x | 12 |
| 12 | 0.177 | 1044 | 3.95x | 12 |

**Moderate (~13ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 3.447 | 576 | 1.00x | 12 |
| 2 | 1.784 | 576 | 1.93x | 12 |
| 4 | 0.944 | 576 | 3.65x | 12 |
| 6 | 0.662 | 576 | 5.21x | 12 |
| 8 | 0.798 | 576 | 4.32x | 12 |
| 12 | 0.636 | 576 | 5.42x | 12 |

**Heavy (~35ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 3.865 | 216 | 1.00x | 12 |
| 2 | 2.004 | 216 | 1.93x | 12 |
| 4 | 1.083 | 216 | 3.57x | 12 |
| 6 | 0.856 | 216 | 4.51x | 12 |
| 8 | 0.854 | 216 | 4.52x | 12 |
| 12 | 0.734 | 216 | 5.26x | 12 |

**Observations** (auto-derived from the table data above, not hand-written):

- --simpar, Light (~1.3ms/rep): best speedup 2.50x at workers=8 (this machine has 6 physical cores).
- --simpar, Moderate (~13ms/rep): best speedup 2.97x at workers=6 (this machine has 6 physical cores).
- --simpar, Heavy (~35ms/rep): best speedup 2.86x at workers=4 (this machine has 6 physical cores).
- --proc, Light (~1.3ms/rep): best speedup 3.95x at workers=12 (this machine has 6 physical cores).
- --proc, Moderate (~13ms/rep): best speedup 5.42x at workers=12 (this machine has 6 physical cores).
- --proc, Heavy (~35ms/rep): best speedup 5.26x at workers=12 (this machine has 6 physical cores).


### Python 3.14.7

- Captured: 2026-09-08T16:11:49.185645+00:00
- Commit: `fe74ad6`
- Python: `3.14.7 (main, Sep  1 2026, 14:18:09) [Clang 22.1.3 ]`
- OS: BunsenLabs GNU/Linux 12 (Boron) (kernel `6.1.0-52-amd64`)
- CPU: AMD Ryzen 5 5600X3D 6-Core Processor -- 6 physical cores, 12 logical (2 threads/core), 2200.0000-4451.8359 MHz, 96 MiB (1 instance) L3
- Load average at capture (1/5/15m): `2.02 9.29 13.11 1/874 117637`
- `uptime`: `12:11:49 up 1 day,  7:12,  1 user,  load average: 2.02, 9.29, 13.11`
- `nvidia-smi`: `NVIDIA GeForce RTX 4070, 39 %, 541 MiB, 12282 MiB`

#### --simpar (solve)

**Light (~1.3ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 0.278 | 507 | 1.00x |
| 2 | 0.229 | 507 | 1.21x |
| 4 | 0.119 | 507 | 2.33x |
| 6 | 0.106 | 507 | 2.61x |
| 8 | 0.126 | 507 | 2.21x |
| 12 | 0.118 | 507 | 2.34x |

**Moderate (~13ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 1.056 | 204 | 1.00x |
| 2 | 0.626 | 204 | 1.69x |
| 4 | 0.379 | 204 | 2.79x |
| 6 | 0.400 | 204 | 2.64x |
| 8 | 0.411 | 204 | 2.57x |
| 12 | 0.408 | 204 | 2.59x |

**Heavy (~35ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 |
|---|---|---|---|
| 1 | 1.341 | 87 | 1.00x |
| 2 | 0.792 | 87 | 1.69x |
| 4 | 0.468 | 87 | 2.87x |
| 6 | 0.528 | 87 | 2.54x |
| 8 | 0.497 | 87 | 2.70x |
| 12 | 0.569 | 87 | 2.36x |

#### --proc (testsolve, isp=12 fixed)

**Light (~1.3ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 0.624 | 1044 | 1.00x | 12 |
| 2 | 0.329 | 1044 | 1.90x | 12 |
| 4 | 0.198 | 1044 | 3.15x | 12 |
| 6 | 0.139 | 1044 | 4.48x | 12 |
| 8 | 0.145 | 1044 | 4.30x | 12 |
| 12 | 0.144 | 1044 | 4.33x | 12 |

**Moderate (~13ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 2.976 | 576 | 1.00x | 12 |
| 2 | 1.577 | 576 | 1.89x | 12 |
| 4 | 0.811 | 576 | 3.67x | 12 |
| 6 | 0.596 | 576 | 5.00x | 12 |
| 8 | 0.657 | 576 | 4.53x | 12 |
| 12 | 0.560 | 576 | 5.31x | 12 |

**Heavy (~35ms/rep)**

| workers | seconds | calls | speedup vs. workers=1 | isp |
|---|---|---|---|---|
| 1 | 3.343 | 216 | 1.00x | 12 |
| 2 | 1.713 | 216 | 1.95x | 12 |
| 4 | 0.907 | 216 | 3.69x | 12 |
| 6 | 0.652 | 216 | 5.13x | 12 |
| 8 | 0.723 | 216 | 4.62x | 12 |
| 12 | 0.622 | 216 | 5.38x | 12 |

**Observations** (auto-derived from the table data above, not hand-written):

- --simpar, Light (~1.3ms/rep): best speedup 2.61x at workers=6 (this machine has 6 physical cores).
- --simpar, Moderate (~13ms/rep): best speedup 2.79x at workers=4 (this machine has 6 physical cores).
- --simpar, Heavy (~35ms/rep): best speedup 2.87x at workers=4 (this machine has 6 physical cores).
- --proc, Light (~1.3ms/rep): best speedup 4.48x at workers=6 (this machine has 6 physical cores).
- --proc, Moderate (~13ms/rep): best speedup 5.31x at workers=12 (this machine has 6 physical cores).
- --proc, Heavy (~35ms/rep): best speedup 5.38x at workers=12 (this machine has 6 physical cores).

