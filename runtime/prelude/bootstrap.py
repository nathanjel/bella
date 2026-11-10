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
  methods that read files. An ImportWarning goes to
  `_bella_import_warning`: the default filters ignore it, so it has no effect until a warnings
  module could have changed them, and is refused from then on.

The module runs as `_frozen_importlib`, so its classes say so in `__module__`, as CPython's do.
"""
import sys

__intrinsics__ = ["_find_and_load", "_find_and_load_lazy_submodule", "_handle_fromlist", "_module_repr", "_setup"]

_bootstrap_external = None

_NOT_GIVEN = object()
_repr_running = []


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


def spec_from_loader(name, loader, *, origin=None, is_package=None):
    """Return a module spec based on various loader methods."""
    if origin is None:
        origin = getattr(loader, '_ORIGIN', None)

    if not origin and hasattr(loader, 'get_filename'):
        if _bootstrap_external is None:
            raise NotImplementedError
        spec_from_file_location = _bootstrap_external.spec_from_file_location

        if is_package is None:
            return spec_from_file_location(name, loader=loader)
        search = [] if is_package else None
        return spec_from_file_location(name, loader=loader,
                                       submodule_search_locations=search)

    if is_package is None:
        if hasattr(loader, 'is_package'):
            try:
                is_package = loader.is_package(name)
            except ImportError:
                is_package = None  # aka, undefined
        else:
            # the default
            is_package = False

    return ModuleSpec(name, loader, origin=origin, is_package=is_package)


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

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if _bella_is_builtin(fullname):  # bella: _imp.is_builtin
            return spec_from_loader(fullname, cls, origin=cls._ORIGIN)
        else:
            return None

    @staticmethod
    def create_module(spec):
        """Create a built-in module"""
        # bella: _imp.create_builtin; sys.builtin_module_names is not there yet, _imp.is_builtin decides
        if not _bella_is_builtin(spec.name):
            raise ImportError(f'{spec.name!r} is not a built-in module',
                              name=spec.name)
        return _call_with_frames_removed(_bella_create_builtin, spec.name)

    @staticmethod
    def exec_module(module):
        """Exec a built-in module"""
        # bella: _imp.exec_builtin: create_module made the whole of it

    # bella: @_requires_builtin, written out (it needs functions' __dict__); `self` is the wrapper's name for the class
    @classmethod
    def get_code(self, fullname):
        """Return None as built-in modules do not have code objects."""
        _check_builtin(fullname)
        return None

    @classmethod
    def get_source(self, fullname):
        """Return None as built-in modules do not have source code."""
        _check_builtin(fullname)
        return None

    @classmethod
    def is_package(self, fullname):
        """Return False as built-in modules are never packages."""
        _check_builtin(fullname)
        return False


def _check_builtin(fullname):
    if not _bella_is_builtin(fullname):
        raise ImportError(f'{fullname!r} is not a built-in module',
                          name=fullname)


def _check_frozen(fullname):
    import _imp
    if not _imp.is_frozen(fullname):
        raise ImportError(f'{fullname!r} is not a frozen module',
                          name=fullname)


class FrozenImporter:

    """Meta path import for frozen modules.

    All methods are either class or static methods to avoid the need to
    instantiate the class.

    """

    _ORIGIN = "frozen"

    # bella: a frozen module's code is compiled into the program like any other module's, and the import system finds it
    # in the registry (_spec_from_compiled). The class's own finder and loader methods are CPython's text over _imp, whose
    # answers are the pin's (the names table): what CPython freezes, whether or not this program has it

    @classmethod
    def _fix_up_module(cls, module):
        import _imp  # bella: the module's own `_imp` is _setup's argument; it is imported where it is used
        spec = module.__spec__
        state = spec.loader_state
        if state is None:
            # The module is missing FrozenImporter-specific values.

            # Fix up the spec attrs.
            origname = vars(module).pop('__origname__', None)
            assert origname, 'see PyImport_ImportFrozenModuleObject()'
            ispkg = hasattr(module, '__path__')
            assert _imp.is_frozen_package(module.__name__) == ispkg, ispkg
            filename, pkgdir = cls._resolve_filename(origname, spec.name, ispkg)
            spec.loader_state = type(sys.implementation)(
                filename=filename,
                origname=origname,
            )
            __path__ = spec.submodule_search_locations
            if ispkg:
                assert __path__ == [], __path__
                if pkgdir:
                    spec.submodule_search_locations.insert(0, pkgdir)
            else:
                assert __path__ is None, __path__

            # Fix up the module attrs (the bare minimum).
            assert not hasattr(module, '__file__'), module.__file__
            if filename:
                try:
                    module.__file__ = filename
                except AttributeError:
                    pass
            if ispkg:
                if module.__path__ != __path__:
                    assert module.__path__ == [], module.__path__
                    module.__path__.extend(__path__)
        else:
            # These checks ensure that _fix_up_module() is only called
            # in the right places.
            __path__ = spec.submodule_search_locations
            ispkg = __path__ is not None
            # Check the loader state.
            assert sorted(vars(state)) == ['filename', 'origname'], state
            if state.origname:
                # The only frozen modules with "origname" set are stdlib modules.
                (__file__, pkgdir,
                 ) = cls._resolve_filename(state.origname, spec.name, ispkg)
                assert state.filename == __file__, (state.filename, __file__)
                if pkgdir:
                    assert __path__ == [pkgdir], (__path__, pkgdir)
                else:
                    assert __path__ == ([] if ispkg else None), __path__
            else:
                __file__ = None
                assert state.filename is None, state.filename
                assert __path__ == ([] if ispkg else None), __path__
            # Check the file attrs.
            if __file__:
                assert hasattr(module, '__file__')
                assert module.__file__ == __file__, (module.__file__, __file__)
            else:
                assert not hasattr(module, '__file__'), module.__file__
            if ispkg:
                assert hasattr(module, '__path__')
                assert module.__path__ == __path__, (module.__path__, __path__)
            else:
                assert not hasattr(module, '__path__'), module.__path__
        assert not spec.has_location

    @classmethod
    def _resolve_filename(cls, fullname, alias=None, ispkg=False):
        if not fullname or not getattr(sys, '_stdlib_dir', None):
            return None, None
        try:
            sep = cls._SEP
        except AttributeError:
            sep = cls._SEP = '\\' if sys.platform == 'win32' else '/'

        if fullname != alias:
            if fullname.startswith('<'):
                fullname = fullname[1:]
                if not ispkg:
                    fullname = f'{fullname}.__init__'
            else:
                ispkg = False
        relfile = fullname.replace('.', sep)
        if ispkg:
            pkgdir = f'{sys._stdlib_dir}{sep}{relfile}'
            filename = f'{pkgdir}{sep}__init__.py'
        else:
            pkgdir = None
            filename = f'{sys._stdlib_dir}{sep}{relfile}.py'
        return filename, pkgdir

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        import _imp  # bella: the module's own `_imp` is _setup's argument; it is imported where it is used
        info = _call_with_frames_removed(_imp.find_frozen, fullname)
        if info is None:
            return None
        # We get the marshaled data in exec_module() (the loader
        # part of the importer), instead of here (the finder part).
        # The loader is the usual place to get the data that will
        # be loaded into the module.  (For example, see _LoaderBasics
        # in _bootstrap_external.py.)  Most importantly, this importer
        # is simpler if we wait to get the data.
        # However, getting as much data in the finder as possible
        # to later load the module is okay, and sometimes important.
        # (That's why ModuleSpec.loader_state exists.)  This is
        # especially true if it avoids throwing away expensive data
        # the loader would otherwise duplicate later and can be done
        # efficiently.  In this case it isn't worth it.
        _, ispkg, origname = info
        spec = spec_from_loader(fullname, cls,
                                origin=cls._ORIGIN,
                                is_package=ispkg)
        filename, pkgdir = cls._resolve_filename(origname, fullname, ispkg)
        spec.loader_state = type(sys.implementation)(
            filename=filename,
            origname=origname,
        )
        if pkgdir:
            spec.submodule_search_locations.insert(0, pkgdir)
        return spec

    @staticmethod
    def create_module(spec):
        """Set __file__, if able."""
        module = _new_module(spec.name)
        try:
            filename = spec.loader_state.filename
        except AttributeError:
            pass
        else:
            if filename:
                module.__file__ = filename
        return module

    @staticmethod
    def exec_module(module):
        name = module.__spec__.name
        # bella: _imp.get_frozen_object and exec, the module's compiled body
        _bella_exec(name, module)

    # bella: @_requires_frozen, written out (it needs functions' __dict__); `self` is the wrapper's name for the class
    @classmethod
    def get_code(self, fullname):
        """Return the code object for the frozen module."""
        import _imp
        _check_frozen(fullname)
        return _imp.get_frozen_object(fullname)

    @classmethod
    def get_source(self, fullname):
        """Return None as frozen modules do not have source code."""
        _check_frozen(fullname)
        return None

    @classmethod
    def is_package(self, fullname):
        """Return True if the frozen module is a package."""
        import _imp
        _check_frozen(fullname)
        return _imp.is_frozen_package(fullname)


# ---- types.GenericAlias ----

# bella: Objects/genericaliasobject.c in Python; present_as_c_types names it types.GenericAlias and
# gives it __parameters__ and __typing_unpacked_tuple_args__ as getsets. Its tp_getattro, which
# passes every other name on to the origin, is the runtime's (getattr_impl): a program's class
# overriding __getattribute__ is [P2+], and a read here would find this class's own __doc__.

_ga_absent = object()
_ga_get = _bella_ga_get                          # a member, read past that forwarding
_ga_set = object.__setattr__
_GA_OWN = ('__class__', '__origin__', '__args__', '__unpacked__', '__parameters__',
           '__typing_unpacked_tuple_args__', '__mro_entries__', '__reduce_ex__', '__reduce__')


def _ga_check(value, kind):
    # bella: PyTuple_Check and the others read the type, never __class__
    return issubclass(type(value), kind)


def _ga_type_name(value):
    # bella: %T, PyType_GetFullyQualifiedName
    t = type(value)
    return t.__qualname__ if t.__module__ in ('builtins', '__main__') else t.__module__ + '.' + t.__qualname__


def _ga_index(params, item):
    i = 0
    for p in params:
        if p is item:
            return i
        i += 1
    return -1


def _typing_type_repr(p):
    """_Py_typing_type_repr."""
    if p is ...:
        return '...'
    if p is type(None):
        return 'None'
    if hasattr(p, '__origin__') and hasattr(p, '__args__'):
        return repr(p)                                 # it looks like a GenericAlias
    qualname = getattr(p, '__qualname__', _ga_absent)
    if qualname is _ga_absent:
        return repr(p)
    module = getattr(p, '__module__', None)
    if module is None:
        return repr(p)
    if _ga_check(module, str) and module == 'builtins':
        return str(qualname)                           # builtins don't need a module name
    return str(module) + '.' + str(qualname)


def _make_parameters(args):
    """_Py_make_parameters."""
    parameters = []

    def add(item):
        if _ga_index(parameters, item) < 0:
            parameters.append(item)

    for t in tuple(args):
        if _ga_check(t, type):                         # not __parameters__ of a bare Python class
            continue
        if hasattr(t, '__typing_subst__'):
            add(t)
            continue
        subparams = getattr(t, '__parameters__', _ga_absent)
        if subparams is _ga_absent and (_ga_check(t, tuple) or _ga_check(t, list)):
            subparams = _make_parameters(t)            # lists and tuples, recursively
        if subparams is not _ga_absent and _ga_check(subparams, tuple):
            for t2 in subparams:
                add(t2)
    return tuple(parameters)


def _ga_has_iter(param):
    # bella: Py_TYPE(param)->tp_iter: a TypeVarTuple
    for c in type(param).__mro__:
        if '__iter__' in vars(c):
            return True
    return False


def _subs_tvars(obj, params, argitems):
    """subs_tvars: list[T] with params (T, S) and argitems (str, int) is list[str]."""
    subparams = getattr(obj, '__parameters__', _ga_absent)
    if subparams is _ga_absent or not _ga_check(subparams, tuple) or not subparams:
        return obj
    subargs = []
    for arg in subparams:
        iparam = _ga_index(params, arg)
        if iparam >= 0:
            param = params[iparam]
            arg = argitems[iparam]
            if _ga_has_iter(param) and _ga_check(arg, tuple):
                subargs.extend(arg)
                continue
        subargs.append(arg)
    return obj[tuple(subargs)]


def _is_unpacked_typevartuple(arg):
    if _ga_check(arg, type):
        return False
    return bool(getattr(arg, '__typing_is_unpacked_typevartuple__', False))


def _unpacked_tuple_args(arg):
    if _ga_check(arg, GenericAlias) and _ga_get(arg, '__unpacked__') and _ga_get(arg, '__origin__') is tuple:
        return _ga_get(arg, '__args__')
    result = getattr(arg, '__typing_unpacked_tuple_args__', None)
    return result


def _unpack_args(item):
    newargs = []
    for one in (item if _ga_check(item, tuple) else (item,)):
        if not _ga_check(one, type):
            subargs = _unpacked_tuple_args(one)
            if subargs is not None and _ga_check(subargs, tuple) and not (subargs and subargs[-1] is ...):
                newargs.extend(subargs)
                continue
        newargs.append(one)
    return tuple(newargs)


def _subs_parameters(self, args, parameters, item):
    """_Py_subs_parameters: t = dict[T, list[S]]; t[str, int] has the new args (str, list[int])."""
    nparams = len(parameters)
    if nparams == 0:
        raise TypeError(repr(self) + ' is not a generic class')
    item = _unpack_args(item)
    for param in parameters:
        prepare = getattr(param, '__typing_prepare_subst__', None)
        if prepare is not None:
            item = prepare(self, item if _ga_check(item, tuple) else (item,))
    argitems = item if _ga_check(item, tuple) else (item,)
    nitems = len(argitems)
    if nitems != nparams:
        raise TypeError(f"Too {'many' if nitems > nparams else 'few'} arguments for {self!r}; "
                        f'actual {nitems}, expected {nparams}')
    newargs = []
    for arg in tuple(args):
        if _ga_check(arg, type):
            newargs.append(arg)
            continue
        if _ga_check(arg, tuple) or _ga_check(arg, list):      # recursively, in lists and tuples
            subargs = _subs_parameters(self, arg, parameters, item)
            newargs.append(subargs if _ga_check(arg, tuple) else list(subargs))
            continue
        unpack = _is_unpacked_typevartuple(arg)
        subst = getattr(arg, '__typing_subst__', _ga_absent)
        if subst is not _ga_absent:
            iparam = _ga_index(parameters, arg)
            if iparam < 0:                             # stale: it gained __typing_subst__ later
                raise TypeError(f'argument {arg!r} with __typing_subst__ was not found in __parameters__')
            new = subst(argitems[iparam])
        else:
            new = _subs_tvars(arg, parameters, argitems)
        if unpack:
            if not _ga_check(new, tuple):
                raise TypeError(f'expected __typing_subst__ of {_ga_type_name(arg)} objects to return a tuple, '
                                f'not {_ga_type_name(new)}')
            newargs.extend(new)
        else:
            newargs.append(new)
    return tuple(newargs)


def _ga_parameters(self):
    parameters = _ga_get(self, '_ga_parameters')
    if parameters is None:
        parameters = _make_parameters(_ga_get(self, '__args__'))
        _ga_set(self, '_ga_parameters', parameters)
    return parameters


def _ga_unpacked_tuple_args(self):
    if _ga_get(self, '__unpacked__') and _ga_get(self, '__origin__') is tuple:
        return _ga_get(self, '__args__')
    return None


def _ga_make(cls, origin, args, starred=False):
    """setup_ga, and Py_GenericAlias with cls GenericAlias."""
    self = _bella_new_instance(cls)
    _ga_set(self, '__origin__', origin)
    _ga_set(self, '__args__', args if _ga_check(args, tuple) else (args,))
    _ga_set(self, '__unpacked__', starred)
    _ga_set(self, '_ga_parameters', None)
    return self


class generic_alias_iterator:

    __module__ = 'builtins'
    __slots__ = ('_ga_obj',)

    def __iter__(self):
        return self

    def __next__(self):
        obj = self._ga_obj
        self._ga_obj = None
        if obj is None:
            raise StopIteration
        return _ga_make(GenericAlias, _ga_get(obj, '__origin__'), _ga_get(obj, '__args__'), True)

    def __reduce__(self):
        return (iter, (self._ga_obj,) if self._ga_obj is not None else ((),))


class GenericAlias:
    """Represent a PEP 585 generic type

