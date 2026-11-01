"""Deterministic cases from the review rounds, run against the reference model.

Each test states the CPython behaviour it encodes (verified by the corresponding conformance
case under conformance/cases) and checks that the model reproduces it. They run under pytest
or directly: python -m refmodel.tests.test_cases
"""
from __future__ import annotations

from refmodel.objects import UNSET, ModelError, RefClass, RefObject, Runtime, Site, make_descriptor_class


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
