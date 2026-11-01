# clause: C-3-20
# spec: section 3
# status: P1
# source: review log D-11 (2026-11-01): the reduction protocol as copy uses it is [P1]; pickle stays [P2+]
"""copy.copy and copy.deepcopy on user classes go through __reduce_ex__(4): instance dicts and
slots are copied, __getstate__, __setstate__ and __getnewargs_ex__ are honoured, __reduce__ and
__copy__/__deepcopy__ overrides win, and deepcopy keeps shared references and cycles."""
import copy

log: list[str] = []


class Plain:
    def __init__(self, items: list[int]) -> None:
        self.items = items
        self.label = "plain"


class Slotted:
    __slots__ = ("a", "b")

    def __init__(self) -> None:
        self.a = [1]                        # b stays unset


class Stateful:
    def __init__(self) -> None:
        self.secret = "s"
        self.data = [1, 2]

    def __getstate__(self) -> dict[str, object]:
        log.append("getstate")
        return {"data": self.data}

    def __setstate__(self, state: dict[str, object]) -> None:
        log.append("setstate")
        self.__dict__.update(state)
        self.restored = True


class WithNewArgs:
    n: int

    def __new__(cls, n: int) -> "WithNewArgs":  # noqa: UP037  # clearer next to __new__
        log.append(f"new {n}")
        obj = super().__new__(cls)
        obj.n = n
        return obj

    def __getnewargs_ex__(self) -> tuple[tuple[int], dict[str, object]]:
        return (self.n,), {}


class Reduced:
    def __init__(self, x: int) -> None:
        self.x = x

    def __reduce__(self) -> tuple[type, tuple[int]]:
        log.append("reduce")
        return Reduced, (self.x * 10,)


class Custom:
    def __copy__(self) -> "Custom":  # noqa: UP037
        log.append("__copy__")
        return Custom()

    def __deepcopy__(self, memo: dict[int, object]) -> "Custom":  # noqa: UP037
        log.append("__deepcopy__")
        return self


class Tagged(int):
    pass


p = Plain([1, 2])
shallow, deep = copy.copy(p), copy.deepcopy(p)
print("plain:", shallow.items is p.items, deep.items is p.items, deep.items == p.items, vars(deep), type(deep).__name__)
s = Slotted()
s2 = copy.deepcopy(s)
print("slots:", s2.a == s.a, s2.a is s.a, hasattr(s2, "b"))
st = copy.copy(Stateful())
print("state:", log, vars(st))
log.clear()
w = copy.deepcopy(WithNewArgs(3))
print("newargs:", log, w.n)
log.clear()
r = copy.copy(Reduced(4))
print("reduce:", log, r.x)
log.clear()
c = Custom()
print("custom:", copy.copy(c) is c, copy.deepcopy(c) is c, log)
t = Tagged(5)
t.note = "n"  # type: ignore[attr-defined]  # an int subclass instance has a __dict__
t2 = copy.deepcopy(t)
print("int subclass:", t2 == 5, type(t2).__name__, vars(t2))
shared = [0]
holder = Plain(shared)
holder.again = shared  # type: ignore[attr-defined]  # the same list under two names
holder.me = holder  # type: ignore[attr-defined]  # a cycle
d = copy.deepcopy(holder)
print("sharing and cycles:", d.items is d.again, d.items is not shared, d.me is d)  # type: ignore[attr-defined]
