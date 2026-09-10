# RNG interface design: decoupling from `random.Random`

**Version-boundary note:** 1.1.0 was released from `release-1.1.0`,
branched at `b637a3e` — §12 step 6c-completion (Philox's own
offset-assembly budget) and everything before it in this document's
own step list. Everything from step 6b (`--generator` CLI/library
selection, `Oracle.bump()`'s removal, the `--seed` comma-token syntax
change) onward, plus the still-open CRN-branch convergence step and the
`crn_*` solver-facing-surface removal `release-1.1.0` never reached, is
2.0.0 development on this branch (`pymoso-migration`, now at
`2.0.0.dev0`). `release-1.1.0` also excludes MOCOMPASS/MOPBnB
entirely — see `CLAUDE.md`'s "Version boundary" section for the full
account, including why the branches differ in content, not just
version.

Status: design only, nothing implemented. Written against `pymoso-migration`
at `f884bf2`. Scope is the pseudo-random generator interface and what
replaces the CRN protocol in `chnbase.py`/`chnutils.py`. Onboarding
MRG31k3p and Philox-4x32 is in scope as the interface's validation cases;
their numeric output is not (no jump matrices or round constants are
proposed here — see "Open questions").

## 0. What the current code actually does

Read directly out of `pymoso/prng/mrg32k3a.py` and `pymoso/chnbase.py`
before writing anything below, because the redesign's central claim (§2)
depends on the exact mechanics, not a summary of them.

**Generator primitives** (`prng/mrg32k3a.py`):

- `mrg32k3a(seed) -> (newseed, u)`: one recurrence step. Untouched by
  the jump-ahead fix; brute-force-verified in `test_jump_ahead.py`.
- `jump_substream(prn)`: mutates `prn` in place to `2**76` steps ahead,
  via `mat333mult`/`mat311mod` — exact-integer matrix-power multiplication
  against fixed matrices `a1p76`/`a2p76`.
- `get_next_prnstream(seed, use_cache) -> MRG32k3a`: returns a **new**
  generator seeded `2**127` steps ahead of `seed`, via `a1p127`/`a2p127`.
- `MRG32k3a(random.Random)`: overrides exactly two draw-producing methods,
  `random()` and `getrandbits(k)`. Every other `random.Random` method
  (`normalvariate` is also overridden, for BSM; `gauss`, `uniform`,
  `expovariate`, `choice`, `sample`, `shuffle`, ...) is inherited unmodified
  from CPython and reduces to calls into those two. This is confirmed, not
  assumed — `test_rng_consumption.py`'s docstring records an in-repo grep
  across every actual call site plus two tests that record which hook
  method fires. `expovariate` and `normalvariate` both consume exactly one
  `random()` draw per variate.

**The CRN protocol** (`chnbase.py::Oracle`), four methods, three pieces of
state (`crnold_state`, `crn_obsold`, `crnflag`):

| Method | Effect |
|---|---|
| `crn_setobs()` | `crn_obsold = rng.getstate()` |
| `crn_nextobs()` | `rng.setstate(crn_obsold)`; `jump_substream(rng)`; `crn_setobs()` |
| `crn_reset()` | `rng.setstate(crnold_state)`; `crn_setobs()` |
| `crn_check()` | `crn_reset()` iff `crnflag` |
| `crn_advance()` | `crn_check()`; `rng = get_next_prnstream(rng.get_seed(), crnflag)`; `crnold_state = crn_obsold = rng.getstate()` |

Call sites: `hit()`/`bump()` call `crn_nextobs()` after every replication
and `crn_check()` once at the end (after all `m` replications of one
point). `RASolver.rasolve` calls `orc.crn_advance()` once per RA iteration.
`set_crnflag()` (called once, at Oracle construction, from `solve()`/
`testsolve()`) sets `crnold_state = rng.getstate()` — the oracle stream's
starting position.

Read as a three-level hierarchy:

1. **Iteration** (`crn_advance`, `2**127` jump): once per RA iteration.
2. **Point-within-iteration** (`crnold_state`/`crn_reset`): every point
   estimated in one iteration, under CRN, rewinds to the *same* baseline
   before its replications start — this rewind, not any per-point
   coordinate, is literally what "common random numbers" means here:
   different `x` get compared using the same underlying draws.
3. **Replication-within-point** (`crn_obsold`/`crn_nextobs`, `2**76`
   jump): each successive replication of one point advances one substream
   from the point's baseline.

Without CRN (`crnflag=False`), `crn_check()` no-ops, so `crnold_state`
is never consulted again after construction — the walk through
substreams just continues forward, point after point, iteration after
iteration, however the solver happens to visit points. This distinction
drives §2.

**`MAX_RI`** (`chnutils.py`, used by `get_testsolve_prnstreams`):
for each of `isp` independent sample paths, the function calls
`get_next_prnstream` once for the path's own oracle stream, then calls it
`MAX_RI` (200) more times, discarding each result, purely to walk `iseed`
past a reserved window before deriving the next path's stream. `RASolver.
rasolve` raises if a path's iteration count `nu` exceeds `MAX_RI`, because
exceeding it means the path's own `crn_advance` calls would walk into the
*next* path's reserved window (`docs/phase2a-verification.md` item 3
demonstrates the resulting overlap directly). The reservation and the
guard are two halves of one mechanism: pre-walk a window, then make sure
nothing overruns it.

## 1. Decisions already made (repeating CLAUDE.md, not re-litigating)

- Composition, not inheritance. `random.Random` subclassing is not
  load-bearing for PyMOSO's own users (§4.4 covers where it *is* still
  useful, as an opt-in compatibility shim).
- Pure Python, no new runtime dependencies.
- MRG31k3p first (close sibling, cheap interface validation), then
  Philox-4x32 (counter-based, architecturally motivated). MRG32k3a stays
  default.
- `bump()` is being removed; nothing here designs around it. **Done, §12
  step 6b:** no in-tree callers, no test coverage beyond pinning its own
  leftover behavior, duplicated `hit()`'s replication loop, and both
  in-tree `MOSOSolver`s use `hit()`. Migration for anyone using it out
  of tree: `hit()` with the same arguments returns aggregated stats;
  raw per-replication access returns with the executor rework. See
  `KNOWN_ISSUES.md`.
- `Oracle.g(self, x, rng)`'s signature is fixed.

## 2. The central finding: CRN is already coordinate-pure; today's non-CRN *enumeration* is an artifact, not a specification

This is the load-bearing fact for everything below, so it gets proven,
not asserted — and stated more narrowly here than an earlier draft of
this section stated it. That draft said "non-CRN is not
coordinate-computable." That's wrong, and worth correcting precisely:
it conflated the current *implementation's* byte sequence with what
`crnflag=False` actually promises.

**What `crnflag=False` is a contract for.** Nothing about "don't share
random numbers across alternatives" requires consuming `rng(s)`'s draws
in any particular order, or in the order the current code happens to —
given a seed `s`, dropping the first variate, using the second, or
jumping an arbitrary number of steps all equally satisfy it. The actual
requirements are: (1) the underlying generator's distributional
properties are preserved (whatever stream you land on is still a valid
MRG32k3a/MRG31k3p/Philox stream, not a biased or degenerate one), and
(2) the sample path is deterministic and repeatable relative to the
starting seed. Nothing else. In particular, nothing requires that *which*
stream a point gets depend on when, or in what order, that point
happened to be visited.

**Claim, CRN case:** under `crnflag=True`, replication `r` of *any* point
estimated during iteration `k` of a given oracle stream sits at exactly

```
orc_root  +  k * 2**127  +  r * 2**76      (steps, composed under the recurrence)
```

— a pure function of `(k, r)`, independent of which point, independent of
visitation order, independent of how many other points were estimated
first.

**Proof sketch.** `get_next_prnstream`/`jump_substream` apply matrices
that are themselves the base recurrence matrix raised to `2**127`/`2**76`.
Matrix powers compose: applying the `2**127`-jump matrix twice equals
applying the base matrix `2**128` times, i.e. one jump of `2*2**127`
steps — jump-by-`2**127`, iterated, is linear in the iteration count.
`crn_advance()`'s sequence is: rewind to the current `crnold_state`
(under CRN, always true, since nothing else ever changes `crnold_state`
except `crn_advance` itself), then jump `2**127`, then save that as the
new `crnold_state`. By induction, iteration `k`'s baseline is `orc_root +
k*2**127`. Within one point's `hit()`, `crn_check()` at entry always
rewinds `crn_obsold` to `crnold_state` first (via `crn_reset`), so
replication `r`'s stream is that iteration baseline advanced by `r`
substream jumps — `orc_root + k*2**127 + r*2**76`, regardless of which
`x` is being estimated. This was checked directly against the code above,
not derived from the papers alone.

**Claim, non-CRN case:** today's *implementation* — `crn_check()`
no-opping under `crnflag=False`, so `crn_obsold` walks forward through
the entire iteration, point 1's replications then point 2's then point
3's, in whatever order the solver actually visits them — is not a pure
function of `(k, r)`. That's a true, checkable fact about the code. It is
not a fact about what non-CRN mode *is*. The byte sequence a given call
history produces is an artifact of `crn_check()`'s no-op branch, not a
specification anyone wrote down and promised. Give each point its own
coordinate — `(k, x, r)` instead of just `(k, r)` — and non-CRN mode is
just as coordinate-pure as CRN mode. It's simpler, in fact: CRN requires
deliberately *collapsing* distinct points onto one shared coordinate
(that collapse is the entire mechanism); non-CRN just needs distinct
coordinates for distinct points, which needs no rewinding logic at all,
in either the old design or the new one.

**This makes today's non-CRN order-dependence a defect, not a
characteristic to preserve.** A `solve()`/`testsolve()` call's contract,
as documented and as `--seed`/end-seed reporting implies, is "same seed,
same answer." Today, for `crnflag=False`, that's only true if the solver
also visits points in the same order — true *today* only because there
is exactly one implementation of the visitation order (whatever
`RASolver`'s search happens to do, run serially). It stops being true the
moment dispatch order can vary — parallel replication batching, a
different worker count, points estimated out of submission order —
which is precisely the direction the executor rework (CLAUDE.md's
in-flight decision, "work expressed as data... seeds as computed values
rather than object state") is headed. An RNG design that leaves this in
place doesn't merely fail to improve it; it hands the executor rework a
generator whose non-CRN output is silently order-sensitive, discoverable
only by comparing runs across two dispatch strategies that happen to
order things differently. Fixing it belongs in this phase, as a
prerequisite for the executor work, not filed as a follow-on improvement
for later — see §8 and §12 step 4b, where it's bundled with the MAX_RI
removal for a concrete reason (they move the same goldens).

**Consequence for the design:** the coordinate `(k, x, r)` — iteration,
point, replication — is the shape needed for both modes. CRN mode
deliberately drops `x` from the formula (§3.4); non-CRN mode keeps it.
Neither mode needs a running, order-dependent counter, and neither needs
a rewind operation. §3.4 works out how `x` — an arbitrary tuple of ints,
not a small bounded index — actually folds into a bounded coordinate, and
§4 works out what happens when the same point is asked for twice in one
iteration.

## 3. The interface

### 3.1 Core primitive

```python
def stream_at(base_seed, coordinate) -> Stream
```

Deterministic, side-effect-free: same `(base_seed, coordinate)` always
yields a `Stream` that produces the same draw sequence. `coordinate` is a
non-negative integer (or a small tuple the backend folds into one) chosen
by the *caller* (the framework), not inspected or validated for meaning
by the backend — the backend's only obligation is that distinct
coordinates, within whatever capacity it documents, yield non-overlapping
streams.

This one function is the entire "reach a stream" API. There is no
`advance(n)`, no `jump_ahead()`, no `.setstate()` in the public interface.
Position is never reached by mutating an existing object's state; it is
always reached by asking for it directly. This is what removes the
rewind protocol in §6 — there is nothing to rewind, because nothing
was ever walked forward to begin with.

### 3.2 Conforming generator: required surface

A backend module must provide:

- `stream_at(base_seed, coordinate) -> Stream` (§3.1).
- `Stream.random() -> float`, uniform on `[0, 1)`.
- `Stream.getrandbits(k) -> int`, uniform on `[0, 2**k)`, unbiased.
  Rejection sampling is permitted here (§3.3 explains why this one method
  is exempt from the monotonicity requirement).
- `Stream.normalvariate(mu=0, sigma=1) -> float`, via a **monotone**
  transform of a single `random()` draw (§3.3).
- `validate_seed(tokens) -> seed`, a backend-level (not `Stream`-level)
  function: takes whatever raw tokens the CLI collected for `--seed` and
  either returns a seed value in the shape `stream_at`'s `base_seed`
  expects, or raises with a message naming the backend and the arity
  mismatch (§3.7). Needed because arity is generator-specific and
  argparse parses before a generator is known to be selected — see §3.7.

That's the whole required surface. Everything else — `expovariate`,
`gauss`, `uniform`, `choice`, `sample`, `shuffle`, `triangular`, ... —
is not part of the conforming-generator contract at all; it's provided by
the compatibility adapter (§4.4) for free, exactly as it is today,
because CPython's `random.Random` already implements all of it in terms
of `random()`/`getrandbits()`.

The framework may assume:

- Determinism and non-overlap as specified for `stream_at`.
- A documented coordinate capacity per backend (§3.4) — for MRG-family,
  a finite but astronomically large bound derived from stride sizing; for
  Philox-4x32, the 128-bit counter's full range, which the framework will
  never approach.
- Nothing about internal state shape. No `getstate`/`setstate` is
  required, because nothing in the new protocol ever needs to save and
  restore a position — you just ask for the coordinate you want next.
  (This is a genuine simplification versus today, where `getstate`/
  `setstate` exist purely to serve `crn_reset`/`crn_nextobs`.)

### 3.3 Monotonicity is an interface requirement, not an implementation choice

CRN's variance-reduction guarantee depends on `normalvariate` (today's
concrete CRN-participating transform; `expovariate` too, for problems
like `BSProb` that use it) being a **monotone, single-draw** function of
the underlying uniform. Two different `x` compared under CRN receive the
same uniform draws only because the *transform* from those draws to
simulated values is fixed and order-preserving; a rejection method (draw,
maybe reject, draw again) breaks this because the number of underlying
uniforms consumed to produce one output varies with the output itself,
decorrelating the two alternatives' draw streams from that point on.

This has to be a requirement of the **interface**, checked by the
conformance suite (§7) against every backend, not left to each
implementation's judgment — it is exactly the kind of invariant a
generator author can get wrong without any test failing until someone
notices CRN isn't reducing variance the way the theory says it should,
which is a much harder thing to notice than a failing assertion.
MRG32k3a already satisfies it (Beasley-Springer-Moro, `bsm()`, a rational
approximation of `Φ⁻¹`, purely a function of `u`). MRG31k3p can reuse
`bsm()` verbatim — it produces a uniform on `(0, 1)` from a different
recurrence, but `bsm()` doesn't care what produced `u`. Philox-4x32 needs
the same transform applied to its own uniform output; no new numerics
are required, the same `bsm()` works.

`bsm` should also be **public, standalone API** — not only reachable
through a `Stream` instance — confirmed by a real, not hypothetical,
need (§4.2): a solver author (MOPBnB) wanted `Φ⁻¹` as a pure statistics
function for a sample-size formula, entirely unrelated to drawing a
variate from any stream, found `bsm` wasn't documented or re-exported
from anywhere a solver author would look (`chnutils`), and reimplemented
it byte-for-byte rather than importing it. `bsm`'s only current import
path, `pymoso.prng.mrg32k3a.bsm`, is technically available today but not
discoverable; wherever it ends up living under the new module layout
(§9), it needs a documented public path independent of any generator
instance.

**Getrandbits is deliberately exempt.** MRG32k3a's own `getrandbits`
(`prng/mrg32k3a.py:261-296`) already uses rejection — "digits landed in
the biased remainder... discard and redraw all t digits" — and this has
never been a CRN problem, because nothing in this codebase's own use of
`choice`/`sample` (`get_ranx0`, picking a random starting point) happens
on a CRN-participating stream: `get_ranx0` runs on the separate `xprn`,
never subject to `crn_reset`/`crn_advance`. The monotonicity requirement
therefore scopes to whatever transform is actually used *inside*
`Oracle.g()` for objective-value generation, not to the full generator
surface. A custom `Oracle.g()` that called `rng.choice()` to help compute
an objective would already, today, silently lose CRN's guarantee for
that draw — this is an existing limitation, not one the redesign
introduces, and it's worth writing down explicitly rather than leaving
implicit.

### 3.4 Coordinate encoding

The coordinate has to carry two structurally different things: the part
CRN deliberately makes point-independent (`role`, `isp`, `iteration`,
`replication` — §2's `(k, r)`), and the part non-CRN needs and CRN must
*not* have (the point itself, `x`, plus a `visit` index — §4). So the
formula branches on `crnflag`, rather than always including every
component:

```
index(role, isp, iteration, replication) =                   # crn=True
    role_offset(role)               # {solver, oracle}, disjoint ranges
    + isp * ISP_STRIDE
    + iteration * ITER_STRIDE
    + replication * REPL_STRIDE

index(role, isp, iteration, x, visit, replication) =          # crn=False
    role_offset(role)
    + isp * ISP_STRIDE
    + iteration * ITER_STRIDE
    + offset_within_iteration(x, visit, replication)   # exact, §3.4 below
