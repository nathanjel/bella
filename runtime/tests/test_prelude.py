"""The prelude (runtime/prelude/*.py) run by CPython against the builtins it stands for.

The prelude is Python that Bella compiles into every program (docs/DECISIONS.md, step 3 of the
C++ leg). Run by CPython itself, each function must do what the builtin does, observed through
what it calls: the exact sequence of write() and flush() calls on a file object, the values it
str()s, and the exceptions (type and message) it raises, in the same order of checks.

Run under pytest or directly: python3 runtime/tests/test_prelude.py
"""
from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
import sys
import types
from pathlib import Path
from typing import Any

PRELUDE = Path(__file__).resolve().parents[1] / "prelude"


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"bella_prelude_{name}", PRELUDE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    """A file object that records every call print makes on it."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def write(self, s: object) -> int:
        self.calls.append(("write", s))
        return len(s) if isinstance(s, str) else 0

    def flush(self) -> None:
        self.calls.append(("flush", None))


class Loud:
    """str() of it is observable: it records the call."""

    def __init__(self, log: list[str], name: str) -> None:
        self.log, self.name = log, name

    def __str__(self) -> str:
        self.log.append(self.name)
        return f"<{self.name}>"


class Text(str):
    def __str__(self) -> str:
        return "subclass str()"


def outcome(fn: Any, *args: object, **kwargs: object) -> tuple[object, ...]:
    rec = Recorder()
    log: list[str] = []
    args = tuple(Loud(log, a[1:]) if isinstance(a, str) and a.startswith("@") else a for a in args)
    if kwargs.get("file") == "rec":
        kwargs["file"] = rec
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = fn(*args, **kwargs)
        return ("ok", result, rec.calls, log, out.getvalue())
    except Exception as exc:  # noqa: BLE001 -- the exception is the observable
        return ("raised", type(exc).__name__, str(exc), rec.calls, log)


def test_print_matches_the_builtin() -> None:
    prelude = load("builtins")
    cases: list[tuple[tuple[object, ...], dict[str, object]]] = [
        ((), {}),
        ((1, "a", None, True), {}),
        ((1, 2), {"sep": "-", "end": "!"}),
        ((1, 2), {"sep": None, "end": None}),
        (("@x", "@y"), {"file": "rec"}),
        (("@x", "@y"), {"file": "rec", "sep": Text(","), "end": Text(";")}),
        ((1,), {"file": "rec", "flush": True}),
        ((1,), {"file": "rec", "flush": 0}),
        (("@x",), {"sep": 5}),
        (("@x",), {"end": b"x"}),
        (("@x",), {"sep": 5, "end": 5}),
        (("@x",), {"file": "rec", "sep": 1.5}),
    ]
    for args, kwargs in cases:
        want = outcome(builtins.print, *args, **dict(kwargs))
        got = outcome(prelude.print, *args, **dict(kwargs))
        assert got == want, f"print(*{args}, **{kwargs}):\n  prelude {got}\n  builtin {want}"


def test_print_does_nothing_without_a_stdout() -> None:
    prelude = load("builtins")
    saved = sys.stdout
    try:
        sys.stdout = None  # type: ignore[assignment]
        builtins.print("x", sep=5)          # file is resolved first: no TypeError
        prelude.print("x", sep=5)
    finally:
        sys.stdout = saved


def descriptor_story(prop: Any, sm: Any, cm: Any) -> list[object]:
    """The same class built on the given property, staticmethod and classmethod: what a program
    sees through them, and the messages of their errors."""
    out: list[object] = []

    def getx(self: Any) -> object:
        """the x docstring"""
        return self._x

    def setx(self: Any, v: object) -> None:
        self._x = v

    def delx(self: Any) -> None:
        del self._x

    class C:
        x = prop(getx, setx, delx)
        ro = prop(getx)
        nogetter = prop(None, setx)

        @sm
        def twice(n: int) -> int:
            return n * 2

        @cm
        def who(cls: type) -> str:
            return cls.__name__

    class D(C):
        pass

    c = C()
    c.x = 5
    out += [c.x, C.x.__doc__, C.ro.__doc__, C.twice(3), c.twice(4), C.who(), D.who(), D().who(), type(C.__dict__["x"]).__name__]
    for f in (lambda: setattr(c, "ro", 1), lambda: delattr(c, "ro"), lambda: c.nogetter):
        try:
            f()
        except AttributeError as e:
            out.append(("AttributeError", str(e)))
    del c.x
    out.append(hasattr(c, "_x"))
    wrapped = C.__dict__["twice"]
    out += [wrapped.__func__ is wrapped.__wrapped__, wrapped.__name__, C.__dict__["who"].__func__.__name__]
    q = C.x.setter(setx)
    out += [q.__doc__, q.fget is getx, C.x.getter(lambda s: 1).__doc__]
    anon = prop()

    class E:
        y = anon
    try:
        E().y  # noqa: B018 -- the read raises, which is the point
    except AttributeError as e:
        out.append(str(e))
    return out


def test_property_staticmethod_classmethod_match_the_builtins() -> None:
    prelude = load("builtins")
    want = descriptor_story(property, staticmethod, classmethod)
    got = descriptor_story(prelude.property, prelude.staticmethod, prelude.classmethod)
    # the prelude's classes are named as the builtins; only type(...).__name__ above shows them
    assert got == want, f"\n  prelude {got}\n  builtin {want}"


def test_container_repr_matches_the_builtins() -> None:
    prelude = load("builtins")
    funcs = {list: prelude._list_repr, tuple: prelude._tuple_repr, dict: prelude._dict_repr,
             set: prelude._set_repr, frozenset: prelude._frozenset_repr, type({}.keys()): prelude._keys_repr,
             type({}.values()): prelude._values_repr, type({}.items()): prelude._items_repr}

    saved = builtins.repr

    def prelude_repr(x: object) -> str:
        f = funcs.get(type(x)) or next((g for t, g in funcs.items() if isinstance(x, t)), None)
        return f(x) if f is not None else saved(x)

    builtins.repr = prelude_repr  # type: ignore[assignment]  # nested containers through the prelude too
    try:
        loop: list[object] = [1]
        loop.append(loop)
        d: dict[object, object] = {}
        d["self"] = d
        class S(set[int]):
            pass
        view_loop: dict[str, object] = {}
        view_loop["self"] = view_loop.values()
        values: list[object] = [[], [1, "a"], (), (1,), (1, 2), {}, {"k": [1, (2,)]}, loop, (loop,), d, set(), {3},
                                frozenset(), frozenset({1}), S({2}), S(), {}.keys(), {"a": 1}.keys(), {"a": [1]}.values(),
                                {"a": (1,)}.items(), view_loop.values(), view_loop]
        for v in values:
            assert prelude_repr(v) == saved(v), f"{saved(v)}: prelude {prelude_repr(v)}"
    finally:
        builtins.repr = saved


def test_type_methods_check_their_receiver_a9_2() -> None:
    """list.__repr__(5) and the like: the prelude's methods of the C++ types refuse a receiver of
    another type with the slot wrapper's TypeError (review 2026-11-03, A9-2)."""
    prelude = load("builtins")
    for key, methods in prelude.__type_methods__.items():
        cls = key if isinstance(key, type) else getattr(builtins, key)
        type_name = cls.__name__
        for name, fn in methods.items():
            for wrong in (5, [], (), {}, set(), frozenset()):
                if isinstance(wrong, cls):
                    continue
                want = outcome(getattr(cls, name), wrong)
                got = outcome(fn, wrong)
                assert got == want, f"{type_name}.{name}({wrong!r}):\n  prelude {got}\n  builtin {want}"


