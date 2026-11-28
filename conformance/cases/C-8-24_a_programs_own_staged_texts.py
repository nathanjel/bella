# clause: C-8-24
# spec: section 8
# status: P1
# source: the author's decision of 2026-11-28 (Question 57): a program's own eval, exec and compile of a text the dry run staged
"""A program's own texts, staged as the standard library's are: eval of a literal, exec of one into the module's
namespace, compile of one and the code it gives evaluated, and a class decorator that builds the class's __init__ with
exec while the class is defined (as attrs builds its methods). Each runs the code the build compiled from the text."""
from collections.abc import Callable


def make_init(names: tuple[str, ...]) -> object:
    params = ", ".join(names)
    body = "\n".join(f"    self.{name} = {name}" for name in names)
    namespace: dict[str, object] = {}
    exec(f"def __init__(self, {params}):\n{body}\n", namespace)  # noqa: S102
    return namespace["__init__"]


def fields(*names: str) -> Callable[[type], type]:
    def decorate(cls: type) -> type:
        setattr(cls, "__init__", make_init(names))  # noqa: B010
        return cls
    return decorate


@fields("x", "y")
class Point:
    pass


doubled = eval("[n * 2 for n in range(3)]")  # noqa: S307
exec("total = 1 + 2", globals())  # noqa: S102
code = compile("x + y", "<made>", "eval")
point = Point(1, 2)  # type: ignore[call-arg]
print(point.x, point.y, doubled, globals()["total"])  # type: ignore[attr-defined]
print(eval(code, {"x": 3, "y": 4}), code.co_filename, Point.__init__.__code__.co_varnames)  # noqa: S307
