"""
The 2018 reference pickles in docs/reference/ must not ship in the sdist
or the wheel.

Nothing in the package opens them (TPCTester reads a Python literal
converted from lescombos.pkl), but a pickle inside an installable package
is a latent hazard: anything that later loads it runs whatever the file
names. Today neither artifact can include them. The wheel takes only the
packages listed in pyproject.toml, with include-package-data = false, and
MANIFEST.in adds only pytest.ini, tests/ and pymoso/examples/ to the
sdist. That was checked on 2026-11-18 by building both with the pickles
present.

This test does not build anything. It holds the invariant directly:
- no *.pkl anywhere under the pymoso/ package tree;
- MANIFEST.in names nothing under docs/;
- include-package-data stays false.

That is weaker than inspecting a built sdist and wheel, and it does not catch:
- a pickle outside both pymoso/ and docs/ pulled in by a MANIFEST.in
  pattern that does not mention docs/, such as `recursive-include tests *`
  with a pickle placed under tests/, or `global-include *.pkl`;
- a change of build backend, or a setuptools plugin such as
  setuptools-scm that adds every tracked file to the sdist;
- package_data or data-files entries added to pyproject.toml;
- anything a future setuptools includes by default.

Rebuild and list both artifacts after any change to MANIFEST.in, the
[tool.setuptools] table or the build backend. docs/end-seed-scope.md
lists this among the tests that are knowingly weaker than what they
guard.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_no_pickle_inside_the_package_tree():
    assert sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "pymoso").rglob("*.pkl")) == []


def test_manifest_names_nothing_under_docs():
    lines = [l.split("#", 1)[0].strip() for l in (ROOT / "MANIFEST.in").read_text().splitlines()]
    assert [l for l in lines if re.search(r"(^|[\s/])docs(/|\s|$)", l)] == []


def test_the_wheel_takes_no_package_data():
    pyproject = (ROOT / "pyproject.toml").read_text()
    table = re.search(r"^\[tool\.setuptools\]\n(.*?)(?=^\[|\Z)", pyproject, re.S | re.M).group(1)
    assert re.search(r"^include-package-data\s*=\s*false\s*$", table, re.M)
