"""Deterministic cases from the review rounds, run against the reference model.

Each test states the CPython behaviour it encodes (verified by the corresponding conformance
case under conformance/cases) and checks that the model reproduces it. They run under pytest
or directly: python -m refmodel.tests.test_cases
"""
from __future__ import annotations

import gc
from collections.abc import Callable
import weakref

from refmodel.objects import (
    NO_VERSION,
    UNSET,
    VERSIONS,
    ModelError,
    RefClass,
    RefObject,
    Runtime,
    Site,
    decref,
    incref,
    make_descriptor_class,
)


def _world() -> tuple[Runtime, RefClass, RefClass, RefClass, RefClass]:
    A = RefClass("A", promoted=("x", "y"), attrs={"cv": 10})
    B = RefClass("B", (A,), promoted=("z",))
    S = RefClass("S", (A,), slots=("s",))
    T = RefClass("T", slots=("t",))
    return Runtime(), A, B, S, T


def test_dict_presence_is_inherited_layout_capability() -> None:
    _, A, B, S, T = _world()
    E = RefClass("E", (T,), slots=())            # __slots__ = () under a slotted base
    D = RefClass("D", (T,), slots=("__dict__",))
    assert A.has_dict and B.has_dict and S.has_dict and D.has_dict
    assert not T.has_dict and not E.has_dict     # review round three, finding 2


def test_exposed_dict_has_stable_identity_and_outlives_promotion() -> None:
    rt, A, *_ = _world()
    a = RefObject(A)
    rt.setattr(a, "y", 2)
    rt.setattr(a, "x", 1)
    rt.setattr(a, "w", 3)                        # undeclared: goes to the dict before exposure
    d = rt.expose_dict(a)
    assert d is rt.expose_dict(a)
    assert list(d.items()) == [("y", 2), ("x", 1), ("w", 3)]   # first-assignment order survives promotion
    assert a.inline["x"] is UNSET and a.inline["y"] is UNSET   # inline slots are dead after exposure
    rt.setattr(a, "x", 11)
    assert d["x"] == 11                          # writes go through the dict now
    del a                                        # the dict is an ordinary object: still usable
    assert d["w"] == 3


def test_dict_replacement_and_sharing() -> None:
    rt, A, *_ = _world()
    a, b = RefObject(A), RefObject(A)
    rt.setattr(a, "x", 1)
    old = rt.expose_dict(a)
    incref(old)                                  # a program variable holds the old dict (lifetimes: one count)
    rt.set_dict(a, {"y": 2})
    assert rt.getattr(a, "y") == 2 and old["x"] == 1
    try:
        rt.getattr(a, "x")
    except AttributeError:
        pass
    else:
        raise AssertionError("x should be gone after __dict__ replacement")
    rt.set_dict(b, rt.expose_dict(a))            # second.__dict__ = first.__dict__
    rt.setattr(a, "z", 3)
    assert rt.getattr(b, "z") == 3


def test_a_dropped_dict_leaves_the_object_as_it_was_made() -> None:
    rt, A, *_ = _world()
    a = RefObject(A)
    rt.setattr(a, "y", 2)
    rt.setattr(a, "w", 3)
    rt.drop_dict(a)                              # never exposed: what it held is gone with the dict it would have been
    assert not a.exposed and a.dict is None and a.order == [] and a.inline["y"] is UNSET
    rt.setattr(a, "x", 1)
    assert a.inline["x"] == 1 and a.order == ["x"]            # the class's keys are shared again
    held = rt.expose_dict(a)
    incref(held)                                 # a program variable holds it
    rt.drop_dict(a)                              # exposed: whoever holds the dict keeps it, as it is
    assert not a.exposed and a.dict is None and held.owner is None and list(held.items()) == [("x", 1)]
    fresh = rt.expose_dict(a)
    assert fresh is not held and list(fresh.items()) == []


def _dict_state(o: RefObject) -> tuple[bool, str]:
    """(its dict was deleted and nothing asked since, the dict it has: none, embedded (the object's own values), shared
    (the class's keys, values of its own), plain)."""
    d = o.dict if o.exposed else None
    return o.dropped, "none" if d is None else "plain" if d.split is None else "embedded" if d.owner is o else "shared"


def test_a_deleted_dict_is_settled_by_the_first_thing_asked() -> None:
    """C-3-58, measured on 3.15.2: after `del obj.__dict__` a plain read gives the object an ordinary dict, a write, a
    delete or its __dict__ one that shares the class's keys, and what the class answers alone gives it none."""
    rt, A, *_ = _world()
    data = RefObject(make_descriptor_class("D", lambda d, o, c: 7, lambda d, o, v: None))
    A.set_attr("dd", data)
    a = RefObject(A)
    rt.setattr(a, "x", 1)
    rt.setattr(a, "w", 2)
    rt.del_dict(a)
    assert _dict_state(a) == (True, "none") and a.dict is None and a.order == [] and a.inline["x"] is UNSET
    rt.del_dict(a)                               # again, with none: nothing
    assert rt.getattr(a, "dd") == 7 and _dict_state(a) == (True, "none")     # a data descriptor: the class answers alone
    rt.setattr(a, "dd", 1)
    assert _dict_state(a) == (True, "none")
    site = Site()
    assert rt.getattr(a, "cv", site) == 10       # a plain read reaches the instance: an ordinary dict
    assert _dict_state(a) == (False, "plain")
    rt.setattr(a, "x", 5)
    assert a.inline["x"] is UNSET and rt.expose_dict(a)["x"] == 5
    rt.del_dict(a)
    rt.setattr(a, "x", 6)                        # a write: a dict that shares the class's keys, its values its own
    assert _dict_state(a) == (False, "shared")
    rt.del_dict(a)
    before = list(A.keys)
    try:
        rt.delattr(a, "never")                   # a delete settles it the same way, and the name joins no keys
    except AttributeError:
        pass
    else:
        raise AssertionError("a name it has not")
    assert _dict_state(a) == (False, "shared") and list(A.keys) == before
    rt.del_dict(a)
    d = rt.expose_dict(a)                        # its __dict__: the same
    assert _dict_state(a) == (False, "shared") and rt.expose_dict(a) is d
    rt.del_dict(a)
    rt.set_dict(a, {"k": 1})                     # one given after: that one
    assert _dict_state(a) == (False, "plain") and rt.getattr(a, "k") == 1
    b = RefObject(A)
    rt.del_dict(b)
    assert rt.getattr(b, "cv", site) == 10 and _dict_state(b) == (False, "plain")     # the cached read too


