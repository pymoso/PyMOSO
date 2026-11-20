# docs/reference: original 2018 files, kept as provenance

These are data files from the original 2018 work behind the
dissertation's results: Test Problem C's reference sets, and the seed
pools the experiments drew their streams from. They are kept so that what PyMOSO ships can be
checked against what the dissertation computed. Nothing in the package or
the test suite loads them, and neither the sdist nor the wheel includes them.

| file | what it is | SHA-256 |
|---|---|---|
| `lescombos.pkl` | 516 N_1-local weakly efficient sets of ProbTPC, as a `set` of `frozenset`s of integer 3-tuples (73 distinct points, 4,273 instances) | `cf491fc8e9a589ebd2c43f6628160eb9732d8aa4411e753c1f1d39651107ba9b` |
| `exples.pkl` | their images under the 2018 deterministic oracle, as a `list` of 516 `set`s of float pairs (66 distinct sets, 43 distinct images) | `483e8d98e89033bfd0e55df021085cf665b84a938a9466dc27617bd5798aec21` |
| `orcseeds.pkl` | the 2018 driver's oracle seed pool: a `dict` keyed 0 to 4,999 of MRG32k3a states (6-tuples of integers) | `c2237435b7835eda7ff8256694c2b4a9628d2bdb477913f8fc59423459552c14` |
| `solseeds.pkl` | the solver seed pool, the same form | `a3c1ff18ea425b87d6b1d49733a17818632679f6324f845250f4c154a2c54f0e` |
| `orcseeds.txt` | `orcseeds.pkl` as plain text, no pickle | `e4eb7638295f8bf14f6cf75dd78e385689a04341fd794b0a16c6b5afd48cc390` |
| `solseeds.txt` | `solseeds.pkl` as plain text, no pickle | `e211e5083d14950e42e771b6859bb28b84525fecc3df7db5f0a2ffbfb171de8f` |

Check a copy with `sha256sum docs/reference/*`.

## The seed pools

The 2018 driver (`mpmain.py`) gave run j of every scenario
`orcseeds[j]` for its oracle and `solseeds[j]` for its solver.
Measured (`docs/reconstruction-spec.md`, section 1):
- **10,000 states in all.** All are valid MRG32k3a states and all are
  distinct. The two files share none, and they name no pickle globals.
- **The state convention is reversed:** each component's triple is
  stored oldest first, (x_{n-3}, x_{n-2}, x_{n-1}).
- **They are one chain.** Consecutive seeds are A^(2^77) apart, with A
  MRG32k3a's one-step matrix in that convention. `orcseeds[4999]` one
  jump on is `solseeds[0]`: the oracle block first, the solver block
  second.
- **2^77 is two of L'Ecuyer's substream spacings** and neither of his
  canonical constants.

**The `.txt` files** hold the same states with no pickle at all.
- Format: comment lines beginning `#`, then one line per seed: the key,
  then six integers, the first component's triple then the second's.
- Each was written from its pickle and parsed back with plain string
  handling. The result equalled the pickle's contents, key for key,
  before they were committed (2026-11-19).
- Read these rather than the pickles.

## The live artifact is the Python literal, not the pickle

`pymoso/testers/tpctester.py`'s `soln` is the contents of `lescombos.pkl`,
converted once on 2026-11-18. It was converted with an unpickler that
admits only `builtins.set` and `builtins.frozenset`, the only globals the
file names (checked first with `pickletools`, which reads a pickle without
running it). The literal was then parsed back and checked equal to the
pickle's contents. The tester reads the literal; edit that, not the pickle.

The account of what the two files show is in
[tpc-reference-sets.md](tpc-reference-sets.md).

## Do not unpickle untrusted data

Loading a pickle can run arbitrary code: `pickle.load` calls whatever
callables the file names. Do not `pickle.load` either file, or any
replacement for them, unless you have checked it. To inspect one, use
`python -m pickletools <file>`, which lists the opcodes and the globals
the file names without executing anything. To load one, use an unpickler
whose `find_class` refuses everything except the plain types you expect:

```python
import pickle

class OnlySets(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in (('builtins', 'set'), ('builtins', 'frozenset')):
            return {'set': set, 'frozenset': frozenset}[name]
        raise pickle.UnpicklingError(f'refused {module}.{name}')

with open('docs/reference/lescombos.pkl', 'rb') as f:
    sets = OnlySets(f).load()
```
