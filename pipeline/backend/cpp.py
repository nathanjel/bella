"""The C++ emitter: one L2 module into one C++26 translation unit against bella/runtime.hpp.

Readable output is a design goal (CLAUDE.md): a Python function becomes a C++ function of its
name, its locals keep their Python names, each L2 statement becomes one C++ statement in the same
order, and `frame.line = n` marks the source lines. The rules (docs/emitter.md):

* Temporaries are `Ref`s declared at the top of their region (a function, a `try` body, a
  handler), in their number order, so C++ unwinding destroys them newest first: L2's exception
  edge (docs/l2.md section 8, decision 1). `release t` is `t = Ref{}`; a store moves its value in
  and releases the old one after the new one is stored.
* A frame is a record and a guard (decision 5): `FrameGuard frame(code_f, M, a, b)` after the locals.
* C++ has no `finally`: the block is written out on every way out of the `try`, as CPython's
  compiler does: the normal end, the exception edge (`catch (...)`, then rethrow), and before each
  `return`, `break` or `continue` that leaves it, innermost first, with a loop's held iterator
  released where L2 says (after the `finally` blocks nested in the loop).
* What L2 has that the runtime lacks yet compiles to a refusal where it would run (P-1):
  generators and class bodies until steps 3b and 3a.2.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from pipeline.l1.grammar import Unsupported
from pipeline.l2 import grammar as G

_KEYWORDS = frozenset("""alignas alignof and and_eq asm auto bitand bitor bool break case catch char char8_t char16_t
char32_t class compl concept const consteval constexpr constinit const_cast continue co_await co_return co_yield
decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline
int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register
reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template this
thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq
final override import module contract_assert main std rt Obj Ref Args fn args frame stack_values ns M ret init_constants module_body
""".split())
# Every name the emitter makes matches this (review 2026-11-03, A9-20); a Python name that matches
# it, or that C++ reserves, is escaped.
_COMPILER_NAME = re.compile(r"^(t\d+|e\d+|h\d+|u\d+|gen1|cur1|fin\d+|ended\d+|raised\d+|after\d+|K_\d+|S_\w*|code_\w*|f_\w*|py\w*)$")

_BINARY = {"+": "Add", "-": "Sub", "*": "Mul", "/": "TrueDiv", "//": "FloorDiv", "%": "Mod", "**": "Pow",
           "<<": "LShift", ">>": "RShift", "&": "And", "|": "Or", "^": "Xor", "@": "MatMul"}
_COMPARE = {"<": "Lt", "<=": "Le", "==": "Eq", "!=": "Ne", ">": "Gt", ">=": "Ge", "in": "In", "not in": "NotIn",
            "is": "Is", "is not": "IsNot", "not-in": "NotIn", "is-not": "IsNot"}
_UNARY = {"-": "unary_neg", "+": "unary_pos", "~": "unary_invert"}


@cache
def header_macros() -> frozenset[str]:
    """The macros bella/runtime.hpp defines, its system headers' included (`ENOENT`, `errno`,
    `S_IFMT`): a Python name spelled like one would be replaced by the preprocessor, so the
    compiler says which they are. Without a compiler nothing will read the output."""
    include = Path(__file__).resolve().parents[2] / "runtime" / "include"
    cxx = os.environ.get("CXX", "g++")
    if shutil.which(cxx) is None:
        return frozenset()
    proc = subprocess.run([cxx, f"-std={os.environ.get('CXXSTD', 'c++26')}", f"-I{include}", "-dM", "-E", "-x", "c++", "-"],
                          input='#include "bella/runtime.hpp"\n', capture_output=True, text=True, check=True)
    return frozenset(line.split()[1].partition("(")[0] for line in proc.stdout.splitlines() if line.startswith("#define "))


def cpp_name(name: str) -> str:
    """A Python identifier as a C++ one: kept as written unless C++ reserves it (a keyword, a macro
    of the headers, a name with `__` or starting `_` and a capital) or it matches a name the
    emitter makes; then `py` followed by the name with `_` written `_1` and a non-ASCII character
    `_2` and six hex digits. The escape is injective and never makes `__`, and a kept name never
    starts with `py`."""
    if (name.isascii() and name not in _KEYWORDS and "__" not in name and not re.match(r"^_[A-Z]", name)
            and not _COMPILER_NAME.match(name) and name not in header_macros()):
        return name
    return "py" + "".join("_1" if c == "_" else c if c.isascii() else f"_2{ord(c):06x}" for c in name)


def c_bytes(b: bytes) -> str:
    """A C++ string literal holding these octets: three octal digits, so what follows cannot join them."""
    return '"' + "".join(chr(c) if 32 <= c < 127 and chr(c) not in '\\"?' else f"\\{c:03o}" for c in b) + '"'


def c_string(s: str) -> str:
    """A C++ string literal holding s as UTF-8."""
    out = []
    for b in s.encode("utf-8", "surrogatepass"):
        c = chr(b)
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif 32 <= b < 127 and c != "?":
            out.append(c)
        else:
            out.append(f"\\{b:03o}")
    return '"' + "".join(out) + '"'


_RETURN, _BREAK, _CONTINUE, _ENDLOOP = 1, 2, 3, 4      # how a try with a finally was left


@dataclass
class _Exit:
    """An enclosing construct a `return`, `break` or `continue` passes through on its way out."""
    kind: str                                    # "finally", "cleanup" (except-as's e = None; del e) or "loop"
    body: tuple[G.Stmt, ...] = ()                # the finally block, or the cleanup
    holds: tuple[G.Temp, ...] = ()               # a loop's held temporaries
    ended: str | None = None                     # a loop's flag for running its else block
    flag: str = ""                               # a finally's completion variable
    completions: set[int] = field(default_factory=set)   # the completions that reached a finally
    restore: int = 0                             # a generator's: the handler row outside this construct
    row: int = 0                                 # a generator's: the row whose exception is being handled


@dataclass
class _Row:
    """A generator's handler table: where an exception arriving under this row goes on, and what it drops first."""
    pc: int
    parent: int
    clears: tuple[str, ...] = ()


@dataclass
class _Function:
    code: G.Code
    cname: str
    entry: str
    lines: list[str] = field(default_factory=list)


