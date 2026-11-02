"""The C++ emitter: one L2 module into one C++26 translation unit against bella/runtime.hpp.

Readable output is a design goal (CLAUDE.md): a Python function becomes a C++ function of its
name, its locals keep their Python names, each L2 statement becomes one C++ statement in the same
order, and `frame.line = n` marks the source lines. The rules (docs/emitter.md):

* Temporaries are `Ref`s declared at the top of their region (a function, a `try` body, a
  handler), in their number order, so C++ unwinding destroys them newest first: L2's exception
  edge (docs/l2.md section 8, decision 1). `release t` is `t = Ref{}`; a store moves its value in
  and releases the old one after the new one is stored.
* A frame is a record and a guard (decision 5): `FrameGuard frame(code_f, a, b)` after the locals.
* C++ has no `finally`: the block is written out on every way out of the `try`, as CPython's
  compiler does: the normal end, the exception edge (`catch (...)`, then rethrow), and before each
  `return`, `break` or `continue` that leaves it, innermost first, with a loop's held iterator
  released where L2 says (after the `finally` blocks nested in the loop).
* What L2 has that the runtime lacks yet compiles to a refusal where it would run (P-1):
  generators and class bodies until steps 3b and 3a.2.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from pipeline.l1.grammar import Unsupported
from pipeline.l2 import grammar as G

_KEYWORDS = frozenset("""alignas alignof and and_eq asm auto bitand bitor bool break case catch char char8_t char16_t
char32_t class compl concept const consteval constexpr constinit const_cast continue co_await co_return co_yield
decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline
int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register
reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template this
thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq
final override import module main std rt Obj Ref Args self args frame ns M ret raised ended handled
""".split())
_EMITTER_NAME = re.compile(r"^(t\d+|K_\d+|S_\w*|code_\w*|f_\w*|py_\w*|c_\w*|e\d+)$")

_BINARY = {"+": "Add", "-": "Sub", "*": "Mul", "/": "TrueDiv", "//": "FloorDiv", "%": "Mod", "**": "Pow",
           "<<": "LShift", ">>": "RShift", "&": "And", "|": "Or", "^": "Xor", "@": "MatMul"}
_COMPARE = {"<": "Lt", "<=": "Le", "==": "Eq", "!=": "Ne", ">": "Gt", ">=": "Ge", "in": "In", "not in": "NotIn",
            "is": "Is", "is not": "IsNot", "not-in": "NotIn", "is-not": "IsNot"}
_UNARY = {"-": "unary_neg", "+": "unary_pos", "~": "unary_invert"}


def cpp_name(name: str) -> str:
    """A Python identifier as a C++ one: kept as written unless C++ reserves it (a keyword, a name
    with `__`, `_` and a capital) or the emitter uses it, then prefixed `py_`."""
    if name in _KEYWORDS or "__" in name or re.match(r"^_[A-Z]", name) or _EMITTER_NAME.match(name):
        return "py_" + name.replace("__", "_U_")
    if not name.isascii():
        return "py_" + "".join(c if c.isascii() and (c.isalnum() or c == "_") else f"_u{ord(c):x}_" for c in name)
    return name


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


@dataclass
class _Exit:
    """An enclosing construct a `return`, `break` or `continue` passes through on its way out."""
    kind: str                                    # "finally" or "loop"
    body: tuple[G.Stmt, ...] = ()                # the finally block
    holds: tuple[G.Temp, ...] = ()               # a loop's held temporaries


@dataclass
class _Function:
    code: G.Code
    cname: str
    entry: str
    lines: list[str] = field(default_factory=list)


class Emitter:
    def __init__(self, module: G.Module, namespace: str, filename: str) -> None:
        self.module = module
        self.namespace = namespace
        self.filename = filename
        self.consts: dict[tuple[str, object], str] = {}
        self.const_init: list[str] = []
        self.names: dict[str, str] = {}
        self.functions: list[_Function] = []
        self.by_code: dict[int, _Function] = {}
        self.used: set[str] = set()

    # ---- names and constants --------------------------------------------------------------

    def unique(self, base: str) -> str:
        name, i = base, 1
        while name in self.used:
            i += 1
            name = f"{base}_{i}"
        self.used.add(name)
        return name

    def name(self, text: str) -> str:
        """An interned name (S_x), for attribute and global access."""
        if text not in self.names:
            ident = re.sub(r"\W", "_", text) if text.isascii() else f"u{len(self.names)}"
            self.names[text] = self.unique("S_" + ident)
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
            return f"rt::unsupported_constant({c_string(f'an int literal beyond 62 bits: {value}')})"
        if type(value) is str:
            return self.lazy(("str", value), f"Obj::of(rt::intern({c_string(value)}))" if value.isascii() or
                             not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
                             else f"rt::str_constant_cps({{{', '.join(f'U{ord(c):#x}' for c in value)}}})")
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

    def collect(self, code: G.Code) -> None:
        cname = self.unique("code_" + _ident(code.qualname))
        entry = self.unique("f_" + _ident(code.qualname)) if code.kind != "module" else "module_body"
        fn = _Function(code, cname, entry)
        self.functions.append(fn)
        self.by_code[id(code)] = fn
        for c in _nested_codes(code.body):
            self.collect(c)

    def emit(self) -> str:
        self.collect(self.module.code)
        bodies = [self.function(fn) for fn in self.functions]
        out = [f"// {self.filename}, compiled by Bella (L2 -> C++26). Generated: do not edit.",
               '#include "bella/runtime.hpp"', "", f"namespace {self.namespace} {{",
               "namespace rt = ::bella;", "using rt::Obj;", "using rt::Ref;", "",
               "static rt::Module* M = nullptr;           // this module"]
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
                out.append(f"static Ref {fn.entry}(rt::PyFunction* self, rt::Args args);")
        out.append("")
        out.append("static void init_constants() {")
        out += self.const_init
        out.append("}")
        out.append("")
        for body in bodies:
            out += body
            out.append("")
        out.append(f"}}  // namespace {self.namespace}")
        return "\n".join(out) + "\n"

    def code_record(self, fn: _Function) -> str:
        c = fn.code
        positional = [p for p in c.params if p.kind in ("positional-only", "positional-or-keyword")]
        posonly = sum(1 for p in c.params if p.kind == "positional-only")
        kwonly = [p for p in c.params if p.kind == "keyword-only"]
        varargs = any(p.kind == "*args" for p in c.params)
        varkw = any(p.kind == "**kwargs" for p in c.params)
        names = [p.public or p.name for p in self.param_order(c)]
        return (f"static const rt::Code {fn.cname}{{{c_string(c.name)}, {c_string(c.qualname)}, {c_string(self.filename)}, "
                f"{c.first_line}, {len(positional)}, {posonly}, {len(kwonly)}, {str(varargs).lower()}, "
                f"{str(varkw).lower()}, {{{', '.join(c_string(n) for n in names)}}}}};")

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
        params = [p.name for p in self.param_order(c)]
        frame_locals = [*c.varnames, *(n for n in c.cellvars if n not in c.varnames), *c.freevars]
        self.vars = {n: cpp_name(n) for n in frame_locals}
        if c.kind == "module":
            head = f"rt::Ref {fn.entry}(rt::Module* m) {{"
            self.out += [f"// the module body of {self.filename}", head, "    M = m;", "    init_constants();",
                         "    Obj ns = Obj::of(m->dict);"]
        else:
            self.out += [f"// {c.kind} {c.qualname}  ({self.filename}:{c.first_line})",
                         f"static Ref {fn.entry}(rt::PyFunction* self, rt::Args args) {{"]
        for n in frame_locals:
            self.out.append(f"    Ref {self.vars[n]};")
        guard = ", ".join(["", *(self.vars[n] for n in frame_locals)])
        self.out.append(f"    rt::FrameGuard frame({fn.cname}{guard});")
        if c.kind != "module":
            if params:
                self.out.append(f"    rt::bind(self, args, {{{', '.join('&' + self.vars[n] for n in params)}}});")
            else:
                self.out.append("    rt::bind(self, args, {});")
            for i, n in enumerate(c.freevars):
                self.out.append(f"    {self.vars[n]} = self->closure[{i}];")
            for n in c.cellvars:
                if n in params:
                    self.out.append(f"    {self.vars[n]} = rt::make_cell({self.vars[n]}.get());")
                else:
                    self.out.append(f"    {self.vars[n]} = rt::make_cell();")
            if c.kind in ("generator", "coroutine", "async generator"):
                self.out.append(f"    throw rt::NotImplemented({c_string(f'running the {c.kind} {c.qualname} (step 3b: generators)')});")
                self.out.append("}")
                return self.out
        if c.kind == "classbody":
            self.out.append(f"    throw rt::NotImplemented({c_string(f'the class body {c.qualname} (step 3a.2: classes)')});")
            self.out.append("}")
            return self.out
        self.region(c.body, 1)
        if _falls_through(c.body):
            self.out.append("    return rt::none_ref();")
        self.out.append("}")
        return self.out

    # ---- statements ------------------------------------------------------------------------------

    def add(self, indent: int, text: str) -> None:
        self.out.append("    " * indent + text)

    def region(self, body: tuple[G.Stmt, ...], indent: int) -> None:
        """A block that owns its temporaries: declared here, so unwinding destroys them."""
        temps = sorted(_assigned(body))
        if temps:
            self.add(indent, "Ref " + ", ".join(f"t{n}" for n in temps) + ";")
        self.block(body, indent)

    def block(self, body: tuple[G.Stmt, ...], indent: int) -> None:
        for s in body:
            self.stmt(s, indent)

    def stmt(self, s: G.Stmt, indent: int) -> None:
        a = self.atom
        match s:
            case G.Line(n):
                self.add(indent, f"frame.line = {n};")
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
                arr = f"u{self.fresh()}"
                self.add(indent, f"{{ Ref {arr}[{len(targets)}]; rt::unpack({self.take_obj(value)}, {arr}, {star});")
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
                ended = f"ended{self.fresh()}" if orelse else None
                if ended:
                    self.add(indent, f"bool {ended} = false;")
                self.add(indent, "for (;;) {")
                self.exits.append(_Exit("loop", holds=holds))
                self.loop_flags = getattr(self, "loop_flags", []) + [ended]
                self.block(body, indent + 1)
                self.exits.pop()
                self.loop_flags.pop()
                self.add(indent, "}")
                if ended:
                    self.add(indent, f"if ({ended}) {{")
                    self.block(orelse, indent + 1)
                    self.add(indent, "}")
            case G.EndLoop():
                self.leave_loop(indent)
                flag = self.loop_flags[-1]
                if flag:
                    self.add(indent, f"{flag} = true;")
                self.add(indent, "break;")
            case G.Break():
                self.leave_loop(indent)
                self.add(indent, "break;")
            case G.Continue():
                for ex in reversed(self.exits):
                    if ex.kind == "loop":
                        break
                    self.finally_inline(ex, indent)
                self.add(indent, "continue;")
            case G.Return(value):
                self.add(indent, f"{{ Ref ret = {self.take(value)};")
                for ex in reversed(self.exits):
                    if ex.kind == "loop":
                        for h in ex.holds:
                            self.add(indent + 1, f"t{h.n} = Ref{{}};")
                    else:
                        self.finally_inline(ex, indent + 1)
                self.add(indent + 1, "return ret; }")
            case G.Raise(exc, cause, has_cause):
                if exc is None:
                    self.add(indent, "rt::reraise();")
                else:
                    self.add(indent, f"rt::raise_type({a(exc)}, {a(cause)}, {str(has_cause).lower()});")
            case G.Try():
                self.try_(s, indent)
            case _:
                raise Unsupported(f"the C++ emitter: statement {type(s).__name__}")

    def leave_loop(self, indent: int) -> None:
        """Break or EndLoop: the finally blocks inside the loop, then the loop's held temporaries."""
        for ex in reversed(self.exits):
            if ex.kind == "loop":
                for h in ex.holds:
                    self.add(indent, f"t{h.n} = Ref{{}};")
                return
            self.finally_inline(ex, indent)

    def finally_inline(self, ex: _Exit, indent: int) -> None:
        """A finally block written out on a way out of its try (outside it, as it runs there)."""
        saved = self.exits
        self.exits = self.exits[: self.exits.index(ex)]
        self.add(indent, "{")
        self.region(ex.body, indent + 1)
        self.add(indent, "}")
        self.exits = saved

    def try_(self, s: G.Try, indent: int) -> None:
        if s.finalbody:
            # try/finally: the finally block on the normal path, on the exception edge, and inline
            # before every return, break or continue that leaves the try (statement above)
            ex = _Exit("finally", body=s.finalbody)
            self.add(indent, "try {")
            self.exits.append(ex)
            self.try_handlers(G.Try(s.body, s.handlers, s.orelse), indent + 1)
            self.exits.pop()
            self.add(indent, "} catch (...) {")
            self.add(indent + 1, "{")
            self.region(s.finalbody, indent + 2)
            self.add(indent + 1, "}")
            self.add(indent + 1, "throw;")
            self.add(indent, "}")
            if _falls_through_try(s):
                self.add(indent, "{")
                self.region(s.finalbody, indent + 1)
                self.add(indent, "}")
            return
        self.try_handlers(s, indent)

    def try_handlers(self, s: G.Try, indent: int) -> None:
        if not s.handlers:
            self.add(indent, "{")
            self.region(s.body, indent + 1)
            self.add(indent, "}")
            return
        n = self.fresh()
        raised = f"raised{n}"
        if s.orelse:
            self.add(indent, f"bool {raised} = false;")
        self.add(indent, "try {")
        self.region(s.body, indent + 1)
        self.add(indent, f"}} catch (rt::PyError& e{n}) {{")
        synthetic = sorted(_synthetic_stored(s.body, self.hidden), key=_creation, reverse=True)
        for name in synthetic:                   # stack values die during unwinding (RL-186)
            self.add(indent + 1, f"{self.vars[name]} = rt::none_ref();")
        if s.orelse:
            self.add(indent + 1, f"{raised} = true;")
        self.add(indent + 1, f"rt::Handling handling{n}(e{n}.exc);")
        self.handlers(s.handlers, 0, f"e{n}", indent + 1)
        self.add(indent, "}")
        if s.orelse:
            self.add(indent, f"if (!{raised}) {{")
            self.region(s.orelse, indent + 1)
            self.add(indent, "}")

    def handlers(self, handlers: tuple[G.Handler, ...], i: int, exc: str, indent: int) -> None:
        if i == len(handlers):
            self.add(indent, "throw;")
            return
        h = handlers[i]
        self.add(indent, "{")
        self.region(h.match, indent + 1) if h.match else None
        if h.type is not None:
            self.add(indent + 1, f"bool match = rt::exception_matches({exc}.exc.get(), t{h.type.n}.get());")
            self.add(indent + 1, f"t{h.type.n} = Ref{{}};")
        else:
            self.add(indent + 1, "bool match = true;")
        self.add(indent + 1, "if (match) {")
        if h.name is not None:
            cleanup = (G.Store(h.name, G.Const(None)), G.Delete(h.name))
            self.add(indent + 2, self.store(h.name, f"Ref::share({exc}.exc.get())"))
            ex = _Exit("finally", body=cleanup)
            self.add(indent + 2, "try {")
            self.exits.append(ex)
            self.region(h.body, indent + 3)
            self.exits.pop()
            self.add(indent + 2, "} catch (...) {")
            for st in cleanup:
                self.stmt(st, indent + 3)
            self.add(indent + 3, "throw;")
            self.add(indent + 2, "}")
            if _falls_through(h.body):
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

    # ---- names -------------------------------------------------------------------------------

    def take(self, a: G.Atom) -> str:
        """A consumed operand as a Ref: a temporary moved, a constant shared."""
        if isinstance(a, G.Temp):
            return f"std::move(t{a.n})"
        return f"Ref::share({self.const(a.value)})"

    def take_obj(self, a: G.Atom) -> str:
        return self.atom(a)

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
            case "name":
                return f"rt::load_name(ns, M, {self.name(r.id)})"
        raise Unsupported(f"the C++ emitter: a {r.kind} load of {r.id} (step 3a.2)")

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
                if kw:
                    raise Unsupported(f"the C++ emitter: keywords to the intrinsic {name}")
                return f"rt::runtime_call({c_string(name)}, {'ns' if self.code.kind in ('module', 'classbody') else 'Obj{}'}, M, {{{', '.join(map(a, args))}}})"
            case G.BuildList(items):
                return f"rt::build_list({{{', '.join(map(a, items))}}})"
            case G.BuildTuple(items):
                return f"rt::build_tuple({{{', '.join(map(a, items))}}})"
            case G.BuildMap(keys, values):
                return f"rt::build_map({{{', '.join(map(a, keys))}}}, {{{', '.join(map(a, values))}}})"
            case G.ListAppend(t, v):
                return f"rt::list_append({a(t)}, {a(v)})"
            case G.ListExtend(t, v):
                return f"rt::list_extend({a(t)}, {a(v)})"
            case G.ListToTuple(x):
                return f"rt::list_to_tuple({a(x)})"
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
    if v is None or v is Ellipsis or type(v) in (bool, str):
        return True
    if type(v) is int:
        return -(1 << 62) <= v < (1 << 62)
    return type(v) is tuple and all(_supported_constant(x) for x in v)


def _ident(qualname: str) -> str:
    text = qualname.replace("<locals>", "locals").replace("<lambda>", "lambda").replace("<module>", "module")
    return re.sub(r"\W", "_", text.replace(".", "__")) if text.isascii() else f"code{abs(hash(text)) % 10**8}"


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


def _falls_through(body: tuple[G.Stmt, ...]) -> bool:
    if not body:
        return True
    last = body[-1]
    if isinstance(last, (G.Return, G.Raise, G.Break, G.Continue, G.EndLoop)):
        return False
    if isinstance(last, (G.If, G.IfEnd)):
        return _falls_through(last.body) or _falls_through(last.orelse)
    if isinstance(last, G.Try):
        return _falls_through_try(last)
    if isinstance(last, G.Loop):
        return True                              # a loop ends by break or end-loop, then falls through
    return True


def _falls_through_try(s: G.Try) -> bool:
    if s.finalbody and not _falls_through(s.finalbody):
        return False
    paths = [_falls_through((*s.body, *s.orelse))] + [_falls_through(h.body) for h in s.handlers]
    return any(paths)


def emit_module(module: G.Module, namespace: str, filename: str) -> str:
    return Emitter(module, namespace, filename).emit()
