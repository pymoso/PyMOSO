"""
Smoke tests for the benchmark scripts under docs/.

They live outside the package and nothing else imports them, so an API
change breaks them silently. That has happened twice out of twice:
docs/bench_parallel_dispatch.py was broken from the day generator
selection landed until someone next tried to run it, and
docs/bench_hit_cost.py broke when Oracle.crn_advance() was removed and
was noticed only because a timing run failed.

Each test imports a script and runs it on a trivial workload. Nothing
here measures or asserts a time: the only claim is that the script
still runs to completion against the current code.
"""
import importlib.util
import json
import pathlib

import pytest

pytestmark = pytest.mark.timeout(120)

DOCS = pathlib.Path("docs")


def _load(name):
    path = DOCS / (name + ".py")
    if not path.exists():
        # A source distribution ships tests/ but not docs/.
        pytest.skip("{0} is not present (docs/ is not part of the sdist)".format(path))
    spec = importlib.util.spec_from_file_location("pymoso_docs_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bench_hit_cost_runs(capsys):
    bench = _load("bench_hit_cost")
    bench.main(repeats=2, hit_repeats=2, replication_counts=(1, 3))
    out = capsys.readouterr().out
    assert "stream_at" in out and "crn=True" in out and "crn=False" in out


def test_bench_simpar_ceiling_runs(capsys):
    bench = _load("bench_simpar_ceiling")
    from pymoso.problems.probexpensive import ProbExpensiveBi, ProbExpensiveLight
    from pymoso.solvers.rperle import RPERLE
    from pymoso.solvers.rspline import RSPLINE
    bench.main(tiers=[("Smoke", ProbExpensiveLight, RSPLINE, (97,), 60),
                      ("Smoke 2-D", ProbExpensiveBi, RPERLE, (30, 30), 150)], workers=(2,))
    out = capsys.readouterr().out
    assert "Smoke" in out and "workers=2" in out and "infinite workers" in out
    assert "upsample" in out and "cannot be batched" in out


def test_bench_parallel_dispatch_sweeps_and_reports(tmp_path):
    bench = _load("bench_parallel_dispatch")
    from pymoso.problems.probexpensive import ProbExpensiveModerate
    results = bench.sweep(tiers=[("Smoke", ProbExpensiveModerate, 20, 10)], worker_counts=[1, 2], proc_isp=2)
    assert [r["workers"] for r in results["simpar"]] == [1, 2]
    assert [r["workers"] for r in results["proc"]] == [1, 2]
    raw = tmp_path / "results.json"
    raw.write_text(json.dumps(results))
    out = tmp_path / "report.md"
    bench.report([str(raw)], str(out))
    text = out.read_text()
    assert "Smoke" in text and "simpar-ceiling.md" in text
