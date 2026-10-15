"""Moved to the kernel (sh_platform/profile/tabular.py) because the company profile reads tables too. Module 3 keeps this import name; it is
the same module object, so `T.read_table`, `T.MAX_CELLS` and a test's monkeypatch behave as before."""
import sys

from sh_platform.profile import tabular as _kernel

sys.modules[__name__] = _kernel