def _bootstrap(find: Any) -> Any:
    """runtime/prelude/bootstrap.py under CPython, as `_frozen_importlib`, with the runtime's
    primitives stood in for: what the compiled runtime gives it, for the spec it builds."""
    source = (PRELUDE / "bootstrap.py").read_text(encoding="utf-8")
    module = types.ModuleType("_frozen_importlib")
    module.__dict__.update(_bella_find=find, _bella_is_builtin=lambda name: False, _bella_refuse=None, _bella_exec=None,
                           _bella_create_builtin=None, _bella_import_warning=None, _bella_set_lazy_attributes=None,
                           _bella_shutting_down=lambda: False)
    exec(compile(source, "bootstrap.py", "exec"), module.__dict__)  # noqa: S102  # the module under test
    return module


def test_the_frozen_path_makes_cpythons_spec() -> None:
    """`abc` is the first frozen module a compiled program will reach, and it waits for `_abc`: until
    then this is the check of FrozenImporter's port, against CPython's own spec for a frozen module."""
    import _imp
    import importlib.machinery
    assert _imp.is_frozen("stat")
    real = importlib.machinery.FrozenImporter.find_spec("stat")
    origin = real.loader_state.filename
    b = _bootstrap(lambda name: (origin, False, True) if name == "stat" else None)
    spec = b._spec_from_compiled("stat")
    assert repr(spec).replace(" object at", "") == repr(real).replace(" object at", ""), (spec, real)
    assert (spec.name, spec.origin, spec.parent, spec.has_location, spec.cached, spec.submodule_search_locations) == \
        (real.name, real.origin, real.parent, real.has_location, real.cached, real.submodule_search_locations)
    assert vars(spec.loader_state) == vars(real.loader_state)
    assert repr(spec.loader_state) == repr(real.loader_state)
    module = b.module_from_spec(spec)
    ours = list(vars(module))
    made = importlib.util.module_from_spec(real)
    assert ours == list(vars(made)), (ours, list(vars(made)))
    assert b._module_repr(module) == repr(made) and module.__file__ == made.__file__ and module.__package__ == made.__package__
    assert b._find_spec("nothing_at_all", None) is None


def test_the_source_path_makes_cpythons_spec() -> None:
    import importlib.machinery
    real = importlib.machinery.PathFinder.find_spec("json")
    assert real is not None and real.origin is not None
    b = _bootstrap(lambda name: (real.origin, True, False) if name == "json" else None)
    spec = b._spec_from_compiled("json")
    assert (spec.name, spec.origin, spec.parent, spec.has_location, spec.submodule_search_locations, spec.loader_state) == \
        (real.name, real.origin, real.parent, real.has_location, list(real.submodule_search_locations), real.loader_state)
    assert spec.cached is None and real.cached is not None       # D-16: no bytecode cache
    assert (type(spec.loader).__name__, type(spec.loader).__module__, spec.loader.name, spec.loader.path) == \
        (type(real.loader).__name__, type(real.loader).__module__, real.loader.name, real.loader.path)
    assert spec.loader.is_package("json") and spec.loader.get_filename("json") == real.loader.get_filename("json")
    assert b._module_repr(b.module_from_spec(spec)) == repr(importlib.util.module_from_spec(real))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
