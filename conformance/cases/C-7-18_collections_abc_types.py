# clause: C-7-18
# spec: section 7
# status: P1
# source: decision P-2 (2026-11-02): the _collections_abc shim takes four types from _types
"""The collection ABCs know the interpreter's own generator, coroutine, async-generator and
frame-locals-proxy types (CPython probes them at import by making the objects; phase 1's
shim imports them), and the module keeps CPython's namespace."""
import _collections_abc
import collections.abc
import types
from collections.abc import Iterator

print(_collections_abc.generator is types.GeneratorType,             # type: ignore[attr-defined]  # not in the stub
      _collections_abc.coroutine is types.CoroutineType,             # type: ignore[attr-defined]  # not in the stub
      _collections_abc.async_generator is types.AsyncGeneratorType,  # type: ignore[attr-defined]  # not in the stub
      _collections_abc.framelocalsproxy is types.FrameLocalsProxyType)  # type: ignore[attr-defined]  # not in the stub


def numbers() -> Iterator[int]:
    yield 1


print(isinstance(numbers(), collections.abc.Generator),
      issubclass(types.GeneratorType, collections.abc.Generator),
      issubclass(types.CoroutineType, collections.abc.Coroutine),
      issubclass(types.AsyncGeneratorType, collections.abc.AsyncGenerator),
      issubclass(types.FrameLocalsProxyType, collections.abc.Mapping))
print(sorted(name for name in vars(_collections_abc) if name.startswith("_") and not name.startswith("__")))
