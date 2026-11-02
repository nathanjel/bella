"""eval1: the executable semantics of L1.

A reference interpreter for PyCore that delegates every primitive operation to CPython itself
(the semantics of ``+`` on ints, of ``iter``/``next``, of ``isinstance`` are Python's, so the
reference may use them) while implementing the parts L1 makes explicit: scoping and binding,
control flow, the iteration protocol, exception handling, truthiness, function objects.

It is the oracle each later level is tested against: eval2(P(x)) must equal eval1(x).
"""
from __future__ import annotations

import builtins
import operator
import types
from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipeline.l1 import grammar as L

_BIN: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
    "//": operator.floordiv, "%": operator.mod, "**": operator.pow, "<<": operator.lshift,
    ">>": operator.rshift, "&": operator.and_, "|": operator.or_, "^": operator.xor, "@": operator.matmul,
}
_IBIN: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.iadd, "-": operator.isub, "*": operator.imul, "/": operator.itruediv,
    "//": operator.ifloordiv, "%": operator.imod, "**": operator.ipow, "<<": operator.ilshift,
    ">>": operator.irshift, "&": operator.iand, "|": operator.ior, "^": operator.ixor, "@": operator.imatmul,
}
_UN: dict[str, Callable[[Any], Any]] = {"-": operator.neg, "+": operator.pos, "~": operator.invert}
_CMP: dict[str, Callable[[Any, Any], Any]] = {
    "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne, ">": operator.gt,
    ">=": operator.ge, "in": lambda a, b: operator.contains(b, a),
    "not-in": lambda a, b: not operator.contains(b, a), "is": operator.is_, "is-not": operator.is_not,
}


class _Break(BaseException):
    pass


class _Continue(BaseException):
    pass


class _Return(BaseException):
    def __init__(self, value: Any) -> None:
        self.value = value


_SIGNALS = (_Break, _Continue, _Return)


@dataclass
class Scope:
    vars: Any                              # a dict; a class body's is the mapping __prepare__ made
    parent: Scope | None = None            # enclosing scope (closures), None for the module
    locals_: frozenset[str] = frozenset()  # names that are local throughout (Python's rule)
    globals_: frozenset[str] = frozenset()
    nonlocals_: frozenset[str] = frozenset()
    module: Scope | None = None
    # bindings of the frontend's synthetic names (comparison temporaries, comprehension helpers):
    # real bindings for the program's semantics, invisible to globals(), locals() and friends
    temps: dict[str, Any] = field(default_factory=dict)
    synthetic: frozenset[str] = frozenset()   # on a module scope: the names its frontend generated
    is_class: bool = False                 # a class body: invisible to the scopes nested in it
    cell: Any = None                       # a class body's __class__ cell, when it has one
    classdict: Any = None                  # a class body's __classdict__ cell, when it has one
    caller: Any = None                     # on a module scope: caller_for's function

    def is_module(self) -> bool:
        return self.module is None


_MISSING = object()            # the `missing` intrinsic: what super() finds absent


def __bella_call__(fn: Any, args: Any, kwargs: Any) -> Any:
    return fn(*args, **kwargs)


def caller_for(module: Scope) -> Any:
    """The function eval1 makes its calls through, one per module, whose globals are that
    module's: C code that reads the calling frame's globals (type.__new__ filling a missing
    __module__) then sees the program's module, as under CPython, not eval1's. Code that walks
    further up the stack (sys._getframe, sys._getframemodulename) is not served by this."""
    if module.caller is None:
        module.caller = types.FunctionType(__bella_call__.__code__, module.vars, "__bella_call__")
    return module.caller


class ClassBodyFunction:
    """What a ClassBody evaluates to: build_class calls it with the namespace."""

    def __init__(self, interp: Interpreter, node: L.ClassBody, closure: Scope) -> None:
        self.interp, self.node, self.closure = interp, node, closure

    def __call__(self, ns: Any) -> Any:
        return self.interp.run_class_body(self.node, self.closure, ns)


