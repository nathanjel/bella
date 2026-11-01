"""The staging prototype (Gate 0 task 5, docs/staging.md): the pieces, and the refusals the
conformance corpus cannot show because CPython passes where Bella must stop.

The corpus itself runs under the replay in `make staging-check` (pipeline/staging/check.py).
"""
from __future__ import annotations

import collections
import os
import subprocess
import sys
import tempfile
import textwrap
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.staging import annotations as tables  # noqa: E402
from pipeline.staging import intrinsics, scan  # noqa: E402

RUN = ROOT / "pipeline" / "staging" / "run.py"
CASES = ROOT / "conformance" / "cases"


def _replay(source: str, *options: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp, "prog.py")
        script.write_text(textwrap.dedent(source), encoding="utf-8")
        return subprocess.run([sys.executable, str(RUN), *options, str(script)], capture_output=True, text=True,
                              env=dict(os.environ, PYTHONHASHSEED="0"), check=False, timeout=600)


def test_annotation_tables_answer_as_cpython_does() -> None:
    """Build-time STRING forms equal what CPython's own fallback returns at runtime; a form that
    is not a build-time constant (a set of strings, a lambda) is marked unstable."""
    source = textwrap.dedent('''
        import typing
        def f(a: int | None, b: list["Q"], c: typing.Callable[[int], str], *r: int, k: typing.Literal[1, "x"] = 1) -> dict[str, "Q"]: ...
        def g(a: -1, b: (int, str), c: ..., d: None, e: 1 / 0) -> "x": ...
        def h(a: {"p", "q"}, b: lambda: 0) -> None: ...
        class C:
            x: int
            y: "C"
        def outer():
            T = int
            def inner(a: T, b: list[T]) -> T: ...
            return inner
        z: tuple[int, ...] = ()
    ''')
    import annotationlib
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "mod.py")
        path.write_text(source, encoding="utf-8")
        built = tables.tables_for_source(str(path))
        module = types.ModuleType("mod")
        module.__file__ = str(path)
        # as the import system compiles it: without this file's `from __future__ import annotations`
        exec(compile(source, str(path), "exec", dont_inherit=True), vars(module))  # noqa: S102  # CPython itself
    objects = [module.f, module.g, module.h, module.C, module.outer(), module]
    assert len(built) == len(objects)
    for obj in objects:
        code = obj.__annotate__.__code__
        entry = built[tables.entry_key(code.co_filename, code.co_qualname, code.co_firstlineno)]
        try:
            expected: object = annotationlib.get_annotations(obj, format=annotationlib.Format.STRING)
        except ZeroDivisionError:
            expected = "raises"
        if obj is module.h:
            assert entry["unstable"] is not None and "a" in entry["unstable"] and "b" in entry["unstable"]
        elif expected == "raises":
            assert entry["string_raises"] is not None and entry["string_raises"][0] == "ZeroDivisionError"
            assert entry["second_raises"] is not None and entry["second_raises"][0] == "ZeroDivisionError"
        else:
            assert entry["string"] == expected, (obj, entry["string"], expected)


def test_scan_names_sites_as_frames_do_and_resolves_aliases() -> None:
    source = textwrap.dedent('''
        from collections import namedtuple as nt
        import collections as c
        import typing as t
        exec("x = 1")
        P = nt("P", "a b")
        def f():
            def g():
                return eval("1")
            Q = c.namedtuple("Q", ["x"], rename=True)
            class N(t.NamedTuple):
                k: int
                v: str
            return lambda: compile("1", "<s>", "eval")
        class K:
            def m(self):
                exec(self.text)
        R = nt("R", computed)
    ''')
    sites, calls = scan.scan(source, "mod", "mod.py")
    assert sites == [("mod:<module>:5", "exec"), ("mod:f.<locals>.g:9", "eval"),
                     ("mod:f.<locals>.<lambda>:14", "compile"), ("mod:K.m:17", "exec")]
    assert [(c.typename, c.fields, c.rename) for c in calls] == [
        ("P", "a b", False), ("Q", ("x",), True), ("N", ("k", "v"), False)]


