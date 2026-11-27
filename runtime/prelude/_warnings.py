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
    _quiet_callers                               # noqa: B018  # the frames of a Python module that stands for a C module, with no frame of the program's between them and here
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _bella_shutting_down                         # noqa: B018  # _Py_IsInterpreterFinalizing
    _bella_import_if_held                        # noqa: B018  # (importer, name): importer(name), where a module of that name the program does not hold is not found
    _find_source_encoding                        # noqa: B018  # (fd, filename, io): _PyTokenizer_FindEncodingFilename's answer or None, and whether it left an error set
    _fd_seek                                     # noqa: B018  # lseek(fd, offset, SEEK_SET) worked
    _bella_holds                                 # noqa: B018  # the program holds a module of this name
    _own_data                                    # noqa: B018  # an argument's own data as the exact base object: the runtime's (RL-698)
    _repr_text                                   # noqa: B018  # %R: the characters of an object's repr, an exact str (RL-748's class)
    _class_name                                  # noqa: B018  # _PyType_Name of a class itself
    _type_fullname                               # noqa: B018  # %T: the fully qualified name of an object's type
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

    def _quiet_callers() -> int:
        return 0

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

    def _bella_import_if_held(importer: Callable[[str], object], name: str) -> object:
        return importer(name)

    _find_source_encoding: Callable[[int, str, object], tuple[str | None, bool]] = _missing
    _fd_seek: Callable[[int, int], bool] = _missing

    def _bella_holds(name: str) -> bool:
        return True
    _own_data: Callable[..., Any] = _missing

    def _repr_text(value: object) -> str:        # a stand-in for CPython's run of this file
        return str.__str__(repr(value))

    def _class_name(cls: type) -> str:           # a stand-in for CPython's run of this file
        return cls.__name__

    def _type_fullname(value: object) -> str:    # a stand-in for CPython's run of this file
        cls = type(value)
        return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__

import _io
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
        try:                                     # PyImport_Import. A program that holds no `warnings` module has none to find: the
            wm = _bella_import_if_held(__import__, "warnings")   # import fails as for a module that is not installed (D-27)
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
    assert issubclass(type(depth), int)
    return depth


def _version() -> int:
    version = _state["filters_version"]
    assert issubclass(type(version), int)
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
        if not issubclass(type(arg), str):
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
    if not issubclass(type(context_filters), list):
        raise ValueError("_filters of warnings._warnings_context must be a list")
    return context_filters


def _global_filters() -> list[object]:           # get_warnings_filters
    found = _warnings_attr("filters", False)
    if found is not _ABSENT:
        _state["filters"] = found
    current = _state["filters"]
    if not issubclass(type(current), list):
        raise ValueError("_warnings.filters must be a list")
    return current


def _once_registry() -> dict[object, object]:    # get_once_registry
    found = _warnings_attr("onceregistry", False)
    if found is _ABSENT:
        registry = _state["once_registry"]
        assert issubclass(type(registry), dict)
        return registry
    if not issubclass(type(found), dict):
        raise TypeError("_warnings.onceregistry must be a dict, not '" + _tp_name(found) + "'")
    _state["once_registry"] = found
    return found


def _default_action() -> str:                    # get_default_action
    found = _warnings_attr("defaultaction", False)
    if found is _ABSENT:
        action = _state["default_action"]
        assert issubclass(type(action), str)
        return action
    if not issubclass(type(found), str):
        raise TypeError("_warnings.defaultaction must be a string, not '" + _tp_name(found) + "'")
    _state["default_action"] = found
    return found


def _ssize(value: object) -> int:                # PyLong_AsSsize_t: an int only, no __index__
    if not issubclass(type(value), int):
        raise TypeError("an integer is required")
    value = _own_data(value)                     # the int's value: nothing of a subclass's is asked (RL-698)
    if value > _MAXSIZE or value < -_MAXSIZE - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return value  # type: ignore[no-any-return]


def _filter_search(category: object, text: object, lineno: int, module: object, filename: object, list_name: str,
                   items: list[object]) -> tuple[object, object]:   # filter_search: (item, action), (None, None) for no match
    i = 0
    while i < list.__len__(items):               # PyList_GET_SIZE and PyList_GET_ITEM at each turn: the list's own storage, as it
        item = list.__getitem__(items, i)        # is then; and the five slots of the tuple (PyTuple_GET_ITEM), RL-698
        if not issubclass(type(item), tuple) or tuple.__len__(item) != 5:  # type: ignore[arg-type]
            raise ValueError("warnings." + list_name + " item " + str(i) + " isn't a 5-tuple")
        action, msg, cat, mod, ln_obj = _own_data(item)
        if not issubclass(type(action), str):
            raise TypeError("action must be a string, not '" + _tp_name(action) + "'")
        good_msg = _matched(msg, text, _ABSENT)
        good_mod = _matched(mod, module, filename)
        is_subclass = issubclass(category, cat)  # type: ignore[arg-type]
        ln = _ssize(ln_obj)
        if good_msg and is_subclass and good_mod and (ln == 0 or lineno == ln):
            return item, action
        i += 1
    return None, None


