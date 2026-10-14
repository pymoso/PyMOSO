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
- **Identical results across machines.** The suite proves identity
  across process counts and start methods on one machine. Identity
  across hosts was shown on Databricks, within x86-64 and glibc
  (`docs/spark-backend.md`, "On a real cluster"), and nowhere else.

## Behaviour with no test

- **R-SPLINE minimizes the first objective of a multi-objective
  problem.** True of the code (`RSPLINE` calls `spline` with its default
  objective, 0) but untested. A test would solve a two-objective problem
  with `RSPLINE` and check the solution against the first objective
  alone.
- **`RPE` and `RSPLINE` under `--crn`.** The README's "all built-in
  solvers except MOCOMPASS and MOPBnB support common random numbers"
  is backed for `RPERLE` (a golden) and `RMINRLE` (the `get_nbors`
  whole-run comparison). Nothing runs `RPE` or `RSPLINE` with
  `crn=True`. A test would solve with each under `crn=True` and check
  that two points in one iteration share replications.
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

## Descriptions of the algorithms

What a parameter does (`betadel` "affects how likely it is for RLE to
keep its given solution"), what `accel` and `spsolve` return, and what
RLE certifies are descriptions of the published algorithms. The papers
cited at the top of the README are their reference; the parameter
table's defaults and solver lists are checked against the code
(tests/test_readme_param_table.py), and its descriptions are not.
MOCOMPASS and MOPBnB have not been checked against their papers at all
(docs/mocompass-mopbnb-known-issues.md).