class Emitter:
    def __init__(self, module: G.Module, namespace: str, filename: str, prelude: bool = False) -> None:
        self.module = module
        self.namespace = namespace
        self.filename = filename
        self.prelude = prelude                   # the prelude: C functions in CPython, no frames
        self.consts: dict[tuple[str, object], str] = {}
        self.const_init: list[str] = []
        self.names: dict[str, str] = {}
        self.functions: list[_Function] = []
        self.parent_kind: dict[int, str] = {}       # a code's enclosing code's kind (CO_METHOD: defined in a class body)
        self.nested: dict[int, bool] = {}           # CO_NESTED: an enclosing code is a function's (a generic's parameter scope too)
        self.by_code: dict[int, _Function] = {}
        self.used: set[str] = set()

    # ---- names and constants --------------------------------------------------------------

    def unique(self, base: str) -> str:
        name, i = base, 1
        while name in self.used or name in header_macros():   # S_IFMT is a macro of <sys/stat.h>
            i += 1
            name = f"{base}_{i}"
        self.used.add(name)
        return name

    def name(self, text: str) -> str:
        """An interned name (S_x), for attribute and global access."""
        if text not in self.names:
            dunder = len(text) > 4 and text.startswith("__") and text.endswith("__")
            self.names[text] = self.unique("S_" + ("dunder_" if dunder else "") + _ident(text))
        return self.names[text]

    def const(self, value: object) -> str:
        """A constant as a C++ expression of type Obj."""
        if value is None:
            return "rt::None()"
        if value is True or value is False:
            return f"rt::boolean({'true' if value else 'false'})"
        if value is Ellipsis:
            return "Obj::of(rt::ELLIPSIS)"
        if type(value) is int:
            if -(1 << 62) <= value < (1 << 62):
                return f"Obj::small({value}{'LL' if abs(value) > 2**31 else ''})"
            # a literal CPython reads is within 4300 decimal digits; a hex one need not be
            text = str(value) if value.bit_length() < 14000 else hex(value)
            return self.lazy(("int", value), f'rt::big_int_constant("{text}")')
        if type(value) is str:
            # a NUL inside: the literal's length given, or the string would end there
            text = (f"std::string_view({c_string(value)}, {len(value.encode('utf-8', 'surrogatepass'))})" if "\0" in value
                    else c_string(value))
            return self.lazy(("str", value), f"Obj::of(rt::intern({text}))" if value.isascii() or
                             not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
                             else f"rt::str_constant_cps({{{', '.join(f'char32_t{{{ord(c):#x}}}' for c in value)}}})")
        if type(value) is bytes:
            return self.lazy(("bytes", value), f"rt::bytes_constant({c_bytes(value)}, {len(value)})")
        if type(value) is float:
            # a hexadecimal literal is the value's exact bits; the key tells 0.0 from -0.0
            text = "HUGE_VAL" if value == math.inf else value.hex()
            return self.lazy(("float", value.hex()), f"rt::float_constant({text})")
        if type(value) is complex:
            # a literal's parts: 0.0 and a non-negative number, perhaps an infinity
            parts = ", ".join("HUGE_VAL" if part == math.inf else part.hex() for part in (value.real, value.imag))
            return self.lazy(("complex", (value.real.hex(), value.imag.hex())), f"rt::complex_constant({parts})")
        if type(value) is tuple and all(_supported_constant(v) for v in value):
            items = ", ".join(self.const(v) for v in value)
            return self.lazy(("tuple", value), f"rt::tuple_new({{{items}}}).release()")
        # refused where it is used, never when the module starts (P-1)
        kind = type(value).__name__
        return f"rt::unsupported_constant({c_string(f'a {kind} constant: {value!r}')})"

    def lazy(self, key: tuple[str, object], init: str) -> str:
        """A constant made when the module first runs, never at static initialisation."""
        if key not in self.consts:
            name = f"K_{len(self.consts) + 1}"
            self.consts[key] = name
            self.const_init.append(f"    {name} = {init};")
        return self.consts[key]

    def atom(self, a: G.Atom | None) -> str:
        if a is None:
            return "Obj{}"
        if isinstance(a, G.Temp):
            return f"t{a.n}.get()"
        return self.const(a.value)

    # ---- code objects --------------------------------------------------------------------------

    def collect(self, code: G.Code, parent: G.Code | None = None) -> None:
        cname = self.unique("code_" + _ident(code.qualname))
        entry = self.unique("f_" + _ident(code.qualname)) if code.kind != "module" else "module_body"
        fn = _Function(code, cname, entry)
        self.functions.append(fn)
        self.by_code[id(code)] = fn
        self.parent_kind[id(code)] = parent.kind if parent is not None else ""
        self.nested[id(code)] = parent is not None and (self.nested.get(id(parent), False) or parent.kind not in ("module", "classbody"))
        for c in _nested_codes(code.body):
            self.collect(c, code)

    def emit(self) -> str:
        self.collect(self.module.code)
        bodies = [self.function(fn) for fn in self.functions]
        out = [f"// {self.filename}, compiled by Bella (L2 -> C++26). Generated: do not edit.",
               '#include "bella/runtime.hpp"', "", f"namespace {self.namespace} {{",
               "namespace rt = ::bella;", "using rt::Obj;", "using rt::Ref;", "",
               "static bool constants_made = false;      // made once, by the module's first run"]
        for text, ident in sorted(self.names.items(), key=lambda kv: kv[1]):
            out.append(f"static const rt::Str* const {ident} = rt::intern({c_string(text)});")
        if self.consts:
            out.append("static Obj " + ", ".join(sorted(self.consts.values(), key=lambda k: int(k[2:]))) + ";")
        out.append("")
        for fn in self.functions:
            out.append(self.code_record(fn))
        out.append("")
        for fn in self.functions:
            if fn.code.kind != "module":
                out.append(f"static Ref {fn.entry}(rt::PyFunction* fn, rt::Args args);")
        out.append("")
        out.append("static void init_constants() {")
        out.append("    if (constants_made) return;")
        out.append("    constants_made = true;")
        out += self.const_init
        out.append("}")
        out.append("")
        for body in bodies:
            out += body
            out.append("")
        out.append(f"}}  // namespace {self.namespace}")
        return "\n".join(out) + "\n"

    def code_record(self, fn: _Function) -> str:
        """The code object's names and counts (dialect specification E-02 as narrowed in v0.14): co_varnames in CPython's order
        (the parameters, then the other locals as they are first bound; the compiler's own temporaries left out), co_cellvars,
        co_freevars, and co_flags from the kind of code."""
        c = fn.code
        positional = [p for p in c.params if p.kind in ("positional-only", "positional-or-keyword")]
        posonly = sum(1 for p in c.params if p.kind == "positional-only")
        kwonly = [p for p in c.params if p.kind == "keyword-only"]
        varargs = any(p.kind == "*args" for p in c.params)
        varkw = any(p.kind == "**kwargs" for p in c.params)
        params = self.param_order(c)
        public = {p.name: p.public or p.name for p in params}
        meta = dict(c.meta)
        hidden = meta.get("hidden")
        hidden_names: frozenset[str] = hidden if isinstance(hidden, frozenset) else frozenset()
        co_varnames = meta.get("co_varnames")
        locals_: tuple[str, ...] = co_varnames if isinstance(co_varnames, tuple) else c.varnames
        names = [public[p.name] for p in params] + [n for n in locals_ if n not in public and n not in hidden_names]
        co_cellvars = meta.get("co_cellvars")
        cellvars = [n for n in (co_cellvars if isinstance(co_cellvars, tuple) else c.cellvars) if n not in hidden_names]
        freevars = [n for n in c.freevars if n not in hidden_names]
        doc = "nullptr" if c.docstring is None else c_string(c.docstring)
        flags = 0
        if c.kind not in ("module", "classbody"):
            flags |= 0x1 | 0x2                                         # CO_OPTIMIZED, CO_NEWLOCALS
        flags |= (0x4 if varargs else 0) | (0x8 if varkw else 0)      # CO_VARARGS, CO_VARKEYWORDS
        if self.nested.get(id(c), False):
            flags |= 0x10                                              # CO_NESTED: some enclosing code is a function's
        # compute_code_flags: ff_features & PyCF_MASK, of which future.c sets two (the other features are mandatory now)
        if "annotations" in self.module.future:
            flags |= 0x1000000                                         # CO_FUTURE_ANNOTATIONS
        if "barry_as_FLUFL" in self.module.future:
            flags |= 0x400000                                          # CO_FUTURE_BARRY_AS_BDFL (G16 #1)
        flags |= {"generator": 0x20, "coroutine": 0x80, "async generator": 0x200}.get(c.kind, 0)
        if c.docstring is not None:
            flags |= 0x4000000                                         # CO_HAS_DOCSTRING
        if self.parent_kind.get(id(c)) == "classbody" and c.kind not in ("module", "classbody"):
            flags |= 0x8000000                                         # CO_METHOD
        # a frame CPython does not have (the prelude's C functions, an inlined comprehension)
        # never enters a traceback (RL-223, RL-224)
        shown = "false" if self.prelude or dict(c.meta).get("inlined", False) else "true"
        inlined = "true" if dict(c.meta).get("inlined", False) and not self.prelude else "false"   # the prelude stands for C, which has none
        def strings(ns: list[str]) -> str:
            return "{" + ", ".join(c_string(n) for n in ns) + "}"
        return (f"static const rt::Code {fn.cname}{{{c_string(c.name)}, {c_string(c.qualname)}, {c_string(self.filename)}, "
                f"{c.first_line}, {len(positional)}, {posonly}, {len(kwonly)}, {str(varargs).lower()}, "
                f"{str(varkw).lower()}, {strings(names)}, {doc}, {shown}, {strings(cellvars)}, {strings(freevars)}, {flags}, {inlined}}};")

    @staticmethod
    def param_order(c: G.Code) -> list[G.Param]:
        """co_varnames' order: positional, keyword-only, *args, **kwargs."""
        order = ("positional-only", "positional-or-keyword", "keyword-only", "*args", "**kwargs")
        return sorted(c.params, key=lambda p: order.index(p.kind))

    def function(self, fn: _Function) -> list[str]:
        c = fn.code
        self.code = c
        self.out: list[str] = []
        self.exits: list[_Exit] = []
        self.hidden = _hidden(c)
        self.counter = 0
        self.flat = False
        # PEP 709: an inlined comprehension runs in its enclosing frame, so its lines are that frame's (a warning's stacklevel, a
        # traceback through the enclosing call); its own record is not on the frame chain (review G15 #2)
        self.inlined = bool(dict(c.meta).get("inlined", False)) and not self.prelude
        params = [p.name for p in self.param_order(c)]
        frame_locals = [*c.varnames, *(n for n in c.cellvars if n not in c.varnames), *c.freevars]
        self.vars = {n: cpp_name(n) for n in frame_locals}
        if c.kind == "module":
            head = f"rt::Ref {fn.entry}(rt::Module* m) {{"
            # a module whose body failed runs again in a new module object (spec section 8): the
            # module pointer is the body's argument, and each function's is the one it was made in
            self.out += [f"// the module body of {self.filename}", head, "    rt::Module* M = m;", "    init_constants();",
                         "    Obj ns = Obj::of(m->locals != nullptr ? m->locals : m->dict);"]
        elif c.kind == "classbody":
            # __build_class__ calls the body with the class namespace (runtime/prelude/build_class.py)
            self.out += [f"// the body of class {c.qualname}  ({self.filename}:{c.first_line})",
                         f"static Ref {fn.entry}(rt::PyFunction* fn, rt::Args args) {{",
                         "    [[maybe_unused]] rt::Module* M = fn->module;", "    Obj ns = args.pos(0);"]
        elif c.kind == "generator":
            return self.generator(fn, frame_locals, params)
        else:
            self.out += [f"// {c.kind} {c.qualname}  ({self.filename}:{c.first_line})",
                         f"static Ref {fn.entry}(rt::PyFunction* fn, rt::Args args) {{",
                         "    [[maybe_unused]] rt::Module* M = fn->module;"]
        for n in frame_locals:
            self.out.append(f"    Ref {self.vars[n]};")
        guard = ", ".join(["", *(self.vars[n] for n in frame_locals)])
        self.out.append(f"    rt::FrameGuard frame({fn.cname}, M{guard});")
        # the frontend's variables for what CPython keeps on its stack, and a list, set or dict
        # comprehension helper's iterator (PEP 709 inlines those; a generator's is a real frame's
        # argument): dropped newest first when an exception leaves, before the frame is recorded,
        # as eval2's unwind_synthetic does (review log RL-186)
        arguments = set() if c.kind == "generator" else {p.name for p in c.params}
        stack = sorted((_synthetic_stored(c.body, self.hidden) | arguments) & self.hidden, key=_creation, reverse=True)
        if stack:
            self.out.append(f"    rt::StackValues stack_values({', '.join(self.vars[n] for n in stack)});")
        if c.kind == "classbody":
            for n in c.cellvars:
                self.out.append(f"    {self.vars[n]} = rt::make_cell();")
            for i, n in enumerate(c.freevars):
                self.out.append(f"    {self.vars[n]} = fn->closure[{i}];")
        elif c.kind != "module":
            if params:
                self.out.append(f"    rt::bind(fn, args, {{{', '.join('&' + self.vars[n] for n in params)}}});")
            else:
                self.out.append("    rt::bind(fn, args, {});")
            for i, n in enumerate(c.freevars):
                self.out.append(f"    {self.vars[n]} = fn->closure[{i}];")
            for n in c.cellvars:
                if n in params:
                    self.out.append(f"    {self.vars[n]} = rt::make_cell({self.vars[n]}.get());")
                else:
                    self.out.append(f"    {self.vars[n]} = rt::make_cell();")
            if c.kind in ("coroutine", "async generator"):
                self.out.append(f"    throw rt::NotImplemented({c_string(f'running the {c.kind} {c.qualname} (step 3b: generators)')});")
                self.out.append("}")
                return self.out
        if _returns_through_finally(c.body):
            self.out.append("    Ref ret;                                   // a return's value while finally blocks run")
        self.region(c.body, 1)
        if G.falls_through(c.body):
            self.out.append("    return rt::none_ref();")
        self.out.append("}")
        return self.out

    # ---- generators: the state machine (design section 10.3; docs/emitter.md) --------------------------

    def generator(self, fn: _Function, frame_locals: list[str], params: list[str]) -> list[str]:
        """Two functions. The one the program calls binds the arguments into a new generator, as RETURN_GENERATOR leaves
        them. The other is one resume: a `switch` on where the last one stopped, with `case` labels at the yields. A case
        label may sit inside an `if` or a loop, and nothing a yield crosses lives on the C++ stack, but C++ cannot jump
        into a try block or back into a handler: so a try whose code yields has no C++ try of its own. A single try
        around the switch catches everything, and `cur1`, the row of the table for where execution is, says where each
        exception goes on, as CPython's exception table does. A try that does not yield is emitted as in any function."""
        c = fn.code
        self.flat = True
        self.slots: dict[str, int] = {}
        self.int_slots: list[str] = []
        self.rows: dict[int, _Row] = {}
        self.synthetic_names: set[str] = set()
        self.next_pc = 0
        self.cur = 0
        for n in frame_locals:
            self.slot(self.vars[n])
        if _returns_through_finally(c.body):
            self.slot("ret")
        self.region(c.body, 4)
        if G.falls_through(c.body):
            self.add(4, "gen1->pc = rt::GEN_RETURNED;")
            self.add(4, "return rt::none_ref();")
        body = self.out
        stack = sorted(_synthetic_stored(c.body, self.hidden) & self.hidden, key=_creation, reverse=True)
        temps = sorted((n for n in self.slots if _TEMP.match(n)), key=lambda n: int(n[1:]), reverse=True)
        guard = ", ".join(["", *(self.vars[n] for n in frame_locals)])
        out = [f"// generator {c.qualname}  ({self.filename}:{c.first_line}): one resume",
               f"static Ref {fn.entry}_resume(rt::Generator* gen1) {{",
               "    [[maybe_unused]] rt::Module* M = gen1->module;"]
        out += [f"    Ref& {name} = gen1->slots[{i}];" for name, i in self.slots.items()]
        out += [f"    int& {name} = gen1->ints[{i}];" for i, name in enumerate(self.int_slots)]
        out += ["    [[maybe_unused]] int& cur1 = gen1->handler;",
                f"    rt::FrameGuard frame({fn.cname}, M{guard});",
                "    frame.line = gen1->line;",
                "    for (;;) {",
                "        try {",
                "            rt::gen_raise_pending(gen1);",
                "            switch (gen1->pc) {",
                "            case 0:;"]
        out += body
        out += ["            }",
                "            __builtin_unreachable();",
                "        } catch (rt::PyError& e1) {",
                "            frame.arrived(e1);"]
        if self.rows:
            out.append("            switch (cur1) {")
            for k, row in sorted(self.rows.items()):
                out.append(f"            case {k}:")
                out += [f"                {name} = rt::none_ref();" if name in self.synthetic_names else f"                {name} = Ref{{}};" for name in row.clears]
                out += [f"                rt::gen_caught(gen1, {k}, e1);",
                        f"                gen1->pc = {row.pc};",
                        f"                cur1 = {row.parent};",
                        "                continue;"]
            out += ["            default:", "                break;", "            }"]
        out += [f"            {name} = Ref{{}};" for name in temps]
        out += [f"            {self.vars[name]} = Ref{{}};" for name in stack]
        out += ["            gen1->pc = rt::GEN_RETURNED;",
                "            rt::gen_uncaught(gen1, e1);",
                "        }",
                "    }",
                "}",
                f"// the generator function {c.qualname}: its call makes the generator",
                f"static Ref {fn.entry}(rt::PyFunction* fn, rt::Args args) {{",
                "    [[maybe_unused]] rt::Module* M = fn->module;",
                f"    Ref made = rt::make_generator(fn, {fn.cname}, {fn.entry}_resume, {len(self.slots)}, {len(self.int_slots)}, {len(self.rows) + 1});",
                "    auto* gen1 = static_cast<rt::Generator*>(made.get().object());"]
        out += [f"    Ref& {self.vars[n]} = gen1->slots[{self.slots[self.vars[n]]}];" for n in frame_locals]
        out.append(f"    rt::FrameGuard frame({fn.cname}, M);")
        out.append(f"    rt::bind(fn, args, {{{', '.join('&' + self.vars[n] for n in params)}}});")
        out += [f"    {self.vars[n]} = fn->closure[{i}];" for i, n in enumerate(c.freevars)]
        for n in c.cellvars:
            out.append(f"    {self.vars[n]} = rt::make_cell({self.vars[n]}.get());" if n in params else f"    {self.vars[n]} = rt::make_cell();")
        out += ["    return made;", "}"]
        return out

    def slot(self, name: str) -> str:
        self.slots.setdefault(name, len(self.slots))
        return name

    def new_pc(self) -> int:
        self.next_pc += 1
        return self.next_pc

    def new_row(self, parent: int, clears: tuple[str, ...]) -> int:
        k = len(self.rows) + 1
        self.rows[k] = _Row(self.new_pc(), parent, clears)
        return k

    def clears_of(self, body: tuple[G.Stmt, ...]) -> tuple[str, ...]:
        """What an exception leaving these statements drops, as unwinding would: the temporaries newest first, then the
        frontend's variables for what CPython keeps on its stack (review log RL-186)."""
        for n in _all_assigned(body):
            self.slot(f"t{n}")
        temps = [f"t{n}" for n in sorted(_all_assigned(body), reverse=True)]
        synthetic = [self.vars[n] for n in sorted(_synthetic_stored(body, self.hidden), key=_creation, reverse=True)]
        self.synthetic_names |= set(synthetic)
        return (*temps, *synthetic)

    def yield_(self, value: G.Atom, after: str, indent: int) -> None:
        pc = self.new_pc()
        self.add(indent, f"gen1->pc = {pc}; gen1->line = frame.line;")
        self.add(indent, f"return {self.take(value)};")
        self.add(indent, f"case {pc}:;")
        self.add(indent, after)

    def yield_from(self, value: G.Atom, after: str, indent: int) -> None:
        pc = self.new_pc()
        self.add(indent, f"rt::gen_delegate_to(gen1, {self.atom(value)});")
        if isinstance(value, G.Temp):            # GET_YIELD_FROM_ITER consumes it: the iterator is what the frame holds
            self.add(indent, f"t{value.n} = Ref{{}};")
        self.add(indent, f"gen1->pc = {pc}; gen1->line = frame.line;")
        self.add(indent, f"case {pc}:;")
        self.add(indent, "{")
        self.add(indent + 1, "Ref step = rt::gen_delegate_step(gen1);")
        self.add(indent + 1, "if (!rt::is_end(step)) return step;")
        self.add(indent, "}")
        self.add(indent, after)

    def gen_return(self, value: str, indent: int) -> None:
        self.add(indent, "gen1->pc = rt::GEN_RETURNED;")
        self.add(indent, f"return {value};")

    def enter_row(self, row: int, indent: int) -> None:
        self.cur = row
        self.add(indent, f"cur1 = {row};")

    def flat_try(self, s: G.Try, indent: int) -> None:
        if s.finalbody:
            self.flat_finally(s, indent)
        else:
            self.flat_handlers(s, indent)

    def flat_finally(self, s: G.Try, indent: int) -> None:
        """As `try_`: the normal end and every jump out reach the label with the completion noted, the block runs there
        once, and the exception edge has its own copy, run with the exception as the one being handled."""
        parent = self.cur
        flag = self.aux("fin")
        self.int_slots.append(flag)
        after = self.aux("after")
        row = self.new_row(parent, self.clears_of(s.body + tuple(st for h in s.handlers for st in (*h.match, *h.body)) + s.orelse))
        ex = _Exit("finally", body=s.finalbody, flag=flag, restore=parent)
        self.add(indent, f"{flag} = 0;")
        self.enter_row(row, indent)
        self.exits.append(ex)
        self.flat_handlers(G.Try(s.body, s.handlers, s.orelse), indent)
        self.exits.pop()
        self.add(indent, f"{flag}_end:;")
        self.cur = parent
        self.add(indent, f"cur1 = {parent};")
        self.add(indent, "{")
        self.region(s.finalbody, indent + 1)
        self.add(indent, "}")
        for kind in sorted(ex.completions):
            self.add(indent, f"if ({flag} == {kind}) {{")
            self.leave(kind, len(self.exits) - 1, indent + 1)
            self.add(indent, "}")
        self.add(indent, f"goto {after};")
        # the exception edge
        self.add(indent, f"case {self.rows[row].pc}:;")
        inner = self.new_row(parent, self.clears_of(s.finalbody))
        self.add(indent, f"rt::gen_handling_push(gen1, {row});")
        self.enter_row(inner, indent)
        self.exits.append(_Exit("handling", row=row, restore=parent))
        self.add(indent, "{")
        self.region(s.finalbody, indent + 1)
        self.add(indent, "}")
        self.exits.pop()
        self.cur = parent
        self.add(indent, f"cur1 = {parent};")
        self.add(indent, f"{{ rt::Ref keep = gen1->errors[{row}]->exc; std::uint64_t recorded = gen1->errors[{row}]->recorded; rt::gen_handling_pop(gen1, {row}); throw rt::PyError(std::move(keep), recorded); }}")
        self.add(indent, f"case {self.rows[inner].pc}:;")
        self.add(indent, f"rt::gen_handling_pop(gen1, {row});")
        self.add(indent, f"rt::gen_rethrow(gen1, {inner});")
        self.add(indent, f"{after}:;")

    def flat_handlers(self, s: G.Try, indent: int) -> None:
        if not s.handlers:
            self.add(indent, "{")
            self.region(s.body, indent + 1)
            self.add(indent, "}")
            return
        parent = self.cur
        after = self.aux("after")
        row = self.new_row(parent, self.clears_of(s.body))
        self.enter_row(row, indent)
        self.exits.append(_Exit("flat", restore=parent))
        self.add(indent, "{")
        self.region(s.body, indent + 1)
        self.add(indent, "}")
        self.exits.pop()
        self.cur = parent
        self.add(indent, f"cur1 = {parent};")
        if s.orelse:
            self.add(indent, "{")
            self.region(s.orelse, indent + 1)
            self.add(indent, "}")
        self.add(indent, f"goto {after};")
        # an exception arrived: the handlers run with it as the one being handled
        self.add(indent, f"case {self.rows[row].pc}:;")
        matching = tuple(f"t{n}" for n in sorted({n for h in s.handlers for n in _assigned(h.match)}, reverse=True))
        inner = self.new_row(parent, (*matching, *self.clears_of(tuple(st for h in s.handlers for st in h.body))))
        self.add(indent, f"rt::gen_handling_push(gen1, {row});")
        self.enter_row(inner, indent)
        self.exits.append(_Exit("handling", row=row, restore=parent))
        self.flat_chain(s.handlers, 0, row, indent)
        self.exits.pop()
        self.cur = parent
        self.add(indent, f"rt::gen_handling_pop(gen1, {row});")
        self.add(indent, f"cur1 = {parent};")
        self.add(indent, f"goto {after};")
        self.add(indent, f"case {self.rows[inner].pc}:;")
        self.add(indent, f"rt::gen_handling_pop(gen1, {row});")
        self.add(indent, f"rt::gen_rethrow(gen1, {inner});")
        self.add(indent, f"{after}:;")

    def flat_chain(self, handlers: tuple[G.Handler, ...], i: int, row: int, indent: int) -> None:
        """`handlers`, where the exception is gen1's for the row. None matching: it goes on, as the handlers' own would."""
        exc = f"gen1->errors[{row}]->exc"
        if i == len(handlers):
            self.add(indent, f"throw rt::PyError(gen1->errors[{row}]->exc, gen1->errors[{row}]->recorded);")
            return
        h = handlers[i]
        self.add(indent, "{")
        for n in _assigned(h.match):             # a case label may follow in this block: nothing on the C++ stack
            self.slot(f"t{n}")
        self.block(h.match, indent + 1)
        if h.type is not None:
            self.add(indent + 1, f"if (rt::exception_matches({exc}.get(), t{h.type.n}.get())) {{")
            self.add(indent + 2, f"t{h.type.n} = Ref{{}};")
        else:
            self.add(indent + 1, "if (true) {")
        if h.name is not None:
            cleanup = (G.Store(h.name, G.Const(None)), G.Delete(h.name))
            self.add(indent + 2, self.store(h.name, f"Ref::share({exc}.get())"))
            parent = self.cur
            named = self.new_row(parent, self.clears_of(h.body))
            self.enter_row(named, indent + 2)
            self.exits.append(_Exit("flat", restore=parent))
            self.exits.append(_Exit("cleanup", body=cleanup))
            self.add(indent + 2, "{")
            self.region(h.body, indent + 3)
            self.add(indent + 2, "}")
            self.exits.pop()
            self.exits.pop()
            self.cur = parent
            self.add(indent + 2, f"cur1 = {parent};")
            done = self.aux("after")
            if G.falls_through(h.body):
                for st in cleanup:
                    self.stmt(st, indent + 2)
                self.add(indent + 2, f"goto {done};")
            self.add(indent + 2, f"case {self.rows[named].pc}:;")
            for st in cleanup:
                self.stmt(st, indent + 2)
            self.add(indent + 2, f"rt::gen_rethrow(gen1, {named});")
            self.add(indent + 2, f"{done}:;")
        else:
            self.add(indent + 2, "{")
            self.region(h.body, indent + 3)
            self.add(indent + 2, "}")
        self.add(indent + 1, "} else {")
        if h.type is not None:
            self.add(indent + 2, f"t{h.type.n} = Ref{{}};")
        self.flat_chain(handlers, i + 1, row, indent + 2)
        self.add(indent + 1, "}")
        self.add(indent, "}")

    # ---- statements ------------------------------------------------------------------------------

    def add(self, indent: int, text: str) -> None:
        self.out.append("    " * indent + text)

    def region(self, body: tuple[G.Stmt, ...], indent: int) -> None:
        """A block that owns its temporaries: declared here, so unwinding destroys them."""
        temps = sorted(_assigned(body))
        if temps and self.flat and _yields(body):
            for n in temps:
                self.slot(f"t{n}")
        elif temps:
            self.add(indent, "Ref " + ", ".join(f"t{n}" for n in temps) + ";")
        self.block(body, indent)

    def block(self, body: tuple[G.Stmt, ...], indent: int) -> None:
        for s in body:
            self.stmt(s, indent)

    def stmt(self, s: G.Stmt, indent: int) -> None:
        a = self.atom
        match s:
            case G.Line(n):
                self.add(indent, f"frame.line = {n};" + (" rt::detail::enclosing_line(frame, frame.line);" if self.inlined else ""))
            case G.Let(t, G.Yield(value)) if self.flat:
                self.yield_(value, f"t{t.n} = std::move(gen1->sent);", indent)
            case G.Do(G.Yield(value)) if self.flat:
                self.yield_(value, "gen1->sent = Ref{};", indent)
            case G.Let(t, G.YieldFrom(value)) if self.flat:
                self.yield_from(value, f"t{t.n} = std::move(gen1->sent);", indent)
            case G.Do(G.YieldFrom(value)) if self.flat:
                self.yield_from(value, "gen1->sent = Ref{};", indent)
            case G.Let(t, op):
                self.add(indent, f"t{t.n} = {self.op(op)};")
            case G.Do(op):
                self.add(indent, f"{self.op(op)};")
            case G.Release(t):
                self.add(indent, f"t{t.n} = Ref{{}};")
            case G.Store(ref, value):
                self.add(indent, self.store(ref, self.take(value)))
            case G.Delete(ref):
                self.add(indent, self.delete(ref))
            case G.Unpack(targets, value, star):
                # UNPACK_SEQUENCE pops its source: it dies after the unpack, before the targets
                # are used (review 2026-11-03, A9-7)
                arr = self.aux("u")
                self.add(indent, f"{{ Ref {arr}[{len(targets)}]; rt::unpack({self.atom(value)}, {arr}, {star});")
                if isinstance(value, G.Temp):
                    self.add(indent + 1, f"t{value.n} = Ref{{}};")
                for i, t in enumerate(targets):
                    self.add(indent + 1, f"t{t.n} = std::move({arr}[{i}]);")
                self.add(indent, "}")
            case G.If(test, body, orelse):
                self.add(indent, f"if (rt::test(t{test.n})) {{")
                self.block(body, indent + 1)
                if orelse:
                    self.add(indent, "} else {")
                    self.block(orelse, indent + 1)
                self.add(indent, "}")
            case G.IfEnd(t, body, orelse):
                self.add(indent, f"if (rt::is_end(t{t.n})) {{")
                self.block(body, indent + 1)
                if orelse:
                    self.add(indent, "} else {")
                    self.block(orelse, indent + 1)
                self.add(indent, "}")
            case G.Loop(body, holds, orelse):
                ended = self.aux("ended") if orelse else None
                if ended and self.flat:
                    self.int_slots.append(ended)
                    self.add(indent, f"{ended} = 0;")
                elif ended:
                    self.add(indent, f"bool {ended} = false;")
                self.add(indent, "for (;;) {")
                self.exits.append(_Exit("loop", holds=holds, ended=ended))
                self.block(body, indent + 1)
                self.exits.pop()
                self.add(indent, "}")
                if ended:
                    self.add(indent, f"if ({ended}) {{")
                    self.block(orelse, indent + 1)
                    self.add(indent, "}")
            case G.EndLoop():
                self.leave(_ENDLOOP, len(self.exits) - 1, indent)
            case G.Break():
                self.leave(_BREAK, len(self.exits) - 1, indent)
            case G.Continue():
                self.leave(_CONTINUE, len(self.exits) - 1, indent)
            case G.Return(value):
                if any(ex.kind == "finally" for ex in self.exits):
                    self.add(indent, f"ret = {self.take(value)};")
                    self.leave(_RETURN, len(self.exits) - 1, indent)
                else:
                    for ex in reversed(self.exits):
                        if ex.kind == "loop":
                            for h in ex.holds:
                                self.add(indent, f"t{h.n} = Ref{{}};")
                        else:
                            self.cleanup_inline(ex, indent)
                    if self.flat:
                        self.gen_return(self.take(value), indent)
                    else:
                        self.add(indent, f"return {self.take(value)};")
            case G.Raise(exc, cause, has_cause):
                if exc is None:
                    self.add(indent, "rt::reraise();")
                else:
                    self.add(indent, f"rt::raise_type({a(exc)}, {a(cause)}, {str(has_cause).lower()});")
            case G.Try():
                self.try_(s, indent)
            case _:
                raise Unsupported(f"the C++ emitter: statement {type(s).__name__}")

    def leave(self, kind: int, start: int, indent: int) -> None:
        """A return, break, continue or loop end on its way out, from exit `start` outward: a
        handler's `e = None; del e` inline (it cannot raise), a loop's held temporaries released
        where L2 says, and at the first `finally` a jump past its try with the completion noted,
        so that the block runs once, outside the try's own catch (review 2026-11-03, A9-5)."""
        for i in range(start, -1, -1):
            ex = self.exits[i]
            if ex.kind in ("cleanup", "flat", "handling"):
                self.cleanup_inline(ex, indent)
                continue
            if ex.kind == "finally":
                ex.completions.add(kind)
                self.add(indent, f"{ex.flag} = {kind}; goto {ex.flag}_end;")
                return
            # a loop
            if kind == _RETURN:
                for h in ex.holds:
                    self.add(indent, f"t{h.n} = Ref{{}};")
                continue
            if kind in (_BREAK, _ENDLOOP):
                for h in ex.holds:
                    self.add(indent, f"t{h.n} = Ref{{}};")
            if kind == _ENDLOOP and ex.ended:
                self.add(indent, f"{ex.ended} = true;")
            self.add(indent, "continue;" if kind == _CONTINUE else "break;")
            return
        assert kind == _RETURN, "a break or continue outside a loop"
        if self.flat:
            self.gen_return("std::move(ret)", indent)
        else:
            self.add(indent, "return ret;")

    def cleanup_inline(self, ex: _Exit, indent: int) -> None:
        if ex.kind == "cleanup":
            for st in ex.body:
                self.stmt(st, indent)
        elif ex.kind == "flat":                  # a generator's try, left by a jump: its row no longer applies
            self.add(indent, f"cur1 = {ex.restore};")
        elif ex.kind == "handling":              # and a handler's: the exception is no longer being handled
            self.add(indent, f"rt::gen_handling_pop(gen1, {ex.row});")
            self.add(indent, f"cur1 = {ex.restore};")

    def try_(self, s: G.Try, indent: int) -> None:
        if self.flat and _yields((s,)):
            self.flat_try(s, indent)
            return
        if self.flat:                            # a case label may follow: what it declares stays in a block of its own
            self.add(indent, "{")
            self.plain_try(s, indent + 1)
            self.add(indent, "}")
            return
        self.plain_try(s, indent)

    def plain_try(self, s: G.Try, indent: int) -> None:
        if not s.finalbody:
            self.try_handlers(s, indent)
            return
        # try/finally. The normal end, and every return, break or continue leaving the try, reach
        # the label after it with the completion noted; the block runs there once, outside the
        # catch, and the completion goes on outward. On the exception edge the block runs with
        # the exception as the one being handled (a bare raise re-raises it, a new exception
        # takes it as __context__), then it propagates (A9-5, A9-6).
        flag = self.aux("fin")
        ex = _Exit("finally", body=s.finalbody, flag=flag)
        self.add(indent, "{")
        self.add(indent + 1, f"int {flag} = 0;                            // how the try was left")
        self.add(indent + 1, "try {")
        self.exits.append(ex)
        self.try_handlers(G.Try(s.body, s.handlers, s.orelse), indent + 2)
        self.exits.pop()
        e = self.aux("e")
        self.add(indent + 1, f"}} catch (rt::PyError& {e}) {{")
        self.add(indent + 2, f"frame.arrived({e});                     // recorded where it arrived (RL-221)")
        for name in sorted(_synthetic_stored(s.body, self.hidden), key=_creation, reverse=True):
            self.add(indent + 2, f"{self.vars[name]} = rt::none_ref();")   # stack values (RL-186)
        self.add(indent + 2, f"rt::Handling {self.aux('h')}({e}.exc);")
        self.add(indent + 2, "{")
        self.region(s.finalbody, indent + 3)
        self.add(indent + 2, "}")
        self.add(indent + 2, f"rt::rethrow({e});")
        self.add(indent + 1, "}")
        self.add(indent + 1, f"{flag}_end:")
        self.add(indent + 1, "{")
        self.region(s.finalbody, indent + 2)
        self.add(indent + 1, "}")
        for kind in sorted(ex.completions):
            self.add(indent + 1, f"if ({flag} == {kind}) {{")
            self.leave(kind, len(self.exits) - 1, indent + 2)
            self.add(indent + 1, "}")
        self.add(indent, "}")

    def try_handlers(self, s: G.Try, indent: int) -> None:
        if not s.handlers:
            self.add(indent, "{")
            self.region(s.body, indent + 1)
            self.add(indent, "}")
            return
        raised = self.aux("raised")
        e = self.aux("e")
        if s.orelse:
            self.add(indent, f"bool {raised} = false;")
        self.add(indent, "try {")
        self.region(s.body, indent + 1)
        self.add(indent, f"}} catch (rt::PyError& {e}) {{")
        self.add(indent + 1, f"frame.arrived({e});                     // recorded where it arrived (RL-221)")
        synthetic = sorted(_synthetic_stored(s.body, self.hidden), key=_creation, reverse=True)
        for name in synthetic:                   # stack values die during unwinding (RL-186)
            self.add(indent + 1, f"{self.vars[name]} = rt::none_ref();")
        if s.orelse:
            self.add(indent + 1, f"{raised} = true;")
        self.add(indent + 1, f"rt::Handling {self.aux('h')}({e}.exc);")
        self.handlers(s.handlers, 0, e, indent + 1)
        self.add(indent, "}")
        if s.orelse:
            self.add(indent, f"if (!{raised}) {{")
            self.region(s.orelse, indent + 1)
            self.add(indent, "}")

    def handlers(self, handlers: tuple[G.Handler, ...], i: int, exc: str, indent: int) -> None:
        if i == len(handlers):
            self.add(indent, f"rt::rethrow({exc});")
            return
        h = handlers[i]
        self.add(indent, "{")
        self.region(h.match, indent + 1) if h.match else None
        matched = self.aux("h")
        if h.type is not None:
            self.add(indent + 1, f"bool {matched} = rt::exception_matches({exc}.exc.get(), t{h.type.n}.get());")
            self.add(indent + 1, f"t{h.type.n} = Ref{{}};")
        else:
            self.add(indent + 1, f"bool {matched} = true;")
        self.add(indent + 1, f"if ({matched}) {{")
        if h.name is not None:
            cleanup = (G.Store(h.name, G.Const(None)), G.Delete(h.name))
            self.add(indent + 2, self.store(h.name, f"Ref::share({exc}.exc.get())"))
            ex = _Exit("cleanup", body=cleanup)
            self.add(indent + 2, "try {")
            self.exits.append(ex)
            self.region(h.body, indent + 3)
            self.exits.pop()
            self.add(indent + 2, "} catch (...) {")
            for st in cleanup:
                self.stmt(st, indent + 3)
            self.add(indent + 3, "throw;")
            self.add(indent + 2, "}")
            if G.falls_through(h.body):
                for st in cleanup:
                    self.stmt(st, indent + 2)
        else:
            self.region(h.body, indent + 2)
        self.add(indent + 1, "} else {")
        self.handlers(handlers, i + 1, exc, indent + 2)
        self.add(indent + 1, "}")
        self.add(indent, "}")

    def fresh(self) -> int:
        self.counter += 1
        return self.counter

    def aux(self, base: str) -> str:
        """A name of the emitter's own, which no escaped Python name can be."""
        name = f"{base}{self.fresh()}"
        assert _COMPILER_NAME.match(name), name
        return name

    # ---- names -------------------------------------------------------------------------------

    def take(self, a: G.Atom) -> str:
        """A consumed operand as a Ref: a temporary moved, a constant shared."""
        if isinstance(a, G.Temp):
            return f"std::move(t{a.n})"
        return f"Ref::share({self.const(a.value)})"

    def load(self, r: G.NameRef) -> str:
        match r.kind:
            case "local":
                return f"rt::load_fast({self.vars[r.id]}, {c_string(r.id)})"
            case "cell":
                return f"rt::load_deref({self.vars[r.id]}, {c_string(r.id)}, false)"
            case "free":
                return f"rt::load_deref({self.vars[r.id]}, {c_string(r.id)}, true)"
            case "global":
                return f"rt::load_global(M, {self.name(r.id)})"
            case "name" if r.mapping == "module":    # in a comprehension inlined into the module's code
                return f"rt::load_module_name(M, {self.name(r.id)})"
            case "name":
                return f"rt::load_name(ns, M, {self.name(r.id)})"
            case "classdict":
                # LOAD_FROM_DICT_OR_GLOBALS / _OR_DEREF: the class namespace first
                mapping = "ns" if r.mapping == "locals" else f"rt::cell_contents({self.vars['__classdict__']})"
                if r.then == "global":
                    return f"rt::load_classdict({mapping}, M, {self.name(r.id)})"
                return f"rt::load_classdict_free({mapping}, {self.name(r.id)}, {self.vars[r.id]}, {c_string(r.id)})"
        raise Unsupported(f"the C++ emitter: a {r.kind} load of {r.id}")

    def store(self, r: G.NameRef, value: str) -> str:
        match r.kind:
            case "local":
                return f"{self.vars[r.id]} = {value};"
            case "cell" | "free":
                return f"rt::store_deref({self.vars[r.id]}, {value});"
            case "global":
                return f"rt::store_global(M, {self.name(r.id)}, {value});"
            case "name":
                return f"rt::store_name(ns, {self.name(r.id)}, {value});"
        raise Unsupported(f"the C++ emitter: a {r.kind} store to {r.id}")

    def delete(self, r: G.NameRef) -> str:
        match r.kind:
            case "local":
                return f"rt::delete_fast({self.vars[r.id]}, {c_string(r.id)});"
            case "cell" | "free":
                return f"rt::delete_deref({self.vars[r.id]}, {c_string(r.id)});"
            case "global":
                return f"rt::delete_global(M, {self.name(r.id)});"
            case "name":
                return f"rt::delete_name(ns, {self.name(r.id)});"
        raise Unsupported(f"the C++ emitter: a {r.kind} delete of {r.id}")

    # ---- operations ------------------------------------------------------------------------------

    def op(self, o: G.Op) -> str:
        a = self.atom
        match o:
            case G.Load(ref):
                return self.load(ref)
            case G.Copy(x):
                return f"Ref::share({a(x)})"
            case G.Locals():
                return "Ref::share(ns)"
            case G.CellOf(ref):
                return f"Ref::share({self.vars[ref.id]}.get())"
            case G.Builtin(name):
                return f"rt::builtin({c_string(name)})"
            case G.Binary(op, x, y):
                return f"rt::binary(rt::BinOp::{_BINARY[op]}, {a(x)}, {a(y)})"
            case G.InPlace(op, x, y):
                return f"rt::inplace(rt::BinOp::{_BINARY[op.rstrip('=')]}, {a(x)}, {a(y)})"
            case G.Unary(op, x):
                return f"rt::{_UNARY[op]}({a(x)})"
            case G.Not(x):
                return f"Ref::steal(rt::boolean(!rt::is_true_obj({a(x)})))"
            case G.Truth(x):
                return f"rt::truth_ref({a(x)})"
            case G.Compare(op, x, y):
                return f"rt::compare(rt::CmpOp::{_COMPARE[op]}, {a(x)}, {a(y)})"
            case G.GetAttr(obj, name):
                return f"rt::getattr({a(obj)}, {self.name(name)})"
            case G.SetAttr(obj, name, value):
                return f"rt::setattr({a(obj)}, {self.name(name)}, {a(value)})"
            case G.DelAttr(obj, name):
                return f"rt::delattr({a(obj)}, {self.name(name)})"
            case G.GetItem(obj, key):
                return f"rt::getitem({a(obj)}, {a(key)})"
            case G.SetItem(obj, key, value):
                return f"rt::setitem({a(obj)}, {a(key)}, {a(value)})"
            case G.DelItem(obj, key):
                return f"rt::delitem({a(obj)}, {a(key)})"
            case G.Iter(x):
                return f"rt::iter({a(x)})"
            case G.ForNext(it):
                return f"rt::for_next({a(it)})"
            case G.Call(f, args, kw):
                pos = ", ".join(map(a, args))
                if not kw:
                    return f"rt::invoke({a(f)}, {{{pos}}})"
                names = ", ".join(self.name(k) for k, _ in kw)
                values = ", ".join(a(v) for _, v in kw)
                return f"rt::invoke_kw({a(f)}, {{{pos}}}, {{{names}}}, {{{values}}})"
            case G.CallEx(f, args, kwargs):
                return f"rt::call_ex({a(f)}, {a(args)}, {a(kwargs)})"
            case G.Runtime(name, args, kw):
                ns = "ns" if self.code.kind in ("module", "classbody") else "Obj{}"
                tail = ""
                if kw:
                    tail = (f", {{{', '.join(self.name(k) for k, _ in kw)}}}, {{{', '.join(a(v) for _, v in kw)}}}")
                return f"rt::runtime_call({c_string(name)}, {ns}, M, {{{', '.join(map(a, args))}}}{tail})"
            case G.BuildList(items):
                return f"rt::build_list({{{', '.join(map(a, items))}}})"
            case G.BuildTuple(items):
                return f"rt::build_tuple({{{', '.join(map(a, items))}}})"
            case G.BuildMap(keys, values):
                return f"rt::build_map({{{', '.join(map(a, keys))}}}, {{{', '.join(map(a, values))}}})"
            case G.BuildSet(items, folded):
                return f"rt::{'build_folded_set' if folded else 'build_set'}({{{', '.join(map(a, items))}}})"
            case G.SetAdd(t, v):
                return f"rt::set_add({a(t)}, {a(v)})"
            case G.SetUpdate(t, v):
                return f"rt::set_update({a(t)}, {a(v)})"
            case G.ListAppend(t, v):
                return f"rt::list_append({a(t)}, {a(v)})"
            case G.ListExtend(t, v):
                return f"rt::list_extend_star({a(t)}, {a(v)})"
            case G.ListToTuple(x):
                return f"rt::list_to_tuple({a(x)})"
            case G.DictUpdate(t, v):
                return f"rt::dict_update({a(t)}, {a(v)})"
            case G.DictMerge(t, v, f):
                return f"rt::dict_merge({a(t)}, {a(v)}, {a(f)})"
            case G.MapAdd(t, k, v):
                return f"rt::setitem({a(t)}, {a(k)}, {a(v)})"
            case G.MakeFunction(code, defaults, kwdefaults, closure, annotate):
                fn = self.by_code[id(code)]
                cells = ", ".join(map(a, closure))
                return (f"rt::make_function({fn.cname}, {fn.entry}, M, {a(defaults)}, {a(kwdefaults)}, "
                        f"{{{cells}}}, {a(annotate)})")
            case G.Yield() | G.YieldFrom():
                return 'throw rt::NotImplemented("yield (step 3b: generators)")'
        return f"(throw rt::NotImplemented({c_string(f'the operation {type(o).__name__} in compiled code')}), Ref{{}})"


