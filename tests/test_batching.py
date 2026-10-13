"""
Batching across hit() calls: Oracle.hit_many and RASolver.estimate_many
(docs/simpar-ceiling.md).

The claim under test is that batching changes nothing but when
replications run. Every result, every solver's stored estimates and
simulation count, and the end seed are what the one-point-at-a-time
loops give. The goldens say the same for the scenarios they cover;
these tests say it for every solver, both CRN settings, and the case
that needs care -- points that come back infeasible and are asked for
again.
"""
import pytest

from pymoso import executor as executor_module
from pymoso.chnbase import RASolver
from pymoso.chnutils import get_solv_prnstreams, isp_run, solve
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpb import ProbTPB
from pymoso.problems.probtpc import ProbTPC
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

import _executor_problems as problems

pytestmark = pytest.mark.timeout(120)

ALL = [("mrg32k3a", mrg32k3a), ("mrg31k3p", mrg31k3p), ("philox4x32", philox4x32)]
generators = pytest.mark.parametrize("name,backend", ALL, ids=[n for n, _ in ALL])


def one_at_a_time(self, points):
    """estimate_many without batching: the loop it replaced."""
    return [self.estimate(x) for x in points]


def _oracle(problem, backend, crn):
    orc = problem(backend.stream_at(backend.DEFAULT_SEED, 1, 0))
    orc.set_crnflag(crn)
    orc.set_simpar(1)
    return orc


# ---------------------------------------------------------------------------
# Oracle.hit_many
# ---------------------------------------------------------------------------

REQUESTS = [((40, 40), 4), ((41, 40), 1), ((40, 40), 3), ((99, 99), 2), ((0, 50), 5), ((40, 40), 2)]


@generators
@pytest.mark.parametrize("crn", [False, True])
def test_hit_many_is_the_hits_one_by_one(name, backend, crn):
    """Including a point asked for three times and an infeasible one."""
    one = _oracle(ProbTPA, backend, crn)
    expected = [one.hit(x, m) for x, m in REQUESTS]
    many = _oracle(ProbTPA, backend, crn)
    assert many.hit_many(REQUESTS) == expected
    assert many.get_endseed() == one.get_endseed()
    assert many.get_high_water_mark() == one.get_high_water_mark()
    # and they leave the oracle in the same place for what comes next
    assert many.hit((40, 40), 2) == one.hit((40, 40), 2)
    assert many.hit_many([]) == []


def test_hit_many_hands_the_executor_every_block_in_one_call(monkeypatch):
    seen = []
    real_run = executor_module.SerialExecutor.run
    monkeypatch.setattr(executor_module.SerialExecutor, "run",
                        lambda self, blocks: (seen.append([(b.x, b.count) for b in blocks]), real_run(self, blocks))[1])
    _oracle(ProbTPA, mrg32k3a, False).hit_many(REQUESTS)
    assert seen == [REQUESTS]


# ---------------------------------------------------------------------------
# RASolver.estimate_many
# ---------------------------------------------------------------------------

def _solver(problem, backend, crn, m=3):
    orc = _oracle(problem, backend, crn)
    solver = RASolver(orc, sprn=None, x0=(5, 5))
    solver.m = m
    solver.gbar = {}
    solver.sehat = {}
    return solver


def _state(solver):
    return (solver.gbar, solver.sehat, solver.num_calls, solver.orc.get_endseed())


@generators
@pytest.mark.parametrize("crn", [False, True])
def test_estimate_many_is_estimate_in_a_loop_including_repeated_infeasible_points(name, backend, crn):
    """SometimesInfeasible makes a point's feasibility differ between
    its first block of replications and its next, so a point listed
    several times is simulated once, twice or three times depending on
    what came back -- the rounds in estimate_many's docstring."""
    points = [(i % 4, i % 3) for i in range(30)] + [(1, 1)] * 6
    loop = _solver(problems.SometimesInfeasible, backend, crn)
    expected = [loop.estimate(x) for x in points]
    if not crn:     # under CRN every point sees the same streams, so the same feasibility
        assert any(not isfeas for isfeas, _, _ in expected) and any(isfeas for isfeas, _, _ in expected)
    batched = _solver(problems.SometimesInfeasible, backend, crn)
    assert batched.estimate_many(points) == expected
    assert _state(batched) == _state(loop)
    # a second pass finds the feasible ones stored and re-simulates the rest
    assert batched.estimate_many(points) == [loop.estimate(x) for x in points]
    assert _state(batched) == _state(loop)


