# Sibling helper module for the multi-file custom-problem fixture --
# the realistic case for any nontrivial simulation: the objective
# computation is factored out rather than inlined in the Oracle
# subclass. Deliberately draws from rng itself, not just pure
# arithmetic, so it's actually part of the RNG-consumption chain being
# validated, not incidental.
PENALTY = 3.0

def noisy_quadratic(x0, rng):
    z = rng.normalvariate(0, 1)
    return x0**2 + PENALTY*z
