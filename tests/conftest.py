"""Session-wide checks that run before any test is collected."""
import os
import subprocess
import sys

import pytest

# The installed pymoso, as every fresh-interpreter test sees it.
# tests/_pymoso_cli.py and the direct [sys.executable, "-I", ...] calls
# all run under -I, which ignores PYTHONPATH and the current directory,
# so they import pymoso from site-packages. This process imports it from
# whatever is first on sys.path. In a second worktree sharing a venv's
# editable install, or from another checkout, the two are different
# trees: in-process tests check one, subprocess tests silently check the
# other (docs/phase7-plan.md, the subprocess-tree guard). Passing
# PYTHONPATH through instead would undo what -I is for (KNOWN_ISSUES.md
# issue 9).
_PROBE = [sys.executable, "-I", "-c", "import pymoso; print(pymoso.__file__)"]


def _same_file(a, b):
    norm = lambda p: os.path.normcase(os.path.realpath(p))
    return norm(a) == norm(b)


def pytest_configure(config):
    import pymoso

    here = pymoso.__file__
    probe = subprocess.run(_PROBE, capture_output=True, text=True,
                           timeout=60)
    installed = probe.stdout.strip()
    if probe.returncode == 0 and _same_file(here, installed):
        return
    if probe.returncode != 0:
        installed = ("(none: `import pymoso` fails under -I)\n"
                     + probe.stderr.strip())
    raise pytest.UsageError(
        "the tests would run two different pymoso trees.\n"
        f"  this process imports:              {here}\n"
        f"  {sys.executable} -I imports: {installed}\n"
        "Tests that start a fresh interpreter use the second. Run the "
        "suite from the checkout that is installed in this environment, "
        "or install the tree under test into it "
        "(uv pip install -e <tree>).")