def test_a_finaliser_meets_the_dropped_object() -> None:
    """The object is without its dict before the del releases anything (set_dict_inline_values stores the new dict and
    marks the values invalid first): a finaliser that reads then gives it an ordinary dict (measured on 3.15.2)."""
    rt, A, *_ = _world()
    seen: list[object] = []
    a = RefObject(A)
    incref(a)

    def fin(obj: RefObject) -> None:
        seen.append(_dict_state(a))
        try:
            rt.getattr(a, "w")
        except AttributeError:
            seen.append("no w")

    Looker = RefClass("Looker", attrs={"__del__": fin})
    rt.setattr(a, "x", RefObject(Looker))
    rt.setattr(a, "w", 2)
    rt.del_dict(a)
    assert seen == [(True, "none"), "no w"] and _dict_state(a) == (False, "plain")


def test_the_dict_an_instance_has_is_its_classes() -> None:
    """C-3-59, measured on 3.15.2: a type written in C with its own dict slot, and what derives from it, has an ordinary
    dict; an int's or a tuple's subclass a dict of its own that shares the class's keys; both made at the first write,
    the first delete or when asked for, and never by a read."""
    rt = Runtime()
    X = RefClass("X", dict_kind="plain")
    shared = RefClass("I", dict_kind="shared")
    assert RefClass("E", (X,)).dict_kind == "plain" and RefClass("M", (RefClass("Mixin"), X)).dict_kind == "plain"
    for cls in (X, shared):
        o = RefObject(cls)
        try:
            rt.getattr(o, "a")
        except AttributeError:
            pass
        assert _dict_state(o) == (False, "none")                 # a read asks for none
        rt.setattr(o, "a", 1)
        assert _dict_state(o) == (False, cls.dict_kind) and rt.getattr(o, "a") == 1
        asked = RefObject(cls)
        assert _dict_state(asked) == (False, "none") and rt.expose_dict(asked) is rt.expose_dict(asked)
        assert _dict_state(asked) == (False, cls.dict_kind)
    o = RefObject(shared)
    before = list(shared.keys)
    try:
        rt.delattr(o, "never")                   # the delete that fails makes the dict, and the name joins no keys
    except AttributeError:
        pass
    else:
        raise AssertionError("a name it has not")
    assert _dict_state(o) == (False, "shared") and list(shared.keys) == before
    rt.expose_dict(o).clear_()                   # its values are its own: cleared, it is an ordinary dict
    assert _dict_state(o) == (False, "plain")
    rt.del_dict(o)                               # no values in the object to mark invalid: as when it was made
    assert _dict_state(o) == (False, "none")
    rt.setattr(o, "a", 1)
    assert _dict_state(o) == (False, "shared")
    for refused, error in ((lambda: rt.del_dict(RefObject(X)), TypeError), (lambda: RefClass("Bad", promoted=("x",), dict_kind="plain"), ValueError),
                           (lambda: RefClass("Bad", dict_kind="odd"), ValueError)):
        try:
            refused()
        except error:
            pass
        else:
            raise AssertionError("refused")
    plain = RefObject(X)
    rt.setattr(plain, "a", 1)
    rt.drop_dict(plain)                          # a C type's own Py_CLEAR(self->dict): none again, and an ordinary one next
    assert _dict_state(plain) == (False, "none")
    rt.setattr(plain, "a", 1)
    assert _dict_state(plain) == (False, "plain")


def test_a_class_has_thirty_places_for_its_keys() -> None:
    """C-3-60, measured on 3.15.2 (found by the Hypothesis machine): a key takes one of a class's thirty places, and so
    does each instance made while more than one is left; an instance that stores a name the keys cannot take has an
    ordinary dict from there on, its values in the order they were stored."""
    rt = Runtime()
    K = RefClass("K")
    first = RefObject(K)
    rt.setattr(first, "x", 1)
    rt.setattr(first, "y", 2)
    assert K.keys == ["x", "y"] and K.keys_left == 27          # one instance and two keys
    for _ in range(40):
        RefObject(K)
    assert K.keys_left == 1                                    # the last place is a key's
    o = RefObject(K)
    rt.setattr(o, "x", 1)
    rt.setattr(o, "w", 2)                                      # one more name joins
    assert K.keys == ["x", "y", "w"] and K.keys_left == 0 and _dict_state(o) == (False, "none")
    rt.setattr(o, "v", 3)                                      # and then none
    assert _dict_state(o) == (False, "plain") and list(rt.expose_dict(o)) == ["x", "w", "v"] and K.keys == ["x", "y", "w"]
    rt.setattr(o, "y", 4)                                      # a name the keys hold is one more of the dict's now
    assert list(rt.expose_dict(o)) == ["x", "w", "v", "y"]
    p = RefObject(K)
    rt.setattr(p, "y", 1)
    rt.setattr(p, "x", 2)
    try:
        rt.delattr(p, "never")                                 # a delete that fails changes nothing
    except AttributeError:
        pass
    assert _dict_state(p) == (False, "none") and K.keys == ["x", "y", "w"]
    shared = RefClass("N", dict_kind="shared")                 # no values in the object: an instance takes no place
    for _ in range(40):
        RefObject(shared)
    assert shared.keys_left == 30 and RefClass("S", (K,)).keys_left == 30       # and a subclass has places of its own
    known = RefClass("Known", static_attributes=("b", "a"))
    assert known.keys == ["a", "b"] and known.keys_left == 28


def test_inline_field_shadows_class_attribute_and_cache_notices() -> None:
    rt, A, *_ = _world()
    A.set_attr("x", 1)
    a = RefObject(A)
    site = Site()
    assert rt.getattr(a, "x", site) == 1         # caches ClassAttr
    rt.setattr(a, "x", 2)                        # stored inline (promoted), dict stays None
    assert rt.getattr(a, "x", site) == 2         # review round three, finding 3
    rt.delattr(a, "x")
    assert rt.getattr(a, "x", site) == 1


def test_descriptor_class_promotion_invalidates_instance_storage_entries() -> None:
    rt, A, *_ = _world()
    a = RefObject(A)
    store: dict[int, object] = {}
    desc_cls = make_descriptor_class("Desc", lambda d, o, c: store.get(id(o), "from-descriptor"))
    A.set_attr("x", RefObject(desc_cls))         # non-data descriptor named like a promoted field
    rt.setattr(a, "x", 5)                        # instance storage wins over a non-data descriptor
    site = Site()
    assert rt.getattr(a, "x", site) == 5
    desc_cls.set_attr("__set__", lambda d, o, v: store.__setitem__(id(o), v))   # now a data descriptor
    assert rt.getattr(a, "x", site) == "from-descriptor"      # finding of 2026-10-31 (see objects.py)
    desc_cls.del_attr("__set__")                 # demotion: instance storage visible again
    assert rt.getattr(a, "x", site) == 5


