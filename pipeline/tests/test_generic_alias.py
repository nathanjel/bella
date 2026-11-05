"""Subscripting a class and types.GenericAlias, compiled, against CPython.

Case C-3-36 shows the behaviour by exception class, as a case must; these compare messages too, and
what `dir()` lists, which GenericAlias needed: every name of a built-in type, from the names table.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

PROGRAMS: list[tuple[str, str]] = [
    ('not_subscriptable', "class P:\n    pass\nclass N:\n    __class_getitem__ = None\nclass M(type):\n    pass\nclass Q(metaclass=M):\n    pass\nfor f in (lambda: P[int], lambda: N[int], lambda: str[int], lambda: int[int], lambda: object[int], lambda: M[int], lambda: Q[int], lambda: ValueError[int], lambda: 1[0], lambda: None[0]):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('a_hook_that_raises', "class C:\n    def __class_getitem__(cls, item):\n        raise ValueError('hook')\nclass D:\n    __class_getitem__ = 5\nclass E:\n    @property\n    def __class_getitem__(self):\n        return 1\nfor k in (C, D, E):\n    try:\n        print(k[1])\n    except (ValueError, TypeError) as e:\n        print(type(e).__name__, e)\n"),
    ('metaclass_hook_attribute', "class M(type):\n    def __getattr__(cls, name):\n        print('asked', name)\n        if name == '__class_getitem__':\n            return lambda item: ('from the metaclass', item)\n        raise AttributeError(name)\nclass C(metaclass=M):\n    pass\nprint(C[1])\n"),
    ('hook_arguments', "for f in (lambda: list.__class_getitem__(), lambda: list.__class_getitem__(1, 2), lambda: dict.__class_getitem__(k=1), lambda: tuple.__class_getitem__(1, 2)):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\nprint(list.__class_getitem__(int), slice[int], frozenset[int])\nclass D(dict):\n    pass\nprint(D[int], D[int].__origin__ is D, D[int](a=1), type(D[int](a=1)).__name__, D[int](a=1).__orig_class__)\n"),
    ('constructor_messages', "from types import GenericAlias as G\nfor f in (lambda: G(), lambda: G(list), lambda: G(list, int, str), lambda: G(list, args=int), lambda: G(origin=list, args=int)):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\nprint(G.__doc__, G.__name__, G.__qualname__, G.__module__, G.__bases__, G.__mro__)\n"),
    ('read_only_messages', "a = list[int]\nfor f in (lambda: setattr(a, '__origin__', 1), lambda: setattr(a, '__args__', 1), lambda: setattr(a, '__unpacked__', 1), lambda: setattr(a, '__parameters__', 1), lambda: setattr(a, '__typing_unpacked_tuple_args__', 1), lambda: delattr(a, '__origin__'), lambda: delattr(a, '__parameters__')):\n    try:\n        f()\n    except AttributeError as e:\n        print(e)\n"),
    ('absent_messages', "a = list[int]\nfor f in (lambda: a.nothing, lambda: setattr(a, 'x', 1), lambda: delattr(a, 'x'), lambda: delattr(a, '__name__'), lambda: a.__bases__, lambda: a.__copy__, lambda: a.__deepcopy__):\n    try:\n        print(f())\n    except AttributeError as e:\n        print(e, getattr(e, 'name', None))\n"),
    ('no_dict_messages', "class S:\n    __slots__ = ('a',)\ns = S()\nfor f in (lambda: setattr(s, 'x', 1), lambda: delattr(s, 'x'), lambda: object.__setattr__(s, 'x', 1), lambda: object.__delattr__(s, 'x'), lambda: delattr(s, 'a'), lambda: object.__delattr__(s, 'a'), lambda: s.a):\n    try:\n        f()\n    except AttributeError as e:\n        print(e)\nclass D:\n    pass\nd = D()\nfor f in (lambda: delattr(d, 'x'), lambda: object.__delattr__(d, 'x')):\n    try:\n        f()\n    except AttributeError as e:\n        print(e)\n"),
    ('the_type_is_immutable', "from types import GenericAlias as G\nfor f in (lambda: setattr(G, 'x', 1), lambda: delattr(G, '__repr__'), lambda: setattr(G, '__repr__', 1)):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('check_messages', "a = list[int]\nfor f in (lambda: isinstance([], a), lambda: issubclass(list, a), lambda: isinstance([], (int, a)), lambda: issubclass(a, list), lambda: a.__instancecheck__(1), lambda: a.__subclasscheck__(1)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('compare_messages', "for f in (lambda: list[int] < list[int], lambda: list[int] < 1, lambda: 1 < list[int], lambda: hash(list[[int]]), lambda: hash(list[{}]), lambda: list[int] + 1):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('substitution_messages', "class V:\n    def __init__(self, n):\n        self.n = n\n    def __repr__(self):\n        return '~' + self.n\n    def __typing_subst__(self, arg):\n        return arg\nT, S = V('T'), V('S')\nfor f in (lambda: list[int][str], lambda: list[int][()], lambda: list[T][int, str], lambda: dict[T, S][int], lambda: list[T][()], lambda: dict[T, list[S]][int]):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\nclass Stale:\n    def __repr__(self):\n        return '<stale>'\ns = Stale()\nl = list[s]\nprint(l.__parameters__)\nStale.__typing_subst__ = lambda self, a: a\ntry:\n    from types import GenericAlias as G\n    G(list, (T, s))[int]\nexcept TypeError as e:\n    print(e)\nclass U:\n    __typing_is_unpacked_typevartuple__ = True\n    def __typing_subst__(self, arg):\n        return arg\n    def __repr__(self):\n        return '<u>'\nclass Mine:\n    pass\nfor v in (1, Mine(), 'x'):\n    try:\n        tuple[U()][v]\n    except TypeError as e:\n        print(e)\n"),
    ('subst_raises', "class V:\n    def __typing_subst__(self, arg):\n        raise ValueError('subst')\n    def __repr__(self):\n        return 'V'\ntry:\n    list[V()][int]\nexcept ValueError as e:\n    print(e)\nclass W:\n    @property\n    def __typing_subst__(self):\n        raise KeyError('attr')\ntry:\n    print(list[W()].__parameters__)\nexcept KeyError as e:\n    print('KeyError', e)\nclass X:\n    @property\n    def __parameters__(self):\n        raise KeyError('params')\ntry:\n    print(list[X()].__parameters__)\nexcept KeyError as e:\n    print('KeyError', e)\nclass Y:\n    def __typing_prepare_subst__(self, alias, args):\n        raise ValueError('prepare')\n    def __typing_subst__(self, arg):\n        return arg\n    def __repr__(self):\n        return 'Y'\ntry:\n    list[Y()][int]\nexcept ValueError as e:\n    print(e)\n"),
    ('repr_raises', "class B:\n    def __repr__(self):\n        raise ValueError('repr')\nclass Q:\n    @property\n    def __qualname__(self):\n        raise KeyError('q')\nclass O:\n    @property\n    def __origin__(self):\n        raise KeyError('o')\nfor v in (B(), Q(), O()):\n    try:\n        print(repr(list[v]))\n    except (ValueError, KeyError) as e:\n        print(type(e).__name__, e)\nl = []\nl.append(l)\ntry:\n    print(list[l].__parameters__)\nexcept RecursionError:\n    print('RecursionError')\n"),
    ('qualname_and_module_of_args', "class M:\n    __qualname__ = 'Q'\n    __module__ = 7\nclass N:\n    __qualname__ = 7\n    __module__ = 'mod'\nclass P:\n    __qualname__ = 'Q'\n    __module__ = 'builtins'\nprint(list[M()], list[N()], list[P()], list[M], list[N], list[P])\nimport types\nprint(list[types.SimpleNamespace], list[types.GenericAlias], list[len], list[print], list[int.__add__] if False else 'skip')\n"),
    ('call_of_a_class_with_a_setter', "from types import GenericAlias as G\nlog = []\nclass C:\n    def __setattr__(self, name, value):\n        log.append((name, type(value).__name__))\nc = G(C, int)()\nprint(log, hasattr(c, '__orig_class__'))\nclass I:\n    def __new__(cls):\n        return 5\nprint(G(I, int)())\nclass R:\n    __slots__ = ()\nprint(type(G(R, int)()).__name__, list[int]() , dict[int, int]())\ndef f(*a, **k):\n    return (a, k)\nprint(G(f, int)(1, k=2))\nprint(G(f, int).__name__, G(f, int).__wrapped__ if False else 'x')\n"),
    ('forwarded_calls_and_descriptors', "class O:\n    @property\n    def prop(self):\n        return 'p'\n    @staticmethod\n    def sm():\n        return 's'\n    @classmethod\n    def cm(cls):\n        return cls.__name__\n    def __getattr__(self, name):\n        return 'instance hook'\nclass M(type):\n    def __getattr__(cls, name):\n        return 'class hook ' + name\n    def meta(cls):\n        return 'meta ' + cls.__name__\nclass C(metaclass=M):\n    pass\nfrom types import GenericAlias as G\na = G(O, int)\nb = G(C, int)\nprint(type(a.prop).__name__, a.sm(), a.cm(), b.anything, b.meta())\nprint(hasattr(b, 'x'), getattr(b, 'y', 'd'), b.__name__)\nprint(list[int].__add__ is list.__add__, list[int].__eq__ is list.__eq__, list[int].__repr__ is list.__repr__, list[int].__doc__ == list.__doc__, list[int].__hash__)\n"),
    ('a_subclass_with_its_own_attributes', "from types import GenericAlias as G\nclass S(G):\n    extra = 'on the subclass'\n    def own(self):\n        return 'own'\n    def __getitem__(self, item):\n        return ('S', super().__getitem__(item))\n    def __call__(self, *a):\n        return ('called', a)\nclass V:\n    def __typing_subst__(self, a):\n        return a\n    def __repr__(self):\n        return 'V'\ns = S(list, V())\nprint(s[int], s(1), repr(s), s == G(list, s.__args__))\ntry:\n    print(s.extra)\nexcept AttributeError as e:\n    print(e)\ntry:\n    print(s.own)\nexcept AttributeError as e:\n    print(e)\nprint(s.__class__.__name__, s.__mro_entries__(()), s.__reduce__()[0].__name__)\nclass WithSetter(G):\n    pass\nw = WithSetter(list, int)\nw.note = 1\ntry:\n    print(w.note)\nexcept AttributeError as e:\n    print(e)\n"),
    ('generic_base_classes', "from types import GenericAlias as G\nclass B:\n    def __class_getitem__(cls, item):\n        return G(cls, item)\nclass C(B[int]):\n    pass\nclass D(B[int], dict[str, int]):\n    pass\nprint(C.__bases__, C.__orig_bases__, D.__bases__, D.__orig_bases__, D.__mro__, C.__dict__['__orig_bases__'])\nclass E(C):\n    pass\nprint('__orig_bases__' in vars(E), E.__orig_bases__)\nclass F(list[int].__origin__ if False else object):\n    pass\ntry:\n    class H(list[int], tuple[int]):\n        pass\nexcept (TypeError, Exception) as e:\n    print(type(e).__name__)\n"),
    ('iterator_object', "it = iter(list[int])\nprint(type(it).__name__, type(it).__module__, type(it).__qualname__, repr(type(it)), type(it).__mro__)\nprint(it.__reduce__()[0] is iter, it.__reduce__()[1][0] == list[int], next(it), it.__reduce__() == (iter, ((),)), list(it))\nfor f in (lambda: next(it), lambda: class_of_it(1)):\n    try:\n        f()\n    except (StopIteration, NameError) as e:\n        print(type(e).__name__)\ntry:\n    a, b = list[int]\nexcept ValueError as e:\n    print(e)\nfirst, = list[int]\nprint(first, [*list[int]], (*tuple[int], 1))\n"),
    ('dir_of_everything', "class A:\n    x = 1\n    def f(self): pass\nclass B(A):\n    __slots__ = ('s',)\nclass C:\n    __slots__ = ()\nclass E(Exception):\n    y = 2\nclass D(dict):\n    z = 3\na = A()\na.inst = 1\nfor v in (a, A, B, B(), C, C(), E, E(), D, D(), 1, 'a', [], {}, (), None, int, str, list, dict, tuple, object, type, object(), len, property, property(), staticmethod, classmethod, range(1), slice(1), ValueError, ValueError(), list[int]):\n    print(dir(v))\nprint(type(a.__dir__()).__name__, type(A.__dir__(A)).__name__)\n"),
    ('dir_of_modules_and_metaclasses', "import sys, types, _types\nprint(dir(sys) == dir(sys), 'path' in dir(sys), dir(sys)[0], dir(types)[:3], dir(_types)[:3])\nimport builtins\nprint(dir(builtins)[:4], 'len' in dir(builtins))\nclass M(type):\n    q = 1\nclass N(metaclass=M):\n    r = 2\nprint(dir(N), dir(N()), 'q' in dir(N), 'q' in dir(M))\nclass Own:\n    def __dir__(self):\n        return ['b', 'a', 'b']\nprint(dir(Own()))\nclass Bad:\n    def __dir__(self):\n        return 1\ntry:\n    dir(Bad())\nexcept TypeError as e:\n    print(e)\nclass Lying:\n    @property\n    def __class__(self):\n        return 5\nprint(dir(Lying()))\nclass Fake:\n    x = 1\nclass LyingClass:\n    y = 2\n    @property\n    def __class__(self):\n        return Fake\nprint(dir(LyingClass()))\nclass NotDict:\n    __dict__ = 5\nprint(dir(NotDict()))\nfor f in (lambda: object.__dir__(), lambda: object().__dir__(1), lambda: type.__dir__(), lambda: int.__dir__(int, 1)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('getattribute_of_object', "class C:\n    k = 'class'\n    @property\n    def p(self):\n        return 'prop'\nc = C()\nc.i = 'inst'\nf = object.__getattribute__\nprint(f(c, 'k'), f(c, 'p'), f(c, 'i'), type(f(c, 'f') if False else 1).__name__, c.__getattribute__('k'), f(1, '__class__'), f('a', '__class__'), f(None, '__class__'))\nfor g in (lambda: f(c, 'absent'), lambda: f(c, 1), lambda: f(c), lambda: f(), lambda: c.__getattribute__(), lambda: c.__getattribute__('k', 1)):\n    try:\n        print(g())\n    except (AttributeError, TypeError) as e:\n        print(type(e).__name__, e)\nclass D:\n    def lookup(self, name):\n        return super().__getattribute__(name)\n    x = 5\nprint(D().lookup('x'))\n"),
]


def _refused(src: str, reason: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert got.returncode == 70 and reason in got.stderr, got


def test_a_union_of_aliases_is_refused_until_it_exists() -> None:
    _refused("print(list[int] | None)\n", "types.UnionType")
    _refused("print(None | list[int])\n", "types.UnionType")


def test_getattribute_past_a_getattr_is_refused() -> None:
    """The instances' path runs __getattr__ and cannot yet skip it, as object.__getattribute__ must."""
    _refused("class C:\n    def __getattr__(self, n):\n        return 1\nprint(object.__getattribute__(C(), 'x'))\n", "__getattr__")


def test_a_program_overriding_getattribute_stays_refused() -> None:
    """[P2+], spec section 3: the alias's forwarding is the runtime's, not this."""
    _refused("class C:\n    def __getattribute__(self, n):\n        return 1\nprint(C().x)\n", "__getattribute__")


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
    test_a_union_of_aliases_is_refused_until_it_exists()
    test_getattribute_past_a_getattr_is_refused()
    test_a_program_overriding_getattribute_stays_refused()