def _get_filter(category: object, text: object, lineno: int, module: object, filename: object) -> tuple[str, object]:   # get_filter: (action, item)
    context_filters = _context_filters()
    if context_filters is not None:
        assert issubclass(type(context_filters), list)
        item, action = _filter_search(category, text, lineno, module, filename, "_warnings_context _filters", context_filters)
        if action is not None:
            assert issubclass(type(action), str)
            return action, item
    else:
        item, action = _filter_search(category, text, lineno, module, filename, "filters", _global_filters())
        if action is not None:
            assert issubclass(type(action), str)
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
    assert issubclass(type(filename), str)
    if _bella_shutting_down():
        return
    try:
        _display_source_line(f_stderr, filename, lineno)
    except BaseException:  # noqa: BLE001, S110
        pass


def _display_source_line(f: object, filename: str, lineno: int) -> None:   # _Py_DisplaySourceLine(f, filename, lineno, 2, NULL, NULL)
    """The line `lineno` of the file, read for this one use: opened in bytes by io.open (by its name, else by the last part of
    its name in each directory of sys.path), decoded as its first two lines say (UTF-8 when they say nothing), without the
    spaces, tabs and form feeds before it, two spaces before it and a new line after. Nothing for a name in angle brackets, a
    file that cannot be opened or rewound, or a line it does not have. Whatever is raised on the way ends it; the caller
    drops it."""
    # "things like <string> or <stdin>": PyUnicode_READ_CHAR, so the characters themselves, whatever a subclass's
    # __getitem__ would answer (RL-461)
    if str.__len__(filename) > 0 and str.__getitem__(filename, 0) == "<" and str.__getitem__(filename, -1) == ">":
        return
    try:
        io = _bella_import_if_held(__import__, "io")   # PyImport_ImportModule("io"), and any failure is the end of it
    except ImportError:
        if _bella_holds("io") or dict.get(sys.modules, "io", _ABSENT) is not _ABSENT:
            raise
        io = _io                                 # a program that holds no io module: io.open and io.TextIOWrapper are _io's own
    # "PyErr_Clear()" and then the search, and further down the close: what the C does after it dropped an error is done
    # after the handler, where an io.open or a close of the program's sees no error of this function's (review A38, RL-866)
    opened = False
    binary: object = None
    try:
        binary = io.open(filename, "rb")  # type: ignore[attr-defined]
        opened = True
    except BaseException:  # noqa: BLE001, S110
        pass
    if not opened:
        binary = _find_source_file(filename, io)
        if binary is None:
            return
    fd = _as_file_descriptor(binary)
    found, failed = _find_source_encoding(fd, filename, io)   # the tokenizer over the file's first lines, until its second
    if not _fd_seek(fd, 0):
        return
    if found is not None and failed:
        # The C drops the tokenizer's error only when it found no encoding. With one (a UTF-8 mark, a coding spec) and an
        # error after it (a spec that contradicts the mark, a NUL, a first token that is none), the error is still set when
        # io.TextIOWrapper is called: the call fails before the type makes its object, and the C closes the file and prints
        # no line. Measured on 3.15.2. A TextIOWrapper the program put in io would run first, with that error set.
        if getattr(io, "TextIOWrapper", _ABSENT) is not _io.TextIOWrapper:
            _bella_refuse("_warnings' reading of a source file through an io.TextIOWrapper the program replaced, after the tokenizer failed on the file's first lines")
        try:
            binary.close()
        except BaseException:  # noqa: BLE001, S110
            pass
        return
    wrapped = False
    fob: object = None
    try:
        fob = io.TextIOWrapper(binary, "utf-8" if found is None else found)  # type: ignore[attr-defined]
        wrapped = True
    except BaseException:  # noqa: BLE001, S110
        pass
    if not wrapped:
        try:
            binary.close()  # type: ignore[attr-defined]
        except BaseException:  # noqa: BLE001, S110
            pass
        return
    del binary
    line: object = None
    for _ in range(lineno):
        try:
            line = _get_line(fob)
        except BaseException:  # noqa: BLE001
            line = None
            break
    try:
        fob.close()
    except BaseException:  # noqa: BLE001, S110
        pass
    if not issubclass(type(line), str):
        return
    assert issubclass(type(line), str)
    start = 0
    while start < str.__len__(line) and str.__getitem__(line, start) in " \t\f":
        start += 1
    if start:
        line = str.__getitem__(line, slice(start, None))
    _file_write("  ", f)                         # _Py_WriteIndent(2, f)
    _file_write(line, f)
    _file_write("\n", f)


