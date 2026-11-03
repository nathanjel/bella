"""Subclasses of the built-in types compiled against CPython (decision 2026-11-03: the instance
is the built-in's object, with the subclass's attribute storage; cases C-3-34 for dict, C-3-35 for
int).

Which operations call a dict subclass's overrides and which take its entries directly, as measured
on 3.15.2: the item operations and len/in/iteration call them, merges and copies read the entries
unless the subclass overrides __iter__, and the dict's own methods never call them. Also what
calling dict() does now that it has a constructor: its arguments, its errors (with the note
CPython adds), object.__new__'s refusal for a dict subclass, and the length hint list() asks for.
The runtime's words are compared too (stdout and the exit status).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_builtin_subclasses
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

DICT_DISPATCH = "class Loud(dict):\n    def __getitem__(self, k):\n        print('getitem', k)\n        return dict.__getitem__(self, k)\n    def __setitem__(self, k, v):\n        print('setitem', k)\n        dict.__setitem__(self, k, v)\n    def __missing__(self, k):\n        print('missing', k)\n        return 0\n    def keys(self):\n        print('keys')\n        return dict.keys(self)\n    def __iter__(self):\n        print('iter')\n        return dict.__iter__(self)\n    def __len__(self):\n        print('len')\n        return dict.__len__(self)\n    def __contains__(self, k):\n        print('contains', k)\n        return dict.__contains__(self, k)\nd = Loud(a=1)\nprint('-- built', d)\nd['b'] = 2\nprint(d['a'], d['zz'])\nprint('get', d.get('a'), d.get('q'))\nprint('--update'); x = {}; x.update(d); print(x)\nprint('--merge'); print({**d})\nprint('--kwargs'); print((lambda **k: k)(**d))\nprint('--copy'); c = d.copy(); print(type(c).__name__, c)\nprint('--or'); print(type(d | {'c': 3}).__name__)\nprint('--dict()'); print(dict(d))\nprint('--in'); print('a' in d)\nprint('--len'); print(len(d))\nprint('--list'); print(list(d))\nprint('--eq'); print(d == {'a': 1, 'b': 2})\nprint('--repr'); print(repr(d))\nclass Plain(dict):\n    pass\np = Plain({1: 2}, x=3)\nprint(p, type(p).__name__, Plain.fromkeys('ab', 0), type(Plain.fromkeys('ab')).__name__)\nns_log = []\nclass Recording(dict):\n    def __setitem__(self, k, v):\n        ns_log.append(k)\n        dict.__setitem__(self, k, v)\nclass Meta(type):\n    @classmethod\n    def __prepare__(mcls, name, bases):\n        return Recording()\nclass K(metaclass=Meta):\n    a = 1\n    def f(self): pass\nprint(ns_log, type(K.__dict__).__name__)\n"

DICT_CONSTRUCTION = "print(dict(), dict(a=1), dict({1: 2}), dict([(1, 2), (3, 4)]), dict({1: 2}, b=3), dict([], x=1))\nfor args in (((1, 2), ), ([(1,)],), ([1],)):\n    try:\n        print(dict(*args))\n    except (TypeError, ValueError) as e:\n        print(type(e).__name__, e)\ntry:\n    dict({}, {})\nexcept TypeError as e:\n    print(e)\nclass D(dict):\n    pass\ntry:\n    object.__new__(D)\nexcept TypeError as e:\n    print(e)\nprint(type(dict.__new__(D)).__name__, dict.__new__(D), type(D.fromkeys([1, 2])).__name__)\nd = D(x=1)\nd.__init__({'y': 2})\nprint(d)\ntry:\n    dict([1])\nexcept TypeError as e:\n    print(e.__notes__)\nclass N(dict):\n    def __new__(cls):\n        return dict.__new__(cls)\nclass M2(N):\n    pass\nfor c in (N, M2):\n    try:\n        object.__new__(c)\n    except TypeError as e:\n        print(e)\nclass L:\n    def __len__(self):\n        print('len of L')\n        return 2\n    def __iter__(self):\n        print('iter of L')\n        return iter([1, 2])\nprint(list(L()), tuple(L()))\nclass H:\n    def __length_hint__(self):\n        print('hint')\n        return 'x'\n    def __iter__(self):\n        return iter([])\ntry:\n    list(H())\nexcept TypeError as e:\n    print(e)\n"


# int(): its arguments and errors; an int subclass's overrides (reflected ones first, as for any
# subclass); range() and chr() take ints through __index__ (found on the way)
INT_INDEX = 'class I:\n    def __index__(self):\n        return 3\nprint(list(range(I())), chr(True), chr(I() + 62) if False else chr(65), list(range(True, 3)))\n'

INT_ERRORS_AND_OVERRIDES = 'for f in (lambda: int("012", 0), lambda: int("1__0"), lambda: int(""), lambda: int(" "), lambda: int("12a"), lambda: int("8", 8),\n          lambda: int("5", 1), lambda: int(5, 10), lambda: int(base=10), lambda: int([]), lambda: int("x" * 300),\n          lambda: int("9" * 4301), lambda: int(1, 2, 3), lambda: int(x=1), lambda: int("1", foo=2), lambda: int("1", 2, base=3),\n          lambda: int("1\\x002"), lambda: int("\\x1c5"), lambda: int("0x", 16), lambda: int("0x10", 10), lambda: int("-_1")):\n    try:\n        print(repr(f()))\n    except (TypeError, ValueError) as e:\n        print(type(e).__name__, e)\nclass W:\n    def __int__(self):\n        return "nine"\nclass Sub(int):\n    pass\nclass R:\n    def __int__(self):\n        return Sub(4)\nfor f in (lambda: int(W()), lambda: int(Sub(7)) + 0):\n    try:\n        print(f())\n    except TypeError as e:\n        print(type(e).__name__, e)\nclass E(int):\n    def __eq__(self, other):\n        return "eq"\n    def __hash__(self):\n        return 99\n    def __neg__(self):\n        return "neg"\n    def __radd__(self, other):\n        return "radd"\n    def __index__(self):\n        return 2\ne = E(3)\nprint(e == 3, 3 == e, hash(e), -e, 1 + e, e + 1, [0, 1, 2, 3, 4][e], {e: 1}.get(3), {3: \'x\'}.get(e), e in {3}, abs(E(-4)))\nclass B(int):\n    def __bool__(self):\n        return False\nprint(bool(B(5)), not B(5), "yes" if B(5) else "no")\n'

# a str constant with a NUL inside was cut at it (found on the way: the literal's length is emitted)
NUL_IN_A_CONSTANT = 'print(len("1\\x002"), repr("a\\x00b"))\n'


def test_dict_subclass_dispatch_is_cpythons() -> None:
    same(DICT_DISPATCH)


def test_dict_construction_and_length_hints() -> None:
    same(DICT_CONSTRUCTION)


def test_int_index_conversions() -> None:
    same(INT_INDEX)


def test_int_errors_and_subclass_overrides() -> None:
    same(INT_ERRORS_AND_OVERRIDES)


def test_a_str_constant_keeps_its_nul() -> None:
    same(NUL_IN_A_CONSTANT)


def test_int_from_an_int_subclass_returned_by_int_is_refused() -> None:
    """CPython copies the value with a DeprecationWarning, which the runtime cannot issue yet."""
    if shutil.which("g++") is None:
        return
    body = "class S(int):\n    pass\nclass R:\n    def __int__(self):\n        return S(4)\nint(R())"
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr, got


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
