"""Built-in functions written in Python (docs/DECISIONS.md, step 3 of the C++ leg).

Bella compiles this module into every program and puts the names in __all__ into the builtins.
CPython runs it in runtime/tests/test_prelude.py against the builtins it stands for, so each
function is checked against CPython directly, before Bella compiles it.
"""
import sys

__all__ = ["print", "input", "breakpoint", "property", "staticmethod", "classmethod"]
# Py_ReprEnter and Py_ReprLeave, for the built-in modules written in Python; _GetSet, which the runtime makes CPython's descriptors
__intrinsics__ = ["_enter", "_leave", "_GetSet"]


def print(*args: object, sep: object = " ", end: object = "\n", file: object = None, flush: object = False) -> None:
    """print(*args, sep=' ', end='\\n', file=None, flush=False), in builtin_print_impl's order:
    the file first (nothing at all when sys.stdout is None), then sep and end, each str(), then
    flush."""
    if file is None:
        file = sys.stdout
        if file is None:
            return
    if sep is None:
        sep = " "
    elif not isinstance(sep, str):
        raise TypeError("sep must be None or a string, not " + type(sep).__name__)
    if end is None:
        end = "\n"
    elif not isinstance(end, str):
        raise TypeError("end must be None or a string, not " + type(end).__name__)
    first = True
    for arg in args:
        if not first:
            file.write(str(sep))  # type: ignore[attr-defined]  # any object with write()
        first = False
        file.write(str(arg))  # type: ignore[attr-defined]
    file.write(str(end))  # type: ignore[attr-defined]
    if flush:
        file.flush()  # type: ignore[attr-defined]


def _standard_stream(name: str) -> object:
    """PySys_GetAttr and builtin_input's own test: the stream in sys's dict; one that is not there, or None, is lost."""
    stream = sys.__dict__.get(name)
    if stream is None:
        raise RuntimeError("lost sys." + name)
    return stream


def _flush_quietly(stream: object) -> None:
    """_PyFile_Flush with its error cleared (PyErr_Clear: whatever was raised)."""
    try:
        stream.flush()  # type: ignore[attr-defined]
    except BaseException:  # noqa: BLE001, S110
        pass


def _is_the_terminal(stream: object, descriptor: int) -> bool:
    """Whether `stream` is the process's own stream on that descriptor and a terminal: a stream without a fileno() is not, and a
    fileno() that is no C long is an error."""
    try:
        number = stream.fileno()  # type: ignore[attr-defined]
    except BaseException:  # noqa: BLE001
        return False
    fd = _number_index(number)                   # PyLong_AsLong
    if not -0x8000000000000000 <= fd <= 0x7fffffffffffffff:
        raise OverflowError("Python int too large to convert to C long")
    return fd == descriptor and _bella_isatty(fd)


_NO_TERMINAL = object()                          # the terminal's way gave up before reading: the other way is taken
_NO_HOOK = object()                              # sys has no breakpointhook


def _input_from_the_terminal(args: tuple[object, ...], fin: object, fout: object) -> object:
    """The readline branch of builtin_input_impl: sys.stdin's encoding and errors, sys.stdout flushed, the prompt encoded as
    sys.stdout would encode it, PyOS_Readline, and the line decoded as sys.stdin would decode it. A stream without an encoding
    and errors that are str is no terminal's after all."""
    try:
        stdin_encoding = fin.encoding  # type: ignore[attr-defined]
        stdin_errors = fin.errors  # type: ignore[attr-defined]
    except BaseException:  # noqa: BLE001
        return _NO_TERMINAL
    if not isinstance(stdin_encoding, str) or not isinstance(stdin_errors, str):
        return _NO_TERMINAL
    str.encode(stdin_encoding)                   # PyUnicode_AsUTF8: a lone surrogate is an error
    str.encode(stdin_errors)
    _flush_quietly(fout)
    prompt = b""
    if args:
        try:
            stdout_encoding = fout.encoding  # type: ignore[attr-defined]
            stdout_errors = fout.errors  # type: ignore[attr-defined]
        except BaseException:  # noqa: BLE001
            return _NO_TERMINAL
        if not isinstance(stdout_encoding, str) or not isinstance(stdout_errors, str):
            return _NO_TERMINAL
        str.encode(stdout_encoding)
        str.encode(stdout_errors)
        prompt = str.encode(str(args[0]), stdout_encoding, stdout_errors)
        if b"\0" in prompt:
            raise ValueError("input: prompt string cannot contain null characters")
    line = _bella_readline(prompt)               # PyOS_Readline: the line's bytes, none at the end of the input; None when interrupted
    if line is None:
        raise KeyboardInterrupt
    if not line:
        raise EOFError
    line = line[:-1]                             # "strip trailing '\n'": the last byte, whatever it is
    if line[-1:] == b"\r":
        line = line[:-1]
    return bytes.decode(line, stdin_encoding, stdin_errors)


