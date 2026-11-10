# clause: C-7-55
# spec: section 7
# status: P1
# source: dialect specification section 2 (entry and exit), Python/pylifecycle.c (make_pre_finalization_calls, wait_for_thread_shutdown), Lib/threading.py (_shutdown)
"""The end of a program that dies of an uncaught exception: its report first, then threading._shutdown if threading was imported
(the functions given to threading._register_atexit, newest first; one that raises ends the shutdown and is reported as ignored),
then atexit's handlers, which see threading shut down and may not register with it any more; a SystemExit raised by a handler is
reported as ignored like any other exception, and the exit status stays 1."""
# ruff: noqa: E501, SLF001
import atexit
import sys
import threading


def say(*words: object) -> None:
    print(*words)
    print(*words, file=sys.stderr)


class Handler:
    def __repr__(self) -> str:
        return "<the handler>"

    def __call__(self, name: str) -> None:
        say("handler", name, "shutting down:", threading._SHUTTING_DOWN, "the main thread done:", threading.main_thread()._os_thread_handle.is_done())  # type: ignore[attr-defined]
        if name == "registers with threading":
            try:
                threading._register_atexit(say, "never called")  # type: ignore[attr-defined]
            except RuntimeError as e:
                say("  RuntimeError", e)
        if name == "exits":
            raise SystemExit("a text from a handler")


handler: Handler = Handler()


def at_threading(name: str) -> None:
    say("threading's", name, "shutting down:", threading._SHUTTING_DOWN, "handlers still registered:", atexit._ncallbacks())  # type: ignore[attr-defined]
    if name == "raiser":
        raise ValueError("from threading's shutdown")


atexit.register(handler, "oldest")
threading._register_atexit(at_threading, "never reached: the raiser ends the shutdown")  # type: ignore[attr-defined]
threading._register_atexit(at_threading, "raiser")  # type: ignore[attr-defined]
atexit.register(handler, "exits")
threading._register_atexit(at_threading, "newest")  # type: ignore[attr-defined]
atexit.register(handler, "registers with threading")
say("before:", threading._SHUTTING_DOWN, threading.main_thread()._os_thread_handle.is_done(), atexit._ncallbacks())  # type: ignore[attr-defined]
raise KeyError("uncaught")
