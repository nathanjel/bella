"""importlib._bootstrap: the import system of a compiled program (step 3b, compiled imports).

CPython's import system is written in Python (Lib/importlib/_bootstrap.py, frozen into the
interpreter as `_frozen_importlib`) under a fast path in C (Python/import.c). Bella keeps the
same split: the runtime's `__import__` is import.c's `PyImport_ImportModuleLevelObject`, in
C++ (runtime/src/imports.cpp), and it calls this module's `_find_and_load` and
`_handle_fromlist` where import.c calls them. This module is CPython 3.15.2's text for the parts
a closed world uses (licences.md L-01), unchanged except where a line says `bella:`:

* The finder is the closed world's: every module the build found is compiled into the program
  (spec section 8), and `_find_spec` asks the runtime's registry (`_bella_find`) where CPython
  walks sys.meta_path; a module the registry does not have is not installed. The spec and loader
  are the ones CPython's path finder makes for a source file: a `ModuleSpec` with a location and
  a `SourceFileLoader` (of `_frozen_importlib_external`), whose `exec_module` runs the module's
  compiled body in the module's namespace (`_bella_exec`) where CPython execs its code.
* A program has one thread in phase 1, so a module lock is always this thread's own: taking it
  waits for nothing and never deadlocks, and `_find_and_load` does what CPython's does when the
  lock is free.
* What phase 1 lacks is refused where it would run (`_bella_refuse`, exit 70): the loader's
  methods that read files, and lazy submodules (PEP 810, next). An ImportWarning goes to
  `_bella_import_warning`: the default filters ignore it, so it has no effect until a warnings
  module could have changed them, and is refused from then on.

The module runs as `_frozen_importlib`, so its classes say so in `__module__`, as CPython's do.
"""
import sys

__intrinsics__ = ["_find_and_load", "_handle_fromlist", "_module_repr", "_setup"]

_bootstrap_external = None


def _new_module(name):
    return type(sys)(name)


def _lock_unlock_module(name):
    """Acquires then releases the module lock for a given module name.

    This is used to ensure a module is completely initialized, in the
    event it is being imported by another thread.
    """
    # bella: one thread: the lock is free or this thread's own, so taking it waits for nothing
    return None


def _call_with_frames_removed(f, *args, **kwds):
    """remove_importlib_frames in import.c will always remove sequences
    of importlib frames that end with a call to this function

    Use it instead of a normal call in places where including the importlib
    frames introduces unwanted noise into the traceback (e.g. when executing
    module code)
    """
    return f(*args, **kwds)


# Module specifications #######################################################

def _module_repr(module):
    """The implementation of ModuleType.__repr__()."""
    loader = getattr(module, '__loader__', None)
    if spec := getattr(module, "__spec__", None):
        return _module_repr_from_spec(spec)
    # Fall through to a catch-all which always succeeds.
    try:
        name = module.__name__
    except AttributeError:
        name = '?'
    try:
        filename = module.__file__
    except AttributeError:
        if loader is None:
            return f'<module {name!r}>'
        else:
            return f'<module {name!r} ({loader!r})>'
    else:
        return f'<module {name!r} from {filename!r}>'


