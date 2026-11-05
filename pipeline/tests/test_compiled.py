"""Compiled programs against CPython (step 3a.1 of the C++ leg, docs/emitter.md).

Each program goes through the frontend, L2 and the C++ emitter, is compiled against the runtime
(pipeline/build.py) and run; its output and exit status must be CPython's. The programs use what
the runtime has: functions, closures, exceptions, try/finally on every way out, loops, unpacking,
strings, tuples, lists and dicts, and since step 3a.2 classes and their special methods. Exceptions are printed by
type, never by message (CLAUDE.md).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from conformance.harness import mask_stderr
from pipeline.build import build

_HAVE_CXX = shutil.which("g++") is not None


def same(src: str, hashseed: str | None = None) -> str:
    """The program's stdout and exit status, compiled and under CPython; `hashseed` fixes
    PYTHONHASHSEED for both when the output depends on str hashes (a set's order)."""
    src = textwrap.dedent(src)
    env = dict(os.environ, PYTHONHASHSEED=hashseed) if hashseed is not None else None
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False, cwd=tmp, env=env)
        exe = build(prog, "prog.py")
        got = subprocess.run([str(exe)], capture_output=True, text=True, check=False, cwd=tmp, env=env)
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


def test_an_instance_dict_is_an_ordinary_dict_3a3() -> None:
    """vars(obj) is a dict like any other (step 3a.3, design section 3): any key, the dict's
    methods and their errors, attributes read through keys the program built, `del obj.__dict__`,
    and a lookup that starts again when a key's __eq__ changes the dict."""
    same('class C:\n    pass\no = C()\nvars(o)[1] = "int key"\nvars(o)["a" + "b"] = "built key"\nprint(o.ab, vars(o), len(vars(o)), 1 in vars(o), [k for k in vars(o) if isinstance(k, str)])\no.z = 3\ndel vars(o)["z"]\nprint(hasattr(o, "z"), list(vars(o).items()), list(vars(o).keys()), list(vars(o).values()))\nd = vars(o)\ndel o.__dict__\nprint(d is vars(o), vars(o), d)\np = C(); p.x = 1; p.y = 2\nq = vars(p).copy(); q["w"] = 9\nprint(q, vars(p), vars(p).setdefault("x", 5), vars(p).setdefault("n"), vars(p))\nvars(p).update({"u": 1}, v=2); vars(p).update([("t", 3)])\nprint(list(vars(p).items()), vars(p).popitem(), dict.fromkeys("ab", 0), dict.fromkeys([1]))\nvars(p).clear(); print(vars(p), hasattr(p, "x"))\nfor f in (lambda: {}.popitem(), lambda: {}.update([(1, 2, 3)]), lambda: {}.update({}, {}), lambda: {}.setdefault(),\n          lambda: {}.copy(1), lambda: {}.get(), lambda: {}.keys(1), lambda: {}.pop(1, 2, 3), lambda: {}.get(k=1)):\n    try:\n        f()\n    except (KeyError, TypeError, ValueError) as e:\n        print(type(e).__name__, e)\nclass K:\n    def __init__(self, d): self.d = d\n    def __hash__(self): return 1\n    def __eq__(self, other):\n        if self.d is not None:\n            self.d.clear(); self.d[K(None)] = "re-added"\n            self.d = None\n        return False\nd = {}\nd[K(None)] = "first"\nprint(d.get(K(d), "restart ends: absent"), len(d))\ntry:\n    C.__dict__["x"] = 1\nexcept TypeError as e:\n    print("TypeError", type(C.__dict__).__name__)\n')


def test_dict_views_3a3() -> None:
    """keys(), values() and items() are live views: their types, repr (recursion included),
    len, `in`, iteration that fails when the dict changes size, and hashing."""
    same("d = {'a': 1, 'b': [2]}\nk, v, i = d.keys(), d.values(), d.items()\nprint(k, v, i, type(k).__name__, type(iter(v)).__name__, type(iter(i)).__name__, type(iter(k)).__name__)\nprint(len(k), 'a' in k, 1 in v, ('a', 1) in i, ('a', 2) in i, ['a', 1] in i, bool({}.keys()), list(i))\nfor x in (k, v, i):\n    try:\n        print(type(x).__name__, hash(x) is not None)\n    except TypeError as e:\n        print(e)\nprint(v == v, v == d.values())\ne = {}\ne['self'] = e.values()\nprint(repr(e.values()), repr(e))\nd['c'] = 3\nprint(k, len(v), list(i)[-1])\ntry:\n    for key in d:\n        d['z'] = 3\nexcept RuntimeError as err:\n    print(err)\nit = iter(d.items())\nnext(it)\nd['new'] = 1\ntry:\n    next(it)\nexcept RuntimeError as err:\n    print('items', err)\nfor x, y in d.items():\n    print(x, y, end='; ')\nprint()\ntry:\n    {}.keys().__repr__.__self__\nexcept Exception:\n    pass\n")