def input(*args: object, **kwds: object) -> object:  # noqa: A001
    """input(prompt='', /), in builtin_input_impl's order: the three standard streams, each of which may be lost; sys.stderr
    flushed; then readline's way when sys.stdin and sys.stdout are the process's own and terminals, else str(prompt) written to
    sys.stdout, which is flushed, and sys.stdin.readline() without its newline (PyFile_GetLine). No event is audited: no hook can
    be added (sys.addaudithook)."""
    if kwds:
        raise TypeError("input() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("input expected at most 1 argument, got " + str(len(args)))
    fin = _standard_stream("stdin")
    fout = _standard_stream("stdout")
    ferr = _standard_stream("stderr")
    _flush_quietly(ferr)
    if _is_the_terminal(fin, 0) and _is_the_terminal(fout, 1):
        line = _input_from_the_terminal(args, fin, fout)
        if line is not _NO_TERMINAL:
            return line
    if args:
        write = fout.write  # type: ignore[attr-defined]  # PyFile_WriteObject, Py_PRINT_RAW: the writer first, then str(prompt)
        write(str(args[0]))
    _flush_quietly(fout)
    line = fin.readline()  # type: ignore[attr-defined]  # PyFile_GetLine(fin, -1)
    if isinstance(line, bytes):
        if not line:
            raise EOFError("EOF when reading a line")
        return line[:-1] if line[-1:] == b"\n" else line
    if isinstance(line, str):
        if not line:
            raise EOFError("EOF when reading a line")
        return line[:-1] if line[-1] == "\n" else line
    raise TypeError(_bella_type_name(fin) + ".readline() must return a str, not " + _bella_type_name(line))


def breakpoint(*args: object, **kws: object) -> object:  # noqa: A001
    """builtin_breakpoint: sys.breakpointhook, called with the arguments. sys has no hook of its own here (the sys surface of
    section 7), so one the program put there is called, and without one this is sys_breakpointhook where pdb cannot be imported
    (D-11): nothing under PYTHONBREAKPOINT=0, else CPython's warning for a hook it cannot import, and the program goes on. A
    hook named by PYTHONBREAKPOINT is an import by a computed name, and stops by name."""
    hook = sys.__dict__.get("breakpointhook", _NO_HOOK)
    if hook is not _NO_HOOK:
        return hook(*args, **kws)  # type: ignore[operator]
    named = _bella_getenv("PYTHONBREAKPOINT")
    if named == "0":
        return None
    if named:
        _bella_refuse("breakpoint() with PYTHONBREAKPOINT naming a hook (" + named + ": an import by a computed name)")
    _warn('Ignoring unimportable $PYTHONBREAKPOINT: "pdb.set_trace"', "RuntimeWarning")
    return None


try:
    _bella_new_instance                          # noqa: B018  # PyType_GenericAlloc: an instance of the type, its fields unset
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords, with its refusals
    _number_index                                # noqa: B018  # _PyNumber_Index, then the int's value
    _bella_isatty                                # noqa: B018  # isatty(fd)
    _bella_readline                              # noqa: B018  # PyOS_Readline over PyOS_StdioReadline
    _bella_type_name                             # noqa: B018  # PyErr_Format's %T: the type's fully qualified name
    _bella_getenv                                # noqa: B018  # Py_GETENV
    _bella_refuse                                # noqa: B018  # a stop by name
    _warn                                        # noqa: B018  # PyErr_WarnEx(category, message, 1): a message and the category's name
except NameError:                                # CPython runs this file (runtime/tests/test_prelude.py): what stands for them
    import operator
    import os
    import warnings
    from collections.abc import Callable

    _bella_new_instance: Callable[..., object] = object.__new__
    _number_index: Callable[[object], int] = operator.index
    _bella_isatty: Callable[[int], bool] = os.isatty
    _bella_getenv: Callable[[str], str | None] = os.environ.get

    def _bella_readline(prompt: bytes) -> bytes | None:
        raise AssertionError("no terminal under the tests")

    def _bella_type_name(obj: object) -> str:
        cls = type(obj)
        return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__

    def _bella_refuse(what: str) -> None:
        raise NotImplementedError(what)

    def _warn(message: str, category: str) -> None:
        warnings.warn(message, {"RuntimeWarning": RuntimeWarning}[category], stacklevel=3)

    def _tp_name(obj: object) -> str:
        return type(obj).__name__

    def _unpack_keywords(fname: str, names: tuple[str, ...], posonly: int, minpos: int, maxpos: int, minkw: int, args: tuple[object, ...],
                         kwds: dict[str, object], absent: object) -> list[object]:
        """The runtime's primitive for a function whose parameters are all optional and take a position or a name."""
        if len(args) + len(kwds) > len(names):
            raise TypeError(fname + "() takes at most " + str(len(names)) + (" keyword" if not args else "") + " arguments (" + str(len(args) + len(kwds)) + " given)")
        out = [*args, *[absent] * (len(names) - len(args))]
        for keyword, value in kwds.items():
            if keyword not in names:
                raise TypeError(fname + "() got an unexpected keyword argument '" + keyword + "'")
            if names.index(keyword) < len(args):
                raise TypeError("argument for " + fname + "() given by name ('" + keyword + "') and position (" + str(names.index(keyword) + 1) + ")")
            out[names.index(keyword)] = value
        return out


# ---- property, staticmethod and classmethod (Objects/descrobject.c, Objects/funcobject.c) ----
#
# Each is CPython's C struct: its fields are slots whose members are taken out of the type once it is made (`_field`), so that
# the type's namespace holds what CPython's holds and nothing else; what C declares as a member or a getset is a `_GetSet` in
# the class body, which the runtime makes the descriptor the names table says (types.cpp, present_methods). `__new__` is given
# after the three exist, as a class body's `__new__` is wrapped in a staticmethod.

_NULL = object()                                 # a field that holds nothing, where None is something a program can put there
_type_qualname = type.__dict__["__qualname__"].__get__   # PyType_GetQualName, whatever a metaclass answers


class _GetSet:
    """A member (PyMemberDef) or a getset (PyGetSetDef) of the three types, by the functions that read, write and delete it:
    no setter is a read-only one, no deleter one that cannot be deleted. The runtime makes each the descriptor the names table
    says and words the refusals itself; run by CPython, the descriptor is this class."""

    __slots__ = ("fdel", "fget", "fset", "member", "refusal")

    def __init__(self, fget: object, fset: object = None, fdel: object = None, member: bool = False) -> None:
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.member = member
        self.refusal = "readonly attribute"

    def __set_name__(self, owner: type, name: str) -> None:
        if not self.member:
            self.refusal = "attribute '" + name + "' of '" + owner.__name__ + "' objects is not writable"

    def __get__(self, obj: object, owner: object = None) -> object:
        if obj is None:
            return self
        return self.fget(obj)  # type: ignore[operator]

    def __set__(self, obj: object, value: object) -> None:
        if self.fset is None:
            raise AttributeError(self.refusal)
        self.fset(obj, value)  # type: ignore[operator]

    def __delete__(self, obj: object) -> None:
        if self.fdel is None:
            raise AttributeError(self.refusal)
        self.fdel(obj)  # type: ignore[operator]


def _field(cls: type, name: str) -> tuple[Callable[[object], object], Callable[[object, object], None]]:
    """A field of the struct: the slot's member leaves the type, and its two functions read and write the field."""
    member = cls.__dict__[name]
    delattr(cls, name)
    return member.__get__, member.__set__


def _new_receiver(args: tuple[object, ...], owner: type) -> type:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(owner.__name__ + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(owner.__name__ + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(owner.__name__ + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + owner.__name__)  # type: ignore[attr-defined]
    return cls  # type: ignore[return-value]


def _slot_receiver(args: tuple[object, ...], owner: type, name: str) -> object:   # wrapperdescr_call's checks
    if not args:
        raise TypeError("descriptor '" + name + "' of '" + owner.__name__ + "' object needs an argument")
    if not issubclass(type(args[0]), owner):
        raise TypeError("descriptor '" + name + "' requires a '" + owner.__name__ + "' object but received a '" + _tp_name(args[0]) + "'")
    return args[0]


def _method_one(args: tuple[object, ...], kwds: dict[str, object], owner: type, name: str) -> object:   # a METH_O method's argument
    if not args:
        raise TypeError("unbound method " + owner.__name__ + "." + name + "() needs an argument")
    if not issubclass(type(args[0]), owner):
        raise TypeError("descriptor '" + name + "' for '" + owner.__name__ + "' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
    if kwds:
        raise TypeError(owner.__name__ + "." + name + "() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError(owner.__name__ + "." + name + "() takes exactly one argument (" + str(len(args) - 1) + " given)")
    return args[1]


def _is_abstract(obj: object) -> bool:           # _PyObject_IsAbstract; a field that holds nothing is not
    if obj is None:
        return False
    if getattr(obj, "__isabstractmethod__", False):
        return True
    return False


def _property_name(self: object) -> object:      # property_name: the name it was given, or its getter's; _NULL for neither
    name = _name_of(self)
    if name is not _NULL:
        return name
    fget = _fget_of(self)
    if fget is None:
        return _NULL
    return getattr(fget, "__name__", _NULL)


def _property_lacks(self: object, obj: object, what: str) -> AttributeError:   # property_descr_get's and property_descr_set's error
    name = _property_name(self)
    qualname = _type_qualname(type(obj))
    if name is not _NULL:
        return AttributeError("property " + repr(name) + " of " + repr(qualname) + " object has no " + what)
    return AttributeError("property of " + repr(qualname) + " object has no " + what)


def _property_copy(old: object, fget: object, fset: object, fdel: object) -> object:   # property_copy
    if fget is None:
        fget = _fget_of(old)
    if fset is None:
        fset = _fset_of(old)
    if fdel is None:
        fdel = _fdel_of(old)
    doc = None if _getter_doc_of(old) and fget is not None else _doc_of(old)   # None: __init__ takes the getter's
    new = type(old)(fget, fset, fdel, doc)  # type: ignore[call-arg]
    if issubclass(type(new), property):
        _put_name(new, _name_of(old))
    return new


def _property_get_name(self: object) -> object:  # property_get__name__
    name = _property_name(self)
    if name is _NULL:
        raise AttributeError("'property' object has no attribute '__name__'")
    return name


def _property_del_name(self: object) -> None:    # property_set__name__ given nothing
    _put_name(self, _NULL)


def _property_del_doc(self: object) -> None:     # PyMember_SetOne given nothing: the field is empty, and reads None
    _put_doc(self, None)


class property:
    __slots__ = ("_getter_doc", "_prop_del", "_prop_doc", "_prop_get", "_prop_name", "_prop_set")

    fget = _GetSet(lambda self: _fget_of(self), member=True)
    fset = _GetSet(lambda self: _fset_of(self), member=True)
    fdel = _GetSet(lambda self: _fdel_of(self), member=True)
    __doc__ = _GetSet(lambda self: _doc_of(self), lambda self, value: _put_doc(self, value), _property_del_doc, member=True)  # type: ignore[assignment]
    __name__ = _GetSet(_property_get_name, lambda self, value: _put_name(self, value), _property_del_name)  # type: ignore[assignment]
    __isabstractmethod__ = _GetSet(lambda self: _is_abstract(_fget_of(self)) or _is_abstract(_fset_of(self)) or _is_abstract(_fdel_of(self)))

    def __init__(*args: object, **kwds: object) -> None:   # property_init_impl
        self = _slot_receiver(args, property, "__init__")
        fget, fset, fdel, doc = _unpack_keywords("property", ("fget", "fset", "fdel", "doc"), 0, 0, 4, 0, args[1:], kwds, None)
        _put_fget(self, fget)
        _put_fset(self, fset)
        _put_fdel(self, fdel)
        _put_doc(self, None)
        _put_name(self, _NULL)
        _put_getter_doc(self, False)
        if doc is None and fget is not None:     # no docstring given: the getter's, if it has one
            doc = getattr(fget, "__doc__", None)
            if doc is not None:
                _put_getter_doc(self, True)
        if type(self) is property:
            _put_doc(self, doc)
            return
        try:                                     # a subclass: its own __doc__ would hide the member, so the instance's dict or slot has it
            self.__doc__ = doc
        except AttributeError:
            if _getter_doc_of(self):
                raise

    def __get__(self, obj: object = _NULL, owner: object = None) -> object:   # property_descr_get, under wrap_descr_get
        if obj is None:
            if owner is None:
                raise TypeError("__get__(None, None) is invalid")
            return self
        if obj is _NULL:
            raise TypeError("__get__ expected at least 1 argument, got 0")
        fget = _fget_of(self)
        if fget is None:
            raise _property_lacks(self, obj, "getter")
        return fget(obj)  # type: ignore[operator]  # a callable, as the caller gave it

    def __set__(self, obj: object, value: object) -> None:   # property_descr_set
        fset = _fset_of(self)
        if fset is None:
            raise _property_lacks(self, obj, "setter")
        fset(obj, value)  # type: ignore[operator]

    def __delete__(self, obj: object) -> None:
        fdel = _fdel_of(self)
        if fdel is None:
            raise _property_lacks(self, obj, "deleter")
        fdel(obj)  # type: ignore[operator]

    def __set_name__(*args: object, **kwds: object) -> None:   # property_set_name: the last class to hold it names it
        """Method to set name of a property."""
        if not args:
            raise TypeError("unbound method property.__set_name__() needs an argument")
        if not issubclass(type(args[0]), property):
            raise TypeError("descriptor '__set_name__' for 'property' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
        if kwds:
            raise TypeError("property.__set_name__() takes no keyword arguments")
        if len(args) != 3:
            raise TypeError("__set_name__() takes 2 positional arguments but " + str(len(args) - 1) + " were given")
        _put_name(args[0], args[2])

    def getter(*args: object, **kwds: object) -> object:
        """Descriptor to obtain a copy of the property with a different getter."""
        value = _method_one(args, kwds, property, "getter")
        return _property_copy(args[0], value, None, None)

    def setter(*args: object, **kwds: object) -> object:
        """Descriptor to obtain a copy of the property with a different setter."""
        value = _method_one(args, kwds, property, "setter")
        return _property_copy(args[0], None, value, None)

    def deleter(*args: object, **kwds: object) -> object:
        """Descriptor to obtain a copy of the property with a different deleter."""
        value = _method_one(args, kwds, property, "deleter")
        return _property_copy(args[0], None, None, value)


_fget_of, _put_fget = _field(property, "_prop_get")
_fset_of, _put_fset = _field(property, "_prop_set")
_fdel_of, _put_fdel = _field(property, "_prop_del")
_doc_of, _put_doc = _field(property, "_prop_doc")
_name_of, _put_name = _field(property, "_prop_name")
_getter_doc_of, _put_getter_doc = _field(property, "_getter_doc")


def _property_new(*args: object, **kwds: object) -> object:   # PyType_GenericNew: the arguments are __init__'s; the fields hold nothing
    self = _bella_new_instance(_new_receiver(args, property))
    _put_fget(self, None)
    _put_fset(self, None)
    _put_fdel(self, None)
    _put_doc(self, None)
    _put_name(self, _NULL)
    _put_getter_doc(self, False)
    return self


def _one_callable(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # sm_new, cm_new: no keywords, one argument
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(name + " expected 1 argument, got " + str(len(args)))
    return args[0]


def _wraps(wrapper: object, wrapped: object) -> None:   # functools_wraps: through the wrapper's own __setattr__
    for attr in ("__module__", "__name__", "__qualname__", "__doc__"):
        try:
            value = getattr(wrapped, attr)
        except AttributeError:
            continue
        setattr(wrapper, attr, value)


def _wrapped_attribute(wrapped: object, obj: object, name: str) -> object:   # descriptor_get_wrapped_attribute
    d: dict[str, object] = obj.__dict__
    if name in d:
        return d[name]
    value = getattr(wrapped, name)
    d[name] = value
    return value


def _set_wrapped_attribute(obj: object, name: str, value: object, type_name: str) -> None:   # descriptor_set_wrapped_attribute
    d: dict[str, object] = obj.__dict__
    if value is _NULL:
        if name not in d:
            raise AttributeError("'" + type_name + "' object has no attribute '" + name + "'")
        del d[name]
        return
    d[name] = value


class staticmethod:
    __slots__ = ("__dict__", "_sm_callable")

    __func__ = _GetSet(lambda self: _sm_callable_of(self), member=True)
    __wrapped__ = _GetSet(lambda self: _sm_callable_of(self), member=True)
    __isabstractmethod__ = _GetSet(lambda self: _is_abstract(_sm_callable_of(self)))
    __annotations__ = _GetSet(lambda self: _wrapped_attribute(_sm_callable_of(self), self, "__annotations__"),  # type: ignore[assignment]
                              lambda self, value: _set_wrapped_attribute(self, "__annotations__", value, "staticmethod"),
                              lambda self: _set_wrapped_attribute(self, "__annotations__", _NULL, "staticmethod"))
    __annotate__ = _GetSet(lambda self: _wrapped_attribute(_sm_callable_of(self), self, "__annotate__"),
                           lambda self, value: _set_wrapped_attribute(self, "__annotate__", value, "staticmethod"),
                           lambda self: _set_wrapped_attribute(self, "__annotate__", _NULL, "staticmethod"))

    def __init__(*args: object, **kwds: object) -> None:   # sm_init
        self = _slot_receiver(args, staticmethod, "__init__")
        _sm_set(self, _one_callable("staticmethod", args[1:], kwds))

    def __get__(self, obj: object = _NULL, owner: object = None) -> object:   # sm_descr_get, under wrap_descr_get
        if owner is None:
            if obj is None:
                raise TypeError("__get__(None, None) is invalid")
            if obj is _NULL:
                raise TypeError("__get__ expected at least 1 argument, got 0")
        return _sm_callable_of(self)

    def __call__(self, *args: object, **kwargs: object) -> object:   # sm_call
        return _sm_callable_of(self)(*args, **kwargs)  # type: ignore[operator]

    def __repr__(*args: object, **kwds: object) -> str:   # sm_repr
        self = _slot_receiver(args, staticmethod, "__repr__")
        if kwds:
            raise TypeError("wrapper __repr__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("expected 0 arguments, got " + str(len(args) - 1))
        return "<staticmethod(" + repr(_sm_callable_of(self)) + ")>"


_sm_callable_of, _put_sm_callable = _field(staticmethod, "_sm_callable")


def _sm_set(self: object, func: object) -> None:   # sm_set_callable: __init__ after __new__ gives the same one
    if _sm_callable_of(self) is func:
        return
    _put_sm_callable(self, func)
    _wraps(self, func)


def _sm_new(*args: object, **kwds: object) -> object:   # sm_new
    cls = _new_receiver(args, staticmethod)
    func = _one_callable("staticmethod", args[1:], kwds)
    self = _bella_new_instance(cls)
    _put_sm_callable(self, _NULL)
    _sm_set(self, func)
    return self


def _a_function() -> None:
    pass


_MethodType = type(_a_function.__get__(0))      # types.MethodType: any callable bound to an object


class classmethod:
    __slots__ = ("__dict__", "_cm_callable")

    __func__ = _GetSet(lambda self: _cm_callable_of(self), member=True)
    __wrapped__ = _GetSet(lambda self: _cm_callable_of(self), member=True)
    __isabstractmethod__ = _GetSet(lambda self: _is_abstract(_cm_callable_of(self)))
    __annotations__ = _GetSet(lambda self: _wrapped_attribute(_cm_callable_of(self), self, "__annotations__"),  # type: ignore[assignment]
                              lambda self, value: _set_wrapped_attribute(self, "__annotations__", value, "classmethod"),
                              lambda self: _set_wrapped_attribute(self, "__annotations__", _NULL, "classmethod"))
    __annotate__ = _GetSet(lambda self: _wrapped_attribute(_cm_callable_of(self), self, "__annotate__"),
                           lambda self, value: _set_wrapped_attribute(self, "__annotate__", value, "classmethod"),
                           lambda self: _set_wrapped_attribute(self, "__annotate__", _NULL, "classmethod"))

    def __init__(*args: object, **kwds: object) -> None:   # cm_init
        self = _slot_receiver(args, classmethod, "__init__")
        _cm_set(self, _one_callable("classmethod", args[1:], kwds))

    def __get__(self, obj: object = _NULL, owner: object = None) -> object:
        # cm_descr_get since 3.13: a method of the callable itself, which need not be a descriptor (review 2026-11-03, A9-19)
        if owner is None:
            if obj is None:
                raise TypeError("__get__(None, None) is invalid")
            if obj is _NULL:
                raise TypeError("__get__ expected at least 1 argument, got 0")
            owner = type(obj)
        return _MethodType(_cm_callable_of(self), owner)

    def __repr__(*args: object, **kwds: object) -> str:   # cm_repr
        self = _slot_receiver(args, classmethod, "__repr__")
        if kwds:
            raise TypeError("wrapper __repr__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("expected 0 arguments, got " + str(len(args) - 1))
        return "<classmethod(" + repr(_cm_callable_of(self)) + ")>"


_cm_callable_of, _put_cm_callable = _field(classmethod, "_cm_callable")


def _cm_set(self: object, func: object) -> None:   # cm_set_callable
    if _cm_callable_of(self) is func:
        return
    _put_cm_callable(self, func)
    _wraps(self, func)


def _cm_new(*args: object, **kwds: object) -> object:   # cm_new
    cls = _new_receiver(args, classmethod)
    func = _one_callable("classmethod", args[1:], kwds)
    self = _bella_new_instance(cls)
    _put_cm_callable(self, _NULL)
    _cm_set(self, func)
    return self


property.__new__ = _sm_new(staticmethod, _property_new)  # type: ignore[assignment, method-assign]
staticmethod.__new__ = _sm_new(staticmethod, _sm_new)  # type: ignore[assignment, method-assign]
classmethod.__new__ = _sm_new(staticmethod, _cm_new)  # type: ignore[assignment, method-assign]


# ---- the containers' repr, installed as list.__repr__, tuple.__repr__ and dict.__repr__ ----

_running: list[object] = []      # the containers whose repr is being made (Py_ReprEnter)


def _enter(obj: object) -> bool:
    for x in _running:
        if x is obj:
            return False
    _running.append(obj)
    return True


def _leave(obj: object) -> None:
    i = len(_running) - 1
    while i >= 0:
        if _running[i] is obj:
            del _running[i]
            return
        i -= 1


def _receiver(self: object, cls: type, name: str) -> None:
    """A slot wrapper's check (wrapperdescr_call): list.__repr__(5) is a TypeError, as for the
    C++ types' methods (review 2026-11-03, A9-2)."""
    if not isinstance(self, cls):
        raise TypeError("descriptor '" + name + "' requires a '" + cls.__name__ + "' object but received a '" +
                        type(self).__name__ + "'")


def _list_repr(self: list[object]) -> str:
    _receiver(self, list, "__repr__")
    if not list.__len__(self):                   # list_repr: the items, whatever a subclass says
        return "[]"
    if not _enter(self):
        return "[...]"
    try:
        return "[" + ", ".join([repr(x) for x in list.__iter__(self)]) + "]"
    finally:
        _leave(self)


def _tuple_repr(self: tuple[object, ...]) -> str:
    _receiver(self, tuple, "__repr__")
    items = list(tuple.__iter__(self))           # the items, whatever a subclass says
    if not items:
        return "()"
    if not _enter(self):
        return "(...)"
    try:
        if len(items) == 1:
            return "(" + repr(items[0]) + ",)"
        return "(" + ", ".join([repr(x) for x in items]) + ")"
    finally:
        _leave(self)


try:
    _dict_next                                   # noqa: B018  # PyDict_Next, given to this module by the compiled runtime
except NameError:
    def _dict_next(d: dict[object, object], i: int) -> tuple[int, object, object] | None:
        """Run by CPython (runtime/tests/test_prelude.py): the entries as they are at each step.
        CPython walks its entry array, deleted slots included; this walk sees no deleted slots."""
        items = list(d.items())
        return (i + 1, *items[i]) if i < len(items) else None


def _dict_repr(self: dict[object, object]) -> str:
    """dict_repr: the entries as PyDict_Next walks them, so an entry a key's or value's repr adds
    is shown too, with no check of the size (review 2026-11-03, A9-17)."""
    _receiver(self, dict, "__repr__")
    return _anydict_repr(self)


def _frozendict_repr(self: frozendict[object, object]) -> str:
    """frozendict_repr: the type's name around what a dict shows, or nothing when it is empty."""
    _receiver(self, frozendict, "__repr__")
    if _dict_next(self, 0) is None:
        return type(self).__name__ + "()"
    return type(self).__name__ + "(" + _anydict_repr(self) + ")"


def _anydict_repr(self: dict[object, object] | frozendict[object, object]) -> str:
    if _dict_next(self, 0) is None:              # ma_used == 0: never a subclass's __len__ or __bool__
        return "{}"
    if not _enter(self):
        return "{...}"
    try:
        parts: list[str] = []
        i = 0
        while True:
            entry = _dict_next(self, i)
            if entry is None:
                break
            i, k, v = entry
            parts.append(repr(k) + ": " + repr(v))
        return "{" + ", ".join(parts) + "}"
    finally:
        _leave(self)


def _set_repr(self: set[object]) -> str:
    _receiver(self, set, "__repr__")
    return _set_like_repr(self)


def _frozenset_repr(self: frozenset[object]) -> str:
    _receiver(self, frozenset, "__repr__")
    return _set_like_repr(self)


def _set_like_repr(self: set[object] | frozenset[object]) -> str:
    """set_repr: set() when empty; the type's name around the braces for a subclass and frozenset."""
    name = type(self).__name__
    if (set.__len__ if isinstance(self, set) else frozenset.__len__)(self) == 0:   # so->used: not what a subclass's __len__ says
        return name + "()"
    if not _enter(self):
        return name + "(...)"
    try:
        inner = "{" + ", ".join([repr(x) for x in self]) + "}"
        return inner if type(self) is set else name + "(" + inner + ")"
    finally:
        _leave(self)


_dict_keys = type({}.keys())
_dict_values = type({}.values())
_dict_items = type({}.items())


def _keys_repr(self: object) -> str:
    _receiver(self, _dict_keys, "__repr__")
    return _view_repr(self)


def _values_repr(self: object) -> str:
    _receiver(self, _dict_values, "__repr__")
    return _view_repr(self)


def _items_repr(self: object) -> str:
    _receiver(self, _dict_items, "__repr__")
    return _view_repr(self)


def _view_repr(self: object) -> str:
    """dictview_repr: the type's name around the repr of a list of the view."""
    if not _enter(self):
        return "..."
    try:
        return type(self).__name__ + "(" + repr(list(self)) + ")"  # type: ignore[call-overload]  # a view is iterable
    finally:
        _leave(self)


__type_methods__: dict[object, dict[str, object]] = {
    "list": {"__repr__": _list_repr}, "tuple": {"__repr__": _tuple_repr}, "dict": {"__repr__": _dict_repr},
    "frozendict": {"__repr__": _frozendict_repr},
    "set": {"__repr__": _set_repr}, "frozenset": {"__repr__": _frozenset_repr},
    _dict_keys: {"__repr__": _keys_repr}, _dict_values: {"__repr__": _values_repr}, _dict_items: {"__repr__": _items_repr}}
