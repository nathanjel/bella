"""eval2: the executable semantics of L2 (docs/l2.md section 5; decisions of 2026-11-02).

eval2 runs L2 on host objects by translating each code object into a host Python function and
running it. The translation is statement for statement, so what L2 says is what runs:

* Temporaries are host locals (`_l2_t<n>`): `Let` assigns one, `Release` deletes it, and the
  host's reference counting does the rest, so an object dies exactly at the `Release` that drops
  its last reference, and its finaliser and weak-reference callbacks run there.
* The exception edge is generated code: around every `Try` body and every function body, an
  `except BaseException` sets the temporaries that region assigns to None, newest first, and
  re-raises, so they die before any handler runs, while the frame's locals stay with the
  traceback (CPython's `exception_unwind`).
* `local`, `cell` and `free` names are the host function's own variables. The host compiler
  re-derives which name is which from the generated code, and eval2 checks that the code objects
  it gets have exactly L2's slot tables in L2's order: a second, independent check of
  resolve-names (`SlotMismatch`).
* `global`, `name` and `classdict` accesses, and every runtime operation, go through one helper
  object per module (`_Runtime`), reached as a closure variable: the generated functions' globals
  are the module's own namespace and contain nothing else, so C code that reads the calling
  frame's globals sees the program's module, as under CPython.

Names beginning `_l2_` are reserved for the translation.
"""
from __future__ import annotations

import ast
import builtins
import operator
import string.templatelib as templatelib
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipeline.l1 import eval1 as E1
from pipeline.l1.grammar import Refused, Unsupported
from pipeline.l2 import grammar as G

RESERVED = "_l2_"
END = E1._ABSENT                    # the end marker ForNext returns: any private sentinel
_INPLACE: dict[str, Callable[[Any, Any], Any]] = {"+": operator.iadd, "-": operator.isub, "*": operator.imul, "/": operator.itruediv,
            "//": operator.ifloordiv, "%": operator.imod, "**": operator.ipow, "<<": operator.ilshift,
            ">>": operator.irshift, "&": operator.iand, "|": operator.ior, "^": operator.ixor, "@": operator.imatmul}
_CMP = {"<": "<", "<=": "<=", "==": "==", "!=": "!=", ">": ">", ">=": ">=", "in": "in", "not-in": "not in",
        "is": "is", "is-not": "is not"}
_HOST_STATE_NAMES = ("locals", "vars", "dir", "globals", "eval", "exec", "compile")


class SlotMismatch(AssertionError):
    """The host compiler's code object disagrees with L2's slot tables: resolve-names is wrong."""


# ---- the runtime the generated code calls --------------------------------------------------------

