"""Executable reference model of Bella's object model (design document, section 3).

The model is a Python program that behaves the way the runtime's attribute machinery is
*specified* to behave: promoted inline fields, lazily materialised instance dictionaries
with exposure, replacement and sharing, descriptors by Python's rules, ``__getattr__``,
class versions, and inline caches with their validity predicates. It is tested against
CPython on random operation sequences (``refmodel.selftest`` with the standard library
only, ``refmodel/tests`` with Hypothesis) so that the specification can be wrong in a
way a test can show, before any C++ exists.
"""
from refmodel.objects import (
    UNSET,
    CacheEntry,
    ModelError,
    RefClass,
    RefObject,
    Runtime,
    Site,
)

__all__ = ["UNSET", "CacheEntry", "ModelError", "RefClass", "RefObject", "Runtime", "Site"]
