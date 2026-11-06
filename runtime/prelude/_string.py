"""_string, for string.Formatter: the markup and field name parsers of str.format, one step at a time.

The machines are the runtime's (runtime/src/format.cpp), the ones str.format itself runs; here they are iterators.
"""

__all__ = ["formatter_field_name_split", "formatter_parser"]

__name__ = "_string"

try:
    _markup_next                                 # noqa: B018  # formatteriter_next, from a position
    _field_split                                 # noqa: B018  # field_name_split, with no auto numbering
    _field_next                                  # noqa: B018  # fieldnameiter_next, from a position
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc: a type's __new__ makes its instance
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance: Callable[..., Any] = _missing
    _markup_next: Callable[..., Any] = _missing
    _field_split: Callable[..., Any] = _missing
    _field_next: Callable[..., Any] = _missing
    _tp_name: Callable[..., str] = _missing


class formatteriterator:
    __module__ = "builtins"
    __slots__ = ("_a_text", "_b_position")

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        step = _markup_next(self._a_text, self._b_position)
        if step is None:
            raise StopIteration
        self._b_position = step[0]
        return step[1]


class fieldnameiterator:
    __module__ = "builtins"
    __slots__ = ("_a_text", "_b_position")

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        step = _field_next(self._a_text, self._b_position)
        if step is None:
            raise StopIteration
        self._b_position = step[0]
        return step[1]


def _text_argument(args: tuple[object, ...], kwds: dict[str, object], name: str) -> str:
    if kwds:
        raise TypeError("_string." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_string." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    if not issubclass(type(args[0]), str):
        raise TypeError("expected str, got " + _tp_name(args[0]))
    return args[0]  # type: ignore[return-value]


def formatter_parser(*args: object, **kwds: object) -> object:
    it = _bella_new_instance(formatteriterator)
    it._a_text = _text_argument(args, kwds, "formatter_parser")
    it._b_position = 0
    return it


def formatter_field_name_split(*args: object, **kwds: object) -> object:
    text = _text_argument(args, kwds, "formatter_field_name_split")
    first, where = _field_split(text)
    it = _bella_new_instance(fieldnameiterator)
    it._a_text = text
    it._b_position = where
    return first, it
