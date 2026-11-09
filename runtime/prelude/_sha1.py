"""_sha1, in Python (Modules/sha1module.c) over the runtime's digest (hashes.cpp, written from RFC 3174): the sha1() constructor with
3.15's data, usedforsecurity and string parameters, and the sha1 type with update, digest, hexdigest, copy, name, digest_size and
block_size, each message the C's. A hash's state travels as bytes, so copy() copies bytes."""

__all__ = ["SHA1Type", "_GIL_MINSIZE", "sha1"]

__name__ = "_sha1"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _hash_new                                    # noqa: B018  # hashes.cpp: (algorithm, params) -> state bytes
    _hash_update                                 # noqa: B018  # (state, data) -> state
    _hash_digest                                 # noqa: B018  # (state) -> bytes
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing
    _hash_new: Callable[..., bytes] = _missing
    _hash_update: Callable[..., bytes] = _missing
    _hash_digest: Callable[..., bytes] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__
    _unpack_keywords: Callable[..., Any] = _missing

_GIL_MINSIZE = 2048
_ABSENT: object = object()


def _buffer(value: object) -> bytes:             # GET_BUFFER_VIEW_OR_ERROUT: a str is told to encode, the rest needs the buffer API
    if issubclass(type(value), str):
        raise TypeError("Strings must be encoded before hashing")
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("object supporting the buffer API required")


def _constructor_args(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> bytes | None:
    """The clinic's (data=b'', *, usedforsecurity=True, string=None): the data to hash first, or None for none."""
    data, usedforsecurity, string = _unpack_keywords(name, ("data", "usedforsecurity", "string"), 0, 0, 1, 0, args, kwds, _ABSENT)
    if usedforsecurity is not _ABSENT:
        bool(usedforsecurity)                    # the converter runs after the parsing
    if string is not _ABSENT:                    # an explicit None counts as given: the C warns, then hashes it
        if data is not _ABSENT:
            raise TypeError("'data' and 'string' are mutually exclusive and support for 'string' keyword parameter is slated for "
                            "removal in a future version.")
        _bella_refuse("the 'string' keyword parameter of " + name + "() (3.15 warns of its removal)")
    if data is _ABSENT:
        return None
    return _buffer(data)


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


class sha1:  # noqa: N801                       # _sha1.sha1, the type SHA1Type names
    __slots__ = ("_state",)

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided string."""
        if kwds:
            raise TypeError("sha1.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("sha1.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("sha1.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("sha1.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> sha1:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: sha1 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha1"

    @property
    def digest_size(self) -> int:
        return 20

    @property
    def block_size(self) -> int:
        return 64


SHA1Type = sha1


def _sha1_new(*args: object, **kwds: object) -> sha1:
    """Return a new SHA1 hash object; optionally initialized with a string."""
    data = _constructor_args("sha1", args, kwds)
    self: sha1 = _bella_new_instance(SHA1Type)
    self._state = _hash_new("sha1", None)
    if data is not None:
        self._state = _hash_update(self._state, data)
    return self


_sha1_new.__name__ = "sha1"
_sha1_new.__qualname__ = "sha1"
sha1 = _sha1_new  # type: ignore[assignment,misc]
