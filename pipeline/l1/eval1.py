"""eval1: the executable semantics of L1.

A reference interpreter for PyCore that delegates every primitive operation to CPython itself
(the semantics of ``+`` on ints, of ``iter``/``next``, of ``isinstance`` are Python's, so the
reference may use them) while implementing the parts L1 makes explicit: scoping and binding,
control flow, the iteration protocol, exception handling, truthiness, function objects.

It is the oracle each later level is tested against: eval2(P(x)) must equal eval1(x).
"""
from __future__ import annotations

import _suggestions  # type: ignore[import-not-found]  # CPython's own, private: the hint it prints
import builtins
import operator
import string.templatelib as templatelib
import sys
import types
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib._bootstrap import _calc___package__, _resolve_name  # type: ignore[attr-defined]  # the import system's own
from pathlib import Path
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.l1.frontend import lower
from pipeline.l1.wf import _bound_in, _walrus, check
from pipeline.staging import annotate_rt

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
    classdict_scope: Scope | None = None   # an annotate function's class: its namespace is read first

    def is_module(self) -> bool:
        return self.module is None


_MISSING = object()            # the `missing` intrinsic: what super() finds absent


def __bella_call__(fn: Any, args: Any, kwargs: Any) -> Any:
    # a call with no keyword items passes no dict (CALL); one with any, even an empty **{},
    # passes the dict (CALL_FUNCTION_EX): a C type that refuses keywords can tell the two apart
    return fn(*args) if kwargs is None else fn(*args, **kwargs)


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


# ---- imports ---------------------------------------------------------------------------------
# The frontend lowers import statements to import_name, import_from and import_star (desugar-
# imports). eval1 runs the last two with CPython's own IMPORT_FROM and import-star code, on the
# object import_name returned: a module-level `from _ import NAME` whose __import__ hands that
# object over once, then behaves as the real one (a lazy attribute made by IMPORT_FROM keeps
# the builtins it was made with), so lazy objects, the sys.modules fallback and every error are
# CPython's.
_FROM_CODE: dict[str, types.CodeType] = {}
_STAR_CODE = compile("from _ import *", "<bella import *>", "exec", dont_inherit=True)


def _handing_over(value: Any) -> dict[str, Any]:
    real = builtins.__import__
    handed = [False]

    def __import__(*args: Any, **kwargs: Any) -> Any:
        if not handed[0]:
            handed[0] = True
            return value
        return real(*args, **kwargs)
    return {**vars(builtins), "__import__": __import__}


def import_from(module: Any, name: str) -> Any:
    """IMPORT_FROM (_PyEval_ImportFrom, _PyEval_LazyImportFrom on a lazy object)."""
    code = _FROM_CODE.get(name)
    if code is None:
        code = _FROM_CODE[name] = compile(f"from _ import {name} as __bella_value__", "<bella import>", "exec",
                                          dont_inherit=True)
    ns: dict[str, Any] = {"__builtins__": _handing_over(module), "__name__": "<bella import>"}
    exec(code, ns)  # noqa: S102  # CPython's own IMPORT_FROM on the given object
    return ns["__bella_value__"]


def import_star(module: Any, namespace: Any) -> None:
    """INTRINSIC_IMPORT_STAR (import_all_from): __all__, else the public keys of __dict__,
    stored into the namespace (a dict directly, another mapping by __setitem__)."""
    exec(_STAR_CODE, {"__builtins__": _handing_over(module), "__name__": "<bella import *>"}, namespace)  # noqa: S102


with warnings.catch_warnings():
    warnings.simplefilter("ignore")              # "'str' object is not callable": placeholders
    # compiled now: nothing on eval1's path may import or warn while a program runs
    _AT_MODULE_LEVEL = compile("'bella:f'('bella:0', 'bella:1', 'bella:2', 'bella:3', 'bella:4')",
                               "<bella import>", "eval", dont_inherit=True)


def _call_at_module_level(globals_: dict[str, Any], func: Any, *args: Any) -> Any:
    """func(*args) from a frame whose globals and locals are both `globals_`, as a module body's
    are: __lazy_import__ requires it of the frame that calls it (import.c, 3.15.2). The call is an
    expression whose constants are the function and its arguments, so the namespace is not
    touched (eval adds __builtins__ if missing, as exec does for any module)."""
    values = {"bella:f": func, **{f"bella:{i}": a for i, a in enumerate(args)}}
    consts = tuple(values[c] if isinstance(c, str) and c in values else c for c in _AT_MODULE_LEVEL.co_consts)
    assert len(args) == 5 and sum(isinstance(c, str) and c in values for c in _AT_MODULE_LEVEL.co_consts) == 6
    return eval(_AT_MODULE_LEVEL.replace(co_consts=consts), globals_, globals_)  # noqa: S307  # constants only


