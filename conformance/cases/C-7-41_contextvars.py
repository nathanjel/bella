# clause: C-7-41
# spec: section 7
# status: P1
# source: dialect specification section 7, Python/context.c, Lib/contextvars.py
"""The _contextvars module behind contextvars: ContextVar (its constructor's parsing, get with the three fallbacks, set and the Token
it returns, reset with the used, other-variable and other-context errors), Token (MISSING, the context manager), Context (a mapping
of variables with copy-on-write sharing: copy_context and copy snapshot the current variables, run enters the context so that sets
inside land in it and are kept after, re-entering is refused, equality compares values), the iterator types, and the shapes."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _contextvars as m
import contextvars
import weakref


def t(f):  # type: ignore[no-untyped-def]
    try:
        v = f()
    except Exception as e:
        return type(e).__name__ + ": " + hide(str(e))  # type: ignore[no-untyped-call]
    return hide(repr(v))  # type: ignore[no-untyped-call]


def hide(s):  # type: ignore[no-untyped-def]
    out = []
    i = 0
    while i < len(s):
        j = s.find(" at 0x", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j] + " at 0x…")
        k = j + 6
        while k < len(s) and s[k] in "0123456789abcdef":
            k += 1
        i = k
    return "".join(out)


print("module:", m.__doc__, [(n, type(getattr(m, n)).__name__) for n in sorted(dir(m)) if not n.startswith("__")])
print("Context:", [(n, type(getattr(m.Context, n)).__name__) for n in sorted(vars(m.Context)) if not n.startswith("_") or n in ("__eq__", "__ne__", "__hash__", "__iter__", "__getitem__", "__contains__", "__len__", "__new__", "__doc__")], m.Context.__module__, m.Context.__qualname__)
print("ContextVar:", [(n, type(getattr(m.ContextVar, n)).__name__) for n in sorted(vars(m.ContextVar)) if not n.startswith("_") or n in ("__class_getitem__", "__doc__", "__hash__", "__new__", "__repr__")], m.ContextVar.__module__)
print("Token:", [(n, type(getattr(m.Token, n)).__name__) for n in sorted(vars(m.Token)) if not n.startswith("_") or n in ("__class_getitem__", "__doc__", "__hash__", "__new__", "__repr__", "__enter__", "__exit__")], m.Token.__module__)
v = m.ContextVar("v")  # type: ignore[var-annotated]
d = m.ContextVar("d", default=5)
print("new:", t(lambda: m.ContextVar()), t(lambda: m.ContextVar(1)), t(lambda: m.ContextVar("a", 2)), t(lambda: m.ContextVar("a", default=2, x=3)), t(lambda: m.ContextVar(name="a")), t(lambda: m.ContextVar("a", "b", "c")), t(lambda: m.ContextVar(b"a")), t(lambda: m.ContextVar("a", x=3)), t(lambda: m.ContextVar("a", default=1, default2=2)), t(lambda: m.ContextVar(x=3)), t(lambda: m.ContextVar("a", default=None)), t(lambda: m.ContextVar("a", default=None).get()))  # type: ignore[call-overload,no-untyped-call]
print("var:", t(lambda: v), t(lambda: d), v.name, t(lambda: setattr(v, "name", "x")), t(lambda: delattr(v, "name")), t(lambda: v.default), t(lambda: v.get()), t(lambda: v.get(1)), t(lambda: v.get(1, 2)), t(lambda: v.get(default=1)), t(lambda: d.get()), t(lambda: d.get(None)), t(lambda: d.get(1)), t(lambda: hash(v) == hash(v)), t(lambda: hash(v) == hash(m.ContextVar("v"))), t(lambda: v == v), t(lambda: v == m.ContextVar("v")), t(lambda: setattr(v, "x", 1)))  # type: ignore[attr-defined,call-overload,no-untyped-call]
tok = v.set(10)
print("set:", t(lambda: tok), t(lambda: tok.var is v), t(lambda: tok.old_value), t(lambda: type(tok.old_value).__name__), t(lambda: type(tok.old_value).__module__), t(lambda: type(tok.old_value).__qualname__), t(lambda: m.Token.MISSING is tok.old_value), t(lambda: m.Token.MISSING), t(lambda: type(m.Token.MISSING)()), t(lambda: type(m.Token.MISSING).__mro__), t(lambda: bool(m.Token.MISSING)), t(lambda: v.get()), t(lambda: setattr(tok, "var", 1)), t(lambda: setattr(tok, "old_value", 1)), t(lambda: setattr(tok, "x", 1)), t(lambda: hash(tok)))  # type: ignore[no-untyped-call]
tok2 = v.set(20)
print("reset:", t(lambda: tok2.old_value), t(lambda: v.get()), t(lambda: v.reset(tok2)), t(lambda: v.get()), t(lambda: tok2), t(lambda: v.reset(tok2)), t(lambda: d.reset(tok)), t(lambda: v.reset(5)), t(lambda: v.reset()), t(lambda: v.set()), t(lambda: v.set(1, 2)), t(lambda: v.set(value=1)), t(lambda: v.reset(token=tok)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print("reset 2:", t(lambda: v.reset(tok)), t(lambda: v.get()), t(lambda: v.get("dflt")))  # type: ignore[no-untyped-call]
ctx = m.copy_context()
print("context:", t(lambda: type(ctx)), t(lambda: len(ctx)), t(lambda: list(ctx)), t(lambda: ctx[v]), t(lambda: ctx[d]), t(lambda: v in ctx), t(lambda: d in ctx), t(lambda: 5 in ctx), t(lambda: ctx[5]), t(lambda: ctx.get(5)), t(lambda: ctx.get(v)), t(lambda: ctx.get(v, 3)), t(lambda: ctx.get(v, 3, 4)), t(lambda: ctx.get()), t(lambda: ctx.get(key=v)), t(lambda: list(ctx.keys())), t(lambda: list(ctx.values())), t(lambda: list(ctx.items())), t(lambda: type(ctx.keys()).__name__), t(lambda: type(ctx.keys()).__module__), t(lambda: type(ctx.values()).__name__), t(lambda: type(ctx.items()).__name__), t(lambda: type(iter(ctx)).__name__), t(lambda: next(iter(ctx))), t(lambda: hash(ctx)), t(lambda: m.Context[int]), t(lambda: m.ContextVar[int]), t(lambda: m.Token[int]), t(lambda: type(ctx.keys())()), t(lambda: iter(ctx.keys()) is not None), t(lambda: len(ctx.keys())), t(lambda: ctx.keys(1)), t(lambda: ctx.items(x=1)), t(lambda: ctx.copy(1)), t(lambda: ctx.values(1)))  # type: ignore[call-arg,call-overload,comparison-overlap,index,misc,no-untyped-call]
v.set(1)
print("copies:", t(lambda: ctx[v]), t(lambda: m.copy_context()[v]), t(lambda: ctx == m.copy_context()), t(lambda: ctx != m.copy_context()), t(lambda: ctx == ctx.copy()), t(lambda: ctx < ctx), t(lambda: ctx == 5), t(lambda: ctx != 5), t(lambda: ctx.copy() is ctx), t(lambda: m.Context() == m.Context()), t(lambda: len(m.Context())), t(lambda: m.Context(1)), t(lambda: m.Context(x=1)), t(lambda: m.Token()), t(lambda: m.Token.__new__(m.Token)), t(lambda: m.copy_context(1)), t(lambda: m.copy_context(x=1)), t(lambda: m.Context.__new__(m.Context, 1)), t(lambda: m.ContextVar.__new__(m.ContextVar, "q").name))  # type: ignore[call-arg,no-untyped-call,operator]


def inner(*a, **k):  # type: ignore[no-untyped-def]
    v.set(99)
    return (a, k, v.get(), m.copy_context()[v], len(m.copy_context()))


print("run:", t(lambda: ctx.run(inner, 1, 2, k=3)), t(lambda: v.get()), t(lambda: ctx[v]), t(lambda: ctx.run()), t(lambda: ctx.run(5)), t(lambda: type(ctx.run(lambda: ctx.run(inner)))), t(lambda: ctx.run(lambda: m.copy_context() == ctx)), t(lambda: ctx.run(lambda: m.copy_context() is ctx)), t(lambda: ctx.run(lambda: v.set(7)).old_value), t(lambda: ctx[v]), t(lambda: ctx.run(lambda: v.reset(tok))), t(lambda: ctx.run(callable=1)), t(lambda: ctx.run(lambda **k: k, a=1)))  # type: ignore[arg-type,call-arg,no-untyped-call]


def resets():  # type: ignore[no-untyped-def]
    t1 = v.set(5)
    return (v.get(), m.copy_context()[v], v.reset(t1), v.get(), t1, m.copy_context().get(v, "gone"))  # type: ignore[func-returns-value]


print("resets:", t(resets), t(lambda: v.get()))  # type: ignore[no-untyped-call]


def with_block():  # type: ignore[no-untyped-def]
    with v.set(123) as tk:
        inside = (v.get(), tk.var is v)
    return inside, v.get()


def with_raise():  # type: ignore[no-untyped-def]
    try:
        with v.set(321):
            raise ValueError("inside")
    except ValueError as e:
        return str(e), v.get()
    return None  # type: ignore[unreachable]


print("with:", t(with_block), t(with_raise), t(lambda: tok.__enter__() is tok), t(lambda: tok.__exit__(None, None, None)), t(lambda: tok.__exit__()), t(lambda: tok.__exit__(1, 2)), t(lambda: tok.__enter__(1)), t(lambda: tok.__exit__(1, 2, 3, 4)))  # type: ignore[arg-type,call-arg,no-untyped-call]
w = m.ContextVar("w")  # type: ignore[var-annotated]
v.set([1])
w.set(2)
a = m.copy_context()
v.set([1])
b = m.copy_context()
print("equality:", a == b, a == a.copy(), a is a.copy(), a.copy() == a, len(a), t(lambda: a.run(lambda: w.set(3)) and None), a == b, a[w], b[w], t(lambda: sorted(x.name for x in a)), t(lambda: sorted(x.name for x in a.keys())), t(lambda: sorted(repr(x) for x in a.values())), t(lambda: sorted((k.name, repr(x)) for k, x in a.items())), t(lambda: len(a.items())), t(lambda: len(a.values())))  # type: ignore[no-untyped-call]


class Eq:
    def __eq__(self, o):  # type: ignore[no-untyped-def]
        return True

    __hash__ = None  # type: ignore[assignment]


e = m.ContextVar("e")  # type: ignore[var-annotated]
e.set(Eq())
c1 = m.copy_context()
e.set(Eq())
c2 = m.copy_context()
print("values compare:", c1 == c2, c1 != c2, m.Context.__eq__(c1, 5), m.Context.__eq__(c1, c2), t(lambda: m.Context.__eq__(5, c1)), t(lambda: m.Context.__contains__(5, v)), t(lambda: m.ContextVar.get(5)), t(lambda: m.Context.run(5, print)), t(lambda: m.Token.__enter__(5)))  # type: ignore[arg-type,call-overload,no-untyped-call,operator,type-var]


def nested():  # type: ignore[no-untyped-def]
    outer = m.copy_context()

    def inner2():  # type: ignore[no-untyped-def]
        v.set("in")
        return (v.get(), m.copy_context() == outer, len(m.copy_context()))
    r = outer.run(inner2)
    return r, v.get(), outer[v], outer.run(lambda: v.get()), len(outer)


print("nested:", t(nested))  # type: ignore[no-untyped-call]
fresh = m.Context()
d_ = m.ContextVar("d", default="D")


def in_fresh():  # type: ignore[no-untyped-def]
    return (v.get("none"), d_.get(), len(m.copy_context()), v.set(1).old_value, len(m.copy_context()), fresh[v])


print("fresh:", t(lambda: fresh.run(in_fresh)), t(lambda: fresh[v]), t(lambda: v.get()), t(lambda: d_.get()), t(lambda: d_ in m.copy_context()))  # type: ignore[no-untyped-call]
tk = v.set(5)
print("other context:", t(lambda: fresh.run(lambda: v.reset(tk))), t(lambda: m.Context().run(lambda: v.reset(tk))), t(lambda: tk), t(lambda: v.reset(tk)), t(lambda: v.reset(tk)))  # type: ignore[no-untyped-call]
x = m.ContextVar("x")  # type: ignore[var-annotated]
print("del:", t(lambda: x.get()), t(lambda: m.Context().run(lambda: x.set(1) and x.get())), t(lambda: x.get()))  # type: ignore[no-untyped-call]
tkx = x.set(1)
ctx2 = m.copy_context()
print("del 2:", t(lambda: ctx2.run(lambda: x.reset(tkx))), t(lambda: x.reset(tkx)), t(lambda: x.get()), t(lambda: x in m.copy_context()), t(lambda: x in ctx2))  # type: ignore[no-untyped-call]


def reenter():  # type: ignore[no-untyped-def]
    return ctx2.run(lambda: ctx2.run(len))  # type: ignore[call-arg]


print("reenter:", t(reenter), t(lambda: ctx2.run(lambda: m.Context().run(lambda: ctx2.run(len)))))  # type: ignore[call-arg,no-untyped-call]
e2 = m.ContextVar("e2")  # type: ignore[var-annotated]
try:
    e2.get()
except LookupError as ex:
    print("lookup:", ex.args[0] is e2, type(ex).__name__, len(ex.args))
try:
    ctx[e2]
except KeyError as ex:
    print("key:", ex.args[0] is e2, type(ex).__name__)
print("subclass:", t(lambda: type("V2", (m.ContextVar,), {})), t(lambda: type("C2", (m.Context,), {})), t(lambda: type("T2", (m.Token,), {})))  # type: ignore[no-untyped-call]
print("weak:", t(lambda: weakref.ref(ctx) is not None), t(lambda: weakref.ref(v)), t(lambda: weakref.ref(tok)))  # type: ignore[no-untyped-call]
print("package:", contextvars.__all__, contextvars.ContextVar is m.ContextVar, contextvars.copy_context is m.copy_context, type(contextvars.copy_context()).__name__)
