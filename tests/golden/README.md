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
the old fork's numbers (both this migration's pre-fix capture and its
post-fix capture below each match two of the old fork's own values, at
the cases where nothing either codebase changed affects that particular
code path) and some don't; this wasn't investigated further, it isn't
the point of this baseline being here.

**Capture conditions (current, post jump-ahead fix):**

- Environment: `.venv-baseline`, CPython 3.10.21, this repo installed
  editable (`uv pip install -e .`), captured from the source tree
  directly.
- Commit: `e095287` on the `pymoso-migration` branch (the jump-ahead
  fix itself).
- Command: `pytest tests/test_golden.py -vv` for the CLI cases; direct
  `solve()`/`testsolve()` calls (see the test file) for the two
  library-level cases. Re-run twice to confirm determinism before being
  written into `CASES`.

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
  was ever exercised (see KNOWN_ISSUES.md issue 6). Both match their
  CLI counterparts' end seeds exactly, as expected: the CLI commands
  are thin wrappers over these same functions.

**New, captured separately (MOCOMPASS/MOPBnB brought in-tree):**

- Environment: `.venv-baseline`, CPython 3.10.21, same source tree.
  Commit: `f884bf2` (parent of the commit bringing these solvers
  in-tree). Re-run twice each, same determinism check as above.
- `mocompass_tpa`, `mopbnb_tpa`: `ProbTPA`, `--param lb 0 --param ub 50`,
  `x0=(40, 40)`, `--budget=1000`, matching the existing `ProbTPA` cases'
  shape exactly. `testsolve_mocompass`, `testsolve_mopbnb`: same box,
  `--isp=4`, mirroring `testsolve_tpa`'s shape.
- Both `testsolve_*` cases' end seeds are identical to `testsolve_tpa`'s
  and to each other -- expected, not a coincidence: per
  `docs/end-seed-scope.md`, `testsolve`'s reported end seed is a pure
  function of the stream-allocation schedule (`isp`/`MAX_RI`/`crn`/seed),
  fixed before any solver runs, and does not depend on which solver or
  what it actually does.
- These two solvers' own `.sample()` calls needed a Python-3.11+
  compatibility fix (wrapping set arguments in `sorted()`, since
  `random.sample()` stopped accepting sets) before landing in-tree; this
  necessarily changes the exact sequence of points sampled relative to
  whatever these files' un-fixed, out-of-tree behavior gave under
  Python 3.10's implicit set-iteration order. These values are captured
  fresh against the fixed, in-tree code -- there was no prior in-tree
  baseline to preserve continuity with. See
  `docs/mocompass-mopbnb-known-issues.md` for detail.

### Current values (SPLI's nearest-integer line search)

**Capture conditions:** twice on each of `.venv-baseline` and
`.venv-dev`, identical. "Before" is the values after SPLI's return at
an infeasible point, below.

**Why they moved, deliberately.** SPLI's line search now goes to the
nearest integer point, halves up, where it floored
(`docs/algorithm-audit.md`, finding 4; `tests/test_spli_nearest.py`).
In one dimension every step is a whole number, so `rspline_simpleso`
did not move; nor did the example solvers.

| Case | Final ν before / after | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|---|
| rperle_tpa (and simpar2, solve() library call) | 14 / 15 | 1,060 / 1,145 | `{(11,20)}` | `{(23,38)}` | moved |
| rpe_tpa | 14 / 15 | 1,036 / 1,139 | `{(11,21)}` | `{(23,38)}` | moved; equal to rperle_tpa's |
| rminrle_tpa | 16 / 15 | 1,195 / 1,084 | `{(33,40), (34,40)}` | `{(34,40), (34,41), (35,41), (36,41)}` | moved |
| rperle_tpa_seed2 | 14 / 12 | 1,134 / 1,035 | `{(27,26)}` | `{(6,7), (7,8), (8,7)}` | moved |
| rperle_tpa_crn | 8 / 8 | 1,080 / 1,075 | `{(0,7), (0,8), (10,7), (20,8), (21,8)}` | `{(0,6), (0,7), (0,8), (10,8), (21,8)}` | **unchanged** |
| testsolve_tpa | -- | -- | `{(39,0), (39,1)}`, `{(16,8)}`, `{(11,4), (11,5), (14,2)}`, `{(27,19)}` | `{(36,2), (36,3), (37,5)}`, `{(14,6), (15,8)}`, `{(12,4), (12,5)}`, `{(15,12), (16,14)}` | moved |
| testsolve() library call | 14, 14, 14, 14 / 14, 15, 14, 13 | -- | `{(26,22), (26,23), (29,22)}`, `{(25,23), (29,20)}`, `{(37,40), (37,41), (40,40)}`, `{(14,14), (15,14)}` | `{(27,33)}`, `{(30,36), (32,37)}`, `{(30,38), (31,38), (31,39)}`, `{(7,25), (7,26)}` | moved |

| Case | End seed |
|---|---|
| rperle_tpa, rperle_tpa_simpar2, rpe_tpa, solve() library call | `2517142237, 665811671, 3380533723, 2206904786, 2365409261, 2739352961` |
| rminrle_tpa | `4141303608, 3438113027, 28307458, 3941246114, 1564520191, 4162565512` |
| rperle_tpa_seed2 | `2610745870, 2569889759, 3472340748, 590630483, 3721417536, 1652950390` |
| testsolve_tpa | `4244682198, 3625174356, 12273143, 1664344229, 2348137384, 1201660776` |
| testsolve() library call | `8469352, 1992542596, 263836292, 1756683918, 1965808740, 924476425` |
| every other case | as in the sections below |

### Historical: unchanged by SPLI's return at an infeasible point

**No end seed moved; five solutions did.** SPLI now returns at an
infeasible line-search point (`docs/algorithm-audit.md`, finding 5;
`tests/test_spli_infeasible.py`). Every case was run before and after,
twice on each of `.venv-baseline` and `.venv-dev`, identical. Only
`tests/test_solution_sensitivity.py` failed, and it is the one file
regenerated.

