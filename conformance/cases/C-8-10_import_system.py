# clause: C-8-10
# spec: section 8
# status: P1
# source: step 3b (compiled imports): Python/import.c, Python/ceval.c and importlib/_bootstrap.py, 3.15.2
"""The import system as CPython's: a module's namespace as the import system fills it, the
spec and loader it is given, sys.modules in the order modules finish, the parent's attribute
bound once a submodule has loaded, relative imports and their errors, a failing module removed
from sys.modules and run again by the next import, ModuleNotFoundError and ImportError with
their name, name_from and path, a None in sys.modules, an object a module put into sys.modules
in its place, PEP 562's __getattr__ and __dir__, import * with and without __all__, __import__
called with each statement's arguments, and a hook installed as builtins.__import__."""
import builtins
import sys

print("main:", __name__, __package__, __spec__, list(globals())[:7], type(globals()["__loader__"]).__name__)
print("main file:", __file__.endswith("C-8-10_import_system.py"), sys.path[0] == __file__.rpartition("/")[0])

import imppkg.sub  # noqa: E402  -- after the prints on purpose: the package's body runs here

print("bound:", type(imppkg).__name__, imppkg.__name__, imppkg.sub.__name__, imppkg.sub is sys.modules["imppkg.sub"])
print("order:", [k for k in sys.modules if k.startswith("imppkg")])
print("namespace:", list(vars(imppkg.plain))[:8])
print("package namespace:", list(vars(imppkg))[:8])
spec = imppkg.plain.__spec__
print("spec:", type(spec).__name__, type(spec).__module__, spec.name, spec.parent, spec.has_location, spec.origin == imppkg.plain.__file__)
print("cached:", spec.cached is not None and spec.cached.endswith("/__pycache__/plain.cpython-315.pyc"))
loader: object = imppkg.plain.__loader__
print("loader:", type(loader).__name__, type(loader).__module__, loader is spec.loader,
      vars(loader)["name"], vars(loader)["path"] == spec.origin)
print("package spec:", imppkg.__spec__.submodule_search_locations == imppkg.__path__, imppkg.__path__[0].endswith("/imppkg"))
print("repr:", repr(imppkg.plain).startswith("<module 'imppkg.plain' from '"), repr(imppkg.plain).endswith("plain.py'>"), repr(sys))
print("spec repr:", repr(sys.__spec__))

import imppkg.plain as alias  # noqa: E402
from imppkg import plain  # noqa: E402

print("same module:", alias is plain is imppkg.plain)

for attempt in (1, 2):
    try:
        import imppkg.failing  # noqa: F401
    except LookupError as exc:
        print("failing, attempt", attempt, ":", exc.args, "| in sys.modules:", "imppkg.failing" in sys.modules,
              "| bound on the package:", hasattr(imppkg, "failing"))


def missing(statement: str) -> None:
    try:
        if statement == "top":
            import imppkg_absent  # type: ignore[import-not-found]  # noqa: F401  # absent on purpose
        elif statement == "sub":
            import imppkg.absent  # type: ignore[import-not-found]  # noqa: F401  # absent on purpose
        elif statement == "not a package":
            import imppkg.plain.child  # type: ignore[import-not-found]  # noqa: F401  # a module's child
        elif statement == "from":
            from imppkg.plain import absent  # type: ignore[attr-defined]  # noqa: F401  # absent on purpose
        elif statement == "relative in main":
            __import__("", globals(), None, ["nothing"], 1)  # from . import nothing: main has no package
    except ImportError as exc:
        path = exc.path if exc.path is None else exc.path.rpartition("/")[2]
        print("missing", statement, "->", type(exc).__name__, exc.name, getattr(exc, "name_from", "-"), path)


for statement in ("top", "sub", "not a package", "from", "relative in main"):
    missing(statement)

sys.modules["imppkg_blocked"] = None  # type: ignore[assignment]  # a None blocks the import
try:
    import imppkg_blocked  # type: ignore[import-not-found]  # noqa: F401  # blocked on purpose
except ImportError as exc:
    print("blocked ->", type(exc).__name__, exc.name)

import imppkg.replaced  # noqa: E402

print("replaced:", imppkg.replaced, sys.modules["imppkg.replaced"])

from imppkg import hooks  # noqa: E402

print("PEP 562:", hooks.computed, hooks.present, dir(hooks))
try:
    hooks.absent  # noqa: B018  # __getattr__ refuses it
except AttributeError as exc:
    print("PEP 562 refuses:", exc.args)
try:
    plain.absent  # type: ignore[attr-defined]  # noqa: B018  # absent on purpose
except AttributeError as exc:
    print("module attribute ->", type(exc).__name__, exc.name, exc.obj is plain)

from imppkg.stars import *  # noqa: E402, F403
from imppkg.nostars import *  # noqa: E402, F403

print("stars:", a, _b, version, "c" in globals(), "_plain" in globals())  # noqa: F405  # bound by import *
try:
    from imppkg.badstars import *  # noqa: F403
except TypeError:
    print("badstars: TypeError")

calls: list[str] = []
original = builtins.__import__


def hook(name: str, globals: object = None, locals: object = None, fromlist: object = (), level: int = 0) -> object:
    calls.append(f"{name} fromlist={fromlist} level={level} globals={globals is MODULE_GLOBALS} locals={locals is None}")
    return original(name, globals, locals, fromlist, level)  # type: ignore[arg-type]  # passed on as given


MODULE_GLOBALS = globals()
builtins.__import__ = hook  # type: ignore[assignment]  # a hook, as importlib's tests install one
import imppkg.plain  # noqa: E402, F811
from imppkg import stars as s  # noqa: E402


def local() -> None:
    import imppkg.sub as sub_alias  # noqa: F401
    from imppkg.sub import deep  # noqa: F401


local()
builtins.__import__ = original
print("hook saw:", calls)
print("__import__:", __import__("imppkg.sub").__name__, __import__("imppkg.sub", fromlist=["deep"]).__name__, s.a)
del sys.modules["imppkg.plain"]
import imppkg.plain  # noqa: E402, F811

print("rerun: a new module object:", imppkg.plain is not plain, "| bound on the package:", imppkg.plain is sys.modules["imppkg.plain"])
print("end")
