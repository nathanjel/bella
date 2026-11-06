"""_functools, in Python, from Modules/_functoolsmodule.c; see itertools.py beside it.

Its types are named for `functools`, the module that shows them. `_bella_new_instance` makes a KeyWrapper, which has no
__new__ of its own to show; the cache's dict is asked by the hash the key already gave, as the C does, so that a key's
__hash__ runs once per call.
"""

__all__ = ["KeyWrapper", "Placeholder", "_PlaceholderType", "_lru_cache_wrapper", "cmp_to_key", "partial", "reduce"]

__name__ = "_functools"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _repr_enter                                  # noqa: B018  # Py_ReprEnter: false when it is in there already
    _repr_leave                                  # noqa: B018  # Py_ReprLeave
    _bella_new_instance                          # noqa: B018  # an instance of a type with no __new__ of its own
    _has_dict                                    # noqa: B018  # the C's self->dict is not NULL
    _method_new                                  # noqa: B018  # PyMethod_New
    _hash_of                                     # noqa: B018  # PyObject_Hash
    _get_hashed                                  # noqa: B018  # _PyDict_GetItemRef_KnownHash; a default when absent
    _set_hashed                                  # noqa: B018  # _PyDict_SetItem_KnownHash
    _pop_hashed                                  # noqa: B018  # _PyDict_Pop_KnownHash; a default when absent
    _is_callable                                 # noqa: B018  # PyCallable_Check
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _repr_enter: Callable[..., bool] = _missing
    _repr_leave: Callable[..., None] = _missing
    _bella_new_instance: Callable[..., Any] = _missing
    _has_dict: Callable[..., bool] = _missing
    _method_new: Callable[..., Any] = _missing
    _hash_of: Callable[..., int] = _missing
    _get_hashed: Callable[..., Any] = _missing
    _set_hashed: Callable[..., None] = _missing
    _pop_hashed: Callable[..., Any] = _missing
    _is_callable: Callable[..., bool] = _missing

_SSIZE_MAX = 2**63 - 1
_set = object.__setattr__
_ABSENT = object()