def zero_arg_super(s: Any, cell: Any, first: Any) -> Any:
    """super() with no arguments in a function (super_init_without_args, Objects/typeobject.c):
    a `super` that is not the builtin is called with no arguments; the builtin reads the
    function's first argument and its __class__ cell, with CPython's errors in its order."""
    if s is not builtins.super:
        return s()
    if first is _MISSING:
        raise RuntimeError("super(): no arguments")
    if cell is _MISSING:
        raise RuntimeError("super(): __class__ cell not found")
    empty = False
    try:
        cls = cell.cell_contents
    except ValueError:
        empty = True
    if empty:
        raise RuntimeError("super(): empty __class__ cell")
    if not isinstance(cls, type):
        raise RuntimeError(f"super(): __class__ is not a type ({type(cls).__name__})")
    return builtins.super(cls, first)


_PRELUDE = Path(__file__).resolve().parents[2] / "runtime" / "prelude"
_LOWERED: dict[Path, L.Module] = {}


def _lowered(path: Path) -> L.Module:
    """A runtime module written in Python (runtime/prelude), lowered once per process."""
    if path not in _LOWERED:
        from pipeline.l1.frontend import lower
        from pipeline.l1.wf import check
        module = lower(path.read_text(encoding="utf-8"), path.name)
        check(module)
        _LOWERED[path] = module
    return _LOWERED[path]


def make_function(interp: Interpreter, node: L.FunctionDef | L.Lambda, closure: Scope) -> types.FunctionType:
    """A real CPython function object for an L1 function, so that binding as a method,
    ``staticmethod``, ``functools.wraps`` and ``type.__new__``'s checks see CPython's function
    type (the oracle delegates objects to CPython; the compiled runtime has its own). Calling it
    enters ``Interpreter.call``, which binds the arguments as CPython does, with
    ``__defaults__`` and ``__kwdefaults__`` read when the call happens."""
    module = closure if closure.is_module() else closure.module
    assert module is not None
    name = node.name if isinstance(node, L.FunctionDef) else "<lambda>"

    def __bella_l1__(*args: Any, **kwargs: Any) -> Any:
        return interp.call(fn, node, closure, args, kwargs)

    fn = types.FunctionType(__bella_l1__.__code__, module.vars, name, None, __bella_l1__.__closure__)
    fn.__qualname__ = node.qualname or name
    return fn


def _function_str(fn: Any) -> str:
    """_PyObject_FunctionStr: module.qualname() for a function, qualname() for a builtin."""
    qualname = getattr(fn, "__qualname__", None)
    if qualname is None:
        return str(fn)
    module = getattr(fn, "__module__", None)
    if module is not None and module != "builtins":
        return f"{module}.{qualname}()"
    return f"{qualname}()"


def _tp_name(t: type) -> str:
    return t.__name__ if t.__flags__ & (1 << 9) or t.__module__ == "builtins" else f"{t.__module__}.{t.__qualname__}"


def _fully_qualified(t: type) -> str:
    """%T (_PyType_GetFullyQualifiedName): module.qualname, with no module for builtins and
    __main__."""
    module = t.__module__
    return t.__qualname__ if module in ("builtins", "__main__") else f"{module}.{t.__qualname__}"


def _names(names: list[str]) -> str:
    """format_missing (Python/ceval.c): 'a', 'a' and 'b', 'a', 'b', and 'c'."""
    quoted = [repr(n) for n in names]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return f"{quoted[0]} and {quoted[1]}"
    return ", ".join(quoted[:-2]) + f", {quoted[-2]}, and {quoted[-1]}"


