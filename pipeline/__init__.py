"""Bella pipeline: IR levels, passes, and the toy end-to-end slice (design document, section 8).

Levels: L0 is CPython's ``ast``; L1 (``pipeline.l1``) is PyCore, the desugared tree with
explicit protocol operations; L2-L4 do not exist yet. ``pipeline.slice`` runs a program
through parse -> L1 -> eval1 and through the toy C++ emitter, and compares both with CPython.
"""
