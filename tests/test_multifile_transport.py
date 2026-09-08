"""
Transport correctness for multi-file custom problems under --simpar
(KNOWN_ISSUES.md issue 9, docs/forkserver-hang.md): the actual
regression test for the forkserver hang, using a real multi-file
fixture (the one from KNOWN_ISSUES.md issue 11 / tests/test_cli.py --
requires that loading bug fixed first, or this test can't even get to
the transport question) run under real --simpar, not a synthetic
reproduction.

"Same result as serial execution" is checked two ways, not one:
end seed (the existing --simpar convention, per docs/upstream-simpar.md
-- seed assignment is deterministic and identical regardless of
simpar) AND the actual returned solution set, read back from each
run's saved output file. End seed alone is not enough evidence here --
see docs/end-seed-scope.md: it fingerprints the stream-allocation
schedule, not what any stream actually computed, so a transport bug
that silently reconstructs the wrong thing could still land on the
right end seed by coincidence. The solution set is the thing that
would actually catch that.

Confirmed failing before the fix landed (Python 3.14, forkserver
default): timed out, caught by pytest-timeout, not a clean assertion
failure -- exactly the hang docs/forkserver-hang.md diagnosed via
py-spy. A detector never observed detecting isn't proven to work.
"""
import ast
import re
import subprocess

import pytest

pytestmark = pytest.mark.timeout(90)

# Comfortably above the ~1-3s a real small --simpar run takes when it
# isn't hanging, well below the module-level pytest-timeout backstop --
# see tests/test_simpar_worker_lifecycle.py for the same convention.
SUBPROCESS_TIMEOUT = 30

SEED = ["1", "2", "3", "4", "5", "6"]

HELPER_SRC = '''\
PENALTY = 3.0

def noisy_quadratic(x0, rng):
    z = rng.normalvariate(0, 1)
    return x0**2 + PENALTY*z
'''

PROBLEM_SRC = '''\
from pymoso.chnbase import Oracle
from helper import noisy_quadratic, PENALTY

class MyProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        feas_range = range(-100, 101)
        obj = []
        is_feas = False
        if len(x) == self.dim:
            is_feas = True
            for i in x:
                if not i in feas_range:
                    is_feas = False
        if is_feas:
            obj1 = noisy_quadratic(x[0], rng)
            z1 = rng.normalvariate(0, 1)
            obj2 = (x[0] - 2)**2 + z1 + 0*PENALTY
            obj = (obj1, obj2)
        return is_feas, obj
'''

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)


def run_solve(tmp_path, odir, extra_args):
    cmd = ["pymoso", "solve", "--budget=200", f"--odir={odir}", "--seed", *SEED,
           *extra_args, "myproblem.py", "RPERLE", "40"]
    try:
        return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True,
                               timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"{' '.join(cmd)} did not complete within {SUBPROCESS_TIMEOUT}s -- "
            "the forkserver hang (KNOWN_ISSUES.md issue 9, docs/forkserver-hang.md) "
            "has regressed, or the transport fix isn't landed yet."
        )


def end_seed(proc):
    match = SEED_RE.search(proc.stdout)
    assert match, f"no seed line found in:\n{proc.stdout}"
    return tuple(int(v) for v in match.group(1).split())


def solution_set(tmp_path, odir):
    rundata = tmp_path / odir / f"rundata_{odir}.txt"
    assert rundata.is_file(), f"{rundata} was not written"
    lines = [l for l in rundata.read_text().splitlines() if l.strip()]
    return {ast.literal_eval(l) for l in lines}


def test_multifile_problem_under_simpar_matches_serial(tmp_path):
    (tmp_path / 'helper.py').write_text(HELPER_SRC)
    (tmp_path / 'myproblem.py').write_text(PROBLEM_SRC)

    serial = run_solve(tmp_path, "serial_run", [])
    assert serial.returncode == 0, serial.stderr

    parallel = run_solve(tmp_path, "parallel_run", ["--simpar=4"])
    assert parallel.returncode == 0, parallel.stderr

    assert end_seed(parallel) == end_seed(serial)
    assert solution_set(tmp_path, "parallel_run") == solution_set(tmp_path, "serial_run")
