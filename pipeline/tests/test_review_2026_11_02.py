"""Regression tests for the findings of the 2026-11-02 reviews of `3d4e428..58bb34b`
(astra-low 07 and gemini-4-argon-high 06; docs/reviews/review-log.md, RL-136 on).

Each test runs its program under eval1 and under CPython (the oracle) and requires the same
output, or requires the frontend to reject what CPython's compiler rejects, with CPython's
message. Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_02
"""
from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
import json
import textwrap
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.l1.eval1 import Interpreter
from pipeline.l1.frontend import lower
from pipeline.l1.modules import ROOT, ModuleSystem
from pipeline.l1.wf import WellFormednessError, check
from pipeline.tests.test_frontend_eval1 import both


def same(src: str) -> str:
    e1, ref = both(textwrap.dedent(src))
    assert e1 == ref, f"eval1:\n{e1}\nCPython:\n{ref}"
    return ref


def rejected_as_cpython_rejects(src: str) -> None:
    src = textwrap.dedent(src)
    try:
        compile(src, "<cpython>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        expected = exc.msg
    else:
        raise AssertionError(f"CPython accepts {src!r}")
    try:
        lower(src, "<test>")
    except SyntaxError as exc:
        assert exc.msg == expected, f"{exc.msg!r} != CPython's {expected!r}"
    else:
        raise AssertionError(f"{src!r} lowered; CPython: {expected}")


# ---- calls (RL-136, RL-164) ---------------------------------------------------------------------

def test_a_lone_starred_argument_becomes_a_tuple_when_the_call_is_made_a7_1() -> None:
    out = same('''
        data = [1]
        def kw():
            data.append(2)
            print("kw")
            return 0
        def f(*args, **kwargs):
            print(args, sorted(kwargs))
        f(*data, x=kw())
        class I:
            def __iter__(self):
                print("iter")
                return iter([1])
        f(*I(), x=kw())
        f(0, *I(), x=kw())
        f(*I(), *I(), x=kw())
        t = (5,)
        f(*t)
        try:
            f(*5, x=kw())
        except TypeError as e:
            print(e)
    ''')
    assert out.startswith("kw\n(1, 2)")


def test_a_run_of_keywords_is_evaluated_whole_before_it_is_merged_g6_2_7_1() -> None:
    same('''
        events = []
        def s(n):
            events.append(n)
            return n
        def f(**kw):
            return sorted(kw)
        try:
            f(**{"a": 0}, a=s(1), b=s(2))
        except TypeError as e:
            print(events, e)
        events.clear()
        try:
            f(a=s(1), b=s(2), **{"b": 0}, c=s(3))
        except TypeError as e:
            print(events, e)
        class M:
            def keys(self):
                events.append("keys")
                return ["z"]
            def __getitem__(self, k):
                events.append("getitem")
                return 9
        events.clear()
        print(f(x=s(1), **M(), y=s(2)), events)
    ''')


# ---- annotations (RL-137, RL-138, RL-145 to RL-150, RL-168) --------------------------------------------

def test_pep_563_modules_and_classes_have_a_real_annotations_dict_a7_2() -> None:
    same('''
        """doc"""
        from __future__ import annotations
        print("__annotations__" in globals(), "__annotate__" in globals())
        x: int
        if True:
            y: list[int] = []
        print(__annotations__, "__conditional_annotations__" in globals(), __doc__)
        class M(type):
            @classmethod
            def __prepare__(mcls, name, bases):
                class NS(dict):
                    def __getitem__(self, k):
                        print("getitem", k)
                        return dict.__getitem__(self, k)
                    def __setitem__(self, k, v):
                        print("setitem", k)
                        dict.__setitem__(self, k, v)
                return NS()
        class C(metaclass=M):
            """class doc"""
            a: int
            def m(self, p: str) -> None: pass
        print(C.__annotations__, C.m.__annotations__)
        class K:
            def m(self, q: int): pass
        print("__annotations__" in K.__dict__)
    ''')


def test_a_class_namespace_sees_cpythons_stores_with_and_without_pep_563() -> None:
    """Found while testing A7-2: under PEP 563 only a generic definition or a type alias makes
    __classdictcell__; without it any definition or annotation does (measured on 3.15.2)."""
    for future in ("", "from __future__ import annotations\n"):
        for body in ("def m(self): pass", "def m(self, p: int): pass", "a: int", "x = 1", "f = lambda: 1",
                     "class Inner: pass", "def g[T](self): pass", "type A = int", "class G[T]: pass",
                     "(x): int", "import sys; sys.y: int", "if True: z: int"):
            same(future + textwrap.dedent('''
                class M(type):
                    @classmethod
                    def __prepare__(mcls, name, bases):
                        class NS(dict):
                            def __setitem__(self, k, v):
                                print("set", k)
                                dict.__setitem__(self, k, v)
                        return NS()
                class C(metaclass=M):
                    BODY
            ''').replace("BODY", body))


def test_pep_563_keeps_an_annotations_dict_set_by_the_program() -> None:
    same('''
        from __future__ import annotations
        __annotations__ = {"pre": 1}
        z: str
        print(__annotations__)
    ''')


def test_an_annotated_target_without_value_evaluates_its_parts_a7_3_g6_2_2() -> None:
    same('''
        def show(tag, v):
            print(tag)
            return v
        class O: pass
        show("obj", [0])[show("key", 0)]: int
        show("o", O()).x: int
        show("s", [0, 1, 2])[show("lo", 0):show("hi", 1):show("step", 1)]: int
        show("t", {})[show("a", 1), show("b", 2)]: int
        class C:
            show("in class", O()).y: int
        def f():
            show("in function", O()).z: int
            self = O()
            self.a: int
        f()
        print(hasattr(O(), "x"))
    ''')


def test_function_scope_declarations_mangle_and_ignore_non_simple_targets_g6_2_2() -> None:
    same('''
        _C__x = "global"
        x = "global x"
        class C:
            def f(self):
                __x: int
                try:
                    return __x
                except UnboundLocalError:
                    return "unbound"
        def h():
            (x): int
            return x
        print(C().f(), h())
    ''')


def test_function_annotations_under_pep_563_are_the_source_text_g6_2_1() -> None:
    same('''
        from __future__ import annotations
        class C:
            def f(self, a: __Priv, b: f"{int}", c: 1 < 2 < 3, *args: *Ts, **kw: [i for i in x]) -> __Priv:
                pass
        print(C.f.__annotations__, C.f.__annotate__.__qualname__)
    ''')


def test_function_annotations_are_an_annotate_function_lowered_by_every_pass_g6_2_1() -> None:
    same('''
        def g(x: [t for t in (int,)], y: f"{1 + 1}", z: 1 < 2 < 3) -> {k: v for k, v in [(1, 2)]}:
            return 1
        print(g.__annotations__, g.__annotate__.__name__, g.__annotate__.__qualname__)
        class C:
            T = int
            def m(self, __p: T, *args: str) -> "C":
                pass
        print(C.m.__annotations__, C.m.__annotate__.__qualname__)
        def gen[U](a: U, *b: tuple[U, ...]) -> list[U]:
            return [a]
        print(gen.__annotations__["a"] is gen.__type_params__[0])
        try:
            C.m.__annotate__(3)
        except NotImplementedError:
            print("format 3: NotImplementedError")
    ''')


# ---- comprehensions (RL-139, RL-154 to RL-156) -------------------------------------------------

def test_a_comprehension_advances_the_iterator_made_outside_it_a7_4() -> None:
    same('''
        class I:
            def __init__(self):
                self.done = False
            def __iter__(self):
                print("iter")
                return self
            def __next__(self):
                if self.done:
                    raise StopIteration
                self.done = True
                return 1
        print([x for x in I()], {x for x in I()}, {x: x for x in I()})
        g = (x for x in I())
        print("created")
        print(next(g))
    ''')


def test_walrus_in_comprehensions_binds_where_pep_572_says_g6_2_4() -> None:
    same('''
        fn = lambda: ([(y := i) for i in (1, 2, 3)], y)
        print(fn())
        def f():
            global gx
            [gx := i for i in (1, 2, 3)]
            [[(gy := j) for j in range(i)] for i in (1, 2)]
            return gy
        print(f(), gx)
    ''')


def test_yield_in_a_comprehension_is_cpythons_syntax_error_g6_2_4_3() -> None:
    rejected_as_cpython_rejects('''
        def g():
            return [(yield x) for x in (1, 2)]
    ''')


# ---- dictionaries (RL-140, RL-162) -------------------------------------------------------------

def test_dict_merges_take_the_stored_hashes_a7_5() -> None:
    same('''
        trace = []
        class K:
            def __hash__(self):
                trace.append("hash")
                return 1
        k = K()
        m = {k: 3}
        trace.clear()
        n = {**m}
        print(trace, len(n))
        n = {1: 2, **m, **frozendict({k: 4})}
        print(trace, len(n))
        def f(**kw):
            return kw
        try:
            f(**m)
        except TypeError as e:
            print(e, trace)
        try:
            f(**{"a": 1}, **{"a": 2})
        except TypeError as e:
            print(e)
        print(f(**frozendict(b=2), c=3))
    ''')


def test_a_mapping_pattern_rest_is_dict_update_g6_2_6_3() -> None:
    same('''
        import collections.abc
        class PairsOnly:
            def __iter__(self): return iter([("a", 1)])
            def __getitem__(self, k): return 1
            def __len__(self): return 1
            def get(self, k, d=None): return 1 if k == "a" else d
        collections.abc.Mapping.register(PairsOnly)
        try:
            match PairsOnly():
                case {**rest}:
                    print(rest)
        except TypeError as e:
            print("TypeError", e)
        match {"a": 1, "b": 2}:
            case {"a": 1, **rest}:
                print(rest)
    ''')


# ---- classes (RL-141, RL-163) ---------------------------------------------------------------------------

def test_an_optional_class_attribute_that_is_none_is_called_a7_6() -> None:
    same('''
        class M(type):
            __prepare__ = None
        try:
            class C(metaclass=M):
                pass
            print("created")
        except TypeError as e:
            print("prepare:", e)
        class B:
            __mro_entries__ = None
        try:
            class D(B()):
                pass
        except TypeError as e:
            print("mro_entries:", e)
    ''')


# ---- the strict check (RL-142, RL-166) ----------------------------------------------------------

def test_a_globals_call_does_not_relax_the_programs_name_check_a7_7() -> None:
    for src in ("globals()\nprint(missing)\n", "def unused():\n    return globals()\nprint(missing)\n",
                "def f():\n    global zz\n    return 1\nprint(zz)\n"):
        try:
            check(lower(src, "<test>"))
        except WellFormednessError as exc:
            assert "is bound nowhere" in str(exc)
        else:
            raise AssertionError(f"{src!r} passed the strict check")
    # a global binding a function makes, also through its comprehensions, binds the module's name
    for src in ("def f():\n    global zz\n    zz = 1\nf()\nprint(zz)\n",
                "def f():\n    global gx\n    [gx := i for i in (1, 2)]\nf()\nprint(gx)\n",
                "class C:\n    global q\n    q = 1\nprint(q)\n"):
        check(lower(src, "<test>"))
    # library modules keep the runtime lookup (P-3)
    assert check(lower("globals()['late'] = 1\nprint(late)\n", "<test>"), strict=False)


# ---- compile-time errors (RL-156, RL-161, RL-165, RL-166) ----------------------------------------------

def test_what_cpythons_compiler_rejects_is_rejected_with_its_message_g6() -> None:
    for src in ('''
                    class Point: x = 1
                    match Point():
                        case Point(x=1, x=1):
                            pass
                ''', '''
                    try:
                        lazy import json
                    except ImportError:
                        pass
                ''', '''
                    class C:
                        from json import *
                ''', '''
                    x = 1
                    def g():
                        nonlocal x
                ''', '''
                    def f(x):
                        global x
                ''', '''
                    def f():
                        global y
                        nonlocal y
                ''', '''
                    def f(a, a):
                        pass
                ''', '''
                    f(x=1, x=2)
                '''):
        rejected_as_cpython_rejects(src)


# ---- PEP 695 (RL-151 to RL-153) -----------------------------------------------------------------

def test_generic_class_scopes_see_the_class_and_mangle_type_parameters_g6_2_3() -> None:
    same('''
        class Outer:
            class Base:
                pass
            class Inner[T](Base):
                pass
            class Box[__T](list[__T]):
                v = __T
                __w = 1
            def m[__U](self, a: __U) -> __U:
                return a
        print(Outer.Inner.__bases__, Outer.Box.v is Outer.Box.__type_params__[0], Outer.Box.v.__name__)
        print(sorted(k for k in Outer.Box.__dict__ if "w" in k), Outer.m.__type_params__)
    ''')


def test_a_type_alias_takes_the_qualname_of_where_it_stands_g6_2_3_3() -> None:
    same('''
        class C:
            type A = int
            type G[T] = list[T]
            def m(self):
                type L = str
                return L
        def f():
            type F[U] = U
            return F
        type Top = int
        for a in (C.A, C.G, C().m(), f(), Top):
            print(repr(a), a.__qualname__, a.__name__, a.evaluate_value.__qualname__)
    ''')


# ---- generators (RL-157 to RL-159) ---------------------------------------------------------

def test_a_yield_inside_an_intrinsics_operands_runs_g6_2_5_1() -> None:
    same('''
        def g1():
            yield f"val={(yield 1)!r}"
        def g2():
            return [10, 20, 30][(yield 1):]
        def g3():
            return [x * 2 for x in (yield "iter")]
        def g4():
            return 1 < (yield "mid") < 5
        for g, v in ((g1, 7), (g2, 1), (g3, (1, 2)), (g4, 3)):
            it = g()
            print(next(it))
            try:
                print(it.send(v))
            except StopIteration as e:
                print("return", e.value)
    ''')


def test_a_yield_in_a_for_target_is_a_refusal_not_a_crash_g6_2_5_2() -> None:
    m = lower("def g(xs):\n    a = [0]\n    for a[(yield 1)] in xs:\n        pass\nit = g([5])\nnext(it)\n", "<test>")
    check(m)
    try:
        Interpreter(dict(vars(builtins))).run_module(m)
    except L.Refused as exc:
        assert "yield inside a for target" in str(exc)
    else:
        raise AssertionError("not refused")


def test_a_running_generator_is_the_frame_on_top_g6_2_5_3() -> None:
    sites: list[str] = []
    interp: Any = None

    def probe() -> None:
        sites.append(interp.site())
    src = textwrap.dedent('''
        def gen():
            probe()
            yield 1
            probe()
            yield 2
        def driver():
            it = gen()
            next(it)
            probe()
            next(it)
        driver()
    ''')
    m = lower(src, "<test>")
    check(m, frozenset({"probe"}))
    interp = Interpreter(dict(vars(builtins)) | {"probe": probe})
    with contextlib.redirect_stdout(io.StringIO()):
        interp.run_module(m)
    assert sites == ["__main__:gen", "__main__:driver", "__main__:gen"], sites
    assert interp.frames == [], interp.frames


# ---- match (RL-160) ---------------------------------------------------------------------------------

def test_signed_and_complex_mapping_keys_are_literals_g6_2_6_1() -> None:
    same('''
        match {-1: "neg", 1+2j: "cplx", -2.5: "f"}:
            case {-1: a, 1+2j: b, -2.5: c}:
                print(a, b, c)
    ''')
    rejected_as_cpython_rejects('''
        match {}:
            case {-1: a, -1: b}:
                pass
    ''')


# ---- the module system and the corpus tool (RL-143, RL-144, RL-167) -----------------------------------

def test_the_closure_holds_the_programs_modules_and_tells_library_code_by_the_lock_g6_2_7_4() -> None:
    lock = ROOT / "targets" / "closure" / "data_easy_sales.lock.json"
    system = ModuleSystem(Interpreter(), "closure", lock)
    data = json.loads(lock.read_text(encoding="utf-8"))
    program = {n for n, m in data["modules"].items() if m["status"] == "program"}
    assert program <= set(system.closure), program - set(system.closure)
    roots = set(data["roots"])
    assert all(system.closure[n] in system.library for n in program - roots)
    assert not any(system.closure[n] in system.library for n in roots)
    assert system.closure["humanize"].name == "__init__.py"


def test_the_corpus_baseline_is_written_only_from_a_complete_run_a7() -> None:
    spec = importlib.util.spec_from_file_location("eval1_corpus", ROOT / "tools" / "eval1_corpus.py")
    assert spec is not None and spec.loader is not None
    tool: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    before = tool.BASELINE.read_text(encoding="utf-8")
    tool.run = lambda level=1: {"C-2-01_evaluation_order.py": True}       # a harness that stopped early
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert tool.main(["--update"]) == 1
    assert "incomplete" in out.getvalue()
    assert tool.BASELINE.read_text(encoding="utf-8") == before


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
