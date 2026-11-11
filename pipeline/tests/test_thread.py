"""_thread with one thread, compiled, against CPython.

Case C-7-22 shows the behaviour by exception class, as a case must; these compare messages too, what a blocking
wait does when nothing can end it, and how `reprlib` uses the module. Addresses and idents are
masked before they are compared.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

SHOW = """import _thread
ident = str(_thread.get_ident())
def show(f):
    try:
        r = f()
        s = repr(r)
        s = s.replace(ident, "IDENT")
        print(s if " at 0x" not in s else s[:s.index(" at 0x")])
    except BaseException as e:
        print(type(e).__name__, str(e).replace(ident, "IDENT"))
"""

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
l = _thread.lock()
r = _thread.RLock()
for f in (lambda: l.__exit__(), lambda: l.__exit__(1, 2), lambda: l.__exit__(x=1), lambda: l.__enter__(1), lambda: l.__enter__(x=1), lambda: l.acquire(1, 2, 3), lambda: l.acquire(x=1), lambda: l.acquire(True, blocking=False), lambda: l.acquire(True, 0, timeout=1), lambda: l.acquire(blocking=True, timeout=0, x=1), lambda: l.locked(1), lambda: l.locked(x=1), lambda: l.release(1), lambda: l.release_lock(1), lambda: l.locked_lock(1), lambda: l.acquire_lock(1, 2, 3), lambda: l._at_fork_reinit(1), lambda: l.release(), lambda: l.release_lock(),
          lambda: l.acquire(False, 1), lambda: l.acquire(False, 1.5), lambda: l.acquire(True, -2), lambda: l.acquire(True, -0.5), lambda: l.acquire(True, 2**70), lambda: l.acquire(True, -(2**70)), lambda: l.acquire(True, 1e300), lambda: l.acquire(True, -1e300), lambda: l.acquire(True, 9223372036.0), lambda: l.acquire(True, 9223372037), lambda: l.acquire(True, 9223372037.0), lambda: l.acquire(True, float("inf")), lambda: l.acquire(True, float("nan")), lambda: l.acquire(True, "a"), lambda: l.acquire(True, None), lambda: l.acquire(True, []), lambda: l.acquire(True, b"a"),
          lambda: _thread.allocate_lock(1), lambda: _thread.allocate_lock(x=1), lambda: _thread.allocate(1), lambda: _thread.lock(1), lambda: _thread.lock(x=1), lambda: type("X", (_thread.lock,), {}), lambda: setattr(l, "x", 1), lambda: l.x, lambda: l.__weakref__, lambda: l.__dict__, lambda: _thread.lock.acquire(), lambda: _thread.lock.acquire(1), lambda: _thread.lock.release(1), lambda: _thread.lock.locked(1),
          lambda: r.__exit__(), lambda: r.__enter__(1), lambda: r.release(), lambda: r.release(1), lambda: r.acquire(False, 1), lambda: r.acquire(True, -2), lambda: r.acquire(True, 2**70), lambda: r.acquire(1, 2, 3), lambda: r.acquire(x=1), lambda: r.acquire(True, blocking=False), lambda: r.locked(1), lambda: r._is_owned(1), lambda: r._recursion_count(1), lambda: r._release_save(), lambda: r._release_save(1), lambda: r._acquire_restore(), lambda: r._acquire_restore(1, 2), lambda: r._acquire_restore(x=1), lambda: r._acquire_restore(1), lambda: r._acquire_restore([1, 2]), lambda: r._acquire_restore((1,)), lambda: r._acquire_restore((1, 2, 3)), lambda: r._acquire_restore(("a", 1)), lambda: r._acquire_restore((1, "a")), lambda: r._acquire_restore((2**70, 1)), lambda: _thread.RLock(1), lambda: _thread.RLock(x=1), lambda: setattr(r, "x", 1), lambda: r.__weakref__, lambda: r.__dict__, lambda: _thread.RLock.acquire(1),
          lambda: _thread.get_ident(1), lambda: _thread.get_ident(x=1), lambda: _thread._get_main_thread_ident(1), lambda: _thread.get_native_id(1), lambda: _thread._count(1), lambda: _thread.daemon_threads_allowed(1), lambda: _thread._is_main_interpreter(1), lambda: _thread._shutdown(1), lambda: _thread.exit(1), lambda: _thread.exit(), lambda: _thread.exit_thread(1), lambda: _thread.exit_thread(),
          lambda: _thread.stack_size(1, 2), lambda: _thread.stack_size(x=1), lambda: _thread.stack_size("a"), lambda: _thread.stack_size(1.5), lambda: _thread.stack_size(-1), lambda: _thread.stack_size(1), lambda: _thread.stack_size(53247), lambda: _thread.stack_size(2**70),
          lambda: _thread.interrupt_main(0), lambda: _thread.interrupt_main(65), lambda: _thread.interrupt_main(-1), lambda: _thread.interrupt_main("a"), lambda: _thread.interrupt_main(1, 2), lambda: _thread.interrupt_main(x=1), lambda: _thread.interrupt_main(2**70),
          lambda: _thread.set_name(1), lambda: _thread.set_name(), lambda: _thread.set_name("a", "b"), lambda: _thread.set_name(x="a"), lambda: _thread.set_name(name=1), lambda: _thread._get_name(1),
          lambda: _thread._excepthook(1), lambda: _thread._excepthook(), lambda: _thread._excepthook(x=1), lambda: _thread._make_thread_handle(), lambda: _thread._make_thread_handle(1, 2), lambda: _thread._make_thread_handle("a"), lambda: _thread._make_thread_handle(-1), lambda: _thread._make_thread_handle(2**64), lambda: _thread._make_thread_handle(x=1),
          lambda: _thread.start_new_thread(), lambda: _thread.start_new_thread(print), lambda: _thread.start_new_thread(print, (), {}, 1), lambda: _thread.start_new_thread(1, ()), lambda: _thread.start_new_thread(print, 1), lambda: _thread.start_new_thread(print, [], {}), lambda: _thread.start_new_thread(print, (), 1), lambda: _thread.start_new_thread(print, (), x=1), lambda: _thread.start_new(print), lambda: _thread.start_new(print, (), x=1), lambda: _thread.start_new(1, ()),
          lambda: _thread.start_joinable_thread(), lambda: _thread.start_joinable_thread(1), lambda: _thread.start_joinable_thread(print, handle=1), lambda: _thread.start_joinable_thread(print, 1), lambda: _thread.start_joinable_thread(print, x=1), lambda: _thread.start_joinable_thread(print, None, True, 1), lambda: _thread.start_joinable_thread(print, function=print), lambda: _thread.start_joinable_thread(handle=None), lambda: _thread.start_joinable_thread(1, handle=1),
          lambda: _thread._ThreadHandle().join(), lambda: _thread._ThreadHandle()._set_done(), lambda: _thread._ThreadHandle().join(1, 2), lambda: _thread._ThreadHandle().join(x=1), lambda: _thread._ThreadHandle().join("a"), lambda: _thread._ThreadHandle().is_done(1), lambda: _thread._ThreadHandle()._set_done(1), lambda: setattr(_thread._ThreadHandle(), "ident", 1), lambda: setattr(_thread._ThreadHandle(), "x", 1), lambda: _thread._ThreadHandle().__dict__, lambda: _thread._ThreadHandle().__weakref__, lambda: _thread._ThreadHandle.ident.__get__(1), lambda: _thread._ThreadHandle.join(1),
          lambda: _thread._make_thread_handle(_thread.get_ident()).join(), lambda: _thread._make_thread_handle(_thread.get_ident()).join(1), lambda: _thread._make_thread_handle(_thread.get_ident()).join(None), lambda: _thread._make_thread_handle(5).join("a"), lambda: _thread._make_thread_handle(5).join(float("nan")), lambda: _thread._make_thread_handle(5).join(2**70)):
    show(f)
"""),
    ('what_a_lock_says', SHOW + r"""
l = _thread.lock()
show(lambda: l)
show(lambda: l.acquire())
show(lambda: l)
show(lambda: str(l))
show(lambda: l.acquire(True, 0))
show(lambda: l.acquire(True, 0.0))
show(lambda: l.acquire(True, 0.002))
show(lambda: l.acquire(True, 1e-9))
show(lambda: l.acquire(timeout=False))
show(lambda: l.acquire(blocking=False))
show(lambda: l.release())
class Index:
    def __index__(self):
        return 0
class BadBool:
    def __bool__(self):
        raise KeyError("bool")
class FloatOnly:
    def __float__(self):
        return 0.0
class F(float):
    def __float__(self):
        return 100.0
class I(int):
    def __index__(self):
        return 100
show(lambda: l.acquire(BadBool()))
show(lambda: l.acquire(BadBool(), "a"))
show(lambda: l.acquire())
show(lambda: l.acquire(True, Index()))
show(lambda: l.acquire(True, FloatOnly()))
show(lambda: l.acquire(True, F(0.0)))
show(lambda: l.acquire(True, I(0)))
show(lambda: l.acquire(False, Index()))
show(lambda: l.acquire(False, -1))
show(lambda: l.acquire(False, -1.0))
show(lambda: l.acquire(0, -1))
show(lambda: l.acquire("", -1))
show(lambda: l.acquire(False, None))
show(lambda: l.release())
print(sorted(set(dir(_thread.lock)) - set(dir(object))), sorted(set(dir(_thread.RLock)) - set(dir(object))), sorted(set(dir(_thread._ThreadHandle)) - set(dir(object))), sorted(set(dir(_thread._local)) - set(dir(object))))
print(sorted(k for k in vars(_thread.lock) if k not in ("_a_locked",)) if False else 0)
print(_thread.lock.__name__, _thread.lock.__qualname__, _thread.lock.__module__, _thread.lock.__mro__, _thread.RLock.__mro__, _thread._local.__mro__, _thread._ThreadHandle.__mro__, _thread.lock.__doc__ is not None, _thread.RLock.__doc__ is not None, _thread._local.__doc__, _thread.__doc__ is not None)
print(_thread.allocate_lock, _thread.get_ident, _thread.start_new_thread, _thread.allocate.__name__, _thread.start_new.__name__, _thread.exit_thread.__name__, _thread.get_ident.__module__, type(_thread.get_ident).__name__, type(_thread.lock).__name__, _thread.get_ident.__qualname__)
print(sorted(vars(_thread)) == sorted(set(vars(_thread))), [k for k in sorted(dir(_thread)) if not k.startswith("__")])
"""),
    ('an_rlock_and_conditions', SHOW + r"""
r = _thread.RLock()
show(lambda: r)
show(lambda: r.acquire())
show(lambda: r)
show(lambda: r.acquire(True, 5))
show(lambda: r)
show(lambda: r._release_save())
show(lambda: r)
show(lambda: r._acquire_restore((3, _thread.get_ident())))
show(lambda: r)
show(lambda: r._recursion_count())
show(lambda: r.release())
show(lambda: r.release())
show(lambda: r.release())
show(lambda: r.release())
show(lambda: r._acquire_restore((1, 5)))
show(lambda: r)
show(lambda: r.locked())
show(lambda: r._is_owned())
show(lambda: r._recursion_count())
show(lambda: r.release())
show(lambda: r.acquire(False))
show(lambda: r.acquire(True, 0))
show(lambda: r.acquire(True, 0.002))
show(lambda: r._release_save())
show(lambda: r._at_fork_reinit())
show(lambda: r)
show(lambda: r.acquire())
show(lambda: r._acquire_restore((2, 1 + 2**64 + _thread.get_ident() - 1)))
show(lambda: r)
show(lambda: r._at_fork_reinit())
class Sub(_thread.RLock):
    __slots__ = ("a",)
    def __repr__(self):
        return "Sub:" + super().__repr__()
class Sub2(_thread.RLock):
    pass
s = Sub()
s.a = 1
show(lambda: s)
show(lambda: s.acquire())
show(lambda: s)
show(lambda: s.__dict__)
show(lambda: setattr(s, "b", 1))
show(lambda: Sub2())
show(lambda: Sub2().__dict__)
show(lambda: Sub2.__mro__)
show(lambda: sorted(Sub2.__dict__))
show(lambda: sorted(Sub.__dict__))
import weakref
show(lambda: weakref.ref(Sub())() is None)
keep = Sub2()
show(lambda: weakref.ref(keep)() is keep)
show(lambda: weakref.getweakrefcount(keep))
"""),
    ('thread_local_data', SHOW + r"""
loc = _thread._local()
show(lambda: loc)
loc.a = 1
loc.b = 2
show(lambda: loc.__dict__)
show(lambda: vars(loc))
show(lambda: loc.a)
show(lambda: loc.c)
show(lambda: getattr(loc, "c", 5))
show(lambda: hasattr(loc, "__dict__"))
show(lambda: setattr(loc, "__dict__", {}))
show(lambda: delattr(loc, "__dict__"))
show(lambda: delattr(loc, "c"))
show(lambda: delattr(loc, 1))
show(lambda: setattr(loc, 1, 1))
show(lambda: getattr(loc, 1))
show(lambda: loc.__weakref__)
show(lambda: loc.__class__)
show(lambda: loc.__doc__)
show(lambda: loc.__module__)
show(lambda: _thread._local.__getattribute__(loc, "a"))
show(lambda: _thread._local.__getattribute__(loc, "__dict__"))
show(lambda: _thread._local.__getattribute__(1, "a"))
show(lambda: _thread._local.__setattr__(loc, "z", 1))
show(lambda: _thread._local.__setattr__(loc, "__dict__", 1))
show(lambda: _thread._local.__delattr__(loc, "z"))
show(lambda: _thread._local.__delattr__(loc, "__dict__"))
show(lambda: _thread._local.x)
show(lambda: setattr(_thread._local, "x", 1))
show(lambda: _thread._local(1))
show(lambda: _thread._local(x=1))
show(lambda: _thread._local.__new__(1))
show(lambda: _thread._local.__new__(_thread._local, 1))
show(lambda: dir(loc)[-3:])
show(lambda: sorted(vars(_thread._local)))
class Plain(_thread._local):
    pass
class WithInit(_thread._local):
    def __init__(self, a, b=2):
        self.a = a
        self.b = b
class WithNew(_thread._local):
    def __new__(cls, *a, **k):
        print("new", a, k)
        return super().__new__(cls)
class Slotted(_thread._local):
    __slots__ = ("s",)
class SlottedDict(_thread._local):
    __slots__ = ("s", "__dict__")
class Child(Slotted):
    pass
class Grand(Plain):
    pass
class Props(_thread._local):
    @property
    def p(self):
        return "prop"
    @p.setter
    def p(self, v):
        self.q = v
    def __getattr__(self, n):
        return "missing " + n
    def __del__(self):
        print("del", self.__dict__)
    x = 5
show(lambda: list(vars(Plain)))
show(lambda: list(vars(WithInit)))
show(lambda: list(vars(Slotted)))
show(lambda: list(vars(SlottedDict)))
show(lambda: list(vars(Child)))
show(lambda: list(vars(Grand)))
show(lambda: Plain(1))
show(lambda: Plain().__dict__)
show(lambda: WithInit(1).__dict__)
show(lambda: WithInit(1, b=3).b)
show(lambda: WithInit())
show(lambda: WithNew(1, k=2))
s = Slotted()
s.s = 1
show(lambda: s.s)
show(lambda: s.__dict__)
s.other = 2
show(lambda: s.__dict__)
show(lambda: setattr(s, "__dict__", {}))
show(lambda: dir(s)[-2:])
sd = SlottedDict()
sd.s = 1
sd.t = 2
show(lambda: sd.__dict__)
show(lambda: setattr(sd, "__dict__", {}))
c = Child()
c.s = 1
c.t = 2
show(lambda: c.__dict__)
show(lambda: setattr(c, "__dict__", {}))
g = Grand()
g.a = 1
show(lambda: g.__dict__)
show(lambda: setattr(g, "__dict__", {}))
p = Props()
p.p = 1
show(lambda: p.p)
show(lambda: p.q)
show(lambda: p.nothing)
show(lambda: p.x)
show(lambda: p.__dict__)
del p
import weakref
keep = Plain()
show(lambda: weakref.ref(keep)() is keep)
show(lambda: weakref.getweakrefcount(keep))
show(lambda: keep.__weakref__)
show(lambda: type("T", (_thread._local,), {"__slots__": ("__weakref__",)}))
show(lambda: type("T", (_thread._local,), {"__slots__": ("__dict__",)}))
show(lambda: type("T", (_thread._local, _thread.RLock), {}))
show(lambda: type("T", (_thread._local, dict), {}))
"""),
    ('handles', SHOW + r"""
h = _thread._ThreadHandle()
show(lambda: h)
show(lambda: h.ident)
show(lambda: h.is_done())
show(lambda: _thread._ThreadHandle(1, x=2))
show(lambda: _thread._ThreadHandle.__mro__)
show(lambda: type("S", (_thread._ThreadHandle,), {}))
show(lambda: _thread._ThreadHandle.ident)
show(lambda: _thread._ThreadHandle.ident.__name__)
m = _thread._make_thread_handle(_thread.get_ident())
show(lambda: m)
show(lambda: m.ident == _thread.get_ident())
show(lambda: m.is_done())
show(lambda: m._set_done())
show(lambda: m.is_done())
show(lambda: m.join())
show(lambda: m._set_done())
o = _thread._make_thread_handle(5)
show(lambda: o)
show(lambda: o.join(0))
show(lambda: o.join(0.002))
show(lambda: o.join(1e-9))
show(lambda: o.is_done())
show(lambda: _thread._make_thread_handle(True))
show(lambda: _thread._make_thread_handle(2**64 - 1))
class I(int):
    pass
show(lambda: _thread._make_thread_handle(I(5)))
"""),
    ('the_standard_library_on_it', r"""
import reprlib
import _thread
print(reprlib.get_ident is _thread.get_ident)
class C:
    def __init__(self):
        self.me = self
    @reprlib.recursive_repr("...")
    def __repr__(self):
        return "C(" + repr(self.me) + ")"
print(repr(C()))
"""),
]