For example, for t = list[int], t.__origin__ is list and t.__args__
is (int,)."""

    __module__ = 'types'
    __slots__ = ('__origin__', '__args__', '__unpacked__', '_ga_parameters')

    def __new__(cls, *args, **kwds):
        if kwds:
            raise TypeError('GenericAlias() takes no keyword arguments')
        if len(args) != 2:
            raise TypeError(f'GenericAlias expected 2 arguments, got {len(args)}')
        return _ga_make(cls, args[0], args[1])

    def __setattr__(self, name, value):
        # bella: the members are read-only, and the parameters' slot is not CPython's to show
        if name in ('__origin__', '__args__', '__unpacked__'):
            raise AttributeError('readonly attribute')
        if name == '_ga_parameters':
            raise AttributeError(f"'types.GenericAlias' object has no attribute '{name}' and no __dict__ for setting new attributes")
        _ga_set(self, name, value)

    def __delattr__(self, name):
        if name in ('__origin__', '__args__', '__unpacked__'):
            raise AttributeError('readonly attribute')
        if name == '_ga_parameters':
            raise AttributeError(f"'types.GenericAlias' object has no attribute '{name}' and no __dict__ for setting new attributes")
        object.__delattr__(self, name)

    def __repr__(self):
        parts = []
        for p in _ga_get(self, '__args__'):
            if type(p) is list:                        # a ParamSpec's list of type arguments
                parts.append('[' + ', '.join([_typing_type_repr(x) for x in p]) + ']')
            else:
                parts.append(_typing_type_repr(p))
        inner = ', '.join(parts) if parts else '()'    # tuple[()]
        star = '*' if _ga_get(self, '__unpacked__') else ''
        return star + _typing_type_repr(_ga_get(self, '__origin__')) + '[' + inner + ']'

    def __getitem__(self, item):
        newargs = _subs_parameters(self, _ga_get(self, '__args__'), _ga_parameters(self), item)
        return _ga_make(GenericAlias, _ga_get(self, '__origin__'), newargs, _ga_get(self, '__unpacked__'))

    def __hash__(self):
        return hash(_ga_get(self, '__origin__')) ^ hash(_ga_get(self, '__args__'))

    def __call__(self, /, *args, **kwds):
        obj = _ga_get(self, '__origin__')(*args, **kwds)
        try:
            obj.__orig_class__ = self
        except (AttributeError, TypeError):
            pass
        return obj

    def __eq__(self, other):
        if not _ga_check(other, GenericAlias):
            return NotImplemented
        if _ga_get(self, '__unpacked__') != _ga_get(other, '__unpacked__'):
            return False
        a, b = _ga_get(self, '__origin__'), _ga_get(other, '__origin__')
        if not (a is b or a == b):                     # PyObject_RichCompareBool
            return False
        return _ga_get(self, '__args__') == _ga_get(other, '__args__')

    def __ne__(self, other):
        if not _ga_check(other, GenericAlias):
            return NotImplemented
        return GenericAlias.__eq__(self, other) is not True

    def __or__(self, other):
        return _union_type_or(self, other)

    def __ror__(self, other):
        return _union_type_or(other, self)

    def __mro_entries__(self, bases, /):
        return (_ga_get(self, '__origin__'),)

    def __instancecheck__(self, instance, /):
        raise TypeError('isinstance() argument 2 cannot be a parameterized generic')

    def __subclasscheck__(self, subclass, /):
        raise TypeError('issubclass() argument 2 cannot be a parameterized generic')

    def __reduce__(self):
        origin, args = _ga_get(self, '__origin__'), _ga_get(self, '__args__')
        if _ga_get(self, '__unpacked__'):
            return (next, (iter(_ga_make(GenericAlias, origin, args)),))
        return (type(self), (origin, args))

    def __reduce_ex__(self, protocol, /):
        # bella: object.__reduce_ex__, which asks a class's own __reduce__
        return type(self).__reduce__(self)

    def __dir__(self):
        names = dir(_ga_get(self, '__origin__'))
        for name in _GA_OWN:
            if name not in names:
                names.append(name)
        return names

    def __iter__(self):
        it = _bella_new_instance(generic_alias_iterator)
        it._ga_obj = self
        return it


# ---- sentinel ----

# bella: Objects/sentinelobject.c in Python; present_as_c_types puts it in builtins, and gives it __name__ and __module__
# as members, which a class statement cannot have, since a class has those of its own.

class sentinel:
    """sentinel(name, /, *, repr=None)
