# clause: C-3-70
# spec: section 3 (functions: __closure__ and its cells)
# status: P1
# source: Objects/cellobject.c (cell_richcompare, cell_repr; no tp_hash)
"""A closure's cell compares by what it holds, with the whole comparison protocol and its TypeError, and an empty cell comes
before anything else; a type with a comparison of its own and no hash is unhashable; its repr names the cell and what it
holds."""
import types
from collections.abc import Callable


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def cell_of(value: object) -> types.CellType:
    closure = (lambda: value).__closure__
    assert closure is not None
    return closure[0]


first, again, second, word, empty = cell_of(1), cell_of(1), cell_of(2), cell_of("a"), types.CellType()
print("a cell's own:", first == again, first is again, first != second, first < second, second <= first, empty < first, empty == types.CellType(), first > empty, first.__eq__(again), first.__eq__(1),  # type: ignore[operator]
      first.__lt__(second), type(first).__ge__(empty, empty), attempt(lambda: first < word), attempt(lambda: hash(first)), attempt(lambda: {first}), vars(type(first))["__hash__"],  # type: ignore[operator]
      first in [again], sorted([second, empty, first]) == [empty, first, second], repr(empty).startswith("<cell at ") and repr(empty).endswith(": empty>"),  # type: ignore[type-var]
      repr(first).startswith("<cell at ") and ": int object at " in repr(first), type(vars(type(first))["__eq__"]).__name__, type(first.__repr__).__name__)
