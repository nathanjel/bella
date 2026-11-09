"""_hmac, in Python (Modules/hmacmodule.c, the HACL* HMAC module) over the runtime's digests (hashes.cpp): new(key, msg, digestmod)
and the HMAC type with update, digest, hexdigest, copy, name, digest_size and block_size; the one-shot compute_digest and the
compute_<algorithm> functions; UnknownHashError. HMAC itself is RFC 2104 over the digest's block, in Python."""

__all__ = ["HMAC", "UnknownHashError", "_GIL_MINSIZE", "compute_blake2b_32", "compute_blake2s_32", "compute_digest", "compute_md5",
           "compute_sha1", "compute_sha224", "compute_sha256", "compute_sha384", "compute_sha3_224", "compute_sha3_256",
           "compute_sha3_384", "compute_sha3_512", "compute_sha512", "new"]

__name__ = "_hmac"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
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
    _keyword_suggestion: Callable[..., str | None] = _missing
    _hash_new: Callable[..., bytes] = _missing
    _hash_update: Callable[..., bytes] = _missing
    _hash_digest: Callable[..., bytes] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__
    _unpack_keywords: Callable[..., Any] = _missing

_GIL_MINSIZE = 2048
_ABSENT: object = object()


class UnknownHashError(ValueError):
    pass


UnknownHashError.__module__ = "_hmac"

# algorithm -> (digest size, block size); blake2 only in the one-shots, as the C has it (its HMAC uses the full 64 or 32 bytes)
_DIGESTS: dict[str, tuple[int, int]] = {"md5": (16, 64), "sha1": (20, 64), "sha224": (28, 64), "sha256": (32, 64), "sha384": (48, 128),
                                        "sha512": (64, 128), "sha3_224": (28, 144), "sha3_256": (32, 136), "sha3_384": (48, 104),
                                        "sha3_512": (64, 72)}
_BLAKE2: dict[str, tuple[int, int]] = {"blake2b": (64, 128), "blake2s": (32, 64)}


def _buffer(value: object) -> bytes:             # GET_BUFFER_VIEW_OR_ERROUT
    if issubclass(type(value), str):
        raise TypeError("Strings must be encoded before hashing")
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("object supporting the buffer API required")


def _algorithm(digestmod: object, allow_blake2: bool) -> str:   # find_hash_info: a known name (case does not matter), else the error
    if issubclass(type(digestmod), str):
        name = str.lower(digestmod)  # type: ignore[arg-type]
        if name in _DIGESTS:
            return name
        if name in _BLAKE2:
            if allow_blake2:
                return name
            raise ValueError("invalid HACL* algorithm")
    raise UnknownHashError("unsupported hash algorithm " + (str(digestmod) if issubclass(type(digestmod), str) else repr(digestmod)))


def _digest_of(name: str) -> tuple[int, int]:
    return _DIGESTS[name] if name in _DIGESTS else _BLAKE2[name]


def _params(name: str) -> object:
    if name in _BLAKE2:
        return (_BLAKE2[name][0], b"", b"", b"", 1, 1, 0, b"\x00" * 8, 0, 0, False)
    return None


def _hash(name: str, data: bytes) -> bytes:
    return _hash_digest(_hash_update(_hash_new(name, _params(name)), data))


def _hmac_start(name: str, key: bytes) -> tuple[bytes, bytes]:   # RFC 2104: the inner state after the key block, the outer key block
    _, block = _digest_of(name)
    if len(key) > block:
        key = _hash(name, key)
    key = key + b"\x00" * (block - len(key))
    inner = _hash_update(_hash_new(name, _params(name)), bytes(k ^ 0x36 for k in key))
    outer = bytes(k ^ 0x5C for k in key)
    return inner, outer


def _hmac_finish(name: str, inner: bytes, outer: bytes) -> bytes:
    return _hash(name, outer + _hash_digest(inner))


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


