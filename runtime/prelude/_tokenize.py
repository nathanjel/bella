"""_tokenize, in Python (Python/Python-tokenize.c): the module tokenize imports while it loads, which linecache and traceback reach
through tokenize.open and detect_encoding. Its one class, TokenizerIter, is the C tokenizer: construction takes the clinic's
arguments as the C does (a readline, positional only; extra_tokens, required by keyword; encoding, a str), and iterating stops by
name until the tokenizer is ported (the tricky CLI target's business)."""

__all__ = ["TokenizerIter"]

__name__ = "_tokenize"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    _bella_new_instance = object.__new__

_ABSENT = object()


class TokenizerIter:
    __slots__ = ("_encoding", "_extra_tokens", "_readline")

    def __new__(cls, *args: object, **kwds: object) -> TokenizerIter:   # tokenizeriter_new: (readline, /, *, extra_tokens, encoding=None)
        if len(args) + len(kwds) > 3:
            raise TypeError("tokenizeriter() takes at most 3 arguments (" + str(len(args) + len(kwds)) + " given)")
        if len(args) != 1:
            raise TypeError("tokenizeriter() takes exactly 1 positional argument (" + str(len(args)) + " given)")
        extra_tokens = kwds.get("extra_tokens", _ABSENT)
        if extra_tokens is _ABSENT:
            raise TypeError("tokenizeriter() missing required argument 'extra_tokens' (pos 2)")
        for keyword in kwds:
            if keyword not in ("extra_tokens", "encoding"):
                raise TypeError("tokenizeriter() got an unexpected keyword argument '" + keyword + "'")
        encoding = kwds.get("encoding", _ABSENT)
        if encoding is not _ABSENT and not isinstance(encoding, str):
            raise TypeError("tokenizeriter() argument 'encoding' must be str, not " + ("None" if encoding is None else _tp_name(encoding)))
        self: TokenizerIter = _bella_new_instance(cls)
        self._readline = args[0]
        self._extra_tokens = bool(extra_tokens)
        self._encoding = None if encoding is _ABSENT else encoding
        return self

    def __iter__(self) -> TokenizerIter:
        return self

    def __next__(self) -> tuple[object, ...]:
        _bella_refuse("the C tokenizer (_tokenize.TokenizerIter): tokenize.generate_tokens and tokenize.tokenize over source text")
        raise AssertionError  # unreachable
