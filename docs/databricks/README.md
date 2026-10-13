# The Databricks run

**Finished and archived, 2026-10-13.** Three runs were made, all
verified; the cluster access they depended on has ended and no
further run is planned. The results and what they establish are in
`docs/spark-backend.md`, "On a real cluster". The three blocks are in
`results/` and can still be re-checked:

    python docs/databricks/dbx_kit.py verify docs/databricks/results/<file>

Nothing here is maintained. The notebook's embedded known-good values
are left exactly as the blocks were checked against (tree `e7e4dc1b`,
commit `baa7027`), which is what keeps the blocks verifiable -- and
means the notebook as it stands would print `tree_ok=FAIL` against
any later pymoso. No test covers this directory.

**If anyone runs it again, it needs these first.** The first two are
defects in the kit that the runs exposed; they are why some of its
numbers must not be quoted.

1. **Fix the `x` column of the `R` lines.** It is task work time over
   wall time, and under contention it overstates the speedup (9.55
   printed for 6.1). It misled the person the measurement was for.
   Print the wall time, and a speedup against an uncontended cost per
   replication -- for instance one measured by running a few blocks
   alone first.
2. **Record the executor hosts each timing line actually used.** The
   kit counts hosts once, in the probe. The clusters autoscaled, so
   no timing line has a known worker count. Have each task return its
   hostname, or probe before and after every line.
3. **Run `dbx_kit.py gen`** against the tree being installed, with a
   second interpreter on the other side of Python 3.12 (see the end
   of this file), and push before going.
4. **Treat the embedded Python-version split as provisional.** If
   KNOWN_ISSUES.md issue 17 is fixed, the `core` value stops
   depending on the Python version and `core_expected()` should go.
5. **It has only ever met classic sessions on x86-64.** Serverless,
   Spark Connect on Databricks, non-x86 executors and a cluster of
   fixed size are the things it was built to measure and did not get
   the chance to.

What follows is the run sheet as it was used.

| File | What it is |
|---|---|
| `pymoso_dbx_notebook.py` | Paste into a notebook cell. Self-contained. |
| `dbx_kit.py` | Before: writes the known-good values into the notebook. After: checks a typed copy of the block. Also runs the notebook against a local Spark. |

## Before leaving

1. **Push `dev-2.0`.** The cluster installs from GitHub. Until the
   Phase 4 commits are on `origin/dev-2.0` the install has no
   `pymoso.backends` and the notebook can only report that.
2. If `pymoso/` changed since the known-good values were generated,
   regenerate them and push again:

       .venv-extras/bin/python docs/databricks/dbx_kit.py gen /path/to/a/python3.11

   The second interpreter is any Python older than 3.12 with pymoso
   installed; one value differs across that boundary (below). The
   notebook prints `tree_ok=FAIL` on the cluster if what is installed
   there is not the tree the values came from.
3. Take `pymoso_dbx_notebook.py` as it is after that.

## On the cluster

Cell 1, alone:

    %pip install git+https://github.com/pymoso/PyMOSO.git@dev-2.0

Cell 2: the whole of `pymoso_dbx_notebook.py`.

With the defaults it took three and a half minutes on this
six-core machine. How long it takes on a cluster is not known: the
sweep runs further where there are more cores, and every Spark job
costs more than it does locally. Both long parts are time-boxed
(`SWEEP_SECONDS`, `REPL_SECONDS`, ten and fifteen minutes), so allow
half an hour. Progress is printed as it goes. **Copy only the block
between the two rulers at the end**, each line with its `~xx`, and
the `SUM` line. If something fails the block is still printed, with an
`X` line naming what failed; a cancel prints it too.

To re-run only part of it, edit `SECTIONS` near the top. The other
knobs are next to it: `SWEEP_MAX_PATHS` and `SWEEP_SECONDS` bound the
scaling sweep, `REPL_PARTS` and `REPL_SECONDS` the break-even probe.

## Afterwards

Type the block into a file and run

    python docs/databricks/dbx_kit.py verify typed.txt

It reports each mistyped line by number, a missing line, a wrong
`SUM`, and then re-checks every hash against the known-good values
itself, without trusting the PASS or FAIL the cluster printed. Spacing
and letter case do not matter.

## Reading the block