class HMAC:                                      # _hmac.HMAC: made by new() alone
    __slots__ = ("_inner", "_name", "_outer")

    def update(self, *args: object, **kwds: object) -> None:
        """Update the HMAC object with the given message."""
        nargs = len(args) + len(kwds)
        if nargs > 1:
            raise TypeError("update() takes at most 1 argument (" + str(nargs) + " given)")
        if kwds:
            if "msg" not in kwds:                # the required argument is missing before the keyword is unexpected
                raise TypeError("update() missing required argument 'msg' (pos 1)")
            msg = kwds["msg"]
        elif args:
            msg = args[0]
        else:
            raise TypeError("update() missing required argument 'msg' (pos 1)")
        self._inner = _hash_update(self._inner, _buffer(msg))

    def digest(self, *args: object, **kwds: object) -> bytes:
        """Return the digest of the bytes passed to the update() method so far."""
        _no_args("HMAC.digest", args, kwds)
        return _hmac_finish(self._name, self._inner, self._outer)

    def hexdigest(self, *args: object, **kwds: object) -> str:
        """Return hexadecimal digest of the bytes passed to the update() method so far.

This may be used to exchange the value safely in email or other non-binary
environments."""
        _no_args("HMAC.hexdigest", args, kwds)
        return bytes.hex(_hmac_finish(self._name, self._inner, self._outer))

    def copy(self, *args: object, **kwds: object) -> HMAC:
        """Return a copy ("clone") of the HMAC object."""
        if kwds or args:
            raise TypeError("copy() takes no arguments")
        other: HMAC = _bella_new_instance(type(self))
        other._name = self._name
        other._inner = self._inner
        other._outer = self._outer
        return other

    def __repr__(self) -> str:
        return "<" + self._name + " HMAC object @ " + hex(id(self)) + ">"

    @property
    def name(self) -> str:
        return "hmac-" + self._name

    @property
    def digest_size(self) -> int:
        return _digest_of(self._name)[0]

    @property
    def block_size(self) -> int:
        return _digest_of(self._name)[1]


HMAC.__module__ = "_hmac"


def new(*args: object, **kwds: object) -> HMAC:
    """Return a new HMAC object."""
    values = _unpack_keywords("new", ("key", "msg", "digestmod"), 0, 1, 3, 0, args, kwds, _ABSENT)
    key, msg, digestmod = values
    if digestmod is _ABSENT:
        raise TypeError("new() missing 1 required argument 'digestmod'")
    name = _algorithm(digestmod, False)
    self: HMAC = _bella_new_instance(HMAC)
    self._name = name
    self._inner, self._outer = _hmac_start(name, _buffer(key))
    if msg is not _ABSENT and msg is not None:
        self._inner = _hash_update(self._inner, _buffer(msg))
    return self


def compute_digest(*args: object, **kwds: object) -> bytes:
    """Compute the HMAC-based digest of the given message using the given digest algorithm."""
    values = _unpack_keywords("compute_digest", ("key", "msg", "digest"), 0, 3, 3, 0, args, kwds, _ABSENT)
    key, msg, digest = values
    name = _algorithm(digest, True)
    return _one_shot(name, key, msg)


def _one_shot(name: str, key: object, msg: object) -> bytes:
    inner, outer = _hmac_start(name, _buffer(key))
    inner = _hash_update(inner, _buffer(msg))
    return _hmac_finish(name, inner, outer)


def _compute(fname: str, algorithm: str) -> object:
    def compute(*args: object, **kwds: object) -> bytes:
        if kwds:
            raise TypeError("_hmac." + fname + "() takes no keyword arguments")
        if len(args) != 2:
            raise TypeError(fname + " expected 2 arguments, got " + str(len(args)))
        return _one_shot(algorithm, args[0], args[1])
    compute.__name__ = compute.__qualname__ = fname
    compute.__doc__ = "Perform a one-shot HMAC-" + algorithm.upper() + " computation."
    return compute


compute_md5 = _compute("compute_md5", "md5")
compute_sha1 = _compute("compute_sha1", "sha1")
compute_sha224 = _compute("compute_sha224", "sha224")
compute_sha256 = _compute("compute_sha256", "sha256")
compute_sha384 = _compute("compute_sha384", "sha384")
compute_sha512 = _compute("compute_sha512", "sha512")
compute_sha3_224 = _compute("compute_sha3_224", "sha3_224")
compute_sha3_256 = _compute("compute_sha3_256", "sha3_256")
compute_sha3_384 = _compute("compute_sha3_384", "sha3_384")
compute_sha3_512 = _compute("compute_sha3_512", "sha3_512")
compute_blake2b_32 = _compute("compute_blake2b_32", "blake2b")
compute_blake2s_32 = _compute("compute_blake2s_32", "blake2s")
