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
    except TypeError:
        print(f"  {what}: TypeError")
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
    print("7. a slot a class declares again: a cell for each declaration (RL-541)")
    heap.deaths.clear()
    D = RefClass("D", slots=("x", "a"), heap=heap)
    F = RefClass("F", (D,), slots=("x",), heap=heap)
    G = RefClass("G", (F,), slots=("x", "m"), attrs={"base_x": D.attrs["x"], "middle_x": F.attrs["x"]}, heap=heap)
    g = RefObject(G)
    incref(g)
    print("  cells behind the name:", len(D.shadowed_fields), len(F.shadowed_fields), len(G.shadowed_fields))
    attempt("the base's before any store", lambda: rt.getattr(g, "base_x"))
    for name, n in (("x", 1), ("base_x", 2), ("middle_x", 3), ("a", 4), ("m", 5)):
        v = tagged(n)
        rt.setattr(g, name, v)
    attempt("the name", lambda: rt.getattr(g, "x"))
    attempt("the base's member", lambda: rt.getattr(g, "base_x"))
    attempt("the middle class's member", lambda: rt.getattr(g, "middle_x"))
    site = O.Site(heap)
    first = "".join(shown(rt.getattr(g, n, site)) for n in ("x", "x", "base_x", "base_x"))
    print(f"  one place, read twice each: {first}, hits {site.hits}")
    kept = G.attrs["x"]
    incref(kept)
    G.del_attr("x")
    attempt("the name once the class's member is gone", lambda: rt.getattr(g, "x", site))
    attempt("again", lambda: rt.getattr(g, "x", site))
    print(f"  hits {site.hits}")
    attempt("a store by the name", lambda: rt.setattr(g, "x", tagged(6)))
    print("  after the store:", [f"t{t}" for t in heap.deaths])
    attempt("the middle class's member", lambda: rt.getattr(g, "middle_x"))
    attempt("a delete by the name", lambda: rt.delattr(g, "x"))
    attempt("deleted again", lambda: rt.delattr(g, "x"))
    attempt("the base's member still", lambda: rt.getattr(g, "base_x"))
    G.set_attr("x", kept)
    attempt("the member put back", lambda: rt.getattr(g, "x"))
    attempt("the middle class's cell is empty", lambda: rt.getattr(g, "middle_x"))
    rt.setattr(g, "middle_x", tagged(7))
    heap.deaths.clear()
    decref(g)
    print("  after the object:", [f"t{t}" for t in heap.deaths])
    # a member of a class that is no base, which a class has under a name: it applies to none of that class's objects
    Else = RefClass("Elsewhere", slots=("x",), heap=heap)
    B = RefClass("Borrowed", (D,), slots=(), attrs={"x": Else.attrs["x"], "own": D.attrs["x"]}, heap=heap)
    b = RefObject(B)
    incref(b)
    attempt("a member of a class that is no base: a read", lambda: rt.getattr(b, "x"))
    attempt("a store", lambda: rt.setattr(b, "x", 1))
    attempt("a delete", lambda: rt.delattr(b, "x"))
    attempt("the base's own member, a store", lambda: rt.setattr(b, "own", 2))
    attempt("and a read", lambda: rt.getattr(b, "own"))
    decref(b)
    # a slot under the name of a field of the built-in base: the base's field is a cell behind it (RL-564)
    BE = RefClass("BaseException", native=("__dict__", "args", "cause"), heap=heap)
    E = RefClass("E", (BE,), slots=("args", "__dict__"), heap=heap)
    K = RefClass("K", (E,), attrs={"base_args": BE.attrs["args"]}, heap=heap)
    print("  cells behind the name:", len(BE.shadowed_fields), len(E.shadowed_fields), len(K.shadowed_fields))
    k = RefObject(K)
    incref(k)
    rt.setattr(k, "base_args", tagged(11))
    attempt("the slot before any store", lambda: rt.getattr(k, "args"))
    rt.setattr(k, "args", tagged(12))
    rt.setattr(k, "cause", tagged(13))
    rt.setattr(k, "other", tagged(14))
    attempt("the slot", lambda: rt.getattr(k, "args"))
    attempt("the base's field", lambda: rt.getattr(k, "base_args"))
    heap.deaths.clear()
    decref(k)
    print("  after the object:", [f"t{t}" for t in heap.deaths])
    print("8. a built-in type's dealloc: where it clears its weak references and its dict (RL-565)")
    for kind, fields, release, own_dict in (("deque", ("items",), ("__weakref__", "items"), False),
                                            ("partial", ("func", "args"), ("__weakref__", "func", "args", "__dict__"), True),
                                            ("BytesIO", (), ("__dict__", "__weakref__"), True),
                                            ("enumerate", ("it",), ("it",), False)):
        base_slots = fields + (("__dict__",) if own_dict else ()) + (("__weakref__",) if "__weakref__" in release else ())
        B = RefClass(kind, slots=base_slots, hidden=fields, release=release, heap=heap)
        for shape in range(3):                       # the type itself, a class with a dict, a class with slots
            if shape == 0:
                K = B
            elif shape == 1:
                K = RefClass("K", (B,), heap=heap)
            else:
                K = RefClass("K", (B,), slots=("b", "a") if B.has_weakref else ("b", "a", "__weakref__"), heap=heap)
            o = RefObject(K)
            incref(o)
            n = 20
            for f in fields:
                rt.state_set(o, f, tagged(n))
                n += 1
            if shape == 1 or (shape == 0 and own_dict):
                rt.setattr(o, "x", tagged(30))
            if shape == 2:
                rt.setattr(o, "a", tagged(31))
                rt.setattr(o, "b", tagged(32))
            heap.deaths.clear()
            if K.has_weakref:
                w = O.weak_ref(o, lambda _: heap.deaths.append("weak"))
                decref(o)
                print(f"  {kind}, shape {shape}:", [t if t == "weak" else f"t{t}" for t in heap.deaths])
                del w
            else:
                decref(o)
                print(f"  {kind}, shape {shape}, no weak reference:", [f"t{t}" for t in heap.deaths])
    print("9. a chain longer than the native stack: what is put off, and when it goes (RL-624)")

    def chain(names: tuple[str, str], length: int) -> tuple[RefObject, list[RefObject]]:
        Node = RefClass("Node", slots=(*names, "__weakref__"), heap=heap)
        nodes: list[RefObject] = []
        head: RefObject | None = None
        for i in reversed(range(length)):            # node i holds node i + 1 and a value of its own, t(200 + i)
            node = RefObject(Node)
            incref(node)
            if head is not None:
                rt.setattr(node, names[0], head)
                decref(head)
            rt.setattr(node, names[1], tagged(200 + i))
            head = node
            nodes.insert(0, node)
        assert head is not None
        return head, nodes

    for names in (("a_nxt", "b_pay"), ("b_nxt", "a_pay")):
        for room in (None, 4, 5, 7):
            head, _ = chain(names, 12)
            heap.deaths.clear()
            heap.stack_room = room
            decref(head)
            heap.stack_room = None
            print(f"  the next node in {names[0]}, room for {room or 'any'}:", [f"t{t}" for t in heap.deaths], "| put off:", len(heap.delete_later))
    head, nodes = chain(("a_nxt", "b_pay"), 6)
    w = O.weak_ref(nodes[2], lambda _: heap.deaths.append("weak"))
    heap.deaths.clear()
    heap.stack_room = 3                              # no room even at the outermost dealloc: what is put off waits
    decref(head)
    print("  room for 3:", [f"t{t}" for t in heap.deaths], "| put off:", len(heap.delete_later),
          "| a weak reference to a node put off reaches:", "nothing" if w() is None else "the node")
    heap.stack_room = None
    heap.deaths.clear()
    other = tagged(300)
    incref(other)
    decref(other)                                    # the first dealloc that ends with room lets them go
    print("  then, at another object's end:", [t if t == "weak" else f"t{t}" for t in heap.deaths], "| put off:", len(heap.delete_later))
    del w
    decref(plain)
    decref(p)


main()