def test_estimate_many_reports_a_failing_simulation_the_way_estimate_does():
    solver = _solver(problems.RaisesAtThirteen, mrg32k3a, False)
    with pytest.raises(RuntimeError, match=r"Unable to simulate RaisesAtThirteen. Message: boom at \(13,\)"):
        solver.estimate_many([(1,), (13,), (2,)])
    with pytest.raises(RuntimeError, match=r"Unable to simulate RaisesAtThirteen. Message: boom at \(13,\)"):
        solver.estimate((13,))


# ---------------------------------------------------------------------------
# Whole runs: batching changes no result
# ---------------------------------------------------------------------------

RUNS = [
    (ProbTPA, RPERLE, (40, 40), 1500),
    (ProbTPA, RPERLE, (0, 50), 800),          # a corner: neighbours outside the domain, asked for repeatedly
    (ProbTPA, RMINRLE, (50, 50), 800),
    (ProbTPA, RPE, (40, 40), 800),
    (ProbTPB, RPERLE, (50, 50), 800),
    (ProbTPC, RPERLE, (5, 5, 5), 800),
    (ProbSimpleSO, RSPLINE, (97,), 600),
]


def _run(problem, solver, x0, budget, crn, generator, simpar=1):
    backend = {n: b for n, b in ALL}[generator]
    orcstream, solvstream = get_solv_prnstreams(backend.DEFAULT_SEED, backend)
    orc = problem(orcstream)
    orc.set_crnflag(crn)
    with orc.set_simpar(simpar):
        res = isp_run(solver, budget, orc, sprn=solvstream, x0=x0)
    return res


@pytest.mark.parametrize("problem,solver,x0,budget", RUNS, ids=["{0}-{1}-{2}".format(p.__name__, s.__name__, x) for p, s, x, _ in RUNS])
@pytest.mark.parametrize("crn", [False, True])
def test_a_run_is_identical_with_and_without_batching(problem, solver, x0, budget, crn, monkeypatch):
    """Every iteration's solution, the simulation count after every
    iteration, the end seed and the oracle's high-water mark."""
    batched = _run(problem, solver, x0, budget, crn, "mrg32k3a")
    monkeypatch.setattr(RASolver, "estimate_many", one_at_a_time)
    assert _run(problem, solver, x0, budget, crn, "mrg32k3a") == batched


@pytest.mark.parametrize("generator", ["mrg31k3p", "philox4x32"])
def test_a_run_is_identical_with_and_without_batching_on_the_other_generators(generator, monkeypatch):
    batched = _run(ProbTPA, RPERLE, (0, 50), 800, False, generator)
    monkeypatch.setattr(RASolver, "estimate_many", one_at_a_time)
    assert _run(ProbTPA, RPERLE, (0, 50), 800, False, generator) == batched


@pytest.mark.parametrize("crn", [False, True])
def test_a_batched_run_on_workers_is_the_serial_run(crn):
    serial = _run(ProbTPA, RPERLE, (0, 50), 600, crn, "mrg32k3a")
    assert _run(ProbTPA, RPERLE, (0, 50), 600, crn, "mrg32k3a", simpar=3) == serial


def test_a_bi_objective_solver_really_does_submit_several_points_at_once(monkeypatch):
    """Otherwise everything above passes vacuously."""
    sizes = []
    real_run = executor_module.SerialExecutor.run
    monkeypatch.setattr(executor_module.SerialExecutor, "run",
                        lambda self, blocks: (sizes.append(len(blocks)), real_run(self, blocks))[1])
    _run(ProbTPA, RPERLE, (40, 40), 1500, False, "mrg32k3a")
    assert max(sizes) >= 4 and sum(1 for n in sizes if n > 1) >= 10


def test_a_one_dimensional_problem_never_has_two_points_to_submit(monkeypatch):
    """Why the original --simpar benchmark cannot observe batching
    (docs/simpar-ceiling.md): R-SPLINE on a one-dimensional problem
    estimates one new point at a time, always."""
    sizes = []
    real_run = executor_module.SerialExecutor.run
    monkeypatch.setattr(executor_module.SerialExecutor, "run",
                        lambda self, blocks: (sizes.append(len(blocks)), real_run(self, blocks))[1])
    _run(ProbSimpleSO, RSPLINE, (97,), 2000, False, "mrg32k3a")
    assert sizes and set(sizes) == {1}
