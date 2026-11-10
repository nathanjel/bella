"""importlib._bootstrap_external: the path-based half of the import system, as a compiled program has it (step 3b, compiled
imports; decision of 2026-11-09).

CPython's module (Lib/importlib/_bootstrap_external.py, frozen as `_frozen_importlib_external`) finds modules on sys.path and
loads them from source, bytecode and extension files. A compiled program's modules are found by the build (spec section 8) and the
loaders of bootstrap.py run their compiled bodies, so this module keeps CPython's text for what a closed world still observes
(licences.md L-01), unchanged except where a line says `bella:`:

* the constants and the pure functions (the suffixes, MAGIC_NUMBER, `_pack_uint32`, `cache_from_source`, `source_from_cache`,
  `decode_source`, `spec_from_file_location`) as CPython has them; the suffixes and the magic number are the pin's build's,
  from the names table;
* the loader classes bootstrap.py defines (SourceFileLoader and its bases) are this module's, as their `__module__` says, and the
  others (SourcelessFileLoader, ExtensionFileLoader, AppleFrameworkLoader, NamespaceLoader, NamespacePath) exist with their
  pure methods, stopping by name where they would read a file or load an extension;
* the finders (PathFinder, FileFinder, WindowsRegistryFinder) exist for `importlib.machinery` and `isinstance`; a search stops by
  name, since the closed world is resolved at build time (E-04) and `sys.path_hooks` has no entries.

The module runs as `_frozen_importlib_external`, so its classes say so in `__module__`, as CPython's do; `_bootstrap` is the
`_frozen_importlib` module (bootstrap.py), set before this body runs as `_set_bootstrap_module` would set it.
"""
import _imp
import _io
import sys
import _warnings
# bella: `import marshal` (the runtime has no marshal: reading this module's `marshal` stops by name, through the names table)

_bootstrap = _bootstrap                           # noqa: PLW0127  # bella: set by the runtime before the body runs (_set_bootstrap_module)

_MS_WINDOWS = False                               # bella: the targets are posix (manifest [platform])

path_separators = ['/']                           # bella: _os.sep and altsep on posix
path_sep = path_separators[0]
path_sep_tuple = tuple(path_separators)
path_separators = ''.join(path_separators)
_pathseps_with_colon = {f':{s}' for s in path_separators}

_CASE_INSENSITIVE_PLATFORMS_STR_KEY = 'win',
_CASE_INSENSITIVE_PLATFORMS_BYTES_KEY = 'cygwin', 'darwin', 'ios', 'tvos', 'watchos'
_CASE_INSENSITIVE_PLATFORMS = (_CASE_INSENSITIVE_PLATFORMS_BYTES_KEY
                               + _CASE_INSENSITIVE_PLATFORMS_STR_KEY)


def _make_relax_case():
    # bella: linux is case-sensitive: the function that always answers False
    def _relax_case():
        """True if filenames must be checked case-insensitively and ignore environment flags are not set."""
        return False
    return _relax_case


_relax_case = _make_relax_case()


def _pack_uint32(x):
    """Convert a 32-bit integer to little-endian."""
    return (int(x) & 0xFFFFFFFF).to_bytes(4, 'little')


def _unpack_uint64(data):
    """Convert 8 bytes in little-endian to an integer."""
    assert len(data) == 8
    return int.from_bytes(data, 'little')


def _unpack_uint32(data):
    """Convert 4 bytes in little-endian to an integer."""
    assert len(data) == 4
    return int.from_bytes(data, 'little')


def _unpack_uint16(data):
    """Convert 2 bytes in little-endian to an integer."""
    assert len(data) == 2
    return int.from_bytes(data, 'little')


def _path_join(*path_parts):
    """Replacement for os.path.join()."""
    return path_sep.join([part.rstrip(path_separators)
                          for part in path_parts if part])


def _path_split(path):
    """Replacement for os.path.split()."""
    i = max(path.rfind(p) for p in path_separators)
    if i < 0:
        return '', path
    return path[:i], path[i + 1:]


def _path_stat(path):
    """Stat the path.

    Made a separate function to make it easier to override in experiments
    (e.g. cache stat results).

    """
    _bella_refuse("the import system's _path_stat (a path finder's search: the closed world is resolved at build time, E-04)")


