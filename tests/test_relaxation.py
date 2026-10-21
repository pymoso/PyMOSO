"""
The relaxation R-PERLE, R-PE and R-MinRLE use, against the preprint's
definition (Cooper, Hunter and Nagaraj, Optimization Online
2018/06/6649, section 3.2): f(x, beta) = se * n**(1/2 - beta), where se
is the standard error sigma/sqrt(n). So beta = 1/2, the default, is one
standard error. Until 2.0 the code computed se / m**beta, which is
smaller by sqrt(m) at every beta (docs/algorithm-audit.md, finding 2).
"""
from types import SimpleNamespace

import pytest

from pymoso.chnbase import RLESolver
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE

RELAXATIONS = (
    ('RPERLE.fse', RPERLE.fse, 'betaeps'),
    ('RPE.fse', RPE.fse, 'betaeps'),
    ('RLESolver.calc_delta', RLESolver.calc_delta, 'betadel'),
)


@pytest.mark.parametrize('name, relax, param', RELAXATIONS, ids=[r[0] for r in RELAXATIONS])
def test_default_beta_is_one_standard_error(name, relax, param):
    solver = SimpleNamespace(m=100, **{param: 0.5})
    assert relax(solver, 0.3) == 0.3


@pytest.mark.parametrize('name, relax, param', RELAXATIONS, ids=[r[0] for r in RELAXATIONS])
@pytest.mark.parametrize('beta', (0.1, 0.3, 1.0, 1.5))
def test_relaxation_is_the_preprints(name, relax, param, beta):
    solver = SimpleNamespace(m=100, **{param: beta})
    assert relax(solver, 0.3) == pytest.approx(0.3 * 100 ** (0.5 - beta), rel=1e-12)


@pytest.mark.parametrize('name, relax, param', RELAXATIONS, ids=[r[0] for r in RELAXATIONS])
def test_infinite_beta_is_no_relaxation(name, relax, param):
    # the preprint's f(x, inf) := 0, a sample-path local efficient set
    solver = SimpleNamespace(m=100, **{param: float('inf')})
    assert relax(solver, 0.3) == 0.0
