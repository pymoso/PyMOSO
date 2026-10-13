"""
Regression test for the --simpar worker-leak hang.

chnutils.solve() spawns self.simpar worker Process objects
(Oracle.set_simpar) before running the RA loop, and only tears them
down (Oracle.mp_cleanup) if that loop returns normally. An infeasible
x0 raises a ValueError from RASolver.get_min partway through, skipping
teardown: the workers are non-daemon and block forever on
input.get() (chnbase.py's mp_worker), so Python's multiprocessing
atexit machinery hangs the whole CLI process trying to join them at
exit, instead of exiting after printing the error. Confirmed directly
by hand before this test existed: `pymoso solve --simpar=4
--budget=10000 ProbTPA RPERLE 97 97` (x0=(97,97) is infeasible for
ProbTPA, whose domain is [0,50] per component) hung for 57 minutes
before being killed.

The property under test is *that the process exits at all* within a
generous timeout -- not any particular exit code. Do not tighten this
to assert a specific returncode later: today it's whatever
sys.exit(1)/the OS produces on an unhandled hang-then-kill, and once
the fix below lands it becomes a clean 1, but a future refactor to the
error-handling path could legitimately change that number without
reintroducing the hang this test exists to catch. The only thing that
must never regress is "the process exits."

Confirmed failing (times out) before the fix: Oracle.set_simpar/
mp_cleanup wrapped in a context manager so teardown runs on every exit
path, not just the successful one (see chnbase.py, Oracle.__enter__/
__exit__, and chnutils.solve()'s `with orc.set_simpar(simpar):`).
"""
import subprocess

import pytest

from _pymoso_cli import pymoso_argv

pytestmark = pytest.mark.timeout(60)

# Comfortably above the ~1-3s a real --simpar run takes when it isn't
# hanging, well below the module-level 60s pytest-timeout backstop, so
# a genuine hang fails here first with a clear, specific message.
SUBPROCESS_TIMEOUT = 30


def test_infeasible_x0_with_simpar_exits_rather_than_hanging(tmp_path):
    cmd = ["pymoso", "solve", "--simpar=4", "--budget=10000",
           "ProbTPA", "RPERLE", "97", "97"]  # (97, 97) infeasible: ProbTPA's domain is [0, 50]
    try:
        proc = subprocess.run(pymoso_argv(cmd), cwd=tmp_path, capture_output=True,
                               text=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "pymoso did not exit within {0}s -- the --simpar worker-leak "
            "hang has regressed (an infeasible x0 leaves Oracle's worker "
            "Process objects running after set_simpar(), and nothing "
            "tears them down before the interpreter tries to exit)."
            .format(SUBPROCESS_TIMEOUT)
        )
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert "infeasible" in proc.stdout


# ---------------------------------------------------------------------------
# KNOWN_ISSUES.md issue 15: an exception in g() under --simpar.
#
# The worker loop this replaced did not catch anything: the worker died
# with the exception, nothing came back, and the parent waited for that
# replication's result with no timeout. Observed failing first, against
# the code before the worker pool (pymoso/pool.py), on Python 3.10 and
# 3.14: the dead worker's traceback reached stderr, pymoso itself
# reported nothing, and the run was still going when the timeout killed
# it. The same problem without --simpar reported the error and exited
# immediately, then as now.
# ---------------------------------------------------------------------------

RAISING_SRC = '''\
from pymoso.chnbase import Oracle

class RaisingProb(Oracle):
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        if x[0] < 97:
            raise ZeroDivisionError("boom at {0}".format(x))
        return True, (x[0]**2 + rng.normalvariate(0, 3),)
'''


@pytest.mark.parametrize("simpar", [1, 2])
def test_an_exception_in_g_is_reported_with_or_without_simpar(simpar, tmp_path):
    (tmp_path / 'raisingprob.py').write_text(RAISING_SRC)
    cmd = ["pymoso", "solve", f"--simpar={simpar}", "--budget=200", "raisingprob.py", "RSPLINE", "97"]
    try:
        proc = subprocess.run(pymoso_argv(cmd), cwd=tmp_path, capture_output=True,
                               text=True, timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "pymoso did not exit within {0}s -- an exception in g() under "
            "--simpar is hanging the run again instead of being reported "
            "(KNOWN_ISSUES.md issue 15).".format(SUBPROCESS_TIMEOUT)
        )
    assert proc.returncode != 0, (proc.stdout, proc.stderr)
    assert "Unable to simulate RaisingProb" in proc.stdout and "boom at" in proc.stdout
