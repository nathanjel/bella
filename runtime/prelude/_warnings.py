"""_warnings, in Python (Python/_warnings.c): the C half of the warnings machinery, which warnings.py imports over _py_warnings
and whose objects then stand in the module (filters, warn, warn_explicit, the once registry, the default action, the context
variable and the lock). The rules are the C's: the filters are read from the warnings module each time and remembered, a plain-str
module filter matches exactly where a pattern is matched (against the module, or the filename when the module is not given), the
registry's version follows this module's own counter, and the frame a warning is charged to comes from the runtime's frame chain,
which, as CPython's, has no frame for this module's functions. Showing a warning goes through warnings._showwarnmsg; the C's own
printing (show_warning) is for when the warnings module is not there to ask: on the way out, when nothing is imported any more
and sys.modules is empty, or with its _showwarnmsg deleted. It prints the line of the warning; the source line beneath it, which
the C reads from the file, stops by name."""

__all__ = ["_acquire_lock", "_defaultaction", "_filters_mutated_lock_held", "_onceregistry", "_release_lock", "_warnings_context",
           "filters", "warn", "warn_explicit"]

__name__ = "_warnings"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _frame                                       # noqa: B018  # the frame n callers above the one calling into this module: (globals, filename, lineno), or None
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _bella_shutting_down                         # noqa: B018  # _Py_IsInterpreterFinalizing
except NameError:
    import operator
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    _number_index: Callable[[object], int] = operator.index

    def _unpack_keywords(fname: str, names: tuple[str, ...], posonly: int, minpos: int, maxpos: int, minkw: int, args: tuple[object, ...],
                         kwds: dict[str, object], absent: object) -> list[object]:
        raise ImportError("this file needs the runtime's primitives")

    def _frame(n: int) -> tuple[dict[str, object], str, int] | None:   # under CPython: this module's functions have frames, three deep
        import sys as _s
        try:
            f = _s._getframe(3 + n)
        except ValueError:
            return None
        return (f.f_globals, f.f_code.co_filename, f.f_lineno)

    def _bella_shutting_down() -> bool:
        import sys as _s
        return _s.is_finalizing()

import sys

import _contextvars

_ABSENT = object()                               # a NULL: an attribute the warnings module lacks, an argument not given
_MAXSIZE = 2**63 - 1

# ---- the interpreter's warnings state (_PyWarnings_InitState) -----------------------------------------------------------------
filters: list[object] = [("default", None, DeprecationWarning, "__main__", 0), ("ignore", None, DeprecationWarning, None, 0),
                         ("ignore", None, PendingDeprecationWarning, None, 0), ("ignore", None, ImportWarning, None, 0),
                         ("ignore", None, ResourceWarning, None, 0)]
_onceregistry: dict[object, object] = {}
_defaultaction = "default"
_warnings_context: _contextvars.ContextVar[object] = _contextvars.ContextVar("_warnings_context")
_state: dict[str, object] = {"filters": filters, "once_registry": _onceregistry, "default_action": _defaultaction, "filters_version": 0,
                             "lock_depth": 0}   # st->filters and the others follow the warnings module's attributes once seen; one thread holds the mutex


def _warnings_attr(name: str, try_import: bool) -> object:   # get_warnings_attr: the warnings module's attribute, or _ABSENT
    if try_import and not _bella_shutting_down():   # "don't try to import after the start of the Python finalization"
        try:
            wm = __import__("warnings")
        except ImportError:
            return _ABSENT
    else:
        wm = sys.modules.get("warnings")
        if wm is None:
            return _ABSENT
    return getattr(wm, name, _ABSENT)


def _acquire_lock(*args: object, **kwds: object) -> None:
    _noargs("_acquire_lock", args, kwds)
    _state["lock_depth"] = _depth() + 1


def _release_lock(*args: object, **kwds: object) -> None:
    _noargs("_release_lock", args, kwds)
    if _depth() == 0:
        raise RuntimeError("cannot release un-acquired lock")
    _state["lock_depth"] = _depth() - 1


def _depth() -> int:
    depth = _state["lock_depth"]
    assert isinstance(depth, int)
    return depth


def _version() -> int:
    version = _state["filters_version"]
    assert isinstance(version, int)
    return version


