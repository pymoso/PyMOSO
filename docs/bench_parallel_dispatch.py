#!/usr/bin/env python
"""
Benchmark harness for --simpar/--proc dispatch: the before-picture for
the executor rework. NOT part of the test suite (tests/test_parallel_
dispatch.py owns the portable, worker-count-independent correctness
assertions -- this script is the absolute-timing counterpart that must
never be asserted on in CI, only recorded as a committed artifact).

Two modes:

    python docs/bench_parallel_dispatch.py sweep --out RESULTS.json
    python docs/bench_parallel_dispatch.py report RESULTS_A.json [RESULTS_B.json ...] --out docs/parallel-dispatch-baseline.md

`sweep` runs the actual timing matrix under whichever Python
interpreter invokes it and writes raw results + machine info to a JSON
file. `report` reads one or more such JSON files (e.g. one captured
under 3.10, one under 3.14 -- see CLAUDE.md's Environments section) and
renders the final Markdown artifact. Kept as two steps so the
(slow, interpreter-specific) sweep and the (fast, format-only) report
generation can be iterated on separately, and so results from
differently-versioned interpreters can be assembled into one document
without re-running anything.

Each timed cell does one untimed warm-up call first, so CPU boost
ramp-up (this machine idles at 2.2GHz, boosts to ~4.45GHz) doesn't
inflate the first measurement at each worker count.
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, '.')

from pymoso.chnutils import get_solv_prnstreams, isp_run, testsolve
from pymoso.problems.probexpensive import ProbExpensiveHeavy, ProbExpensiveLight, ProbExpensiveModerate
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.expensivetester import ExpensiveTester

SEED = (12345,) * 6
X0 = (50,)
WORKER_COUNTS = [1, 2, 4, 6, 8, 12]

# (label, problem class, --simpar budget, --proc per-isp budget)
TIERS = [
    ("Light (~1.3ms/rep)", ProbExpensiveLight, 500, 80),
    ("Moderate (~13ms/rep)", ProbExpensiveModerate, 200, 40),
    ("Heavy (~35ms/rep)", ProbExpensiveHeavy, 80, 15),
]

PROC_ISP = 12  # fixed across the --proc sweep; see report() notes on why


class LightTester(ExpensiveTester):
    def __init__(self):
        super().__init__()
        self.ranorc = ProbExpensiveLight


class HeavyTester(ExpensiveTester):
    def __init__(self):
        super().__init__()
        self.ranorc = ProbExpensiveHeavy


TESTERS = {
    ProbExpensiveLight: LightTester,
    ProbExpensiveModerate: ExpensiveTester,
    ProbExpensiveHeavy: HeavyTester,
}


# ---------------------------------------------------------------------------
# Machine info
# ---------------------------------------------------------------------------

def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _lscpu_field(field):
    out = _run(["lscpu"])
    if not out:
        return None
    for line in out.splitlines():
        if line.startswith(field):
            return line.split(":", 1)[1].strip()
    return None


def _os_release():
    try:
        with open("/etc/os-release") as f:
            fields = dict(
                line.strip().split("=", 1) for line in f if "=" in line
            )
        name = fields.get("PRETTY_NAME", "").strip('"')
        return name or None
    except OSError:
        return None


def _nvidia_smi():
    if shutil.which("nvidia-smi") is None:
        return None
    return _run([
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader",
    ])


def _git_commit():
    return _run(["git", "rev-parse", "--short", "HEAD"])


def machine_info():
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "os_release": _os_release(),
        "kernel": platform.release(),
        "cpu_model": _lscpu_field("Model name"),
        "physical_cores": _lscpu_field("Core(s) per socket"),
        "logical_cpus": _lscpu_field("CPU(s):"),
        "threads_per_core": _lscpu_field("Thread(s) per core"),
        "cpu_max_mhz": _lscpu_field("CPU max MHz"),
        "cpu_min_mhz": _lscpu_field("CPU min MHz"),
        "l3_cache": _lscpu_field("L3 cache"),
        "loadavg": _run(["cat", "/proc/loadavg"]),
        "uptime": _run(["uptime"]),
        "nvidia_smi": _nvidia_smi(),
    }


# ---------------------------------------------------------------------------
# Timed cells
# ---------------------------------------------------------------------------

def time_solve(problem_cls, simpar, budget):
    orcstream, solvstream = get_solv_prnstreams(SEED, False)
    orc = problem_cls(orcstream)
    orc.set_crnflag(False)
    t0 = time.perf_counter()
    with orc.set_simpar(simpar):
        res = isp_run(RSPLINE, budget, orc, sprn=solvstream, x0=X0)
    elapsed = time.perf_counter() - t0
    calls = res['simcalls'][max(res['simcalls'])]
    return elapsed, calls


def time_testsolve(problem_cls, proc, isp, budget):
    tester = TESTERS[problem_cls]
    t0 = time.perf_counter()
    res, _ = testsolve(tester, RSPLINE, X0, budget=budget, seed=SEED, isp=isp, proc=proc, crn=False)
    elapsed = time.perf_counter() - t0
    calls = sum(res[p]['simcalls'][max(res[p]['simcalls'])] for p in res)
    return elapsed, calls


def sweep():
    results = {"machine": machine_info(), "simpar": [], "proc": []}

    for label, problem_cls, simpar_budget, proc_budget in TIERS:
        print(f"=== {label} ===", file=sys.stderr)

        print("  --simpar warm-up...", file=sys.stderr)
        time_solve(problem_cls, 1, simpar_budget)
        for workers in WORKER_COUNTS:
            elapsed, calls = time_solve(problem_cls, workers, simpar_budget)
            print(f"  --simpar={workers:<3} {elapsed:7.3f}s  ({calls} calls)", file=sys.stderr)
            results["simpar"].append({
                "tier": label, "workers": workers, "budget": simpar_budget,
                "elapsed_s": elapsed, "calls": calls,
            })

        print("  --proc warm-up...", file=sys.stderr)
        time_testsolve(problem_cls, 1, PROC_ISP, proc_budget)
        for workers in WORKER_COUNTS:
            elapsed, calls = time_testsolve(problem_cls, workers, PROC_ISP, proc_budget)
            print(f"  --proc={workers:<3}   {elapsed:7.3f}s  ({calls} calls, isp={PROC_ISP})", file=sys.stderr)
            results["proc"].append({
                "tier": label, "workers": workers, "isp": PROC_ISP, "budget": proc_budget,
                "elapsed_s": elapsed, "calls": calls,
            })

    return results


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _table(rows, columns):
    header = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def render_machine_section(machine):
    lines = [
        f"- Captured: {machine['captured_at']}",
        f"- Commit: `{machine['git_commit']}`",
        f"- Python: `{machine['python_version'].splitlines()[0]}`",
        f"- OS: {machine['os_release']} (kernel `{machine['kernel']}`)",
        f"- CPU: {machine['cpu_model']} -- {machine['physical_cores']} physical cores, "
        f"{machine['logical_cpus']} logical ({machine['threads_per_core']} threads/core), "
        f"{machine['cpu_min_mhz']}-{machine['cpu_max_mhz']} MHz, {machine['l3_cache']} L3",
        f"- Load average at capture (1/5/15m): `{machine['loadavg']}`",
        f"- `uptime`: `{machine['uptime']}`",
        f"- `nvidia-smi`: `{machine['nvidia_smi'] or 'not present'}`",
    ]
    return "\n".join(lines)


def render_sweep_tables(run_label, results):
    out = [f"### {run_label}\n"]
    out.append(render_machine_section(results["machine"]))
    out.append("")

    # Read isp from the actual results, not the module constant --
    # otherwise a report rendered against a JSON file from a run made
    # with a different PROC_ISP would show a header that contradicts
    # its own table's isp column.
    proc_isp = results["proc"][0]["isp"] if results["proc"] else "?"

    for mechanism, key, extra_cols, extra_fmt in [
        ("--simpar (solve)", "simpar", [], lambda r: []),
        (f"--proc (testsolve, isp={proc_isp} fixed)", "proc", ["isp"], lambda r: [r["isp"]]),
    ]:
        out.append(f"#### {mechanism}\n")
        by_tier = {}
        for r in results[key]:
            by_tier.setdefault(r["tier"], []).append(r)
        for tier, rows in by_tier.items():
            out.append(f"**{tier}**\n")
            serial = next(r for r in rows if r["workers"] == 1)
            table_rows = []
            for r in rows:
                speedup = serial["elapsed_s"] / r["elapsed_s"] if r["elapsed_s"] > 0 else float("nan")
                table_rows.append([
                    r["workers"], f"{r['elapsed_s']:.3f}", r["calls"], f"{speedup:.2f}x",
                    *extra_fmt(r),
                ])
            out.append(_table(table_rows, ["workers", "seconds", "calls", "speedup vs. workers=1", *extra_cols]))
            out.append("")
    return "\n".join(out)


REPORT_PREAMBLE = """\
# Parallel dispatch baseline

