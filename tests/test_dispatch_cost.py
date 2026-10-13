"""
dispatch_cost: what one request for replications costs in place and
on a backend, measured because the user asked.

It replaces nothing automatic. A backend once timed what it carried
and warned when dispatch looked like a loss; that measured the wrong
thing and was removed, and the repair that would have run the user's
work unasked was declined. This function is the same question put the
right way round: the user calls it, says which request to measure,
and gets numbers and no opinion.

Timings are never asserted here, only that they are present and
positive.
"""
import math
import statistics
import warnings

import pytest

import pymoso
from pymoso.backends.measure import DispatchCost, dispatch_cost
from pymoso.pool import LocalBackend
from pymoso.problems.probtpa import ProbTPA
from test_remote_backend import FreshInterpreterBackend

pytestmark = pytest.mark.timeout(180)


@pytest.fixture
def elsewhere(tmp_path):
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    return directory


def test_it_reports_one_request_in_place_and_on_the_backend():
    cost = dispatch_cost(ProbTPA, (30, 30), replications=12, parts=3, backend=LocalBackend(), jobs=4)
    assert isinstance(cost, DispatchCost)
    assert (cost.replications, cost.parts, cost.x, cost.backend) == (12, 3, (30, 30), "LocalBackend")
    assert cost.in_place_seconds > 0 and cost.first_job_seconds > 0
    assert len(cost.job_seconds) == 4 and all(seconds > 0 for seconds in cost.job_seconds)
    assert cost.identical is True
    assert math.isclose(cost.per_replication_seconds, cost.in_place_seconds / 12)
    assert cost.median_job_seconds == statistics.median(cost.job_seconds)
    assert math.isclose(cost.ratio, cost.in_place_seconds / cost.median_job_seconds)


def test_it_makes_exactly_the_dispatches_it_says_on_a_remote_backend(elsewhere):
    backend = FreshInterpreterBackend(elsewhere)
    cost = dispatch_cost(ProbTPA, [30, 30], replications=6, parts=2, backend=backend, jobs=2)
    assert backend.jobs == 3                                # the first, reported apart, and the two asked for
    assert cost.identical is True and cost.backend == "FreshInterpreterBackend" and cost.x == (30, 30)


@pytest.mark.parametrize("generator", ["mrg32k3a", "mrg31k3p", "philox4x32"])
def test_every_generator(generator):
    cost = dispatch_cost(ProbTPA, (30, 30), replications=4, parts=2, backend=LocalBackend(), jobs=1, generator=generator)
    assert cost.identical is True


def test_the_request_to_measure_is_the_callers_to_state():
    """No default for the size of the request, the number of tasks or
    the backend: each is a guess about someone else's solver and
    cluster."""
    for missing in ("replications", "parts", "backend"):
        kwargs = dict(replications=4, parts=2, backend=LocalBackend())
        del kwargs[missing]
        with pytest.raises(TypeError, match=missing):
            dispatch_cost(ProbTPA, (30, 30), **kwargs)
    with pytest.raises(TypeError):
        dispatch_cost(ProbTPA, (30, 30), 4, 2, LocalBackend())      # keyword-only
    for bad in (dict(replications=0), dict(parts=0), dict(jobs=0)):
        kwargs = dict(replications=4, parts=2, backend=LocalBackend())
        kwargs.update(bad)
        with pytest.raises(ValueError):
            dispatch_cost(ProbTPA, (30, 30), **kwargs)


def test_it_reports_and_does_not_advise():
    cost = dispatch_cost(ProbTPA, (30, 30), replications=6, parts=2, backend=LocalBackend(), jobs=2)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        text = str(cost)
    lines = text.splitlines()
    assert len(lines) == 4
    assert "6 replications" in lines[0] and "in place" in lines[1] and "2 tasks" in lines[2] and "identical" in lines[3]
    lowered = text.lower()
    for verdict in ("should", "recommend", "worth", "faster", "slower", "better", "worse", "use ", "avoid", "pays", "loses"):
        assert verdict not in lowered, verdict
    assert not hasattr(cost, "verdict") and not hasattr(cost, "advice")


def test_an_infeasible_point_is_measured_like_any_other():
    cost = dispatch_cost(ProbTPA, (10 ** 6, 10 ** 6), replications=4, parts=2, backend=LocalBackend(), jobs=1)
    assert cost.identical is True


def test_it_is_importable_from_the_top_level_without_importing_the_backends_first():
    assert pymoso.dispatch_cost is dispatch_cost
    from pymoso import dispatch_cost as from_top
    assert from_top is dispatch_cost
    with pytest.raises(AttributeError):
        pymoso.no_such_name
