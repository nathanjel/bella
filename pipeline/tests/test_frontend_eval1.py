"""Differential tests: frontend + eval1 against CPython, and the pass manager.

Run under pytest or directly: python3 -m pipeline.tests.test_frontend_eval1
"""
from __future__ import annotations

import builtins
import contextlib
import io
from typing import Any

from pipeline.l1.eval1 import Interpreter
from pipeline.l1.frontend import FRONTEND_PASSES, lower
from pipeline.l1.grammar import Unsupported
from pipeline.l1.wf import WellFormednessError, check
from pipeline.passes import manager
from pipeline.passes.spec import REGISTRY, Discharge, Fact, Level, Obligation, PassSpec, RegisteredPass


class CM:
    """A context manager with an observable protocol, injected into both worlds."""

    def __init__(self, tag: str, swallow: bool = False) -> None:
        self.tag, self.swallow = tag, swallow

    def __enter__(self) -> str:
        print("enter", self.tag)
        return self.tag

    def __exit__(self, t: Any, v: Any, tb: Any) -> bool:
        print("exit", self.tag, None if t is None else t.__name__)
        return self.swallow


def both(src: str, extra: dict[str, Any] | None = None) -> tuple[str, str]:
    extra = extra or {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m = lower(src, "<test>")
        check(m, frozenset(extra))
        Interpreter(dict(vars(builtins)) | extra).run_module(m)
    ref = io.StringIO()
    with contextlib.redirect_stdout(ref):
        # dont_inherit: this module's `from __future__ import annotations` must not reach the program
        exec(compile(src, "<cpython>", "exec", dont_inherit=True), {"__name__": "__main__", **extra})  # noqa: S102 -- the oracle
    return buf.getvalue(), ref.getvalue()


PROGRAM = '''
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

total = 0
for i in range(10):
    total += fib(i)
print("fib sum", total, 1 < 2 < 3, 3 > 2 > 5)
xs = [x * x for x in range(6) if x % 2 == 0]
print(xs, f"{total:>5}|{xs!r}|{total!s:^6}|")
d = {"a": 1}
try:
    print(d["b"])
except KeyError as e:
    print("KeyError", e.args)
finally:
    print("finally")

def outer():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    inc(); inc()
    return count
print("closure", outer())

def shadow():
    return len([1, 2])
def len(s):
    return -1
print(shadow())
del len
print(shadow())

trace = []
def v(name, value):
    trace.append(name)
    return value
print(v("a", 1) < v("b", 2) < v("c", 3), v("a", 3) < v("b", 2) < v("c", 1), trace)
print(0 or 5, 3 and 0, 2 and 4, [] or "x", 7 if trace else 8)
items = {"k": [1, 2, 3]}
items["k"][1:3] = [9]
print(items, items["k"][-1], items["k"][::-1])
'''


def test_program_matches_cpython() -> None:
    got, ref = both(PROGRAM)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


WITH_PROGRAM = '''
with cm("A") as a:
    print("in with", a)
with cm("B", swallow=True) as b:
    1 // 0
    print("not reached")
print("after", -7 // 2, -7 % 2)
try:
    with cm("C") as c:
        raise ValueError("boom")
except ValueError as e:
    print("propagated", e.args)
with cm("D"), cm("E") as e:
    print("nested", e)
'''


def test_with_desugaring_matches_pep343() -> None:
    got, ref = both(WITH_PROGRAM, {"cm": CM})
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


DECORATOR_PROGRAM = '''
order = []
def deco(tag):
    order.append("eval " + tag)
    def wrap(f):
        order.append("apply " + tag)
        def inner(x):
            return f(x) + 1
        return inner
    return wrap

@deco("outer")
@deco("inner")
def f(x):
    return x * 10

print(f(4), order)
'''


def test_decorators_evaluate_top_down_apply_bottom_up() -> None:
    got, ref = both(DECORATOR_PROGRAM)
    assert got == ref


def test_unbound_name_is_a_compile_time_error() -> None:
    try:
        check(lower("print(nowhere)\n", "<test>"))
    except WellFormednessError as exc:
        assert "nowhere" in str(exc)
    else:
        raise AssertionError("unbound name accepted")


def test_unsupported_constructs_are_named_not_approximated() -> None:
    for src, needle in (("try:\n    pass\nexcept* E:\n    pass\n", "TryStar"), ("x = 1\nawait x\n", "Await")):
        try:
            lower(src, "<test>")
        except Unsupported as exc:
            assert needle in str(exc)
        else:
            raise AssertionError(f"{src!r} lowered silently")


def test_pass_manager_orders_by_facts_and_rejects_incomplete_specs() -> None:
    passes = manager.pipeline(FRONTEND_PASSES)
    ordered = [p.spec.name for p in manager.order(passes)]
    assert ordered[-1] == "to-l1"
    assert set(ordered[:-1]) == set(FRONTEND_PASSES[:-1])
    # a lowering pass without obligations is refused
    bad = RegisteredPass(PassSpec("bogus", Level.L1, Level.L2), lambda t: t)
    try:
        manager.order([bad])
    except manager.PassError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("incomplete spec accepted")
    # a pass whose required fact nobody produces is reported with the missing fact
    needy = RegisteredPass(PassSpec("needy", Level.L1, Level.L1, requires=frozenset({Fact.TYPES}),
                                    obligations=(Obligation("wf", "x"),), discharge=Discharge.TESTED), lambda t: t)
    try:
        manager.order([needy])
    except manager.PassError as exc:
        assert "TYPES" in str(exc)
    else:
        raise AssertionError("unsatisfiable pass accepted")
    assert all(name in REGISTRY for name in FRONTEND_PASSES)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