class _Runtime:
    """One per module: its namespace (the globals of every function it defines) and the helpers."""

    def __init__(self, interp: Interpreter, g: dict[str, Any]) -> None:
        self.interp = interp
        self.G = g
        self.B = interp.builtins

    # names ------------------------------------------------------------------------------------

    def lg(self, name: str) -> Any:
        """LOAD_GLOBAL: the module's namespace, then builtins."""
        g = self.G
        if name in g:
            return E1._reify(g[name], name, g)
        if name in self.B:
            return E1._reify(self.B[name], name, self.B)
        raise NameError(f"name '{name}' is not defined", name=name)

    def sg(self, name: str, value: Any) -> None:
        self.G[name] = value

    def dg(self, name: str) -> None:
        if name not in self.G:
            raise NameError(f"name '{name}' is not defined", name=name)
        del self.G[name]

    def ln(self, ns: Any, name: str) -> Any:
        """LOAD_NAME: the namespace mapping (a KeyError means absent), then globals, builtins."""
        if ns is not self.G:
            found = True
            try:
                value = ns[name]
            except KeyError:
                found = False
            if found:
                return E1._reify(value, name, ns)
        return self.lg(name)

    def sn(self, ns: Any, name: str, value: Any) -> None:
        ns[name] = value

    def dn(self, ns: Any, name: str) -> None:
        """DELETE_NAME: any failure is a NameError."""
        failed = False
        try:
            del ns[name]
        except Exception:  # noqa: BLE001
            failed = True
        if failed:
            raise NameError(f"name '{name}' is not defined", name=name)

    def lcg(self, mapping: Any, name: str) -> Any:
        """LOAD_FROM_DICT_OR_GLOBALS."""
        found = True
        try:
            value = mapping[name]
        except KeyError:
            found = False
        if found:
            return E1._reify(value, name, mapping)
        return self.lg(name)

    def lcf(self, mapping: Any, name: str, cell: Any) -> Any:
        """LOAD_FROM_DICT_OR_DEREF: the mapping, then the cell (NameError when it is empty)."""
        found = True
        try:
            value = mapping[name]
        except KeyError:
            found = False
        if found:
            return E1._reify(value, name, mapping)
        return cell()

    @staticmethod
    def cell(thunk: Any) -> Any:
        return thunk.__closure__[0]

    # operations -------------------------------------------------------------------------------

    def builtin(self, name: str) -> Any:
        return self.interp.intrinsic_value(name)

    iter = staticmethod(builtins.iter)
    tuple: Any = staticmethod(builtins.tuple)
    set: Any = staticmethod(builtins.set)

    @staticmethod
    def next(it: Any) -> Any:
        return builtins.next(it, END)

    @staticmethod
    def inplace(op: str, a: Any, b: Any) -> Any:
        return _INPLACE[op](a, b)

    @staticmethod
    def unpack(value: Any, before: int, after: int) -> list[Any]:
        return E1.unpack_iterable(value, before, after)

    list_extend = staticmethod(E1._list_extend)
    dict_update = staticmethod(E1._dict_update)
    map_add = staticmethod(E1._map_add)

    @staticmethod
    def set_update(target: Any, value: Any) -> None:
        target.update(value)

    @staticmethod
    def dict_merge(target: dict[str, Any], m: Any, fn: Any) -> None:
        """DICT_MERGE, with _PyEval_FormatKwargsError's errors (as eval1's `arguments`)."""
        failure: TypeError | None = None
        dupkey: tuple[Any] | None = None
        try:
            dupkey = E1._dict_merge(target, m)
        except AttributeError:
            if hasattr(m, "keys"):
                raise
            failure = TypeError(f"Value after ** must be a mapping, not {E1._fully_qualified(type(m))}")
        if failure is not None:
            raise failure
        if dupkey is not None:
            raise TypeError(f"{E1._function_str(fn)} got multiple values for keyword argument '{dupkey[0]}'")

    def make(self, fn: Any, code: G.Code, defaults: Any, kwdefaults: Any, annotate: Any) -> Any:
        """MAKE_FUNCTION's attributes on the host function the nested def made."""
        fn.__name__ = code.name
        fn.__qualname__ = code.qualname
        fn.__defaults__ = defaults
        fn.__kwdefaults__ = kwdefaults
        if code.kind != "classbody":
            fn.__doc__ = code.docstring
        if annotate is not None:
            fn.__annotate__ = annotate
        return fn

    def match(self, exc: BaseException, spec: Any) -> bool:
        return E1._matches(exc, spec)

    @staticmethod
    def refused(what: str) -> Refused:
        return Refused(what)

    def run(self, name: str, ns: Any, *args: Any, **kwargs: Any) -> Any:
        """An L1 intrinsic called by name, with the running frame's namespace where it needs one."""
        return self.interp.call_intrinsic(self, name, ns, args, kwargs)

    def host_state(self, fn: Any, ns: Any, frame_locals: Any, hidden: frozenset[str], *args: Any, **kwargs: Any) -> Any:
        """locals(), vars(), dir() and globals() called by name with no arguments: the frame's
        own variables (PEP 667: a fresh dict in a function), never the translation's."""
        if args or kwargs or fn not in (builtins.locals, builtins.vars, builtins.dir, builtins.globals):
            if fn in (builtins.eval, builtins.exec, builtins.compile):
                raise Refused(f"{fn.__name__}() of source text is excluded (E-01)")
            return fn(*args, **kwargs)
        if fn is builtins.globals:
            return self.G
        if ns is not None:
            return sorted(ns.keys()) if fn is builtins.dir else ns
        snapshot = {k: v for k, v in frame_locals.items() if not k.startswith(RESERVED) and k not in hidden}
        return sorted(snapshot) if fn is builtins.dir else snapshot

    @staticmethod
    def call_args_tuple(value: Any) -> builtins.tuple[Any, ...]:
        """_MAKE_CALLARGS_A_TUPLE: _Py_Check_ArgsIterable, then PySequence_Tuple."""
        if type(value) is builtins.tuple:
            return value
        if getattr(type(value), "__iter__", None) is None and not E1._is_sequence(value):
            raise TypeError(f"Value after * must be an iterable, not {E1._tp_name(type(value))}")
        return builtins.tuple(value)


