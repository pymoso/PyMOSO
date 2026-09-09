"""
The generator-agnostic pieces of docs/rng-interface-design.md's RNG
interface: the Stream protocol every conforming backend must satisfy
(§3.2), and the backward-compatibility adapter (§3.6) that lets a
Stream be used anywhere a random.Random-shaped object is expected.

Not yet wired into any backend or into chnbase.py/chnutils.py -- this is
scaffolding, built ahead of its first real caller because the step list
(docs/rng-interface-design.md §12 step 2) groups it with mrg_common.py's
generalized jump, not because anything consumes it yet. MRG32k3a keeps
subclassing random.Random directly and unchanged; nothing here changes
its behavior.
"""
import random
from typing import Protocol, runtime_checkable


@runtime_checkable
class Stream(Protocol):
    """The complete required surface a conforming generator backend's
    stream_at(base_seed, coordinate) must return (§3.2). Everything
    else -- expovariate, gauss, uniform, choice, sample, shuffle,
    triangular, ... -- is not part of this contract; it's what
    RandomCompatAdapter below provides for free, the same way CPython's
    random.Random already implements all of it in terms of random()/
    getrandbits()."""

    def random(self) -> float:
        """Uniform on [0, 1)."""
        ...

    def getrandbits(self, k: int) -> int:
        """Uniform on [0, 2**k), unbiased. Rejection sampling is
        permitted here -- see §3.3 for why this one method is exempt
        from the monotonicity requirement normalvariate is not."""
        ...

    def normalvariate(self, mu: float = 0, sigma: float = 1) -> float:
        """A monotone, single-draw transform of one random() draw
        (§3.3) -- required, not incidental: CRN's variance-reduction
        guarantee depends on it."""
        ...


class RandomCompatAdapter(random.Random):
    """Backward-compatibility adapter (§3.6), needed because
    Oracle.g(self, x, rng) hands `rng` directly to arbitrary third-party
    code (custom Oracles, and -- confirmed, not hypothetical, per §3.6 --
    custom MOSOSolvers like MOCOMPASS/MOPBnB) documented only as
    "an rng-shaped object," which today means the *entire* random.Random
    API, not just the four Stream methods.

    Composition at the core: __init__/random/getrandbits/normalvariate
    all delegate to a composed Stream object (`self._stream`), never
    implement the recurrence themselves -- subclassing random.Random
    here is a purely cosmetic, opt-in convenience layer on top of that,
    not the load-bearing mechanism (the Stream/stream_at layer above is,
    and is what the conformance suite in §7 tests). A caller that wants
    the full stdlib distribution surface (gauss, uniform, triangular,
    shuffle, ...) gets it for free, backed by `self._stream`, exactly as
    it does today from MRG32k3a's own random.Random subclassing.

    Not yet used by MRG32k3a itself (see module docstring) -- this class
    exists so the pattern is written down and testable ahead of that
    wiring, not because anything constructs one yet.
    """

    def __init__(self, stream: Stream):
        self._stream = stream
        # random.Random.seed() only accepts None/int/float/str/bytes/
        # bytearray; this call's only purpose is to satisfy that type
        # check; the parent's C-level Mersenne state it seeds is never
        # consulted, since random()/getrandbits()/normalvariate() are
        # fully overridden below -- same reasoning as MRG32k3a.seed()'s
        # own super().seed() call.
        super().__init__(0)

    def random(self) -> float:
        return self._stream.random()

    def getrandbits(self, k: int) -> int:
        return self._stream.getrandbits(k)

    def normalvariate(self, mu: float = 0, sigma: float = 1) -> float:
        return self._stream.normalvariate(mu, sigma)