--

Create a unique sentinel object with the given name."""

    __slots__ = ('_s_name', '_s_module', '_s_repr')

    def __new__(*args, **kwds):                        # sentinel_new_impl
        if not args:
            raise TypeError('sentinel.__new__(): not enough arguments')
        cls = args[0]
        if not _ga_check(cls, type):
            raise TypeError(f'sentinel.__new__(X): X is not a type object ({_ga_type_name(cls)})')
        if not issubclass(cls, sentinel):
            raise TypeError(f'sentinel.__new__({cls.__name__}): {cls.__name__} is not a subtype of sentinel')
        for key in kwds:
            if key != 'repr':
                raise TypeError(f"sentinel() got an unexpected keyword argument '{key}'")
        if len(args) != 2:
            raise TypeError(f'sentinel() takes exactly 1 positional argument ({len(args) - 1} given)')
        name = args[1]
        if not _ga_check(name, str):
            raise TypeError(f'sentinel() argument 1 must be str, not {_ga_type_name(name)}')
        given = kwds.get('repr')
        if given is not None and not _ga_check(given, str):
            raise TypeError(f"sentinel() argument 'repr' must be str or None, not {_ga_type_name(given)}")
        self = _bella_new_instance(cls)
        _ga_set(self, '_s_name', name)
        _ga_set(self, '_s_module', _bella_caller_module())
        _ga_set(self, '_s_repr', given)
        return self

    def __repr__(self):
        given = self._s_repr
        return self._s_name if given is None else given

    def __copy__(self):
        return self

    def __deepcopy__(self, memo, /):
        return self

    def __reduce__(self):
        return self._s_name

    def __or__(self, other):
        return _union_type_or(self, other)

    def __ror__(self, other):
        return _union_type_or(other, self)

    # tp_hash = PyObject_GenericHash and tp_richcompare = _Py_BaseObject_RichCompare: object's, as the type's own slots
    def __hash__(self):
        return object.__hash__(self)

    def __eq__(self, other):
        return object.__eq__(self, other)

    def __ne__(self, other):
        return object.__ne__(self, other)

    def __lt__(self, other):
        return object.__lt__(self, other)

    def __le__(self, other):
        return object.__le__(self, other)

    def __gt__(self, other):
        return object.__gt__(self, other)

    def __ge__(self, other):
        return object.__ge__(self, other)


# ---- typing.Union ----

# bella: Objects/unionobject.c in Python; present_as_c_types names it typing.Union, has no __new__ of its own to show
# (make_union alone makes one, as _bella_new_instance), and gives it __name__, __qualname__, __origin__ and
# __parameters__ as getsets. type.__or__ and type.__ror__ are the runtime's and come here, as _union_type_or.

_union_set = object.__setattr__
_UNION_OWN = ('_union_hashable', '_union_unhashable', '_union_params')


_typealias_type = None                           # typing.TypeAliasType, once _typing has made it


def _set_typealias_type(t):
    global _typealias_type
    _typealias_type = t


def _is_unionable(obj):
    """is_unionable"""
    return obj is None or _ga_check(obj, type) or type(obj) is sentinel or _ga_check(obj, GenericAlias) or type(obj) is Union \
        or (_typealias_type is not None and type(obj) is _typealias_type)


def _union_type_check(arg, msg):
    """type_check: the unionable ones without asking typing, which has the last word on the rest."""
    if arg is None:
        return type(None)
    if _is_unionable(arg):
        return arg
    import typing
    return typing._type_check(arg, msg)


class _UnionBuilder:
    """unionbuilder."""

    __slots__ = ('args', 'hashable', 'unhashable', 'checked')

    def __init__(self, checked):
        self.args = []
        self.hashable = set()
        self.unhashable = None
        self.checked = checked

    def add_unchecked(self, arg):
        try:
            hash(arg)
            hashable = True
        except BaseException:                          # the C clears whatever it was
            hashable = False
        if hashable:
            if arg in self.hashable:
                return
            self.hashable.add(arg)
        elif self.unhashable is None:
            self.unhashable = [arg]
        else:
            if arg in self.unhashable:
                return
            self.unhashable.append(arg)
        self.args.append(arg)

    def add_tuple(self, items):
        for item in items:
            self.add(item)

    def add(self, arg):
        if arg is None:
            arg = type(None)
        elif type(arg) is Union:
            self.add_tuple(arg.__args__)
            return
        if self.checked:
            self.add_unchecked(_union_type_check(arg, 'Union[arg, ...]: each arg must be a type.'))
        else:
            self.add_unchecked(arg)

    def make(self):                                    # make_union
        n = len(self.args)
        if n == 0:
            raise TypeError('Cannot take a Union of no types.')
        if n == 1:
            return self.args[0]
        result = _bella_new_instance(Union)
        _union_set(result, '__args__', tuple(self.args))
        _union_set(result, '_union_hashable', frozenset(self.hashable))
        _union_set(result, '_union_unhashable', None if self.unhashable is None else tuple(self.unhashable))
        _union_set(result, '_union_params', None)
        return result


def _union_type_or(a, b):
    """_Py_union_type_or: unchecked, because is_unionable said so."""
    if not _is_unionable(a) or not _is_unionable(b):
        return NotImplemented
    ub = _UnionBuilder(False)
    ub.add(a)
    ub.add(b)
    return ub.make()


def _union_from_tuple(args):
    """_Py_union_from_tuple."""
    ub = _UnionBuilder(True)
    if type(args) is tuple:
        ub.add_tuple(args)
    else:
        ub.add(args)
    return ub.make()


def _union_nb_or(a, b):
    ub = _UnionBuilder(True)
    ub.add(a)
    ub.add(b)
    return ub.make()


def _union_parameters(self):
    parameters = self._union_params
    if parameters is None:                             # union_init_parameters: once
        parameters = _make_parameters(self.__args__)
        _union_set(self, '_union_params', parameters)
    return parameters


def _unions_equal(a, b):
    """unions_equal."""
    ha, hb = a._union_hashable, b._union_hashable
    if not (ha is hb or ha == hb):
        return False
    ua, ub = a._union_unhashable, b._union_unhashable
    if ua is not None and ub is not None:
        if len(ua) != len(ub):
            return False
        for arg in ua:
            if arg not in ub:
                return False
        for arg in ub:
            if arg not in ua:
                return False
    elif ua is not None or ub is not None:
        return False
    return True


def _union_wrapper(args, kwds, name, n):
    """A slot wrapper's checks: the receiver's type, wrapper_call, check_num_args."""
    if not args:
        raise TypeError(f"descriptor '{name}' of 'typing.Union' object needs an argument")
    if type(args[0]) is not Union:
        raise TypeError(f"descriptor '{name}' requires a 'typing.Union' object but received a '{_ga_type_name(args[0])}'")
    if kwds:
        raise TypeError(f'wrapper {name}() takes no keyword arguments')
    if len(args) - 1 != n:
        raise TypeError(f"expected {n} argument{'' if n == 1 else 's'}, got {len(args) - 1}")


class Union:
    """Represent a union type

