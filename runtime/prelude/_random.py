"""_random, in Python (Modules/_randommodule.c): the Mersenne Twister (MT19937, Matsumoto and Nishimura's init_genrand, init_by_array
and genrand_int32 as the C has them, on 624 words kept as Python ints), the Random type with random (53 bits from two words), seed
(an int's absolute value or an object's hash, split into 32-bit words from the right; None takes 2496 bytes of the system's entropy),
getstate, setstate and getrandbits, each with the C's conversions and messages. random.Random subclasses it."""

__all__ = ["Random"]

__name__ = "_random"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _sys                                         # noqa: B018  # posix.cpp: the system calls by name (urandom)
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)

    def _sys(name: str, *args: object) -> Any:
        import os
        return getattr(os, name)(*args)


_N = 624
_M = 397
_MATRIX_A = 0x9908B0DF
_UPPER_MASK = 0x80000000
_LOWER_MASK = 0x7FFFFFFF
_MASK32 = 0xFFFFFFFF
_ABSENT: object = object()


def _init_genrand(mt: list[int], s: int) -> None:   # init_genrand
    mt[0] = s & _MASK32
    for i in range(1, _N):
        prev = mt[i - 1]
        mt[i] = (1812433253 * (prev ^ (prev >> 30)) + i) & _MASK32


def _init_by_array(self: Random, key: list[int]) -> None:   # init_by_array
    mt = self._state
    _init_genrand(mt, 19650218)
    i, j = 1, 0
    length = len(key)
    for _ in range(max(_N, length)):
        prev = mt[i - 1]
        mt[i] = ((mt[i] ^ ((prev ^ (prev >> 30)) * 1664525)) + key[j] + j) & _MASK32
        i += 1
        j += 1
        if i >= _N:
            mt[0] = mt[_N - 1]
            i = 1
        if j >= length:
            j = 0
    for _ in range(_N - 1):
        prev = mt[i - 1]
        mt[i] = ((mt[i] ^ ((prev ^ (prev >> 30)) * 1566083941)) - i) & _MASK32
        i += 1
        if i >= _N:
            mt[0] = mt[_N - 1]
            i = 1
    mt[0] = 0x80000000
    self._index = _N


def _genrand_uint32(self: Random) -> int:        # genrand_uint32
    mt = self._state
    if self._index >= _N:
        for kk in range(_N - _M):
            y = (mt[kk] & _UPPER_MASK) | (mt[kk + 1] & _LOWER_MASK)
            mt[kk] = mt[kk + _M] ^ (y >> 1) ^ (_MATRIX_A if y & 1 else 0)
        for kk in range(_N - _M, _N - 1):
            y = (mt[kk] & _UPPER_MASK) | (mt[kk + 1] & _LOWER_MASK)
            mt[kk] = mt[kk + _M - _N] ^ (y >> 1) ^ (_MATRIX_A if y & 1 else 0)
        y = (mt[_N - 1] & _UPPER_MASK) | (mt[0] & _LOWER_MASK)
        mt[_N - 1] = mt[_M - 1] ^ (y >> 1) ^ (_MATRIX_A if y & 1 else 0)
        self._index = 0
    y = mt[self._index]
    self._index += 1
    y ^= y >> 11
    y ^= (y << 7) & 0x9D2C5680
    y ^= (y << 15) & 0xEFC60000
    y ^= y >> 18
    return y & _MASK32


def _seed(self: Random, arg: object) -> None:    # random_seed
    if arg is None or arg is _ABSENT:
        data = _sys("urandom", 4 * _N)           # _PyOS_URandomNonblock; what fails there stops by name in posix.cpp
        _init_by_array(self, [int.from_bytes(data[4 * i:4 * i + 4], "little") for i in range(_N)])
        return
    if issubclass(type(arg), int):
        n = int.__abs__(arg)  # type: ignore[arg-type]   # int.__abs__, never a subclass's
    else:
        n = hash(arg) & 0xFFFFFFFFFFFFFFFF     # the hash as a size_t
    bits = int.bit_length(n)
    keyused = 1 if bits == 0 else (bits - 1) // 32 + 1
    _init_by_array(self, [(n >> (32 * i)) & _MASK32 for i in range(keyused)])