def _path_is_mode_type(path, mode):
    """Test whether the path is the specified mode type."""
    try:
        stat_info = _path_stat(path)
    except OSError:
        return False
    return (stat_info.st_mode & 0o170000) == mode


def _path_isfile(path):
    """Replacement for os.path.isfile."""
    return _path_is_mode_type(path, 0o100000)


def _path_isdir(path):
    """Replacement for os.path.isdir."""
    if not path:
        path = _os_getcwd()
    return _path_is_mode_type(path, 0o040000)


def _path_isabs(path):
    """Replacement for os.path.isabs."""
    return path.startswith(path_separators)


def _path_abspath(path):
    """Replacement for os.path.abspath."""
    if not _path_isabs(path):
        for sep in path_separators:
            path = path.removeprefix(f".{sep}")
        return _path_join(_os_getcwd(), path)
    else:
        return path


def _os_getcwd():                                 # bella: posix.getcwd through the posix module, which _os stands for in CPython
    import posix
    return posix.getcwd()


def _os_fspath(path):                             # bella: _os.fspath
    import posix
    return posix.fspath(path)


def _write_atomic(path, data, mode=0o666):
    """Best-effort function to write data to a path atomically.
    Be prepared to handle a FileExistsError if concurrent writing of the
    temporary file is attempted."""
    _bella_refuse("the import system's _write_atomic (a compiled program writes no bytecode)")


_code_type = type(_write_atomic.__code__)

MAGIC_NUMBER = int(_cpython_table("imp:pyc_magic_number_token")).to_bytes(4, 'little')   # bella: _imp.pyc_magic_number_token, the pin's

_PYCACHE = '__pycache__'
_OPT = 'opt-'

SOURCE_SUFFIXES = ['.py']

EXTENSION_SUFFIXES = _cpython_table("imp:extension_suffixes").split("\n")   # bella: _imp.extension_suffixes(), the pin's build's

BYTECODE_SUFFIXES = ['.pyc']
# Deprecated.
DEBUG_BYTECODE_SUFFIXES = OPTIMIZED_BYTECODE_SUFFIXES = BYTECODE_SUFFIXES


def cache_from_source(path, *, optimization=None):
    """Given the path to a .py file, return the path to its .pyc file.

    The .py file does not need to exist; this simply returns the path to the
    .pyc file calculated as if the .py file were imported.

    The 'optimization' parameter controls the presumed optimization level of
    the bytecode file. If 'optimization' is not None, the string representation
    of the argument is taken and verified to be alphanumeric (else ValueError
    is raised).

    If sys.implementation.cache_tag is None then NotImplementedError is raised.

    """
    path = _os_fspath(path)  # bella: _os.fspath
    head, tail = _path_split(path)
    base, sep, rest = tail.rpartition('.')
    tag = sys.implementation.cache_tag
    if tag is None:
        raise NotImplementedError('sys.implementation.cache_tag is None')
    # bella: the tag is always None here (D-16: a compiled program has no bytecode cache), so the rest of CPython's
    # function, which builds the name, is never reached
    _bella_refuse("importlib.util.cache_from_source with a cache tag (D-16: sys.implementation.cache_tag is None)")


def source_from_cache(path):
    """Given the path to a .pyc. file, return the path to its .py file.

    The .pyc file does not need to exist; this simply returns the path to
    the .py file calculated to correspond to the .pyc file.  If path does
    not conform to PEP 3147/488 format, ValueError will be raised. If
    sys.implementation.cache_tag is None then NotImplementedError is raised.

    """
    # bella: sys.implementation.cache_tag is None (D-16): a compiled program has no bytecode cache
    raise NotImplementedError('sys.implementation.cache_tag is None')


def _get_sourcefile(bytecode_path):
    """Convert a bytecode file path to a source path (if possible).

    This function exists purely for backwards-compatibility for
    PyImport_ExecCodeModuleWithFilenames() in the C API.

    """
    if len(bytecode_path) == 0:
        return None
    rest, _, extension = bytecode_path.rpartition('.')
    if not rest or extension.lower()[-3:-1] != 'py':
        return bytecode_path
    try:
        source_path = source_from_cache(bytecode_path)
    except (NotImplementedError, ValueError):
        source_path = bytecode_path[:-1]

    return source_path if _path_isfile(source_path) else bytecode_path


