"""property, staticmethod and classmethod compiled, against CPython on the same machine: the words of their errors, which case
C-3-55 does not compare (its rows say the type of each), and with them a slotted class's own names, which its instances cannot
set (case C-3-54). The three are written in Python (runtime/prelude/builtins.py) from Objects/descrobject.c and
Objects/funcobject.c; runtime/tests/test_prelude.py runs that file under CPython against the built-ins."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""import abc


def m(g):
    try:
        return repr(g())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)


def f():
    '''f's doc'''


def g(self):
    return 1


def setter(self, v):
    self.v = v


class NoName:
    def __call__(self, obj):
        return 7


class NoneName:
    __name__ = None

    def __call__(self, obj):
        return 7


print("repr:", repr(staticmethod(f))[:22], repr(classmethod(f))[:21], type(repr(property(f))).__name__)
print("construct:", m(lambda: staticmethod()), m(lambda: staticmethod(f, f)), m(lambda: staticmethod(function=f)), m(lambda: classmethod()), m(lambda: classmethod(f, f)), m(lambda: classmethod(function=f)),
      m(lambda: property(f, f, f, "d", 5)), m(lambda: property(nope=1)), m(lambda: type(property(fget=f, fset=g, fdel=g, doc="d")).__name__), m(lambda: staticmethod(1).__func__), m(lambda: classmethod(None).__func__))
print("new and init:", m(lambda: staticmethod.__new__(staticmethod)), m(lambda: classmethod.__new__(classmethod)), m(lambda: type(property.__new__(property)).__name__), m(lambda: property.__new__(property).fget),
      m(lambda: staticmethod.__new__(staticmethod, f).__func__ is f), m(lambda: staticmethod.__new__(int, f)), m(lambda: property.__new__(property, 1, 2, 3, 4, 5, 6).fget))
s = staticmethod(f)
s.__init__(g)
c = classmethod(f)
c.__init__(g)
print("init again:", s.__func__ is g, s.__name__, s.__doc__, c.__func__ is g, c.__qualname__, m(lambda: s.__init__()), m(lambda: c.__init__(f, f)))
p = property(f, doc="given")
p.__init__(g)
print("property init again:", p.fget is g, p.__doc__, p.fset, m(lambda: p.__init__(1, 2, 3, 4, 5)))

# the name
class A:
    x = property(g)
    y = x
    anon = property()
    only_set = property(None, setter)
    unnamed = property(NoName())
    none_named = property(NoneName())

a = A()
print("names:", A.x.__name__, A.y.__name__, m(lambda: A.anon.__name__), A.only_set.__name__, A.unnamed.__name__, A.none_named.__name__)
print("refusals:", m(lambda: a.anon), m(lambda: setattr(a, "x", 1)), m(lambda: delattr(a, "x")), m(lambda: setattr(a, "unnamed", 1)), m(lambda: setattr(a, "none_named", 1)), m(lambda: delattr(a, "only_set")), m(lambda: a.only_set))
loose = property(None)
print("loose:", m(lambda: loose.__get__(a)), m(lambda: loose.__set__(a, 1)), m(lambda: loose.__delete__(a)), m(lambda: loose.__name__), loose.__get__(None, A) is loose, m(lambda: loose.__get__(None, None)), m(lambda: loose.__get__()),
      m(lambda: loose.__set__(a)), m(lambda: loose.__delete__()), m(lambda: loose.__set_name__(A)), m(lambda: loose.__set_name__(A, "n", 3)), loose.__set_name__(A, 5), m(lambda: loose.__name__), m(lambda: loose.__get__(a)))
named = property(g)
named.__name__ = "given"
print("name set:", named.__name__, m(lambda: setattr(named, "__name__", None)), named.__name__, m(lambda: delattr(named, "__name__")), named.__name__, m(lambda: delattr(named, "__name__")), named.__name__)
copy = A.x.setter(setter)
print("copies:", copy.__name__, copy.fget is g, copy.fset is setter, copy.fdel, A.x.getter(None).fget is g, A.x.deleter(g).fdel is g, type(copy).__name__, m(lambda: A.x.setter()), m(lambda: A.x.getter(1, 2)), m(lambda: A.x.deleter(fdel=g)))

# the doc
pd = property(f)
pe = property(f, doc="explicit")
print("doc:", pd.__doc__, pe.__doc__, pd.setter(g).__doc__, pd.getter(g).__doc__, pe.getter(g).__doc__, property(g).__doc__, property(doc=5).__doc__, pd.getter(None).__doc__)
pd.__doc__ = "written"
print("doc written:", pd.__doc__, pd.getter(g).__doc__, pd.setter(g).__doc__)
del pd.__doc__
print("doc deleted:", pd.__doc__, m(lambda: delattr(pd, "__doc__")), pd.getter(f).__doc__)

class Sub(property):
    '''sub's doc'''

class Slotted(property):
    __slots__ = ()

class WithDocSlot(property):
    __slots__ = ("__doc__",)

sp = Sub(f)
print("subclass:", sp.__doc__, vars(sp), Sub(g).__doc__, vars(Sub(g)), Sub(f, doc="x").__doc__, type(sp.setter(g)).__name__, sp.setter(g).__doc__, Sub.__doc__, sp.fget is f, m(lambda: setattr(sp, "fget", 1)), m(lambda: setattr(sp, "extra", 1)), sp.extra)
print("slotted subclass:", m(lambda: Slotted(g).__doc__), m(lambda: Slotted(f)), m(lambda: Slotted(g, doc="x").__doc__), m(lambda: WithDocSlot(f).__doc__), m(lambda: WithDocSlot(g).__doc__))

class SM(staticmethod):
    def __init__(self, func, extra):
        super().__init__(func)
        self.extra = extra

print("sm subclass:", m(lambda: SM(f, 1)), m(lambda: SM(f)))

class SM2(staticmethod):
    pass

class CM2(classmethod):
    def __setattr__(self, name, value):
        seen.append(name)
        object.__setattr__(self, name, value)

seen = []
cm2 = CM2(f)
print("subclasses:", type(SM2(f)).__name__, SM2(f).__func__ is f, vars(SM2(f)) == vars(staticmethod(f)), seen, vars(cm2) == vars(classmethod(f)))

# calling and binding
class B:
    s = staticmethod(lambda *a, **k: (a, k))
    c = classmethod(lambda cls, *a: (cls.__name__, a))
    callable_cm = classmethod(NoName())

print("call:", B.s(1, x=2), B().s(), B.__dict__["s"](3), B.c(1), B().c(), m(lambda: B.__dict__["c"](1)), B.__dict__["c"].__get__(None, int)(), B.__dict__["c"].__get__(5)(), m(lambda: B.__dict__["c"].__get__()),
      m(lambda: B.__dict__["s"].__get__()), m(lambda: B.__dict__["s"].__get__(None) is B.__dict__["s"].__func__), B.__dict__["s"].__get__(1, 2) is B.__dict__["s"].__func__, B.__dict__["s"].__get__(None, 2) is B.__dict__["s"].__func__, m(lambda: B.__dict__["c"].__get__(None)), m(lambda: B.callable_cm()), type(B.callable_cm).__name__,
      callable(staticmethod(f)), callable(classmethod(f)), callable(property(f)))

# abstract
class Abstract:
    __isabstractmethod__ = True

class Raises:
    @property
    def __isabstractmethod__(self):
        raise ValueError("no")

class Falsy:
    __isabstractmethod__ = 0

print("abstract:", property(Abstract()).__isabstractmethod__, property(None, Abstract()).__isabstractmethod__, property(None, None, Abstract()).__isabstractmethod__, property(Falsy()).__isabstractmethod__, property().__isabstractmethod__,
      m(lambda: property(Raises()).__isabstractmethod__), staticmethod(Abstract()).__isabstractmethod__, classmethod(Falsy()).__isabstractmethod__, m(lambda: staticmethod(Raises()).__isabstractmethod__),
      abc.abstractmethod(f) is f, staticmethod(f).__isabstractmethod__, m(lambda: type(staticmethod(Raises())).__name__))

# annotations
def ann(a: int) -> str:
    return ""

sa = staticmethod(ann)
ca = classmethod(ann)
print("annotations:", sa.__annotations__, "__annotations__" in vars(sa), ca.__annotations__ is ann.__annotations__, callable(sa.__annotate__), sorted(vars(sa)), m(lambda: staticmethod(1).__annotations__), m(lambda: classmethod(1).__annotate__))
sa.__annotations__ = {"q": 1}
print("annotations set:", sa.__annotations__, ann.__annotations__ == {"a": int, "return": str}, m(lambda: delattr(sa, "__annotations__")), "__annotations__" in vars(sa), m(lambda: delattr(sa, "__annotations__")), m(lambda: delattr(sa, "__annotations__")),
      m(lambda: delattr(classmethod(1), "__annotate__")))
print("generic:", staticmethod[int], classmethod[int, str], m(lambda: property[int]), type(staticmethod[int]).__name__)
print("the types:", property.__doc__[:19], staticmethod.__doc__[:25], classmethod.__doc__[:24], property.__name__, property.__qualname__, property.__module__, staticmethod.__mro__, property.__flags__ & (1 << 10) != 0,
      m(lambda: setattr(property, "x", 1)), m(lambda: setattr(staticmethod, "__doc__", "d")))
print("methods:", type(property.getter).__name__, type(property.__get__).__name__, type(property.__set__).__name__, type(property.__delete__).__name__, type(property.__init__).__name__, type(property.__set_name__).__name__,
      type(staticmethod.__call__).__name__, type(staticmethod.__get__).__name__, type(staticmethod.__repr__).__name__, type(vars(staticmethod)["__new__"]).__name__, type(vars(classmethod)["__class_getitem__"]).__name__,
      type(vars(staticmethod)["__annotations__"]).__name__, type(vars(classmethod)["__annotate__"]).__name__, property.getter.__doc__, property.fget.__doc__, property.fget.__name__, property.fget.__objclass__ is property, repr(property.fget),
      repr(staticmethod.__func__), repr(staticmethod.__isabstractmethod__), repr(property.__dict__["__name__"]), repr(property.__dict__["__doc__"]), staticmethod.__dict__["__dict__"].__name__)
print("hash and eq:", property(f) == property(f), hash(pe) == hash(pe), staticmethod(f) == staticmethod(f), bool(property()), m(lambda: property() < property()), m(lambda: len(staticmethod(f))))
import copy as copying
pc = property(g)
print("copying:", copying.copy(pc) is pc, copying.deepcopy(pc) is pc, m(lambda: staticmethod(len).__reduce_ex__(2)), m(lambda: property(len).__reduce_ex__(2)), m(lambda: type(copying.copy(staticmethod(len))).__name__),
      m(lambda: property(len).__reduce_ex__(0)), m(lambda: Sub(len).__reduce_ex__(2)), m(lambda: SM2(len).__reduce_ex__(2)))
print("getattribute:", property.__getattribute__ is object.__getattribute__, type(vars(property).get("__getattribute__")).__name__, sorted(n for n in vars(property) if n.startswith("__") and n not in ("__doc__", "__isabstractmethod__", "__name__", "__set_name__")))
import weakref
print("weak:", m(lambda: type(weakref.ref(property())).__name__), m(lambda: type(weakref.ref(staticmethod(f))).__name__), m(lambda: type(weakref.ref(Sub())).__name__))
import inspect
print("inspect:", inspect.isdatadescriptor(property()), inspect.ismethoddescriptor(staticmethod(f)), inspect.ismethoddescriptor(classmethod(f)), inspect.unwrap(staticmethod(f)) is f, m(lambda: str(inspect.signature(staticmethod(ann)))),
      inspect.getdoc(property(f)), m(lambda: inspect.isfunction(staticmethod(f))))
import functools
print("functools:", functools.cached_property.__mro__, m(lambda: functools.singledispatchmethod(staticmethod(f)).func.__func__ is f))


class S:
    __slots__ = ("a",)
    x = 1

    def meth(self):
        pass

def carried(act, target):
    try:
        act()
    except AttributeError as e:
        return ("AttributeError", str(e), e.name, e.obj is target)
    return "ok"

s_ = S()
print("slotted class:", carried(lambda: setattr(s_, "x", 2), s_), carried(lambda: delattr(s_, "x"), s_), carried(lambda: setattr(s_, "meth", 2), s_), carried(lambda: delattr(s_, "meth"), s_), carried(lambda: setattr(s_, "nope", 2), s_),
      carried(lambda: delattr(s_, "nope"), s_), carried(lambda: delattr(s_, "a"), s_), carried(lambda: setattr(s_, "__doc__", "d"), s_), carried(lambda: setattr(s_, "__module__", "d"), s_))
"""

