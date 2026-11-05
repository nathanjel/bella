# clause: C-7-22
# spec: section 7
# status: P1
# source: dialect specification section 7 (the single-threaded shim), Modules/_threadmodule.c
"""_thread with one thread: a lock, an RLock and their timeouts, thread-local data, a thread handle, and what the
module answers about the only thread. Creating a thread is [P2+] and stays out of this case."""
# ruff: noqa: B018, B023, RUF015, SIM117
import _thread
import weakref


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except BaseException as exc:
        return type(exc).__name__
    return "no error"


# ---- what the module is
print(_thread.error is RuntimeError, _thread.TIMEOUT_MAX, _thread._NAME_MAXLEN, _thread.LockType is _thread.lock, _thread.allocate is _thread.allocate_lock, _thread.start_new is _thread.start_new_thread, _thread.exit is _thread.exit_thread, _thread.__name__)  # type: ignore[attr-defined]
print(_thread.get_ident() == _thread.get_ident(), type(_thread.get_ident()).__name__, _thread.get_ident() == _thread._get_main_thread_ident(), _thread.get_ident() > 0, _thread.get_native_id() > 0, _thread._count(), _thread.daemon_threads_allowed(), _thread._is_main_interpreter(), _thread._shutdown())  # type: ignore[attr-defined]
print(_thread.stack_size(), _thread.stack_size(100000), _thread.stack_size(), _thread.stack_size(), failed(lambda: _thread.stack_size(1)), failed(lambda: _thread.stack_size(-1)), failed(lambda: _thread.stack_size("a")), failed(lambda: _thread.stack_size(1, 2)), failed(lambda: _thread.exit()), failed(lambda: _thread.exit_thread()), failed(lambda: _thread.interrupt_main(0)), failed(lambda: _thread.interrupt_main(65)), failed(lambda: _thread.interrupt_main("a")), failed(lambda: _thread.set_name(1)), failed(lambda: _thread._excepthook(1)))  # type: ignore[arg-type,call-arg]
print(failed(lambda: _thread.start_new_thread(print)), failed(lambda: _thread.start_new_thread(1, ())), failed(lambda: _thread.start_new_thread(print, 1)), failed(lambda: _thread.start_new_thread(print, (), 1)), failed(lambda: _thread.start_new_thread(print, (), {}, 1)), failed(lambda: _thread.start_joinable_thread()), failed(lambda: _thread.start_joinable_thread(1)), failed(lambda: _thread.start_joinable_thread(print, handle=1)), failed(lambda: _thread.start_joinable_thread(print, x=1)))  # type: ignore[arg-type,call-arg,call-overload]

# ---- a lock
lock = _thread.allocate_lock()
print(type(lock).__name__, type(lock).__module__, type(lock) is _thread.lock, lock.locked(), lock.acquire(), lock.locked(), lock.acquire(False), lock.acquire(blocking=False), lock.acquire(True, 0), lock.acquire(True, 0.001), lock.acquire(timeout=0), lock.acquire(True, False), lock.release(), lock.locked(), lock.acquire(True, 0), lock.release(), lock.acquire(False), lock.locked_lock(), lock.release_lock(), lock.acquire_lock(), lock.release(), lock.acquire(True, -1), lock.release(), lock.acquire(False, -1), lock.release(), lock.acquire(True, -1.0), lock.release())  # type: ignore[func-returns-value]
with lock:
    print(lock.locked(), lock.acquire(False))
print(lock.locked(), lock.__enter__(), lock.locked(), lock.__exit__(None, None, None), lock.locked(), failed(lambda: lock.release()), failed(lambda: lock.release_lock()), failed(lambda: lock.__exit__(1, 2, 3)), failed(lambda: lock.__exit__()))  # type: ignore[arg-type,call-arg,func-returns-value]
for args in ((False, 1), (False, 0), (False, 1.5), (True, -2), (True, -0.5), (True, 2**70), (True, -(2**70)), (True, 1e300), (True, -1e300), (True, _thread.TIMEOUT_MAX + 2048), (True, float("inf")), (True, float("nan")), (True, "a"), (True, None), (True, [])):  # type: ignore[var-annotated]
    print(failed(lambda: lock.acquire(*args)), lock.locked())