class ModuleSpec:
    """The specification for a module, used for loading.

    A module's spec is the source for information about the module.  For
    data associated with the module, including source, use the spec's
    loader.

    `name` is the absolute name of the module.  `loader` is the loader
    to use when loading the module.  `parent` is the name of the
    package the module is in.  The parent is derived from the name.

    `is_package` determines if the module is considered a package or
    not.  On modules this is reflected by the `__path__` attribute.

    `origin` is the specific location used by the loader from which to
    load the module, if that information is available.  When filename is
    set, origin will match.

    `has_location` indicates that a spec's "origin" reflects a location.
    When this is True, `__file__` attribute of the module is set.

    `cached` is the location of the cached bytecode file, if any.

    `submodule_search_locations` is the sequence of path entries to
    search when importing submodules.  If set, is_package should be
    True--and False otherwise.

    Packages are simply modules that (may) have submodules.  If a spec
    has a non-None value in `submodule_search_locations`, the import
    system will consider modules loaded from the spec as packages.

    Only finders (see importlib.abc.MetaPathFinder and
    importlib.abc.PathEntryFinder) should modify ModuleSpec instances.

    """

    def __init__(self, name, loader, *, origin=None, loader_state=None,
                 is_package=None):
        self.name = name
        self.loader = loader
        self.origin = origin
        self.loader_state = loader_state
        self.submodule_search_locations = [] if is_package else None
        self._uninitialized_submodules = []

        # file-location attributes
        self._set_fileattr = False
        self._cached = None

    def __repr__(self):
        args = [f'name={self.name!r}', f'loader={self.loader!r}']
        if self.origin is not None:
            args.append(f'origin={self.origin!r}')
        if self.submodule_search_locations is not None:
            args.append(f'submodule_search_locations={self.submodule_search_locations}')
        return f'{self.__class__.__name__}({", ".join(args)})'

    def __eq__(self, other):
        smsl = self.submodule_search_locations
        try:
            return (self.name == other.name and
                    self.loader == other.loader and
                    self.origin == other.origin and
                    smsl == other.submodule_search_locations and
                    self.cached == other.cached and
                    self.has_location == other.has_location)
        except AttributeError:
            return NotImplemented

    @property
    def cached(self):
        if self._cached is None:
            if self.origin is not None and self._set_fileattr:
                # bella: _bootstrap_external's _get_cached, below
                self._cached = _get_cached(self.origin)
        return self._cached

    @cached.setter
    def cached(self, cached):
        self._cached = cached

    @property
    def parent(self):
        """The name of the module's parent."""
        if self.submodule_search_locations is None:
            return self.name.rpartition('.')[0]
        else:
            return self.name

    @property
    def has_location(self):
        return self._set_fileattr

    @has_location.setter
    def has_location(self, value):
        self._set_fileattr = bool(value)


def _spec_from_module(module, loader=None, origin=None):
    # This function is meant for use in _setup().
    try:
        spec = module.__spec__
    except AttributeError:
        pass
    else:
        if spec is not None:
            return spec

    name = module.__name__
    if loader is None:
        try:
            loader = module.__loader__
        except AttributeError:
            # loader will stay None.
            pass
    try:
        location = module.__file__
    except AttributeError:
        location = None
    if origin is None:
        if loader is not None:
            origin = getattr(loader, '_ORIGIN', None)
        if not origin and location is not None:
            origin = location
    try:
        submodule_search_locations = list(module.__path__)
    except AttributeError:
        submodule_search_locations = None

    spec = ModuleSpec(name, loader, origin=origin)
    spec._set_fileattr = False if location is None else (origin == location)
    spec.cached = None
    spec.submodule_search_locations = submodule_search_locations
    return spec


def _init_module_attrs(spec, module, *, override=False):
    # The passed-in module may be not support attribute assignment,
    # in which case we simply don't set the attributes.
    # __name__
    if (override or getattr(module, '__name__', None) is None):
        try:
            module.__name__ = spec.name
        except AttributeError:
            pass
    # __loader__
    if override or getattr(module, '__loader__', None) is None:
        loader = spec.loader
        if loader is None:
            # A backward compatibility hack.
            if spec.submodule_search_locations is not None:
                if _bootstrap_external is None:
                    raise NotImplementedError
                NamespaceLoader = _bootstrap_external.NamespaceLoader

                loader = NamespaceLoader.__new__(NamespaceLoader)
                loader._path = spec.submodule_search_locations
                spec.loader = loader
                # While the docs say that module.__file__ is not set for
                # built-in modules, and the code below will avoid setting it if
                # spec.has_location is false, this is incorrect for namespace
                # packages.  Namespace packages have no location, but their
                # __spec__.origin is None, and thus their module.__file__
                # should also be None for consistency.  While a bit of a hack,
                # this is the best place to ensure this consistency.
                #
                # See bpo-32305
                module.__file__ = None
        try:
            module.__loader__ = loader
        except AttributeError:
            pass
    # __package__
    if override or getattr(module, '__package__', None) is None:
        try:
            module.__package__ = spec.parent
        except AttributeError:
            pass
    # __spec__
    try:
        module.__spec__ = spec
    except AttributeError:
        pass
    # __path__
    if override or getattr(module, '__path__', None) is None:
        if spec.submodule_search_locations is not None:
            # XXX We should extend __path__ if it's already a list.
            try:
                module.__path__ = spec.submodule_search_locations
            except AttributeError:
                pass
    # __file__
    if spec.has_location:
        if override or getattr(module, '__file__', None) is None:
            try:
                module.__file__ = spec.origin
            except AttributeError:
                pass

    return module


