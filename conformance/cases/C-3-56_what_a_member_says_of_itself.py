# clause: C-3-56
# spec: section 3
# status: P1
# source: Objects/descrobject.c (member_get_doc, getset_get_doc), Objects/structseq.c (the fields' docs), and the member and getset tables of the types named below
"""What a member says of itself: the __doc__ of a member descriptor and of a getset descriptor is the text its type's C
definition gives it, or None; a struct sequence's fields have theirs; a program's own __slots__ member has none, and the
__dict__ and __weakref__ a class gets have the two CPython gives every class."""
# ruff: noqa: E501
import functools
import grp
import os
import pwd
import re
import sys
import time
import types


class Slots:
    __slots__ = ("a", "b")


class Plain:
    pass


def docs(owner: type, *names: str) -> list[tuple[str, str | None]]:
    """Each name's descriptor, as the type's own namespace holds it, and its doc."""
    return [(type(vars(owner)[name]).__name__[0] + ":" + name, vars(owner)[name].__doc__) for name in names]


def main() -> None:
    # the fields of struct sequences
    print("os.stat_result:", docs(os.stat_result, "st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid", "st_size", "st_atime", "st_mtime", "st_ctime", "st_atime_ns", "st_blksize", "st_blocks", "st_rdev"))
    print("os, the others:", docs(os.statvfs_result, "f_bsize", "f_namemax", "f_fsid"), docs(os.terminal_size, "columns", "lines"), docs(os.times_result, "user", "elapsed"), docs(os.uname_result, "sysname", "machine"),
          docs(os.waitid_result, "si_pid", "si_code"), docs(os.sched_param, "sched_priority"))
    print("sys:", docs(type(sys.version_info), "major", "releaselevel"), docs(type(sys.flags), "debug", "utf8_mode"), docs(type(sys.float_info), "max", "epsilon"), docs(type(sys.int_info), "bits_per_digit"),
          docs(type(sys.hash_info), "width", "algorithm"), docs(type(sys.thread_info), "name", "lock"))
    print("time, pwd, grp:", docs(time.struct_time, "tm_year", "tm_wday", "tm_isdst", "tm_zone", "tm_gmtoff"), docs(pwd.struct_passwd, "pw_name", "pw_dir"), docs(grp.struct_group, "gr_name", "gr_mem"))

    # numbers and the small built-in types
    print("numbers:", docs(int, "real", "imag", "numerator", "denominator"), docs(float, "real", "imag"), docs(complex, "real", "imag"), docs(range, "start", "stop", "step"), docs(slice, "start", "stop", "step"))
    print("descriptors:", docs(property, "fget", "fset", "fdel", "__isabstractmethod__", "__name__"), docs(staticmethod, "__func__", "__wrapped__", "__isabstractmethod__"), docs(classmethod, "__func__", "__wrapped__"),
          docs(super, "__thisclass__", "__self__", "__self_class__"))
    print("functions:", docs(types.FunctionType, "__code__", "__defaults__", "__kwdefaults__", "__globals__", "__closure__", "__name__", "__qualname__", "__dict__", "__annotations__", "__builtins__", "__type_params__"),
          docs(types.MethodType, "__func__", "__self__"), docs(types.BuiltinFunctionType, "__self__", "__name__", "__qualname__", "__module__"), docs(types.CellType, "cell_contents"),
          docs(functools.partial, "func", "args", "keywords"))
    print("generators and code:", docs(types.GeneratorType, "gi_running", "gi_yieldfrom", "gi_suspended", "__name__", "__qualname__"), docs(types.CodeType, "co_argcount", "co_name", "co_filename", "co_firstlineno", "co_flags"))
    print("type and module:", docs(type, "__name__", "__qualname__", "__module__", "__mro__", "__bases__", "__base__", "__dict__", "__doc__", "__abstractmethods__", "__flags__", "__annotations__"),
          docs(types.ModuleType, "__dict__"), docs(types.SimpleNamespace, "__dict__"))

    # exceptions
    print("exceptions:", docs(BaseException, "args", "__traceback__", "__cause__", "__context__", "__suppress_context__", "__dict__"), docs(OSError, "errno", "strerror", "filename", "filename2", "characters_written"),
          docs(SystemExit, "code"), docs(StopIteration, "value"), docs(ImportError, "msg", "name", "path", "name_from"), docs(AttributeError, "name", "obj"), docs(NameError, "name"),
          docs(SyntaxError, "msg", "filename", "lineno", "offset", "text", "end_lineno", "end_offset", "print_file_and_line"), docs(UnicodeEncodeError, "encoding", "object", "start", "end", "reason"),
          docs(BaseExceptionGroup, "message", "exceptions"))

    # the library's C types
    print("re:", docs(re.Pattern, "pattern", "flags", "groups", "groupindex"), docs(re.Match, "string", "re", "pos", "endpos", "lastindex", "lastgroup", "regs"))
    print("aliases:", docs(types.GenericAlias, "__origin__", "__args__", "__parameters__", "__unpacked__", "__typing_unpacked_tuple_args__"), docs(types.UnionType, "__args__", "__parameters__", "__name__", "__qualname__", "__origin__"),
          docs(type({}.keys()), "mapping"), docs(types.MappingProxyType))

    # a program's classes: a slot has no doc; the two getsets every class with a dict gets have theirs
    print("a program's classes:", docs(Slots, "a", "b"), docs(Plain, "__dict__", "__weakref__"), [type(Slots.a).__name__, type(vars(Plain)["__dict__"]).__name__])  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