```

The `crn=True` branch is exactly §2's proof, unchanged — this is why
CRN runs stay bit-identical through the coordinate-mechanism-swap step
(§8, §12 step 3) regardless of anything §4 adds for non-CRN. `x` never
enters that branch at all; it doesn't need to.

The `crn=False` branch as written here — `offset_within_iteration(x,
visit, replication)`, defined below via the exact `point_code(x)` scheme
— is the *target* design. The function itself is built and directly
tested in §12 step 4a (§7.1 items 8-9, already landed one step earlier,
in step 3, since they're pure-function tests independent of `crnflag` or
chnbase.py's wiring); what step 4a does *not* do is make it the `crn=
False` branch's *default* coordinate. §12 step 3 (behavior-preserving)
gives the `crn=False` branch a temporary running-ordinal coordinate that
reproduces today's exact order-dependent walk, deliberately not this
formula, so that step stays goldens-green per §8 — and step 4a leaves
that default untouched too, reaching `offset_within_iteration` only via
`hit()`'s new, additive `visit=`/`sync=` parameters (§4.1, §4.3), which
no existing caller passes. Step 4b is where `crn=False`'s *default* path
actually switches over to `offset_within_iteration` and picks up the
reproducibility fix described in §2, bundled with `MAX_RI`'s removal —
one cutover, not two, since both changes restructure the same
enumeration and regenerating goldens twice for overlapping reasons would
cost the reviewer two passes for one conceptual change.

`REPL_STRIDE = 2**76`, `ITER_STRIDE = 2**127` — unchanged from today,
because changing either breaks bit-identical reproduction (§8) — apply
to the `crn=True` branch's `replication * REPL_STRIDE` term specifically.
The `crn=False` branch does not reuse `REPL_STRIDE`; it has no
bit-identity obligation once its default path switches over at step 4b
and instead sizes its own,
independent replication budget (`REPL_BITS`, below) as part of
`offset_within_iteration`. `ISP_STRIDE` is new (§8 — MAX_RI's
replacement), shared by both branches, and must satisfy `ISP_STRIDE >
ITER_STRIDE * (max iterations ever expected)`, with the whole index
comfortably inside the generator's proven recurrence period.
`stream_at(seed, index)` then applies one **generalized** jump — matrix
power by an *arbitrary* `index`, not just the two hardcoded exponents —
computed by the same binary-exponentiation technique
`test_jump_ahead.py::_exact_jump_n` already implements and validates
independently as a reference. `jump_substream`/`get_next_prnstream`
become the two fixed special cases of this one general operation, kept
(as thin wrappers, or as-is) because other code may still call them
directly and because the exact-integer brute-force tests pin their
literal behavior.

**`offset_within_iteration(x, visit, replication)`, the non-CRN branch's
new piece.** An
earlier draft of this section reached for a hash of `(x, visit)` reduced
modulo a slot count, and accepted a probabilistic (birthday-bound)
collision risk as the cost of admitting an arbitrary-dimension tuple into
the coordinate space. That's the wrong default for this codebase. It
changes what kind of claim the whole scheme makes — MRG32k3a's own appeal
to this audience is that the `2**76`/`2**127` spacings guarantee
non-overlap *by construction*, not "with negligible probability," and a
reviewer who has internalized that standard (correctly) would not accept
a quietly weaker one smuggled into one branch of the same document. Ruled
out first, per instruction, rather than accepted and then defended:

- **Enumerating points in visitation order** and assigning slots
  1, 2, 3, ... — rejected; this is exactly §2's defect, relocated rather
  than fixed (still depends on when a point was first seen).
- **Canonical sort-then-assign** — rejected; the set of points an
  iteration will visit isn't known upfront (`spli`/`ne`/`pli` discover
  them incrementally during the search), so there's nothing to sort at
  the moment a coordinate is first needed.
- **A declared feasible-region bound on the `Oracle`**, letting the
  framework map `x`'s position in a known box to an exact index —
  checked directly against every built-in problem
  (`pymoso/problems/*.py`) rather than assumed: none exists. Each
  problem inlines its own feasibility check (`ProbTPA`: `xr = range(0,
  51)`; `ProbTPB`: `range(0, 101)`; `ProbTPC`: `range(-5*df, 5*df+1)`;
  `BSProb`: `0 <= x_i <= tau`), and `chnbase.Oracle` declares no
  `bounds`/`lower`/`upper` attribute at all. A declared-bound convention
  would need a new, optional interface addition no existing custom Oracle
  provides, so it can only ever be an opportunistic special case, not the
  general answer.

**What does work, exactly, with no probability involved:** `x` doesn't
need a *declared* bound — it needs an exact, collision-free integer
encoding, and integer tuples have one for free. Zigzag-encode each
component to a non-negative integer (`zz(v) = 2v` for `v >= 0`, `-2v-1`
for `v < 0` — a standard bijection `Z -> N`), then pack the `dim`
zigzagged values into one integer positionally, radix `2**W`:

```
point_code(x) = sum(zz(x[i]) * (2**W)**i for i in range(dim))
```

This is an exact bijection on the domain `{x : all(zz(x[i]) < 2**W for i
in range(dim))}` — not approximately collision-free, not
collision-resistant, literally injective, the same kind of guarantee
`mat333mult`'s exact integer arithmetic gives over the float version it
replaced. The only failure mode is a component that doesn't fit in `W`
bits, and that failure is *detectable at encode time*, per point, before
any stream is derived: check `all(zz(xi) < 2**W for xi in x)` and raise
if not, rather than silently reducing mod something and risking a
collision no one can see. This mirrors this project's own established
posture toward exactly this class of problem — `MAX_RI` moved from an
unenforced bare local to a promoted, checked constant (KNOWN_ISSUES.md
issue 3); the same move here is: fail loudly and exactly, never silently
and probabilistically.

**Sizing, adaptive per Oracle.** Split the within-iteration budget
(`ITER_STRIDE = 2**127`, reused from the CRN branch so both branches
share one top-level `isp`/`iteration` allocation) three ways:

```
REPL_BITS  = 32   # replication < 2**32 -- matches mrgm1i's own magnitude;
                  # calc_m(nu) = ceil(mconst * 1.1**nu) reaches ~1.9e8 by
                  # nu=200 (today's old MAX_RI) at the default mconst=2,
                  # so 2**24 (~16.7M) would NOT have been enough headroom
                  # -- checked by computing calc_m(200), not assumed
VISIT_BITS = 20   # visit < 2**20 (~1M) -- far beyond any realistic
                  # solver-controlled resample count (§4.1)
POINT_BITS = 127 - REPL_BITS - VISIT_BITS = 75

W = POINT_BITS // self.dim     # adaptive: computed once per Oracle,
                                # not a single fixed constant for every
                                # problem

offset_within_iteration(x, visit, replication) =
    point_code(x) * 2**(VISIT_BITS + REPL_BITS)
    + visit * 2**REPL_BITS
    + replication
```

**Landed differently, corrected here rather than left standing** (a
defect found while planning §12 step 8, not at this design stage):
`replication` above is packed at stride 1, i.e. one raw recurrence step
per replication. That's wrong — it silently assumes a single
replication consumes exactly one raw draw, which no built-in problem's
`g()` does. The landed split instead reserves real headroom per
replication: `REPL_RESERVE_BITS = 14` (16,384 draws/replication,
enforced at runtime — exceeding it raises rather than silently
overlapping the next replication), `REPL_COUNT_BITS = 32` (unchanged
from the `REPL_BITS` figure/reasoning above), `VISIT_BITS = 6` (shrunk
from 20 to make room for the reserve within the fixed 127-bit budget —
`POINT_BITS = 75` is unchanged, so `W` below is unaffected), with
`replication` itself now multiplied by `2**REPL_RESERVE_BITS` in the
formula. Full reasoning, the empirical reproduction, and which goldens
moved are in §12's unnumbered prerequisite-fix entry, right before step
8 (the step whose planning surfaced this).

`self.dim` is already an `Oracle` attribute every problem sets — the
adaptive `W` needs no new interface surface. Checked against every
built-in problem's actual feasible range, not assumed: `ProbSimpleSO`/
`ProbExpensive` (`dim=1`) get `W=75` bits, unlimited in practice;
`ProbTPA`/`ProbTPB` (`dim=2`, ranges `[0,50]`/`[0,100]`) get `W=37`
bits (`|x_i| < ~6.9e10`); `ProbTPC` (`dim=3`, range `±5*density_factor`)
gets `W=25` (`|x_i| < ~1.7e7`); `BSProb` (`dim=9`, range `[0, tau=100]`)
gets `W=8` (`|x_i| < 256`) — tight relative to the others, but `tau=100`
fits with room to spare. Every existing built-in problem lands inside
the exact scheme with margin; nothing in this repository currently needs
a fallback at all. A custom problem with both high dimension and large
per-component magnitude could exceed its adaptive `W` — that raises
(above), with a message naming `self.dim`, the offending component, and
the budget, actionable by the user (reduce the point's magnitude/encode
it differently, or use `crn=True`, which never needs `x` in the
coordinate at all) rather than degrading silently.

**If a probabilistic fallback is ever wanted later** (this design doesn't
propose one — flagged for completeness, since the question was asked
directly): a hash-based `point_slot` the way the earlier draft described
is the shape it would take, and the honest way to disclose it would be
(a) the birthday-bound collision probability at the chosen slot count for
a stated realistic points-per-iteration figure, and (b) what a collision
actually costs — not corruption, a *correlation*: two colliding points
`x1`/`x2` would draw identical replication streams for the one iteration
where they collide, which is exactly what CRN does deliberately for every
pair, just unintended and undisclosed to the solver for this one pair.
Concretely, it biases whichever pairwise comparison that iteration's
search makes between `x1` and `x2` (e.g. `spli`/`ne`'s `fxp1[nobj] <
fxs[nobj]`) toward whatever correlation the shared draws happen to
induce — not systematically toward either point, just no longer
independent for that comparison. The hash input would need to include
`iteration` (the earlier draft's formula didn't), so a collision doesn't
recur for the same pair every iteration — otherwise the bias would
compound rather than average out. None of this is needed while the exact
scheme covers every real case; it's recorded here so a future author
who *does* need a fallback isn't starting from nothing.

For Philox-4x32, `coordinate` packs directly into the counter — the same
`point_code(x)`/`visit`/`replication` split as above (adaptive `W` sized
against the counter's available bits rather than `ITER_STRIDE`), which
for a 128-bit counter gives even more headroom than the MRG-family case
already checked above, at every `dim`. No jump computation either way.

### 3.5 Should the interface expose jump-ahead at all?

No. `stream_at(base_seed, coordinate)` is the only way to reach a stream.
Whether a backend gets there by a generalized matrix-power jump
(MRG32k3a, MRG31k3p) or by packing bits directly into a counter
(Philox-4x32) is invisible outside the backend module.

MRG31k3p is the actual test of this, per the brief, and it passes: it is
also a matrix linear recurrence mod two primes (different order,
different coefficients, per L'Ecuyer & Touzin 2000), so it needs the same
generalized-jump machinery MRG32k3a needs — meaning that machinery
belongs in a **shared** module (`mrg_common.py`, §9), parameterized by
each generator's own recurrence matrix, not duplicated per generator or
leaked into the interface. The interface only ever sees `stream_at`; two
backends built entirely differently underneath (strided matrix jump vs.
counter-packing) both satisfy it identically.

### 3.6 Backward-compatibility adapter — needed, not hypothetical

CLAUDE.md's instruction is composition over inheritance "with a backward-
compatibility adapter only if you can show it's needed." It's needed:
`Oracle.g(self, x, rng)` hands `rng` directly to arbitrary third-party
code (`pymoso/examples/myproblem.py`, and every real custom Oracle this
package's users write), documented only as "`prng.MRG32k3a` object" — an
unbounded surface, not an enumerated one. The *reason* subclassing
`random.Random` worked as well as it did originally is precisely that
overriding two methods (`random`, `getrandbits`) makes the *entire*
`random.Random` API — `gauss`, `uniform`, `triangular`, `shuffle`, ...,
none of which this codebase's own code calls, all of which a third-party
`Oracle.g()` legally could — correctly backed by MRG32k3a, for free.
Dropping that silently breaks any custom Oracle calling something outside
{`random`, `normalvariate`, `expovariate`, `getrandbits`-derived methods},
with no warning until someone's simulation output quietly stops matching
what they expect.

This was argued from what a third-party `Oracle.g()` *legally could* do —
confirmed since, by what a real `MOSOSolver` actually *does* do. Both
MOCOMPASS and MOPBnB (§4.2) call `.sample()` on their solver-level
stream, repeatedly, on `set` arguments — a method well outside the four
the interface requires, on the solver side of the API rather than the
oracle side this section originally argued from. The need isn't confined
to `Oracle.g()`; it's the whole `MOSOSolver`/`Oracle` surface a third
party can reach an `rng`-shaped object from.

Proposed shape: keep a thin `random.Random` subclass per backend — the
same shape MRG32k3a is today — but its `__init__`/`random()`/
`getrandbits()`/`normalvariate()` all delegate to a composed backend
`Stream` object rather than implementing the recurrence themselves. This
is not "inheritance instead of composition"; it's composition at the
core (the `stream_at`/`Stream` layer has zero `random.Random` dependency,
is what the conformance suite in §7 tests, and is what MRG31k3p/
Philox-4x32 implement), with an *optional*, purely cosmetic
`random.Random`-shaped wrapper on top for any caller — framework or
third-party — that wants the full stdlib distribution surface. `Oracle.g`
keeps receiving something that walks and quacks like `random.Random`,
unchanged from a caller's perspective.

### 3.7 `--seed` is generator-shaped, not a fixed 6-tuple — argparse validates arity generically, the generator validates content

Checked directly against the code, not assumed: `cli.py:68` today is
`subp.add_argument('--seed', nargs=6, type=int, ...)` — the arity (6) and
element type (`int`) are hardcoded into the argparse declaration itself,
because there has only ever been one generator. Once generator selection
(§3.8, decided) is real, this breaks by construction: MRG31k3p's seed
shape is whatever L'Ecuyer & Touzin's own state vector requires (open
question 4 — not yet sourced, but there is no reason to assume it's also
6 integers), and Philox-4x32's is a key/counter pair, not 6 integers at
all. A CLI flag whose parser hardcodes one generator's shape can't serve
a second one.

`--seed` stays **optional** in every case — omitting it uses whichever
generator was selected's (§3.8) own default seed (below), exactly as
omitting it today falls back to `chnutils.DEFAULT_SEED`.

**Division of responsibility**, matching this design's existing posture
of "the backend owns what only the backend can validate" (§3.1's
coordinate, §3.4's per-Oracle `W`):

- **argparse** accepts `--seed` generically — raw tokens (not coerced to
  `int` at parse time, since Philox's shape isn't necessarily a flat
  tuple of integers). Argparse cannot validate arity against a
  generator it doesn't know at parse time; it shouldn't try.

  **Correction, found implementing §12 step 6b: not `nargs='+'`.**
  This section originally specified `nargs='+'` for the CLI flag
  itself. Checked directly, not assumed, once real: an unbounded
  `nargs='+'` on an *optional* argument greedily consumes every
  following argv token, including required positionals — `pymoso
  solve --seed 1 2 3 4 5 6 ProbTPA RPERLE 4 14`, the exact form this
  project's own `EPILOG`/README examples have always used, failed
  parsing entirely under it ("the following arguments are required:
  `<problem>`, `<solver>`, `<x>`"), because `--seed` swallowed
  `ProbTPA RPERLE 4 14` too. It only worked with `--seed` placed after
  every positional — a real regression from `nargs=6`'s own behavior,
  and inconsistent with every other option this CLI has, all of which
  are order-independent (`test_options_after_positional_args_still_
  accepted`, `test_param_option_after_other_options_still_accepted`).

  **What shipped instead:** `--seed` takes exactly one argparse token —
  a comma-separated string with no spaces (`--seed
  12345,32123,5322,2,9543,666666666`), split on `,` before being handed
  to the selected generator's own `validate_seed`. A single token can
  never swallow a neighboring positional regardless of where `--seed`
  appears, so order-independence is preserved. This is a visible
  invocation-syntax change from the pre-6b space-separated form
  (`--seed 12345 32123 ...`) — every README/`EPILOG` example, and
  `tests/test_golden.py`/`tests/test_multifile_transport.py`'s own CLI
  invocations, were updated to match, with the underlying seed values
  themselves unchanged (no golden moved).
- **The selected generator** validates arity and content, via
  `validate_seed` (§3.2's added required-surface entry). This is a
  parse-time-adjacent step run once the generator is known (immediately
  after generator selection resolves, before `solve()`/`testsolve()`
  does anything else with the seed) — not deferred to first use, so a bad
  `--seed` fails before any simulation work starts, the same "fail loudly
  and immediately" posture as `point_code`'s overflow check (§3.4).

**Error message names both the expected and actual generator/arity**,
not a generic "wrong number of arguments": `"mrg32k3a expects 6
integers, got 4"`. This matters specifically because seed tokens are
positional and untyped at the CLI boundary — a user who copies a
Philox-shaped seed into a run still using MRG32k3a (or the reverse) needs
to be told what was expected and what was actually given, not have the
values silently reinterpreted against the wrong generator's layout
(which, for two same-length-but-differently-shaped seeds, could produce
a *valid-looking* wrong seed rather than an obvious crash) or fail with
an unlabeled arity error that doesn't say which generator's expectation
it violated.

**Each generator's default seed** is a per-generator constant, part of
the same required surface `validate_seed` belongs to. For MRG32k3a, this
is `(12345,)*6` — checked directly: `chnutils.py:61`'s `DEFAULT_SEED =
(12345, 12345, 12345, 12345, 12345, 12345)` today, echoed in `cli.py`'s
own `--seed 12345 32123 5322 2 9543 666666666` usage example and in
every README/golden invocation that omits `--seed`. This does **not**
change under the redesign — every current golden and README example that
omits `--seed` depends on landing on this exact default, and changing it
would move output for no reason connected to the RNG redesign's actual
goals (§8's bit-identity accounting already has enough deliberate
movers). MRG31k3p's and Philox-4x32's own defaults are undetermined here
— folded into their onboarding steps (§12 steps 5-6) alongside their seed
shapes generally, not fabricated in advance of implementing either
backend, the same posture open question 4 already takes toward
MRG31k3p's jump matrices.

### 3.8 Generator selection: a CLI flag plus the matching kwarg, per-run scope — settled (open question 6)

**Mechanism:** a new CLI flag (name not fixed by this design — used as
`--generator` in examples below, a naming detail, not the decision) on
both `solve` and `testsolve`, alongside the matching `solve()`/
`testsolve()` kwarg — the same shape as `--budget`/`--crn` today (a
`_add_common_options` addition in `cli.py`, per §12's step-7 note that
this is a CLI/testers-layer change, not an RNG-interface one). Value is
the backend's canonical name (`"mrg32k3a"`, `"mrg31k3p"`,
`"philox4x32"` — the same strings §3.7's `validate_seed` error message
already names), `choices=`-restricted the way argparse already restricts
other enumerated flags, default `"mrg32k3a"` for continuity with every
current invocation that specifies no generator at all.

**Scope: per-run, not per-role or per-oracle.** One flag selects one
backend for the entire `solve()`/`testsolve()` call — both the solver-role
and oracle-role streams (and, if `sync=` is used, the sync-role range,
§4.3) come from the same backend. Ruled out, not merely undiscussed:
letting the solver stream and oracle stream use two different backends,
or letting an `Oracle` subclass declare its own preferred backend as a
class attribute independent of the CLI. Both would mean `stream_at`'s
`base_seed` isn't a single value for the run, `--seed`'s own shape
(§3.7) couldn't be validated as one generator's arity, and `endseed`
(§8.2) would have no single backend to report a next-seed for — a
per-run scope is what keeps §3.7 and §8.2 well-defined at all, not an
independent stylistic preference.

**Recorded in run metadata.** Checked against the code, not assumed:
`basecomm.py:120`'s `gen_humanfile(name, probn, solvn, budget, runtime,
param, vals, startseed, endseed)` already builds the human-readable
metadata string `save_metadata` (`solve.py:130`) writes to the run's
output directory, carrying `startseed`/`endseed` today. The selected
generator's name becomes a new field there (and in `testsolve`'s
equivalent), for the same reason `--crn`'s value already needs recording
somewhere a later reader can find it: two runs supplying the *same*
`--seed` tokens under two different generators produce entirely
unrelated output (the tokens mean something different per backend — even
where two backends happened to share an arity, per §3.7 they are not
interchangeable), so a run's own record of what it did is incomplete,
and misleading in a way that looks complete, without saying which
generator consumed the seed.

### 3.9 `stream_at`'s coordinate is two-dimensional, not flat — found onboarding Philox (§12 step 6)

§3.1 already left room for this ("`coordinate` is a non-negative integer
(**or a small tuple the backend folds into one**)") without ever working
out why a tuple might actually be needed. Philox's own onboarding
(§12 step 6) forced the question, but the gap it exposes isn't
Philox-specific — it's present in every generator this document has
onboarded so far, MRG32k3a included, just absorbed silently because
MRG32k3a's period is large enough to not need calling it out.

**Every generator this document has looked at already has two distinct
kinds of movement, not one.** MRG32k3a's own two named jumps say this
directly: `get_next_prnstream` (2**127) reaches a *new, independent
stream*; `jump_substream` (2**76) moves to a *new position within the
current one*. `chnbase.py`'s own coordinate assembly already computes
these as two separate quantities — `self._iteration` (which stream) and
`offset_within_iteration(x, visit, replication, W)` (where within it) —
before ever combining them into one flat integer
(`self._iteration * ITER_STRIDE + offset_within_iteration(...)`). The
flattening is real work the framework does, not a natural shape
`coordinate` already had. It goes unnoticed for MRG32k3a/MRG31k3p only
because their periods (`2**191`/`2**185`) comfortably absorb a flat
integer built by multiplying a "which stream" count by a "within-stream"
stride — there is enough room that the two dimensions never need
separate treatment.

Philox doesn't have that room to spare *in one dimension* — §12 step 6's
own sizing found iteration-count alone (one `isp` path's own history,
before `isp` multiplicity or `sync` ever enter it) overruns the 128-bit
counter by 20 bits at budget-anchored ceilings, not period-anchored
ones. But Philox's *combined* (key, counter) capacity, once "which
stream" and "position within it" are kept as the two separate
quantities they already are, is comparable to the MRG family's own
periods — the mismatch isn't a lack of capacity, it's that the existing
interface flattens two dimensions with different natural homes
(counter: within-stream position, comfortably `<2**128`; key: which
stream, comfortably `<2**64`) into one dimension sized for whichever is
larger, and Philox's "larger" (the counter) is smaller than either MRG
period.

**The fix is not a Philox-specific branch.** `stream_at`'s own signature
should carry the two dimensions it already implicitly has:

```python
def stream_at(base_seed, stream, offset) -> Stream
```

`stream` selects an independent, non-overlapping stream (the `isp`/
`iteration`/`role`/`sync` dimensions currently folded into the high bits
of one flat coordinate); `offset` selects a position within it (`point`/
`visit`/`replication`, currently the low bits). Each backend maps the
pair onto its own mechanism, exactly as the two existing MRG jumps
already do conceptually:

- **MRG-family**: `stream_at(seed, stream, offset) = jump_seed_n(seed,
  stream * ITER_STRIDE + offset)` — the *same* arithmetic as today,
  since a flat integer was always a valid (if unlabeled) MRG mechanism.
  No existing golden moves under this change; it relabels an existing
  computation, it doesn't alter it.
- **Philox**: `stream_at(seed, stream, offset) = Philox4x32(key =
  key_from(seed, stream), counter = offset)` — direct indexing on both
  halves, no jump at all, the natural Random123 usage (key = which
  independent stream, counter = position within it) rather than a
  bit-split of one undifferentiated integer.

**A wrong first move, corrected here rather than left standing:** the
intuitive way to compose `isp` into this (isp selects a *sub-stream*,
so it feels like it belongs "outside" the rest) is to treat it as an
*outer layer* — isp's own `stream_at` call wrapping the entire rest of
Oracle's own `(stream, offset)` reach as if it were one big `offset`.
That reintroduces exactly the overflow this section exists to fix: at
that outer layer, "offset" would have to hold Oracle's *entire* own
reach, including its own `stream` component — `role`/`iteration`-or-
`sync` folded back into one flattened number before ever reaching
Philox's counter, the identical mistake the interface already made
once, just moved up one layer. Checked directly, not caught by
inspection alone: this was the first version of this section's own
Philox sizing, and it put the total back over 128 bits.

What actually works: `isp`, `role`, and `iteration`-or-`sync` are not
layered, they compose **additively into the same `stream` value** —
`chnutils.py`'s own isp-offset and `chnbase.py`'s own iteration/sync-
offset add together exactly the way repeated MRG `jump_seed_n` calls
already compose (`jump_seed_n(jump_seed_n(root,a),b) ==
jump_seed_n(root,a+b)`). Philox's key addition (`key = (base_key +
stream) mod 2**64`) has the identical algebraic shape, so the same
composition holds there too — `isp*ISP_ITER_MARGIN + iteration` is one
`stream` value, not an outer `offset` wrapping an inner one. Under this
grouping, `offset` only ever has to hold the innermost thing —
`point`/`visit`/`replication` — and `stream` holds everything else,
flat, in the *same* dimension. That's what makes the two-part split fit
Philox's own (64-bit key, 128-bit counter) split with real margin on
both sides (§12 step 6's own sizing, corrected with this grouping) —
not a coincidence of picking generous-enough numbers, a consequence of
grouping the dimensions correctly in the first place.

**What this would actually take is smaller than it sounds**, because the
seam already exists: `chnbase.py`'s own call sites (`hit()`,
`_hit_via_coordinate`, `crn_advance()`) already compute `self._iteration`
and an offset-shaped value separately, immediately before combining
them into today's flat coordinate. The change is inserting a seam at
the point that combination already happens — passing the two values
through instead of pre-flattening them — not a rewrite of how
coordinates get computed in the first place.

**Sequencing relative to step 6b (`--generator` CLI/library wiring):**
6b does not depend on this split to land. Selecting MRG32k3a (the
default) or MRG31k3p works today with the flat coordinate exactly as
it stands — nothing about *choosing which generator class to
construct* requires the split. But Philox will not be genuinely
selectable *for real solving* (as opposed to standalone conformance
testing, which is all step 6 itself delivers) until this split exists:
`chnbase.py`'s coordinate assembly has nowhere to hand Philox a
(key, counter) pair as long as it only ever produces one flat integer.
So: 6b can be built and land against today's flat coordinate now; this
split is a prerequisite for Philox specifically becoming usable through
6b's own selection mechanism, not for 6b to exist at all. Recorded as
its own step (§12, step 6c) rather than left as prose only here, per
this document's own established rule about known-necessary work with
no place in the step list.

## 4. What replaces the CRN protocol

Every method in §0's table existed to manage one shared, mutable `rng`
object's position — save it, rewind to it, jump from it. Coordinate
lookup has no shared mutable position to manage, so most of the protocol
doesn't get replaced with an equivalent; it disappears, because the
problem it solved no longer exists.

| Old | New |
|---|---|
| `crnold_state` (a saved `rng` state) | `self._iteration: int` (a counter) |
| `crn_obsold` (a saved `rng` state) | `self._replication: int` (a counter, reset at point-estimate boundaries under CRN — see below) |
| `set_crnflag()` seeding `crnold_state` | `self._iteration = 0` |
| `crn_advance()` | `self._iteration += 1` — no jump computed here at all; the jump happens lazily, the next time a stream is actually requested |
| `crn_setobs()` / `crn_reset()` / `crn_check()` | **removed**. There is nothing to rewind to: `hit()` asks for `stream_at(root, index(role=oracle, isp, self._iteration, r))` directly, for whichever `r` it needs, and that computation depends only on `self._iteration`, never on how many draws happened for some *other* point earlier in this iteration. Under CRN, "rewinding" was only ever a way to fake coordinate-independence with a stateful object; a real coordinate is independent by construction. |
| `crn_nextobs()` | Under CRN: `self._replication` resets to `0` at the start of each point's `hit()` call (this *is* the point-independence — every point's replication `0` maps to the same coordinate) and increments per replication within it. Under non-CRN: replication `0..m-1` is computed per point, from `offset_within_iteration`/`point_code` (§3.4, §4.1) — no counter runs across points at all, resolving §2's defect rather than reproducing it. |

`Oracle.hit()`'s call shape barely changes: instead of "mutate `self.rng`,
call `self.g(x, self.rng)`, then mutate `self.rng` again," it becomes
"compute a coordinate, call `stream_at` to get a throwaway `Stream`, call
`self.g(x, stream)`." `self.rng` as a persistent mutable attribute goes
away entirely; nothing needs it to persist between calls, because nothing
is ever resumed — every replication's stream is requested fresh, by
coordinate.

**Solver-visible surface is unchanged.** `RASolver.rasolve`'s only touch
points are `self.orc.crn_advance()` (still a single no-arg call — now
`self._iteration += 1` instead of a jump) and `self.orc.rng.get_seed()`
for endseed reporting (§8 covers what that becomes). `RASolver`/
`RLESolver` subclasses — including any third-party ones — need zero
changes; this is entirely internal to `Oracle`.

### 4.1 The `gbar`/`sehat` cache is part of the specification, not an optimization — and the `visit` extension point

`hit()` has exactly one caller in this codebase: `RASolver.estimate()`
(`chnbase.py:747`). `estimate()` checks `self.gbar`/`self.sehat` — reset
only at the top of each RA iteration (`chnbase.py:385-386`), before
`self.m` is even set for that iteration (`chnbase.py:383`) — and returns
the cached value on a repeat `x` without calling `hit()` again. Every one
of `estimate()`'s several call sites within one iteration (`ne`, `pli`,
`spli`, `get_min`, `remove_nlwep`, `get_ncn`, `upsample`, each of which
commonly revisits the same `x` — that's the cache's whole reason to
exist) goes through this same check. `self.m` never changes mid-iteration
either (it's fixed once per iteration and every `estimate()` call within
it uses that fixed value — there's no incremental-sample-size path where
a point gets topped up to a larger `m` later in the same iteration). So,
checked directly against the code rather than assumed: **an `RASolver`
never asks `hit()` to sample the same `(iteration, x)` pair twice.** The
cache isn't an optimization that happens to save some draws; it's the
reason `offset_within_iteration`/`point_code` keying is safe for `RASolver` at all — a
repeat derivation of the same coordinate is harmless specifically because
`estimate()`'s memoization guarantees it's never actually consumed twice.

That guarantee is `RASolver`-specific, not something `Oracle`/`hit()`
itself enforces or should enforce. `MOSOSolver` is the actual base class
(`RASolver` is one concrete algorithm family built on it); a general MOSO
algorithm is entitled to revisit a point and *choose* to re-sample it
rather than reuse a cached estimate — that's the algorithm's decision to
make, not a policy the RNG layer gets to impose by making repeat
coordinates always resolve to the same stream. The framework's job is to
provide the mechanism (a coordinate that can be made to differ for a
repeat visit) without deciding the policy (whether any given solver
*wants* it to differ).

Concretely: `Oracle.hit(x, m, visit=0)` — one new keyword argument,
additive, default-compatible with every existing caller and with
`RASolver` specifically (which never needs to pass anything but the
default, since its own cache means the default is never asked to
disambiguate two real visits).

**Continuation, not reset, is what `visit=0` must mean by default —
corrected against two real `MOSOSolver` implementations, not designed in
the abstract.** An earlier draft of this section treated `visit` as the
whole mechanism: pass `visit=1`, `visit=2` for a deliberately independent
resample, and otherwise every `hit(x, m)` call at the default `visit=0`
would draw the *same* coordinate's replications `0..m-1` again. Checked
against two real custom `MOSOSolver` implementations from prior work
(MOCOMPASS and MOPBnB, analyzed in full in §4.2 — not yet in-tree, so
this is external validation, not fixture code) rather than assumed: that
default is wrong. Neither solver wants a fresh independent resample when
it revisits a point; both want the *next* replications appended to what
they already have. MOPBnB is the clean case — `solve()` calls
`self.orc.hit(x, R[iterk-1])` once per point per iteration, then later in
the *same* iteration calls `self.orc.hit(x, rdiff)` again for the same
`x`, expecting `rdiff` genuinely new draws so its incremental mean/
variance update (`update_gbar`) isn't silently averaging a repeated
sample into itself. It does this today with no state of its own — it
relies entirely on the framework's current non-CRN behavior being a
forward-only walk that never repeats a position. That is precisely the
behavior §2 calls a defect (order-dependent, not reproducible once
dispatch order can vary) and precisely what step 4b replaces — `visit=0`
itself is additive and behavior-preserving at step 4a (it reproduces
today's forward-only walk exactly, since nothing changes what the
default path computes until 4b switches it over). **This makes
the dependency direct, not incidental: MOPBnB's correctness today already
depends on the property §2 is fixing, so the fix must ship a mechanism
that preserves that property — not one that merely happens to please a
solver that would be equally happy with something else.** A `visit=0`
default that resets to replication `0` on every call would silently
corrupt MOPBnB's estimator exactly the way `--crn` already does today
(§4.2) — a different bug with the identical shape: a rewind back to a
baseline the solver didn't ask for and has no way to detect happened.

The fix: `visit=0`'s replications are **not** indexed from `0` on every
call. The framework tracks, per `(iteration, x, visit)`, how many
replications have already been drawn, and each `hit()` call at that
`(x, visit)` gets the *next* contiguous block — automatically, with no
solver-side bookkeeping, which is also a strict simplification over
MOCOMPASS's current hand-rolled `self.seeds`/`nx` (§4.2): that whole
mechanism exists only because the framework gives it no other way to get
continuation, and disappears once continuation is what `hit()` already
does. `visit` (nonzero) stays reserved for the case *neither* of these
two real solvers turned out to need — a solver that wants to explicitly
discard continuation and start an independent block. It remains part of
the interface because a general `MOSOSolver` is entitled to want that
(§4's original argument for exposing it at all still holds), but it's now
correctly understood as the exception path, not the primary mechanism.
This needs to be designed in now, before any real `MOSOSolver` besides
the RA family exists against the new interface — losing it would mean
discovering the gap only when someone tries to implement one, which is a
worse time to find it, and in this case it very nearly was: the gap
wasn't found by anticipating it, it was found by tracing what a real
solver already does.

### 4.2 External validation: MOCOMPASS and MOPBnB

**Update:** both landed in-tree, compatibility-only, as
`pymoso/solvers/mocompass.py`/`mopbnb.py` — the role question below is
settled (shipped examples). The compatibility fixes made to bring them
in (the `random.sample()`/3.11+ fix, the `sys.exit()`→`TypeError` fix,
the `--crn` refusal) are recorded in
`docs/mocompass-mopbnb-known-issues.md`, which also carries the three
known algorithmic caveats (items 1-3 below plus the aliasing bug) forward
without re-deriving this section's narrative. Their algorithmic
correctness against the source papers is still unreviewed — everything
below remains live evidence for the RNG interface design, not a
correctness sign-off.

Two real custom `MOSOSolver` implementations from prior work, written
against roughly the 1.0.8 API — `mocompass.py`, `mopbnb.py`. Analyzed by
reading in full and by running both against `ProbTPA`
on both environments (`pymoso solve --param lb 0 --param ub 50 ProbTPA
<file> 25 25`), plus small standalone scripts driving `Oracle.hit`/
`getstate`/`setstate` directly to check specific claims empirically
rather than by inspection alone.

**Run status.** Both run correctly on `.venv-baseline` (3.10). Both fail
immediately on `.venv-dev` (3.14):

```
TypeError: Population must be a sequence.  For dicts or sets, use sorted(d).
```

`random.Random.sample()` stopped accepting `set` arguments; every
`self.sprn.sample(some_set, ...)` call in both files (MOCOMPASS:
`sample_set`, `cssample`, `sample_mpr`; MOPBnB: `sample_region`) hits
this. Pre-existing, orthogonal to this work — a stdlib change between the
Python version these were written against and 3.14 — not something the
RNG redesign causes or fixes. Noted because it's a real, current-branch
compatibility gap for anyone trying to run either file today, squarely
in the 3.10-floor/3.14-dev territory this project already tracks.

**`--crn` silently corrupts both**, confirmed empirically, and this is
the second, independent argument for §11 open question 7 (below):

```
orc.set_crnflag(True)
fx1 = orc.hit((5, 5), 4)      # first call
fx2 = orc.hit((40, 10), 4)    # different point, no crn_advance() between
fx3 = orc.hit((5, 5), 4)      # revisit (5, 5), still no crn_advance()
fx1 == fx3   # True
```

Both solvers call `self.orc.crn_advance()` exactly once, at the very end
of `solve()`, identically placed — never once per algorithmic iteration
the way `RASolver.rasolve` does. `hit()` calls `crn_check()` at the end
of every call, which rewinds to `crnold_state` — set once, at
construction, and never advanced by either solver. Under `--crn`, every
`hit()` call in the entire run, for every point, therefore starts from
the same frozen baseline: `fx1 == fx3` above is a direct replay, not a
coincidence. Reproduced with MOPBnB's exact call shape (plain `hit()`
calls, no manual state management at all), so this is a property of the
`crn_advance()`-once-at-the-end pattern itself, not specific to
MOCOMPASS's own bookkeeping — any `MOSOSolver` that copies it inherits
the same silent corruption.

**§11 open question 7, answered: remove the solver-facing `crn_*`
surface entirely, for two independent reasons.** (1) The framework-
leakage argument: a solver calling `orc.crn_advance()` before returning
is bookkeeping that belongs to `solve()`/`testsolve()`, not a decision an
algorithm designer should have to make — CRN is a framework feature for
expert users who opt in via `--crn`, not a protocol solver authors
implement against. (2) This evidence: the one call site both real
solvers actually contain doesn't merely fail to help `--crn` — it
silently breaks the feature it appears to support, and there is no way
for the solver author to have discovered this without the kind of direct
`getstate`-level testing done here, since nothing raises. The migration
story stays "delete that line" — under the coordinate interface, the
framework decides when an iteration boundary happens, and no solver-level
call exists to get wrong.

**§3.6's compatibility adapter, confirmed needed with a concrete example,
not a hypothetical one.** Every `.sprn.sample(...)` call above is on a
`set`, none of the four required conforming-generator methods, exactly
the shape of dependency §3.6 argued a custom `Oracle.g()` *might* have on
the full `random.Random` surface — except here it's a custom *solver*,
observed actually doing it, in both files.

**`bsm()` should be public, standalone API — confirmed with a concrete
example, not a hypothetical one.** MOPBnB defines its own `bsm`/`bsma`/
`bsmb`/`bsmc`, checked byte-for-byte identical to
`pymoso/prng/mrg32k3a.py`'s, and calls it as a pure inverse-normal-CDF
function inside a sample-size formula (`bsm(1 - alphak[iterk]/2)`),
never through an `rng` object. `bsm` is technically importable today
(`pymoso.prng.mrg32k3a.bsm`) but isn't re-exported from `chnutils` or
documented anywhere a solver author would find it — this is a real user
reimplementing framework internals because they weren't discoverable,
not a capability that was genuinely missing. Strengthens §3.3's point
that `bsm` becomes shared machinery (`mrg_common.py`, or wherever it
ends up living per §9) into a concrete requirement: it needs a public
import path the framework documents, independent of any `Stream`
instance.

**MOCOMPASS's `self.seeds` cross-point synchronization: confirmed
deliberate, by the author, not an artifact — corrected from an earlier
draft of this section, which left it open.** It *intends* a real,
different CRN policy: points sharing the same cumulative sample-effort
level (`nx[x]`) share underlying draws, regardless of iteration or point
identity. (§4.3 has a further correction to this paragraph, found later,
during implementation: today's mechanism only partially achieves that
intent, independent of the aliasing bug below — read §4.3 before taking
"implements" at face value.) That is a real requirement, and §4.3
addresses it directly — the earlier draft's proposed port ("just pass
`crn=True`") was wrong, and wrong in an instructive way (§4.3). The
*aliasing bug* — a later revisit landing on a checkpoint some other
point's call happened to write last (§4.1) — stays a separate finding: a
defect in `self.seeds` being a mutable dict two different call sites can
overwrite, not in the synchronization policy itself. §4.3 shows the two
separate cleanly once coordinates are computed instead of cached: the
same policy is
expressible with nothing to overwrite, because nothing is stored.

**Known issues in these two files, for context — not evidence for the
RNG design, not acted on here:** MOCOMPASS materializes the entire
feasible region via `set(product(*arglist))`, which doesn't scale to
large boxes; MOPBnB's `update_gbar` recomputes `sehat[x]` once per
objective inside a loop that ignores its own index (visible in a test
run: a sample-size formula fed by that computation produced "16221167823086
additional replications" before the budget guard caught it); and — found
here — MOPBnB's `except KeyError:` block calls `sys.exit()` but never
`import sys`, confirmed empirically (`NameError: name 'sys' is not
defined`, not the intended usage message) by running it without
`--param lb`/`--param ub`.

### 4.3 CRN is a policy the framework picked, not a fact about the coordinate — `sync`

MOCOMPASS forces a correction one level up from §4.1/§4.2. The framework
calls `crnflag=True` "CRN," but it implements exactly one synchronization
policy: every point estimated during RA iteration `k` shares the stream
at coordinate `(k, r)` (§2). MOCOMPASS needs a *different* policy —
points sharing the same cumulative sample-effort level, `nx[x]`, share
the stream, independent of which iteration either point is in. `sar()`
doesn't hold `nx[x]` equal across points within an iteration in general
(only close to it early on, which is why the two policies coincide often
enough to look related and diverge once points' histories start to
differ) — so passing `crn=True` at the framework level, the port §4.2
originally proposed, is a different policy that happens to overlap with
MOCOMPASS's intent sometimes, not an implementation of it. Recommending
that port was wrong, and wrong for a reason worth generalizing from: the
framework currently offers one fixed synchronization axis (`iteration`)
and calls it *the* CRN mechanism, when the actual, general property CRN
depends on is just — some solver-chosen quantity determines which draws
get shared, and `iteration` is only the RA family's choice of that
quantity, not the only sensible one.

**The fix is not a second framework policy; it's exposing the axis as a
parameter.** Every coordinate in this design already reduces to `role_
offset + isp*ISP_STRIDE + <synchronization component> + replication*
REPL_STRIDE` (§3.4) — RASolver's default `<synchronization component>`
is `self._iteration * ITER_STRIDE`, computed and advanced by the
framework. Nothing about `stream_at` cares what that component actually
*means*; it's cheap, in the sense §12's instructions asked for, to let a
solver supply it directly instead of accepting the framework's default:

```
Oracle.hit(x, m, visit=0, sync=None)
```

- `sync=None` (default): unchanged from §4.1 — the framework's own
  per-`(iteration, x, visit)` auto-continuation scheme, `crnflag`-gated
  exactly as designed. `RASolver` never needs anything else, and this is
  what keeps its behavior — and the CRN branch's bit-identical proof
  (§2, §8) — untouched by this section.
- `sync=<non-negative int>`: the solver *is* the synchronization axis.
  The coordinate becomes `role_offset + isp*ISP_STRIDE + SYNC_ROLE_OFFSET
  + sync*SYNC_STRIDE + replication*REPL_STRIDE` — `x` and `visit` are not
  folded in at all, deliberately, because the whole point of supplying
  `sync` is that point identity shouldn't determine the stream. Passing
  both `sync` and a non-default `visit` is refused (`ValueError`) rather
  than given an ambiguous resolution — a solver taking control of the
  axis has taken control of it, there's no sensible way to also apply
  the default per-point escape hatch on top.

MOCOMPASS's port, corrected: delete `self.seeds` and every `getstate`/
`setstate` call, keep `nx` (still needed for the incremental-mean
bookkeeping `update_gbar` already does), and call
`self.orc.hit(x, ax, sync=nx[x])`. That's the whole mechanism — the
identical policy the paper's algorithm wants, with `nx[x]` playing
exactly the role it already plays in the existing code, minus the state
that was ever at risk of being overwritten. **The aliasing bug (§4.1,
§4.2) cannot recur under this design**, and not by discipline or a
narrower dict key — there is no dict. `stream_at(base_seed, coordinate)`
is a pure function; two different points supplying the same `sync` value
compute the identical stream independently, in either order, any number
of times, with nothing written and therefore nothing to overwrite. This
is the concrete payoff of `stream_at` being computed rather than reached
by mutating a stored position (§3.1) applied to a case this design didn't
originally have in view: it doesn't just make the framework's own two
built-in policies safe, it makes an arbitrary third one the same way, for
free, because "safe" was never about which policy — it was about giving
up cached, mutable position-tracking at all.

**Correction, found during §12 step 3's implementation, not anticipated
here: "the identical policy the paper's algorithm wants" overstates what
today's `self.seeds` mechanism actually achieves, so `sync=` is not
purely preserving it.** Implementing step 3's replacement for `Oracle`'s
CRN protocol required instrumenting the pre-step-3 code directly, and
that turned up something this section didn't have in view: `Oracle.
crn_nextobs()` — the method that decided where each replication's stream
landed — always jumped from its own internally-tracked `crn_obsold`,
never from `self.rng`'s live state, so MOCOMPASS's `rng.setstate(start_
state)` call is honored for exactly one draw (`g()` runs before `crn_
nextobs()` does) and ignored for every replication after the first
within that `hit()` call, and for `end_state` itself — confirmed
empirically, not inferred, by checking `self.crn_obsold ==
self.rng.getstate()` at the moment `crn_nextobs()` consults it, against
a real MOCOMPASS run (`crn_obsold` never matched). Full derivation in
`docs/mocompass-mopbnb-known-issues.md` item 4, alongside item 3's
aliasing bug this is distinct from — that bug corrupts an already-
partial mechanism, it isn't the only thing standing between today's code
and the paper's intended synchronization.

Concretely, this means `self.orc.hit(x, ax, sync=nx[x])` does not
reproduce what `self.seeds`-based MOCOMPASS actually computes today —
it reproduces what the *paper's* policy computes, which today's
implementation only partially achieves (correctly for each checkpoint's
first replication, not for the rest). **Porting MOCOMPASS onto `sync=`
is therefore a behavior change to that solver, not a refactor of it** —
this document's own working-agreement discipline (CLAUDE.md: patching
vs. rewriting, and reporting findings before fixing them) applies to
that port the same way it applies to any other behavior change: MOCOMPASS's
own golden(s) move when `sync=` lands and it's ported, for a real reason
(closer alignment with the cited algorithm), not an incidental one, and
that needs the same sign-off any golden move needs, not silent
regeneration. It also means the eventual correctness review against Li
et al. (2015) inherits an open question from here, not an assumption:
whether the paper's synchronization, once actually implemented via
`sync=`, changes MOCOMPASS's empirical behavior/convergence relative to
what this branch's `self.seeds`-based version has been producing — a
question that review needs to check directly, since this document
cannot settle it from the interface side alone.

`SYNC_ROLE_OFFSET` needs its own disjoint region of the coordinate space
(a third value alongside `{solver, oracle}` for `role`, §3.4), not a
reuse of the oracle role's iteration-indexed range — so a solver that
mixes default-mode and `sync`-mode `hit()` calls in the same run (nothing
here needs this today; RASolver doesn't, MOCOMPASS doesn't mix, but a
future solver might) can't have a chosen `sync` value collide with a
framework-computed `iteration` value that happens to numerically match.
Cheap to reserve now, expensive to retrofit later.

**What this doesn't change:** `RASolver`'s behavior, the CRN branch's
bit-identical proof, or anything in §2, §6, §7, §8 — `sync` is an
additive, opt-in override of the default coordinate-assembly policy
(§4.1), not a replacement for it, in the same additive spirit as `visit`.
It does mean `Oracle.hit`'s final proposed signature is `hit(x, m,
visit=0, sync=None)`, and that this needed a second real external solver,
not just the first, to be found — worth registering as its own point:
one reference implementation validated the interface's *shape*
(§4.1's continuation fix); it took a second, with a genuinely different
algorithm design, to show the shape still wasn't general enough. Whatever
role these two files end up playing (§4.2), that argues for not treating
one hand-written custom solver as sufficient coverage for "does this
interface work for real algorithms" going forward.

## 5. Why this matters beyond the interface itself

Once a replication's stream is `stream_at(root, index(role, isp,
iteration, replication))` — a pure function of four small integers, no
shared mutable state consulted — a worker no longer needs a live `Oracle`/
`rng` object shipped to it at all for the streams it uses; it needs the
four integers and the root seed, which is exactly what `--simpar`'s
existing per-replication dispatch already sends (`hit()`'s `simpar > 1`
branch already does `cseed = self.rng.get_seed(); self.req_q.put((x,
cseed))` — a concrete seed, not a live object). This is precisely the
gap `testsolve`'s `--proc` path has instead (KNOWN_ISSUES.md issue 9,
`docs/forkserver-hang.md`'s "prerequisite for the Spark goal" section):
it ships fully-constructed, already-seeded `Oracle` instances because
there was no cheaper way to hand a worker "the right position" than
handing it the object that remembers that position. A coordinate is
cheaper than an object by construction. This document does not fix
`--proc` — that's executor-rework territory per CLAUDE.md's in-flight
decisions, and needs its own design for how coordinates get assigned to
dispatched work — but it removes the specific obstacle (`rng`-as-mutable-
object-with-memory) that made `--proc`'s fix a different, harder problem
than `--simpar`'s.

## 6. How MAX_RI disappears, concretely

`MAX_RI` exists for one reason: `get_testsolve_prnstreams` doesn't know
in advance how many `2**127` jumps a given sample path's RA iterations
will consume, so it reserves a fixed window (`MAX_RI` jumps) and the
`RASolver.rasolve` guard exists purely to stop a path from silently
overrunning that reservation into the next path's window.

With `index = role_offset + isp*ISP_STRIDE + iteration*ITER_STRIDE +
replication*REPL_STRIDE`, path `isp`'s streams are computed directly from
`isp` and `iteration` — there is nothing to reserve, because there is no
enumeration step at all. Deriving path 5's starting stream costs exactly
the same `O(log(index))` matrix-power work whether path 5 is requested
first or last, and whether path 0 through 4 used 3 iterations or 3,000.
The pre-walk loop in `get_testsolve_prnstreams` (`for i in
range(MAX_RI): ...`) is deleted, not replaced.

The *collision-avoidance reason* for `RASolver.rasolve`'s `nu > MAX_RI`
check disappears completely — overrun into another path's window isn't
possible when there's no shared, order-dependent walk to overrun. **Open
question 9, settled (§11): the check is removed entirely, not
repurposed.** No replacement runaway-loop guard is added — a generous
fixed ceiling would just be a new arbitrary constant with no principled
basis now that stream headroom no longer motivates one, and a solver
that never progresses (§12 step 4b's MyRAAlg note) is a defect in that
solver, not something the framework should paper over with a magic
number. One concrete consequence, not a hypothetical one: `RASolver`
has no bound on `nu` left at all after this step, so a solver whose
`spsolve` never calls `self.estimate` — the README's own "Template RA
Solver," `MyRAAlg`, exactly matches this shape (§12 step 4b) — no
longer fails cleanly after 201 iterations. **Not an indefinite hang**,
corrected against the actual landed code rather than predicted in
advance: `calc_b`'s `1.2**nu` term overflows to a Python float `inf`
around `nu≈3882` (`calc_m`'s own `1.1**nu` would overflow later, around
`nu≈7449`, but `calc_b` runs first each iteration and gets there
sooner), and `ceil(inf)` raises `OverflowError` — confirmed by running
it directly, `nu=3882` reached in 0.03s. So the actual failure mode is
a fast (well under a second), confusing crash naming neither `MyRAAlg`
nor the real cause, not a hang — tracked as part of step 4b's own
deliverables, not a gap discovered later.

## 7. Conformance test suite

Written before any generator implementation, run against every backend
(MRG32k3a, MRG31k3p, Philox-4x32) via parametrization — a defect
detector is only proven by being seen to detect, so each test here needs
at least one backend-shaped counterexample considered while writing it,
the same discipline the working agreement already applies to fixes.

1. **Determinism.** `stream_at(seed, idx)` called twice, independently,
   produces identical draw sequences.
2. **Distinctness / non-overlap.** For a battery of distinct coordinates
   spanning the documented capacity (including adjacent ones — `idx` and
   `idx+1` — which is where a stride bug would actually show up), the
   first `N` draws of each stream share no prefix and the derived raw
   states differ.
3. **Exact-integer brute-force jump validation** (MRG-family only) —
   direct port of `test_jump_ahead.py`'s method: an independent reference
   implementation of the recurrence, in arbitrary-precision Python
   integers, computing the same generalized matrix power `stream_at`
   uses internally, checked against brute-force single-stepping for
   several seeds and several exponents (small, to keep brute force
   cheap, plus the two literal exponents `2**76`/`2**127` for direct
   comparison against today's `jump_substream`/`get_next_prnstream`).
   For MRG31k3p specifically, this test must exist and pass *before* the
   MRG31k3p backend is considered done — it's the "close sibling"
   generator's whole reason for going first, and it directly re-uses
   `_exact_jump_n`'s technique, generalized to MRG31k3p's own recurrence
   matrix once that's sourced (§11, open question 4).
4. **Monotonicity of the CRN-participating transform.** For a fixed
   backend, feed a monotonically increasing sequence of raw uniforms
   directly into the `normalvariate`/`bsm`-equivalent transform (bypass
   the generator, since the transform is a pure function of `u`) and
   assert non-decreasing output. Every backend's transform gets this
   test — this is where a backend that switched to a rejection-based
   normal generator would get caught, and per §3.3 it needs to be caught
   here, not discovered as an unexplained CRN variance regression later.
5. **`getrandbits` unbiasedness smoke test.** Basic distributional sanity
   (chi-square or similar) on `getrandbits(k)` output for a couple of
   `k` — not a full statistical battery (TestU01-grade validation is
   explicitly out of scope for this phase; flagged, not silently
   skipped).
6. **Cross-process reproducibility.** `stream_at(seed, idx)` computed in
   a spawned worker process (only `seed`/`idx` crossing the process
   boundary, not a live generator object) reproduces the same draws as
   the same call in the parent. This is the direct test of §5's claim
   and should use `forkserver` explicitly (matching `.venv-dev`'s
   default and where the current design's blind spots have actually
   been found before), not rely on `fork`'s copy-on-write to paper over
   a real gap.
7. **Bit-identical migration proof** (MRG32k3a only, one-time, tied to
   §12 step 3) — for a battery of
   `(isp, iteration, replication)` triples, the new coordinate-derived
   seed equals the seed the *old* `crn_reset`/`crn_advance`/
   `jump_substream`/`get_next_prnstream` stateful walk would have
   produced for the same call sequence. This is the concrete, checked
   claim behind "lands with goldens green," not an assumption riding on
   §2's proof alone — the proof says it *should* hold; this test is what
   actually establishes it does, on the real code, the same way
   `test_jump_ahead.py` didn't stop at the papers' math either.

### 7.1 Coordinate-assembly tests — the layer above, which items 1-7 don't reach

Items 1-7 exercise `stream_at` and below: a backend's own correctness,
generic to whatever coordinate it's handed. They say nothing about
whether `chnbase.py` computes the *right* coordinate from `(isp,
iteration, x, visit, replication)` — that's a different layer,
introduced across §12 steps 3-4a, landed before step 4b (the step that
actually makes any of it load-bearing for a default, goldens-affecting
call), not folded into it:

8. **`point_code`/`offset_within_iteration` exactness.** A battery of
   distinct `x` (including adjacent integer points, negative components,
   and points differing in only the last dimension — where a radix-packing
   bug would actually show up) must produce pairwise-distinct
   `offset_within_iteration` values, asserted directly (`assert a != b`),
   not sampled statistically — the scheme is exact, so the test can be
   too. A companion round-trip test decodes a computed
   `offset_within_iteration` back into `(point_code, visit, replication)`
   and asserts it recovers exactly what was encoded.
9. **Overflow raises, not collides.** For an adaptively-computed `W`
   (§3.4) and a component deliberately constructed to exceed `2**W`,
   assert the encoder raises (a specific, named exception) rather than
   wrapping/truncating — the negative-space check for item 8's positive
   claim, and the concrete test that the coordinate scheme's "fail
   loudly" choice (§3.4) is what actually happens, not just what was
   intended. Landed in step 3, alongside item 8.
10. **Order-independence, operationally — not just architecturally.**
    Construct two `RASolver` runs (or a lower-level harness driving
    `Oracle.hit()` directly) that estimate the same set of points within
    one iteration in two different orders, and assert every point gets
    the *same* stream regardless of order. This is the direct,
    operational test of §2's fix. Its harness is built in step 3 and
    **run once against step 3's own code and observed failing** —
    demonstrating the defect concretely, the same discipline
    `test_max_ri.py` already applies to `MAX_RI` overlap
    (`docs/phase2a-verification.md` item 3). It stays failing through
    step 4a too — 4a doesn't touch the `crn=False` branch's *default*
    coordinate, only adds opt-in paths (`visit!=0`, `sync=`) nothing
    default-shaped exercises — and only flips to **required to pass** at
    step 4b, when the default path actually switches over. A test never
    seen failing against the bug it names isn't proven to catch that
    bug.
11. **No collision past the old `MAX_RI` ceiling.** With `MAX_RI`'s
    reservation gone, assert directly that two `isp` paths' coordinate
    ranges don't overlap even at iteration counts well beyond the old
    200 — the positive replacement for what `test_max_ri.py` checked
    negatively (that exceeding the reservation raised). Landed and
    passing at step 4a, against the coordinate/index function directly —
    it needs no live dependency on `get_testsolve_prnstreams`'s actual
    dispatch, only on the `ISP_STRIDE`-based formula those functions will
    use. `test_max_ri.py` itself doesn't become obsolete until step 4b,
    when its guard is actually removed from `RASolver.rasolve` (§6, open
    question 9, settled) and `get_testsolve_prnstreams`'s real dispatch
    switches to the formula this item already exercised in isolation —
    that's when this item should replace it, not before.
12. **`sync`'s coordinate space stays disjoint from the default's**
    (§4.3). Assert that no `(isp, iteration, x, visit, replication)`
    coordinate computed via the default path ever equals any
    `(isp, sync, replication)` coordinate computed via the `sync=`
    override, across a battery of both, for the same `base_seed` —
    the direct check that `SYNC_ROLE_OFFSET` actually gives `sync` its
    own region rather than merely making collision unlikely. Also assert
    the specific property MOCOMPASS's port depends on: two `hit()` calls
    for different `x`, same `sync` value, produce identical draws for
    *every* replication, independent of call order — the operational
    demonstration that computed coordinates give MOCOMPASS's *intended*
    cross-point sharing (the paper's policy) in full. `self.seeds` never
    actually did this beyond each checkpoint's first replication (§4.3,
    docs/mocompass-mopbnb-known-issues.md item 4), independent of its
    separate aliasing failure mode (§4.1) — so this item is checking that
    `sync=` achieves something `self.seeds` didn't, not merely that it
    reproduces `self.seeds` more safely.

§8.1 says plainly what this buys and what remains a gap until it exists.

## 8. Bit-identical preservation: what holds and what doesn't

**Holds, unconditionally:** the generator primitives themselves.
`mrg32k3a()`'s recurrence step, and the two literal jump distances
(`2**76`, `2**127`) computed via exact-integer matrix power, are not
changing at all — `test_jump_ahead.py` keeps passing unchanged because
nothing in this design touches `mat333mult`/`mat311mod`/`a1p76`/`a2p76`/
`a1p127`/`a2p127`. These become (part of) the shared `mrg_common.py`
machinery other generators reuse the *technique* of, not code they share
directly (MRG31k3p's matrices are its own).

**Holds, through step 3 specifically (§12), for every scenario `solve()`/
`testsolve()` exercise today:** both the CRN branch (permanently, per
§2's proof and §3.4) and, temporarily, the non-CRN branch, via the
compatibility running-ordinal coordinate described in §3.4's note —
provided that ordinal reproduces today's *specific* enumeration order:
all `isp` solver-stream jumps first, then all `isp` oracle-stream jumps
each followed by its reservation walk, and within each path, the exact
point-visitation order `RASolver`'s search actually produces. §7 item 7
is the check for this, and it's a precondition for calling step 3 done,
not an assumption.

**Does not hold, by design, once step 4b lands (§6, §12):** two things
change together, deliberately, in the same step, because both restructure
the same enumeration — neither moves at step 4a, which touches no
default-path behavior at all:

- `testsolve()`'s reported end seed and any run whose path-to-path stream
  boundaries depended on `MAX_RI`'s reservation walk — removing that walk
  changes the observable schedule (`docs/end-seed-scope.md`) structurally
  for every multi-path `testsolve` run, regardless of whether any
  individual path's iteration count ever got near the old 200.
- **Every `crnflag=False` run's stream positions**, once the non-CRN
  branch switches from the running ordinal to `offset_within_iteration`/`point_code`
  (§2, §3.4, §4.1) — this is the larger of the two changes in practice.
  Checked directly against `tests/test_golden.py`: of its 8 CLI cases
  plus the 2 library-level cases, only `rperle_tpa_crn` passes `--crn`;
  the other 9 (`rperle_tpa`, `rminrle_tpa`, `rpe_tpa`, `rspline_simpleso`,
  `testsolve_tpa`, `rperle_tpa_seed2`, `rperle_tpa_simpar2`, and both
  `test_library_*_end_seed_matches_baseline` cases) are all `crnflag=
  False`. An earlier draft of this section said "`solve()`'s goldens are
  unaffected [by MAX_RI removal]" — that's still true of MAX_RI in
  isolation (`get_solv_prnstreams` never used it), but wrong as a
  statement about step 4b as a whole once the non-CRN fix is bundled into
  it: nearly the entire golden suite moves, `solve()` cases included, not
  only `testsolve()`'s multi-path cases. `rperle_tpa`/`rperle_tpa_simpar2`
  should still match *each other* post-fix (`--simpar` doesn't enter the
  coordinate formula, §3.4), which is a property worth asserting
  explicitly when regenerating rather than only checking each against a
  fresh baseline independently.

Both moves require the same sign-off any golden regeneration requires per
CLAUDE.md ("NEVER regenerate or edit them without being asked") —
`tests/test_golden.py` (nearly all cases) and
`tests/test_solution_sensitivity.py`'s `EXPECTED_SOLUTIONS` (which
depends on `isp=4`'s path-to-path *and* point-to-point behavior) need
deliberate, reviewed regeneration at step 4b, in one pass, not two.

### 8.1 What actually verifies step 4b, given the golden suite mostly can't

Asked directly, so answered directly rather than assumed: with 9 of 10
`test_golden.py` cases moving and `test_solution_sensitivity.py`
regenerated as part of the same step, neither provides a continuity
check *across* step 4b — both encode step 4b's output, they don't verify
it independently. That's a real gap against this project's own working
agreement ("a regression test must be observed failing before the fix
lands"), not a minor one, and it's worth inventorying precisely rather
than leaving "presumably fine" standing in for an answer.

**What does carry real weight, checked, not presumed:**

- `rperle_tpa_crn` — the one `test_golden.py` case that does *not* move
  at step 4b, precisely because it's the CRN branch, which §3.4 keeps
  structurally untouched by step 4b's changes. Its continued, unmodified
  presence is a genuine regression check that step 4b didn't leak into
  the CRN path — the one golden case actually doing continuity work
  here, and it's doing it by construction (isolating exactly the branch
  step 4b doesn't touch), not by coincidence.
- `test_jump_ahead.py` — stays green, but checked directly: it exercises
  `mrg32k3a()`/`jump_substream`/`get_next_prnstream`/the generalized jump,
  none of which step 4b touches at all. It's real, unmodified coverage of
  a layer step 4b doesn't change — which means it provides **zero**
  coverage of step 4b's actual risk surface (coordinate assembly, `ISP_
  STRIDE`, `point_code`). Worth being explicit that "stays green" here
  isn't evidence step 4b is correct; it's evidence step 4b didn't touch
  this file, a different and much weaker claim.
- `test_rng_consumption.py`'s two `ranx0`/`get_ranx0` tests
  (`test_getrandbits_draw_sequence_matches_baseline`,
  `test_get_ranx0_x0_and_stream_position_matches_baseline`) — checked
  directly against `get_testsolve_prnstreams`: `xprn = MRG32k3a(iseed)`
  is built from the caller's original `iseed` argument directly, before
  any `isp`/`MAX_RI`/oracle-stream threading happens, so `x0` selection
  is structurally independent of everything step 4b changes. These stay
  green and stay meaningful, but — same caveat as `test_jump_ahead.py` —
  meaningful about a path adjacent to step 4b's changes, not about the
  changes themselves.

**What does not, despite appearing to:** `test_solution_sensitivity.py`
and the 9 non-`--crn` `test_golden.py` cases are *updated by* step 4b,
not checks *of* step 4b — a passing test here after regeneration only
confirms the code produces whatever it produces, not that what it
produces is right. Treating them as coverage would be circular.

**The actual gap: nothing currently proposed exercises the new
chnbase.py-layer coordinate-assembly logic itself** — `point_code`'s
injectivity, its overflow-raises-rather-than-collides behavior, or an
operational (not just architectural) demonstration that visitation order
stops mattering. §7's conformance suite is scoped to the generator layer
(`stream_at` and below); nothing above that line was covered. §7.1 closes
this — items 8-9 land in step 3, items 11-12 in step 4a, all *before*
step 4b, not alongside it, and item 10's order-independence harness
specifically needs to be run against pre-step-4b code first and observed
failing (it's built and confirmed failing already at step 3, and stays
failing through 4a — see §7.1 item 10), the same discipline
`test_max_ri.py` already applied to demonstrating `MAX_RI` overlap before
that guard existed. Until all of §7.1 has landed and item 10 has been
seen to fail-then-pass, step 4b would be landing on "the golden suite
went quiet" rather than "the change was verified" — not acceptable per
the working agreement, and not what this document is proposing.

### 8.2 What `endseed` becomes — settled (open question 8), superseding the "next unused `isp`" sketch above

**A guarantee, not a probability.** The framework tracks one running
high-water mark per run: the largest coordinate index actually passed to
`stream_at`, across every role a run touches (solver, oracle, and the
sync range if `sync=` was used, §4.3) — updated on every `stream_at`
call, not derived after the fact. **Landed differently, oracle-role
only — see the "Wired in as of step 8 stage 1" note below** for why
solver-role isn't covered and why that's a real, stated limitation
rather than a gap in "every role" above; everything else in this
section (the guarantee's shape, its caveat, the opaque-token framing)
is unchanged from the original design. At the end of `solve()`/`testsolve()`,
`endseed` is the seed value `stream_at(root, high_water_mark + 1)` would
produce — computed directly from a known extent, not read off wherever
an accumulated walk happened to stop (the concept §5/§8 already
established doesn't exist for a coordinate-derived stream). This
supersedes the earlier "report the seed for `index(role=oracle/solver,
isp=next unused, 0, 0)`" sketch in the original text of this question:
that framing was `testsolve`-shaped (it only makes sense where distinct
`isp` blocks exist) and conservative in a way that buys nothing (it
reserves an entire unused `ISP_STRIDE` block rather than reporting the
tightest safe value); tracking the actual high-water mark works
identically for `solve()`'s single path and `testsolve()`'s many, so nothing
`isp`-specific is needed.

**What the guarantee is, precisely, and its caveat.** By `stream_at`'s
determinism (§3.1) and the same jump-composition reasoning §2 uses for
the CRN branch, a follow-up run started fresh from `endseed` as its own
`base_seed` occupies underlying recurrence positions strictly beyond
every position this run actually touched — computed disjointness, not a
birthday-bound argument, the same standard §3.4 held `point_code` to.
The caveat is exactly where that guarantee's scope ends: it covers
non-overlap with *this run's own consumed extent*, not non-overlap
forever — a pathological follow-up run, run from `endseed` and itself
consuming enough coordinate range, could still wrap the generator's
period and re-enter positions the original run touched. For MRG32k3a
this is not a practical concern — its period (~2**191, L'Ecuyer 2002) is
astronomically larger than what even a run reaching the old 200-iteration
ceiling consumes (order ~2**28) — so it's recorded here as a documented
caveat, not an enforced boundary. That check is per-generator, not
assumed to transfer: **where a generator's capacity bound is actually
reachable — flagged specifically for Philox-4x32, depending on how its
onboarding (§12 step 6) partitions the counter between `(key,
counter)` — the boundary must raise** (tying into §3.2's "documented
coordinate capacity per backend") rather than silently permit a
computation past it. This is a per-generator decision made at that
generator's own onboarding step, not something this document fixes for a
backend not yet built; MRG32k3a's own case is settled here because its
margin is checked, not assumed.

**Opaque token, same as today.** `endseed`'s reported value carries no
decodable meaning — CLAUDE.md is explicit that the seed "does NOT
fingerprint a run's randomness," and nothing here changes that framing,
it only changes how the value is computed. Its only two properties are
(1) it round-trips through the selected generator's own `validate_seed`
(§3.7) — same shape as any other `--seed` value, six integers for
MRG32k3a, whatever Philox's own shape is — and (2) users copy-paste it
into a follow-up `--seed`, they don't interpret it. No new "readable"
representation is being introduced.

**Wired in as of step 8 stage 1 (`solve()`'s own path) — oracle-role
only, a deliberate, stated scope, not "every role" above.**
`Oracle.get_endseed()` (`pymoso/chnbase.py`) tracks `_high_water_mark`,
updated at every call site that computes an oracle-role coordinate:
`hit()`'s CRN branch (at this step, `bump()` under `crnflag=True` did
the same, sharing the mechanism — `bump()` has since been removed
outright, §12 step 6b, not converged, since it had no in-tree caller),
and `_hit_via_coordinate`'s offset/sync branches alike.
`RASolver.solve()`/`rasolve()` and MOCOMPASS/MOPBnB's own `solve()`
methods (all three, not just `RASolver` — fixing one and not the other
two would be worse than fixing neither) now report `orc.get_endseed()`
instead of `orc.rng.get_seed()`.

**Solver-role is explicitly out of scope, and here's why that's safe in
practice, not just unaddressed:** `RASolver`'s own `sprn`/`solvprn`
(and `RLESolver`'s equivalents) are not coordinate-based — no onboarded
generator's `stream_at` covers solver-role yet — so they draw as an
ordinary, uninstrumented `MRG32k3a` stream, one raw step at a time.
Reaching the coordinate region oracle-role's own `ITER_STRIDE`-scaled
coordinates occupy would take on the order of `2**127` such draws —
not reachable by anything that runs to completion, so `get_endseed()`'s
guarantee holds *in practice* against solver-role's own draws too, but
that's a consequence of solver-role's draw volume being astronomically
small relative to `ITER_STRIDE`, not something this method tracks or
checks. A caller that actually needs the guarantee to cover solver-role
formally (not just practically) is relying on something `get_endseed()`
does not yet provide — recorded as a real, stated limitation, not
"every role" as the original text above claimed before this landed.

**Confirmed, not assumed, that oracle-role tracking fixes the concrete
gap this section identified before landing:** MOCOMPASS and MOPBnB,
which used to report *identical* `endseed`s for identical
seed/problem/budget despite verified-different internal consumption,
now diverge — `1146796796...` vs `3809509318...` for the
`mocompass_tpa`/`mopbnb_tpa` golden cases, checked directly.

**A finding, surfaced and accepted, not forced to match a
pre-registered expectation:** `rperle_tpa_crn` — the one CRN-branch
golden case, expected *not* to move (the CRN branch's own coordinate
formula was reasoned, before implementing, to already coincide with a
true high-water mark) — moved anyway. Traced precisely: `rasolve()`'s
loop calls `self.orc.crn_advance()` unconditionally after every
`spsolve()`, including the final one that exhausts the budget (the
`while` condition is only checked at the top of the loop, so this last
`crn_advance()` runs with nothing after it). Combined with the
pre-existing offset between `nu` and `Oracle._iteration` (iteration
`nu`'s own `spsolve()` runs at `orc._iteration = nu - 1`;
`crn_advance()` then bumps `_iteration` to `nu`), the old endseed
(`orc.rng.get_seed()` after that trailing `crn_advance()`) reported
`nu_final * ITER_STRIDE` — a full, unused `ITER_STRIDE` (`2**127`) past
the last iteration whose replications were actually drawn
(`(nu_final-1) * ITER_STRIDE + m * REPL_STRIDE`). Confirmed directly by
instrumenting a real run: every `hit()` call happened at
`orc._iteration = 6`, `m = 4`, giving a high-water mark of exactly
`6*ITER_STRIDE + 4*REPL_STRIDE` — bit-for-bit what `get_endseed()`
computed. **The pre-registered expectation was wrong, not the
implementation**: it didn't account for this trailing, unconditional
`crn_advance()` call. The new value is not a regression — it's tighter
(reflects real consumption) while remaining provably safe (nothing ran
at `_iteration = nu_final`, so nothing beyond the new value was ever
touched); the old value was simply more conservative than it needed to
be, for the CRN branch specifically. This also makes the CRN case
consistent with every other one: every `endseed` now reflects actual
consumption rather than a reserved position, oracle-role-wide, not just
for the cases that already visibly collided. The trailing
`crn_advance()` call itself is left alone deliberately — harmless now
that `endseed` no longer depends on `rng`'s own walk position, and
restructuring `rasolve()`'s loop to save one unused jump is churn on a
path everything else depends on for no behavioral gain. Noted here as
an observation, not a to-do.

**Every `crnflag=False`/CRN golden moved in this pass** — not only the
MOCOMPASS/MOPBnB pair and `rperle_tpa_crn`: the mechanism changed for
all of them, even though the step-4b/step-8-prerequisite values already
reflected *something* real, just not the high-water mark this section
promises. `testsolve()`'s own end seed was unaffected by this stage —
still `get_testsolve_prnstreams`'s reservation value at that point, a
separate piece of scope, staged as its own follow-on (stage 2, below).

**`testsolve` keeps the same logic as `solve`, deliberately, not as a
special case — landed as stage 2.** The single high-water-mark tracked
across every `isp` path a `testsolve` run touches, exactly the mechanism
above: each path's own `Oracle.get_high_water_mark()` combined as
`max(t*ISP_STRIDE + local_max_t)` (`t*ISP_STRIDE` is what makes
different paths' coordinate ranges disjoint in the first place, §6/§12
step 4b, so this reduces to a single `max` over `isp` terms, not a
merge across overlapping ranges) — the follow-up-run use case this
exists for barely applies to `testsolve` (its own multi-path structure
isn't typically chained the way a `solve` run's `endseed` is), but a
second code path bought nothing here that the first didn't already
provide, and a special case would only be a second thing to keep
correct. Confirmed, not just designed: the three-way
`testsolve_tpa`/`testsolve_mocompass`/`testsolve_mopbnb` match — bit-
identical before this landed, despite each running a different solver
across the same 4 `isp` paths — now breaks, each reflecting its own
solver's real consumption. Full account, including the `--proc` worker-
boundary mechanism (`oracle_high_water_mark` as a new result-dict key,
not the `Oracle` object itself, which never crosses back from a worker
process unchanged) and a new, correct `ranx0`-sensitivity this exposes,
in §12's own step 8 entry.

## 9. Proposed module layout

Not load-bearing for the design itself, but concrete enough to plan
steps against:

```
pymoso/prng/
  base.py          # Stream / stream_at protocol (typing.Protocol or ABC),
                    # the compatibility-adapter base class, and
                    # point_code/offset_within_iteration (§3.4) -- generator-
                    # agnostic pure-integer coordinate assembly, used by
                    # every backend's crn=False branch identically
  mrg_common.py     # generalized matrix-power jump (parameterized by a
                    # recurrence's matrices/moduli), shared by mrg32k3a.py
                    # and mrg31k3p.py
  mrg32k3a.py       # existing recurrence + matrices, refactored onto
                    # mrg_common's generalized jump; jump_substream/
                    # get_next_prnstream kept as thin wrappers
  mrg31k3p.py       # new
  philox4x32.py     # new
```

`point_code`/`offset_within_iteration` live in `base.py`, not per-backend,
because §3.4's scheme is pure integer arithmetic over `x`/`visit`/
`replication` with no dependency on which generator consumes the result —
every backend's `crn=False` branch calls the same function and only
differs in how it turns the resulting integer into a stream (§3.4,
§3.5). This is also where §7.1's coordinate-assembly tests live, as tests
of `base.py` directly, independent of any specific backend.

`chnbase.py`/`chnutils.py` depend only on `base.py`'s protocol plus
whichever concrete backend is selected via §3.8's `--generator`
flag/kwarg.

## 10. What breaks for existing custom solvers/oracles

- `Oracle.g(self, x, rng)`: unchanged. Not broken.
- Anything calling `rng.<any random.Random method>` inside `g()`:
  unchanged, via the adapter (§3.6). Not broken.
- Direct calls to `Oracle.crn_reset`/`crn_advance`/`crn_setobs`/
  `crn_check`, or reads of `crnold_state`/`crn_obsold`, from a custom
  *solver* (not oracle) that manages CRN itself beyond what `RASolver`
  already does: **breaks**, deliberately — settled in §11 item 7 (remove,
  not deprecate), not just recommended. No longer a hypothetical
  "grep finds no in-tree caller" judgment call: two real external
  solvers, MOCOMPASS and MOPBnB, are exactly this case — each calls
  `orc.crn_advance()` directly (§4.2) — and the finding there is that the
  call doesn't just become obsolete, it was silently defeating `--crn`
  all along. Their own migration is "delete that line," not "call this
  instead" — there's nothing to preserve a compatibility path to.
- Direct imports of `prng.mrg32k3a.get_next_prnstream`/`jump_substream`/
  `mrg32k3a`/`bsm`: unchanged in the module they live in (§9 keeps
  `mrg32k3a.py` as a real module with these names), so anyone importing
  them directly keeps working, though `bsm` becomes shared, publicly
  re-exported machinery (§3.3, §4.2 — confirmed needed, not hypothetical:
  MOPBnB reimplemented it byte-for-byte rather than finding the existing
  one).
- Both external reference solvers fail outright on `.venv-dev` (3.14) as
  written — `random.Random.sample()` no longer accepts a `set` argument,
  and both call `self.sprn.sample()` on sets throughout. Pre-existing,
  orthogonal to this redesign (a stdlib change, not a `pymoso` one), but
  real: neither runs on the dev environment without a fix unrelated to
  anything here (§4.2).
- `Oracle.hit(x, m)` gaining `visit=0`/`sync=None` parameters (§4.1,
  §4.3): additive, default-compatible. Not broken — including for a
  custom `MOSOSolver` that already calls `hit()` directly today, since
  omitting both reproduces its current single-visit-per-point behavior
  exactly. A solver ported to use `sync` explicitly (MOCOMPASS, §4.3)
  gets to delete state (`self.seeds`, every `getstate`/`setstate` call),
  not add any — but, unlike every other bullet in this section, that
  port is not a pure compatibility no-op for MOCOMPASS specifically: its
  own numerical output moves, on purpose, because §4.3's correction
  found `self.seeds` never gave it the paper's synchronization beyond
  each checkpoint's first replication. This is the one item in this
  "what breaks" section that names a genuine behavior change, not
  reassurance that nothing does.

## 11. Open questions

Answering these was explicitly asked for in some cases (marked); the
rest are genuine forks not resolved by anything in CLAUDE.md or the
existing code, surfaced rather than guessed.

1. **[asked] Does the interface expose jump-ahead?** No — answered in
   §3.5. `stream_at(base_seed, coordinate)` only.
2. **[asked] Is monotonicity an interface or implementation requirement?**
   Interface — answered in §3.3, with the getrandbits exemption stated
   explicitly.
3. **[asked] Bit-identical preservation?** Yes for the generator
   primitives, permanently; yes for the CRN branch, permanently (§2); yes
   for the non-CRN branch, through steps 3 and 4a, via a temporary
   compatibility encoding that 4a's additive `visit=`/`sync=` opt-ins
   leave untouched for every default-shaped call; no, by design, for both
   `testsolve`'s end seed *and* every `crnflag=False` run once step 4b
   lands — answered in detail in §8, including exactly which goldens move
   (nearly the whole suite, corrected from an earlier, narrower draft of
   this answer) and why.
4. **MRG31k3p's concrete jump matrices/stride sizing.** L'Ecuyer & Touzin
   (2000) presumably documents recommended stream/substream spacing for
   MRG31k3p the way the 2002 O-O RNG paper does for MRG32k3a; this design
   does not fabricate matrix values without the paper in hand.
   Alternative if the paper doesn't hand them over directly: derive them
   the same way `test_jump_ahead.py`'s reference implementation already
   demonstrates is tractable — generalized matrix power of MRG31k3p's own
   base recurrence matrix, computed in exact Python integers, no need for
   pre-published fixed-power matrices at all. Either way, this is an
   implementation task for the MRG31k3p step, not a design blocker.
5. **[settled — arithmetic, not policy] Concrete sizing for
   `ISP_STRIDE`, and for `REPL_BITS`/`VISIT_BITS` in the non-CRN
   branch's `offset_within_iteration`** (§3.4), and independently,
   verifying the whole index stays well inside each generator's proven
   recurrence period so it never wraps. `ISP_STRIDE` is a
   literature-period check per generator. `REPL_BITS`/`VISIT_BITS` were
   framed as policy choices in the original draft of this question,
   pending open question 9's resolution — with 9 settled (removed
   entirely, no ceiling), there is no chosen `nu` ceiling left to size a
   margin against, only `nu`'s actual bound: a run can't exceed roughly
   `budget` RA iterations in the degenerate case where an iteration
   consumes as little as one simulation call (a real `RASolver` consumes
   far more per iteration in practice, since `spsolve` calls `estimate`
   repeatedly; `budget` is the loose, checkable worst case, not a typical
   one). So this is now a direct computation — confirm the values
   proposed in §3.4 (32/20), already checked once against `calc_m`'s
   growth at the old `nu=200`, against the realistic *range* of
   `--budget` values instead, and write the resulting margin down in the
   generator's own docs. No further design judgment call remains here.
6. **[settled] Generator selection mechanism.** A CLI flag plus the
   matching `solve()`/`testsolve()` kwarg — the same shape as
   `--budget`/`--crn` — scoped per-run (one backend for the whole run,
   not per-role or per-oracle), recorded in the run's saved metadata
   alongside `startseed`/`endseed` — decided in §3.8, which also states
   why the alternatives (per-role, per-`Oracle`-class) were ruled out
   rather than merely undiscussed. §3.7 specifies how `--seed` behaves
   *given* a selection; §3.8 is what makes a selection exist to give.
7. **[settled] Deprecation of direct `crn_*` access.** Remove entirely,
   not deprecate — decided, with two independent arguments, in §4.2:
   framework leakage (a solver shouldn't be making this decision at all),
   plus direct evidence that the one call site both real reference
   solvers actually contain (`crn_advance()` once, at the end of
   `solve()`) silently breaks `--crn` rather than merely being redundant
   under it (§4.2's `fx1 == fx3` demonstration). No shim — a
   deprecated-but-callable `crn_advance()` would keep the exact footgun
   alive for anyone who copies the same pattern, not preserve a real
   capability.
8. **[settled] What `endseed` becomes, concretely.** §5/§8 establish that
   a raw mutable-`rng`-derived seed no longer has a natural single
   "current position" to report. Decided in §8.2: report the seed that
   `stream_at(root, high_water_mark + 1)` would produce, where
   `high_water_mark` is the largest coordinate index the run actually
   passed to `stream_at` across every role it touched — a guarantee
   against overlap with what the run actually consumed, not a
   probabilistic one, with a stated, checked caveat (wrap-around is not
   practically reachable for MRG32k3a; must raise rather than silently
   permit for a generator, flagged for Philox-4x32, where it is). Opaque
   token at the CLI, same shape `validate_seed` (§3.7) already defines;
   `testsolve` uses the identical logic as `solve`, deliberately, not a
   special case. Supersedes the earlier "next unused `isp`" sketch that
   stood here.
9. **[settled] Does `RASolver.rasolve` keep an iteration-count ceiling at
   all** (§6), once `MAX_RI`'s collision-avoidance reason is gone?
   Removed entirely, not repurposed — no replacement runaway-loop guard.
   A generous fixed ceiling would only be a new arbitrary constant
   invented for no reason connected to stream headroom, the thing that
   motivated the old one. Consequence, checked, not hypothetical: the
   README's own `MyRAAlg` template (a solver whose `spsolve` never calls
   `self.estimate`, so `nu` never stops growing) currently fails fast —
   `RuntimeError` after 201 iterations via the guard being removed here
   — and will hang indefinitely once this lands. Tracked as part of step
   4's own deliverables (§12), not a follow-on.
10. **`SYNC_ROLE_OFFSET`/`SYNC_STRIDE` sizing** (§4.3) — how much of the
    coordinate space `sync`-mode reserves, and how large a `sync` value
    (and how many `replication`s per value) it supports before running
    into the same period ceiling `ISP_STRIDE`/`ITER_STRIDE` are checked
    against (open question 5). `nx[x]` in MOCOMPASS grows with total
    replications taken, so its plausible range is the same order as
    `REPL_BITS`'s own sizing check (`calc_m`-scale, not `MAX_RI`-scale,
    since `sync` here is a solver's own running count, not an iteration
    index) — worth confirming against a real run rather than assumed
    identical, since a general `MOSOSolver`'s `sync` values aren't
    guaranteed to grow the way `calc_m` does.

## 12. Step list

Each step names what lands and whether it's behavior-preserving (goldens
stay green, checked by §7 item 7 where relevant) or deliberately
behavior-changing (goldens move, on purpose, with sign-off).

1. **[preserving]** Write the conformance suite (§7) against the
   *current* MRG32k3a, adapted to call through a thin `stream_at`
   wrapper around today's `get_next_prnstream`/`jump_substream`. This
   proves the test suite itself is meaningful before any real interface
   exists to test — a suite that never fails against a deliberately
   broken backend isn't proven to work, same discipline as everywhere
   else on this branch.
2. **[preserving]** Build `prng/base.py` (protocol + adapter) and
   `prng/mrg_common.py` (generalized matrix-power jump, extracted from
   `mrg32k3a.py`'s existing `mat333mult`/`mat311mod` plus a new
   arbitrary-exponent binary-exponentiation routine). Refactor
   `mrg32k3a.py` onto it; `jump_substream`/`get_next_prnstream` become
   thin wrappers calling the general jump at the two fixed exponents.
   `test_jump_ahead.py` passes unchanged — this step touches
   implementation, not the two hardcoded distances.
3. **[preserving]** Replace `chnbase.py::Oracle`'s CRN protocol per §4,
   using the compatibility-encoding coordinate function that reproduces
   today's exact enumeration order for *both* branches — the CRN branch
   permanently (§2, §3.4), and the non-CRN branch via a temporary
   running-ordinal coordinate (§3.4's note) that reproduces today's exact
   point-visitation order, deliberately not `offset_within_iteration`/
   `point_code` yet. Also land §7.1 items 8-9 (`point_code` exactness and
   overflow-raises) here — they test pure integer functions with no
   dependency on `crnflag` or how `chnbase.py` wires them in, so there's
   no reason to wait for step 4a to write and pass them, and doing so
   here means step 4a starts from already-verified building blocks
   rather than building and verifying them under the same change. Also
   land §7.1 item
   10's harness (the order-independence test) here, **run against this
   step's own code and confirmed still failing** — step 3 deliberately
   keeps the old order-dependent behavior for `crnflag=False`, so item 10
   failing at this point is expected and is itself the checkpoint that
   the harness actually detects the defect it's meant to detect, per the
   working agreement's "a detector never seen detecting isn't proven to
   work." Run §7 item 7 (the bit-identical migration proof) and
   `tests/test_golden.py`, `tests/test_solution_sensitivity.py`,
   `tests/test_rng_consumption.py` unchanged; all must stay green — every
   case, `crnflag=False` ones included, not just `rperle_tpa_crn`.
   `RASolver`/`RLESolver` untouched.
4a. **[preserving]** The mechanism, none of it load-bearing for any
   default call yet. Add `Oracle.hit`'s `visit=0` and `sync=None`
   parameters (§4.1, §4.3) as purely additive kwargs: at their defaults
   (`visit=0`, `sync=None` — what every existing caller passes, since
   `RASolver`/`RLESolver` never supply either), `hit()`'s coordinate
   computation is **untouched**, still routing through step 3's temporary
   running-ordinal/CRN encoding exactly as before. Only an explicit
   `visit!=0` or `sync=<int>` call routes through the real
   `offset_within_iteration`/`point_code`/index machinery — built as pure
   functions already in step 3 (items 8-9), extended here with its
   `ISP_STRIDE` component and the `REPL_BITS`/`VISIT_BITS` sizing
   constants (open question 5: confirm §3.4's proposed 32/20 split
   against the realistic `--budget` range now that no `nu` ceiling bounds
   it, and write the result into the generator's own docs — arithmetic,
   not a policy call, per open question 5's resolution). `SYNC_ROLE_OFFSET`
   (§4.3) lands here too, since item 12 below exercises it. Land §7.1
   items 11-12 (no collision past the old `MAX_RI` ceiling; `sync`'s
   coordinate space disjoint from the default's) — both exercised through
   these new, explicitly-invoked paths (item 11 against the index
   function directly; item 12 via direct `hit(x, m, sync=k)` calls), not
   through anything a real `solve()`/`testsolve()` run reaches. §7.1 item
   10's harness, unchanged from step 3, **stays failing** — the direct,
   checkable confirmation that this step hasn't touched the default path
   either. Every existing golden stays green, checked the same way step 3
   was (§7 item 7, `test_golden.py`, `test_solution_sensitivity.py`,
   `test_rng_consumption.py` all unchanged).

   This split is real, not cosmetic, specifically because nothing here
   requires the default path to move: `visit`/`sync` are new arguments
   nothing existing supplies, `ISP_STRIDE`-based collision-freedom (item
   11) is a property of the index formula itself, checkable without
   `get_testsolve_prnstreams` actually using it yet, and `sync`'s
   disjointness (item 12) is a property of which *role* region a
   coordinate falls in, independent of what the oracle-role default
   currently computes. If any of that had turned out to require the
   switch below to already be in effect, this document would say so and
   keep step 4 whole rather than claim a separation that isn't real — it
   doesn't.

   **Convergence item, found during implementation, not designed in
   advance: `_hit_opt_in` (the method backing `visit`/`sync`) is a
   second replication loop, structurally parallel to `hit()`'s own —
   same shape CLAUDE.md's own working agreement already flags for
   `bump()` ("duplicates `hit()`'s replication loop," the stated reason
   `bump()` is being removed).** It already drifted once before landing:
   an early version omitted `hit()`'s `m==1` special case (avoiding
   `statistics.variance()`'s two-point minimum), caught only because a
   test happened to call it at `m==1` (§7.1's own tests, not any
   production path). Two independent implementations of the same
   replication-and-aggregation logic is exactly the shape that produces
   this class of bug — a fix to one loop's edge case not propagating to
   the other's, silently, until something exercises the gap. Not
   resolved here: `hit()` and `_hit_opt_in` differ only in how a
   replication's stream is obtained (the live, advancing `rng` versus a
   coordinate computed fresh per call), not in what happens to the
   result once obtained (feasibility check, mean/variance aggregation,
   `m==1` short-circuit) — that shared part should become one function
   the two paths both call, not two copies kept in sync by discipline.
   Whether that unification happens as part of step 4b (once the
   default path also moves to coordinate-based computation, at which
   point `hit()` and `_hit_opt_in` may converge on their own) or is left
   for the executor rework (CLAUDE.md's in-flight decision, "work
   expressed as data... seeds as computed values rather than object
   state" — a rework that touches this exact seam) is an open call, not
   decided here; recorded so it doesn't ship as two replication loops
   indefinitely by default by nobody having named it.
4b. **[behavior-changing, needs sign-off]** The switch: two changes,
   bundled, because both restructure the same schedule and regenerating
   goldens twice for overlapping reasons wastes a review pass. (a) Remove
   `MAX_RI`'s reservation walk from `get_testsolve_prnstreams` (§6),
   switching `isp` to the direct `ISP_STRIDE`-based offset 4a already
   validated in isolation (item 11) — now used for real. (b) Switch the
   non-CRN branch's *default* coordinate (i.e., delete 4a's
   `visit=0`-and-`sync=None` special case) from step 3's running ordinal
   to `offset_within_iteration`/`point_code` (§2, §3.4, §4.1), fixing the
   order-dependence defect for every ordinary call. (c) Remove
   `RASolver.rasolve`'s `nu > MAX_RI` check outright (open question 9,
   settled) — no replacement guard. Re-run §7.1 item 10's harness, **now
   required to pass** — that pass is the actual regression-test evidence
   for the fix (§8.1), not the regenerated goldens, which by this point
   only confirm the code changed, not that it changed correctly.
   Regenerate `tests/golden/`'s cases — essentially all of them, per §8's
   corrected accounting, not only `testsolve_*` — and
   `test_solution_sensitivity.py`'s `EXPECTED_SOLUTIONS`, deliberately,
   with review: per CLAUDE.md, goldens are never touched without being
   asked, and this step is exactly that ask, made *after* §7.1's own
   tests are green, not as a substitute for them. Confirm
   `rperle_tpa`/`rperle_tpa_simpar2` still match each other post-fix (§8)
   as part of that review, not just each against a fresh baseline.

   **Also part of this step, not a follow-on:** (c)'s guard removal
   changes what stops `MyRAAlg` (README's "Template RA Solver,"
   `pymoso/examples/myraalg.py`) -- checked directly: `spsolve` never
   calls `self.estimate`, so `self.num_calls` never advances, and today
   that loop is stopped only by the guard this step deletes, confirmed
   by `test_readme_examples.py`'s own `test_myraalg_spsolve_runs_
   directly` docstring ("it now hits the MAX_RI guard after 201 fast,
   simulation-free iterations, for any budget"). **Not an indefinite
   hang** -- an earlier draft of this section predicted one, corrected
   here against the actual landed code rather than left standing: run
   directly, `RASolver.rasolve`'s own `calc_b(nu) = ceil(bconst*(dim-1)*
   1.2**nu)` overflows to a Python float `inf` around `nu≈3882` (`calc_m`'s
   `1.1**nu` would overflow later, ~7449, but `calc_b` runs first each
   iteration and gets there sooner), and `ceil(inf)` raises
   `OverflowError` -- confirmed empirically, `nu=3882` reached in 0.03s.
   So the actual change is from one fast, clearly-labeled failure
   (`RuntimeError` naming `MAX_RI`, after 201 iterations) to a different
   fast, confusing one (`OverflowError` naming neither `MyRAAlg` nor the
   real cause, after ~3882) -- both terminate quickly; neither reaches a
   normal budget-exhausted stop. Three concrete actions, all landing
   here:
   - Add a `KNOWN_ISSUES.md` entry (next number after 11, alongside
     issue 8 in the "Behavior changes introduced by this migration"
     section — the same category, since this isn't inherited from any
     released version either) stating the change precisely: before this
     step, `MyRAAlg` run via `solve()` raises `RuntimeError` naming
     `MAX_RI` after 201 iterations; after, it raises `OverflowError`
     from `calc_b` after ~3882 iterations, naming neither `MyRAAlg` nor
     the actual cause. Not written before this step lands — the
     condition it describes isn't true until then (working agreement:
     state things accurately, not in advance of being true, and not
     predicted instead of checked).
   - Update README's "Template RA Solver" prose (currently: "this
     template never terminates when run via `solve()`, at any budget...
     the retrospective-approximation loop cannot reach a normal
     budget-exhausted stop") — the second clause stays true before and
     after this step (neither failure mode is a budget-exhausted stop);
     the first clause ("never terminates") was never literally true
     either way (both a `RuntimeError` and an `OverflowError` are
     terminations) and shouldn't imply the process hangs. Reword to name
     the actual post-step-4b behavior (an unrelated-looking crash after
     thousands of fast iterations) rather than leave a reader to infer
     it, and to stop implying "never terminates" means "hangs."
   - Checked now, not assumed: **nothing in the test suite currently
     needs marking or skipping.** `test_myraalg_spsolve_runs_directly`
     calls `spsolve` directly (never enters `rasolve`'s loop) and
     `test_algorithm_snippets_run_against_a_live_solver` `exec`s the
     README's algorithm snippets directly against a solver instance
     (also never calls `rasolve`) — both were already written to avoid
     the full loop, specifically because of the guard's existing
     behavior. Neither is affected by the guard's removal (and even if
     they were, the actual behavior is a fast crash, not a hang, so
     pytest-timeout would not have been the mechanism that caught it
     either way). If a future test is ever added that does call
     `MyRAAlg.solve()`/`rasolve()` to completion, it must be marked or
     skipped with a reference to the new `KNOWN_ISSUES.md` entry as part
     of *that* change, not this one.
5. **[new capability — done]** Onboard MRG31k3p: source or derive its
   recurrence matrices (open question 4), implement on `mrg_common.py`,
   full §7 suite including the brute-force jump proof (§7 item 3)
   specific to MRG31k3p. No existing goldens touch this generator, so
   nothing here can move them — confirmed directly, not assumed: full
   suite green on both venvs after landing, no `test_golden.py`/
   `test_solution_sensitivity.py` case moved.

   Landed as `pymoso/prng/mrg31k3p.py` (the `MRG31k3p` class,
   `mrg31k3p()`'s own exact-integer single-step recurrence, `jump_seed_n`/
   `get_next_prnstream`/`jump_substream` mirroring `mrg32k3a.py`'s own
   structure) and `tests/test_mrg31k3p_conformance.py` (52 tests: §7
   items 1/2/3/5/6, the cached-exponent-vs-general-path check, and the
   deliberately-broken-backend proof, re-verified against this generator
   specifically rather than assumed to carry over from `tests/
   test_prng_conformance.py`'s own MRG32k3a-specific proof). Items 4 and
   7 don't need re-testing here — see the new test file's own docstring
   for why. `stream_at` is not the narrow "thin" stand-in step 1 used
   (that existed only because the general jump didn't yet); MRG31k3p
   goes straight to the real, arbitrary-coordinate `jump_seed_n`, since
   step 2's generalized machinery already exists and needed no changes
   to support a second generator — confirming the interface genuinely
   fits, not just in principle.

   `REPL_STRIDE`/`ITER_STRIDE` are reused directly from `mrg32k3a.py`,
   not redefined — every coordinate constant sized against MRG32k3a's
   period stays global, not per-generator, per the margin arithmetic
   below. `mrg_common.py`'s `mat_pow_mod`/`jump_n` needed zero changes:
   already parameterized on matrix and modulus, exactly as its own
   docstring anticipated. `bsm` is reused verbatim for `normalvariate`
   (imported, not copied) — generator-agnostic by construction, per §3.3.
   No `REPL_RESERVE_STRIDE`-cached jump is built for MRG31k3p at this
   step — nothing calls its replication-coordinate path yet (this
   generator isn't wired into `chnbase.py` at all, see below), so
   caching it now would be speculative rather than the "cache what a
   measured regression proved matters" discipline step 2's own commit
   established.

   **Constants, sourced, not fabricated.** Primary source:
   `MRG31k3p.java` from L'Ecuyer's own SSJ library
   (github.com/umontreal-simul/ssj, `src/main/java/umontreal/ssj/rng/
   MRG31k3p.java`) — executable reference code from the generator's own
   author, cited there as L'Ecuyer & Touzin, *Fast Combined Multiple
   Recursive Generators with Multipliers of the Form a = ±2^q ±2^r*
   (WSC 2000). The original paper itself was not read directly (not
   fetched); this is a real distinction from a from-the-paper citation,
   stated plainly rather than implied away. `M1 = 2147483647` (2^31−1,
   a Mersenne prime), `M2 = 2147462579` (2^31−21069), independently
   corroborated by a second implementation's documentation (Theano).
   Recurrences derived two independent ways from the same SSJ source —
   decoding its fast bit-shift step implementation, and cross-checking
   against its own separately-published exact one-step jump matrices —
   both agreeing exactly:
   ```
   Component 1 (mod M1): x1(n) = (4194304·x1(n-2) + 129·x1(n-3)) mod M1
   Component 2 (mod M2): x2(n) = (32768·x2(n-1) + 32769·x2(n-3)) mod M2
   ```
   Output `z = (x1(n) − x2(n)) mod M1`, normalized — the same
   difference-of-components combination MRG32k3a uses. `NORM = 2**-31`
   exactly (confirmed by direct computation against SSJ's own literal,
   `4.656612873077392578125e-10`) — deliberately not `1/M1`, so the
   boundary case normalizes strictly below `1.0` rather than to exactly
   `1.0`, matching SSJ's own "must never return either 0 or 1" comment.

   **A third, independent validation, done at implementation time, not
   assumed from the sourcing above:** the companion matrices
   `pymoso/prng/mrg31k3p.py` actually uses were checked against SSJ's own
   published one-step jump matrices (`A1p0`/`A2p0`) via exact linear
   algebra — SSJ's state-vector convention is the reverse of this
   codebase's own (newest-first vs. oldest-first, matrix coefficients in
   the first row vs. the last), so `A1p0`/`A2p0` conjugated by the
   reversal permutation must equal this module's own `_m1_step`/
   `_m2_step` if both are correct; computed by hand and confirmed exact
   for both components, not merely plausible. A from-scratch
   reimplementation of SSJ's exact bit-shift `nextValue()` (Java int32
   semantics emulated) additionally reproduced this module's own first
   three draws from the default seed exactly, diverging afterward from a
   bug in that reimplementation's own incomplete overflow emulation —
   noted rather than hidden, since the matrix-conjugation proof above
   already settles correctness independent of that script's own defect.

   **Period does not transfer from MRG32k3a, and needed its own check.**
   SSJ's own javadoc states `ρ ≈ 2**185`, citing the same paper. A
   separate summary described "period near 2^186, with 2 cycles near
   2^185" — not chased down further (per instruction: the two readings
   may both be true simultaneously, since total state space and
   individual cycle length are different quantities, and either way
   `2**185` is the more conservative figure and changes no downstream
   constant). Treated as **unresolved but conservatively handled**:
   every margin check below uses `2**185`, the smaller of the two
   readings.

   **Existing coordinate constants checked against `2**185`, not
   reused on faith — kept global, not made per-generator.** Every
   `ISP_STRIDE`/`SYNC_ROLE_OFFSET`/`REPL_STRIDE`/`ITER_STRIDE` value
   (mrg32k3a.py, sized against MRG32k3a's own `2**191`) stays safely
   under `2**185` too, computed directly:

   | Constant | Value | Headroom under `2**185` |
   |---|---|---|
   | `REPL_STRIDE` (CRN replication spacing) | `2**76` | `2**109` replications before wrap |
   | `ITER_STRIDE` (RA iteration spacing) | `2**127` | `2**58` iterations before wrap |
   | `ISP_STRIDE` (isp path spacing) | `2**159` | `2**26` isp paths before wrap |
   | `SYNC_ROLE_OFFSET` (sync zone start) | `2**175` | `2**10` (1024×) — the tightest ratio in the scheme |
   | sync values available past `SYNC_ROLE_OFFSET` | `SYNC_STRIDE = 2**108` | `2**76` sync values |

   Sanity-checked against L'Ecuyer's own chosen margins for MRG31k3p in
   SSJ (`W = 2**72` substream, `Z = 2**134` stream, both against his own
   stated `2**185`): `period/W = 2**113`, `period/Z = 2**51`. At the
   tier with a rough analog (`REPL_STRIDE` ≈ his substream `W`, both
   "one safely-isolated replication"), our margin (`2**109`) is in the
   same range as his (`2**113`), not wildly different. At the next tier
   (`ITER_STRIDE` vs his stream `Z`), ours is *more* generous
   (`2**58` vs `2**51`, ~128×) — flagged per instruction rather than
   assumed benign, but assessed as expected, not miscalibrated: our
   `ITER_STRIDE` governs a far finer-grained, far more frequently-
   incremented unit (one RA iteration within one run) than his "stream"
   (typically one whole independent generator instance in SSJ's own
   usage), so needing more headroom at that tier is the expected
   consequence of a finer unit, not evidence the constant is too loose.
   `SYNC_ROLE_OFFSET` has no real analog in his flatter substream/stream
   scheme (it is pymoso's own, novel policy-zone boundary, §4.3) — its
   `2**10` ratio is the tightest number in the table, but the absolute
   remaining space (`2**185 − 2**175 ≈ 2**185`) and its own actual
   downstream usage (`2**76` sync values available, dwarfing any
   realistic MOCOMPASS-scale need, itself checked against `--budget` in
   mrg32k3a.py's own comment) both remain enormous. **Conclusion: keep
   every one of these constants global, not per-generator** — nothing
   here is tight enough to need MRG31k3p-specific values, and making
   them per-generator would change the interface's own shape (a
   decision this finding does not call for).

   **`--generator` CLI/library wiring is out of scope for this step** —
   MRG31k3p will be real, tested code with no way for a user to select
   it until step 6b (below) lands.

   **No `validate_seed` implemented — checked, not silently skipped:**
   §3.7 describes a generator's own `validate_seed` as part of the
   `--seed` CLI validation story, but grepping the whole `pymoso/`
   package confirms no such function exists anywhere yet, not even for
   MRG32k3a — it's a CLI-layer concept tied to `--generator` selection
   (§3.8), which is step 6b's own scope, not step 5's. Implementing it
   for MRG31k3p alone, ahead of MRG32k3a having one, would invent an
   inconsistent precedent; deferred to land alongside step 6b instead.
6. **[new capability — done]** Onboard Philox-4x32: counter-packing `stream_at`
   (§3.4), `bsm()`-based `normalvariate` (reused as-is), full §7 suite.
   This is the step that actually tests §3.5's claim under load — if
   Philox needs anything from the interface beyond `stream_at`/`random`/
   `getrandbits`/`normalvariate`, that's the signal the interface
   under-specified something, and it needs to surface here, not be
   patched around quietly. It did — see §3.9, added by this step.

   Landed as `pymoso/prng/philox4x32.py` (`philox4x32_r`, the round
   function; `Philox4x32Stream`, deliberately *not* a `random.Random`
   subclass — the first real user of `base.RandomCompatAdapter`'s own
   stated purpose, rather than a second, divergent convention; `stream_at`)
   and `tests/test_philox4x32_conformance.py` (60 tests). Validated more
   strongly than step 5 could be: the round function matches Random123's
   own published known-answer-test vectors (`tests/kat_vectors` in that
   repository) bit-for-bit at three independent inputs, not just
   internal self-consistency — an external ground truth, not a
   from-scratch reimplementation checked against itself. Confirmed
   directly, not assumed: full suite green on both venvs after landing,
   no existing golden or test moved.

   **Constants, sourced, not fabricated.** Primary: Random123's own
   `philox.h` (github.com/DEShawResearch/random123, mirrored at
   thesalmons.org — John Salmon, the paper's own author). Corroborated
   independently by the C++ standardization proposal P2075 ("Philox as
   an extension of the C++ RNG engines"), which states the same
   constants and a checkable test vector.
   ```
   M0 = 0xD2511F53, M1 = 0xCD9E8D57   (round multipliers)
   W0 = 0x9E3779B9, W1 = 0xBB67AE85   (Weyl/key-bump constants)
   ```
   Round function (ctr = 4×uint32, key = 2×uint32), read directly from
   the source: `hi0,lo0 = mulhilo32(M0,ctr[0])`; `hi1,lo1 =
   mulhilo32(M1,ctr[2])`; `ctr' = (hi1^ctr[1]^key[0], lo1,
   hi0^ctr[3]^key[1], lo0)`. Key bump: `key' = (key[0]+W0, key[1]+W1)
   mod 2**32`. Round 1 uses the unbumped key; each later round bumps
   first, then applies the round function. Both multipliers are odd
   (checked, not assumed) — the round function's invertibility for a
   fixed key, which the "distinct coordinates → non-overlapping
   streams" guarantee rests on, depends on that.

   **Round count: 10**, `PHILOX4x32_DEFAULT_ROUNDS` in the same source —
   the library default, not the statistical minimum (Salmon et al. 2011
   report BigCrush passing at 7 rounds). Using 10 because that's what
   "Philox4x32" means in the ecosystem (numpy, PyTorch, the C++
   proposal all default to it), not a stronger claim than "matches
   established practice."

   **The capacity question (carried from §8.2), resolved into §3.9's
   finding, not a Philox-only fix.** Sized against budget-anchored
   ceilings, not period-anchored ones, per instruction, since RASolver's
   own `calc_m`/`calc_b` are that solver's schedule only — nothing in
   the framework bounds replications-per-iteration or iterations-per-run
   for an arbitrary `MOSOSolver`, only `--budget` does, loosely (each
   replication costs at least one unit of it). Chosen ceilings, recorded
   as policy, not derived:
   - **Replications/iteration and iterations/run**: `10**9` each —
     "implausible" defined against this project's own precedent
     (`mrg32k3a.py`'s own comment: nothing in this project's docs/
     README/tests has ever budgeted past 400,000; `10**9` is ~2500×
     beyond that). 30 bits each.
   - **Per-replication reserve**: 4096 counter positions (16,384 raw
     words) — the same ~16× BSProb-margin reasoning `REPL_RESERVE_BITS`
     already used, expressed in counter units (4 words/counter
     increment). 12 bits.
   - **isp count**: 10,000 paths, absurd against real `--isp` usage
     (single/double-digit in practice). 14 bits.
   - **Point/visit**: unchanged reasoning from §3.4 (BSProb's dim=9
     floor for point bits; minimal nonzero headroom for visit, no real
     caller yet).

   Even at these tight ceilings, one `isp` path's own full history
   (iteration count × one iteration's own point/visit/replication
   width) is 148 bits — **20 bits over Philox's 128-bit counter before
   `isp` multiplicity or `sync` ever enter it.** Not a margin problem:
   one iteration's own width alone (118 bits) fits with `2**10` to
   spare, so shrinking the tight layers further doesn't recover the 20
   bits without breaking something real (point bits are already at
   BSProb's floor). What resolves it is §3.9's stream/offset split, not
   a smaller number anywhere in this list — recorded there, not
   duplicated here, since it isn't specific to this step's own
   constants.

   Every constant in the table above — `REPL_STRIDE`/`ITER_STRIDE`
   included, unchanged from `mrg32k3a.py` — has always been a *chosen*
   policy number, not a derived one, and this document is correcting
   itself on that point rather than leaving the earlier framing to
   stand: `ITER_STRIDE = 2**127` was inherited from L'Ecuyer's own
   illustrative substream-spacing example (his package's own convention
   for "how far apart to space independent streams"), not derived from
   any pymoso-specific requirement — the calc_m(200)/period-margin
   arguments made for it elsewhere in this document were real headroom
   checks, but checks *of* a chosen number, not derivations of one.
   Recorded here so a future reader doesn't mistake "checked against
   calc_m(200)" for "provably correct" the way `MAX_RI` once was mistaken
   for a real ceiling.

   **`stream_at` implemented as direct counter indexing, not iterated
   jumping** — no jump-ahead computation at all for Philox, confirming
   §3.5's own claim under load: `MRG31k3p`/`MRG32k3a` reach a coordinate
   by computing how far to jump from a fixed start; Philox reaches it by
   indexing directly into (key, counter), the native operation the
   construction is built around. Full §7 conformance suite, every
   reference value derived independently for Philox (not ported from
   the MRG-family suites), including its own deliberately-broken-backend
   proof. `getrandbits` is simpler here than for the MRG family, and
   provably unbiased without rejection: Philox's own output is 32-bit
   words directly, so any `k<=32`-bit slice of one word is exactly
   uniform (a power-of-two range sliced from a power-of-two range is
   still exactly uniform — no `mrgm1i`-style non-power-of-two remainder
   to reject). `bsm` reused verbatim for `normalvariate` (imported, not
   copied) — generator-agnostic per §3.3.

   No existing golden should move: this step implements the generator
   only, matching step 5's own scope — not wired into `chnbase.py`'s
   coordinate machinery or any CLI/library selection surface. Confirmed
   directly, not assumed, once landed.
6b. **[new capability, not sequenced against 5/6's own landing order —
   done]** Wire §3.8's already-settled generator-selection design (a
   `--generator` CLI flag plus the matching `solve()`/`testsolve()`
   kwarg) into the CLI and library layers, generically over whatever
   generators are registered at the time — not hardcoded to MRG31k3p
   specifically, so it doesn't need a second pass when Philox (step 6)
   lands. Given a home here, not left as step 7's own prose-only "it
   can land whenever the CLI work is scheduled" note — the same
   reasoning step 8 started from before being promoted out of step 7's
   placeholder text into its own step, so this doesn't go undiscovered
   the same way. Before this landed, every generator onboarded by step
   5/6 was real, tested code with no way for a user to actually reach
   it — `solve()`/`testsolve()` always constructed `MRG32k3a`, the
   default, regardless of what else existed in `pymoso/prng/`. No
   existing golden moved: this only adds a new selection path, it
   doesn't touch the default's own — confirmed directly, full suite
   green on both venvs throughout.

   **Landed as:** the real work turned out to be finding #2 from this
   step's own preparatory report, not the CLI/kwarg wiring itself —
   `chnbase.py::Oracle` had hardcoded `.prng.mrg32k3a` imports
   throughout its own internals (`_hit_via_coordinate`, `crn_advance`,
   `_advance_replication`, `get_endseed`, `_touch_coordinate`), so
   selecting which class to construct `self.rng` from was never going
   to be enough by itself. `pymoso/prng/registry.py` (new): `GENERATORS`
   name→module map, `CRN_CAPABLE` (the MRG family only), `backend_for_
   stream` (`type(self.rng)` → owning module, `isinstance`-based so
   instrumentation subclasses resolve correctly). `Oracle` resolves and
   caches its own backend (`self._backend_name`, a string — not the
   module directly, which broke `--proc`'s own live-Oracle pickling:
   confirmed directly, "`TypeError: cannot pickle 'module' object`"
   before this fix) the first time `set_crnflag()` runs; `Oracle.
   __init__`'s own signature is untouched, so no existing custom Oracle
   subclass needed changes. Three new required Stream-protocol methods
   (§3.2, all three backends): `advance(delta)` (replaces raw
   `jump_seed_n` chaining on a bare seed tuple — O(1) for the MRG
   family via `jump_seed_n`'s existing cached fast path, cheaper still
   for Philox, exact counter addition with no jump computation at all;
   timed directly, not assumed, since "should be O(1)" and "is O(1)"
   have diverged on this branch before), `raw_consumed()` (replaces the
   removed `set_class_cache()`/`.generate` monkeypatch instrumentation),
   and `root_seed()` (distinct from `get_seed()` for Philox specifically
   — `get_seed()`'s own full `(key, counter, buffer)` state isn't the
   2-tuple base key `stream_at` expects as `_orc_root`; confirmed
   directly this needed its own method, not reuse). `MRG31k3p` gained
   its own cached `REPL_RESERVE_STRIDE` matrices (absent until this
   step, since nothing called that path before). `Philox4x32Stream`'s
   constructor now takes one combined `(key, counter)` argument (or
   `get_seed()`'s own 3-tuple), matching the MRG family's own single-
   seed-argument shape — required for `--proc`'s `rngcls(seed)` worker
   reconstruction to work generically across backends at all.

   `sync=`/`visit!=0` and the CRN branch itself stay MRG-family-only,
   deliberately — both raise `NotImplementedError` naming the generator,
   at `set_crnflag()`/`hit()` call time. Recorded as its own future step
   (CRN convergence, §12 below step 8) with the concrete shape traced,
   not left as an unexplained wall.

   `chnutils.get_solv_prnstreams`/`get_testsolve_prnstreams` also
   generalized: every construction in both turned out to already be
   expressible through `stream_at` alone (`get_next_prnstream(seed) ==
   stream_at(seed, 1, 0)`, `MRG32k3a(seed) == stream_at(seed, 0, 0)`,
   both confirmed directly), so neither needed `get_next_prnstream`'s
   own CRN-specific machinery — both now work uniformly across all
   three backends. Found tracing this exact seed math, not fixed:
   `get_testsolve_prnstreams`'s own `orc_root` coincides with the last
   solver stream's own starting position (`KNOWN_ISSUES.md` issue 14) —
   a real, pre-existing independence violation, reproduced byte-for-byte
   rather than fixed inline (a fix moves `testsolve()`'s own `endseed`
   and needs its own sign-off).

   `--seed` itself shipped as one comma-separated token, not `nargs='+'`
   — see §3.7's own correction note for why. `commands/solve.py`/
   `commands/testsolve.py` call the selected generator's `validate_seed`
   at runtime (not argparse), record the generator's name in run
   metadata (`gen_humanfile`), and print seed values generically
   (`basecomm.format_seed_for_display`, falling back to `repr()` for
   any shape that isn't a flat tuple of ints — Philox's own `get_seed()`
   return, in particular).

   **Found running real end-to-end scenarios, not hypothetical, once
   Philox was actually reachable:** `pymoso testsolve --generator
   philox4x32 ...` with no `<x>` raised `AttributeError:
   'Philox4x32Stream' object has no attribute 'choice'`. Every built-in
   tester's own `get_ranx0` calls `rng.choice()`; `BSProb`'s own `g()`
   calls `rng.expovariate()`; MOCOMPASS/MOPBnB call
   `self.sprn.sample()` — all "an rng-shaped object" per §3.6's own
   documented contract (the *entire* `random.Random` API), which
   `Philox4x32Stream` deliberately does not provide (only §3.2's
   minimal Stream protocol — unlike MRG32k3a/MRG31k3p, real
   `random.Random` subclasses with the full surface natively).
   `RandomCompatAdapter` (§3.6) exists for exactly this and had never
   been wired to anything ("nothing constructs one yet," its own prior
   docstring). `pymoso.prng.base.ensure_random_compatible(stream)` is
   the wiring — returns `stream` unchanged if already a `random.Random`
   (a no-op for the MRG family, so the default path is untouched),
   wraps it otherwise. Applied at every point a stream reaches such
   code (`chnbase.py`'s `mp_replicate` and `_hit_via_coordinate`'s own
   `g(x, ...)` calls — the *unwrapped* stream stays what
   `raw_consumed()`/`backend_for_stream` see, since the adapter doesn't
   expose either; `chnutils.py`'s `get_solv_prnstreams`/
   `get_testsolve_prnstreams` for `solvstream`/`xprn`/each `solprn`) —
   never at `orcstream`/`orcprn`, which become `Oracle.rng` and must
   stay the real backend instance for `set_crnflag()`'s own
   `type(self.rng)` lookup.

   **A second bug, found immediately after fixing the first:**
   `RandomCompatAdapter` itself didn't pickle —
   `random.Random`'s own inherited `__reduce__` reconstructs via
   `self.__class__()` (zero arguments) then applies state;
   `RandomCompatAdapter.__init__` requires `stream`, so that failed
   outright (confirmed directly: `pickle.dumps(RandomCompatAdapter(
   stream))` raised `TypeError`). `testsolve()`'s own `--proc` path
   needs this (`KNOWN_ISSUES.md` issue 9's own "ships fully-
   constructed... Oracle instances" pattern) — without it, `pymoso
   testsolve --generator philox4x32 ...` *hung* rather than raising (a
   forkserver-pickling-error hang, the same class of failure issue 9
   already tracks, triggered by a new cause). Fixed with a `__reduce__`
   override reconstructing via the real constructor, passing
   `self._stream`.

   Both verified by reverting (`git stash`) and confirming the new
   tests fail first — an `ImportError` on the removed function, not a
   passing-by-luck test — then pass after restoring.
6c. **[interface change, found onboarding step 6, not Philox-specific —
   see §3.9 — done]** Split `stream_at`'s coordinate into `(stream,
   offset)`: `stream` selects an independent, non-overlapping stream
   (`isp`/`iteration`/`role`/`sync`, currently the high bits of one flat
   coordinate); `offset` selects a position within it (`point`/`visit`/
   `replication`, currently the low bits). MRG-family maps the pair
   onto the same flat-integer arithmetic it uses today
   (`stream*ITER_STRIDE + offset`) — no existing golden moves, this
   relabels a computation already being done, not a new one. Philox
   maps it directly onto `(key, counter)` — no jump at all. `chnbase.py`
   already computes `self._iteration` and an offset-shaped value
   separately before flattening them today, so the change is inserting
   a seam at an existing combination point, not a rewrite — confirmed
   directly, not assumed: full suite green on both venvs after landing,
   every golden byte-identical to before, `--proc`/`--simpar` included
   (the `(stream, offset)` pair pickles as an ordinary 2-tuple).

   **Landed as:** `stream_at(seed, stream, offset)` on all three
   generators (`mrg32k3a.py`, `mrg31k3p.py`, `philox4x32.py`);
   `pymoso.prng.base.one_past`/`StreamFamilyExceeded` (the carry, proven
   below); `Oracle._high_water_mark` as a `(stream, offset)` tuple (the
   *last* coordinate touched, not "one past" it — a change from step 8's
   own flat-integer form, so the carry's own safety could be checked
   explicitly rather than baked unchecked into every `_touch_coordinate`
   call site); `chnbase.py`'s `_hit_via_coordinate`/`get_endseed`/
   `get_high_water_mark` and `chnutils.py`'s `get_testsolve_prnstreams`/
   `testsolve` migrated to it. `RASolver.solve`/MOCOMPASS/MOPBnB needed
   no changes — they already just forward `Oracle.get_high_water_mark()`'s
   own return value through their result dict.

   **The carry, proven before use, not assumed.** `one_past(stream,
   offset, offset_capacity, stream_family_capacity)` raises
   `StreamFamilyExceeded` if carrying `offset` past its own capacity
   would push `stream + 1` outside the family that reserved it (e.g.
   past `ISP_ITER_MARGIN`, spilling into what should be the next isp
   path's own zone) — the same class of defect `MAX_RI`'s own unenforced
   silent overlap was. Tested four ways, deliberately, not just the
   common path: the generic mechanics in isolation
   (`tests/test_stream_offset_carry.py`, including landing exactly on
   the boundary and one past it); against Philox's own real, budget-
   anchored constants (`tests/test_philox4x32_conformance.py`) — where
   the boundary is actually reachable in a test, unlike MRG32k3a's own
   `ISP_ITER_MARGIN = 2**32`; through `Oracle.get_endseed()`'s own
   wiring, white-box (`_high_water_mark` set directly to the boundary
   rather than run there — `tests/test_oracle_endseed.py`); and through
   `chnutils.testsolve()`'s own, separate combination logic
   (`tests/test_testsolve_endseed_carry.py`, `par_runs` monkeypatched to
   return controlled per-path values) — a distinct call site with its
   own choice of which constant to pass, not covered by any of the
   other three. The sync zone's own family capacity is `None`
   (unbounded) at every one of these layers, confirmed directly at a
   stream value far beyond anything the default zone could reach, not
   assumed safe from the shape of the constant alone.

   **A pre-existing structural finding, surfaced while doing this
   proof, not introduced by it, and not fixed here:** `SYNC_ROLE_OFFSET`
   (`2**175`) is *larger* than `ISP_STRIDE` (`2**159`) — a single isp
   path's own sync-zone coordinate already exceeds what should be the
   *entire* reserved range of the next isp path. `sync=` and multi-path
   `testsolve()` (`isp > 1`) are therefore not actually compatible in
   the shipped scheme. This predates step 6c (the same flat arithmetic
   already had this property; step 6c only relabels it) and is
   unreached by anything in this codebase today — no in-tree caller
   uses `sync=` at all, checked directly, not assumed. Recorded in
   `mrg32k3a.py` at `SYNC_ROLE_OFFSET`'s own definition, not fixed:
   resolving it means relocating `SYNC_ROLE_OFFSET` below `ISP_STRIDE`,
   a real redesign of §4.3's own sizing, not a relabeling — out of this
   step's own scope.

   **Debt, recorded not fixed: the CRN branch was not migrated.**
   `crn_advance()`/`_advance_replication()`/`hit()`'s own `crnflag=True`
   path keep their incremental, stateful `rng`/`_next_seed` mutation
   mechanism rather than moving to `stream_at`. This is proven
   equivalent — by induction (in `crn_advance()`'s own docstring) and
   empirically (`get_endseed() == _next_seed`, `tests/test_oracle_
   endseed.py`) — but proof of equivalence is not the same as one
   implementation: two implementations computing the same "replicate
   and aggregate" logic, the same shape as the `_hit_opt_in`/`hit()`
   duplication §12 step 4a found and step 4b resolved by convergence
   (and, until §12 step 6b removed it outright rather than converging
   it — no in-tree caller, nothing to preserve — `bump()` made this a
   third instance). Not fixed here: unifying it means removing the
   `rng`-mutation model (including its `cache_clear()` calls) that
   `crn_advance()`'s own public surface still depends on — a real
   behavior change, not a relabeling, which would move goldens and so
   falls outside this step's own scope. Recorded in `crn_advance()`'s
   own docstring, not only here. **Reclassified, §12 step
   6c-completion** (below): no longer only drift-risk — it is what
   blocks `--crn` from working under any non-MRG generator, since
   nothing here routes through a selected backend at all.

   **Not sequenced against 6b**: 6b (bare CLI/library selection) doesn't
   need this to land — MRG32k3a/MRG31k3p both work today with the flat
   coordinate, and 6b can be built and shipped against that as-is. This
   step is a prerequisite for Philox specifically becoming selectable
   *for real solving* through 6b's own mechanism (as opposed to the
   standalone conformance testing step 6 itself delivers) — `chnbase.py`
   has nowhere to hand Philox a `(key, counter)` pair until this lands.
   Given a home here, not left as prose only in §3.9, per this
   document's own established rule about known-necessary work with no
   place in the step list.

   **Correction, found preparing 6b, recorded here rather than quietly
   folded into 6b's own scope: this step's own report overclaimed.**
   "This step is a prerequisite for Philox specifically becoming
   selectable for real solving" is true, but incomplete — what actually
   landed rebuilt only the Oracle-role *bookkeeping* (`_touch_coordinate`/
   `get_endseed`/`get_high_water_mark`/`one_past`, and `testsolve()`'s
   cross-path aggregation) into `(stream, offset)` pairs. It did not
   build the generator-specific *offset assembly* Philox's own module
   already documented as settled: `philox4x32.py`'s own comment above
   `OFFSET_CAPACITY` stated "point(72) + visit(4) + replication
   count(30) + replication reserve(12) = 118 bits ... step 6's own
   figures" from the moment that module landed, but nothing anywhere in
   the codebase packed an offset against those four numbers — the only
   `offset_within_iteration`/`point_width` that existed was
   `pymoso.prng.base`'s, sized to MRG-family's 127-bit budget (point
   75/visit 6/repl-count 32/repl-reserve 14, matching
   `ITER_STRIDE=2**127`), and `chnbase.py::Oracle._hit_via_coordinate`
   called it unconditionally, with no generator-selection argument at
   all.

   The practical consequence, checked directly rather than assumed: an
   offset built with the 127-bit budget and handed to Philox's own
   `stream_at` does **not** raise anything. `stream_at`'s own bounds
   check is against `COUNTER_BITS` (2**128, the raw hardware limit),
   not `OFFSET_CAPACITY` — an offset in `[2**118, 2**127)` is silently
   accepted, well inside the hardware limit, quietly exceeding this
   module's own declared capacity with no exception anywhere. Closer in
   shape to `MAX_RI`'s original unenforced silent overlap than to a
   merely-confusing error message.

6c-completion. **[preserving, done]** Closes the gap above: `pymoso.prng.base.
   point_width`/`offset_within_iteration` take the offset budget
   (`point_bits`/`visit_bits`/`repl_count_bits`/`repl_reserve_bits`) as
   parameters now, defaulting to the existing MRG-family constants — so
   every existing call site, `chnbase.py`'s included, is byte-identical,
   confirmed by the full suite unchanged on both venvs, no golden moved.
   `philox4x32.py` gained its own `point_width`/`offset_within_iteration`,
   calling the same shared packing logic with its own 72/4/30/12 figures
   — an oversized point/visit/replication now raises the correctly-scoped
   `PointCodeOverflow`/`VisitOverflow`/`ReplicationOverflow` at assembly
   time, before `stream_at` ever sees it, rather than nothing at all.
   Regression coverage in `tests/test_philox_offset_budget.py`,
   including the pre-fix defect (`stream_at` silently accepting an
   oversized offset) demonstrated directly with code that predates this
   step, and the two fix-dependent assertions confirmed failing
   (`AttributeError`, the functions not existing yet) before the fix
   landed and passing after.

   **Still not wired in — this step closes the mechanism gap, not the
   reachability gap.** `chnbase.py::Oracle._hit_via_coordinate` still
   calls `pymoso.prng.base.point_width`/`offset_within_iteration`
   unconditionally; nothing anywhere in the framework calls
   `philox4x32.point_width`/`offset_within_iteration` yet. Philox
   remains not usable for real solving through this codebase's own
   coordinate path — only through direct, standalone `stream_at` calls,
   exactly as before this step. §12 step 6b (below) is what threads a
   selected generator through `Oracle`'s own internals so this budget is
   actually honored on a real `solve()`/`testsolve()` run; a reader
   should not take this step alone as having made Philox usable.

   **Reclassifies the CRN branch's own unmigrated-debt entry** (this
   step's "Debt, recorded not fixed" paragraph above, and CLAUDE.md's
   "Known open items"): that debt was recorded on drift-risk grounds
   (a third parallel replicate-and-aggregate implementation, alongside
   `bump()` and the `_hit_opt_in`/`hit()` convergence already resolved).
   It is now also a hard blocker: `crn_advance()`/`_advance_replication()`
   never moved off incremental `rng`/`_next_seed` mutation and the
   MRG-specific `get_next_prnstream`/`jump_substream` calls that back it,
   so there is no coordinate concept for `--crn` to route through for any
   non-MRG generator at all — not a missing budget (this step's own
   fix), a missing mechanism. `--generator=philox4x32` combined with
   `--crn` has nothing to call. §12 step 6b is expected to make this
   combination raise a clear, named error (mirroring MOCOMPASS/MOPBnB's
   own outright `--crn` refusal) rather than silently doing something
   wrong, and to document the limitation in `--generator`'s own CLI help
   and the README, not only in the error a user hits after the fact —
   CRN is the framework facility for algorithm testing (§1), so "Philox
   is supported" carries a real asterisk without saying so up front.
7. **[dissolved — intentionally empty, nothing dropped]** This entry is
   deliberately blank; it is not a placeholder for forgotten work. It
   originally held four decisions this step list said had to be settled
   before step 4 could land: generator selection, `endseed`,
   `REPL_BITS`/`VISIT_BITS` sizing, and `RASolver.rasolve`'s guard. All
   four have since been decided elsewhere in this document, and none of
   them turned out to need a standalone step to hold them:
   - **Generator selection** (open question 6) is settled in §3.8 (a CLI
     flag plus the matching kwarg) — a CLI/testers-layer addition that
     doesn't touch `chnbase.py`'s coordinate logic at all, so it isn't
     sequenced against steps 1-6 in any way. Actually wiring it is its
     own step, 6b above, not folded in here — corrected from an earlier
     version of this bullet that left it as "can land whenever the CLI
     work is scheduled" prose with no place in the step list, the exact
     gap the `endseed` bullet below already names as a failure mode
     worth avoiding.
   - **`endseed`** (open question 8): what it *should* become is settled
     in §8.2 (the run's tracked coordinate high-water mark, one past).
     Actually wiring that formula into `chnutils.py`/`RASolver.rasolve`'s
     reporting is not part of steps 1-6 either, but — corrected here,
     found only once step 4b actually landed — it is not a no-op the way
     generator selection is: step 4b's own `crn_advance()` reports based
     on its call count only, confirmed to lose real information (§8.2's
     own note, e.g. MOCOMPASS/MOPBnB now reporting identical `endseed`s
     despite verified-different consumption). That wiring is its own
     step, below, not folded in here.
   - **`REPL_BITS`/`VISIT_BITS`/`ISP_STRIDE` sizing** (open question 5)
     turned out to need no separate decision once open question 9 was
     settled — with no `nu` ceiling left to size a margin against, it
     reduces to a direct computation, done as part of step 4a, above, not
     gated on anything happening first.
   - **`RASolver.rasolve`'s guard** (open question 9) is settled: removed
     entirely, no replacement. That removal is inseparable from the
     `MAX_RI`-removal it was always paired with, so it lands as part of
     step 4b, above, not as its own step.

   This entry is kept as a numbered placeholder — rather than deleted,
   which would shift steps 5 and 6 (MRG31k3p, Philox onboarding) down by
   one and break every existing cross-reference to "step 5"/"step 6"
   elsewhere in this document (§3.7's generator-defaults note, §8.2's
   Philox capacity-boundary note, §3.4's onboarding references) — so a
   reader who reaches step 7 and finds it empty can confirm that on
   purpose, from this entry itself, rather than wonder whether a step
   went missing.
**Prerequisite fix, found while planning step 8, landed before it —
kept unnumbered for the same reason step 7 above is: not renumbering
steps 5/6/8 and everything that cross-references them by number.**
Planning step 8's high-water-mark tracker required reasoning precisely
about what coordinate each replication actually occupies — which
surfaced a real defect in step 4b's already-landed, already-regenerated
default (`crnflag=False`) path, not anything about step 8 itself:
`offset_within_iteration` (§3.4) packed `replication` at stride 1 (no
reserved margin), on the unstated assumption that a single replication
consumes exactly one raw draw. No built-in `g()` satisfies that —
`ProbTPA`/`ProbTPB`/`ProbTPC` each draw 3 `normalvariate()`s per
replication, `BSProb` draws ~1000 `expovariate()`s (`tau=100`,
`lambd=10` → Poisson(1000) arrivals) — so replication *i*'s stream ran
into positions replication *i-1*'s own `g()` call had already consumed.
Confirmed directly: replication 1's first two draws were bit-identical
to replication 0's second and third. Replications under the default
path were not independent, and `obse` (driving RA's sample-size
decisions) was computed from correlated, not i.i.d., draws.

Not a step-8 blocker in the sense of blocking design work, but a
correctness bug that had to be fixed *before* step 8, not folded into
it: step 8's high-water-mark tracker would otherwise have tracked a
scheme with no real per-replication reserve to measure "one past" of
(see the "sync branch" REPL_STRIDE-margin note below).

**Root cause, precisely:** REPL_BITS (§3.4) was sized as a replication-
*count* budget (calc_m(200) headroom, checked directly:
calc_m(200) = 379,810,553 ≈ 2**28.5), never as a per-replication
*draw* reserve — nothing in its derivation claimed the latter, and
`offset_within_iteration`'s stride-1 packing of `replication` silently
assumed it anyway. The CRN and `sync` branches don't share this defect:
both advance replication-to-replication by the same `REPL_STRIDE`
(2**76) the CRN branch has always used — astronomically larger than any
realistic draw count, so `rperle_tpa_crn` (the CRN golden) is confirmed
unaffected by this fix.

**Fix, sized with the same rigor as step 4a's own constants** (figures
checked directly, not assumed): the non-CRN coordinate budget is fixed
at 127 bits (shared with `ITER_STRIDE`, §3.4), so a real per-replication
reserve has to come out of the existing three-way split, not be added
on top.

- `REPL_RESERVE_BITS = 14` (16,384 raw draws/replication) — ~16x
  margin over BSProb's own ~1000-draw workload, the heaviest built-in
  `g()`. Enforced at runtime, not just assumed: `chnbase.py`'s
  `_hit_via_coordinate` counts each replication's actual raw draws
  (wrapping the stream's `generate` hook) and raises
  `ReplicationDrawOverflow` — not a silent overlap — if a `g()` exceeds
  it. This was the user's explicit choice over a "generous enough that
  nothing realistic exceeds it, and hope" posture: exceeding a finite
  reserve must fail loudly (the same posture `point_code`'s own
  overflow check already established), because a reserve sized against
  today's built-in problems cannot bound an arbitrary custom `g()`.
- `REPL_COUNT_BITS = 32` — unchanged from the original `REPL_BITS`.
  calc_m(200) ≈ 2**28.5 still leaves ~5.6x margin. Headroom beyond
  calc_m(200)'s scale is moot regardless: `calc_m`'s own float overflow
  (nu≈7440) is preceded by `calc_b`'s (nu≈3882, KNOWN_ISSUES.md issue
  12) for every RASolver-family case checked, so a run reaching a
  larger `m` than `REPL_COUNT_BITS` covers already fails via that
  overflow before `hit()` ever sees it — the same reasoning step 4a
  applied when sizing the original `REPL_BITS` against calc_m(200)
  rather than the unbounded case.
- `VISIT_BITS = 6` (64 values) — shrunk from the original 20 to make
  room for `REPL_RESERVE_BITS` within the fixed 127-bit budget. Unlike
  the other three figures here, this one isn't a measured requirement:
  no in-tree caller passes `visit != 0` today (§4.1's own continuation
  default handles every current caller), so 64 is headroom for a
  currently-hypothetical future use, not a checked bound. Revisit if a
  real caller ever needs more than 64 independent resample generations
  for one point within one iteration.
- `POINT_BITS = 75` — unchanged; still `W = 75 // 9 = 8` for BSProb
  (dim=9, the tightest built-in problem).

**Same audit found two related, smaller gaps, fixed alongside:**
neither `visit >= 2**VISIT_BITS` nor `replication >= 2**REPL_COUNT_BITS`
was ever checked at runtime — both would have silently overflowed into
the neighboring positional field instead of raising, the exact failure
mode `point_code`'s own overflow check was written to prevent (§3.4).
`offset_within_iteration` now raises `VisitOverflow`/
`ReplicationOverflow` respectively. The `sync` branch and `ISP_STRIDE`
(the other coordinate-assembly constants in this document) were also
checked against this same failure mode — both already honor their
own computed widths as real strides (`REPL_STRIDE`, `ISP_STRIDE`), so
neither had this specific defect.

**This is the second instance, in this RNG work, of a test verifying
the property it names rather than the property that matters** — the
first is this document's own `docs/end-seed-scope.md` (end-seed
goldens don't fingerprint consumption). `tests/test_oracle_noncrn_
default.py`'s `LoggingOracle.g()` never actually drew from the stream
it was handed (it read `rng.get_seed()[0]` and returned), so its
disjointness assertions checked *starting coordinates* — genuinely
distinct by construction — never *drawn values*, which is the property
that actually matters and the one this defect violated. See
`docs/end-seed-scope.md`'s own new section for the general lesson;
`tests/test_replication_independence.py` is the fix's regression
coverage, built specifically to exercise real draws instead.

**Goldens affected:** only the ones whose `nu` (RA iteration count at
budget exhaustion) actually changed — confirmed empirically, not
assumed, since the CLI's reported end seed is `crn_advance()`-derived
and depends only on `nu`, not on what `hit()` drew inside an iteration
(the same scoping gap step 8 itself exists to fix). Checked directly:
RPE's `nu` was unchanged (13 → 13, golden unaffected); RPERLE's `nu`
changed (12 → 13, golden moved) because its sample-driven upsample/
neighbor decisions are sensitive to which raw values got drawn.
`rperle_tpa`/`rminrle_tpa`/`rperle_tpa_seed2`/`rperle_tpa_simpar2` (and
the library-level `rperle_tpa`-equivalent) moved on this basis;
`rpe_tpa`/`rspline_simpleso`/`mocompass_tpa`/`mopbnb_tpa`/`testsolve_*`
did not, and `rperle_tpa_crn` is unaffected by construction (CRN branch
untouched). `test_solution_sensitivity.py`'s `EXPECTED_SOLUTIONS` also
moved — expected, and the point of that golden's existence: it is
sensitive to consumption changes end-seed goldens cannot see at all,
exactly as `docs/end-seed-scope.md` says.

8. **[behavior-changing, both stages done]** Wire §8.2's real `endseed`
   formula into `chnutils.py`'s
   `solve()`/`testsolve()` and `RASolver.rasolve`'s reporting, replacing
   `crn_advance()`'s call-count-only jump (§8.2's own gap, found once
   step 4b actually landed: `endseed` used to report
   `self._iteration * ITER_STRIDE`'s position, real movement but not
   what a run actually consumed via `hit()`'s own coordinate calls —
   confirmed concretely, since MOCOMPASS and MOPBnB, which call
   `crn_advance()` exactly once regardless of internal replication
   count, used to report *identical* `endseed`s for identical
   seed/problem/budget despite verified-different consumption). Staged
   in two, deliberately: `solve()`'s own path first, `testsolve()`'s
   cross-path aggregation as a separate follow-on, since the latter
   crosses the `--proc` worker boundary — where every multiprocessing
   bug in this project has lived — and the two stages have different
   verification signatures (`solve()`: `mocompass_tpa`/`mopbnb_tpa`
   diverging; `testsolve()`: the three-way `testsolve_tpa`/
   `testsolve_mocompass`/`testsolve_mopbnb` match breaking), so checking
   them independently is more informative than one combined
   regeneration, and a failure tells you which half.

   **Stage 1 (`solve()`'s path) — done:** `Oracle.get_endseed()`
   (`pymoso/chnbase.py`), **oracle-role only** — see §8.2's own "Wired
   in as of step 8 stage 1" note for the full scoping reasoning
   (solver-role isn't coordinate-based yet, and would need on the order
   of `2**127` ordinary draws to reach where oracle-role begins — a
   real, stated limitation, not "every role" covered). `RASolver.solve`/
   `rasolve`, and MOCOMPASS/MOPBnB's own `solve()` methods, all
   switched from `orc.rng.get_seed()` to `orc.get_endseed()` together —
   fixing one and not the other two would be worse than fixing neither.
   Confirmed: `mocompass_tpa`/`mopbnb_tpa` now diverge, as expected.
   `rperle_tpa_crn` moved too, contrary to the pre-registered
   expectation that it wouldn't — a real finding, traced to `rasolve()`'s
   own trailing, unconditional `crn_advance()` call past the last used
   iteration; full account, and why the new value is a correct
   tightening rather than a regression, in §8.2. Left as an observation,
   not a to-do: restructuring `rasolve()`'s loop to avoid that one
   unused jump is churn on a path everything else depends on, for no
   behavioral gain now that `endseed` no longer depends on `rng`'s walk
   position at all.

   **Every `crnflag=False`/CRN golden moved in stage 1's own pass** —
   not only the MOCOMPASS/MOPBnB pair; the reporting mechanism changed
   for all of them. `tests/golden/README.md` carries the full list and
   reasoning. `testsolve()`'s own end seed was unaffected by stage 1 —
   still `get_testsolve_prnstreams`'s reservation value at that point.

   **Stage 2 (`testsolve()`'s cross-path aggregation) — done.** Each
   `isp` path's own `Oracle` already tracked its own `_high_water_mark`
   (stage 1's own mechanism, unchanged); stage 2 adds
   `Oracle.get_high_water_mark()` (the raw int `get_endseed()` derives
   its seed from) and a new `'oracle_high_water_mark'` key on
   `RASolver.solve`'s and MOCOMPASS/MOPBnB's own result dicts, so it
   survives the `--proc` worker boundary as an ordinary picklable value
   (the object itself never does — each `isp` path's `Oracle` runs in
   its own process, so the caller's own reference to it never reflects
   what the worker actually did). `chnutils.testsolve()` combines them,
   after `par_runs()` returns every path's result: `max(t*ISP_STRIDE +
   res[t]['oracle_high_water_mark'] for t in range(isp))`, then reports
   `jump_seed_n(orc_root, that)` — `get_testsolve_prnstreams` now also
   returns `orc_root` (a 5th value) for this, alongside its own
   pre-existing reservation-based `iseed` (kept, unused by `testsolve()`
   itself any more, for callers that only need a cheap independent seed).

   Confirmed both pre-registered signatures before regenerating, not
   assumed: `testsolve_tpa`/`testsolve_mocompass`/`testsolve_mopbnb`
   (previously bit-identical to each other and to the `testsolve()`
   library case — the `testsolve()`-shaped analog of stage 1's own
   MOCOMPASS/MOPBnB collision) now diverge, each reflecting its own
   solver's real consumption across all 4 `isp` paths; every `solve()`-
   path case (already on the real formula since stage 1) is untouched by
   this stage, confirmed identical to its stage-1 value, not just
   assumed unaffected.

   **A new, correct consequence, not a bug:** `endseed` can now depend
   on `ranx0`/which `x0` a solver actually searched from — something the
   reservation-based mechanism this replaces could never reflect (it
   never touched `xprn`'s own consumption at all, per `docs/end-seed-
   scope.md`'s original analysis). Confirmed directly:
   `tests/test_solution_sensitivity.py`'s own `ranx0=True` case's
   `end_seed` moved, for this reason specifically, not because
   `EXPECTED_SOLUTIONS` moved again (it didn't — that was the earlier,
   separate replication-independence-fix pass). `docs/end-seed-scope.md`
   carries its own correction note for this.

   Explicitly not sequenced relative to MRG31k3p/Philox onboarding
   (steps 5-6) — independent concerns, could land before, after, or
   between them.
9. **[not started — scoped out of step 6b, recorded here so it doesn't
   go undiscovered]** CRN-branch convergence: unify `crn_advance()`/
   `_advance_replication()`/`hit()`'s own `crnflag=True` path onto
   `_hit_via_coordinate`'s stateless, `Stream.advance()`-based mechanism
   instead of the incremental `rng`/`_next_seed` mutation model it still
   uses. Traced concretely while building step 6b, not a hypothetical:

   - `crn_advance()`'s own coordinate formula (`_iteration*ITER_STRIDE +
     m*REPL_STRIDE`, by induction in its own docstring) is structurally
     identical to `_hit_via_coordinate`'s sync branch (`SYNC_ROLE_OFFSET
     + sync*SYNC_STRIDE + replication*REPL_STRIDE`) minus the point
     component — CRN is point-independent by construction (§2), so its
     coordinate never needed `x` in the first place. The two branches
     already share a shape; only the CRN branch still computes it via
     live `rng` mutation instead of `stream_at`/`advance()`.
   - `_advance_replication()`'s own "reset `rng` to the tracked
     `_next_seed`, discarding whatever `g()`/an external `setstate()`
     call left it at, then jump `REPL_STRIDE`" is exactly what
     `Stream.advance()` already provides, *once* `_next_seed`/
     `_iteration_baseline_seed` become tracked `Stream` objects instead
     of raw seed tuples extracted via `get_seed()`. That representation
     change is the actual size of this step — not a parameterization
     like step 6b's own three fixes, a real rewrite of what those two
     attributes *are*, comparable in shape to step 4b's own
     `_hit_opt_in`/`hit()` convergence.
   - Not attempted inside step 6b itself, deliberately: step 6b already
     carries the `Stream.advance()`/`raw_consumed()` protocol additions,
     the Philox constructor/`root_seed()` fixes, the registry, three
     `validate_seed`s, CLI/kwarg wiring, and test rewrites — folding in
     a rewrite that changes what `_next_seed`/`_iteration_baseline_seed`
     mean, with several existing tests asserting on both directly
     (`tests/test_oracle_endseed.py`, `tests/test_oracle_coordinate_
     migration.py`), would put any failure in a diff too large to
     isolate. Same reasoning step 4 itself was split on.

   **Priority, reclassified alongside step 6c-completion's own note:**
   this was recorded in CLAUDE.md purely as drift-risk (a second
   parallel "replicate and aggregate" implementation, after `bump()`'s
   removal left only these two). It is now also what blocks `--crn` and
   `sync=` from working under any non-MRG generator at all — `set_crnflag()`
   raises `NotImplementedError` for `crnflag=True` under Philox, and
   `_hit_via_coordinate` raises the same for `sync=`, both naming this
   step, precisely because neither has anywhere to route to without it.
   Until this lands, "Philox is supported" keeps the asterisk step 6b's
   own CLI help and README text document.