def _supported_constant(v: object) -> bool:
    if v is None or v is Ellipsis or type(v) in (bool, str, bytes, float, complex):
        return True
    if type(v) is int:
        return True
    return type(v) is tuple and all(_supported_constant(x) for x in v)


def _ident(qualname: str) -> str:
    """A qualified name as the readable part of a code record's or function's C++ name: the same on
    every run (a non-ASCII character is its code point), and never with `__`, which C++ reserves
    (review 2026-11-03, A9-20). Names this maps alike are told apart by `unique`."""
    text = qualname.replace("<locals>", "locals").replace("<lambda>", "lambda").replace("<module>", "module")
    text = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" if c.isascii() else f"_u{ord(c):x}_"
                   for c in text)
    return re.sub(r"_+", "_", text).strip("_") or "anonymous"


def _nested_codes(body: tuple[G.Stmt, ...]) -> Iterator[G.Code]:
    for s in body:
        op = getattr(s, "op", None)
        if isinstance(op, G.MakeFunction):
            yield op.code
        for name in ("body", "orelse", "finalbody"):
            yield from _nested_codes(getattr(s, name, ()))
        if isinstance(s, G.Try):
            for h in s.handlers:
                yield from _nested_codes(h.match)
                yield from _nested_codes(h.body)


_TEMP = re.compile(r"^t\d+$")


