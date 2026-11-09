"""_blake2, in Python (Modules/blake2module.c) over the runtime's BLAKE2 (hashes.cpp, written from RFC 7693 with the tree parameters):
the blake2b and blake2s types, each its own constructor with every parameter of the parameter block and 3.15's data, usedforsecurity
and string; update, digest, hexdigest, copy, name, digest_size, block_size; the size constants on the types and the module."""

__all__ = ["BLAKE2B_MAX_DIGEST_SIZE", "BLAKE2B_MAX_KEY_SIZE", "BLAKE2B_PERSON_SIZE", "BLAKE2B_SALT_SIZE", "BLAKE2S_MAX_DIGEST_SIZE",
           "BLAKE2S_MAX_KEY_SIZE", "BLAKE2S_PERSON_SIZE", "BLAKE2S_SALT_SIZE", "_GIL_MINSIZE", "blake2b", "blake2s"]

__name__ = "_blake2"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _hash_new                                    # noqa: B018  # hashes.cpp: (algorithm, params) -> state bytes
    _hash_update                                 # noqa: B018  # (state, data) -> state
    _hash_digest                                 # noqa: B018  # (state) -> bytes
    _number_index                                # noqa: B018  # PyNumber_Index
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _hash_new: Callable[..., bytes] = _missing
    _hash_update: Callable[..., bytes] = _missing
    _hash_digest: Callable[..., bytes] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)
    _unpack_keywords: Callable[..., Any] = _missing

_GIL_MINSIZE = 2048
BLAKE2B_SALT_SIZE = 16
BLAKE2B_PERSON_SIZE = 16
BLAKE2B_MAX_KEY_SIZE = 64
BLAKE2B_MAX_DIGEST_SIZE = 64
BLAKE2S_SALT_SIZE = 8
BLAKE2S_PERSON_SIZE = 8
BLAKE2S_MAX_KEY_SIZE = 32
BLAKE2S_MAX_DIGEST_SIZE = 32
_ABSENT: object = object()
_PARAMETERS = ("data", "digest_size", "key", "salt", "person", "fanout", "depth", "leaf_size", "node_offset", "node_depth", "inner_size",
               "last_node", "usedforsecurity", "string")


def _buffer(value: object) -> bytes:             # the data: GET_BUFFER_VIEW_OR_ERROUT
    if issubclass(type(value), str):
        raise TypeError("Strings must be encoded before hashing")
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("object supporting the buffer API required")


def _py_buffer(value: object) -> bytes:          # key, salt, person: the clinic's Py_buffer
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")


_index = _number_index                           # PyNumber_Index: the runtime's, with its messages (review G15 #6)


def _c_int(value: object) -> int:                # the clinic's int
    n = _index(value)
    if n > 2**31 - 1:
        raise OverflowError("Python int too large to convert to C int")
    if n < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return n


def _unsigned(value: object, what: str) -> int:  # _PyLong_UnsignedLong_Converter / _PyLong_UnsignedLongLong_Converter
    n = _index(value)
    if n < 0:
        raise ValueError("Cannot convert negative int")
    if n >= 2**64:
        raise OverflowError("Python int too large for C unsigned long" + ("" if what == "leaf_size" else " long"))
    return n


