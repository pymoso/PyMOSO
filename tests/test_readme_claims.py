"""
Layer 5: the README's factual claims name the tests that establish
them.

A claim is followed by an HTML comment, invisible when the README is
rendered:

    <!-- verified: tests/test_file.py::test_name; tests/other.py::test_name -->

This file checks that every test named that way exists, so a renamed or
deleted test cannot leave a claim pointing at nothing. It cannot check
that the test proves the claim; that is review. A claim no test backs
is listed in docs/unverified-claims.md with what would establish it.
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
ANNOTATION = re.compile(r"<!-- verified: (.*?) -->")


def _references():
    return [ref.strip() for group in ANNOTATION.findall(README) for ref in group.split(";")]


def _test_functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def test_the_readme_carries_its_annotations():
    assert len(ANNOTATION.findall(README)) >= 27


@pytest.mark.parametrize("ref", sorted(set(_references())))
def test_every_named_test_exists(ref):
    path, _, name = ref.partition("::")
    assert name, "{0}: name a test, not only a file".format(ref)
    assert (ROOT / path).is_file(), "{0}: no such file".format(ref)
    assert name in _test_functions(ROOT / path), "{0}: no such test".format(ref)


def test_a_reference_to_a_missing_test_is_caught():
    """The check, shown detecting."""
    real = sorted(set(_references()))[0]
    path, _, _ = real.partition("::")
    assert "test_there_is_no_such_test" not in _test_functions(ROOT / path)


def test_the_unverified_claims_are_listed():
    if not (ROOT / "docs").is_dir():
        # A source distribution ships tests/ but not docs/.
        pytest.skip("docs/ is not part of the sdist")
    assert (ROOT / "docs" / "unverified-claims.md").is_file()