| Case | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|
| rperle_tpa (and simpar2, solve() library call) | 1,028 / 1,060 | `{(8,21)}` | `{(11,20)}` | unchanged |
| rpe_tpa | 1,028 / 1,036 | `{(8,21)}` | `{(11,21)}` | unchanged |
| rperle_tpa_crn | 1,085 / 1,080 | `{(0,7), (0,8), (10,7)}` | `{(0,7), (0,8), (10,7), (20,8), (21,8)}` | unchanged |
| testsolve_tpa | -- | path 0 `{(43,0), (43,1), (44,1)}` | path 0 `{(39,0), (39,1)}` | unchanged |
| testsolve() library call | -- | path 3 `{(19,13), (21,11)}` | path 3 `{(14,14), (15,14)}` | unchanged |

Every other case returned what it did. The end seeds are those of the
next section (`docs/end-seed-scope.md`, the seventh instance).

### Values set by PE's LWEP filter

**Capture conditions:** twice on each of `.venv-baseline` and
`.venv-dev`, identical. "Before" is the SPLINE stop fix's values,
below. ν is the final RA iteration's number.

**Why they moved, deliberately.** PE places its epsilon values from the
LWEPs among Min's output, and starts its tracebacks from Min's output,
as the listing does; it filtered the previous solution and placed from
all of Min's output (`docs/algorithm-audit.md`, finding 3;
`tests/test_pe_lwep_filter.py`). R-MinRLE has no PE and did not move;
nor did R-SPLINE or the example solvers.

| Case | Final ν before / after | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|---|
| rperle_tpa (and simpar2, solve() library call) | 14 / 14 | 1,084 / 1,028 | `{(35,39), (39,38)}` | `{(8,21)}` | **unchanged** |
| rpe_tpa | 14 / 14 | 1,138 / 1,028 | `{(33,40)}` | `{(8,21)}` | moved; equal to rperle_tpa's again |
| rperle_tpa_seed2 | 12 / 14 | 1,022 / 1,134 | `{(30,36), (30,37), (30,38)}` | `{(27,26)}` | moved |
| rperle_tpa_crn | 7 / 8 | 1,181 / 1,085 | 10 points | `{(0,7), (0,8), (10,7)}` | moved |
| testsolve_tpa | -- | -- | `{(32,1)}`, `{(14,9), (14,10), (14,11), (16,6), (18,4)}`, `{(11,3), (12,4), (13,4)}`, `{(18,18), (19,18)}` | `{(43,0), (43,1), (44,1)}`, `{(16,8)}`, `{(11,4), (11,5), (14,2)}`, `{(27,19)}` | moved |
| testsolve() library call | 11, 11, 13, 11 / 14, 14, 14, 14 | -- | `{(22,25), (23,24)}`, `{(32,25), (33,24)}`, `{(36,40)}`, `{(15,31), (17,31)}` | `{(26,22), (26,23), (29,22)}`, `{(25,23), (29,20)}`, `{(37,40), (37,41), (40,40)}`, `{(19,13), (21,11)}` | moved |

**The end seed's blind spot, a third time for `rperle_tpa`**
(`docs/end-seed-scope.md`, the seventh instance): its solution went
from two points to one, none in common, in 56 fewer simulation calls,
and its end seed, with `rperle_tpa_simpar2`'s and the `solve()`
library call's, is what it was. `tests/test_solution_sensitivity.py`
(the `testsolve_tpa` computation) moved on every path.

| Case | End seed |
|---|---|
| rpe_tpa | `2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658` |
| rperle_tpa_crn | `923826343, 324720588, 3520057607, 2369325274, 481703105, 875203729` |
| rperle_tpa_seed2 | `3017716348, 1164624147, 1959750905, 3905490566, 3460109705, 2293446127` |
| testsolve_tpa | `3152774270, 410798641, 30954636, 1162836765, 3775738568, 4231190908` |
| testsolve() library call | `3821022682, 3698201652, 1914137393, 374897783, 2982944267, 2480987988` |
| every other case | as in the next section |

### Historical: the SPLINE stop fix, pre PE's LWEP filter

**Capture conditions:** twice on each of `.venv-baseline` and
`.venv-dev`, identical. "Before" is the search-limit fix's values,
below. ν is the final RA iteration's number.

**Why they moved, deliberately.** SPLINE now stops when its calls
exceed the search limit b, not when they reach it, and so takes one
more pass when a pass lands exactly on b (`docs/algorithm-audit.md`,
finding 14; `tests/test_spline_stop.py`). Every case's solution was
compared, not only those whose end seed moved: R-PERLE's, R-PE's and
R-SPLINE's are unchanged in every case, as is the `testsolve()`
library call.

| Case | Final ν before / after | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|---|
| rminrle_tpa | 15 / 16 | 1,024 / 1,195 | `{(36,41), (37,41)}` | `{(33,40), (34,40)}` | moved |
| testsolve_tpa | -- | -- | path 0 `{(42,3)}`, path 3 `{(13,18)}` | path 0 `{(32,1)}`, path 3 `{(18,18), (19,18)}` | moved; paths 1 and 2 unchanged |

`tests/test_solution_sensitivity.py`'s solution sets are `testsolve_tpa`'s
computation and moved with it, paths 0 and 3.

| Case | End seed |
|---|---|
| rminrle_tpa | `934352227, 2566036280, 3952654006, 4077942181, 2316375006, 212199263` |
| testsolve_tpa | `428304056, 346485484, 1619176594, 1600379305, 3253197826, 3926570837` |
| every other case | as in the next section |

### Historical: the search-limit fix, pre the SPLINE stop fix

**Capture conditions:** twice on each of `.venv-baseline` and
`.venv-dev`, identical. "Before" is the tie-break fix's values, below.

