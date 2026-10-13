"""
Backends that run pooled work somewhere other than worker processes on
this machine. `pymoso.pool.LocalBackend` describes what a backend is.

Nothing in the rest of pymoso imports this package at module scope,
and this is the only place in pymoso where a module may import an
optional dependency at module scope
(tests/test_dependency_boundary.py). The modules here do not, as it
happens: `remote` needs none, and `spark` imports pyspark only when a
job is dispatched.
"""
