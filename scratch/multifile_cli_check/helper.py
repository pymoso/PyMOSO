PENALTY = 3.0

def noisy_quadratic(x0, rng):
    z = rng.normalvariate(0, 1)
    return x0**2 + PENALTY*z