**Why it moved, deliberately.** The search limit b was 0 in one
dimension, in every iteration, and is now ceil(8 x 1.2^nu) there
(`docs/algorithm-audit.md`, finding 9; `tests/test_search_limit.py`).
Only `rspline_simpleso` is one-dimensional; every other case is two-
dimensional, where b is unchanged, and did not move.
`tests/test_solution_sensitivity.py` has no one-dimensional case and
did not move either.

| Case | Iterations before / after | Simcalls before / after | Solution before / after | End seed |
|---|---|---|---|---|
| rspline_simpleso | 29 / 25 | 1,023 / 1,076 | `{(0,)}` / `{(0,)}` | moved |

| Case | End seed |
|---|---|
| rspline_simpleso | `1637142171, 3902145111, 18424598, 4071908608, 2396963664, 4071290962` |
| every other case | as in the next section |

### Historical: the tie-break fix, pre the search-limit fix

**Capture conditions:** twice on each of `.venv-baseline` and
`.venv-dev`, identical. "Before" is the traceback fix's values, below.

**Why they moved, deliberately.** PE now breaks a tie between the two
objectives' epsilon counts with one draw from the solver's stream,
where it always took objective 0 (`docs/algorithm-audit.md`, finding
7; `tests/test_pe_traceback.py`). A tie shifts every later draw on
that stream, which SPLI's perturbations also use. R-MinRLE has no PE
and did not move; nor did R-SPLINE or the example solvers.

| Case | Iterations before / after | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|---|
| rperle_tpa (and simpar2, solve() library call) | 14 / 15 | 1,132 / 1,084 | `{(32,40), (33,40)}` | `{(35,39), (39,38)}` | moved |
| rpe_tpa | 14 / 15 | 1,084 / 1,138 | `{(32,40), (33,40)}` | `{(33,40)}` | moved; no longer equal to rperle_tpa's |
| rperle_tpa_seed2 | 12 / 13 | 1,028 / 1,022 | `{(21,20), (22,16)}` | `{(30,36), (30,37), (30,38)}` | moved |
| rperle_tpa_crn | 8 / 8 | 1,119 / 1,181 | 12 points | 10 points, 4 not in the 12 | **unchanged** |
| testsolve_tpa | -- | -- | `{(36,5), (37,6), (38,5), (38,6)}`, `{(16,8)}`, `{(11,3)}`, `{(15,12)}` | `{(42,3)}`, `{(14,9), (14,10), (14,11), (16,6), (18,4)}`, `{(11,3), (12,4), (13,4)}`, `{(13,18)}` | moved |
| testsolve() library call | 13, 13, 14, 13 / 12, 12, 14, 12 | -- | `{(22,38), (22,39)}`, `{(33,32), (33,33)}`, `{(32,27), (32,28)}`, `{(36,29), (39,19)}` | `{(22,25), (23,24)}`, `{(32,25), (33,24)}`, `{(36,40)}`, `{(15,31), (17,31)}` | **returned to its value before the traceback fix** |

**Two more blind spots of the end seed** (`docs/end-seed-scope.md`,
the seventh instance). `rperle_tpa_crn` kept its end seed for the
second capture running while its solution changed. The `testsolve()`
library call's end seed is again `608833221, ...`, its value before
the traceback fix, although every one of its four paths returned a
solution different from both earlier captures. Its end seed is
combined from the four paths' high-water marks; path 2 ran 14
iterations in all three captures, the most of any path, and is likely
(inferred, not traced) what sets it.

