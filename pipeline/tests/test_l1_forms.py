"""Gate 0 task 4, step A5: several and starred targets with CPython's unpacking, starred, set and
dict displays built as codegen builds them, set and dict comprehensions, generator expressions,
walrus targets in comprehensions, generator functions on real generator objects, and async
defs whose coroutines refuse to run; eval1 against CPython.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_forms
"""
from __future__ import annotations

from pipeline.l1.eval1 import Interpreter
from pipeline.l1.frontend import lower
from pipeline.l1.grammar import Refused
from pipeline.tests.test_frontend_eval1 import both

FORMS = 'trace = []\nclass H:\n    def __init__(self, n): self.n = n\n    def __hash__(self):\n        trace.append("hash " + str(self.n)); return self.n\n    def __eq__(self, o): return self is o\ndef v(name, x):\n    trace.append(name); return x\ndef err(f):\n    try: f()\n    except Exception as e: return type(e).__name__ + ": " + str(e)\na = b = c = [1]\nprint(a is b is c)\nx, *y, z = range(5)\nprint(x, y, z)\n*s, = "ab"\nprint(s)\nfirst, (second, *third) = 1, [2, 3, 4]\nprint(first, second, third)\ndef bad2():\n    p, q = [1, 2, 3]\ndef bad3():\n    p, q = iter([1, 2, 3])\ndef bad4():\n    p, *q, r = [1]\ndef bad5():\n    p, q = 5\ndef bad6():\n    p, q, r = (1, 2)\nimport itertools\ndef bad7():\n    p, q = itertools.count()\nprint(err(bad2), err(bad3), err(bad4), err(bad5), err(bad6), err(bad7), sep="\\n")\nprint([*range(3), 4, *"ab"], (*[1], 2), sorted({*[3, 1], 2}))\ns1 = {v("a", H(1)), v("b", H(2))}\nprint(trace); trace.clear()\ns2 = {v("a", H(1)), *v("b", [H(2)]), v("c", H(3))}\nprint(trace); trace.clear()\nd = {v("k1", H(1)): v("v1", 1), **v("m", {"z": 0}), v("k2", H(2)): v("v2", 2)}\nprint(trace, len(d)); trace.clear()\nbig2 = {H(0): v("v0", 0), H(1): v("v1", 1), H(2): 2, H(3): 3, H(4): 4, H(5): 5, H(6): 6, H(7): 7, H(8): 8, H(9): 9, H(10): 10, H(11): 11, H(12): 12, H(13): 13, H(14): 14, H(15): 15, H(16): 16}\nprint(trace); trace.clear()\nprint(err(lambda: {**1}), err(lambda: [*1]), err(lambda: {*1}))\n'

GENERATORS = 'def err(f):\n    try:\n        return f()\n    except Exception as e:\n        return type(e).__name__ + ": " + str(e)\ndef counter(n):\n    total = 0\n    for i in range(n):\n        got = yield i\n        if got is not None:\n            total += got\n    return total\ng = counter(3)\nprint(type(g).__name__, g.__name__, g.__qualname__, next(g), g.send(10), g.send(5))\ntry:\n    g.send(1)\nexcept StopIteration as stop:\n    print("returned", stop.value)\ndef delegate():\n    result = yield from counter(2)\n    yield "result " + str(result)\nprint(list(delegate()))\ndef guarded():\n    try:\n        yield 1\n        yield 2\n    finally:\n        print("finally runs")\ngg = guarded()\nprint(next(gg)); gg.close(); print("closed")\ndef catcher():\n    while True:\n        try:\n            yield\n        except ValueError as e:\n            print("caught", e.args)\nc = catcher(); next(c); c.throw(ValueError("x")); c.close()\nit = iter([])\ndef leaks():\n    yield next(it)\nprint(err(lambda: list(leaks())))\ndef catches_inside():\n    try:\n        x = (yield 1) + next(it)\n    except StopIteration:\n        yield "caught StopIteration inside"\nprint(list(catches_inside()))\nsquares = (x * x for x in range(4) if x)\nprint(type(squares).__name__, squares.__name__, squares.__qualname__, list(squares))\ndef outer():\n    return (y for y in [1])\nprint(outer().__qualname__)\nprint(sorted({x % 3 for x in range(10)}), {k: v for k, v in [("a", 1), ("b", 2)]})\ndef walrus(xs):\n    ys = [last := x * 2 for x in xs]\n    return ys, last\nprint(walrus([1, 2]))\ntotal = [s := 0]\nrunning = [s := s + x for x in [1, 2, 3]]\nprint(running, s)\nk = lambda xs: [y * 2 for y in xs]\nprint(k([1, 2]))\nlg = lambda: (yield 5)\nprint(type(lg()).__name__, list(lg()))\ndef ctx():\n    try:\n        raise KeyError("outer")\n    except KeyError:\n        def inner():\n            yield\n            raise ValueError("in gen")\n        gi = inner(); next(gi)\n        try:\n            next(gi)\n        except ValueError as e:\n            print("context", type(e.__context__).__name__)\nctx()\nasync def co(a, b=2):\n    await a\ncoro = co(1)\nprint(type(coro).__name__, coro.__name__, coro.__qualname__)\ncoro.close()\nprint(err(lambda: co()))\n'


def check(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_assignment_and_display_forms() -> None:
    check(FORMS)


def test_generators_comprehensions_and_async_defs() -> None:
    check(GENERATORS)


def test_running_a_coroutine_is_refused_and_no_handler_catches_it() -> None:
    src = """
async def co():
    pass
log = []
try:
    try:
        co().send(None)
    except BaseException:
        log.append("caught")
finally:
    log.append("finally")
"""
    interp = Interpreter()
    try:
        interp.run_module(lower(src, "<test>"))
    except Refused as exc:
        assert "[P2+]" in str(exc)
    else:
        raise AssertionError("running a coroutine was not refused")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
