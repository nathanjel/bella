"""Built-in functions written in Python (docs/DECISIONS.md, step 3 of the C++ leg).

Bella compiles this module into every program and puts the names in __all__ into the builtins.
CPython runs it in runtime/tests/test_prelude.py against the builtins it stands for, so each
function is checked against CPython directly, before Bella compiles it.
"""
import sys

__all__ = ["print", "property", "staticmethod", "classmethod"]
__intrinsics__ = ["_enter", "_leave"]            # Py_ReprEnter and Py_ReprLeave, for the built-in modules written in Python


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


class _IsAbstractMethod:
    """__isabstractmethod__ of property, staticmethod and classmethod: a read-only getset, true when
    one of the object's callables is abstract (_PyObject_IsAbstract)."""

    def __init__(self, owner: str, *callables: str) -> None:
        self._owner = owner
        self._callables = callables

    def __get__(self, obj: object, owner: object = None) -> object:
        if obj is None:
            return self
        for name in self._callables:
            if getattr(getattr(obj, name), "__isabstractmethod__", False):
                return True
        return False

    def __set__(self, obj: object, value: object) -> None:
        raise AttributeError("attribute '__isabstractmethod__' of '" + self._owner + "' objects is not writable")

    def __delete__(self, obj: object) -> None:
        raise AttributeError("attribute '__isabstractmethod__' of '" + self._owner + "' objects is not writable")


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

    __isabstractmethod__ = _IsAbstractMethod("property", "fget", "fset", "fdel")

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

    __isabstractmethod__ = _IsAbstractMethod("staticmethod", "__func__")

    def __init__(self, f: object) -> None:
        self.__func__ = f
        _wraps(self, f)

    def __get__(self, obj: object, owner: object = None) -> object:
        return self.__func__

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.__func__(*args, **kwargs)  # type: ignore[operator]


def _a_function() -> None:
    pass


_MethodType = type(_a_function.__get__(0))      # types.MethodType: any callable bound to an object


class classmethod:
    """Convert a function to be a class method."""

    __isabstractmethod__ = _IsAbstractMethod("classmethod", "__func__")

    def __init__(self, f: object) -> None:
        self.__func__ = f
        _wraps(self, f)

    def __get__(self, obj: object, owner: object = None) -> object:
        # cm_descr_get since 3.13: a method of the callable itself, which need not be a descriptor
        # (review 2026-11-03, A9-19)
        if owner is None:
            owner = type(obj)
        return _MethodType(self.__func__, owner)


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


def _receiver(self: object, cls: type, name: str) -> None:
    """A slot wrapper's check (wrapperdescr_call): list.__repr__(5) is a TypeError, as for the
    C++ types' methods (review 2026-11-03, A9-2)."""
    if not isinstance(self, cls):
        raise TypeError("descriptor '" + name + "' requires a '" + cls.__name__ + "' object but received a '" +
                        type(self).__name__ + "'")


def _list_repr(self: list[object]) -> str:
    _receiver(self, list, "__repr__")
    if not self:
        return "[]"
    if not _enter(self):
        return "[...]"
    try:
        return "[" + ", ".join([repr(x) for x in self]) + "]"
    finally:
        _leave(self)


def _tuple_repr(self: tuple[object, ...]) -> str:
    _receiver(self, tuple, "__repr__")
    items = list(tuple.__iter__(self))           # the items, whatever a subclass says
    if not items:
        return "()"
    if not _enter(self):
        return "(...)"
    try:
        if len(items) == 1:
            return "(" + repr(items[0]) + ",)"
        return "(" + ", ".join([repr(x) for x in items]) + ")"
    finally:
        _leave(self)


try:
    _dict_next                                   # noqa: B018  # PyDict_Next, given to this module by the compiled runtime
except NameError:
    def _dict_next(d: dict[object, object], i: int) -> tuple[int, object, object] | None:
        """Run by CPython (runtime/tests/test_prelude.py): the entries as they are at each step.
        CPython walks its entry array, deleted slots included; this walk sees no deleted slots."""
        items = list(d.items())
        return (i + 1, *items[i]) if i < len(items) else None


def _dict_repr(self: dict[object, object]) -> str:
    """dict_repr: the entries as PyDict_Next walks them, so an entry a key's or value's repr adds
    is shown too, with no check of the size (review 2026-11-03, A9-17)."""
    _receiver(self, dict, "__repr__")
    return _anydict_repr(self)


def _frozendict_repr(self: frozendict[object, object]) -> str:
    """frozendict_repr: the type's name around what a dict shows, or nothing when it is empty."""
    _receiver(self, frozendict, "__repr__")
    if _dict_next(self, 0) is None:
        return type(self).__name__ + "()"
    return type(self).__name__ + "(" + _anydict_repr(self) + ")"


def _anydict_repr(self: dict[object, object] | frozendict[object, object]) -> str:
    if _dict_next(self, 0) is None:              # ma_used == 0: never a subclass's __len__ or __bool__
        return "{}"
    if not _enter(self):
        return "{...}"
    try:
        parts: list[str] = []
        i = 0
        while True:
            entry = _dict_next(self, i)
            if entry is None:
                break
            i, k, v = entry
            parts.append(repr(k) + ": " + repr(v))
        return "{" + ", ".join(parts) + "}"
    finally:
        _leave(self)


def _set_repr(self: set[object]) -> str:
    _receiver(self, set, "__repr__")
    return _set_like_repr(self)


def _frozenset_repr(self: frozenset[object]) -> str:
    _receiver(self, frozenset, "__repr__")
    return _set_like_repr(self)


def _set_like_repr(self: set[object] | frozenset[object]) -> str:
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


_dict_keys = type({}.keys())
_dict_values = type({}.values())
_dict_items = type({}.items())


def _keys_repr(self: object) -> str:
    _receiver(self, _dict_keys, "__repr__")
    return _view_repr(self)


def _values_repr(self: object) -> str:
    _receiver(self, _dict_values, "__repr__")
    return _view_repr(self)


def _items_repr(self: object) -> str:
    _receiver(self, _dict_items, "__repr__")
    return _view_repr(self)


def _view_repr(self: object) -> str:
    """dictview_repr: the type's name around the repr of a list of the view."""
    if not _enter(self):
        return "..."
    try:
        return type(self).__name__ + "(" + repr(list(self)) + ")"  # type: ignore[call-overload]  # a view is iterable
    finally:
        _leave(self)


__type_methods__: dict[object, dict[str, object]] = {
    "list": {"__repr__": _list_repr}, "tuple": {"__repr__": _tuple_repr}, "dict": {"__repr__": _dict_repr},
    "frozendict": {"__repr__": _frozendict_repr},
    "set": {"__repr__": _set_repr}, "frozenset": {"__repr__": _frozenset_repr},
    _dict_keys: {"__repr__": _keys_repr}, _dict_values: {"__repr__": _values_repr}, _dict_items: {"__repr__": _items_repr}}
