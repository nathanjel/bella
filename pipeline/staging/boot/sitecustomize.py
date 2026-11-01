"""The replay model: a program run as the compiled program would run it (docs/staging.md).

pipeline/staging/run.py puts this directory on PYTHONPATH, so CPython runs this file at
start-up, before the program, and then runs the program exactly as `python script.py` would
(same `__main__`, arguments, tracebacks). From here on:

* the phase-1 configuration holds: the D-20 omissions behave as modules not installed;
* `exec` and `eval` of a text run only code staged by the dry run, looked up by call site and
  text and compiled at build time (the stand-in for the C++ the compiler emits); any other text,
  any code object and any `compile` stop the program with the E-01 refusal, which no `except`
  clause sees (design section 10.4: a refusal is not a Python exception);
* `annotationlib` is the phase-1 shim (runtime/shims/annotationlib.py): where CPython re-runs an
  annotate function's `__code__` against substitute globals, it calls the second entry point
  the compiler generated for that `__annotate__` (decision S-1, pipeline/staging/annotations.py).

Model scaffolding, not part of the contract: the import system keeps the real `exec` and
`compile` (a compiled program has no loader; its modules are compiled in), and so does the
`traceback` module's parse for carets (the traceback adaptation formats from source maps). An
entry point is found by the annotate function's code object, where the compiler attaches it to
the function it generates. Nothing is imported here that start-up has not imported.
"""
import builtins
import marshal
import os
import sys

TYPE_CHECKING = False
if TYPE_CHECKING:                  # nothing beyond start-up's modules is imported at runtime
    from types import FrameType
    from typing import Any, NoReturn

_REAL_EXEC = builtins.exec
_REAL_EVAL = builtins.eval
_REAL_COMPILE = builtins.compile
_CodeType = type(_REAL_COMPILE("0", "<bella>", "eval"))


