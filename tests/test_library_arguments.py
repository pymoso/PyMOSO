"""
What solve() and testsolve() do with arguments that are wrong.

Found driving the library from a notebook, where there is no CLI in
front of it to parse and check: a misspelt solver parameter was
silently ignored, a list for x0 failed deep inside a solver with a
message about sets, and a parameter that was not a number failed
without saying which one. Each now fails at the call, by name.
"""
import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.mocompass import MOCOMPASS
from pymoso.solvers.mopbnb import MOPBnB
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.testers.tpatester import TPATester

pytestmark = pytest.mark.timeout(120)

SEED = (12345,) * 6


# ---------------------------------------------------------------------------
# Solver parameters that do not exist
# ---------------------------------------------------------------------------

def test_an_unknown_solver_parameter_is_refused_by_name_with_the_ones_that_exist():
    with pytest.raises(TypeError) as refused:
        solve(ProbTPA, RPERLE, (30, 30), budget=100, seed=SEED, betaesp=0.4)      # a typo for betaeps
    message = str(refused.value)
    assert "RPERLE" in message and "betaesp" in message
    for accepted in ("betadel", "betaeps", "bconst", "mconst", "radius"):
        assert accepted in message
    assert "x0" not in message and "sprn" not in message        # supplied by solve(), not by the user


def test_testsolve_refuses_one_too():
    with pytest.raises(Exception, match="nosuchparam"):
        testsolve(TPATester, RPERLE, (30, 30), budget=100, seed=SEED, isp=2, nosuchparam=3)


@pytest.mark.parametrize("solver,problem,x0,accepted", [
    (RPERLE, ProbTPA, (30, 30), {"radius", "mconst", "bconst", "betadel", "betaeps"}),
    (RMINRLE, ProbTPA, (30, 30), {"radius", "mconst", "bconst", "betadel"}),
    (RPE, ProbTPA, (30, 30), {"radius", "mconst", "bconst", "betaeps"}),
    (RSPLINE, ProbSimpleSO, (40,), {"radius", "mconst", "bconst"}),
])
def test_every_parameter_a_solver_lists_is_one_it_takes(solver, problem, x0, accepted):
    """The list in the error is the solver's own declaration; this
    holds the declaration to what the solver really accepts."""
    from pymoso.chnbase import accepted_params
    assert set(accepted_params(solver)) == accepted
    for name in sorted(accepted):
        solve(problem, solver, x0, budget=60, seed=SEED, **{name: 2 if name == "radius" else 0.5 if name.startswith("beta") else 3})


@pytest.mark.parametrize("solver,extra,accepted", [
    (MOCOMPASS, {}, {"numsamples", "ub", "lb"}),
    (MOPBnB, {}, {"subregions", "alpha", "delta", "R0", "ub", "lb"}),
])
def test_the_solvers_that_are_not_ra_solvers_refuse_unknown_parameters_too(solver, extra, accepted):
    from pymoso.chnbase import accepted_params
    assert set(accepted_params(solver)) == accepted
    assert solve(ProbTPA, solver, (30, 30), budget=200, seed=SEED, ub=40, lb=20, **extra)
    with pytest.raises(TypeError, match="nosuchparam"):
        solve(ProbTPA, solver, (30, 30), budget=200, seed=SEED, ub=40, lb=20, nosuchparam=1)


def test_a_custom_solver_declares_its_own_parameters_and_they_are_listed():
    class Tuned(RPERLE):
        PARAMS = ("stubbornness",)

        def __init__(self, orc, **kwargs):
            self.stubbornness = kwargs.pop("stubbornness", 1.0)
            super().__init__(orc, **kwargs)

    solve(ProbTPA, Tuned, (30, 30), budget=100, seed=SEED, stubbornness=2)
    with pytest.raises(TypeError) as refused:
        solve(ProbTPA, Tuned, (30, 30), budget=100, seed=SEED, stuborness=2)
    assert "stubbornness" in str(refused.value) and "stuborness" in str(refused.value)


# ---------------------------------------------------------------------------
# The starting point
# ---------------------------------------------------------------------------

def test_x0_may_be_a_list():
    """It failed inside the solver with "cannot use 'list' as a set
    element". Any sequence of the right length is the same point."""
    expected = solve(ProbTPA, RPERLE, (30, 30), budget=200, seed=SEED)
    assert solve(ProbTPA, RPERLE, [30, 30], budget=200, seed=SEED) == expected
    expected = testsolve(TPATester, RPERLE, (30, 30), budget=100, seed=SEED, isp=2)
    assert testsolve(TPATester, RPERLE, [30, 30], budget=100, seed=SEED, isp=2) == expected


