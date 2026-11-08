"""_contextvars, in Python (Python/context.c): Context, ContextVar, Token and copy_context with the C's rules and messages. The
thread's current context is this module's (phase 1 runs one thread); a context's variables are an immutable mapping replaced on every
set and shared by a copy, as the C's HAMT is, kept here as a dict that is copied rather than mutated. The C iterates a context in its
hash tree's order, which depends on addresses; this file iterates in insertion order (neither is a specified observable)."""

__all__ = ["Context", "ContextVar", "Token", "copy_context"]

__name__ = "_contextvars"

__hidden_classes__ = ["keys", "values", "items", "MISSING"]   # the hamt iterators (types of builtins) and Token.MISSING's type

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__


_ABSENT: object = object()


class MISSING:                                   # _PyContextTokenMissing_Type, "Token.MISSING": one instance, Token.MISSING
    __slots__ = ()
    __module__ = "Token"

    def __repr__(self) -> str:
        return "<Token.MISSING>"


_missing_token: MISSING = _bella_new_instance(MISSING)


class keys:  # noqa: N801                       # _PyHamtKeys_Type: an iterator over a context's variables
    __slots__ = ("_it", "_n")
    __module__ = "builtins"

    def __iter__(self) -> keys:
        return self

    def __next__(self) -> object:
        return next(self._it)

    def __len__(self) -> int:                    # hamt_baseiter_tp_len: the mapping's length, however far the iteration is
        return self._n


class values:  # noqa: N801                     # _PyHamtValues_Type
    __slots__ = ("_it", "_n")
    __module__ = "builtins"

    def __iter__(self) -> values:
        return self

    def __next__(self) -> object:
        return next(self._it)

    def __len__(self) -> int:                    # hamt_baseiter_tp_len: the mapping's length, however far the iteration is
        return self._n


class items:  # noqa: N801                      # _PyHamtItems_Type
    __slots__ = ("_it", "_n")
    __module__ = "builtins"

    def __iter__(self) -> items:
        return self

    def __next__(self) -> object:
        return next(self._it)

    def __len__(self) -> int:                    # hamt_baseiter_tp_len: the mapping's length, however far the iteration is
        return self._n


def _iterator(cls: type, variables: dict[ContextVar, object], it: object) -> object:
    self = _bella_new_instance(cls)
    self._it = it  # noqa: SLF001
    self._n = len(variables)  # noqa: SLF001
    return self


def _check_key(key: object) -> ContextVar:       # context_check_key_type
    if type(key) is not ContextVar:
        raise TypeError("a ContextVar key was expected, got " + repr(key))
    return key


class Context:
    __slots__ = ("_entered", "_prev", "_vars", "__weakref__")

    def __new__(cls, *args: object, **kwds: object) -> Context:   # context_tp_new
        if args or kwds:
            raise TypeError("Context() does not accept any arguments")
        return _context_from_vars({})

    def __getitem__(self, key: object) -> object:
        var = _check_key(key)
        found = self._vars.get(var, _ABSENT)
        if found is _ABSENT:
            raise KeyError(var)
        return found

    def __contains__(self, key: object) -> bool:
        return _check_key(key) in self._vars

    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self) -> object:
        return _iterator(keys, self._vars, iter(self._vars))

    def __eq__(self, other: object) -> bool:   # context_tp_richcompare: _PyHamt_Eq, exact contexts only
        if type(other) is not Context:
            return NotImplemented
        return _vars_equal(self._vars, other._vars)

    def __ne__(self, other: object) -> bool:
        if type(other) is not Context:
            return NotImplemented
        return not _vars_equal(self._vars, other._vars)

    __hash__ = None  # type: ignore[assignment]

    def get(self, *args: object, **kwds: object) -> object:
        """Return the value for `key` if `key` has the value in the context object.

If `key` does not exist, return `default`.  If `default` is not
given, return None."""
        if kwds:
            raise TypeError("Context.get() takes no keyword arguments")
        if len(args) < 1:
            raise TypeError("get expected at least 1 argument, got " + str(len(args)))
        if len(args) > 2:
            raise TypeError("get expected at most 2 arguments, got " + str(len(args)))
        var = _check_key(args[0])
        default = args[1] if len(args) == 2 else None
        found = self._vars.get(var, _ABSENT)
        return default if found is _ABSENT else found

    def items(self, *args: object, **kwds: object) -> object:
        """Return all variables and their values in the context object.

The result is returned as a list of 2-tuples (variable, value)."""
        _no_args("Context.items", args, kwds)
        return _iterator(items, self._vars, iter(list(self._vars.items())))

    def keys(self, *args: object, **kwds: object) -> object:
        """Return a list of all variables in the context object."""
        _no_args("Context.keys", args, kwds)
        return _iterator(keys, self._vars, iter(self._vars))

    def values(self, *args: object, **kwds: object) -> object:
        """Return a list of all variables' values in the context object."""
        _no_args("Context.values", args, kwds)
        return _iterator(values, self._vars, iter(list(self._vars.values())))

    def copy(self, *args: object, **kwds: object) -> Context:
        """Return a shallow copy of the context object."""
        _no_args("Context.copy", args, kwds)
        return _context_from_vars(self._vars)

    def run(self, *args: object, **kwds: object) -> object:   # context_run: _PyContext_Enter, the call, _PyContext_Exit
        if len(args) < 1:
            raise TypeError("run() missing 1 required positional argument")
        _enter(self)
        try:
            return args[0](*args[1:], **kwds)  # type: ignore[operator]
        finally:
            _exit(self)