def test_slots_are_data_descriptors_and_reject_undeclared_names() -> None:
    rt, A, B, S, T = _world()
    t = RefObject(T)
    try:
        rt.setattr(t, "w", 1)
    except AttributeError:
        pass
    else:
        raise AssertionError("T has no __dict__")
    rt.setattr(t, "t", 1)
    assert rt.getattr(t, "t") == 1
    rt.delattr(t, "t")
    try:
        rt.getattr(t, "t")
    except AttributeError:
        pass
    else:
        raise AssertionError("unset slot must raise")
    s = RefObject(S)
    rt.setattr(s, "w", 1)                        # S inherits a __dict__ from A
    assert rt.getattr(s, "w") == 1


def test_unsound_cache_is_reported_not_hidden() -> None:
    rt, A, *_ = _world()
    a = RefObject(A)
    site = Site()
    A.set_attr("x", 1)
    assert rt.getattr(a, "x", site) == 1
    # corrupt the cache on purpose: pretend the class never changed
    A.set_attr("x", 2)
    entry = site.entries[0]
    object.__setattr__(entry, "version", A.version)
    try:
        rt.getattr(a, "x", site)
    except ModelError:
        pass
    else:
        raise AssertionError("a stale entry served silently")



# ---- review 2026-11-01 (docs/reviews/review-log.md): each mirrors a conformance case ---------

def test_getattr_after_attributeerror_c_3_09() -> None:
    """C-3-09: an unset slot and a descriptor whose __get__ raises AttributeError both fall
    through to __getattr__; without a hook the AttributeError propagates."""
    rt = Runtime()
    hook = lambda obj, name: f"fallback:{name}"  # noqa: E731
    Slotted = RefClass("Slotted", slots=("s",), attrs={"__getattr__": hook})
    assert rt.getattr(RefObject(Slotted), "s", Site()) == "fallback:s"

    def raising_get(desc: RefObject, obj: RefObject, owner: RefClass) -> int:
        raise AttributeError("from __get__")
    Raising = make_descriptor_class("Raising", raising_get)
    W = RefClass("W", attrs={"p": RefObject(Raising), "__getattr__": hook})
    site = Site()
    assert [rt.getattr(RefObject(W), "p", site) for _ in range(2)] == ["fallback:p", "fallback:p"]
    NoHook = RefClass("NoHook", slots=("s",))
    try:
        rt.getattr(RefObject(NoHook), "s", Site())
    except AttributeError:
        pass
    else:
        raise AssertionError("an unset slot without __getattr__ must raise AttributeError")


def test_attribute_hooks_run_once_per_read_c_3_10() -> None:
    """C-3-10: the cache check must not execute __get__ or __getattr__ a second time."""
    rt = Runtime()
    calls: list[str] = []

    def counting_get(desc: RefObject, obj: RefObject, owner: RefClass) -> int:
        calls.append("get")
        return len(calls)
    C = RefClass("C", attrs={"p": RefObject(make_descriptor_class("Counting", counting_get))})
    c, site = RefObject(C), Site()
    assert [rt.getattr(c, "p", site) for _ in range(3)] == [1, 2, 3]
    assert calls == ["get", "get", "get"]

    calls.clear()
    Lazy = RefClass("Lazy")

    def lazy(obj: RefObject, name: str) -> int:
        calls.append(f"getattr {name}")
        Lazy.set_attr(name, 2)                  # memoise on the class (bumps its version)
        return 1
    Lazy.set_attr("__getattr__", lazy)
    z, site = RefObject(Lazy), Site()
    assert [rt.getattr(z, "x", site), rt.getattr(z, "x", site), rt.getattr(RefObject(Lazy), "x", site)] == [1, 2, 2]
    assert calls == ["getattr x"]


def test_class_attribute_becomes_descriptor_c_3_11() -> None:
    """C-3-11: a ClassAttr entry depends on the found object's class and version too."""
    rt = Runtime()
    D = RefClass("D")
    d = RefObject(D)
    Holder = RefClass("Holder", attrs={"x": d})
    h, site = RefObject(Holder), Site()
    assert rt.getattr(h, "x", site) is d
    D.set_attr("__get__", lambda desc, obj, owner=None: 99)
    assert rt.getattr(h, "x", site) == 99
    D.del_attr("__get__")
    assert rt.getattr(h, "x", site) is d



# ---- review log D-1 (2026-11-01): class versions from one global counter ---------------------

def test_dead_class_entries_never_match_a_new_class_c_3_12() -> None:
    """C-3-12, RL-23: classes that die one after another and are read through one site. Each
    new class misses on its first read, whatever memory it reuses, and no entry keeps a class
    alive."""
    rt, site = Runtime(), Site()
    shapes = [
        ("TwoSlots", {"slots": ("a", "x")}, "second slot"),
        ("OneSlot", {"slots": ("x",)}, "first slot"),
        ("ClassAttribute", {"attrs": {"x": "class attribute"}}, None),
        ("Plain", {"promoted": ("x",)}, "instance dictionary"),
    ]
    versions: list[int] = []
    for _ in range(2):
        for name, layout, stored in shapes:
            K = RefClass(name, **layout)  # type: ignore[arg-type]
            versions.append(K.version)
            o = RefObject(K)
            incref(o)                       # the program's variable; its release below lets the object go
            if stored is not None:
                rt.setattr(o, "x", stored)
            misses = site.misses
            first = rt.getattr(o, "x", site)
            # the first read misses, whatever a dead class left at this address; whether the second
            # hits depends on the allocator (dead classes' entries fill the site unless an address is
            # reused), so it is not asserted: run alone, the seventh class finds the site megamorphic
            assert site.misses == misses + 1, name
            assert first == rt.getattr(o, "x", site) == (stored or "class attribute")
            ref = weakref.ref(K)
            decref(o)
            del K, o
            gc.collect()
            assert ref() is None, f"a cache entry kept {name} alive"
    assert len(set(versions)) == len(versions) and NO_VERSION not in versions


