"""The replay model: a program run as the compiled program would run it (docs/staging.md).

pipeline/staging/run.py puts this directory on PYTHONPATH, so CPython runs this file at
start-up, before the program, and then runs the program exactly as `python script.py` would
(same `__main__`, arguments, tracebacks). From here on:

* the phase-1 configuration holds: the D-20 omissions behave as modules not installed;
* `exec` and `eval` of a text run only code staged by the dry run, looked up by call site and
  text and compiled at build time (the stand-in for the C++ the compiler emits); any other text,
  any code object and any `compile` stop the program with the E-01 refusal, which no `except`
  clause sees (design section 10.4: a refusal is not a Python exception);
* `annotationlib` is the phase-1 shim (runtime/shims/annotationlib.py), whose `__code__`
  fallbacks read the build-time tables.

Model scaffolding, not part of the contract: the import system keeps the real `exec` and
`compile` (a compiled program has no loader; its modules are compiled in), and so does the
`traceback` module's parse for carets (the traceback adaptation formats from source maps). The
shim's tables are found by the annotate function's code object, where the compiler would attach
them to the function it generates. Nothing is imported here that start-up has not imported.
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
    return f"{frame.f_globals.get('__name__')}:{frame.f_code.co_qualname}:{frame.f_lineno}"


_texts: dict[tuple[str, str], Any] = {}             # (site, text) -> code compiled at build time
_tables: dict[str, dict[str, Any]] = {}
_intrinsics: dict[tuple[str, ...], Any] = {}
_mechanism = os.environ.get("BELLA_STAGING_MECHANISM", "staged")
_NAMEDTUPLE_SITE = "collections:namedtuple:447"


def _code_for(kind: str, source: Any, frame: FrameType) -> Any:
    site = _site(frame)
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    if not isinstance(text, str):
        _refuse(f"E-01: {kind} of a code object at {site}")
    if _mechanism == "intrinsics":
        fields = frame.f_locals.get("field_names") if site == _NAMEDTUPLE_SITE else None
        code = _intrinsics.get(tuple(fields)) if fields is not None else None
        if code is None:
            _refuse(f"E-01: {kind} at {site}: no compiler intrinsic generates this code (fields {fields!r})")
        return code
    code = _texts.get((site, text))
    if code is None:
        _refuse(f"E-01: {kind} at {site} of a text the dry run did not stage (spec section 8)")
    return code


def _namespaces(frame: FrameType, g: Any, loc: Any) -> tuple[Any, Any]:
    if g is None:
        g = frame.f_globals
        if loc is None:      # PEP 667: a function's locals() is a snapshot
            loc = dict(frame.f_locals) if frame.f_code.co_flags & 0x1 else frame.f_locals
    return g, loc


def exec(source: Any, globals: Any = None, locals: Any = None, /, *, closure: Any = None) -> None:  # noqa: A001
    frame = sys._getframe(1)
    code = _code_for("exec", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    _REAL_EXEC(code, g, loc)  # noqa: S102  # staged code, compiled at build time


def eval(source: Any, globals: Any = None, locals: Any = None, /) -> Any:  # noqa: A001
    frame = sys._getframe(1)
    code = _code_for("eval", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    return _REAL_EVAL(code, g, loc)  # noqa: S307


def compile(source: Any, filename: Any, mode: str, *args: Any, **kwargs: Any) -> Any:  # noqa: A001
    frame = sys._getframe(1)
    caller: FrameType | None = frame
    while caller is not None:
        if caller.f_globals.get("__name__") == "traceback":
            return _REAL_COMPILE(source, filename, mode, *args, **kwargs)
        caller = caller.f_back
    _refuse(f"E-01: compile at {_site(frame)}")


class _Hooks:
    """What the shim asks the runtime (in Bella, intrinsics the compiler provides)."""

    @staticmethod
    def compiled_annotations(annotate: object) -> dict[str, Any] | None:
        code = getattr(annotate, "__code__", None)   # model only: the compiler attaches the entry
        if not isinstance(code, _CodeType):
            return None
        key = f"{os.path.realpath(code.co_filename)}::{code.co_qualname}::{code.co_firstlineno}"
        return _tables.get(key)

    @staticmethod
    def refuse(message: str) -> NoReturn:
        _refuse(message)

    @staticmethod
    def exception(recorded: list[str]) -> BaseException:
        cls = getattr(builtins, recorded[0], None)
        if not (isinstance(cls, type) and issubclass(cls, BaseException)):
            _refuse(f"[P2+] annotationlib: the fallback raises {recorded[0]}, which is not a built-in exception")
        exception: BaseException = cls(recorded[1])
        return exception


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


class _ShimFinder:
    shims: dict[str, str] = {}

    @classmethod
    def find_spec(cls, name: str, path: object = None, target: object = None) -> object:
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
        _texts.update(data["texts"])
        _tables.update(data["annotations"])
        _intrinsics.update(data["intrinsics"])
    shims = os.environ.get("BELLA_STAGING_SHIMS", "")
    for entry in sorted(os.listdir(shims)) if shims else ():
        if entry.endswith(".py"):
            _ShimFinder.shims[entry[:-3]] = os.path.join(shims, entry)
    sys.meta_path.insert(0, _ShimFinder)  # type: ignore[arg-type]
    for loader in ("_frozen_importlib", "_frozen_importlib_external"):
        vars(sys.modules[loader]).update(exec=_REAL_EXEC, compile=_REAL_COMPILE)
    builtins.exec = exec        # type: ignore[assignment]
    builtins.eval = eval        # type: ignore[assignment]
    builtins.compile = compile


if os.environ.get("BELLA_STAGING") == "replay":
    _install()