def _frame_builtins(globals_: dict[str, Any]) -> Any:
    """_PyEval_BuiltinsFromGlobals: globals['__builtins__'] (a module stands for its dict), else
    the interpreter's."""
    b = dict.get(globals_, "__builtins__", _MISSING)
    if b is _MISSING:
        return vars(builtins)
    return vars(b) if isinstance(b, types.ModuleType) else b


def import_name(name: str, fromlist: Any, level: int, mode: str, globals_: dict[str, Any], locals_: Any) -> Any:
    """IMPORT_NAME (_PyEval_LazyImportName, _PyEval_ImportName; Python/ceval.c, 3.15.2). A
    default-mode import (module scope, outside try/except/finally) is lazy when the lazy-imports
    mode is "all" or __lazy_modules__ names the module; a lazy one calls __lazy_import__."""
    b = _frame_builtins(globals_)
    lazy = mode == "lazy"
    if mode == "default":
        if sys.get_lazy_imports() == "all":
            lazy = True
        else:
            listed: Any = _MISSING
            try:
                listed = globals_["__lazy_modules__"]
            except KeyError:
                pass
            if listed is not _MISSING:
                absolute = name if level == 0 else _resolve_name(name, _calc___package__(globals_), level)
                lazy = absolute in listed
    key = "__lazy_import__" if lazy else "__import__"
    found = True
    try:
        func = b[key]
    except KeyError:
        found = False
    if not found:
        raise ImportError(f"{key} not found")
    if lazy:
        return _call_at_module_level(globals_, func, name, globals_, globals_ if locals_ is None else locals_, fromlist, level)
    return func(name, globals_, None if locals_ is None else locals_, fromlist, level)


def _reify(value: Any, name: str, namespace: Any) -> Any:
    """A lazy import loaded from a namespace (a global, a builtin, a class body's name) is
    resolved and the namespace, if it still holds it, gets the result (pipeline/staging/
    annotate_rt.py, read from CPython 3.15.2's bytecodes.c)."""
    return annotate_rt._reify(value, name, namespace)


_PRELUDE = Path(__file__).resolve().parents[2] / "runtime" / "prelude"
_LOWERED: dict[Path, L.Module] = {}