def _refuse(message: str) -> NoReturn:
    """Stop the program, as a runtime refusal does: flushed output, no except clause, no
    finally block, no atexit handler, exit status 70."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:  # noqa: BLE001, S110  # a closed stream must not hide the refusal
            pass
    os.write(2, f"bella: refused: {message}\n".encode())
    os._exit(70)


def _site(frame: FrameType) -> str:
    """The function a call is made from (no line: see pipeline/staging/dryrun.py)."""
    return f"{frame.f_globals.get('__name__')}:{frame.f_code.co_qualname}"


def _where(frame: FrameType) -> str:
    return f"{_site(frame)}:{frame.f_lineno}"


_texts: dict[tuple[str, str, str], Any] = {}        # (site, operation, text) -> (code, future flags)
_compiled: dict[tuple[Any, ...], Any] = {}          # compile(): what it depends on -> outcome
_staged_code: set[int] = set()                      # ids of the code objects staged compile() hands out
_FUTURE_MASK = 0x3FE0000                            # every CO_FUTURE_* flag
_AST_RESULT = 0x400 | 0x8000                        # PyCF_ONLY_AST, PyCF_OPTIMIZED_AST
_entry_points: dict[str, tuple[tuple[str, ...], Any]] = {}   # annotate key -> (free variables, code)
_FunctionType: Any = type(_refuse)        # types.FunctionType, without importing types
_rt = type(sys)("annotate_rt")          # the entry points' helpers; not in sys.modules
_intrinsics: dict[tuple[str, ...], Any] = {}
_refused: dict[str, str] = {}                       # "module:qualname" -> refusal (manifest [refused])
_unstaged: dict[str, str] = {}                      # "module:qualname" -> refusal for a miss (manifest [unstaged])
_unsupported: dict[str, list[str]] = {}             # module -> functions phase 1 refuses ([lazy_unsupported])
_mechanism = os.environ.get("BELLA_STAGING_MECHANISM", "staged")
_NAMEDTUPLE_SITE = "collections:namedtuple"


def _miss(kind: str, frame: FrameType) -> NoReturn:
    site = _site(frame)
    _refuse(_unstaged.get(site) or f"E-01: {kind} at {_where(frame)} of a text the dry run did not stage (spec section 8)")


def _code_for(kind: str, source: Any, frame: FrameType) -> Any:
    site = _site(frame)
    if site in _refused:         # a phase policy, enforced whether or not the dry run staged the text
        _refuse(_refused[site])
    if isinstance(source, _CodeType):
        if id(source) in _staged_code:       # code a staged compile() returned: compiled at build time
            return source
        _refuse(f"E-01: {kind} of a code object at {_where(frame)}")
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    if not isinstance(text, str):
        _refuse(f"E-01: {kind} of a {type(source).__name__} at {_where(frame)}")
    if _mechanism == "intrinsics":
        fields = frame.f_locals.get("field_names") if site == _NAMEDTUPLE_SITE else None
        code = _intrinsics.get(tuple(fields)) if fields is not None else None
        if code is None:
            _refuse(f"E-01: {kind} at {_where(frame)}: no compiler intrinsic generates this code (fields {fields!r})")
        return code
    staged = _texts.get((site, kind, text))
    if staged is None:
        _miss(kind, frame)
    code, flags = staged
    if frame.f_code.co_flags & _FUTURE_MASK != flags:     # compiled in another context
        _refuse(f"E-01: {kind} at {_where(frame)}: the caller's __future__ flags differ from the staged code's")
    return code


def _namespaces(frame: FrameType, g: Any, loc: Any) -> tuple[Any, Any]:
    if g is None:
        g = frame.f_globals
        if loc is None:      # PEP 667: a function's locals() is a snapshot
            loc = dict(frame.f_locals) if frame.f_code.co_flags & 0x1 else frame.f_locals
    return g, loc


def exec(source: Any, globals: Any = None, locals: Any = None, /, *, closure: Any = None) -> None:  # noqa: A001
    frame = sys._getframe(1)
    if closure is not None and not isinstance(source, _CodeType):
        raise TypeError("closure can only be used when source is a code object")   # as CPython's exec
    code = _code_for("exec", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    if closure is None:
        _REAL_EXEC(code, g, loc)  # noqa: S102  # staged code, compiled at build time
    else:
        _REAL_EXEC(code, g, loc, closure=closure)  # noqa: S102


def eval(source: Any, globals: Any = None, locals: Any = None, /) -> Any:  # noqa: A001
    frame = sys._getframe(1)
    code = _code_for("eval", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    return _REAL_EVAL(code, g, loc)  # noqa: S307


def compile(source: Any, filename: Any, mode: str, flags: int = 0, dont_inherit: bool = False,  # noqa: A001
            optimize: int = -1, *, module: Any = None, _feature_version: int = -1) -> Any:
    """A staged compile() returns the code compiled at build time, or raises what it raised."""
    frame = sys._getframe(1)
    caller: FrameType | None = frame
    while caller is not None:
        if caller.f_globals.get("__name__") == "traceback":
            return _REAL_COMPILE(source, filename, mode, flags, dont_inherit, optimize, module=module,
                                 _feature_version=_feature_version)
        caller = caller.f_back
    site = _site(frame)
    if site in _refused:
        _refuse(_refused[site])
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    if not isinstance(text, str) or flags & _AST_RESULT:
        _refuse(f"E-01: compile at {_where(frame)}")
    inherited = 0 if dont_inherit else frame.f_code.co_flags & _FUTURE_MASK
    outcome = _compiled.get((site, "compile", text, str(filename), str(mode), flags | inherited, optimize, module, _feature_version))
    if outcome is None:
        _miss("compile", frame)
    if outcome[0] == "raises":
        cls = getattr(builtins, outcome[1], None)
        if not (isinstance(cls, type) and issubclass(cls, BaseException)):
            _refuse(f"E-01: compile at {_where(frame)} raised {outcome[1]}, which is not a built-in exception")
        raise cls(*outcome[2])
    return outcome[1]


def _unsupported_function(module: str, function: str) -> Any:
    def refused(*args: object, **kwargs: object) -> NoReturn:
        _refuse(f"[P2+] {module}.{function} is unsupported in phase 1: it imports a module phase 1 does not have "
                "(manifest [lazy_unsupported])")
    return refused


def _entry_point(annotate: object) -> tuple[tuple[str, ...], Any]:
    code = getattr(annotate, "__code__", None)       # model only: the compiler attaches the entry point
    entry = None
    if isinstance(code, _CodeType):
        entry = _entry_points.get(f"{os.path.realpath(code.co_filename)}::{code.co_qualname}::{code.co_firstlineno}")
    if entry is None:
        _refuse("[P2+] annotationlib: FORWARDREF and STRING of an annotate function the compiler did not "
                "generate re-run its __code__ (spec section 3; docs/staging.md, decision S-1)")
    return entry


class _Hooks:
    """What the shim asks the runtime (in Bella, what the compiler provides)."""

    @staticmethod
    def has_entry_point(annotate: object) -> bool:
        code = getattr(annotate, "__code__", None)
        return isinstance(code, _CodeType) and (
            f"{os.path.realpath(code.co_filename)}::{code.co_qualname}::{code.co_firstlineno}" in _entry_points)

    @staticmethod
    def annotate_freevars(annotate: object) -> tuple[str, ...]:
        return _entry_point(annotate)[0]

    @staticmethod
    def annotate_with(annotate: object, globals: dict[str, Any], closure: tuple[Any, ...] | None = None,
                      argdefs: object = None, kwdefaults: object = None) -> Any:
        """The function CPython builds from annotate.__code__ with these globals and cells: the
        entry point, called with them."""
        freevars, code = _entry_point(annotate)
        entry: Any = _FunctionType(code, {"_rt": _rt, "__builtins__": builtins})
        cells = dict(zip(freevars, closure or (), strict=True))
        return lambda format: entry(format, globals, cells)

    @staticmethod
    def refuse(message: str) -> NoReturn:
        _refuse(message)


class _ShimLoader:
    @staticmethod
    def create_module(spec: object) -> None:
        return None

    @staticmethod
    def exec_module(module: object) -> None:
        origin = module.__spec__.origin  # type: ignore[attr-defined]
        with open(origin, "rb") as f:
            code = _REAL_COMPILE(f.read(), origin, "exec", dont_inherit=True)
        vars(module)["_bella"] = _Hooks
        _REAL_EXEC(code, vars(module))  # noqa: S102


def _signature_refused(*args: object, **kwargs: object) -> NoReturn:
    _refuse("[P2+] inspect: the signature of a compiled function needs its metadata at runtime, which "
            "phase 1 does not have (decision S-2, docs/staging.md)")


class _PatchingLoader:
    """A module whose code reaches what a compiled program cannot provide, with that one entry
    point replaced by its refusal (model only: in Bella the refusal is where `__code__` is read)."""

    patches: dict[str, dict[str, Any]] = {"inspect": {"_signature_from_function": _signature_refused}}

    def __init__(self, loader: Any, name: str) -> None:
        self._loader, self._name = loader, name

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._loader, attr)

    def create_module(self, spec: object) -> object:
        return self._loader.create_module(spec)

    def exec_module(self, module: object) -> None:
        self._loader.exec_module(module)
        for qualname, replacement in self.patches[self._name].items():
            owner: Any = module
            *path, attr = qualname.split(".")
            for part in path:            # Logger.__reduce__: the method of a class
                owner = getattr(owner, part)
            setattr(owner, attr, replacement)


class _ShimFinder:
    shims: dict[str, str] = {}

    @classmethod
    def find_spec(cls, name: str, path: object = None, target: object = None) -> object:
        if name in _PatchingLoader.patches:
            finders: list[Any] = list(sys.meta_path)
            for finder in finders:
                spec = None if finder is cls else finder.find_spec(name, path, target)
                if spec is not None:
                    spec.loader = _PatchingLoader(spec.loader, name)
                    return spec
        origin = cls.shims.get(name)
        if origin is None:
            return None
        spec = sys.modules["_frozen_importlib"].ModuleSpec(name, _ShimLoader, origin=origin)
        spec.has_location = True
        return spec


def _install() -> None:
    for name in filter(None, os.environ.get("BELLA_SIMULATE_BLOCK", "").split(",")):
        sys.modules[name] = None  # type: ignore[assignment]  # D-20, as conformance/simulate does
    for path in filter(None, os.environ.get("BELLA_STAGING_ARTEFACTS", "").split(os.pathsep)):
        with open(path, "rb") as f:
            data = marshal.load(f)
        if data["optimize"] != sys.flags.optimize:
            _refuse(f"E-01: {path} was staged at optimisation level {data['optimize']}, not {sys.flags.optimize}")
        _texts.update(data["texts"])
        _compiled.update(data["compiled"])
        _staged_code.update(id(o[1]) for o in data["compiled"].values() if o[0] == "code")
        _entry_points.update(data["annotations"])
        _refused.update(data["refused"])
        _unstaged.update(data["unstaged"])
        for module, functions in data["unsupported"].items():
            for function in functions:
                _PatchingLoader.patches.setdefault(module, {})[function] = _unsupported_function(module, function)
        _intrinsics.update(data["intrinsics"])
    with open(os.environ["BELLA_STAGING_RT"], "rb") as f:
        _REAL_EXEC(_REAL_COMPILE(f.read(), f.name, "exec", dont_inherit=True), vars(_rt))  # noqa: S102
    shims = os.environ.get("BELLA_STAGING_SHIMS", "")
    for entry in sorted(os.listdir(shims)) if shims else ():
        if entry.endswith(".py"):
            _ShimFinder.shims[entry[:-3]] = os.path.join(shims, entry)
    sys.meta_path.insert(0, _ShimFinder)  # type: ignore[arg-type]
    for name in [n for n in _PatchingLoader.patches if sys.modules.get(n) is not None]:   # loaded at start-up
        for qualname, replacement in _PatchingLoader.patches[name].items():
            owner: Any = sys.modules[name]
            *parts, attr = qualname.split(".")
            for part in parts:
                owner = getattr(owner, part)
            setattr(owner, attr, replacement)
    for loader in ("_frozen_importlib", "_frozen_importlib_external"):
        vars(sys.modules[loader]).update(exec=_REAL_EXEC, compile=_REAL_COMPILE)
    builtins.exec = exec        # type: ignore[assignment]
    builtins.eval = eval        # type: ignore[assignment]
    builtins.compile = compile


if os.environ.get("BELLA_STAGING") == "replay":
    _install()
