"""Gate 0 task 4, step A3: class statements, lowered as CPython's compiler lowers them (a body
function run by build_class, runtime/prelude/build_class.py), eval1 against CPython.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_classes
"""
from __future__ import annotations

from pipeline.tests.test_frontend_eval1 import both

BUILD = '''
trace = []
def t(name, value=None):
    trace.append(name)
    return value
def deco(name):
    trace.append("evaluate " + name)
    def apply(c):
        trace.append("apply " + name + " to " + c.__name__)
        return c
    return apply
class Recorder(dict):
    def __setitem__(self, key, value):
        trace.append("store " + key)
        super().__setitem__(key, value)
class Meta(type):
    @classmethod
    def __prepare__(mcls, name, bases, **kw):
        trace.append("prepare " + name + " " + repr(sorted(kw)))
        return Recorder()
    def __new__(mcls, name, bases, ns, **kw):
        trace.append("new " + name + " " + repr(sorted(kw)))
        return super().__new__(mcls, name, bases, dict(ns))
    def __init__(cls, name, bases, ns, **kw):
        super().__init__(name, bases, ns)
class Base:
    def __init_subclass__(cls, /, flavour=None, **kw):
        trace.append("init_subclass " + cls.__name__ + " " + repr(flavour))
        super().__init_subclass__(**kw)
class Named:
    def __set_name__(self, owner, name):
        trace.append("set_name " + owner.__name__ + "." + name)
@deco("outer")
@deco("inner")
class C(t("base", Base), metaclass=t("meta", Meta), flavour=t("kw", "sour")):
    t("body")
    x = 1
    attr = Named()
    @staticmethod
    def s():
        return "static"
print(trace)
trace.clear()
print(type(C).__name__, C.s(), C.x, [k.__name__ for k in C.__mro__], sorted([k for k in vars(C) if not k.startswith("__")]))
class Sub(C, flavour="sweet"):
    pass
print(trace)
trace.clear()
'''

METACLASSES = '''
def error(make):
    try:
        make()
    except Exception as exc:
        return type(exc).__name__ + ": " + str(exc)
    return "no error"
class M1(type): pass
class M2(type): pass
class M3(M1): pass
class A(metaclass=M1): pass
class B(metaclass=M2): pass
class Derived(metaclass=M3): pass
def conflict():
    class X(A, B): pass
print(error(conflict))
class Y(A, Derived): pass
print(type(Y).__name__)
def function_meta(name, bases, ns, **kw):
    return (name, len(bases), sorted([k for k in ns]), kw)
class Z(A, metaclass=function_meta, extra=1):
    q = 2
print(Z)
class BadPrepare(type):
    @classmethod
    def __prepare__(mcls, name, bases):
        return 42
def bad():
    class W(metaclass=BadPrepare): pass
print(error(bad))
class NotAMapping:
    __prepare__ = staticmethod(lambda name, bases: 1)
def bad2():
    class W(metaclass=NotAMapping()): pass
print(error(bad2))
class Entries:
    def __mro_entries__(self, bases):
        return (int, A)
class E(Entries(), object):
    pass
print([k.__name__ for k in E.__mro__], E.__orig_bases__[1] is object, "__orig_bases__" in vars(E))
class BadEntries:
    def __mro_entries__(self, bases):
        return [int]
def bad3():
    class W(BadEntries()): pass
print(error(bad3))
bases = (int,)
kw = {"metaclass": type}
class Starred(*bases, **kw):
    pass
print(Starred(5) + 1, type(Starred).__name__)
class DropsCell(type):
    def __new__(mcls, name, bases, ns):
        kept = {}
        for k, v in ns.items():
            if k != "__classcell__":
                kept[k] = v
        return super().__new__(mcls, name, bases, kept)
def dropped():
    class W(metaclass=DropsCell):
        def m(self):
            return __class__
print(error(dropped))
class Swaps(type):
    def __new__(mcls, name, bases, ns):
        made = super().__new__(mcls, name, bases, ns)
        return super().__new__(mcls, name + "2", bases, {})
def swapped():
    class W(metaclass=Swaps):
        def m(self):
            return __class__
print(error(swapped))
'''

