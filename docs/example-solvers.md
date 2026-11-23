# Known issues: the example solvers

`ExampleSearchSolver` (`pymoso/solvers/examplesearch.py`), the example
search-based solver, and `ExampleBnBSolver`
(`pymoso/solvers/examplebnb.py`), the example branch-based solver, are
two `MOSOSolver`s from prior work, written against roughly the 1.0.8
API. They are an implementation example only: do not use them for
serious solving or testing at this time. Neither is described in the
README, deliberately: describing them there would present them as
supported.

They were brought in-tree as a **compatibility-only** pass: the fixes
that landed with them (a Python 3.11+ `random.sample()` incompatibility,
a library-hostile `sys.exit()` on missing parameters, a silent-corruption
interaction with `--crn`) make the files run correctly on the current
branch. Nothing else about their behaviour has been reviewed.

This is not `KNOWN_ISSUES.md`: that file tracks defects in PyMOSO's
shipped *framework* code across real released versions, anchored to
actual PyPI history. These are caveats in brand-new example code nobody
has released. Deeper narrative and evidence for all three items below —
plus the `random.sample()`/`sys.exit()`/`--crn` findings this doc doesn't
repeat — lives in `docs/rng-interface-design.md`, sections 4.1-4.3, where
these two files were analyzed as evidence for the RNG interface
redesign: two `MOSOSolver`s written against the 1.0.8 API, before this
redesign.

## How the items are sorted

Every item below is a defect on the code's own terms: something the code
sets out to do and does not do, or does at a cost its own budget does not
bound. None is listed only because the code differs from a published
algorithm. Where earlier versions of this document made that comparison,
the comparison has been removed and the defect is stated without it.

## 0. The branch-based solver's subregions are not regions

**The headline finding about this solver** (Phase 7 step 6,
2026-10-18). The solver is built around partitioning: it branches the
feasible region into subregions, samples each, and prunes the
subregions that cannot hold efficient points. That a pruned subregion
is a *region*, a contiguous piece of the space, is what makes pruning
it informative.
Here, `get_isubreg` builds subregion `i` as
`set(islice(mcX, i, xcard, B))`: every B-th point of a Python set in
its iteration order, which follows the points' hashes, not their
positions. Each "subregion" is a sample scattered over the whole box.
Measured on {0..10}^2 with `B = 2`: both first-level subregions span 0
to 10 in both coordinates (61 and 60 points, interleaved). Pruning one
removes a scattered sample, so the solver is global random sampling
with elimination, not the partitioning its own structure describes. A
structural defect, not an implementation slip beside items 2 and 2b.
Not fixed. Any result obtained with `ExampleBnBSolver` says
nothing about partition-and-bound (docs/plateau-problems.md uses it
only as "a non-local sampler").

## 1. The search-based solver materializes the entire feasible region

`solve()` builds `mcD = set(product(*arglist))` over `[lb, ub]^dim` up
front. This doesn't scale to large `--param lb`/`--param ub` boxes —
memory and time grow with the full box size, not with how much of it the
search actually visits. Not fixed here.

## 2. The branch-based solver's `update_gbar` recomputes `sehat[x]` ignoring its own loop index

```python
for i, fi in enumerate(fx):
    sehat[x] = tuple((nx*(sehat[x][i] + gbar[x][i]**2) + ax*(s2[i] + fx[i]**2)) / (nx + ax)
                      for i in range(self.orc.num_obj))
```

The outer `i`/`fi` from `enumerate(fx)` are unused inside the inner tuple
comprehension, which shadows `i` and re-derives its own range. Looks like
a bug — observed producing a nonsensical downstream sample-size request
("16221167823086 additional replications") in a real test run, caught
harmlessly by the `rdiff*len(allspts) < budget` guard before it did
anything. Not fixed here.

## 2b. The branch-based solver asks for replications unbounded by its budget