def _get_line(f: object) -> object:              # PyFile_GetLine(f, -1): a line without its new line; the file's end is an EOFError
    line = f.readline()  # type: ignore[attr-defined]
    # the C reads the object's own characters, whatever a subclass's __len__, __getitem__ or __eq__ would answer, and a line
    # that ends in a new line is cut to a str or bytes of its own (RL-461, the rest of it)
    if issubclass(type(line), bytes):
        size = bytes.__len__(line)
        if size == 0:
            raise EOFError("EOF when reading a line")
        return bytes.__getitem__(line, slice(0, size - 1)) if bytes.__getitem__(line, size - 1) == 10 else line
    if issubclass(type(line), str):
        size = str.__len__(line)
        if size == 0:
            raise EOFError("EOF when reading a line")
        return str.__getitem__(line, slice(0, size - 1)) if str.__getitem__(line, size - 1) == "\n" else line
    raise TypeError(_type_fullname(f) + ".readline() must return a str, not " + _type_fullname(line))   # "%T ... %T"


def _as_file_descriptor(value: object) -> int:   # PyObject_AsFileDescriptor
    if issubclass(type(value), int):
        if issubclass(type(value), bool):
            _bella_refuse("_warnings' RuntimeWarning for a bool used as the descriptor of a warning's source file (a warning inside the showing of one)")
        fd = int.__index__(value)  # type: ignore[arg-type]
    else:
        method = getattr(value, "fileno", _ABSENT)
        if method is _ABSENT:
            raise TypeError("argument must be an int, or have a fileno() method")
        given = method()  # type: ignore[operator]
        if not issubclass(type(given), int):
            raise TypeError("fileno() returned a non-integer")
        if issubclass(type(given), bool):
            _bella_refuse("_warnings' RuntimeWarning for a bool used as the descriptor of a warning's source file (a warning inside the showing of one)")
        fd = int.__index__(given)
    if fd < -2**31 or fd >= 2**31:
        raise OverflowError("Python int too large to convert to C int")
    if fd < 0:
        raise ValueError("file descriptor cannot be a negative integer (" + str(fd) + ")")
    return fd


_MAXPATHLEN = 4096


def _find_source_file(filename: str, io: object) -> object:   # _Py_FindSourceFile: the tail of the name in sys.path's directories, or None
    try:
        filepath = str.encode(filename, "utf-8", "surrogateescape")   # PyUnicode_EncodeFSDefault
    except BaseException:  # noqa: BLE001
        return None
    nul = bytes.find(filepath, b"\0")            # the C's strings end at a NUL
    if nul >= 0:
        filepath = filepath[:nul]
    tail = filepath[bytes.rfind(filepath, b"/") + 1:]
    syspath = dict.get(sys.__dict__, "path", _ABSENT)
    if not issubclass(type(syspath), list):
        return None
    assert issubclass(type(syspath), list)
    try:
        opener = io.open  # type: ignore[attr-defined]
    except BaseException:  # noqa: BLE001
        return None
    for i in range(list.__len__(syspath)):
        if i >= list.__len__(syspath):           # PyList_GetItem on a list that has shrunk
            break
        entry = list.__getitem__(syspath, i)
        if not issubclass(type(entry), str):
            continue
        try:
            path = str.encode(entry, "utf-8", "surrogateescape")
        except BaseException:  # noqa: BLE001
            continue
        if bytes.__len__(path) + 1 + bytes.__len__(tail) >= _MAXPATHLEN:   # "Too long"
            continue
        if bytes.find(path, b"\0") >= 0:         # "v contains '\0'"
            continue
        if path and path[-1:] != b"/":
            path += b"/"
        try:
            return opener(bytes.decode(path + tail, "utf-8"), "rb")   # the name as the C builds it: UTF-8, or no call
        except BaseException:  # noqa: BLE001, S112
            continue
    return None


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
    if registry is not _ABSENT and registry is not None and not issubclass(type(registry), dict):
        raise TypeError("'registry' must be a dict or None")
    if issubclass(type(message), Warning):             # normalise the message
        text: object = str(message)
        category = type(message)
    else:
        text = message
        message = category(message)  # type: ignore[operator]
    if source is None:
        source = _ABSENT
    key = (text, category, lineno)
    if registry is not _ABSENT and registry is not None:
        assert issubclass(type(registry), dict)
        if _already_warned(registry, key, False):
            return
    given, item = _get_filter(category, text, lineno, module, filename)
    action = _own_data(given)                    # _PyUnicode_EqualToASCIIString: the action's characters (RL-698)
    if action == "error":
        raise message  # type: ignore[misc]
    if action == "ignore":
        return
    rc = False
    if action != "always" and action != "all":   # store in the registry that we've been here
        if registry is not _ABSENT and registry is not None:
            assert issubclass(type(registry), dict)
            dict.__setitem__(registry, key, True)
        if action == "once":
            if registry is _ABSENT or registry is None:
                registry = _once_registry()
            assert issubclass(type(registry), dict)
            rc = _update_registry(registry, text, category, False)
        elif action == "module":
            if registry is not _ABSENT and registry is not None:
                assert issubclass(type(registry), dict)
                rc = _update_registry(registry, text, category, False)
        elif action != "default":
            raise RuntimeError("Unrecognized action (" + _repr_text(given) + ") in warnings.filters:\n " + _repr_text(item))
    if rc:                                       # already warned for this module
        return
    _call_show_warning(category, text, message, filename, lineno, sourceline, None if source is _ABSENT else source, module)