SCOPES = '''
x = "global x"
def enclosing():
    v = "enclosing v"
    w = "enclosing w"
    class K:
        seen = v                  # free in the class: the namespace, then the enclosing cell
        w = "class w"
        print(seen, w, x)
        def method(self):
            return v, w, x
        found = [v + str(i) for i in range(2)]
        try:
            print(v)
        finally:
            pass
    return K
K = enclosing()
print(K().method(), K.found, K.seen, K.w)
def late():
    v = "enclosing"
    class L:
        try:
            print(v)
        except NameError as exc:
            print("NameError", exc.name)
        v = "class"
    return L
late()
class G:
    global gx
    gx = "set from a class"
    y = 1
    del y
    try:
        del never
    except NameError as exc:
        print("NameError", exc.name)
    names = sorted(locals())
print(gx, hasattr(G, "y"), G.names)
def counter():
    n = 0
    class Counting:
        nonlocal n
        n = n + 1
    return n
print(counter())
base = "module base"
class Comprehension:
    base = 10
    items = [i for i in range(base)][:3]      # the outermost iterable is the class's
    inner = [base for i in range(1)]          # the element is not: the module's
print(Comprehension.items, Comprehension.inner)
'''

NAMES = '''
class C:
    """  The doc.
        Second line."""
    __private = 1
    _C__other = 2
    __dunder__ = 3
    def __method(self, __p):
        self.__s = __p
        return self.__private
    def call(self):
        return self.__method(5), self.__s
    class __Inner:
        __inner = 4
        def m(self):
            return self.__inner
    def nested(self):
        def helper(self):
            self.from_nested = 1
        helper(self)
        return self.from_nested
    def aug(self):
        self.augmented += 1
    def ann(self):
        self.annotated: int = 1
    def unpacked(self):
        self.a, (self.b, other) = 1, (2, 3)
        for self.loop in range(1):
            pass
print(sorted([k for k in vars(C) if not k.startswith("__")]))
print(C().call(), C._C__Inner.__name__, C._C__Inner.__qualname__, C._C__Inner().m())
print(C.__static_attributes__, C._C__Inner.__static_attributes__, repr(C.__doc__), C.__qualname__)
class _:
    __kept = 1
class __Under:
    __y = 1
print(sorted([k for k in vars(_) if "kept" in k]), sorted([k for k in vars(__Under) if "y" in k]))
def outer():
    class InFunction:
        class Nested:
            def m(self):
                pass
    return InFunction
print(outer().__qualname__, outer().Nested.__qualname__, outer().Nested.m.__qualname__)
class NoDoc:
    pass
print(NoDoc.__doc__, NoDoc.__firstlineno__)
def deco(c):
    return c
@deco

class Decorated:
    pass
print(Decorated.__firstlineno__)
'''

SUPER = '''
def error(make):
    try:
        make()
    except Exception as exc:
        return type(exc).__name__ + ": " + str(exc)
    return "no error"
class A:
    def who(self):
        return "A"
    @classmethod
    def make(cls):
        return "A.make " + cls.__name__
class B(A):
    def who(self):
        return "B>" + super().who()
    @classmethod
    def make(cls):
        return "B>" + super().make()
    def nested(self):
        def inner():
            return super().who()
        return inner
    def lambda_super(self):
        return (lambda: super())
    def via_class(self):
        return __class__.__name__
    @staticmethod
    def static():
        return super().who()
print(B().who(), B.make(), B().via_class())
print(error(B().nested()), error(B().lambda_super()), error(B.static))
class C(B):
    def who(self):
        return "C>" + super().who()
print(C().who(), C.make())
def free_function(self):
    return super().who()
print(error(lambda: free_function(B())))
class Rebound(A):
    def who(self):
        return super()               # a super that is not the builtin is called with no arguments
real = super
super = lambda *args: ("rebound", args)
print(Rebound().who())
super = real
print(type(Rebound().who()).__name__)
class Early:
    def m(self):
        return __class__
    try:
        m(None)
    except NameError as exc:
        print("NameError", exc.name)
'''


def check(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_build_class_order_metaclass_prepare_and_hooks() -> None:
    check(BUILD)


def test_metaclass_resolution_mro_entries_and_class_cell_checks() -> None:
    check(METACLASSES)


def test_class_body_scopes() -> None:
    check(SCOPES)


def test_class_namespace_names_mangling_and_static_attributes() -> None:
    check(NAMES)


def test_zero_argument_super_and_class_cell() -> None:
    check(SUPER)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
