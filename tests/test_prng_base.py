"""
pymoso/prng/base.py: the Stream protocol (§3.2) and the
RandomCompatAdapter backward-compatibility adapter (§3.6). Neither is
wired into MRG32k3a or chnbase.py yet (docs/rng-interface-design.md §12
step 2 groups this module with mrg_common.py's generalized jump, not
with any consumer) -- these tests check the new module on its own
terms: the protocol matches structurally, and the adapter actually
delegates rather than reimplementing anything.

Warning for anyone writing another Stream double against this interface,
found while writing this file's own: a getrandbits(k) that ignores k and
returns a fixed value can hang, not fail loudly. random.Random's
_randbelow_with_getrandbits (behind choice()/sample()/shuffle() once a
class defines getrandbits, as RandomCompatAdapter and MRG32k3a both do)
rejection-samples -- it keeps redrawing while the result is >= the
caller's n, discarding and asking again. FakeStream below originally
returned a fixed 7 regardless of k; that is a valid getrandbits(k) value
for k >= 3, but adapter.choice() on a 3-element sequence asks for
getrandbits(2) (range [0, 4)), 7 is never < 3, and the loop never
terminates -- no assertion, no traceback, just a hang, caught only
because test_adapter_provides_the_full_random_random_surface_for_free
below timed out rather than passed or failed cleanly. Fixed by making
the fake return 0, which is valid for every k >= 1, not by special-
casing k in the fake.
"""
from pymoso.prng.base import Stream, RandomCompatAdapter
from pymoso.prng.mrg32k3a import MRG32k3a


class FakeStream:
    """A minimal, deterministic Stream double -- canned return values,
    and records every call it receives so delegation can be checked
    precisely (which method, with what arguments), not just "didn't
    crash."""

    def __init__(self):
        self.calls = []

    def random(self):
        self.calls.append(("random", ()))
        return 0.25

    def getrandbits(self, k):
        self.calls.append(("getrandbits", (k,)))
        # Always 0, deliberately, not an arbitrary fixed constant: 0 is
        # a valid draw from [0, 2**k) for every k >= 1, so it can't ever
        # trip random.Random's own rejection-sampling loop in
        # _randbelow_with_getrandbits (choice()/sample() keep redrawing
        # while r >= n; a fixed constant that happens to be >= whatever
        # n a caller uses -- 7 was tried first here and hung exactly
        # this way under choice() on a 3-element sequence) -- the
        # boundary case test_adapter_provides_the_full_random_random_
        # surface_for_free below exists to catch.
        return 0

    def normalvariate(self, mu=0, sigma=1):
        self.calls.append(("normalvariate", (mu, sigma)))
        return 1.5


class MissingNormalvariate:
    """Structurally incomplete: has random/getrandbits but not
    normalvariate -- the negative case for the isinstance check below."""

    def random(self):
        return 0.5

    def getrandbits(self, k):
        return 0


def test_fake_stream_satisfies_the_protocol_structurally():
    assert isinstance(FakeStream(), Stream)


def test_incomplete_stream_does_not_satisfy_the_protocol():
    assert not isinstance(MissingNormalvariate(), Stream)


def test_mrg32k3a_already_satisfies_the_stream_protocol():
    """MRG32k3a already implements random/getrandbits/normalvariate
    (it always has, for other reasons) -- confirms the protocol
    describes MRG32k3a's real, existing surface, not a hypothetical
    future one, even before anything wires it through Stream/
    RandomCompatAdapter."""
    rng = MRG32k3a((12345,) * 6)
    assert isinstance(rng, Stream)


def test_adapter_delegates_random_to_the_composed_stream():
    stream = FakeStream()
    adapter = RandomCompatAdapter(stream)
    assert adapter.random() == 0.25
    assert stream.calls == [("random", ())]


def test_adapter_delegates_getrandbits_with_its_argument():
    stream = FakeStream()
    adapter = RandomCompatAdapter(stream)
    assert adapter.getrandbits(16) == 0
    assert stream.calls == [("getrandbits", (16,))]


def test_adapter_delegates_normalvariate_with_its_arguments():
    stream = FakeStream()
    adapter = RandomCompatAdapter(stream)
    assert adapter.normalvariate(mu=2, sigma=3) == 1.5
    assert stream.calls == [("normalvariate", (2, 3))]


def test_adapter_provides_the_full_random_random_surface_for_free():
    """§3.6's actual claim: overriding random()/getrandbits() makes the
    *entire* random.Random API correctly backed by the composed stream
    -- choice() here, routed through _randbelow -> getrandbits(),
    confirmed by checking the fake stream's own call log, not just that
    choice() returned a value from the sequence (which stdlib's
    machinery would also do if it silently fell back to unrelated
    entropy)."""
    stream = FakeStream()
    adapter = RandomCompatAdapter(stream)
    result = adapter.choice(["a", "b", "c"])
    assert result in ("a", "b", "c")
    assert any(name == "getrandbits" for name, _args in stream.calls)
