"""The functions of traceback (CPython 3.15.2, Lib/traceback.py) that its adaptation replaces (manifest.toml
[adaptations] and [replaced]): each def stands for the one of the same qualified name, whose signature it repeats; the
frontend puts its body there (pipeline/l1/frontend.py, replace_functions).

_find_incompatible_extension_module looks for an extension module built for another Python version on sys.path, to
suggest it when an import fails; a closed world has none, so it finds none."""


def _find_incompatible_extension_module(module_name):  # type: ignore[no-untyped-def]
    return None