def module_from_spec(spec):
    """Create a module based on the provided spec."""
    # Typically loaders will not implement create_module().
    module = None
    if hasattr(spec.loader, 'create_module'):
        # If create_module() returns `None` then it means default
        # module creation should be used.
        module = spec.loader.create_module(spec)
    elif hasattr(spec.loader, 'exec_module'):
        raise ImportError('loaders that define exec_module() '
                          'must also define create_module()')
    if module is None:
        module = _new_module(spec.name)
    _init_module_attrs(spec, module)
    return module


def _module_repr_from_spec(spec):
    """Return the repr to use for the module."""
    name = '?' if spec.name is None else spec.name
    if spec.origin is None:
        loader = spec.loader
        if loader is None:
            return f'<module {name!r}>'
        elif (
            _bootstrap_external is not None
            and isinstance(loader, _bootstrap_external.NamespaceLoader)
        ):
            return f'<module {name!r} (namespace) from {list(loader._path)}>'
        else:
            return f'<module {name!r} ({loader!r})>'
    else:
        if spec.has_location:
            return f'<module {name!r} from {spec.origin!r}>'
        else:
            return f'<module {spec.name!r} ({spec.origin})>'


def _load_unlocked(spec):
    # A helper for direct use by the import system.
    module = module_from_spec(spec)

    # This must be done before putting the module in sys.modules
    # (otherwise an optimization shortcut in import.c becomes
    # wrong).
    spec._initializing = True
    try:
        sys.modules[spec.name] = module
        try:
            if spec.loader is None:
                if spec.submodule_search_locations is None:
                    raise ImportError('missing loader', name=spec.name)
                # A namespace package so do nothing.
            else:
                spec.loader.exec_module(module)
        except:  # noqa: E722  # CPython's own text: any exception
            try:
                del sys.modules[spec.name]
            except KeyError:
                pass
            raise
        # Move the module to the end of sys.modules.
        # We don't ensure that the import-related module attributes get
        # set in the sys.modules replacement case.  Such modules are on
        # their own.
        module = sys.modules.pop(spec.name)
        sys.modules[spec.name] = module
        # bella: no -v (sys.flags.verbose is 0), so no _verbose_message
    finally:
        spec._initializing = False

    return module


# Loaders #####################################################################

class BuiltinImporter:

    """Meta path import for built-in modules.

    All methods are either class or static methods to avoid the need to
    instantiate the class.

    """

    _ORIGIN = "built-in"

    # bella: the runtime makes its built-in modules (sys, builtins) before any program code runs,
    # and finds no other; the class is the loader of their specs. Its methods, which ask _imp,
    # are refused until a program reaches them.
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        _bella_refuse("importlib.machinery.BuiltinImporter.find_spec (step 3b: the core modules)")

    @staticmethod
    def create_module(spec):
        """Create a built-in module"""
        _bella_refuse("importlib.machinery.BuiltinImporter.create_module (step 3b: the core modules)")

    @staticmethod
    def exec_module(module):
        """Exec a built-in module"""
        _bella_refuse("importlib.machinery.BuiltinImporter.exec_module (step 3b: the core modules)")


# bella: _bootstrap_external's source loader, as its path finder makes one for a .py file. A
# compiled program has no source to read at runtime, so the methods that read files are refused;
# what a module's namespace shows (the loader's type, name and path, its equality) is CPython's.

def _path_split(path):
    """Replacement for os.path.split()."""
    i = path.rfind('/')  # bella: path_separators is '/' on the targets (posix)
    if i < 0:
        return '', path
    return path[:i], path[i + 1:]


