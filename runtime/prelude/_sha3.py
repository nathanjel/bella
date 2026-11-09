"""_sha3, in Python (Modules/sha3module.c) over the runtime's Keccak (hashes.cpp, written from FIPS 202): the six types, each its own
constructor with 3.15's data, usedforsecurity and string parameters; update, digest, hexdigest, copy, name, digest_size, block_size and
the three underscored facts; the two SHAKEs' digest(length) and hexdigest(length). The clinic names every constructor's errors
sha3_224(), as the C does."""

__all__ = ["_GIL_MINSIZE", "implementation", "sha3_224", "sha3_256", "sha3_384", "sha3_512", "shake_128", "shake_256"]

__name__ = "_sha3"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _hash_new                                    # noqa: B018  # hashes.cpp: (algorithm, params) -> state bytes
    _hash_update                                 # noqa: B018  # (state, data) -> state
    _hash_digest                                 # noqa: B018  # (state) -> bytes
    _hash_xof                                    # noqa: B018  # (state, length) -> bytes, SHAKE's
    _number_index                                # noqa: B018  # PyNumber_Index
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
    _hash_xof: Callable[..., bytes] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)
    _unpack_keywords: Callable[..., Any] = _missing

_GIL_MINSIZE = 2048
implementation = "HACL"
_ABSENT: object = object()


def _buffer(value: object) -> bytes:
    if issubclass(type(value), str):
        raise TypeError("Strings must be encoded before hashing")
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("object supporting the buffer API required")


def _constructor_args(args: tuple[object, ...], kwds: dict[str, object]) -> bytes | None:   # (data=b'', /, *, usedforsecurity=True, string=None)
    data, usedforsecurity, string = _unpack_keywords("sha3_224", ("data", "usedforsecurity", "string"), 0, 0, 1, 0, args, kwds, _ABSENT)
    if usedforsecurity is not _ABSENT:
        bool(usedforsecurity)                    # the converter runs after the parsing
    if string is not _ABSENT:                    # an explicit None counts as given: the C warns, then hashes it
        if data is not _ABSENT:
            raise TypeError("'data' and 'string' are mutually exclusive and support for 'string' keyword parameter is slated for "
                            "removal in a future version.")
        _bella_refuse("the 'string' keyword parameter of a sha3 constructor (3.15 warns of its removal)")
    if data is _ABSENT:
        return None
    return _buffer(data)


_index = _number_index                           # PyNumber_Index: the runtime's, with its messages (review G15 #6)