# ---- the frame a warning is charged to (setup_context) ------------------------------------------------------------------------

def _is_internal_filename(filename: object) -> bool:
    return issubclass(type(filename), str) and str.__contains__(filename, "importlib") and str.__contains__(filename, "_bootstrap")  # type: ignore[arg-type]


def _is_filename_to_skip(filename: object, skip_file_prefixes: tuple[object, ...] | None) -> bool:
    if skip_file_prefixes and issubclass(type(filename), str):
        for prefix in skip_file_prefixes:
            if str.startswith(filename, prefix):  # type: ignore[arg-type]   # PyUnicode_Tailmatch: the characters of both
                return True
    return False


def _setup_context(stack_level: int, skip_file_prefixes: tuple[object, ...] | None) -> tuple[object, int, object, object]:
    """(filename, lineno, module, registry) of the frame stack_level frames up, as the C computes them; the registry is whatever
    the globals hold under __warningregistry__ (warn_explicit checks it), a new dict when they hold nothing."""
    if skip_file_prefixes:
        for prefix in skip_file_prefixes:
            if not issubclass(type(prefix), str):
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
    if module is _ABSENT or not (module is None or issubclass(type(module), str)):
        module = "<string>"
    return filename, lineno, module, registry


def _get_category(message: object, category: object) -> object:
    if issubclass(type(message), Warning):             # the category argument is ignored
        return type(message)
    if category is None:
        return UserWarning
    if not issubclass(type(category), type):
        raise TypeError("category must be a Warning subclass, not '" + _tp_name(category) + "'")
    if not issubclass(category, Warning):
        raise TypeError("category must be a Warning subclass, not class '" + _class_name(category) + "'")   # tp_name
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
    # decimal and datetime are CPython's Python versions here, and such a module's own text counts its frames as levels
    # (`stacklevel=2` in datetime.utcnow, where the C module warns at level 1): its frames are none a program sees, so the
    # levels it counts for them are taken off (Question 50)
    quiet = _quiet_callers()
    if quiet and level > 1:
        level = max(1, level - quiet)
    prefixes: tuple[object, ...] | None
    if skip_file_prefixes is _ABSENT:
        prefixes = None
    elif not issubclass(type(skip_file_prefixes), tuple):
        raise TypeError("warn() argument 'skip_file_prefixes' must be tuple, not " + _tp_name(skip_file_prefixes))
    else:
        prefixes = _own_data(skip_file_prefixes)   # PyTuple_GET_SIZE and PyTuple_GET_ITEM: the tuple's own entries (RL-698)
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
    if not issubclass(type(filename), str):
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
        if not issubclass(type(module_globals), dict):
            raise TypeError("module_globals must be a dict or a frozendict, not " + _tp_name(module_globals))
        _bella_refuse("warn_explicit() with module_globals (the module loader's source line, _PyImport_BlessMyLoader)")
    source_line = None
    _acquire_lock()
    try:
        _warn_explicit(category, message, filename, line, module, registry, source_line, source)
    finally:
        _release_lock()

