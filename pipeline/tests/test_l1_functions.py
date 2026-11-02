"""Gate 0 task 4, steps A1 and A2: parameters, calls with unpacking, lambdas, function objects,
decorators and PEP 649 annotations, eval1 against CPython. The conformance cases C-3-25 and
C-3-26 hold the same behaviour as dialect programs; they need classes and imports, which come
in steps A3 and A4, so here the class-based helpers are injected from the host.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_functions
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from pipeline.l1.frontend import clean_doc, lower
from pipeline.l1.grammar import Unsupported
from pipeline.tests.test_frontend_eval1 import both

trace: list[str] = []


class Logged(Mapping[str, int]):
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def keys(self) -> list[str]:  # type: ignore[override]
        trace.append("keys")
        return list(self.names)

    def __getitem__(self, key: str) -> int:
        trace.append("get " + key)
        return len(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)


class QuietDict(dict[str, int]):
    def keys(self) -> list[str]:  # type: ignore[override]
        trace.append("never")
        return []

    def __getitem__(self, key: str) -> int:
        trace.append("never")
        return 0


class GetitemKeyError(Mapping[str, int]):
    """A KeyError from __getitem__ is reported as a duplicate keyword: CPython's quirk."""

    def keys(self) -> list[str]:  # type: ignore[override]
        return ["a"]

    def __getitem__(self, key: str) -> int:
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(["a"])

    def __len__(self) -> int:
        return 1


class Manager:
    def __enter__(self) -> str:
        return "entered"

    def __exit__(self, *exc: object) -> None:
        print("exit")


HOST: dict[str, Any] = {"Logged": Logged, "QuietDict": QuietDict, "GetitemKeyError": GetitemKeyError,
                        "Manager": Manager, "host_trace": trace}

ERRORS = '''
def error(call):
    try:
        call()
    except TypeError as exc:
        return str(exc)
    return "no error"
'''

BINDING = ERRORS + '''
def shape(a, /, b=2, *rest, c, d=4, **extra):
    return (a, b, rest, c, d, sorted(extra.items()))
print(shape(1, c=3))
print(shape(1, 5, 6, 7, c=3, d=8, e=9))
print(shape(1, *[5, 6], c=3, **{"z": 1, "y": 2}))
print(shape(*(1,), **{"c": 3, "b": 7}))
print(shape(1, *range(3), *"ab", c=0))
def kw_like_posonly(a, /, **kw):
    return a, kw
print(kw_like_posonly(1, a=2))
def two(a, b): pass
def kwo(a, *, b, c): pass
def posonly(a, b=1, /): pass
def m3(a, b, /, c): pass
def defaults(a, b=1, c=2): pass
def alpha(alpha, beta): pass
def three(a, b, c): pass
print(error(lambda: two(1)))
print(error(lambda: two(1, 2, 3)))
print(error(lambda: two(1, a=1)))
print(error(lambda: two(1, 2, c=3)))
print(error(lambda: kwo(1, 2, 3, b=1)))
print(error(lambda: kwo(1)))
print(error(lambda: kwo()))
print(error(lambda: posonly(a=1)))
print(error(lambda: posonly(1, 2, 3)))
print(error(lambda: m3(a=1, b=2, c=3)))
print(error(lambda: defaults()))
print(error(lambda: defaults(1, 2, 3, 4)))
print(error(lambda: alpha(1, alpah=2)))
print(error(lambda: three()))
print(error(lambda: three(**{"a": 1})))
print(error(lambda: two(**{1: 2})))
'''

UNPACKING = ERRORS + '''
trace = []
def v(name, value):
    trace.append(name)
    return value
def collect(*args, **kwargs):
    return args, list(kwargs)
print(collect(v("p1", 1), *v("s1", [2]), v("p2", 3), k=v("k1", 4), **v("m1", {"j": 5})), trace)
trace.clear()
print(collect(x=v("kw x", 1), *v("star", [1]), **v("dstar", {"z": 1})), trace)
trace.clear()
print(collect(**Logged(["ab", "c"])), host_trace)
host_trace.clear()
print(collect(**QuietDict(q=1)), host_trace)
print(error(lambda: collect(*v("not iterable", 1))))
print(error(lambda: collect(**v("not a mapping", 1))))
print(error(lambda: collect(**{"a": 1}, a=2)))
print(error(lambda: collect(**{"a": 1}, **{"a": 2})))
print(error(lambda: collect(**Logged(["a"]), **{"a": 1})), host_trace)
host_trace.clear()
try:
    collect(**GetitemKeyError())
except KeyError as exc:
    print("KeyError propagates", exc.args)
class_without_keys = 1
print(error(lambda: print(**{"sep": 1}, sep=2)))
'''