def test_the_intrinsic_template_is_namedtuples() -> None:
    """The compiler's copy of namedtuple's field processing agrees with collections.namedtuple."""
    specs: list[tuple[str | tuple[str, ...], bool]] = [
        ("x y", False), ("x, y", False), (("a",), False), ("abc def abc _x", True), ("x x", False),
        ("_x", False), ("x def", False), ("1x", True), ((), False)]
    for fields, rename in specs:
        try:
            factory: Any = collections.namedtuple   # called with values, which mypy's plugin cannot read
            made: Any = factory("T", fields, rename=rename)
            expected: tuple[str, ...] | None = made._fields
        except ValueError:
            expected = None
        assert intrinsics.namedtuple_fields(fields, rename) == expected, (fields, rename)
    assert intrinsics.namedtuple_new_text(("a",)) == "lambda _cls, a,: _tuple_new(_cls, (a,))"


def test_a_text_the_dry_run_did_not_stage_stops_the_program() -> None:
    """A dataclass made under the main guard, which the dry run does not run: its exec text was
    never staged. The refusal is not an exception: neither `except BaseException` nor `finally`
    sees it, and output is flushed."""
    proc = _replay('''
        import dataclasses
        def make(names: list[str]) -> type:
            return dataclasses.make_dataclass("Made", names)
        if __name__ == "__main__":
            print("before")
            try:
                make(["p", "q"])
            except BaseException:
                print("caught")
            finally:
                print("finally")
    ''')
    assert proc.returncode == 70, proc.stderr
    assert proc.stdout == "before\n"
    assert "E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class:499" in proc.stderr


def test_a_literal_namedtuple_in_a_function_is_staged_by_a_probe() -> None:
    """Only the main guard calls make(): the probe stages its literal fields. Computed fields
    match a staged text when they spell the same fields, and are refused when they do not."""
    ok = _replay('''
        import collections
        def make() -> type:
            return collections.namedtuple("Pt", "u v w")
        if __name__ == "__main__":
            print(make()(1, 2, 3))
    ''')
    assert (ok.returncode, ok.stdout) == (0, "Pt(u=1, v=2, w=3)\n"), ok.stderr
    computed = _replay('''
        import collections
        def make(fields: str) -> type:
            return collections.namedtuple("Pt", fields)
        def literal() -> type:
            return collections.namedtuple("Pt", "u v w")
        if __name__ == "__main__":
            print(make(" ".join(["u", "v", "w"]))(1, 2, 3))
            print(make(" ".join(["u", "x"]))(1, 2))
    ''')
    assert computed.returncode == 70 and computed.stdout == "Pt(u=1, v=2, w=3)\n", (computed.stdout, computed.stderr)
    assert "eval at collections:namedtuple:447 of a text the dry run did not stage" in computed.stderr


def test_compile_and_code_objects_are_refused() -> None:
    proc = _replay('''
        if __name__ == "__main__":
            print(eval("1 + 1"))
    ''')
    assert proc.returncode == 70 and "E-01: eval at __main__:<module>:3" in proc.stderr, proc.stderr
    proc = _replay('''
        code = compile("1", "<s>", "eval")
    ''')
    assert proc.returncode == 70 and "E-01: compile at __main__:<module>:2" in proc.stderr, proc.stderr


def test_the_unbound_forwardref_boundary_is_refused_as_p2() -> None:
    proc = subprocess.run([sys.executable, str(RUN), "C-3-22_forwardref_unbound_name.py"], cwd=CASES,
                          capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="0"), check=False)
    assert proc.returncode == 70 and "[P2+]" in proc.stderr and "FORWARDREF" in proc.stderr, proc.stderr


def test_intrinsics_alone_do_not_cover_dataclasses() -> None:
    proc = subprocess.run([sys.executable, str(RUN), "--mechanism", "intrinsics", "C-8-08_staged_dataclass.py"],
                          cwd=CASES, capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="0"), check=False)
    assert proc.returncode == 70 and "no compiler intrinsic" in proc.stderr, proc.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