def _path_join(*path_parts):
    """Replacement for os.path.join()."""
    return '/'.join([part.rstrip('/')
                     for part in path_parts if part])


def cache_from_source(path, debug_override=None, *, optimization=None):
    """Given the path to a .py file, return the path to its .pyc file.

    The .py file does not need to exist; this simply returns the path to the
    .pyc file calculated as if the .py file were imported.

    The 'optimization' parameter controls the presumed optimization level of
    the bytecode file. If 'optimization' is not None, the string representation
    of the argument is taken and verified to be alphanumeric (else ValueError
    is raised).

    The debug_override parameter is deprecated. If debug_override is not None,
    a True value is the same as setting 'optimization' to the empty string
    while a False value is equivalent to setting 'optimization' to '1'.

    If sys.implementation.cache_tag is None then NotImplementedError is raised.

    """
    if debug_override is not None or optimization is not None:
        _bella_refuse("importlib.util.cache_from_source with debug_override or optimization (step 3b)")
    head, tail = _path_split(path)
    base, sep, rest = tail.rpartition('.')
    # bella: sys.implementation.cache_tag is 3.15's (D-16 changes only the implementation's name),
    # sys.flags.optimize is 0 and sys.pycache_prefix is None
    tag = 'cpython-315'
    almost_filename = ''.join([(base if base else rest), sep, tag])
    filename = almost_filename + '.pyc'
    return _path_join(head, '__pycache__', filename)


def _get_cached(filename):
    if filename.endswith('.py'):  # bella: SOURCE_SUFFIXES
        try:
            return cache_from_source(filename)
        except NotImplementedError:
            pass
    elif filename.endswith('.pyc'):
        return filename
    else:
        return None


class SourceFileLoader:

    """Concrete implementation of SourceLoader using the file system."""

    __module__ = '_frozen_importlib_external'

    def __init__(self, fullname, path):
        """Cache the module name and the path to the file found by the
        finder."""
        self.name = fullname
        self.path = path

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.__dict__ == other.__dict__)

    def __hash__(self):
        return hash(self.name) ^ hash(self.path)

    def get_filename(self, name=None):
        """Return the path to the source file as found by the finder."""
        # bella: FileLoader.get_filename under _check_name
        if name is None:
            name = self.name
        elif self.name != name:
            # bella: CPython's text formats with %, which the runtime lacks yet; the same message
            raise ImportError(f'loader for {self.name} cannot handle {name}', name=name)
        return self.path

    def is_package(self, fullname):
        """Concrete implementation of InspectLoader.is_package by checking if
        the path returned by get_filename has a filename of '__init__.py'."""
        filename = _path_split(self.get_filename(fullname))[1]
        filename_base = filename.rsplit('.', 1)[0]
        tail_name = fullname.rpartition('.')[2]
        return filename_base == '__init__' and tail_name != '__init__'

    def create_module(self, spec):
        """Use default semantics for module creation."""

    def exec_module(self, module):
        """Execute the module."""
        # bella: CPython gets the code (get_code(module.__name__), which checks the name) and execs
        # it in module.__dict__; a compiled program runs the module's compiled body there
        self.get_filename(module.__name__)
        _bella_exec(self.name, module)

    def get_code(self, fullname):
        _bella_refuse("a source loader's get_code (a compiled program has no code objects to load)")

    def get_source(self, fullname):
        _bella_refuse("a source loader's get_source (step 3b: reading files)")

    def get_data(self, path):
        _bella_refuse("a source loader's get_data (step 3b: reading files)")

    def path_stats(self, path):
        _bella_refuse("a source loader's path_stats (step 3b: reading files)")

    def source_to_code(self, data, path, *, _optimize=-1):
        _bella_refuse("a source loader's source_to_code (E-01: no compiler at runtime)")

    def load_module(self, fullname):
        _bella_refuse("a source loader's load_module (step 3b)")

    def get_resource_reader(self, module):
        _bella_refuse("a source loader's get_resource_reader (importlib.resources is [P2+])")


