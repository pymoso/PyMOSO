"""
pyproject.toml has to build under the setuptools a user already has,
not only under the one it asks for.

`[build-system] requires` is honoured only when pip builds in an
isolated environment. Where isolation is off -- a managed cluster's
pip configuration, `--no-build-isolation`, an offline build -- the
installed setuptools is used whatever its version. `pip install
git+https://...@dev-2.0` failed that way on a Databricks runtime:

    configuration error: `project.license` must be valid exactly by
    one definition (2 matches found)

That is setuptools older than 77 meeting the PEP 639 spelling,
`license = "MIT"` with `license-files` under `[project]`, which it
does not know. The table spelling `license = { text = "MIT" }` is
accepted by every setuptools from 61 (the first to read `[project]`)
through 84, checked by building under 61.0.0, 68.2.2, 75.8.0, 77.0.3
and 84.0.0 with isolation off. LICENSE.txt is picked up by
setuptools' default pattern under all of them.

Current setuptools warns that the table spelling stops being
supported on 2027-02-18. Returning to the PEP 639 spelling then
brings this failure back for anyone still building without isolation
on a setuptools older than 77; it is a decision to make then, not a
tidy-up to make now.

This test cannot build under five setuptools versions -- that needs a
network -- so it holds the spelling that was checked.
"""
import pathlib
import re

PYPROJECT = (pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()


def _table(name):
    match = re.search(r"^\[" + re.escape(name) + r"\]\n(.*?)(?=^\[|\Z)", PYPROJECT, re.S | re.M)
    assert match, name
    return match.group(1)


def test_the_license_is_spelled_the_way_every_supported_setuptools_reads():
    project = _table("project")
    assert re.search(r'^license = \{ text = "MIT" \}$', project, re.M), "see this module's docstring before changing it"
    assert not re.search(r"^license-files\b", project, re.M)


def test_the_build_requirement_does_not_claim_more_than_the_file_needs():
    """A floor of 77 would say the file needs PEP 639 support. It must
    not: that floor is exactly what is ignored where isolation is off."""
    assert re.search(r'^requires = \["setuptools>=61"\]$', _table("build-system"), re.M)