def _noargs(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("_warnings." + fname + "() takes no keyword arguments")
    if args:
        raise TypeError("_warnings." + fname + "() takes no arguments (" + str(len(args)) + " given)")


def _filters_mutated_lock_held(*args: object, **kwds: object) -> None:
    _noargs("_filters_mutated_lock_held", args, kwds)
    if _depth() == 0:
        raise RuntimeError("warnings lock is not held")
    _state["filters_version"] = _version() + 1


# ---- the filters ---------------------------------------------------------------------------------------------------------------

def _matched(obj: object, arg: object, arg2: object) -> bool:   # check_matched
    if obj is None:
        return True
    if type(obj) is str:                         # an internal plain text default filter must match exactly
        if arg is _ABSENT:
            return False
        if not isinstance(arg, str):
            raise TypeError("Can't compare " + _tp_name(obj) + " and " + _tp_name(arg))
        return str.__eq__(obj, arg) is True
    if arg is not _ABSENT:                       # otherwise a regex filter: its match() method
        result = obj.match(arg)  # type: ignore[attr-defined]
    else:
        from _py_warnings import _match_filename
        result = _match_filename(obj, arg2)
    return bool(result)


def _context_filters() -> object:                # get_warnings_context_filters: the context's _filters, or None
    ctx = _warnings_context.get(None)
    if ctx is None:
        return None
    context_filters = ctx._filters  # type: ignore[attr-defined]
    if not isinstance(context_filters, list):
        raise ValueError("_filters of warnings._warnings_context must be a list")
    return context_filters


def _global_filters() -> list[object]:           # get_warnings_filters
    found = _warnings_attr("filters", False)
    if found is not _ABSENT:
        _state["filters"] = found
    current = _state["filters"]
    if not isinstance(current, list):
        raise ValueError("_warnings.filters must be a list")
    return current


def _once_registry() -> dict[object, object]:    # get_once_registry
    found = _warnings_attr("onceregistry", False)
    if found is _ABSENT:
        registry = _state["once_registry"]
        assert isinstance(registry, dict)
        return registry
    if not isinstance(found, dict):
        raise TypeError("_warnings.onceregistry must be a dict, not '" + _tp_name(found) + "'")
    _state["once_registry"] = found
    return found


def _default_action() -> str:                    # get_default_action
    found = _warnings_attr("defaultaction", False)
    if found is _ABSENT:
        action = _state["default_action"]
        assert isinstance(action, str)
        return action
    if not isinstance(found, str):
        raise TypeError("_warnings.defaultaction must be a string, not '" + _tp_name(found) + "'")
    _state["default_action"] = found
    return found


def _ssize(value: object) -> int:                # PyLong_AsSsize_t: an int only, no __index__
    if not isinstance(value, int):
        raise TypeError("an integer is required")
    if value > _MAXSIZE or value < -_MAXSIZE - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return int(value)


def _filter_search(category: object, text: object, lineno: int, module: object, filename: object, list_name: str,
                   items: list[object]) -> tuple[object, object]:   # filter_search: (item, action), (None, None) for no match
    for i, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) != 5:
            raise ValueError("warnings." + list_name + " item " + str(i) + " isn't a 5-tuple")
        action, msg, cat, mod, ln_obj = item
        if not isinstance(action, str):
            raise TypeError("action must be a string, not '" + _tp_name(action) + "'")
        good_msg = _matched(msg, text, _ABSENT)
        good_mod = _matched(mod, module, filename)
        is_subclass = issubclass(category, cat)  # type: ignore[arg-type]
        ln = _ssize(ln_obj)
        if good_msg and is_subclass and good_mod and (ln == 0 or lineno == ln):
            return item, action
    return None, None


def _get_filter(category: object, text: object, lineno: int, module: object, filename: object) -> tuple[str, object]:   # get_filter: (action, item)
    context_filters = _context_filters()
    if context_filters is not None:
        assert isinstance(context_filters, list)
        item, action = _filter_search(category, text, lineno, module, filename, "_warnings_context _filters", context_filters)
        if action is not None:
            assert isinstance(action, str)
            return action, item
    else:
        item, action = _filter_search(category, text, lineno, module, filename, "filters", _global_filters())
        if action is not None:
            assert isinstance(action, str)
            return action, item
    return _default_action(), None


def _already_warned(registry: dict[object, object], key: object, should_set: bool) -> bool:
    version = dict.get(registry, "version", _ABSENT)
    if version is _ABSENT or type(version) is not int or version != _version():
        dict.clear(registry)
        dict.__setitem__(registry, "version", _version())
    else:
        already = dict.get(registry, key, _ABSENT)
        if already is not _ABSENT and already:
            return True
    if should_set:                               # this warning wasn't found in the registry: set it
        dict.__setitem__(registry, key, True)
    return False


def _update_registry(registry: dict[object, object], text: object, category: object, add_zero: bool) -> bool:
    altkey = (text, category, 0) if add_zero else (text, category)
    return _already_warned(registry, altkey, True)


def _file_write(value: object, f: object) -> None:   # PyFile_WriteObject(value, f, Py_PRINT_RAW), PyFile_WriteString
    writer = f.write  # type: ignore[attr-defined]
    writer(str(value))


