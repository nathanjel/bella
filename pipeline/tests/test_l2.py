"""L2: to-anf, lifetimes, wf2 and eval2 against CPython (docs/l2.md v1).

Each program runs under CPython and through frontend -> to-anf -> lifetimes -> wf2 -> eval2; the
two outputs must be equal. The programs are release-point probes: objects whose `__del__` prints,
sent through each kind of place CPython drops a reference (docs/l2.md section 5), so a release
one statement early or late changes the output.

Run under pytest or directly: python3 -m pipeline.tests.test_l2
"""
from __future__ import annotations

import builtins
import contextlib
import gc
import io

from pipeline.l1.frontend import lower
from pipeline.l1.wf import check as wf1
from pipeline.l2 import grammar as G
from pipeline.l2 import wf as wf2
from pipeline.l2.eval2 import Interpreter, SlotMismatch, compile_module
from pipeline.l2.lifetimes import lifetimes
from pipeline.l2.lower import to_l2

PRELUDE = '''
class O:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("del", self.n)
    def __mul__(self, other):
        return O(f"{self.n}*{other.n}")
def mk(n):
    return O(n)
def boom():
    raise KeyError("boom")
'''


def l2(src: str) -> G.Module:
    m1 = lower(src, "<test>")
    wf1(m1)
    m2: G.Module = lifetimes(to_l2(m1))
    wf2.check(m2, lifetimes=True)
    return m2


def _quiet_collect(namespace: dict[str, object] | None = None) -> None:
    """A module's namespace is a reference cycle (its functions hold it): clear and collect it
    outside any capture, so that what it holds never dies inside the next program's output."""
    with contextlib.redirect_stdout(io.StringIO()):
        if namespace is not None:
            namespace.clear()
        gc.collect()


def both(src: str) -> tuple[str, str]:
    src = PRELUDE + src
    _quiet_collect()
    got = io.StringIO()
    with contextlib.redirect_stdout(got):
        interp = Interpreter(dict(vars(builtins)))
        interp.load_runtime()       # as the module system does: no lowering once the program runs
        ns = interp.run_module(l2(src))
    _quiet_collect(ns)
    ref = io.StringIO()
    oracle: dict[str, object] = {"__name__": "__main__"}
    with contextlib.redirect_stdout(ref):
        exec(compile(src, "<cpython>", "exec", dont_inherit=True), oracle)  # noqa: S102 -- the oracle
    _quiet_collect(oracle)
    return got.getvalue(), ref.getvalue()


def same(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval2\n{got}\n--- cpython\n{ref}"


def test_operands_die_last_evaluated_first() -> None:
    same('''
def f(*args):
    print("f called")
r = mk("a") * mk("b")
print("product", r.n)
del r
f(mk(1), mk(2), mk(3))
print("end")
''')


def test_exception_edge_kills_temporaries_before_the_handler() -> None:
    same('''
def f(*args):
    pass
try:
    f(mk(1), mk(2), boom())
except KeyError:
    print("handler")
try:
    mk(3) + mk(4)
except TypeError:
    print("handler 2")
''')


def test_a_traceback_keeps_a_raising_frames_locals() -> None:
    same('''
def parse():
    buf = mk("buf")
    other = mk("other")
    raise ValueError("bad")
try:
    parse()
except ValueError as e:
    saved = e
print("after handler")
del saved
print("after del saved")
def g():
    a = mk("a"); b = mk("b"); c = mk("c")
    return 0
g()
print("after g: reverse slot order")
''')


def test_loop_iterators_and_finally_order() -> None:
    same('''
class Gen:
    def __init__(self, tag):
        self.tag = tag
    def __iter__(self):
        return self
    def __next__(self):
        raise StopIteration
    def __del__(self):
        print("iterator dies", self.tag)
def items(tag):
    yield 1
    yield 2
for x in Gen("plain"):
    pass
print("after the loop")
def early():
    for x in items("gen"):
        try:
            return x
        finally:
            print("finally runs first")
print(early())
for i in range(3):
    for j in range(3):
        if j == 1:
            break
    else:
        print("never")
        continue
    print("outer", i)
''')


def test_and_or_drop_the_left_operand_first() -> None:
    same('''
class B(O):
    def __bool__(self):
        print("bool", self.n)
        return self.n == "true"
v = B("false") and mk("right")
print("and:", v.n)
del v
w = B("true") or mk("never")
print("or:", w.n)
del w
z = B("false") or mk("right2")
print("or2:", z.n)
''')


def test_a_suspended_generator_does_not_hold_what_it_yielded() -> None:
    same('''
def gen():
    yield mk("yielded")
    print("resumed")
    yield None
g = gen()
x = next(g)
del x
print("after del x")
next(g)
del g
print("end")
''')


def test_augmented_assignment_loads_the_name_first() -> None:
    same('''
g = 1
def f():
    global g
    g = 100
    return 5
g += f()
print(g)
''')


def test_names_kinds_closures_and_classes() -> None:
    same('''
def outer():
    n = 0
    def bump():
        nonlocal n
        n += 1
        return n
    bump(); bump()
    return n, [k * n for k in range(3)], (lambda: n)()
print(outer())
class Base:
    def who(self):
        return "base"
class Derived(Base):
    tag = "t"
    def who(self):
        return "derived of " + super().who()
    def again(self):
        return super(Derived, self).who()
print(Derived().who(), Derived().again(), Derived.tag)
def walrus(xs):
    ys = [last := x * 2 for x in xs]
    return ys, last
print(walrus([1, 2]))
def scope():
    a = 1
    hidden = [a for _ in range(2)]
    return sorted(locals())
print(scope())
''')


def test_wf2_rejects_a_bad_release_discipline() -> None:
    def module(body: tuple[G.Stmt, ...]) -> G.Module:
        return G.Module(G.Code("<module>", "<module>", "module", (), (), (), (), body))
    t1 = G.Temp(1)
    good = (G.Let(t1, G.Builtin("print")), G.Release(t1))
    wf2.check(module(good))
    for bad, why in [((G.Let(t1, G.Builtin("print")),), "unreleased"),
                     ((G.Let(t1, G.Builtin("print")), G.Release(t1), G.Release(t1)), "not live"),
                     ((G.Let(t1, G.Builtin("print")), G.Release(t1), G.Do(G.Call(t1, ()))), "not live")]:
        try:
            wf2.check(module(bad))
        except wf2.WellFormednessError as exc:
            assert why in str(exc), str(exc)
        else:
            raise AssertionError(f"accepted {bad}")


def test_eval2_checks_the_slot_tables_against_the_host() -> None:
    m = l2("def f():\n    x = 1\n    return x\n")
    make = next(s for s in m.code.body if isinstance(s, G.Let) and isinstance(s.op, G.MakeFunction))
    assert isinstance(make, G.Let) and isinstance(make.op, G.MakeFunction)
    code = make.op.code
    wrong = G.Code(code.name, code.qualname, code.kind, code.params, (), (), (), code.body)   # x missing
    bad = G.Module(G.Code("<module>", "<module>", "module", (), (), (), (),
                          (G.Let(make.t, G.MakeFunction(wrong)), G.Store(G.NameRef("name", "f"), make.t))))
    try:
        compile_module(bad)
    except SlotMismatch as exc:
        assert "f" in str(exc)
    else:
        raise AssertionError("a wrong slot table was accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
