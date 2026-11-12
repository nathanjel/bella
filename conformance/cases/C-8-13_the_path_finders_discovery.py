# clause: C-8-13
# spec: section 8 (the closed world), section 7 (traceback)
# status: P1
# source: Lib/importlib/_bootstrap_external.py (PathFinder.discover, FileFinder.discover), Lib/traceback.py
#         (_compute_suggestion_error), Python/suggestions.c (_suggestions._generate_suggestions)
"""PathFinder.discover lists, lazily, the modules the path finder finds: under a package its modules and subpackages, one level
down, each with a new spec of the kind an import uses; at the top level the modules on sys.path. A module that is not a package
has nothing to list, and says so when the list is first asked for. The report of a ModuleNotFoundError suggests the closest name
the list holds, for a module of a package (traceback asks every finder of sys.meta_path that has the method)."""
import importlib
import importlib.machinery
import importlib.util
import sys
import traceback
from collections.abc import Callable

import imppkg.sub

PathFinder = importlib.machinery.PathFinder


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


listing = PathFinder.discover(imppkg.__spec__)
print("lazy:", type(listing).__name__, type(PathFinder.discover()).__name__)
specs = {spec.name: spec for spec in listing}
print("under the package:", "imppkg.plain" in specs, "imppkg.sub" in specs, "imppkg.sub.deep" in specs, "imppkg" in specs)
plain = specs["imppkg.plain"]
module_loader: object = imppkg.plain.__loader__
print("a module's spec:", type(plain).__name__, type(plain.loader).__name__, plain.name, plain.parent, plain.has_location,
      plain.origin == imppkg.plain.__file__, plain.submodule_search_locations, plain is imppkg.plain.__spec__,
      plain.loader is module_loader)
sub = specs["imppkg.sub"]
print("a package's spec:", type(sub.loader).__name__, sub.parent, sub.origin == imppkg.sub.__file__,
      sub.submodule_search_locations == imppkg.sub.__path__)
print("under the subpackage:", sorted(n for n in (spec.name for spec in PathFinder.discover(imppkg.sub.__spec__)) if n.startswith("imppkg.sub.d")))
print("top level:", "imppkg" in {spec.name for spec in PathFinder.discover()})
print("not a package:", type(PathFinder.discover(imppkg.plain.__spec__)).__name__, attempt(lambda: list(PathFinder.discover(imppkg.plain.__spec__))))
print("finders with the method:", [type(f).__name__ if not isinstance(f, type) else f.__name__ for f in sys.meta_path if hasattr(f, "discover")])

for name, expected in (("imppkg.plian", "imppkg.plain"), ("imppkg.sbu", "imppkg.sub"), ("imppkg.sub.deeep", "imppkg.sub.deep"),
                       ("imppkg.zzzzzzzz", None)):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError as exc:
        line = traceback.format_exception_only(exc)[-1].rstrip("\n")
        suggested = line.endswith(f". Did you mean: '{expected}'?") if expected is not None else "Did you mean" not in line
        print("suggestion:", name, exc.name == name, suggested)
