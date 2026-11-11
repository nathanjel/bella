# clause: C-3-55
# spec: section 3
# status: P1
# source: Objects/descrobject.c (property_members, property_getsetlist), Objects/funcobject.c (sm_memberlist, cm_memberlist, sm_getsetlist, cm_getsetlist)
"""The members of property, staticmethod and classmethod. A property's getter, setter and deleter are read-only members and it
has no __dict__, so nothing else can be put on one but its __doc__ and its __name__; a staticmethod's and a classmethod's
function is a read-only member under two names, and they have a __dict__ that starts with the function's names and takes
whatever a program adds. What each type's own namespace holds, and of what kind. Then what the three do with what they hold:
a property's name (the last class to hold it, or its getter's) and its docstring (the getter's unless one is given, and where a
subclass keeps it), the copies getter, setter and deleter make, what the constructors take, __init__ called again, __get__ by
hand, __isabstractmethod__, the annotations a staticmethod and a classmethod take from their function, and pickling."""
# ruff: noqa: E501
import copy
from collections.abc import Callable


def f() -> None:
    pass


def documented(self: object) -> int:
    """the getter's"""
    return 1


def plain(self: object) -> int:
    return 2


def store(self: object, value: object) -> None:
    pass


def annotated(a: int) -> str:
    return ""


class Nameless:
    def __call__(self, obj: object) -> int:
        return 7


class Abstract:
    __isabstractmethod__ = True


class NotAbstract:
    __isabstractmethod__ = 0


class Refusing:
    @property
    def __isabstractmethod__(self) -> bool:
        raise ValueError("asked")


class Sub(property):
    """the subclass's"""


class SlottedSub(property):
    __slots__ = ()


class DocSlot(property):
    __slots__ = ("__doc__",)


class Static(staticmethod):  # type: ignore[type-arg]
    pass


class Recording(classmethod):  # type: ignore[type-arg]
    def __setattr__(self, name: str, value: object) -> None:
        SEEN.append(name)
        object.__setattr__(self, name, value)


class TwoArguments(staticmethod):  # type: ignore[type-arg]
    def __init__(self, func: Callable[[], None], extra: int) -> None:
        super().__init__(func)


SEEN: list[str] = []


class Holder:
    x = property(plain)
    y = x
    anon = property()
    only_set = property(None, store)
    nameless = property(Nameless())
    s = staticmethod(lambda *a, **k: (a, k))
    c = classmethod(lambda cls, *a: (cls.__name__, a))
    callable_object = classmethod(Nameless())  # type: ignore[var-annotated]


def m(g: Callable[[], object]) -> str:
    try:
        return repr(g())
    except Exception as e:
        return type(e).__name__


def attempt(obj: object, name: str) -> str:
    out = []
    for act in (lambda: setattr(obj, name, 5), lambda: delattr(obj, name)):
        try:
            act()  # type: ignore[no-untyped-call]
            out.append("ok")
        except AttributeError as e:
            out.append("AttributeError (none)" if e.name is None and e.obj is None else "AttributeError (name and obj)" if e.obj is obj else "AttributeError (other)")
        except Exception as e:
            out.append(type(e).__name__)
    return name + ": set " + out[0] + ", del " + out[1]


