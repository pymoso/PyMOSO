# Databricks notebook source
# PyMOSO on a real cluster: one run, one screen of results.
#
# HOW TO RUN
#   Cell 1, on its own (it restarts Python):
#       %pip install git+https://github.com/pymoso/PyMOSO.git@dev-2.0
#   Cell 2: paste this whole file and run it. Nothing else is needed.
#
# WHAT TO KEEP
#   Only the block printed at the end between the two rulers. Each line
#   ends with "~xx", a check on that line, and the block ends with a SUM
#   over all of it; docs/databricks/dbx_kit.py verify <file> checks a
#   typed copy and says which line is wrong. Everything printed above the
#   block is progress, and everything below it is detail for reading on
#   the spot. Neither needs copying.
#
# IF SOMETHING FAILS
#   Each part is independent and the block is printed whatever happened,
#   including after a cancel. A failed part leaves an "X" line naming it.
#   To re-run only some parts, edit SECTIONS below.
#
# Generated values in the KNOWN block further down come from
# dbx_kit.py gen; do not edit them by hand.
import hashlib
import json
import os
import platform
import socket
import sys
import time
import traceback
import warnings

KIT = "1"

CFG = dict(
    # Which parts to run, in this order.
    SECTIONS=("env", "probe", "identity", "sweep", "repl"),
    # Tasks in the hardware probe. More than the cluster has slots, so
    # that every executor gets some.
    PROBE_TASKS=128,
    # Scaling sweep: sample paths of this cost, doubling the number of
    # paths until the speedup stops growing, the cap, or the time box.
    SWEEP_UNITS=20000,          # sha256 rounds per replication (~4 ms)
    SWEEP_BUDGET=400,
    SWEEP_MAX_PATHS=512,
    SWEEP_SECONDS=600,
    # Replication-level break-even: (sha256 rounds per replication,
    # budget) for each cost tier, and the simpar values to try. A budget
    # is only checked between RA iterations (KNOWN_ISSUES.md issue 16):
    # these run 1,182, 468, 468 and 231 replications, and the block
    # reports that real count, not the budget.
    REPL_TIERS=((20000, 1000), (100000, 300), (500000, 300), (2000000, 100)),
    REPL_PARTS=(6, 32),
    REPL_SECONDS=900,
    # Identity checks: small, free of the cost burn, exact.
    IDENT_ISP=8,
    IDENT_BUDGET=150,
)
CFG.update(globals().get("DBX_OVERRIDES", {}))      # the local test harness only

SEED = (12345,) * 6
X0 = (40, 40, 40)

# KNOWN-BEGIN
KNOWN = {'core': {'py311-': 'af9024fb', 'py312+': '707b5a73'},
 'generated': '2026-10-13 09:12:05',
 'ident': {'builtin': '23369797',
           'crn': '66b3450e',
           'libm': 'cbc74a42',
           'paths': '38124230',
           'philox': '93b7367b',
           'repl': 'e80f92d8'},
 'libm': 'bd003174',
 'libm_fn': {'atan': '7e5aae7d',
             'cos': 'ac22d20c',
             'erf': 'ae68b33d',
             'exp': 'ddd6c6c5',
             'gamma': 'b6d097e1',
             'log': 'd8173881',
             'oracle': 'ea40a44a',
             'pow': '829cafcc',
             'sin': '5b585872',
             'sqrt': '3f43787b',
             'tan': '14e71c87',
             'tanh': '75f0cb06'},
 'on': 'x86_64 glibc-2.41 python 3.14.8',
 'pymoso': '2.0.0.dev0',
 'repl': {'100': ['e80f92d8', 231], '1000': ['34fb189f', 1182], '300': ['9293efce', 468]},
 'sweep': {'1': ['f8f0015e', 519],
           '1024': ['fa8d6686', 526989],
           '128': ['47458801', 66087],
           '16': ['9e8c26fd', 8394],
           '2': ['ff0c9928', 1011],
           '256': ['f1c62fd4', 132801],
           '32': ['b3a1c6e7', 16665],
           '4': ['d3e53114', 2130],
           '512': ['ec5670b4', 264921],
           '64': ['252eeae4', 33621],
           '8': ['97932a35', 4377]},
 'tree': 'e7e4dc1b'}
