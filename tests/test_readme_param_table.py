"""
The README's "Table of Algorithm-Specific Parameters" is generated,
and checked against the solvers.

Which parameters exist, and which built-in solvers take each, come
from the solvers' own PARAMS declarations (chnbase.accepted_params).
Defaults and descriptions come from tests/_solver_param_docs.py, which
this file holds to the code in two ways that need no knowledge of a
solver's attribute names:

- the documented parameters are exactly the declared ones;
- for every solver taking a parameter, constructing it with the
  documented default passed explicitly gives the same object state as
  leaving the parameter out, and a parameter documented as required
  is refused when left out.

To regenerate the README block after changing a solver or the docs
file, print build_table() and paste it over the old table.
"""
import difflib
import inspect

import pytest

from pymoso import solvers
from pymoso.chnbase import accepted_params
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA

from _solver_param_docs import PARAM_DOCS, REQUIRED

SOLVERS = [cls for _, cls in inspect.getmembers(solvers, inspect.isclass)]    # listitems' order
HEADER = (
    "| Parameter Name | Default Value | Affected Solvers | Description |\n"
    "| -------------- | ------------- | ---------------- | ----------- |"
)
README = open("README.md", encoding="utf-8").read()


def _declared():
    return {name: [cls for cls in SOLVERS if name in accepted_params(cls)]
            for name in {p for cls in SOLVERS for p in accepted_params(cls)}}


def build_table():
    declared = _declared()
    rows = [HEADER]
    for name, (default, description) in PARAM_DOCS.items():
        shown = "*(required)*" if default is REQUIRED else "`{0!r}`".format(default)
        takers = ", ".join("`{0}`".format(cls.__name__) for cls in declared[name])
        rows.append("| `{0}` | {1} | {2} | {3} |".format(name, shown, takers, description))
    return "\n".join(rows)


def _construct(cls, **params):
    """A solver of `cls` on a fresh oracle and solver stream, with the
    required parameters the docs file names supplied unless given."""
    orc = ProbTPA(mrg32k3a.MRG32k3a((12345,) * 6))
    orc.set_crnflag(False)
    for name, (default, _) in PARAM_DOCS.items():
        if default is REQUIRED and name in accepted_params(cls):
            params.setdefault(name, {'lb': 0, 'ub': 50}[name])
    return cls(orc, sprn=mrg32k3a.MRG32k3a((1, 2, 3, 4, 5, 6)), x0=(40, 40), **params)


def _state(solver):
    return {k: v for k, v in vars(solver).items() if k not in ("orc", "sprn")}


def test_the_documented_parameters_are_exactly_the_declared_ones():
    assert set(PARAM_DOCS) == set(_declared())


@pytest.mark.parametrize("name", sorted(PARAM_DOCS))
def test_each_default_is_the_one_every_solver_taking_it_uses(name):
    default = PARAM_DOCS[name][0]
    for cls in _declared()[name]:
        if default is REQUIRED:
            params = {n: v for n, v in {'lb': 0, 'ub': 50}.items() if n != name and n in accepted_params(cls)}
            orc = ProbTPA(mrg32k3a.MRG32k3a((12345,) * 6))
            orc.set_crnflag(False)
            with pytest.raises((TypeError, KeyError, ValueError)):
                cls(orc, sprn=mrg32k3a.MRG32k3a((1, 2, 3, 4, 5, 6)), x0=(40, 40), **params)
        else:
            assert _state(_construct(cls, **{name: default})) == _state(_construct(cls)), (cls.__name__, name)


def test_a_wrong_documented_default_is_caught():
    """The check above, shown detecting: radius 2 is not the default."""
    assert _state(_construct(solvers.RPERLE, radius=2)) != _state(_construct(solvers.RPERLE))


def test_readme_parameter_table_matches_generated():
    start = README.index(HEADER.split("\n")[0])
    end = README.index("\n\n", start)
    actual, expected = README[start:end], build_table()
    assert actual == expected, "\n".join(difflib.unified_diff(
        expected.splitlines(), actual.splitlines(), "generated", "README", lineterm=""))
