"""Hypothesis stateful differential test: the reference model against CPython.

The same oracle as refmodel.selftest, with Hypothesis generating the operation sequence and
shrinking any failure to a minimal reproducer. Requires the dev extras (uv sync --extra dev).
"""
from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, settings, strategies as st  # noqa: E402
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule  # noqa: E402

from refmodel.oracle import NAMES, RUNTIME_VARIANTS, World  # noqa: E402

objects = st.integers(0, 9)
classes = st.integers(0, 6)
names = st.sampled_from(NAMES)
values = st.integers(0, 99)


class AttributeModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.world = World()
        assert len(self.world.objects) == 10 and len(self.world.classes) == 7

    @rule(obj=objects, name=names, computed=st.booleans())
    def get(self, obj: int, name: str, computed: bool) -> None:
        self.world.apply(("get", obj, name, computed))

    @rule(obj=objects, name=names, value=values)
    def set(self, obj: int, name: str, value: int) -> None:
        self.world.apply(("set", obj, name, value))

    @rule(obj=objects, name=names)
    def delete(self, obj: int, name: str) -> None:
        self.world.apply(("del", obj, name))

    @rule(obj=objects)
    def expose(self, obj: int) -> None:
        self.world.apply(("expose", obj))

    @rule(obj=objects, src=st.one_of(st.none(), objects))
    def replace_dict(self, obj: int, src: int | None) -> None:
        self.world.apply(("replace_dict", obj, src))

    @rule(cls=classes, name=names, value=values)
    def set_class_attr(self, cls: int, name: str, value: int) -> None:
        self.world.apply(("set_class_attr", cls, name, value))

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
