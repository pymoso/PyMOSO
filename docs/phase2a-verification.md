<!--
Provenance note (added when this file was ported onto pymoso-migration;
it did not exist on this branch before, only on old-work, this
project's earlier fork -- see "Commit outstanding phase 2a/3 artifacts
before migrating to pymoso/master", e273e14):

This describes work done against old-work's codebase, before this
project moved onto the canonical repository (github.com/pymoso/PyMOSO).
File paths and line numbers below (e.g. `mrg32k3a.py:319-365`) refer to
that fork's layout, not necessarily this branch's current files. The
scratch/ scripts it cites were throwaway and gitignored even there
(see its own item 5's closing note) -- they were never committed and
are not recoverable.

Ported rather than left as a dangling citation because
test_jump_ahead.py, test_max_ri.py, and test_infeasible_x0.py all cite
specific items here by number as "how this was originally found." That
history is real and worth keeping. But the CURRENT authority for
whether these properties still hold on this branch is not this file --
it's the permanent regression tests themselves, plus, for issue 1
specifically, a direct re-check against a real PyPI 1.0.8 install:

- Item 1 (jump-ahead): re-verified by tests/test_jump_ahead.py's
  brute-force/exact-matrix-power equivalence tests (independent of
  this file, driving the actual current mrg32k3a()/mat333mult/
  mat311mod), and by KNOWN_ISSUES.md issue 1's direct 1.0.8 check
  (divisible-by-256 end seeds, confirmed on a real install).
- Item 2 (--simpar crash): superseded -- resolved upstream by 917bf06,
  independently of this project. See KNOWN_ISSUES.md issue 2 and
  docs/upstream-simpar.md, not this file, for the current picture.
- Item 3 (MAX_RI): re-verified by tests/test_max_ri.py at the time, and
  by KNOWN_ISSUES.md issue 2's direct 1.0.8 source check (bare
  `max_RI = 200`, still unenforced) -- the latter still holds, but
  test_max_ri.py itself was deleted when MAX_RI was removed entirely
  from this branch (§12 step 4b: the reserved-window guard it tested
  was replaced by `point_code`/`offset_within_iteration`,
  collision-free by construction, not strengthened in place). Current
  coverage: tests/test_oracle_visit_sync.py's
  test_iteration_and_replication_never_overflow_one_isp_stride_block /
  test_no_collision_between_isp_paths_at_iteration_counts_well_beyond_max_ri.
- Item 4 (infeasible x0): re-verified by tests/test_infeasible_x0.py,
  and by KNOWN_ISSUES.md issue 4's direct 1.0.8 behavioral check
  (same KeyError/"Unable to run accel()" outputs reproduced live).
- Item 5 (Oracle.bump()): not independently re-verified on this
  branch by any permanent test as of this porting; read as historical
  only unless re-checked. (On `pymoso-migration`, `bump()` was later
  removed outright -- §12 step 6b, past this release's own `b637a3e`
  boundary -- but that removal is not part of `release-1.1.0`:
  `Oracle.bump()` is still present and unchanged here. Don't assume
  `pymoso-migration`'s KNOWN_ISSUES.md issue numbering applies on this
  branch either -- this branch's own issue 14 is the unrelated
  MOCOMPASS/MOPBnB exclusion.)

Body below is otherwise unedited from old-work.
-->

# PyMOSO Phase 2a — Verification

Converts the open questions from `docs/phase1-review.md` into facts, via
self-contained reproductions. Throwaway scripts live in `scratch/`
(gitignored) — each finding below cites the script that produced it.

---

## 1. MRG32k3a jump-ahead: incorrect for realistic seeds

**Answer:** The shipped `jump_substream`/`get_next_prnstream`
(`prng/mrg32k3a.py:319-365`) are wrong. They agree with an exact
(arbitrary-precision) implementation of the same jump only when seed
components are small (e.g. the toy default seed `(12345,)*6`, or
`(1,2,3,4,5,6)`). For realistic seeds — i.e. any seed after even one real
jump — they diverge, with errors from hundreds up to a large fraction of
the modulus after chained jumps.

**Evidence** (`scratch/task1_jumpahead.py`, `scratch/task1_stress.py`,
`scratch/task1_mechanism.py`):

- Derived the exact recurrence as two 3×3 companion matrices over Python's
  arbitrary-precision ints, from the recurrence itself:
  `x1[n] = a12*x1[n-2] - a13n*x1[n-3]`, `x2[n] = a21*x2[n-1] - a23n*x2[n-3]`
  (read directly off `mrg32k3a()`, `mrg32k3a.py:79-93`). Validated the
  matrix-power jump-by-N against brute-force single-stepping for
  N=10³,10⁴,10⁵ — exact match, 0 mismatches.
- 200 random-seed trials: shipped `jump_substream` (2^76) mismatched the
  exact result in **200/200** cases; shipped `get_next_prnstream` (2^127)
  mismatched in **200/200**. 20 chains of 50 successive jumps: **20/20**
  mismatched, with drift growing each jump.
- **Mechanism, pinned down exactly**: `mat333mult`
  (`mrg32k3a.py:273-293`) sums three float products of matrix elements
  (~10⁹) times seed components (~10⁹), giving row sums ~2^62-2^63. float64
  has only 53 bits of exact-integer precision (2^53 ≈ 9.0×10¹⁵); at
  2^62-2^63 the ULP is 1024-2048. The rounded sum is then reduced mod
  m1/m2 (`mat311mod`, `mrg32k3a.py:296-316`), which subtracts multiples of
  the exactly-representable modulus, so the low bits below the ULP stay
  zero — exactly the "components divisible by 256" signature CLAUDE.md
  documents. 195-199 of 200 trial outputs had all six seed components
  divisible by 256.
- Scoped the blast radius: the plain single-step generator `mrg32k3a()`
  (used for every actual simulated replication) is **not** affected —
  validated exact against 500 random full-range seeds and a 2000-step
  chain. Only the jump-ahead matrix path is broken, i.e. every
  `crn_advance()` call after the first in a run. Golden tests all start
  from tiny seeds, so their first 2^127 jump is exact by luck; every
  subsequent RA-iteration jump silently drifts and the goldens just
  capture that drift as "expected."

**Confidence:** High. Self-contained (no external reference values),
cross-checked against brute force.

---

## 2. `--simpar>1` with `--crn`: crashes unconditionally, independent of `--crn`

**Answer:** `Oracle.hit()`'s parallel branch (`chnbase.py:1217`) calls
`get_next_prnstream(start_seed)` with one argument, but the function
requires `(seed, crn)`. This raises `TypeError` deterministically whenever
`nproc = min(simpar, m) >= 2` — which happens on essentially the first
real `estimate()` call for any `simpar>=2` run, since `calc_m(nu)` is
already ≥2 by RA iteration 1 for any reasonable `mconst`. The `TypeError`
is swallowed by `estimate()`'s generic exception handler → `sys.exit()` →
re-caught by `RLESolver.spsolve`'s bare `except:` (`chnbase.py:807`) →
`sys.exit()` again, producing a misleading double "Unable to simulate /
Unable to run accel()" instead of a real traceback.

**Evidence** (live repro, no script needed):

- `pymoso solve --budget=500 --simpar=2 --param mconst 5 ProbTPA RPERLE 40
  40` fails immediately: `get_next_prnstream() missing 1 required
  positional argument: 'crn'`.
- Confirmed **pre-existing in the genuine PyPI 1.0.4 wheel** — downloaded
  fresh via `uv pip install pymoso==1.0.4 --no-cache` into an isolated
  venv (not this repo's editable install; see caveat below) and
  reproduced the identical crash and message. Not a modernization
  regression — `--simpar>1` has apparently never worked in any published
  version.

Since parallel execution can't run at all, CRN correctness was separately
verified in the only path that does execute (`simpar=1`), using a
synthetic oracle that returns its raw draw as the "objective" so stream
position is directly observable (`scratch/task2_crn_serial.py`): under
CRN, three different candidate points evaluated within one RA iteration
draw identical values (correct); across iterations, after
`crn_advance()`, the baseline correctly changes. CRN itself is sound; the
`simpar` machinery around it is not.

**Confidence:** High on the crash — fully reproducible, root-caused to
one line, confirmed upstream. High on serial CRN correctness — direct
construction and observation.

---

## 3. `max_RI = 200`: enormous headroom in practice; breach is silent stream reuse

**3a — how much headroom.** (`scratch/task3_headroom.py`) Instrumented
final RA-iteration counts (`self.nu`) across budgets 1,000-400,000 for
RPERLE/RPE/RMINRLE on ProbTPA and RSPLINE on ProbSimpleSO, all at default
`mconst=2`. Counts grow logarithmically in budget (`calc_m(nu) =
ceil(mconst·1.1^nu)` grows geometrically): at budget=400,000, only 68-92
iterations are reached, far short of 200. Directly computing the minimum
possible cumulative budget from `calc_m` (assuming just one evaluation
per iteration — a lower bound; real runs do many more per iteration via
the neighbor/pli search): reaching iteration 200 requires **at least
~4.2×10⁹** simulation calls, with the single point evaluation at
iteration 200 alone needing ~3.8×10⁸ replications. At default settings no
realistic budget gets near 200; only a deliberately tiny `mconst` and/or
a budget in the billions would reach it.

**3b — what happens on breach.** (`scratch/task3_maxri_breach.py`) No
exception, no check anywhere — `max_RI` appears only at
`chnutils.py:162` and `:173`, nowhere else in the codebase. Demonstrated
the overlap directly using the real `Oracle.crn_advance()` method: built
streams for 3 ISPs via `get_testsolve_prnstreams`, then drove ISP 0's
Oracle through repeated `crn_advance()` calls exactly as
`RASolver.rasolve` would (`chnbase.py:212`). **After exactly 201 RA
iterations, ISP 0's rng state becomes bit-for-bit identical to ISP 1's
starting seed** — confirming the reservation is exactly 200 iterations
wide, and iteration 201 walks straight into ISP 1's territory (continuing
to overlap ISP 1's own draws from there on).

**Confidence:** High on the headroom-budget number (exact, from the
actual `calc_m` formula). High on the breach mechanism (drives the real
production `crn_advance()`, not a reimplementation) — though a full
multi-hour real algorithmic solve literally reaching nu=200 with search
overhead included was not run, given the compute cost; the standalone
harness exercises the identical code path so this should generalize, but
flagging the gap explicitly.

---

## 4. Infeasible x0: KeyError confirmed; refines the phase-1 analysis by solver

**Answer:** `get_min`'s `min(mcS | {self.x0}, key=lambda t:
self.gbar[t][k])` (`chnbase.py:238`) always includes `x0` unconditionally
in its input, so that input is never empty — the `except ValueError` in
`RPERLE.pe`/`RPE.pe`/`RMINRLE`'s equivalent is **dead code**, unreachable
via infeasible x0. The real failure is `KeyError`, since `x0` is absent
from `self.gbar` (`upsample` excludes infeasible points).

- **RPE** (plain `RASolver`, no wrapping try/except around `spsolve`):
  raw, unhandled `KeyError: (-100, -100)` with a full traceback reaching
  the user — reproduced live.
- **RPERLE, RMINRLE** (`RLESolver` subclasses): the same `KeyError` is
  caught one level up by `RLESolver.spsolve`'s bare `except:`
  (`chnbase.py:807-811`), producing `"Unable to run accel(). Message:
  (-100, -100)"` then `sys.exit()` — no raw traceback, but not the
  intended "Is x0 feasible?" message either.
- **RSPLINE**: genuinely correct and unaffected — it never calls
  `get_min`; it checks `if not warm_start` after `upsample`
  (`solvers/rspline.py:48-52`) and prints the accurate `"Empty warm
  start. Is x0 feasible?"`.

**Evidence** (`scratch/task4_infeasible_x0.py`): reproduced for all four
built-in solvers with real infeasible x0 (`(-100,-100)` for ProbTPA's
[0,50] domain, `(-1000,)` for ProbSimpleSO's [-100,100] domain), full
tracebacks captured.

**Confidence:** High — direct reproduction, not inference.

---

## 5. `Oracle.bump()`: works correctly as documented; one real gap vs. `hit()`

**Answer:** `bump()` is not broken. Exercised directly against `hit()`
from identical rng/CRN starting states across m∈{1,2,5,13} and
crn∈{False,True} (`scratch/task5_bump.py`): bump()'s raw per-replication
observations, hand-aggregated (mean/variance), match `hit()`'s internal
aggregation exactly, and both leave the rng in the identical end state
(same `crn_nextobs()`-per-replication + final `crn_check()` pattern).
Feasibility semantics (`all(feas)`) match too.

**Spec** (there is no in-tree caller to read as documentation, so this is
derived from direct exercise):

- Returns `(isfeas: bool, obs: list[tuple[float, ...]])` — `len(obs) ==
  m`, each entry the raw per-replication objective tuple, vs. `hit()`'s
  `(isfeas, obmean, obse)` aggregated stats.
- Consumes the rng identically to `hit()`: one `crn_nextobs()` per
  replication, then one `crn_check()` at the end. CRN semantics match
  `hit()` exactly.
- Does **not** touch `num_calls`, `gbar`, or `sehat` — those live on the
  solver (`RASolver`), not `Oracle`. Like `hit()`, bookkeeping is the
  caller's responsibility, mirroring what `RASolver.estimate()` does
  after calling `hit()`. An out-of-tree solver calling `bump()` directly
  must replicate that bookkeeping itself.
- Has **no `simpar`/parallel branch at all** — confirmed by source
  inspection and by setting `orc.simpar=4` and observing it still runs
  serially in under a millisecond. This is the one real, confirmed
  divergence from `hit()`: any out-of-tree solver expecting `bump()` to
  also parallelize under `simpar>1` gets silent serial execution, not an
  error.
- Incidental finding while comparing: `hit()`'s own `m==1` branch returns
  `obse` as a `list` (`chnbase.py:1181`) while its `m>1` branch returns a
  `tuple` (`chnbase.py:1197`) — a small internal type inconsistency in
  `hit()`, unrelated to `bump()`; the docstring says "tuple of float."

**Confidence:** High — direct, repeated, byte-level comparison against
`hit()`'s own aggregation, not just code reading.

---

## Side finding: baseline venvs are currently editable installs, not real 1.0.4

Not one of the five questions, but relevant to trusting future
verification work: `.venv-baseline` and `.venv-wheel` are currently
**editable installs of this dev repo**
(`direct_url.json: {"editable": true, "url":
"file:///home/kyle/Documents/PyMOSO"}`), not immutable copies of the real
PyPI 1.0.4 wheel — most likely because `uv pip install pymoso==1.0.4`
reused a stale cache entry from an earlier editable install under the
same version number. Network access works (verified), and a fresh
`--no-cache` install correctly pulls the genuine wheel from
`files.pythonhosted.org`. This doesn't call the existing
`tests/golden/` values into question — they're frozen text, presumably
captured correctly at the time — but re-capturing or re-diffing against
true 1.0.4 semantics won't work with these two venvs as they stand;
rebuild with `--no-cache` first.
