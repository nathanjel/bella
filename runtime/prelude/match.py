"""The runtime half of `match` (Gate 0 task 4, step A5b).

The frontend's desugar-match pass turns each case into ordinary checks and calls these helpers
where CPython's codegen emits MATCH_SEQUENCE, MATCH_MAPPING, MATCH_KEYS and MATCH_CLASS. They
are those instructions of CPython 3.15.2 (Python/bytecodes.c; _PyEval_MatchKeys and
_PyEval_MatchClass in Python/ceval.c) in Python, with their order of effects and messages,
compiled with the runtime and run at the first statement that needs one, in no sys.modules
(runtime/src/call.cpp, load_match).

A type's name in the messages is its tp_name, which no attribute of the class tells (a C type made
from a spec keeps the spec's whole name, re.Pattern; a class statement's is its __name__):
`_bella_tp_name_of` is the runtime's own, given to this module by whoever runs it (the compiled
runtime, eval1 and eval2).
"""
__intrinsics__ = ["match_is_sequence", "match_is_mapping", "match_keys", "mapping_rest", "match_class"]

try:
    _bella_tp_name_of                            # noqa: B018  # a class's own tp_name
except NameError:
    from collections.abc import Callable

    def _missing(*args: object) -> str:
        raise ImportError("this file needs the runtime's primitives")

    _bella_tp_name_of: Callable[[type], str] = _missing

_SEQUENCE = 1 << 5          # Py_TPFLAGS_SEQUENCE: list, tuple, range, ...; Sequence.register sets it
_MAPPING = 1 << 6           # Py_TPFLAGS_MAPPING: dict, mappingproxy, ...; Mapping.register sets it
_MATCH_SELF = 1 << 22       # _Py_TPFLAGS_MATCH_SELF: bool, bytearray, bytes, dict, float, ...
_type_mro = type.__dict__["__mro__"].__get__


def match_is_sequence(subject: object) -> bool:
    """MATCH_SEQUENCE: by the type's flag (str, bytes and bytearray do not have it)."""
    return bool(type(subject).__flags__ & _SEQUENCE)


def match_is_mapping(subject: object) -> bool:
    """MATCH_MAPPING: by the type's flag."""
    return bool(type(subject).__flags__ & _MAPPING)


def match_keys(subject: object, keys: tuple[object, ...]) -> tuple[object, ...] | None:
    """MATCH_KEYS: subject.get(key, dummy) for each key in order, looked up once; a missing key
    ends the match (None); a key given twice is a ValueError."""
    if not keys:
        return ()
    get = subject.get  # type: ignore[attr-defined]  # a mapping, checked by match_is_mapping
    seen: set[object] = set()
    dummy = object()
    values: list[object] = []
    for key in keys:
        if key in seen:
            raise ValueError(f"mapping pattern checks duplicate key ({key!r})")
        seen.add(key)
        value = get(key, dummy)
        if value is dummy:
            return None
        values.append(value)
    return tuple(values)


def mapping_rest(subject: object, keys: tuple[object, ...]) -> dict[object, object]:
    """**rest: BUILD_MAP, DICT_UPDATE with the subject, then DELETE_SUBSCR of each key. The
    display is DICT_UPDATE itself, where dict.update would also take an iterable of pairs
    (review 2026-11-02, G6 2.6.3)."""
    rest: dict[object, object] = {**subject}  # type: ignore[dict-item]  # a mapping, checked by match_is_mapping
    for key in keys:
        del rest[key]
    return rest


def _attr(subject: object, cls: type, name: str, seen: set[str] | None) -> tuple[bool, object]:
    if seen is not None:
        if name in seen:
            raise TypeError(f"{_bella_tp_name_of(cls)}() got multiple sub-patterns for attribute {name!r}")
        seen.add(name)
    missing = False
    value: object = None
    try:
        value = getattr(subject, name)
    except AttributeError:
        missing = True                # PyObject_GetOptionalAttr: an absent attribute fails the match
    return not missing, value


def match_class(cls: object, subject: object, nargs: int, kwargs: tuple[str, ...]) -> tuple[object, ...] | None:
    """MATCH_CLASS: isinstance(subject, cls), then the positional attributes named by
    __match_args__ (or the subject itself, for a class that matches itself), then the keyword
    ones; an absent attribute ends the match (None)."""
    if type not in _type_mro(type(cls)):
        raise TypeError("class pattern must refer to a class")
    if not isinstance(subject, cls):  # type: ignore[arg-type]  # a class, checked above
        return None
    nattrs = nargs + len(kwargs)
    if not nattrs:
        return ()
    seen: set[str] | None = set() if nargs > 0 and nattrs > 1 else None
    attrs: list[object] = []
    if nargs:
        match_self = False
        absent = object()
        match_args = getattr(cls, "__match_args__", absent)
        if match_args is not absent:
            if type(match_args) is not tuple:
                raise TypeError(f"{_bella_tp_name_of(cls)}.__match_args__ must be a tuple (got {_bella_tp_name_of(type(match_args))})")
        else:
            match_args = ()
            match_self = bool(cls.__flags__ & _MATCH_SELF)
        allowed = 1 if match_self else len(match_args)
        if allowed < nargs:
            plural = "" if allowed == 1 else "s"
            raise TypeError(f"{_bella_tp_name_of(cls)}() accepts {allowed} positional sub-pattern{plural} ({nargs} given)")
        if match_self:
            attrs.append(subject)
        else:
            for i in range(nargs):
                name = match_args[i]
                if type(name) is not str:
                    raise TypeError(f"__match_args__ elements must be strings (got {_bella_tp_name_of(type(name))})")
                found, value = _attr(subject, cls, name, seen)
                if not found:
                    return None
                attrs.append(value)
    for name in kwargs:
        found, value = _attr(subject, cls, name, seen)
        if not found:
            return None
        attrs.append(value)
    return tuple(attrs)