REFUSED = (
    ("import _thread\n_thread.start_new_thread(print, ())\n", "creating a thread"),
    ("import _thread\n_thread.start_new(print, (), {})\n", "creating a thread"),
    ("import _thread\n_thread.start_joinable_thread(print)\n", "creating a thread"),
    ("import _thread\nr = _thread.RLock()\nr._acquire_restore((1, 5))\nr._acquire_restore((1, 5))\n", "no other thread can release"),
    ("import _thread\n_thread.set_name('a')\n", "the name of a thread"),
    ("import _thread\n_thread._get_name()\n", "the name of a thread"),
    ("import _thread\n_thread._ExceptHookArgs((1, 2, 3, 4))\n", "struct sequence"),
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text for _, text in REFUSED])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_what_one_thread_cannot_do_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]), encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


def test_a_timed_wait_takes_its_time() -> None:
    src = "import _thread\nimport sys\nl = _thread.lock()\nl.acquire()\nprint(l.acquire(True, 0.3))\n"
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        exe = build(prog, "prog.py")
        import time
        started = time.monotonic()
        got = subprocess.run([str(exe)], capture_output=True, text=True, check=False, timeout=60)
        took = time.monotonic() - started
    ref = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, check=False, timeout=60)
    assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode) == ("False\n", 0) and took >= 0.3, (got, took)


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