print(failed(lambda: lock.acquire(1, 2, 3)), failed(lambda: lock.acquire(x=1)), failed(lambda: lock.acquire(True, blocking=False)), failed(lambda: lock.acquire(True, 0, timeout=1)), lock.locked(), failed(lambda: lock.locked(1)), failed(lambda: lock.release(1)), failed(lambda: lock.__enter__(1)), failed(lambda: _thread.allocate_lock(1)), failed(lambda: _thread.lock(1)), failed(lambda: _thread.lock(x=1)), failed(lambda: type("X", (_thread.lock,), {})), failed(lambda: setattr(lock, "x", 1)), failed(lambda: lock.x), weakref.ref(lock)() is lock, failed(lambda: lock.__weakref__), failed(lambda: _thread.lock.acquire()), failed(lambda: _thread.lock.acquire(1)), callable(lock.acquire), hash(lock) == hash(lock), lock == lock, lock == _thread.lock(), lock != lock, str(lock) == repr(lock), repr(lock).startswith("<unlocked _thread.lock object at 0x"))  # type: ignore[arg-type,attr-defined,call-arg,misc]
lock.acquire()
print(repr(lock).startswith("<locked _thread.lock object at 0x"), _thread.lock().locked())
lock.release()


class Counter:
    def __index__(self) -> int:
        return 0


class Truth:
    def __bool__(self) -> bool:
        return False


lock.acquire()
print(lock.acquire(Truth()), lock.acquire(True, Counter()), lock.acquire(0), lock.acquire(""), lock.acquire([]), lock.acquire(None) if False else 0)  # type: ignore[arg-type]
lock.release()

# ---- an RLock
r = _thread.RLock()
print(type(r).__name__, type(r).__module__, r.locked(), r._is_owned(), r._recursion_count(), r.acquire(), r.locked(), r._is_owned(), r._recursion_count(), r.acquire(), r.acquire(False), r.acquire(True, 0), r._recursion_count(), r.release(), r._recursion_count(), r.locked(), r.release(), r.release(), r.release(), r.locked(), r._recursion_count(), failed(lambda: r.release()), failed(lambda: r._release_save()), failed(lambda: r.acquire(False, 1)), failed(lambda: r.acquire(True, -2)), failed(lambda: r.acquire(True, 2**70)), failed(lambda: r.acquire(1, 2, 3)), failed(lambda: r.acquire(x=1)), r.locked())  # type: ignore[arg-type,attr-defined,call-arg,func-returns-value]
with r:
    with r:
        print(r._recursion_count(), r.locked())  # type: ignore[attr-defined]
    print(r._recursion_count())  # type: ignore[attr-defined]
print(r.locked(), r.__enter__(), r.__exit__(1, 2, 3), failed(lambda: r.__exit__(1, 2, 3)), failed(lambda: r.__exit__()))  # type: ignore[arg-type,call-arg,func-returns-value]
r.acquire()
r.acquire()
state = r._release_save()  # type: ignore[attr-defined]
print(state[0], state[1] == _thread.get_ident(), r.locked(), r._recursion_count(), r._is_owned(), r._acquire_restore(state), r.locked(), r._recursion_count(), r._is_owned())  # type: ignore[attr-defined]
r.release()
r.release()
print(r.locked(), failed(lambda: r._acquire_restore(1)), failed(lambda: r._acquire_restore((1,))), failed(lambda: r._acquire_restore((1, 2, 3))), failed(lambda: r._acquire_restore(("a", 1))), failed(lambda: r._acquire_restore((1, "a"))), failed(lambda: r._release_save(1)), failed(lambda: r.locked(1)), failed(lambda: r._is_owned(1)), failed(lambda: r._recursion_count(1)), r.locked())  # type: ignore[attr-defined,call-arg]
print(repr(r).startswith("<unlocked _thread.RLock object owner=0 count=0 at 0x"), failed(lambda: _thread.RLock(1)), failed(lambda: _thread.RLock(x=1)), failed(lambda: setattr(r, "x", 1)), weakref.ref(r)() is r)  # type: ignore[call-arg]
r.acquire()
print(repr(r).startswith("<locked _thread.RLock object owner=" + str(_thread.get_ident()) + " count=1 at 0x"))
r.release()