def _length_arg(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> int:   # the SHAKEs' (length, /)
    nargs = len(args) + len(kwds)
    if kwds:
        if nargs > 1:
            raise TypeError(name + "() takes at most 1 argument (" + str(nargs) + " given)")
        if "length" not in kwds:                 # the required argument is missing before the keyword is unexpected
            raise TypeError(name + "() missing required argument 'length' (pos 1)")
        value = kwds["length"]
    else:
        if nargs > 1:
            raise TypeError(name + "() takes at most 1 argument (" + str(nargs) + " given)")
        if nargs == 0:
            raise TypeError(name + "() missing required argument 'length' (pos 1)")
        value = args[0]
    n = _index(value)
    if n < -(2**63) or n > 2**63 - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if n < 0:
        raise ValueError("length cannot be negative")
    if n >= 2**29:                               # the HACL interface's limit
        raise OverflowError("digest length is too large")
    return n


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


class sha3_224:  # noqa: N801
    """sha3_224([data], *, usedforsecurity=True) -> SHA3 object

Return a new SHA3 hash object with a hashbit length of 28 bytes."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> sha3_224:
        data = _constructor_args(args, kwds)
        self: sha3_224 = _bella_new_instance(cls)
        self._state = _hash_new("sha3_224", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("sha3_224.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("sha3_224.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("sha3_224.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("sha3_224.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> sha3_224:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: sha3_224 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha3_224"

    @property
    def digest_size(self) -> int:
        return 28

    @property
    def block_size(self) -> int:
        return 144

    @property
    def _capacity_bits(self) -> int:
        return 448

    @property
    def _rate_bits(self) -> int:
        return 1152

    @property
    def _suffix(self) -> bytes:
        return b"\x06"


class sha3_256:  # noqa: N801
    """sha3_256([data], *, usedforsecurity=True) -> SHA3 object

Return a new SHA3 hash object with a hashbit length of 32 bytes."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> sha3_256:
        data = _constructor_args(args, kwds)
        self: sha3_256 = _bella_new_instance(cls)
        self._state = _hash_new("sha3_256", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("sha3_256.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("sha3_256.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("sha3_256.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("sha3_256.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> sha3_256:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: sha3_256 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha3_256"

    @property
    def digest_size(self) -> int:
        return 32

    @property
    def block_size(self) -> int:
        return 136

    @property
    def _capacity_bits(self) -> int:
        return 512

    @property
    def _rate_bits(self) -> int:
        return 1088

    @property
    def _suffix(self) -> bytes:
        return b"\x06"


class sha3_384:  # noqa: N801
    """sha3_384([data], *, usedforsecurity=True) -> SHA3 object

Return a new SHA3 hash object with a hashbit length of 48 bytes."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> sha3_384:
        data = _constructor_args(args, kwds)
        self: sha3_384 = _bella_new_instance(cls)
        self._state = _hash_new("sha3_384", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("sha3_384.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("sha3_384.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("sha3_384.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("sha3_384.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> sha3_384:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: sha3_384 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha3_384"

    @property
    def digest_size(self) -> int:
        return 48

    @property
    def block_size(self) -> int:
        return 104

    @property
    def _capacity_bits(self) -> int:
        return 768

    @property
    def _rate_bits(self) -> int:
        return 832

    @property
    def _suffix(self) -> bytes:
        return b"\x06"


class sha3_512:  # noqa: N801
    """sha3_512([data], *, usedforsecurity=True) -> SHA3 object

Return a new SHA3 hash object with a hashbit length of 64 bytes."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> sha3_512:
        data = _constructor_args(args, kwds)
        self: sha3_512 = _bella_new_instance(cls)
        self._state = _hash_new("sha3_512", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("sha3_512.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("sha3_512.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        _no_args("sha3_512.digest", args, kwds)
        return _hash_digest(self._state)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        _no_args("sha3_512.hexdigest", args, kwds)
        return bytes.hex(_hash_digest(self._state))

    def copy(self, *args: object, **kwds: object) -> sha3_512:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: sha3_512 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "sha3_512"

    @property
    def digest_size(self) -> int:
        return 64

    @property
    def block_size(self) -> int:
        return 72

    @property
    def _capacity_bits(self) -> int:
        return 1024

    @property
    def _rate_bits(self) -> int:
        return 576

    @property
    def _suffix(self) -> bytes:
        return b"\x06"


class shake_128:  # noqa: N801
    """shake_128([data], *, usedforsecurity=True) -> SHAKE object

Return a new SHAKE hash object."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> shake_128:
        data = _constructor_args(args, kwds)
        self: shake_128 = _bella_new_instance(cls)
        self._state = _hash_new("shake_128", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("shake_128.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("shake_128.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        return _hash_xof(self._state, _length_arg("digest", args, kwds))

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        return bytes.hex(_hash_xof(self._state, _length_arg("hexdigest", args, kwds)))

    def copy(self, *args: object, **kwds: object) -> shake_128:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: shake_128 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "shake_128"

    @property
    def digest_size(self) -> int:
        return 0

    @property
    def block_size(self) -> int:
        return 168

    @property
    def _capacity_bits(self) -> int:
        return 256

    @property
    def _rate_bits(self) -> int:
        return 1344

    @property
    def _suffix(self) -> bytes:
        return b"\x1f"


class shake_256:  # noqa: N801
    """shake_256([data], *, usedforsecurity=True) -> SHAKE object

Return a new SHAKE hash object."""

    __slots__ = ("_state",)

    def __new__(cls, *args: object, **kwds: object) -> shake_256:
        data = _constructor_args(args, kwds)
        self: shake_256 = _bella_new_instance(cls)
        self._state = _hash_new("shake_256", None)
        if data is not None:
            self._state = _hash_update(self._state, data)
        return self

    def update(self, *args: object, **kwds: object) -> None:
        """Update this hash object's state with the provided bytes-like object."""
        if kwds:
            raise TypeError("shake_256.update() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("shake_256.update() takes exactly one argument (" + str(len(args)) + " given)")
        self._state = _hash_update(self._state, _buffer(args[0]))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest value as a bytes object."""
        return _hash_xof(self._state, _length_arg("digest", args, kwds))

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        return bytes.hex(_hash_xof(self._state, _length_arg("hexdigest", args, kwds)))

    def copy(self, *args: object, **kwds: object) -> shake_256:
        """Return a copy of the hash object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: shake_256 = _bella_new_instance(type(self))
        other._state = self._state
        return other

    @property
    def name(self) -> str:
        return "shake_256"

    @property
    def digest_size(self) -> int:
        return 0

    @property
    def block_size(self) -> int:
        return 136

    @property
    def _capacity_bits(self) -> int:
        return 512

    @property
    def _rate_bits(self) -> int:
        return 1088

    @property
    def _suffix(self) -> bytes:
        return b"\x1f"
