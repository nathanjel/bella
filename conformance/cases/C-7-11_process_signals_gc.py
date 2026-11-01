# clause: C-7-11
# spec: section 7
# status: P1
# source: dialect specification sections 3 and 7, Process and signals (signal in the main thread, atexit) and gc; the threading shim
"""signal in the main thread, atexit at exit (last registered runs first), gc, and the
single-threaded threading shim (locks, local, Event, current_thread) phase 1 provides."""
import atexit
import gc
import os
import signal
import threading
import types

received: list[int] = []


def on_signal(signum: int, frame: types.FrameType | None) -> None:
    received.append(signum)


previous = signal.signal(signal.SIGUSR1, on_signal)
print("previous handler is default:", previous is signal.SIG_DFL)
os.kill(os.getpid(), signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR1)
print("received:", [signal.Signals(s).name for s in received], signal.getsignal(signal.SIGUSR1) is on_signal)
signal.signal(signal.SIGUSR1, signal.SIG_IGN)
signal.raise_signal(signal.SIGUSR1)
print("ignored, still", len(received))
atexit.register(print, "atexit: registered first, runs last")
atexit.register(print, "atexit: registered second, runs first")
print("gc:", gc.isenabled(), isinstance(gc.collect(), int), gc.get_threshold()[0] > 0)
gc.disable()
print("disabled:", gc.isenabled())
gc.enable()
lock = threading.Lock()
with lock:
    print("locked:", lock.locked())
rlock = threading.RLock()
with rlock, rlock:
    print("rlock re-entered")
local = threading.local()
local.x = 1
event = threading.Event()
event.set()
print(threading.current_thread().name, threading.main_thread() is threading.current_thread(), local.x, event.is_set(), threading.active_count())
print("main body done")