E.g. for int | str"""

    __module__ = 'typing'
    __slots__ = ('__args__',) + _UNION_OWN

    def __setattr__(*args, **kwds):
        _union_wrapper(args, kwds, '__setattr__', 2)
        self, name, value = args
        if name == '__args__':
            raise AttributeError('readonly attribute')
        if name in _UNION_OWN:
            raise AttributeError(f"'typing.Union' object has no attribute '{name}' and no __dict__ for setting new attributes")
        _union_set(self, name, value)

    def __delattr__(*args, **kwds):
        _union_wrapper(args, kwds, '__delattr__', 1)
        self, name = args
        if name == '__args__':
            raise AttributeError('readonly attribute')
        if name in _UNION_OWN:
            raise AttributeError(f"'typing.Union' object has no attribute '{name}' and no __dict__ for setting new attributes")
        object.__delattr__(self, name)

    def __repr__(*args, **kwds):
        _union_wrapper(args, kwds, '__repr__', 0)
        return ' | '.join([_typing_type_repr(p) for p in args[0].__args__])

    def __hash__(*args, **kwds):
        _union_wrapper(args, kwds, '__hash__', 0)
        self = args[0]
        unhashable = self._union_unhashable
        if unhashable is not None:
            for arg in unhashable:                     # an error from one of them, if it can
                hash(arg)
            raise TypeError(f'union contains {len(unhashable)} unhashable elements')
        return hash(self._union_hashable)

    def __eq__(*args, **kwds):
        _union_wrapper(args, kwds, '__eq__', 1)
        if type(args[1]) is not Union:
            return NotImplemented
        return _unions_equal(args[0], args[1])

    def __ne__(*args, **kwds):
        _union_wrapper(args, kwds, '__ne__', 1)
        if type(args[1]) is not Union:
            return NotImplemented
        return not _unions_equal(args[0], args[1])

    def __lt__(*args, **kwds):
        _union_wrapper(args, kwds, '__lt__', 1)
        return NotImplemented

    def __le__(*args, **kwds):
        _union_wrapper(args, kwds, '__le__', 1)
        return NotImplemented

    def __gt__(*args, **kwds):
        _union_wrapper(args, kwds, '__gt__', 1)
        return NotImplemented

    def __ge__(*args, **kwds):
        _union_wrapper(args, kwds, '__ge__', 1)
        return NotImplemented

    def __getitem__(*args, **kwds):
        _union_wrapper(args, kwds, '__getitem__', 1)
        self, item = args
        return _union_from_tuple(_subs_parameters(self, self.__args__, _union_parameters(self), item))

    def __or__(*args, **kwds):
        _union_wrapper(args, kwds, '__or__', 1)
        return _union_nb_or(args[0], args[1])

    def __ror__(*args, **kwds):
        _union_wrapper(args, kwds, '__ror__', 1)
        return _union_nb_or(args[1], args[0])

    def __mro_entries__(*args, **kwds):
        if kwds:
            raise TypeError('Union.__mro_entries__() takes no keyword arguments')
        if len(args) != 2:
            raise TypeError(f'Union.__mro_entries__() takes exactly one argument ({len(args) - 1} given)')
        raise TypeError(f'Cannot subclass {args[0]!r}')

    @classmethod
    def __class_getitem__(*args, **kwds):
        """Create a union containing the given types"""
        if kwds:
            raise TypeError('Union.__class_getitem__() takes no keyword arguments')
        if len(args) != 2:
            raise TypeError(f'Union.__class_getitem__() takes exactly one argument ({len(args) - 1} given)')
        return _union_from_tuple(args[1])


def _namespace_self(name, self):
    # bella: what a C method's descriptor checks before it runs
    if not isinstance(self, SimpleNamespace):
        raise TypeError(f"descriptor '{name}' requires a 'types.SimpleNamespace' object but received a '{type(self).__name__}'")


class SimpleNamespace:
    """A simple attribute-based namespace."""

    # bella: Objects/namespaceobject.c in Python; the class is types.SimpleNamespace

    __module__ = 'types'

    def __init__(self, /, *args, **kwargs):
        _namespace_self('__init__', self)
        if len(args) > 1:
            raise TypeError(f'SimpleNamespace expected at most 1 argument, got {len(args)}')
        if args:
            mapping_or_iterable = args[0]
            d = mapping_or_iterable if type(mapping_or_iterable) is dict else dict(mapping_or_iterable)
            for key in d:  # PyArg_ValidateKeywordArguments
                if not isinstance(key, str):
                    raise TypeError('keywords must be strings')
            self.__dict__.update(d)
        self.__dict__.update(kwargs)

    def __repr__(self):
        _namespace_self('__repr__', self)
        name = 'namespace' if type(self) is SimpleNamespace else type(self).__name__
        if self in _repr_running:  # Py_ReprEnter, by identity: __eq__ here compares contents
            return f'{name}(...)'
        _repr_running.append(self)
        try:
            pairs = []
            d = self.__dict__
            for key in list(d):
                if isinstance(key, str) and len(key) > 0:
                    pairs.append(f'{key}={d[key]!r}')
            return f'{name}({", ".join(pairs)})'
        finally:
            _repr_running.pop()

    def __eq__(self, other):
        if isinstance(self, SimpleNamespace) and isinstance(other, SimpleNamespace):
            return self.__dict__ == other.__dict__
        return NotImplemented

    __hash__ = None

    def __reduce__(self):
        return (type(self), (), self.__dict__)

    def __replace__(self, /, *args, **kwargs):
        _namespace_self('__replace__', self)
        if args:
            raise TypeError('__replace__() takes no positional arguments')
        result = type(self)()
        if not isinstance(result, SimpleNamespace):
            raise TypeError(f'expect types.SimpleNamespace type, but {type(self).__name__}() returned '
                            f"'{type(result).__name__}' object")
        result.__dict__.update(self.__dict__)
        result.__dict__.update(kwargs)
        return result


# bella: _bootstrap_external's source loader, as its path finder makes one for a .py file. A
# compiled program has no source to read at runtime, so the methods that read files are refused;
# what a module's namespace shows (the loader's type, name and path, its equality) is CPython's.

def _path_split(path):
    """Replacement for os.path.split()."""
    i = path.rfind('/')  # bella: path_separators is '/' on the targets (posix)
    if i < 0:
        return '', path
    return path[:i], path[i + 1:]


def cache_from_source(path):
    # bella: _bootstrap_external's, for _get_cached below: sys.implementation.cache_tag is None (D-16), so a compiled
    # program has no bytecode cache to name. The module's own function, with CPython's parameters, is bootstrap_external.py's
    raise NotImplementedError('sys.implementation.cache_tag is None')


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


class _LoaderBasics:

    """Base class of common code needed by both SourceLoader and
    SourcelessFileLoader."""

    __module__ = '_frozen_importlib_external'

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


class SourceLoader(_LoaderBasics):

    __module__ = '_frozen_importlib_external'

    # bella: the methods below read or write files, which a compiled program does not do; their docstrings are CPython's
    def path_mtime(self, path):
        """Optional method that returns the modification time (an int) for the
        specified path (a str).

        Raises OSError when the path cannot be handled.
        """
        _bella_refuse("a source loader's path_mtime (a compiled program has no source to read)")

    def path_stats(self, path):
        """Optional method returning a metadata dict for the specified
        path (a str).

        Possible keys:
        - 'mtime' (mandatory) is the numeric timestamp of last source
          code modification;
        - 'size' (optional) is the size in bytes of the source code.

        Implementing this method allows the loader to read bytecode files.
        Raises OSError when the path cannot be handled.
        """
        _bella_refuse("a source loader's path_stats (a compiled program has no source to read)")

    def _cache_bytecode(self, source_path, cache_path, data):
        """Optional method which writes data (bytes) to a file path (a str).

        Implementing this method allows for the writing of bytecode files.

        The source path is needed in order to correctly transfer permissions
        """
        _bella_refuse("a source loader's _cache_bytecode (a compiled program has no bytecode)")

    def set_data(self, path, data):
        """Optional method which writes data (bytes) to a file path (a str).

        Implementing this method allows for the writing of bytecode files.
        """

    def get_source(self, fullname):
        """Concrete implementation of InspectLoader.get_source."""
        _bella_refuse("a source loader's get_source (step 3b: reading files)")

    def source_to_code(self, data, path, fullname=None, *, _optimize=-1):
        """Return the code object compiled from source.

        The 'data' argument can be any object type that compile() supports.
        """
        _bella_refuse("a source loader's source_to_code (E-01: no compiler at runtime)")

    def get_code(self, fullname):
        """Concrete implementation of InspectLoader.get_code.

        Reading of bytecode requires path_stats to be implemented. To write
        bytecode, set_data must also be implemented.

        """
        _bella_refuse("a source loader's get_code (a compiled program has no code objects to load)")


class FileLoader:

    """Base file loader class which implements the loader protocol methods that
    require file system usage."""

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

    def get_filename(self, name=None, *args, **kwargs):
        """Return the path to the source file as found by the finder."""
        # bella: @_check_name, written out (it needs functions' __dict__): the wrapper's parameters and its check, then the
        # method, which takes the name alone
        if name is None:
            name = self.name
        elif self.name != name:
            # bella: CPython's text formats with %, which the runtime lacks yet; the same message
            raise ImportError(f'loader for {self.name} cannot handle {name}', name=name)
        if args or kwargs:
            _bella_refuse("FileLoader.get_filename with arguments beyond the name (the method under @_check_name takes none: a TypeError of its own)")
        return self.path

    def get_data(self, path):
        """Return the data from path as raw bytes."""
        _bella_refuse("a file loader's get_data (step 3b: reading files)")

    def get_resource_reader(self, name=None, *args, **kwargs):
        # bella: @_check_name, written out: its check comes first
        if name is None:
            name = self.name
        elif self.name != name:
            raise ImportError(f'loader for {self.name} cannot handle {name}', name=name)
        _bella_refuse("a source loader's get_resource_reader (importlib.resources is [P2+])")


class SourceFileLoader(FileLoader, SourceLoader):

    """Concrete implementation of SourceLoader using the file system."""

    __module__ = '_frozen_importlib_external'

    def path_stats(self, path):
        """Return the metadata for the path."""
        _bella_refuse("a source loader's path_stats (a compiled program has no source to read)")

    def _cache_bytecode(self, source_path, bytecode_path, data):
        _bella_refuse("a source loader's _cache_bytecode (a compiled program has no bytecode)")

    def set_data(self, path, data, *, _mode=0o666):
        """Write bytes data to a file."""
        _bella_refuse("a source loader's set_data (a compiled program writes no bytecode)")


# bella: they are _bootstrap_external's, whose module runs apart from this one in CPython
for _cls in (_LoaderBasics, SourceLoader, FileLoader, SourceFileLoader):
    for _name in _cls.__dict__:
        _f = _cls.__dict__[_name]
        if callable(_f):
            _f.__module__ = '_frozen_importlib_external'


def _spec_from_compiled(name):
    """bella: what CPython's finders return for a module the closed world has: FrozenImporter's spec
    (find_spec), or the path finder's for a source file (FileFinder.find_spec through
    spec_from_file_location): a spec with a location, its loader, and for a package the
    package's directory to search."""
    found = _bella_find(name)
    if found is None:
        return None
    origin, is_package, frozen = found
    if frozen:
        spec = spec_from_loader(name, FrozenImporter, origin=FrozenImporter._ORIGIN, is_package=is_package)
        spec.loader_state = SimpleNamespace(filename=origin, origname=name)
        if is_package:
            spec.submodule_search_locations.append(_path_split(origin)[0])
        return spec
    spec = ModuleSpec(name, SourceFileLoader(name, origin), origin=origin)
    spec._set_fileattr = True
    if is_package:
        spec.submodule_search_locations = [_path_split(origin)[0]]
    return spec