Found in the same step. After each iteration `solve()` sets the next
sample size from the smallest gap between any two estimated values,
`R = max(R, ceil((z * maxS2 / (dmin / 2))^2))`, and the next iteration
takes `R` replications at every sampled point. The budget is checked
only between iterations, and the guard `rdiff * len(allspts) < budget`
covers only the top-up of points already sampled, not the next
iteration's sampling. Among a few dozen noisy estimates the smallest gap
is tiny, so `R` is enormous on any noisy problem: on the plateau
problem's control (no plateaus, `{0..59}^2`, sigma 1, budget 20,000) the
second iteration asked for 119,016 replications per point, and 306,783
to 680,614 on the plateaus (docs/plateau-problems.md). Item 2's
"16221167823086 additional replications" is the same mechanism. Also:
`get_reps` turns a standard error into a variance as `sex**2 *
sqrt(m)`; from a standard error of the mean that should be `sex**2 *
m`. Not fixed.

## 3. The search-based solver's `self.seeds` cross-point synchronization: intended policy, buggy implementation

The cross-point stream sharing `update_gbar` implements — points at the
same cumulative sample-effort level (`nx[x]`) drawing the same underlying
random numbers — is the solver's intended policy, confirmed
**deliberate** by the code's author, not an accident. The
*implementation* has a real bug: `self.seeds` is a single dict keyed by cumulative replication count,
shared across every point, and when two points reach the same count in
the same pass (common — `sar()` often returns identical `ax` for many
points at once), the second one's write clobbers the first's. A later
revisit can then pick up a checkpoint some *other* point's call happened
to write last, not its own history.

Not fixed here, and not a case of "someday" — it disappears by
construction under the coordinate-based RNG interface redesign's `sync=`
mechanism (`docs/rng-interface-design.md` §4.3): `stream_at(base_seed,
coordinate)` is a pure function, so two points supplying the same `sync`
value compute the identical stream independently, with nothing written
and therefore nothing to overwrite. Porting the solver onto that interface
is the actual fix; patching the dict now would be thrown away.

**Harmless today, and only because of item 4:** the checkpoints the
aliasing corrupts are passed to `setstate()`, which has no effect on any
result in this framework, so a clobbered checkpoint changes nothing. The
aliasing becomes live again the moment the checkpointing is made to take
effect by any route that keeps `self.seeds`; the `sync=` port above is
the route that removes it. That is a reason to keep this item, not to
drop it.

## 4. The search-based solver's checkpointing is dead code: inert on the MRG family, refused on Philox

`update_gbar`'s mechanism:

```python
start_state = self.seeds[start_num]
self.orc.rng.setstate(start_state)
isfeas, fx, sex = self.orc.hit(x, ax)
end_state = self.orc.rng.getstate()
self.seeds[end_num] = end_state
```

This assumes `setstate(start_state)` puts `hit()`'s replications, and
therefore `end_state`, under the caller's control. **In this framework
it controls nothing, and nothing warns.** `Oracle.hit()` computes every
replication's stream from `_orc_root`, which `set_crnflag()` reads from
`orc.rng` once; `chnutils.solve()` and `paths.run_path()` call
`set_crnflag()` before the solver is constructed. Each `g()` call is
handed a fresh stream at its replication's coordinate, never `orc.rng`,
and nothing in `hit()` reads `orc.rng` again. So `setstate()` changes no
result and `getstate()` records a position nothing uses.

When it went dead, by branch:

- **Default path (`crnflag=False`)**, the only one this solver runs,
  since it refuses `--crn`: at `docs/rng-interface-design.md` §12 step
  4b's cutover, commit `18ab096`, which routed it through
  `_hit_via_coordinate` and the fixed `_orc_root`.
- **`--crn` path:** at §12 step 9, commit `390ce4e`, which converged the
  CRN branch onto `_hit_via_coordinate`; from then `hit()` "no longer
  draws from or reseeds `Oracle.rng` on any branch".

**Measured (2026-11-23, Python 3.10 and 3.14, MRG32k3a and MRG31k3p,
both `crnflag` values).** Calling `setstate()` to an unrelated state
before every `hit()`, and the solver's own `setstate`/`hit`/`getstate`
pattern, each left every `hit()` result, the end seed and the
high-water mark unchanged. A `setstate()` *before* `set_crnflag()` did
change them, because that is where the root is read. `g()` was handed
`orc.rng` in 0 of 96 calls. A whole `ExampleSearchSolver` run
(`ProbTPA`, budget 1,000) gave the identical solution and end seed with
`setstate()` replaced by a no-op (200 calls swallowed) and with it
jumping to an unrelated state on every call.

