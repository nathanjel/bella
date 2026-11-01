# clause: C-3-10
# spec: section 3
# status: P1
# source: review 2026-11-01 astra-low-01 finding 4 and gemini-4-argon-high bug 2.1.2 (user hooks run exactly once per read)
"""A descriptor's __get__ and a class's __getattr__ run exactly once per attribute read, and a
__getattr__ that installs a class attribute is not consulted again: the class attribute wins."""

calls: list[str] = []


class Counting:
    def __get__(self, obj: object, owner: object = None) -> int:
        calls.append("get")
        return len(calls)


class C:
    p = Counting()


class Lazy:
    def __getattr__(self, name: str) -> int:
        calls.append(f"getattr {name}")
        setattr(Lazy, name, 2)   # memoise on the class
        return 1


c = C()
print([c.p for _ in range(3)], calls)
calls.clear()
z = Lazy()
print(z.x, z.x, Lazy().x, calls)