def _yields(body: tuple[G.Stmt, ...]) -> bool:
    """These statements suspend the generator somewhere, a function they make being another's."""
    for s in body:
        match s:
            case G.Let(_, G.Yield() | G.YieldFrom()) | G.Do(G.Yield() | G.YieldFrom()):
                return True
            case G.If() | G.IfEnd() | G.Loop():
                if _yields(s.body) or _yields(s.orelse):
                    return True
            case G.Try():
                if _yields(s.body) or _yields(s.orelse) or _yields(s.finalbody):
                    return True
                if any(_yields(h.match) or _yields(h.body) for h in s.handlers):
                    return True
    return False


def _all_assigned(body: tuple[G.Stmt, ...]) -> set[int]:
    """The temporaries these statements assign that live in a generator's slots, a region that does not yield being its
    own (its temporaries are on the C++ stack, and unwinding drops them)."""
    if not _yields(body):
        return set()
    out = _assigned(body)
    for s in body:
        if isinstance(s, (G.If, G.IfEnd, G.Loop)):
            out |= _all_assigned(s.body) | _all_assigned(s.orelse)
        elif isinstance(s, G.Try):
            out |= _all_assigned(s.body) | _all_assigned(s.orelse) | _all_assigned(s.finalbody)
            for h in s.handlers:
                out |= _all_assigned(h.match) | _all_assigned(h.body)
    return out


