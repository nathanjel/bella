"""Compiled programs against CPython (step 3a.1 of the C++ leg, docs/emitter.md).

Each program goes through the frontend, L2 and the C++ emitter, is compiled against the runtime
(pipeline/build.py) and run; its output and exit status must be CPython's. The programs use what
the runtime has: functions, closures, exceptions, try/finally on every way out, loops, unpacking,
strings, tuples, lists and dicts, and since step 3a.2 classes and their special methods. Exceptions are printed by
type, never by message (CLAUDE.md).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from pipeline.build import build

_HAVE_CXX = shutil.which("g++") is not None


def same(src: str) -> str:
    src = textwrap.dedent(src)
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False, cwd=tmp)
        exe = build(prog, "prog.py")
        got = subprocess.run([str(exe)], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (
        f"\n--- compiled (exit {got.returncode})\n{got.stdout}{got.stderr}\n--- CPython (exit {ref.returncode})\n"
        f"{ref.stdout}{ref.stderr}")
    return ref.stdout


def test_argument_binding_follows_cpython() -> None:
    if not _HAVE_CXX:
        return
    same('''
        def f(a, b=2, *args, c, d=4, **kw):
            print(a, b, len(args), c, d, len(kw))
        def g(x, /, y=0):
            print(x, y)
        f(1, c=3)
        f(1, 2, 3, 4, c=5, e=6, z=7)
        g(1, y=2)
        g(5)
        calls = [lambda: f(), lambda: f(1), lambda: g(x=1, y=2), lambda: g(1, 2, 3), lambda: g(1, y=2, y2=3),
                 lambda: f(1, 2, c=3, b=4)]
        for call in calls:
            try:
                call()
            except TypeError as e:
                print("TypeError")
    ''')


def test_closures_nonlocal_and_global() -> None:
    if not _HAVE_CXX:
        return
    same('''
        counter = 0
        def make(start):
            total = start
            def add(n):
                nonlocal total
                total += n
                return total
            return add
        def bump():
            global counter
            counter += 1
        acc = make(10)
        print(acc(1), acc(2), acc(3))
        bump(); bump()
        print("counter", counter)
        def outer():
            x = 1
            def inner():
                return x * 2
            x = 5
            return inner()
        print(outer())
        def unbound():
            try:
                print(later)
            except NameError as e:
                print(type(e).__name__)
            later = 1
        unbound()
    ''')


def test_exceptions_propagate_and_are_handled() -> None:
    if not _HAVE_CXX:
        return
    same('''
        def div(a, b):
            return a // b
        def chain(n):
            if n == 0:
                return div(1, 0)
            return chain(n - 1)
        for f in (lambda: chain(3), lambda: undefined_name, lambda: [1][5], lambda: {}["k"], lambda: 1 + "a",
                  lambda: int.nothing, lambda: (1, 2)[0](3)):
            try:
                f()
            except (ZeroDivisionError, NameError, IndexError, KeyError) as e:
                print("caught", type(e).__name__)
            except TypeError:
                print("caught TypeError")
            except AttributeError:
                print("caught AttributeError")
        try:
            try:
                raise ValueError("inner")
            except ValueError:
                print("handling, re-raising")
                raise
        except ValueError as e:
            print("outer got", type(e).__name__, e.args == ("inner",))
        try:
            try:
                1 // 0
            except ZeroDivisionError as z:
                raise KeyError("k") from z
        except KeyError as k:
            print("cause", type(k.__cause__).__name__, k.__suppress_context__)
        try:
            try:
                1 // 0
            except ZeroDivisionError:
                raise IndexError("during")
        except IndexError as i:
            print("context", type(i.__context__).__name__)
        try:
            raise
        except RuntimeError:
            print("no active exception: RuntimeError")
    ''')


def test_finally_runs_on_every_way_out() -> None:
    if not _HAVE_CXX:
        return
    same('''
        def ret(x):
            try:
                if x:
                    return "returned"
                print("body ran")
            finally:
                print("finally", x)
            return "fell through"
        print(ret(1), ret(0))
        for i in range(4):
            try:
                if i == 1:
                    continue
                if i == 3:
                    break
                print("body", i)
            finally:
                print("finally", i)
        else:
            print("never")
        def nested():
            try:
                try:
                    return "inner"
                finally:
                    print("inner finally")
            finally:
                print("outer finally")
        print(nested())
        def raising():
            try:
                1 // 0
            finally:
                print("finally before the handler")
        try:
            raising()
        except ZeroDivisionError:
            print("handler")
        def else_clause(x):
            try:
                v = 10 // x
            except ZeroDivisionError:
                print("except")
            else:
                print("else", v)
            finally:
                print("finally")
        else_clause(2)
        else_clause(0)
    ''')


def test_loops_unpacking_and_containers() -> None:
    if not _HAVE_CXX:
        return
    same('''
        total = 0
        for i in range(10, 0, -3):
            total += i
        print("total", total)
        n = 0
        while n < 5:
            n += 2
        else:
            print("while else", n)
        a, b = 1, 2
        a, b = b, a
        first, *middle, last = [1, 2, 3, 4, 5]
        print(a, b, first, len(middle), last)
        try:
            x, y = [1]
        except ValueError:
            print("ValueError")
        t = (1, 2, 3)
        l = [4, 5]
        l.append(6) if False else None
        print(t[0], t[-1], l[1], len(t + (4,)), len(l + l), 2 in t, 7 not in l)
        d = {"a": 1, "b": 2}
        d["c"] = 3
        del d["a"]
        for k in d:
            print("key", k, d[k])
        print(len(d), "b" in d, "a" in d)
        s = "abc"
        for ch in s:
            print(ch, end="")
        print()
        print(s[1], s[-1], len(s), "b" in s, s + "d", s * 2, "-".join(["x", "y", "z"]))
        print(f"{s}={len(s)} {s!r}")
        print(1 < 2 < 3, 3 < 2 < 1, 1 == 1.0 if False else True)
        print(repr("it's"), repr('say "hi"'), repr("tab\\tnew\\nline"))
        print(not 0, not 1, 0 or "x", "" and "y", None is None)
    ''')


def test_print_sep_end_and_errors() -> None:
    if not _HAVE_CXX:
        return
    same('''
        print(1, 2, 3, sep="-", end="!\\n")
        print("a", "b", sep="")
        print()
        print("x", sep=None, end=None)
        try:
            print(1, sep=5)
        except TypeError:
            print("TypeError")
        import sys
        print("to stdout", file=sys.stdout, flush=True)
    ''')


def test_uncaught_exception_exits_with_status_1() -> None:
    if not _HAVE_CXX:
        return
    same('''
        def f():
            return 1 // 0
        print("before")
        f()
    ''')


# ---- step 3a.2: classes ------------------------------------------------------------------------


def test_classes_methods_and_attributes() -> None:
    if not _HAVE_CXX:
        return
    same("""
        class Base:
            kind = "base"
            def __init__(self, x):
                self.x = x
            def show(self):
                return f"{type(self).__name__}({self.x})"
            @staticmethod
            def helper(n):
                return n * 2
            @classmethod
            def make(cls, x):
                return cls(x)
            @property
            def double(self):
                return self.x * 2
            @double.setter
            def double(self, v):
                self.x = v // 2
        class Child(Base):
            kind = "child"
            def show(self):
                return "child " + Base.show(self)
        c = Child.make(5)
        print(c.show(), c.kind, Base.kind, c.helper(4), Child.helper(1), c.double)
        c.double = 20
        print(c.x, isinstance(c, Base), issubclass(Child, Base), type(c) is Child, Child.__mro__ == (Child, Base, object))
        print(Child.__name__, Child.__qualname__, Base.__doc__, getattr(c, "missing", "default"), hasattr(c, "x"))
        try:
            del c.double
        except AttributeError as e:
            print("AttributeError")
        try:
            Base()
        except TypeError:
            print("TypeError")
        class Slotted:
            __slots__ = ("a",)
        s = Slotted()
        try:
            s.b = 1
        except AttributeError as e:
            print("AttributeError", e.name)
        s.a = 3
        print(s.a, hasattr(s, "__dict__"))
    """)


def test_special_methods_follow_cpythons_protocols() -> None:
    if not _HAVE_CXX:
        return
    same("""
        log = []
        class V:
            def __init__(self, n): self.n = n
            def __add__(self, o):
                log.append("V.add")
                return V(self.n + (o.n if isinstance(o, V) else o))
            def __radd__(self, o):
                log.append("V.radd")
                return V(o + self.n)
            def __eq__(self, o): return isinstance(o, V) and self.n == o.n
            def __lt__(self, o): return self.n < o.n
            def __repr__(self): return f"V({self.n})"
            def __len__(self): return self.n
            def __bool__(self): return self.n != 0
            def __iter__(self): return iter(range(self.n))
            def __getitem__(self, i): return i * 10
            def __contains__(self, x): return x == "in"
            def __call__(self, *a): return len(a)
        class W(V):
            def __radd__(self, o):
                log.append("W.radd")
                return W(99)
        print(V(1) + V(2), 1 + V(2), V(1) + W(2), log)
        print(V(1) == V(1), V(1) != V(2), V(1) < V(2), V(2) > V(1), sorted_check := [V(3) < V(1)])
        print(len(V(3)), bool(V(0)), list(V(3)), V(2)[4], "in" in V(1), "out" in V(1), V(0)(1, 2, 3))
        print(repr(V(7)), str(V(7)), f"{V(8)}", [V(1), V(2)], {"k": V(3)}, (V(4),))
        class OnlyEq:
            def __eq__(self, o): return True
        try:
            hash(OnlyEq())
        except TypeError:
            print("unhashable")
        class Seq:
            def __getitem__(self, i):
                if i > 2:
                    raise IndexError
                return i
        print(list(Seq()), 2 in Seq())
        try:
            V(1) < 3
        except AttributeError:
            print("AttributeError from __lt__")
        try:
            object() < object()
        except TypeError:
            print("TypeError")
    """)


def test_descriptors_set_name_and_init_subclass() -> None:
    if not _HAVE_CXX:
        return
    same("""
        class Named:
            def __set_name__(self, owner, name):
                print("set_name", owner.__name__, name)
                self.name = name
            def __get__(self, obj, owner=None):
                return "got " + self.name if obj is not None else self
        class Registry:
            subclasses = []
            def __init_subclass__(cls, **kw):
                print("init_subclass", cls.__name__, sorted_keys(kw))
                Registry.subclasses.append(cls.__name__)
        def sorted_keys(d):
            out = []
            for k in d:
                out.append(k)
            return out
        class A(Registry, tag="x"):
            first = Named()
            second = Named()
        print(A().first, A.second.name, Registry.subclasses)
        class E(Exception):
            def __init__(self, code):
                super_init = Exception.__init__
                super_init(self, "code", code)
                self.code = code
        try:
            raise E(7)
        except Exception as e:
            print(type(e).__name__, e.code, e.args, isinstance(e, E))
    """)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
