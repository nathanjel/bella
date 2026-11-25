# clause: C-8-22
# spec: section 8 (imports; the author's decision of 2026-11-25, Question 43: the import system's frames are CPython's)
# status: P1
# source: Lib/importlib/_bootstrap.py (_find_and_load, _resolve_parents, _find_and_load_unlocked, _load_unlocked,
#         _handle_fromlist, _gcd_import, _call_with_frames_removed), Lib/importlib/_bootstrap_external.py (exec_module),
#         Python/import.c (remove_importlib_frames), Python/_warnings.c (is_internal_filename)
"""The import system's frames. CPython's import system is written in Python, so while a module's body runs the running
stack holds its frames between the importer and the module (`<frozen importlib._bootstrap>` and `_bootstrap_external`,
with their own lines), and they count towards the recursion limit. A traceback that leaves an import statement has them
taken out (all of them for an ImportError, a stretch that ends in `_call_with_frames_removed` otherwise); one that leaves
`importlib.import_module`, which calls the import system without the statement, keeps them. A warning's stack level skips
them."""
import importlib
import sys
import warnings

from importframes.show import entries, where


def show_warning(message: Warning | str, category: type[Warning], filename: str, lineno: int, file: object = None,
                 line: str | None = None) -> None:
    print("warning", category.__name__, str(message), where(filename), lineno)


def plain() -> None:
    import importframes.plain  # noqa: F401


def nested() -> None:
    import importframes.nested  # noqa: F401


def parent() -> None:
    import importframes.parent.child  # noqa: F401


def fromlist() -> None:
    import importframes.other  # noqa: F401
    from importframes.other import child  # noqa: F401


def by_name() -> None:
    importlib.import_module("importframes.by_name")


def deep() -> None:
    import importframes.deep  # noqa: F401


def warns() -> None:
    warnings.showwarning = show_warning
    import importframes.warns  # noqa: F401


def value() -> None:
    try:
        import importframes.raises_value  # noqa: F401
    except ValueError as e:
        entries("value", e)


def import_error() -> None:
    try:
        import importframes.raises_import  # noqa: F401
    except ImportError as e:
        entries("import error", e)


def missing() -> None:
    try:
        import importframes.missing  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as e:
        entries("missing", e)


def by_name_missing() -> None:
    try:
        importlib.import_module("importframes.missing")
    except ImportError as e:
        entries("by name missing", e)


def by_name_value() -> None:
    try:
        importlib.import_module("importframes.by_name_value")
    except ValueError as e:
        entries("by name value", e)


for row in (plain, nested, parent, fromlist, by_name, deep, warns, value, import_error, missing, by_name_missing, by_name_value):
    row()
sys.stdout.flush()
