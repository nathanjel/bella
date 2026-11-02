"""User code that empties the class it runs from: the order CPython 3.15.2 prints is the order
runtime/tests/object_reentrancy.cpp must print with object.hpp (review 2026-11-02, A8-1)."""


class Desc:
    def __init__(self, n: str, fail: bool) -> None:
        self.n, self.fail = n, fail

    def __get__(self, obj: object, cls: type) -> str:
        print("  get: deletes", self.n, "from the class")
        delattr(cls, "x")
        print("  get: returns")
        if self.fail:
            raise AttributeError("x")
        return "value"

    def __del__(self) -> None:
        print("  dies", self.n)


class Hook:
    def __call__(self, name: str) -> str:
        print("  hook called; deletes itself from the class")
        del C2.__getattr__
        print("  hook returns")
        return "from hook"

    def __del__(self) -> None:
        print("  dies hook")


class C1:
    x = Desc("desc1", fail=False)


print("1. descriptor deletes itself:")
v = C1().x
print("  caller got", v)


class C2:
    x = Desc("desc2", fail=True)
    __getattr__ = Hook()


print("2. descriptor deletes itself and fails; the hook deletes itself:")
v = C2().x
print("  caller got", v)


class Hook3:
    def __call__(self, name: str) -> str:
        print("  hook called")
        return "from hook"

    def __del__(self) -> None:
        print("  dies hook3")


class Desc3:
    def __get__(self, obj: object, cls: type) -> str:
        print("  get: deletes the hook from the class")
        del C3.__getattr__
        print("  get: fails")
        raise AttributeError("x")


class C3:
    x = Desc3()
    __getattr__ = Hook3()


print("3. the descriptor deletes the hook, then fails:")
v = C3().x
print("  caller got", v)
