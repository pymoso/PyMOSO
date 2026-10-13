"""Optional dependencies in tests: skipped where absent, except where
their absence would mean the tests for them never ran at all.

The `test` CI matrix installs only `.[test]`, so a test that needs
cloudpickle or pyspark has to skip there. A skip is also what a broken
install, a renamed extra or a missing JVM would produce -- silently,
in every job. So the one job that exists to run these tests sets
PYMOSO_REQUIRE_EXTRAS, and under it a missing optional dependency is a
failure, not a skip (.github/workflows/ci.yml, the `extras` job).
"""
import importlib
import os

import pytest


def required(name):
    """Whether PYMOSO_REQUIRE_EXTRAS (a comma-separated list, e.g.
    `cloudpickle,pyspark`) names `name`."""
    return name in [part.strip() for part in os.environ.get("PYMOSO_REQUIRE_EXTRAS", "").split(",")]


def need(name):
    """Import and return the optional module `name`; skip the calling
    test (or module, at import time) if it is not installed -- unless
    it is required, in which case fail."""
    try:
        return importlib.import_module(name)
    except ImportError as e:
        if required(name):
            pytest.fail("{0} is required here (PYMOSO_REQUIRE_EXTRAS) and cannot be imported: {1}".format(name, e))
        pytest.skip("needs {0}, which is not installed".format(name), allow_module_level=True)
