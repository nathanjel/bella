# clause: C-3-09
# spec: section 3
# status: P1
# source: review 2026-11-01 gemini-4-argon-high, bug 2.1.3 (AttributeError from the generic lookup falls through to __getattr__)
"""__getattr__ runs whenever the generic lookup raises AttributeError -- an unset slot, a
descriptor whose __get__ raises it, a property that raises it -- not only when the name is absent."""


class Slotted:
    __slots__ = ("s",)

    def __getattr__(self, name: str) -> str:
        return f"fallback:{name}"


class Raising:
    def __get__(self, obj: object, owner: object = None) -> int:
        raise AttributeError("from __get__")


class WithDescriptor:
    p = Raising()

    @property
    def q(self) -> int:
        raise AttributeError("from property")

    def __getattr__(self, name: str) -> str:
        return f"fallback:{name}"


class NoHook:
    __slots__ = ("s",)


print(Slotted().s)
w = WithDescriptor()
print(w.p, w.q, w.missing)
try:
    print(NoHook().s)  # type: ignore[attr-defined]  # an unset slot, read on purpose
except AttributeError as exc:
    print("no hook:", type(exc).__name__, exc.name)
