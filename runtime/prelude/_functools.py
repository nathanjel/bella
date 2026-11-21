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
    _bella_state_set                             # noqa: B018  # a C function's store into its struct's field (RL-507)
    _has_dict                                    # noqa: B018  # the C's self->dict is not NULL
    _drop_dict                                   # noqa: B018  # the C's Py_CLEAR(self->dict)
    _method_new                                  # noqa: B018  # PyMethod_New
    _hash_of                                     # noqa: B018  # PyObject_Hash
    _get_hashed                                  # noqa: B018  # _PyDict_GetItemRef_KnownHash; a default when absent
    _set_hashed                                  # noqa: B018  # _PyDict_SetItem_KnownHash
    _pop_hashed                                  # noqa: B018  # _PyDict_Pop_KnownHash; a default when absent
    _is_callable                                 # noqa: B018  # PyCallable_Check
    _has_slot                                    # noqa: B018  # a slot of the type, by its own MRO and dicts: the runtime's (RL-644)
    _own_data                                    # noqa: B018  # an argument's own data as the exact base object: the runtime's (RL-698)
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
    _bella_state_set = object.__setattr__
    _has_dict: Callable[..., bool] = _missing
    _drop_dict: Callable[..., None] = _missing
    _method_new: Callable[..., Any] = _missing
    _hash_of: Callable[..., int] = _missing
    _get_hashed: Callable[..., Any] = _missing
    _set_hashed: Callable[..., None] = _missing
    _pop_hashed: Callable[..., Any] = _missing
    _is_callable: Callable[..., bool] = _missing
    _has_slot: Callable[..., bool] = _missing
    _own_data: Callable[..., Any] = _missing

_SSIZE_MAX = 2**63 - 1
_set = _bella_state_set                          # a C function's store into its struct: no class's __setattr__ is asked
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
    __readonly__ = ("func", "args", "keywords")  # partial_memberlist's Py_READONLY (runtime/src/call.cpp, note_prelude_class)

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

    def __setattr__(*args: object, **kwds: object) -> None:      # tp_setattro is PyObject_GenericSetAttr: the members say
        _wrapper(args, kwds, partial, "__setattr__", 2)           # themselves that they are read-only
        self, name, value = args
        object.__setattr__(self, name, value)  # type: ignore[arg-type]

    def __delattr__(*args: object, **kwds: object) -> None:
        _wrapper(args, kwds, partial, "__delattr__", 1)
        self, name = args
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
        if not issubclass(type(state), tuple) or tuple.__len__(state) != 4:  # type: ignore[arg-type]
            raise TypeError("invalid partial state")
        fn, fnargs, kw, dict_ = _own_data(state)   # PyArg_ParseTuple: the tuple's four slots, whatever its class has (RL-685)
        if not _is_callable(fn) or not issubclass(type(fnargs), tuple) or (kw is not None and not issubclass(type(kw), dict)) or (dict_ is not None and not issubclass(type(dict_), dict)):
            raise TypeError("invalid partial state")
        nargs = tuple.__len__(fnargs)            # PyTuple_GET_SIZE
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
                _drop_dict(self)
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
    unset = False                                # the C sets its error over the pending one: raised outside the handler, so that no __context__ of that one shows
    try:
        x = lhs._k_obj  # type: ignore[attr-defined]
        y = other._k_obj  # type: ignore[attr-defined]
    except AttributeError:
        unset = True
    if unset:
        raise AttributeError("object")
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
    it = None                                    # the C sets its error over the pending one: raised outside the handler, so that no __context__ of that one shows
    try:
        it = iter(seq)  # type: ignore[call-overload]
    except TypeError:
        pass
    if it is None:
        raise TypeError("reduce() arg 2 must support iteration")
    for op2 in it:
        if result is _ABSENT:
            result = op2
        else:
            result = func(result, op2)  # type: ignore[operator]
    if result is _ABSENT:
        raise TypeError("reduce() of empty iterable with no initial value")
    return result


# ---- the lru cache
#
# The C keeps a bounded cache's links in a ring through a root that is part of the wrapper. A link's prev and next are borrowed
# pointers: the cache dict owns one reference to each link, the ring the one the link was made with, and the wrapper's end and
# cache_clear take the ring apart and let the links go oldest first (lru_cache_unlink_list, lru_cache_clear_list). Links that
# held each other here would hold themselves for good, and their keys and results with them (RL-600). So a link has an id,
# its prev and next are ids (None at an end), and the wrapper's last field, `_l_links`, is [nodes, first, last, next id].
# `nodes` has each link of the ring under its id and in the ring's order, oldest first: a link that moves to the end is taken
# out of the dict and put in again. That dict is the ring's reference to each link, and its end or its clear() lets them go
# in the ring's order.

class _Link:
    __slots__ = ("id", "prev", "next", "hash", "key", "result")     # lru_list_elem_dealloc: the key, then the result