def test_an_exposed_dict_stays_split_compiled_3a3() -> None:
    """The model's scenarios (refmodel/tests/test_cases.py) compiled: whether an exposed dict is
    split, so its values die in the class's key order, after each dict operation."""
    from refmodel.tests.test_cases import SPLIT_PRELUDE, SPLIT_SCENARIOS, split_program
    parts = [SPLIT_PRELUDE]
    for name in SPLIT_SCENARIOS:
        parts.append(f"print('== {name}')\n" + split_program(name))
    same("\n".join(parts))


def test_dict_view_set_operations_are_refused_3a3() -> None:
    """What the views cannot do yet stops the program (exit 70), never answers wrongly."""
    if not _HAVE_CXX:
        return
    for op in ("d.keys() & {'a'}", "d.items() | set()", "d.keys() == {'a'}", "d.keys().isdisjoint([])"):
        src = f"d = {{'a': 1}}\nprint('start')\nprint({op})\n"
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(src, encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr, (op, got)


def test_argument_errors_are_cpythons() -> None:
    """Every C++ builtin and method a program can call refuses a wrong number of arguments, or a
    keyword, in CPython's words for its calling convention (METH_O, METH_NOARGS, argument clinic,
    slot wrapper); list.index takes start and stop."""
    same('L = [1, 2, 3, 2]\nprint(L.index(2, 2), L.index(2, -3), L.index(2, 0, 2), L.index(3, -100, 100))\nfor a in ((2, 4), (9,), (2, 0, 1), (2, \'x\')):\n    try:\n        L.index(*a)\n    except (ValueError, TypeError) as e:\n        print(type(e).__name__, e)\ncases = {\n "abs": (abs, 1, 1), "callable": (callable, 1, 1), "chr": (chr, 1, 1), "delattr": (delattr, 2, 2), "format": (format, 1, 2),\n "hasattr": (hasattr, 2, 2), "hash": (hash, 1, 1), "id": (id, 1, 1), "isinstance": (isinstance, 2, 2), "issubclass": (issubclass, 2, 2),\n "iter": (iter, 1, 2), "len": (len, 1, 1), "next": (next, 1, 2), "ord": (ord, 1, 1), "repr": (repr, 1, 1), "setattr": (setattr, 3, 3),\n "bool": (bool, 0, 1), "list": (list, 0, 1), "tuple": (tuple, 0, 1), "range": (range, 1, 3),\n "list.append": (L.append, 1, 1), "list.clear": (L.clear, 0, 0), "list.copy": (L.copy, 0, 0), "list.count": (L.count, 1, 1),\n "list.extend": (L.extend, 1, 1), "list.index": (L.index, 1, 3), "list.insert": (L.insert, 2, 2), "list.pop": (L.pop, 0, 1),\n "list.remove": (L.remove, 1, 1), "list.reverse": (L.reverse, 0, 0), "list.__len__": (L.__len__, 0, 0), "list.__iter__": (L.__iter__, 0, 0),\n "list.__getitem__": (L.__getitem__, 1, 1), "list.__setitem__": (L.__setitem__, 2, 2), "list.__contains__": (L.__contains__, 1, 1),\n "dict.__getitem__": ({}.__getitem__, 1, 1), "dict.__setitem__": ({}.__setitem__, 2, 2), "dict.__contains__": ({}.__contains__, 1, 1),\n "dict.__iter__": ({}.__iter__, 0, 0), "dict.__len__": ({}.__len__, 0, 0), "str.join": ("".join, 1, 1), "str.__getitem__": ("".__getitem__, 1, 1),\n "str.__contains__": ("".__contains__, 1, 1), "str.__iter__": ("".__iter__, 0, 0), "tuple.__getitem__": (().__getitem__, 1, 1),\n "set.__len__": (set().__len__, 0, 0), "set.__contains__": (set().__contains__, 1, 1), "set.__iter__": (set().__iter__, 0, 0),\n "keys.__len__": ({}.keys().__len__, 0, 0), "keys.__contains__": ({}.keys().__contains__, 1, 1), "values.__iter__": ({}.values().__iter__, 0, 0),\n}\nfor name, (f, lo, hi) in cases.items():\n    out = []\n    trials = []\n    zeros = [(), (0,), (0, 0), (0, 0, 0), (0, 0, 0, 0)]\n    if lo > 0:\n        trials.append((zeros[lo - 1], {}))\n    trials.append((zeros[hi + 1], {}))\n    for args, kw in trials:\n        try:\n            f(*args)\n            out.append("OK")\n        except TypeError as e:\n            out.append(str(e))\n    try:\n        if lo == 0:\n            f(zz=1)\n        elif lo == 1:\n            f(0, zz=1)\n        elif lo == 2:\n            f(0, 0, zz=1)\n        else:\n            f(0, 0, 0, zz=1)\n        out.append("OK")\n    except TypeError as e:\n        out.append(str(e))\n    print(name, "|", " | ".join(out))\n')


def test_a_starred_call_3a3() -> None:
    """f(*value): a tuple as it is, any iterable made a tuple, anything else CPython's TypeError."""
    same('def f(*a):\n    return a\nt = (1, 2)\nprint(f(*t), f(*[3]), f(0, *t), f(*"ab"), f(*{"k": 1}), f(*range(2)))\nclass S:\n    def __getitem__(self, i):\n        if i > 1:\n            raise IndexError\n        return i\nprint(f(*S()))\ntry:\n    f(*5)\nexcept TypeError as e:\n    print(e)\n')


def test_operators_on_builtin_types_are_cpythons() -> None:
    """Equality of dicts, sets, ranges and slices; set ordering and algebra in CPython's order of
    insertion (so their iteration order, with colliding str hashes); repetition and concatenation
    as sequence slots after the number slots (so `+=` defers to __radd__ and `*=` keeps a list);
    dict | and |=; in-place set operators; the errors CPython raises; one empty tuple."""
    same('print({1} == {1}, {1} == frozenset({1}), {1: 2} == {1: 2}, {1: 2} != {1: 3}, range(2) == range(0, 2), range(0) == range(5, 5))\nprint(range(1, 2) == range(1, 9, 9), slice(1) == slice(1), slice(1, 2) < slice(1, 3), {1} < {1, 2}, {1, 2} >= {2}, {1} > {1})\nprint([0] * 3, 2 * (1,), "ab" * 2, [1] * 0, (1,) * -1, [1, 2] * True)\nt = (1, 2)\ne = ()\nprint(t * 1 is t, e * 5 is (), tuple([]) is e, "x" * 1)\nwords = ["w" + str(i) for i in range(40)]\na = set(words[:25])\nb = set(words[10:40])\nprint(list(a | b))\nprint(list(a & b))\nprint(list(b & a))\nprint(list(a - b))\nprint(list(b - a))\nprint(list(a ^ b))\nprint(list(frozenset(a) | b), type(frozenset(a) | b).__name__, type(a | frozenset(b)).__name__)\nsmall = set(words[:3])\nprint(list(set(words) - small))\nc = set(a)\nd = c\nc |= b\nprint(c is d, list(c))\nc &= set(words[5:15])\nprint(c is d, list(c))\nc -= {"w5", "w6"}\nc ^= {"w7", "zz"}\nprint(c is d, list(c))\nc -= c\nprint(c, c is d)\nx = {1: 2}\ny = x\nx |= [(3, 4)]\nprint(x is y, x, {1: 2} | {3: 4, 1: 5})\nl = [1]\nm = l\nl *= 2\nl += (3,)\nprint(l is m, l)\nclass R:\n    def __radd__(self, other):\n        return "radd"\n    def __rmul__(self, other):\n        return "rmul"\nq = [1]\nq += R()\nprint(q, [1] * R())\nclass I:\n    def __index__(self):\n        return 2\nprint([7] * I(), I() * (8,))\nfor f in (lambda: [1] + (1,), lambda: (1,) + [1], lambda: "a" + 1, lambda: [1] * "a", lambda: "a" * 1.0 if False else "a" * [1],\n          lambda: {1} < [1], lambda: range(1) < range(2), lambda: 1 + "a"):\n    try:\n        print(f())\n    except TypeError as e:\n        print("TypeError", e)\nn = 1\ntry:\n    n += "a"\nexcept TypeError as e:\n    print("TypeError", e)\n', hashseed="0")


def test_operators_cpython_has_and_the_runtime_lacks_are_refused() -> None:
    """str % (formatting), type | type, a keys view compared as a set: refused, never TypeError."""
    if not _HAVE_CXX:
        return
    for body in ("print('%d' % 5)", "print(int | str)", "print({1: 2}.keys() == {1})", "class C:\n    pass\nprint('%s' % C())"):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr, (body, got)


def test_a_builtin_type_without_a_constructor_is_refused() -> None:
    """RL-220: int(), float(), dict() and type(len)() fell into object.__new__ and raised TypeErrors
    CPython does not ("int() takes no arguments" for int("42")); they are refused. An explicit
    object.__new__(int) is checked before its arguments, with CPython's message. dict() and int()
    have their own constructors since the subclasses of built-ins (decision 2026-11-03). A type with
    no __new__ of its own in CPython cannot be made there either: type(len)() is CPython's TypeError."""
    if not _HAVE_CXX:
        return
    same('for f in (lambda: object.__new__(int), lambda: object.__new__(dict, 1), lambda: object(1)):\n    try:\n        f()\n    except TypeError as e:\n        print("TypeError", e)\nprint(type(object()).__name__, str(5), list("ab"), dict(a=1), int("42"), int())\n')
    same("for f in (lambda: type(len)(), lambda: object.__new__(type(len)), lambda: type(iter([]))(), lambda: type({}.keys())()):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n")
    for body in ("type(...)()",):                # float() was the example, until it had its own (C-6-12)
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\ntry:\n    {body}\nexcept TypeError:\n    print('TypeError')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr, (body, got)



def same_report(src: str, merged: bool = False) -> None:
    """stdout, stderr and the exit status, compiled and under CPython; stderr with the harness's
    D-06 mask (a traceback frame is file and line; the source echo dropped), addresses hidden.
    `merged`: one stream, as `2>&1` shows it, so the order of the two is compared too."""
    src = textwrap.dedent(src)
    err = subprocess.STDOUT if merged else subprocess.PIPE
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        runs = [subprocess.run(cmd, stdout=subprocess.PIPE, stderr=err, text=True, check=False, cwd=tmp)
                for cmd in ([sys.executable, str(prog)], [str(build(prog, "prog.py"))])]
    ref, got = ((mask_stderr(r.stdout) if merged else r.stdout, re.sub(r" at 0x[0-9a-f]+", "", mask_stderr(r.stderr or "")),
                 r.returncode) for r in runs)
    assert got == ref, f"\n--- compiled\n{got[0]}{got[1]}\n--- CPython\n{ref[0]}{ref[1]}"


_REPORTS = {
    "raise in a try, through its finally": """
        def g():
            try:
                raise ValueError("boom")
            finally:
                y = 2
        g()
        """,
    "a bare raise keeps the original line": """
        def f():
            try:
                x = [][0]
            except IndexError:
                y = 1
                raise
        f()
        """,
    "raise e lists the frame twice": """
        def f():
            try:
                x = [][0]
            except IndexError as e:
                y = 1
                raise e
        f()
        """,
    "a failed call under a finally": """
        def g():
            raise KeyError("k")
        def f():
            try:
                g()
            finally:
                z = 3
        f()
        """,
    "a raise in a loop's try": """
        def f():
            for i in range(3):
                try:
                    if i == 2:
                        raise ValueError(i)
                finally:
                    k = i
        f()
        """,
    "a bare raise in a function called from a handler": """
        def g():
            raise
        def f():
            try:
                x = [][0]
            except IndexError:
                g()
        f()
        """,
    "the prelude has no frames": """
        class C:
            def __repr__(self):
                raise KeyError("in repr")
        def f():
            x = [C()]
            print(repr(x))
        f()
        """,
    "an inlined comprehension has no frame": """
        def f(n):
            return [10 // (x - n) for x in range(3)]
        f(1)
        """,
    "the cause and the context are reported": """
        def f():
            try:
                x = [][0]
            except IndexError as e:
                raise KeyError("k") from e
        try:
            f()
        except KeyError:
            raise RuntimeError("during")
        """,
    "an unraisable exception's chain": """
        class D:
            def __del__(self):
                try:
                    [][0]
                except IndexError:
                    raise KeyError("from del")
        d = D()
        del d
        print("after")
        """,
    "stdout is flushed before the report": """
        import sys
        print("out")
        sys.stderr.write("err\\n")
        raise KeyError(1)
        """,
}


def test_traceback_entries_and_the_report_are_cpythons() -> None:
    """RL-221: a frame is recorded where the exception arrives, not where it leaves; RL-223 and
    RL-224: an inlined comprehension and the prelude have no frames; RL-226: the report prints
    the chain; RL-227: stdout is flushed before it (C-3-30 runs them together)."""
    if not _HAVE_CXX:
        return
    for name, src in _REPORTS.items():
        try:
            same_report(src, merged=name.startswith("stdout is flushed"))
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
