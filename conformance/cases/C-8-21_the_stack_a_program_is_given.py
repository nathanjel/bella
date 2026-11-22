# clause: C-8-21
# spec: section 8 (Resources)
# status: P1
# source: Python/ceval.c (_Py_CheckRecursiveCall: the frames of Python calls are on the heap, a raised limit is reached),
#         Objects/object.c (PyObject_Repr), Modules/_json.c (encoder_listencode_obj), decision 16 as changed on 2026-11-22
"""How deep a program goes on the stack it is given. A recursion reaches the limit the program set, also one raised to
50 000; data nested 5 000 deep is written by `json`, shown by `repr` and `str`, compared and hashed. The program runs on
its process's first thread. (None of these depths is near what either side can hold; where each side stops is the
machine's and is not looked at.)"""
import json
import os
import sys
import threading
from collections.abc import Callable


def depth(n: int) -> int:
    try:
        return depth(n + 1)
    except RecursionError:
        return n


def lists(levels: int) -> list[object]:
    data: list[object] = []
    for _ in range(levels):
        data = [data]
    return data


def tuples(levels: int) -> tuple[object, ...]:
    data: tuple[object, ...] = ()
    for _ in range(levels):
        data = (data,)
    return data


def dicts(levels: int) -> dict[str, object]:
    data: dict[str, object] = {}
    for _ in range(levels):
        data = {"k": data}
    return data


def outcome(walk: Callable[[], object]) -> str:
    try:
        return str(walk())
    except RecursionError:
        return "RecursionError"


LEVELS = 5_000

print("the limit a program starts with:", sys.getrecursionlimit(), "| reached:", depth(0))
sys.setrecursionlimit(50_000)
print("raised to 50 000 | reached:", depth(0))
sys.setrecursionlimit(1000)
print("and back at 1000 | reached:", depth(0))

nested, deep, keyed = lists(LEVELS), tuples(LEVELS), dicts(LEVELS)
print("json.dumps:", outcome(lambda: len(json.dumps(nested))), outcome(lambda: len(json.dumps(keyed))))
print("repr:", outcome(lambda: len(repr(nested))), outcome(lambda: len(repr(deep))), outcome(lambda: len(repr(keyed))),
      "| str:", outcome(lambda: len(str(nested))))
other, another, more = lists(LEVELS), tuples(LEVELS), dicts(LEVELS)
print("==:", outcome(lambda: nested == other), outcome(lambda: deep == another), outcome(lambda: keyed == more),
      "| hash:", outcome(lambda: hash(deep) == hash(another)))
print("on the process's first thread:", threading.get_native_id() == os.getpid(), threading.current_thread() is threading.main_thread())
