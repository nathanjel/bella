"""Mechanism 2 of the staging prototype: compiler intrinsics for a known user (docs/staging.md).

The compiler recognises `collections.namedtuple` calls whose fields are literals (scan.py) and
generates `__new__` itself, from its own copy of namedtuple's template. At runtime the eval in
`collections.namedtuple` is answered by field list, not by text. This file is that copy: the
field-name processing and the text of CPython 3.15.2's `collections/__init__.py` (lines 388 to
447), which the compiler would have to track for every CPython version it supports.

Nothing comparable is written for dataclasses: the text it generates comes from 267 lines of
helpers in 3.15.2's `dataclasses.py` (`_FuncBuilder`, `_field_assign`, `_field_init`,
`_init_param`, `_init_fn`, `_frozen_set_del_attr`, `_hash_add`) and the 249-line
`_process_class` that chooses among them, 516 of the module's 1,826 lines. docs/staging.md
compares the mechanisms without it.
"""
from __future__ import annotations

import keyword

from pipeline.staging.scan import NamedTupleCall

NAMEDTUPLE_SITE = "collections:namedtuple:447"


def namedtuple_fields(fields: str | tuple[str, ...], rename: bool) -> tuple[str, ...] | None:
    """The field names namedtuple ends up with, or None where it raises before generating code."""
    names = fields.replace(",", " ").split() if isinstance(fields, str) else [str(f) for f in fields]
    if rename:
        seen: set[str] = set()
        for index, name in enumerate(names):
            if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_") or name in seen:
                names[index] = f"_{index}"
            seen.add(name)
    seen = set()
    for name in names:
        if not name.isidentifier() or keyword.iskeyword(name) or (name.startswith("_") and not rename) or name in seen:
            return None
        seen.add(name)
    return tuple(names)


def namedtuple_new_text(fields: tuple[str, ...]) -> str:
    """The text namedtuple evaluates for `__new__` (3.15.2, `collections/__init__.py:446`)."""
    arg_list = ", ".join(fields)
    if len(fields) == 1:
        arg_list += ","
    return f"lambda _cls, {arg_list}: _tuple_new(_cls, ({arg_list}))"


def intrinsic_table(calls: list[NamedTupleCall]) -> dict[tuple[str, ...], str]:
    """Field list -> text of `__new__`, for every namedtuple the compiler can see statically."""
    table: dict[tuple[str, ...], str] = {}
    for call in calls:
        fields = namedtuple_fields(call.fields, call.rename)
        if fields is not None:
            table[fields] = namedtuple_new_text(fields)
    return table
