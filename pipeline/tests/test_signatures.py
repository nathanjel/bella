"""inspect.signature compiled, against CPython (decision S-2 as revised 2026-11-10; C-3-24 is the case): the messages of bind,
which the case does not compare; signatures after a function's defaults are rebound; nested functions, properties, descriptors
and abstract methods; and the boundary: the signature of a built-in, which CPython parses from __text_signature__, stops by
name, and so does a class that defines neither __init__ nor __new__, since it takes object's."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import inspect
def f(a, b=2, /, c=3, *args, d, e=5, **kw):
    pass
def g(x, *, y):
    pass
sig = inspect.signature(f)
for call in (lambda: sig.bind(), lambda: sig.bind(1), lambda: sig.bind(1, d=4, b=9), lambda: sig.bind_partial(), lambda: sig.bind_partial(d=1, a=2),
             lambda: inspect.signature(g).bind(1, 2), lambda: inspect.signature(g).bind(1), lambda: inspect.signature(g).bind(1, y=2, z=3),
             lambda: inspect.signature(g).bind(x=1, y=2, **{"x ": 3}), lambda: inspect.signature(g).bind(1, x=2, y=3),
             lambda: inspect.signature(5), lambda: inspect.signature("text"), lambda: inspect.signature(None),
             lambda: inspect.Parameter("1bad", inspect.Parameter.KEYWORD_ONLY), lambda: inspect.Parameter("p", 99),
             lambda: inspect.Parameter("p", inspect.Parameter.VAR_POSITIONAL, default=1),
             lambda: inspect.Signature([inspect.Parameter("p", inspect.Parameter.KEYWORD_ONLY), inspect.Parameter("q", inspect.Parameter.POSITIONAL_ONLY)]),
             lambda: inspect.Signature([inspect.Parameter("p", inspect.Parameter.KEYWORD_ONLY), inspect.Parameter("p", inspect.Parameter.KEYWORD_ONLY)]),
             lambda: sig.replace(parameters=[1]), lambda: inspect.getfullargspec(5)):
    try:
        r = call()
        print(type(r).__name__, getattr(r, "arguments", r))
    except (TypeError, ValueError, AttributeError) as e:
        print(type(e).__name__, e)
print(repr(sig), repr(sig.parameters["c"]), sig.parameters["a"].kind.description, str(inspect.Parameter.VAR_KEYWORD))
"""

SHAPES = r"""
import abc, functools, inspect
def outer(n):
    def inner(a, b=n, *, c=n * 2):
        return a
    return inner
f = outer(5)
print(inspect.signature(f))
f.__defaults__ = (7, 8)
f.__kwdefaults__ = {"c": "kw"}
print(inspect.signature(f), f.__code__.co_varnames[:f.__code__.co_argcount])
f.__defaults__ = None
f.__kwdefaults__ = None
print(inspect.signature(f))
class Base(abc.ABC):
    @abc.abstractmethod
    def run(self, job: str, *, dry: bool = False) -> int: ...
    @property
    def size(self) -> int:
        return 0
    @functools.cached_property
    def cached(self) -> str:
        return ""
    def _plain(self, x): pass
    method = functools.partialmethod(_plain, 1)
class Impl(Base):
    def run(self, job, *, dry=False, extra=None):
        return 1
    @classmethod
    def build(cls, *parts, sep="/"):
        return cls()
    @staticmethod
    def join(a, b):
        return a
print(inspect.signature(Base.run), inspect.signature(Impl.run), inspect.signature(Impl().run), inspect.signature(Impl.build),
      inspect.signature(Impl().build), inspect.signature(Impl.join), inspect.signature(Impl.__dict__["join"]),
      inspect.signature(Base.size.fget), inspect.signature(Impl().method))   # inspect.signature(Impl) is object's: STOPS
class Meta(type):
    def __call__(cls, first, second=2):
        return super().__call__()
class WithMeta(metaclass=Meta):
    pass
class Sub(dict):
    def __init__(self, source=(), /, *, strict=False):
        super().__init__(source)
print(inspect.signature(WithMeta), inspect.signature(Sub), inspect.signature(Sub().update.__func__) if hasattr(Sub().update, "__func__") else "builtin method")
@functools.lru_cache(maxsize=4)
def cached(a, b=1):
    return a
@functools.singledispatch
def dispatch(value, verbose=False):
    return value
print(inspect.signature(cached), inspect.signature(dispatch), inspect.signature(functools.partial(functools.partial(cached, 1), b=2)))
async def agen(n: int):
    yield n
print(inspect.isasyncgenfunction(agen), inspect.signature(agen), inspect.iscoroutinefunction(agen), inspect.isgeneratorfunction(agen),
      inspect.unwrap(cached) is cached.__wrapped__, inspect.signature(lambda *, k: k), inspect.signature(lambda: 0))
print(inspect.signature(outer).parameters["n"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD, len(inspect.signature(f).parameters),
      inspect.signature(f).parameters == inspect.signature(outer(5)).parameters, inspect.signature(f) == inspect.signature(outer(6)))
"""

# CPython parses these from __text_signature__, which the names table does not carry yet
STOPS = {
    "a built-in function": "import inspect\ninspect.signature(len)",
    "a method descriptor": "import inspect\ninspect.signature(dict.get)",
    "a built-in type": "import inspect\ninspect.signature(int)",
    "a class with neither __init__ nor __new__ (object's)": "import inspect\nclass C:\n    pass\ninspect.signature(C)",
}


def test_messages() -> None:
    same(MESSAGES)


def test_shapes() -> None:
    same(SHAPES)


def test_a_builtins_signature_stops_by_name() -> None:
    if shutil.which("g++") is None:
        return
    for what, body in STOPS.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "__text_signature__" in got.stderr, (what, got)


if __name__ == "__main__":
    test_messages()
    test_shapes()
    test_a_builtins_signature_stops_by_name()
