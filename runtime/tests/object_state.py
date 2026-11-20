"""What runtime/tests/object_state.cpp prints, from the reference model: a built-in type's fields that have no name
(RL-507; refmodel RefClass(hidden=..., members=..., readonly=...), Runtime.state_get, state_set, state_del). `make object-test` compares the two."""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from refmodel import objects as O  # noqa: E402
from refmodel.objects import RefClass, RefObject, Runtime, decref, incref  # noqa: E402


def shown(v: object) -> str:
    return f"t{v.tag}" if isinstance(v, RefObject) else str(v)


def attempt(what: str, f: Callable[[], object]) -> None:
    try:
        v = f()
    except AttributeError:
        print(f"  {what}: AttributeError")
    else:
        print(f"  {what}: {'done' if v is None else shown(v)}")


def main() -> None:
    heap = O.HEAP = O.Heap()
    rt = Runtime()
    T = RefClass("T", heap=heap)

    def tagged(n: int) -> RefObject:
        return RefObject(T, tag=n)

    print("1. a field has no name")
    E = RefClass("enumerate", slots=("_count", "_it"), hidden=("_count", "_it"), heap=heap)
    P = RefClass("Page", (E,), heap=heap)
    plain, p = RefObject(E), RefObject(P)
    incref(plain)
    incref(p)
    rt.state_set(plain, "_count", 0)
    rt.state_set(p, "_count", 1)
    print("  the class has it:", E.lookup("_count") is not None)
    attempt("getattr of a plain one", lambda: rt.getattr(plain, "_count"))
    attempt("setattr of a plain one", lambda: rt.setattr(plain, "_count", 5))
    attempt("delattr of a plain one", lambda: rt.delattr(plain, "_count"))
    attempt("its field", lambda: rt.state_get(plain, "_count"))
    attempt("a field never stored", lambda: rt.state_get(plain, "_it"))
    attempt("deleting a field never stored", lambda: rt.state_del(plain, "_it"))

    print("2. the attribute of a class that derives")
    attempt("getattr before any store", lambda: rt.getattr(p, "_count"))
    attempt("setattr", lambda: rt.setattr(p, "_count", 2))
    attempt("getattr", lambda: rt.getattr(p, "_count"))
    attempt("its field", lambda: rt.state_get(p, "_count"))
    attempt("delattr", lambda: rt.delattr(p, "_count"))
    attempt("delattr again", lambda: rt.delattr(p, "_count"))
    attempt("its field", lambda: rt.state_get(p, "_count"))

    print("3. a slot and a kept attribute under the name")
    R = RefClass("ref", slots=("_hash",), hidden=("_hash",), heap=heap)
    for cls in (RefClass("IdRef", (R,), slots=("_hash",), heap=heap), RefClass("Kept", (R,), promoted=("_hash",), heap=heap)):
        o = RefObject(cls)
        incref(o)
        rt.state_set(o, "_hash", 7)
        rt.setattr(o, "_hash", 1000)
        attempt(f"{cls.name}: getattr", lambda o=o: rt.getattr(o, "_hash"))        # type: ignore[misc]
        attempt(f"{cls.name}: its field", lambda o=o: rt.state_get(o, "_hash"))    # type: ignore[misc]
        rt.delattr(o, "_hash")
        attempt(f"{cls.name}: getattr after delattr", lambda o=o: rt.getattr(o, "_hash"))      # type: ignore[misc]
        attempt(f"{cls.name}: its field after delattr", lambda o=o: rt.state_get(o, "_hash"))  # type: ignore[misc]
        attempt(f"{cls.name}: the field deleted", lambda o=o: rt.state_del(o, "_hash"))        # type: ignore[misc]
        attempt(f"{cls.name}: its field then", lambda o=o: rt.state_get(o, "_hash"))           # type: ignore[misc]
        attempt(f"{cls.name}: deleted again", lambda o=o: rt.state_del(o, "_hash"))            # type: ignore[misc]
        decref(o)

    print("4. released in the order the built-in type declares them; a store keeps the new value first")
    M = RefClass("M", slots=("b", "_a", "c"), hidden=("_a", "c"), heap=heap)
    N = RefClass("N", (M,), slots=("a", "d"), hidden=("d",), heap=heap)
    m = RefObject(N)
    incref(m)
    rt.state_set(m, "c", tagged(1))
    rt.setattr(m, "b", tagged(2))
    rt.state_set(m, "_a", tagged(3))
    rt.state_set(m, "d", tagged(4))
    rt.setattr(m, "a", tagged(5))
    rt.state_set(m, "c", tagged(6))
    print("  after the second store:", [f"t{t}" for t in heap.deaths])
    decref(m)
    print("  after the object:", [f"t{t}" for t in heap.deaths])

    print("5. hidden once the class and a class that derives from it exist")
    del heap.deaths[:]
    Q = RefClass("Q", slots=("u", "v", "w"), hidden=("u", "w"), heap=heap)
    QS = RefClass("QS", (Q,), heap=heap)
    q = RefObject(QS)
    incref(q)
    rt.state_set(q, "u", tagged(7))
    rt.setattr(q, "v", tagged(8))
    rt.state_set(q, "w", tagged(9))
    print("  the class has them:", Q.lookup("u") is not None, Q.lookup("v") is not None, Q.lookup("w") is not None)
    attempt("getattr", lambda: rt.getattr(q, "u"))
    attempt("its field", lambda: rt.state_get(q, "u"))
    attempt("setattr", lambda: rt.setattr(q, "u", 11))
    attempt("getattr", lambda: rt.getattr(q, "u"))
    attempt("its field", lambda: rt.state_get(q, "u"))
    attempt("the slot that stays", lambda: rt.getattr(q, "v"))
    QT = RefClass("QT", (Q,), slots=("u",), heap=heap)
    t = RefObject(QT)
    incref(t)
    rt.setattr(t, "u", 4)
    rt.state_set(t, "u", 5)
    attempt("a later class's slot of the name", lambda: rt.getattr(t, "u"))
    attempt("its field", lambda: rt.state_get(t, "u"))
    decref(t)
    decref(q)
    print("  after the object:", [f"t{t}" for t in heap.deaths])
    print("6. a member the type shows: the type's own cell, under any name, and read-only where the type says")
    Pt = RefClass("partial", slots=("func", "args", "_p"), hidden=("func", "args", "_p"), members=("func", "args"), readonly=("args",), heap=heap)
    Sh = RefClass("Shadowed", (Pt,), attrs={"func": 99, "saved": Pt.attrs["args"]}, heap=heap)
    o = RefObject(Sh)
    incref(o)
    rt.state_set(o, "func", 1)
    rt.state_set(o, "args", 2)
    print("  the class has them:", Pt.lookup("func") is not None, Pt.lookup("args") is not None, Pt.lookup("_p") is not None)
    attempt("the name a deriving class has", lambda: rt.getattr(o, "func"))
    attempt("the field", lambda: rt.state_get(o, "func"))
    attempt("the member under another name", lambda: rt.getattr(o, "saved"))
    attempt("a read-only member", lambda: rt.getattr(o, "args"))
    attempt("a store through it", lambda: rt.setattr(o, "args", 5))
    attempt("a delete through it", lambda: rt.delattr(o, "args"))
    attempt("the type's own store", lambda: rt.state_set(o, "args", 7))
    attempt("read again", lambda: rt.getattr(o, "args"))
    q2 = RefObject(Pt)
    incref(q2)
    rt.state_set(q2, "func", 3)
    attempt("a store through a member that takes one", lambda: rt.setattr(q2, "func", 4))
    attempt("its field", lambda: rt.state_get(q2, "func"))
    attempt("a delete through it", lambda: rt.delattr(q2, "func"))
    attempt("its field then", lambda: rt.state_get(q2, "func"))
    decref(q2)
    decref(o)
    decref(plain)
    decref(p)


main()
