"""_thread, in Python, for a runtime with one thread (spec section 7, the manifest's shim); see itertools.py beside it.

From Modules/_threadmodule.c, line by line, as far as one thread can tell: a lock the only thread holds has no one
to release it, so a timed acquire waits out its timeout and says no, and an untimed one would wait for ever, which
stops by name. Creating a thread stops by name too, with the milestone's (spec section 7): `threading` is [P2+].
An RLock's owner and a handle's ident are the thread's ident, as they are in the C.
"""

__all__ = ["LockType", "RLock", "TIMEOUT_MAX", "_ExceptHookArgs", "_NAME_MAXLEN", "_ThreadHandle", "_count", "_excepthook",
           "_get_main_thread_ident", "_get_name", "_is_main_interpreter", "_local", "_make_thread_handle", "_shutdown",
           "allocate", "allocate_lock", "daemon_threads_allowed", "error", "exit", "exit_thread", "get_ident", "get_native_id",
           "interrupt_main", "lock", "set_name", "stack_size", "start_joinable_thread", "start_new", "start_new_thread"]

__name__ = "_thread"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _sequence_check                              # noqa: B018  # PySequence_Check
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _thread_ident                                # noqa: B018  # PyThread_get_thread_ident_ex
    _native_thread_id                            # noqa: B018  # PyThread_get_thread_native_id
    _sleep_ns                                    # noqa: B018  # a wait no other thread can end
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
except NameError:
    from collections.abc import Callable
    from typing import Any, NoReturn

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _sequence_check: Callable[..., bool] = _missing
    _tp_name: Callable[..., str] = _missing
    _thread_ident: Callable[[], int] = _missing
    _native_thread_id: Callable[[], int] = _missing
    _sleep_ns: Callable[[int], None] = _missing

    def _bella_refuse(text: str) -> NoReturn:
        raise ImportError(text)

TIMEOUT_MAX = 9223372036.0
_NAME_MAXLEN = 15
error = RuntimeError

_TIMEOUT_UNSET = -1000000000                     # _PyTime_FromSeconds(-1)
_PY_TIMEOUT_MAX = 9223372036854775               # LLONG_MAX / 1000, in microseconds
_PYTIME_MIN = -(2**63)
_PYTIME_MAX = 2**63 - 1
_DEADLOCK = "a blocking wait on a lock no other thread can release (the threads milestone, [P2+])"
_ABSENT = object()


