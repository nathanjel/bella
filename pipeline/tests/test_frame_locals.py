"""locals(), vars() and dir() of the calling frame, compiled against CPython (C-8-15, C-8-03; the author's decision of
2026-11-14: every function answers, from the variables its frame already hands the runtime).

The case has the kinds of frame; here are the shapes of a function's variables that the table of a code record has to get
right (Code::frame_slots: where each name CPython's code object has is kept among the frame's variables): every kind of
parameter, names bound by every statement that binds, cells and free variables of several depths, `__class__`, a generator
between its yields, generic functions, names a comprehension used and gave back, deleted and never bound ones. And the
stop that stays: inside a list, set or dict comprehension, whose variables are the frame's around it while it runs (PEP 709).

Run under pytest or directly: python3 -m pipeline.tests.test_frame_locals
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_compiled_imports import same

FUNCTIONS = r"""
import functools
import operator


def every_parameter(a, b=2, /, c=3, d=4, *args, e, f=6, **kwargs):
    return list(locals().items())


print(every_parameter(1, e=5))
print(every_parameter(1, 20, 30, 40, 50, 60, e=5, f=7, g=8))


def no_star(a, *, b):
    return list(locals()), dir(), list(vars())


print(no_star(1, b=2))


def only_star(*args, **kwargs):
    extra = len(args)
    return list(locals().items())


print(only_star(1, 2, k=3))


def binders(seq):
    global made_global
    made_global = 1
    for index, (left, right) in enumerate(seq):
        pass
    else:
        after_loop = True
    while (count := len(seq)) > 5:
        break
    with open(__file__, encoding="utf-8") as handle, open(__file__, "rb") as second:
        pass
    try:
        import os.path as osp
        from operator import add as plus, sub
        raise KeyError("k")
    except (KeyError, ValueError) as error:
        inside = list(locals())
    finally:
        cleanup = "done"

    def nested_function():
        pass

    class NestedClass:
        pass

    match seq:
        case [first, *others]:
            matched = True
        case {"key": captured}:
            matched = False
    lam = lambda: None
    star, *rest_of = seq
    aug = 1
    aug += 1
    annotated: int = 5
    only_declared: str
    return inside, list(locals()), "made_global" in locals(), "error" in locals(), sorted(locals()) == dir(), type(locals()["handle"]).__name__


for row in binders([(1, 2), (3, 4)]):
    print(row)


def deletions(a, b):
    c = 1
    d = 2
    del a, c
    first = list(locals())
    a = 5
    second = list(locals())
    del b
    del d
    return first, second, list(locals())


print(deletions(1, 2))


def conditional(flag):
    if flag:
        yes = 1
    else:
        no = 2
    return list(locals())


print(conditional(True), conditional(False))


def after_comprehensions(n):
    squares = [x * x for x in range(n)]
    table = {k: v for k, v in zip("ab", squares)}
    seen = {y for y in squares if y}
    lazy = (z for z in squares)
    x = "an x of its own"
    return list(locals()), sorted(k for k in locals() if len(k) == 1)


print(after_comprehensions(3))


def cells(a, b, c):
    own = 1
    shared_one = 2
    zeta = 3
    alpha = 4

    def middle(m):
        mid_own = shared_one + a

        def innermost():
            nonlocal zeta
            zeta = alpha + c + m
            return list(locals()), dir()

        return list(locals()), innermost(), list(locals().items())[:2]

    before = list(locals())
    result = middle(10)
    return before, result, list(locals()), locals()["zeta"]


for row in cells(1, 2, 3):
    print(row)


def cell_states():
    empty: int

    def reader():
        return empty

    one = list(locals())
    empty = 1
    two = list(locals().items())[-1]
    del empty
    return one, two, list(locals())


print(cell_states())


class Shape:
    def area(self, factor):
        return list(locals())

    def with_super(self, factor):
        super().__init__()
        return list(locals()), locals()["__class__"] is Shape

    def with_class_cell(self):
        return __class__.__name__, list(locals())

    @staticmethod
    def static(value):
        return list(locals())

    @classmethod
    def clsm(cls, value):
        return list(locals())

    @property
    def prop(self):
        return list(locals())

    def __private(self, __p=1):
        __q = 2
        return list(locals())

    def reach(self):
        return self.__private()


shape = Shape()
print(shape.area(2), shape.with_super(3), shape.with_class_cell(), Shape.static(1), Shape.clsm(2), shape.prop, shape.reach())


def stops(limit):
    total = 0
    seen = [list(locals())]
    for i in range(limit):
        total += i
        got = yield list(locals())
        seen.append(got)
    try:
        yield sorted(locals())
    finally:
        last = "set in finally"
        seen.append(sorted(locals()))
    return seen


steps = stops(2)
print(next(steps), steps.send("sent"), steps.send("again"))
try:
    next(steps)
except StopIteration as stop:
    print(stop.value)


def generic[T, *Ts, **P](value: T, *rest: *Ts) -> list[str]:
    inner: T = value
    return list(locals())


print(generic(1, 2, 3), generic.__type_params__)


class Generic[T]:
    def method(self, value: T) -> list[str]:
        return list(locals())

    names = sorted(n for n in dir() if not n.startswith("__"))


print(Generic().method(1), Generic.names)