**One defect, two symptoms.**

- **MRG family:** the calls run and do nothing.
- **Philox:** `Oracle.rng` is a raw `Philox4x32Stream`, which has
  neither method, so the first `getstate()` raised `AttributeError` from
  inside `solve()`. The solver now refuses Philox at construction, beside
  its `--crn` refusal, with an error naming the generator
  (`tests/test_example_solvers_compat.py`). The refusal tests for the
  methods, not for the generator's name.

The checkpointing is kept, not deleted: it is the case
`docs/rng-interface-design.md` §4.2-4.3 gives as the motivation for
`sync=`.

**The fix is a port, after 2.0.0, not a wording change.** `sync=`
provides what the checkpointing reaches for:
`self.orc.hit(x, ax, sync=nx[x])` gives every point at the same
cumulative sample effort the same streams, computed rather than stored.
That changes what the solver computes and moves its goldens, so it
needs the sign-off any behaviour change does (§4.3).

**Historical: the framework before the redesign.** Found while
implementing §12 step 3 (replacing `Oracle`'s CRN protocol). In the
1.0.8-era framework, `Oracle.crn_nextobs()`, which decided where each
replication's stream landed, always jumped from `self.crn_obsold`, a
value the `Oracle` tracked across *every* `hit()`/`bump()` call
regardless of which point called it, never from `self.rng`'s live
state. Instrumenting `crn_nextobs()` against a real run of this solver
confirmed `self.crn_obsold` never equalled `self.rng.getstate()` when it
was consulted. `setstate(start_state)` was honored for exactly one draw:
`g()` ran before `crn_nextobs()` did, so the *first* replication of a
`hit()` call drew from `start_state`, and every later replication, and
`end_state` itself, came from the shared `crn_obsold` walk. Under that
framework the synchronization was partly real: correct for each
checkpoint's first replication, not for the rest. Between step 3 and
step 4b the default path drew from `Oracle.rng` directly; what
`setstate()` did in that window was not measured.

**This changes the scope of any future review of this solver, not
just its findings.** Whether the synchronization takes effect has to
be checked directly, not carried in from the code's comments or from
earlier versions of this file: under the 1.0.8-era framework it partly
did, and under this one it does not at all. Porting the solver onto
`sync=` would implement the synchronization's intent for the first
time, which is why that port is a behaviour change (§4.3).

## Other notes

**The `random.sample()` fix changes which points get sampled, on
purpose.** Wrapping every `.sample()` call's set argument in `sorted()`
(required for Python 3.11+ compatibility — `random.sample()` no longer
accepts sets) necessarily changes selection relative to whatever these
files' un-fixed behavior gave under Python 3.10's implicit,
hash-order-dependent set iteration. This is correct and unavoidable, not
a regression: 3.10's own ordering was never a specification, just
whatever CPython's set implementation happened to do. Recorded here
explicitly so a future review of this code doesn't
mistake this for something that changed the algorithm's *logic* — it
didn't; it changed which of several equally-valid orderings feeds the
same unmodified sampling logic. `tests/golden/README.md` captures fresh
baselines against the fixed code, not against any prior in-tree behavior.

**The README's own `MOSOSolver`-authoring guidance named the exact
pattern that breaks `--crn`.** (Corrected in Phase 6: `crn_advance()`
no longer exists, and the README no longer mentions it. Kept as
written below.) It told solver authors they'll
"use (or wrap) `hit` and `crn_advance()`" — call `crn_advance()` once, at
the end — which is exactly what silently corrupts `--crn` for any solver
that isn't `RASolver`-based (§4.2's `fx1 == fx3` demonstration). Not
fixed here; the actual fix is removing the solver-facing `crn_*` surface
entirely (`docs/rng-interface-design.md` §11, open question 7, settled:
remove, not deprecate).
