"""_typing, in Python (Objects/typevarobject.c, Modules/_typingmodule.c): TypeVar, ParamSpec, ParamSpecArgs, ParamSpecKwargs, TypeVarTuple,
TypeAliasType, Generic, NoDefault, _idfunc, and Union, which is the runtime's. The intrinsics of PEP 695 (INTRINSIC_TYPEVAR and its
bound and constraints forms, SET_TYPEPARAM_DEFAULT, PARAMSPEC, TYPEVARTUPLE, SUBSCRIPT_GENERIC, SET_FUNCTION_TYPE_PARAMS, TYPEALIAS) are
_bella_type_params, _bella_generic_class, _bella_typealias and _bella_set_type_params, which read the parameter list the frontend
wrote as text (pipeline/l1/frontend.py, _TypeParams) and take the lazy expressions' functions it names."""

__all__ = ["Generic", "NoDefault", "ParamSpec", "ParamSpecArgs", "ParamSpecKwargs", "TypeAliasType", "TypeVar", "TypeVarTuple", "Union", "_idfunc"]
__intrinsics__ = ["type_params", "generic_class", "typealias", "set_type_params"]
__hidden_classes__ = ["_ConstEvaluator"]         # a type of _typing's that is no name of the module

__name__ = "_typing"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_caller_module                         # noqa: B018  # caller(): the calling function's __module__
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_class_set                             # noqa: B018  # a store into a type's dict, which a class statement refuses for __qualname__
    _bella_bootstrap                             # noqa: B018  # _frozen_importlib's functions by name: the union's, GenericAlias
except NameError:
    from collections.abc import Callable
    from typing import Any

    _bella_new_instance = object.__new__

    def _bella_class_set(cls: type, name: str, value: object) -> None:
        pass                                     # under CPython the prelude is read, not run: the member is the C's

    def _bella_bootstrap(name: str, *args: object) -> Any:
        import types
        import typing

        if name == "GenericAlias":
            return types.GenericAlias(*args)
        if name == "_union_from_tuple":
            return typing.Union[args[0]]  # noqa: UP007  # the pair as typing.Union makes it, strings allowed
        if name == "_union_type_or":
            return args[0] | args[1]  # type: ignore[operator]
        return None

    def _bella_caller_module() -> object:
        return "__main__"

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(obj: object) -> str:
        t = type(obj)
        return t.__name__ if t.__module__ in ("builtins", "__main__") else t.__module__ + "." + t.__name__

Union = type(int | None)                         # _PyUnion_Type, the runtime's (typing.Union)
_FORMAT_STRING = 4                               # _Py_ANNOTATE_FORMAT_STRING


class _Absent:
    pass


_ABSENT = _Absent()