def _lowered(path: Path) -> L.Module:
    """A runtime module written in Python (runtime/prelude), lowered once per process."""
    if path not in _LOWERED:
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
        return self.run_in(m, {"__name__": name})

    def run_in(self, m: L.Module, namespace: dict[str, Any]) -> Scope:
        """A module body with `namespace` as its globals (a module's own __dict__, when the
        module system runs it)."""
        namespace.setdefault("__builtins__", vars(builtins))   # what exec() adds to a module's globals
        module = Scope(vars=namespace, synthetic=m.synthetic)
        self.block(m.body, module)
        return module

    def load_runtime(self) -> None:
        """The Python half of the runtime (runtime/prelude), lowered and run by this interpreter
        like any compiled module; the module system loads it before the program starts, so that
        no lowering happens while program code runs."""
        if self.prelude is None:
            loaded: dict[str, Any] = {}
            for module in ("build_class", "match"):
                loaded.update(self.run_module(_lowered(_PRELUDE / f"{module}.py"), f"bella.{module}").vars)
            self.prelude = loaded

    def runtime(self, name: str) -> Any:
        self.load_runtime()
        assert self.prelude is not None
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
                return _reify(scope.vars[name], name, scope.vars)
            if name in self.builtins:
                return _reify(self.builtins[name], name, self.builtins)   # fall-through to builtins (C-8-02)
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
                    return _reify(value, name, scope.vars)
                if name in scope.locals_:
                    return self.load(name, module, line)   # bound in the body: globals, builtins
        elif name in scope.locals_:
            if name in scope.vars:
                return scope.vars[name]
            # CPython 3.15 leaves UnboundLocalError.name as None (measured; NameError carries it)
            raise UnboundLocalError(f"cannot access local variable '{name}' where it is not associated with a value")
        elif scope.classdict_scope is not None and scope.classdict_scope.classdict is not None:
            # LOAD_FROM_DICT_OR_GLOBALS / LOAD_FROM_DICT_OR_DEREF: the class's namespace first
            mapping = scope.classdict_scope.classdict.cell_contents
            found = True
            try:
                value = mapping[name]
            except KeyError:
                found = False
            if found:
                return _reify(value, name, mapping)
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
        if name in self._syn(scope):
            scope.temps.pop(name, None)
            return
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
            star = next((i for i, x in enumerate(t.elts) if isinstance(x, L.StarTarget)), None)
            before = len(t.elts) if star is None else star
            after = -1 if star is None else len(t.elts) - star - 1
            for sub, v in zip(t.elts, unpack_iterable(value, before, after), strict=True):
                self.assign(sub.target if isinstance(sub, L.StarTarget) else sub, v, scope)
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
        elif isinstance(s, (L.Pass, L.Declare)):
            pass
        elif isinstance(s, L.FunctionDef):
            fn: Any = self.function(s, scope)
            for d in reversed(s.decorators):          # evaluated before the defaults, applied now
                fn = caller_for(_module_of(scope))(self.expr(d, scope), (fn,), None)
            self.store(s.store or s.name, fn, scope)
        elif isinstance(s, L.Raise):
            # RAISE_VARARGS: both expressions are evaluated, then do_raise instantiates them
            exc = self.expr(s.exc, scope) if s.exc is not None else None
            cause = self.expr(s.cause, scope) if s.cause is not None else None
            self._raise(exc, cause, s.cause is not None)
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
        """try/except/else/finally. A refusal passes through untouched (no handler, no finally);
        return, break and continue run the finally block outside any handler, as CPython does;
        an except clause's name is set to None and deleted afterwards (codegen's cleanup)."""
        pending: BaseException | None = None
        try:
            handled = False
            try:
                self.block(s.body, scope)
            except (*_SIGNALS, L.Refused):
                raise
            except BaseException as exc:  # noqa: BLE001  # the program's handlers decide
                handler = self._handler(s, _unwrap(exc), scope)
                if handler is None:
                    raise
                handled = True
                self._run_handler(handler, _unwrap(exc), scope)
            if not handled:
                self.block(s.orelse, scope)
        except L.Refused:
            raise
        except _SIGNALS as signal:
            pending = signal
        except BaseException:  # noqa: BLE001  # finally runs while the exception propagates
            self.block(s.finalbody, scope)
            raise
        else:
            self.block(s.finalbody, scope)
            return
        self.block(s.finalbody, scope)
        raise pending

    def _handler(self, s: L.Try, exc: BaseException, scope: Scope) -> L.Handler | None:
        for h in s.handlers:
            if h.type is None or _matches(exc, self.expr(h.type, scope)):
                return h
        return None

    def _run_handler(self, h: L.Handler, exc: BaseException, scope: Scope) -> None:
        if h.name:
            self.store(h.name, exc, scope)
        try:
            self.block(h.body, scope)
        finally:
            if h.name:
                self.store(h.name, None, scope)
                self.delete(h.name, scope)

    # ---- generators ------------------------------------------------------------------------
    # A generator function's body runs on host generators, so the program gets a real generator
    # object: send, throw, close, yield from and the exception context are CPython's. Only code
    # that contains a yield runs on them; the rest goes through the plain evaluator. PEP 479
    # would turn a StopIteration into a RuntimeError at each of these inner frames, so they carry
    # it in a _Carrier and the program sees it again at its except clauses and at the boundary of
    # the generator itself.
    def run_generator(self, node: L.FunctionDef | L.Lambda, scope: Scope) -> Any:
        try:
            try:
                if isinstance(node, L.Lambda):
                    yield from self.gblock(node.prelude, scope)
                    return (yield from self.gexpr(node.body, scope))
                yield from self.gblock(node.body, scope)
                return None
            except _Return as r:
                return r.value
        except _Carrier as carried:
            inner = carried.inner
        raise inner                 # here PEP 479 makes it the RuntimeError, as at CPython's boundary

    def gblock(self, stmts: tuple[L.Stmt, ...], scope: Scope) -> Any:
        try:
            for s in stmts:
                if _has_yield(s):
                    yield from self.gstmt(s, scope)
                else:
                    self.stmt(s, scope)
        except StopIteration as exc:
            raise _Carrier(exc) from None

    def gstmt(self, s: L.Stmt, scope: Scope) -> Any:
        try:
            if isinstance(s, L.ExprStmt):
                yield from self.gexpr(s.value, scope)
            elif isinstance(s, L.Assign):
                if _has_yield_target(s.target):
                    raise L.Refused(f"a yield inside an assignment target is not lowered (line {s.line})")
                self.assign(s.target, (yield from self.gexpr(s.value, scope)), scope)
            elif isinstance(s, L.AugAssign):
                if not isinstance(s.target, L.NameTarget):
                    raise L.Refused(f"a yield in an augmented assignment to {type(s.target).__name__} is not lowered "
                                    f"(line {s.line})")
                cur = self.load(s.target.id, scope, s.line)
                self.store(s.target.id, _IBIN[s.op](cur, (yield from self.gexpr(s.value, scope))), scope)
            elif isinstance(s, L.Return):
                raise _Return((yield from self.gexpr(s.value, scope)) if s.value is not None else None)
            elif isinstance(s, L.If):
                taken = yield from self.gexpr(s.test, scope)
                yield from self.gblock(s.body if taken else s.orelse, scope)
            elif isinstance(s, L.While):
                broke = False
                while (yield from self.gexpr(s.test, scope)):
                    try:
                        yield from self.gblock(s.body, scope)
                    except _Break:
                        broke = True
                        break
                    except _Continue:
                        continue
                if not broke:
                    yield from self.gblock(s.orelse, scope)
            elif isinstance(s, L.For):
                it = iter((yield from self.gexpr(s.iterable, scope)))
                broke = False
                while True:
                    v = next(it, _MISSING)
                    if v is _MISSING:
                        break
                    self.assign(s.target, v, scope)
                    try:
                        yield from self.gblock(s.body, scope)
                    except _Break:
                        broke = True
                        break
                    except _Continue:
                        continue
                if not broke:
                    yield from self.gblock(s.orelse, scope)
            elif isinstance(s, L.Try):
                yield from self.gtry(s, scope)
            elif isinstance(s, L.Raise):
                exc = (yield from self.gexpr(s.exc, scope)) if s.exc is not None else None
                cause = (yield from self.gexpr(s.cause, scope)) if s.cause is not None else None
                self._raise(exc, cause, s.cause is not None)
            elif isinstance(s, L.Assert):
                if not (yield from self.gexpr(s.test, scope)):
                    raise AssertionError((yield from self.gexpr(s.msg, scope))) if s.msg is not None else AssertionError()
            else:
                raise L.Refused(f"a yield inside {type(s).__name__} is not lowered (line {s.line})")
        except StopIteration as exc:
            raise _Carrier(exc) from None

    def gtry(self, s: L.Try, scope: Scope) -> Any:
        pending: BaseException | None = None
        try:
            handled = False
            try:
                yield from self.gblock(s.body, scope)
            except (*_SIGNALS, L.Refused):
                raise
            except BaseException as exc:  # noqa: BLE001  # the program's handlers decide
                handler = self._handler(s, _unwrap(exc), scope)
                if handler is None:
                    raise
                handled = True
                inner = _unwrap(exc)
            if handled:
                assert handler is not None
                # the handler runs while the program's exception, not its carrier, is the one
                # being handled (sys.exception(), the context of what the handler raises)
                try:
                    raise inner
                except BaseException:  # noqa: BLE001
                    if handler.name:
                        self.store(handler.name, inner, scope)
                    try:
                        yield from self.gblock(handler.body, scope)
                    finally:
                        if handler.name:
                            self.store(handler.name, None, scope)
                            self.delete(handler.name, scope)
            else:
                yield from self.gblock(s.orelse, scope)
        except L.Refused:
            raise
        except _SIGNALS as signal:
            pending = signal
        except BaseException:  # noqa: BLE001  # finally runs while the exception propagates
            yield from self.gblock(s.finalbody, scope)
            raise
        else:
            yield from self.gblock(s.finalbody, scope)
            return
        yield from self.gblock(s.finalbody, scope)
        raise pending

    def gexpr(self, e: L.Expr, scope: Scope) -> Any:
        try:
            if not _has_yield(e):
                return self.expr(e, scope)
            if isinstance(e, L.Yield):
                value = (yield from self.gexpr(e.value, scope)) if e.value is not None else None
                return (yield value)
            if isinstance(e, L.YieldFrom):
                return (yield from (yield from self.gexpr(e.value, scope)))   # PEP 380, by the host
            if isinstance(e, L.Truth):
                return bool((yield from self.gexpr(e.operand, scope)))
            if isinstance(e, L.Not):
                return not (yield from self.gexpr(e.operand, scope))
            if isinstance(e, L.UnaryOp):
                return _UN[e.op]((yield from self.gexpr(e.operand, scope)))
            if isinstance(e, L.BinOp):
                left = yield from self.gexpr(e.left, scope)
                return _BIN[e.op](left, (yield from self.gexpr(e.right, scope)))
            if isinstance(e, L.Compare):
                left = yield from self.gexpr(e.left, scope)
                return _CMP[e.op](left, (yield from self.gexpr(e.right, scope)))
            if isinstance(e, L.BoolOp):
                left = yield from self.gexpr(e.left, scope)
                if e.op == "and":
                    return (yield from self.gexpr(e.right, scope)) if left else left
                return left if left else (yield from self.gexpr(e.right, scope))
            if isinstance(e, L.IfExp):
                taken = yield from self.gexpr(e.test, scope)
                return (yield from self.gexpr(e.body if taken else e.orelse, scope))
            if isinstance(e, L.GetAttr):
                return getattr((yield from self.gexpr(e.obj, scope)), e.name)
            if isinstance(e, L.GetItem):
                obj = yield from self.gexpr(e.obj, scope)
                return obj[(yield from self.gexpr(e.key, scope))]
            if isinstance(e, L.Call) and not isinstance(e.func, L.Intrinsic) and \
                    not (isinstance(e.func, L.Name) and e.func.id == "__bind__") and \
                    not any(isinstance(a, L.Starred) for a in e.args) and all(k is not None for k, _ in e.kwargs):
                fn = yield from self.gexpr(e.func, scope)
                args: list[Any] = []
                for a in e.args:
                    args.append((yield from self.gexpr(a, scope)))
                kwargs: dict[str, Any] = {}
                for k, v in e.kwargs:
                    assert k is not None
                    kwargs[k] = yield from self.gexpr(v, scope)
                return caller_for(_module_of(scope))(fn, args, kwargs if e.kwargs else None)
            if isinstance(e, (L.ListLit, L.TupleLit)) and not any(isinstance(x, L.Starred) for x in e.items) \
                    and len(e.items) <= _STACK_USE_GUIDELINE:
                values: list[Any] = []
                for x in e.items:
                    values.append((yield from self.gexpr(x, scope)))
                return tuple(values) if isinstance(e, L.TupleLit) else values
            raise L.Refused(f"a yield inside {type(e).__name__} is not lowered (line {e.line})")
        except StopIteration as exc:
            raise _Carrier(exc) from None

    def _raise(self, exc: Any, cause: Any, has_cause: bool) -> None:
        if exc is None:
            raise  # noqa: PLE0704  # re-raise the exception being handled (Python's own machinery)
        if isinstance(exc, type) and issubclass(exc, BaseException):
            exc = exc()
        if has_cause:
            if isinstance(cause, type) and issubclass(cause, BaseException):
                cause = cause()
            raise exc from cause
        raise exc

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
                      nonlocals_=node.nonlocals if isinstance(node, L.FunctionDef) else frozenset(), module=module,
                      classdict_scope=_nearest_class(closure) if isinstance(node, L.FunctionDef) and node.classdict else None)
        synthetic = self._syn(closure)
        for name, value in bind_arguments(fn, node, args, kwargs).items():
            # a parameter the frontend generated (a comprehension's iterator, the annotate
            # function's format) is a real binding, invisible to the program
            (scope.temps if name in synthetic else scope.vars)[name] = value
        if node.kind == "generator":
            gen = self.run_generator(node, scope)
            gen.__name__, gen.__qualname__ = fn.__name__, fn.__qualname__
            return gen
        if node.kind in ("coroutine", "async generator"):
            made: Any = (_refused_coroutine if node.kind == "coroutine" else _refused_async_generator)(fn.__qualname__)
            made.__name__, made.__qualname__ = fn.__name__, fn.__qualname__
            return made
        if not is_def:
            assert isinstance(node, L.Lambda)
            self.block(node.prelude, scope)
            return self.expr(node.body, scope)
        assert isinstance(node, L.FunctionDef)
        try:
            self.block(node.body, scope)
        except _Return as r:
            return r.value
        return None

    def display(self, e: L.ListLit | L.TupleLit | L.SetLit, scope: Scope) -> Any:
        """starunpack_helper (Python/codegen.c): with no starred item and at most 30 items, every
        item is evaluated before the container is built; otherwise it is built at the first
        starred item (or empty, when big) and each later item added as it is evaluated
        (LIST_APPEND/SET_ADD, LIST_EXTEND/SET_UPDATE); a tuple is made from the list."""
        is_set = isinstance(e, L.SetLit)
        big = len(e.items) > _STACK_USE_GUIDELINE
        if not big and not any(isinstance(x, L.Starred) for x in e.items):
            values = [self.expr(x, scope) for x in e.items]
            return set(values) if is_set else tuple(values) if isinstance(e, L.TupleLit) else values
        pending: list[Any] = []
        built: Any = (set() if is_set else []) if big else None
        for x in e.items:
            if isinstance(x, L.Starred):
                if built is None:
                    built = set(pending) if is_set else list(pending)
                value = self.expr(x.value, scope)
                if is_set:
                    built.update(value)                 # _PySet_Update: its own errors
                else:
                    _list_extend(built, value)
            else:
                value = self.expr(x, scope)
                if built is None:
                    pending.append(value)
                elif is_set:
                    built.add(value)
                else:
                    built.append(value)
        return tuple(built) if isinstance(e, L.TupleLit) else built

    def dict_display(self, e: L.DictLit, scope: Scope) -> dict[Any, Any]:
        """codegen_dict: runs of pairs become sub-dicts (evaluated, then built), a run longer than
        15 pairs is built pair by pair (MAP_ADD); `**m` is merged with DICT_UPDATE."""
        result: dict[Any, Any] | None = None
        run: list[tuple[L.Expr, L.Expr]] = []

        def flush() -> None:
            nonlocal result
            if not run:
                return
            sub: dict[Any, Any] = {}
            if len(run) * 2 > _STACK_USE_GUIDELINE:
                for k, v in run:
                    key = self.expr(k, scope)
                    sub[key] = self.expr(v, scope)
            else:
                pairs = [(self.expr(k, scope), self.expr(v, scope)) for k, v in run]
                for key, value in pairs:
                    sub[key] = value
            if result is None:
                result = sub
            else:
                result.update(sub)
            run.clear()

        for k, v in zip(e.keys, e.values, strict=True):
            if k is None:
                flush()
                if result is None:
                    result = {}
                _dict_update(result, self.expr(v, scope))
            else:
                if len(run) * 2 > _STACK_USE_GUIDELINE:
                    run.append((k, v))
                    flush()
                else:
                    run.append((k, v))
        flush()
        return {} if result is None else result

    def run_class_body(self, node: L.ClassBody, closure: Scope, ns: Any) -> Any:
        """The class body with ns as its locals; returns the __class__ cell, or None."""
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
                _list_extend(args, self.expr(a.value, scope))
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
            if isinstance(e.func, L.Intrinsic) and e.func.name in ("type_params", "generic_class", "typealias"):
                args, _ = self.arguments(e, e.func, scope)
                return _pep695(e.func.name, args, _module_of(scope).vars.get("__name__", "__main__"))
            if isinstance(e.func, L.Intrinsic) and e.func.name in ("import_name", "import_star"):
                args, _ = self.arguments(e, e.func, scope)
                module = _module_of(scope)
                namespace = scope.vars if scope.is_module() or scope.is_class else None
                if e.func.name == "import_star":
                    assert namespace is not None, "import * in a function is a SyntaxError"
                    import_star(args[0], namespace)
                    return None
                name, fromlist, level, mode = args
                return import_name(name, fromlist, level, mode, module.vars, namespace)
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
            return caller_for(_module_of(scope))(fn, args, kwargs if e.kwargs else None)
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
            if e.name == "import_from":
                return import_from
            if e.name == "map_add":
                return _map_add
            if e.name == "set_add":
                return set.add
            if e.name == "set_type_params":
                return _set_type_params
            if e.name == "unpack":
                return unpack_iterable
            if e.name == "template":
                return templatelib.Template
            if e.name == "interpolation":
                return templatelib.Interpolation
            if e.name in _MATCH_HELPERS:
                return self.runtime(_MATCH_HELPERS[e.name])
            return getattr(builtins, e.name)
        if isinstance(e, L.ClassBody):
            return ClassBodyFunction(self, e, scope)
        if isinstance(e, L.GetAttr):
            return getattr(self.expr(e.obj, scope), e.name)
        if isinstance(e, L.GetItem):
            return self.expr(e.obj, scope)[self.expr(e.key, scope)]
        if isinstance(e, (L.ListLit, L.TupleLit, L.SetLit)):
            return self.display(e, scope)
        if isinstance(e, L.DictLit):
            return self.dict_display(e, scope)
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