# KNOWN-END

try:
    import pymoso
    from pymoso.chnbase import Oracle
    IMPORT_ERROR = None
except Exception as _e:                              # the block still has to print
    IMPORT_ERROR = _e
    Oracle = object


# ---------------------------------------------------------------------------
# The test problem. Defined here, in the notebook, on purpose: it reaches
# the executors the way a user's own problem does, by value.
# ---------------------------------------------------------------------------

def _burn(units):
    """CPU cost that never touches x or the random stream: `units`
    chained sha256 rounds. Results are identical at every cost."""
    digest = b"pymoso-dbx"
    for _ in range(units):
        digest = hashlib.sha256(digest).digest()


class DbxProblem(Oracle):
    """Three dimensions, two objectives, noisy quadratics. Uses only
    integer arithmetic, addition of floats, and pymoso's own normal
    variate -- nothing whose last bit depends on the machine's maths
    library beyond what pymoso itself uses."""
    burn_units = 0

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 3
        super().__init__(rng)

    def g(self, x, rng):
        if not all(-200 <= xi <= 200 for xi in x):
            return False, ()
        _burn(self.burn_units)
        z1 = rng.normalvariate(0, 2)
        z2 = rng.normalvariate(0, 2)
        f1 = (x[0] - 6) ** 2 + (x[1] + 4) ** 2 + (x[2] - 2) ** 2 + z1
        f2 = (x[0] + 5) ** 2 + (x[1] - 3) ** 2 + (x[2] + 6) ** 2 + z2
        return True, (f1, f2)


class LibmProblem(DbxProblem):
    """The same shape, with objectives that go through the platform's
    maths library on purpose. If this one differs across machines and
    DbxProblem does not, the difference is the user's own arithmetic,
    not the backend."""

    def g(self, x, rng):
        import math
        if not all(-200 <= xi <= 200 for xi in x):
            return False, ()
        u = rng.random()
        z = rng.normalvariate(0, 1)
        e = rng.expovariate(1.5)
        a = math.sqrt((x[0] - 6) ** 2 + (x[1] + 4) ** 2 + (x[2] - 2) ** 2 + 1.0)
        b = math.sqrt((x[0] + 5) ** 2 + (x[1] - 3) ** 2 + (x[2] + 6) ** 2 + 1.0)
        f1 = math.pow(a, 1.7) + math.exp(0.3 * z) + math.sin(3.0 * u) + math.log1p(e)
        f2 = math.pow(b, 1.7) + math.tanh(z) * 2.0 + math.cos(5.0 * u) + math.atan2(e, 1.0 + u)
        return True, (f1, f2)


def tier(units, base=None):
    """The problem at a given cost. A class made on the spot, as a
    parameterised user problem would be."""
    base = base or DbxProblem
    return type("{0}_{1}".format(base.__name__, units), (base,), {"burn_units": units})


def tester_for(problem):
    class DbxTester:
        def __init__(self):
            self.ranorc = problem

        def metric(self, eles):
            return len(eles)
    return DbxTester


# ---------------------------------------------------------------------------
# Hashing: short, exact, and the same on every machine and Python.
# ---------------------------------------------------------------------------

def canon(obj):
    if isinstance(obj, bool) or obj is None:
        return repr(obj)
    if isinstance(obj, float):
        return obj.hex()
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, str):
        return "s:" + obj
    if isinstance(obj, dict):
        return "{" + ",".join(sorted(canon(k) + "=" + canon(v) for k, v in obj.items())) + "}"
    if isinstance(obj, (set, frozenset)):
        return "<" + ",".join(sorted(canon(v) for v in obj)) + ">"
    if isinstance(obj, (list, tuple)):
        return "(" + ",".join(canon(v) for v in obj) + ")"
    return "?" + type(obj).__name__


def h8(obj):
    return hashlib.sha256(canon(obj).encode("ascii", "replace")).hexdigest()[:8]


def normalise(text):
    return " ".join(text.strip().lower().split())


def line_check(text):
    return hashlib.sha256(normalise(text).encode("ascii", "replace")).hexdigest()[:2]


