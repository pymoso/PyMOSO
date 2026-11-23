# docs/reference: files from a PyMOSO ancestor, and published targets

These data files came from a PyMOSO ancestor, which was used for
auditing and reverse engineering: Test Problem C's reference sets, and
two seed pools. They are kept so that what PyMOSO ships can be checked
against the dissertation's published appendix. Nothing in the package or
the test suite loads them, and neither the sdist nor the wheel includes
them (`tests/test_reference_files_not_shipped.py`). This file also
records the targets read from the dissertation's published Figure 9.

| file | what it is | SHA-256 |
|---|---|---|
| `lescombos.pkl` | 516 N_1-local weakly efficient sets of ProbTPC, as a `set` of `frozenset`s of integer 3-tuples (73 distinct points, 4,273 instances) | `cf491fc8e9a589ebd2c43f6628160eb9732d8aa4411e753c1f1d39651107ba9b` |
| `exples.pkl` | their images under the ancestor's deterministic oracle, as a `list` of 516 `set`s of float pairs (66 distinct sets, 43 distinct images) | `483e8d98e89033bfd0e55df021085cf665b84a938a9466dc27617bd5798aec21` |
| `orcseeds.pkl` | an oracle seed pool: a `dict` keyed 0 to 4,999 of MRG32k3a states (6-tuples of integers) | `c2237435b7835eda7ff8256694c2b4a9628d2bdb477913f8fc59423459552c14` |
| `solseeds.pkl` | a solver seed pool, the same form | `a3c1ff18ea425b87d6b1d49733a17818632679f6324f845250f4c154a2c54f0e` |
| `orcseeds.txt` | `orcseeds.pkl` as plain text, no pickle | `e4eb7638295f8bf14f6cf75dd78e385689a04341fd794b0a16c6b5afd48cc390` |
| `solseeds.txt` | `solseeds.pkl` as plain text, no pickle | `e211e5083d14950e42e771b6859bb28b84525fecc3df7db5f0a2ffbfb171de8f` |

Check a copy with `sha256sum docs/reference/*`.

## The seed pools

Measured, and re-checkable from the `.txt` forms. The MRG32k3a
recurrence matrices used were written from L'Ecuyer's definition, not
taken from any code base.
- **10,000 states in all.** Each file is a `dict` keyed 0 to 4,999, with
  6-tuples of integers as values. All are valid MRG32k3a states and all
  are distinct. The two files share none, and they name no pickle
  globals.
- **The state convention is reversed:** each component's triple is
  stored oldest first, (x_{n-3}, x_{n-2}, x_{n-1}). Read newest first,
  no A^(2^k) for k from 60 to 130 fits.
- **They are one chain.** Consecutive seeds are A^(2^77) apart, with A
  MRG32k3a's one-step matrix in that convention, the same jump in both
  files. `orcseeds[4999]` one jump on is `solseeds[0]`: the oracle block
  first, the solver block second.
- **2^77 is two of L'Ecuyer's substream spacings** (2^76) and neither of
  his canonical constants (2^76 for a substream, 2^127 for a stream).
  Consecutive seeds are about 1.5 × 10^23 draws apart.

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

What the two T_C files show is in
[tpc-reference-sets.md](tpc-reference-sets.md).

## Targets read from the published Figure 9

The dissertation's Figure 9, Test Problem C's coverage-error quantiles
for MO-COMPASS, R-MinRLE and R-PERLE, read from the drawing commands in
the figure's PDF. Measured.
- **The axes are linear.** t runs 0 to 4 × 10^6 across x = 90.222 to
  759.822 pt. dH runs 0 to 7 across y = 74.476 to 462.556 pt, so 55.44
  pt per unit. The scales come from the gridlines and tick labels.
- **Nine quantile curves,** three per dash pattern: dotted (MO-COMPASS),
  dashed `[9.25 4]` (R-MinRLE) and solid (R-PERLE). One further 3-vertex
  dotted fragment at the top edge is not a curve.
- **The plateau value 0.43038** is (98.335981 − 74.475691) / 55.44, the
  y of the final vertices of R-PERLE's median and 0.75 curves. Under
  today's `true_g` it is the metric of one state: the complete global
  image set plus one point off the front, (−3, −3, −2) or its mirror.

R-PERLE's curves, each vertex as (t in units of 10^6, dH). t is rounded
to 0.01, and the paths run past the frame's right edge to 4.158.
- **0.25:** (0.01, 1.10082), (0.05, 1.10082), (0.06, 0.77913), (0.07,
  0.64559), (0.35, 0.64559), (0.36, 0.4877), (0.38, 0.4877), (0.39,
  0.43038), (0.46, 0.43038), (0.47, 0), (4.158, 0)
- **0.5:** (0.01, 1.81705), (0.02, 1.81705), (0.03, 1.77983), (0.04,
  1.69655), (0.05, 1.10082), (0.07, 1.10082), (0.08, 0.77913), (0.09,
  0.64559), (0.49, 0.64559), (0.5, 0.43038), (4.158, 0.43038)
- **0.75:** (0.01, 2.68379), (0.02, 2.2576), (0.03, 2.2576), (0.04,
  1.97912), (0.05, 1.77983), (0.06, 1.10082), (0.2, 1.10082), (0.21,
  0.77913), (0.39, 0.77913), (0.4, 0.64559), (0.41, 0.68813), (0.42,
  0.64559), (0.54, 0.64559), (0.55, 0.67495), (0.56, 0.77913), (0.57,
  0.64559), (0.89, 0.64559), (0.9, 0.43038), (4.158, 0.43038)

At 1, 2, 3 and 4 × 10^6 (0.25 / 0.5 / 0.75):
- R-PERLE: 0 / 0.43038 / 0.43038 at every one.
- R-MinRLE: 0 / 0.4304 / 0.4304 at 1 and 4 × 10^6, and 0 / 0.3921 /
  0.4304 at 2 and 3 × 10^6.
- MO-COMPASS: 2.209 / 4.024 / 6.170 at 1 × 10^6, falling to 1.904 /
  3.865 / 5.894 at 4 × 10^6.

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