def _new_receiver(args: tuple[object, ...], owner: type, shown: str) -> None:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(shown + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(shown + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(shown + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + shown)  # type: ignore[attr-defined]


def _receiver(args: tuple[object, ...], cls: type, name: str, shown: str) -> None:   # a method descriptor's
    if not args:
        raise TypeError("unbound method " + shown + "." + name + "() needs an argument")
    if not issubclass(type(args[0]), cls):
        raise TypeError("descriptor '" + name + "' for '" + cls.__module__ + "." + cls.__name__ + "' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")


def _noargs(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, shown: str) -> None:   # METH_NOARGS
    _receiver(args, cls, name, shown)
    if kwds:
        raise TypeError(shown + "." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(shown + "." + name + "() takes no arguments (" + str(len(args) - 1) + " given)")


def _one(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, shown: str) -> object:   # METH_O
    _receiver(args, cls, name, shown)
    if kwds:
        raise TypeError(shown + "." + name + "() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError(shown + "." + name + "() takes exactly one argument (" + str(len(args) - 1) + " given)")
    return args[1]


def _wrapper(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, count: int) -> None:   # wrapper_call
    if not args:
        raise TypeError("descriptor '" + name + "' of '" + cls.__module__ + "." + cls.__name__ + "' object needs an argument")
    if not issubclass(type(args[0]), cls):
        raise TypeError("descriptor '" + name + "' requires a '" + cls.__module__ + "." + cls.__name__ + "' object but received a '" + _tp_name(args[0]) + "'")
    if kwds:
        raise TypeError("wrapper " + name + "() takes no keyword arguments")
    if len(args) != count + 1:
        raise TypeError("expected " + str(count) + " argument" + ("" if count == 1 else "s") + ", got " + str(len(args) - 1))


# ---- Placeholder

class _PlaceholderType:
    """The type of the Placeholder singleton.

Used as a placeholder for partial arguments."""

    __module__ = "functools"
    __slots__ = ()

    def __new__(*args: object, **kwds: object) -> _PlaceholderType:
        _new_receiver(args, _PlaceholderType, "functools._PlaceholderType")
        if len(args) > 1 or kwds:
            raise TypeError("PlaceholderType takes no arguments")
        if _the_placeholder is not None:
            return _the_placeholder
        return _bella_new_instance(args[0])  # type: ignore[arg-type]

    def __repr__(*args: object, **kwds: object) -> str:
        _wrapper(args, kwds, _PlaceholderType, "__repr__", 0)
        return "Placeholder"

    def __reduce__(*args: object, **kwds: object) -> str:
        _noargs(args, kwds, _PlaceholderType, "__reduce__", "_PlaceholderType")
        return "Placeholder"


_the_placeholder: _PlaceholderType | None = None
Placeholder = _PlaceholderType()
_the_placeholder = Placeholder


# ---- partial

class partial:
    """Create a new function with partial application of the given arguments
and keywords."""

    __module__ = "functools"
    __slots__ = ("func", "args", "keywords", "_p_phcount", "__dict__", "__weakref__")

    def __new__(*args: object, **kwds: object) -> partial:   # partial_new
        _new_receiver(args, partial, "functools.partial")
        cls = args[0]
        rest = args[1:]
        if not rest:
            raise TypeError("type 'partial' takes at least one argument")
        func = rest[0]
        if not _is_callable(func):
            raise TypeError("the first argument must be callable")
        new_args = rest[1:]
        new_nargs = len(new_args)
        if new_nargs and new_args[-1] is Placeholder:
            raise TypeError("trailing Placeholders are not allowed")
        for value in kwds.values():
            if value is Placeholder:
                raise TypeError("Placeholder cannot be passed as a keyword argument")
        pto_args: tuple[object, ...] | None = None
        pto_kw: dict[str, object] | None = None
        pto_phcount = 0
        if issubclass(type(func), partial) and not _has_dict(func):
            pto_args = func.args  # type: ignore[attr-defined]
            pto_kw = func.keywords  # type: ignore[attr-defined]
            pto_phcount = func._p_phcount  # type: ignore[attr-defined]
            func = func.func  # type: ignore[attr-defined]
        self = _bella_new_instance(cls)  # type: ignore[arg-type]
        _set(self, "func", func)
        phcount = 0
        for i in range(new_nargs - 1):
            if new_args[i] is Placeholder:
                phcount += 1
        merged: tuple[object, ...]
        if pto_phcount > 0 and new_nargs > 0:
            assert pto_args is not None
            npargs = len(pto_args)
            total = npargs
            if new_nargs > pto_phcount:
                total += new_nargs - pto_phcount
            items = []
            j = 0
            for i in range(total):
                if i < npargs:
                    item = pto_args[i]
                    if j < new_nargs and item is Placeholder:
                        item = new_args[j]
                        j += 1
                        pto_phcount -= 1
                else:
                    item = new_args[j]
                    j += 1
                items.append(item)
            merged = tuple(items)
            count = pto_phcount + phcount
        elif pto_args is None:
            merged = new_args
            count = phcount
        else:
            merged = pto_args + new_args
            count = pto_phcount + phcount
        _set(self, "args", merged)
        _set(self, "_p_phcount", count)
        if pto_kw is None or not pto_kw:
            _set(self, "keywords", kwds)
        else:
            keywords = dict(pto_kw)
            keywords.update(kwds)
            _set(self, "keywords", keywords)
        return self

    def __setattr__(*args: object, **kwds: object) -> None:
        _wrapper(args, kwds, partial, "__setattr__", 2)
        self, name, value = args
        if name in ("func", "args", "keywords"):
            raise AttributeError("readonly attribute")
        if name == "_p_phcount":
            raise AttributeError("'" + _tp_name(self) + "' object has no attribute '_p_phcount'")
        _set(self, name, value)  # type: ignore[arg-type]

    def __delattr__(*args: object, **kwds: object) -> None:
        _wrapper(args, kwds, partial, "__delattr__", 1)
        self, name = args
        if name in ("func", "args", "keywords"):
            raise AttributeError("readonly attribute")
        if name == "_p_phcount":
            raise AttributeError("'" + _tp_name(self) + "' object has no attribute '_p_phcount'")
        object.__delattr__(self, name)  # type: ignore[arg-type]

    def __call__(*args: object, **kwds: object) -> object:      # partial_call
        if not args:
            raise TypeError("descriptor '__call__' of 'functools.partial' object needs an argument")
        self = args[0]
        if not issubclass(type(self), partial):
            raise TypeError("descriptor '__call__' requires a 'functools.partial' object but received a '" + _tp_name(self) + "'")
        given = args[1:]
        count = self._p_phcount  # type: ignore[attr-defined]
        if len(given) < count:
            raise TypeError("missing positional arguments in 'partial' call; expected at least " + str(count) + ", got " + str(len(given)))
        keywords = self.keywords  # type: ignore[attr-defined]
        if keywords:
            total = dict(keywords)
            total.update(kwds)
        else:
            total = kwds
        pto_args = self.args  # type: ignore[attr-defined]
        if count:
            items = []
            j = 0
            for item in pto_args:
                if item is Placeholder:
                    item = given[j]
                    j += 1
                items.append(item)
            while j < len(given):
                items.append(given[j])
                j += 1
            return self.func(*items, **total)  # type: ignore[attr-defined]
        return self.func(*pto_args, *given, **total)  # type: ignore[attr-defined]

    def __get__(*args: object, **kwds: object) -> object:       # partial_descr_get, by wrap_descr_get
        if not args:
            raise TypeError("descriptor '__get__' of 'functools.partial' object needs an argument")
        self = args[0]
        if kwds:
            raise TypeError("wrapper __get__() takes no keyword arguments")
        if len(args) < 2 or len(args) > 3:
            raise TypeError("__get__ expected at least 1 argument, got 0" if len(args) < 2 else "__get__ expected at most 2 arguments, got " + str(len(args) - 1))
        obj = args[1]
        if obj is None and (len(args) < 3 or args[2] is None):
            raise TypeError("__get__(None, None) is invalid")
        if obj is None:
            return self
        return _method_new(self, obj)

    def __repr__(*args: object, **kwds: object) -> str:         # partial_repr
        _wrapper(args, kwds, partial, "__repr__", 0)
        self = args[0]
        if not _repr_enter(self):
            return "..."
        try:
            fn = self.func  # type: ignore[attr-defined]
            arglist = ""
            for item in self.args:  # type: ignore[attr-defined]
                arglist = arglist + ", " + repr(item)
            for key, value in self.keywords.items():  # type: ignore[attr-defined]
                arglist = arglist + ", " + str(key) + "=" + repr(value)
            cls = type(self)
            return str(cls.__module__) + "." + str(cls.__qualname__) + "(" + repr(fn) + arglist + ")"
        finally:
            _repr_leave(self)

    def __reduce__(*args: object, **kwds: object) -> tuple[object, ...]:
        _noargs(args, kwds, partial, "__reduce__", "partial")
        self = args[0]
        return (type(self), (self.func,), (self.func, self.args, self.keywords, self.__dict__ if _has_dict(self) else None))  # type: ignore[attr-defined]

    def __setstate__(*args: object, **kwds: object) -> None:    # partial_setstate
        state = _one(args, kwds, partial, "__setstate__", "partial")
        self = args[0]
        if not issubclass(type(state), tuple) or len(state) != 4:  # type: ignore[arg-type]
            raise TypeError("invalid partial state")
        fn, fnargs, kw, dict_ = state  # type: ignore[misc]
        if not _is_callable(fn) or not issubclass(type(fnargs), tuple) or (kw is not None and not issubclass(type(kw), dict)) or (dict_ is not None and not issubclass(type(dict_), dict)):
            raise TypeError("invalid partial state")
        nargs = len(fnargs)
        if nargs and tuple.__getitem__(fnargs, nargs - 1) is Placeholder:
            raise TypeError("trailing Placeholders are not allowed")
        phcount = 0
        for i in range(nargs - 1):
            if tuple.__getitem__(fnargs, i) is Placeholder:
                phcount += 1
        if type(fnargs) is not tuple:
            fnargs = tuple(fnargs)
        if kw is None:
            kw = {}
        elif type(kw) is not dict:
            kw = dict(kw)
        _set(self, "func", fn)
        _set(self, "args", fnargs)
        _set(self, "keywords", kw)
        _set(self, "_p_phcount", phcount)
        if dict_ is None:
            if _has_dict(self):                  # the old one goes, as it is; whoever holds it keeps it
                object.__delattr__(self, "__dict__")
        else:
            _set(self, "__dict__", dict_)


# ---- cmp_to_key

class KeyWrapper:
    __module__ = "functools"
    __slots__ = ("_k_cmp", "_k_obj")
    __hash__ = None  # type: ignore[assignment]
    __text_signature__ = "(obj)"

    def __call__(*args: object, **kwds: object) -> KeyWrapper:    # keyobject_call: "O:K"
        if not args:
            raise TypeError("descriptor '__call__' of 'functools.KeyWrapper' object needs an argument")
        self = args[0]
        if not issubclass(type(self), KeyWrapper):
            raise TypeError("descriptor '__call__' requires a 'functools.KeyWrapper' object but received a '" + _tp_name(self) + "'")
        given = args[1:]
        if len(given) + len(kwds) > 1:
            raise TypeError("K() takes at most 1 argument (" + str(len(given) + len(kwds)) + " given)")
        if given:
            obj = given[0]
        elif "obj" in kwds:
            obj = kwds["obj"]
        elif kwds:
            for key in kwds:
                raise TypeError("K() got an unexpected keyword argument '" + key + "'")
        else:
            raise TypeError("K() missing required argument 'obj' (pos 1)")
        made = _bella_new_instance(type(self))
        _set(made, "_k_cmp", self._k_cmp)  # type: ignore[attr-defined]
        _set(made, "_k_obj", obj)
        return made

    def __lt__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__lt__", 1)
        return _key_call(args[0], args[1]) < 0  # type: ignore[operator]

    def __le__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__le__", 1)
        return _key_call(args[0], args[1]) <= 0  # type: ignore[operator]

    def __eq__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__eq__", 1)
        return _key_call(args[0], args[1]) == 0

    def __ne__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__ne__", 1)
        return _key_call(args[0], args[1]) != 0

    def __gt__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__gt__", 1)
        return _key_call(args[0], args[1]) > 0  # type: ignore[operator]

    def __ge__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, KeyWrapper, "__ge__", 1)
        return _key_call(args[0], args[1]) >= 0  # type: ignore[operator]


def _key_call(lhs: object, other: object) -> object:   # keyobject_richcompare
    if type(other) is not type(lhs):
        raise TypeError("other argument must be K instance")
    try:
        x = lhs._k_obj  # type: ignore[attr-defined]
        y = other._k_obj  # type: ignore[attr-defined]
    except AttributeError:
        raise AttributeError("object") from None
    return lhs._k_cmp(x, y)  # type: ignore[attr-defined]


def cmp_to_key(*args: object, **kwds: object) -> KeyWrapper:
    """Convert a cmp= function into a key= function.

  mycmp
    Function that compares two objects."""
    if len(args) + len(kwds) > 1:
        raise TypeError("cmp_to_key() takes at most 1 argument (" + str(len(args) + len(kwds)) + " given)")
    if args:
        mycmp = args[0]
    elif "mycmp" in kwds:
        mycmp = kwds["mycmp"]
    elif kwds:
        for key in kwds:
            raise TypeError("cmp_to_key() got an unexpected keyword argument '" + key + "'")
    else:
        raise TypeError("cmp_to_key() missing required argument 'mycmp' (pos 1)")
    made = _bella_new_instance(KeyWrapper)
    _set(made, "_k_cmp", mycmp)
    return made


# ---- reduce

def reduce(*args: object, **kwds: object) -> object:
    """Apply a function of two arguments cumulatively to the items of an iterable, from left to right.

This effectively reduces the iterable to a single value.  If initial is
present, it is placed before the items of the iterable in the
calculation, and serves as a default when the iterable is empty.

For example, reduce(lambda x, y: x+y, [1, 2, 3, 4, 5])
calculates ((((1 + 2) + 3) + 4) + 5)."""
    if len(args) + len(kwds) > 3:
        raise TypeError("reduce() takes at most 3 arguments (" + str(len(args) + len(kwds)) + " given)")
    if len(args) < 2:
        raise TypeError("reduce() takes at least 2 positional arguments (" + str(len(args)) + " given)")
    for key in kwds:
        if key != "initial":
            raise TypeError("reduce() got an unexpected keyword argument '" + key + "'")
    if len(args) > 2 and kwds:
        raise TypeError("argument for reduce() given by name ('initial') and position (3)")
    func, seq = args[0], args[1]
    result = args[2] if len(args) > 2 else kwds.get("initial", _ABSENT)
    try:
        it = iter(seq)  # type: ignore[call-overload]
    except TypeError:
        raise TypeError("reduce() arg 2 must support iteration") from None
    for op2 in it:
        if result is _ABSENT:
            result = op2
        else:
            result = func(result, op2)  # type: ignore[operator]
    if result is _ABSENT:
        raise TypeError("reduce() of empty iterable with no initial value")
    return result


# ---- the lru cache

class _Link:
    __slots__ = ("prev", "next", "hash", "key", "result")


_kwd_mark = object()


def _make_key(args: tuple[object, ...], kwds: dict[str, object], typed: bool) -> object:   # lru_cache_make_key
    if not typed and not kwds:
        if len(args) == 1:
            key = args[0]
            if type(key) is str or type(key) is int:
                return key
        return args
    items = list(args)
    if kwds:
        items.append(_kwd_mark)
        for keyword, value in kwds.items():
            items.append(keyword)
            items.append(value)
    if typed:
        for item in args:
            items.append(type(item))
        for value in kwds.values():
            items.append(type(value))
    return tuple(items)


class _lru_cache_wrapper:
    """Create a cached callable that wraps another function.

user_function:      the function being cached

maxsize:  0         for no caching
          None      for unlimited cache size
          n         for a bounded cache

typed:    False     cache f(3) and f(3.0) as identical calls
          True      cache f(3) and f(3.0) as distinct calls

cache_info_type:    namedtuple class with the fields:
                        hits misses currsize maxsize
"""

    __module__ = "functools"
    __slots__ = ("_l_func", "_l_maxsize", "_l_typed", "_l_cache", "_l_hits", "_l_misses", "_l_info", "_l_kind", "_l_root", "__dict__", "__weakref__")

    def __new__(*args: object, **kwds: object) -> _lru_cache_wrapper:   # lru_cache_new: "OOpO:lru_cache"
        _new_receiver(args, _lru_cache_wrapper, "functools._lru_cache_wrapper")
        cls = args[0]
        given = list(args[1:])
        names = ("user_function", "maxsize", "typed", "cache_info_type")
        if len(given) + len(kwds) > 4:
            raise TypeError("lru_cache() takes at most 4 arguments (" + str(len(given) + len(kwds)) + " given)")
        for i in range(len(given), 4):
            if names[i] in kwds:
                given.append(kwds[names[i]])
            else:
                raise TypeError("lru_cache() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        for key in kwds:
            if key not in names:
                raise TypeError("lru_cache() got an unexpected keyword argument '" + key + "'")
            if names.index(key) < len(args) - 1:
                raise TypeError("argument for lru_cache() given by name ('" + key + "') and position (" + str(names.index(key) + 1) + ")")
        func, maxsize_o, typed, info = given
        typed = bool(typed)
        if not _is_callable(func):
            raise TypeError("the first argument must be callable")
        if maxsize_o is None:
            kind = "infinite"
            maxsize = -1
        elif hasattr(type(maxsize_o), "__index__"):
            maxsize = _number_index(maxsize_o)
            if maxsize > _SSIZE_MAX or maxsize < -_SSIZE_MAX - 1:
                raise OverflowError("cannot fit '" + _tp_name(maxsize_o) + "' into an index-sized integer")
            if maxsize < 0:
                maxsize = 0
            kind = "uncached" if maxsize == 0 else "bounded"
        else:
            raise TypeError("maxsize should be integer or None")
        self = _bella_new_instance(cls)  # type: ignore[arg-type]
        root = _Link()
        root.prev = root
        root.next = root
        _set(self, "_l_root", root)
        _set(self, "_l_kind", kind)
        _set(self, "_l_typed", typed)
        _set(self, "_l_cache", {})
        _set(self, "_l_func", func)
        _set(self, "_l_hits", 0)
        _set(self, "_l_misses", 0)
        _set(self, "_l_maxsize", maxsize)
        _set(self, "_l_info", info)
        return self

    def __call__(*args: object, **kwds: object) -> object:      # lru_cache_call
        if not args:
            raise TypeError("descriptor '__call__' of 'functools._lru_cache_wrapper' object needs an argument")
        self = args[0]
        if not issubclass(type(self), _lru_cache_wrapper):
            raise TypeError("descriptor '__call__' requires a 'functools._lru_cache_wrapper' object but received a '" + _tp_name(self) + "'")
        kind = self._l_kind  # type: ignore[attr-defined]
        given = args[1:]
        if kind == "uncached":
            _set(self, "_l_misses", self._l_misses + 1)  # type: ignore[attr-defined]
            return self._l_func(*given, **kwds)  # type: ignore[attr-defined]
        key = _make_key(given, kwds, self._l_typed)  # type: ignore[attr-defined]
        h = _hash_of(key)
        cache = self._l_cache  # type: ignore[attr-defined]
        found = _get_hashed(cache, key, h, _ABSENT)
        if kind == "infinite":
            if found is not _ABSENT:
                _set(self, "_l_hits", self._l_hits + 1)  # type: ignore[attr-defined]
                return found
            _set(self, "_l_misses", self._l_misses + 1)  # type: ignore[attr-defined]
            result = self._l_func(*given, **kwds)  # type: ignore[attr-defined]
            _set_hashed(cache, key, h, result)
            return result
        if found is not _ABSENT:                 # bounded_lru_cache_get
            _extract(found)
            _append(self, found)
            _set(self, "_l_hits", self._l_hits + 1)  # type: ignore[attr-defined]
            return found.result
        _set(self, "_l_misses", self._l_misses + 1)  # type: ignore[attr-defined]
        result = self._l_func(*given, **kwds)  # type: ignore[attr-defined]
        return _bounded_update(self, result, key, h, cache)

    def __get__(*args: object, **kwds: object) -> object:       # lru_cache_descr_get, by wrap_descr_get
        if not args:
            raise TypeError("descriptor '__get__' of 'functools._lru_cache_wrapper' object needs an argument")
        self = args[0]
        if kwds:
            raise TypeError("wrapper __get__() takes no keyword arguments")
        if len(args) < 2 or len(args) > 3:
            raise TypeError("__get__ expected at least 1 argument, got 0" if len(args) < 2 else "__get__ expected at most 2 arguments, got " + str(len(args) - 1))
        obj = args[1]
        if obj is None and (len(args) < 3 or args[2] is None):
            raise TypeError("__get__(None, None) is invalid")
        if obj is None:
            return self
        return _method_new(self, obj)

    def cache_info(*args: object, **kwds: object) -> object:
        """Report cache statistics"""
        _noargs(args, kwds, _lru_cache_wrapper, "cache_info", "_lru_cache_wrapper")
        self = args[0]
        maxsize = self._l_maxsize  # type: ignore[attr-defined]
        return self._l_info(self._l_hits, self._l_misses, None if maxsize == -1 else maxsize, len(self._l_cache))  # type: ignore[attr-defined]

    def cache_clear(*args: object, **kwds: object) -> None:
        """Clear the cache and cache statistics"""
        _noargs(args, kwds, _lru_cache_wrapper, "cache_clear", "_lru_cache_wrapper")
        self = args[0]
        root = self._l_root  # type: ignore[attr-defined]
        link = root.next
        root.prev = root
        root.next = root
        _set(self, "_l_hits", 0)
        _set(self, "_l_misses", 0)
        self._l_cache.clear()  # type: ignore[attr-defined]
        while link is not root:                  # lru_cache_clear_list
            following = link.next
            link.prev = None
            link.next = None
            link = following

    def __reduce__(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, _lru_cache_wrapper, "__reduce__", "_lru_cache_wrapper")
        return args[0].__qualname__  # type: ignore[attr-defined]

    def __copy__(*args: object, **kwds: object) -> object:      # METH_VARARGS: any arguments, unread
        _receiver(args, _lru_cache_wrapper, "__copy__", "_lru_cache_wrapper")
        if kwds:
            raise TypeError("_lru_cache_wrapper.__copy__() takes no keyword arguments")
        return args[0]

    def __deepcopy__(*args: object, **kwds: object) -> object:  # METH_VARARGS
        _receiver(args, _lru_cache_wrapper, "__deepcopy__", "_lru_cache_wrapper")
        if kwds:
            raise TypeError("_lru_cache_wrapper.__deepcopy__() takes no keyword arguments")
        return args[0]


def _extract(link: _Link) -> None:               # lru_cache_extract_link
    link.prev.next = link.next
    link.next.prev = link.prev


def _append(self: object, link: _Link) -> None:  # lru_cache_append_link
    root = self._l_root  # type: ignore[attr-defined]
    last = root.prev
    last.next = link
    root.prev = link
    link.prev = last
    link.next = root


def _bounded_update(self: object, result: object, key: object, h: int, cache: dict[object, object]) -> object:   # bounded_lru_cache_update
    if _get_hashed(cache, key, h, _ABSENT) is not _ABSENT:   # the function added the key, reentrantly: the link is up to date
        return result
    root = self._l_root  # type: ignore[attr-defined]
    if len(cache) < self._l_maxsize or root.next is root:  # type: ignore[attr-defined]
        link = _Link()
        link.hash = h
        link.key = key
        link.result = result
        _set_hashed(cache, key, h, link)
        _append(self, link)
        return result
    link = root.next                             # the oldest link goes, and is used again
    _extract(link)
    try:
        popped = _pop_hashed(cache, link.key, link.hash, _ABSENT)
    except BaseException:
        link.prev = root                         # lru_cache_prepend_link: back as the oldest
        link.next = root.next
        root.next.prev = link
        root.next = link
        raise
    if popped is _ABSENT:                        # gone already: an orphan
        return result
    oldkey = link.key
    oldresult = link.result
    link.hash = h
    link.key = key
    link.result = result
    _set_hashed(cache, key, h, link)
    _append(self, link)
    del popped, oldkey, oldresult
    return result