| Case | End seed |
|---|---|
| rperle_tpa | `2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658` |
| rminrle_tpa | `1660848401, 3982892888, 3117683308, 3201171133, 1965520305, 1045130260` |
| rpe_tpa | `2818038775, 1087741337, 3653104262, 2674052920, 139999430, 3804951309` |
| rspline_simpleso | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` |
| testsolve_tpa | `129432915, 1994717513, 830958108, 2162896734, 3623015892, 338784799` |
| rperle_tpa_crn | `1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043` |
| rperle_tpa_seed2 | `475503349, 3494235769, 3386972397, 2983267235, 3075726867, 2248836774` |
| rperle_tpa_simpar2 | `2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658` |
| solve() library call | `2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658` |
| testsolve() library call | `608833221, 1812491834, 2623259368, 3887640181, 811678161, 2382318639` |
| example_search_tpa, example_bnb_tpa, testsolve_example_search, testsolve_example_bnb | unchanged; `tests/test_golden.py` |

### Historical: the traceback fix, pre the tie-break fix

**Capture conditions:** as for the relaxation fix, below: twice on
each of `.venv-baseline` and `.venv-dev`, identical; "before" from the
relaxation fix's tree in a scratch install.

**One case moved, the `testsolve()` library call** (`ranx0=False`,
x0 `(40, 40)`, four paths). PE's traceback now reads the intervals on
the objective it constrains (`docs/algorithm-audit.md`, finding 1;
`tests/test_pe_traceback.py`). Paths 0-2 are unchanged. Path 3:

| | Before | After |
|---|---|---|
| Iterations | 12 | 13 |
| Simcalls | 1,033 | 1,137 |
| Solution | `{(21,31)}` | `{(36,29), (39,19)}` |
| End seed (whole call) | `608833221, 1812491834, 2623259368, 3887640181, 811678161, 2382318639` | `3347470030, 2041325172, 2574648445, 2621857106, 1320715482, 98588082` |

**Every other case is unchanged, and not only in its end seed:** the
six R-PERLE, R-PE and R-MinRLE `solve()` cases and `testsolve_tpa`'s
four paths returned the same solutions and simcalls as after the
relaxation fix. Whatever the corrected bound changed on those runs
did not reach a solution or a simulation count.

| Case | End seed |
|---|---|
| testsolve() library call | `3347470030, 2041325172, 2574648445, 2621857106, 1320715482, 98588082` |
| every other case | as in the next section |

### Historical: the relaxation fix, pre the traceback fix

**Capture conditions:** `.venv-baseline` (CPython 3.10) and
`.venv-dev` (CPython 3.14), this repo installed editable, captured
from the source tree, twice on each: identical values. The "before"
column was taken from the commit before the fix (`4b01e2b`), in a
scratch install, and reproduces the previous goldens exactly.

**Why they moved, deliberately.** R-PERLE, R-PE and R-MinRLE computed
their relaxation as se/m^β with se already σ̂/√m; the R-PERLE
preprint defines se · m^(1/2 - β), larger by √m. The code now computes
the preprint's (`docs/algorithm-audit.md`, finding 2;
`tests/test_relaxation.py`). R-SPLINE and the two example solvers do
not use the relaxation, and their cases did not move.

| Case | Iterations | Simcalls before / after | Solution before | Solution after | End seed |
|---|---|---|---|---|---|
| rperle_tpa | 14 / 14 | 1,042 / 1,132 | `{(34,38), (35,38), (35,39), (36,39)}` | `{(32,40), (33,40)}` | moved |
| rperle_tpa_simpar2 | 14 / 14 | 1,042 / 1,132 | as rperle_tpa | as rperle_tpa | moved, with it |
| rpe_tpa | 14 / 14 | 1,029 / 1,084 | `{(35,39), (40,40), (41,40)}` | `{(32,40), (33,40)}` | moved; still equal to rperle_tpa's |
| rminrle_tpa | 16 / 16 | 1,306 / 1,024 | `{(27,28), (27,29)}` | `{(36,41), (37,41)}` | moved |
| rperle_tpa_seed2 | 12 / 12 | 1,029 / 1,028 | `{(28,31), (29,31), (30,31)}` | `{(21,20), (22,16)}` | **unchanged** |
| rperle_tpa_crn | 8 / 8 | 1,183 / 1,119 | 11 points | 12 points, 4 of them new | **unchanged** |
| testsolve_tpa | -- | -- | four paths (`tests/test_solution_sensitivity.py`'s prior values) | all four changed | moved |
| solve() library call | as rperle_tpa | | | | moved, with it |
| testsolve() library call (ranx0=False) | -- | -- | not recorded | not recorded | **unchanged** |

**Two cases kept their end seeds while their solutions changed
completely.** `rperle_tpa_seed2` went from `{(28,31), (29,31),
(30,31)}` to `{(21,20), (22,16)}`, no point in common, with an
identical end seed. The end seed is one past the largest oracle
coordinate touched (`Oracle.get_endseed`). Without CRN that is set by
the last iteration, its largest point code and the replications drawn
there, so a run ending at the same iteration with the same largest
touch lands on the same value whatever else it found. With CRN the
coordinate has no point in it at all. `docs/end-seed-scope.md`, the
seventh instance.

| Case | End seed |
|---|---|
| rperle_tpa | `3379879516, 2064463187, 3070037076, 2057738628, 3140940286, 2423122255` |
| rminrle_tpa | `1660848401, 3982892888, 3117683308, 3201171133, 1965520305, 1045130260` |
| rpe_tpa | `3379879516, 2064463187, 3070037076, 2057738628, 3140940286, 2423122255` |
| rspline_simpleso | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` |
| testsolve_tpa | `2313342306, 4042774198, 3964834499, 2176857534, 4175967009, 2563160311` |
| rperle_tpa_crn | `1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043` |
| rperle_tpa_seed2 | `2175629958, 147802191, 2425104019, 853609596, 4132240727, 4089413332` |
| rperle_tpa_simpar2 | `3379879516, 2064463187, 3070037076, 2057738628, 3140940286, 2423122255` |
| solve() library call | `3379879516, 2064463187, 3070037076, 2057738628, 3140940286, 2423122255` |
| testsolve() library call | `608833221, 1812491834, 2623259368, 3887640181, 811678161, 2382318639` |
| example_search_tpa, example_bnb_tpa, testsolve_example_search, testsolve_example_bnb | unchanged; `tests/test_golden.py` |

Superseded by this capture: rperle_tpa, rperle_tpa_simpar2 and the
solve() library call `900181699, 3252648471, 384599192, 813079481,
747618736, 882165191`; rpe_tpa the same; rminrle_tpa `3101702307,
2274224287, 2252695779, 2887425027, 4188880773, 159891216`;
testsolve_tpa `2485384564, 3157617357, 1600102004, 2564266890,
2564580077, 3801707191`.

### Historical: R-SPLINE x0 re-estimation reverted, pre the relaxation fix

**One case moved back, `rspline_simpleso`, to its value before the
section below.** R-SPLINE's x0 re-estimation was reverted, by decision,
after it was measured to make R-SPLINE worse at practical budgets
(`docs/phase7-plan.md`, step 7, "x0 re-estimation"). The case is
`rspline_simpleso`'s value in "Historical: post testsolve() role-layout
fix, pre R-SPLINE x0 re-estimation", below, again: end seed
`2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931`,
1,023 simcalls, 29 iterations, solution `{(0,)}`. Before restoring it,
the reverted code was run under the golden's command, twice on each of
`.venv-baseline` and `.venv-dev`, and gave that end seed every time; and a stand-in for the reverted `spsolve`, used for the
measurement, reproduces it too. Every other case is as it has been
since the role-layout fix.

### Historical: post R-SPLINE x0 re-estimation, pre its reversion

Superseded: R-SPLINE's x0 re-estimation was reverted (above). Kept as
the record of the move and the reasons for it.


**Capture conditions:** `.venv-baseline` (CPython 3.10.22) and
`.venv-dev` (CPython 3.14.8), this repo installed editable, captured
from the source tree directly, twice on each: identical values.
Command: `pymoso solve --budget=1000 ProbSimpleSO RSPLINE 40`.

**One case moved, `rspline_simpleso`, and deliberately.** R-SPLINE now
estimates x0 again in every RA iteration and starts its search from x0
when x0's estimate is better than the warm start's, as R-PE, R-PERLE
and R-MinRLE already did through `get_min` (`docs/phase7-plan.md`,
step 7; approved, its own commit). Estimating x0 costs simulation
calls, so the budget ran out three iterations sooner:

| | Before | After |
|---|---|---|
| Iterations | 29 | 26 |
| Simcalls | 1,023 | 1,009 |
| Solution | `{(0,)}` | `{(0,)}` |
| End seed | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` | `3284326634, 477001502, 351030955, 2381370830, 1499024205, 1527143741` |

**The solution did not move.** The end seed and simcalls were
predicted before the change, from an in-process shadow of it, and
matched. No other case uses R-SPLINE, and no other value moved: every
other row of the table below is unchanged.

| Case | End seed |
|---|---|
| rspline_simpleso | `3284326634, 477001502, 351030955, 2381370830, 1499024205, 1527143741` |
| every other case | as in the next section |

### Historical: post testsolve() role-layout fix, pre R-SPLINE x0 re-estimation

All of this section's values are current, `rspline_simpleso`'s included
since the reversion (above).

**Capture conditions:** `.venv-baseline`, CPython 3.10.22, this repo
installed editable, captured from the source tree directly, at the
testsolve() role-layout fix itself (the commit immediately prior to
this regeneration). Command: `pytest tests/test_golden.py
tests/test_solution_sensitivity.py -v`; cross-checked against an
independent capture under `.venv-dev` (CPython 3.14.8) -- identical
values.

**Captured against the fix for KNOWN_ISSUES.md issue 10**, which was
two distinct defects in `chnutils.get_testsolve_prnstreams`, both from
rooting the oracle role "wherever the solver-stream loop ended":

1. *Seed collision.* That position was the last solver stream's own
   seed, so path 0's oracle stream and the last path's solver stream
   started at the same place -- with the default `--isp=1`, the same
   path's own solver and oracle.
2. *Dependence on `--isp`.* That position was stream `isp` from the
   run's seed, so every path's oracle streams moved whenever the number
   of paths changed. Extending a study from 100 sample paths to 200
   changed the results of the first 100.

The fix puts the three roles in fixed, separate zones (x0 at stream 0,
path t's solver at stream 1 + t, path t's oracle streams in slot t + 1)
so no two roles share a position and none depends on `--isp`. Solver
and x0 streams did not move; every oracle root did. Consequently
`testsolve_tpa`/`testsolve_mocompass`/`testsolve_mopbnb` and the
`testsolve()` library case moved, and nothing else: every `solve()`-path
case is identical to the previous capture below -- confirmed directly,
not assumed (`solve()` builds its two streams separately and had
neither defect). Predicted before the change and matched exactly.

`test_solution_sensitivity.py` moved in both of its parts: its
`EXPECTED_SOLUTIONS` (every path's replications changed, so every
path's search did) and its `end_seed`. **Its `end_seed` still equals
`testsolve_tpa`'s** -- both moved to the same new value. They are the
identical computation (same tester/solver/budget/seed/isp/proc/crn,
both `ranx0=True`), reached through the CLI in one case and the library
in the other, so a uniform change to the layout has to move them
together; that the equality survived is evidence the move was uniform
rather than path- or entry-point-specific.

| Case | End seed |
|---|---|
| rperle_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rminrle_tpa | `3101702307, 2274224287, 2252695779, 2887425027, 4188880773, 159891216` |
| rpe_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rspline_simpleso | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` |
| testsolve_tpa | `2485384564, 3157617357, 1600102004, 2564266890, 2564580077, 3801707191` |
| rperle_tpa_crn | `1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043` |
| rperle_tpa_seed2 | `2175629958, 147802191, 2425104019, 853609596, 4132240727, 4089413332` |
| rperle_tpa_simpar2 | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| solve() library call | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| testsolve() library call | `608833221, 1812491834, 2623259368, 3887640181, 811678161, 2382318639` |
| example_search_tpa | `1146796796, 3308305028, 386855827, 2694500999, 2221614380, 1025642763` |
| example_bnb_tpa | `3809509318, 1900386143, 1103642148, 1010814338, 790187922, 3654332215` |
| testsolve_example_search | `2346975725, 1224100873, 2386202199, 4246821866, 1768963681, 2406381760` |
| testsolve_example_bnb | `559300817, 691733575, 3730937374, 1133024474, 2779640938, 790303042` |

The last four rows were renamed, not recaptured: the solvers MOCOMPASS
and MOPBnB became `ExampleSearchSolver` and `ExampleBnBSolver`, so
`mocompass_tpa`, `mopbnb_tpa`, `testsolve_mocompass` and
`testsolve_mopbnb` became `example_search_tpa`, `example_bnb_tpa`,
`testsolve_example_search` and `testsolve_example_bnb`. All four were
run under the new names on both venvs before the test was edited, and
matched these values exactly: the end seed does not depend on the
solver's name. Everything else in this file uses the names in force
when it was written.

`test_solution_sensitivity.py`'s `EXPECTED_SOLUTIONS`, old and new (its
`end_seed` is `testsolve_tpa`'s, above):

| Path | Before the fix | After the fix |
|---|---|---|
| 0 | `{(31, 6), (32, 6)}` | `{(32, 1), (32, 3)}` |
| 1 | `{(1, 8), (17, 7)}` | `{(12, 16), (16, 8)}` |
| 2 | `{(7, 4), (8, 4), (9, 3)}` | `{(9, 3), (11, 0)}` |
| 3 | `{(26, 16), (26, 17)}` | `{(18, 18), (18, 19), (19, 16), (19, 17)}` |

---

## Historical: post §12 step 8 stage 2 (testsolve()'s aggregation), pre testsolve() role-layout fix

The four `testsolve` values in this section are the ones the
role-layout fix replaced. Like every historical section here, they are
a record, not restorable defaults: they were produced with path 0's
oracle stream sharing a seed with a solver stream, and with every
path's streams depending on `--isp`.


**Capture conditions:** `.venv-baseline`, CPython 3.10.21, this repo
installed editable, captured from the source tree directly. Commit:
`9155674` on the `pymoso-migration` branch (step 8 stage 2 itself, the
commit immediately prior to this regeneration). Command: `pytest
tests/test_golden.py tests/test_solution_sensitivity.py -v`; also
cross-checked against an independent capture under `.venv-dev` (CPython
3.14) -- identical values, as expected (this arithmetic has no
Python-version dependence).

