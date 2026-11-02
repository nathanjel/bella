"""Regression tests for the findings of the second 2026-11-02 reviews, of `58bb34b..d28b256`
(astra-low 08 and gemini-4-argon-high 07; docs/reviews/review-log.md, RL-169 on).

Each program runs under CPython and through frontend -> to-anf -> lifetimes -> wf2 -> eval2 and
must print the same: the programs are release-point probes, so a reference dropped one step early
or late changes the output. The object model's findings (A8-1, A8-10) are tested in
refmodel/tests/test_cases.py and by `make object-test` (runtime/tests/object_reentrancy.*).
Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_02b
"""
from __future__ import annotations

from pipeline.l2 import grammar as G
from pipeline.l2 import wf as wf2
from pipeline.tests.test_l2 import same

# ---- implementation frames (RL-170) -------------------------------------------------------------


def test_a_failed_operation_releases_its_operands_before_the_handler_a8_2() -> None:
    same('''
class P:
    def __init__(self, n): self.n = n
    def __del__(self): print("del", self.n)
def f(*a, **k): pass
try:
    x = 1
    x += P("inplace")
except TypeError:
    print("handler inplace")
try:
    a, b = [P("item")]
except ValueError:
    print("handler unpack")
try:
    f(*P("star"))
except TypeError:
    print("handler star")
try:
    f(**P("starstar"))
except TypeError:
    print("handler starstar")
print("after")
''')


# ---- with (RL-171) ------------------------------------------------------------------------------


def test_a_failed_enter_or_target_releases_the_statements_references_a8_3() -> None:
    same('''
class V:
    def __del__(self): print("del value")
class Fails:
    def __enter__(self): raise ValueError("bad")
    def __exit__(self, *args): pass
    def __del__(self): print("del failing manager")
class Gives:
    def __enter__(self): return V()
    def __exit__(self, *args):
        print("exit", args[0].__name__ if args[0] else None)
        return True
    def __del__(self): print("del manager")
class NoExit:
    def __enter__(self): return 1
    def __del__(self): print("del half manager")
try:
    with Fails(): pass
except ValueError:
    print("handler")
with Gives() as (a, b):
    print("body")
try:
    with NoExit(): pass
except TypeError:
    print("handler no exit")
print("after")
''')


# ---- chained comparisons and decorators (RL-172, RL-180) --------------------------------------


def test_a_chained_comparisons_middle_operand_is_a_stack_value_a8_4() -> None:
    same('''
class C:
    def __init__(self, n, v): self.n, self.v = n, v
    def __lt__(self, o): return self.v < (o.v if isinstance(o, C) else o)
    def __gt__(self, o): return self.v > (o.v if isinstance(o, C) else o)
    def __del__(self): print("del", self.n)
print(C("a", 1) < C("b", 2) < C("c", 3))
print("false first:", C("a", 3) < C("b", 1) < C("c", 2))
print("false in the middle:", C("a", 1) < C("b", 2) < C("c", 0) < C("d", 4))
def run():
    print(1 < C("mid", 2) < 3)
    print("after comparison")
run()
class K:
    r = C("k1", 0) < C("k2", 1) < C("k3", 2)
print("class body", K.r)
''')


def test_a_decorator_dies_once_applied_g7_2_3() -> None:
    same('''
class Probe:
    def __init__(self, name): self.name = name
    def __call__(self, x): return x
    def __del__(self): print("del", self.name)
def outer():
    print("outer start")
    @Probe("function decorator")
    @Probe("inner decorator")
    def g(): pass
    print("outer middle")
    @Probe("class decorator")
    class K: pass
    print("outer end")
outer()
print("after")
''')


# ---- slot tables and scopes (RL-173, RL-174) ----------------------------------------------------


def test_an_annotation_alone_takes_no_slot_a8_5() -> None:
    same('''
class O:
    def __init__(self, n): self.n = n
    def __del__(self): print(self.n)
def f():
    z: int
    a = O("a")
    z = O("z")
f()
def g():
    q: int
    def inner(): return q
    q = 1
    return inner()
print(g())
''')


def test_a_global_declaration_stops_an_enclosing_functions_binding_a8_6() -> None:
    same('''
x = "module"
def outer():
    x = "outer"
    def middle():
        global x
        def inner(): return x
        return inner
    return middle()
print(outer()())
def outer2():
    x = "outer2"
    def middle():
        global x
        def deeper():
            def inner(): return x
            return inner
        return deeper()
    return middle()
print(outer2()())
''')


# ---- host state, exception names, unreachable code (RL-175, RL-176, RL-177) ------------------


def test_locals_and_vars_are_known_by_identity_a8_7() -> None:
    same('''
def f():
    see = locals
    print(sorted(see()))
    print(sorted(locals(*())))
    v = vars
    print(sorted(v()))
    d = dir
    print(d())
f()
''')


def test_a_programs_baseexception_does_not_reach_the_translation_a8_8() -> None:
    same('''
BaseException = int
try:
    1 / 0
except ZeroDivisionError:
    print("caught")
class M:
    def __enter__(self): return self
    def __exit__(self, *a):
        print("exit", a[0].__name__ if a[0] else None)
        return True
with M():
    1 / 0
print("survived")
''')


