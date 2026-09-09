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
  was ever exercised (see KNOWN_ISSUES.md issue 7). Both match their
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

### Current values (post replication-independence fix)

**Capture conditions:** `.venv-baseline`, CPython 3.10.21, this repo
installed editable, captured from the source tree directly. Commit:
`1eca229` on the `pymoso-migration` branch (the replication-independence
fix itself, the commit immediately prior to this regeneration). Command:
`pytest tests/test_golden.py tests/test_solution_sensitivity.py -v`;
also cross-checked against an independent capture under `.venv-dev`
(CPython 3.14) -- identical values, as expected (this arithmetic has no
Python-version dependence).

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

**These values are still an intermediate state, not a settled
baseline -- read this before relying on them**, for the same reason the
step-4b entry below already gave: `crn_advance()` still reports
`endseed` based only on its own call count, not a real high-water mark
of what a run actually consumed via `hit()`'s own coordinate
computation (`docs/rng-interface-design.md` §8.2, not yet wired into
`chnutils.py`/`RASolver.rasolve`'s reporting -- §12's own step 8).
**Every `crnflag=False` value below will move again** when that lands.

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