Before-picture for the executor rework (see CLAUDE.md's "Known open
items"). Absolute timings only -- these are NOT enforced by the test
suite (tests/test_parallel_dispatch.py owns the portable,
worker-count-independent correctness assertions: identical results and
simulation-call counts across worker counts, and today's job-dispatch
counts). Regenerate with docs/bench_parallel_dispatch.py; do not
hand-edit the numbers below.

Both mechanisms are dispatched unbatched today: one job per replication
for `--simpar`, one job per independent sample path for `--proc`,
regardless of worker count (confirmed in
tests/test_parallel_dispatch.py). `--proc`'s job count is fixed by
`isp`, not `proc` -- each `--proc` table below fixes isp across its own
worker-count sweep (see its header and `isp` column), so workers beyond
isp have nothing to do; that's expected, not a bug. It's the same
reason the README's `--isp=20 --proc=10` and `--isp=100 --proc=20`
examples oversubscribe this specific 6-physical-/12-logical-core
machine (10 and 20 both exceed 12 logical threads, and 10 already
exceeds 6 physical cores) -- those numbers reflect contention on this
hardware, not anything inherent to `--proc` itself.
"""


def report(input_paths, out_path):
    sections = []
    for path in input_paths:
        with open(path) as f:
            data = json.load(f)
        version = data["machine"]["python_version"].split()[0]
        sections.append(render_sweep_tables(f"Python {version}", data))

    doc = REPORT_PREAMBLE + "\n" + "\n\n".join(sections) + "\n"
    with open(out_path, "w") as f:
        f.write(doc)
    print(f"wrote {out_path}", file=sys.stderr)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    sweep_p = sub.add_parser("sweep")
    sweep_p.add_argument("--out", required=True)

    report_p = sub.add_parser("report")
    report_p.add_argument("inputs", nargs="+")
    report_p.add_argument("--out", required=True)

    args = parser.parse_args()

    if args.mode == "sweep":
        results = sweep()
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"wrote {args.out}", file=sys.stderr)
    elif args.mode == "report":
        report(args.inputs, args.out)


if __name__ == "__main__":
    main()