# An object without a __dict__ asked to set or delete a name: "is read-only" where its type has the name, "no attribute" where
# it has not, with "and no __dict__ for setting new attributes" unless the class has a __setattr__ of its own; a C type's
# __module__ is its tp_name's and no name of the type. Over the built-in types, and through object.__setattr__ as well.
READ_ONLY = r"""import types
import typing
import itertools
import operator


class Slotted:
    __slots__ = ("x",)
    shared = 1

    def meth(self):
        pass


def show(label, target, name):
    for action in ("set", "del"):
        try:
            if action == "set":
                setattr(target, name, 1)
            else:
                delattr(target, name)
            out = "ok"
        except Exception as e:
            out = (type(e).__name__, str(e), getattr(e, "name", "(no name)"), getattr(e, "obj", None) is target)
        print(label, action, out)


u = int | str
for name in ("__module__", "__doc__", "__args__", "__or__", "__name__", "__qualname__", "__origin__", "new"):
    show("union", u, name)
ga = list[int]
for name in ("__module__", "__doc__", "__args__", "__origin__", "__mro_entries__"):
    show("alias", ga, name)
for obj, label in ((1, "int"), ("s", "str"), ((), "tuple"), (1.5, "float"), (b"", "bytes"), (frozenset(), "frozenset"), (range(1), "range"), (object(), "object"), (None, "None"), (len, "builtin"), (str.upper, "methdesc"),
                   (itertools.count(), "count"), (operator.itemgetter(1), "itemgetter"), (Slotted(), "Slotted"), (iter([]), "list_iterator"), ({}.keys(), "dict_keys"), (slice(1), "slice"), (..., "ellipsis"),
                   (typing.TypeVar("T"), "TypeVar"), (types.MappingProxyType({}), "mappingproxy"), (enumerate([]), "enumerate"), (zip(), "zip")):
    for name in ("__module__", "__doc__", "__hash__", "__eq__", "__init__", "__class_getitem__", "__len__", "__name__", "__qualname__", "__dict__", "__weakref__", "__slots__", "meth", "shared"):
        show(label, obj, name)


class Guarded:
    __slots__ = ("x",)
    shared = 1

    def meth(self):
        pass

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        super().__delattr__(name)


for name in ("shared", "meth", "x", "__doc__", "__module__", "new", "__slots__"):
    show("guarded", Guarded(), name)
    for act in (lambda: object.__setattr__(Slotted(), name, 1), lambda: object.__delattr__(Slotted(), name)):
        try:
            act()
            print("direct", name, "ok")
        except Exception as e:
            print("direct", name, type(e).__name__, e, e.name, e.obj is None)
"""


def test_the_three_descriptors_say_what_cpythons_say() -> None:
    same(MESSAGES)


def test_an_object_without_a_dict_refuses_in_cpythons_words() -> None:
    same(READ_ONLY)


if __name__ == "__main__":
    test_the_three_descriptors_say_what_cpythons_say()
    test_an_object_without_a_dict_refuses_in_cpythons_words()
