# Golden end-seed baselines

`tests/test_golden.py` shells out to the `pymoso` CLI (and, as of this
migration, calls `chnutils.solve`/`chnutils.testsolve` directly as a
library) for a fixed set of problem/solver/seed/budget combinations and
asserts the reported ending seed matches a hardcoded value. It is a pure
regression check on the RNG stream's final position -- it does not (by
itself) say anything about solution quality.

## This baseline is captured against github.com/pymoso/PyMOSO, not the earlier fork

Earlier baselines (see "Historical: PyPI 1.0.4" below) were captured
against a fork based on the PyPI 1.0.4 wheel. This project has since
moved onto the canonical repository, github.com/pymoso/PyMOSO. The
values in `CASES` as of this migration are captured fresh from *that*
source tree, not carried over or adjusted from the old fork's numbers --
the two codebases differ in ways (the `--simpar` rework, whitespace
normalization, an added bus-scheduling problem, etc.) that can and do
change exact end-seed output even where the underlying defect (issue 1
below) is unchanged. Some individual case values happen to coincide with
the old fork's pre-fix numbers and some don't; this wasn't investigated
further; it isn't the point of this baseline being here.

**Capture conditions:**

- Environment: `.venv-baseline`, CPython 3.10.21, this repo installed
  editable (`uv pip install -e .`), captured from the source tree
  directly.
- Commit: `a8242f2` on the `pymoso-migration` branch (after restoring
  library kwarg defaults, before the jump-ahead fix).
- Command: `pytest tests/test_golden.py -vv` for the CLI cases; direct
  `solve()`/`testsolve()` calls (see the test file) for the two
  library-level cases.

**Why capture from source instead of a wheel:** the earlier (1.0.4)
capture was taken from a PyPI wheel specifically because the old fork's
`master`, at that point in its own history, would not compile
(pre-existing syntax errors, since fixed). No such blocker exists here --
`compileall` is clean on this branch (aside from one unrelated,
already-fixed `TabError` in `pymoso/examples/mytester.py`) -- so this
capture is taken directly from the checked-out source, which is also
what every subsequent regeneration should do.

**New in this capture, not present in the original 1.0.4 baseline:**

- `rperle_tpa_simpar2`: exercises `--simpar=2`, which crashed
  unconditionally on every version this project has tested until
  `917bf06` (see `docs/upstream-simpar.md`, KNOWN_ISSUES.md issue 2) --
  there was no working `--simpar` case to capture before now. Its end
  seed is identical to plain `rperle_tpa`'s, which is expected and
  correct, not a bug: `docs/upstream-simpar.md` documents that the
  seed handed to each replication is derived from the same
  `crn_nextobs()` sequence regardless of `simpar`, so parallelism only
  changes *where* a replication's `g()` call executes, never which
  seed it uses.
- `test_library_solve_end_seed_matches_baseline` /
  `test_library_testsolve_end_seed_matches_baseline`: direct
  `chnutils.solve()`/`chnutils.testsolve()` calls. These functions had
  never been under any regression coverage before this migration --
  only the CLI, which always passes every keyword argument explicitly,
  was ever exercised (see KNOWN_ISSUES.md issue 7). Both match their
  CLI counterparts' end seeds exactly, as expected: the CLI commands
  are thin wrappers over these same functions.

### Current values (pre jump-ahead fix)

| Case | End seed |
|---|---|
| rperle_tpa | `738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184` |
| rminrle_tpa | `351780864, 2663153664, 3654082560, 106530816, 1144764416, 1616205824` |
| rpe_tpa | `3303566336, 4006175744, 3614092288, 1314799616, 1181410816, 4085780480` |
| rspline_simpleso | `703488000, 1321244672, 1775603712, 3804634112, 1506610176, 4268795904` |
| testsolve_tpa | `4147335168, 2708353024, 1540286464, 2835288064, 3722176512, 2227803136` |
| rperle_tpa_crn | `3661742080, 1011607552, 2254225408, 2663375872, 466939904, 3186325504` |
| rperle_tpa_seed2 | `1248518144, 988284928, 1514053632, 1982265344, 806676480, 2743545856` |
| rperle_tpa_simpar2 | `738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184` |
| solve() library call | `738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184` |
| testsolve() library call | `4147335168, 2708353024, 1540286464, 2835288064, 3722176512, 2227803136` |

**These values are pre-fix.** Every one of them is expected to change
once the jump-ahead fix (KNOWN_ISSUES.md issue 1) lands in a subsequent
commit, at which point this table moves down to a "Historical" section
and a fresh post-fix table takes its place, following the same pattern
below for the original 1.0.4 baseline.

---

## Historical: PyPI 1.0.4 (pre-fix, on the original fork), retained for reference only

The values below were captured from the genuine PyPI `pymoso==1.0.4`
wheel on CPython 3.10.21, against the fork this project started from
before moving to github.com/pymoso/PyMOSO (see that fork's own
`tests/golden/` artifacts, preserved on the `old-work` branch, for the
full historical record including the post-jump-ahead-fix values that
existed on that base). They are kept here only as a record of what
1.0.4 produced -- **not** as a fallback or a value to regenerate
against: every one of these seven end seeds has all six components
divisible by 256, the exact signature of the float64 precision loss
documented in KNOWN_ISSUES.md issue 1.

| Case | Old (1.0.4, original fork) end seed |
|---|---|
| rperle_tpa | `1977704448, 4260704256, 2500841472, 2104219648, 3452829696, 2812925952` |
| rminrle_tpa | `3587104768, 2166626304, 1141821440, 1049742336, 335185920, 3014187008` |
| rpe_tpa | `2841247744, 261109760, 2690854912, 499741696, 1685186560, 3208818688` |
| rspline_simpleso | `109225984, 1898143744, 4152428544, 1883361280, 1586790400, 2178549760` |
| testsolve_tpa | `4147335168, 2708353024, 1540286464, 2835288064, 3722176512, 2227803136` |
| rperle_tpa_crn | `3661742080, 1011607552, 2254225408, 2663375872, 466939904, 3186325504` |
| rperle_tpa_seed2 | `1349353472, 3887125504, 1020818432, 1885945856, 1962877952, 476176384` |

This project's earlier fork also captured a 40-independent-seed solution
-quality comparison (Hausdorff distance, RPERLE/ProbTPA/TPATester) across
its own jump-ahead fix, finding no statistically significant difference
(Welch's t=1.62, p≈0.10) -- consistent with the defect corrupting only
the *independence guarantee* between stream positions, not the validity
of individual draws. That comparison is not repeated here; see the
`old-work` branch for the full writeup if it's needed again on this base.