FUNCTIONS = '''
trace = []
def note(name):
    trace.append("evaluate " + name)
    def apply(fn):
        trace.append("apply " + name + " to " + fn.__name__)
        return fn
    return apply
def default(value):
    trace.append("default")
    return value
@note("outer")
@note("inner")
def decorated(x=default(1), *, k=default(2)):
    """First line.
        Indented more.
    Back at the margin.

\tA tab."""
    return x
print(trace)
print(decorated.__name__, decorated.__qualname__, decorated.__module__, repr(decorated.__doc__))
print(decorated.__defaults__, decorated.__kwdefaults__, decorated(), decorated(5))
decorated.__defaults__ = (10,)
print(decorated())
def outer():
    def middle(n):
        return lambda: n * 2
    return middle
inner = outer()(21)
print(inner(), inner.__name__, inner.__qualname__, inner.__doc__, inner.__defaults__)
square = lambda n, power=2: n ** power
print(square(3), square(2, power=3), square.__qualname__, (lambda *a, **k: (a, k))(1, b=2))
counter = lambda: (count := 5) + count
print(counter())
def no_doc():
    f"not a docstring {1}"
print(no_doc.__doc__, no_doc.__annotate__, no_doc.__annotations__, no_doc.__type_params__)
def method_like(self):
    return self
print(method_like.__get__(7)(), type(method_like).__name__)
class_free = staticmethod(method_like)
print(class_free.__func__ is method_like)
'''

ANNOTATIONS = '''
def annotated(p: int, /, a: Later, *args: str, k: format, **kw: bytes) -> list[int]:
    pass
class_like = 1
Later = "later, bound after the def"
ann = annotated.__annotations__
print(list(ann), ann["a"], ann["k"] is format, ann["return"], ann is annotated.__annotations__)
annotate = annotated.__annotate__
print(annotate(1) == ann, annotate(2) == ann, annotate.__qualname__, annotate.__name__, annotate.__defaults__)
try:
    annotate(3)
except NotImplementedError as exc:
    print("NotImplementedError", exc.args)
try:
    annotate(format=1)
except TypeError as exc:
    print("TypeError", exc)
def forward(x: "Missing") -> None:
    pass
def unbound(x: Missing):
    pass
print(forward.__annotations__)
try:
    unbound.__annotations__
except NameError as exc:
    print("NameError", exc.name)
def closure():
    T = int
    def f(x: T): pass
    return f
print(closure().__annotations__, closure().__annotate__.__qualname__)
'''

FUTURE_ANNOTATIONS = '''
from __future__ import annotations
def f(a: int, b: list[int] = []) -> 1 + 2:
    pass
print(f.__annotations__)
'''

HYGIENE = '''
def shadowing(type, iter, format, str, repr):
    with Manager() as m:
        pass
    squares = [n * n for n in range(3)]
    return [m, squares, f"{type!r:>8}|{iter!s}|{format}"]
print(shadowing("t", "i", "f", 1, 2))
slice = None
print([1, 2, 3][1:], [1, 2, 3][::-1])
'''


def check(src: str) -> None:
    got, ref = both(src, HOST)
    trace.clear()
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_argument_binding_and_its_errors_match_cpython() -> None:
    check(BINDING)


def test_call_unpacking_matches_list_extend_and_dict_merge() -> None:
    check(UNPACKING)


def test_function_objects_decorators_and_lambdas() -> None:
    check(FUNCTIONS)


def test_pep649_annotations_are_lazy_and_in_cpython_order() -> None:
    check(ANNOTATIONS)


def test_desugarings_call_builtins_whatever_the_program_binds() -> None:
    check(HYGIENE)


def test_docstrings_are_cleaned_as_cpython_cleans_them() -> None:
    samples = ["", "x", "  lead", "a\n  b\n c", "a\n\n   b\n  \n   c", "\tt\n\tu", "a\n    b\n      c\n",
               "  first\n       second\n     third\n\n\ttab", "only\n   ", "x\n\t\n  y"]
    for doc in samples:
        src = f"def f():\n    {doc!r}\n"
        ns: dict[str, Any] = {}
        exec(compile(src, "<doc>", "exec", dont_inherit=True), ns)  # noqa: S102  # the oracle
        assert clean_doc(doc) == ns["f"].__doc__, (doc, clean_doc(doc), ns["f"].__doc__)


def test_future_annotations_need_imports_first() -> None:
    try:
        lower(FUTURE_ANNOTATIONS, "<test>")
    except Unsupported as exc:
        assert "ImportFrom" in str(exc)      # step A4; the PEP 563 strings are lowered already
    else:
        raise AssertionError("from __future__ import lowered before imports exist")


def test_type_parameters_are_refused_not_dropped() -> None:
    try:
        lower("def f[T](x): pass\n", "<test>")
    except Unsupported as exc:
        assert "type parameters" in str(exc)
    else:
        raise AssertionError("PEP 695 type parameters dropped silently")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