def _unpack(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int, maxpos: int) -> list[object]:
    """_PyArg_UnpackKeywords for a clinic signature: the values in order, _ABSENT for one not given."""
    nargs = len(args)
    if nargs > maxpos:
        if maxpos == 0:
            raise TypeError(name + "() takes no positional arguments")
        if maxpos == minpos == 1:
            raise TypeError(name + "() takes exactly 1 positional argument (" + str(nargs) + " given)")
        raise TypeError(name + "() takes at most " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    if nargs + len(kwds) > len(names):
        raise TypeError(name + "() takes at most " + str(len(names)) + (" keyword" if nargs == 0 else "") + " argument" + ("" if len(names) == 1 else "s") + " (" + str(nargs + len(kwds)) + " given)")
    values: list[object] = list(args)
    for key in names[nargs:]:
        values.append(kwds.pop(key, _ABSENT))
    for key in kwds:
        if key in names:
            raise TypeError("argument for " + name + "() given by name ('" + key + "') and position (" + str(names.index(key) + 1) + ")")
        raise TypeError(name + "() got an unexpected keyword argument '" + key + "'")
    for i in range(minpos):
        if values[i] is _ABSENT:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
    return values


def _str_argument(name: str, argument: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(name + "() argument '" + argument + "' must be str, not " + _tp_name(value))
    return value


def _flag(name: str, argument: str, value: object) -> bool:   # the clinic's bool converter: PyObject_IsTrue
    if value is _ABSENT:
        return False
    return bool(value)


def _new_receiver(args: tuple[object, ...], owner: type, shown: str) -> None:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(shown + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(shown + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(shown + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + shown)  # type: ignore[attr-defined]


def _typing_call(name: str, *args: object, **kwds: object) -> object:   # call_typing_func_object
    import typing

    return getattr(typing, name)(*args, **kwds)


def _type_check(arg: object, msg: str) -> object:   # type_check: typing._type_check, except for None
    if arg is None:
        return type(None)
    return _typing_call("_type_check", arg, msg)


def _make_union(a: object, b: object) -> object:   # make_union: a typing.Union of the pair, strings allowed (_Py_union_from_tuple)
    return _bella_bootstrap("_union_from_tuple", (a, b))


def _type_repr(p: object) -> str:               # _Py_typing_type_repr
    if p is Ellipsis:
        return "..."
    if p is type(None):
        return "None"
    if hasattr(p, "__origin__") and hasattr(p, "__args__"):
        return repr(p)
    qualname = getattr(p, "__qualname__", None)
    if qualname is None:
        return repr(p)
    module = getattr(p, "__module__", None)
    if module is None:
        return repr(p)
    if isinstance(module, str) and module == "builtins":
        return str(qualname)
    return str(module) + "." + str(qualname)


class NoDefaultType:
    """NoDefaultType()
--

The type of the NoDefault singleton."""

    __module__ = "builtins"
    __slots__ = ()

    def __new__(cls, *args: object, **kwds: object) -> NoDefaultType:   # nodefault_new
        if args or kwds:
            raise TypeError("NoDefaultType takes no arguments")
        return NoDefault

    def __repr__(self) -> str:
        return "typing.NoDefault"

    def __reduce__(self) -> str:
        return "NoDefault"


NoDefault: NoDefaultType = _bella_new_instance(NoDefaultType)


class _ConstEvaluator:
    """_ConstEvaluator()
--

Internal type for implementing evaluation functions."""

    __slots__ = ("_value",)

    def __repr__(self) -> str:
        return "<constevaluator " + repr(self._value) + ">"

    def __call__(self, *args: object, **kwds: object) -> object:   # constevaluator_call
        if kwds:
            raise TypeError("constevaluator.__call__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("constevaluator.__call__() takes exactly 1 argument (" + str(len(args)) + " given)")
        fmt = args[0]
        if not isinstance(fmt, int):                 # the clinic's int converter
            if not hasattr(type(fmt), "__index__"):
                raise TypeError("'" + _tp_name(fmt) + "' object cannot be interpreted as an integer")
            fmt = fmt.__index__()
        value = self._value
        if fmt == _FORMAT_STRING:
            if isinstance(value, tuple):
                return "(" + ", ".join(_type_repr(item) for item in value) + ")"
            return _type_repr(value)
        return value


def _constevaluator(value: object) -> _ConstEvaluator:   # constevaluator_alloc
    ce: _ConstEvaluator = _bella_new_instance(_ConstEvaluator)
    ce._value = value
    return ce


def _default_of(default_value: object, evaluate_default: object, store: object, name: str) -> object:
    """typevar_default and its kin: the default once computed, else the lazy function's answer, kept."""
    if default_value is not _ABSENT:
        return default_value
    if evaluate_default is None:
        return NoDefault
    computed = evaluate_default()  # type: ignore[operator]
    setattr(store, name, computed)
    return computed


class TypeVar:
    """Type variable.

The preferred way to construct a type variable is via the dedicated
syntax for generic functions, classes, and type aliases::

    class Sequence[T]:  # T is a TypeVar
        ...

This syntax can also be used to create bound and constrained type
variables::

    # S is a TypeVar bound to str
    class StrSequence[S: str]:
        ...

    # A is a TypeVar constrained to str or bytes
    class StrOrBytesSequence[A: (str, bytes)]:
        ...

Type variables can also have defaults:

    class IntDefault[T = int]:
        ...

However, if desired, reusable type variables can also be constructed
manually, like so::

   T = TypeVar('T')  # Can be anything
   S = TypeVar('S', bound=str)  # Can be any subtype of str
   A = TypeVar('A', str, bytes)  # Must be exactly str or bytes
   D = TypeVar('D', default=int)  # Defaults to int

Type variables exist primarily for the benefit of static type
checkers.  They serve as the parameters for generic types as well
as for generic function and type alias definitions.

The variance of type variables is inferred by type checkers when they
are created through the type parameter syntax and when
``infer_variance=True`` is passed. Manually created type variables may
be explicitly marked covariant or contravariant by passing
``covariant=True`` or ``contravariant=True``. By default, manually
created type variables are invariant. See PEP 484 and PEP 695 for more
details.
"""

    __slots__ = ("_name", "_bound", "_evaluate_bound", "_constraints", "_evaluate_constraints", "_default_value", "_evaluate_default",
                 "_covariant", "_contravariant", "_infer_variance", "__dict__")

    def __new__(*args: object, **kwds: object) -> TypeVar:   # noqa: N805  # typevar_new
        _new_receiver(args, TypeVar, "typing.TypeVar")
        if len(args) >= 2:
            if "name" in kwds:
                raise TypeError("argument for typevar() given by name ('name') and position (1)")
            name_arg = args[1]
        elif "name" in kwds:                     # name precedes *constraints: positional or keyword
            name_arg = kwds.pop("name")
        else:
            raise TypeError("typevar() missing required argument 'name' (pos 1)")
        name = _str_argument("typevar", "name", name_arg)
        constraints = tuple(args[2:])
        options = _unpack("typevar", (), kwds, ("bound", "default", "covariant", "contravariant", "infer_variance"), 0, 0)
        bound, default_value, covariant, contravariant, infer_variance = options
        covariant = _flag("typevar", "covariant", covariant)
        contravariant = _flag("typevar", "contravariant", contravariant)
        infer_variance = _flag("typevar", "infer_variance", infer_variance)
        if covariant and contravariant:
            raise ValueError("Bivariant types are not supported.")
        if infer_variance and (covariant or contravariant):
            raise ValueError("Variance cannot be specified with infer_variance.")
        if bound is _ABSENT or bound is None:
            bound = None
        else:
            bound = _type_check(bound, "Bound must be a type.")
        if len(constraints) == 1:
            raise TypeError("A single constraint is not allowed")
        if len(constraints) == 0:
            constraints_value: object = None
        elif bound is not None:
            raise TypeError("Constraints cannot be combined with bound=...")
        else:
            constraints_value = constraints
        if default_value is _ABSENT:
            default_value = NoDefault
        module = _bella_caller_module()
        return _typevar_alloc(name, bound, None, constraints_value, None, default_value, covariant, contravariant, infer_variance, module)

    @property
    def __name__(self) -> object:
        return self._name

    @property
    def __covariant__(self) -> bool:
        return self._covariant

    @property
    def __contravariant__(self) -> bool:
        return self._contravariant

    @property
    def __infer_variance__(self) -> bool:
        return self._infer_variance

    @property
    def __bound__(self) -> object:               # typevar_bound
        if self._bound is not None:
            return self._bound
        if self._evaluate_bound is None:
            return None
        self._bound = self._evaluate_bound()
        return self._bound

    @property
    def __constraints__(self) -> object:         # typevar_constraints
        if self._constraints is not None:
            return self._constraints
        if self._evaluate_constraints is None:
            return ()
        self._constraints = self._evaluate_constraints()
        return self._constraints

    @property
    def __default__(self) -> object:             # typevar_default
        return _default_of(self._default_value, self._evaluate_default, self, "_default_value")

    @property
    def evaluate_bound(self) -> object:
        if self._evaluate_bound is not None:
            return self._evaluate_bound
        if self._bound is not None:
            return _constevaluator(self._bound)
        return None

    @property
    def evaluate_constraints(self) -> object:
        if self._evaluate_constraints is not None:
            return self._evaluate_constraints
        if self._constraints is not None:
            return _constevaluator(self._constraints)
        return None

    @property
    def evaluate_default(self) -> object:
        if self._evaluate_default is not None:
            return self._evaluate_default
        if self._default_value is not _ABSENT:
            return _constevaluator(self._default_value)
        return None

    def __repr__(self) -> str:                   # typevar_repr
        if self._infer_variance:
            return self._name
        return ("+" if self._covariant else "-" if self._contravariant else "~") + self._name

    def __or__(self, other: object) -> object:
        return _make_union(self, other)

    def __ror__(self, other: object) -> object:
        return _make_union(other, self)

    def __typing_subst__(self, arg: object, /) -> object:
        return _typing_call("_typevar_subst", self, arg)

    def __typing_prepare_subst__(self, alias: object, args: object, /) -> object:   # typevar_typing_prepare_subst_impl
        params = alias.__parameters__  # type: ignore[attr-defined]
        i = params.index(self)
        args_len = len(args)  # type: ignore[arg-type]
        if i < args_len:
            return args
        if i == args_len:
            dflt = self.__default__
            if dflt is not NoDefault:
                return args + (dflt,)  # type: ignore[operator]
        raise TypeError("Too few arguments for " + str(alias) + "; actual " + str(args_len) + ", expected at least " + str(i + 1))

    def __reduce__(self) -> object:
        return self._name

    def has_default(self) -> bool:
        return self._evaluate_default is not None or (self._default_value is not NoDefault and self._default_value is not _ABSENT)

    def __mro_entries__(self, bases: object, /) -> object:
        raise TypeError("Cannot subclass an instance of TypeVar")


def _typevar_alloc(name: str, bound: object, evaluate_bound: object, constraints: object, evaluate_constraints: object, default_value: object,
                   covariant: bool, contravariant: bool, infer_variance: bool, module: object) -> TypeVar:   # typevar_alloc
    tv: TypeVar = _bella_new_instance(TypeVar)
    tv._name = name
    tv._bound = bound
    tv._evaluate_bound = evaluate_bound
    tv._constraints = constraints
    tv._evaluate_constraints = evaluate_constraints
    tv._default_value = default_value
    tv._evaluate_default = None
    tv._covariant = covariant
    tv._contravariant = contravariant
    tv._infer_variance = infer_variance
    if module is not None:
        tv.__module__ = module  # type: ignore[assignment]
    return tv


class ParamSpecArgs:
    """The args for a ParamSpec object.

Given a ParamSpec object P, P.args is an instance of ParamSpecArgs.

ParamSpecArgs objects have a reference back to their ParamSpec::

    >>> P = ParamSpec("P")
    >>> P.args.__origin__ is P
    True

This type is meant for runtime introspection and has no special meaning
to static type checkers.
"""

    __slots__ = ("_origin",)

    def __new__(*args: object, **kwds: object) -> ParamSpecArgs:   # noqa: N805
        _new_receiver(args, ParamSpecArgs, "typing.ParamSpecArgs")
        (origin,) = _unpack("paramspecargs", args[1:], kwds, ("origin",), 1, 1)
        return _paramspecattr(args[0], origin)  # type: ignore[arg-type, return-value]

    @property
    def __origin__(self) -> object:
        return self._origin

    def __repr__(self) -> str:                   # paramspecargs_repr
        if type(self._origin) is ParamSpec:
            return self._origin._name + ".args"
        return repr(self._origin) + ".args"

    def __eq__(self, other: object) -> object:   # paramspecattr_richcompare
        if type(other) is not type(self):
            return NotImplemented
        return self._origin == other._origin  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> object:
        if type(other) is not type(self):
            return NotImplemented
        return self._origin != other._origin  # type: ignore[attr-defined]

    __hash__ = None  # type: ignore[assignment]

    def __mro_entries__(self, bases: object, /) -> object:
        raise TypeError("Cannot subclass an instance of ParamSpecArgs")


class ParamSpecKwargs:
    """The kwargs for a ParamSpec object.

Given a ParamSpec object P, P.kwargs is an instance of ParamSpecKwargs.

ParamSpecKwargs objects have a reference back to their ParamSpec::

    >>> P = ParamSpec("P")
    >>> P.kwargs.__origin__ is P
    True

This type is meant for runtime introspection and has no special meaning
to static type checkers.
"""

    __slots__ = ("_origin",)

    def __new__(*args: object, **kwds: object) -> ParamSpecKwargs:   # noqa: N805
        _new_receiver(args, ParamSpecKwargs, "typing.ParamSpecKwargs")
        (origin,) = _unpack("paramspeckwargs", args[1:], kwds, ("origin",), 1, 1)
        return _paramspecattr(args[0], origin)  # type: ignore[arg-type, return-value]

    @property
    def __origin__(self) -> object:
        return self._origin

    def __repr__(self) -> str:                   # paramspeckwargs_repr
        if type(self._origin) is ParamSpec:
            return self._origin._name + ".kwargs"
        return repr(self._origin) + ".kwargs"

    def __eq__(self, other: object) -> object:
        if type(other) is not type(self):
            return NotImplemented
        return self._origin == other._origin  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> object:
        if type(other) is not type(self):
            return NotImplemented
        return self._origin != other._origin  # type: ignore[attr-defined]

    __hash__ = None  # type: ignore[assignment]

    def __mro_entries__(self, bases: object, /) -> object:
        raise TypeError("Cannot subclass an instance of ParamSpecKwargs")


def _paramspecattr(cls: type, origin: object) -> object:   # paramspecattr_new
    psa = _bella_new_instance(cls)
    psa._origin = origin
    return psa


class ParamSpec:
    """Parameter specification variable.

The preferred way to construct a parameter specification is via the
dedicated syntax for generic functions, classes, and type aliases,
where the use of '**' creates a parameter specification::

    type IntFunc[**P] = Callable[P, int]

The following syntax creates a parameter specification that defaults
to a callable accepting two positional-only arguments of types int
and str:

    type IntFuncDefault[**P = (int, str)] = Callable[P, int]

For compatibility with Python 3.11 and earlier, ParamSpec objects
can also be created as follows::

    P = ParamSpec('P')
    DefaultP = ParamSpec('DefaultP', default=(int, str))

Parameter specification variables exist primarily for the benefit of
static type checkers.  They are used to forward the parameter types of
one callable to another callable, a pattern commonly found in
higher-order functions and decorators.  They are only valid when used
in ``Concatenate``, or as the first argument to ``Callable``, or as
parameters for user-defined Generics. See class Generic for more
information on generic types.

An example for annotating a decorator::

    def add_logging[**P, T](f: Callable[P, T]) -> Callable[P, T]:
        '''A type-safe decorator to add logging to a function.'''
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            logging.info(f'{f.__name__} was called')
            return f(*args, **kwargs)
        return inner

    @add_logging
    def add_two(x: float, y: float) -> float:
        '''Add two numbers together.'''
        return x + y

Parameter specification variables can be introspected. e.g.::

    >>> P = ParamSpec("P")
    >>> P.__name__
    'P'

Note that only parameter specification variables defined in the global
scope can be pickled.
"""

    __slots__ = ("_name", "_bound", "_default_value", "_evaluate_default", "_covariant", "_contravariant", "_infer_variance", "__dict__")

    def __new__(*args: object, **kwds: object) -> ParamSpec:   # noqa: N805  # paramspec_new
        _new_receiver(args, ParamSpec, "typing.ParamSpec")
        name, bound, default_value, covariant, contravariant, infer_variance = _unpack(
            "paramspec", args[1:], kwds, ("name", "bound", "default", "covariant", "contravariant", "infer_variance"), 1, 1)
        name = _str_argument("paramspec", "name", name)
        covariant = _flag("paramspec", "covariant", covariant)
        contravariant = _flag("paramspec", "contravariant", contravariant)
        infer_variance = _flag("paramspec", "infer_variance", infer_variance)
        if covariant and contravariant:
            raise ValueError("Bivariant types are not supported.")
        if infer_variance and (covariant or contravariant):
            raise ValueError("Variance cannot be specified with infer_variance.")
        if bound is _ABSENT:
            bound = None
        if default_value is _ABSENT:
            default_value = NoDefault
        return _paramspec_alloc(name, bound, default_value, covariant, contravariant, infer_variance, _bella_caller_module())

    @property
    def __name__(self) -> object:
        return self._name

    @property
    def __bound__(self) -> object:
        return self._bound

    @property
    def __covariant__(self) -> bool:
        return self._covariant

    @property
    def __contravariant__(self) -> bool:
        return self._contravariant

    @property
    def __infer_variance__(self) -> bool:
        return self._infer_variance

    @property
    def args(self) -> object:
        """Represents positional arguments."""
        return _paramspecattr(ParamSpecArgs, self)

    @property
    def kwargs(self) -> object:
        """Represents keyword arguments."""
        return _paramspecattr(ParamSpecKwargs, self)

    @property
    def __default__(self) -> object:
        """The default value for this ParamSpec."""
        return _default_of(self._default_value, self._evaluate_default, self, "_default_value")

    @property
    def evaluate_default(self) -> object:
        if self._evaluate_default is not None:
            return self._evaluate_default
        if self._default_value is not _ABSENT:
            return _constevaluator(self._default_value)
        return None

    def __repr__(self) -> str:
        if self._infer_variance:
            return self._name
        return ("+" if self._covariant else "-" if self._contravariant else "~") + self._name

    def __or__(self, other: object) -> object:
        return _make_union(self, other)

    def __ror__(self, other: object) -> object:
        return _make_union(other, self)

    def __typing_subst__(self, arg: object, /) -> object:
        return _typing_call("_paramspec_subst", self, arg)

    def __typing_prepare_subst__(self, alias: object, args: object, /) -> object:
        return _typing_call("_paramspec_prepare_subst", self, alias, args)

    def __reduce__(self) -> object:
        return self._name

    def has_default(self) -> bool:
        return self._evaluate_default is not None or (self._default_value is not NoDefault and self._default_value is not _ABSENT)

    def __mro_entries__(self, bases: object, /) -> object:
        raise TypeError("Cannot subclass an instance of ParamSpec")


def _paramspec_alloc(name: str, bound: object, default_value: object, covariant: bool, contravariant: bool, infer_variance: bool,
                     module: object) -> ParamSpec:   # paramspec_alloc
    ps: ParamSpec = _bella_new_instance(ParamSpec)
    ps._name = name
    ps._bound = bound
    ps._covariant = covariant
    ps._contravariant = contravariant
    ps._infer_variance = infer_variance
    ps._default_value = default_value
    ps._evaluate_default = None
    if module is not None:
        ps.__module__ = module  # type: ignore[assignment]
    return ps


class TypeVarTuple:
    """Type variable tuple. A specialized form of type variable that enables
variadic generics.

The preferred way to construct a type variable tuple is via the
dedicated syntax for generic functions, classes, and type aliases,
where a single '*' indicates a type variable tuple::

    def move_first_element_to_last[T, *Ts](tup: tuple[T, *Ts]) -> tuple[*Ts, T]:
        return (*tup[1:], tup[0])

Type variables tuples can have default values:

    type AliasWithDefault[*Ts = (str, int)] = tuple[*Ts]

For compatibility with Python 3.11 and earlier, TypeVarTuple objects
can also be created as follows::

    Ts = TypeVarTuple('Ts')  # Can be given any name
    DefaultTs = TypeVarTuple('Ts', default=(str, int))

Just as a TypeVar (type variable) is a placeholder for a single type,
a TypeVarTuple is a placeholder for an *arbitrary* number of types. For
example, if we define a generic class using a TypeVarTuple::

    class C[*Ts]: ...

Then we can parameterize that class with an arbitrary number of type
arguments::

    C[int]       # Fine
    C[int, str]  # Also fine
    C[()]        # Even this is fine

For more details, see PEP 646.

Note that only TypeVarTuples defined in the global scope can be
pickled.
"""

    __slots__ = ("_name", "_bound", "_default_value", "_evaluate_default", "_covariant", "_contravariant", "_infer_variance", "__dict__")

    def __new__(*args: object, **kwds: object) -> TypeVarTuple:   # noqa: N805  # typevartuple_impl
        _new_receiver(args, TypeVarTuple, "typing.TypeVarTuple")
        name, bound, covariant, contravariant, infer_variance, default_value = _unpack(
            "typevartuple", args[1:], kwds, ("name", "bound", "covariant", "contravariant", "infer_variance", "default"), 1, 1)
        name = _str_argument("typevartuple", "name", name)
        covariant = _flag("typevartuple", "covariant", covariant)
        contravariant = _flag("typevartuple", "contravariant", contravariant)
        infer_variance = _flag("typevartuple", "infer_variance", infer_variance)
        if covariant and contravariant:
            raise ValueError("Bivariant types are not supported.")
        if infer_variance and (covariant or contravariant):
            raise ValueError("Variance cannot be specified with infer_variance.")
        if bound is _ABSENT:
            bound = None
        if default_value is _ABSENT:
            default_value = NoDefault
        return _typevartuple_alloc(name, bound, default_value, covariant, contravariant, infer_variance, _bella_caller_module())

    @property
    def __name__(self) -> object:
        return self._name

    @property
    def __bound__(self) -> object:
        return self._bound

    @property
    def __covariant__(self) -> bool:
        return self._covariant

    @property
    def __contravariant__(self) -> bool:
        return self._contravariant

    @property
    def __infer_variance__(self) -> bool:
        return self._infer_variance

    @property
    def __default__(self) -> object:
        """The default value for this TypeVarTuple."""
        return _default_of(self._default_value, self._evaluate_default, self, "_default_value")

    @property
    def evaluate_default(self) -> object:
        if self._evaluate_default is not None:
            return self._evaluate_default
        if self._default_value is not _ABSENT:
            return _constevaluator(self._default_value)
        return None

    def __iter__(self) -> object:                # unpack_iter
        return iter((_unpack_typevartuple(self),))

    def __repr__(self) -> str:
        if self._infer_variance:
            return self._name
        return ("+" if self._covariant else "-" if self._contravariant else "~") + self._name

    def __typing_subst__(self, arg: object, /) -> object:
        raise TypeError("Substitution of bare TypeVarTuple is not supported")

    def __typing_prepare_subst__(self, alias: object, args: object, /) -> object:
        return _typing_call("_typevartuple_prepare_subst", self, alias, args)

    def __reduce__(self) -> object:
        return self._name

    def has_default(self) -> bool:
        return self._evaluate_default is not None or (self._default_value is not NoDefault and self._default_value is not _ABSENT)

    def __mro_entries__(self, bases: object, /) -> object:
        raise TypeError("Cannot subclass an instance of TypeVarTuple")


def _typevartuple_alloc(name: str, bound: object, default_value: object, covariant: bool, contravariant: bool, infer_variance: bool,
                        module: object) -> TypeVarTuple:   # typevartuple_alloc
    tvt: TypeVarTuple = _bella_new_instance(TypeVarTuple)
    tvt._name = name
    tvt._bound = bound
    tvt._covariant = covariant
    tvt._contravariant = contravariant
    tvt._infer_variance = infer_variance
    tvt._default_value = default_value
    tvt._evaluate_default = None
    if module is not None:
        tvt.__module__ = module  # type: ignore[assignment]
    return tvt


def _unpack_typevartuple(tvt: object) -> object:   # unpack: typing.Unpack[tvt]
    import typing

    return typing.Unpack[tvt]  # type: ignore[index]


def _unpack_typevartuples(params: tuple[object, ...]) -> tuple[object, ...]:   # unpack_typevartuples
    if any(type(p) is TypeVarTuple for p in params):
        return tuple(_unpack_typevartuple(p) if type(p) is TypeVarTuple else p for p in params)
    return params


def _type_param_default(typeparam: object) -> object:   # get_type_param_default
    if type(typeparam) is TypeVar or type(typeparam) is ParamSpec or type(typeparam) is TypeVarTuple:
        return typeparam.__default__  # type: ignore[attr-defined]
    raise TypeError("Expected a type param, got " + repr(typeparam))


def _check_type_params(type_params: tuple[object, ...]) -> object:   # typealias_check_type_params: None for an empty tuple
    if not type_params:
        return None
    default_seen = False
    for type_param in type_params:
        dflt = _type_param_default(type_param)
        if dflt is NoDefault:
            if default_seen:
                raise TypeError("non-default type parameter '" + repr(type_param) + "' follows default type parameter")
        else:
            default_seen = True
    return type_params


class TypeAliasType:
    """Type alias.

Type aliases are created through the type statement::

    type Alias = int

In this example, Alias and int will be treated equivalently by static
type checkers.

At runtime, Alias is an instance of TypeAliasType. The __name__
attribute holds the name of the type alias. The value of the type alias
is stored in the __value__ attribute. It is evaluated lazily, so the
value is computed only if the attribute is accessed.

Type aliases can also be generic::

    type ListOrSet[T] = list[T] | set[T]

In this case, the type parameters of the alias are stored in the
__type_params__ attribute.

See PEP 695 for more information.
"""

    __slots__ = ("_name", "_qualname", "_type_params", "_compute_value", "_value", "_module")

    def __new__(*args: object, **kwds: object) -> TypeAliasType:   # noqa: N805  # typealias_new
        _new_receiver(args, TypeAliasType, "typing.TypeAliasType")
        name, value, type_params, qualname = _unpack("typealias", args[1:], kwds, ("name", "value", "type_params", "qualname"), 2, 2)
        name = _str_argument("typealias", "name", name)
        if type_params is _ABSENT:
            checked: object = None
        else:
            if not isinstance(type_params, tuple):
                raise TypeError("type_params must be a tuple")
            checked = _check_type_params(type_params)
        if qualname is _ABSENT or qualname is None:
            qualname = name
        elif not isinstance(qualname, str):
            raise TypeError("qualname must be a string")
        return _typealias_alloc(name, qualname, checked, None, value, _bella_caller_module())

    @property
    def __name__(self) -> object:
        return self._name

    @property
    def __value__(self) -> object:               # typealias_get_value
        if self._value is not _ABSENT:
            return self._value
        result = self._compute_value()  # type: ignore[operator]
        self._value = result
        return result

    @property
    def evaluate_value(self) -> object:
        if self._compute_value is not None:
            return self._compute_value
        return _constevaluator(self._value)

    @property
    def __parameters__(self) -> object:
        if self._type_params is None:
            return ()
        return _unpack_typevartuples(self._type_params)

    @property
    def __type_params__(self) -> object:
        if self._type_params is None:
            return ()
        return self._type_params

    @property
    def __module__(self) -> object:              # typealias_module: given, else the value function's
        if self._module is not None:
            return self._module
        if self._compute_value is not None:
            return getattr(self._compute_value, "__module__", None)
        return None

    @__module__.setter
    def __module__(self, value: object) -> None:
        self._module = value

    def __repr__(self) -> str:
        return self._qualname

    def __reduce__(self) -> object:
        return self._name

    def __getitem__(self, args: object) -> object:   # typealias_subscript
        if self._type_params is None:
            raise TypeError("Only generic type aliases are subscriptable")
        return _bella_bootstrap("GenericAlias", self, args)

    def __or__(self, other: object) -> object:   # _Py_union_type_or
        return _bella_bootstrap("_union_type_or", self, other)

    def __ror__(self, other: object) -> object:
        return _bella_bootstrap("_union_type_or", other, self)

    def __iter__(self) -> object:                # unpack_iter
        return iter((_unpack_typevartuple(self),))


def _typealias_qualname(self: TypeAliasType) -> object:   # the __qualname__ member, which a class body cannot declare
    return self._qualname


_bella_class_set(TypeAliasType, "__qualname__", property(_typealias_qualname))


def _typealias_alloc(name: str, qualname: object, type_params: object, compute_value: object, value: object, module: object) -> TypeAliasType:
    ta: TypeAliasType = _bella_new_instance(TypeAliasType)
    ta._name = name
    ta._qualname = qualname
    ta._type_params = type_params
    ta._compute_value = compute_value
    ta._value = _ABSENT if compute_value is not None else value
    ta._module = module
    return ta


class Generic:
    """Abstract base class for generic types.

On Python 3.12 and newer, generic classes implicitly inherit from
Generic when they declare a parameter list after the class's name::

    class Mapping[KT, VT]:
        def __getitem__(self, key: KT) -> VT:
            ...
        # Etc.

On older versions of Python, however, generic classes have to
explicitly inherit from Generic.

After a class has been declared to be generic, it can then be used as
follows::

    def lookup_name[KT, VT](mapping: Mapping[KT, VT], key: KT, default: VT) -> VT:
        try:
            return mapping[key]
        except KeyError:
            return default
"""

    __slots__ = ()

    @classmethod
    def __class_getitem__(cls, *args: object, **kwds: object) -> object:   # generic_class_getitem
        """Parameterizes a generic class.

At least, parameterizing a generic class is the *main* thing this
method does. For example, for some generic class `Foo`, this is called
when we do `Foo[int]` - there, with `cls=Foo` and `params=int`.

However, note that this method is also called when defining generic
classes in the first place with `class Foo[T]: ...`."""
        return _typing_call("_generic_class_getitem", cls, *args, **kwds)

    @classmethod
    def __init_subclass__(cls, *args: object, **kwds: object) -> object:   # generic_init_subclass
        """Function to initialize subclasses."""
        return _typing_call("_generic_init_subclass", cls, *args, **kwds)


def _idfunc(*args: object, **kwds: object) -> object:
    if kwds:
        raise TypeError("_typing._idfunc() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_typing._idfunc() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


# ---- the intrinsics of a generic definition (Python/intrinsics.c), over the frontend's parameter text ----

def _split_params(text: str) -> list[str]:
    """The items of a parameter list the frontend wrote, split at the commas outside parentheses."""
    items: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def _thunk_index(call: str) -> int:              # "__bella_3__()" -> 3
    call = call.strip()
    if not call.startswith("__bella_") or not call.endswith("__()"):
        raise SystemError("a lazy expression the frontend did not write: " + call)
    return int(call[len("__bella_"):-len("__()")])


def _make_params(text: str, thunks: tuple[object, ...]) -> tuple[object, ...]:
    """INTRINSIC_TYPEVAR, TYPEVAR_WITH_BOUND, TYPEVAR_WITH_CONSTRAINTS, PARAMSPEC, TYPEVARTUPLE and SET_TYPEPARAM_DEFAULT, in the order the
    parameters stand: `T`, `T: thunk()`, `T: (*thunk(),)`, `*Ts`, `**P`, each with an optional ` = thunk()` (` = *thunk()` for a
    TypeVarTuple's default)."""
    made: list[object] = []
    for item in _split_params(text):
        default: object = None
        if " = " in item:
            item, default_text = item.split(" = ", 1)
            default_text = default_text.strip()
            if default_text.startswith("*"):
                default_text = default_text[1:]
            default = thunks[_thunk_index(default_text)]
        item = item.strip()
        param: object
        if item.startswith("**"):
            param = _paramspec_alloc(item[2:], None, _ABSENT, False, False, True, None)
        elif item.startswith("*"):
            param = _typevartuple_alloc(item[1:], None, _ABSENT, False, False, True, None)
        else:
            name, _, bound_text = item.partition(":")
            name = name.strip()
            bound_text = bound_text.strip()
            if not bound_text:
                param = _typevar_alloc(name, None, None, None, None, _ABSENT, False, False, True, None)
            elif bound_text.startswith("(*"):     # "(*thunk(),)": the constraints' one lazy function
                param = _typevar_alloc(name, None, None, None, thunks[_thunk_index(bound_text[2:-2])], _ABSENT, False, False, True, None)
            else:
                param = _typevar_alloc(name, None, thunks[_thunk_index(bound_text)], None, None, _ABSENT, False, False, True, None)
        if default is not None:                  # _Py_set_typeparam_default
            param._evaluate_default = default  # type: ignore[attr-defined]
        made.append(param)
    return tuple(made)


def _bella_type_params(text: str, *thunks: object) -> tuple[object, ...]:   # "def __bella_tp__[PARAMS](): pass"
    return _make_params(text[len("def __bella_tp__["):-len("](): pass")], thunks)


def _bella_generic_class(text: str, *thunks: object) -> tuple[object, ...]:   # "class __bella_tp__[PARAMS]: pass": (params, Generic[params])
    params = _make_params(text[len("class __bella_tp__["):-len("]: pass")], thunks)
    return params, _typing_call("_GenericAlias", Generic, _unpack_typevartuples(params))   # _Py_subscript_generic


def _bella_typealias(text: str, compute_value: object, *thunks: object) -> TypeAliasType:   # "type NAME[PARAMS] = __bella_v__()"
    head = text[len("type "):-len(" = __bella_v__()")]
    name, bracket, rest = head.partition("[")
    type_params = _make_params(rest[:-1], thunks) if bracket else None
    return _typealias_alloc(name, compute_value.__qualname__, type_params or None, compute_value, _ABSENT, None)   # type: ignore[attr-defined]


def _bella_set_type_params(function: object, params: tuple[object, ...]) -> object:   # INTRINSIC_SET_FUNCTION_TYPE_PARAMS
    function.__type_params__ = params  # type: ignore[attr-defined]
    return function


type_params = _bella_type_params
generic_class = _bella_generic_class
typealias = _bella_typealias
set_type_params = _bella_set_type_params

_bella_bootstrap("_set_typealias_type", TypeAliasType)   # is_unionable: a TypeAliasType joins a union