def _show_warning(filename: object, lineno: int, text: object, category: object, sourceline: object) -> None:   # show_warning
    """The C's own printing on sys.stderr: "filename:lineno: Category: text", a write for each part. Whatever goes wrong ends it
    and is dropped (PyErr_Clear). Beneath it the C prints the source line: the one it was given, as it stands (it measures the
    indentation and then writes the whole line); or, given none, the one it reads from the file: nothing for a file name in
    angle brackets, as the "<sys>" of a warning with no frame, and nothing on the way out, where its import of io fails
    (measured on 3.15.2: a warning from a __del__ that runs at exit is one line)."""
    f_stderr = dict.get(sys.__dict__, "stderr", _ABSENT)
    try:
        name = category.__name__  # type: ignore[attr-defined]
        if f_stderr is _ABSENT:
            _bella_refuse("_warnings' note that sys.stderr is lost (show_warning writes it to the C stream)")
        _file_write(filename, f_stderr)
        _file_write(":" + str(lineno) + ": ", f_stderr)
        _file_write(name, f_stderr)
        _file_write(": ", f_stderr)
        _file_write(text, f_stderr)
        _file_write("\n", f_stderr)
    except BaseException:  # noqa: BLE001
        return
    if sourceline is not None:
        try:
            _file_write(sourceline, f_stderr)
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            _file_write("\n", f_stderr)
        except BaseException:  # noqa: BLE001, S110
            pass
        return
    assert isinstance(filename, str)             # _Py_DisplaySourceLine(f_stderr, filename, lineno, 2, NULL, NULL)
    if (str.__len__(filename) > 0 and filename[0] == "<" and filename[-1] == ">") or _bella_shutting_down():
        return
    _bella_refuse("_warnings' own printing of a warning's source line (show_warning, with the warnings module not there to ask)")


def _call_show_warning(category: object, text: object, message: object, filename: object, lineno: int, sourceline: object,
                       source: object, module: object) -> None:
    show_fn = _warnings_attr("_showwarnmsg", True)
    if show_fn is _ABSENT:
        _show_warning(filename, lineno, text, category, sourceline)
        return
    if not callable(show_fn):
        raise TypeError("warnings._showwarnmsg() must be set to a callable")
    cls = _warnings_attr("WarningMessage", False)
    if cls is _ABSENT:
        raise RuntimeError("unable to get warnings.WarningMessage")
    if module is _ABSENT:                        # a NULL ends the C's argument list: WarningMessage's own default
        msg = cls(message, category, filename, lineno, None, sourceline, source)  # type: ignore[operator]
    else:
        msg = cls(message, category, filename, lineno, None, sourceline, source, module)  # type: ignore[operator]
    show_fn(msg)


def _warn_explicit(category: object, message: object, filename: object, lineno: int, module: object, registry: object,
                   sourceline: object, source: object) -> None:   # warn_explicit, under the lock
    if module is None:                           # a warning emitted late in shutdown: ignored
        return
    if registry is not _ABSENT and registry is not None and not isinstance(registry, dict):
        raise TypeError("'registry' must be a dict or None")
    if isinstance(message, Warning):             # normalise the message
        text: object = str(message)
        category = type(message)
    else:
        text = message
        message = category(message)  # type: ignore[operator]
    if source is None:
        source = _ABSENT
    key = (text, category, lineno)
    if registry is not _ABSENT and registry is not None:
        assert isinstance(registry, dict)
        if _already_warned(registry, key, False):
            return
    action, item = _get_filter(category, text, lineno, module, filename)
    if action == "error":
        raise message  # type: ignore[misc]
    if action == "ignore":
        return
    rc = False
    if action != "always" and action != "all":   # store in the registry that we've been here
        if registry is not _ABSENT and registry is not None:
            assert isinstance(registry, dict)
            dict.__setitem__(registry, key, True)
        if action == "once":
            if registry is _ABSENT or registry is None:
                registry = _once_registry()
            assert isinstance(registry, dict)
            rc = _update_registry(registry, text, category, False)
        elif action == "module":
            if registry is not _ABSENT and registry is not None:
                assert isinstance(registry, dict)
                rc = _update_registry(registry, text, category, False)
        elif action != "default":
            raise RuntimeError("Unrecognized action (" + repr(action) + ") in warnings.filters:\n " + repr(item))
    if rc:                                       # already warned for this module
        return
    _call_show_warning(category, text, message, filename, lineno, sourceline, None if source is _ABSENT else source, module)


# ---- the frame a warning is charged to (setup_context) ------------------------------------------------------------------------

def _is_internal_filename(filename: object) -> bool:
    return isinstance(filename, str) and "importlib" in filename and "_bootstrap" in filename


def _is_filename_to_skip(filename: object, skip_file_prefixes: tuple[object, ...] | None) -> bool:
    if skip_file_prefixes and isinstance(filename, str):
        for prefix in skip_file_prefixes:
            if filename.startswith(prefix):  # type: ignore[arg-type]
                return True
    return False


