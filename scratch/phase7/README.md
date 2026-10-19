# Phase 7 scratch: two measurements made after step 1

Not part of the package or the suite. Run from the repository root with
`.venv-dev/bin/python scratch/phase7/<script>`. The write-up is in
`docs/phase7-plan.md` (step 1, "At three or more objectives", and step
1b).

- `dtlz2_lattice.py` is copied unchanged from the `many-objective`
  branch (`d959c34`, `scratch/manyobj/dtlz2_lattice.py`), the
  many-objective baseline's test problem.

## get_ncn at M = 2-6

`ncn_many.py OUT.jsonl 30000 2,3,4,5,6 3` produced `ncn_many_30k.jsonl`
(log with `uptime` before and after: `ncn_many_30k.log`). RMINRLE on
lattice DTLZ2 (L = 4, sigma 0.05, the baseline's x0, Philox), with
`docs/bench_biobjective_profile.py`'s probes. Each configuration runs
plain, time and count; all three must return the same solution and end
seed. In count mode the early-exit shadow asserts the same `ncn` as the
real code on every call (`shadow_checked == ncn_calls` in every row).

## Remembering infeasible points within an iteration (step 1b)

`infeas_cache.py OUT.jsonl [CONFIG-SUBSTRING]` runs each configuration
without and with a shadow that answers a repeat of an oracle-infeasible
point from a record kept for the iteration. Nothing in `pymoso/`
changes. `infeas_deterministic.jsonl` is every built-in-style problem
(box feasibility); `infeas_random.jsonl` is the positive control
(`P_INFEAS=0.03`, `RPERLE RandomEdge`), where feasibility is random and
the comparison must, and does, see differences.

`infeas_shadow.py` is the same shadow as a module for a scratch venv:
installed with a `.pth` line (`import infeas_shadow`) it loads in every
interpreter, `-I` subprocesses included, when `INFEAS_SHADOW=1`;
`INFEAS_SHADOW_LOG=<file>` logs each skipped repeat with its pid. That
is how the full suite was run with the shadow on.

## What a whole-run feasibility record would hold (KNOWN_ISSUES issue 18)

KNOWN_ISSUES issue 18 and the check this measured were withdrawn on
2026-10-17 (docs/phase7-plan.md, step 1b's decisions). The numbers
stand as a measurement; nothing uses them.

`feas_memory.py OUT.jsonl` produced `feas_memory.jsonl`: per run, the
distinct points ever estimated feasible and infeasible, the largest
single iteration's `gbar`, and the bytes the two sets occupy (tuples
included, measured with tracemalloc).

## Step 2's identity check

`step2_record.py OUT.jsonl` runs 39 counted configurations and records,
per run, the solution, end seed, simcalls, a digest of every `get_ncn`
call's input and answer in sequence, and the calls `get_ncn` made to
`calc_delta` and the dominance predicates. `--compare BEFORE AFTER`
requires every run identical. `step2_before.jsonl` was recorded on the
tree before step 2a. `step2_after_relaxations.jsonl` is after step 2a,
computing relaxations once: 39 of 39 identical.
`step2_after_early_exit.jsonl` is after step 2b, the early exit: 39 of
39 identical to the record after step 2a, with fewer predicate calls.
For step 2c the script also digests every `get_nondom` call the solver
bases make, input and answer in order, and counts the `does_dominate`
calls inside it (`front.does_dominate`); `--compare` checks those only
when both records have them. `step2c_before.jsonl` is the tree after
step 2b recorded that way (39 of 39 identical to
`step2_after_early_exit.jsonl` on the older fields), and
`step2c_after.jsonl` is after step 2c: 39 of 39 identical, every
`get_nondom` answer included. `STEP2_ONLY=<substring>`
and `--compare-subset` run part of it, which is how a deliberately
wrong version was shown to be caught.

## Step 2 end to end

`manyobj_sweep_after_step2.jsonl` (and `.log`) is the many-objective
sweep (240 runs) on `30bfa68`, made with `many-objective`'s own
`docs/bench_many_objective.py` and `scratch/manyobj/` at `d959c34`,
extracted unchanged outside the repository (`git archive many-objective
docs/bench_many_objective.py scratch/manyobj | tar -x -C DIR`, then
`python DIR/docs/bench_many_objective.py sweep OUT.jsonl`).
`manyobj_retime_after_step2.jsonl` reruns its 29 loaded runs (`retime`);
the comparison is between the two merged with `quiet` and the
original's sweep and retime files merged the same way; as in the
original, the merged files are not kept (`quiet` rebuilds them,
checking each rerun against its original).
`ncn_many_30k_after_step2.jsonl` is step 1's 15 `plain` runs rerun twice
on the same tree, with the original wall time beside both. The results
are in docs/phase7-plan.md, step 2, "Step 2 measured end to end".

## Step 3: the jump

`jump_profile.py runs OUT.jsonl` profiles every `jump_seed_n` call in
eight real runs (both MRG generators) by path, with the general
exponents' bit lengths, set bits and trailing zeros: `jump_runs.jsonl`
(made on the code before step 3; shares under a timing wrapper, so
upper bounds). `jump_profile.py parts OUT.json` times a general jump's
pieces: `jump_parts.json`. `jump_runs_plain.py LABEL` times the same
runs uninstrumented; `jump_runs_plain.jsonl` is old and new code
alternately, twice (the old code by putting `HEAD`'s three
`pymoso/prng/` files in place, bytecode caching off).
`jump_first_call.py GENERATOR` is a fresh interpreter's first and
second jumps (the power tables' build cost). `step3_after_jump.jsonl`
is `step2_record.py` after step 3: 39 of 39 identical to
`step2c_after.jsonl`. Results: docs/hit-cost-baseline.md, "After the
cheaper jump".

## R-SPLINE's x0 re-estimation, reverted

`rspline_x0_measure.py` compares R-SPLINE with the x0 re-estimation of
commit `00c3dea` (a subclass holding that commit's `spsolve`) against
R-SPLINE without it, on step 4's problems, starts and seeds, and counts
how often the search restarted from x0 and how often the warm start it
gave up was truly better. Output: `rspline_x0_measure.txt`. The change
was reverted on this evidence (docs/phase7-plan.md, step 7).

## Steps 4 and 5: NE

`ne_quadratic_runs.jsonl` is `docs/bench_ne_quadratic.py run`'s raw
output (1,040 runs), made after R-SPLINE's x0 re-estimation was
reverted; `docs/ne-quadratic-tables.md` is generated from it and
`docs/ne-quadratic.md` reads it.

## Step 5b: radius

`barrier.py` is the barrier problem (kept here, by decision).
`radius_runs.jsonl` is `docs/bench_radius.py run`'s raw output (1,450
runs); `radius_nbors_1.json` and `radius_nbors_2.json` are two runs of
`bench_radius.py nbors`, the construction timing (the report uses the
first). `docs/neighbourhood-radius-tables.md` is generated from them.

## Step 6: plateaus

`plateau.py` is the plateau problem (kept here, by decision; it reuses
`barrier.certified_by`). `plateau_runs.jsonl` is
`docs/bench_plateau.py run`'s raw output (1,040 runs, ExampleBnBSolver's
included); `plateau_describe.json` is `describe`'s, the problem's trap
counts. `docs/plateau-problems-tables.md` is generated from them.

## Step 6b: CRN synchronization

`crnsync.py` holds the inventory and cyclic twins (`SyncVar`, `SyncFixed`, `CycRare`, `CycFixed` and
their single-objective counterparts), the calibration oracles (`Calib`,
`CalibVar`) and `RandRange`; it reuses `barrier.certified_by`.
`crn_covariance.json` is `docs/bench_crn.py covariance`'s raw output and
`crn_covariance.log` its progress log (with both twin pairs, about 74
minutes on 3.14, beside the solver runs). `crn_runs.jsonl` is
`docs/bench_crn.py run`'s output (640 runs, six worker processes; counted,
so running in parallel does not matter) and `crn_runs.log` its log.
`docs/crn-failure-tables.md` is generated from both.
`crn_covariance.json` was rerun once to add the sweep's part/rejoin
counts; every other field came back identical.

`crnsign.py` holds the sign problems: `Route` (and `RouteBelow`, a
wrong model for the mutation check), `Split` (exact only) and
`Antithetic`, with each one's exact correlations. `crn_sign_covariance.json`
is `docs/bench_crn_sign.py covariance`'s output (about 23 minutes on
3.14; its `anti_exact_swap` rows were added afterwards from
`exact_only()`, which samples nothing) and `crn_sign_covariance.log`
its log; `crn_sign_runs.jsonl` is `docs/bench_crn_sign.py run`'s output
(360 runs, six workers) and `crn_sign_runs.log` its log.
`docs/crn-sign-tables.md` is generated from both.
