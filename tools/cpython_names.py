"""The names CPython has, recorded for the compiled runtime's refusals.

A compiled program may name something CPython provides that Bella's runtime does not have yet: a
builtin (`sorted`), an attribute of `sys` (`sys.maxsize`) or a method of a built-in type
(`str.startswith`, `object.__sizeof__`). CPython would find it; answering NameError or
AttributeError would be a wrong answer, so the runtime refuses instead (`bella: not implemented`,
exit 70). This tool records, from the pinned CPython, which names exist:

* `builtins:<name>`: the builtins module, as a script sees it;
* `globals:<name>`: the globals CPython gives a script before it runs (`__file__`, `__builtins__`);
* `sys:<name>`: the sys module, as a script sees it;
* `binop:<type><op><type>`, `iop:...`, `cmp:...`: the operators CPython handles between the
  built-in types the runtime has (and `instance`, a plain class's object, for any instance whose
  own methods declined): handled means not rejected as an unsupported operand (or, for an
  ordering, as not supported between the instances); `==` and `!=` count when a type's own
  method decides, not the identity fallback. The runtime refuses a handled operation it does
  not implement, rather than raise the TypeError CPython would not.
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
import builtins, json, sys, types

def type_names():
    found = {}
    def add(t):
        if isinstance(t, type):
            found.setdefault(t.__name__, {}).update({n: type(v).__name__ for n, v in vars(t).items()})
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
    samples = [iter([]), iter(()), iter(""), iter("é"), iter({}), iter({}.values()), iter({}.items()),
               iter(set()), iter(range(1)), iter(Seq()), reversed([]), {}.keys(), {}.values(), {}.items(),
               outer, outer().__closure__[0], outer.__code__, type.__dict__, [].append, list.append,
               dict.__dict__["fromkeys"], type.__dict__["__name__"], object.__init__, object().__init__,
               sys.stdout, NotImplemented, Ellipsis, None, tb, tb.tb_frame, gen(), slice(1), Probe().__init__]
    for v in [*vars(builtins).values(), *vars(types).values()]:
        add(v)
    for s in samples:
        add(type(s))
    # type's attributes as a class reads them: a getset that raises for a plain class is left out
    found["type"] = {n: k for n, k in found["type"].items() if hasattr(Probe, n)}
    return found

def operators():
    import copy
    import operator as op
    class Instance:
        pass
    reps = {"int": lambda: 3, "bool": lambda: True, "str": lambda: "a%s", "tuple": lambda: (1,), "list": lambda: [1],
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

print(json.dumps({"builtins": sorted(dir(builtins)), "globals": GLOBALS, "sys": sorted(dir(sys)),
                  "types": type_names(), "operators": operators()}))
'''


def pinned_python() -> str:
    return str(tomllib.loads((PROJECT / "bella.toml").read_text(encoding="utf-8"))["reference"]["python"])


def record() -> tuple[str, list[tuple[str, str]]]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp, "probe.py")
        script.write_text(PROBE, encoding="utf-8")
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, cwd=tmp)
    data = json.loads(out.stdout)
    names = {(f"{scope}:{n}", "") for scope in ("builtins", "globals", "sys") for n in data[scope]}
    names |= {(f"{t}:{n}", kind) for t, ns in data["types"].items() for n, kind in ns.items()}
    names |= {(key, "") for key in data["operators"]}
    version = ".".join(map(str, sys.version_info[:3]))
    return version, sorted(names)


def render(version: str, names: list[tuple[str, str]]) -> str:
    lines = [f"// Generated by tools/cpython_names.py from CPython {version}; do not edit. The names CPython has:",
             "// builtins, a script's globals, sys, and each built-in type's own attributes with the kind of",
             "// object it is, as `scope:name`, sorted for binary search. The runtime refuses a name it lacks,",
             "// and an object it cannot present as CPython's (runtime/src/call.cpp).",
             "struct CPythonName {",
             "    std::string_view key, kind;",
             "};",
             "static constexpr CPythonName CPYTHON_NAMES[] = {"]
    lines += [f'    {{"{n}", "{k}"}},' for n, k in names]
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
    version, names = record()
    text = render(version if running == pinned else f"{version} [UNPINNED]", names)
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