def _new(name: str, cls: type, args: tuple[object, ...], kwds: dict[str, object], max_digest: int, max_key: int, salt_size: int,
         max_offset: int) -> object:
    """py_blake2b_or_s_new: the parameters checked in the C's order, the state made, the data hashed."""
    values = _unpack_keywords(name, _PARAMETERS, 0, 0, 1, 0, args, kwds, _ABSENT)
    given: dict[str, object] = {parameter: value for parameter, value in zip(_PARAMETERS, values, strict=True) if value is not _ABSENT}
    digest_size = _c_int(given["digest_size"]) if "digest_size" in given else max_digest
    key = _py_buffer(given["key"]) if "key" in given else b""
    salt = _py_buffer(given["salt"]) if "salt" in given else b""
    person = _py_buffer(given["person"]) if "person" in given else b""
    fanout = _c_int(given["fanout"]) if "fanout" in given else 1
    depth = _c_int(given["depth"]) if "depth" in given else 1
    leaf_size = _unsigned(given["leaf_size"], "leaf_size") if "leaf_size" in given else 0
    node_offset = _unsigned(given["node_offset"], "node_offset") if "node_offset" in given else 0
    node_depth = _c_int(given["node_depth"]) if "node_depth" in given else 0
    inner_size = _c_int(given["inner_size"]) if "inner_size" in given else 0
    last_node = bool(given["last_node"]) if "last_node" in given else False
    if "usedforsecurity" in given:
        bool(given["usedforsecurity"])
    string = given.get("string", _ABSENT)
    data = given.get("data", _ABSENT)
    if string is not _ABSENT:                    # an explicit None counts as given: the C warns, then hashes it
        if data is not _ABSENT:
            raise TypeError("'data' and 'string' are mutually exclusive and support for 'string' keyword parameter is slated for "
                            "removal in a future version.")
        _bella_refuse("the 'string' keyword parameter of " + name + "() (3.15 warns of its removal)")
    if digest_size <= 0 or digest_size > max_digest:
        raise ValueError("digest_size for " + name + " must be between 1 and " + str(max_digest) + " bytes, got " + str(digest_size))
    if len(key) > max_key:
        raise ValueError("maximum key length is " + str(max_key) + " bytes, got " + str(len(key)))
    if len(salt) > salt_size:
        raise ValueError("maximum salt length is " + str(salt_size) + " bytes, got " + str(len(salt)))
    if len(person) > salt_size:
        raise ValueError("maximum person length is " + str(salt_size) + " bytes, got " + str(len(person)))
    if fanout < 0 or fanout > 255:
        raise ValueError("'fanout' must be between 0 and 255")
    if depth < 1 or depth > 255:
        raise ValueError("'depth' must be between 1 and 255")
    if node_depth < 0 or node_depth > 255:
        raise ValueError("'node_depth' must be between 0 and 255")
    if inner_size < 0 or inner_size > max_digest:
        raise ValueError("'inner_size' must be between 0 and " + str(max_digest))
    if leaf_size > 2**32 - 1:
        raise OverflowError("'leaf_size' is too large")
    if node_offset > max_offset:
        raise OverflowError("'node_offset' is too large")
    self = _bella_new_instance(cls)
    params = (digest_size, key, salt, person, fanout, depth, leaf_size, int.to_bytes(node_offset, 8, "little"), node_depth, inner_size, last_node)
    object.__setattr__(self, "_state", _hash_new(name, params))
    object.__setattr__(self, "_size", digest_size)
    if data is not _ABSENT:
        object.__setattr__(self, "_state", _hash_update(self._state, _buffer(data)))  # type: ignore[attr-defined]
    return self


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


class blake2b:  # noqa: N801
    """Return a new BLAKE2b hash object."""

    __slots__ = ("_size", "_state")
    SALT_SIZE = 16
    PERSON_SIZE = 16
    MAX_KEY_SIZE = 64
    MAX_DIGEST_SIZE = 64

    def __new__(cls, *args: object, **kwds: object) -> blake2b:
        return _new("blake2b", cls, args, kwds, 64, 64, 16, 2**64 - 1)  # type: ignore[return-value]

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("blake2b.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("blake2b.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("blake2b.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("blake2b.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> blake2b:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: blake2b = _bella_new_instance(type(self))
        other._state = self._state
        other._size = self._size
        return other

    @property
    def name(self) -> str:
        return "blake2b"

    @property
    def digest_size(self) -> int:
        return self._size

    @property
    def block_size(self) -> int:
        return 128


class blake2s:  # noqa: N801
    """Return a new BLAKE2s hash object."""

    __slots__ = ("_size", "_state")
    SALT_SIZE = 8
    PERSON_SIZE = 8
    MAX_KEY_SIZE = 32
    MAX_DIGEST_SIZE = 32

    def __new__(cls, *args: object, **kwds: object) -> blake2s:
        return _new("blake2s", cls, args, kwds, 32, 32, 8, 2**48 - 1)  # type: ignore[return-value]

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("blake2s.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("blake2s.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("blake2s.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("blake2s.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> blake2s:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: blake2s = _bella_new_instance(type(self))
        other._state = self._state
        other._size = self._size
        return other

    @property
    def name(self) -> str:
        return "blake2s"

    @property
    def digest_size(self) -> int:
        return self._size

    @property
    def block_size(self) -> int:
        return 64