**Captured against `docs/rng-interface-design.md` §12 step 8, stage 2:**
`chnutils.testsolve()`'s own reported `endseed` is now the real
aggregated high-water mark across every `isp` path -- each path's own
`RASolver.solve()`/MOCOMPASS/MOPBnB result dict carries its local
`oracle_high_water_mark` (`Oracle.get_high_water_mark()`, crossing the
`--proc` worker boundary as an ordinary picklable int), and `testsolve()`
combines them as `max(t*ISP_STRIDE + local_max_t for t in
range(isp))`, then reports `jump_seed_n(orc_root, that)` -- replacing
`get_testsolve_prnstreams`'s reservation-based "next `isp` slot" value.
Only `testsolve_tpa`/`testsolve_mocompass`/`testsolve_mopbnb` and the
`testsolve()` library case moved in this pass; every `solve()`-path
case (already on the real formula since stage 1) is untouched --
confirmed directly, not assumed (`rperle_tpa`/`rminrle_tpa`/`rpe_tpa`/
`rspline_simpleso`/`rperle_tpa_crn`/`rperle_tpa_seed2`/
`rperle_tpa_simpar2`/`mocompass_tpa`/`mopbnb_tpa`/the `solve()` library
case all identical to the stage-1 capture below). The three `testsolve_*`
cases used to be bit-identical to each other and to the `testsolve()`
library case -- the `testsolve()`-shaped analog of the `mocompass_tpa`/
`mopbnb_tpa` collision stage 1 closed -- and now diverge, confirmed
before regenerating: the three-way match breaks, each reflecting its
own solver's real consumption across all 4 `isp` paths, as expected
going in.

