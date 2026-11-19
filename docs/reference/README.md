# docs/reference: original 2018 files, kept as provenance

These are files from the original 2018 work behind the dissertation's
Test Problem C results. They are kept so that what PyMOSO ships can be
checked against what the dissertation computed. Nothing in the package or
the test suite loads them, and neither the sdist nor the wheel includes them.

| file | what it is | SHA-256 |
|---|---|---|
| `lescombos.pkl` | 516 N_1-local weakly efficient sets of ProbTPC, as a `set` of `frozenset`s of integer 3-tuples (73 distinct points, 4,273 instances) | `cf491fc8e9a589ebd2c43f6628160eb9732d8aa4411e753c1f1d39651107ba9b` |
| `exples.pkl` | their images under the 2018 deterministic oracle, as a `list` of 516 `set`s of float pairs (66 distinct sets, 43 distinct images) | `483e8d98e89033bfd0e55df021085cf665b84a938a9466dc27617bd5798aec21` |

Check a copy with `sha256sum docs/reference/*.pkl`.

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