def _get_cached(filename):
    if filename.endswith(tuple(SOURCE_SUFFIXES)):
        try:
            return cache_from_source(filename)
        except NotImplementedError:
            pass
    elif filename.endswith(tuple(BYTECODE_SUFFIXES)):
        return filename
    else:
        return None


def _calc_mode(path):
    """Calculate the mode permissions for a bytecode file."""
    try:
        mode = _path_stat(path).st_mode
    except OSError:
        mode = 0o666
    # We always ensure write access so we can update cached files
    # later even when the source files are read-only on Windows (#6074)
    mode |= 0o200
    return mode


def _classify_pyc(data, name, exc_details):
    """Perform basic validity checking of a pyc header and return the flags field,
    which determines how the pyc should be further validated against the source.

    *data* is the contents of the pyc file. (Only the first 16 bytes are
    required, though.)

    *name* is the name of the module being imported. It is used for logging.

    *exc_details* is a dictionary passed to ImportError if it raised for
    improved debugging.

    ImportError is raised when the magic number is incorrect or when the flags
    field is invalid. EOFError is raised when the data is found to be truncated.

    """
    magic = data[:4]
    if magic != MAGIC_NUMBER:
        message = f'bad magic number in {name!r}: {magic!r}'
        raise ImportError(message, **exc_details)
    if len(data) < 16:
        message = f'reached EOF while reading pyc header of {name!r}'
        raise EOFError(message)
    flags = _unpack_uint32(data[4:8])
    # Only the first two flags are defined.
    if flags & ~0b11:
        message = f'invalid flags {flags!r} in {name!r}'
        raise ImportError(message, **exc_details)
    return flags


def _compile_bytecode(data, name=None, bytecode_path=None, source_path=None):
    """Compile bytecode as found in a pyc."""
    _bella_refuse("the import system's _compile_bytecode (bytecode: a compiled program has none, E-02)")


def _code_to_timestamp_pyc(code, mtime=0, source_size=0):
    "Produce the data for a timestamp-based pyc."
    _bella_refuse("the import system's _code_to_timestamp_pyc (bytecode: a compiled program has none, E-02)")


def _code_to_hash_pyc(code, source_hash, checked=True):
    "Produce the data for a hash-based pyc."
    _bella_refuse("the import system's _code_to_hash_pyc (bytecode: a compiled program has none, E-02)")


def decode_source(source_bytes):
    """Decode bytes representing source code and return the string.

    Universal newline support is used in the decoding.
    """
    import tokenize  # To avoid bootstrap issues.
    import _io
    source_bytes_readline = _io.BytesIO(source_bytes).readline
    encoding = tokenize.detect_encoding(source_bytes_readline)
    return _io.TextIOWrapper(_io.BytesIO(source_bytes), encoding=encoding[0], newline=None).read()


# Module specifications #######################################################

_POPULATE = object()


def spec_from_file_location(name, location=None, *, loader=None,
                            submodule_search_locations=_POPULATE):
    """Return a module spec based on a file location.

    To indicate that the module is a package, set
    submodule_search_locations to a list of directory paths.  An
    empty list is sufficient, though its not otherwise useful to the
    import system.

    The loader must take a spec as its only __init__() arg.

    """
    if location is None:
        # The caller may simply want a partially populated location-
        # oriented spec.  So we set the location to a bogus value and
        # fill in as much as we can.
        location = '<unknown>'
        if hasattr(loader, 'get_filename'):
            # ExecutionLoader
            try:
                location = loader.get_filename(name)
            except ImportError:
                pass
    else:
        location = _os_fspath(location)
        try:
            location = _path_abspath(location)
        except OSError:
            pass

    # If the location is on the filesystem, but doesn't actually exist,
    # we could return None here, indicating that the location is not
    # valid.  However, we don't have a good way of testing since an
    # indirect location (e.g. a zip file or URL) will look like a
    # non-existent file relative to the filesystem.

    spec = _bootstrap.ModuleSpec(name, loader, origin=location)
    spec._set_fileattr = True

    # Pick a loader if one wasn't provided.
    if loader is None:
        for loader_class, suffixes in _get_supported_file_loaders():
            if location.endswith(tuple(suffixes)):
                loader = loader_class(name, location)
                spec.loader = loader
                break
        else:
            return None

    # Set submodule_search_paths appropriately.
    if submodule_search_locations is _POPULATE:
        # Check the loader.
        if hasattr(loader, 'is_package'):
            try:
                is_package = loader.is_package(name)
            except ImportError:
                pass
            else:
                if is_package:
                    spec.submodule_search_locations = []
    else:
        spec.submodule_search_locations = submodule_search_locations
    if spec.submodule_search_locations == []:
        if location:
            dirname = _path_split(location)[0]
            spec.submodule_search_locations.append(dirname)

    return spec