_STACK_USE_GUIDELINE = 30          # _PY_STACK_USE_GUIDELINE (Include/internal/pycore_compile.h)
_MATCH_HELPERS = {"match_is_sequence": "is_sequence", "match_is_mapping": "is_mapping", "match_keys": "match_keys",
                  "mapping_rest": "mapping_rest", "match_class": "match_class"}


class _Carrier(BaseException):
    """A StopIteration on its way through eval1's generator frames (see run_generator)."""

    def __init__(self, inner: StopIteration) -> None:
        self.inner = inner


def _unwrap(exc: BaseException) -> BaseException:
    return exc.inner if isinstance(exc, _Carrier) else exc


def _matches(exc: BaseException, spec: Any) -> bool:
    """An except clause: _PyEval_CheckExceptTypeValid, then PyErr_GivenExceptionMatches (by the
    MRO, not __subclasscheck__)."""
    classes = spec if isinstance(spec, tuple) else (spec,)
    for c in classes:
        if not (isinstance(c, type) and BaseException in c.__mro__):
            raise TypeError("catching classes that do not inherit from BaseException is not allowed")
    return any(c in type(exc).__mro__ for c in classes)


def _pep695(kind: str, args: list[Any], module_name: str) -> Any:
    """PEP 695's objects, made by CPython (the oracle lends them; the compiled runtime has its
    own): the text is a generic function, class or alias whose lazy expressions call the
    thunks, so TypeVar bounds, constraints and defaults and an alias's value stay lazy and are
    eval1's to compute; __module__ is the program's."""
    text, *rest = args
    ns: dict[str, Any] = {"__name__": module_name, "__builtins__": vars(builtins)}
    if kind == "typealias":
        ns["__bella_v__"], *thunks = rest
    else:
        thunks = rest
    for i, thunk in enumerate(thunks):
        ns[f"__bella_{i}__"] = thunk
    exec(compile(text, f"<{module_name}>", "exec", dont_inherit=True), ns)  # noqa: S102  # CPython makes the objects
    made = ns["__bella_tp__"] if kind != "typealias" else ns[text.split()[1].split("[")[0]]
    if kind == "type_params":
        return made.__type_params__
    if kind == "generic_class":
        return made.__type_params__, made.__orig_bases__[0]
    return made


