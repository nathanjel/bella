"""_sha2, in Python (Modules/sha2module.c) over the runtime's digests (hashes.cpp, written from FIPS 180-4): sha224, sha256, sha384
and sha512 with 3.15's data, usedforsecurity and string parameters, and the four types with update, digest, hexdigest, copy, name,
digest_size and block_size, each message the C's. A hash's state travels as bytes, so copy() copies bytes."""

__all__ = ["SHA224Type", "SHA256Type", "SHA384Type", "SHA512Type", "_GIL_MINSIZE", "sha224", "sha256", "sha384", "sha512"]

__name__ = "_sha2"

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


class SHA224Type:                               # _sha2.SHA224Type, what sha224() makes
    __slots__ = ("_state",)

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided string."""
        if kwds:
            raise TypeError("SHA224Type.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("SHA224Type.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("SHA224Type.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("SHA224Type.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> SHA224Type:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: SHA224Type = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha224"

    @property
    def digest_size(self) -> int:
        return 28

    @property
    def block_size(self) -> int:
        return 64


def sha224(*args: object, **kwds: object) -> SHA224Type:
    """Return a new SHA-224 hash object; optionally initialized with a string."""
    data = _constructor_args("sha224", args, kwds)
    self: SHA224Type = _bella_new_instance(SHA224Type)
    self._state = _hash_new("sha224", None)
    if data is not None:
        self._state = _hash_update(self._state, data)
    return self


class SHA256Type:                               # _sha2.SHA256Type, what sha256() makes
    __slots__ = ("_state",)

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided string."""
        if kwds:
            raise TypeError("SHA256Type.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("SHA256Type.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("SHA256Type.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("SHA256Type.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> SHA256Type:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: SHA256Type = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha256"

    @property
    def digest_size(self) -> int:
        return 32

    @property
    def block_size(self) -> int:
        return 64


def sha256(*args: object, **kwds: object) -> SHA256Type:
    """Return a new SHA-256 hash object; optionally initialized with a string."""
    data = _constructor_args("sha256", args, kwds)
    self: SHA256Type = _bella_new_instance(SHA256Type)
    self._state = _hash_new("sha256", None)
    if data is not None:
        self._state = _hash_update(self._state, data)
    return self


class SHA384Type:                               # _sha2.SHA384Type, what sha384() makes
    __slots__ = ("_state",)

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided string."""
        if kwds:
            raise TypeError("SHA384Type.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("SHA384Type.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("SHA384Type.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("SHA384Type.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> SHA384Type:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: SHA384Type = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha384"

    @property
    def digest_size(self) -> int:
        return 48

    @property
    def block_size(self) -> int:
        return 128


def sha384(*args: object, **kwds: object) -> SHA384Type:
    """Return a new SHA-384 hash object; optionally initialized with a string."""
    data = _constructor_args("sha384", args, kwds)
    self: SHA384Type = _bella_new_instance(SHA384Type)
    self._state = _hash_new("sha384", None)
    if data is not None:
        self._state = _hash_update(self._state, data)
    return self


class SHA512Type:                               # _sha2.SHA512Type, what sha512() makes
    __slots__ = ("_state",)

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided string."""
        if kwds:
            raise TypeError("SHA512Type.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("SHA512Type.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("SHA512Type.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("SHA512Type.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> SHA512Type:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: SHA512Type = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha512"

    @property
    def digest_size(self) -> int:
        return 64

    @property
    def block_size(self) -> int:
        return 128


def sha512(*args: object, **kwds: object) -> SHA512Type:
    """Return a new SHA-512 hash object; optionally initialized with a string."""
    data = _constructor_args("sha512", args, kwds)
    self: SHA512Type = _bella_new_instance(SHA512Type)
    self._state = _hash_new("sha512", None)
    if data is not None:
        self._state = _hash_update(self._state, data)
    return self