def _bless_my_loader(module_globals):
    """Helper function for _warnings.c

    See GH#97850 for details.
    """
    # 2022-10-06(warsaw): For now, this helper is only used in _warnings.c and
    # that use case only has the module globals.  This function could be
    # extended to accept either that or a module object.  However, in the
    # latter case, it would be better to raise certain exceptions when looking
    # at a module, which should have either a __loader__ or __spec__.loader.
    # For backward compatibility, it is possible that we'll get an empty
    # dictionary for the module globals, and that cannot raise an exception.
    if not isinstance(module_globals, dict):
        return None

    missing = object()
    loader = module_globals.get('__loader__', None)
    spec = module_globals.get('__spec__', missing)

    if loader is None:
        if spec is missing:
            # If working with a module:
            # raise AttributeError('Module globals is missing a __spec__')
            return None
        elif spec is None:
            raise ValueError('Module globals is missing a __spec__.loader')

    spec_loader = getattr(spec, 'loader', missing)

    if spec_loader in (missing, None):
        if loader is None:
            exc = AttributeError if spec_loader is missing else ValueError
            raise exc('Module globals is missing a __spec__.loader')
        _bella_refuse("_bless_my_loader's DeprecationWarning for a module without __spec__.loader (warnings from the import system: step 3b)")
        spec_loader = loader

    assert spec_loader is not None
    if loader is not None and loader != spec_loader:
        _bella_refuse("_bless_my_loader's DeprecationWarning for a __loader__ that is not __spec__.loader (step 3b)")

    return spec_loader


# Loaders #####################################################################

class WindowsRegistryFinder:

    """Meta path finder for modules declared in the Windows registry."""

    REGISTRY_KEY = (
        'Software\\Python\\PythonCore\\{sys_version}'
        '\\Modules\\{fullname}')
    REGISTRY_KEY_DEBUG = (
        'Software\\Python\\PythonCore\\{sys_version}'
        '\\Modules\\{fullname}\\Debug')
    DEBUG_BUILD = (_MS_WINDOWS and '_d.pyd' in EXTENSION_SUFFIXES)

    @staticmethod
    def _open_registry(key):
        _bella_refuse("WindowsRegistryFinder (the Windows registry: the targets are posix)")

    @classmethod
    def _search_registry(cls, fullname):
        _bella_refuse("WindowsRegistryFinder (the Windows registry: the targets are posix)")

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        _bella_refuse("WindowsRegistryFinder (the Windows registry: the targets are posix)")


# bella: bootstrap.py's loader classes are this module's (their __module__ says so), as the import system itself uses them
_LoaderBasics = _bootstrap._LoaderBasics
SourceLoader = _bootstrap.SourceLoader
FileLoader = _bootstrap.FileLoader
SourceFileLoader = _bootstrap.SourceFileLoader


class SourcelessFileLoader(FileLoader, _LoaderBasics):

    """Loader which handles sourceless file imports."""

    def get_code(self, fullname):
        _bella_refuse("SourcelessFileLoader.get_code (bytecode: a compiled program has none, E-02)")

    def get_source(self, fullname):
        """Return None as there is no source code."""
        return None