def _spec_from_compiled(name):
    """bella: what CPython's path finder returns for a source file the closed world has
    (FileFinder.find_spec through spec_from_file_location): a spec with a location, its loader,
    and for a package the package's directory to search."""
    found = _bella_find(name)
    if found is None:
        return None
    origin, is_package = found
    spec = ModuleSpec(name, SourceFileLoader(name, origin), origin=origin)
    spec._set_fileattr = True
    if is_package:
        spec.submodule_search_locations = [_path_split(origin)[0]]
    return spec


# Import itself ###############################################################

def _find_spec(name, path, target=None):
    """Find a module's spec."""
    # bella: the closed world's registry stands for sys.meta_path's finders (spec section 8)

    # We check sys.modules here for the reload case.  While a passed-in
    # target will usually indicate a reload there is no guarantee, whereas
    # sys.modules provides one.
    is_reload = name in sys.modules
    spec = _spec_from_compiled(name)
    if spec is not None:
        # The parent import may have already imported this module.
        if not is_reload and name in sys.modules:
            module = sys.modules[name]
            try:
                __spec__ = module.__spec__
            except AttributeError:
                # We use the found spec since that is the one that
                # we would have used if the parent module hadn't
                # beaten us to the punch.
                return spec
            else:
                if __spec__ is None:
                    return spec
                else:
                    return __spec__
        else:
            return spec
    else:
        return None


_ERR_MSG_PREFIX = 'No module named '


def _find_and_load_unlocked(name, import_):
    path = None
    parent = name.rpartition('.')[0]
    parent_spec = None
    if parent:
        # _resolve_parents() has normally imported the parent already.  It can
        # be missing again by now if its import failed in another thread or
        # something removed it from sys.modules; it is then imported afresh,
        # like any other module that is not in sys.modules.  That import runs
        # while holding name's lock, the lock order _resolve_parents() exists
        # to avoid; it is tolerated here because the case is so rare.
        if parent not in sys.modules:
            _call_with_frames_removed(import_, parent)
        # Crazy side-effects!
        module = sys.modules.get(name)
        if module is not None:
            return module
        parent_module = sys.modules[parent]
        try:
            path = parent_module.__path__
        except AttributeError:
            msg = f'{_ERR_MSG_PREFIX}{name!r}; {parent!r} is not a package'
            raise ModuleNotFoundError(msg, name=name) from None
        parent_spec = parent_module.__spec__
        if getattr(parent_spec, '_initializing', False):
            _call_with_frames_removed(import_, parent)
        # Crazy side-effects (again)!
        module = sys.modules.get(name)
        if module is not None:
            return module
        child = name.rpartition('.')[2]
    spec = _find_spec(name, path)
    if spec is None:
        raise ModuleNotFoundError(f'{_ERR_MSG_PREFIX}{name!r}', name=name)
    else:
        if parent_spec:
            # Temporarily add child we are currently importing to parent's
            # _uninitialized_submodules for circular import tracking.
            parent_spec._uninitialized_submodules.append(child)
        try:
            module = _load_unlocked(spec)
        finally:
            if parent_spec:
                parent_spec._uninitialized_submodules.pop()
    if parent:
        # Set the module as an attribute on its parent.
        parent_module = sys.modules[parent]
        try:
            setattr(parent_module, child, module)
        except AttributeError:
            msg = f"Cannot set an attribute on {parent!r} for child module {child!r}"
            # bella: _warnings.warn(msg, ImportWarning), which the default filters ignore; refused once
            # a warnings module could have changed them (runtime/src/imports.cpp, import_warning)
            _bella_import_warning(msg)
    # bella: no lazy submodules yet (PEP 810, the next increment), so _imp._set_lazy_attributes has
    # none to set
    return module


_NEEDS_LOADING = object()


# Return whether module (a sys.modules value) is still executing.
def _is_initializing(module):
    return getattr(getattr(module, '__spec__', None), '_initializing', False)


