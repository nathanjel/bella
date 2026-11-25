"""Hypothesis stateful differential test: the reference model against CPython.

The same oracle as refmodel.selftest, with Hypothesis generating the operation sequence and
shrinking any failure to a minimal reproducer. Requires the dev extras (uv sync --extra dev).
"""
from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, settings, strategies as st  # noqa: E402
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule  # noqa: E402

from refmodel.oracle import (  # noqa: E402
    BUFFER_SLOTS, FUNCTION_SLOTS, MODULE_SLOTS, NAMES, RUNTIME_CLASS, RUNTIME_OBJECTS, RUNTIME_VARIANTS, VIEW_SLOTS, World,
)

objects = st.integers(0, 11)
classes = st.integers(0, 8)
names = st.sampled_from(NAMES)
values = st.one_of(st.integers(0, 99), st.just("tagged"))      # "tagged": a fresh object whose death is compared
held = st.integers(0, RUNTIME_OBJECTS[0] - 1)                    # objects another may hold (recreate_class drops the rest)
ring_classes = st.lists(st.integers(0, 7).filter(lambda c: c != RUNTIME_CLASS), min_size=1, max_size=4)


class AttributeModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.world = World(cycles=True, buffers=True, modules=True)
        assert len(self.world.objects) == 12 and len(self.world.classes) == 9

    def teardown(self) -> None:
        self.world.close()

    @rule(obj=objects, name=names, computed=st.booleans())
    def get(self, obj: int, name: str, computed: bool) -> None:
        self.world.apply(("get", obj, name, computed))

    def _value(self, value: int | str) -> object:
        return self.world.new_tag() if value == "tagged" else value

    @rule(obj=objects, name=names, value=values)
    def set(self, obj: int, name: str, value: int | str) -> None:
        self.world.apply(("set", obj, name, self._value(value)))

    @rule(obj=objects, name=names, other=held)
    def link(self, obj: int, name: str, other: int) -> None:
        """One of the program's objects holds another: cycles."""
        self.world.apply(("set", obj, name, ("O", other)))

    @rule(classes=ring_classes, name=names, extra=names, weaks=st.lists(st.sampled_from((None, True, False)), min_size=4, max_size=4),
          reviver=st.one_of(st.none(), names), hold=st.one_of(st.none(), held))
    def ring(self, classes: list[int], name: str, extra: str, weaks: list[bool | None], reviver: str | None, hold: int | None) -> None:
        tags = tuple(self.world.new_tag() for _ in classes)
        self.world.apply(("ring", tuple(classes), name, extra, tags, tuple(weaks[:len(classes)]), reviver, hold))

    # ---- buffers: exporters and the views that hold them (refmodel/objects.py, "Buffers") ----
    @rule(slot=st.integers(0, BUFFER_SLOTS - 1), kind=st.sampled_from(("bytearray", "bytes")))
    def buffer_new(self, slot: int, kind: str) -> None:
        self.world.apply(("buffer_new", slot, kind, self.world.new_tag()))

    @rule(slot=st.integers(0, BUFFER_SLOTS - 1))
    def buffer_drop(self, slot: int) -> None:
        self.world.apply(("buffer_drop", slot))

    @rule(view=st.integers(0, VIEW_SLOTS - 1), slot=st.integers(0, BUFFER_SLOTS - 1))
    def view_new(self, view: int, slot: int) -> None:
        self.world.apply(("view_new", view, slot))

    @rule(view=st.integers(0, VIEW_SLOTS - 1), of=st.integers(0, VIEW_SLOTS - 1), sliced=st.booleans())
    def view_of(self, view: int, of: int, sliced: bool) -> None:
        self.world.apply(("view_of", view, of, sliced))

    @rule(view=st.integers(0, VIEW_SLOTS - 1))
    def view_release(self, view: int) -> None:
        self.world.apply(("view_release", view))

    @rule(view=st.integers(0, VIEW_SLOTS - 1))
    def view_drop(self, view: int) -> None:
        self.world.apply(("view_drop", view))

    @rule(slot=st.integers(0, BUFFER_SLOTS - 1))
    def resize(self, slot: int) -> None:
        self.world.apply(("resize", slot))

    # ---- modules and the functions made in them (refmodel/objects.py, "Modules, and what runs in them") ----
    @rule(slot=st.integers(0, MODULE_SLOTS - 1))
    def module_new(self, slot: int) -> None:
        self.world.apply(("module_new", slot, self.world.new_tag()))

    @rule(fn=st.integers(0, FUNCTION_SLOTS - 1), slot=st.integers(0, MODULE_SLOTS - 1), named=st.booleans())
    def module_def(self, fn: int, slot: int, named: bool) -> None:
        self.world.apply(("module_def", fn, slot, named))

    @rule(fn=st.integers(0, FUNCTION_SLOTS - 1), into=st.integers(0, FUNCTION_SLOTS - 1))
    def module_inner(self, fn: int, into: int) -> None:
        self.world.apply(("module_inner", fn, into))

    @rule(slot=st.integers(0, MODULE_SLOTS - 1), value=st.one_of(st.just("tagged"), st.tuples(st.just("M"), st.integers(0, MODULE_SLOTS - 1)),
                                                             st.tuples(st.just("O"), held)))
    def module_store(self, slot: int, value: object) -> None:
        self.world.apply(("module_store", slot, self.world.new_tag() if value == "tagged" else value))

    @rule(fn=st.integers(0, FUNCTION_SLOTS - 1))
    def module_read(self, fn: int) -> None:
        self.world.apply(("module_read", fn))

    @rule(slot=st.integers(0, MODULE_SLOTS - 1))
    def module_drop(self, slot: int) -> None:
        self.world.apply(("module_drop", slot))

    @rule(fn=st.integers(0, FUNCTION_SLOTS - 1))
    def function_drop(self, fn: int) -> None:
        self.world.apply(("function_drop", fn))

    @rule(slot=st.integers(0, MODULE_SLOTS - 1), put=st.booleans())
    def module_table(self, slot: int, put: bool) -> None:
        self.world.apply(("module_table", slot, put))

    @rule(slot=st.integers(0, MODULE_SLOTS - 1))
    def module_weak(self, slot: int) -> None:
        self.world.apply(("module_weak", slot))

    @rule(generation=st.integers(0, 2))
    def collect(self, generation: int) -> None:
        self.world.apply(("collect", generation))

    @rule()
    def release_kept(self) -> None:
        self.world.apply(("release_kept",))

    @rule(obj=objects)
    def drop(self, obj: int) -> None:
        self.world.apply(("drop", obj))

    @rule(obj=objects, times=st.integers(1, 35))
    def churn(self, obj: int, times: int) -> None:
        self.world.apply(("churn", obj, times))

    @rule(obj=objects, name=names)
    def delete(self, obj: int, name: str) -> None:
        self.world.apply(("del", obj, name))

    @rule(obj=objects)
    def expose(self, obj: int) -> None:
        self.world.apply(("expose", obj))

    @rule(obj=objects, src=st.one_of(st.none(), objects))
    def replace_dict(self, obj: int, src: int | None) -> None:
        self.world.apply(("replace_dict", obj, src))

    @rule(obj=objects, then=st.sampled_from(("none", "get", "set", "del", "expose")), name=names, value=values,
          probe=st.one_of(st.none(), st.tuples(names, names)))
    def del_dict(self, obj: int, then: str, name: str, value: int | str, probe: tuple[str, str] | None) -> None:
        tagged = None if probe is None else (probe[0], self.world.new_tag(), probe[1], self.world.new_tag())
        self.world.apply(("del_dict", obj, then, name, self._value(value) if then == "set" else 0, tagged))

    @rule(obj=objects, delete_first=st.booleans(), first=names, second=names)
    def probe(self, obj: int, delete_first: bool, first: str, second: str) -> None:
        tags = tuple(self.world.new_tag() for _ in range(4))
        self.world.apply(("probe", obj, delete_first, (first, second, *tags)))

    @rule(cls=classes, name=names, value=values)
    def set_class_attr(self, cls: int, name: str, value: int | str) -> None:
        self.world.apply(("set_class_attr", cls, name, self._value(value)))

    @rule(cls=classes, name=names)
    def del_class_attr(self, cls: int, name: str) -> None:
        self.world.apply(("del_class_attr", cls, name))

    @rule(cls=classes, name=names, data=st.booleans())
    def install_descriptor(self, cls: int, name: str, data: bool) -> None:
        self.world.apply(("install_descriptor", cls, name, data))

    @rule(idx=st.integers(0, 63))
    def promote_descriptor(self, idx: int) -> None:
        assume(self.world.descriptors)
        self.world.apply(("promote_descriptor", idx % len(self.world.descriptors)))

    @rule(idx=st.integers(0, 63))
    def demote_descriptor(self, idx: int) -> None:
        assume(self.world.descriptors)
        self.world.apply(("demote_descriptor", idx % len(self.world.descriptors)))

    @rule(variant=st.integers(0, RUNTIME_VARIANTS - 1))
    def recreate_class(self, variant: int) -> None:
        self.world.apply(("recreate_class", variant))

    @invariant()
    def model_agrees_with_cpython(self) -> None:
        self.world.sweep()


AttributeModel.TestCase.settings = settings(max_examples=300, stateful_step_count=80, deadline=None)
TestAttributeModel = AttributeModel.TestCase
