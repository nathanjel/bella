# clause: C-8-11
# spec: section 8
# status: P1
# source: docs/staging.md section 4 (a compile stages its outcome: the code, or the exception with its arguments), typing._make_forward_ref
"""typing compiles each string forward reference eagerly, while the module body runs (annotationlib's
ForwardRef.__forward_code__ calls compile(text, "<string>", "eval")). The build stages that compile: the
program gets the code object CPython made, or the exception it raised. A code object's names and counts,
that the reference keeps the one it made, that two compiles of one text give equal code objects that are
not the same object (and of two texts, unequal ones), and the SyntaxError of a reference that is not an
expression, from which typing raises its own with the first as its context. Evaluating such a code object
is ForwardRef.evaluate of an expression, which C-3-23 keeps [P2+]."""
import annotationlib
import typing
from typing import List, Optional, TypeVar, Union  # noqa: UP035


class Node:
    pass


class Leaf:
    pass


T = TypeVar("T", bound="Node")
bound = T.__bound__
print(type(bound).__name__, bound.__forward_arg__, bound.__forward_module__)  # type: ignore[union-attr]
code = bound.__forward_code__  # type: ignore[union-attr]
print(type(code).__name__, code.co_name, code.co_qualname, code.co_filename, code.co_firstlineno)
print(code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_nlocals, code.co_varnames,
      code.co_cellvars, code.co_freevars, code.co_flags)
print(bound.__forward_code__ is code, bound.__code__ is code)  # type: ignore[union-attr]

maybe = Optional["Node"]  # noqa: UP045
items = List["Node"]  # noqa: UP006
either = Union["Leaf", int]  # noqa: UP007
first = typing.get_args(maybe)[0]
second = typing.get_args(items)[0]
third = typing.get_args(either)[0]
print(first, second, third, first == second, first is second)
print(first.__forward_code__ == second.__forward_code__, first.__forward_code__ is second.__forward_code__,
      first.__forward_code__ != second.__forward_code__, first.__forward_code__ == third.__forward_code__,
      first.__forward_code__ == code, third.__forward_code__.co_filename)

U = TypeVar("U", "Node", "list[Node]")
print(U.__constraints__)

try:
    TypeVar("V", bound="1 +")  # noqa: F722
except SyntaxError as e:
    inner = e.__context__
    print(type(e).__name__, e.lineno, e.offset, e.text, e.filename)
    print(type(inner).__name__, isinstance(inner, SyntaxError) and (inner.filename, inner.lineno, inner.offset,  # noqa: PLR2004
                                                                    inner.text, inner.end_lineno, inner.end_offset))
    print(e.__suppress_context__, e.__cause__)

lazy = annotationlib.ForwardRef("Node | None")
print(lazy.__code__, lazy.__forward_code__.co_name, lazy.__code__ is lazy.__forward_code__)  # type: ignore[attr-defined]
print(annotationlib.ForwardRef("Node").evaluate(globals={"Node": Node}) is Node)
