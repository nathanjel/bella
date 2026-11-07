# clause: C-3-46
# spec: section 3 (Functions, reflection; E-02 as narrowed in v0.14)
# status: P1
# source: dialect specification v0.14, Objects/codeobject.c (code_memberlist), Objects/funcobject.c (func_get_code, func_set_code)
"""A function's __code__ and __closure__: the names and counts a code object carries (co_name, co_qualname, co_firstlineno with a
decorator, the argument counts, co_nlocals, co_varnames in CPython's order with an inlined comprehension's variables, co_cellvars,
co_freevars, co_flags for every kind of function), one code object per function, the closure's cells and cell_contents, and what
dataclasses builds on them (slots=True repointing the __class__ cell). The bytecode side (co_code, co_consts, replace, code(...))
is excluded (E-02, E-07) and not here."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001, UP046, UP047
import dataclasses


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def f(a, b=1, /, c=2, *args, d, e=3, **kw):  # type: ignore[no-untyped-def]
    """doc"""
    x = a + c
    y = [i for i in range(3)]
    return x, y, d, e, args, kw


def outer():  # type: ignore[no-untyped-def]
    v = 1

    def inner():  # type: ignore[no-untyped-def]
        return v

    return inner


def gen():  # type: ignore[no-untyped-def]
    yield 1


async def co():  # type: ignore[no-untyped-def]
    pass


async def ag():  # type: ignore[no-untyped-def]
    yield 1


lam = lambda q: q  # noqa: E731


class C:
    def meth(self):  # type: ignore[no-untyped-def]
        return __class__  # type: ignore[name-defined]

    def plain(self):  # type: ignore[no-untyped-def]
        return 1

    @staticmethod
    def st():  # type: ignore[no-untyped-def]
        pass

    @property
    def prop(self):  # type: ignore[no-untyped-def]
        return 1


inner = outer()  # type: ignore[no-untyped-call]
for fn in (f, outer, inner, gen, co, ag, lam, C.meth, C.plain, C.st, C.prop.fget):  # type: ignore[attr-defined]
    c = fn.__code__
    print(c.co_name, c.co_qualname, c.co_firstlineno, c.co_argcount, c.co_posonlyargcount, c.co_kwonlyargcount, c.co_nlocals, c.co_varnames, c.co_cellvars, c.co_freevars, hex(c.co_flags), c.co_filename.rsplit("/", 1)[-1], type(c).__name__, type(c).__module__, fn.__code__ is fn.__code__, fn.__code__ == fn.__code__, fn.__closure__ if fn.__closure__ is None else [type(x).__name__ for x in fn.__closure__])
print(inner.__closure__[0].cell_contents, C.meth.__closure__[0].cell_contents is C, failed(lambda: setattr(f, "__code__", 1)), failed(lambda: delattr(f, "__code__")), f.__code__ == gen.__code__, hash(f.__code__) == hash(f.__code__), f.__code__ != gen.__code__, f.__code__.co_name == "f", f(1, d=4), inner(), outer.__code__.co_cellvars, type(inner.__closure__[0]).__name__, failed(lambda: inner.__closure__[0].cell_contents == 1))  # type: ignore[index,no-untyped-call]
cell = outer.__closure__ if outer.__closure__ is not None else inner.__closure__[0]
print(cell.cell_contents, failed(lambda: setattr(cell, "cell_contents", 5)), inner(), failed(lambda: delattr(cell, "cell_contents")), failed(lambda: cell.cell_contents), failed(lambda: inner()))  # type: ignore[no-untyped-call,union-attr]


@dataclasses.dataclass(slots=True)
class S:
    a: int
    b: str = "x"

    def twice(self):  # type: ignore[no-untyped-def]
        return self.a * 2

    def me(self):  # type: ignore[no-untyped-def]
        return super().__repr__()[:3]


s = S(2)
print(s, s.twice(), S.__slots__, S.__dictoffset__, S.__weakrefoffset__, hasattr(s, "__dict__"), s.me(), dataclasses.fields(S)[1].default, failed(lambda: setattr(s, "zz", 1)), S.twice.__code__.co_freevars, S.me.__code__.co_freevars, S.me.__closure__[0].cell_contents is S)  # type: ignore[index,no-untyped-call]