def test_a_reissued_version_is_served_stale_d_1() -> None:
    """What per-class versions would do: give a new class a number a dead class's entry still
    carries. The cache then selects the dead class's plan, and the model reports it."""
    rt, site = Runtime(), Site()
    Old = RefClass("Old", attrs={"x": "old"})
    assert rt.getattr(RefObject(Old), "x", site) == "old"
    stale = Old.version
    del Old
    New = RefClass("New", slots=("x",))
    n = RefObject(New)
    rt.setattr(n, "x", "new")
    New.version = stale
    try:
        rt.getattr(n, "x", site)
    except ModelError:
        pass
    else:
        raise AssertionError("a reissued version served a dead class's entry silently")


def test_every_bump_takes_a_new_version_and_exhaustion_stops_caching_d_1() -> None:
    A = RefClass("A")
    B = RefClass("B", (A,), promoted=("x",))
    C = RefClass("C", (A,))
    before = {A.version, B.version, C.version}
    A.set_attr("x", 1)                           # A and both subclasses: three new, distinct versions
    after = {A.version, B.version, C.version}
    assert len(after) == 3 and not after & before
    C.unregister()                               # a dying subclass leaves its bases
    c_version = C.version
    A.set_attr("x", 2)
    assert C.version == c_version and C not in A.subclasses

    rt, site = Runtime(), Site()
    saved = VERSIONS.limit
    VERSIONS.limit = VERSIONS.next               # one version left: A takes it, B gets none
    try:
        A.set_attr("x", 3)
        assert A.version != NO_VERSION and B.version == NO_VERSION
        b = RefObject(B)
        assert [rt.getattr(b, "x", site) for _ in range(3)] == [3, 3, 3]
        assert site.hits == 0 and site.entries == []       # an uncacheable class is always looked up
        rt.setattr(b, "x", 4)
        assert [rt.getattr(b, "x", site) for _ in range(2)] == [4, 4] and site.hits == 0
        a = RefObject(A)
        assert [rt.getattr(a, "x", site) for _ in range(2)] == [3, 3] and site.hits == 1
    finally:
        VERSIONS.limit = saved

# ---- lifetimes (task 3; review log RL-20, RL-49; case C-9-08) ------------------------------------

def _tagged(heap: object, tag: str) -> RefObject:
    """A value whose death the heap logs, held by the caller until it is stored."""
    from refmodel import objects as O
    tracked = RefClass("Tracked")
    v = RefObject(tracked, tag=tag)
    O.incref(v)
    return v


def _store(rt: Runtime, obj: RefObject, name: str, tag: str) -> None:
    from refmodel import objects as O
    v = _tagged(O.HEAP, tag)
    rt.setattr(obj, name, v)
    O.decref(v)                       # the caller's temporary ends


def _fresh_heap() -> object:
    from refmodel import objects as O
    O.HEAP = O.Heap()
    return O.HEAP


def _deaths() -> list[object]:
    from refmodel import objects as O
    out = list(O.HEAP.deaths)
    O.HEAP.deaths.clear()
    return out


def test_attribute_values_die_in_the_class_key_order_c_9_08() -> None:
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Plain = RefClass("Plain", promoted=("x", "y"))
    first = RefObject(Plain)
    O.incref(first)
    _store(rt, first, "x", "x1")
    _store(rt, first, "y", "y1")
    O.decref(first)
    assert _deaths() == ["x1", "y1"]
    later = RefObject(Plain)
    O.incref(later)
    for name in ("y", "z", "x"):
        _store(rt, later, name, f"{name}2")
    O.decref(later)
    assert _deaths() == ["x2", "y2", "z2"]          # the class's keys, not this instance's order
    Init = RefClass("Init", static_attributes=("b", "a"))
    init = RefObject(Init)
    O.incref(init)
    _store(rt, init, "b", "b")
    _store(rt, init, "a", "a")
    O.decref(init)
    assert _deaths() == ["a", "b"]                  # __static_attributes__, sorted


def test_rebinding_deleting_and_dicts_c_9_08() -> None:
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Plain = RefClass("Plain", promoted=("x",))
    o = RefObject(Plain)
    O.incref(o)
    _store(rt, o, "x", "old")
    _store(rt, o, "x", "new")
    assert _deaths() == ["old"]
    rt.delattr(o, "x")
    assert _deaths() == ["new"]
    _store(rt, o, "y", "y")
    d = rt.expose_dict(o)
    O.incref(d)                                     # a program variable holds the dict
    O.decref(o)
    assert _deaths() == []
    O.decref(d)
    assert _deaths() == ["y"]
    o2 = RefObject(Plain)
    O.incref(o2)
    _store(rt, o2, "y", "y")
    _store(rt, o2, "x", "x")
    q, pv = _tagged(O.HEAP, "q"), _tagged(O.HEAP, "p")
    rt.set_dict(o2, {"q": q, "p": pv})
    O.decref(q)
    O.decref(pv)
    assert _deaths() == ["x", "y"]                  # the old dict was split: key order
    O.decref(o2)
    assert _deaths() == ["q", "p"]                  # an installed dict: insertion order
    a1, a2 = RefObject(Plain), RefObject(Plain)
    O.incref(a1)
    O.incref(a2)
    _store(rt, a1, "x", "shared")
    rt.set_dict(a2, rt.expose_dict(a1))
    O.decref(a1)
    assert _deaths() == []
    O.decref(a2)
    assert _deaths() == ["shared"]


def test_a_failed_delete_moves_the_key_c_9_08() -> None:
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Probe = RefClass("Probe")
    probe = RefObject(Probe)
    try:
        rt.delattr(probe, "y")
    except AttributeError:
        pass
    second = RefObject(Probe)
    O.incref(second)
    _store(rt, second, "x", "x")
    _store(rt, second, "y", "y")
    O.decref(second)
    assert _deaths() == ["y", "x"]


def test_slots_die_most_derived_first_then_the_dict_c_9_08() -> None:
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Slotted = RefClass("Slotted", slots=("p", "q"))
    Derived = RefClass("Derived", (Slotted,), slots=("r", "__dict__"))
    s = RefObject(Derived)
    O.incref(s)
    for name in ("x", "q", "r", "p"):
        _store(rt, s, name, name)
    O.decref(s)
    assert _deaths() == ["r", "p", "q", "x"]