class ExtensionFileLoader(FileLoader, _LoaderBasics):

    """Loader for extension modules.

    The constructor is designed to work with FileFinder.

    """

    def __init__(self, name, path):
        self.name = name
        self.path = path

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.__dict__ == other.__dict__)

    def __hash__(self):
        return hash(self.name) ^ hash(self.path)

    def create_module(self, spec):
        """Create an uninitialized extension module"""
        _bella_refuse("ExtensionFileLoader.create_module (an extension module: a compiled program has none)")

    def exec_module(self, module):
        """Initialize an extension module"""
        _bella_refuse("ExtensionFileLoader.exec_module (an extension module: a compiled program has none)")

    def is_package(self, fullname):
        """Return True if the extension module is a package."""
        file_name = _path_split(self.path)[1]
        return any(file_name == '__init__' + suffix
                   for suffix in EXTENSION_SUFFIXES)

    def get_code(self, fullname):
        """Return None as an extension module cannot create a code object."""
        return None

    def get_source(self, fullname):
        """Return None as extension modules have no source code."""
        return None

    def get_filename(self, name=None, *args, **kwargs):
        """Return the path to the source file as found by the finder."""
        # bella: @_check_name, written out: the wrapper's parameters and its check, then the method, which takes the name alone
        if name is None:
            name = self.name
        elif self.name != name:
            raise ImportError(f'loader for {self.name} cannot handle {name}', name=name)
        if args or kwargs:
            _bella_refuse("ExtensionFileLoader.get_filename with arguments beyond the name (the method under @_check_name takes none: a TypeError of its own)")
        return self.path


class NamespacePath:
    """Represents a namespace package's path.

    It uses the module *name* to find its parent module, and from there it looks
    up the parent's __path__. When this changes, the module's own path is
    recomputed, using *path_finder*. The initial value is set to *path*.

    For top-level modules, the parent module's path is sys.path.

    *path_finder* should be a callable with the same signature as
    MetaPathFinder.find_spec((fullname, path, target=None) -> spec).
    """

    # When invalidate_caches() is called, this epoch is incremented
    # https://bugs.python.org/issue45703
    _epoch = 0

    def __init__(self, name, path, path_finder):
        self._name = name
        self._path = path
        self._last_parent_path = tuple(self._get_parent_path())
        self._last_epoch = self._epoch
        self._path_finder = path_finder

    def _find_parent_path_names(self):
        """Returns a tuple of (parent-module-name, parent-path-attr-name)"""
        parent, dot, me = self._name.rpartition('.')
        if dot == '':
            # This is a top-level module. sys.path contains the parent path.
            return 'sys', 'path'
        # Not a top-level module. parent-module.__path__ contains the
        #  parent path.
        return parent, '__path__'

    def _get_parent_path(self):
        parent_module_name, path_attr_name = self._find_parent_path_names()
        try:
            module = sys.modules[parent_module_name]
        except KeyError as e:
            raise ModuleNotFoundError(
                f"{parent_module_name!r} must be imported before finding {self._name!r}.",
                name=parent_module_name,
            ) from e
        else:
            return getattr(module, path_attr_name)

    def _recalculate(self):
        # If the parent's path has changed, recalculate _path
        parent_path = tuple(self._get_parent_path())  # Make a copy
        if parent_path != self._last_parent_path or self._epoch != self._last_epoch:
            spec = self._path_finder(self._name, parent_path)
            # Note that no changes are made if a loader is returned, but we
            #  do remember the new parent path
            if spec is not None and spec.loader is None:
                if spec.submodule_search_locations:
                    self._path = spec.submodule_search_locations
            self._last_parent_path = parent_path     # Save the copy
            self._last_epoch = self._epoch
        return self._path

    def __iter__(self):
        return iter(self._recalculate())

    def __getitem__(self, index):
        return self._recalculate()[index]

    def __setitem__(self, index, path):
        self._path[index] = path

    def __len__(self):
        return len(self._recalculate())

    def __repr__(self):
        return f'NamespacePath({self._path!r})'

    def __contains__(self, item):
        return item in self._recalculate()

    def append(self, item):
        self._path.append(item)


# For backwards-compatibility for anyone desperate enough to get at the class back in the day.
_NamespacePath = NamespacePath


