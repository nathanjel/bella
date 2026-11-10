"""_tokenize, in Python (Python/Python-tokenize.c): the module tokenize imports while it loads. Its one class, TokenizerIter, is
CPython's tokenizer: construction takes the clinic's arguments as the C does (a readline, positional only; extra_tokens, required
by keyword; encoding, a str), and each next() is the C's tokenizeriter_next over the lexer itself, which the runtime has as the
C's own text (runtime/src/tokenizer.cpp, one primitive: `_tokenizer(name, ...)`). The tokenizer's state is the runtime's, under
a handle that a small object frees when the iterator dies, as tokenizeriter_dealloc frees the C's."""

__all__ = ["TokenizerIter"]

__name__ = "_tokenize"

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _tokenizer                                   # noqa: B018  # the tokenizer: "new", "next", "free"
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _tokenizer: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    _bella_new_instance = object.__new__

    def _unpack_keywords(fname: str, names: tuple[str, ...], posonly: int, minpos: int, maxpos: int, minkw: int, args: tuple[object, ...],
                         kwds: dict[str, object], absent: object) -> list[object]:
        raise ImportError("this file needs the runtime's primitives")

_ABSENT = object()


class _State:                                    # the C's tok_state, by its handle: freed with the iterator that holds it
    __slots__ = ("_handle",)

    def __init__(self, handle: int) -> None:
        self._handle = handle

    def __del__(self) -> None:
        _tokenizer("free", self._handle)


class TokenizerIter:
    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> TokenizerIter:   # tokenizeriter_new: (readline, /, *, extra_tokens, encoding=None)
        readline, extra_tokens, encoding = _unpack_keywords("tokenizeriter", ("readline", "extra_tokens", "encoding"), 1, 1, 1, 1, args, kwds, _ABSENT)
        extra = bool(extra_tokens)                # the converters run in the parameters' order, after the parsing
        if encoding is _ABSENT:
            encoding = None
        else:
            if not isinstance(encoding, str):
                raise TypeError("tokenizeriter() argument 'encoding' must be str, not " + ("None" if encoding is None else _tp_name(encoding)))
            if "\0" in str.encode(encoding, "utf-8").decode("utf-8"):   # PyUnicode_AsUTF8AndSize, then the clinic's length check
                raise ValueError("embedded null character")
        self: TokenizerIter = _bella_new_instance(cls)
        self._state = _State(_tokenizer("new", readline, extra, encoding))
        return self

    def __iter__(self) -> TokenizerIter:
        return self

    def __next__(self) -> tuple[object, ...]:    # tokenizeriter_next
        result = _tokenizer("next", self._state._handle)
        if result is None:
            raise StopIteration("EOF")
        if result is False:                       # the C returned NULL and set nothing
            raise StopIteration
        return result  # type: ignore[no-any-return]
