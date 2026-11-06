# clause: C-7-28
# spec: section 7
# status: P1
# source: dialect specification section 7, Python/sysmodule.c, Objects/floatobject.c, Objects/longobject.c
"""The sys surface the specification names, and what the library reads of it when it imports: the named tuples with everything they say of themselves,
the version, the limits, the recursion limit and the digit limit. What depends on where and how CPython was built prints only its type."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001
import sys


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


print(sys.version_info, sys.version_info[:2], sys.version_info >= (3, 15), sys.version_info < (3, 16), sys.version_info.major, sys.version_info.minor, sys.version_info.micro, sys.version_info.releaselevel, sys.version_info.serial, tuple(sys.version_info), len(sys.version_info), sys.version_info == (3, 15, 2, "final", 0), hash(sys.version_info) == hash((3, 15, 2, "final", 0)))
print(sys.hexversion, hex(sys.hexversion), sys.api_version, sys.byteorder, sys.maxsize, sys.maxunicode, sys.float_repr_style, sys.platlibdir, sys.abiflags, sys.dont_write_bytecode, sys.pycache_prefix, sys.warnoptions, sys._xoptions, sys.platform, sys.getdefaultencoding(), sys.getfilesystemencoding(), sys.getfilesystemencodeerrors())
print(type(sys.version).__name__, sys.version.split()[0], type(sys.copyright).__name__, sys.copyright.split("\n")[0], type(sys.executable).__name__, type(sys.prefix).__name__, type(sys.base_prefix).__name__, type(sys.exec_prefix).__name__, type(sys.base_exec_prefix).__name__, type(sys.path).__name__, type(sys.argv).__name__, type(sys.orig_argv).__name__, type(sys.stdlib_module_names).__name__, "os" in sys.stdlib_module_names, "nothing" in sys.stdlib_module_names, type(sys.modules).__name__, type(sys.builtin_module_names).__name__)
for value in (sys.version_info, sys.flags, sys.float_info, sys.int_info, sys.hash_info, sys.thread_info):
    cls = type(value)
    print(repr(cls), cls.__name__, cls.__qualname__, cls.__module__, [c.__name__ for c in cls.__mro__], repr(cls.__doc__), cls.n_fields, cls.n_sequence_fields, cls.n_unnamed_fields, cls.__match_args__, list(vars(cls)), hex(cls.__flags__))
    print(len(value), failed(lambda: type("X", (cls,), {})), failed(lambda: cls()), failed(lambda: cls(())), failed(lambda: cls(range(cls.n_sequence_fields))), failed(lambda: setattr(value, cls.__match_args__[0], 1)), failed(lambda: setattr(value, "x", 1)), failed(lambda: value.x), failed(lambda: vars(value)), type(vars(cls)[cls.__match_args__[0]]).__name__, failed(lambda: value.__replace__(nothing=1)), type(value.__replace__()).__name__, value.__replace__() == value, value.__reduce__()[0] is cls, value.__reduce__()[1][0] == tuple(value), type(value.__reduce__()[1][1]).__name__, isinstance(value, tuple), value == tuple(value), repr(value).startswith("sys." + cls.__name__ + "("))  # type: ignore[call-arg,no-untyped-call,union-attr]
print(sys.float_info, sys.float_info.max, sys.float_info.min, sys.float_info.epsilon, sys.float_info.dig, sys.float_info.mant_dig, sys.float_info.radix, sys.float_info.rounds, sys.float_info.max_exp, sys.float_info.min_exp, sys.float_info.max_10_exp, sys.float_info.min_10_exp, 1.0 + sys.float_info.epsilon > 1.0)
print(sys.int_info, sys.int_info.bits_per_digit, sys.int_info.sizeof_digit, sys.int_info.default_max_str_digits, sys.int_info.str_digits_check_threshold)
print(sys.hash_info, sys.hash_info.width, sys.hash_info.modulus, sys.hash_info.inf, sys.hash_info.nan, sys.hash_info.imag, sys.hash_info.algorithm, sys.hash_info.hash_bits, sys.hash_info.seed_bits, sys.hash_info.cutoff, hash(float("inf")) == sys.hash_info.inf, hash(float("-inf")) == -sys.hash_info.inf, hash(1j) == sys.hash_info.imag, hash(sys.hash_info.modulus) == 0)
print(sys.thread_info.name, sys.thread_info.lock, type(sys.thread_info.version).__name__, len(sys.thread_info))
flags = sys.flags
print(flags.debug, flags.inspect, flags.interactive, flags.optimize, flags.dont_write_bytecode, flags.no_user_site, flags.no_site, flags.ignore_environment, flags.verbose, flags.bytes_warning, flags.quiet, flags.isolated, flags.dev_mode, flags.utf8_mode, flags.warn_default_encoding, flags.safe_path, flags.int_max_str_digits, type(flags.hash_randomization).__name__, flags.gil if hasattr(flags, "gil") else "", flags.thread_inherit_context, flags.context_aware_warnings, flags.lazy_imports, len(flags), tuple(flags)[:11], repr(flags).startswith("sys.flags(debug=0, inspect=0,"), flags.__reduce__()[1][1]["thread_inherit_context"] == flags.thread_inherit_context, sorted(flags.__reduce__()[1][1]))  # type: ignore[attr-defined,index]
print(sys.getrecursionlimit(), failed(lambda: sys.getrecursionlimit(1)), failed(lambda: sys.setrecursionlimit()), failed(lambda: sys.setrecursionlimit("a")), failed(lambda: sys.setrecursionlimit(0)), failed(lambda: sys.setrecursionlimit(-1)), failed(lambda: sys.setrecursionlimit(2**70)), sys.setrecursionlimit(500), sys.getrecursionlimit(), sys.setrecursionlimit(1000), sys.getrecursionlimit())  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]


def down(n):  # type: ignore[no-untyped-def]
    return down(n + 1)  # type: ignore[no-untyped-call]


print(failed(lambda: down(0)))  # type: ignore[no-untyped-call]
print(sys.get_int_max_str_digits(), failed(lambda: sys.get_int_max_str_digits(1)), failed(lambda: sys.set_int_max_str_digits()), failed(lambda: sys.set_int_max_str_digits("a")), failed(lambda: sys.set_int_max_str_digits(1)), failed(lambda: sys.set_int_max_str_digits(639)), failed(lambda: sys.set_int_max_str_digits(-1)), sys.set_int_max_str_digits(640), sys.get_int_max_str_digits(), failed(lambda: str(10**640)), failed(lambda: int("1" * 641)), len(str(10**639)), sys.set_int_max_str_digits(0), sys.get_int_max_str_digits(), len(str(10**5000)), sys.set_int_max_str_digits(4300), sys.get_int_max_str_digits())  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]
print(type(sys.getsizeof(1)).__name__, type(sys.getsizeof("")).__name__, sys.getsizeof(1, 2) > 0, failed(lambda: sys.getsizeof()), sys.getsizeof(object()) > 0, sys.getsizeof([]) > 0, failed(lambda: sys.getsizeof(1, 2, 3)))  # type: ignore[call-arg,no-untyped-call]
print(sys.is_finalizing(), failed(lambda: sys.is_finalizing(1)), sys.getswitchinterval(), failed(lambda: sys.getswitchinterval(1)), failed(lambda: sys.setswitchinterval(0)), failed(lambda: sys.setswitchinterval(-1)), failed(lambda: sys.setswitchinterval("a")), sys.setswitchinterval(0.01), sys.getswitchinterval(), sys.setswitchinterval(0.005))  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]
print(failed(lambda: sys.getdefaultencoding(1)), failed(lambda: setattr(sys, "new_name", 1)), sys.new_name if hasattr(sys, "new_name") else "", failed(lambda: sys.nothing), hasattr(sys, "nothing"), failed(lambda: delattr(sys, "new_name")), hasattr(sys, "new_name"))  # type: ignore[attr-defined,call-arg,no-untyped-call]
impl = sys.implementation
print(type(impl).__name__, impl.version, impl.version == sys.version_info, impl.hexversion == sys.hexversion, type(impl.name).__name__, sorted(k for k in vars(impl)), type(impl._multiarch).__name__)