def test_code_after_a_return_is_dropped_a8_9() -> None:
    same('''
def f():
    return 1
    x = 2
def g():
    while True:
        break
        print("never")
    raise KeyError("k")
    print("never")
print(f())
try:
    g()
except KeyError:
    print("g raised")
''')


# ---- wf2 (RL-179) -------------------------------------------------------------------------------


def test_a_finally_cannot_use_what_a_return_consumed_a8_11() -> None:
    v, f = G.Temp(1), G.Temp(2)
    fn = G.Code("f", "f", "function", (), (), (), (), (
        G.Let(v, G.Copy(G.Const("value"))),
        G.Try((G.Return(v),), finalbody=(
            G.Let(f, G.Load(G.NameRef("global", "print"))),
            G.Do(G.Call(f, (v,))),
            G.Release(f),
        )),
    ))
    module = G.Module(G.Code("<module>", "<module>", "module", (), (), (), (), (
        G.Let(f, G.MakeFunction(fn)), G.Do(G.Call(f, ())), G.Release(f))))
    try:
        wf2.check(module)
    except wf2.WellFormednessError as exc:
        assert "t1 used where it is not live" in str(exc)
    else:
        raise AssertionError("wf2 accepted a finally that uses a returned temporary")


def test_a_return_through_finally_runs_and_releases_in_order_a8_11() -> None:
    same('''
class T:
    def __init__(self, n): self.n = n
    def __del__(self): print("del", self.n)
def f():
    try:
        return T("returned")
    finally:
        print("finally")
r = f()
print("got", r.n)
del r
def g():
    for i in range(2):
        try:
            if i:
                break
            continue
        finally:
            print("finally", i)
    return T("after loop")
print(g().n)
''')


# ---- augmented assignment (RL-182, RL-183) and found while fixing (RL-184 to RL-186) -----------


def test_augmented_assignment_releases_in_cpythons_order_g7_2_8_g7_2_9() -> None:
    same('''
class Dead:
    def __init__(self, name): self.name = name
    def __add__(self, other): return Dead("res")
    def __del__(self): print("del", self.name)
class Items:
    def __getitem__(self, k): return Dead("cur")
    def __setitem__(self, k, v): pass
class Attrs:
    def __init__(self): self.__dict__["attr"] = Dead("cur")
    def __setattr__(self, name, value): pass
print("--- subscript ---")
Items()[Dead("key")] += Dead("val")
print("--- attribute ---")
Attrs().attr += Dead("val")
print("--- end ---")
''')


def test_a_discarded_result_dies_after_the_arguments() -> None:
    same('''
class T:
    def __init__(self, n): self.n = n
    def __del__(self): print("del", self.n)
def f(*a): return T("result")
f(T(1), T(2))
print("after")
''')


def test_match_drops_the_subject_and_its_intermediates_where_cpython_does() -> None:
    same('''
class T:
    def __init__(self, n): self.n = n
    def __del__(self): print("del", self.n)
    __match_args__ = ("n",)
def run():
    match T("subject"):
        case int():
            print("int")
        case _:
            print("default")
    print("after match")
    match [T("a"), T("b")]:
        case [x, *rest]:
            print("captured", x.n, len(rest))
    del x, rest
    print("after sequence")
    match {"k": T("v"), "j": T("w")}:
        case {"k": val, **others}:
            print("mapping", val.n, len(others))
    del val, others
    print("after mapping")
    match T("obj"):
        case T(n="other"):
            print("no")
        case T(n=name) if name == "obj":
            print("class pattern", name)
    print("after class")
    match [T("p"), T("q")]:
        case [1, _]:
            print("no")
        case [_, y] if y.n == "zzz":
            print("guard false")
        case _:
            print("default")
    print("after failed cases")
run()
''')


def test_synthetic_variables_die_during_unwinding_as_cpythons_stack_values_do() -> None:
    same('''
class T:
    def __init__(self, n): self.n = n
    def __eq__(self, o): raise ValueError("eq")
    def __del__(self): print("del", self.n)
    __hash__ = None
class NoSet:
    def __setattr__(self, k, v): raise ValueError("no")
def boom(x):
    if x == 2: raise KeyError("k")
    return True
try:
    match T("module subject"):
        case 1:
            print("one")
except ValueError:
    print("handler module match")
def run():
    try:
        match [T("item")]:
            case [1]:
                print("one")
    except ValueError:
        print("handler match")
    try:
        NoSet().x = a = T("chained value")
    except ValueError:
        print("handler chained")
    try:
        r = [T(f"elem {x}") for x in [0, 1, 2] if boom(x)]
    except KeyError:
        print("handler comprehension")
    try:
        g = list(T(f"genexp elem {x}") for x in [0, 1, 2] if boom(x))
    except KeyError:
        print("handler genexp")
    print("run end")
run()
try:
    class K:
        match T("class subject"):
            case 1:
                pass
except ValueError:
    print("handler class")
print("end")
''')


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