`test_solution_sensitivity.py`'s `end_seed` also moved in this pass, for
an unrelated reason worth stating precisely: not from `EXPECTED_
SOLUTIONS` (unaffected, already regenerated in the replication-
independence-fix pass), but because `endseed` is now sensitive to
`ranx0`/which `x0` a solver actually searched from -- a new property as
of step 8 (the mechanism this document's earlier passes reported could
never see this; see `docs/end-seed-scope.md`'s own "Partially
superseded" note). Confirmed, not coincidental: this value now equals
`testsolve_tpa`'s own end seed exactly, because both are the identical
computation (same tester/solver/budget/seed/isp/proc/crn, both
`ranx0=True`).

**These values are now a fully settled baseline under §12 step 8's own
design** -- both stages are landed; nothing currently scheduled moves
these again.

| Case | End seed |
|---|---|
| rperle_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rminrle_tpa | `3101702307, 2274224287, 2252695779, 2887425027, 4188880773, 159891216` |
| rpe_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rspline_simpleso | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` |
| testsolve_tpa | `3654817394, 2187457693, 4207556677, 3585739323, 608476310, 697649114` |
| rperle_tpa_crn | `1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043` |
| rperle_tpa_seed2 | `2175629958, 147802191, 2425104019, 853609596, 4132240727, 4089413332` |
| rperle_tpa_simpar2 | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| solve() library call | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| testsolve() library call | `1744404958, 3393812160, 2418775421, 509218500, 1460079748, 3249260099` |
| mocompass_tpa | `1146796796, 3308305028, 386855827, 2694500999, 2221614380, 1025642763` |
| mopbnb_tpa | `3809509318, 1900386143, 1103642148, 1010814338, 790187922, 3654332215` |
| testsolve_mocompass | `2422441504, 1336929696, 2999367015, 1940896654, 3321487088, 1155700982` |
| testsolve_mopbnb | `3460682149, 1730614318, 2650224894, 981491354, 3020985147, 1482257229` |

`rperle_tpa`/`rperle_tpa_simpar2` still match *each other* (`--simpar`
doesn't enter the coordinate formula, §3.4), and continue to coincide
with `rpe_tpa` (a `crnflag=False` end seed depends only on
`(Oracle._iteration, m)` at the last `hit()` call, the same for both
solvers at the same `nu`). `test_solution_sensitivity.py`'s
`test_testsolve_ranx0_solution_sets_match_baseline`'s `end_seed` --
`3654817394, ...` -- is the same value as `testsolve_tpa` above, for
the reason given above; not reproduced in this table since it isn't one
of `test_golden.py`'s own `CASES`.

---

## Historical: post §12 step 8 stage 1 (Oracle.get_endseed()), pre-stage-2

**Capture conditions:** `.venv-baseline`, CPython 3.10.21, this repo
installed editable, captured from the source tree directly. Commit:
`adfc156` on the `pymoso-migration` branch (step 8 stage 1 itself, the
commit immediately prior to that regeneration). Command: `pytest
tests/test_golden.py tests/test_solution_sensitivity.py -v`; also
cross-checked against an independent capture under `.venv-dev` (CPython
3.14) -- identical values.

**Superseded by §12 step 8 stage 2** (`testsolve()`'s own aggregation,
see the "Current values" section above) for the four `testsolve_*`/
`testsolve()`-library cases only -- every `solve()`-path value below is
identical to the current one, unaffected by stage 2. Retained for
provenance only, not as a target to restore.

**Captured against `docs/rng-interface-design.md` §12 step 8, stage 1
(the commit immediately prior to that regeneration):**
`Oracle.get_endseed()` -- a tracked high-water mark of every oracle-role
coordinate actually passed to a replication, oracle-role only (§8.2's
own explicit scope) -- wired into `RASolver.solve`/`rasolve` and
MOCOMPASS/MOPBnB's own `solve()` methods, replacing `crn_advance()`'s
call-count-only reporting (`self._iteration * ITER_STRIDE`). Confirmed
before regenerating, not assumed: `mocompass_tpa`/`mopbnb_tpa` now
diverge from each other (previously identical despite verified-
different internal consumption -- the concrete gap this stage exists to
close). `rperle_tpa_crn` moved too, **contrary to this document's own
pre-registered expectation that it wouldn't** -- traced to
`RASolver.rasolve()`'s own trailing, unconditional `crn_advance()` call
past the last iteration that actually ran (full account in
`docs/rng-interface-design.md` §8.2's "Wired in as of step 8 stage 1"
note). The new value is a correct tightening (nothing beyond it was
ever touched), not a regression -- the old value was simply more
conservative than it needed to be for the CRN branch specifically. Every
`crnflag=False`/CRN case moved in this pass. `testsolve_tpa`/
`testsolve_mocompass`/`testsolve_mopbnb` and the `testsolve()` library
case did **not** move -- unaffected by this stage, deliberately: they
still report `get_testsolve_prnstreams`'s reservation value, which
stage 2 (aggregating each `isp` path's own high-water mark across the
`--proc` worker boundary, not yet landed) will replace.

**These values are still an intermediate state, not a settled
baseline.** `testsolve()`'s own end seed is still `get_testsolve_
prnstreams`'s reservation value (unaffected by this stage, above) --
it moves once step 8 stage 2 lands. `test_solution_sensitivity.py`'s
values are unaffected by this stage entirely (see the capture-
conditions note above) and are not reproduced below.

| Case | End seed |
|---|---|
| rperle_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rminrle_tpa | `3101702307, 2274224287, 2252695779, 2887425027, 4188880773, 159891216` |
| rpe_tpa | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| rspline_simpleso | `2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931` |
| testsolve_tpa | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| rperle_tpa_crn | `1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043` |
| rperle_tpa_seed2 | `2175629958, 147802191, 2425104019, 853609596, 4132240727, 4089413332` |
| rperle_tpa_simpar2 | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| solve() library call | `900181699, 3252648471, 384599192, 813079481, 747618736, 882165191` |
| testsolve() library call | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| mocompass_tpa | `1146796796, 3308305028, 386855827, 2694500999, 2221614380, 1025642763` |
| mopbnb_tpa | `3809509318, 1900386143, 1103642148, 1010814338, 790187922, 3654332215` |
| testsolve_mocompass | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| testsolve_mopbnb | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |

`rperle_tpa`/`rperle_tpa_simpar2` still match *each other* (`--simpar`
doesn't enter the coordinate formula, §3.4), and now coincide with
`rpe_tpa` too -- not an error, checked: a `crnflag=False` end seed
depends only on `(Oracle._iteration, m)` at the last `hit()` call, and
`calc_m(nu)` is the same function of `nu` for every `RASolver`-family
solver; `rperle_tpa`/`rpe_tpa` both ended this run at `nu=13`.

---

## Historical: post replication-independence fix, pre-step-8-stage-1

**Capture conditions:** `.venv-baseline`, CPython 3.10.21, this repo
installed editable, captured from the source tree directly. Commit:
`1eca229` on the `pymoso-migration` branch (the replication-independence
fix itself, the commit immediately prior to that regeneration). Command:
`pytest tests/test_golden.py tests/test_solution_sensitivity.py -v`;
also cross-checked against an independent capture under `.venv-dev`
(CPython 3.14) -- identical values.

**Superseded by §12 step 8 stage 1** (`Oracle.get_endseed()`, see the
"Current values" section above) -- these values still reported
`crn_advance()`'s call-count-only position, not a real high-water mark
of actual consumption. Retained for provenance only, not as a target to
restore.

**Captured against `docs/rng-interface-design.md` §12's unnumbered
prerequisite-fix entry, landed immediately before step 8:**
`offset_within_iteration`'s `replication` field went from stride 1 (no
reserved margin -- replications sharing more than one raw draw per
`g()` call, which every built-in problem does, were not actually
independent) to a real `2**REPL_RESERVE_BITS`-wide reserve per
replication. Only the cases whose `nu` (RA iteration count at budget
exhaustion) actually changed moved -- checked directly, not assumed: a
`crnflag=False` end seed here is purely a function of `nu`
(`crn_advance()`'s own call-count-only reporting, §8.2's still-open
gap), not of what `hit()` actually drew, so a case only moves if the
fix's changed draws fed back into that specific solver's own
sample-driven control flow. `rperle_tpa`/`rminrle_tpa`/
`rperle_tpa_seed2`/`rperle_tpa_simpar2` and the `solve()` library call
moved; `rpe_tpa`/`rspline_simpleso`/`testsolve_tpa`/`mocompass_tpa`/
`mopbnb_tpa`/`testsolve_mocompass`/`testsolve_mopbnb`/the `testsolve()`
library call did not (their own `nu`, or `testsolve()`'s reservation-
based end seed entirely, were unaffected). `rperle_tpa_crn` is
unchanged, deliberately -- the CRN branch is untouched by this fix, just
as it was untouched by step 4b.

| Case | End seed |
|---|---|
| rperle_tpa | `596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049` |
| rminrle_tpa | `3224044943, 1227141655, 2220611050, 1504589054, 2829780440, 108189859` |
| rpe_tpa | `596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049` |
| rspline_simpleso | `3728532268, 988545039, 1631700325, 1143954198, 2209269908, 1591407377` |
| testsolve_tpa | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| rperle_tpa_crn | `3777646647, 1837464056, 4204654757, 664239048, 4190510072, 2959195122` |
| rperle_tpa_seed2 | `377212572, 86764798, 2286711681, 1003464262, 2322852652, 1042342679` |
| rperle_tpa_simpar2 | `596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049` |
| solve() library call | `596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049` |
| testsolve() library call | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| mocompass_tpa | `1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925` |
| mopbnb_tpa | `1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925` |
| testsolve_mocompass | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| testsolve_mopbnb | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |

`rperle_tpa`/`rperle_tpa_simpar2` still match *each other*, confirmed
explicitly, not just each against its own fresh baseline -- `--simpar`
still doesn't enter the coordinate formula (§3.4). `rperle_tpa` and
`rpe_tpa` now coincide too, exactly (not an error, checked): both ended
this run at `nu=13`, and a `crnflag=False` end seed depends only on
`nu`, not on which solver produced it.

`tests/test_solution_sensitivity.py`'s `EXPECTED_SOLUTIONS` moved in
this same pass -- expected, and the reason that golden exists: it is
sensitive to consumption changes this fix made, which end-seed matching
alone cannot see (`docs/end-seed-scope.md`).

---

## Historical: post step 4b coordinate cutover, pre-replication-reserve-fix

**Capture conditions:** `.venv-baseline`, CPython 3.10.21, this repo
installed editable, captured from the source tree directly. Commit:
`18ab096` on the `pymoso-migration` branch (the step 4b cutover itself,
the commit immediately prior to that regeneration). Command: `pytest
tests/test_golden.py tests/test_solution_sensitivity.py -v`; also
cross-checked against an independent capture under `.venv-dev` (CPython
3.14) -- identical values, as expected (this arithmetic has no
Python-version dependence).

**Captured against `docs/rng-interface-design.md` §12 step 4b:**
`MAX_RI`'s reservation walk removed from `get_testsolve_prnstreams`
(`isp` now a direct `ISP_STRIDE`-based offset), and the `crnflag=False`
default path cut over from the temporary running-ordinal compatibility
encoding to `offset_within_iteration`/`point_code` -- fixing the order-
dependence defect §2 of that document proves is a defect, not a
characteristic to preserve. Every `crnflag=False` case below moved;
`rperle_tpa_crn` is the one case that didn't, deliberately -- the CRN
branch is untouched by step 4b, and its continued, unmodified value
here is itself a regression check that the cutover didn't leak into it
(§8.1's own point).

**Superseded, not by §8.2's endseed-formula wiring (still not landed)
but by a defect found in this cutover itself:** `offset_within_
iteration`'s `replication` field was packed at stride 1, with no
reserved margin, on the unstated assumption that a single replication
consumes exactly one raw draw. No built-in problem's `g()` satisfies
that, so replications sharing the same point were not actually
independent below these values' capture -- see the "Current values"
section above and `docs/rng-interface-design.md`'s unnumbered §12
prerequisite entry (immediately before step 8) for the full
reproduction and fix. These values remain here for provenance only, not
as a target to restore.

| Case | End seed |
|---|---|
| rperle_tpa | `3003961408, 3529909391, 14538032, 3603919910, 566682685, 1235016484` |
| rminrle_tpa | `927434978, 1593504038, 2143021818, 1749489845, 1330187821, 2371554242` |
| rpe_tpa | `596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049` |
| rspline_simpleso | `3728532268, 988545039, 1631700325, 1143954198, 2209269908, 1591407377` |
| testsolve_tpa | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| rperle_tpa_crn | `3777646647, 1837464056, 4204654757, 664239048, 4190510072, 2959195122` |
| rperle_tpa_seed2 | `894854942, 3096943843, 1340932684, 2817164986, 4019721871, 366681695` |
| rperle_tpa_simpar2 | `3003961408, 3529909391, 14538032, 3603919910, 566682685, 1235016484` |
| solve() library call | `3003961408, 3529909391, 14538032, 3603919910, 566682685, 1235016484` |
| testsolve() library call | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| mocompass_tpa | `1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925` |
| mopbnb_tpa | `1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925` |
| testsolve_mocompass | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |
| testsolve_mopbnb | `756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130` |

`rperle_tpa`/`rperle_tpa_simpar2` still matched *each other*, confirmed
explicitly, not just each against its own fresh baseline -- `--simpar`
still doesn't enter the coordinate formula (§3.4).

---

## Historical: post jump-ahead-fix, pre-coordinate-cutover capture

The values below are what `CASES` held between the jump-ahead fix
landing and step 4b's coordinate cutover (the section above). Every
`crnflag=False` value moved at that cutover, for the reason given
above -- these are not restorable defaults; the pre-cutover non-CRN
walk was order-dependent, which `docs/rng-interface-design.md` §2
establishes is a defect, not a specification.

| Case | Post jump-ahead-fix, pre-cutover end seed |
|---|---|
| rperle_tpa | `4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938` |
| rminrle_tpa | `33132303, 325849388, 376624132, 1563924626, 293517807, 795864341` |
| rpe_tpa | `3464732221, 1507014170, 850131796, 3585675128, 2782941437, 844928957` |
| rspline_simpleso | `3294576687, 175234757, 49170740, 679432683, 2711532206, 2761197391` |
| testsolve_tpa | `1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063` |
| rperle_tpa_crn | `3777646647, 1837464056, 4204654757, 664239048, 4190510072, 2959195122` |
| rperle_tpa_seed2 | `4131271395, 3226219906, 777515709, 589263233, 2312345461, 1567227549` |
| rperle_tpa_simpar2 | `4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938` |
| solve() library call | `4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938` |
| testsolve() library call | `1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063` |
| mocompass_tpa | `1613792524, 277130510, 1927400324, 3116048775, 1439906304, 2566931280` |
| mopbnb_tpa | `1428784311, 1122505905, 2703958324, 3312341562, 3339561538, 1282989044` |
| testsolve_mocompass | `1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063` |
| testsolve_mopbnb | `1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063` |

None of these has all six components divisible by 256 -- confirmed
directly, not just asserted -- unlike every pre-jump-ahead-fix value
below, which does.

---

## Historical: this migration's own pre jump-ahead-fix capture

The values below are what `CASES` held between this migration's phase-0
capture commit and the jump-ahead fix landing (i.e., exactly what's
described in the rest of this file's prose above, before the fix).
Every one of these ten end seeds has all six components divisible by
256, the exact signature of the float64 precision loss documented in
KNOWN_ISSUES.md issue 1 -- captured from this branch's own source tree,
not a wheel, unlike the 1.0.4 baseline further below.

| Case | Pre-fix end seed (this migration) |
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
