"""
Regression tests: --simpar, --budget, --isp, --proc must be rejected at
the CLI layer with a clear message when non-positive, rather than
reaching mp.Pool downstream (which raises an opaque error for a
non-positive process count).

Updated for the docopt->argparse migration: the check itself moved
from a separate basecomm.validate_positive_int() call (exit 1, message
on stdout) to argparse's native `type=` mechanism (cli.positive_int,
exit 2, message on stderr via argparse's own parser.error()) --
preferred per this migration's instructions. Same protection (rejected
before reaching mp.Pool), different, argparse-standard presentation.
See docs/phase2c-cli-migration.md for the full list of such deliberate
differences.
"""
import subprocess

import pytest

from _pymoso_cli import pymoso_argv

pytestmark = pytest.mark.timeout(60)

CASES = [
    (["pymoso", "solve", "--budget=0", "ProbTPA", "RPERLE", "40", "40"], "--budget"),
    (["pymoso", "solve", "--simpar=-1", "ProbTPA", "RPERLE", "40", "40"], "--simpar"),
    (["pymoso", "testsolve", "--isp=0", "TPATester", "RPERLE"], "--isp"),
    (["pymoso", "testsolve", "--proc=-2", "TPATester", "RPERLE"], "--proc"),
]


@pytest.mark.parametrize("cmd,option_name", CASES, ids=[c[1] for c in CASES])
def test_non_positive_option_rejected_with_clear_message(cmd, option_name, tmp_path):
    proc = subprocess.run(pymoso_argv(cmd), cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert option_name in proc.stderr
    assert "positive integer" in proc.stderr
    # must fail fast at the CLI layer, not deep in mp.Pool
    assert "Pool" not in proc.stderr
    assert "Traceback" not in proc.stderr