@pytest.mark.parametrize("x0", [(30,), (30, 30, 30), []])
def test_x0_of_the_wrong_dimension_is_refused_at_the_call(x0):
    for call in (
        lambda: solve(ProbTPA, RPERLE, x0, budget=100, seed=SEED),
        lambda: testsolve(TPATester, RPERLE, x0, budget=100, seed=SEED, isp=2),
    ):
        with pytest.raises(ValueError, match=r"x0 must have 2 components") as refused:
            call()
        assert "{0}".format(len(x0)) in str(refused.value)


@pytest.mark.parametrize("x0", [30, None, "30", (30.5, 30), ("30", "30"), (True, 30)])
def test_x0_that_is_not_a_sequence_of_integers_is_refused_at_the_call(x0):
    with pytest.raises(TypeError, match="x0"):
        solve(ProbTPA, RPERLE, x0, budget=100, seed=SEED)


def test_x0_is_not_checked_when_starting_points_are_drawn():
    """With ranx0 every path draws its own; the argument is unused,
    and a CLI user has to pass something."""
    res, _ = testsolve(TPATester, RPERLE, (0,), budget=100, seed=SEED, isp=2, ranx0=True)
    assert len(res) == 2


# ---------------------------------------------------------------------------
# Solver parameters that are not numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [2, 2.0, True])
def test_a_numeric_parameter_reaches_the_solver_as_the_float_it_always_was(value):
    """Every solver parameter has always been passed through float().
    That is unchanged, so no result moves."""
    seen = {}

    class Spy(RPERLE):
        def __init__(self, orc, **kwargs):
            seen.update(kwargs)
            super().__init__(orc, **kwargs)

    solve(ProbTPA, Spy, (30, 30), budget=60, seed=SEED, mconst=value)
    assert seen["mconst"] == float(value) and type(seen["mconst"]) is float
    seen.clear()
    testsolve(TPATester, Spy, (30, 30), budget=60, seed=SEED, isp=1, mconst=value)
    assert seen["mconst"] == float(value) and type(seen["mconst"]) is float


@pytest.mark.parametrize("value", ["x", "2", None, [2], (1, 2)])
def test_a_parameter_that_is_not_a_number_is_refused_by_name(value):
    """It used to be `could not convert string to float: 'x'`, with no
    word of which keyword -- or, for the string "2", to work."""
    for call in (
        lambda: solve(ProbTPA, RPERLE, (30, 30), budget=60, seed=SEED, betaeps=value),
        lambda: testsolve(TPATester, RPERLE, (30, 30), budget=60, seed=SEED, isp=2, betaeps=value),
    ):
        with pytest.raises(TypeError, match="betaeps") as refused:
            call()
        assert "number" in str(refused.value)


# ---------------------------------------------------------------------------
# What to do about a class that cannot be sent to a worker
# ---------------------------------------------------------------------------

def _refusal(cls, monkeypatch):
    import sys
    from pymoso.executor import ClassRef
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    with pytest.raises(ValueError) as refused:
        ClassRef(cls)
    return str(refused.value)


def test_the_advice_for_a_class_with_no_source_leads_with_the_notebook_extra(monkeypatch):
    """The remedy used to end "define it in a .py file", which is the
    wrong advice where the class was defined in a notebook -- most of
    all on a hosted one, where there is no obvious file to put it in.
    The extra comes first; the file is the alternative outside a
    notebook."""
    namespace = {'__name__': 'a_module_that_is_not_in_sys_modules'}
    exec("from pymoso.chnbase import Oracle\nclass Interactive(Oracle):\n    pass\n", namespace)
    message = _refusal(namespace['Interactive'], monkeypatch)
    assert "no locatable source" in message
    assert message.index("pymoso[notebook]") < message.index(".py file")
    assert "Outside a notebook" in message
    assert "Define it in a .py file and try again" not in message


def test_the_advice_for_a_class_defined_inside_a_function_does_too(monkeypatch):
    def make():
        class Local(ProbTPA):
            pass
        return Local

    message = _refusal(make(), monkeypatch)
    assert "cannot be sent to a worker process" in message
    assert message.index("pymoso[notebook]") < message.index(".py file")
    assert "Outside a notebook" in message