def block_sum(lines):
    return hashlib.sha256("\n".join(normalise(t) for t in lines).encode("ascii", "replace")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# What every machine is asked to compute, and to say about itself.
# Runs on the driver and, through a UDF, on the executors.
# ---------------------------------------------------------------------------

def tree_fingerprint():
    """A hash of the installed pymoso's source: which commit is really
    installed here."""
    import pymoso
    root = os.path.dirname(pymoso.__file__)
    digest = hashlib.sha256()
    for sub in ("", "backends", "commands", "prng", "problems", "solvers", "testers"):
        folder = os.path.join(root, sub)
        if not os.path.isdir(folder):
            digest.update(("missing:" + sub).encode())
            continue
        for name in sorted(n for n in os.listdir(folder) if n.endswith(".py")):
            digest.update((sub + "/" + name).encode())
            with open(os.path.join(folder, name), "rb") as f:
                digest.update(f.read().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:8]


def core_workload():
    """pymoso's own generators and one real Oracle: every float it
    produces, exactly."""
    from pymoso.prng import registry
    from pymoso.prng.base import ensure_random_compatible
    from pymoso.prng.mrg32k3a import bsm
    values = []
    for name in ("mrg32k3a", "mrg31k3p", "philox4x32"):
        mod = registry.GENERATORS[name]
        for stream, offset in ((0, 0), (3, 12345), (7, 2 ** 40 + 17)):
            s = ensure_random_compatible(mod.stream_at(mod.DEFAULT_SEED, stream, offset))
            values.extend(s.random() for _ in range(40))
            values.extend(s.normalvariate(0, 1) for _ in range(400))
        for crn in (False, True):
            orc = DbxProblem(mod.stream_at(mod.DEFAULT_SEED, 1, 0))
            orc.set_crnflag(crn)
            for x in ((3, 4, 5), (-7, 0, 11), (40, 40, 40)):
                values.append(orc.hit(x, 9))
    # The normal variate's tails are where it calls log().
    values.extend(bsm(u) for u in (1e-12, 1e-9, 1e-6, 1e-3, 0.02, 0.3, 0.5, 0.7, 0.98, 1 - 1e-3, 1 - 1e-6, 1 - 1e-9))
    return h8(values)


def libm_workload():
    """The maths library directly, function by function, and an Oracle
    whose g() uses it. Returns (overall hash, {function: hash})."""
    import math
    from pymoso.prng import registry
    grid = [k / 37.0 for k in range(1, 400)]
    functions = {
        "exp": [math.exp(v) for v in grid] + [math.exp(-v) for v in grid],
        "log": [math.log(v) for v in grid] + [math.log1p(v) for v in grid],
        "sin": [math.sin(v) for v in grid] + [math.sin(1e5 * v) for v in grid],
        "cos": [math.cos(v) for v in grid] + [math.cos(1e5 * v) for v in grid],
        "tan": [math.tan(v) for v in grid],
        "pow": [math.pow(v, 1.7) for v in grid] + [v ** 0.3 for v in grid],
        "atan": [math.atan2(v, 1.3) for v in grid] + [math.atan(v) for v in grid],
        "tanh": [math.tanh(v) for v in grid] + [math.sinh(v) for v in grid],
        "erf": [math.erf(v) for v in grid] + [math.erfc(v) for v in grid],
        "gamma": [math.lgamma(v) for v in grid] + [math.gamma(v) for v in grid if v < 9],
        "sqrt": [math.sqrt(v) for v in grid],
    }
    hits = []
    for name in ("mrg32k3a", "philox4x32"):
        mod = registry.GENERATORS[name]
        orc = LibmProblem(mod.stream_at(mod.DEFAULT_SEED, 1, 0))
        orc.set_crnflag(False)
        for x in ((3, 4, 5), (-7, 0, 11), (40, 40, 40)):
            hits.append(orc.hit(x, 9))
    functions["oracle"] = hits
    per_function = {name: h8(values) for name, values in functions.items()}
    return h8(sorted(per_function.items())), per_function


def machine_report(index):
    """One JSON string: what this process is, and what it computed."""
    out = {"i": int(index)}
    try:
        out["host"] = socket.gethostname()
        out["pid"] = os.getpid()
        out["py"] = platform.python_version()
        out["arch"] = platform.machine()
        out["libc"] = "-".join(part for part in platform.libc_ver() if part) or platform.system()
        out["cores"] = os.cpu_count()
        try:
            out["aff"] = len(os.sched_getaffinity(0))
        except Exception:
            out["aff"] = None
        cpu = ""
        try:
            with open("/proc/cpuinfo") as f:
                for row in f:
                    if row.lower().startswith(("model name", "cpu model", "hardware")):
                        cpu = row.split(":", 1)[1].strip()
                        break
        except Exception:
            cpu = ""
        out["cpu"] = cpu or platform.processor() or "?"
    except Exception as e:
        out["facts_err"] = type(e).__name__ + ": " + str(e)[:80]
    try:
        import pymoso
        out["pymoso"] = pymoso.__version__
        out["tree"] = tree_fingerprint()
        try:
            import cloudpickle
            out["cp"] = cloudpickle.__version__
        except Exception:
            out["cp"] = "none"
        started = time.perf_counter()
        out["core"] = core_workload()
        out["libm"], out["libm_fn"] = libm_workload()
        out["secs"] = round(time.perf_counter() - started, 3)
    except Exception as e:
        out["err"] = type(e).__name__ + ": " + str(e)[:120]
    return json.dumps(out)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

LINES = []          # the block
DETAILS = []        # for reading on the spot, not for copying
T0 = time.time()


def progress(text):
    print("[{0:6.0f}s] {1}".format(time.time() - T0, text), flush=True)


def emit(text):
    text = " ".join(str(text).split())
    LINES.append(text)
    progress("> " + text)


def short(values, limit=3):
    """Distinct values, most common first, as a/b/c."""
    counts = {}
    for v in values:
        counts[str(v)] = counts.get(str(v), 0) + 1
    ordered = sorted(counts, key=lambda k: (-counts[k], k))
    text = "/".join(v.replace(" ", "_") for v in ordered[:limit])
    return text + ("/+{0}".format(len(ordered) - limit) if len(ordered) > limit else "")


def verdict(ok):
    return "PASS" if ok else "FAIL"


def core_expected(python_version):
    """pymoso's normal variate adds its terms with the built-in sum(),
    and Python 3.12 changed how sum() adds floats. About four variates
    in ten differ in the last bit between Python 3.11 and 3.12 on the
    same machine, so the known-good value depends on which side of
    3.12 the Python computing it is."""
    try:
        major, minor = (int(part) for part in str(python_version).split(".")[:2])
    except Exception:
        return None
    return known("core", "py312+" if (major, minor) >= (3, 12) else "py311-")


def known(*keys):
    value = KNOWN
    for key in keys:
        if not isinstance(value, dict) or str(key) not in value:
            return None
        value = value[str(key)]
    return value


def run_on_executors(spark, function, count):
    """`function(i)` for i in range(count), one Spark task each; the
    same route SparkBackend takes."""
    from pyspark.sql.functions import udf
    from pyspark.sql.types import StringType
    try:
        column = udf(function, StringType(), useArrow=False)("id")
    except TypeError:                                 # a pyspark without useArrow
        column = udf(function, StringType())("id")
    rows = spark.range(count, numPartitions=count).select("id", column.alias("r")).collect()
    return [row["r"] for row in sorted(rows, key=lambda row: row["id"])]


def conf(spark, key):
    try:
        value = spark.conf.get(key)
        return value if value not in (None, "") else None
    except Exception:
        return None


def section_env(spark):
    mode = "connect" if "connect" in type(spark).__module__ else "classic"
    try:
        context = spark.sparkContext
        parallelism = context.defaultParallelism
        has_context = "yes"
    except Exception:
        parallelism = None
        has_context = "no"
    dbr = os.environ.get("DATABRICKS_RUNTIME_VERSION") or conf(spark, "spark.databricks.clusterUsageTags.sparkVersion") or "?"
    try:
        import pyspark
        pyspark_version = pyspark.__version__
    except Exception:
        pyspark_version = "?"
    emit("E1 kit={0} dbr={1} spark={2} pyspark={3} mode={4} sc={5}".format(
        KIT, dbr, getattr(spark, "version", "?"), pyspark_version, mode, has_context))
    node = conf(spark, "spark.databricks.clusterUsageTags.clusterNodeType") or "?"
    workers = conf(spark, "spark.databricks.clusterUsageTags.clusterWorkers") or conf(spark, "spark.executor.instances") or "?"
    emit("E2 node={0} workers={1} exec_cores={2} par={3} serverless={4}".format(
        node, workers, conf(spark, "spark.executor.cores") or "?", parallelism if parallelism is not None else "?",
        os.environ.get("IS_SERVERLESS") or conf(spark, "spark.databricks.serverless.enabled") or "?"))
    driver = json.loads(machine_report(-1))
    STATE["driver"] = driver
    emit("D1 py={0} arch={1} libc={2} cores={3} cp={4}".format(
        driver.get("py"), driver.get("arch"), driver.get("libc"), driver.get("cores"), driver.get("cp", "?")))
    emit("D2 cpu={0}".format(str(driver.get("cpu", "?")).replace(" ", "_")[:60]))
    if "err" in driver:
        emit("X driver {0}".format(driver["err"][:60]))
        return
    tree_ok = driver.get("tree") == known("tree")
    emit("D3 pymoso={0} tree={1} tree_ok={2}".format(driver.get("pymoso"), driver.get("tree"), verdict(tree_ok)))
    emit("D4 core={0} {1} libm={2} {3}".format(
        driver.get("core"), verdict(driver.get("core") == core_expected(driver.get("py"))),
        driver.get("libm"), verdict(driver.get("libm") == known("libm"))))


def section_probe(spark):
    count = CFG["PROBE_TASKS"]
    started = time.perf_counter()
    reports = [json.loads(r) for r in run_on_executors(spark, machine_report, count)]
    elapsed = time.perf_counter() - started
    STATE["reports"] = reports
    hosts = {r.get("host") for r in reports}
    workers = {(r.get("host"), r.get("pid")) for r in reports}
    errors = [r for r in reports if "err" in r or "facts_err" in r]
    emit("P1 tasks={0} hosts={1} workers={2} err={3} secs={4:.1f}".format(count, len(hosts), len(workers), len(errors), elapsed))
    emit("P2 py={0} arch={1} libc={2} cores={3} aff={4}".format(
        short(r.get("py") for r in reports), short(r.get("arch") for r in reports),
        short(r.get("libc") for r in reports), short(r.get("cores") for r in reports), short(r.get("aff") for r in reports)))
    cpus = sorted({str(r.get("cpu")) for r in reports})
    emit("P3 cpus={0} cpu={1}".format(len(cpus), short((str(r.get("cpu")) for r in reports), 2)[:58]))
    emit("P4 pymoso={0} tree={1} trees={2} tree_ok={3} cp={4}".format(
        short(r.get("pymoso") for r in reports), short(r.get("tree") for r in reports),
        len({r.get("tree") for r in reports}),
        verdict(all(r.get("tree") == known("tree") for r in reports)), short(r.get("cp") for r in reports)))
    if errors:
        emit("X probe {0}".format(str(errors[0].get("err") or errors[0].get("facts_err"))[:60]))
        DETAILS.append("probe errors: " + json.dumps(errors[:5]))
    driver = STATE.get("driver", {})
    for name in ("core", "libm"):
        seen = [r.get(name) for r in reports if name in r]
        distinct = sorted(set(seen))
        if name == "core":
            local_ok = bool(seen) and all(r.get("core") == core_expected(r.get("py")) for r in reports if "core" in r)
        else:
            local_ok = bool(seen) and distinct == [known(name)]
        text = "ID {0} h={1} hashes={2} of={3} drv={4} loc={5}".format(
            name, short(seen, 2), len(distinct), len(seen),
            verdict(bool(seen) and distinct == [driver.get(name)]), verdict(local_ok))
        if name == "libm" and not local_ok:
            bad = sorted({fn for r in reports for fn, h in (r.get("libm_fn") or {}).items() if h != known("libm_fn", fn)})
            text += " bad=" + ",".join(bad)[:40]
        emit(text)
        if len(distinct) > 1:
            by_cpu = {}
            for r in reports:
                by_cpu.setdefault((r.get(name), r.get("cpu"), r.get("libc"), r.get("arch")), set()).add(r.get("host"))
            DETAILS.append("{0} hashes by machine: {1}".format(name, {str(k): len(v) for k, v in by_cpu.items()}))


def identity_runs():
    """The end-to-end identity checks: name -> function of a backend
    (None for none). Small, no cost burn. dbx_kit.py runs the same
    functions locally to produce the known-good hashes."""
    from pymoso.chnutils import solve, testsolve
    from pymoso.solvers.rperle import RPERLE
    from pymoso.testers.tpatester import TPATester
    budget, isp = CFG["IDENT_BUDGET"], CFG["IDENT_ISP"]

    def kw(backend, base, **extra):
        base = dict(base)
        if backend is not None:
            base.update(backend=backend, **extra)
        return base

    return [
        ("paths", lambda b: testsolve(tester_for(DbxProblem), RPERLE, X0, **kw(b, dict(budget=budget, seed=SEED, isp=isp)))),
        ("builtin", lambda b: testsolve(TPATester, RPERLE, (30, 30), **kw(b, dict(budget=budget, seed=SEED, isp=isp)))),
        ("repl", lambda b: solve(DbxProblem, RPERLE, X0, **kw(b, dict(budget=budget, seed=SEED), simpar=4))),
        ("crn", lambda b: solve(DbxProblem, RPERLE, X0, **kw(b, dict(budget=budget, seed=SEED, crn=True), simpar=4))),
        ("philox", lambda b: solve(DbxProblem, RPERLE, X0, **kw(b, dict(budget=budget, generator="philox4x32"), simpar=4))),
        ("libm", lambda b: solve(LibmProblem, RPERLE, X0, **kw(b, dict(budget=budget, seed=SEED), simpar=4))),
    ]


def section_identity(spark):
    from pymoso.backends.spark import SparkBackend
    import pymoso.backends.spark as spark_module
    from pymoso.backends.remote import SlowDispatchWarning, VersionMismatch
    from pymoso.chnutils import testsolve
    from pymoso.solvers.rperle import RPERLE
    from pymoso.testers.tpatester import TPATester

    for name, run in identity_runs():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SlowDispatchWarning)
                here = h8(run(None))
                there = h8(run(SparkBackend(spark)))
            emit("I {0} h={1} drv={2} loc={3}".format(name, there, verdict(there == here), verdict(there == known("ident", name))))
        except KeyboardInterrupt:
            raise
        except BaseException as e:
            failed("ident-" + name, e)
    sent = spark_module.__version__
    spark_module.__version__ = "0.0.0-dbx"
    try:
        testsolve(TPATester, RPERLE, (30, 30), budget=50, seed=SEED, isp=2, backend=SparkBackend(spark))
        emit("I version raised=nothing FAIL")
    except VersionMismatch:
        emit("I version raised=VersionMismatch PASS")
    except Exception as e:
        emit("I version raised={0} FAIL".format(type(e).__name__))
        DETAILS.append("version check: " + "".join(traceback.format_exception(type(e), e, e.__traceback__))[-1500:])
    finally:
        spark_module.__version__ = sent