def _set_type_params(fn: Any, params: tuple[Any, ...]) -> Any:
    """INTRINSIC_SET_FUNCTION_TYPE_PARAMS."""
    fn.__type_params__ = params
    return fn


def _nearest_class(scope: Scope) -> Scope | None:
    s: Scope | None = scope
    while s is not None:
        if s.is_class:
            return s
        s = s.parent
    return None


def _map_add(target: dict[Any, Any], key: Any, value: Any) -> None:
    """MAP_ADD: a dict comprehension's item, the key evaluated before the value."""
    dict.__setitem__(target, key, value)


async def _refused_coroutine(what: str) -> Any:
    """What calling an async def makes: a real coroutine, which refuses when it runs."""
    raise L.Refused(f"running the coroutine {what} is [P2+] (async, decision P-1)")


async def _refused_async_generator(what: str) -> Any:
    raise L.Refused(f"running the async generator {what} is [P2+] (async, decision P-1)")
    yield  # type: ignore[unreachable]  # makes it an async generator


_YIELDS: dict[int, tuple[L.Node, bool]] = {}


def _has_yield(node: L.Node) -> bool:
    """The node's own code yields: a Yield or YieldFrom in it, not in a function or lambda
    nested in it (a nested def's decorators and defaults count; its body does not). Cached by
    identity, the node kept with its answer so that its id cannot be reused by another."""
    entry = _YIELDS.get(id(node))
    if entry is None or entry[0] is not node:
        entry = _YIELDS[id(node)] = (node, _scan_yield(node))
    return entry[1]


