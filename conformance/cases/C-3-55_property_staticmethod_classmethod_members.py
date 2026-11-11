# clause: C-3-55
# spec: section 3
# status: P1
# source: Objects/descrobject.c (property_members, property_getsetlist), Objects/funcobject.c (sm_memberlist, cm_memberlist, sm_getsetlist, cm_getsetlist)
"""The members of property, staticmethod and classmethod. A property's getter, setter and deleter are read-only members and it
has no __dict__, so nothing else can be put on one but its __doc__ and its __name__; a staticmethod's and a classmethod's
function is a read-only member under two names, and they have a __dict__ that starts with the function's names and takes
whatever a program adds. What each type's own namespace holds, and of what kind."""
# ruff: noqa: E501
from collections.abc import Callable


def f() -> None:
    pass


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


if __name__ == "__main__":
    main()
