"""Problems for tests/test_replication_draws.py, in a module of their own
so that worker processes can import them."""
from pymoso.oracle import Oracle


class Draws(Oracle):
    """One objective, the mean of the `draws` uniform values each
    replication makes, so that two replications drawing the same values
    give the same observation. The default reserve."""
    draws = 16

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        return True, (sum(rng.random() for _ in range(self.draws)) / self.draws,)


class WideDraws(Draws):
    """A reserve of 2**16 draws, and a g() that uses all of them."""
    replication_draws = 1 << 16
    draws = 1 << 16


class WideReserve(Draws):
    """A reserve of 2**16 draws that g() mostly leaves unused: the
    spacing without the cost of drawing it all."""
    replication_draws = 1 << 16


class WideDrawsOneTooMany(WideDraws):
    draws = (1 << 16) + 1


class SmallDraws(Draws):
    """A reserve of 2**4 draws: smaller than the default, which is
    allowed, and leaves the point code ten more bits."""
    replication_draws = 1 << 4
