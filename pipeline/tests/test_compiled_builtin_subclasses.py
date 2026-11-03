"""Subclasses of the built-in types compiled against CPython (decision 2026-11-03: the instance
is the built-in's object, with the subclass's attribute storage; case C-3-34 for dict).

Which operations call a dict subclass's overrides and which take its entries directly, as measured
on 3.15.2: the item operations and len/in/iteration call them, merges and copies read the entries
unless the subclass overrides __iter__, and the dict's own methods never call them. Also what
calling dict() does now that it has a constructor: its arguments, its errors (with the note
CPython adds), object.__new__'s refusal for a dict subclass, and the length hint list() asks for.
The runtime's words are compared too (stdout and the exit status).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_builtin_subclasses
"""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

DICT_DISPATCH = "class Loud(dict):\n    def __getitem__(self, k):\n        print('getitem', k)\n        return dict.__getitem__(self, k)\n    def __setitem__(self, k, v):\n        print('setitem', k)\n        dict.__setitem__(self, k, v)\n    def __missing__(self, k):\n        print('missing', k)\n        return 0\n    def keys(self):\n        print('keys')\n        return dict.keys(self)\n    def __iter__(self):\n        print('iter')\n        return dict.__iter__(self)\n    def __len__(self):\n        print('len')\n        return dict.__len__(self)\n    def __contains__(self, k):\n        print('contains', k)\n        return dict.__contains__(self, k)\nd = Loud(a=1)\nprint('-- built', d)\nd['b'] = 2\nprint(d['a'], d['zz'])\nprint('get', d.get('a'), d.get('q'))\nprint('--update'); x = {}; x.update(d); print(x)\nprint('--merge'); print({**d})\nprint('--kwargs'); print((lambda **k: k)(**d))\nprint('--copy'); c = d.copy(); print(type(c).__name__, c)\nprint('--or'); print(type(d | {'c': 3}).__name__)\nprint('--dict()'); print(dict(d))\nprint('--in'); print('a' in d)\nprint('--len'); print(len(d))\nprint('--list'); print(list(d))\nprint('--eq'); print(d == {'a': 1, 'b': 2})\nprint('--repr'); print(repr(d))\nclass Plain(dict):\n    pass\np = Plain({1: 2}, x=3)\nprint(p, type(p).__name__, Plain.fromkeys('ab', 0), type(Plain.fromkeys('ab')).__name__)\nns_log = []\nclass Recording(dict):\n    def __setitem__(self, k, v):\n        ns_log.append(k)\n        dict.__setitem__(self, k, v)\nclass Meta(type):\n    @classmethod\n    def __prepare__(mcls, name, bases):\n        return Recording()\nclass K(metaclass=Meta):\n    a = 1\n    def f(self): pass\nprint(ns_log, type(K.__dict__).__name__)\n"

DICT_CONSTRUCTION = "print(dict(), dict(a=1), dict({1: 2}), dict([(1, 2), (3, 4)]), dict({1: 2}, b=3), dict([], x=1))\nfor args in (((1, 2), ), ([(1,)],), ([1],)):\n    try:\n        print(dict(*args))\n    except (TypeError, ValueError) as e:\n        print(type(e).__name__, e)\ntry:\n    dict({}, {})\nexcept TypeError as e:\n    print(e)\nclass D(dict):\n    pass\ntry:\n    object.__new__(D)\nexcept TypeError as e:\n    print(e)\nprint(type(dict.__new__(D)).__name__, dict.__new__(D), type(D.fromkeys([1, 2])).__name__)\nd = D(x=1)\nd.__init__({'y': 2})\nprint(d)\ntry:\n    dict([1])\nexcept TypeError as e:\n    print(e.__notes__)\nclass N(dict):\n    def __new__(cls):\n        return dict.__new__(cls)\nclass M2(N):\n    pass\nfor c in (N, M2):\n    try:\n        object.__new__(c)\n    except TypeError as e:\n        print(e)\nclass L:\n    def __len__(self):\n        print('len of L')\n        return 2\n    def __iter__(self):\n        print('iter of L')\n        return iter([1, 2])\nprint(list(L()), tuple(L()))\nclass H:\n    def __length_hint__(self):\n        print('hint')\n        return 'x'\n    def __iter__(self):\n        return iter([])\ntry:\n    list(H())\nexcept TypeError as e:\n    print(e)\n"


def test_dict_subclass_dispatch_is_cpythons() -> None:
    same(DICT_DISPATCH)


def test_dict_construction_and_length_hints() -> None:
    same(DICT_CONSTRUCTION)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