def _scan_yield(node: Any) -> bool:
    if isinstance(node, (L.Yield, L.YieldFrom)):
        return True
    if isinstance(node, (L.Lambda, L.ClassBody)):
        return any(_scan_yield(p.default) for p in getattr(node, "params", ()) if p.default is not None)
    if isinstance(node, L.FunctionDef):
        return any(_scan_yield(d) for d in node.decorators) or \
            any(_scan_yield(p.default) for p in node.params if p.default is not None)
    for v in vars(node).values():
        items = v if isinstance(v, tuple) else (v,)
        for x in items:
            if isinstance(x, L.Node) and _scan_yield(x):
                return True
            if isinstance(x, L.Handler) and (x.type is not None and _scan_yield(x.type) or any(_scan_yield(b) for b in x.body)):
                return True
            if isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], L.Node) and _scan_yield(x[1]):
                return True
    return False


def _has_yield_target(t: L.Target) -> bool:
    return any(_scan_yield(v) for v in vars(t).values() if isinstance(v, L.Node))


def _list_extend(target: list[Any], value: Any) -> None:
    """LIST_EXTEND: a TypeError from a value that is neither iterable nor a sequence becomes
    "Value after * must be an iterable" (the original dropped, not chained)."""
    error: TypeError | None = None
    try:
        target.extend(value)
    except TypeError:
        if getattr(type(value), "__iter__", None) is None and not _is_sequence(value):
            error = TypeError(f"Value after * must be an iterable, not {_tp_name(type(value))}")
        else:
            raise
    if error is not None:
        raise error