# Import itself ###############################################################

def _find_spec(name, path, target=None):
    """Find a module's spec."""
    # bella: the closed world's registry stands for sys.meta_path's finders (spec section 8)
    if _bella_shutting_down():
        # CPython: sys.meta_path is None once finalize_modules has begun
        raise ImportError("sys.meta_path is None, Python is likely shutting down")

    # We check sys.modules here for the reload case.  While a passed-in
    # target will usually indicate a reload there is no guarantee, whereas
    # sys.modules provides one.
    is_reload = name in sys.modules
    spec = BuiltinImporter.find_spec(name, path, target)
    if spec is None:
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


def _find_and_load_unlocked(name, import_, *, lazy_submodule=False):
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
            if lazy_submodule:
                return None
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
        if lazy_submodule:
            return None
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
    # Set attributes to lazy submodules on the module.
    try:
        _bella_set_lazy_attributes(module, name)  # bella: _imp._set_lazy_attributes
    except Exception as e:
        msg = f"Cannot set lazy attributes on {name!r}: {e!r}"
        # bella: _warnings.warn(msg, ImportWarning), as above
        _bella_import_warning(msg)
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


def _find_and_load(name, import_, *, lazy_submodule=False):
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
                return _find_and_load_unlocked(
                    name, import_, lazy_submodule=lazy_submodule)
    else:
        # Verify the module is still in sys.modules. Another thread may have
        # removed it (due to import failure) between our sys.modules.get()
        # above and the _initializing check. If removed, we retry the import
        # to preserve normal semantics: the caller gets the exception from
        # the actual import failure rather than a synthetic error.
        if sys.modules.get(name) is not module:
            return _find_and_load(name, import_, lazy_submodule=lazy_submodule)

    if module is None:
        message = f'import of {name} halted; None in sys.modules'
        raise ModuleNotFoundError(message, name=name)

    return module


