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


def _is_type(obj: object) -> bool:
    """PyType_Check: the object's type derives from type (by tp_mro, not __instancecheck__)."""
    return type in _type_mro(type(obj))


def _is_subtype(a: type, b: type) -> bool:
    """PyType_IsSubtype: b in a's MRO (not __subclasscheck__)."""
    return b in _type_mro(a)


def _tp_name(t: type) -> str:
    """tp_name: the qualified name of a heap type is its __name__; a static type's carries its
    module unless it is a builtin."""
    if t.__flags__ & (1 << 9) or t.__module__ == "builtins":
        return t.__name__
    return t.__module__ + "." + t.__qualname__


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
        if tuple not in _type_mro(type(new_base)):        # PyTuple_Check
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
    """PyMapping_Check: the type has a __getitem__ (a mapping slot), as a list does too."""
    return getattr(type(obj), "__getitem__", None) is not None


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
            raise RuntimeError(f"__class__ not set defining {name!r} as {cls!r}. "
                               "Was __classcell__ propagated to type.__new__?")
        if cell_cls is not cls:
            raise TypeError(f"__class__ set to {cell_cls!r} defining {name!r} as {cls!r}")
    return cls
