"""The names CPython has, recorded for the compiled runtime's refusals.

A compiled program may name something CPython provides that Bella's runtime does not have yet: a
builtin (`sorted`), an attribute of `sys` (`sys.maxsize`) or a method of a built-in type
(`str.startswith`, `object.__sizeof__`). CPython would find it; answering NameError or
AttributeError would be a wrong answer, so the runtime refuses instead (`bella: not implemented`,
exit 70). This tool records, from the pinned CPython, which names exist:

* `builtins:<name>`: the builtins module, as a script sees it;
* `globals:<name>`: the globals CPython gives a script before it runs (`__file__`, `__builtins__`);
* `sys:<name>`: the sys module, as a script sees it;
* `<module>:<name>`: each attribute of the built-in modules the manifest lists as core or mapped,
  which the runtime provides one by one: a name it lacks yet is refused, never an AttributeError
  or an ImportError a program would take as the module's answer;
* `stdlib:<name>`: `sys.stdlib_module_names`, the standard library's top-level modules: the
  runtime refuses importing one it does not have compiled yet (rather than answer
  ModuleNotFoundError), and words a module's errors as CPython does when the program's own module
  shadows one (`_PyModule_IsPossiblyShadowing`);
* `binop:<type><op><type>`, `iop:...`, `cmp:...`: the operators CPython handles between the
  built-in types the runtime has (and `instance`, a plain class's object, for any instance whose
  own methods declined): handled means not rejected as an unsupported operand (or, for an
  ordering, as not supported between the instances); `==` and `!=` count when a type's own
  method decides, not the identity fallback. The runtime refuses a handled operation it does
  not implement, rather than raise the TypeError CPython would not.
* `flags:<name>`, `heapflags:<name>`: a type's tp_flags in the kind column, and those of a class that says nothing on it as its base;
* `itemsize:<name>`, `state:<name>`: the built-in types with items in the object, and those with C fields past what object has, by
  which object.__getstate__ and __reduce_ex__ refuse what they could not bring back;
* `builtin_module:<name>`: `sys.builtin_module_names`, which the runtime gives as the pin's;
* `final:<tp_name>`: the built-in types a class cannot derive from (no Py_TPFLAGS_BASETYPE);
* `<type>:<name>`: each built-in type's own attributes (its `__dict__`), keyed by `__name__`, with
  the kind of object CPython keeps there (`wrapper_descriptor`, `method_descriptor`, ...), which
  says how the attribute presents itself; the runtime walks a class's MRO, so a name is recorded
  once, on the type that defines it. For `type` only the names a class can read
  (`__abstractmethods__` raises for most).

The table is `runtime/src/cpython_names.inc`, committed like the conformance expectations:
`python3 tools/cpython_names.py` writes it, `--check` fails when the pinned CPython disagrees
(`make verify`). `--allow-unpinned` runs on another Python, for development only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "runtime" / "src" / "cpython_names.inc"

# Run as a script by the interpreter being recorded: the names a compiled program could reach.
PROBE = r'''
GLOBALS = sorted(globals())                     # before the probe binds anything
import abc, builtins, json, sys, types

FINAL = set()
WEAKREF = set()
FLAGS = {}
HEAPFLAGS = {}
OFFSETS = {}                                     # tp_dictoffset and tp_weaklistoffset, as "dictoffset,weakrefoffset"
ITEMSIZE = set()
STATE = set()
SHORTNAME = set()

def tp_name(t):
    """PyTypeObject.tp_name, what %T and "'%s' object has no attribute" print: a static type's or a spec's is "module.Name"; a type
    made by type() in C (ast's nodes) is the bare name. The field follows PyVarObject's three words in the pinned (non-free-threaded)
    build."""
    import ctypes
    return ctypes.c_char_p.from_address(id(t) + 3 * ctypes.sizeof(ctypes.c_ssize_t)).value.decode()

def type_names():
    found = {}
    def add(t):
        if isinstance(t, type):
            key = tp_name(t)                     # the table knows a type by its tp_name, which is the runtime's name for it (ast.Match and re.Match differ)
            found.setdefault(key, {}).update({n: type(v).__name__ for n, v in vars(t).items()})
            if t.__module__ != "builtins" and "." not in key:
                SHORTNAME.add(t.__module__ + "." + t.__qualname__)
            if t.__weakrefoffset__:              # _PyType_SUPPORTS_WEAKREFS
                WEAKREF.add(key)
            FLAGS[key] = str(t.__flags__)
            OFFSETS[key] = f"{t.__dictoffset__},{t.__weakrefoffset__}"
            if t.__flags__ & (1 << 10) and key not in HEAPFLAGS:   # what a class that says nothing has, on this base
                try:
                    HEAPFLAGS[key] = str(type("Z", (t,), {}).__flags__)
                except Exception:
                    pass
            if t.__itemsize__:                   # object_getstate_default's tests, for a type written in C
                ITEMSIZE.add(key)
            elif not t.__flags__ & (1 << 9) and t.__basicsize__ > object.__basicsize__ + (8 if t.__dictoffset__ and not t.__flags__ & (1 << 4) else 0) + (8 if t.__weakrefoffset__ > 0 else 0):
                STATE.add(key)
            if not t.__flags__ & (1 << 10):      # Py_TPFLAGS_BASETYPE
                FINAL.add(key)
    class Probe:
        pass
    class Seq:
        def __getitem__(self, i):
            raise IndexError
    def outer():
        x = 1
        def inner():
            return x
        return inner
    try:
        raise ValueError
    except ValueError as e:
        tb = e.__traceback__
    def gen():
        yield 1
    samples = [iter(int, 1), iter([]), iter(()), iter(""), iter("é"), iter({}), iter({}.values()), iter({}.items()),
               iter(set()), iter(range(1)), iter(range(2**64)), iter(Seq()), reversed([]), {}.keys(), {}.values(), {}.items(),
               iter(b""), iter(bytearray()), reversed({}), reversed({}.values()), reversed({}.items()),
               outer, outer().__closure__[0], outer.__code__, type.__dict__, [].append, list.append,
               dict.__dict__["fromkeys"], type.__dict__["__name__"], object.__init__, object().__init__,
               sys.stdout, NotImplemented, Ellipsis, None, tb, tb.tb_frame, gen(), slice(1), Probe().__init__, iter(list[int]),
               t"", t"{0}".interpolations[0], iter(t"")]
    import grp, itertools, posix, pwd, re, struct, time, typing, zlib, _ast, _blake2, _contextvars, _csv, _hmac, _random, _tokenize, _md5, _sha1, _sha2, _sha3, _struct, _codecs, _collections, _functools, _io, _json, _locale, _operator, _sre, _stat, _string, _thread, _typing, _weakref
    for v in [type(typing.NoDefault), type(typing.TypeVar("T", bound=int).evaluate_bound), *vars(_typing).values(), _json.make_scanner, _json.make_encoder, type(sys.version_info), type(sys.flags), type(sys.float_info), type(sys.int_info), type(sys.hash_info), type(sys.thread_info), re.Pattern, re.Match, type(re.compile('').scanner('')), type(_sre.template('', [''])), *vars(_sre).values(), *vars(_io).values(), *vars(_ast).values(), pwd.struct_passwd, grp.struct_group, *vars(posix).values(), *vars(builtins).values(), *vars(types).values(), *vars(itertools).values(), *vars(_operator).values(), *vars(_collections).values(), *vars(_functools).values(), type(_functools.cmp_to_key(None)), _struct.Struct, type(struct.iter_unpack('b', b'a')), time.struct_time, _md5.MD5Type, _sha1.SHA1Type, *vars(_sha2).values(), *vars(_sha3).values(), *vars(_blake2).values(), _hmac.HMAC, _csv.Dialect, _csv.Reader, _csv.Writer, _csv.Error, type(zlib.compressobj()), type(zlib.decompressobj()), zlib._ZlibDecompressor, zlib.error, _contextvars.Context, _contextvars.ContextVar, _contextvars.Token, type(_contextvars.Token.MISSING), type(_contextvars.copy_context().keys()), type(_contextvars.copy_context().values()), type(_contextvars.copy_context().items()), _random.Random, _tokenize.TokenizerIter, *vars(_thread).values(), *vars(_weakref).values()]:
        add(v)
    for s in samples:
        add(type(s))
    if not type(abc.ABC._abc_impl).__flags__ & (1 << 10):
        FINAL.add("_abc._abc_data")
    # type's attributes as a class reads them: a getset that raises for a plain class is left out
    found["type"] = {n: k for n, k in found["type"].items() if hasattr(Probe, n)}
    return found

def operators():
    import copy
    import operator as op
    class Instance:
        pass
    reps = {"int": lambda: 3, "bool": lambda: True, "str": lambda: "a%s", "bytes": lambda: b"a%s", "bytearray": lambda: bytearray(b"a%s"),
            "tuple": lambda: (1,), "list": lambda: [1],
            "dict": lambda: {1: 2}, "set": lambda: {1}, "frozenset": lambda: frozenset({1}), "NoneType": lambda: None,
            "range": lambda: range(2), "slice": lambda: slice(1), "float": lambda: 1.5, "dict_keys": lambda: {1: 2}.keys(),
            "dict_values": lambda: {1: 2}.values(), "dict_items": lambda: {1: 2}.items(), "type": lambda: int,
            "function": lambda: (lambda: 0), "builtin_function_or_method": lambda: len, "ellipsis": lambda: ...,
            "instance": Instance}
    binops = {"+": op.add, "-": op.sub, "*": op.mul, "/": op.truediv, "//": op.floordiv, "%": op.mod, "**": op.pow,
              "<<": op.lshift, ">>": op.rshift, "&": op.and_, "|": op.or_, "^": op.xor, "@": op.matmul}
    iops = {"+=": op.iadd, "-=": op.isub, "*=": op.imul, "/=": op.itruediv, "//=": op.ifloordiv, "%=": op.imod,
            "**=": op.ipow, "<<=": op.ilshift, ">>=": op.irshift, "&=": op.iand, "|=": op.ior, "^=": op.ixor, "@=": op.imatmul}
    orders = {"<": op.lt, "<=": op.le, ">": op.gt, ">=": op.ge}
    out = []
    for a, ma in reps.items():
        for b, mb in reps.items():
            if a == b == "instance":
                continue
            for scope, table in (("binop", binops), ("iop", iops)):
                for sym, f in table.items():
                    try:
                        f(ma(), mb())
                        out.append(f"{scope}:{a}{sym}{b}")
                    except TypeError as e:
                        if not str(e).startswith("unsupported operand type(s)"):
                            out.append(f"{scope}:{a}{sym}{b}")
                    except Exception:
                        out.append(f"{scope}:{a}{sym}{b}")
            for sym, f in orders.items():
                try:
                    f(ma(), mb())
                    out.append(f"cmp:{a}{sym}{b}")
                except TypeError as e:
                    if "not supported between instances of" not in str(e):
                        out.append(f"cmp:{a}{sym}{b}")
            x, y = ma(), mb()
            for sym, name in (("==", "__eq__"), ("!=", "__ne__")):
                own_x = getattr(type(x), name) is not getattr(object, name) and getattr(type(x), name)(x, y) is not NotImplemented
                own_y = getattr(type(y), name) is not getattr(object, name) and getattr(type(y), name)(y, x) is not NotImplemented
                if own_x or own_y:
                    out.append(f"cmp:{a}{sym}{b}")
    return sorted(out)

def native_modules(names):
    import importlib
    out = {}
    for name in names:
        try:
            out[name] = sorted(vars(importlib.import_module(name)))
        except ImportError:
            pass                 # a shim's name, or a module the build's platform lacks
    # importlib/__init__.py gives _frozen_importlib a __file__ when the package is imported (the probe has imported it); the
    # module start-up makes has none, and a program's own `import importlib` sets it as CPython's does
    if "_frozen_importlib" in out:
        out["_frozen_importlib"] = [n for n in out["_frozen_importlib"] if n != "__file__"]
    return out

def docs():
    """The docstrings of the built-in modules a program has from the start, and of the built-in types."""
    import binascii, errno, grp, itertools, math, math.integer, posix, pwd, re, struct, time, typing, zlib, _ast, _bisect, _blake2, _contextvars, _heapq, _opcode, _warnings, _tokenize, _imp, _random, _statistics, _csv, _hmac, _md5, _sha1, _sha2, _sha3, _struct, _codecs, _collections, _functools, _io, _json, _locale, _operator, _sre, _stat, _string, _thread, _typing, _weakref
    out = {"posix": posix.__doc__, "sys.copyright": sys.copyright, "sys": sys.__doc__, "builtins": builtins.__doc__, "itertools": itertools.__doc__, "_operator": _operator.__doc__, "_collections": _collections.__doc__, "errno": errno.__doc__, "_functools": _functools.__doc__, "_io": _io.__doc__, "pwd": pwd.__doc__, "grp": grp.__doc__, "_locale": _locale.__doc__, "_typing": _typing.__doc__, "_json": _json.__doc__, "zlib": zlib.__doc__, "binascii": binascii.__doc__, "_struct": _struct.__doc__, "time": time.__doc__, "math": math.__doc__, "math.integer": math.integer.__doc__, "_md5": _md5.__doc__, "_sha1": _sha1.__doc__, "_sha2": _sha2.__doc__, "_sha3": _sha3.__doc__, "_blake2": _blake2.__doc__, "_hmac": _hmac.__doc__, "_csv": _csv.__doc__, "_contextvars": _contextvars.__doc__, "_bisect": _bisect.__doc__, "_random": _random.__doc__, "_statistics": _statistics.__doc__, "_heapq": _heapq.__doc__, "_opcode": _opcode.__doc__, "_warnings": _warnings.__doc__, "_tokenize": _tokenize.__doc__, "_imp": _imp.__doc__, "_stat": _stat.__doc__, "_string": _string.__doc__, "_thread": _thread.__doc__, "_weakref": _weakref.__doc__}
    out = {k: (v if v is not None else "") for k, v in out.items()}   # a module without a docstring (_md5, _hmac): an empty row, None at run time
    for module in (builtins, sys, errno, itertools, posix, pwd, grp, zlib, binascii, _struct, time, math, math.integer, _md5, _sha1, _sha2, _sha3, _blake2, _hmac, _csv, _contextvars, _bisect, _random, _statistics, _heapq, _opcode, _warnings, _tokenize, _imp, _sre, _codecs, _io, _json, _locale, _typing, _collections, _functools, _operator, _stat, _string, _thread, _weakref):
        for v in vars(module).values():           # their functions', as `<__module__>.<__name__>`, "" for none (no built-in's is empty)
            if isinstance(v, types.BuiltinFunctionType) and isinstance(v.__module__, str):
                out[v.__module__ + "." + v.__name__] = v.__doc__ or ""
    # _imp's constants of the build: what importlib.machinery and _imp answer, recorded from the pin (one row each, the lists joined by newlines)
    out["imp:extension_suffixes"] = "\n".join(_imp.extension_suffixes())
    out["imp:pyc_magic_number_token"] = str(_imp.pyc_magic_number_token)
    out["imp:check_hash_based_pycs"] = _imp.check_hash_based_pycs
    out["imp:frozen_module_names"] = "\n".join(_imp._frozen_module_names())
    out["imp:frozen_packages"] = "\n".join(n for n in _imp._frozen_module_names() if _imp.is_frozen_package(n))
    # find_frozen's original name of each, in the same order ("" for None): Python/frozen.c's aliases
    out["imp:frozen_orignames"] = "\n".join((_imp.find_frozen(n) or (None, None, None))[2] or "" for n in _imp._frozen_module_names())
    for name in ("strict", "ignore", "replace", "xmlcharrefreplace", "backslashreplace", "namereplace", "surrogatepass", "surrogateescape"):
        handler = _codecs.lookup_error(name)      # the error handlers: built-in functions of no module
        out["." + handler.__name__] = handler.__doc__ or ""
    samples = [v for v in [type(sys.version_info), type(sys.flags), type(sys.float_info), type(sys.int_info), type(sys.hash_info), type(sys.thread_info), re.Pattern, re.Match, type(re.compile('').scanner('')), type(_sre.template('', [''])), *vars(_io).values(), *vars(_ast).values(), pwd.struct_passwd, grp.struct_group, *vars(posix).values(), *vars(builtins).values(), *vars(types).values(), *vars(itertools).values(), *vars(_operator).values(), *vars(_collections).values(), *vars(_functools).values(), type(_functools.cmp_to_key(None)), _struct.Struct, type(struct.iter_unpack('b', b'a')), time.struct_time, _md5.MD5Type, _sha1.SHA1Type, *vars(_sha2).values(), *vars(_sha3).values(), *vars(_blake2).values(), _hmac.HMAC, _csv.Dialect, _csv.Reader, _csv.Writer, _csv.Error, type(zlib.compressobj()), type(zlib.decompressobj()), zlib._ZlibDecompressor, zlib.error, _contextvars.Context, _contextvars.ContextVar, _contextvars.Token, type(_contextvars.Token.MISSING), type(_contextvars.copy_context().keys()), type(_contextvars.copy_context().values()), type(_contextvars.copy_context().items()), _random.Random, *vars(_thread).values(), *vars(_weakref).values()] if isinstance(v, type)]
    samples += [type(iter([])), type(iter(())), type(iter("")), type({}.keys()), type({}.values()), type({}.items()), type(iter({})),
                type(iter(set())), type(iter(range(1))), type(iter(range(2**64))), type(None), type(NotImplemented), type(Ellipsis), type(sys.stdout),
                type(iter(b"")), type(iter(bytearray())), type(reversed({})), type(reversed({}.values())), type(reversed({}.items())),
                type(t""), type(t"{0}".interpolations[0]), type(iter(t""))]
    for t in samples:                             # a type's doc under its own scope: _md5.md5 is a function and a type, with different docs
        out["type:" + tp_name(t)] = t.__doc__ if isinstance(t.__doc__, str) else ""
        new = vars(t).get("__new__")              # tp_new's builtin, a builtin_function_or_method bound to the type: its doc under new:<tp_name>
        if isinstance(new, types.BuiltinFunctionType):
            out["new:" + tp_name(t)] = new.__doc__ or ""
    return out

print(json.dumps({"docs": docs(), "builtins": sorted(dir(builtins)), "globals": GLOBALS, "sys": sorted(dir(sys)),
                  "types": type_names(), "final": sorted(FINAL), "weakref": sorted(WEAKREF), "flags": FLAGS, "heapflags": HEAPFLAGS, "offsets": OFFSETS, "itemsize": sorted(ITEMSIZE), "state": sorted(STATE), "shortname": sorted(SHORTNAME), "operators": operators(), "builtin_module": sorted(sys.builtin_module_names), "stdlib": sorted(sys.stdlib_module_names),
                  "modules": native_modules(sys.argv[1:])}))
'''


def pinned_python() -> str:
    return str(tomllib.loads((PROJECT / "bella.toml").read_text(encoding="utf-8"))["reference"]["python"])


def record() -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp, "probe.py")
        script.write_text(PROBE, encoding="utf-8")
        lock = json.loads((PROJECT / "closure.lock.json").read_text(encoding="utf-8"))
        native = sorted(n for n, m in lock["modules"].items() if m["status"] in ("core", "mapped") and m["kind"] == "builtin")
        # and the import system's two frozen modules, whose preludes keep part of CPython's text: a name they lack stops by name
        native += ["_frozen_importlib", "_frozen_importlib_external"]
        out = subprocess.run([sys.executable, str(script), *native], capture_output=True, text=True, check=True, cwd=tmp)
    data = json.loads(out.stdout)
    names = {(f"{scope}:{n}", "") for scope in ("builtins", "globals", "sys", "stdlib", "final", "weakref", "itemsize", "state", "shortname", "builtin_module") for n in data[scope]}
    names |= {(f"{t}:{n}", kind) for t, ns in data["types"].items() for n, kind in ns.items()}
    names |= {(key, "") for key in data["operators"]}
    names |= {(f"{scope}:{t}", value) for scope in ("flags", "heapflags", "offsets") for t, value in data[scope].items()}
    names |= {(f"{module}:{n}", "") for module, ns in data["modules"].items() for n in ns}
    version = ".".join(map(str, sys.version_info[:3]))
    return version, sorted(names), sorted(data["docs"].items())


def _c_text(text: str) -> str:
    """A C++ string literal: JSON's escapes, with the non-ASCII written as UTF-8 by the file's encoding."""
    return json.dumps(text, ensure_ascii=False).replace("?", "\\?")


def render(version: str, names: list[tuple[str, str]], docs: list[tuple[str, str]]) -> str:
    lines = [f"// Generated by tools/cpython_names.py from CPython {version}; do not edit. The names CPython has:",
             "// builtins, a script's globals, sys, the standard library's modules, and each built-in type's own attributes with the kind of",
             "// object it is, as `scope:name`, sorted for binary search. The runtime refuses a name it lacks,",
             "// and an object it cannot present as CPython's (runtime/src/call.cpp).",
             "struct CPythonName {",
             "    std::string_view key, kind;",
             "};",
             "static constexpr CPythonName CPYTHON_NAMES[] = {"]
    lines += [f'    {{"{n}", "{k}"}},' for n, k in names]
    lines.append("};")
    lines += ["// Docstrings: the built-in modules' (`sys`, `builtins`) and the built-in types', by __name__, sorted.",
              "struct CPythonDoc {",
              "    std::string_view name, text;",
              "};",
              "static constexpr CPythonDoc CPYTHON_DOCS[] = {"]
    lines += [f'    {{"{n}", {_c_text(t)}}},' for n, t in docs]
    lines.append("};")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the recorded table differs from this CPython's")
    ap.add_argument("--allow-unpinned", action="store_true", help="run on a Python other than the pinned build")
    args = ap.parse_args(argv)
    running, pinned = ".".join(map(str, sys.version_info[:3])), pinned_python()
    if running != pinned and not args.allow_unpinned:
        print(f"cpython_names: refusing to run on Python {running}; the reference is {pinned} "
              f"(use --allow-unpinned for a non-authoritative run)", file=sys.stderr)
        return 2
    version, names, docs = record()
    text = render(version if running == pinned else f"{version} [UNPINNED]", names, docs)
    if any('"' in n or "\\" in n for n, _ in names):
        raise SystemExit("cpython_names: a name that needs escaping")
    if args.check:
        if OUT.read_text(encoding="utf-8") != text:
            print(f"cpython_names: {OUT.relative_to(PROJECT)} differs from CPython {version}; "
                  f"run python3 tools/cpython_names.py", file=sys.stderr)
            return 1
        print(f"cpython_names: {len(names)} names agree with CPython {version}")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"cpython_names: {len(names)} names from CPython {version} -> {OUT.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
