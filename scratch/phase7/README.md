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
