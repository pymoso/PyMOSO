# README claims no test establishes

Layer 5 of the README's testing (tests/test_readme_claims.py) ties each
factual claim in the README to the tests that establish it, by an HTML
comment after the claim. These are the claims it could not tie to a
test, written at Phase 6. Each says what would establish it. A claim
moves off this list when a test does, and gains an annotation in the
README.

## Measurements, which no test asserts

The suite never asserts on timing (CLAUDE.md, "Testing"). These rest on
the documents that record the measurements.

- **How much `--simpar` speeds a run up**, and that the solver's call
  pattern bounds it: `docs/simpar-ceiling.md`, refreshed at the end of
  Phase 4.
- **When sending replications to a Spark cluster pays** (roughly 100 ms
  per replication or more): `docs/spark-backend.md`, three Databricks
  clusters.
- **That CRN helps less, but still helps, when an oracle's draws are
  desynchronized:** `docs/crn-failure.md`, the inventory twins and the
  `randint` problem.
- **"Configuring a run: what was measured", every figure in it.** Each
  sentence names its document: `docs/hit-cost-baseline.md` (the
  framework's cost per replication), `docs/simpar-ceiling.md`
  (`--simpar` and `--proc` speedups, and the 35-46% sequential share),
  `docs/spark-backend.md` (cluster break-even and path scaling),
  `docs/crn-failure.md` (variance ratios, correlations and seed counts
  under CRN), `docs/plateau-problems.md` (the stall under CRN, and
  radius on plateaus) and `docs/neighbourhood-radius.md` (radius on
  the test problems and on the barrier problem). Timings and solution
  quality are never asserted by the suite.
- **What `betaeps` and `betadel` at 1.0 do to the returned set**, against
  the default: medians of 50 against 15 points (Test Problem A), 51
  against 41 (B) and 9 against 7 (C), R-PERLE at budget 4 x 10^6 with
  CRN. `docs/beta-sweep-reference.md`, "Returned-set sizes" (10 paired
  runs on A and B, 100 on C).
- **Identical results across machines.** The suite proves identity
  across process counts and start methods on one machine. Identity
  across hosts was shown on Databricks, within x86-64 and glibc
  (`docs/spark-backend.md`, "On a real cluster"), and nowhere else.

## Behaviour with no test

- **`RPE` and `RSPLINE` under `--crn`.** The README's claim that the
  built-in solvers other than the two example solvers support common
  random numbers is backed for `RPERLE` (a golden) and `RMINRLE` (the
  `get_nbors` whole-run comparison). Nothing runs `RPE` or `RSPLINE` with
  `crn=True`. A test would solve with each under `crn=True` and check
  that two points in one iteration share replications.
- **What Pasupathy (2010) establishes**, as the README and
  KNOWN_ISSUES.md use it: that σ̂/√m is the error-tolerance rate that is
  both sufficient and not wasteful (Theorems 7 and 8, p. 896; §5.2,
  p. 896; §5.3, p. 897), that m_ν = ⌈2 × 1.1^ν⌉ is its linear growth
  (Table 1, p. 897), that its convergence conditions do not involve a
  search limit like b_ν (C.1-C.3, p. 894; N_k = O_p(1), §5 equation
  (2), p. 895), and that it assumes independent sample paths (§8(ii),
  p. 900). Checked against the paper by the maintainer, who has it; the
  paper is not in the repository, and no test can check a citation.
  **Still an interpretation:** that RLE's δ plays the role of the
  paper's ε_k. The match is of functional form and role, not something
  the paper states (`docs/algorithm-audit.md`, findings 2 and 9).
- **The CRN counterexample:** R-MinRLE's median of 2.83 against 1.93
  without CRN, 9 seeds better and 10 worse, and R-PE's and R-PERLE's
  15 of 20, on the `Antithetic` problem (`docs/crn-failure.md`).
- **The author's reason for b_ν's (d - 1) factor** is his account
  (2026-11-19), recorded in `docs/algorithm-audit.md`, finding 9.
- **KNOWN_ISSUES.md's "Open in 2.0.0", the `bconst` workaround.** That
  setting `bconst` to 8 / (d - 1) gives the papers' search limit is read
  from `calc_b` (`bconst * max(d - 1, 1) * 1.2^nu`), not tested.
- **The oracle contract's zero-variance hazard.** That at a standard
  error of 0 R-PE and R-PERLE step PE's constraint by an absolute 1e-6
  is read from `rperle.py`. That the step vanishes at about 3.4 x 10^10
  is computed from double precision. That PE then repeats its search
  without end is inferred and was never run
  (`docs/algorithm-audit.md`, finding 13).
- **That an oracle drawing random numbers outside `rng` loses
  reproducibility, CRN and independence in parallel.** True by
  construction (PyMOSO controls only `rng`); not tested.
- **A tester subclass that replaces `soln` or `true_g` must recompute
  `soln_images`.** True by reading: the built-in testers compute
  `soln_images` in `__init__` from their module's `soln`, and `metric`
  reads only `soln_images`. A test would subclass a tester, replace
  `soln` after `__init__`, and show `metric` still scoring against the
  old images.
- **The C wrapper examples.** They need a compiled library and are
  deliberately not exercised (tests/test_readme_examples.py). So is
  the note that an `mrg32k3a` seed component can exceed 2^31 and does
  not fit a C `long` on Windows -- true by the generator's modulus,
  `2^32 - 209`.
- **What the optional extras install.** `pymoso[notebook]` adding
  `cloudpickle` and `pymoso[spark]` adding `pyspark` is read from
  `pyproject.toml`; CI's `extras` job installs them, and the release
  checks resolve them, but no test reads the declaration.
- **Python 3.10 or higher.** `requires-python` in `pyproject.toml`,
  exercised by CI's 3.10-3.14 matrix, not by a test.
- **The installation commands.** `python -m pip install .`, the
  `git+` form with an extra and with a tag, `"pymoso<2"` resolving to
  1.1.0, and `python -m build` producing an installable wheel were
  each run by hand in a fresh virtual
  environment on Linux (2026-10-14), not by a test; `clean-clone`
  covers only an editable install of `.[test]`. The Windows
  virtual-environment commands have not been run. What the bare
  `git+` command installs depends on the repository's default
  branch, which is GitHub's setting, not the tree's.

## Descriptions of the algorithms

What a parameter does (`betadel` "RLE's completeness relaxation"), what
`accel` and `spsolve` return, and what
RLE certifies are descriptions of the published algorithms. The papers
cited at the top of the README are their reference; the parameter
table's defaults and solver lists are checked against the code
(tests/test_readme_param_table.py), and its descriptions are not.
`ExampleSearchSolver` and `ExampleBnBSolver` (MO-COMPASS and MOPBnB)
have not been checked against their papers at all
(docs/mocompass-mopbnb-known-issues.md).

The finite-variance requirement on `g()` (Phase 7) is the papers'
assumption, cited by lemma and assumption number
(docs/algorithm-audit.md, the accumulated entries, checked those
citations). "PyMOSO does not check it" is true by reading: nothing in
the framework examines a variance except to compute a sample one. No
test could establish an absence of checking.

## What the README leaves out, by decision

- **The README does not describe `ExampleSearchSolver` or
  `ExampleBnBSolver`.** It has no section on them, no prose presenting
  them as usable, and no claim about what they implement; they appear
  only in the generated `listitems` block and parameter table, in the
  sentence saying the listing includes solvers the README does not
  describe, and as the exception in the sentence on `--crn`. This is a decision recorded in CLAUDE.md, and deliberately
  not a test: asserting that prose is absent is awkward and easy to
  fool (a test for the names would have to allow the generated blocks,
  and would miss a description that never used them). Review keeps it.