def _find_and_load_lazy_submodule(name, import_):
    return _find_and_load(name, import_, lazy_submodule=True)


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


def _resolve_name(name, package, level):
    """Resolve a relative module name to an absolute one."""
    bits = package.rsplit('.', level - 1)
    if len(bits) < level:
        raise ImportError('attempted relative import beyond top-level package')
    base = bits[0]
    return f'{base}.{name}' if name else base


def _sanity_check(name, package, level):
    """Verify arguments are "sane"."""
    if not isinstance(name, str):
        raise TypeError(f'module name must be str, not {type(name)}')
    if level < 0:
        raise ValueError('level must be >= 0')
    if level > 0:
        if not isinstance(package, str):
            raise TypeError('__package__ not set to a string')
        elif not package:
            raise ImportError('attempted relative import with no known parent '
                              'package')
    if not name and level == 0:
        raise ValueError('Empty module name')


def _gcd_import(name, package=None, level=0):
    """Import and return the module based on its name, the package the call is
    being made from, and the level adjustment.

    This function represents the greatest common denominator of functionality
    between import_module and __import__. This includes setting __package__ if
    the loader did not.

    """
    _sanity_check(name, package, level)
    if level > 0:
        name = _resolve_name(name, package, level)
    return _find_and_load(name, _gcd_import)


def _calc___package__(globals):
    """Calculate what __package__ should be.

    __package__ is not guaranteed to be defined or could be set to None
    to represent that its proper value is unknown.

    """
    package = globals.get('__package__')
    spec = globals.get('__spec__')
    if package is not None:
        if spec is not None and package != spec.parent:
            # bella: the runtime's warning, through the _warnings prelude (runtime_warning)
            _bella_import_warning("__package__ != __spec__.parent "
                                  f"({package!r} != {spec.parent!r})", "DeprecationWarning")
        return package
    elif spec is not None:
        return spec.parent
    else:
        _bella_import_warning("can't resolve package from __spec__ or __package__, "
                              "falling back on __name__ and __path__")
        package = globals['__name__']
        if '__path__' not in globals:
            package = package.rpartition('.')[0]
    return package


def __import__(name, globals=None, locals=None, fromlist=(), level=0):
    """Import a module.

    The 'globals' argument is used to infer where the import is occurring from
    to handle relative imports. The 'locals' argument is ignored. The
    'fromlist' argument specifies what should exist as attributes on the module
    being imported (e.g. ``from module import <fromlist>``).  The 'level'
    argument represents the package location to import from in a relative
    import (e.g. ``from ..pkg import mod`` would have a 'level' of 2).

    """
    if level == 0:
        module = _gcd_import(name)
    else:
        globals_ = globals if globals is not None else {}
        package = _calc___package__(globals_)
        module = _gcd_import(name, package, level)
    if not fromlist:
        # Return up to the first dot in 'name'. This is complicated by the fact
        # that 'name' may be relative.
        if level == 0:
            return _gcd_import(name.partition('.')[0])
        elif not name:
            return module
        else:
            # Figure out where to slice the module's name up to the first dot
            # in 'name'.
            cut_off = len(name) - len(name.partition('.')[0])
            # Slice end needs to be positive to alleviate need to special-case
            # when ``'.' not in name``.
            return sys.modules[module.__name__[:len(module.__name__)-cut_off]]
    elif hasattr(module, '__path__'):
        return _handle_fromlist(module, fromlist, _gcd_import)
    else:
        return module


def _exec(spec, module):
    """Execute the spec's specified module in an existing module's namespace."""
    # bella: importlib.reload reaches here (E-04): a compiled module's body ran once, when the build's closed world first imported it
    _bella_refuse("importlib.reload (running a module's body again is import-system customisation, E-04)")


def _setup(builtin_names):
    """Setup importlib by importing needed built-in modules and injecting them
    into the global namespace.

    As sys is needed for sys.modules access and _imp is needed to load built-in
    modules, those two modules must be explicitly passed in.

    """
    # bella: the part of _setup a compiled program observes: the specs and loaders of the built-in
    # modules the runtime made before this module ran (sys.builtin_module_names among them), and of
    # the import system's two frozen modules (_imp.is_frozen of the others is the registry's)
    module_type = type(sys)
    for name, module in sys.modules.items():
        if isinstance(module, module_type):
            if name in builtin_names:
                loader = BuiltinImporter
            elif name == '_frozen_importlib':
                loader = FrozenImporter
            elif name == '_frozen_importlib_external':
                _bella_import_external(module)
                continue
            else:
                continue
            spec = _spec_from_module(module, loader)
            _init_module_attrs(spec, module)
            if loader is FrozenImporter:
                # bella: FrozenImporter._fix_up_module, which runs before sys._stdlib_dir is known: no file
                spec.loader_state = SimpleNamespace(filename=None, origname='importlib._bootstrap')