_NODES, _FIRST, _LAST, _NEXT_ID = 0, 1, 2, 3


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
    # lru_cache_dealloc: the weak references; then lru_cache_tp_clear's order: the cache, the function (RL-587), the type of
    # the info, the dict, and last the links (lru_cache_clear_list; RL-600)
    __slots__ = ("_l_cache", "_l_func", "_l_maxsize", "_l_typed", "_l_hits", "_l_misses", "_l_info", "_l_kind", "_l_links", "__dict__", "__weakref__")
    __release__ = ("__weakref__", "_l_cache", "_l_func", "_l_maxsize", "_l_typed", "_l_hits", "_l_misses", "_l_info", "_l_kind", "__dict__", "_l_links")

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
        elif _has_slot(maxsize_o, "__index__"):   # PyIndex_Check: the type's slot, which no metaclass answers for (RL-616)
            maxsize = _number_index(maxsize_o)
            if maxsize > _SSIZE_MAX or maxsize < -_SSIZE_MAX - 1:
                raise OverflowError("cannot fit '" + _tp_name(maxsize_o) + "' into an index-sized integer")
            if maxsize < 0:
                maxsize = 0
            kind = "uncached" if maxsize == 0 else "bounded"
        else:
            raise TypeError("maxsize should be integer or None")
        self = _bella_new_instance(cls)  # type: ignore[arg-type]
        _set(self, "_l_links", [{}, None, None, 0])
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
            links = self._l_links  # type: ignore[attr-defined]
            _extract(links, found)
            _append(links, found)
            _set(self, "_l_hits", self._l_hits + 1)  # type: ignore[attr-defined]
            return found.result
        _set(self, "_l_misses", self._l_misses + 1)  # type: ignore[attr-defined]
        return _bounded_update(self, given, kwds, key, h, cache)

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
        links = self._l_links  # type: ignore[attr-defined]
        nodes = links[_NODES]                    # lru_cache_unlink_list: the ring is empty before anything goes
        links[_NODES] = {}
        links[_FIRST] = None
        links[_LAST] = None
        _set(self, "_l_hits", 0)
        _set(self, "_l_misses", 0)
        self._l_cache.clear()  # type: ignore[attr-defined]
        nodes.clear()                            # lru_cache_clear_list: the links, oldest first

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


def _extract(links: list[Any], link: _Link) -> None:   # lru_cache_extract_link; the caller has the ring's reference from here
    nodes = links[_NODES]
    before = link.prev  # type: ignore[attr-defined]
    after = link.next  # type: ignore[attr-defined]
    if before is None:
        links[_FIRST] = after
    else:
        nodes[before].next = after
    if after is None:
        links[_LAST] = before
    else:
        nodes[after].prev = before
    del nodes[link.id]  # type: ignore[attr-defined]


def _append(links: list[Any], link: _Link) -> None:    # lru_cache_append_link: the newest, and the last of the entries
    nodes = links[_NODES]
    last = links[_LAST]
    link.prev = last  # type: ignore[attr-defined]
    link.next = None  # type: ignore[attr-defined]
    if last is None:
        links[_FIRST] = link.id  # type: ignore[attr-defined]
    else:
        nodes[last].next = link.id  # type: ignore[attr-defined]
    links[_LAST] = link.id  # type: ignore[attr-defined]
    nodes[link.id] = link  # type: ignore[attr-defined]


def _prepend(links: list[Any], link: _Link) -> None:   # lru_cache_prepend_link: back as the oldest
    nodes = links[_NODES]
    first = links[_FIRST]
    link.prev = None  # type: ignore[attr-defined]
    link.next = first  # type: ignore[attr-defined]
    if first is None:
        links[_LAST] = link.id  # type: ignore[attr-defined]
    else:
        nodes[first].prev = link.id  # type: ignore[attr-defined]
    links[_FIRST] = link.id  # type: ignore[attr-defined]
    rest = list(nodes.items())                   # and the first of the entries, which a dict can only be told by filling it again
    nodes.clear()
    nodes[link.id] = link  # type: ignore[attr-defined]
    for number, other in rest:
        nodes[number] = other


def _bounded_update(self: object, given: tuple[object, ...], kwds: dict[str, object], key: object, h: int, cache: dict[object, object]) -> object:
    """The call and bounded_lru_cache_update. The result is this function's own from the call on, as it is the C function's:
    where the C lets go of it, nothing else here holds it (RL-614)."""
    result = self._l_func(*given, **kwds)  # type: ignore[attr-defined]
    if _get_hashed(cache, key, h, _ABSENT) is not _ABSENT:   # the function added the key, reentrantly: the link is up to date
        return result
    links = self._l_links  # type: ignore[attr-defined]
    if len(cache) < self._l_maxsize or links[_FIRST] is None:  # type: ignore[attr-defined]
        link = _Link()
        link.id = links[_NEXT_ID]  # type: ignore[attr-defined]
        links[_NEXT_ID] += 1
        link.hash = h
        link.key = key
        link.result = result
        _set_hashed(cache, key, h, link)
        _append(links, link)
        return result
    link = links[_NODES][links[_FIRST]]          # the oldest link goes, and is used again
    _extract(links, link)
    try:
        popped = _pop_hashed(cache, link.key, link.hash, _ABSENT)
    except BaseException:
        _prepend(links, link)
        raise
    if popped is _ABSENT:                        # gone already: an orphan
        return result
    oldkey = link.key
    oldresult = link.result
    link.hash = h
    link.key = key
    link.result = result
    try:
        _set_hashed(cache, key, h, link)
    except BaseException:
        # the C's order when the store fails: the link, which alone has the new result by now, then the old key, then the
        # old result; the cache is left one link short
        del result, popped, link
        del oldkey
        del oldresult
        raise
    _append(links, link)
    del popped, oldkey, oldresult
    return result
