"""The import system's text is CPython's, but for the functions listed here (RL-955 of review W47; RL-1032 of review F48).

`runtime/prelude/bootstrap.py` and `bootstrap_external.py` are CPython 3.15.2's `Lib/importlib/_bootstrap.py` and
`_bootstrap_external.py` adapted to a closed world of one thread. Since the import system's functions run as CPython's
frames (Question 43), what a program sees of them is their text: their lines, their locals, what they call and in which
order. The sweep of code objects in the A46 test compares names and counts and found 29 differing functions; this test
compares the text itself, function by function by qualified name, and every function that differs is in `DIFFERS` with
the reason:

* `REFUSED`: the body is one refusal by name, where a closed world cannot do what CPython's text does (a path finder's
  search, bytecode, an extension module, the Windows registry) or the work is not there yet;
* `PART`: CPython's text up to a refusal;
* `CLOSED`: the closed world's own part of it (the modules are found at build time and run compiled);
* `PRIMITIVE`: a primitive of the runtime where CPython's text names a native function the runtime has under another
  name or not at start-up (`_imp.is_builtin`, `_os.getcwd`, `_warnings.warn`);
* `LOCKS`: the module locks, left out until the threads milestone (D-33);
* `VERBOSE`: a call of `_verbose_message` left out (`-v` is not a compiled program's);
* `HOOKED`: the stop for a name whose class overrides a method of str (E-04, Question 52);
* `STALE`: not the pin's text and to be made it (RL-1059);
* `CUT`: CPython's text cut short after a raise that always fires here, and to be made whole.

A function that comes to agree is to leave the table, a function that starts to differ fails until it is listed with its
reason, and a function listed as `REFUSED` must be nothing but its refusal. `ABSENT` lists what CPython's two modules
define and the preludes do not. The count of each kind is what Question 48's entry (D-34) is written from.

Run under pytest or directly: python3 -m pipeline.tests.test_import_text
"""
from __future__ import annotations

import ast
from pathlib import Path

REFUSED, PART, CLOSED, PRIMITIVE, LOCKS, VERBOSE, HOOKED, STALE, CUT = (
    "refused", "refused after a first part", "the closed world's part", "a primitive for a native function", "the module locks (D-33)",
    "_verbose_message left out", "the stop for a hooked name (E-04)", "not the pin's text (RL-1059)", "cut short after its raise")

DIFFERS: dict[str, str] = {
    # ---- _bootstrap
    "_bootstrap._lock_unlock_module": LOCKS,
    "_bootstrap._find_and_load": LOCKS,              # and sys.audit("import", ...), which calls no hook here
    "_bootstrap._requires_builtin": PRIMITIVE,
    "_bootstrap._requires_builtin.<locals>._requires_builtin_wrapper": PRIMITIVE,
    "_bootstrap.BuiltinImporter.find_spec": PRIMITIVE,
    "_bootstrap.BuiltinImporter.create_module": PRIMITIVE,
    "_bootstrap.BuiltinImporter.exec_module": PRIMITIVE,   # _imp.exec_builtin: a built-in module here is made whole
    "_bootstrap._find_and_load_unlocked": PRIMITIVE,
    "_bootstrap._calc___package__": PRIMITIVE,       # its warnings have lost CPython's stack level: RL-1057
    "_bootstrap._load_unlocked": VERBOSE,
    "_bootstrap._gcd_import": HOOKED,
    "_bootstrap._exec": REFUSED,
    "_bootstrap._find_spec": CLOSED,
    "_bootstrap.FrozenImporter.exec_module": CLOSED,
    "_bootstrap._setup": CLOSED,
    # ---- _bootstrap_external
    "_bootstrap_external._path_isdir": PRIMITIVE,
    "_bootstrap_external._path_abspath": PRIMITIVE,
    "_bootstrap_external.spec_from_file_location": PRIMITIVE,
    "_bootstrap_external.FileFinder.__init__": PRIMITIVE,
    "_bootstrap_external._classify_pyc": VERBOSE,
    "_bootstrap_external.cache_from_source": PART,   # D-16: no cache tag; CPython's whole text runs as it is and is to replace it
    "_bootstrap_external.source_from_cache": CUT,
    "_bootstrap_external.FileFinder._find_children": PART,
    "_bootstrap_external._install": PART,
    "_bootstrap_external._bless_my_loader": STALE,
    "_bootstrap_external._fix_up_module": STALE,
    "_bootstrap_external._LoaderBasics.exec_module": CLOSED,
    "_bootstrap_external.PathFinder.discover": CLOSED,
    "_bootstrap_external.PathFinder.invalidate_caches": CLOSED,
    **{"_bootstrap_external." + name: REFUSED for name in (
        "_path_stat", "_write_atomic", "_compile_bytecode", "_code_to_timestamp_pyc", "_code_to_hash_pyc",
        "WindowsRegistryFinder._open_registry", "WindowsRegistryFinder._search_registry", "WindowsRegistryFinder.find_spec",
        "SourceLoader.path_mtime", "SourceLoader.path_stats", "SourceLoader._cache_bytecode", "SourceLoader.get_source",
        "SourceLoader.source_to_code", "SourceLoader.get_code", "FileLoader.get_data", "FileLoader.get_resource_reader",
        "SourceFileLoader.path_stats", "SourceFileLoader._cache_bytecode", "SourceFileLoader.set_data", "SourcelessFileLoader.get_code",
        "ExtensionFileLoader.create_module", "ExtensionFileLoader.exec_module", "NamespaceLoader.get_code",
        "NamespaceLoader.get_resource_reader", "PathFinder._path_hooks", "PathFinder._path_importer_cache", "PathFinder._get_spec",
        "PathFinder.find_spec", "PathFinder.find_distributions", "FileFinder.find_spec", "FileFinder._fill_cache",
        "AppleFrameworkLoader.create_module")},
}