def section_sweep(spark):
    from pymoso.backends.spark import SparkBackend
    from pymoso.chnutils import testsolve
    from pymoso.solvers.rperle import RPERLE
    tester = tester_for(tier(CFG["SWEEP_UNITS"]))
    started = time.time()
    emit("S units={0} budget={1} | n wall_s task_s x sims h ok".format(CFG["SWEEP_UNITS"], CFG["SWEEP_BUDGET"]))
    paths, alone, previous, flat = 1, None, 0.0, 0
    while paths <= CFG["SWEEP_MAX_PATHS"]:
        if alone is not None:
            expected = paths * alone / max(previous, 1.0)
            if time.time() - started + expected > CFG["SWEEP_SECONDS"]:
                emit("S stop=timebox before n={0}".format(paths))
                break
        backend = SparkBackend(spark)
        res, _ = testsolve(tester, RPERLE, X0, budget=CFG["SWEEP_BUDGET"], seed=SEED, isp=paths, backend=backend)
        wall, work = backend.dispatch_seconds, backend.work_seconds
        if alone is None:
            alone = work                                # one path, nothing else running
        speedup = paths * alone / wall
        sims = sum(r["simcalls"][max(r["simcalls"])] for r in res.values())
        digest = h8(res)
        expect = known("sweep", paths)
        ok = "?" if expect is None else ("P" if expect == [digest, sims] else "F")
        emit("S {0} {1:.1f} {2:.2f} {3:.1f} {4} {5} {6}".format(paths, wall, work / paths, speedup, sims, digest, ok))
        flat = flat + 1 if speedup < 1.15 * previous else 0
        if flat >= 2:
            emit("S stop=plateau")
            break
        previous = max(previous, speedup)
        paths *= 2
    else:
        emit("S stop=cap")


