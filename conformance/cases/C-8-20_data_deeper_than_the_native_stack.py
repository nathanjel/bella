# clause: C-8-20
# spec: section 8 (Resources)
# status: P1
# source: Objects/object.c (_Py_Dealloc, _PyTrash_thread_deposit_object, _PyTrash_thread_destroy_chain, PyObject_Repr,
#         PyObject_Str, PyObject_RichCompare), Python/ceval.c (_Py_CheckRecursiveCall, _Py_InitializeRecursionLimits),
#         Include/internal/pycore_pystate.h (_Py_RecursionLimit_GetMargin), Objects/tupleobject.c (tuple_hash)
"""Data nested far deeper than the native stack holds. A chain of objects, each holding the next, is let go whatever
its length: every object dies once, and a weak reference to the first is dead. What walks such data inside one call
(the hash of a tuple of tuples, the repr and the str of nested containers, a comparison) raises RecursionError, and the
program goes on with the data as it was. The program starts itself again under a stack of 1 MiB, where 200 000 levels
are more than the stack holds on any machine; the order in which so deep a chain dies is the machine's and is not
looked at."""
import os
import sys
import weakref
from collections.abc import Callable

SHOW = "BELLA_CASE_SHOW"
DEPTH = 200_000
gone = [0]


class Node:
    """A link that counts its own end."""

    def __init__(self, after: object) -> None:
        self.after = after

    def __del__(self) -> None:
        gone[0] += 1


class Slotted:
    __slots__ = ("after", "__weakref__")

    def __init__(self, after: object) -> None:
        self.after = after


def tuples(depth: int) -> tuple[object, ...]:
    data: tuple[object, ...] = ()
    for _ in range(depth):
        data = (data,)
    return data


def lists(depth: int) -> list[object]:
    data: list[object] = []
    for _ in range(depth):
        data = [data]
    return data


def dicts(depth: int) -> dict[str, object]:
    data: dict[str, object] = {}
    for _ in range(depth):
        data = {"after": data}
    return data


def outcome(act: Callable[[], object]) -> str:
    try:
        act()
    except RecursionError:
        return "RecursionError"
    return "done"


def let_go() -> None:
    """Chains of every kind, dropped at once."""
    head: object = None
    for _ in range(DEPTH):
        head = Node(head)
    gone[0] = 0
    del head
    print("a chain of objects with a finaliser: every one died once:", gone[0] == DEPTH)
    slotted: object = None
    for _ in range(DEPTH):
        slotted = Slotted(slotted)
    seen: list[str] = []
    watch = weakref.ref(slotted, lambda ref: seen.append("the callback"))
    del slotted
    print("a chain of objects with slots:", watch() is None, seen)
    for label, make in (("tuples", tuples), ("lists", lists), ("dicts", dicts)):
        data = make(DEPTH)
        del data
        print("a chain of", label, "is let go")
    mixed: object = None
    for i in range(DEPTH):
        mixed = (mixed,) if i % 3 == 0 else [mixed] if i % 3 == 1 else {"after": mixed}
    del mixed
    print("a chain of all three is let go")


def walked() -> None:
    """What one call walks to the bottom."""
    deep = tuples(DEPTH)
    nested = lists(DEPTH)
    keyed = dicts(DEPTH)
    known: set[object] = {1, 2}
    print("hash of a tuple:", outcome(lambda: hash(deep)), "| again:", outcome(lambda: hash(deep)), "| as a key:", outcome(lambda: {deep: 1}),
          "| in a set:", outcome(lambda: deep in known))
    print("repr:", outcome(lambda: repr(nested)), outcome(lambda: repr(deep)), outcome(lambda: repr(keyed)),
          "| str:", outcome(lambda: str(nested)), "| a format:", outcome(lambda: f"{deep}"))
    other, another, more = tuples(DEPTH), lists(DEPTH), dicts(DEPTH)
    print("==:", outcome(lambda: deep == other), outcome(lambda: nested == another), outcome(lambda: keyed == more),
          "| <:", outcome(lambda: deep < other), "| in:", outcome(lambda: deep in [other]), "| index:", outcome(lambda: [other].index(deep)))
    print("the same object is equal to itself with no walk:", deep == deep, nested == nested, deep in [deep])
    print("and the data is as it was:", len(deep), len(nested), list(keyed), type(deep[0]).__name__)


def again() -> None:
    """Start this program again under a stack of 1 MiB, both outputs in one pipe; print its status and what it wrote."""
    here, there = os.pipe()
    command = 'ulimit -s 1024 && exec "$0" "$@"'
    child = os.posix_spawn("/bin/sh", ["sh", "-c", command, sys.executable, *sys.orig_argv[1:]], {"PYTHONHASHSEED": "0", SHOW: "yes"},
                           file_actions=[(os.POSIX_SPAWN_OPEN, 0, "/dev/null", os.O_RDONLY, 0), (os.POSIX_SPAWN_DUP2, there, 1),
                                         (os.POSIX_SPAWN_DUP2, there, 2), (os.POSIX_SPAWN_CLOSE, here)])
    os.close(there)
    wrote = b""
    while chunk := os.read(here, 65536):
        wrote += chunk
    os.close(here)
    status = os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    print("under a stack of 1 MiB -> status", status)
    for line in wrote.decode().splitlines():
        print("   ", line)


if SHOW in os.environ:
    let_go()
    walked()                                     # what it made is let go when it returns
    print("all of it is let go, and the program goes on:", sum(range(10)))
else:
    print("---- under the stack the program was given")
    let_go()
    print("---- and under a small one")
    again()