NOT_YET = "not there yet: stops by name"
ABSENT: dict[str, str] = {
    **{"_bootstrap." + name: LOCKS for name in (
        "_BlockingOnManager.__enter__", "_BlockingOnManager.__exit__", "_BlockingOnManager.__init__", "_DummyModuleLock.__init__",
        "_DummyModuleLock.__repr__", "_DummyModuleLock.acquire", "_DummyModuleLock.release", "_ImportLockContext.__enter__",
        "_ImportLockContext.__exit__", "_ModuleLock.__init__", "_ModuleLock.__repr__", "_ModuleLock.acquire", "_ModuleLock.has_deadlock",
        "_ModuleLock.locked", "_ModuleLock.release", "_ModuleLockManager.__enter__", "_ModuleLockManager.__exit__",
        "_ModuleLockManager.__init__", "_WeakValueDictionary.__init__", "_WeakValueDictionary.__init__.<locals>.KeyedRef.__init__",
        "_WeakValueDictionary.__init__.<locals>.KeyedRef.__new__", "_WeakValueDictionary.__init__.<locals>.KeyedRef.remove",
        "_WeakValueDictionary._commit_removals", "_WeakValueDictionary.clear", "_WeakValueDictionary.get", "_WeakValueDictionary.setdefault",
        "_get_module_lock", "_has_deadlocked")},
    **{name: NOT_YET for name in (
        "_bootstrap._builtin_from_name", "_bootstrap._install", "_bootstrap._install_external_importers", "_bootstrap._load",
        "_bootstrap._object_name", "_bootstrap._verbose_message", "_bootstrap_external._validate_hash_pyc",
        "_bootstrap_external._validate_timestamp_pyc")},
}


def functions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function of a source file by its qualified name, the nested ones too."""
    out: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + node.name] = node
                walk(node.body, prefix + node.name + ".<locals>.")
            elif isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + ".")

    walk(ast.parse(path.read_text(encoding="utf-8")).body, "")
    return out


def only_refuses(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    return (len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call)
            and isinstance(body[0].value.func, ast.Name) and body[0].value.func.id == "_bella_refuse")


def compared() -> tuple[dict[str, bool], set[str], set[str]]:
    """Each function the preludes share with CPython's two modules and whether its text is CPython's; what CPython alone
    defines; the shared ones that are nothing but a refusal."""
    import importlib as pinned  # noqa: PLC0415
    lib = Path(pinned.__file__).parent
    prelude = Path(__file__).resolve().parents[2] / "runtime" / "prelude"
    first = functions(prelude / "bootstrap.py")      # which also holds the source loaders of the second module
    both = first | functions(prelude / "bootstrap_external.py")
    same: dict[str, bool] = {}
    absent: set[str] = set()
    refusals: set[str] = set()
    for ours, module in ((first, "_bootstrap"), (both, "_bootstrap_external")):
        for name, node in functions(lib / f"{module}.py").items():
            if name not in ours:
                absent.add(f"{module}.{name}")
                continue
            same[f"{module}.{name}"] = ast.unparse(ours[name]) == ast.unparse(node)
            if only_refuses(ours[name]):
                refusals.add(f"{module}.{name}")
    return same, absent, refusals


def test_the_import_systems_text_is_cpythons_but_for_the_listed_functions() -> None:
    same, absent, refusals = compared()
    assert len(same) == 148, len(same)
    differ = {name for name, agrees in same.items() if not agrees}
    wrong = [f"{name}: its text is not CPython's and it is not listed" for name in sorted(differ - set(DIFFERS))]
    wrong += [f"{name}: its text is CPython's now: take it out of DIFFERS" for name in sorted(set(DIFFERS) - differ)]
    wrong += [f"{name}: listed as refused and does more than refuse" for name, why in sorted(DIFFERS.items()) if why == REFUSED and name not in refusals]
    wrong += [f"{name}: nothing but a refusal, and listed as {DIFFERS[name]}" for name in sorted(refusals & set(DIFFERS)) if DIFFERS[name] != REFUSED]
    wrong += [f"{name}: CPython defines it, the preludes do not, and it is not in ABSENT" for name in sorted(absent - set(ABSENT))]
    wrong += [f"{name}: in ABSENT and defined now" for name in sorted(set(ABSENT) - absent)]
    assert not wrong, "\n".join(wrong)


def counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for why in DIFFERS.values():
        out[why] = out.get(why, 0) + 1
    return out


if __name__ == "__main__":
    test_the_import_systems_text_is_cpythons_but_for_the_listed_functions()
    print("ok", len(DIFFERS), "of 148 differ:", counts())
