# clause: C-9-14
# spec: section 9 (lifetimes: a module object is reference-counted like any other; the author's decisions of 2026-11-24 and 2026-11-25)
# status: P1
# source: Objects/moduleobject.c (module_dealloc, module_traverse, module_clear), Objects/funcobject.c (func_clear),
#         Lib/importlib/_bootstrap.py (_load_unlocked), Python/import.c (remove_importlib_frames)
"""When a module dies, and what dies with it. A module object holds its namespace, and what runs in the module (a
function, a frame) holds the namespace, not the module. So a module the program makes dies when the program lets go of
it, its weak references' callbacks first and its namespace then, or in a collection when its namespace holds it. A module
whose body raises is taken out of sys.modules by the import system: it dies as the import's frames go, and its namespace,
which its frame in the traceback holds, when the exception goes; a class it defined holds the namespace in a cycle, which a
collection takes; a function it gave away keeps the namespace, and reads its own names after the import succeeds. Each
collection's deaths are printed sorted, since their order is not defined (D-04)."""
import gc
import sys
import types
import weakref

from dyingpkg.watch import Marker, attempts, deaths, kept, modules, watched


def show(label: str) -> None:
    print(label, deaths)
    deaths.clear()


def collect(label: str) -> None:
    gc.collect()
    print(label, sorted(deaths))
    deaths.clear()


def made() -> None:
    m = types.ModuleType("made")
    m.x = Marker("made.x")  # type: ignore[attr-defined]
    watched(m, "made")
    print("made namespace", sorted(k for k in vars(m) if not k.startswith("__")), m.__name__)
    del m
    show("made dropped")


def held() -> None:
    box: list[types.ModuleType] = [types.ModuleType("held")]
    box[0].x = Marker("held.x")  # type: ignore[attr-defined]
    watched(box[0], "held")
    ref = weakref.ref(box[0])
    show("held kept")
    print("held ref", ref() is not None, ref() is box[0])
    box.clear()
    show("held dropped")
    print("held ref", ref() is None)


def namespace() -> None:
    m = types.ModuleType("namespace")
    m.x = Marker("namespace.x")  # type: ignore[attr-defined]
    watched(m, "namespace")
    ns = vars(m)
    del m
    show("namespace module dropped")
    print("namespace names", sorted(k for k in ns if not k.startswith("__")))
    del ns
    show("namespace dropped")


def selfish() -> None:
    m = types.ModuleType("selfish")
    m.me = m  # type: ignore[attr-defined]
    m.x = Marker("selfish.x")  # type: ignore[attr-defined]
    watched(m, "selfish")
    del m
    show("selfish dropped")
    collect("selfish collected")


def other() -> None:
    a = types.ModuleType("a")
    b = types.ModuleType("b")
    a.other = b  # type: ignore[attr-defined]
    b.other = a  # type: ignore[attr-defined]
    a.x = Marker("a.x")  # type: ignore[attr-defined]
    b.x = Marker("b.x")  # type: ignore[attr-defined]
    watched(a, "a")
    watched(b, "b")
    del a
    show("pair a dropped")
    del b
    show("pair b dropped")
    collect("pair collected")


def failed() -> None:
    try:
        import dyingpkg.fails  # noqa: F401
    except ValueError as e:
        show("failed caught")
        print("failed in sys.modules", "dyingpkg.fails" in sys.modules, type(e).__name__)
    show("failed after")


def failed_class() -> None:
    try:
        import dyingpkg.fails_class  # noqa: F401
    except ValueError:
        show("failed class caught")
    show("failed class after")
    collect("failed class collected")


def failed_once() -> None:
    try:
        import dyingpkg.fails_once  # noqa: F401
    except ValueError:
        pass
    show("once failed")
    print("once kept", [f() for f in kept], attempts)
    import dyingpkg.fails_once as again
    show("once imported")
    print("once kept", [f() for f in kept], again.which(), again.attempt, attempts)
    first = kept.pop(0)
    show("once first given back")
    print("once first", first(), first.__globals__["attempt"], first.__globals__ is not vars(again))
    del first
    show("once first dropped")
    collect("once collected")


gc.disable()
made()
held()
namespace()
selfish()
other()
failed()
failed_class()
failed_once()
print("watched", len(modules), sum(1 for r in modules if r() is None))
collect("end")