# ---- the translation -----------------------------------------------------------------------------

@dataclass
class _Out:
    lines: list[str] = field(default_factory=list)
    linemap: list[int] = field(default_factory=list)    # generated line (1-based) -> source line

    def add(self, indent: int, text: str, line: int) -> None:
        self.lines.append("    " * indent + text)
        self.linemap.append(line)


class _Translator:
    def __init__(self) -> None:
        self.out = _Out()
        self.codes: dict[str, G.Code] = {}     # reserved def name -> its L2 code
        self.consts: list[Any] = []            # constants with no literal spelling (inf, frozenset)
        self.k = 0

    def fresh(self, prefix: str) -> str:
        self.k += 1
        return f"{RESERVED}{prefix}{self.k}"

    # atoms and names --------------------------------------------------------------------------

    def atom(self, a: G.Atom | None) -> str:
        if a is None:
            return "None"
        if isinstance(a, G.Temp):
            return f"{RESERVED}t{a.n}"
        v = a.value
        if v is None or isinstance(v, (bool, str, bytes)) or (type(v) is int):
            return f"({v!r})"
        self.consts.append(v)
        return f"{RESERVED}K[{len(self.consts) - 1}]"

    def load(self, r: G.NameRef) -> str:
        if r.kind in ("local", "cell", "free"):
            return r.id
        if r.kind == "global":
            return f"{RESERVED}R.lg({r.id!r})"
        if r.kind == "name":
            return f"{RESERVED}R.ln({RESERVED}ns, {r.id!r})"
        mapping = f"{RESERVED}ns" if r.mapping == "locals" else "__classdict__"
        if r.then == "global":
            return f"{RESERVED}R.lcg({mapping}, {r.id!r})"
        return f"{RESERVED}R.lcf({mapping}, {r.id!r}, lambda: {r.id})"

    def store(self, r: G.NameRef, value: str) -> str:
        if r.kind in ("local", "cell", "free"):
            return f"{r.id} = {value}"
        if r.kind == "global":
            return f"{RESERVED}R.sg({r.id!r}, {value})"
        if r.kind == "name":
            return f"{RESERVED}R.sn({RESERVED}ns, {r.id!r}, {value})"
        raise Unsupported(f"eval2: a store to {r.kind} {r.id}")

    def delete(self, r: G.NameRef) -> str:
        if r.kind in ("local", "cell", "free"):
            return f"del {r.id}"
        if r.kind == "global":
            return f"{RESERVED}R.dg({r.id!r})"
        if r.kind == "name":
            return f"{RESERVED}R.dn({RESERVED}ns, {r.id!r})"
        raise Unsupported(f"eval2: a delete of {r.kind} {r.id}")

    # operations -------------------------------------------------------------------------------

    def op(self, o: G.Op, code: G.Code, indent: int, line: int, sources: dict[int, G.Op]) -> str:
        a = self.atom
        R = f"{RESERVED}R"
        match o:
            case G.Load(r):
                return self.load(r)
            case G.Copy(x):
                return a(x)
            case G.Locals():
                return f"{RESERVED}ns"
            case G.CellOf(r):
                return f"{R}.cell(lambda: {r.id})"
            case G.Builtin(name):
                return f"{R}.builtin({name!r})"
            case G.Binary(op_, x, y):
                return f"{a(x)} {op_} {a(y)}"
            case G.InPlace(op_, x, y):
                return f"{R}.inplace({op_!r}, {a(x)}, {a(y)})"
            case G.Unary(op_, x):
                return f"{op_}{a(x)}"
            case G.Not(x):
                return f"not {a(x)}"
            case G.Truth(x):
                return f"(True if {a(x)} else False)"
            case G.Compare(op_, x, y):
                return f"{a(x)} {_CMP[op_]} {a(y)}"
            case G.GetAttr(obj, name, _):
                return f"{a(obj)}.{name}"
            case G.SetAttr(obj, name, value):
                return f"{a(obj)}.{name} = {a(value)}"
            case G.DelAttr(obj, name):
                return f"del {a(obj)}.{name}"
            case G.GetItem(obj, key):
                return f"{a(obj)}[{a(key)}]"
            case G.SetItem(obj, key, value):
                return f"{a(obj)}[{a(key)}] = {a(value)}"
            case G.DelItem(obj, key):
                return f"del {a(obj)}[{a(key)}]"
            case G.Iter(x):
                return f"{R}.iter({a(x)})"
            case G.ForNext(it):
                return f"{R}.next({a(it)})"
            case G.Call(f, args, kw):
                parts = [*map(a, args), *(f"{k}={a(v)}" for k, v in kw)]
                src = sources.get(f.n) if isinstance(f, G.Temp) else None
                if isinstance(src, G.Load) and src.ref.id in _HOST_STATE_NAMES and src.ref.kind != "local":
                    # locals(), vars(), dir(): the frame's variables, never the translation's
                    ns = f"{RESERVED}ns" if code.kind in ("module", "classbody") else "None"
                    hidden = a(G.Const(_hidden(code)))
                    return f"{R}.host_state({', '.join([a(f), ns, f'{RESERVED}locals_()', hidden, *parts])})"
                return f"{a(f)}({', '.join(parts)})"
            case G.CallEx(f, args, kwargs):
                return f"{a(f)}(*{a(args)})" if kwargs is None else f"{a(f)}(*{a(args)}, **{a(kwargs)})"
            case G.Runtime(name, args, kw):
                ns = f"{RESERVED}ns" if code.kind in ("module", "classbody") else "None"
                parts = [repr(name), ns, *map(a, args), *(f"{k}={a(v)}" for k, v in kw)]
                return f"{R}.run({', '.join(parts)})"
            case G.BuildList(items):
                return f"[{', '.join(map(a, items))}]"
            case G.BuildTuple(items):
                return f"({', '.join(map(a, items))}{',' if len(items) == 1 else ''})"
            case G.BuildSet(items):
                return f"{{{', '.join(map(a, items))}}}" if items else f"{R}.set()"
            case G.BuildMap(keys, values):
                return "{" + ", ".join(f"{a(k)}: {a(v)}" for k, v in zip(keys, values, strict=True)) + "}"
            case G.ListExtend(t, v):
                return f"{R}.list_extend({a(t)}, {a(v)})"
            case G.ListAppend(t, v):
                return f"{a(t)}.append({a(v)})"
            case G.SetUpdate(t, v):
                return f"{R}.set_update({a(t)}, {a(v)})"
            case G.SetAdd(t, v):
                return f"{a(t)}.add({a(v)})"
            case G.DictUpdate(t, v):
                return f"{R}.dict_update({a(t)}, {a(v)})"
            case G.DictMerge(t, v, f):
                return f"{R}.dict_merge({a(t)}, {a(v)}, {a(f)})"
            case G.MapAdd(t, k, v):
                return f"{R}.map_add({a(t)}, {a(k)}, {a(v)})"
            case G.ListToTuple(x):
                return f"{R}.tuple({a(x)})"
            case G.Yield(x):
                return f"(yield {a(x)})"
            case G.YieldFrom(x):
                return f"(yield from {a(x)})"
        raise Unsupported(f"eval2: operation {type(o).__name__}")

    # code objects ------------------------------------------------------------------------------

    def function(self, code: G.Code, indent: int, line: int) -> str:
        """Emits a nested def for `code`; returns its reserved name."""
        for n in (*code.varnames, *code.cellvars, *code.freevars):
            if n.startswith(RESERVED):
                raise Unsupported(f"eval2: the name {n!r} is reserved for the translation")
        name = self.fresh("c")
        self.codes[name] = code
        params = self.params(code)
        head = "async def" if code.kind in ("coroutine", "async generator") else "def"
        self.out.add(indent, f"{head} {name}({params}):", code.first_line or line)
        body_indent = indent + 1
        first = code.first_line or line
        param_names = {p.name for p in code.params}
        declared = [n for n in (*code.varnames, *code.cellvars) if n not in param_names]
        if declared:
            # dead assignments the symbol table sees: every local and cell of L2 is one for the
            # host, in L2's order (co_varnames follows first appearance, dead code included),
            # and a cell nothing assigns starts empty (a class's __class__, a walrus target)
            self.out.add(body_indent, f"if False: {' = '.join(dict.fromkeys(declared))} = None", first)
        if code.kind == "generator":
            self.out.add(body_indent, "if False: yield", first)        # a generator even without a yield
        if code.freevars:
            # every free variable L2 records is one for the host too, stored to (a comprehension's
            # walrus target) or not (`super` alone makes __class__ free, symtable.c)
            self.out.add(body_indent, f"nonlocal {', '.join(code.freevars)}", first)
        if code.kind in ("coroutine", "async generator"):
            what = f"running the {'coroutine' if code.kind == 'coroutine' else 'async generator'} {code.qualname}"
            self.out.add(body_indent, f"raise {RESERVED}R.refused({what + ' is [P2+] (async, decision P-1)'!r})", first)
            if code.kind == "async generator":
                self.out.add(body_indent, "yield", first)
            return name
        temps = sorted(_assigned(code.body))
        self.out.add(body_indent, "try:", first)
        sources: dict[int, G.Op] = {}
        self.block(code.body, code, body_indent + 1, first, sources)
        if not code.body:
            self.out.add(body_indent + 1, "pass", first)
        self.out.add(body_indent, "except BaseException:", first)
        self.unwind(temps, body_indent + 1, first)
        self.out.add(body_indent + 1, "raise", first)
        return name

    def params(self, code: G.Code) -> str:
        if code.kind in ("module", "classbody"):
            return f"{RESERVED}ns"
        pos = [p.name for p in code.params if p.kind == "positional-only"]
        normal = [p.name for p in code.params if p.kind == "positional-or-keyword"]
        star = next((p.name for p in code.params if p.kind == "*args"), None)
        kwonly = [p.name for p in code.params if p.kind == "keyword-only"]
        kwargs = next((p.name for p in code.params if p.kind == "**kwargs"), None)
        parts: list[str] = [*pos]
        if pos:
            parts.append("/")
        parts += normal
        if star is not None:
            parts.append(f"*{star}")
        elif kwonly:
            parts.append("*")
        parts += kwonly
        if kwargs is not None:
            parts.append(f"**{kwargs}")
        return ", ".join(parts)

    def unwind(self, temps: list[int], indent: int, line: int) -> None:
        """The exception edge: the region's temporaries die newest first."""
        if temps:
            self.out.add(indent, " = ".join(f"{RESERVED}t{n}" for n in reversed(temps)) + " = None", line)

    # statements --------------------------------------------------------------------------------

    def block(self, body: tuple[G.Stmt, ...], code: G.Code, indent: int, line: int,
              sources: dict[int, G.Op], loop_flag: str | None = None) -> int:
        start = len(self.out.lines)
        for s in body:
            line = self.stmt(s, code, indent, line, sources, loop_flag)
        if len(self.out.lines) == start:
            self.out.add(indent, "pass", line)
        return line

    def stmt(self, s: G.Stmt, code: G.Code, indent: int, line: int, sources: dict[int, G.Op],
             loop_flag: str | None) -> int:
        a = self.atom
        add = self.out.add
        match s:
            case G.Line(n):
                return n
            case G.Let(t, G.Yield(G.Temp() as v)):
                # YIELD_VALUE consumes the value: nothing in the frame holds it while suspended
                add(indent, f"{RESERVED}box = [{a(v)}]", line)
                add(indent, f"del {a(v)}", line)
                add(indent, f"{a(t)} = (yield {RESERVED}box.pop())", line)
            case G.Let(t, o):
                if isinstance(o, G.MakeFunction):
                    fname = self.function(o.code, indent, line)
                    add(indent, f"{a(t)} = {RESERVED}R.make({fname}, {RESERVED}codes[{fname!r}], {a(o.defaults)}, "
                                f"{a(o.kwdefaults)}, {a(o.annotate)})", line)
                    add(indent, f"del {fname}", line)
                else:
                    sources[t.n] = o
                    add(indent, f"{a(t)} = {self.op(o, code, indent, line, sources)}", line)
            case G.Do(G.Yield(G.Temp() as v)):
                add(indent, f"{RESERVED}box = [{a(v)}]", line)
                add(indent, f"del {a(v)}", line)
                add(indent, f"(yield {RESERVED}box.pop())", line)
            case G.Do(o):
                add(indent, self.op(o, code, indent, line, sources), line)
            case G.Unpack(targets, value, star):
                before = len(targets) if star < 0 else star
                after = -1 if star < 0 else len(targets) - star - 1
                names = ", ".join(a(t) for t in targets) + ("," if len(targets) == 1 else "")
                add(indent, f"{names} = {RESERVED}R.unpack({a(value)}, {before}, {after})", line)
                if isinstance(value, G.Temp):
                    add(indent, f"del {a(value)}", line)
            case G.Store(r, v):
                add(indent, self.store(r, a(v)), line)
                if isinstance(v, G.Temp):
                    add(indent, f"del {a(v)}", line)
            case G.Delete(r):
                add(indent, self.delete(r), line)
            case G.Release(t):
                add(indent, f"del {a(t)}", line)
            case G.If(t, body, orelse):
                add(indent, f"if {a(t)}:", line)
                add(indent + 1, f"del {a(t)}", line)
                line = self.block(body, code, indent + 1, line, sources, loop_flag)
                add(indent, "else:", line)
                add(indent + 1, f"del {a(t)}", line)
                line = self.block(orelse, code, indent + 1, line, sources, loop_flag)
            case G.IfEnd(t, body, orelse):
                add(indent, f"if {a(t)} is {RESERVED}END:", line)
                add(indent + 1, f"del {a(t)}", line)
                line = self.block(body, code, indent + 1, line, sources, loop_flag)
                add(indent, "else:", line)
                line = self.block(orelse, code, indent + 1, line, sources, loop_flag)
            case G.Loop(body, holds, orelse):
                flag = self.fresh("e") if orelse else None
                if flag:
                    add(indent, f"{flag} = False", line)
                inner = indent
                if holds:
                    add(indent, "try:", line)
                    inner = indent + 1
                add(inner, "while True:", line)
                self.block(body, code, inner + 1, line, sources, flag or "")
                if holds:
                    add(indent, "finally:", line)
                    add(indent + 1, " = ".join(a(h) for h in holds) + " = None", line)
                if flag:
                    add(indent, f"if {flag}:", line)
                    line = self.block(orelse, code, indent + 1, line, sources, loop_flag)
            case G.Break():
                add(indent, "break", line)
            case G.Continue():
                add(indent, "continue", line)
            case G.EndLoop():
                if loop_flag:
                    add(indent, f"{loop_flag} = True", line)
                add(indent, "break", line)
            case G.Return(v):
                add(indent, f"return {a(v)}", line)
            case G.Raise(exc, cause, has_cause):
                if exc is None:
                    add(indent, "raise", line)
                elif has_cause:
                    add(indent, f"raise {a(exc)} from {a(cause)}", line)
                else:
                    add(indent, f"raise {a(exc)}", line)
            case G.Try():
                line = self.try_(s, code, indent, line, sources, loop_flag)
            case _:
                raise Unsupported(f"eval2: statement {type(s).__name__}")
        return line

    def try_(self, s: G.Try, code: G.Code, indent: int, line: int, sources: dict[int, G.Op],
             loop_flag: str | None) -> int:
        add = self.out.add
        temps = sorted(_assigned(s.body))
        add(indent, "try:", line)
        if temps:
            add(indent + 1, "try:", line)
            self.block(s.body, code, indent + 2, line, sources, loop_flag)
            add(indent + 1, "except BaseException:", line)
            self.unwind(temps, indent + 2, line)
            add(indent + 2, "raise", line)
        else:
            self.block(s.body, code, indent + 1, line, sources, loop_flag)
        if s.handlers:
            exc = self.fresh("x")
            add(indent, f"except BaseException as {exc}:", line)
            inner = indent + 1
            for h in s.handlers:
                # a clause's type is evaluated only when the clauses before it did not match
                if h.match:
                    self.block(h.match, code, inner, line, sources, loop_flag)
                test = "True" if h.type is None else f"{RESERVED}R.match({exc}, {self.atom(h.type)})"
                add(inner, f"if {test}:", line)
                body_indent = inner + 1
                if h.type is not None:
                    add(body_indent, f"del {self.atom(h.type)}", line)
                if h.name is not None:
                    add(body_indent, self.store(h.name, exc), line)
                    add(body_indent, "try:", line)
                    self.block(h.body, code, body_indent + 1, line, sources, loop_flag)
                    add(body_indent, "finally:", line)
                    add(body_indent + 1, self.store(h.name, "None"), line)
                    add(body_indent + 1, self.delete(h.name), line)
                else:
                    self.block(h.body, code, body_indent, line, sources, loop_flag)
                add(inner, "else:", line)
                if h.type is not None:
                    add(inner + 1, f"del {self.atom(h.type)}", line)
                inner += 1
            add(inner, "raise", line)
        if s.orelse:
            if not s.handlers:
                raise Unsupported("eval2: try/else without handlers")
            add(indent, "else:", line)
            line = self.block(s.orelse, code, indent + 1, line, sources, loop_flag)
        if s.finalbody:
            add(indent, "finally:", line)
            line = self.block(s.finalbody, code, indent + 1, line, sources, loop_flag)
        if not s.handlers and not s.finalbody:
            add(indent, "finally:", line)
            add(indent + 1, "pass", line)
        return line