def _assigned(body: tuple[G.Stmt, ...]) -> set[int]:
    """The temporaries a region assigns, nested regions excluded (a try body, a handler and a
    finally block own theirs); if-branches and loops belong to the region."""
    out: set[int] = set()
    for s in body:
        if isinstance(s, G.Let):
            out.add(s.t.n)
        elif isinstance(s, G.Unpack):
            out.update(t.n for t in s.targets)
        if isinstance(s, (G.If, G.IfEnd, G.Loop)):
            out |= _assigned(s.body) | _assigned(s.orelse)
    return out


def _synthetic_stored(body: tuple[G.Stmt, ...], hidden: frozenset[str]) -> set[str]:
    out: set[str] = set()
    for s in body:
        if isinstance(s, G.Store) and s.ref.id in hidden:
            out.add(s.ref.id)
        for name in ("body", "orelse", "finalbody"):
            out |= _synthetic_stored(getattr(s, name, ()), hidden)
        if isinstance(s, G.Try):
            for h in s.handlers:
                out |= _synthetic_stored(h.match, hidden) | _synthetic_stored(h.body, hidden)
    return out


def _creation(name: str) -> int:
    digits = len(name) - len(name.rstrip("0123456789"))
    return int(name[-digits:]) if digits else -1


def _hidden(code: G.Code) -> frozenset[str]:
    hidden = dict(code.meta).get("hidden", frozenset())
    return frozenset(n for n in hidden if isinstance(n, str)) if isinstance(hidden, frozenset) else frozenset()


def _returns_through_finally(body: tuple[G.Stmt, ...], in_finally: bool = False) -> bool:
    for s in body:
        if isinstance(s, G.Return) and in_finally:
            return True
        if isinstance(s, G.Try):
            inside = in_finally or bool(s.finalbody)
            if _returns_through_finally(s.body, inside) or _returns_through_finally(s.orelse, inside):
                return True
            if any(_returns_through_finally(h.body, inside) for h in s.handlers):
                return True
            if _returns_through_finally(s.finalbody, in_finally):
                return True
        elif isinstance(s, (G.If, G.IfEnd, G.Loop)):
            if _returns_through_finally(s.body, in_finally) or _returns_through_finally(s.orelse, in_finally):
                return True
    return False


def emit_module(module: G.Module, namespace: str, filename: str, prelude: bool = False) -> str:
    return Emitter(module, namespace, filename, prelude).emit()
