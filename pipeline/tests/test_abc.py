"""`_abc` and what the frozen `abc` needs of the runtime, compiled, against CPython.

Case C-7-19 shows the behaviour by exception class, as a case must; these compare messages too,
and hold what only the compiled side can show: the refusals.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES: list[tuple[str, str]] = [
    ('instantiate', "from abc import ABC, abstractmethod\nclass A(ABC):\n    @abstractmethod\n    def f(self): pass\n    @abstractmethod\n    def g(self): pass\nclass B(ABC):\n    @abstractmethod\n    def f(self): pass\nfor c in (A, B):\n    try:\n        c()\n    except TypeError as e:\n        print(e)\ntry:\n    object.__new__(A)\nexcept TypeError as e:\n    print(e)\n"),
    ('register', "from abc import ABC\nclass A(ABC):\n    pass\nclass B(ABC):\n    pass\nB.register(A)\nfor f in (lambda: A.register(1), lambda: A.register(B), lambda: issubclass(1, A), lambda: isinstance(1, 1)):\n    try:\n        f()\n    except (TypeError, RuntimeError) as e:\n        print(type(e).__name__, e)\n"),
    ('hook', "from abc import ABC\nclass A(ABC):\n    @classmethod\n    def __subclasshook__(cls, C):\n        return 1\nclass B(ABC):\n    @classmethod\n    def __subclasshook__(cls, C):\n        raise ValueError('from the hook')\nclass C:\n    pass\nfor k in (A, B):\n    try:\n        issubclass(C, k)\n    except (AssertionError, ValueError) as e:\n        print(type(e).__name__, e)\n"),
    ('wrong_impl', "from abc import ABC\nclass A(ABC):\n    pass\nA._abc_impl = 1\nfor f in (lambda: isinstance(1, A), lambda: issubclass(int, A), lambda: A.register(int)):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('no_impl', "import _abc\nfor f in (lambda: _abc._abc_instancecheck(int, 1), lambda: _abc._abc_subclasscheck(int, int), lambda: _abc._reset_caches(int), lambda: _abc._reset_registry(int), lambda: _abc._get_dump(int)):\n    try:\n        f()\n    except AttributeError as e:\n        print(e, e.name, e.obj)\n"),
    ('arguments', "import _abc\nfor f in (lambda: _abc._abc_init(), lambda: _abc._abc_init(1, 2), lambda: _abc._abc_init(self=1), lambda: _abc._abc_register(int), lambda: _abc._abc_instancecheck(), lambda: _abc._abc_subclasscheck(1, 2, 3), lambda: _abc.get_cache_token(1), lambda: _abc._reset_caches(), lambda: _abc._get_dump()):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('flags', "from abc import ABC\ntry:\n    class Both(ABC):\n        __abc_tpflags__ = (1 << 5) | (1 << 6)\nexcept TypeError as e:\n    print(e)\nclass One(ABC):\n    __abc_tpflags__ = 1 << 5\nprint('__abc_tpflags__' in vars(One), hasattr(One, '__abc_tpflags__'))\n"),
    ('init_of_anything', "import _abc\nclass O:\n    pass\no = O()\ntry:\n    _abc._abc_init(1)\nexcept AttributeError as e:\n    print(e)\ntry:\n    _abc._abc_init(o)\nexcept AttributeError as e:\n    print(e)\nclass P:\n    __bases__ = ()\no = P()\no.x = 1\n_abc._abc_init(o)\nprint(vars(o).keys(), type(o._abc_impl).__name__, o.__abstractmethods__ == set())\n"),
    ('bad_namespaces', "import _abc\nclass N1:\n    __dict__ = 1\nclass N2:\n    class __dict__:\n        @staticmethod\n        def items():\n            return 1\nclass N3:\n    class __dict__:\n        @staticmethod\n        def items():\n            return [1]\nclass N4:\n    class __dict__:\n        @staticmethod\n        def items():\n            return [(1, 2, 3)]\nclass N5:\n    __bases__ = []\n    class __dict__:\n        @staticmethod\n        def items():\n            return []\nfor k in (N1, N2, N3, N4, N5):\n    try:\n        _abc._abc_init(k())\n    except (TypeError, AttributeError) as e:\n        print(k.__name__, type(e).__name__, e)\n"),
    ('abstract_name_not_a_str', "import _abc\nclass B:\n    __abstractmethods__ = [1]\nclass C(B):\n    pass\ntry:\n    _abc._abc_init(C)\nexcept TypeError as e:\n    print(e)\n"),
    ('instance_lies', "from abc import ABC\nclass A(ABC):\n    pass\nclass R:\n    pass\nA.register(R)\nissubclass(R, A)\nclass Unhashable:\n    @property\n    def __class__(self):\n        return []\nclass Number:\n    @property\n    def __class__(self):\n        return 5\nclass Hashes:\n    def __hash__(self):\n        print('hashed')\n        return 1\nclass Slotted:\n    __slots__ = ()\n    def __hash__(self):\n        print('not hashed')\n        return 1\nclass ViaHash:\n    @property\n    def __class__(self):\n        return Hashes()\nclass ViaSlots:\n    @property\n    def __class__(self):\n        return Slotted()\nfor k in (Unhashable, Number, ViaHash, ViaSlots):\n    try:\n        print(isinstance(k(), A))\n    except TypeError as e:\n        print(k.__name__, e)\n"),
    ('truthy_subclasscheck', "from abc import ABCMeta\nclass M(ABCMeta):\n    def __subclasscheck__(cls, C):\n        print('check', C.__name__)\n        return 'yes' if C.__name__ == 'Liar' else ''\nclass A(metaclass=M):\n    pass\nimport _abc\nclass Liar:\n    pass\nclass Other:\n    @property\n    def __class__(self):\n        return Liar\nclass Third:\n    @property\n    def __class__(self):\n        return int\nprint(repr(_abc._abc_instancecheck(A, Liar())), repr(_abc._abc_instancecheck(A, Other())), repr(_abc._abc_instancecheck(A, Third())))\n"),
    ('subclasses_replaced', "from abc import ABC\nclass A(ABC):\n    @classmethod\n    def __subclasses__(cls):\n        return (1,)\nclass B(ABC):\n    @classmethod\n    def __subclasses__(cls):\n        return [int]\nclass C:\n    pass\ntry:\n    issubclass(C, A)\nexcept TypeError as e:\n    print(e)\nprint(issubclass(C, B), issubclass(int, B), issubclass(bool, B))\n"),
    ('hash_of_a_metaclass', "from abc import ABCMeta\nclass M(ABCMeta):\n    __hash__ = None\nclass A(metaclass=ABCMeta):\n    pass\nA.register(int)\nclass U(metaclass=M):\n    pass\ntry:\n    issubclass(U, A)\nexcept TypeError as e:\n    print(e)\ntry:\n    A.register(U)\nexcept TypeError as e:\n    print(e)\n"),
    ('is_abstract_raises', "from abc import ABC\nclass Bad:\n    @property\n    def __isabstractmethod__(self):\n        raise ValueError('asked')\nclass NoAttr:\n    @property\n    def __isabstractmethod__(self):\n        raise AttributeError('no')\nclass T:\n    __isabstractmethod__ = 1\nclass F:\n    def __bool__(self):\n        print('bool')\n        return False\nclass G:\n    __isabstractmethod__ = F()\nclass A(ABC):\n    n = NoAttr()\n    t = T()\n    g = G()\nprint(A.__abstractmethods__ == {'t'})\ntry:\n    class B(ABC):\n        b = Bad()\nexcept ValueError as e:\n    print(e)\nprint(classmethod(T()).__isabstractmethod__, staticmethod(T()).__isabstractmethod__, property(T()).__isabstractmethod__)\ntry:\n    classmethod(Bad()).__isabstractmethod__\nexcept ValueError as e:\n    print(e)\n"),
    ('is_abstract_read_only', "def f():\n    pass\nfor v in (classmethod(f), staticmethod(f), property(f)):\n    for act in (lambda: setattr(v, '__isabstractmethod__', True), lambda: delattr(v, '__isabstractmethod__')):\n        try:\n            act()\n        except AttributeError as e:\n            print(e)\n"),
    ('is_abstract_of_property_parts', "def a():\n    pass\na.__isabstractmethod__ = True\ndef b():\n    pass\nprint(property(a).__isabstractmethod__, property(b, a).__isabstractmethod__, property(b, b, a).__isabstractmethod__, property(b, b, b).__isabstractmethod__, property().__isabstractmethod__)\nclass P(property):\n    pass\nprint(P(a).__isabstractmethod__, P(b).getter(a).__isabstractmethod__, type(P(a).setter(b)).__name__)\n"),
    ('ordering_of_a_class_namespace', "class C:\n    a = 1\n    def __eq__(self, o):\n        return True\n    def f(self):\n        pass\nprint([k for k in vars(C) if k != '__weakref__'])\nclass S:\n    '''doc'''\n    __slots__ = ('x',)\nprint(list(vars(S)))\nclass H(C):\n    b = 1\nprint(list(vars(H)), C.__hash__)\nclass O:\n    __dict__ = 1\nprint(O().__dict__, O.__dict__['__dict__'])\n"),
    ('subclass_hook_of_object', "class C:\n    pass\nprint(object.__subclasshook__(int), C.__subclasshook__(int), type(vars(object)['__subclasshook__']).__name__)\nfor f in (lambda: object.__subclasshook__(), lambda: object.__subclasshook__(1, 2)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('subclasses', "class A:\n    pass\nclass B(A):\n    pass\nclass C(A):\n    pass\nclass D(B, C):\n    pass\nprint(A.__subclasses__(), B.__subclasses__(), D.__subclasses__(), type(A.__subclasses__()).__name__, A.__subclasses__() is A.__subclasses__())\nfor f in (lambda: A.__subclasses__(1), lambda: type.__subclasses__()):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\nprint(type.__subclasses__(A) == A.__subclasses__())\nclass M(type):\n    pass\nclass N(M):\n    pass\nprint(M.__subclasses__(M), type.__subclasses__(M))\n"),
    ('a_class_dict_is_live', "class C:\n    a = 1\n    def f(self):\n        pass\nk = C.__dict__.keys()\nv = C.__dict__.values()\ni = C.__dict__.items()\nprint(type(k).__name__, type(v).__name__, type(i).__name__, type(iter(C.__dict__)).__name__)\nprint('a' in k, ('a', 1) in i, ('a', 2) in i)\nC.b = 2\nprint(len(k) == len(C.__dict__), 'b' in k, list(k)[-1], list(i)[-1], list(v)[-1])\nC.a = 9\nprint(('a', 9) in i, ('a', 1) in i)\ndel C.b\nprint('b' in k, list(k)[-1])\nC.b = 3\nprint(list(k)[-1])\nprint(list(C.__dict__)[-1], len(list(C.__dict__.items())) == len(C.__dict__))\n"),
    ('a_class_dict_changing_in_a_loop', "class C:\n    a = 1\ntry:\n    for name in C.__dict__:\n        C.z = 1\nexcept RuntimeError as e:\n    print(e)\ntry:\n    for name, value in C.__dict__.items():\n        del C.z\nexcept RuntimeError as e:\n    print(e)\nfor name in C.__dict__.keys():\n    C.a = 2\nprint(C.__dict__['a'])\n"),
    ('a_value_dies_with_the_class_attribute', "class V:\n    def __init__(self, n):\n        self.n = n\n    def __del__(self):\n        print('dies', self.n)\nclass C:\n    a = V('a')\nitems = C.__dict__.items()\nprint('replacing')\nC.a = V('b')\nprint('deleting')\ndel C.a\nprint('deleted', list(items)[-1][0])\nC.c = V('c')\nx = C.__dict__['c']\ndel C.c\nprint('still held', x.n)\ndel x\nprint('end')\n"),
    ('mappingproxy', "class C:\n    a = 1\nd = C.__dict__\nprint(repr(d).startswith('mappingproxy({'), str(d).startswith(\"{'\"), type(d.copy()).__name__, d.copy()['a'], d.copy() is d.copy())\nprint(d == dict(d), d != dict(d), d == d, d == 1, 1 == d, dict(d) == d, d != 1)\nfor f in (lambda: hash(d), lambda: d < 1, lambda: 1 < d, lambda: d < d, lambda: d.keys(1), lambda: d.items(1), lambda: d.values(1), lambda: d.copy(1)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\ntry:\n    d['x'] = 1\nexcept TypeError as e:\n    print(e)\nprint(dict(d)['a'], {**d}['a'])\n"),
    ('builtin_functions', "import sys\nfor f in (len, sys.exit, print, [].append, {}.get, ''.join, sys.stdout.write):\n    print(f.__module__, f.__name__, f.__qualname__, type(f.__self__).__name__)\nprint(object.__new__.__qualname__, object.__new__.__module__, object.__new__.__self__, dict.fromkeys.__qualname__)\nprint(len.__self__ is sys.modules['builtins'], sys.exit.__self__ is sys, [].append.__self__)\nlen.__module__ = 'mine'\nprint(len.__module__, sys.modules['builtins'].len.__module__)\ndel len.__module__\nprint(len.__module__)\nlen.__module__ = 'builtins'\nfor act in (lambda: str.join.__module__, lambda: str.join.__self__):\n    try:\n        act()\n    except AttributeError as e:\n        print(e)\nimport _abc\nprint(_abc._abc_init.__module__, _abc._abc_init.__qualname__, _abc._abc_init.__self__ is _abc, repr(_abc._abc_init))\n"),
    ('impl_is_an_object', "from abc import ABC\nclass A(ABC):\n    pass\nimpl = A._abc_impl\nt = type(impl)\nprint(t.__name__, t.__qualname__, t.__module__, t, t.__doc__, t.__bases__, t.__mro__, type(t))\nprint(type(t()).__name__, type(t(1, 2, k=3)).__name__, repr(impl).startswith('<_abc._abc_data object at '), str(impl).startswith('<_abc._abc_data object at '), impl == impl, impl != impl, impl == t(), hash(impl) == hash(impl), bool(impl))\nfor f in (lambda: setattr(impl, 'x', 1), lambda: impl.x, lambda: t.__new__(int), lambda: t.__new__(1), lambda: t.__new__()):\n    try:\n        f()\n    except (AttributeError, TypeError) as e:\n        print(type(e).__name__, e)\nt.note = 5\nprint(impl.note, t.note)\ndel t.note\n"),
    ('impl_is_not_a_base', "from abc import ABC\nclass A(ABC):\n    pass\ntry:\n    class X(type(A._abc_impl)):\n        pass\n    print('made')\nexcept TypeError as e:\n    print(e)\n"),
    ('cache_token', "import abc, _abc\nfrom abc import ABC\nt = abc.get_cache_token()\nclass A(ABC):\n    pass\nprint(abc.get_cache_token() == t, abc.get_cache_token is _abc.get_cache_token)\nclass B:\n    pass\nA.register(B)\nprint(abc.get_cache_token() - t)\nA.register(B)\nprint(abc.get_cache_token() - t)\nA._abc_registry_clear()\nprint(abc.get_cache_token() - t, issubclass(B, A))\nA._abc_caches_clear()\nprint(issubclass(B, A))\n"),
    ('abstractmethod_keeps_its_function', "from abc import abstractmethod, ABC\ndef f():\n    pass\nprint(abstractmethod(f) is f, f.__isabstractmethod__)\nfor v in (1, 'x', None):\n    try:\n        abstractmethod(v)\n    except AttributeError as e:\n        print(type(e).__name__)\nclass A(ABC):\n    @abstractmethod\n    def f(self):\n        '''doc'''\n        return 'base'\nclass B(A):\n    def f(self):\n        return super().f() + ' and child'\nprint(B().f(), A.f.__doc__, A.f.__name__, A.f.__isabstractmethod__)\n"),
    ('init_subclass_and_set_name_run_before_init', "from abc import ABC, abstractmethod\nORDER = []\nclass D:\n    def __set_name__(self, o, n):\n        ORDER.append(('set_name', n, hasattr(o, '_abc_impl')))\nclass A(ABC):\n    def __init_subclass__(cls):\n        ORDER.append(('init_subclass', cls.__name__, '_abc_impl' in vars(cls), '__abstractmethods__' in vars(cls)))\nclass B(A):\n    d = D()\n    @abstractmethod\n    def f(self):\n        pass\nprint(ORDER)\n"),
    ('final_types', "import types\nfor base in (bool, type(None), range, slice, type(len), type(lambda: 0), type(iter([])), type({}.keys()), type(NotImplemented), type(...), types.MappingProxyType):\n    try:\n        class X(base):\n            pass\n        print('made', base.__name__)\n    except TypeError as e:\n        print(e)\n"),
    ('update_abstractmethods', "import abc\nfrom abc import ABC, abstractmethod\nclass A(ABC):\n    @abstractmethod\n    def f(self):\n        pass\nclass B(A):\n    pass\nB.g = abstractmethod(lambda self: None)\nprint(B.__abstractmethods__ == {'f'})\nabc.update_abstractmethods(B)\nprint(B.__abstractmethods__ == {'f', 'g'})\nB.f = lambda self: 1\nB.g = lambda self: 2\nabc.update_abstractmethods(B)\nprint(B.__abstractmethods__ == set(), B().f(), B().g())\nprint(abc.update_abstractmethods(int) is int, abc.update_abstractmethods(object) is object)\n"),
    ('metaclass_conflict', "from abc import ABC, ABCMeta\nclass M(type):\n    pass\nclass P(metaclass=M):\n    pass\ntry:\n    class Q(ABC, P):\n        pass\nexcept TypeError as e:\n    print(e)\nclass MM(ABCMeta, M):\n    pass\nclass R(ABC, P, metaclass=MM):\n    pass\nprint(type(R).__name__, [c.__name__ for c in R.__mro__])\n"),
    ('abc_of_builtin_bases', "from abc import ABC, abstractmethod\nclass L(dict, ABC):\n    @abstractmethod\n    def f(self):\n        pass\ntry:\n    L()\nexcept TypeError as e:\n    print(e)\nclass M(L):\n    def f(self):\n        return len(self)\nm = M({1: 2})\nprint(m.f(), isinstance(m, L), isinstance(m, dict), issubclass(M, ABC), issubclass(dict, ABC))\n"),
    ('exception_abc', "from abc import ABC, abstractmethod\nclass E(Exception, ABC):\n    @abstractmethod\n    def f(self):\n        pass\ntry:\n    E()\nexcept TypeError as e:\n    print(e)\nclass F(E):\n    def f(self):\n        return 1\ntry:\n    raise F('x')\nexcept E as e:\n    print(type(e).__name__, e.args, e.f())\nE.register(KeyError)\ntry:\n    raise KeyError('k')\nexcept E:\n    print('not caught by a virtual base')\nexcept KeyError as e:\n    print('KeyError', e.args)\n"),
]


def _refused(src: str, reason: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert got.returncode == 70 and reason in got.stderr, got


def test_get_dump_refuses_what_it_would_show_as_weak_references() -> None:
    """A set with entries holds classes here and weak references there: refused until step 3c."""
    _refused("from abc import ABC\nclass A(ABC):\n    pass\nA.register(int)\nA._dump_registry()\n", "_abc._get_dump")


def test_the_subclasses_of_a_builtin_are_refused() -> None:
    """CPython's list names classes of its own, which a compiled program does not have."""
    _refused("print(object.__subclasses__())\n", "the subclasses of the built-in type 'object'")


def pytest_generate_tests(metafunc: Any) -> None:
    if "message" in metafunc.fixturenames:
        metafunc.parametrize("message", MESSAGES, ids=[name for name, _ in MESSAGES])


def test_as_cpython(message: tuple[str, str]) -> None:
    same(message[1])


if __name__ == "__main__":
    for item in MESSAGES:
        test_as_cpython(item)
    test_get_dump_refuses_what_it_would_show_as_weak_references()
    test_the_subclasses_of_a_builtin_are_refused()