def _vars_equal(a: dict[ContextVar, object], b: dict[ContextVar, object]) -> bool:   # _PyHamt_Eq
    if len(a) != len(b):
        return False
    for key, value in a.items():
        other = b.get(key, _ABSENT)
        if other is _ABSENT:
            return False
        if value is not other and not (value == other):
            return False
    return True


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


def _context_from_vars(variables: dict[ContextVar, object]) -> Context:   # context_new_from_vars
    ctx: Context = _bella_new_instance(Context)
    ctx._vars = variables
    ctx._prev = None
    ctx._entered = False
    return ctx


_current: Context | None = None                  # the thread state's context, made on first use (context_get)


def _get() -> Context:                           # context_get
    global _current
    if _current is None:
        _current = _context_from_vars({})
    return _current


def _enter(ctx: Context) -> None:                # _PyContext_Enter
    global _current
    if ctx._entered:
        raise RuntimeError("cannot enter context: " + repr(ctx) + " is already entered")
    ctx._entered = True
    ctx._prev = _current
    _current = ctx


def _exit(ctx: Context) -> None:                 # _PyContext_Exit
    global _current
    if not ctx._entered:
        raise RuntimeError("cannot exit context: " + repr(ctx) + " has not been entered")
    if _current is not ctx:
        raise RuntimeError("cannot exit context: thread state references a different context object")
    _current = ctx._prev
    ctx._prev = None
    ctx._entered = False


def copy_context(*args: object, **kwds: object) -> Context:   # PyContext_CopyCurrent
    _no_args("_contextvars.copy_context", args, kwds)
    return _context_from_vars(_get()._vars)


