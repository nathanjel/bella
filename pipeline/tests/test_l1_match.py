"""Gate 0 task 4, step A5b: match statements (desugar-match and runtime/prelude/match.py),
eval1 against CPython, effects logged in the order CPython performs them.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_match
"""
from __future__ import annotations

from pipeline.l1.frontend import lower
from pipeline.tests.test_frontend_eval1 import both

EFFECTS = '''
import collections.abc
log = []
class Eq:
    def __init__(self, n): self.n = n
    def __eq__(self, other):
        log.append(f"eq {self.n} {other!r}")
        return self.n == other
class Seq(collections.abc.Sequence):
    def __init__(self, *items): self.items = items
    def __len__(self):
        log.append("len"); return len(self.items)
    def __getitem__(self, i):
        log.append(f"getitem {i}"); return self.items[i]
    def __iter__(self):
        log.append("iter"); return iter(self.items)
class Map(collections.abc.Mapping):
    def __init__(self, **d): self.d = d
    def __len__(self):
        log.append("len"); return len(self.d)
    def __getitem__(self, k):
        log.append(f"getitem {k}"); return self.d[k]
    def __iter__(self):
        log.append("iter"); return iter(self.d)
    def get(self, k, default=None):
        log.append(f"get {k}"); return self.d.get(k, default)
class Point:
    __match_args__ = ("x", "y")
    def __init__(self, x, y): self.x, self.y = x, y
    def __getattribute__(self, name):
        if not name.startswith("__"):
            log.append(f"getattr {name}")
        return object.__getattribute__(self, name)
def show(label, subject):
    log.clear()
    match subject:
        case [1, *rest] if rest:
            result = ("starts with 1", rest)
        case [first, *_, last]:
            result = ("first and last", first, last)
        case {"a": 1, **others}:
            result = ("a is 1", others)
        case {"b": (2 | 3) as b}:
            result = ("b", b)
        case Point(0, y=yy):
            result = ("on the y axis", yy)
        case Point(x, y) if x == y:
            result = ("diagonal", x)
        case int(n) | float(n):
            result = ("number", n)
        case str() as s:
            result = ("string", s)
        case None:
            result = ("none",)
        case _:
            result = ("other",)
    print(label, result, log)
show("list", [1, 2, 3])
show("list no rest", [1])
show("seq", Seq(5, 6, 7))
show("map", Map(a=1, b=2))
show("map b", Map(b=3))
show("point axis", Point(0, 4))
show("point diag", Point(2, 2))
show("point", Point(1, 2))
show("int", 7)
show("float", 1.5)
show("str is no sequence", "abc")
show("none", None)
show("bytes", b"x")
show("tuple", (9, 8))
match Eq(2):
    case 1 | 2 | 3:
        print("matched value", log)
x = "unset"
match 5:
    case x if x > 10:
        print("not reached")
    case _:
        print("guard failed; the capture stays:", x)
match [1, [2, 3]]:
    case [a, [b, c]] | [a, b, c]:
        print("nested", a, b, c)
def err(subject, kind):
    try:
        match subject:
            case Bad(1) if kind == "match_args":
                pass
            case Point(1, 2, 3) if kind == "too many":
                pass
            case Point(1, x=2) if kind == "duplicate":
                pass
    except Exception as exc:
        return type(exc).__name__ + ": " + str(exc)
    return "no error"
class Bad:
    __match_args__ = ["a"]
    a = 1
print(err(Bad(), "match_args"), err(Point(1, 2), "too many"), err(Point(1, 2), "duplicate"), sep="\\n")
'''


def check(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_match_semantics_and_order_of_effects() -> None:
    check(EFFECTS)


def test_compile_time_pattern_errors_are_syntax_errors() -> None:
    for src in ("match x:\n    case y:\n        pass\n    case 1:\n        pass\n",
                "match x:\n    case _:\n        pass\n    case 1:\n        pass\n",
                "match x:\n    case [a, a]:\n        pass\n",
                "match x:\n    case [a] | [b]:\n        pass\n",
                "match x:\n    case {1: a, 1: b}:\n        pass\n",
                "match x:\n    case [*a, *b]:\n        pass\n"):
        try:
            lower(src, "<test>")
        except SyntaxError:
            try:
                compile(src, "<cpython>", "exec", dont_inherit=True)
            except SyntaxError:
                continue
            raise AssertionError(f"CPython accepts {src!r}") from None
        raise AssertionError(f"{src!r} was accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
