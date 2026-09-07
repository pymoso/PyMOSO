"""
Regression tests: --simpar, --budget, --isp, --proc must be rejected at
the CLI layer with a clear message when non-positive, rather than
reaching mp.Pool downstream (which raises an opaque error for a
non-positive process count).
"""
import subprocess

import pytest

CASES = [
    (["pymoso", "solve", "--budget=0", "ProbTPA", "RPERLE", "40", "40"], "--budget"),
    (["pymoso", "solve", "--simpar=-1", "ProbTPA", "RPERLE", "40", "40"], "--simpar"),
    (["pymoso", "testsolve", "--isp=0", "TPATester", "RPERLE"], "--isp"),
    (["pymoso", "testsolve", "--proc=-2", "TPATester", "RPERLE"], "--proc"),
]


@pytest.mark.parametrize("cmd,option_name", CASES, ids=[c[1] for c in CASES])
def test_non_positive_option_rejected_with_clear_message(cmd, option_name, tmp_path):
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert option_name in proc.stdout
    assert "positive integer" in proc.stdout
    # must fail fast at the CLI layer, not deep in mp.Pool
    assert "Pool" not in proc.stdout
    assert "Traceback" not in proc.stdout
