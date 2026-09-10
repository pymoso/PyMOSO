# Changelog

## 1.1.0

**Upgrading from 1.0.8? Read this first: numerical results will not match.**

This release fixes an incorrect pseudo-random stream jump-ahead defect
present in every published 1.x version, including 1.0.8. `mrg32k3a`'s
stream-advance matrix multiplication was done in floating point, losing
precision and landing streams near — not at — their intended positions,
with error compounding across successive jumps. Every individual
simulation replication draws from a correct stream; the defect was
confined to how streams were advanced between them. **This is an
implementation fix, not a correction to the published convergence
theory** the algorithms are proven against — the theory is unaffected,
but end seeds and per-run solution values from 1.x will not reproduce
bit-for-bit under 1.1.0, for any seed. See `KNOWN_ISSUES.md` issue 1
for the full mechanism and verification.

**Error handling.** Bare `except:` clauses that swallowed tracebacks
are gone — errors now report specific exception types with real
tracebacks. Library code that called `sys.exit()` on bad input now
raises instead, so library callers can catch it rather than having
their process killed. An infeasible starting point (`x0`) now reports
a clear `ValueError` naming it, instead of a misleading downstream
error. A `--simpar`/`--proc` worker-process leak on the error path is
fixed — `Oracle` is a context manager now, so worker cleanup runs even
when a run raises partway through. (One related leak — worker
processes orphaned if the *parent* process is killed externally, e.g.
`SIGKILL` — is not fixed; no Python-level mechanism can fully close
that gap. See `KNOWN_ISSUES.md` issue 10.)

**CLI rewritten on argparse; zero runtime dependencies.** `docopt` is
gone from the runtime path (`install_requires = []` — confirmed empty
at this release, and confirmed no other package appears in a fresh
install of either the editable checkout or the built wheel, on Python
3.10 and 3.14 alike). This also closes a real correctness defect
inherited from every prior version: `docopt` matched `--seed`/
`--param` values by total token count across the whole command line,
so a wrong `--seed` value count could silently borrow a neighboring
token — including the problem or solver name — and complete a run
using the wrong seed or starting point, with no error. `argparse`'s
per-option arity validation closes this: a malformed `--seed`/
`--param` now fails cleanly with a real error message and a non-zero
exit code. See `KNOWN_ISSUES.md` issue 6.

**Library API defaults that had never actually worked.**
`chnutils.solve()`/`chnutils.testsolve()`, called exactly as the
README's own documented examples show (omitting `budget`, `seed`,
`simpar`, etc.), raised `KeyError` immediately — every keyword
argument was popped with no default, on every version checked,
including this project's own original base. Defaults are restored and
centralized (`DEFAULT_BUDGET`, etc.), matching the CLI's own
documented values, with a test asserting the two can't drift apart.
Calling the library functions as documented now works. See
`KNOWN_ISSUES.md` issue 7.

**Multi-file custom problems/testers.** A user-supplied problem or
tester file that imports a sibling module in the same directory (the
realistic shape for any nontrivial simulation) failed immediately with
`ModuleNotFoundError`, on every version checked, including 1.0.8 —
`sys.path` was never updated to include the file's own directory.
Fixed. See `KNOWN_ISSUES.md` issue 11.

**Python 3.10–3.14.** CPython `random.Random` internals this project
depended on directly were removed; the package now runs across the
full 3.10–3.14 range, tested on both ends (3.10 as the compatibility
floor, 3.14 as primary development).

**Known limitation on Python 3.14: `testsolve --proc` hangs with a
custom (file-supplied) problem or tester.** `forkserver` became the
default multiprocessing start method on Linux in 3.14; `solve
--simpar`'s dispatch mechanism was fixed to survive it (source-bundle
transport), but `testsolve --proc` ships a live, already-seeded
`Oracle` instance to each worker, which that fix doesn't cover — the
result is an indefinite hang, no error, specific to custom problem/
tester files supplied by path (built-in problems/testers are
unaffected). See `KNOWN_ISSUES.md` issue 9.

**MOCOMPASS and MOPBnB are not in this release.** They are not
shipped: bringing in-tree implementations of two other groups'
published algorithms, and reviewing their correctness against the
source papers, is deliberately deferred to 2.0.0 rather than falling
out incidentally from this release's version boundary. See
`KNOWN_ISSUES.md` issue 13.

**Documentation.** Ten documentation defects in example code are
fixed; README code blocks, CLI help text, and the `listitems` output
are now generated from and tested byte-identical against live source,
so they can't drift silently. `docs/end-seed-scope.md` explains
precisely what a reported end seed does and does not guarantee (it
fingerprints the stream-allocation schedule, not what any stream
actually drew — a distinction with real consequences for anyone trying
to use it to detect a changed run). `docs/rng-interface-design.md`
ships as development documentation for the RNG redesign behind this
release's numerical fix; it now carries an explicit note that most of
what it describes is 2.0.0-era design work, not 1.1.0's shipped
behavior (see the note at its head).

For anything not listed above, including what remains open for a
future release, see `KNOWN_ISSUES.md` in full.
