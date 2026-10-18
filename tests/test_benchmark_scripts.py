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
import io
import json
import os
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


def test_bench_biobjective_profile_runs_and_reports(tmp_path, monkeypatch):
    # os.getloadavg is Unix-only: run as on Windows, where its absence
    # failed this test in CI (commit 5527f60).
    monkeypatch.delattr(os, "getloadavg", raising=False)
    bench = _load("bench_biobjective_profile")
    raw = str(tmp_path / "profile.jsonl")
    configs = [("RPERLE", "Bi"), ("RSPLINE", "One")]
    seeds = {"mrg32k3a": [bench.SEEDS["mrg32k3a"][0]]}
    bench.run(raw, configs=configs, generators=("mrg32k3a",), seeds=seeds, budget=150, verbose=False)
    bench.run(raw, configs=configs, generators=("mrg32k3a",), seeds=seeds, budget=150, verbose=False)
    assert len(open(raw).read().splitlines()) == 8, "a second run must resume, not repeat"
    bench.validate(raw, tiers=("Light",), configs=configs[:1], budget=150, verbose=False)
    out = io.StringIO()
    bench.report(raw, tiers=("Light",), out=out)
    text = out.getvalue()
    assert "RPERLE" in text and "Model check" in text and "Required against done" in text


def test_bench_ne_quadratic_runs(tmp_path, monkeypatch):
    # run as on Windows, which has no os.getloadavg (see
    # test_bench_biobjective_profile_runs_and_reports)
    monkeypatch.delattr(os, "getloadavg", raising=False)
    bench = _load("bench_ne_quadratic")
    out = tmp_path / "runs.jsonl"
    bench.run(str(out), pairs=[("RPERLE", "ProbTPA"), ("RSPLINE", "ProbSimpleSO")], reps=1, budget=300,
              checkpoints=(150, 300), verbose=False)
    rows = [json.loads(line) for line in open(out)]
    assert len(rows) == 2 * len(bench.CELLS)
    assert any(r["candidates"] for r in rows if r["cell"] == "best+quadratic")
    bench.report(str(out), str(tmp_path / "report.md"))
    assert "### Quality" in (tmp_path / "report.md").read_text()


def test_bench_radius_runs(tmp_path, monkeypatch):
    # run as on Windows, which has no os.getloadavg (see
    # test_bench_biobjective_profile_runs_and_reports)
    monkeypatch.delattr(os, "getloadavg", raising=False)
    bench = _load("bench_radius")
    table, agree, total, positives = bench.verify(radii=(1, 2), thicknesses=(1,), extra=3, random_tables=2,
                                                  verbose=False)
    assert agree == total and positives and table[(1, 1)] == (True, True) and table[(1, 2)] == (True, False)
    nb = bench.nbors(str(tmp_path / "nbors.json"), radii=(1, 2), dims=(2,), repeats=2)
    out = tmp_path / "runs.jsonl"
    bench.run(str(out), pairs=[("RPERLE", "Barrier1"), ("RSPLINE", "ProbSimpleSO")], radii=(1, 2),
              seeds={"subject": 1, "control": 1}, budget=300, checkpoints=(150, 300), verbose=False)
    rows = [json.loads(line) for line in open(out)]
    assert len(rows) == 4 and all("certified" in r for r in rows if r["problem"] == "Barrier1")
    bench.report(str(out), str(tmp_path / "nbors.json"), str(tmp_path / "report.md"))
    assert "escape the barrier" in (tmp_path / "report.md").read_text()
