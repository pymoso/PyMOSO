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

from pymoso.chnbase import RLESolver, accepted_params
from pymoso.solvers.rminrle import RMINRLE
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


# At beta <= 0 the relaxation does not shrink as m grows (se is of order
# m**-1/2, so se * m**(1/2 - beta) is of order m**-beta), and it grows
# with m below 0. The value is used, with a warning, once per solver.

def _construct(cls, **kwargs):
    from pymoso.prng import mrg32k3a
    from pymoso.problems.probtpa import ProbTPA
    orc = ProbTPA(mrg32k3a.stream_at(mrg32k3a.DEFAULT_SEED, 1, 0))
    return cls(orc, sprn=None, x0=(5, 5), **kwargs)


def _beta_warnings(record):
    return [w for w in record if 'convergence guarantee' in str(w.message)]


@pytest.mark.parametrize('cls, param', (
    (RPERLE, 'betaeps'), (RPE, 'betaeps'), (RPERLE, 'betadel'), (RMINRLE, 'betadel')))
@pytest.mark.parametrize('beta', (0.0, -0.5))
def test_beta_at_or_below_zero_warns_and_is_used(cls, param, beta):
    with pytest.warns(UserWarning) as record:
        solver = _construct(cls, **{param: beta})
    found = _beta_warnings(record)
    assert len(found) == 1
    message = str(found[0].message)
    assert message.startswith('{0}={1}:'.format(param, beta))
    assert 'continues with this value' in message
    assert 'grows' in message
    assert getattr(solver, param) == beta


@pytest.mark.parametrize('cls', (RPERLE, RPE, RMINRLE))
@pytest.mark.parametrize('beta', (None, 0.1, 0.5, float('inf')))
def test_beta_above_zero_does_not_warn(cls, beta, recwarn):
    params = ('betaeps', 'betadel') if beta is not None else ()
    _construct(cls, **{p: beta for p in params if p in accepted_params(cls)})
    assert not _beta_warnings(recwarn.list)
