"""How the CLI tests launch `pymoso`.

Tests spawn `[sys.executable, "-I", "-m", "pymoso", ...]`, not the bare
`pymoso` console script, so they always exercise the installation they
are running under. A bare `pymoso` resolves through $PATH and can land
on an unrelated (stale) install, which fails the suite in ways that look
like real regressions.

`-I` (isolated mode) is deliberate, not decoration: plain `-m` puts the
current directory on sys.path, which the console script does not. Several
tests run with `cwd` set to the directory holding a user's problem files,
so without `-I` a sibling `import helper` would succeed whether or not
`basecomm.load_user_module` adds the file's directory to sys.path,
silently turning the multi-file regression tests into rubber stamps
(KNOWN_ISSUES.md issue 9). `-I` also ignores PYTHON* environment
variables; no test here relies on any.
"""
import sys

# Per-subprocess time limit for CLI tests that don't set their own. Passed
# as `timeout=` to subprocess.run so a hang fails that one test with
# TimeoutExpired, with or without pytest-timeout installed. The slowest CLI
# case measured is ~7s (solve --odir); 30s matches the SUBPROCESS_TIMEOUT
# used elsewhere in the suite and stays under the 60s module marker, so
# this fires first with the specific error.
CLI_TIMEOUT = 30


def pymoso_argv(cmd):
    """Turn a `["pymoso", *args]` command list into a real argv."""
    assert cmd[0] == "pymoso", cmd
    return [sys.executable, "-I", "-m", *cmd]