def test_slots_die_sorted_by_name_not_declared_order_c_9_08() -> None:
    """CPython sorts a class's __slots__ when it makes the class (review 2026-11-02, A8-10)."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Base = RefClass("Base", slots=("zeta", "alpha"))
    Unsorted = RefClass("Unsorted", (Base,), slots=("mid", "beta"))
    u = RefObject(Unsorted)
    O.incref(u)
    for name in ("zeta", "alpha", "mid", "beta"):
        _store(rt, u, name, name)
    O.decref(u)
    assert _deaths() == ["beta", "mid", "alpha", "zeta"]


def test_a_descriptor_is_owned_while_its_get_runs_a8_1() -> None:
    """A lookup holds the descriptor it found while __get__ runs: one whose __get__ deletes it
    from the class is still alive inside __get__, and dies as __get__ fails, before the
    __getattr__ hook runs (review 2026-11-02, A8-1; measured on 3.15.2,
    runtime/tests/object_reentrancy.py, which also covers the hook's own lifetime on the header)."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    seen: dict[str, list[object]] = {}

    def get(d: object, obj: object, cls: object) -> object:
        C.del_attr("x")
        seen["in get, after the delete"] = list(O.HEAP.deaths)
        raise AttributeError("x")

    def hook(obj: object, name: str) -> object:
        seen["in the hook"] = list(O.HEAP.deaths)
        return "from hook"

    C = RefClass("C", attrs={"__getattr__": hook})
    desc = RefObject(make_descriptor_class("Desc", get), tag="desc")
    O.incref(desc)
    C.set_attr("x", desc)
    O.decref(desc)                                  # only the class holds it now
    obj = RefObject(C)
    O.incref(obj)
    assert rt.getattr(obj, "x", Site()) == "from hook"
    assert seen == {"in get, after the delete": [], "in the hook": ["desc"]}


def test_a_getattr_hook_is_called_as_call_attribute_does() -> None:
    """slot_tp_getattr_hook calls a function hook with the object and the name, binds a descriptor
    hook first, and calls any other callable with the name alone (CPython's call_attribute)."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    calls: list[tuple[object, ...]] = []

    def plain(obj: object, name: str) -> object:
        calls.append(("function", name))
        return 1

    def call(self: object, name: str) -> object:
        calls.append(("__call__", name))
        return 2

    def get(d: object, obj: object, cls: object) -> object:
        def bound(name: str) -> object:
            calls.append(("bound", obj is instance_b, name))
            return 3
        return bound

    A = RefClass("A", attrs={"__getattr__": plain})
    hook_c = RefObject(RefClass("Callable", attrs={"__call__": call}))
    B = RefClass("B", attrs={"__getattr__": RefObject(make_descriptor_class("Binder", get))})
    C = RefClass("C", attrs={"__getattr__": hook_c})
    instance_b = RefObject(B)
    O.incref(instance_b)
    got = [rt.getattr(RefObject(A), "x"), rt.getattr(instance_b, "y"), rt.getattr(RefObject(C), "z")]
    assert got == [1, 3, 2], got
    assert calls == [("function", "x"), ("bound", True, "y"), ("__call__", "z")], calls


# An exposed dict under the program's dict operations (step 3a.3): which ones keep it split, so
# that its values die in the class's key order, and which make it ordinary (insertion order).
# A scenario is a list of statements: run as a CPython program after SPLIT_PRELUDE, and through
# the model by _SPLIT_STEPS; "|" marks a checkpoint in both.
SPLIT_PRELUDE = """
class V:
    def __init__(s, n): s.n = n
    def __del__(s): print(s.n)
class C: pass
seed = C(); seed.p = 0; seed.q = 0; seed.r = 0
"""
SPLIT_INSTANCE = "o = C(); o.r = V('r'); o.q = V('q'); o.p = V('p')\nd = vars(o)"
SPLIT_SCENARIOS: dict[str, list[str]] = {
    "exposed": ["del o", "|", "del d"],
    "int key": ["d[1] = V('1')", "del o", "del d"],
    "new str key": ["d['s'] = V('s')", "del o", "del d"],
    "delete and reinsert": ["del d['q']", "|", "d['q'] = V('q2')", "del o", "del d"],
    "popitem": ["del o", "x = d.popitem()", "del x", "|", "del d"],
    "clear, owner alive": ["d.clear()", "|", "d['q'] = V('q2')", "d['p'] = V('p2')", "del o", "|", "del d"],
    "clear, owner dead": ["del o", "d.clear()", "|", "d['q'] = V('q2')", "d['p'] = V('p2')", "del d"],
    "clear after replacement": ["o.__dict__ = {}", "d.clear()", "|", "d['q'] = V('q2')", "d['p'] = V('p2')", "del d", "|",
                                "del o"],
    "copy": ["c = d.copy()", "del o", "del d", "|", "del c"],
}


def split_program(scenario: str) -> str:
    steps = ["print('|')" if s == "|" else s for s in SPLIT_SCENARIOS[scenario]]
    return SPLIT_INSTANCE + "\n" + "\n".join(steps) + "\n"


class _SplitWorld:
    def __init__(self) -> None:
        from refmodel import objects as O
        self.O = O
        _fresh_heap()
        self.rt = Runtime()
        C = RefClass("C")
        seed = RefObject(C)
        O.incref(seed)
        for n in ("p", "q", "r"):
            self.rt.setattr(seed, n, 0)
        self.o = RefObject(C)
        O.incref(self.o)
        for n in ("r", "q", "p"):
            _store(self.rt, self.o, n, n)
        self.d = self.rt.expose_dict(self.o)
        O.incref(self.d)
        self.c: object = None

    def put(self, key: object, tag: str) -> None:
        v = _tagged(self.O.HEAP, tag)
        self.d.store(key, v)
        self.O.decref(v)

    def popitem(self) -> None:
        _, v = self.d.popitem_()
        self.O.decref(v)

    def copy(self) -> None:
        self.c = self.d.copy_()
        self.O.incref(self.c)


_SPLIT_STEPS: dict[str, Callable[[_SplitWorld], object]] = {
    "|": lambda w: w.O.HEAP.deaths.append("|"),
    "del o": lambda w: w.O.decref(w.o),
    "del d": lambda w: w.O.decref(w.d),
    "del c": lambda w: w.O.decref(w.c),
    "d[1] = V('1')": lambda w: w.put(1, "1"),
    "d['s'] = V('s')": lambda w: w.put("s", "s"),
    "d['q'] = V('q2')": lambda w: w.put("q", "q2"),
    "d['p'] = V('p2')": lambda w: w.put("p", "p2"),
    "del d['q']": lambda w: w.d.delete("q"),
    "x = d.popitem()": lambda w: w.popitem(),
    "del x": lambda w: None,
    "d.clear()": lambda w: w.d.clear_(),
    "o.__dict__ = {}": lambda w: w.rt.set_dict(w.o, {}),
    "c = d.copy()": lambda w: w.copy(),
}


def _split_model(scenario: str) -> list[object]:
    w = _SplitWorld()
    for step in SPLIT_SCENARIOS[scenario]:
        _SPLIT_STEPS[step](w)
    return _deaths()


def test_an_exposed_dict_stays_split_as_cpythons() -> None:
    """vars(obj) under dict operations: CPython 3.15.2 (run here) and the model agree on the order
    every value dies in, which says whether the dict was split (the class's key order) or ordinary
    (insertion order) at each point."""
    import subprocess
    import sys
    for scenario in SPLIT_SCENARIOS:
        out = subprocess.run([sys.executable, "-c", SPLIT_PRELUDE + split_program(scenario)],
                             capture_output=True, text=True, check=True)
        got = _split_model(scenario)
        assert got == out.stdout.split(), (scenario, got, out.stdout.split())


def test_a_found_object_is_borrowed_and_never_read_dead_rl_20() -> None:
    """A cache entry names its found object without holding it. Replacing the class attribute
    kills the descriptor while the entry still names it; the class took a new version first, so
    the entry is never valid again and never read."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Desc = make_descriptor_class("Desc", lambda d, o, c: "described")
    A = RefClass("A")
    desc = RefObject(Desc, tag="desc")
    O.incref(desc)
    A.set_attr("x", desc)
    O.decref(desc)                                  # only the class holds it now
    site = Site()
    obj = RefObject(A)
    O.incref(obj)
    assert rt.getattr(obj, "x", site) == "described"
    assert site.entries and site.entries[0].found is desc
    A.set_attr("x", 5)
    assert _deaths() == ["desc"]                    # dead, while the stale entry still names it
    assert rt.getattr(obj, "x", site) == 5          # the entry's version is gone: never dereferenced


def test_releasing_before_the_version_bump_is_caught_rl_20() -> None:
    """Fault injection: a class mutation that released the old value before taking a new version
    would let a finaliser meet an entry that is still valid and names a dead object."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    Desc = make_descriptor_class("Desc", lambda d, o, c: "described")
    A = RefClass("A")
    desc = RefObject(Desc)
    O.incref(desc)
    A.set_attr("x", desc)
    O.decref(desc)
    site = Site()
    obj = RefObject(A)
    O.incref(obj)
    rt.getattr(obj, "x", site)

    def wrong_set_attr(self: RefClass, name: str, value: object) -> None:
        old = self.attrs.get(name)
        O.incref(value)
        self.attrs[name] = value
        O.decref(old)                               # released first ...
        self.bump()                                 # ... versioned after: wrong
    try:
        wrong_set_attr(A, "x", 5)
    except ModelError as exc:
        assert "valid cache entry" in str(exc)
    else:
        raise AssertionError("a valid entry naming a dead object went unnoticed")


BASE_EXCEPTION_FIELDS = ("__dict__", "args", "__traceback__", "__cause__", "__context__")   # BaseException_clear


def test_a_builtin_bases_fields_die_after_the_slots_in_its_clear_order() -> None:
    """An exception's args, cause and context are C fields of BaseException: never in its
    __dict__, released by BaseException_clear after the subclass's __slots__, the dict first.
    Measured on 3.15.2 (review 2026-11-03, A10-3): slot, dict value, args, cause, context."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    base = RefClass("BaseException", native=BASE_EXCEPTION_FIELDS)
    E = RefClass("E", (RefClass("Exception", (base,)),), slots=("s",))
    e = RefObject(E)
    O.incref(e)
    for name, tag in (("args", "arg"), ("s", "slot"), ("x", "dictval"), ("__cause__", "cause"), ("__context__", "context")):
        _store(rt, e, name, tag)
    assert list(rt.expose_dict(e)) == ["x"]
    O.decref(e)
    assert _deaths() == ["slot", "dictval", "arg", "cause", "context"]
    # AttributeError_clear: obj and name, then BaseException_clear
    attribute_error = RefClass("AttributeError", (base,), native=("obj", "name", *BASE_EXCEPTION_FIELDS))
    a = RefObject(attribute_error)
    O.incref(a)
    for name in ("args", "x", "name", "obj"):
        _store(rt, a, name, name)
    O.decref(a)
    assert _deaths() == ["obj", "name", "x", "args"]
    # the solid base decides: a mixin first keeps the exception's layout
    mixed = RefObject(RefClass("Mixed", (RefClass("Mixin"), RefClass("Exception2", (base,)))))
    O.incref(mixed)
    for name in ("args", "x"):
        _store(rt, mixed, name, name)
    O.decref(mixed)
    assert _deaths() == ["x", "args"]


def test_a_dict_subclass_instance_is_a_dict_released_last() -> None:
    """An instance of a dict subclass holds the dict's entries itself, beside its slots and its
    instance dict, and dies as subtype_dealloc then dict_dealloc release it: the slots, the instance
    dict, then the entries in order, each key before its value (decision 2026-11-03; measured on
    3.15.2: slot, attribute, value, key; case C-3-34)."""
    from refmodel import objects as O
    _fresh_heap()
    rt = Runtime()
    builtin_dict = RefClass("dict", native=("__dict__", "__payload__"))
    Slotted = RefClass("Slotted", (builtin_dict,), slots=("s", "__dict__"))
    d = RefObject(Slotted)
    O.incref(d)
    assert d.payload is not None
    value, key = _tagged(O.HEAP, "value"), _tagged(O.HEAP, "key")
    d.payload.put("k", value)
    d.payload.put(key, 1)
    O.decref(value)                                 # the caller's temporaries end
    O.decref(key)
    _store(rt, d, "s", "slot")
    _store(rt, d, "attr", "attribute")
    assert list(rt.expose_dict(d)) == ["attr"]      # the entries are not the instance's attributes
    O.decref(d)
    assert _deaths() == ["slot", "attribute", "value", "key"]


def test_a_store_that_fails_takes_no_count() -> None:
    """d[k] = v whose key comparison raises leaves v's count as it was: insertdict releases the
    value it was given before the error propagates (review 2026-11-03, A10-5)."""
    from refmodel import objects as O
    _fresh_heap()

    class Key:
        def __hash__(self) -> int:
            return 1

        def __eq__(self, other: object) -> bool:
            raise ValueError("eq")

    d = O.RefDict()
    first = _tagged(O.HEAP, "first")
    d.store(Key(), first)
    O.decref(first)
    v = _tagged(O.HEAP, "value")
    try:
        d.store(Key(), v)
    except ValueError:
        pass
    else:
        raise AssertionError("the comparison did not raise")
    assert v.refs == 1 and len(d) == 1
    O.decref(v)
    assert _deaths() == ["value"]


def test_slot_descriptors_stand_in_the_class_dict_sorted() -> None:
    """type_new_slots sorts __slots__, and the class dict takes the member descriptors in that order
    (found by the stateful test: a class's attributes are released in its dict's order)."""
    assert [n for n in RefClass("R", slots=("x", "k", "a")).attrs] == ["a", "k", "x"]

    class R:
        __slots__ = ("x", "k", "a")
    assert [n for n in vars(R) if n in ("x", "k", "a")] == ["a", "k", "x"]


def test_a_finaliser_runs_once_whoever_runs_it_first() -> None:
    """PEP 442: the collector, or at exit the walk that stands for it (RL-281), runs a finaliser on
    a live object; its death then does not run it again. A lone death still runs it."""
    from refmodel import objects as O
    _fresh_heap()
    ran: list[str] = []
    C = RefClass("C", attrs={"__del__": lambda self: ran.append(self.tag)})
    collected, lone = RefObject(C, tag="collected"), RefObject(C, tag="lone")
    O.incref(collected)
    O.incref(lone)
    collected.finalize()
    collected.finalize()
    assert ran == ["collected"]
    alive = [collected.alive]
    O.decref(collected)
    alive.append(collected.alive)
    assert ran == ["collected"] and alive == [True, False]
    O.decref(lone)
    assert ran == ["collected", "lone"] and not lone.alive


def test_a_metaclass_mro_is_what_lookups_walk() -> None:
    """mro_internal (RL-314): a replaced MRO decides lookups from then on, under a new version, so
    a cache entry of the old order cannot match."""
    _fresh_heap()
    O1 = RefClass("O1", attrs={"x": "O1"})
    O2 = RefClass("O2", attrs={"x": "O2"})
    T = RefClass("T", (O1, O2))
    found = T.lookup("x")
    assert found is not None and found[0] == "O1"
    before = T.version
    T.set_mro([T, O2, O1, *O1.mro[1:]])
    found = T.lookup("x")
    assert found is not None and found[0] == "O2" and T.version != before


def test_a_view_of_a_class_dict_changes_no_death() -> None:
    """The dict behind `C.__dict__.items()` follows the class, in its order, and holds a second
    count that is always dropped first: with or without it a value dies at the same moment, and a
    finaliser reads the class as already changed."""
    from refmodel import objects as O

    def story(with_view: bool) -> list[object]:
        _fresh_heap()
        log: list[object] = []
        K = RefClass("K", attrs={"a": 1})
        V = RefClass("V", attrs={"__del__": lambda self: log.append((self.tag, "dies", sorted(K.attrs)))})
        if with_view:
            assert K.class_dict() == {"a": 1}
        for name in ("x", "y"):
            v = RefObject(V, tag=name)
            O.incref(v)
            K.set_attr(name, v)
            O.decref(v)
            log.append(("set", name))
        K.set_attr("x", 2)
        log.append("replaced x")
        K.del_attr("y")
        log.append("deleted y")
        z = RefObject(V, tag="z")
        O.incref(z)
        K.set_attr("z", z)
        O.decref(z)
        K.dispose()
        log.append("disposed")
        if with_view:
            assert K.dict_view is None
        return log

    assert story(True) == story(False)
    _fresh_heap()
    K = RefClass("K", attrs={"a": 1, "b": 2})
    view = K.class_dict()
    K.del_attr("a")
    K.set_attr("c", 3)
    K.set_attr("a", 4)
    K.set_attr("b", 5)
    assert list(view.items()) == list(K.attrs.items()) == [("b", 5), ("c", 3), ("a", 4)]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


def test_a_finaliser_that_keeps_its_object_leaves_it_whole() -> None:
    """Spec section 9, C-9-04: the object lives on with its weak references and its fields, its finaliser
    spent; the second release runs no finaliser, and clears the references before the fields go."""
    from refmodel import objects as O
    _fresh_heap()
    log: list[str] = []
    kept: list[RefObject] = []

    def keep(self: RefObject) -> None:
        log.append("finaliser")
        O.incref(self)
        kept.append(self)

    C = RefClass("C", slots=("v", "__weakref__"), attrs={"__del__": keep})
    V = RefClass("V")
    o, value = RefObject(C), RefObject(V, tag="value")
    O.incref(o)
    O.incref(value)
    Runtime().setattr(o, "v", value)
    O.decref(value)
    plain = O.weak_ref(o)
    with_callback = O.weak_ref(o, lambda w: log.append(f"callback, dead={w() is None}"))
    O.decref(o)
    seen = (o.alive, plain() is o, with_callback() is o, list(log), list(kept), list(O.HEAP.deaths))
    assert seen == (True, True, True, ["finaliser"], [o], [])
    log.clear()
    O.decref(kept.pop())
    assert (o.alive, plain(), with_callback(), log, O.HEAP.deaths) == (False, None, None, ["callback, dead=True"], ["value"])


def test_a_list_of_weak_references_is_in_cpythons_order() -> None:
    """The basic reference is shared and first; the others come newest first, and their callbacks in that
    order; one that dies before its target leaves the list and is never called; a class has room for
    weak references as it has for a dict, unless __slots__ leaves it out."""
    from refmodel import objects as O
    _fresh_heap()
    log: list[str] = []
    C = RefClass("C")
    o = RefObject(C)
    O.incref(o)

    def named(n: str) -> Callable[[object], None]:
        return lambda w: log.append(n)

    first, second, gone = O.weak_ref(o, named("first")), O.weak_ref(o, named("second")), O.weak_ref(o, named("gone"))
    basic = O.weak_ref(o)
    assert O.weak_ref(o) is basic and basic.refs == 2 and o.weakrefs == [basic, gone, second, first]
    O.decref(gone)
    assert list(o.weakrefs) == [basic, second, first]
    O.decref(o)
    assert (log, basic(), first(), o.weakrefs) == (["second", "first"], None, None, [])
    S = RefClass("S", slots=("x",))
    W = RefClass("W", (S,), slots=("__weakref__",))
    try:
        O.weak_ref(RefObject(S))
    except TypeError:
        pass
    else:
        raise AssertionError("a class with __slots__ and no __weakref__ has no room for one")
    w = RefObject(W)
    O.incref(w)
    assert O.weak_ref(w)() is w


# ---- the cycle collector (step 3c): refmodel/collector.py against CPython's ---------------------------------------

def _cpython_cycle(resurrect: bool) -> tuple[list[str], int]:
    """C-9-07's shape on CPython, with its collector off but for the one collection asked."""
    events: list[str] = []
    keep: list[object] = []
    refs: list[weakref.ref[object]] = []

    class Node:
        def __del__(self) -> None:
            events.append(f"del plain={refs[0]() is None} callback={refs[1]() is None}")
            if resurrect:
                keep.append(self)

    was = gc.isenabled()
    gc.disable()
    try:
        gc.collect()
        n = Node()
        n.me = n  # type: ignore[attr-defined]
        refs.append(weakref.ref(n))
        refs.append(weakref.ref(n, lambda _: events.append("callback")))
        del n
        found = gc.collect()
        events.append(f"after plain={refs[0]() is None} callback={refs[1]() is None} kept={len(keep)}")
        keep.clear()
        gc.collect()
        events.append(f"released plain={refs[0]() is None}")
    finally:
        if was:
            gc.enable()
    return events, found


def _model_cycle(resurrect: bool) -> tuple[list[str], int]:
    from refmodel import collector
    from refmodel import objects as O
    from refmodel.objects import weak_ref

    saved = O.HEAP
    heap = O.HEAP = O.Heap()
    try:
        events: list[str] = []
        keep: list[RefObject] = []
        refs: list[O.RefWeak] = []

        def fin(obj: RefObject) -> None:
            events.append(f"del plain={refs[0]() is None} callback={refs[1]() is None}")
            if resurrect:
                incref(obj)
                keep.append(obj)

        rt = Runtime()
        node = RefClass("Node", attrs={"__del__": fin}, heap=heap)
        n = RefObject(node)
        incref(n)
        rt.setattr(n, "me", n)
        refs.append(weak_ref(n))
        refs.append(weak_ref(n, lambda _: events.append("callback")))
        decref(n)
        found = collector.collect(heap)
        events.append(f"after plain={refs[0]() is None} callback={refs[1]() is None} kept={len(keep)}")
        for obj in reversed(keep):
            decref(obj)
        keep.clear()
        collector.collect(heap)
        events.append(f"released plain={refs[0]() is None}")
        return events, found
    finally:
        O.HEAP = saved


def test_the_cyclic_sequence_is_cpythons_c_9_07() -> None:
    """C-9-01, C-9-02, C-9-07 in the model: the callback before the finaliser, a weak reference without a callback
    alive inside it and through a resurrection, and the number a collection finds, as CPython 3.15.2 gives them."""
    for resurrect in (False, True):
        assert _model_cycle(resurrect) == _cpython_cycle(resurrect), resurrect


def test_generations_are_cpythons() -> None:
    """Which generation a survivor is in after collections of each generation, and that a young collection leaves
    alone what an older object holds: the model against CPython's gc.get_objects(generation)."""
    from refmodel import collector
    from refmodel import objects as O

    class R:
        pass

    def cpython() -> list[list[int]]:
        gc.disable()
        try:
            gc.collect()
            old = R()
            gc.collect()                       # old in the oldest generation
            objs = [R() for _ in range(4)]
            objs[0].peer = objs[1]  # type: ignore[attr-defined]
            objs[1].peer = objs[0]  # type: ignore[attr-defined]  # a young cycle
            old.held = objs[2]  # type: ignore[attr-defined]
            objs[2].peer = objs[2]  # type: ignore[attr-defined]  # a young cycle an old object holds
            objs[3].peer = objs[3]  # type: ignore[attr-defined]
            keep = [objs[3]]
            del objs
            out: list[list[int]] = []
            for generation in (0, 1, 0, 2):
                found = gc.collect(generation)
                members = [old, old.held, keep[0]]  # type: ignore[attr-defined]
                out.append([found] + [next(g for g in range(3) if any(x is m for x in gc.get_objects(g))) for m in members])
            return out
        finally:
            gc.enable()

    def model() -> list[list[int]]:
        saved = O.HEAP
        heap = O.HEAP = O.Heap()
        try:
            rt = Runtime()
            K = RefClass("R", heap=heap)
            collector.collect(heap)
            old = RefObject(K)
            incref(old)
            collector.collect(heap)
            objs = [RefObject(K) for _ in range(4)]
            for o in objs:
                incref(o)
            rt.setattr(objs[0], "peer", objs[1])
            rt.setattr(objs[1], "peer", objs[0])
            rt.setattr(old, "held", objs[2])
            rt.setattr(objs[2], "peer", objs[2])
            rt.setattr(objs[3], "peer", objs[3])
            keep = objs[3]
            for o in objs[:3]:
                decref(o)
            out: list[list[int]] = []
            for generation in (0, 1, 0, 2):
                found = collector.collect(heap, generation)
                members = [old, rt.getattr(old, "held"), keep]
                out.append([found] + [int(heap.gc.where[id(m)].name.split()[-1]) for m in members])
            return out
        finally:
            O.HEAP = saved

    assert model() == cpython()


def test_a_collection_is_scheduled_by_the_threshold_and_runs_at_a_look() -> None:
    """_PyObject_GC_Link: the 2001st new object schedules a collection, which runs at the next look (_Py_RunGC) and
    takes the first generation; a disabled collector runs none, a threshold of 0 schedules none."""
    from refmodel import collector
    from refmodel import objects as O

    saved = O.HEAP
    heap = O.HEAP = O.Heap()
    try:
        K = RefClass("K", heap=heap)
        made = []

        def scheduled() -> bool:
            return heap.gc.scheduled

        for _ in range(2000):
            made.append(RefObject(K))
            incref(made[-1])
        assert not scheduled() and heap.gc.counts[0] == 2000
        made.append(RefObject(K))
        incref(made[-1])
        assert scheduled()
        assert collector.look(heap) == 0 and not scheduled()
        assert heap.gc.counts == [0, 1, 0] and len(heap.gc.generations[1]) == 2001
        heap.gc.enabled = False
        heap.gc.counts[0] = 2000
        RefObject(K).refs = 1
        assert not scheduled()                    # disabled: nothing scheduled
        heap.gc.enabled, heap.gc.thresholds[0] = True, 0
        RefObject(K).refs = 1
        assert not scheduled()                    # threshold 0: automatic collection off
    finally:
        O.HEAP = saved
