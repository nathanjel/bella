"""Deterministic cases from the review rounds, run against the reference model.

Each test states the CPython behaviour it encodes (verified by the corresponding conformance
case under conformance/cases) and checks that the model reproduces it. They run under pytest
or directly: python -m refmodel.tests.test_cases
"""
from __future__ import annotations

import gc
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
            if stored is not None:
                rt.setattr(o, "x", stored)
            misses = site.misses
            assert rt.getattr(o, "x", site) == rt.getattr(o, "x", site) == (stored or "class attribute")
            assert site.misses == misses + 1, name
            ref = weakref.ref(K)
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

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