def _no_args(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


def _one_arg(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(qualname + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


class Random:
    """Random() -> create a random number generator with its own internal state."""

    __slots__ = ("_index", "_state")

    def __new__(cls, *args: object, **kwds: object) -> Random:   # PyType_GenericNew: zeroed, the arguments are __init__'s
        self: Random = _bella_new_instance(cls)
        self._state = [0] * _N
        self._index = 0
        return self

    def __init__(self, *args: object, **kwds: object) -> None:   # random_init: ($self, [seed])
        if kwds:
            raise TypeError("Random() takes no keyword arguments")
        if len(args) > 1:
            raise TypeError("Random expected at most 1 argument, got " + str(len(args)))
        _seed(self, args[0] if args else _ABSENT)

    def random(self, *args: object, **kwds: object) -> float:
        """random() -> x in the interval [0, 1)."""
        _no_args("Random.random", args, kwds)
        a = _genrand_uint32(self) >> 5
        b = _genrand_uint32(self) >> 6
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0)

    def seed(self, *args: object, **kwds: object) -> None:
        """seed([n]) -> None.

Defaults to use urandom and falls back to a combination
of the current time and the process identifier."""
        if kwds:
            raise TypeError("Random.seed() takes no keyword arguments")
        if len(args) > 1:
            raise TypeError("seed expected at most 1 argument, got " + str(len(args)))
        _seed(self, args[0] if args else None)

    def getstate(self, *args: object, **kwds: object) -> tuple[int, ...]:
        """getstate() -> tuple containing the current state."""
        _no_args("Random.getstate", args, kwds)
        return (*self._state, self._index)

    def setstate(self, *args: object, **kwds: object) -> None:
        """setstate(state) -> None.  Restores generator state."""
        state = _one_arg("Random.setstate", args, kwds)
        if not issubclass(type(state), tuple):
            raise TypeError("state vector must be a tuple")
        if tuple.__len__(state) != _N + 1:  # type: ignore[arg-type]
            raise ValueError("state vector is the wrong size")
        new_state: list[int] = []
        for i in range(_N):
            element = tuple.__getitem__(state, i)  # type: ignore[arg-type]  # PyTuple_GET_ITEM: the tuple's own items, whatever a subclass's __getitem__ says
            if not issubclass(type(element), int):   # PyLong_AsUnsignedLong
                raise TypeError("an integer is required")
            value = int.__index__(element)
            if value < 0:
                raise OverflowError("can't convert negative value to unsigned int")
            if value > 0xFFFFFFFFFFFFFFFF:
                raise OverflowError("Python int too large to convert to C unsigned long")
            new_state.append(value & _MASK32)
        index = _number_index(tuple.__getitem__(state, _N))  # type: ignore[arg-type]   # PyLong_AsLong
        if index > 0x7FFFFFFFFFFFFFFF or index < -0x8000000000000000:
            raise OverflowError("Python int too large to convert to C long")
        if index < 0 or index > _N:
            raise ValueError("invalid state")
        self._index = index
        self._state = new_state

    def getrandbits(self, *args: object, **kwds: object) -> int:
        """getrandbits(k) -> x.  Generates an int with k random bits."""
        arg = _one_arg("Random.getrandbits", args, kwds)
        k = _number_index(arg)                   # the clinic's uint64 converter
        if k < 0:
            raise ValueError("Cannot convert negative int")
        if k > 0xFFFFFFFFFFFFFFFF:
            raise OverflowError("Python int too large for C uint64_t")
        if k == 0:
            return 0
        if k <= 32:
            return _genrand_uint32(self) >> (32 - k)
        words = (k - 1) // 32 + 1
        if words > (2**63 - 1) // 4 or words * 4 >= 2**47:   # PyMem_Malloc fails: beyond PY_SSIZE_T_MAX / 4, or beyond the address space
            raise MemoryError
        result = 0
        shift = 0
        for _ in range(words):
            r = _genrand_uint32(self)
            if k < 32:
                r >>= 32 - k
            result |= r << shift
            shift += 32
            k -= 32
        return result


Random.__module__ = "_random"