def _noargs(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


def _method(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, shown: str) -> tuple[object, ...]:
    """A method descriptor's checks of its receiver; what is left is its arguments."""
    if not args:
        raise TypeError("unbound method " + shown + "." + name + "() needs an argument")
    if not issubclass(type(args[0]), cls):
        raise TypeError("descriptor '" + name + "' for '" + cls.__module__ + "." + cls.__name__ + "' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
    return args[1:]


def _new_receiver(args: tuple[object, ...], owner: type, shown: str) -> None:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(shown + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(shown + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(shown + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + shown)  # type: ignore[attr-defined]


def _from_seconds(obj: object) -> int:           # _PyTime_FromSecondsObject, _PyTime_ROUND_TIMEOUT
    if hasattr(type(obj), "__index__"):          # PyIndex_Check
        ns = _number_index(obj) * 1000000000
        if not _PYTIME_MIN <= ns <= _PYTIME_MAX:
            raise OverflowError("timestamp out of range for C PyTime_t")
        return ns
    d = float.from_number(obj)                   # PyFloat_AsDouble
    if d != d:
        raise ValueError("Invalid value NaN (not a number)")
    d *= 1e9
    if not -9223372036854775808.0 <= d < 9223372036854775808.0:
        raise OverflowError("timestamp out of range for C PyTime_t")
    return d.__ceil__() if d >= 0 else d.__floor__()


def _parse_timeout(timeout: object, blocking: bool) -> int:   # lock_acquire_parse_timeout
    ns = _TIMEOUT_UNSET if timeout is _ABSENT else _from_seconds(timeout)
    if not blocking and ns != _TIMEOUT_UNSET:
        raise ValueError("can't specify a timeout for a non-blocking call")
    if ns < 0 and ns != _TIMEOUT_UNSET:
        raise ValueError("timeout value must be a non-negative number")
    if not blocking:
        return 0
    if ns != _TIMEOUT_UNSET and (ns + 999) // 1000 > _PY_TIMEOUT_MAX:   # _PyTime_AsMicroseconds, rounded up
        raise OverflowError("timeout value is too large")
    return ns


def _acquire_arguments(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[bool, object]:
    """acquire(blocking=True, timeout=-1)'s clinic: _PyArg_UnpackKeywords."""
    total = len(args) + len(kwds)
    if total > 2:
        raise TypeError(name + "() takes at most 2 " + ("" if args else "keyword ") + "arguments (" + str(total) + " given)")
    blocking, timeout = True, _ABSENT
    if args:
        blocking = args[0]  # type: ignore[assignment]
    if len(args) > 1:
        timeout = args[1]
    for key, value in kwds.items():
        if key == "blocking":
            if args:
                raise TypeError("argument for " + name + "() given by name ('blocking') and position (1)")
            blocking = value  # type: ignore[assignment]
        elif key == "timeout":
            if len(args) > 1:
                raise TypeError("argument for " + name + "() given by name ('timeout') and position (2)")
            timeout = value
        else:
            raise TypeError(name + "() got an unexpected keyword argument '" + key + "'")
    return bool(blocking), timeout


def _wait_in_vain(ns: int) -> bool:              # a wait that nothing can end: its timeout, then no
    if ns == _TIMEOUT_UNSET:
        _bella_refuse(_DEADLOCK)
    if ns > 0:
        _sleep_ns(ns)
    return False


def _exit_arguments(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    if kwds:
        raise TypeError(qualname + ".__exit__() takes no keyword arguments")
    if len(args) != 3:
        raise TypeError("__exit__ expected 3 arguments, got " + str(len(args)))


class lock:
    __slots__ = ("_a_locked", "__weakref__")

    def __new__(*args: object, **kwds: object) -> lock:   # lock_new
        _new_receiver(args, lock, "_thread.lock")
        cls, args = args[0], args[1:]
        if kwds:
            raise TypeError("lock() takes no keyword arguments")
        if args:
            raise TypeError("lock() takes no positional arguments")
        self = object.__new__(cls)
        self._a_locked = False
        return self

    def __repr__(*args: object, **kwds: object) -> str:
        self = args[0]
        return "<" + ("locked" if self._a_locked else "unlocked") + " _thread.lock object at " + hex(id(self)) + ">"  # type: ignore[attr-defined]

    def acquire(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, lock, "acquire", "lock")
        return _lock_acquire("acquire", args[0], rest, kwds)

    def acquire_lock(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, lock, "acquire_lock", "lock")
        return _lock_acquire("acquire_lock", args[0], rest, kwds)

    def release(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, lock, "release", "lock")
        _noargs("lock.release", rest, kwds)
        _lock_release(args[0])

    def release_lock(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, lock, "release_lock", "lock")
        _noargs("lock.release_lock", rest, kwds)
        _lock_release(args[0])

    def locked(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, lock, "locked", "lock")
        _noargs("lock.locked", rest, kwds)
        return args[0]._a_locked  # type: ignore[attr-defined]

    def locked_lock(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, lock, "locked_lock", "lock")
        _noargs("lock.locked_lock", rest, kwds)
        return args[0]._a_locked  # type: ignore[attr-defined]

    def __enter__(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, lock, "__enter__", "lock")
        _noargs("lock.__enter__", rest, kwds)
        return _lock_acquire("acquire", args[0], (), {})

    def __exit__(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, lock, "__exit__", "lock")
        _exit_arguments("lock", rest, kwds)
        _lock_release(args[0])

    def _at_fork_reinit(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, lock, "_at_fork_reinit", "lock")
        _noargs("lock._at_fork_reinit", rest, kwds)
        args[0]._a_locked = False  # type: ignore[attr-defined]


LockType = lock


def _lock_acquire(name: str, self: object, args: tuple[object, ...], kwds: dict[str, object]) -> bool:
    blocking, timeout = _acquire_arguments(name, args, kwds)
    ns = _parse_timeout(timeout, blocking)
    if not self._a_locked:  # type: ignore[attr-defined]
        self._a_locked = True  # type: ignore[attr-defined]
        return True
    return _wait_in_vain(ns)


def _lock_release(self: object) -> None:
    if not self._a_locked:  # type: ignore[attr-defined]
        raise RuntimeError("release unlocked lock")
    self._a_locked = False  # type: ignore[attr-defined]


class RLock:
    __slots__ = ("_a_owner", "_b_count", "__weakref__")

    def __new__(*args: object, **kwds: object) -> RLock:   # rlock_new
        _new_receiver(args, RLock, "_thread.RLock")
        cls, args = args[0], args[1:]
        if kwds:
            raise TypeError("RLock() takes no keyword arguments")
        if args:
            raise TypeError("RLock() takes no positional arguments")
        self = object.__new__(cls)
        self._a_owner = 0
        self._b_count = 0
        return self

    def __repr__(*args: object, **kwds: object) -> str:
        self = args[0]
        count = self._b_count  # type: ignore[attr-defined]
        return ("<" + ("locked " if count else "unlocked ") + _tp_name(self) + " object owner=" + str(self._a_owner if count else 0)  # type: ignore[attr-defined]
                + " count=" + str(count) + " at " + hex(id(self)) + ">")

    def acquire(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, RLock, "acquire", "RLock")
        blocking, timeout = _acquire_arguments("acquire", rest, kwds)
        return _rlock_acquire(args[0], _parse_timeout(timeout, blocking))

    def release(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, RLock, "release", "RLock")
        _noargs("RLock.release", rest, kwds)
        _rlock_release(args[0])

    def __enter__(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, RLock, "__enter__", "RLock")
        _noargs("RLock.__enter__", rest, kwds)
        return _rlock_acquire(args[0], _TIMEOUT_UNSET)

    def __exit__(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, RLock, "__exit__", "RLock")
        _exit_arguments("RLock", rest, kwds)
        _rlock_release(args[0])

    def locked(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, RLock, "locked", "RLock")
        _noargs("RLock.locked", rest, kwds)
        return args[0]._b_count != 0  # type: ignore[attr-defined]

    def _is_owned(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, RLock, "_is_owned", "RLock")
        _noargs("RLock._is_owned", rest, kwds)
        return _rlock_owned(args[0])

    def _recursion_count(*args: object, **kwds: object) -> int:
        rest = _method(args, kwds, RLock, "_recursion_count", "RLock")
        _noargs("RLock._recursion_count", rest, kwds)
        return args[0]._b_count if _rlock_owned(args[0]) else 0  # type: ignore[attr-defined]

    def _release_save(*args: object, **kwds: object) -> tuple[int, int]:
        rest = _method(args, kwds, RLock, "_release_save", "RLock")
        _noargs("RLock._release_save", rest, kwds)
        self = args[0]
        if not _rlock_owned(self):
            raise RuntimeError("cannot release un-acquired lock")
        state = self._b_count, self._a_owner  # type: ignore[attr-defined]
        self._b_count = 0  # type: ignore[attr-defined]
        return state

    def _acquire_restore(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, RLock, "_acquire_restore", "RLock")
        if kwds:
            raise TypeError("RLock._acquire_restore() takes no keyword arguments")
        if len(rest) != 1:
            raise TypeError("RLock._acquire_restore() takes exactly one argument (" + str(len(rest)) + " given)")
        state = rest[0]
        if issubclass(type(state), tuple):       # PyArg_Parse's "(nK)": converttuple
            if len(state) != 2:  # type: ignore[arg-type]
                raise TypeError("_acquire_restore() argument must be tuple of length 2, not " + str(len(state)))  # type: ignore[arg-type]
        else:
            if not _sequence_check(state) or issubclass(type(state), (str, bytes, bytearray)):
                raise TypeError("_acquire_restore() argument must be 2-item tuple, not " + ("None" if state is None else _tp_name(state)))
            if len(state) != 2:  # type: ignore[arg-type]
                raise TypeError("_acquire_restore() argument must be sequence of length 2, not " + str(len(state)))  # type: ignore[arg-type]
            state = tuple(state)  # type: ignore[arg-type]
        count = _number_index(state[0])  # type: ignore[index]
        if not -(2**63) <= count < 2**63:
            raise OverflowError("Python int too large to convert to C ssize_t")
        owner = state[1]  # type: ignore[index]
        if not issubclass(type(owner), int):
            raise TypeError("_acquire_restore() argument 2 must be int, not " + type(owner).__name__)
        self = args[0]
        if self._b_count and not _rlock_owned(self):  # type: ignore[attr-defined]
            _bella_refuse(_DEADLOCK)
        if count < 1:
            _bella_refuse("RLock._acquire_restore with a count below 1")
        self._a_owner = int.__index__(owner) & 0xFFFFFFFFFFFFFFFF  # type: ignore[attr-defined]
        self._b_count = count  # type: ignore[attr-defined]

    def _at_fork_reinit(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, RLock, "_at_fork_reinit", "RLock")
        _noargs("RLock._at_fork_reinit", rest, kwds)
        args[0]._b_count = 0  # type: ignore[attr-defined]


def _rlock_owned(self: object) -> bool:
    return self._b_count != 0 and self._a_owner == _thread_ident()  # type: ignore[attr-defined]


def _rlock_acquire(self: object, ns: int) -> bool:   # _PyRecursiveMutex_LockTimed
    if self._b_count == 0:  # type: ignore[attr-defined]
        self._a_owner = _thread_ident()  # type: ignore[attr-defined]
        self._b_count = 1  # type: ignore[attr-defined]
        return True
    if self._a_owner == _thread_ident():  # type: ignore[attr-defined]
        self._b_count += 1  # type: ignore[attr-defined]
        return True
    return _wait_in_vain(ns)


def _rlock_release(self: object) -> None:        # _PyRecursiveMutex_TryUnlock
    if not _rlock_owned(self):
        raise RuntimeError("cannot release un-acquired lock")
    self._b_count -= 1  # type: ignore[attr-defined]


class _local:                                    # one thread has one dict, the instance's; local_getattro is the runtime's
    """Thread-local data."""

    __slots__ = ("_a_self_reference", "__dict__", "__weakref__")

    def __new__(*args: object, **kwds: object) -> _local:   # local_new
        _new_receiver(args, _local, "_thread._local")
        cls, args = args[0], args[1:]
        if cls.__init__ is object.__init__ and (args or kwds):
            raise TypeError("Initialization arguments are not supported")
        from _weakref import ref
        self = object.__new__(cls)
        _local_slot.__set__(self, ref(self))     # the reference local_new's dummy keeps: a program can count it
        return self

    def __setattr__(self, name: str, value: object) -> None:   # local_setattro
        if name == "__dict__":
            raise AttributeError("'" + _tp_name(self) + "' object attribute '__dict__' is read-only")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name == "__dict__":
            raise AttributeError("'" + _tp_name(self) + "' object attribute '__dict__' is read-only")
        object.__delattr__(self, name)


_local_slot = vars(_local)["_a_self_reference"]   # out of the class's namespace after this, as the C has no such member

_NOT_STARTED = 0
_RUNNING = 1
_DONE = 2


class _ThreadHandle:
    __slots__ = ("_a_ident", "_b_state")

    def __new__(*args: object, **kwds: object) -> _ThreadHandle:
        _new_receiver(args, _ThreadHandle, "_thread._ThreadHandle")
        cls, args = args[0], args[1:]
        self = object.__new__(cls)
        self._a_ident = 0
        self._b_state = _NOT_STARTED
        return self

    def __repr__(*args: object, **kwds: object) -> str:
        return "<" + _tp_name(args[0]) + " object: ident=" + str(args[0]._a_ident) + ">"  # type: ignore[attr-defined]

    def is_done(*args: object, **kwds: object) -> bool:
        rest = _method(args, kwds, _ThreadHandle, "is_done", "_ThreadHandle")
        _noargs("_ThreadHandle.is_done", rest, kwds)
        return args[0]._b_state == _DONE  # type: ignore[attr-defined]

    def _set_done(*args: object, **kwds: object) -> None:
        rest = _method(args, kwds, _ThreadHandle, "_set_done", "_ThreadHandle")
        _noargs("_ThreadHandle._set_done", rest, kwds)
        if args[0]._b_state == _NOT_STARTED:  # type: ignore[attr-defined]
            raise RuntimeError("thread not started")
        args[0]._b_state = _DONE  # type: ignore[attr-defined]

    def join(*args: object, **kwds: object) -> None:   # PyThreadHandleObject_join, ThreadHandle_join
        rest = _method(args, kwds, _ThreadHandle, "join", "_ThreadHandle")
        if kwds:
            raise TypeError("_ThreadHandle.join() takes no keyword arguments")
        if len(rest) > 1:
            raise TypeError("join() takes at most 1 argument (" + str(len(rest)) + " given)")
        ns = _TIMEOUT_UNSET
        if rest and rest[0] is not None:
            ns = _from_seconds(rest[0])
            if ns < 0:                           # a negative timeout means "wait forever"
                ns = _TIMEOUT_UNSET
        self = args[0]
        if self._b_state == _NOT_STARTED:  # type: ignore[attr-defined]
            raise RuntimeError("thread not started")
        if self._b_state == _DONE:  # type: ignore[attr-defined]
            return
        if self._a_ident == _thread_ident():  # type: ignore[attr-defined]
            raise RuntimeError("Cannot join current thread")
        _wait_in_vain(ns)


class _ExceptHookArgs:
    def __new__(cls, *args: object, **kwds: object) -> _ExceptHookArgs:
        _bella_refuse("_thread._ExceptHookArgs, a struct sequence (the threads milestone, [P2+])")


def _make_thread_handle(*args: object, **kwds: object) -> _ThreadHandle:
    if kwds:
        raise TypeError("_thread._make_thread_handle() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_thread._make_thread_handle() takes exactly one argument (" + str(len(args)) + " given)")
    if not issubclass(type(args[0]), int):
        raise TypeError("ident must be an integer")
    ident = int.__index__(args[0])  # type: ignore[arg-type]
    if ident < 0:
        raise OverflowError("can't convert negative int to unsigned")
    if ident >= 2**64:
        raise OverflowError("int too big to convert")
    handle = _ThreadHandle()
    handle._a_ident = ident
    handle._b_state = _RUNNING
    return handle


def allocate_lock(*args: object, **kwds: object) -> lock:
    _noargs("_thread.allocate_lock", args, kwds)
    return lock()


def allocate(*args: object, **kwds: object) -> lock:
    _noargs("_thread.allocate", args, kwds)
    return lock()


def get_ident(*args: object, **kwds: object) -> int:
    _noargs("_thread.get_ident", args, kwds)
    return _thread_ident()


def _get_main_thread_ident(*args: object, **kwds: object) -> int:
    _noargs("_thread._get_main_thread_ident", args, kwds)
    return _thread_ident()


def get_native_id(*args: object, **kwds: object) -> int:
    _noargs("_thread.get_native_id", args, kwds)
    return _native_thread_id()


def _count(*args: object, **kwds: object) -> int:
    _noargs("_thread._count", args, kwds)
    return 0


def daemon_threads_allowed(*args: object, **kwds: object) -> bool:
    _noargs("_thread.daemon_threads_allowed", args, kwds)
    return True


def _is_main_interpreter(*args: object, **kwds: object) -> bool:
    _noargs("_thread._is_main_interpreter", args, kwds)
    return True


def _shutdown(*args: object, **kwds: object) -> None:   # nothing to wait for
    _noargs("_thread._shutdown", args, kwds)


def exit(*args: object, **kwds: object) -> None:
    _noargs("_thread.exit", args, kwds)
    raise SystemExit


def exit_thread(*args: object, **kwds: object) -> None:
    _noargs("_thread.exit_thread", args, kwds)
    raise SystemExit


_stack_size = [0]


def stack_size(*args: object, **kwds: object) -> int:   # thread_stack_size: "|n:stack_size"
    if kwds:
        raise TypeError("stack_size() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("stack_size() takes at most 1 argument (" + str(len(args)) + " given)")
    new_size = _number_index(args[0]) if args else 0
    if not -(2**63) <= new_size < 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if new_size != 0 and new_size < 53248:       # _PyOS_MIN_STACK_SIZE + SYSTEM_PAGE_SIZE
        raise ValueError("size must be at least 53248 bytes")
    old = _stack_size[0]
    _stack_size[0] = new_size
    return old


def interrupt_main(*args: object, **kwds: object) -> None:   # thread_interrupt_main: signum=SIGINT, /
    if kwds:
        raise TypeError("interrupt_main() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("signum() takes at most 1 argument (" + str(len(args)) + " given)")
    signum = _number_index(args[0]) if args else 2
    if not -(2**63) <= signum < 2**63:           # the format "i"
        raise OverflowError("Python int too large to convert to C long")
    if signum > 2147483647:
        raise OverflowError("signed integer is greater than maximum")
    if signum < -2147483648:
        raise OverflowError("signed integer is less than minimum")
    if not 1 <= signum < 65:
        raise ValueError("signal number out of range")
    _bella_refuse("_thread.interrupt_main: raising a signal (the module signal)")


def set_name(*args: object, **kwds: object) -> None:
    total = len(args) + len(kwds)
    if total > 1:
        raise TypeError("set_name() takes at most 1 " + ("" if args else "keyword ") + "argument (" + str(total) + " given)")
    if not args and "name" not in kwds:
        raise TypeError("set_name() missing required argument 'name' (pos 1)")
    for key in kwds:
        if key != "name":
            raise TypeError("set_name() got an unexpected keyword argument '" + key + "'")
    name = args[0] if args else kwds["name"]
    if not issubclass(type(name), str):
        raise TypeError("set_name() argument 'name' must be str, not " + type(name).__name__)
    _bella_refuse("_thread.set_name: the name of a thread (the threads milestone, [P2+])")


def _get_name(*args: object, **kwds: object) -> str:
    _noargs("_thread._get_name", args, kwds)
    _bella_refuse("_thread._get_name: the name of a thread (the threads milestone, [P2+])")


def _excepthook(*args: object, **kwds: object) -> None:
    if kwds:
        raise TypeError("_thread._excepthook() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_thread._excepthook() takes exactly one argument (" + str(len(args)) + " given)")
    raise TypeError("_thread.excepthook argument type must be ExceptHookArgs")


def _start_new(alias: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # thread_PyThread_start_new_thread
    if kwds:
        raise TypeError(alias + "() takes no keyword arguments")
    if len(args) < 2:
        raise TypeError("start_new_thread expected at least 2 arguments, got " + str(len(args)))
    if len(args) > 3:
        raise TypeError("start_new_thread expected at most 3 arguments, got " + str(len(args)))
    if not callable(args[0]):
        raise TypeError("first arg must be callable")
    if not issubclass(type(args[1]), tuple):
        raise TypeError("2nd arg must be a tuple")
    if len(args) == 3 and not issubclass(type(args[2]), dict):
        raise TypeError("optional 3rd arg must be a dictionary")
    _bella_refuse("creating a thread (the threads milestone, [P2+])")


def start_new_thread(*args: object, **kwds: object) -> int:
    _start_new("start_new_thread", args, kwds)
    return 0


def start_new(*args: object, **kwds: object) -> int:
    _start_new("start_new", args, kwds)
    return 0


def start_joinable_thread(*args: object, **kwds: object) -> _ThreadHandle:   # "O|Op:start_joinable_thread"
    names = ("function", "handle", "daemon")
    total = len(args) + len(kwds)
    if total > 3:
        raise TypeError("start_joinable_thread() takes at most 3 arguments (" + str(total) + " given)")
    given: dict[str, object] = {}
    for index, value in enumerate(args):
        given[names[index]] = value
    for key, value in kwds.items():
        if key not in names:
            raise TypeError("start_joinable_thread() got an unexpected keyword argument '" + key + "'")
        if key in given:
            raise TypeError("argument for start_joinable_thread() given by name ('" + key + "') and position (" + str(names.index(key) + 1) + ")")
        given[key] = value
    if "function" not in given:
        raise TypeError("start_joinable_thread() missing required argument 'function' (pos 1)")
    if "daemon" in given:
        bool(given["daemon"])
    if not callable(given["function"]):
        raise TypeError("thread function must be callable")
    handle = given.get("handle")
    if handle is not None and type(handle) is not _ThreadHandle:
        raise TypeError("'handle' must be a _ThreadHandle")
    _bella_refuse("creating a thread (the threads milestone, [P2+])")