def _hidden(code: G.Code) -> frozenset[str]:
    """The frontend's synthetic locals of a code object: never in what locals() shows."""
    hidden = dict(code.meta).get("hidden", frozenset())
    return frozenset(n for n in hidden if isinstance(n, str)) if isinstance(hidden, frozenset) else frozenset()


def _assigned(body: tuple[G.Stmt, ...]) -> set[int]:
    """Temporaries a region assigns, nested regions included (not nested code objects)."""
    out: set[int] = set()
    for s in body:
        if isinstance(s, G.Let):
            out.add(s.t.n)
        elif isinstance(s, G.Unpack):
            out.update(t.n for t in s.targets)
        for name in ("body", "orelse", "finalbody"):
            out |= _assigned(getattr(s, name, ()))
        if isinstance(s, G.Try):
            for h in s.handlers:
                out |= _assigned(h.match) | _assigned(h.body)
    return out


# ---- compiling and running ----------------------------------------------------------------------

@dataclass
class _Compiled:
    factory: types.CodeType
    codes: dict[str, G.Code]
    consts: list[Any]


def _fix_lines(tree: ast.AST, linemap: list[int]) -> None:
    for node in ast.walk(tree):
        if hasattr(node, "lineno"):
            n = node.lineno
            node.lineno = linemap[n - 1] if 0 < n <= len(linemap) else 1
            if getattr(node, "end_lineno", None) is not None:
                setattr(node, "end_lineno", node.lineno)  # noqa: B010