# This class is actually exposed publicly in a namespace package's __loader__
# attribute, so it should be available through a non-private name.
# https://github.com/python/cpython/issues/92054
class NamespaceLoader:
    def __init__(self, name, path, path_finder):
        self._path = NamespacePath(name, path, path_finder)

    def is_package(self, fullname):
        return True

    def get_source(self, fullname):
        return ''

    def get_code(self, fullname):
        _bella_refuse("NamespaceLoader.get_code (compile() at runtime, E-01)")

    def create_module(self, spec):
        """Use default semantics for module creation."""

    def exec_module(self, module):
        pass

    def get_resource_reader(self, module):
        _bella_refuse("NamespaceLoader.get_resource_reader (importlib.resources is [P2+])")


# We use this exclusively in module_from_spec() for backward-compatibility.
_NamespaceLoader = NamespaceLoader


# Finders #####################################################################

class PathFinder:

    """Meta path finder for sys.path and package __path__ attributes."""

    @staticmethod
    def invalidate_caches():
        """Call the invalidate_caches() method on all path entry finders
        stored in sys.path_importer_cache (where implemented)."""
        for name, finder in list(sys.path_importer_cache.items()):
            # Drop entry if finder name is a relative path. The current
            # working directory may have changed.
            if finder is None or not _path_isabs(name):
                del sys.path_importer_cache[name]
            elif hasattr(finder, 'invalidate_caches'):
                finder.invalidate_caches()
        # Also invalidate the caches of NamespacePaths
        # https://bugs.python.org/issue45703
        NamespacePath._epoch += 1
        # bella: importlib.metadata's MetadataPathFinder is outside the phase-1 manifest; its caches do not exist here

    @staticmethod
    def _path_hooks(path):
        """Search sys.path_hooks for a finder for 'path'."""
        _bella_refuse("PathFinder._path_hooks (a path finder's search: the closed world is resolved at build time, E-04)")

    @classmethod
    def _path_importer_cache(cls, path):
        """Get the finder for the path entry from sys.path_importer_cache.

        If the path entry is not in the cache, find the appropriate finder
        and cache it. If no finder is available, store None.

        """
        _bella_refuse("PathFinder._path_importer_cache (a path finder's search: the closed world is resolved at build time, E-04)")

    @classmethod
    def _get_spec(cls, fullname, path, target=None):
        """Find the loader or namespace_path for this module/package name."""
        _bella_refuse("PathFinder._get_spec (a path finder's search: the closed world is resolved at build time, E-04)")

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """Try to find a spec for 'fullname' on sys.path or 'path'.

        The search is based on sys.path_hooks and sys.path_importer_cache.
        """
        _bella_refuse("PathFinder.find_spec (a path finder's search: the closed world is resolved at build time, E-04)")

    @classmethod
    def discover(cls, parent=None):
        if parent is None:
            path = sys.path
        elif parent.submodule_search_locations is None:
            raise ValueError(f'{parent} is not a package module')
        else:
            path = parent.submodule_search_locations

        for entry in set(path):
            if not isinstance(entry, str):
                continue
            if (finder := cls._path_importer_cache(entry)) is None:
                continue
            if discover := getattr(finder, 'discover', None):
                yield from discover(parent)

    @staticmethod
    def find_distributions(*args, **kwargs):
        """
        Find distributions.

        Return an iterable of all Distribution instances capable of
        loading the metadata for packages matching ``context.name``
        (or all names if ``None`` indicated) along the paths in the list
        of directories ``context.path``.
        """
        _bella_refuse("PathFinder.find_distributions (importlib.metadata is outside the phase-1 manifest)")