def _bella_import_external(module):
    """bella: what _install_external_importers' import of _frozen_importlib_external gives the module start-up made:
    FrozenImporter.find_spec's spec (_imp.find_frozen's original name, _resolve_filename's file under sys._stdlib_dir),
    create_module's __file__, then _init_module_attrs."""
    origname = 'importlib._bootstrap_external'   # Python/frozen.c's alias
    spec = spec_from_loader(module.__name__, FrozenImporter, origin=FrozenImporter._ORIGIN, is_package=False)
    filename, _ = FrozenImporter._resolve_filename(origname, module.__name__, False)   # as find_spec does: the class's _SEP is set here
    spec.loader_state = SimpleNamespace(filename=filename, origname=origname)
    if filename:
        module.__file__ = filename
    _init_module_attrs(spec, module)


# ---- structseq (Objects/structseq.c): a type of named tuples for the modules written in Python

def _bella_structseq(name, module, fields, visible, settle=None, has_new=True, says_module=True):
    """`fields` in order, None for one with no name; the first `visible` are the tuple's. CPython names the type's
    constructor `structseq` in its messages. What makes the result look as C makes it is _bella_structseq_finish.
    `settle(items, past)`: what a type's own tp_new does to a new one after the common part (statresult_new). With no
    `has_new` a program cannot make one (Py_TPFLAGS_DISALLOW_INSTANTIATION); with no `says_module` its __module__ is its tp_name's, not in its dict."""
    shown = name if module == "builtins" else module + "." + name   # the tp_name: a type of no module's is in builtins
    named = [f for f in fields if f is not None]
    total = len(fields)
    unnamed = total - len(named)

    def receiver(args, method):                  # a method descriptor's
        if not args:
            raise TypeError("unbound method " + name + "." + method + "() needs an argument")
        if not issubclass(type(args[0]), cls):
            raise TypeError("descriptor '" + method + "' for '" + shown + "' objects doesn't apply to a '" + type(args[0]).__name__ + "' object")

    def __new__(*args, **kwds):                  # tp_new_wrapper, then structseq_new_impl
        if not args:
            raise TypeError(shown + ".__new__(): not enough arguments")
        wanted = args[0]
        if not issubclass(type(wanted), type):
            raise TypeError(shown + ".__new__(X): X is not a type object (" + type(wanted).__name__ + ")")
        if not issubclass(wanted, cls):
            raise TypeError(shown + ".__new__(" + wanted.__name__ + "): " + wanted.__name__ + " is not a subtype of " + shown)
        rest = args[1:]
        given = len(rest) + len(kwds)
        if given > 2:
            raise TypeError("structseq() takes at most 2 " + ("keyword " if not rest else "") + "arguments (" + str(given) + " given)")
        for key in kwds:
            if key not in ("sequence", "dict"):
                suggestion = _bella_keyword_suggestion(("sequence", "dict"), key)
                raise TypeError("structseq() got an unexpected keyword argument '" + key + "'" + ("" if suggestion is None else ". Did you mean '" + suggestion + "'?"))
        if rest and "sequence" in kwds:
            raise TypeError("argument for structseq() given by name ('sequence') and position (1)")
        if len(rest) > 1 and "dict" in kwds:
            raise TypeError("argument for structseq() given by name ('dict') and position (2)")
        if not rest and "sequence" not in kwds:
            raise TypeError("structseq() missing required argument 'sequence' (pos 1)")
        arg = rest[0] if rest else kwds["sequence"]
        if len(rest) > 1:
            extra, has_extra = rest[1], True
        elif "dict" in kwds:
            extra, has_extra = kwds["dict"], True
        else:
            extra, has_extra = None, False
        try:                                     # PySequence_Fast: only a failure to iterate has its words
            it = iter(arg)
        except TypeError:
            raise TypeError("constructor requires a sequence") from None
        items = list(it)
        if has_extra and not issubclass(type(extra), dict):
            raise TypeError(shown + "() takes a dict as second arg, if any")
        size = len(items)
        if visible != total:
            if size < visible:
                raise TypeError(shown + "() takes an at least " + str(visible) + "-sequence (" + str(size) + "-sequence given)")
            if size > total:
                raise TypeError(shown + "() takes an at most " + str(total) + "-sequence (" + str(size) + "-sequence given)")
        elif size != visible:
            raise TypeError(shown + "() takes a " + str(visible) + "-sequence (" + str(size) + "-sequence given)")
        past = items[visible:]
        if has_extra and dict.__len__(extra) > 0:   # the dict itself: PyDict_GET_SIZE, PyDict_GetItemStringRef
            found = 0
            for field in fields[size:]:
                if dict.__contains__(extra, field):
                    found += 1
                    past.append(dict.__getitem__(extra, field))
                else:
                    past.append(None)
            if dict.__len__(extra) > found:
                raise TypeError(shown + "() got duplicate or unexpected field name(s)")
        else:
            past += [None] * (total - size)
        if settle is not None:
            settle(items, past)
        return _bella_structseq_make(cls, items[:visible], past)

    def __repr__(*args, **kwds):                 # wrapper_call, then structseq_repr
        if not args:
            raise TypeError("descriptor '__repr__' of '" + shown + "' object needs an argument")
        if not issubclass(type(args[0]), cls):
            raise TypeError("descriptor '__repr__' requires a '" + shown + "' object but received a '" + type(args[0]).__name__ + "'")
        if kwds:
            raise TypeError("wrapper __repr__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("expected 0 arguments, got " + str(len(args) - 1))
        values = tuple.__iter__(args[0])
        return shown + "(" + ", ".join([field + "=" + repr(next(values)) for field in named[:visible]]) + ")"

    def __reduce__(*args, **kwds):               # structseq_reduce
        receiver(args, "__reduce__")
        if kwds:
            raise TypeError(name + ".__reduce__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError(name + ".__reduce__() takes no arguments (" + str(len(args) - 1) + " given)")
        past = {}
        for field, value in zip(fields[visible:], _bella_structseq_hidden(args[0])):
            past[field] = value
        return (cls, (tuple(tuple.__iter__(args[0])), past))

    def __replace__(*args, **kwds):              # structseq_replace
        receiver(args, "__replace__")
        if len(args) != 1:
            raise TypeError("__replace__() takes no positional arguments")
        if unnamed > 0:
            raise TypeError("__replace__() is not supported for " + shown + " because it has unnamed field(s)")
        values = [*tuple.__iter__(args[0]), *_bella_structseq_hidden(args[0])]
        for i, field in enumerate(fields):
            if field in kwds:
                values[i] = kwds.pop(field)
        if kwds:
            raise TypeError("Got unexpected field name(s): " + repr(list(kwds)))
        return _bella_structseq_make(cls, values[:visible], values[visible:])

    body = {"__new__": __new__, "__repr__": __repr__, "__reduce__": __reduce__, "__replace__": __replace__}
    if not has_new:
        del body["__new__"]
    for method in body.values():
        method.__qualname__ = name + "." + method.__name__
    for field in named:                          # where the members go, in CPython's order
        body[field] = None
    body["__doc__"] = None
    if says_module:
        body["__module__"] = module
    body["n_sequence_fields"] = visible
    body["n_fields"] = total
    body["n_unnamed_fields"] = unnamed
    body["__match_args__"] = tuple([f for f in fields[:visible] if f is not None])
    body["__slots__"] = ("_s_past",)
    cls = type(name, (tuple,), body)
    _bella_structseq_finish(cls, module, fields, has_new)
    return cls


# ---- what sys has as named tuples and values: Python/sysmodule.c, and what the library reads when it imports

def _bella_sys_surface(thread_version, hash_randomization):
    version_info = _bella_structseq("version_info", "sys", ["major", "minor", "micro", "releaselevel", "serial"], 5, has_new=False, says_module=False)
    flags = _bella_structseq("flags", "sys", ["debug", "inspect", "interactive", "optimize", "dont_write_bytecode", "no_user_site", "no_site", "ignore_environment", "verbose", "bytes_warning", "quiet",
                                              "hash_randomization", "isolated", "dev_mode", "utf8_mode", "warn_default_encoding", "safe_path", "int_max_str_digits", "gil", "thread_inherit_context",
                                              "context_aware_warnings", "lazy_imports"], 18, has_new=False, says_module=False)
    float_info = _bella_structseq("float_info", "sys", ["max", "max_exp", "max_10_exp", "min", "min_exp", "min_10_exp", "dig", "mant_dig", "epsilon", "radix", "rounds"], 11, says_module=False)
    int_info = _bella_structseq("int_info", "sys", ["bits_per_digit", "sizeof_digit", "default_max_str_digits", "str_digits_check_threshold"], 4, says_module=False)
    hash_info = _bella_structseq("hash_info", "sys", ["width", "modulus", "inf", "nan", "imag", "algorithm", "hash_bits", "seed_bits", "cutoff"], 9, says_module=False)
    thread_info = _bella_structseq("thread_info", "sys", ["name", "lock", "version"], 3, says_module=False)
    # Python/errors.c's UnraisableHookArgs, what sys.unraisablehook is called with; no module holds it
    unraisable_args = _bella_structseq("UnraisableHookArgs", "builtins", ["exc_type", "exc_value", "exc_traceback", "err_msg", "object"], 5, says_module=False)
    version = _bella_structseq_make(version_info, [3, 15, 2, "final", 0], [])
    return {
        "version_info": version,
        "flags": _bella_structseq_make(flags, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, hash_randomization, 0, False, 1, 0, False, 4300], [1, 0, 0, -1]),
        "float_info": float_info([1.7976931348623157e+308, 1024, 308, 2.2250738585072014e-308, -1021, -307, 15, 53, 2.220446049250313e-16, 2, 1]),
        "int_info": int_info([30, 4, 4300, 640]),
        "hash_info": hash_info([64, 2305843009213693951, 314159, 0, 1000003, "siphash13", 64, 128, 0]),
        "thread_info": thread_info(["pthread", "pymutex", thread_version]),
        "implementation": SimpleNamespace(name="bella", cache_tag=None, version=version, hexversion=51315440, _multiarch="x86_64-linux-gnu", supports_isolated_interpreters=False),
        "_bella_unraisable_args": unraisable_args,   # the runtime's own: it takes it out of what goes into sys
    }


# ---- what object says to whoever would copy an instance (Objects/typeobject.c)

_ABSENT_SLOT = object()


def _get_slotnames(cls):                         # _PyType_GetSlotNames
    found = type.__dict__["__dict__"].__get__(cls).get("__slotnames__", _ABSENT_SLOT)
    if found is not _ABSENT_SLOT:
        if found is not None and not issubclass(type(found), list):
            raise TypeError(_bella_tp_name_of(cls) + ".__slotnames__ should be a list or None, not " + _tp_name(found))
        return found
    import copyreg
    names = copyreg._slotnames(cls)
    if names is not None and not issubclass(type(names), list):
        raise TypeError("copyreg._slotnames didn't return a list or None")
    return names


def _getstate_default(obj, required):            # object_getstate_default
    cls = type(obj)
    layout = _bella_pickle_layout(cls)           # 2: tp_itemsize; 1: a C type's fields, which neither dict nor slots hold
    if required and layout == 2:
        raise TypeError("cannot pickle " + _bella_tp_name_of(cls) + " objects")
    state = _bella_instance_dict(obj)
    slotnames = _get_slotnames(cls)
    if required and layout == 1:
        raise TypeError("cannot pickle '" + _bella_tp_name_of(cls) + "' object")
    if slotnames is not None and list.__len__(slotnames) > 0:
        slots = {}
        size = list.__len__(slotnames)
        i = 0
        while i < size:
            name = list.__getitem__(slotnames, i)
            try:
                slots[name] = getattr(obj, name)
            except AttributeError:               # It is not an error if the attribute is not present
                pass
            if size != list.__len__(slotnames):  # it is stored on the class, so it may mutate
                raise RuntimeError("__slotnames__ changed size during iteration")
            i += 1
        if len(slots) > 0:
            state = (state, slots)
    return state


def _getstate(obj, required):                    # object_getstate
    getstate = obj.__getstate__
    if type(getstate) is type(len) and getstate.__self__ is obj and type(obj).__getstate__ is object.__dict__["__getstate__"]:
        return _getstate_default(obj, required)  # not overridden: pass the required argument
    return getstate()


def _get_new_arguments(obj):                     # _PyObject_GetNewArguments
    found = _lookup_special(obj, "__getnewargs_ex__")
    if found:
        newargs = found[0]()
        if not issubclass(type(newargs), tuple):
            raise TypeError("__getnewargs_ex__ should return a tuple, not '" + _tp_name(newargs) + "'")
        if tuple.__len__(newargs) != 2:          # PyTuple_GET_SIZE: what the tuple holds, whatever a subclass says
            raise ValueError("__getnewargs_ex__ should return a tuple of length 2, not " + str(tuple.__len__(newargs)))
        args = tuple.__getitem__(newargs, 0)
        kwargs = tuple.__getitem__(newargs, 1)
        if not issubclass(type(args), tuple):
            raise TypeError("first item of the tuple returned by __getnewargs_ex__ must be a tuple, not '" + _tp_name(args) + "'")
        if not issubclass(type(kwargs), dict):
            raise TypeError("second item of the tuple returned by __getnewargs_ex__ must be a dict, not '" + _tp_name(kwargs) + "'")
        return args, kwargs
    found = _lookup_special(obj, "__getnewargs__")
    if found:
        args = found[0]()
        if not issubclass(type(args), tuple):
            raise TypeError("__getnewargs__ should return a tuple, not '" + _tp_name(args) + "'")
        return args, None
    return None, None


def _reduce_newobj(obj):                         # reduce_newobj
    cls = type(obj)
    if _bella_no_tp_new(cls):
        raise TypeError("cannot pickle '" + _bella_tp_name_of(cls) + "' object")
    args, kwargs = _get_new_arguments(obj)
    import copyreg
    hasargs = args is not None
    if kwargs is None or dict.__len__(kwargs) == 0:
        newobj = copyreg.__newobj__
        newargs = (cls, *(tuple.__iter__(args) if hasargs else ()))
    elif args is not None:
        newobj = copyreg.__newobj_ex__
        newargs = (cls, args, kwargs)
    else:
        raise SystemError("bad argument to internal function")
    state = _getstate(obj, not (hasargs or issubclass(cls, list) or issubclass(cls, dict)))
    listitems = iter(obj) if issubclass(cls, list) else None     # _PyObject_GetItemsIter
    dictitems = iter(obj.items()) if issubclass(cls, dict) else None
    return (newobj, newargs, state, listitems, dictitems)


def _common_reduce(obj, proto):                  # _common_reduce
    if proto >= 2:
        return _reduce_newobj(obj)
    import copyreg
    return copyreg._reduce_ex(obj, proto)


def _object_reduce_ex(*args, **kwds):            # object___reduce___ex___impl: METH_O, with its int
    obj = args[0]
    if kwds:
        raise TypeError("object.__reduce_ex__() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError("object.__reduce_ex__() takes exactly one argument (" + str(len(args) - 1) + " given)")
    proto = _number_index(args[1])
    if not -2147483648 <= proto <= 2147483647:
        raise OverflowError("Python int too large to convert to C int")
    try:
        reduce = obj.__reduce__
    except AttributeError:
        return _common_reduce(obj, proto)
    if type(obj).__reduce__ is not object.__dict__["__reduce__"]:   # overridden
        return reduce()
    return _common_reduce(obj, proto)


def _object_reduce(*args, **kwds):               # object___reduce___impl
    if kwds:
        raise TypeError("object.__reduce__() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("object.__reduce__() takes no arguments (" + str(len(args) - 1) + " given)")
    return _common_reduce(args[0], 0)


def _object_getstate(*args, **kwds):             # object___getstate___impl
    if kwds:
        raise TypeError("object.__getstate__() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("object.__getstate__() takes no arguments (" + str(len(args) - 1) + " given)")
    return _getstate_default(args[0], False)

