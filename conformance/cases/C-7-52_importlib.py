# clause: C-7-52
# spec: sections 3, 7, 8
# status: P1
# source: dialect specification sections 7 and 8, Lib/importlib/__init__.py, machinery.py, util.py, _abc.py, Python/import.c (_imp)
"""importlib as a program sees it in a closed world: import_module by absolute and relative name (the closed world's modules, a
module outside it, the C's argument errors), the package's __import__, the frozen modules it is built on (their names in
sys.modules, their identities), importlib.machinery's suffixes and finder and loader classes (the loaders of the program's own
modules among them), importlib.util's spec_from_file_location, module_from_spec, spec_from_loader, find_spec, resolve_name,
source_hash, decode_source, MAGIC_NUMBER and LazyLoader, _imp's answers about built-in and frozen modules and its lock, and
inspect.getmodulename, which reads the suffixes."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import importlib
import importlib.machinery
import importlib.util
import inspect
import json
import json.decoder
import os
import sys
import types

import _imp


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def spec_view(spec):  # type: ignore[no-untyped-def]
    if spec is None:
        return None
    return (spec.name, type(spec.loader).__name__ if not isinstance(spec.loader, type) else spec.loader.__name__, os.path.basename(spec.origin) if isinstance(spec.origin, str) and "/" in spec.origin else spec.origin,
            spec.submodule_search_locations if spec.submodule_search_locations is None else [os.path.basename(p) for p in spec.submodule_search_locations], spec.parent, spec.has_location)   # not spec.cached: D-16


print("modules:", [n in sys.modules for n in ("_frozen_importlib", "_frozen_importlib_external", "_imp", "importlib", "importlib._bootstrap", "importlib._bootstrap_external", "importlib.machinery", "importlib.util", "importlib._abc")])
print("identities:", importlib._bootstrap is sys.modules["_frozen_importlib"], importlib._bootstrap_external is sys.modules["_frozen_importlib_external"], importlib._bootstrap.__name__, importlib._bootstrap_external.__name__, importlib._bootstrap.__package__, importlib.machinery.ModuleSpec is importlib._bootstrap.ModuleSpec, importlib.util.module_from_spec is importlib._bootstrap.module_from_spec, type(importlib.__import__).__name__, importlib.__import__.__module__, importlib.__import__.__qualname__)
print("package:", [hasattr(importlib, n) for n in ("_RELOADING", "_abc", "_bootstrap", "_bootstrap_external", "_imp", "_pack_uint32", "_unpack_uint32", "import_module", "invalidate_caches", "machinery", "reload", "sys", "util")], importlib.__all__ if hasattr(importlib, "__all__") else None, importlib.machinery.__all__, sorted(n for n in dir(importlib.util) if not n.startswith("_")), [c.__name__ for c in importlib._abc.Loader.__mro__], type(importlib._abc.Loader).__name__)

# import_module
j = importlib.import_module("json")
jd = importlib.import_module(".decoder", "json")
print("import_module:", j is json, jd is json.decoder, importlib.import_module("json.decoder") is json.decoder, importlib.import_module("os.path") is os.path, m(lambda: importlib.import_module("no_such_module_anywhere")), m(lambda: importlib.import_module(".x")), m(lambda: importlib.import_module(".x", "")), m(lambda: importlib.import_module("..x", "json")), m(lambda: importlib.import_module("...x", "json.decoder")), m(lambda: importlib.import_module(1)), m(lambda: importlib.import_module("")), m(lambda: importlib.import_module(".", "json").__name__))  # type: ignore[arg-type,no-untyped-call]
print("__import__:", importlib.__import__("json") is json, importlib.__import__("json.decoder") is json, importlib.__import__("json.decoder", fromlist=["JSONDecoder"]) is json.decoder, importlib.__import__("decoder", {"__package__": "json"}, None, (), 1) is json.decoder, importlib.__import__("", {"__package__": "json"}, None, ("decoder",), 1) is json, m(lambda: importlib.__import__("x", None, None, (), 1)), m(lambda: importlib.__import__("x", {"__package__": 3}, None, (), 1)), m(lambda: importlib.__import__("x", {}, None, (), -1)))  # type: ignore[no-untyped-call]
print("find after:", importlib.util.find_spec("json") is not None)   # not invalidate_caches(): CPython's PathFinder imports importlib.metadata there, outside the manifest

# machinery
mach = importlib.machinery
print("suffixes:", mach.SOURCE_SUFFIXES, mach.BYTECODE_SUFFIXES, importlib._bootstrap_external.DEBUG_BYTECODE_SUFFIXES is mach.BYTECODE_SUFFIXES, importlib._bootstrap_external.OPTIMIZED_BYTECODE_SUFFIXES is mach.BYTECODE_SUFFIXES, mach.EXTENSION_SUFFIXES, mach.all_suffixes(), _imp.extension_suffixes() == mach.EXTENSION_SUFFIXES)
print("classes:", [(c.__name__, c.__module__) for c in (mach.ModuleSpec, mach.BuiltinImporter, mach.FrozenImporter, mach.PathFinder, mach.FileFinder, mach.SourceFileLoader, mach.SourcelessFileLoader, mach.ExtensionFileLoader, mach.NamespaceLoader, mach.WindowsRegistryFinder, mach.AppleFrameworkLoader)], [c.__name__ for c in mach.SourceFileLoader.__mro__], [c.__name__ for c in mach.SourcelessFileLoader.__mro__], [c.__name__ for c in mach.AppleFrameworkLoader.__mro__])
print("loaders of modules:", type(json.__loader__).__name__, type(json.__loader__).__module__, type(json.__loader__) is mach.SourceFileLoader, isinstance(json.__loader__, importlib._bootstrap_external.FileLoader), isinstance(json.__loader__, importlib._bootstrap_external.SourceLoader), json.__loader__.name, os.path.basename(json.__loader__.path), json.__loader__.is_package("json"), json.decoder.__loader__.is_package("json.decoder"), m(lambda: json.__loader__.get_filename("other")), os.path.basename(json.__loader__.get_filename()), json.__loader__ == mach.SourceFileLoader("json", json.__loader__.path), hash(json.__loader__) == hash(mach.SourceFileLoader("json", json.__loader__.path)), os.__loader__ is mach.FrozenImporter, sys.__loader__ is mach.BuiltinImporter, os.__spec__.origin, sys.__spec__.origin)  # type: ignore[comparison-overlap,no-untyped-call,union-attr]
print("specs:", spec_view(json.__spec__), spec_view(json.decoder.__spec__), spec_view(os.__spec__), spec_view(sys.__spec__), os.__spec__.loader_state.filename.endswith("os.py"), os.__spec__.loader_state.origname, json.__spec__._set_fileattr, json.__spec__.loader_state, hasattr(json, "__cached__"), json.__file__ == json.__spec__.origin)  # type: ignore[attr-defined,no-untyped-call]
print("finders:", mach.FileFinder.__name__, repr(mach.FileFinder("/tmp", (mach.SourceFileLoader, [".py"]))), mach.FileFinder("x", (mach.SourceFileLoader, [".py"]))._loaders, mach.FileFinder("/x")._path_mtime, mach.WindowsRegistryFinder.REGISTRY_KEY, mach.WindowsRegistryFinder.DEBUG_BUILD, isinstance(mach.PathFinder.find_spec, types.MethodType), mach.PathFinder.find_spec.__self__ is mach.PathFinder)  # type: ignore[attr-defined]

# util
util = importlib.util
print("constants:", util.MAGIC_NUMBER, _imp.pyc_magic_number_token, int.from_bytes(util.MAGIC_NUMBER, "little") == _imp.pyc_magic_number_token, util.MAGIC_NUMBER[2:], _imp.check_hash_based_pycs)
spec = util.spec_from_file_location("mymod", "/some/where/mymod.py")
print("spec_from_file_location:", spec_view(spec), type(spec.loader).__name__, spec.loader.name, spec.loader.path, spec._set_fileattr, spec_view(util.spec_from_file_location("pkg", "/some/where/pkg/__init__.py")), spec_view(util.spec_from_file_location("x", "/a/b.pyc")), spec_view(util.spec_from_file_location("x", "/a/b" + mach.EXTENSION_SUFFIXES[-1])), util.spec_from_file_location("x", "/a/b.txt"), spec_view(util.spec_from_file_location("x", "/a/b.txt", loader=json.__loader__)), spec_view(util.spec_from_file_location("x", loader=json.__loader__)), spec_view(util.spec_from_file_location("x", "rel/path.py", submodule_search_locations=["/p", "/q"]))[3], spec_view(util.spec_from_file_location("x", "/a/b.py", submodule_search_locations=[])), m(lambda: util.spec_from_file_location("x", 3)))  # type: ignore[arg-type,no-untyped-call,union-attr]
mod = util.module_from_spec(spec)  # type: ignore[arg-type]
print("module_from_spec:", type(mod).__name__, mod.__name__, mod.__spec__ is spec, mod.__loader__ is spec.loader, mod.__file__, hasattr(mod, "__cached__"), mod.__package__, mod.__path__ if hasattr(mod, "__path__") else "no __path__", sorted(k for k in vars(mod) if k != "__doc__"), mod.__doc__, repr(mod).replace("/some/where/", "<dir>/"))  # type: ignore[union-attr]
pkg = util.module_from_spec(util.spec_from_file_location("pkg", "/some/where/pkg/__init__.py"))  # type: ignore[arg-type]
print("package module:", pkg.__package__, pkg.__path__, repr(pkg).replace("/some/where/", "<dir>/"))
ls = util.spec_from_loader("ls", loader=None, origin="made up", is_package=True)
print("spec_from_loader:", spec_view(ls), ls.origin, repr(ls), spec_view(util.spec_from_loader("ll", loader=json.__loader__)), spec_view(util.spec_from_loader("nl", mach.NamespaceLoader("nl", [], mach.PathFinder.find_spec))), m(lambda: util.spec_from_loader("x", loader=None)))  # type: ignore[arg-type,no-untyped-call,union-attr]
print("find_spec:", spec_view(util.find_spec("json")), spec_view(util.find_spec("json.decoder")), spec_view(util.find_spec("decoder", "json")), util.find_spec("no_such_module_anywhere"), spec_view(util.find_spec("os")), spec_view(util.find_spec("sys")), m(lambda: util.find_spec(".decoder")), m(lambda: util.find_spec("json.no_such")), m(lambda: util.find_spec("no_such.sub")), util.find_spec("json") is json.__spec__, util.find_spec("json").loader is json.__loader__)  # type: ignore[no-untyped-call,union-attr]
print("resolve_name:", util.resolve_name("a.b", None), util.resolve_name(".b", "pkg"), util.resolve_name("..b", "pkg.sub"), util.resolve_name("...b", "a.b.c"), m(lambda: util.resolve_name(".b", None)), m(lambda: util.resolve_name(".b", "")), m(lambda: util.resolve_name("..b", "pkg")), m(lambda: util.resolve_name(".", "pkg")))  # type: ignore[no-untyped-call]
print("source_hash:", util.source_hash(b"x = 1"), util.source_hash(b""), util.source_hash(bytearray(b"print(1)\n")), _imp.source_hash(0, b"x"), _imp.source_hash(-1, b"x"), m(lambda: util.source_hash("x")), m(lambda: _imp.source_hash(2**64, b"")), m(lambda: _imp.source_hash("k", b"")), m(lambda: _imp.source_hash(b"")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print("decode_source:", repr(util.decode_source(b"x = 1\r\ny = 2\n")), repr(util.decode_source(b"# -*- coding: latin-1 -*-\nz = '\xe9'\n")), repr(util.decode_source(b"")), repr(util.decode_source(b"\xef\xbb\xbfa = 1\n")), m(lambda: util.decode_source(b"# coding: nope\nx\n")), m(lambda: util.decode_source(b"\xff\xfe\n")))  # type: ignore[no-untyped-call]
lazy_spec = util.spec_from_loader("lazy_target", util.LazyLoader(json.__loader__))  # type: ignore[arg-type]
print("lazy:", type(lazy_spec.loader).__name__, type(lazy_spec.loader.loader).__name__, m(lambda: util.LazyLoader(3)), [c.__name__ for c in util.LazyLoader.__mro__], m(lambda: util.LazyLoader.factory(mach.SourceFileLoader)("n", "/p").loader.path))  # type: ignore[arg-type,attr-defined,no-untyped-call,union-attr]

# _imp
print("_imp:", _imp.__doc__, sorted(n for n in dir(_imp) if not n.startswith("__")))
print("builtins and frozen:", [_imp.is_builtin(n) for n in ("sys", "builtins", "math", "_imp", "json", "nope", "")], [_imp.is_frozen(n) for n in ("os", "codecs", "_frozen_importlib", "json", "sys", "")], _imp.is_frozen_package("os"), _imp.is_frozen_package("__phello__"), m(lambda: _imp.is_frozen_package("json")), _imp.find_frozen("os"), _imp.find_frozen("json"), _imp.find_frozen("__phello__"), len(_imp._frozen_module_names()), "os" in _imp._frozen_module_names(), _imp.init_frozen("json"), m(lambda: _imp.get_frozen_object("json")), m(lambda: _imp.is_builtin(1)), m(lambda: _imp.is_frozen()), m(lambda: _imp.find_frozen(1)), m(lambda: _imp.find_frozen("os", 1)), m(lambda: _imp.find_frozen(name="os")))  # type: ignore[arg-type,attr-defined,call-arg,no-untyped-call]
print("lock:", _imp.lock_held(), _imp.acquire_lock(), _imp.lock_held(), _imp.acquire_lock(), _imp.release_lock(), _imp.lock_held(), _imp.release_lock(), _imp.lock_held(), m(lambda: _imp.release_lock()), m(lambda: _imp.acquire_lock(1)), m(lambda: _imp.lock_held(x=1)))  # type: ignore[call-arg,func-returns-value,no-untyped-call]
print("others:", _imp.exec_builtin(sys), m(lambda: _imp._override_multi_interp_extensions_check(1)), m(lambda: _imp.create_builtin(1)), m(lambda: _imp.exec_builtin()), [type(getattr(_imp, n)).__name__ for n in ("is_builtin", "source_hash", "check_hash_based_pycs", "pyc_magic_number_token")], repr(_imp.is_builtin.__doc__), repr(_imp.source_hash.__doc__), repr(_imp.find_frozen.__doc__)[:60])  # type: ignore[arg-type,attr-defined,call-arg,no-untyped-call]

# inspect reads the suffixes
print("getmodulename:", [inspect.getmodulename(n) for n in ("a/b.py", "b.pyc", "c" + mach.EXTENSION_SUFFIXES[0], "d" + mach.EXTENSION_SUFFIXES[-1], "e.txt", "f.py.bak", "__init__.py")], inspect.getmodule(json.loads) is json, inspect.getmodule(inspect.getmodulename) is inspect, inspect.ismodule(importlib.machinery))