def decorated(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return list(locals()), fn(*args, **kwargs)
    return wrapper


@decorated
def target(x, y=2):
    return list(locals().items())


print(target(1))
print((lambda a, *b, c=3, **d: list(locals().items()))(1, 2, x=4))
print((lambda: (lambda: list(locals()))())(), (lambda q: (lambda: q and list(locals()))())(1))


def recursion(n, acc=()):
    if n:
        return recursion(n - 1, (*acc, tuple(locals())))
    return acc, tuple(locals())


print(recursion(2))


def shadows_builtins():
    locals_before = locals()
    vars = "a local named vars"
    dir = "a local named dir"
    return sorted(locals_before), sorted(locals()), vars, dir


print(shadows_builtins())


def exceptions():
    try:
        try:
            raise ValueError(1)
        except ValueError as first:
            names_inner = sorted(locals())
            raise TypeError(2) from first
    except TypeError as second:
        names_outer = sorted(locals())
    return names_inner, names_outer, sorted(locals())


print(exceptions())


def identity(a, b=[]):
    snapshot = locals()
    return snapshot["a"] is a, snapshot["b"] is b, locals()["snapshot"] is snapshot, vars()["snapshot"]["a"] is a


print(identity(object()))
print("callers:", (lambda: sorted(functools.reduce(lambda acc, f: acc | set(f()), [locals, vars], set())))(),
      (lambda only: list(map(operator.call, [locals, vars, dir])))(1))
"""

NAMESPACES = r"""
import types

print(locals() is globals(), vars() is globals(), dir() == sorted(globals()), dir() == sorted(vars()), "types" in dir())
locals()["through_locals"] = 1
vars()["through_vars"] = 2
print(through_locals, through_vars)


class Plain:
    a = 1
    snapshot = dict(locals())
    locals()["b"] = 2
    del a
    after = sorted(n for n in locals() if not n.startswith("__"))
    same = (locals() is locals(), vars() is locals(), type(locals()).__name__)

    class Inner:
        deep = sorted(n for n in locals() if not n.startswith("__"))
        qualname = locals()["__qualname__"]

    def method(self):
        return sorted(locals())


print(sorted(Plain.snapshot), Plain.b, Plain.after, Plain.same, Plain.Inner.deep, Plain.Inner.qualname, Plain().method(), hasattr(Plain, "a"))


class Recording(dict):
    def __init__(self):
        super().__init__()
        self.log = []

    def __setitem__(self, key, value):
        self.log.append(("set", key))
        super().__setitem__(key, value)

    def keys(self):
        self.log.append(("keys",))
        return super().keys()


class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return Recording()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, dict(namespace))
        cls.log = namespace.log
        return cls


class Prepared(metaclass=Meta):
    one = 1
    is_it = type(locals()).__name__, locals() is vars()
    listed = dir()
    locals()["two"] = 2


print(Prepared.is_it, Prepared.listed, Prepared.two, Prepared.log)


class NotADict:
    def __init__(self):
        self.data = {}

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def keys(self):
        return iter(sorted(self.data, reverse=True))


class MetaMapping(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return NotADict()

    def __new__(mcs, name, bases, namespace):
        return super().__new__(mcs, name, bases, dict(namespace.data))


class Mapped(metaclass=MetaMapping):
    zed = 1
    kind = type(locals()).__name__
    listed = dir()
    same = locals() is vars()


print(Mapped.kind, Mapped.listed, Mapped.same)


def function_with_class(free):
    captured = free * 2

    class Local:
        uses = captured
        names = sorted(n for n in locals() if not n.startswith("__"))
        has_free = "captured" in locals(), "free" in dir()

        def method(self):
            return captured, sorted(locals())

    return Local.names, Local.has_free, Local().method(), sorted(locals())


print(function_with_class(3))
namespace = types.SimpleNamespace(x=1)
print(vars(namespace), vars(Plain)["b"], dir(namespace)[-1], vars(types)["SimpleNamespace"] is types.SimpleNamespace)
for bad in (lambda: locals(1), lambda: locals(a=1), lambda: vars(1, 2), lambda: vars(a=1), lambda: dir(1, 2), lambda: dir(a=1), lambda: vars(1), lambda: vars([])):
    try:
        bad()
    except TypeError as error:
        print(type(error).__name__)
"""

# Inside a list, set or dict comprehension the frame's locals include the comprehension's own variables (PEP 709): not yet
STOPS = (
    "def f():\n    return [locals() for _ in range(1)]\nprint('start')\nf()\n",
    "def f():\n    return {n: vars() for n in range(1)}\nprint('start')\nf()\n",
    "def f():\n    return {tuple(dir()) for n in range(1)}\nprint('start')\nf()\n",
    "import operator\ndef f():\n    return [operator.call(locals) for _ in range(1)]\nprint('start')\nf()\n",
    "print('start')\n[locals() for _ in range(1)]\n",
    "print('start')\nclass C:\n    names = [dir() for _ in range(1)]\n",
)


def _stops(source: str, words: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and words in got.stderr, got


def test_a_functions_variables_of_every_kind() -> None:
    same({"main.py": FUNCTIONS})


def test_a_modules_and_a_class_bodys_namespace() -> None:
    """The namespace itself: writes go through; the mapping `__prepare__` gave, a dict subclass or no dict at all, whose own
    keys() dir() asks; vars() and dir() with an argument as before; the argument errors."""
    same({"main.py": NAMESPACES})


def test_inside_an_inlined_comprehension_stops() -> None:
    for source in STOPS:
        _stops(source, "inside a list, set or dict comprehension")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
