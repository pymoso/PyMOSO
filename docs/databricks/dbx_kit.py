#!/usr/bin/env python
"""
Companion to pymoso_dbx_notebook.py: the notebook is run once on a
cluster nothing can be exported from, so everything that can be done
beforehand or afterwards is done here.

    python docs/databricks/dbx_kit.py gen [other-python ...]
        Compute the known-good values from the pymoso installed in this
        environment and write them into the notebook (between KNOWN-BEGIN
        and KNOWN-END). Run it on the tree that will be pushed; the
        notebook then prints PASS or FAIL on the cluster by itself.
        Needs cloudpickle (the `notebook` extra). One value depends on
        whether Python is older than 3.12 (the notebook's
        core_expected() says why): name an interpreter on the other
        side of 3.12, with pymoso installed, to have both embedded.

    python docs/databricks/dbx_kit.py known [processes]
        Print the same values as JSON without writing anything, to
        compare what different Python versions compute.

    python docs/databricks/dbx_kit.py verify typed_block.txt
        Check a hand-typed copy of the block the notebook printed: each
        line's own check, the SUM over all of them, and every hash
        against the known-good values. Says which line is wrong.

    python docs/databricks/dbx_kit.py localtest classic|connect [--fail] [--defaults]
        Run the notebook, unmodified, against a local Spark with small
        workloads, and check the block it prints. Needs pyspark and a
        JVM; set PYSPARK_PYTHON to a second interpreter to have the
        executors differ from the driver. --fail adds a part that
        raises, to show the block still prints. --defaults runs the
        workloads at the size the cluster will (a quarter of an hour
        or more on a laptop).
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import pprint
import runpy
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
NOTEBOOK = HERE / "pymoso_dbx_notebook.py"
BEGIN, END = "# KNOWN-BEGIN\n", "# KNOWN-END\n"
KNOWN_PATHS = 1024


def load_notebook():
    spec = importlib.util.spec_from_file_location("pymoso_dbx_notebook", NOTEBOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# gen
# ---------------------------------------------------------------------------

def compute_known(nb, paths=KNOWN_PATHS, proc=6):
    import platform
    import pymoso
    from pymoso import executor
    from pymoso.chnutils import solve, testsolve
    from pymoso.solvers.rperle import RPERLE

    known = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "on": "{0} {1} python {2}".format(platform.machine(), "-".join(platform.libc_ver()), platform.python_version()),
        "pymoso": pymoso.__version__,
        "tree": nb.tree_fingerprint(),
        # Keyed by which side of Python 3.12 computed it: see the
        # notebook's core_expected().
        "core": {"py312+" if sys.version_info >= (3, 12) else "py311-": nb.core_workload()},
    }
    known["libm"], known["libm_fn"] = nb.libm_workload()
    known["ident"] = {name: nb.h8(run(None)) for name, run in nb.identity_runs()}

    # The sweep's paths, at no cost: the burn never touches x or the
    # stream, so these are the results at every cost.
    res, _ = testsolve(nb.tester_for(nb.tier(0)), RPERLE, nb.X0, budget=nb.CFG["SWEEP_BUDGET"], seed=nb.SEED, isp=paths, proc=proc)
    known["sweep"] = {}
    count = 1
    while count <= paths:
        part = {i: res[i] for i in range(count)}
        sims = sum(r["simcalls"][max(r["simcalls"])] for r in part.values())
        known["sweep"][str(count)] = [nb.h8(part), sims]
        count *= 2

    # Replication level: the result, and how many replications were
    # really run (every block the oracle planned, infeasible ones too).
    known["repl"] = {}
    real_run = executor.SerialExecutor.run
    for _, budget in nb.CFG["REPL_TIERS"]:
        ran = [0]

        def counting(self, blocks, ran=ran):
            blocks = list(blocks)
            ran[0] += sum(block.count for block in blocks)
            return real_run(self, blocks)

        executor.SerialExecutor.run = counting
        try:
            result = solve(nb.tier(0), RPERLE, nb.X0, budget=budget, seed=nb.SEED)
        finally:
            executor.SerialExecutor.run = real_run
        known["repl"][str(budget)] = [nb.h8(result), ran[0]]
    return known


def command_gen(other_pythons=()):
    nb = load_notebook()
    known = compute_known(nb)
    for python in other_pythons:
        import subprocess
        result = subprocess.run([python, str(pathlib.Path(__file__).resolve()), "known"], capture_output=True, text=True)
        lines = [line for line in result.stdout.splitlines() if line.startswith("KNOWN-JSON ")]
        if not lines:
            raise SystemExit("{0} did not produce known values:\n{1}".format(python, result.stderr[-2000:]))
        other = json.loads(lines[0][len("KNOWN-JSON "):])
        different = sorted(k for k in other if k != "core" and other[k] != known[k])
        if different:
            raise SystemExit("{0} computes different values for {1}: the notebook cannot embed one answer".format(python, different))
        known["core"].update(other["core"])
        print("  ", python, "agrees on everything but core, which is", other["core"])
    source = NOTEBOOK.read_text()
    head, rest = source.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    literal = "KNOWN = " + pprint.pformat(known, width=100, sort_dicts=True) + "\n"
    NOTEBOOK.write_text(head + BEGIN + literal + END + tail)
    print("wrote known-good values into", NOTEBOOK.name)
    print("  tree", known["tree"], "| core", known["core"], "| libm", known["libm"])
    print("  ident", known["ident"])
    print("  sweep", {k: v for k, v in known["sweep"].items() if int(k) <= 8}, "... to", KNOWN_PATHS)
    print("  repl ", known["repl"])
    print("  budget against simulations really run:",
          ", ".join("{0} -> {1} ({2:.2f}x)".format(b, v[1], v[1] / int(b)) for b, v in known["repl"].items()))


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def parse_block(text):
    """The block's lines, from printed output or from a typed copy.
    Returns (list of (content, check or None), sum or None, declared
    line count or None)."""
    rows, total, declared = [], None, None
    inside = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or set(line) == {"="}:
            continue
        if line.upper().startswith("PYMOSO-DBX"):
            inside, rows, total = True, [], None
            continue
        if line.startswith("[") and "s] " in line[:12]:
            continue                                    # progress output
        if line.upper().startswith("DETAILS"):
            break
        if line.upper().startswith("SUM "):
            parts = line.split()
            total = parts[1].lower()
            for part in parts[2:]:
                if part.lower().startswith("lines="):
                    declared = int(part.split("=")[1])
            break
        if "~" in line:
            content, check = line.rsplit("~", 1)
            rows.append((content.strip(), check.strip().lower()))
        elif inside:
            rows.append((line, None))
    return rows, total, declared


def check_block(nb, text, out=print):
    rows, total, declared = parse_block(text)
    problems = 0
    if not rows:
        out("no block found: expected lines ending in ~xx and a SUM line")
        return 1
    for number, (content, check) in enumerate(rows, 1):
        want = nb.line_check(content)
        if check is None:
            out("line {0:2d}: no ~xx check typed (should be ~{1}) | {2}".format(number, want, content))
            problems += 1
        elif check != want:
            out("line {0:2d}: MISTYPED -- its check is ~{1}, the text gives ~{2} | {3}".format(number, check, want, content))
            problems += 1
    if declared is not None and declared != len(rows):
        out("the block says lines={0} and {1} were found: a line is missing or doubled".format(declared, len(rows)))
        problems += 1
    want = nb.block_sum([content for content, _ in rows])
    if total is None:
        out("no SUM line found (should be {0})".format(want))
        problems += 1
    elif total != want:
        out("SUM does not match: typed {0}, the lines give {1}".format(total, want))
        problems += 1
    out("{0} lines; transcription {1}".format(len(rows), "OK" if not problems else "HAS {0} PROBLEM(S)".format(problems)))

    # What the block says, re-checked against the known-good values
    # rather than trusted from the PASS/FAIL the cluster printed.
    known = nb.KNOWN
    verdicts = []
    for content, _ in rows:
        fields = content.lower().split()            # a typed copy may differ in case
        named = dict(f.split("=", 1) for f in fields if "=" in f)
        tag = fields[0].upper()
        if tag in ("D3", "P4") and "tree" in named:
            verdicts.append(("{0} installed tree".format("driver" if tag == "D3" else "executors"), named["tree"] == known.get("tree"), named["tree"]))
        if tag == "D4":
            verdicts.append(("driver core", named.get("core") in known.get("core", {}).values(), named.get("core")))
            verdicts.append(("driver libm", named.get("libm") == known.get("libm"), named.get("libm")))
        if tag == "ID":
            name = fields[1]
            expect = list(known.get("core", {}).values()) if name == "core" else [known.get(name)]
            verdicts.append(("executors {0} ({1} distinct over {2} tasks)".format(name, named.get("hashes"), named.get("of")),
                             named.get("h") in expect and named.get("hashes") == "1", named.get("h")))
        if tag == "I" and "h" in named:
            verdicts.append(("end to end " + fields[1], named["h"] == known.get("ident", {}).get(fields[1]) and named.get("drv") == "pass", named["h"]))
        if tag == "I" and fields[1] == "version":
            verdicts.append(("version check", fields[-1] == "pass", named.get("raised")))
        if tag == "S" and len(fields) == 8 and fields[1].isdigit():
            expect = known.get("sweep", {}).get(fields[1])
            verdicts.append(("sweep n={0}".format(fields[1]), expect == [fields[6], int(fields[5])], fields[6]))
        if tag == "R" and len(fields) == 13 and fields[1].isdigit():
            expect = known.get("repl", {}).get(fields[4])
            verdicts.append(("repl units={0} k={1}".format(fields[1], fields[2]), expect == [fields[11], int(fields[5])], fields[11]))
        if tag == "X":
            verdicts.append(("reported failure: " + content[2:], False, ""))
    bad = [v for v in verdicts if not v[1]]
    out("{0} checks against local known-good values (generated {1} on {2}): {3} agree, {4} do not".format(
        len(verdicts), known.get("generated"), known.get("on"), len(verdicts) - len(bad), len(bad)))
    for name, _, value in bad:
        out("  DIFFERS: {0} {1}".format(name, value))
    return problems + len(bad)


def command_verify(path):
    nb = load_notebook()
    return 1 if check_block(nb, pathlib.Path(path).read_text()) else 0


# ---------------------------------------------------------------------------
# localtest
# ---------------------------------------------------------------------------

LOCAL_OVERRIDES = dict(
    PROBE_TASKS=12,
    SWEEP_UNITS=2000, SWEEP_MAX_PATHS=16, SWEEP_SECONDS=240,
    REPL_TIERS=((2000, 1000), (20000, 300), (100000, 300), (400000, 100)),
    REPL_PARTS=(3, 6), REPL_SECONDS=600,
)


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def command_localtest(mode, fail=False, defaults=False):
    from pyspark.sql import SparkSession
    if mode == "classic":
        builder = SparkSession.builder.master(os.environ.get("DBX_LOCAL_MASTER", "local-cluster[3,2,1024]"))
    else:
        builder = SparkSession.builder.remote("local[6]")
    spark = builder.config("spark.ui.enabled", "false").getOrCreate()
    overrides = {} if defaults else dict(LOCAL_OVERRIDES)
    if fail:
        overrides["SECTIONS"] = ("env", "no-such-part", "probe", "identity")
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(Tee(sys.stdout, captured)):
            runpy.run_path(str(NOTEBOOK), init_globals={"spark": spark, "DBX_OVERRIDES": overrides}, run_name="__main__")
    finally:
        spark.stop()
    nb = load_notebook()
    print("\n----- dbx_kit verify, on the block exactly as printed -----")
    problems = check_block(nb, captured.getvalue())
    rows, _, _ = parse_block(captured.getvalue())
    print("block: {0} lines, longest {1} characters".format(len(rows), max(len(c) + 4 for c, _ in rows)))
    return problems


def main(argv):
    if len(argv) >= 2 and argv[1] == "gen":
        return command_gen([a for a in argv[2:] if not a.startswith("-")])
    if len(argv) >= 2 and argv[1] == "known":
        known = compute_known(load_notebook(), proc=int(argv[2]) if len(argv) > 2 else 6)
        del known["generated"], known["on"]
        print("KNOWN-JSON " + json.dumps(known, sort_keys=True))
        return 0
    if len(argv) >= 3 and argv[1] == "verify":
        return command_verify(argv[2])
    if len(argv) >= 3 and argv[1] == "localtest":
        return 1 if command_localtest(argv[2], fail="--fail" in argv, defaults="--defaults" in argv) else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
