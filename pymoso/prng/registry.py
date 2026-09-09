"""
§12 step 6b: the generator registry. Maps each backend's canonical
name (§3.8) to its module, so `--generator`/the matching `solve()`/
`testsolve()` kwarg select generically over whatever is registered --
not hardcoded to one generator, so onboarding a fourth backend later
needs no second pass through cli.py/chnutils.py.

Registry-only, no user-supplied generator path (the way problems/
solvers load a user's own .py file): a generator isn't decoupled
enough from Oracle's own internals for a third-party module to safely
drop in. `Oracle`'s CRN branch alone assumes a small, closed set of
backend shapes (`get_next_prnstream`/`jump_substream`, §12
step 6c-completion's own reclassification of that debt), and
`_hit_via_coordinate` depends on `Stream.advance`/`raw_consumed`
existing at all -- neither is part of the historical, permissive
"an rng-shaped object" contract (§3.6) a custom problem/solver's own
`g(x, rng)` gets to rely on. A user module could satisfy §3.2's
Stream protocol and still silently break here.
"""
from . import mrg32k3a, mrg31k3p, philox4x32

GENERATORS = {
    'mrg32k3a': mrg32k3a,
    'mrg31k3p': mrg31k3p,
    'philox4x32': philox4x32,
}

DEFAULT_GENERATOR = 'mrg32k3a'

# Reverse of GENERATORS -- module -> canonical name, for error messages
# that need to name a backend a caller only has the module object for
# (e.g. Oracle.set_crnflag()/self._backend).
GENERATOR_NAMES = {module: name for name, module in GENERATORS.items()}

# Generators whose Oracle-internal CRN mechanism (get_next_prnstream/
# jump_substream) actually exists. MRG32k3a/MRG31k3p share it (both
# random.Random subclasses with the same jump-ahead shape); Philox has
# no jump-ahead and no such functions at all -- structurally, not just
# incidentally, unable to back the CRN branch as it stands today. `--crn`
# combined with a generator outside this set raises, at generator-
# selection time, rather than reaching a coordinate-shaped AttributeError
# deep in chnbase.py. See docs/rng-interface-design.md §12's CRN
# convergence step (scoped out of 6b, not forgotten) for what would
# actually close this gap.
CRN_CAPABLE = {'mrg32k3a', 'mrg31k3p'}


# §12 step 6b: reverse lookup, Stream class -> owning generator module.
# Oracle.set_crnflag() resolves its own backend from type(self.rng) via
# this, rather than requiring solve()/testsolve()'s own generator
# selection to also reach into Oracle's constructor -- Oracle.__init__
# stays exactly `def __init__(self, rng)`, unchanged, so every existing
# custom Oracle subclass (which typically just forwards to
# super().__init__(rng)) keeps working without touching its own
# signature. A `random.Random()` instance used only to read `.dim`
# (commands/solve.py's/testsolve.py's own throwaway-Oracle pattern)
# never calls set_crnflag(), so this lookup never runs for it.
STREAM_CLASS_TO_GENERATOR = {
    mrg32k3a.MRG32k3a: mrg32k3a,
    mrg31k3p.MRG31k3p: mrg31k3p,
    philox4x32.Philox4x32Stream: philox4x32,
}


def backend_for_stream(stream):
    """
    Look up which registered generator module owns `stream`'s class.

    Parameters
    ----------
    stream : Stream instance

    Returns
    -------
    module

    Raises
    ------
    KeyError
        `stream` isn't an instance of one of the three registered
        generators' own Stream classes (or a subclass of one -- e.g.
        tests/test_rng_consumption.py's own RecordingMRG32k3a, an
        instrumentation subclass monkeypatched in as the live rng
        class, resolves to mrg32k3a via isinstance) -- a custom Oracle
        built over a genuinely unrelated, arbitrary rng-shaped object
        (§3.6's own permissive "an rng-shaped object" posture for
        g()'s own rng argument) was already not supported for
        coordinate-based non-CRN solving before this step
        (_hit_via_coordinate was already hardcoded to MRG32k3a
        specifically); this makes that pre-existing limitation fail
        with a named cause instead of silently, not a new restriction.
    """
    for cls, module in STREAM_CLASS_TO_GENERATOR.items():
        if isinstance(stream, cls):
            return module
    raise KeyError(
        '{0!r} is not an instance of any registered generator\'s own '
        'Stream class ({1}) -- Oracle can only resolve its own '
        'backend from a registered generator\'s own class. See '
        'docs/rng-interface-design.md §12 step 6b.'.format(
            type(stream), ', '.join(c.__name__ for c in STREAM_CLASS_TO_GENERATOR)
        )
    )


def get_generator(name):
    """
    Look up a registered generator backend by its canonical name (§3.8).

    Parameters
    ----------
    name : str

    Returns
    -------
    module

    Raises
    ------
    KeyError
        `name` is not a registered generator. Argparse's own `choices=`
        (cli.py) makes this unreachable from the CLI; kept as a real
        check here for the library path (`solve()`/`testsolve()`'s own
        `generator=` kwarg), where nothing else validates it.
    """
    try:
        return GENERATORS[name]
    except KeyError:
        raise KeyError(
            '{0!r} is not a registered generator. Registered generators: '
            '{1}.'.format(name, ', '.join(sorted(GENERATORS)))
        )