def _setup_context(stack_level: int, skip_file_prefixes: tuple[object, ...] | None) -> tuple[object, int, object, object]:
    """(filename, lineno, module, registry) of the frame stack_level frames up, as the C computes them; the registry is whatever
    the globals hold under __warningregistry__ (warn_explicit checks it), a new dict when they hold nothing."""
    if skip_file_prefixes:
        for prefix in skip_file_prefixes:
            if not isinstance(prefix, str):
                raise TypeError("Found non-str '" + _tp_name(prefix) + "' in skip_file_prefixes.")
    depth = 0
    f = _frame(0)
    if stack_level <= 0 or (f is not None and _is_internal_filename(f[1])):
        stack_level -= 1
        while stack_level > 0 and f is not None:
            depth += 1
            f = _frame(depth)
            stack_level -= 1
    else:
        stack_level -= 1
        while stack_level > 0 and f is not None:   # next_external_frame
            while True:
                depth += 1
                f = _frame(depth)
                if f is None or not (_is_internal_filename(f[1]) or _is_filename_to_skip(f[1], skip_file_prefixes)):
                    break
            stack_level -= 1
    if f is None:
        globals_ = sys.__dict__
        filename: object = "<sys>"
        lineno = 0
    else:
        globals_, filename, lineno = f
    registry = dict.get(globals_, "__warningregistry__", _ABSENT)
    if registry is _ABSENT:
        registry = {}
        dict.__setitem__(globals_, "__warningregistry__", registry)
    module = dict.get(globals_, "__name__", _ABSENT)
    if module is _ABSENT or not (module is None or isinstance(module, str)):
        module = "<string>"
    return filename, lineno, module, registry


def _get_category(message: object, category: object) -> object:
    if isinstance(message, Warning):             # the category argument is ignored
        return type(message)
    if category is None:
        return UserWarning
    if not isinstance(category, type):
        raise TypeError("category must be a Warning subclass, not '" + _tp_name(category) + "'")
    if not issubclass(category, Warning):
        raise TypeError("category must be a Warning subclass, not class '" + category.__name__ + "'")
    return category


# ---- the module's functions (clinic) -------------------------------------------------------------------------------------------

def warn(*args: object, **kwds: object) -> None:
    message, category, stacklevel, source, skip_file_prefixes = _unpack_keywords("warn", ("message", "category", "stacklevel", "source", "skip_file_prefixes"), 0, 1, 4, 0, args, kwds, _ABSENT)
    if category is _ABSENT:
        category = None
    if stacklevel is _ABSENT:
        level = 1
    else:
        level = _number_index(stacklevel)
        if level > _MAXSIZE or level < -_MAXSIZE - 1:
            raise OverflowError("Python int too large to convert to C ssize_t")
    if source is _ABSENT:
        source = None
    prefixes: tuple[object, ...] | None
    if skip_file_prefixes is _ABSENT:
        prefixes = None
    elif not isinstance(skip_file_prefixes, tuple):
        raise TypeError("warn() argument 'skip_file_prefixes' must be tuple, not " + _tp_name(skip_file_prefixes))
    else:
        prefixes = skip_file_prefixes
    category = _get_category(message, category)
    if prefixes is not None:
        if len(prefixes) > 0:
            if level < 2:
                level = 2
        else:
            prefixes = None
    filename, lineno, module, registry = _setup_context(level, prefixes)   # do_warn
    _acquire_lock()
    try:
        _warn_explicit(category, message, filename, lineno, module, registry, None, source)
    finally:
        _release_lock()


def warn_explicit(*args: object, **kwds: object) -> None:
    message, category, filename, lineno, module, registry, module_globals, source = _unpack_keywords(
        "warn_explicit", ("message", "category", "filename", "lineno", "module", "registry", "module_globals", "source"), 0, 4, 8, 0, args, kwds, _ABSENT)
    if not isinstance(filename, str):
        raise TypeError("warn_explicit() argument 'filename' must be str, not " + _tp_name(filename))
    line = _number_index(lineno)
    if line > 2**31 - 1 or line < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    if registry is _ABSENT:
        registry = None
    if module_globals is _ABSENT:
        module_globals = None
    if source is _ABSENT:
        source = None
    if module_globals is not None:
        if not isinstance(module_globals, dict):
            raise TypeError("module_globals must be a dict or a frozendict, not " + _tp_name(module_globals))
        _bella_refuse("warn_explicit() with module_globals (the module loader's source line, _PyImport_BlessMyLoader)")
    source_line = None
    _acquire_lock()
    try:
        _warn_explicit(category, message, filename, line, module, registry, source_line, source)
    finally:
        _release_lock()

