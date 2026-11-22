"""build_class: what a class statement calls (Gate 0 task 4, step A3).

The frontend lowers ``class C(B, metaclass=M, **kw): body`` the way CPython's compiler does:
the body becomes a function of the namespace, and the statement becomes
``C = build_class(body, "C", B, metaclass=M, **kw)`` (decorators applied to the result). This
is CPython 3.15.2's ``builtin___build_class__`` and ``update_bases`` (Python/bltinmodule.c)
and ``_PyType_CalculateMetaclass`` (Objects/typeobject.c), in Python, with their order of
effects and their messages. It is compiled with the program like any other module, so the
runtime carries no class-creation machinery of its own beyond ``type`` itself.

``body`` is the frontend's class-body function, which no program can name: CPython's
``__build_class__`` requires a function there, and this one is never handed anything else.
"""

__intrinsics__ = ["build_class"]                  # what the compiled runtime takes from this module

_type_mro = type.__dict__["__mro__"].__get__      # tp_mro, whatever a metaclass defines as __mro__

try:
    _has_slot                                    # noqa: B018  # a slot of the type, by its own MRO and dicts: the runtime's (RL-644)
    _repr_text                                   # noqa: B018  # %R: the characters of an object's repr, an exact str (RL-748's class)
except NameError:                                # CPython runs this file (the evaluators and the tests): what stands for it
    _type_dict = type.__dict__["__dict__"].__get__

    def _has_slot(value: object, name: str) -> bool:
        return any(name in _type_dict(klass) for klass in _type_mro(type(value)))

    def _repr_text(value: object) -> str:        # a stand-in for CPython's run of this file
        return str.__str__(repr(value))


_type_flags = type.__dict__["__flags__"].__get__      # tp_flags and the names, whatever a metaclass defines under theirs (RL-794)
_type_name = type.__dict__["__name__"].__get__
_type_module = type.__dict__["__module__"].__get__
_type_qualname = type.__dict__["__qualname__"].__get__


def _in_mro(mro: tuple[type, ...], cls: type) -> bool:
    """The class is one of the MRO's, by identity, as the C compares pointers: `in` asks a metaclass's __eq__ (RL-784)."""
    for klass in mro:
        if klass is cls:
            return True
    return False


def _is_type(obj: object) -> bool:
    """PyType_Check: the object's type derives from type (by tp_mro, not __instancecheck__)."""
    return _in_mro(_type_mro(type(obj)), type)


def _is_subtype(a: type, b: type) -> bool:
    """PyType_IsSubtype: b in a's MRO (not __subclasscheck__)."""
    return _in_mro(_type_mro(a), b)


def _tp_name(t: type) -> str:
    """tp_name: the qualified name of a heap type is its __name__; a static type's carries its
    module unless it is a builtin. Read as the C reads the struct: no property of a metaclass is asked."""
    if _type_flags(t) & (1 << 9) or _type_module(t) == "builtins":
        return str.__str__(_type_name(t))
    return str.__str__(_type_module(t)) + "." + str.__str__(_type_qualname(t))


_ABSENT = object()     # an absent attribute, told apart from one that is None (review 2026-11-02, A7-6)


def _update_bases(bases: tuple[object, ...]) -> tuple[object, ...]:
    """PEP 560: a base that is not a class and has __mro_entries__ is replaced by the tuple it
    returns, given the original bases."""
    new_bases: list[object] | None = None
    for i in range(len(bases)):
        base = bases[i]
        if _is_type(base):
            if new_bases is not None:
                new_bases.append(base)
            continue
        meth = getattr(base, "__mro_entries__", _ABSENT)   # PyObject_GetOptionalAttr: None is a value
        if meth is _ABSENT:
            if new_bases is not None:
                new_bases.append(base)
            continue
        new_base = meth(bases)
        if not _in_mro(_type_mro(type(new_base)), tuple):   # PyTuple_Check
            raise TypeError("__mro_entries__ must return a tuple")
        if new_bases is None:
            new_bases = list(bases[:i])
        new_bases.extend(new_base)                    # a tuple, checked above
    if new_bases is None:
        return bases
    return tuple(new_bases)


def _calculate_metaclass(metatype: type, bases: tuple[object, ...]) -> type:
    """The most derived metaclass of metatype and the bases' types, or a conflict."""
    winner = metatype
    for base in bases:
        tmptype = type(base)
        if _is_subtype(winner, tmptype):
            continue
        if _is_subtype(tmptype, winner):
            winner = tmptype
            continue
        raise TypeError("metaclass conflict: the metaclass of a derived class must be a (non-strict) "
                        "subclass of the metaclasses of all its bases")
    return winner


def _is_mapping(obj: object) -> bool:
    """PyMapping_Check: the type has a __getitem__ (a mapping slot), as a list does too. The slot is filled by whatever a
    class of the MRO has under the name, None included, and no metaclass is asked (RL-636, RL-644)."""
    return _has_slot(obj, "__getitem__")


def build_class(body: object, name: str, /, *bases: object, **kwds: object) -> object:
    orig_bases = bases
    bases = _update_bases(orig_bases)
    meta: object
    if "metaclass" in kwds:
        meta = kwds.pop("metaclass")
        isclass = _is_type(meta)
    else:
        meta = type(bases[0]) if bases else type
        isclass = True
    if isclass:
        meta = _calculate_metaclass(meta, bases)  # type: ignore[arg-type]  # a class, checked above
    prepare = getattr(meta, "__prepare__", _ABSENT)    # PyObject_GetOptionalAttr: None is a value
    if prepare is _ABSENT:
        ns: object = {}
    else:
        ns = prepare(name, bases, **kwds)
    if not _is_mapping(ns):
        owner = _tp_name(meta) if isclass else "<metaclass>"  # type: ignore[arg-type]  # a class
        raise TypeError(f"{owner}.__prepare__() must return a mapping, not {_tp_name(type(ns))}")
    cell = body(ns)  # type: ignore[operator]  # the frontend's class-body function
    if bases is not orig_bases:
        ns["__orig_bases__"] = orig_bases  # type: ignore[index]  # a mapping, checked above
    cls = meta(name, bases, ns, **kwds)  # type: ignore[operator]  # a metaclass or a callable
    if _is_type(cls) and cell is not None:
        empty = False
        try:
            cell_cls = cell.cell_contents                       # the __class__ cell
        except ValueError:
            empty = True                   # PyCell_GetRef finds nothing; no exception to chain
        if empty:
            raise RuntimeError(f"__class__ not set defining {_repr_text(name)} as {_repr_text(cls)}. "
                               "Was __classcell__ propagated to type.__new__?")
        if cell_cls is not cls:
            raise TypeError(f"__class__ set to {_repr_text(cell_cls)} defining {_repr_text(name)} as {_repr_text(cls)}")
    return cls