class ContextVar:
    __slots__ = ("_default", "_hash", "_name")

    def __new__(cls, *args: object, **kwds: object) -> ContextVar:   # contextvar_tp_new: "O|$O:ContextVar"
        if len(args) + len(kwds) > 2:
            raise TypeError("ContextVar() takes at most 2 arguments (" + str(len(args) + len(kwds)) + " given)")
        if len(args) > 1:
            raise TypeError("ContextVar() takes at most 1 positional argument (" + str(len(args)) + " given)")
        if not args:                             # the required positional is checked before the keywords are matched
            raise TypeError("ContextVar() takes exactly 1 positional argument (0 given)")
        default: object = _ABSENT
        for keyword, value in kwds.items():
            if keyword != "default":
                raise TypeError("ContextVar() got an unexpected keyword argument '" + keyword + "'")
            default = value
        name = args[0]
        if not issubclass(type(name), str):
            raise TypeError("context variable name must be a str")
        self: ContextVar = _bella_new_instance(cls)
        self._name = name
        self._default = default
        h = object.__hash__(self) ^ hash(name)   # contextvar_generate_hash: the address's hash with the name's
        self._hash = -2 if h == -1 else h
        return self

    def __hash__(self) -> int:
        return self._hash

    def __repr__(self) -> str:
        text = "<ContextVar name=" + repr(self._name)
        if self._default is not _ABSENT:
            text += " default=" + repr(self._default)
        return text + " at " + hex(id(self)) + ">"

    @property
    def name(self) -> object:
        return self._name

    def get(self, *args: object, **kwds: object) -> object:   # PyContextVar_Get
        """Return a value for the context variable for the current context.

If there is no value for the variable in the current context, the
method will:
 * return the value of the default argument of the method, if
   provided; or
 * return the default value for the context variable, if it was
   created with one; or
 * raise a LookupError."""
        if kwds:
            raise TypeError("ContextVar.get() takes no keyword arguments")
        if len(args) > 1:
            raise TypeError("get expected at most 1 argument, got " + str(len(args)))
        found = _get()._vars.get(self, _ABSENT)
        if found is not _ABSENT:
            return found
        if args:
            return args[0]
        if self._default is not _ABSENT:
            return self._default
        raise LookupError(self)

    def set(self, *args: object, **kwds: object) -> Token:   # PyContextVar_Set
        """Call to set a new value for the context variable in the current context.

The required value argument is the new value for the context
variable.

Returns a Token object that can be used to restore the variable to
its previous value via the `ContextVar.reset()` method."""
        if kwds:
            raise TypeError("ContextVar.set() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("ContextVar.set() takes exactly one argument (" + str(len(args)) + " given)")
        ctx = _get()
        token = _token(ctx, self, ctx._vars.get(self, _ABSENT))
        _assoc(self, args[0])
        return token

    def reset(self, *args: object, **kwds: object) -> None:   # _contextvars_ContextVar_reset_impl, PyContextVar_Reset
        """Reset the context variable.

The variable is reset to the value it had before the
`ContextVar.set()` that created the token was used."""
        if kwds:
            raise TypeError("ContextVar.reset() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("ContextVar.reset() takes exactly one argument (" + str(len(args)) + " given)")
        token = args[0]
        if type(token) is not Token:
            raise TypeError("expected an instance of Token, got " + repr(token))
        _reset(self, token)


def _assoc(var: ContextVar, value: object) -> None:   # contextvar_set: a new mapping with the pair
    ctx = _get()
    new_vars = dict(ctx._vars)
    new_vars[var] = value
    ctx._vars = new_vars


def _reset(var: ContextVar, token: Token) -> None:   # PyContextVar_Reset
    if token._used:
        raise RuntimeError(repr(token) + " has already been used once")
    if var is not token._var:
        raise ValueError(repr(token) + " was created by a different ContextVar")
    ctx = _get()
    if ctx is not token._ctx:
        raise ValueError(repr(token) + " was created in a different Context")
    token._used = True
    if token._old is _ABSENT:                    # contextvar_del
        if var not in ctx._vars:
            raise LookupError(var)
        new_vars = dict(ctx._vars)
        del new_vars[var]
        ctx._vars = new_vars
    else:
        _assoc(var, token._old)


class Token:
    __slots__ = ("_ctx", "_old", "_used", "_var")

    def __new__(cls, *args: object, **kwds: object) -> Token:   # token_tp_new
        raise RuntimeError("Tokens can only be created by ContextVars")

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return "<Token" + (" used" if self._used else "") + " var=" + repr(self._var) + " at " + hex(id(self)) + ">"

    @property
    def var(self) -> ContextVar:
        return self._var

    @property
    def old_value(self) -> object:
        return _missing_token if self._old is _ABSENT else self._old

    def __enter__(self, *args: object, **kwds: object) -> Token:
        """Enter into Token context manager."""
        _no_args("Token.__enter__", args, kwds)
        return self

    def __exit__(self, *args: object, **kwds: object) -> None:
        """Exit from Token context manager, restore the linked ContextVar."""
        if kwds:
            raise TypeError("Token.__exit__() takes no keyword arguments")
        if len(args) != 3:
            raise TypeError("__exit__ expected 3 arguments, got " + str(len(args)))
        _reset(self._var, self)


def _token(ctx: Context, var: ContextVar, old: object) -> Token:   # token_new
    token: Token = _bella_new_instance(Token)
    token._ctx = ctx
    token._var = var
    token._old = old
    token._used = False
    return token


Token.MISSING = _missing_token  # type: ignore[attr-defined]