class FileFinder:

    """File-based finder.

    Interactions with the file system are cached for performance, being
    refreshed when the directory the finder is handling has been modified.

    """

    def __init__(self, path, *loader_details):
        """Initialize with the path to search on and a variable number of
        2-tuples containing the loader and the file suffixes the loader
        recognizes."""
        loaders = []
        for loader, suffixes in loader_details:
            loaders.extend((suffix, loader) for suffix in suffixes)
        self._loaders = loaders
        # Base (directory) path
        if not path or path == '.':
            self.path = _os_getcwd()
        else:
            self.path = _path_abspath(path)
        self._path_mtime = -1
        self._path_cache = set()
        self._relaxed_path_cache = set()

    def invalidate_caches(self):
        """Invalidate the directory mtime."""
        self._path_mtime = -1

    def _get_spec(self, loader_class, fullname, path, smsl, target):
        loader = loader_class(fullname, path)
        return spec_from_file_location(fullname, path, loader=loader,
                                       submodule_search_locations=smsl)

    def find_spec(self, fullname, target=None):
        """Try to find a spec for the specified module.

        Returns the matching spec, or None if not found.
        """
        _bella_refuse("FileFinder.find_spec (a path finder's search: the closed world is resolved at build time, E-04)")

    def _fill_cache(self):
        """Fill the cache of potential modules and packages for this directory."""
        _bella_refuse("FileFinder._fill_cache (a directory listing for a path finder's search, E-04)")

    @classmethod
    def path_hook(cls, *loader_details):
        """A class method which returns a closure to use on sys.path_hook
        which will return an instance using the specified loaders and the path
        called on the closure.

        If the path called on the closure is not a directory, ImportError is
        raised.

        """
        def path_hook_for_FileFinder(path):
            """Path hook for importlib.machinery.FileFinder."""
            if not _path_isdir(path):
                raise ImportError('only directories are supported', path=path)
            return cls(path, *loader_details)

        return path_hook_for_FileFinder

    def _find_children(self):
        # bella: _os.scandir of the directory, for a search the closed world does not make (E-04); a generator, as CPython's
        # is, so nothing is asked of the directory before the first item
        _bella_refuse("FileFinder._find_children (a directory listing for a path finder's search, E-04)")
        yield

    def discover(self, parent=None):
        if parent and parent.submodule_search_locations is None:
            raise ValueError(f'{parent} is not a package module')

        module_prefix = f'{parent.name}.' if parent else ''
        for child_name in self._find_children():
            if spec := self.find_spec(module_prefix + child_name):
                yield spec

    def __repr__(self):
        return f'FileFinder({self.path!r})'


class AppleFrameworkLoader(ExtensionFileLoader):
    """A loader for modules that have been packaged as frameworks for
    compatibility with Apple's iOS App Store policies.
    """
    def create_module(self, spec):
        _bella_refuse("AppleFrameworkLoader.create_module (an extension module: a compiled program has none)")


# Import setup ###############################################################

def _fix_up_module(ns, name, pathname, cpathname=None):
    # This function is used by PyImport_ExecCodeModuleObject().
    loader = ns.get('__loader__')
    spec = ns.get('__spec__')
    if not loader:
        if spec:
            loader = spec.loader
        elif pathname == cpathname:
            loader = SourcelessFileLoader(name, pathname)
        else:
            loader = SourceFileLoader(name, pathname)
    if not spec:
        spec = spec_from_file_location(name, pathname, loader=loader)
        if cpathname:
            spec.cached = _path_abspath(cpathname)
    try:
        ns['__spec__'] = spec
        ns['__loader__'] = loader
        ns['__file__'] = pathname
        ns['__cached__'] = cpathname
    except Exception:
        # Not important enough to report.
        pass


def _get_supported_file_loaders():
    """Returns a list of file-based module loaders.

    Each item is a tuple (loader, suffixes).
    """
    # bella: _imp.create_dynamic exists, so the extension loader is listed, as on the pin (linux)
    extension_loaders = [(ExtensionFileLoader, list(EXTENSION_SUFFIXES))]
    source = SourceFileLoader, SOURCE_SUFFIXES
    bytecode = SourcelessFileLoader, BYTECODE_SUFFIXES
    return extension_loaders + [source, bytecode]


def _set_bootstrap_module(_bootstrap_module):
    global _bootstrap
    _bootstrap = _bootstrap_module


def _install(_bootstrap_module):
    """Install the path-based import components."""
    _set_bootstrap_module(_bootstrap_module)
    _bella_refuse("_frozen_importlib_external._install (installing the path finders: the closed world is resolved at build time, E-04)")
