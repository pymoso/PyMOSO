# Known issues: MOCOMPASS and MOPBnB (in-tree example solvers)

`pymoso/solvers/mocompass.py` and `pymoso/solvers/mopbnb.py` were brought
in-tree as a **compatibility-only** pass: the fixes that landed with them
(a Python 3.11+ `random.sample()` incompatibility, a library-hostile
`sys.exit()` on missing parameters, a silent-corruption interaction with
`--crn`) make the files run correctly on the current branch. Their
algorithmic behavior has **not** been reviewed or validated against the
source papers — that is separate, future work. The three items below are
caveats in this codebase's own implementation, not defects in the
published algorithms; see each file's docstring for the full citation and
disclaimer.

This is not `KNOWN_ISSUES.md`: that file tracks defects in PyMOSO's
shipped *framework* code across real released versions, anchored to
actual PyPI history. These are caveats in brand-new example code nobody
has released. Deeper narrative and evidence for all three items below —
plus the `random.sample()`/`sys.exit()`/`--crn` findings this doc doesn't
repeat — lives in `docs/rng-interface-design.md`, sections 4.1-4.3, where
these two files were analyzed as external validation of the RNG interface
redesign.

## 1. MOCOMPASS materializes the entire feasible region

`solve()` builds `mcD = set(product(*arglist))` over `[lb, ub]^dim` up
front. This doesn't scale to large `--param lb`/`--param ub` boxes —
memory and time grow with the full box size, not with how much of it the
search actually visits. Not fixed here.

## 2. MOPBnB's `update_gbar` recomputes `sehat[x]` ignoring its own loop index

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

## 3. MOCOMPASS's `self.seeds` cross-point synchronization: deliberate policy, buggy implementation

The cross-point stream sharing `update_gbar` implements — points at the
same cumulative sample-effort level (`nx[x]`) drawing the same underlying
random numbers — is confirmed **deliberate**, a real technique from the
MO-COMPASS literature, not an accident. The *implementation* has a real
bug: `self.seeds` is a single dict keyed by cumulative replication count,
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
and therefore nothing to overwrite. Porting MOCOMPASS onto that interface
is the actual fix; patching the dict now would be thrown away.

**Related but distinct — see item 4 below, found afterward:** even
before the aliasing bug can corrupt a checkpoint, the checkpoint values
`self.seeds` records are not what this section assumes they are.

## 4. MOCOMPASS's `rng.setstate()` calls are not actually honored by the framework's jump computation, beyond each call's first replication

Found while implementing `docs/rng-interface-design.md` §12 step 3
(replacing `Oracle`'s CRN protocol), not while reviewing MOCOMPASS
itself — but it changes what item 3 above is describing, so it belongs
here too, not only in the RNG design doc. Distinct from item 3's
aliasing bug and more fundamental: even a version of `self.seeds` that
never aliased would not give MOCOMPASS the synchronization §4.2/item 3
describe as "confirmed deliberate."

`update_gbar`'s mechanism:

```python
start_state = self.seeds[start_num]
self.orc.rng.setstate(start_state)
isfeas, fx, sex = self.orc.hit(x, ax)
end_state = self.orc.rng.getstate()
self.seeds[end_num] = end_state
```

This assumes `setstate(start_state)` puts `hit()`'s entire replication
sequence — and therefore `end_state` — under the caller's control.
Checked directly against the pre-step-3 framework code, not assumed:
`Oracle.crn_nextobs()`, the method that decided where each replication's
stream landed, always jumped from `self.crn_obsold` — a value the
`Oracle` tracks internally across *every* `hit()`/`bump()` call
regardless of which point called it — never from `self.rng`'s actual,
live state. Instrumenting `crn_nextobs()` directly against a real
MOCOMPASS run confirmed `self.crn_obsold` never equals
`self.rng.getstate()` at the moment it's consulted.

`setstate(start_state)` is honored for exactly one draw: `g()` runs
before `crn_nextobs()` does, so the *first* replication of a given
`hit()` call genuinely draws from `start_state`. Every replication after
the first (whenever `ax > 1`), and `end_state` itself, come from the
framework's own `crn_obsold` sequence instead — one counter shared
across every point's `hit()` calls, order-dependent, unrelated to
`start_state` except by coincidence. So `self.seeds[end_num]` does not
record "`start_state` advanced by `ax` replications"; it records
wherever the shared global walk happened to be when this call returned.

The result: MOCOMPASS's cross-point synchronization has only ever been
partially real, independent of item 3's aliasing bug. A checkpoint's
first replication reflects the intended shared position; nothing else
recorded for later reuse does, and a later revisit to that checkpoint
replays the same partial effect, not a full re-synchronization.

**This changes the scope of the eventual correctness review against Li
et al. (2015), not just its findings.** "Does the synchronization
mechanism actually take effect" is now a question that review needs to
check directly against the paper's algorithm, not an assumption it can
carry in from this file's own prior framing (including item 3 above, as
originally written) or from the implementation's own comments. See also
`docs/rng-interface-design.md` §4.3: porting MOCOMPASS onto `sync=` may
not be *preserving* this behavior so much as *implementing the
synchronization's intent for the first time* — a distinction with
consequences for what "porting" means, spelled out there.

## Other notes

**The `random.sample()` fix changes which points get sampled, on
purpose.** Wrapping every `.sample()` call's set argument in `sorted()`
(required for Python 3.11+ compatibility — `random.sample()` no longer
accepts sets) necessarily changes selection relative to whatever these
files' un-fixed behavior gave under Python 3.10's implicit,
hash-order-dependent set iteration. This is correct and unavoidable, not
a regression: 3.10's own ordering was never a specification, just
whatever CPython's set implementation happened to do. Recorded here
explicitly so a future correctness review against the papers doesn't
mistake this for something that changed the algorithm's *logic* — it
didn't; it changed which of several equally-valid orderings feeds the
same unmodified sampling logic. `tests/golden/README.md` captures fresh
baselines against the fixed code, not against any prior in-tree behavior.

**The README's own `MOSOSolver`-authoring guidance names the exact
pattern that breaks `--crn`.** It currently tells solver authors they'll
"use (or wrap) `hit` and `crn_advance()`" — call `crn_advance()` once, at
the end — which is exactly what silently corrupts `--crn` for any solver
that isn't `RASolver`-based (§4.2's `fx1 == fx3` demonstration). Not
fixed here; the actual fix is removing the solver-facing `crn_*` surface
entirely (`docs/rng-interface-design.md` §11, open question 7, settled:
remove, not deprecate).
