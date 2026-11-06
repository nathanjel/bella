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

    # bella: @_requires_builtin, written out (it needs functions' __dict__)
    @classmethod
    def get_code(cls, fullname):
        """Return None as built-in modules do not have code objects."""
        _check_builtin(fullname)
        return None

    @classmethod
    def get_source(cls, fullname):
        """Return None as built-in modules do not have source code."""
        _check_builtin(fullname)
        return None

    @classmethod
    def is_package(cls, fullname):
        """Return False as built-in modules are never packages."""
        _check_builtin(fullname)
        return False


def _check_builtin(fullname):
    if not _bella_is_builtin(fullname):
        raise ImportError(f'{fullname!r} is not a built-in module',
                          name=fullname)


class FrozenImporter:

    """Meta path import for frozen modules.

    All methods are either class or static methods to avoid the need to
    instantiate the class.

    """

    _ORIGIN = "frozen"

    # bella: a frozen module's code is compiled into the program like any other module's; what
    # find_spec reads of _imp.find_frozen and sys._stdlib_dir, the registry says (_spec_from_compiled)

    @staticmethod
    def create_module(spec):
        """Set __file__, if able.

        NOTE: Normally this would be set by importlib.

        """
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

    @classmethod
    def is_package(cls, fullname):
        """Return True if the frozen module is a package."""
        found = _bella_find(fullname)  # bella: _imp.is_frozen_package
        if found is None or not found[2]:
            raise ImportError(f'{fullname!r} is not a frozen module', name=fullname)
        return found[1]


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
    self = object.__new__(cls)
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
        it = object.__new__(generic_alias_iterator)
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
        self = object.__new__(cls)
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


# ---- typing.Union ----

# bella: Objects/unionobject.c in Python; present_as_c_types names it typing.Union, has no __new__ of its own to show
# (make_union alone makes one, as _bella_new_instance), and gives it __name__, __qualname__, __origin__ and
# __parameters__ as getsets. type.__or__ and type.__ror__ are the runtime's and come here, as _union_type_or.

_union_set = object.__setattr__
_UNION_OWN = ('_union_hashable', '_union_unhashable', '_union_params')


def _is_unionable(obj):
    """is_unionable; the runtime has no type alias to ask about yet."""
    return obj is None or _ga_check(obj, type) or type(obj) is sentinel or _ga_check(obj, GenericAlias) or type(obj) is Union


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
    if debug_override is not None:
        _bella_refuse("importlib.util.cache_from_source with debug_override: DeprecationWarning (step 3b)")
    # bella: sys.implementation.cache_tag is None (D-16): a compiled program has no bytecode cache
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

    # bella: the methods below read or write files, which a compiled program does not do
    def path_mtime(self, path):
        _bella_refuse("a source loader's path_mtime (a compiled program has no source to read)")

    def path_stats(self, path):
        _bella_refuse("a source loader's path_stats (a compiled program has no source to read)")

    def _cache_bytecode(self, source_path, cache_path, data):
        _bella_refuse("a source loader's _cache_bytecode (a compiled program has no bytecode)")

    def set_data(self, path, data):
        """Optional method which writes data (bytes) to a file path (a str)."""

    def get_source(self, fullname):
        _bella_refuse("a source loader's get_source (step 3b: reading files)")

    def source_to_code(self, data, path, fullname=None, *, _optimize=-1):
        _bella_refuse("a source loader's source_to_code (E-01: no compiler at runtime)")

    def get_code(self, fullname):
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

    def get_filename(self, name=None):
        """Return the path to the source file as found by the finder."""
        # bella: under _check_name
        if name is None:
            name = self.name
        elif self.name != name:
            # bella: CPython's text formats with %, which the runtime lacks yet; the same message
            raise ImportError(f'loader for {self.name} cannot handle {name}', name=name)
        return self.path

    def get_data(self, path):
        """Return the data from path as raw bytes."""
        _bella_refuse("a file loader's get_data (step 3b: reading files)")

    def get_resource_reader(self, name=None):
        _bella_refuse("a source loader's get_resource_reader (importlib.resources is [P2+])")


class SourceFileLoader(FileLoader, SourceLoader):

    """Concrete implementation of SourceLoader using the file system."""

    __module__ = '_frozen_importlib_external'

    def path_stats(self, path):
        """Return the metadata for the path."""
        _bella_refuse("a source loader's path_stats (a compiled program has no source to read)")

    def _cache_bytecode(self, source_path, bytecode_path, data):
        _bella_refuse("a source loader's _cache_bytecode (a compiled program has no bytecode)")

    def set_data(self, path, data, *, _mode=0):
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