def _check_slots(code: types.CodeType, codes: dict[str, G.Code]) -> types.CodeType:
    """Checks every nested code object against its L2 code, and gives it CPython's names."""
    consts = tuple(_check_slots(c, codes) if isinstance(c, types.CodeType) else c for c in code.co_consts)
    l2 = codes.get(code.co_name)
    if l2 is None:
        return code.replace(co_consts=consts)

    def visible(names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(n for n in names if not n.startswith(RESERVED))
    host = (visible(code.co_varnames), visible(code.co_cellvars), visible(code.co_freevars))
    want_vars = l2.varnames if l2.kind not in ("module", "classbody") else tuple(n for n in l2.varnames)
    want = (want_vars, l2.cellvars, l2.freevars)
    if l2.kind not in ("coroutine", "async generator") and host != want:
        raise SlotMismatch(f"{l2.qualname}: the host compiled {host}, L2 says {want}")
    return code.replace(co_consts=consts, co_name=l2.name, co_qualname=l2.qualname)


def compile_module(m: G.Module) -> tuple[_Compiled, str]:
    tr = _Translator()
    fname = tr.function(m.code, 1, 1)
    tr.out.lines.insert(0, f"def {RESERVED}factory({RESERVED}R, {RESERVED}codes, {RESERVED}END, {RESERVED}locals_, {RESERVED}K):")
    tr.out.linemap.insert(0, 1)
    tr.out.add(1, f"return {fname}", 1)
    source = "\n".join(tr.out.lines) + "\n"
    tree = ast.parse(source)
    _fix_lines(tree, tr.out.linemap)
    flags = 0
    module_code = compile(tree, m.source, "exec", flags=flags, dont_inherit=True)
    factory = next(c for c in module_code.co_consts if isinstance(c, types.CodeType))
    factory = _check_slots(factory, tr.codes)
    return _Compiled(factory, tr.codes, tr.consts), source


class Interpreter:
    """Runs L2 modules (as eval1's Interpreter runs L1 ones)."""

    def __init__(self, builtins_: dict[str, Any] | None = None) -> None:
        self.builtins = dict(vars(builtins)) if builtins_ is None else builtins_
        self.prelude: dict[str, Any] | None = None
        self.eval1 = E1.Interpreter(self.builtins)

    def run_module(self, m: G.Module, name: str = "__main__") -> dict[str, Any]:
        return self.run_in(m, {"__name__": name})

    def load_runtime(self) -> None:
        self.runtime("build_class")

    def run_in(self, m: G.Module | Any, namespace: dict[str, Any]) -> dict[str, Any]:
        """A module body with `namespace` as its globals; an L1 module is lowered to L2 first
        (the module system hands over L1)."""
        if not isinstance(m, G.Module):
            from pipeline.l2.lifetimes import lifetimes
            from pipeline.l2.lower import to_l2
            m = lifetimes(to_l2(m))
        namespace.setdefault("__builtins__", vars(builtins))
        compiled, _ = compile_module(m)
        rt = _Runtime(self, namespace)
        factory = types.FunctionType(compiled.factory, namespace, f"{RESERVED}factory")
        body = factory(rt, compiled.codes, END, _caller_locals, compiled.consts)
        body(namespace)
        return namespace

    # intrinsics ----------------------------------------------------------------------------------

    def intrinsic_value(self, name: str) -> Any:
        """What eval1's Intrinsic evaluates to, for the names that are values."""
        if name == "build_class":
            return self.runtime("build_class")
        if name == "super":
            return E1.zero_arg_super
        if name == "missing":
            return E1._MISSING
        if name == "import_from":
            return E1.import_from
        if name == "special":
            return E1.special_lookup
        if name == "map_add":
            return E1._map_add
        if name == "set_add":
            return set.add
        if name == "set_type_params":
            return E1._set_type_params
        if name == "unpack":
            return E1.unpack_iterable
        if name == "template":
            return templatelib.Template
        if name == "interpolation":
            return templatelib.Interpolation
        if name in E1._MATCH_HELPERS:
            return self.runtime(E1._MATCH_HELPERS[name])
        return getattr(builtins, name)

    def call_intrinsic(self, rt: _Runtime, name: str, ns: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        if name in ("type_params", "generic_class", "typealias"):
            return E1._pep695(name, list(args), rt.G.get("__name__", "__main__"))
        if name == "setup_annotations":
            assert ns is not None, "SETUP_ANNOTATIONS runs in a module or class body"
            E1.setup_annotations(ns)
            return None
        if name == "import_star":
            assert ns is not None, "import * in a function is a SyntaxError"
            E1.import_star(args[0], ns)
            return None
        if name == "import_name":
            mod, fromlist, level, mode = args
            return E1.import_name(mod, fromlist, level, mode, rt.G, ns)
        if name == "call_args_tuple":
            return _Runtime.call_args_tuple(args[0])
        fn = self.intrinsic_value(name)
        return fn(*args, **kwargs)

    def runtime(self, name: str) -> Any:
        """The Python half of the runtime (runtime/prelude), run by this interpreter."""
        if self.prelude is None:
            from pipeline.l2.lifetimes import lifetimes
            from pipeline.l2.lower import to_l2
            loaded: dict[str, Any] = {}
            for module in ("build_class", "match"):
                lowered = E1._lowered(E1._PRELUDE / f"{module}.py")
                loaded.update(self.run_module(lifetimes(to_l2(lowered)), f"bella.{module}"))
            self.prelude = loaded
        return self.prelude[name]


def _caller_locals() -> dict[str, Any]:
    """The variables of the generated function that called host_state (PEP 667's snapshot)."""
    return dict(sys._getframe(1).f_locals)