# Import, or wait for, the parent packages of name.
#
# _find_and_load() calls this before taking name's module lock, so that no
# thread holds a submodule's lock while waiting for its parent.  This avoids
# the deadlocks and import errors of gh-83065 and gh-159963.
def _resolve_parents(name, import_):
    # Wait for each ancestor package that another thread is still
    # initializing, outermost first.  Importing beneath a package while its
    # __init__ is part way through its own imports could give one of the two
    # threads a partially initialized module.  Missing ancestors are not
    # imported: only the immediate parent has to exist.
    parts = name.split('.')
    for i in range(1, len(parts) - 1):
        ancestor = '.'.join(parts[:i])
        if _is_initializing(sys.modules.get(ancestor)):
            _lock_unlock_module(ancestor)
    # Import the immediate parent, or wait for it likewise.
    parent = name.rpartition('.')[0]
    if parent:
        module = sys.modules.get(parent, _NEEDS_LOADING)
        if module is _NEEDS_LOADING or _is_initializing(module):
            _call_with_frames_removed(import_, parent)


def _find_and_load(name, import_):
    """Find and load the module."""

    # Optimization: we avoid unneeded module locking if the module
    # already exists in sys.modules and is fully initialized.
    module = sys.modules.get(name, _NEEDS_LOADING)
    if module is _NEEDS_LOADING or _is_initializing(module):
        if module is not _NEEDS_LOADING:
            # bella: waiting for the thread executing the module: it is this one, so the lock is
            # taken at once; the module is gone if its body failed
            module = sys.modules.get(name, _NEEDS_LOADING)

        if module is _NEEDS_LOADING:
            # bella: sys.audit("import", ...) calls no hook (a program cannot add one in phase 1)
            _resolve_parents(name, import_)
            # bella: the module lock, taken at once (one thread)
            module = sys.modules.get(name, _NEEDS_LOADING)
            if module is _NEEDS_LOADING:
                return _find_and_load_unlocked(name, import_)
    else:
        # Verify the module is still in sys.modules. Another thread may have
        # removed it (due to import failure) between our sys.modules.get()
        # above and the _initializing check. If removed, we retry the import
        # to preserve normal semantics: the caller gets the exception from
        # the actual import failure rather than a synthetic error.
        if sys.modules.get(name) is not module:
            return _find_and_load(name, import_)

    if module is None:
        message = f'import of {name} halted; None in sys.modules'
        raise ModuleNotFoundError(message, name=name)

    return module


def _handle_fromlist(module, fromlist, import_, *, recursive=False):
    """Figure out what __import__ should return.

    The import_ parameter is a callable which takes the name of module to
    import. It is required to decouple the function from assuming importlib's
    import implementation is desired.

    """
    # The hell that is fromlist ...
    # If a package was imported, try to import stuff from fromlist.
    for x in fromlist:
        if not isinstance(x, str):
            if recursive:
                where = module.__name__ + '.__all__'
            else:
                where = "``from list''"
            raise TypeError(f"Item in {where} must be str, "
                            f"not {type(x).__name__}")
        elif x == '*':
            if not recursive and hasattr(module, '__all__'):
                _handle_fromlist(module, module.__all__, import_,
                                 recursive=True)
        elif not hasattr(module, x):
            from_name = f'{module.__name__}.{x}'
            try:
                _call_with_frames_removed(import_, from_name)
            except ModuleNotFoundError as exc:
                # Backwards-compatibility dictates we ignore failed
                # imports triggered by fromlist for modules that don't
                # exist.
                if (exc.name == from_name and
                    sys.modules.get(from_name, _NEEDS_LOADING) is not None):
                    continue
                raise
    return module


def _setup(builtin_names):
    """Setup importlib by importing needed built-in modules and injecting them
    into the global namespace.

    As sys is needed for sys.modules access and _imp is needed to load built-in
    modules, those two modules must be explicitly passed in.

    """
    # bella: the part of _setup a compiled program observes: the specs and loaders of the built-in
    # modules the runtime made before this module ran (sys.builtin_module_names among them)
    module_type = type(sys)
    for name, module in sys.modules.items():
        if isinstance(module, module_type):
            if name in builtin_names:
                loader = BuiltinImporter
            else:
                continue
            spec = _spec_from_module(module, loader)
            _init_module_attrs(spec, module)
