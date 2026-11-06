"""Regression tests for the reviews of the C++ emitter and compiled classes, `d28b256..f12af86`
(astra-low 09 and gemini-4-argon-high 08; docs/reviews/review-log.md, RL-188 on).

Each reviewer's program is compiled (pipeline/build.py) and run; stdout and the exit status must be
CPython's, with PYTHONHASHSEED=0 in both. A finally matrix adds every way out of a try with a finally
(return, break, continue, the loop's end, an exception), nested, raising, and through loops holding
an iterator, since A9-5 and A9-6 showed that the passing cases covered none of them.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_03
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build

FINDINGS: list[tuple[str, str, str]] = [
    ('A9-1', 'list_compare_mutation', 'a=[]; b=[]\nclass C:\n    def __eq__(self, other):\n        a.clear();b.clear()\n        return False\n    def __lt__(self, other): return True\na.extend([C(),1]);b.extend([C(),2])\nprint(a<b)\n'),
    ('A9-2', 'wrong_receiver', "try: list.append(1,2)\nexcept TypeError: print('TypeError')\n"),
    ('A9-3', 'wrong_set_arity', "try: set().discard()\nexcept TypeError: print('TypeError')\n"),
    ('A9-4', 'del_raises', "class C:\n    def __del__(self):\n        print('finalizer')\n        raise ValueError('bad')\nx=C();del x\nprint('after')\n"),
    ('A9-4', 'finalizer_exception_destructor', "class C:\n    def __del__(self): raise ValueError('bad')\ndef f():\n    x=C()\nf()\nprint('after')\n"),
    ('A9-5', 'finally_return_raise', "def f():\n    try: return 1\n    finally:\n        print('finally')\n        raise ValueError('bad')\ntry: f()\nexcept ValueError: print('caught')\n"),
    ('A9-6', 'finally_exception_context', "try:\n    try: raise ValueError('first')\n    finally: raise TypeError('second')\nexcept TypeError as e:\n    print(type(e.__context__).__name__)\n"),
    ('A9-6', 'finally_reraise', "try:\n    try: raise ValueError('original')\n    finally: raise\nexcept BaseException as e: print(type(e).__name__)\n"),
    ('A9-7', 'unpack_lifetime', "class O:\n    def __init__(self,n): self.n=n\n    def __del__(self): print('del',self.n)\n\na,b=[O('a'),O('b')]\ndel a\ndel b\nprint('after')\n"),
    ('A9-8', 'set_exception_leak_fixed', "class O:\n    def __init__(self,n): self.n=n\n    def __del__(self): print('del',self.n)\n\nclass C(O):\n    def __hash__(self): return 1\n    def __eq__(self, other): raise ValueError('bad')\ns={C('first')}\ntry: s.add(C('second'))\nexcept ValueError: print('caught')\nprint('after')\ndel s\n"),
    ('A9-9', 'duplicate_base', "class A: pass\ntry:\n    class B(A,A): pass\n    print('created')\nexcept TypeError: print('TypeError')\n"),
    ('A9-10', 'call_special_shadow', 'class C:\n    @staticmethod\n    def __call__(): return 1\nc=C()\nc.__call__=lambda:2\nprint(c())\n'),
    ('A9-11', 'bad_pop_index', "a=[1,2]\ntry: print(a.pop('bad'))\nexcept TypeError: print('TypeError')\n"),
    ('A9-11', 'bool_as_index', 'a=[1,2]\nprint(a.pop(True))\n'),
    ('A9-12', 'dict_mutation', "s={1:1,2:2}\nit=iter(s)\ns[3]=3\ntry: print(next(it))\nexcept RuntimeError: print('RuntimeError')\n"),
    ('A9-12', 'set_mutation', "s={1,2}\nit=iter(s)\ns.add(3)\ntry: print(next(it))\nexcept RuntimeError: print('RuntimeError')\n"),
    ('A9-13', 'list_rich_result', 'class C:\n    def __eq__(self,other): return False\n    def __lt__(self,other): return 42\nprint([C()]<[C()])\nprint((C(),)<(C(),))\n'),
    ('A9-14', 'len_bool', "class C:\n    def __len__(self): return True\nc=C()\ntry: print(len(c),bool(c))\nexcept TypeError: print('TypeError')\n"),
    ('A9-14', 'len_index', "class I:\n    def __index__(self): return 2\nclass C:\n    def __len__(self): return I()\ntry: print(len(C()))\nexcept TypeError: print('TypeError')\n"),
    ('A9-15', 'dict_hash_copy', "class C:\n    def __hash__(self): print('hash');return 1\nx=C();s={x:1}\nprint('copy')\nt={**s}\nprint(len(t))\n"),
    ('A9-15', 'set_hash_copy', "class C:\n    def __hash__(self): print('hash');return 1\nx=C();s={x}\nprint('copy')\nt=set(s)\nprint(len(t))\n"),
    ('A9-16', 'empty_dict_hash', "class C:\n    def __hash__(self): print('hash');return 1\nprint(C() in {})\n"),
    ('A9-17', 'dict_repr_mutation', "d={}\nclass C:\n    def __repr__(self):\n        d['b']=2\n        return 'C'\nd['a']=C()\nprint(d)\n"),
    ('A9-18', 'duplicate_slot', "try:\n    class C: __slots__=('x','x')\n    print('created')\nexcept TypeError: print('TypeError')\n"),
    ('A9-18', 'invalid_slot', "try:\n    class C: __slots__=('not-valid',)\n    print('created')\nexcept TypeError: print('TypeError')\n"),
    ('A9-19', 'classmethod_callable', "class F:\n    def __call__(self, cls): return cls.__name__\nclass C:\n    method=classmethod(F())\ntry: print(C.method())\nexcept AttributeError: print('AttributeError')\n"),
    ('A9-20', 'flag_collision', 'def f():\n    ended1=3\n    for i in []: pass\n    else: print(ended1)\nf()\n'),
    ('A9-20', 'unary_collision', 'def f():\n    _A__b=1\n    _A_U_b=2\n    print(_A__b,_A_U_b)\nf()\n'),
    ('A9-21', 'notimplemented_bool', "try: print(bool(NotImplemented))\nexcept TypeError: print('TypeError')\n"),
    ('A9-22', 'abs_protocol', "class C:\n    def __abs__(self): return 42\ntry: print(abs(C()))\nexcept TypeError: print('TypeError')\n"),
    ('A9-23', 'factory_doc', 'class C:\n    @property\n    def p(self):\n        "property doc"\n        return 1\nprint(C.p.__doc__)\n'),
    ('A9-23', 'function_doc', 'def f():\n    "a docstring"\nprint(f.__doc__)\n'),
]


# Found while verifying the fixes against the earlier rounds' programs (RL-211 on).
FOUND: list[tuple[str, str]] = [
    ('stack_values_of_a_raising_comprehension', 'class T:\n    def __init__(self, n): self.n = n\n    def __del__(self): print("del", self.n)\nclass NoSet:\n    def __setattr__(self, k, v): raise ValueError("no")\ndef boom(x):\n    if x == 2: raise KeyError("k")\n    return True\ndef run():\n    o = NoSet()\n    try:\n        o.x = a = T("chained value")\n    except ValueError:\n        print("handler chained")\n    try:\n        r = [T(f"elem {x}") for x in range(3) if boom(x)]\n    except KeyError:\n        print("handler comprehension")\n    print("run end")\nrun()\n'),
    ('getattr_hook_as_call_attribute', 'class Desc:\n    def __init__(self, n, fail): self.n, self.fail = n, fail\n    def __get__(self, obj, cls):\n        print("  get: deletes", self.n, "from the class")\n        delattr(cls, "x")\n        print("  get: returns")\n        if self.fail: raise AttributeError("x")\n        return "value"\n    def __del__(self): print("  dies", self.n)\nclass Hook:\n    def __call__(self, name):\n        print("  hook called; deletes itself from the class")\n        del C2.__getattr__\n        print("  hook returns")\n        return "from hook"\n    def __del__(self): print("  dies hook")\n\nclass C1:\n    x = Desc("desc1", fail=False)\nprint("1. descriptor deletes itself:")\nv = C1().x\nprint("  caller got", v)\n\nclass C2:\n    x = Desc("desc2", fail=True)\n    __getattr__ = Hook()\nprint("2. descriptor deletes itself and fails; the hook deletes itself:")\nv = C2().x\nprint("  caller got", v)\n'),
    ('builtin_class_reprs', 'print(object, int, str, list, dict, type, ValueError, BaseException, type(None), type(len), type(print))\nprint(object.__name__, object.__qualname__, object.__module__, int.__qualname__)\nclass C: pass\nprint(C.__mro__, C.mro())\n'),
    ('names_absent_in_cpython_still_raise', 'class C: pass\nclass H:\n    def __getattr__(self, name):\n        return "hook " + name\nfor f in (lambda: "a".nosuch, lambda: C().nosuch, lambda: C.nosuch, lambda: ValueError().nosuch):\n    try:\n        f()\n    except AttributeError as e:\n        print("AttributeError", e)\nprint(H().nosuch, hasattr(C(), "nosuch"), getattr("", "nosuch", "default"))\ntry:\n    nosuch_name\nexcept NameError as e:\n    print("NameError", e)\nimport sys\nprint(type(sys.argv).__name__)\n'),
]

# CPython has these names; the runtime refuses them rather than answer NameError or AttributeError.
REFUSED = {
    "a builtin": "locals()",
    "an attribute of sys": "import sys\nsys.version_info",
    "a str method": "'é'.upper()",
    "an object method": "class C:\n    pass\nC().__sizeof__()",
    "before __getattr__": "class H:\n    def __getattr__(self, n):\n        print('hook', n)\nH().__sizeof__()",
    "a member of type": "class C:\n    pass\nC.__basicsize__",
    "an exception method": "ValueError().add_note",
    "a slot wrapper's docstring": "print(list.__len__.__doc__)",
    "a bound slot wrapper's docstring": "[].__len__.__doc__",
}


def same(src: str) -> None:
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(src), encoding="utf-8")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False, env=env, cwd=tmp)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (
        f"\n--- compiled (exit {got.returncode})\n{got.stdout}{got.stderr}\n--- CPython (exit {ref.returncode})\n{ref.stdout}")


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{fid}-{name}" for fid, name, _ in FINDINGS])
    if "found" in metafunc.fixturenames:
        metafunc.parametrize("found", FOUND, ids=[name for name, _ in FOUND])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


def test_every_way_out_of_a_finally_a9_5_a9_6() -> None:
    same("""
        class P:
            def __init__(self, n): self.n = n
            def __del__(self): print("del", self.n)
            def __iter__(self): return iter([1, 2, 3])
        def ret(raise_in_finally):
            try:
                return "r"
            finally:
                print("finally")
                if raise_in_finally:
                    raise ValueError("f")
        for flag in (False, True):
            try:
                print(ret(flag))
            except ValueError as e:
                print("caught", type(e.__context__).__name__)
        def loop(kind):
            out = []
            for i in P("iterator"):
                try:
                    try:
                        if i == 2:
                            if kind == "break":
                                break
                            if kind == "continue":
                                continue
                            if kind == "return":
                                return out
                        out.append(i)
                    finally:
                        out.append("inner")
                finally:
                    out.append("outer")
                    print("outer finally", i)
            else:
                out.append("else")
            return out
        for k in ("break", "continue", "return", "none"):
            print(k, loop(k))
        def raising_break():
            for i in [1]:
                try:
                    break
                finally:
                    raise KeyError("k")
        try:
            raising_break()
        except KeyError:
            print("KeyError from the finally of a break")
        def handler_return():
            try:
                try:
                    raise ValueError("v")
                except ValueError as e:
                    return "from the handler"
                finally:
                    print("finally after the handler")
            finally:
                print("outer finally")
        print(handler_return())
        def reraise_in_finally():
            try:
                raise ValueError("original")
            finally:
                print("finally sees the exception")
        try:
            reraise_in_finally()
        except ValueError as e:
            print("propagated", e.args)
        def nested_returns():
            try:
                try:
                    return 1
                finally:
                    print("inner")
            finally:
                print("outer")
        print(nested_returns())
        n = 0
        while n < 5:
            n += 1
            try:
                if n == 3:
                    break
            finally:
                print("while finally", n)
        else:
            print("never")
    """)


def test_found_while_verifying(found: tuple[str, str]) -> None:
    same(found[1])


def test_builtins_of_the_prelude_present_as_cpythons() -> None:
    """print is a builtin_function_or_method, never bound as a method; property is immutable; the
    prelude's methods of the C++ types check their receiver; object.__new__ is bound to object
    (found while verifying, RL-217 and RL-218)."""
    same("""
        print(print, type(print).__name__, print.__name__, isinstance(print, type(lambda: 0)))
        class C:
            p = print
        C().p("not bound")
        try:
            property.x = 1
        except TypeError as e:
            print("TypeError", e)
        print(list.append, type(list.append).__name__, [].append.__self__)
        print(object.__new__.__self__, repr(object.__new__)[:43])
        print(repr(int), repr(object), int.__qualname__, type(None))
        for f, a in ((list.__repr__, 5), (set.__repr__, frozenset()), (frozenset.__repr__, set()), (dict.__repr__, [])):
            try:
                f(a)
            except TypeError as e:
                print("TypeError", e)
    """)


def test_names_cpython_has_are_refused() -> None:
    if shutil.which("g++") is None:
        return
    for what, body in REFUSED.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr, (what, got)


def test_generated_names_are_unreserved_and_reproducible() -> None:
    """No identifier the emitter makes contains `__` or starts `_` and a capital (C++ reserves
    them), and the C++ is the same whatever the hash seed (review 2026-11-03, A9-20)."""
    import re
    src = "class T:\n    def __init__(self):\n        self.__x = 1\ndef zażółć():\n    return 1\nprint(zażółć(), T().__init__.__name__)\n"
    outs = []
    for seed in ("0", "1"):
        code = ("import sys; sys.path.insert(0, '.'); from pipeline.build import to_cpp; "
                f"sys.stdout.write(to_cpp({src!r}, 'p.py', 'p'))")
        outs.append(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                   env=dict(os.environ, PYTHONHASHSEED=seed)).stdout)
    assert outs[0] == outs[1]
    text = re.sub(r"//.*", "", re.sub(r'"(?:[^"\\]|\\.)*"', '""', outs[0]))
    reserved = {m for m in re.findall(r"\b[A-Za-z_]\w*\b", text) if "__" in m or re.match(r"_[A-Z]", m)}
    assert not reserved, reserved
    same(src)


if __name__ == "__main__":
    for finding in FINDINGS:
        test_finding(finding)
    test_every_way_out_of_a_finally_a9_5_a9_6()
    for found in FOUND:
        test_found_while_verifying(found)
    test_builtins_of_the_prelude_present_as_cpythons()
    test_names_cpython_has_are_refused()
    test_generated_names_are_unreserved_and_reproducible()
    print(f"ok {len(FINDINGS)} findings, the finally matrix and {len(FOUND) + 3} found while verifying")