def bind_arguments(fn: types.FunctionType, node: L.FunctionDef | L.Lambda,
                   args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """CPython's initialize_locals (Python/ceval.c), in its order and with its messages:
    positional arguments, ``*args``, keywords (multiple values, positional-only names passed as
    keywords, unexpected names with CPython's suggestion), too many positional arguments, then
    the missing positional and keyword-only ones from ``__defaults__`` and ``__kwdefaults__``."""
    qual = fn.__qualname__
    params = node.params
    # matching and messages use the name CPython has; the binding is made under the L1 name
    internal = {p.public or p.name: p.name for p in params}
    posonly = [p.public or p.name for p in params if p.kind == "positional-only"]
    positional = [p.public or p.name for p in params if p.kind in ("positional-only", "positional-or-keyword")]
    kwonly = [p.public or p.name for p in params if p.kind == "keyword-only"]
    star = next((p.public or p.name for p in params if p.kind == "*args"), None)
    dstar = next((p.public or p.name for p in params if p.kind == "**kwargs"), None)
    bound: dict[str, Any] = {}
    extra: dict[str, Any] | None = {} if dstar is not None else None
    n = min(len(args), len(positional))
    for i in range(n):
        bound[positional[i]] = args[i]
    if star is not None:
        bound[star] = tuple(args[n:])
    by_keyword = positional[len(posonly):] + kwonly
    for k, v in kwargs.items():
        if k in by_keyword:
            if k in bound:
                raise TypeError(f"{qual}() got multiple values for argument '{k}'")
            bound[k] = v
        elif extra is not None:
            extra[k] = v
        else:
            passed = [p for p in posonly if p in kwargs]
            if passed:
                raise TypeError(f"{qual}() got some positional-only arguments passed as keyword arguments: "
                                f"'{', '.join(passed)}'")
            import _suggestions  # type: ignore[import-not-found]  # CPython's own, private: the hint it prints
            hint = _suggestions._generate_suggestions(by_keyword, k) if by_keyword else None
            if hint:
                raise TypeError(f"{qual}() got an unexpected keyword argument '{k}'. Did you mean '{hint}'?")
            raise TypeError(f"{qual}() got an unexpected keyword argument '{k}'")
    defaults = fn.__defaults__ or ()
    if len(args) > len(positional) and star is None:
        given_kwonly = sum(1 for k in kwonly if k in bound)
        if defaults:
            sig, plural = f"from {len(positional) - len(defaults)} to {len(positional)}", True
        else:
            sig, plural = str(len(positional)), len(positional) != 1
        kw = (f" positional argument{'s' if len(args) != 1 else ''} (and {given_kwonly} keyword-only "
              f"argument{'s' if given_kwonly != 1 else ''})") if given_kwonly else ""
        was = "was" if len(args) == 1 and not given_kwonly else "were"
        raise TypeError(f"{qual}() takes {sig} positional argument{'s' if plural else ''} but {len(args)}{kw} {was} given")
    if len(args) < len(positional):
        first_default = len(positional) - len(defaults)
        missing = [name for name in positional[len(args):max(first_default, 0)] if name not in bound]
        if missing:
            raise TypeError(f"{qual}() missing {len(missing)} required positional argument{'s' if len(missing) != 1 else ''}: "
                            f"{_names(missing)}")
        for i, name in enumerate(positional):
            if name not in bound and i - first_default >= 0:
                bound[name] = defaults[i - first_default]
    if kwonly:
        kwdefaults = fn.__kwdefaults__
        missing = []
        for name in kwonly:
            if name in bound:
                continue
            if kwdefaults is not None and name in kwdefaults:
                bound[name] = kwdefaults[name]
            else:
                missing.append(name)
        if missing:
            raise TypeError(f"{qual}() missing {len(missing)} required keyword-only argument{'s' if len(missing) != 1 else ''}: "
                            f"{_names(missing)}")
    if dstar is not None:
        assert extra is not None
        bound[dstar] = extra
    return {internal[k]: v for k, v in bound.items()}


def special_lookup(obj: Any, name: str) -> Any:
    """CPython's special-method lookup (_PyObject_LookupSpecial) as the with-statement uses it:
    the name is looked up on the type's MRO, never on the instance, and bound through the
    descriptor protocol; a missing method is a TypeError. The L1 intrinsic ``__special__``."""
    t = type(obj)
    for k in t.__mro__:
        if name in k.__dict__:
            v = k.__dict__[name]
            get = getattr(type(v), "__get__", None)
            return get(v, obj, t) if get is not None else v
    raise TypeError(f"'{t.__name__}' object does not support the context manager protocol")


def _local_names(f: L.FunctionDef | L.Lambda) -> frozenset[str]:
    from pipeline.l1.wf import _bound_in, _walrus
    out: set[str] = {p.name for p in f.params}
    if isinstance(f, L.Lambda):
        _walrus(f.body, out)
        return frozenset(out)
    _bound_in(f.body, out)
    return frozenset(out - set(f.globals) - set(f.nonlocals))


# Host builtins whose result depends on the *interpreter's* own frames rather than on the program:
# called naively they would hand eval1's state to the program (found 2026-11-01 while reproducing
# gemini 2.2.1). They are intrinsics here, or refused.
_HOST_STATE = (builtins.globals, builtins.locals, builtins.vars, builtins.dir,
               builtins.eval, builtins.exec, builtins.compile)


class Interpreter:
    def __init__(self, builtins_: dict[str, Any] | None = None) -> None:
        self.builtins = dict(vars(builtins)) if builtins_ is None else builtins_
        self.builtins.setdefault("__special__", special_lookup)
        self.prelude: dict[str, Any] | None = None

    # ---- entry ---------------------------------------------------------------------------
    def run_module(self, m: L.Module, name: str = "__main__") -> Scope:
        module = Scope(vars={"__name__": name}, synthetic=m.synthetic)
        self.block(m.body, module)
        return module

    def runtime(self, name: str) -> Any:
        """A function of the Python half of the runtime (runtime/prelude), run by this
        interpreter like any compiled module."""
        if self.prelude is None:
            self.prelude = self.run_module(_lowered(_PRELUDE / "build_class.py"), "bella.build_class").vars
        return self.prelude[name]

    def _syn(self, scope: Scope) -> frozenset[str]:
        return (scope if scope.is_module() else scope.module or scope).synthetic

    def _host_state(self, fn: Any, e: L.Call, scope: Scope) -> Any:
        return _host_state_impl(self, fn, e, scope)

    # ---- names -----------------------------------------------------------------------------
    def _load_synthetic(self, name: str, scope: Scope) -> Any:
        s: Scope | None = scope
        while s is not None:
            if name in s.temps:
                return s.temps[name]
            s = s.parent
        if scope.module is not None and name in scope.module.temps:
            return scope.module.temps[name]
        raise NameError(f"synthetic name '{name}' is unbound", name=name)

    def load(self, name: str, scope: Scope, line: int) -> Any:
        if name in self._syn(scope):
            return self._load_synthetic(name, scope)
        if scope.is_module():
            if name in scope.vars:
                return scope.vars[name]
            if name in self.builtins:
                return self.builtins[name]            # fall-through to builtins (C-8-02)
            raise NameError(f"name '{name}' is not defined", name=name)
        module = scope.module or scope
        if name in scope.globals_:
            return self.load(name, module, line)
        if scope.is_class:
            if name not in scope.nonlocals_:
                # LOAD_NAME and LOAD_FROM_DICT_OR_DEREF read the namespace first, through the
                # mapping (a KeyError means absent)
                found = True
                try:
                    value = scope.vars[name]
                except KeyError:
                    found = False
                if found:
                    return value
                if name in scope.locals_:
                    return self.load(name, module, line)   # bound in the body: globals, builtins
        elif name in scope.locals_:
            if name in scope.vars:
                return scope.vars[name]
            # CPython 3.15 leaves UnboundLocalError.name as None (measured; NameError carries it)
            raise UnboundLocalError(f"cannot access local variable '{name}' where it is not associated with a value")
        s: Scope | None = scope.parent
        while s is not None and not s.is_module():
            if s.is_class:
                # a class body's names are invisible to what is nested in it, except the
                # __class__ cell of the nearest class a function is in
                if name == "__class__" and s.cell is not None and not scope.is_class:
                    empty = False
                    try:
                        return s.cell.cell_contents
                    except ValueError:
                        empty = True
                    if empty:
                        raise NameError("cannot access free variable '__class__' where it is not associated with a "
                                        "value in enclosing scope", name="__class__")
                s = s.parent
                continue
            if name in s.vars:
                return s.vars[name]
            if name in s.locals_:
                # a free variable whose binding in the enclosing function does not exist (yet):
                # NameError, never the global of the same name (review 2026-11-01, gemini 2.2.5.3)
                raise NameError(f"cannot access free variable '{name}' where it is not associated with a value "
                                "in enclosing scope", name=name)
            s = s.parent
        return self.load(name, module, line)

    def _enclosing_binding(self, name: str, scope: Scope) -> Scope:
        """The function scope a nonlocal name belongs to (class bodies skipped)."""
        s: Scope | None = scope.parent
        while s is not None and not s.is_module():
            if not s.is_class and (name in s.locals_ or name in s.vars):
                return s
            s = s.parent
        raise SyntaxError(f"no binding for nonlocal '{name}' found")

    def store(self, name: str, value: Any, scope: Scope) -> None:
        if name in self._syn(scope):
            scope.temps[name] = value
            return
        if name in scope.globals_:
            assert scope.module is not None
            scope.module.vars[name] = value
            return
        if name in scope.nonlocals_:
            self._enclosing_binding(name, scope).vars[name] = value
            return
        scope.vars[name] = value           # a class body stores through its mapping

    def delete(self, name: str, scope: Scope) -> None:
        """Python's del of a name (review 2026-11-01, gemini 2.2.5.4): an unbound local raises
        UnboundLocalError, a nonlocal deletes the enclosing binding, a global the module's, and
        a class body deletes through its mapping (any failure is NameError, DELETE_NAME)."""
        if scope.is_module() or name in scope.globals_:
            module = scope if scope.is_module() else scope.module
            assert module is not None
            if name not in module.vars:
                raise NameError(f"name '{name}' is not defined", name=name)
            del module.vars[name]
            return
        if name in scope.nonlocals_:
            s = self._enclosing_binding(name, scope)
            if name not in s.vars:
                raise NameError(f"cannot access free variable '{name}' where it is not associated with a value "
                                "in enclosing scope", name=name)
            del s.vars[name]
            return
        if scope.is_class:
            failed = False
            try:
                del scope.vars[name]
            except Exception:  # noqa: BLE001  # DELETE_NAME replaces any failure with NameError
                failed = True
            if failed:
                raise NameError(f"name '{name}' is not defined", name=name)
            return
        if name not in scope.vars:
            raise UnboundLocalError(f"cannot access local variable '{name}' where it is not associated with a value")
        del scope.vars[name]

    # ---- statements ------------------------------------------------------------------------
    def block(self, stmts: tuple[L.Stmt, ...], scope: Scope) -> None:
        for s in stmts:
            self.stmt(s, scope)

    def assign(self, t: L.Target, value: Any, scope: Scope) -> None:
        if isinstance(t, L.NameTarget):
            self.store(t.id, value, scope)
        elif isinstance(t, L.AttrTarget):
            setattr(self.expr(t.obj, scope), t.name, value)
        elif isinstance(t, L.ItemTarget):
            self.expr(t.obj, scope)[self.expr(t.key, scope)] = value
        elif isinstance(t, L.TupleTarget):
            items = list(value)
            if len(items) != len(t.elts):
                raise ValueError(f"expected {len(t.elts)} values, got {len(items)}")
            for sub, v in zip(t.elts, items, strict=True):
                self.assign(sub, v, scope)
        else:
            raise TypeError(f"unknown target {t}")

    def stmt(self, s: L.Stmt, scope: Scope) -> None:
        if isinstance(s, L.ExprStmt):
            self.expr(s.value, scope)
        elif isinstance(s, L.Assign):
            self.assign(s.target, self.expr(s.value, scope), scope)
        elif isinstance(s, L.AugAssign):
            if isinstance(s.target, L.NameTarget):
                cur = self.load(s.target.id, scope, s.line)
                self.store(s.target.id, _IBIN[s.op](cur, self.expr(s.value, scope)), scope)
            elif isinstance(s.target, L.AttrTarget):
                obj = self.expr(s.target.obj, scope)
                setattr(obj, s.target.name, _IBIN[s.op](getattr(obj, s.target.name), self.expr(s.value, scope)))
            elif isinstance(s.target, L.ItemTarget):
                obj, key = self.expr(s.target.obj, scope), self.expr(s.target.key, scope)
                obj[key] = _IBIN[s.op](obj[key], self.expr(s.value, scope))
            else:
                raise TypeError("illegal augmented assignment target")
        elif isinstance(s, L.Return):
            raise _Return(self.expr(s.value, scope) if s.value is not None else None)
        elif isinstance(s, L.If):
            self.block(s.body if self.expr(s.test, scope) else s.orelse, scope)
        elif isinstance(s, L.While):
            broke = False
            while self.expr(s.test, scope):
                try:
                    self.block(s.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(s.orelse, scope)
        elif isinstance(s, L.For):
            it = iter(self.expr(s.iterable, scope))
            broke = False
            while True:
                try:
                    v = next(it)
                except StopIteration:
                    break
                self.assign(s.target, v, scope)
                try:
                    self.block(s.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(s.orelse, scope)
        elif isinstance(s, L.Break):
            raise _Break()
        elif isinstance(s, L.Continue):
            raise _Continue()
        elif isinstance(s, L.Pass):
            pass
        elif isinstance(s, L.FunctionDef):
            fn: Any = self.function(s, scope)
            for d in reversed(s.decorators):          # evaluated before the defaults, applied now
                fn = caller_for(_module_of(scope))(self.expr(d, scope), (fn,), {})
            self.store(s.store or s.name, fn, scope)
        elif isinstance(s, L.Raise):
            if s.exc is None:
                raise  # re-raise the exception being handled (Python's own machinery)
            exc = self.expr(s.exc, scope)
            if isinstance(exc, type) and issubclass(exc, BaseException):
                exc = exc()
            if s.cause is not None:
                cause = self.expr(s.cause, scope)
                if isinstance(cause, type) and issubclass(cause, BaseException):
                    cause = cause()
                raise exc from cause
            raise exc
        elif isinstance(s, L.Try):
            self.try_stmt(s, scope)
        elif isinstance(s, L.Delete):
            for t in s.targets:
                if isinstance(t, L.NameTarget):
                    self.delete(t.id, scope)
                elif isinstance(t, L.AttrTarget):
                    delattr(self.expr(t.obj, scope), t.name)
                elif isinstance(t, L.ItemTarget):
                    del self.expr(t.obj, scope)[self.expr(t.key, scope)]
                else:
                    raise TypeError("illegal delete target")
        elif isinstance(s, L.Assert):
            if not self.expr(s.test, scope):
                raise AssertionError(self.expr(s.msg, scope)) if s.msg is not None else AssertionError()
        else:
            raise TypeError(f"unknown statement {type(s).__name__}")

    def try_stmt(self, s: L.Try, scope: Scope) -> None:
        try:
            try:
                self.block(s.body, scope)
            except _SIGNALS:
                raise
            except BaseException as exc:
                for h in s.handlers:
                    if h.type is None:
                        matched = True
                    else:
                        t = self.expr(h.type, scope)
                        matched = isinstance(exc, t)
                    if matched:
                        if h.name:
                            self.store(h.name, exc, scope)
                        try:
                            self.block(h.body, scope)
                        finally:
                            if h.name:
                                scope.vars.pop(h.name, None)   # except-clause names are unbound afterwards
                        break
                else:
                    raise
            else:
                self.block(s.orelse, scope)
        finally:
            self.block(s.finalbody, scope)

    # ---- functions and calls -----------------------------------------------------------------
    def function(self, node: L.FunctionDef | L.Lambda, scope: Scope) -> types.FunctionType:
        """MAKE_FUNCTION: defaults in parameter order (positional ones, then keyword-only), the
        docstring, and the annotate function, made in the same scope."""
        defaults = tuple(self.expr(p.default, scope) for p in node.params
                         if p.default is not None and p.kind in ("positional-only", "positional-or-keyword"))
        kwdefaults = {p.name: self.expr(p.default, scope) for p in node.params
                      if p.default is not None and p.kind == "keyword-only"}
        fn = make_function(self, node, scope)
        fn.__defaults__ = defaults or None
        fn.__kwdefaults__ = kwdefaults or None
        if isinstance(node, L.FunctionDef):
            fn.__doc__ = node.docstring
            if node.annotate is not None:
                fn.__annotate__ = self.function(node.annotate, scope)
        return fn

    def call(self, fn: types.FunctionType, node: L.FunctionDef | L.Lambda, closure: Scope,
             args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        module = closure if closure.is_module() else closure.module
        is_def = isinstance(node, L.FunctionDef)
        scope = Scope(vars={}, parent=closure, locals_=_local_names(node),
                      globals_=node.globals if isinstance(node, L.FunctionDef) else frozenset(),
                      nonlocals_=node.nonlocals if isinstance(node, L.FunctionDef) else frozenset(), module=module)
        synthetic = self._syn(closure)
        for name, value in bind_arguments(fn, node, args, kwargs).items():
            # a parameter the frontend generated (a comprehension's iterator, the annotate
            # function's format) is a real binding, invisible to the program
            (scope.temps if name in synthetic else scope.vars)[name] = value
        if not is_def:
            assert isinstance(node, L.Lambda)
            return self.expr(node.body, scope)
        assert isinstance(node, L.FunctionDef)
        try:
            self.block(node.body, scope)
        except _Return as r:
            return r.value
        return None

    def run_class_body(self, node: L.ClassBody, closure: Scope, ns: Any) -> Any:
        """The class body with ns as its locals; returns the __class__ cell, or None."""
        from pipeline.l1.wf import _bound_in
        bound: set[str] = set()
        _bound_in(node.body, bound)
        module = closure if closure.is_module() else closure.module
        scope = Scope(vars=ns, parent=closure, locals_=frozenset(bound - node.globals - node.nonlocals),
                      globals_=node.globals, nonlocals_=node.nonlocals, module=module, is_class=True,
                      cell=types.CellType() if node.classcell else None,
                      classdict=types.CellType(ns) if node.classdict else None)   # LOAD_LOCALS; STORE_DEREF
        try:
            self.block(node.body, scope)
        except _Return as r:
            return r.value
        return None

    def class_cell(self, scope: Scope) -> Any:
        s: Scope | None = scope
        while s is not None:
            if s.is_class and s.cell is not None:
                return s.cell
            s = s.parent
        raise AssertionError("the classcell intrinsic outside a class that has one")

    def arguments(self, e: L.Call, fn: Any, scope: Scope) -> tuple[list[Any], dict[str, Any]]:
        """The positional list (LIST_EXTEND for ``*x``) and the keyword dict (DICT_MERGE for
        ``**m``), with CPython's errors."""
        args: list[Any] = []
        for a in e.args:
            if isinstance(a, L.Starred):
                value = self.expr(a.value, scope)
                error: TypeError | None = None
                try:
                    args.extend(value)
                except TypeError:
                    t = type(value)
                    if getattr(t, "__iter__", None) is None and not _is_sequence(value):
                        error = TypeError(f"Value after * must be an iterable, not {_tp_name(t)}")
                    else:
                        raise
                if error is not None:
                    raise error                 # CPython clears the original (no __context__ from it)
            else:
                args.append(self.expr(a, scope))
        kwargs: dict[str, Any] = {}
        for name, v in e.kwargs:
            value = self.expr(v, scope)
            if name is not None:
                if name in kwargs:              # an explicit keyword after a ** that supplied it
                    raise TypeError(f"{_function_str(fn)} got multiple values for keyword argument '{name}'")
                kwargs[name] = value
                continue
            failure: TypeError | None = None
            dupkey: tuple[Any] | None = None
            try:
                dupkey = _dict_merge(kwargs, value)
            except AttributeError:
                # _PyEval_FormatKwargsError: only an object without keys() is "not a mapping"
                if hasattr(value, "keys"):
                    raise
                failure = TypeError(f"Value after ** must be a mapping, not {_fully_qualified(type(value))}")
            if failure is not None:
                raise failure                   # the AttributeError is dropped, not chained
            if dupkey is not None:
                raise TypeError(f"{_function_str(fn)} got multiple values for keyword argument '{dupkey[0]}'")
        return args, kwargs

    # ---- expressions -----------------------------------------------------------------------
    def expr(self, e: L.Expr, scope: Scope) -> Any:
        if isinstance(e, L.Const):
            return e.value
        if isinstance(e, L.Name):
            return self.load(e.id, scope, e.line)
        if isinstance(e, L.BinOp):
            return _BIN[e.op](self.expr(e.left, scope), self.expr(e.right, scope))
        if isinstance(e, L.UnaryOp):
            return _UN[e.op](self.expr(e.operand, scope))
        if isinstance(e, L.Truth):
            return bool(self.expr(e.operand, scope))
        if isinstance(e, L.Not):
            return not self.expr(e.operand, scope)
        if isinstance(e, L.Compare):
            return _CMP[e.op](self.expr(e.left, scope), self.expr(e.right, scope))
        if isinstance(e, L.BoolOp):
            left = self.expr(e.left, scope)
            if e.op == "and":
                return self.expr(e.right, scope) if left else left
            return left if left else self.expr(e.right, scope)
        if isinstance(e, L.IfExp):
            return self.expr(e.body, scope) if self.expr(e.test, scope) else self.expr(e.orelse, scope)
        if isinstance(e, L.Call):
            if isinstance(e.func, L.Name) and e.func.id == "__bind__":
                name = e.args[0]
                assert isinstance(name, L.Const) and isinstance(name.value, str)
                value = self.expr(e.args[1], scope)
                self.store(name.value, value, scope)
                return value
            fn = self.expr(e.func, scope)
            if any(fn is h for h in _HOST_STATE):
                return self._host_state(fn, e, scope)
            args, kwargs = self.arguments(e, fn, scope)
            return caller_for(_module_of(scope))(fn, args, kwargs)
        if isinstance(e, L.Lambda):
            return self.function(e, scope)
        if isinstance(e, L.Intrinsic):
            if e.name == "build_class":
                return self.runtime("build_class")
            if e.name == "classcell":
                return self.class_cell(scope)
            if e.name == "classdictcell":
                assert scope.is_class and scope.classdict is not None
                return scope.classdict
            if e.name == "super":
                return zero_arg_super
            if e.name == "missing":
                return _MISSING
            return getattr(builtins, e.name)
        if isinstance(e, L.ClassBody):
            return ClassBodyFunction(self, e, scope)
        if isinstance(e, L.GetAttr):
            return getattr(self.expr(e.obj, scope), e.name)
        if isinstance(e, L.GetItem):
            return self.expr(e.obj, scope)[self.expr(e.key, scope)]
        if isinstance(e, L.ListLit):
            return [self.expr(x, scope) for x in e.items]
        if isinstance(e, L.TupleLit):
            return tuple(self.expr(x, scope) for x in e.items)
        if isinstance(e, L.DictLit):
            return {self.expr(k, scope): self.expr(v, scope) for k, v in zip(e.keys, e.values, strict=True)}
        raise TypeError(f"unknown expression {type(e).__name__}")


def _is_sequence(value: Any) -> bool:
    """PySequence_Check: a __getitem__ that is not a dict's."""
    return not isinstance(value, dict) and getattr(type(value), "__getitem__", None) is not None


def _dict_merge(target: dict[str, Any], m: Any) -> tuple[Any] | None:
    """_PyDict_MergeUniq (Objects/dictobject.c, dict_merge with override 2, CPython 3.15.2): a
    dict whose type keeps dict's iteration is read from its storage; anything else through
    keys(), listed first, then m[key]. A key already present stops the merge before m[key] is
    read and is returned (``dupkey``); every other error propagates as raised."""
    if isinstance(m, dict) and type(m).__iter__ is dict.__iter__:
        for k, v in dict.items(m):
            if k in target:
                return (k,)
            target[k] = v
        return None
    for k in list(m.keys()):
        if k in target:
            return (k,)
        target[k] = m[k]
    return None


def _module_of(scope: Scope) -> Scope:
    return scope if scope.is_module() else (scope.module or scope)


def _host_state_impl(interp: Interpreter, fn: Any, e: L.Call, scope: Scope) -> Any:
    if fn in (builtins.eval, builtins.exec, builtins.compile):
        raise L.Unsupported(f"{fn.__name__}() of source text is excluded (E-01) (line {e.line})")
    if e.args or e.kwargs:
        if fn is builtins.globals or fn is builtins.locals:
            raise TypeError(f"{fn.__name__}() takes no arguments")
        args, kwargs = interp.arguments(e, fn, scope)
        return fn(*args, **kwargs)
    if fn is builtins.globals:
        return _module_of(scope).vars
    if scope.is_class:
        if fn is builtins.dir:
            return sorted(scope.vars.keys())
        return scope.vars                                  # locals() and vars() in a class body: the namespace
    if not scope.is_module():
        raise L.Unsupported(f"{fn.__name__}() inside a function is not modelled by eval1 yet (line {e.line})")
    if fn is builtins.dir:
        return sorted(scope.vars)
    return scope.vars                                      # locals() and vars() at module level



def run_source(source: str, filename: str = "<module>") -> Scope:
    from pipeline.l1.frontend import lower
    from pipeline.l1.wf import check
    module = lower(source, filename)
    check(module)
    return Interpreter().run_module(module)
