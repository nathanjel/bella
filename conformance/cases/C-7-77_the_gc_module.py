# clause: C-7-77
# spec: section 7 (gc), section 9
# status: P1
# source: Modules/gcmodule.c and Modules/clinic/gcmodule.c.h (CPython 3.15.2); Lib/weakref.py (finalize._exitfunc imports gc)
"""What the gc module keeps and refuses without a collection running: whether automatic collection is on, the
thresholds, the debugging flags, the module's lists and constants, and which exception each wrong call raises before
anything is collected. Then a finaliser weakref.finalize runs at exit, with automatic collection off while it runs."""
import gc
import weakref
from collections.abc import Callable


def refused(f: Callable[[], object]) -> str:
    try:
        f()
    except Exception as e:
        return type(e).__name__
    return "accepted"


def threshold_refused(args: tuple[object, ...]) -> str:
    return refused(lambda: gc.set_threshold(*args))  # type: ignore[arg-type]


print("enabled at start:", gc.isenabled())
gc.disable()
print("after disable:", gc.isenabled())
gc.disable()
print("after a second disable:", gc.isenabled())
returned: object = gc.enable()  # type: ignore[func-returns-value]
print("after enable:", gc.isenabled(), returned is None)

print("thresholds:", gc.get_threshold())
gc.set_threshold(700)
print("one given:", gc.get_threshold())
gc.set_threshold(5, 6)
print("two given:", gc.get_threshold())
gc.set_threshold(True, -4, 0)
print("three given:", gc.get_threshold())
for args in [(), (1, 2, 3, 4), ("x",), (1.5,), (None,), (2**31,), (-2**31 - 1,), (2**31 - 1, -2**31), (2**70,), (1, "x")]:
    print("set_threshold", len(args), "arguments:", threshold_refused(args), gc.get_threshold())
gc.set_threshold(2000, 10, 10)

print("debug:", gc.get_debug())
gc.set_debug(gc.DEBUG_LEAK)
print("debug after DEBUG_LEAK:", gc.get_debug())
gc.set_debug(0)
print("set_debug:", refused(lambda: gc.set_debug()), refused(lambda: gc.set_debug("x")), refused(lambda: gc.set_debug(2**40)), refused(lambda: gc.set_debug(flags=1)),  # type: ignore[arg-type, call-arg]
      refused(lambda: gc.set_debug(1, 2)), gc.get_debug())  # type: ignore[call-arg]
print("constants:", gc.DEBUG_STATS, gc.DEBUG_COLLECTABLE, gc.DEBUG_UNCOLLECTABLE, gc.DEBUG_SAVEALL, gc.DEBUG_LEAK)
print("garbage:", type(gc.garbage).__name__, gc.garbage, gc.garbage is gc.garbage)
print("callbacks:", type(gc.callbacks).__name__, gc.callbacks)
print("public names:", sorted(n for n in dir(gc) if not n.startswith("_")))
print("module:", gc.__name__, gc.__doc__.splitlines()[0] if gc.__doc__ else None)
print("collect's first line:", (gc.collect.__doc__ or "").splitlines()[0])

print("collect:", refused(lambda: gc.collect(3)), refused(lambda: gc.collect(-1)), refused(lambda: gc.collect("x")), refused(lambda: gc.collect(1.0)),  # type: ignore[arg-type]
      refused(lambda: gc.collect(generation=5)), refused(lambda: gc.collect(gen=1)), refused(lambda: gc.collect(1, 2)), refused(lambda: gc.collect(2**40)))  # type: ignore[call-arg]
print("no arguments:", refused(lambda: gc.isenabled(1)), refused(lambda: gc.enable(a=1)), refused(lambda: gc.disable(0)), refused(lambda: gc.get_threshold(1)),  # type: ignore[call-arg]
      refused(lambda: gc.get_debug(None)), refused(lambda: gc.get_count(1)), refused(lambda: gc.get_stats(1)), refused(lambda: gc.freeze(1)))  # type: ignore[call-arg]
print("one argument:", refused(lambda: gc.is_tracked()), refused(lambda: gc.is_tracked(1, 2)), refused(lambda: gc.is_finalized()), refused(lambda: gc.is_finalized(obj=1)))  # type: ignore[call-arg]
print("get_objects:", refused(lambda: gc.get_objects(3)), refused(lambda: gc.get_objects(-2)), refused(lambda: gc.get_objects("x")), refused(lambda: gc.get_objects(1, 2)),  # type: ignore[arg-type, call-arg]
      refused(lambda: gc.get_objects(gen=1)))  # type: ignore[call-arg]


class Resource:
    pass


resource = Resource()
weakref.finalize(resource, lambda: print("finalizer at exit, automatic collection:", gc.isenabled()))
print("main body done")
