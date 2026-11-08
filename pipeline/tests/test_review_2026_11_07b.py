"""Reviews A14 (Codex astra-low) and G14 (gemini-3.8-flash-high) of 2026-11-07, RL-358 on: every finding's program and what stands
around it, compiled, against CPython."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

JSON_AND_CODE_OBJECTS = r"""
from __future__ import annotations
import json, _json
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e) + ("  notes=" + repr(e.__notes__) if getattr(e, "__notes__", None) else "")
class F(float):
    def __ne__(self, other): return True
    def __eq__(self, other): return False
    def __lt__(self, other): return True
    def __gt__(self, other): return True
    __hash__ = float.__hash__
print(json.dumps(F(1.5)), json.dumps([F(float("inf"))]), m(lambda: json.dumps(F(float("nan")), allow_nan=False)), json.dumps({F(2.0): 1}))
d = {"a": object()}
def default(obj):
    d["b"] = 2
    return 1
print(m(lambda: json.dumps(d, default=default)))
d2 = {"a": object(), "b": 1}
def default2(obj):
    del d2["b"]
    return 1
print(m(lambda: json.dumps(d2, default=default2)))
class T(tuple):
    def __iter__(self): return iter((9,))
print(json.dumps(T((1, 2))), json.dumps([T((1, 2))]))
class Error(Exception):
    def add_note(self, note):
        print("override called")
def bad(obj):
    raise Error("bad")
print(m(lambda: json.dumps([object()], default=bad)))
def f():
    return [(lambda: i) for i in range(2)]
def g():
    x = 1
    r = [(lambda: i + x) for i in range(2)]
    y = 2
    return r
def h():
    a = [i for i in range(2)]
    b = [(lambda: j) for j in range(2)]
    return a, b
print(f.__code__.co_varnames, f.__code__.co_cellvars, g.__code__.co_varnames, g.__code__.co_cellvars, h.__code__.co_varnames, h.__code__.co_cellvars, f()[1](), g()[0]())
def gen[T]():
    pass
def outer():
    class C:
        def meth(self): pass
    return C
print(bool(gen.__code__.co_flags & 0x1000000), bool(gen.__code__.co_flags & 0x10), hex(outer().meth.__code__.co_flags), hex(outer.__code__.co_flags), hex(f.__code__.co_flags))
def outer2():
    x = 1
    def inner():
        return x
    return inner
fn = outer2()
print(fn.__closure__ is fn.__closure__, fn.__closure__ == fn.__closure__, outer2.__closure__ is None)
print(m(lambda: _json.scanstring('"x"', 10**100)), m(lambda: _json.scanstring('"x"', -(10**100))), m(lambda: json.JSONDecoder().scan_once("1", 10**100)), m(lambda: _json.make_encoder(None, 1, 2, None, "a", "b", 1, 1, 1)(1, 10**100)), m(lambda: _json.scanstring('"x"', 2**63 - 1)))
"""


def test_json_encoder_edges_and_code_objects_rl_358_365() -> None:
    """A float subclass's comparisons, a dict mutated by default(), a tuple subclass's __iter__, notes through the base method, an
    inlined comprehension's cells in co_varnames and co_cellvars, CO_NESTED and CO_FUTURE_ANNOTATIONS, one __closure__ tuple, an
    index beyond ssize_t."""
    same(JSON_AND_CODE_OBJECTS)


INLINED_COMPREHENSIONS = r"""
def f(p):
    b = 1
    y = 2
    c1 = [(lambda: z) for z in range(2)]
    c2 = [(lambda: a) for a in range(2)]
    def inner():
        return p + b + y
    return inner, c1, c2

print(f.__code__.co_varnames, f.__code__.co_cellvars, f.__code__.co_nlocals)


def g():
    r = [(x := i * 2) for i in range(2)]
    return r, x

print(g.__code__.co_varnames, g.__code__.co_cellvars, g.__code__.co_nlocals)


def h():
    r = [(x := i * 2) for i in range(2)]
    return lambda: x

print(h.__code__.co_varnames, h.__code__.co_cellvars, h.__code__.co_nlocals)


def k(q):
    s = {(w := i) for i in range(2)}
    t = [(lambda: w) for _ in range(2)]
    return s, t, q

print(k.__code__.co_varnames, k.__code__.co_cellvars, k.__code__.co_nlocals)


def m():
    a = [[(lambda: j) for j in range(2)] for i in range(2)]
    def inner():
        return a
    return inner

print(m.__code__.co_varnames, m.__code__.co_cellvars, m.__code__.co_nlocals)


def n():
    r = [[(x := j) for j in range(2)] for i in range(2)]
    return r, x

print(n.__code__.co_varnames, n.__code__.co_cellvars, n.__code__.co_nlocals)


def o():
    r = [i for i in [j for j in range(2)]]
    return r

print(o.__code__.co_varnames, o.__code__.co_cellvars, o.__code__.co_nlocals)


def q():
    r = [(x := i) for i in range(2)]
    class C:
        v = x
    return r, C

print(q.__code__.co_varnames, q.__code__.co_cellvars, q.__code__.co_nlocals)


def u(p):
    s = [(y := i, w := i + 1) for i in range(2) if (v := i)]
    return s, y, w, v, p

print(u.__code__.co_varnames, u.__code__.co_cellvars, u.__code__.co_nlocals)


def v():
    d = {(k := i): (w := i + 1) for i in range(2) for j in [i] if (c := j)}
    return d, k, w, c

print(v.__code__.co_varnames, v.__code__.co_cellvars, v.__code__.co_nlocals)
"""


def test_inlined_comprehension_names_rl_366_367() -> None:
    """co_cellvars in co_varnames' order for the cells that are fast locals too (a parameter, an inlined comprehension's captured
    variable), the rest sorted; a comprehension's walrus target is a fast local unless a nested function captures it, in the order
    the loop binds the targets; nested comprehensions list the outer's names first; the first iterable's comprehension before the
    comprehension it feeds."""
    same(INLINED_COMPREHENSIONS)


if __name__ == "__main__":
    test_json_encoder_edges_and_code_objects_rl_358_365()
    test_inlined_comprehension_names_rl_366_367()