def section_repl(spark):
    from pymoso.backends.remote import RemotePool, SlowDispatchWarning
    from pymoso.backends.spark import SparkBackend
    from pymoso.chnutils import solve
    from pymoso.solvers.rperle import RPERLE

    class RecordingPool(RemotePool):
        def run(self, tasks):
            tasks = list(tasks)
            self._backend.calls.append([sum(block.count for block in task[1][0]) for task in tasks])
            return super().run(tasks)

    class RecordingBackend(SparkBackend):
        """SparkBackend, noting how many replications each task of each
        job carried. Dispatch itself is untouched."""

        def __init__(self, session):
            super().__init__(session)
            self.calls = []

        def pool(self, workers, initializer=None, initargs=()):
            return RecordingPool(self, initializer, initargs)

    started = time.time()
    emit("R | units k ms_rep req sims jobs ms_job x bound warn h ok")
    for units, budget in CFG["REPL_TIERS"]:
        for parts in CFG["REPL_PARTS"]:
            if time.time() - started > CFG["REPL_SECONDS"]:
                emit("R stop=timebox before units={0} k={1}".format(units, parts))
                return
            backend = RecordingBackend(spark)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = solve(tier(units), RPERLE, X0, budget=budget, seed=SEED, simpar=parts, backend=backend)
            warned = any(issubclass(w.category, SlowDispatchWarning) for w in caught)
            sims = sum(sum(call) for call in backend.calls)
            bound = sims / max(1, sum(max(call) for call in backend.calls))
            wall, work = backend.dispatch_seconds, backend.work_seconds
            digest = h8(result)
            expect = known("repl", budget)
            ok = "?" if expect is None else ("P" if expect == [digest, sims] else "F")
            emit("R {0} {1} {2:.1f} {3} {4} {5} {6:.0f} {7:.2f} {8:.2f} {9} {10} {11}".format(
                units, parts, work / sims * 1e3, budget, sims, backend.jobs, wall / backend.jobs * 1e3,
                work / wall, bound, "Y" if warned else "n", digest, ok))


