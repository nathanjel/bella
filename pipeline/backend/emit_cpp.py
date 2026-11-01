"""Toy C++ emitter: L1 -> readable C++ for integer programs.

This is the end of the first complete compilation path (Gate 0, item 4), not a design for
the real backend: it skips L2-L4 and assumes every value is an exact ``bella::Int`` (or a
``bool`` from a comparison, or a string literal passed to print). Everything else raises
``Unsupported`` naming the construct. What it does keep from the design: Python identifiers,
``//`` and ``%`` lowered to the runtime's floor helpers, ``for`` over ``range`` as a loop
whose variable survives the loop, for/while ``else`` through a break flag, left-to-right
evaluation (each operand bound to a temporary where C++ would not guarantee the order).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.l1 import grammar as L
from pipeline.l1.grammar import Unsupported

_INT_BIN = {"+": "({l} + {r})", "-": "({l} - {r})", "*": "({l} * {r})", "//": "bella::int_floordiv({l}, {r})",
            "%": "bella::int_mod({l}, {r})", "**": "bella::int_pow({l}, {r})", "<<": "({l} << {r})",
            ">>": "({l} >> {r})", "&": "({l} & {r})", "|": "({l} | {r})", "^": "({l} ^ {r})"}
_CMP = {"<": "<", "<=": "<=", "==": "==", "!=": "!=", ">": ">", ">=": ">="}


@dataclass
class _Fn:
    name: str
    params: list[str]
    locals_: list[str] = field(default_factory=list)
    returns_value: bool = False


def _assigned(stmts: tuple[L.Stmt, ...], out: list[str]) -> None:
    for s in stmts:
        if isinstance(s, (L.Assign, L.AugAssign)) and isinstance(s.target, L.NameTarget):
            if s.target.id not in out:
                out.append(s.target.id)
        elif isinstance(s, L.For):
            if isinstance(s.target, L.NameTarget) and s.target.id not in out:
                out.append(s.target.id)
            _assigned(s.body, out)
            _assigned(s.orelse, out)
        elif isinstance(s, (L.If, L.While)):
            _assigned(s.body, out)
            _assigned(s.orelse, out)


def _returns_value(stmts: tuple[L.Stmt, ...]) -> bool:
    for s in stmts:
        if isinstance(s, L.Return) and s.value is not None:
            return True
        if isinstance(s, (L.If, L.While, L.For)) and (_returns_value(s.body) or _returns_value(s.orelse)):
            return True
    return False


class Emitter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent = 0
        self.fn: _Fn | None = None
        self.functions: dict[str, L.FunctionDef] = {}
        self.module_names: list[str] = []
        self.tmp = 0

    # ---- output helpers ---------------------------------------------------------------------
    def emit(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def fresh(self, prefix: str) -> str:
        self.tmp += 1
        return f"_{prefix}{self.tmp}"

    # ---- kinds (the toy's whole type system) ----------------------------------------------
    def kind(self, e: L.Expr) -> str:
        if isinstance(e, L.Const):
            if isinstance(e.value, bool):
                return "bool"
            if isinstance(e.value, int):
                return "int"
            if isinstance(e.value, str):
                return "str"
            raise Unsupported(f"constant {e.value!r} (toy emitter handles int, bool and str literals)")
        if isinstance(e, (L.Name, L.BinOp, L.UnaryOp, L.Call)):
            return "int"
        if isinstance(e, (L.Compare, L.Truth, L.Not)):
            return "bool"
        if isinstance(e, L.BoolOp):
            lk, rk = self.kind(e.left), self.kind(e.right)
            if lk != rk:
                raise Unsupported(f"and/or with mixed operand kinds {lk}/{rk} (line {e.line})")
            return lk
        if isinstance(e, L.IfExp):
            return self.kind(e.body)
        raise Unsupported(f"expression {type(e).__name__} (line {e.line})")

    # ---- expressions ------------------------------------------------------------------------
    def expr(self, e: L.Expr) -> str:
        if isinstance(e, L.Const):
            if isinstance(e.value, bool):
                return "true" if e.value else "false"
            if isinstance(e.value, int):
                if not -(2**62) <= e.value < 2**62:
                    raise Unsupported(f"integer literal {e.value} outside the 63-bit immediate range (BigInt)")
                return f"bella::Int(std::int64_t{{{e.value}}})"
            if isinstance(e.value, str):
                return '"' + e.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
            raise Unsupported(f"constant {e.value!r}")
        if isinstance(e, L.Name):
            return e.id
        if isinstance(e, L.BinOp):
            if e.op not in _INT_BIN:
                raise Unsupported(f"operator {e.op} (line {e.line})")
            return _INT_BIN[e.op].format(l=self.expr(e.left), r=self.expr(e.right))
        if isinstance(e, L.UnaryOp):
            if e.op == "-":
                return f"(-{self.expr(e.operand)})"
            if e.op == "~":
                return f"(~{self.expr(e.operand)})"
            return self.expr(e.operand)
        if isinstance(e, L.Compare):
            if e.op not in _CMP:
                raise Unsupported(f"comparison {e.op} (line {e.line})")
            return f"({self.expr(e.left)} {_CMP[e.op]} {self.expr(e.right)})"
        if isinstance(e, L.Truth):
            return f"bella::truth({self.expr(e.operand)})"
        if isinstance(e, L.Not):
            return f"(!{self.expr(e.operand)})"
        if isinstance(e, L.BoolOp):
            k = self.kind(e)
            left, right = self.expr(e.left), self.expr(e.right)
            if k == "bool":
                return f"({left} {'&&' if e.op == 'and' else '||'} {right})"
            # Python returns an operand: bind the left once, decide on its truth, evaluate the right lazily
            cond = "bella::truth(_l)" if e.op == "or" else "!bella::truth(_l)"
            return f"([&]() -> bella::Int {{ bella::Int _l = {left}; return {cond} ? _l : {right}; }})()"
        if isinstance(e, L.IfExp):
            return f"({self.expr(e.test)} ? {self.expr(e.body)} : {self.expr(e.orelse)})"
        if isinstance(e, L.Call):
            if not isinstance(e.func, L.Name):
                raise Unsupported(f"call of a non-name (line {e.line})")
            if e.kwargs:
                raise Unsupported(f"keyword arguments (line {e.line})")
            if e.func.id == "print":
                return self._call("bella::print", e.args, returns_int=False)
            if e.func.id in self.functions:
                return self._call(e.func.id, e.args, returns_int=_returns_value(self.functions[e.func.id].body))
            raise Unsupported(f"call of {e.func.id!r} (line {e.line}; the toy knows print and user functions)")
        raise Unsupported(f"expression {type(e).__name__} (line {e.line})")

    def _call(self, callee: str, args: tuple[L.Expr, ...], returns_int: bool) -> str:
        """C++ leaves argument evaluation order unspecified (GCC goes right to left); Python is
        left to right (C-2-01). Arguments with possible effects are bound to temporaries in order."""
        if all(isinstance(a, (L.Const, L.Name)) for a in args):
            return f"{callee}({', '.join(self.expr(a) for a in args)})"
        binds, names = [], []
        for a in args:
            t = self.fresh("a")
            names.append(t)
            binds.append(f"auto {t} = {self.expr(a)};")
        call = f"{callee}({', '.join(names)})"
        if returns_int:
            return f"([&]() -> bella::Int {{ {' '.join(binds)} return {call}; }})()"
        return f"([&]() {{ {' '.join(binds)} {call}; }})()"

    # ---- statements -------------------------------------------------------------------------
    def block(self, stmts: tuple[L.Stmt, ...]) -> None:
        self.indent += 1
        if not stmts:
            self.emit("/* pass */")
        for s in stmts:
            self.stmt(s)
        self.indent -= 1

    def stmt(self, s: L.Stmt) -> None:
        if isinstance(s, L.ExprStmt):
            self.emit(f"{self.expr(s.value)};")
        elif isinstance(s, L.Assign):
            if not isinstance(s.target, L.NameTarget):
                raise Unsupported(f"assignment target {type(s.target).__name__} (line {s.line})")
            self.emit(f"{s.target.id} = {self.expr(s.value)};")
        elif isinstance(s, L.AugAssign):
            if not isinstance(s.target, L.NameTarget) or s.op not in _INT_BIN:
                raise Unsupported(f"augmented assignment (line {s.line})")
            self.emit(f"{s.target.id} = {_INT_BIN[s.op].format(l=s.target.id, r=self.expr(s.value))};")
        elif isinstance(s, L.Return):
            if self.fn is None:
                raise Unsupported("return outside a function")
            if s.value is None:
                if self.fn.returns_value:
                    raise Unsupported(f"bare return in a function that returns a value (line {s.line})")
                self.emit("return;")
            else:
                self.emit(f"return {self.expr(s.value)};")
        elif isinstance(s, L.If):
            self.emit(f"if ({self.expr(s.test)}) {{")
            self.block(s.body)
            if s.orelse:
                self.emit("} else {")
                self.block(s.orelse)
            self.emit("}")
        elif isinstance(s, L.While):
            self.loop(f"while ({self.expr(s.test)})", s.body, s.orelse)
        elif isinstance(s, L.For):
            self.for_range(s)
        elif isinstance(s, L.Break):
            self.emit("break;")
        elif isinstance(s, L.Continue):
            self.emit("continue;")
        elif isinstance(s, L.Pass):
            self.emit("/* pass */")
        elif isinstance(s, L.FunctionDef):
            raise Unsupported(f"nested function {s.name} (line {s.line})")
        else:
            raise Unsupported(f"statement {type(s).__name__} (line {s.line})")

    def loop(self, head: str, body: tuple[L.Stmt, ...], orelse: tuple[L.Stmt, ...]) -> None:
        if not orelse:
            self.emit(f"{head} {{")
            self.block(body)
            self.emit("}")
            return
        flag = self.fresh("broke")
        self.emit(f"bool {flag} = false;")
        self.emit(f"{head} {{")
        self.indent += 1
        self._block_with_break_flag(body, flag)
        self.indent -= 1
        self.emit("}")
        self.emit(f"if (!{flag}) {{")
        self.block(orelse)
        self.emit("}")

    def _block_with_break_flag(self, stmts: tuple[L.Stmt, ...], flag: str) -> None:
        for s in stmts:
            if isinstance(s, L.Break):
                self.emit(f"{flag} = true;")
                self.emit("break;")
            elif isinstance(s, L.If):
                self.emit(f"if ({self.expr(s.test)}) {{")
                self.indent += 1
                self._block_with_break_flag(s.body, flag)
                self.indent -= 1
                if s.orelse:
                    self.emit("} else {")
                    self.indent += 1
                    self._block_with_break_flag(s.orelse, flag)
                    self.indent -= 1
                self.emit("}")
            else:
                self.stmt(s)

    def for_range(self, s: L.For) -> None:
        it = s.iterable
        if not (isinstance(it, L.Call) and isinstance(it.func, L.Name) and it.func.id == "range"
                and isinstance(s.target, L.NameTarget)):
            raise Unsupported(f"for over something other than range(...) (line {s.line})")
        args = [self.expr(a) for a in it.args]
        if len(args) == 1:
            start, stop, step = "bella::Int(0)", args[0], None
        elif len(args) == 2:
            start, stop, step = args[0], args[1], None
        elif len(args) == 3 and isinstance(it.args[2], L.Const) and isinstance(it.args[2].value, int) and it.args[2].value > 0:
            start, stop, step = args[0], args[1], args[2]
        else:
            raise Unsupported(f"range with a non-literal or non-positive step (line {s.line})")
        var = s.target.id
        stop_tmp = self.fresh("stop")
        self.emit(f"bella::Int {stop_tmp} = {stop};")
        head = f"for ({var} = {start}; {var} < {stop_tmp}; {var} = {var} + {step or 'bella::Int(1)'})"
        self.loop(head, s.body, s.orelse)

    # ---- functions and module ---------------------------------------------------------------
    def function(self, f: L.FunctionDef) -> None:
        if any(p.default is not None for p in f.params):
            raise Unsupported(f"default parameter values in {f.name}")
        rv = _returns_value(f.body)
        locals_: list[str] = []
        _assigned(f.body, locals_)
        self.fn = _Fn(f.name, [p.name for p in f.params], [n for n in locals_ if n not in {p.name for p in f.params}], rv)
        params = ", ".join(f"bella::Int {p.name}" for p in f.params)
        self.emit(f"{'bella::Int' if rv else 'void'} {f.name}({params}) {{")
        self.indent += 1
        for n in self.fn.locals_:
            self.emit(f"bella::Int {n}{{}};")
        self.indent -= 1
        self.block(f.body)
        if rv:
            self.emit("    return bella::Int(0);  // Python's implicit None is unreachable for value-returning toy functions")
        self.emit("}")
        self.emit("")
        self.fn = None

    def module(self, m: L.Module) -> str:
        self.emit("// generated by bella's toy emitter (pipeline/backend/emit_cpp.py) from " + m.source)
        self.emit("#include \"bella/int.hpp\"")
        self.emit("#include <cstdint>")
        self.emit("#include <iostream>")
        self.emit("")
        for s in m.body:
            if isinstance(s, L.FunctionDef):
                self.functions[s.name] = s
        _assigned(m.body, self.module_names)
        for n in self.module_names:
            self.emit(f"static bella::Int {n}{{}};")
        if self.module_names:
            self.emit("")
        for n in self.functions.values():
            self.emit(f"{'bella::Int' if _returns_value(n.body) else 'void'} {n.name}({', '.join('bella::Int ' + p.name for p in n.params)});")
        if self.functions:
            self.emit("")
        for s in m.body:
            if isinstance(s, L.FunctionDef):
                self.function(s)
        self.emit("int main() {")
        self.emit("    try {")
        self.indent += 1
        self.block(tuple(s for s in m.body if not isinstance(s, L.FunctionDef)))
        self.indent -= 1
        self.emit("    } catch (const bella::NotImplemented& e) {")
        self.emit("        std::cerr << \"bella::NotImplemented: \" << e.what() << '\\n';")
        self.emit("        return 1;")
        self.emit("    } catch (const bella::ZeroDivisionError& e) {")
        self.emit("        std::cerr << \"ZeroDivisionError: \" << e.what() << '\\n';")
        self.emit("        return 1;")
        self.emit("    }")
        self.emit("    return 0;")
        self.emit("}")
        return "\n".join(self.lines) + "\n"


def emit(m: L.Module) -> str:
    return Emitter().module(m)
