"""How many calls fit under a recursion limit, when a level goes through something that is no Python frame (RL-632, RL-633).

`sys.setrecursionlimit` bounds Python frames. A function written in C is none, and since PEP 709 a list, set or dict
comprehension is none either: it runs in the frame around it. A compiled program has frames CPython does not have, the
helper of a comprehension and the functions of the preludes that stand for C functions (`map`, `sorted`, `property`,
`functools.reduce`, the walk of a `repr`), and it counted them, so a recursion through any of them reached half the
depth CPython reaches. Review A29 found it for four shapes; the counter counts the frames CPython has now
(`FrameGuard`: a frame that is not shown takes the look at the native stack and no count).

The sweep recurses through 53 shapes, one call of the program's own function a level, under limits of 60 and 150, twice
each, and prints the count at the RecursionError: a process for each row, compiled against CPython. One row is not
compared: a class called with a Python `__init__`. CPython's specialised instruction for that call pushes a second
frame, so it counts two entries a level, and one more on the calls made before the instruction specialises (29, then
28); a compiled program counts one (RL-639, open).

Run under pytest or directly: python3 -m pipeline.tests.test_recursion_counts
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

SWEEP = r'''
"""How many calls of a program's own function fit under a recursion limit, when each level goes through something that
is no Python frame in CPython: a function written in C, a descriptor, a comprehension. One row a process (argv[1])."""
import collections
import functools
import itertools
import json
import operator
import sys

n = 0


def count() -> None:
    global n
    n += 1


# ---- each `go` calls itself once a level, through the thing its row is named for

def go_plain() -> object:
    count()
    return go_plain()


def go_listcomp() -> object:
    count()
    return [go_listcomp() for _ in (0,)]


def go_setcomp() -> object:
    count()
    return {repr(go_setcomp()) for _ in (0,)}


def go_dictcomp() -> object:
    count()
    return {0: go_dictcomp() for _ in (0,)}


def go_nested_comp() -> object:
    count()
    return [[go_nested_comp() for _ in (0,)] for _ in (0,)]


def go_genexp() -> object:
    count()
    return list(go_genexp() for _ in (0,))


def go_lambda() -> object:
    count()
    return (lambda: go_lambda())()


def go_map() -> object:
    count()
    return list(map(lambda _: go_map(), (0,)))


def go_filter() -> object:
    count()
    return list(filter(lambda _: go_filter(), (0,)))


def go_reduce() -> object:
    count()
    return functools.reduce(lambda a, b: go_reduce(), (0, 1))


def go_sorted() -> object:
    count()
    return sorted((0, 1), key=lambda _: go_sorted())


def go_min() -> object:
    count()
    return min((0, 1), key=lambda _: go_min())


def go_list_sort() -> object:
    count()
    items = [0, 1]
    items.sort(key=lambda _: go_list_sort())
    return items


def go_partial() -> object:
    count()
    return functools.partial(go_partial)()


def go_lru() -> object:
    count()
    return functools.lru_cache(None)(lambda: go_lru())()


def go_cmp_key() -> object:
    count()
    return sorted((0, 1), key=functools.cmp_to_key(lambda a, b: go_cmp_key()))  # type: ignore[arg-type, return-value]


def go_accumulate() -> object:
    count()
    return list(itertools.accumulate((0, 1), lambda a, b: go_accumulate()))  # type: ignore[arg-type, return-value]


def go_starmap() -> object:
    count()
    return list(itertools.starmap(lambda: go_starmap(), ((),)))


def go_takewhile() -> object:
    count()
    return list(itertools.takewhile(lambda _: go_takewhile(), (0,)))


def go_groupby() -> object:
    count()
    return [key for key, _ in itertools.groupby((0,), key=lambda _: go_groupby())]


def go_iter_sentinel() -> object:
    count()
    return next(iter(lambda: go_iter_sentinel(), object()))


def go_any() -> object:
    count()
    return any(go_any() for _ in (0,))


def go_join() -> object:
    count()
    return "".join(str(go_join()) for _ in (0,))


def go_defaultdict() -> object:
    count()
    return collections.defaultdict(lambda: go_defaultdict())[0]


def go_methodcaller() -> object:
    count()
    return operator.methodcaller("again")(Caller())


def go_call_operator() -> object:
    count()
    return operator.call(go_call_operator)


def go_json_default() -> object:
    count()
    return json.dumps(object(), default=lambda _: go_json_default())


class Caller:
    def again(self) -> object:
        return go_methodcaller()


class Shapes:
    @property
    def prop(self) -> object:
        count()
        return self.prop

    @staticmethod
    def static() -> object:
        count()
        return Shapes.static()

    @classmethod
    def by_class(cls) -> object:
        count()
        return cls.by_class()

    def __getattr__(self, name: str) -> object:
        count()
        return getattr(self, name + "x")

    def __getitem__(self, key: int) -> object:
        count()
        return self[key + 1]

    def __call__(self) -> object:
        count()
        return self()

    def __len__(self) -> int:
        count()
        return len(self)

    def __bool__(self) -> bool:
        count()
        return bool(self)

    def __str__(self) -> str:
        count()
        return str(self)

    def __repr__(self) -> str:
        count()
        return repr(self)

    def __format__(self, spec: str) -> str:
        count()
        return format(self, spec)

    def __hash__(self) -> int:
        count()
        return hash(self)

    def __eq__(self, other: object) -> bool:
        count()
        return self == other

    def __lt__(self, other: object) -> bool:
        count()
        return self < other

    def __contains__(self, item: object) -> bool:
        count()
        return item in self

    def __iter__(self) -> object:
        count()
        return iter(self)

    def __index__(self) -> int:
        count()
        return operator.index(self)

    def __enter__(self) -> object:
        count()
        with self as inner:
            return inner

    def __exit__(self, *exc: object) -> None:
        return None

    def __add__(self, other: object) -> object:
        count()
        return self + other

    def __neg__(self) -> object:
        count()
        return -self


class Described:
    def __get__(self, obj: object, owner: object = None) -> object:
        count()
        return Holder().attr


class Holder:
    attr = Described()


class Made:
    def __init__(self) -> None:
        count()
        Made()


class Newer:
    def __new__(cls) -> "Newer":
        count()
        return Newer()


class Sub:
    def __init_subclass__(cls) -> None:
        count()
        type("Deeper", (Sub,), {})


def go_yield_from() -> object:
    count()
    yield from go_yield_from()  # type: ignore[misc]


def go_fstring() -> object:
    count()
    return f"{Shapes()}"


ROWS = {
    "plain": go_plain, "list comprehension": go_listcomp, "set comprehension": go_setcomp, "dict comprehension": go_dictcomp,
    "nested comprehension": go_nested_comp, "generator expression": go_genexp, "lambda": go_lambda, "map": go_map, "filter": go_filter,
    "reduce": go_reduce, "sorted key": go_sorted, "min key": go_min, "list.sort key": go_list_sort, "partial": go_partial,
    "lru_cache": go_lru, "cmp_to_key": go_cmp_key, "accumulate": go_accumulate, "starmap": go_starmap, "takewhile": go_takewhile,
    "groupby": go_groupby, "iter with a sentinel": go_iter_sentinel, "any": go_any, "join": go_join, "defaultdict": go_defaultdict,
    "methodcaller": go_methodcaller, "operator.call": go_call_operator, "json default": go_json_default,
    "property": lambda: Shapes().prop, "staticmethod": Shapes.static, "classmethod": Shapes.by_class,
    "__getattr__": lambda: Shapes().missing, "__getitem__": lambda: Shapes()[0], "__call__": lambda: Shapes()(),
    "__len__": lambda: len(Shapes()), "__bool__": lambda: bool(Shapes()), "__str__": lambda: str(Shapes()), "__repr__": lambda: repr(Shapes()),
    "__format__": lambda: format(Shapes(), ""), "f-string": go_fstring, "__hash__": lambda: hash(Shapes()), "__eq__": lambda: Shapes() == 1,
    "__lt__": lambda: Shapes() < 1, "__contains__": lambda: 1 in Shapes(), "__iter__": lambda: iter(Shapes()),
    "__index__": lambda: operator.index(Shapes()), "with": lambda: Shapes().__enter__(), "__add__": lambda: Shapes() + 1,
    "__neg__": lambda: -Shapes(), "a descriptor's __get__": lambda: Holder().attr, "__init__": Made, "__new__": Newer,
    "__init_subclass__": lambda: type("First", (Sub,), {}), "yield from": lambda: list(go_yield_from()),  # type: ignore[call-overload]
}


def run(label: str) -> None:
    global n
    reached = []
    for limit in (60, 150):
        sys.setrecursionlimit(limit)
        for _ in range(2):                       # caught, and again: the count is the same
            n = 0
            try:
                ROWS[label]()
            except RecursionError:
                reached.append(n)
            else:
                reached.append(-1)
    sys.setrecursionlimit(1000)
    print(label, "|", reached)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        for label in ROWS:
            print(label)
'''

NOT_COMPARED = {"__init__"}                      # RL-639: CPython's own count there is its specialiser's


def test_the_recursion_limit_counts_the_frames_cpython_has() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-counts-"))
    try:
        program = folder / "prog.py"
        program.write_text(SWEEP, encoding="utf-8")
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        listed = subprocess.run([sys.executable, str(program)], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert listed.returncode == 0, listed.stderr
        labels = listed.stdout.splitlines()
        assert len(labels) == 53 and NOT_COMPARED <= set(labels), labels
        binary = str(build(program, "prog.py", notes=False))
        wrong: list[str] = []
        for label in labels:                     # a process for each row: one that ends takes no other with it
            sides = [subprocess.run([*command, label], capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
                     for command in ([sys.executable, str(program)], [binary])]
            reference, compiled = sides
            assert reference.returncode == 0 and reference.stdout.startswith(label + " | ["), (label, reference)
            if label not in NOT_COMPARED and (compiled.returncode, compiled.stdout) != (reference.returncode, reference.stdout):
                wrong.append(f"{label}: compiled {compiled.stdout.strip()!r} (status {compiled.returncode}, {compiled.stderr.strip()[-200:]!r}), "
                             f"CPython {reference.stdout.strip()!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_the_recursion_limit_counts_the_frames_cpython_has()
    print("ok")
