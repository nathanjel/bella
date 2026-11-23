# clause: C-9-13
# spec: section 9
# status: P1
# source: Python/pylifecycle.c (_Py_Finalize, finalize_modules and its steps, finalize_interp_clear), Python/pystate.c
#         (_PyInterpreterState_Clear), Objects/moduleobject.c (_PyModule_ClearDict, module_dealloc, module_clear), Python/gc.c
#         (PyGC_Collect, _PyGC_CollectNoFail); review S22, RL-514 (the author's decision of 2026-11-20: exact, with the collector)
"""At exit CPython takes the program apart in steps, and a finaliser sees the step it runs in. A collection first, while all
is whole (unless the collector is disabled); then sys's special names go and the standard streams are put back; sys.modules
lets go of each module in its order, and a module nothing else holds goes with its namespace if that is in no cycle; the
builtins get back the names they had before the program (no `open`); a collection with every namespace whole; the modules
still held from sys, last imported first, have their names set to None, those with one underscore first; then sys's and the
builtins' names; a last collection, which finds what only sys or the builtins held (a module's names whole, but no builtin
and no stream); and once the interpreter's own state is cleared (the context, the codec registry), the interpreter's last
collection. What the warning filters or gc.callbacks hold is never finalised. Each row starts the program again, sets up one
thing and ends; its finalisers write with `os.write` alone. Nothing assigns to the builtins (E-06)."""
import binascii
import codecs
import contextvars
import gc
import os
import sys
import types
import warnings
import weakref
from collections.abc import Callable

from exitpkg import fin

SHOW = "BELLA_CASE_SHOW"
LABEL = "main"
ROWS = ("stdout", "cycle", "cycle_disabled", "data", "plain", "classattr", "resurrect", "restored", "alive", "weak", "hook",
        "weak_main", "cmodule", "codec", "context", "warnings", "gc_callbacks")
held: object = None
asked: object = None
variable: contextvars.ContextVar[object] = contextvars.ContextVar("variable")


class Holder:
    """A class whose attribute holds an object."""

    held: object = None


class Out(fin.C):
    """A standard stream of the program's own."""

    def write(self, text: str) -> int:
        return 0

    def flush(self) -> None:
        pass


class Resurrected(fin.C):
    def __del__(self, r: Callable[[str, fin.Namespace], None] = fin.report) -> None:
        r(self.tag, self.g)
        sys.__dict__["back"] = self


class Restored:
    """What the builtins and sys say once the modules are gone: the names they had before the program."""

    def __del__(self, w: Callable[[int, bytes], int] = os.write, s: types.ModuleType = sys) -> None:
        try:
            n: object = len("abc")
        except TypeError:
            n = "TypeError"
        try:
            open  # noqa: B018  -- asked for its presence
            o = "open is there"
        except NameError:
            o = "no open"
        w(1, f"  restored: len('abc')={n!r}, {o}, path_importer_cache={s.path_importer_cache!r} path_hooks={s.path_hooks!r} path={s.path!r} argv={s.argv!r} meta_path={s.meta_path!r}\n".encode())


class Asker:
    """A finaliser that asks a builtin: after the builtins are cleared it fails, with nothing left to report it."""

    def __del__(self) -> None:
        print("  asker: print works")


class Late:
    """What a module still held by the end shows: its names are None."""

    def __del__(self, w: Callable[[int, bytes], int] = os.write, m: types.ModuleType = binascii,
                p: types.ModuleType = os.path) -> None:
        w(1, "  late: binascii.hexlify={!r} os.path.join={!r}\n".format(
            m.__dict__.get("hexlify") is not None, p.__dict__.get("join") is not None).encode())


class Category(Warning):
    def described(self) -> str:
        return "a category with a method of the program's"


def hook(*args: object) -> None:
    pass


def callback(ref: object) -> None:
    pass


def search(name: str) -> codecs.CodecInfo | None:
    return None


def on_collection(phase: str, info: dict[str, int]) -> None:
    pass


def set_up(row: str) -> None:
    global held, asked
    if row == "stdout":
        sys.__dict__["stdout"] = Out("sys.stdout", {"LABEL": "a copy"})
    elif row in ("cycle", "cycle_disabled"):
        if row == "cycle_disabled":
            gc.disable()
        cycle: list[object] = [fin.C("a cycle", globals())]
        cycle.append(cycle)
    elif row == "data":
        __import__("exitpkg.datamod")
    elif row == "plain":
        held = fin.C("a global", globals())
    elif row == "classattr":
        Holder.held = fin.C("a class attribute", globals())   # alone: two in one collection have no order (D-04)
    elif row == "resurrect":
        held = Resurrected("resurrected", globals())
    elif row == "restored":
        held = Restored()
    elif row == "alive":
        sys.__dict__["kept"] = __import__("exitpkg.kept").kept
        held = fin.C("a global", globals())
    elif row == "weak":
        held = fin.C("a global", globals())
        sys.__dict__["ref"] = weakref.ref(held, fin.Callback("its weak reference's callback"))
    elif row == "hook":
        sys.excepthook = hook
        held = fin.C("a global", globals())
        asked = Asker()
    elif row == "weak_main":
        held = fin.C("a global", globals())
        sys.__dict__["ref"] = weakref.ref(held, callback)
    elif row == "cmodule":
        sys.excepthook = hook
        held = Late()
    elif row == "codec":
        codecs.register(search)
        held = fin.C("a global", globals())
    elif row == "context":
        variable.set(fin.C("a context variable's value", {"LABEL": "a copy"}))
    elif row == "warnings":
        warnings.simplefilter("ignore", Category)
        held = fin.C("a global", globals())
    elif row == "gc_callbacks":
        gc.callbacks.append(on_collection)
        held = fin.C("a global", globals())


def again(row: str) -> None:
    """Start this program again for one row, both outputs in one pipe; print its status and what it wrote."""
    here, there = os.pipe()
    child = os.posix_spawn(sys.executable, sys.orig_argv, {"PYTHONHASHSEED": "0", SHOW: row},
                           file_actions=[(os.POSIX_SPAWN_OPEN, 0, "/dev/null", os.O_RDONLY, 0), (os.POSIX_SPAWN_DUP2, there, 1),
                                         (os.POSIX_SPAWN_DUP2, there, 2), (os.POSIX_SPAWN_CLOSE, here)])
    os.close(there)
    wrote = b""
    while chunk := os.read(here, 65536):
        wrote += chunk
    os.close(here)
    status = os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    print(row, "-> status", status)
    for line in wrote.decode().splitlines():
        print(line)


if SHOW in os.environ:
    set_up(os.environ[SHOW])
else:
    for name in ROWS:
        again(name)
