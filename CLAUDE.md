# PyMOSO

Python package for multi-objective simulation optimization. Originally a
PhD output (Cooper & Hunter 2018), now being modernized.

## Canonical repository

github.com/pymoso/PyMOSO — NOT HunterResearch/PyMOSO, which is a stale
snapshot 13 commits behind. Both READMEs are nearly identical, so check
the remote, not the content. The `dangerzone` branch is superseded by
master.

`pymoso/master` installs as `1.0.7` (`pymoso/__init__.py`), but PyPI
has `1.0.8` — the released wheel doesn't correspond to any commit in
this history. Don't assume git HEAD and the installed/PyPI package
agree; check both when behavior is in question.

## Critical context

- Golden baselines in `tests/golden/` were captured from the 1.0.4 wheel
  on CPython 3.10.21. NEVER regenerate or edit them without being asked.
  They are the only regression protection this project has.
- MRG32k3a jump-ahead: incorrect for realistic seeds, confirmed and quantified
- --simpar>1 with --crn: not silently wrong — it crashes, unconditionally, regardless of --crn
- max_RI=200: enormous headroom in practice; breach is silent stream reuse, not an exception
- Infeasible x0: confirms KeyError, refines the phase-1 analysis — RPE has a raw unhandled traceback, RPERLE/RMINRLE mask it behind a wrong message


## Environments

- `.venv-baseline` — CPython 3.10, pre-3.11 semantics, for goldens
- Use `uv`, never plain pip. Never install into system Python.

## Working agreement

- Propose a plan before writing code. Wait for approval.
- Smallest change that solves the actual problem. Say so if a rewrite is
  genuinely better, but default to patching.
- Don't reformat code you weren't asked to touch.
- State assumptions. Say "I need to see X" rather than guessing.
- Run tests between changes, not at the end.
- If an acceptance criterion I gave conflicts with what the code needs,
  say so and stop. Don't reinterpret the criterion to make it pass.
- Whitespace-only changes must be provably whitespace-only (`git diff -w`
  empty). Anything substantive gets its own commit.