| Lines | What they answer |
|---|---|
| `E1`, `E2` | Runtime, Spark and pyspark versions, `mode=connect` or `classic`, whether a `sparkContext` exists, node type and configured sizes where the runtime exposes them (`?` where it does not). |
| `D1`-`D4` | The driver: Python, architecture, libc, CPU, and whether the installed pymoso is the expected tree. |
| `P1`-`P4` | The executors, from a probe of 128 tasks: distinct hosts and worker processes reached, Python, architecture, libc, cores, CPU models (`cpus=` is how many different ones), and their pymoso. |
| `ID core`, `ID libm` | **Bit-identity across machines.** Every probe task computes the same floats. `hashes=1` means every executor agreed; `drv` compares with the driver; `loc` with this machine. `core` is pymoso's own generators and one Oracle. `libm` is the platform's maths library and an Oracle that uses it: if `libm` fails and `core` passes, the difference is in a user's own arithmetic, not in the backend, and `bad=` names the functions. |
| `I ...` | Whole runs through `SparkBackend` -- sample paths, a built-in tester sent by reference, replications, `--crn`, Philox, the libm problem -- each against the same run on the driver (`drv`) and against this machine (`loc`). `I version` confirms a pymoso version mismatch is raised by name. |
| `S n ...` | Scaling: `n` sample paths in one job. `wall_s` is the job, `task_s` the mean time one path took where it ran, `x` the speedup over running them one after another on an idle executor, `sims` the simulations actually run, and `ok` whether all `n` results match this machine's. |
| `R ...` | Replication-level break-even, by cost tier and `simpar` (`k`). `ms_rep` is the measured cost of one replication, `req` the budget asked for and `sims` what was actually run, `ms_job` the wall time of one Spark job, `x` the speedup (work done over wall time), `bound` the most the solver's call pattern allowed at that `k`, `warn` whether `SlowDispatchWarning` fired. |
| `X ...` | Something failed. The traceback is printed under the block. |

Three things to know when reading the numbers:

- **`sims` is the real count.** A budget is only checked between RA
  iterations (KNOWN_ISSUES.md issue 16): the four tiers ask for 1,000,
  300, 300 and 100 and run 1,182, 468, 468 and 231. Scale by `sims`.
- **The sweep has no call-pattern bound to match.** The batched bounds
  in `docs/simpar-ceiling.md` are about replications inside one
  `solve()`. Sample paths are independent, so `x` should rise with `n`
  until it reaches the cluster's task slots; watch `task_s` to see
  when paths start slowing each other. The `bound` column in the `R`
  lines is the one that corresponds to that document.
- **`x` in the `R` lines is work over wall time**, both measured on
  the cluster. Below 1, plain `solve()` would have been faster.

For comparison, this machine (6 cores, local Spark, 2026-10-13):
`ms_job` 63-80 for cheap replications; `x` 0.13-0.18 at 1.6 ms per
replication, 0.7-0.9 at 6 ms, 1.8-2.5 at 25 ms, 2.8-4.5 at 97 ms.

## What was tested here, and what was not

The notebook was run unmodified against local Spark with small
workloads (`dbx_kit.py localtest`), every check passing:

| Driver and executors | Spark | Mode |
|---|---|---|
| Python 3.14, executors on a second venv with a non-editable install | 4.2.0 | classic `local-cluster`, and Connect |
| Python 3.10 | 4.2.0 | classic |
| Python 3.11 | 3.5.9 | classic |

Also: a part that raises (block still printed, `X` line present), a
cancel, and the verifier against a faithful copy and one with two
mistyped digits and a missing line.

Not tested: Spark 3.5 under Connect (the pip distribution of 3.5 has
no Connect server to start locally); anything Databricks-specific --
whether `%pip` reaches the executors on serverless, whether a UDF may
import a notebook-scoped library there, what the runtime's own
cloudpickle makes of the payloads. Those are what the run is for.

## One value depends on the Python version

`core` has two known-good values, for Python before 3.12 and from
3.12. pymoso's normal variate (`prng.mrg32k3a.bsm`) adds its terms
with the built-in `sum()`, and Python 3.12 changed `sum()` to
compensate for rounding. On this machine 8,153 of 20,000 normal
variates differ in the last bit between Python 3.11 and 3.12 (largest
relative difference 5.9e-16). Every whole-run hash in the notebook is
the same on 3.10 through 3.14, so it did not move a solution here, but
it can. Found building this kit; not fixed; a driver and executors
always share a Python version, so it does not affect the cluster's
own agreement.
