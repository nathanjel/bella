"""Built-in functions written in Python (docs/DECISIONS.md, step 3 of the C++ leg).

Bella compiles this module into every program and puts the names in __all__ into the builtins.
CPython runs it in runtime/tests/test_prelude.py against the builtins it stands for, so each
function is checked against CPython directly, before Bella compiles it.
"""
import sys

__all__ = ["print", "property", "staticmethod", "classmethod"]


def print(*args: object, sep: object = " ", end: object = "\n", file: object = None, flush: object = False) -> None:
    """print(*args, sep=' ', end='\\n', file=None, flush=False), in builtin_print_impl's order:
    the file first (nothing at all when sys.stdout is None), then sep and end, each str(), then
    flush."""
    if file is None:
        file = sys.stdout
        if file is None:
            return
    if sep is None:
        sep = " "
    elif not isinstance(sep, str):
        raise TypeError("sep must be None or a string, not " + type(sep).__name__)
    if end is None:
        end = "\n"
    elif not isinstance(end, str):
        raise TypeError("end must be None or a string, not " + type(end).__name__)
    first = True
    for arg in args:
        if not first:
            file.write(str(sep))  # type: ignore[attr-defined]  # any object with write()
        first = False
        file.write(str(arg))  # type: ignore[attr-defined]
    file.write(str(end))  # type: ignore[attr-defined]
    if flush:
        file.flush()  # type: ignore[attr-defined]


class property:
    """Property attribute.

  fget
    function to be used for getting an attribute value
  fset
    function to be used for setting an attribute value
  fdel
    function to be used for del'ing an attribute
  doc
    docstring

The descriptor of Objects/descrobject.c in Python: its messages, its name from __set_name__ or
the getter, and the getter's docstring taken over and given up as property_copy does.
"""

    def __init__(self, fget: object = None, fset: object = None, fdel: object = None, doc: object = None) -> None:
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self._getter_doc = False
        if doc is None and fget is not None:
            doc = getattr(fget, "__doc__", None)
            self._getter_doc = doc is not None
        self.__doc__ = doc
        self._name: object = None

    def __set_name__(self, owner: object, name: object) -> None:
        if self._name is None:
            self._name = name

    def _what(self, obj: object, missing: str) -> str:
        name = self._name if self._name is not None else getattr(self.fget, "__name__", None)
        named = "" if name is None else " " + repr(name)
        return "property" + named + " of " + repr(type(obj).__qualname__) + " object has no " + missing

    def __get__(self, obj: object, owner: object = None) -> object:
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError(self._what(obj, "getter"))
        return self.fget(obj)  # type: ignore[operator]  # a callable, as the caller gave it

    def __set__(self, obj: object, value: object) -> None:
        if self.fset is None:
            raise AttributeError(self._what(obj, "setter"))
        self.fset(obj, value)  # type: ignore[operator]

    def __delete__(self, obj: object) -> None:
        if self.fdel is None:
            raise AttributeError(self._what(obj, "deleter"))
        self.fdel(obj)  # type: ignore[operator]

    def _copy(self, fget: object, fset: object, fdel: object) -> object:
        doc = None if self._getter_doc and fget is not None else self.__doc__
        return type(self)(fget, fset, fdel, doc)

    def getter(self, fget: object) -> object:
        return self._copy(fget, self.fset, self.fdel)

    def setter(self, fset: object) -> object:
        return self._copy(self.fget, fset, self.fdel)

    def deleter(self, fdel: object) -> object:
        return self._copy(self.fget, self.fset, fdel)


def _wraps(wrapper: object, f: object) -> None:
    """What staticmethod and classmethod copy from the function since 3.10 (functools_wraps)."""
    for attr in ("__module__", "__name__", "__qualname__", "__doc__"):
        try:
            value = getattr(f, attr)
        except AttributeError:
            continue
        setattr(wrapper, attr, value)
    wrapper.__wrapped__ = f  # type: ignore[attr-defined]


class staticmethod:
    """Convert a function to be a static method."""

    def __init__(self, f: object) -> None:
        self.__func__ = f
        _wraps(self, f)

    def __get__(self, obj: object, owner: object = None) -> object:
        return self.__func__

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.__func__(*args, **kwargs)  # type: ignore[operator]


class classmethod:
    """Convert a function to be a class method."""

    def __init__(self, f: object) -> None:
        self.__func__ = f
        _wraps(self, f)

    def __get__(self, obj: object, owner: object = None) -> object:
        if owner is None:
            owner = type(obj)
        return self.__func__.__get__(owner, type(owner))  # type: ignore[attr-defined]  # a bound method


# ---- the containers' repr, installed as list.__repr__, tuple.__repr__ and dict.__repr__ ----

_running: list[object] = []      # the containers whose repr is being made (Py_ReprEnter)


def _enter(obj: object) -> bool:
    for x in _running:
        if x is obj:
            return False
    _running.append(obj)
    return True


def _leave(obj: object) -> None:
    i = len(_running) - 1
    while i >= 0:
        if _running[i] is obj:
            del _running[i]
            return
        i -= 1


def _list_repr(self: list[object]) -> str:
    if not self:
        return "[]"
    if not _enter(self):
        return "[...]"
    try:
        return "[" + ", ".join([repr(x) for x in self]) + "]"
    finally:
        _leave(self)


def _tuple_repr(self: tuple[object, ...]) -> str:
    if not self:
        return "()"
    if not _enter(self):
        return "(...)"
    try:
        if len(self) == 1:
            return "(" + repr(self[0]) + ",)"
        return "(" + ", ".join([repr(x) for x in self]) + ")"
    finally:
        _leave(self)


def _dict_repr(self: dict[object, object]) -> str:
    if not self:
        return "{}"
    if not _enter(self):
        return "{...}"
    try:
        return "{" + ", ".join([repr(k) + ": " + repr(v) for k, v in self.items()]) + "}"
    finally:
        _leave(self)


def _set_repr(self: set[object]) -> str:
    """set_repr: set() when empty; the type's name around the braces for a subclass and frozenset."""
    name = type(self).__name__
    if not self:
        return name + "()"
    if not _enter(self):
        return name + "(...)"
    try:
        inner = "{" + ", ".join([repr(x) for x in self]) + "}"
        return inner if type(self) is set else name + "(" + inner + ")"
    finally:
        _leave(self)


__type_methods__ = {"list": {"__repr__": _list_repr}, "tuple": {"__repr__": _tuple_repr}, "dict": {"__repr__": _dict_repr},
                    "set": {"__repr__": _set_repr}, "frozenset": {"__repr__": _set_repr}}
