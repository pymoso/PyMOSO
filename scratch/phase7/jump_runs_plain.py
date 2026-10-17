"""Phase 7 step 3: whole-run wall time, uninstrumented, for the runs
jump_profile.py profiles. One line of JSON per run.

    python scratch/phase7/jump_runs_plain.py LABEL
"""
import contextlib
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jump_profile import GENERATORS, RUNS, SEED  # noqa: E402

from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402

for gen, mod in GENERATORS.items():
    for name, cls, solver, x0, budget in RUNS:
        orcstream, solvstream = get_solv_prnstreams(SEED, mod)
        orc = cls(orcstream)
        orc.set_crnflag(False)
        with contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
            t0 = time.perf_counter()
            res = isp_run(solver, budget, orc, solvprn=solvstream, x0=x0)
            wall = time.perf_counter() - t0
        last = max(res['simcalls'])
        print(json.dumps(dict(label=sys.argv[1], generator=gen, run=name, wall=wall,
                              simcalls=res['simcalls'][last], endseed=list(res['endseed']),
                              soln=sorted(map(list, res['itersoln'][last])), load=os.getloadavg()[0])), flush=True)
