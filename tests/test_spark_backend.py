"""
The Spark backend against a real Spark: a local cluster with executor
JVMs of its own, and a local Spark Connect server.

Needs pyspark and a JVM, so it is skipped in the ordinary CI matrix
and run by the `extras` job, where a missing pyspark or JVM is a
failure and not a skip (tests/_extras.py). Everything that does not
need Spark is tested in every cell by tests/test_remote_backend.py.

Each mode runs tests/_spark_scenarios.py once, in a process of its own,
and the tests below read what it reported.

What this proves: pyspark's own serialization of the task, Python
workers that are not the driver and cannot import the driver's
modules, both session kinds, and results identical to no backend.
What it cannot: executors on another host or another architecture, a
Databricks runtime, or behaviour at scale. Those are verified by hand
(docs/spark-backend.md).
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from _extras import need, required

need("pyspark")
need("cloudpickle")

pytestmark = pytest.mark.timeout(600)

SCENARIOS = pathlib.Path(__file__).resolve().parent / "_spark_scenarios.py"
SPARK_TIMEOUT = 480


def _java():
    home = os.environ.get("JAVA_HOME")
    if home and os.path.exists(os.path.join(home, "bin", "java")):
        return True
    return shutil.which("java") is not None


@pytest.fixture(scope="module", params=["classic", "connect"])
def report(request, tmp_path_factory):
    mode = request.param
    if not _java():
        if required("pyspark"):
            pytest.fail("pyspark is required here (PYMOSO_REQUIRE_EXTRAS) and there is no JVM: set JAVA_HOME or put java on PATH")
        pytest.skip("needs a JVM: set JAVA_HOME or put java on PATH")
    if mode == "connect":
        need("grpc")                                        # the Spark Connect client's own dependency
    env = dict(os.environ)
    env["PYSPARK_PYTHON"] = sys.executable                  # executors use this interpreter, not whatever `python3` is
    env["PYSPARK_DRIVER_PYTHON"] = sys.executable
    env.pop("SPARK_REMOTE", None)
    result = subprocess.run(
        [sys.executable, "-I", str(SCENARIOS), mode], capture_output=True, text=True,
        cwd=tmp_path_factory.mktemp("spark-" + mode), env=env, timeout=SPARK_TIMEOUT,
    )
    lines = [line for line in result.stdout.splitlines() if "PYMOSO-SPARK-SCENARIOS " in line]
    assert result.returncode == 0 and lines, result.stdout[-2000:] + result.stderr[-6000:]
    return json.loads(lines[-1].split("PYMOSO-SPARK-SCENARIOS ", 1)[1])


def test_the_session_is_the_kind_asked_for(report):
    if report["mode"] == "classic":
        assert report["has_spark_context"] is True and "connect" not in report["session"]
    else:
        # The reason the backend is built on range() and a UDF: under
        # Spark Connect there is no sparkContext to parallelize with.
        assert report["has_spark_context"] is False and "connect" in report["session"]


def test_the_executors_are_not_the_driver(report):
    """The premise of the by-value scenarios: pymoso is installed for
    the executors' Python, and the driver's own modules are not on
    their path."""
    assert report["executors_import_pymoso"] == [True, True]
    assert report["executors_import_tests_module"] == [False, False]


@pytest.mark.parametrize("scenario", [
    "paths_builtin", "paths_main", "paths_driver_only_module", "paths_user_files",
    "replications_builtin", "replications_builtin_crn", "replications_main",
    "replications_driver_only_module", "replications_user_files", "metrics",
])
def test_spark_computes_what_no_backend_computes(report, scenario):
    assert report[scenario] is True


def test_an_exception_from_g_reaches_the_driver_as_it_would_serially(report):
    serial, spark = report["raising_serial"], report["raising_spark"]
    assert serial is not None and spark is not None
    assert spark[:2] == serial[:2] and "g() failed at x=(20, 20)" in spark[1]
    # The solver wraps what g() raised, serially and on Spark alike;
    # underneath, on Spark, is g()'s own exception as itself and the
    # executor's traceback.
    assert "ZeroDivisionError" in spark[2] and spark[2][-1] == "RemoteTraceback"
    assert "ZeroDivisionError" in serial[2] and "RemoteTraceback" not in serial[2]


def test_a_version_mismatch_is_raised_by_name(report):
    name, message, _ = report["version_mismatch"]
    assert name == "VersionMismatch" and "0.0.0-not-this-one" in message

