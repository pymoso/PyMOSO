# Phase 2c — docopt → argparse CLI migration (pymoso-migration branch)

Commits: `dbd1fa9` (characterize docopt), `b2dd4ab` (replace with
argparse), plus the pytest-timeout/regression-test and context-manager
commits for the worker-leak hang found along the way, and the setup.py
dependency removal that follows this doc. `tests/test_cli_characterization.py`
is the frozen historical record of docopt's exact behavior on this base;
`tests/test_cli.py` is the live, ongoing contract against the real CLI.

This redoes the earlier fork's own phase 2c against
github.com/pymoso/PyMOSO's actual `cli.py`, per Step 0's instruction not
to assume the earlier report still applies. It mostly does: `cli.py`'s
docopt usage string is byte-identical between what was characterized on
the earlier fork and this branch (confirmed by diffing the full file,
not just the usage block — none of the 13 commits between the shared
merge-base and this branch's start touched `cli.py`). The one place
this branch's findings genuinely differ from the earlier report is
`--simpar`, and it differs for a reason that has nothing to do with
which parser is in front of it.

## 1. Ordering constraints: the README's claim doesn't match docopt's actual behavior

The README states (prose, "Finally, users may specify..."): options must
precede the problem argument, and `--param` must be last. **This was
never actually true under docopt** — verified directly:

- `solve ProbTPA RPERLE 4 14 --budget=500` (option after positionals) parsed
  identically to `solve --budget=500 ProbTPA RPERLE 4 14`.
- `solve --param radius 3 --budget=500 ProbTPA RPERLE 45 45` (another option
  after `--param`) parsed fine.

argparse preserves this same permissiveness (confirmed in
`tests/test_cli.py`). So there is **no relaxation to report on this
specific dimension** — it was already permissive; nothing changed.

## 2. The real docopt fragility: silent mis-parsing, not rejection

This is what the README's ordering advice was presumably trying to guard
against, and it's worse than a rejection. docopt's positional/repeated-
group matching is a global token-count satisfaction problem, not a
per-option validation:

- `--seed` with 5 or 7 or 8 values (instead of 6) was **not rejected**
  as long as enough total tokens remained — it silently borrowed
  neighboring tokens (including the problem/solver name!) into `<s>`,
  shifting `<problem>`/`<solver>`/`<x>` to the wrong slots, with no error.
- `--param radius` (missing its value) silently borrowed the next
  token as the value and shifted everything after it down one slot.
- `--param radius 3 --seed 1 2 3 4 5 6 ProbTPA RPERLE 4 14` (a `--param`
  group before a `--seed` group — an order no example shows) vacuumed
  `'radius'` and `'3'` into `<s>` instead of `<param>`/`<val>`.

**argparse fixes the interleaving bug outright**: because it treats each
`--option`'s `nargs` independently rather than as one shared token
stream, `--seed`/`--param` given in any relative order now parse
correctly (`tests/test_cli.py::test_seed_and_param_interleaved_out_of_order_now_parses_correctly`).

**Wrong seed/param counts are mostly, not fully, fixed.** Adding
`type=int` to `--seed` turns "too few values" into a clean parse-time
rejection in every case tested (0, 1, 3, 5), because the borrowed
neighboring token is almost always non-numeric (a problem/solver name)
and fails the `int()` conversion immediately — genuinely better than
docopt, not just different. **"Too many" seed values (7, 8) are not
fully fixed**: argparse's `nargs=6` still only consumes the first 6
tokens, and if the 7th/8th happen to also be numeric, they still shift
into `<problem>`. This reliably fails in practice (a numeral is never a
valid problem name), but with a misleading `"Problem name is not
valid"` message rather than a clean "wrong seed count" one. Same
residual class for `--param` with a missing value.

## 3. Exit codes: uniformly 1 → 2 for parse-level rejections

Every parse-level rejection (missing required argument, unknown
command, invalid numeric value) now exits **2**, argparse's standard
convention (`parser.error()`), where docopt exited **1** (a bare
`sys.exit(usage_string)`). `--help`/`--version` are unaffected (both
exit 0 in both versions). Any script currently checking `$? == 1` to
detect a pymoso CLI usage error needs updating to check for `2`.

## 4. Positive-integer validation: moved to argparse's native `type=`, as instructed

`--budget`/`--simpar`/`--isp`/`--proc` validation moved from
`basecomm.validate_positive_int` (commit `82c177b`: print to
**stdout**, `sys.exit(1)`) to `cli.positive_int` used as `type=`
(argparse's `parser.error()`: message to **stderr**, exit **2**). Same
protection, deliberately different presentation — `tests/test_cli_validation.py`
updated accordingly (that test predates this migration; updating its
assertions to match an instructed, reported change is not silently
breaking a test).

**Bonus, unrequested but free**: a non-integer value (`--budget=abc`)
used to be accepted by docopt as a bare string and only fail downstream
in `commands/solve.py`'s own `int(...)` call, producing a raw,
user-facing Python traceback (exit 1). It's now rejected at parse time
by the same `type=positive_int`, with a clean one-line message and no
traceback (exit 2).

## 5. `--help` text: materially different structure, same content where practical

The README embeds docopt's single monolithic `--help` screen verbatim —
that specific code block no longer matches `pymoso --help`'s output.
What changed:

- **Old**: one screen, always showing all three commands' Usage lines,
  a single shared Options list (mixing solve-only and testsolve-only
  options together), plus Examples/Help.
- **New**: `pymoso --help` shows a short top-level overview (program
  description + one line per subcommand) plus the *same* Examples/Help
  text (kept verbatim as an epilog). Each subcommand now additionally
  has its own dedicated help — `pymoso solve --help`,
  `pymoso testsolve --help`, `pymoso listitems --help` — showing only
  that command's own options. This didn't exist as a concept under
  docopt's single-screen design; it's a net usability improvement, but
  it is a different structure, not a reformatted version of the same
  screen.
- Option descriptions were kept as the exact same text (including their
  embedded "[default: N]" wording) inside each `add_argument(help=...)`.
- Scalar option placeholders changed from docopt's single-letter style
  (`--budget=B`, `--simpar=P`) to argparse's default uppercase-dest
  style (`--budget BUDGET`, `--simpar SIMPAR`); the angle-bracket
  positionals (`<problem>`, `<solver>`, `<x>`, `<tester>`, `<s>`,
  `<param>`, `<val>`) were deliberately kept identical via explicit
  `metavar=` so the vocabulary a user already knows still appears.
- `-v`/`--version` remains top-level only, matching its old scope
  exactly (not added per-subcommand).

Layer 3 (below) handles regenerating the README's embedded help text
from the live parser rather than leaving it stale.

## 6. `--simpar` now succeeds — for a reason unrelated to this migration

The earlier fork's phase 2c report recorded `--simpar` as still failing
after the argparse migration, with the pre-existing `TypeError`
(`get_next_prnstream() missing 1 required positional argument`). That
is **not true on this base**: `--simpar` works, because
github.com/pymoso/PyMOSO's `917bf06` ("improved multiprocessing for
--simpar option") replaced the whole mechanism with a persistent
worker-pool design, independently of and before this migration ever
touched this branch. See `docs/upstream-simpar.md` and
KNOWN_ISSUES.md issue 2. `tests/test_cli.py::test_readme_example_details_simpar_now_succeeds`
confirms this directly rather than assuming it from the diff.

`--simpar` actually running exposed a real, separate bug this
migration *did* find and fix: an infeasible `x0` combined with
`--simpar>1` left `Oracle`'s worker processes running after the
exception skipped `mp_cleanup()`, hanging the CLI process indefinitely
at exit (confirmed: 57 minutes before being killed by hand). Fixed by
making `Oracle` a context manager (`set_simpar` returns `self`,
`__exit__` calls `mp_cleanup()` unconditionally) — see
`docs/upstream-simpar.md`'s "Worker lifetime, part 2" section and
`tests/test_simpar_worker_lifecycle.py` for the full writeup and the
regression test (confirmed failing via timeout before the fix, passing
after).

Separately, still true and reconfirmed here: `ProbTPC`'s README/CLI
example `x0=(31,21,11)` remains infeasible (`ProbTPC`'s domain is
[-10,10] per component at the default `density_factor=2`) — an
unrelated, pre-existing documentation bug, not a CLI-parsing concern,
scheduled for Layer 1/2's fix.

## Test suite structure going forward

- `tests/test_cli_characterization.py` — frozen. Its `DOC` constant is
  a literal copy of the pre-migration docstring, not a live import from
  `pymoso.cli`. Do not update it to match new behavior; it exists to
  keep documenting docopt's specific behavior indefinitely.
- `tests/test_cli.py` — the live, parser-agnostic contract on the real
  `pymoso` CLI. Update its expectations deliberately (with the reason
  recorded, as done here) whenever CLI behavior legitimately changes.
- `tests/test_simpar_worker_lifecycle.py` — regression coverage for the
  worker-leak hang, independent of which CLI parser is in front of it.

All tests pass at every commit in this phase (each commit's exact count
is in its own commit message; the one designed exception is the
pytest-timeout commit, whose regression test is deliberately red there
and green in the very next commit).
