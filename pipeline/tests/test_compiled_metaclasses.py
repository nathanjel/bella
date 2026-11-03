"""Metaclasses compiled against CPython (step 3b of the C++ leg; docs/emitter.md, case C-3-33).

A class whose metaclass is a class of the program's takes its behaviour from that metaclass, as an
instance takes its from its class: calls, attribute stores and deletes, missing attributes,
operators and comparisons, truth, repr and hash. The programs follow what enum and abc do with
their metaclasses (guarded class attributes, __members__, __abstractmethods__), and the class
attributes CPython's type keeps as descriptors (__doc__, __module__, __name__). The runtime's words
are compared too (stdout and the exit status).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_metaclasses
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

ENUM_AND_ABC_SHAPES = 'class EnumLike(type):\n    def __new__(mcls, name, bases, ns):\n        members = {k: v for k, v in ns.items() if k[:1] != "_"}\n        cls = super().__new__(mcls, name, bases, ns)\n        cls._members = members\n        return cls\n    @property\n    def __members__(cls):\n        return {k: v for k, v in cls._members.items()}\n    def __setattr__(cls, name, value):\n        if name in cls.__dict__.get("_members", {}):\n            raise AttributeError("cannot reassign member " + repr(name))\n        super().__setattr__(name, value)\n    def __delattr__(cls, name):\n        if name in cls._members:\n            raise AttributeError("cannot delete member " + repr(name))\n        super().__delattr__(name)\n    def __reversed__(cls):\n        return iter(list(cls._members)[::-1])\n    def __len__(cls):\n        return len(cls._members)\n    def __bool__(cls):\n        return True\nclass Color(metaclass=EnumLike):\n    RED = 1\n    GREEN = 2\nprint(Color.__members__, len(Color), bool(Color), list(type(Color).__reversed__(Color)))\nfor thunk in (lambda: setattr(Color, "RED", 5), lambda: delattr(Color, "GREEN")):\n    try:\n        thunk()\n    except AttributeError as e:\n        print("AttributeError", e)\nColor.extra = 3\ndel Color.extra\nprint(hasattr(Color, "extra"), type(Color).__name__, Color.__dict__["RED"])\nclass Empty(metaclass=EnumLike):\n    pass\nprint(len(Empty), bool(Empty), Empty == Empty, Empty != Color, hash(Empty) == hash(Empty))\nclass EqMeta(type):\n    def __eq__(cls, other):\n        return "eq called"\n    __hash__ = None\nclass E1(metaclass=EqMeta):\n    pass\nprint(E1 == 1)\ntry:\n    hash(E1)\nexcept TypeError as e:\n    print("TypeError", e)\nclass AbstractLike(type):\n    def __new__(mcls, name, bases, ns):\n        cls = super().__new__(mcls, name, bases, ns)\n        abstract = {k for k, v in ns.items() if getattr(v, "__isabstractmethod__", False)}\n        cls.__abstractmethods__ = frozenset(abstract)\n        return cls\ndef abstract(f):\n    f.__isabstractmethod__ = True\n    return f\nclass Shape(metaclass=AbstractLike):\n    @abstract\n    def area(self): ...\ntry:\n    Shape()\nexcept TypeError as e:\n    print("TypeError", e)\nclass Many(metaclass=AbstractLike):\n    @abstract\n    def b(self): ...\n    @abstract\n    def a(self): ...\ntry:\n    Many()\nexcept TypeError as e:\n    print("TypeError", e)\nMany.__abstractmethods__ = frozenset()\nprint(type(Many()).__name__)\ndel Many.__abstractmethods__\nprint(type(Many()).__name__)\ntry:\n    type.__abstractmethods__\nexcept AttributeError as e:\n    print("AttributeError", e)\ntry:\n    Color.__abstractmethods__\nexcept AttributeError as e:\n    print("AttributeError", e)\n'

CLASS_ATTRIBUTES = 'class C:\n    "first"\nC.__doc__ = "second"\nprint(C.__doc__)\nclass D:\n    pass\nprint(D.__doc__)\nD.__doc__ = "set"\nprint(D.__doc__, D.__dict__["__doc__"])\nfor thunk in (lambda: setattr(int, "__doc__", "x"), lambda: delattr(C, "__doc__"), lambda: setattr(C, "__mro__", ())):\n    try:\n        thunk()\n    except (TypeError, AttributeError) as e:\n        print(type(e).__name__, e)\nC.__module__ = "elsewhere"\nprint(C.__module__, repr(C))\nfor thunk in (lambda: delattr(C, "__name__"), lambda: delattr(C, "__module__"), lambda: setattr(int, "__name__", "x"), lambda: setattr(C, "__name__", 5)):\n    try:\n        thunk()\n    except (TypeError, AttributeError) as e:\n        print(type(e).__name__, e)\n'

# CPython's type keeps these as descriptors the runtime does not have yet: a store is refused,
# never put in the class's dict
REFUSED_STORES = (
    "class C:\n    pass\nC.__type_params__ = ()",
    "class C:\n    pass\nC.__basicsize__ = 3",
    "class C:\n    pass\nC.__bases__ = (object,)",
)


def test_metaclasses_in_enum_and_abc_shapes() -> None:
    same(ENUM_AND_ABC_SHAPES)


def test_class_attributes_kept_by_type() -> None:
    same(CLASS_ATTRIBUTES)


def test_class_stores_cpython_takes_through_descriptors_are_refused() -> None:
    if shutil.which("g++") is None:
        return
    for body in REFUSED_STORES:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr, (body, got)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