STATE = {}
SECTION_FUNCTIONS = {
    "env": section_env, "probe": section_probe, "identity": section_identity,
    "sweep": section_sweep, "repl": section_repl,
}


def failed(name, exc):
    emit("X {0} {1}: {2}".format(name, type(exc).__name__, str(exc).replace("\n", " ")[:44]))
    DETAILS.append("--- {0} ---\n{1}".format(name, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:]))


def print_block():
    ruler = "=" * 72
    print()
    print(ruler)
    print("PYMOSO-DBX kit={0}   copy from here to the SUM line".format(KIT))
    for text in LINES:
        print("{0} ~{1}".format(text, line_check(text)))
    print("SUM {0} lines={1}".format(block_sum(LINES), len(LINES)))
    print(ruler)
    if DETAILS:
        print("\nDETAILS (for reading here; not part of the block)\n")
        for text in DETAILS:
            print(text)
            print()


def main(spark):
    del LINES[:], DETAILS[:]
    try:
        if IMPORT_ERROR is not None:
            failed("import-pymoso", IMPORT_ERROR)
        for name in CFG["SECTIONS"]:
            if IMPORT_ERROR is not None and name != "env":
                continue
            progress("section " + name)
            try:
                SECTION_FUNCTIONS[name](spark)
            except KeyboardInterrupt as e:
                failed(name, e)
                emit("X cancelled during {0}".format(name))
                break
            except BaseException as e:
                failed(name, e)
        emit("Z secs={0:.0f} sections={1}".format(time.time() - T0, ",".join(CFG["SECTIONS"])))
    finally:
        print_block()


if __name__ == "__main__":
    main(spark)                                       # noqa: F821 -- the notebook's own session