def main() -> None:
    p = property(f)  # type: ignore[arg-type]
    s = staticmethod(f)
    c = classmethod(f)  # type: ignore[arg-type, var-annotated]
    print("property has:", sorted(n for n in vars(property) if not n.startswith("__") or n in ("__doc__", "__isabstractmethod__", "__name__", "__set_name__")))
    print("staticmethod has:", sorted(vars(staticmethod)))
    print("classmethod has:", sorted(vars(classmethod)))
    for cls, names in ((property, ("fget", "fset", "fdel", "__doc__", "__isabstractmethod__", "__name__")), (staticmethod, ("__func__", "__wrapped__", "__isabstractmethod__", "__dict__")),
                       (classmethod, ("__func__", "__wrapped__", "__isabstractmethod__", "__dict__"))):
        print(cls.__name__ + ":", [(n, type(vars(cls)[n]).__name__, type(getattr(cls, n)).__name__) for n in names])
    print("read:", p.fget is f, p.fset, p.fdel, s.__func__ is f, s.__wrapped__ is f, c.__func__ is f, c.__wrapped__ is f, vars(s), sorted(vars(c)), m(lambda: vars(p)), hasattr(p, "__dict__"),  # type: ignore[comparison-overlap]
          property.fget.__get__(p) is f, staticmethod.__func__.__get__(s) is f, p.__doc__, s.__name__, m(lambda: p.__name__))  # type: ignore[union-attr]
    print("property:", [attempt(property(f), n) for n in ("fget", "fset", "fdel", "__doc__", "__name__", "x", "__isabstractmethod__")])  # type: ignore[arg-type]
    print("staticmethod:", [attempt(staticmethod(f), n) for n in ("__func__", "__wrapped__", "x", "__name__", "__doc__", "__isabstractmethod__", "__dict__")])
    print("classmethod:", [attempt(classmethod(f), n) for n in ("__func__", "__wrapped__", "x", "__name__", "__doc__", "__isabstractmethod__", "__dict__")])  # type: ignore[arg-type]

    # a property's name: the last class to hold it says, else its getter does; set, set to None, deleted
    loose = property(None)
    named = property(plain)
    print("names:", Holder.x.__name__, Holder.y.__name__, Holder.anon.__name__, Holder.only_set.__name__, Holder.nameless.__name__, m(lambda: loose.__name__), named.__name__, m(lambda: property(Nameless()).__name__))
    named.__name__ = "given"
    after = [named.__name__]
    named.__name__ = None  # type: ignore[assignment]
    after.append(named.__name__)
    del named.__name__
    after.append(named.__name__)
    del named.__name__
    loose.__set_name__(Holder, 5)  # type: ignore[attr-defined]
    print("a name set, None, deleted, deleted again:", after, named.__name__, "__set_name__ by hand:", loose.__name__, m(lambda: loose.__set_name__(Holder)), m(lambda: loose.__set_name__(Holder, "n", 3)),  # type: ignore[attr-defined]
          m(lambda: loose.__set_name__(owner=Holder, name="n")))  # type: ignore[attr-defined]

    # what a property refuses for want of an accessor, and its three slots called by hand
    holder = Holder()
    print("no accessor:", m(lambda: holder.anon), m(lambda: setattr(holder, "x", 1)), m(lambda: delattr(holder, "x")), m(lambda: holder.only_set), m(lambda: delattr(holder, "only_set")), holder.x, holder.nameless,
          m(lambda: loose.__get__(holder)), m(lambda: loose.__set__(holder, 1)), m(lambda: loose.__delete__(holder)), loose.__get__(None, Holder) is loose, m(lambda: loose.__get__(None, None)), m(lambda: loose.__get__(None)),
          m(lambda: loose.__get__()), m(lambda: loose.__set__(holder)), m(lambda: loose.__delete__()))  # type: ignore[call-arg, call-overload]

    # the docstring: the getter's unless one is given; a copy asks the new getter when the old one's was the getter's
    from_getter = property(documented)
    given = property(documented, doc="given")
    print("doc:", from_getter.__doc__, given.__doc__, property(plain).__doc__, property(doc=5).__doc__, from_getter.setter(store).__doc__, from_getter.getter(plain).__doc__, given.getter(plain).__doc__,  # type: ignore[arg-type]
          from_getter.getter(None).__doc__, property(None, store, None, "only a doc").__doc__)  # type: ignore[arg-type]
    from_getter.__doc__ = "written"
    written = [from_getter.__doc__, from_getter.getter(plain).__doc__, from_getter.setter(store).__doc__]
    del from_getter.__doc__
    print("doc written, then deleted:", written, from_getter.__doc__, m(lambda: delattr(from_getter, "__doc__")), from_getter.getter(documented).__doc__)

    # the copies: the old accessors where None is given, the name carried, the subclass kept
    setter_copy = Holder.x.setter(store)
    print("copies:", setter_copy.__name__, setter_copy.fget is plain, setter_copy.fset is store, setter_copy.fdel, Holder.x.getter(None).fget is plain, Holder.x.deleter(store).fdel is store, type(setter_copy).__name__,  # type: ignore[arg-type, comparison-overlap]
          type(Sub(plain).setter(store)).__name__, Holder.x.fset, m(lambda: Holder.x.setter()), m(lambda: Holder.x.getter(1, 2)), m(lambda: Holder.x.deleter(fdel=plain)), m(lambda: property.getter()), m(lambda: property.getter(5, plain)))  # type: ignore[call-arg, arg-type]

    # a subclass keeps the docstring in its own dict or slot; with neither it is dropped, unless it is the getter's
    sub = Sub(documented)
    sub.extra = 1  # type: ignore[attr-defined]
    print("subclass:", sub.__doc__, vars(sub), Sub(plain).__doc__, vars(Sub(plain)), Sub(plain, doc="x").__doc__, sub.setter(store).__doc__, Sub.__doc__, sub.fget is documented, m(lambda: setattr(sub, "fget", 1)),
          m(lambda: SlottedSub(plain).__doc__), m(lambda: SlottedSub(documented)), m(lambda: SlottedSub(plain, doc="x").__doc__), m(lambda: DocSlot(documented).__doc__), m(lambda: DocSlot(plain).__doc__), m(lambda: vars(SlottedSub(plain))))

    # what the constructors take, and __new__ by hand
    print("construct:", m(lambda: staticmethod()), m(lambda: staticmethod(f, f)), m(lambda: staticmethod(function=f)), m(lambda: classmethod()), m(lambda: classmethod(f, f)), m(lambda: classmethod(function=f)),  # type: ignore[arg-type, call-arg]
          m(lambda: property(plain, store, store, "d", 5)), m(lambda: property(nope=1)), m(lambda: property(plain, fget=plain)), type(property(fget=plain, fset=store, fdel=store, doc="d")).__name__,  # type: ignore[arg-type, call-arg, misc]
          staticmethod(1).__func__, classmethod(None).__func__, m(lambda: staticmethod.__new__(staticmethod)), m(lambda: classmethod.__new__(classmethod)), property.__new__(property).fget,  # type: ignore[arg-type]
          property.__new__(property, 1, 2, 3, 4, 5, 6).fget, staticmethod.__new__(staticmethod, f).__func__ is f, m(lambda: staticmethod.__new__(int, f)), m(lambda: property.__new__(int)), m(lambda: TwoArguments(f, 1)))  # type: ignore[call-arg]

    # __init__ again: a new function, and its names; a property is as new
    s2 = staticmethod(f)
    s2.__init__(plain)  # type: ignore[misc]
    c2 = classmethod(f)  # type: ignore[arg-type, var-annotated]
    c2.__init__(plain)  # type: ignore[misc]
    p2 = property(documented, store, doc="given")
    p2.__name__ = "kept?"
    p2.__init__(plain)  # type: ignore[misc]
    print("init again:", s2.__func__ is plain, s2.__name__, c2.__func__ is plain, c2.__qualname__, sorted(vars(s2)), p2.fget is plain, p2.fset, p2.__doc__, p2.__name__, m(lambda: s2.__init__()), m(lambda: c2.__init__(f, f)),  # type: ignore[comparison-overlap, misc]
          m(lambda: p2.__init__(1, 2, 3, 4, 5)))  # type: ignore[misc]

    # subclasses: the names go through the subclass's own __setattr__, once
    recorded = Recording(f)  # type: ignore[arg-type]
    print("subclasses:", type(Static(f)).__name__, Static(f).__func__ is f, vars(Static(f)) == vars(staticmethod(f)), SEEN, vars(recorded) == vars(classmethod(f)), repr(Static(len)), repr(staticmethod(len)), repr(classmethod(len)))  # type: ignore[arg-type]

    # calling and binding
    static, cm = Holder.__dict__["s"], Holder.__dict__["c"]
    print("call and bind:", Holder.s(1, x=2), Holder().s(), static(3), Holder.c(1), Holder().c(), m(lambda: cm(1)), cm.__get__(None, int)(), cm.__get__(5)(), m(lambda: cm.__get__()), m(lambda: static.__get__()),
          m(lambda: static.__get__(None)), static.__get__(1, 2) is static.__func__, static.__get__(None, 2) is static.__func__, static.__get__(1) is static.__func__, m(lambda: cm.__get__(None)), Holder.callable_object(),
          type(Holder.callable_object).__name__, callable(staticmethod(f)), callable(classmethod(f)), callable(property(plain)))  # type: ignore[arg-type]

    # __isabstractmethod__: of any of a property's three, of the function; whatever asking raises
    print("abstract:", property(Abstract()).__isabstractmethod__, property(None, Abstract()).__isabstractmethod__, property(None, None, Abstract()).__isabstractmethod__, property(NotAbstract()).__isabstractmethod__,  # type: ignore[arg-type]
          property().__isabstractmethod__, m(lambda: property(Refusing()).__isabstractmethod__), staticmethod(Abstract()).__isabstractmethod__, classmethod(NotAbstract()).__isabstractmethod__,  # type: ignore[arg-type]
          m(lambda: staticmethod(Refusing()).__isabstractmethod__), type(staticmethod(Refusing())).__name__)  # type: ignore[arg-type]

    # the annotations of the function, taken into the dict when first asked; set and deleted there
    sa = staticmethod(annotated)
    ca = classmethod(annotated)  # type: ignore[arg-type, var-annotated]
    before = sorted(vars(sa))
    print("annotations:", sa.__annotations__, "__annotations__" in vars(sa), ca.__annotations__ is annotated.__annotations__, callable(sa.__annotate__), before, sorted(vars(sa)), m(lambda: staticmethod(1).__annotations__),  # type: ignore[arg-type]
          m(lambda: classmethod(1).__annotate__))  # type: ignore[arg-type]
    sa.__annotations__ = {"q": 1}
    print("annotations set, then deleted:", sa.__annotations__, annotated.__annotations__ == {"a": int, "return": str}, m(lambda: delattr(sa, "__annotations__")), "__annotations__" in vars(sa), m(lambda: delattr(sa, "__annotations__")),
          m(lambda: delattr(classmethod(1), "__annotate__")))  # type: ignore[arg-type]

    # the types themselves
    print("the types:", staticmethod[int], classmethod[int, str], m(lambda: property[int]), type(staticmethod[int]).__name__, str(property.__doc__).split("\n")[0], str(staticmethod.__doc__).split("\n")[0],  # type: ignore[misc]
          str(classmethod.__doc__).split("\n")[0], property.__name__, property.__qualname__, property.__module__, staticmethod.__module__, staticmethod.__mro__, m(lambda: setattr(property, "x", 1)), m(lambda: setattr(staticmethod, "__doc__", "d")),
          "__module__" in vars(property), "__module__" in vars(classmethod))
    print("kinds:", [type(v).__name__ for v in (property.getter, property.__get__, property.__set__, property.__delete__, property.__init__, property.__set_name__, staticmethod.__call__, staticmethod.__get__, staticmethod.__repr__,  # type: ignore[attr-defined]
                                                vars(staticmethod)["__new__"], vars(classmethod)["__class_getitem__"], vars(staticmethod)["__annotations__"], vars(classmethod)["__annotate__"])],
          property.getter.__doc__, property.fget.__doc__, property.fget.__name__, property.fget.__objclass__ is property, repr(property.fget), repr(staticmethod.__func__), repr(staticmethod.__isabstractmethod__),  # type: ignore[union-attr]
          repr(vars(property)["__name__"]), repr(vars(property)["__doc__"]), vars(staticmethod)["__dict__"].__name__, property.__getattribute__ is object.__getattribute__)

    # compared and hashed by identity; never weakly referenced, pickled or copied
    p3 = property(plain)
    print("identity:", property(plain) == property(plain), hash(p3) == hash(p3), staticmethod(f) == staticmethod(f), bool(property()), m(lambda: property() < property()), m(lambda: len(staticmethod(f))),  # type: ignore[operator, arg-type]
          copy.copy(p3) is p3, copy.deepcopy(p3) is p3, m(lambda: staticmethod(len).__reduce_ex__(2)), m(lambda: property(len).__reduce_ex__(2)), m(lambda: copy.copy(staticmethod(len))), m(lambda: property(len).__reduce_ex__(0)),
          m(lambda: Sub(len).__reduce_ex__(2)), m(lambda: Static(len).__reduce_ex__(2)))


if __name__ == "__main__":
    main()