class MyLock(_thread.RLock):  # type: ignore[misc]
    def acquire(self, *a: object, **k: object) -> bool:
        print("acquiring")
        return super().acquire(*a, **k)  # type: ignore[arg-type]


m = MyLock()
m.x = 1  # type: ignore[attr-defined]
print(m.acquire(), m.x, m.locked(), m.__dict__, repr(m).startswith("<locked MyLock object owner="), failed(lambda: MyLock(1)))  # type: ignore[attr-defined,call-arg]
with m:
    print(m._recursion_count())  # type: ignore[attr-defined]
m.release()

# ---- thread-local data
loc = _thread._local()
loc.x = 1
print(loc.x, loc.__dict__, vars(loc), type(loc).__name__, type(loc).__module__, hasattr(loc, "y"), failed(lambda: loc.y), failed(lambda: setattr(loc, "__dict__", {})), failed(lambda: delattr(loc, "__dict__")), failed(lambda: delattr(loc, "y")), failed(lambda: _thread._local(1)), failed(lambda: _thread._local(x=1)), failed(lambda: loc.__weakref__), failed(lambda: getattr(loc, 1)), failed(lambda: setattr(loc, 1, 1)), weakref.ref(loc)() is loc, "x" in dir(loc), sorted(set(dir(_thread._local)) - set(dir(object))), sorted(vars(_thread._local)))  # type: ignore[arg-type,call-arg,call-overload]
del loc.x
print(hasattr(loc, "x"), loc.__dict__)


class Sub(_thread._local):
    kind = "sub"

    def __init__(self, v: int = 0) -> None:
        self.v = v

    @property
    def twice(self) -> int:
        return self.v * 2


class Slotted(_thread._local):
    __slots__ = ("a",)


class Plain(_thread._local):
    pass


s = Sub(4)
sl = Slotted()
sl.a = 1
print(s.v, s.twice, s.kind, s.__dict__, list(vars(Plain)), failed(lambda: Plain(1)), failed(lambda: setattr(s, "twice", 1)), sl.a, sl.__dict__, list(vars(Slotted)), Sub(5).v, Sub.__mro__[1] is _thread._local, Plain().__dict__)  # type: ignore[call-arg]

# ---- a thread handle
h = _thread._ThreadHandle()
print(h.ident, h.is_done(), repr(h), failed(lambda: h.join()), failed(lambda: h._set_done()), failed(lambda: setattr(h, "ident", 1)), failed(lambda: setattr(h, "x", 1)), failed(lambda: weakref.ref(h)), type(_thread._ThreadHandle(1, x=2)).__name__)  # type: ignore[call-arg]
me = _thread._make_thread_handle(_thread.get_ident())  # type: ignore[attr-defined]
print(me.ident == _thread.get_ident(), me.is_done(), failed(lambda: me.join()), failed(lambda: me.join(0)), failed(lambda: me.join(None)), repr(me) == "<_thread._ThreadHandle object: ident=" + str(_thread.get_ident()) + ">", me._set_done(), me.is_done(), me.join(), me.join(0))
other = _thread._make_thread_handle(5)  # type: ignore[attr-defined]
print(other.ident, other.is_done(), other.join(0), other.join(0.001), other.is_done(), other._set_done(), other.is_done(), other.join(), failed(lambda: other.join(1, 2)), failed(lambda: other.join("a")), failed(lambda: _thread._make_thread_handle("a")), failed(lambda: _thread._make_thread_handle()), failed(lambda: _thread._make_thread_handle(-1)), failed(lambda: _thread._make_thread_handle(2**64)), _thread._make_thread_handle(2**64 - 1).ident, _thread._make_thread_handle(True).ident)  # type: ignore[attr-defined]