def _dict_update(target: dict[Any, Any], m: Any) -> None:
    """DICT_UPDATE: PyDict_Update (later keys win); an AttributeError from an object without
    keys() becomes "'T' object is not a mapping"."""
    failure: TypeError | None = None
    try:
        if isinstance(m, dict) and type(m).__iter__ is dict.__iter__:
            for k, v in dict.items(m):
                target[k] = v
        else:
            for k in list(m.keys()):
                target[k] = m[k]
    except AttributeError:
        if hasattr(m, "keys"):
            raise
        failure = TypeError(f"'{_fully_qualified(type(m))}' object is not a mapping")
    if failure is not None:
        raise failure


def unpack_iterable(value: Any, before: int, after: int) -> list[Any]:
    """_PyEval_UnpackIterableStackRef (Python/ceval.c, 3.15.2): `before` items; with no starred
    target (after == -1) the iterator must then be exhausted, read one item further only;
    otherwise the rest becomes a list whose last `after` items go to the targets after it."""
    error: Exception | None = None
    try:
        it = iter(value)
    except TypeError:
        if getattr(type(value), "__iter__", None) is None and not _is_sequence(value):
            error = TypeError(f"cannot unpack non-iterable {_tp_name(type(value))} object")
        else:
            raise
    if error is not None:
        raise error
    items: list[Any] = []
    for i in range(before):
        w = next(it, _MISSING)
        if w is _MISSING:
            if after == -1:
                raise ValueError(f"not enough values to unpack (expected {before}, got {i})")
            raise ValueError(f"not enough values to unpack (expected at least {before + after}, got {i})")
        items.append(w)
    if after == -1:
        if next(it, _MISSING) is _MISSING:
            return items
        if type(value) in (list, tuple, dict) and len(value) > before:
            raise ValueError(f"too many values to unpack (expected {before}, got {len(value)})")
        raise ValueError(f"too many values to unpack (expected {before})")
    rest = list(it)
    if len(rest) < after:
        raise ValueError(f"not enough values to unpack (expected at least {before + after}, got {before + len(rest)})")
    tail = rest[len(rest) - after:] if after else []
    del rest[len(rest) - after:]
    return [*items, rest, *tail]


def _module_of(scope: Scope) -> Scope:
    return scope if scope.is_module() else (scope.module or scope)


def _host_state_impl(interp: Interpreter, fn: Any, e: L.Call, scope: Scope) -> Any:
    if fn in (builtins.eval, builtins.exec, builtins.compile):
        raise L.Refused(f"{fn.__name__}() of source text is excluded (E-01) (line {e.line})")
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
        raise L.Refused(f"{fn.__name__}() inside a function is not modelled by eval1 yet (line {e.line})")
    if fn is builtins.dir:
        return sorted(scope.vars)
    return scope.vars                                      # locals() and vars() at module level



def run_source(source: str, filename: str = "<module>") -> Scope:
    module = lower(source, filename)
    check(module)
    return Interpreter().run_module(module)
