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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.staging import annotations as entries  # noqa: E402
from pipeline.staging import intrinsics, scan  # noqa: E402

RUN = ROOT / "pipeline" / "staging" / "run.py"
CASES = ROOT / "conformance" / "cases"


def _replay(source: str, *options: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp, "prog.py")
        script.write_text(textwrap.dedent(source), encoding="utf-8")
        return subprocess.run([sys.executable, str(RUN), *options, str(script)], capture_output=True, text=True,
                              env=dict(os.environ, PYTHONHASHSEED="0"), check=False, timeout=600)


GENERATOR_CORPUS = '''
import typing
flag = False
counter: list[int] = []
if flag:
    skipped: int
module_level: list[Unbound]

def plain(a: int, /, b: str | None, *args: *tuple[int, ...], k: typing.Literal[1, "x"] = 1, **kw: float) -> dict[str, "Q"]: ...

class Outer:
    size = int
    __private: list[__Hidden]
    width: size
    if flag:
        maybe: bytes
    try:
        risky: Unbound
    except ValueError:
        pass
    def method(self, __arg: __Hidden, other: Outer) -> size: ...
    class Inner:
        __deep: __Deep
        def m(self, x: __Deep) -> Inner: ...

def closure():
    T = int
    nonlocal_target = 0
    def inner(a: T, b: list[Missing]) -> T: ...
    def rebinding():
        nonlocal nonlocal_target
        def uses(x: nonlocal_target, y: T) -> None: ...
        return uses
    class InFunction:
        field: T
        other: Gone
        def m(self, v: T) -> InFunction: ...
    return inner, rebinding(), InFunction

def declared_global():
    global counter
    def f(x: counter) -> None: ...
    return f

def generic[U, *Ts](x: U, *rest: *Ts) -> list[U]: ...

class Box[V]:
    item: V
    def get(self, default: V) -> V: ...

def effects(a: {}["missing"], b: 1 / 0) -> None: ...
'''


def test_every_annotate_function_gets_an_entry_point_that_agrees_with_cpython() -> None:
    """The generator (decision S-1) covers the corpus's shapes, and each entry point passed the
    build-time checks against CPython's own code: the same loads, the same answers under STRING's
    and FORWARDREF's substitute environments. Breaking name resolution, mangling or the
    conditional indices makes the checks fail."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "corpus.py")
        path.write_text(textwrap.dedent(GENERATOR_CORPUS), encoding="utf-8")
        found, declined = entries.evaluators_for_source(str(path))
        compiled = entries._annotate_codes(compile(path.read_bytes(), str(path), "exec", dont_inherit=True))
        assert declined == [] and len(found) == len(compiled) == 15, (len(found), len(compiled), declined)
        broken = {"resolution": (entries, "_resolve", lambda owner, name: "global"),
                  "mangling": (entries, "mangle", lambda private, name: name)}
        for label, (module, attr, fake) in broken.items():
            real = getattr(module, attr)
            setattr(module, attr, fake)
            try:
                _, wrong = entries.evaluators_for_source(str(path))
            finally:
                setattr(module, attr, real)
            assert any("MISMATCH" in d for d in wrong), label


def test_the_closure_and_the_corpus_have_entry_points() -> None:
    """Every annotate function CPython generates for the conformance corpus has a checked entry
    point; what is declined is only hand-written (dataclasses', TypedDict's), never a mismatch."""
    declined: list[str] = []
    for path in sorted(CASES.glob("*.py")):
        declined += entries.evaluators_for_source(str(path))[1]
    assert declined == [], declined


def test_a_hand_written_annotate_has_no_entry_point() -> None:
    """An __annotate__ the compiler did not generate, whose FORWARDREF or STRING CPython answers by
    re-running its code, is refused with the milestone's marker."""
    proc = _replay('''
        import annotationlib
        def annotate(format):
            if format > 2:
                raise NotImplementedError
            return {"x": int}
        class C:
            pass
        C.__annotate__ = annotate
        if __name__ == "__main__":
            print(annotationlib.get_annotations(C, format=annotationlib.Format.STRING))
    ''')
    assert proc.returncode == 70 and "[P2+] annotationlib" in proc.stderr, proc.stderr


def test_an_eval_never_runs_code_staged_for_an_exec() -> None:
    """Review 2026-11-01 astra-low-05, A5-1: the same text at the same site, staged by exec and
    run by eval, is refused instead of running the exec-mode code."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "helper.py").write_text("def generated(evaluate):\n    return (eval if evaluate else exec)(\"1 + 1\")\n\n"
                                          "generated(False)\n", encoding="utf-8")
        Path(tmp, "main.py").write_text("import helper\nif __name__ == \"__main__\":\n    print(helper.generated(True))\n",
                                        encoding="utf-8")
        Path(tmp, "lock.json").write_text('{"roots": ["main"], "modules": {"main": {"status": "program"}, '
                                          '"helper": {"status": "program"}}}', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(RUN), "--program-lock", "lock.json", "main.py"], cwd=tmp,
                              capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="0"), check=False)
    assert proc.returncode == 70 and "E-01: eval at helper:generated:2" in proc.stderr, (proc.stdout, proc.stderr)


def test_a_changed_imported_module_rebuilds_the_artefact() -> None:
    """Review 2026-11-01 astra-low-05, A5-2: the artefact depends on every source it was made
    from, by content, so changing an imported module's annotation is seen by the next run."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "helper.py").write_text("def f(x: int): pass\n", encoding="utf-8")
        Path(tmp, "main.py").write_text("import annotationlib, helper\n"
                                        "print(annotationlib.get_annotations(helper.f, format=annotationlib.Format.STRING))\n",
                                        encoding="utf-8")
        Path(tmp, "lock.json").write_text('{"roots": ["main"], "modules": {"main": {"status": "program"}, '
                                          '"helper": {"status": "program"}}}', encoding="utf-8")
        outputs = []
        for annotation in ("int", "bytes"):
            Path(tmp, "helper.py").write_text(f"def f(x: {annotation}): pass\n", encoding="utf-8")
            outputs.append(subprocess.run([sys.executable, str(RUN), "--program-lock", "lock.json", "main.py"], cwd=tmp,
                                          capture_output=True, text=True, check=False).stdout)
    assert outputs == ["{'x': 'int'}\n", "{'x': 'bytes'}\n"], outputs


def test_inputs_module_bodies_read_are_recorded() -> None:
    """Review 2026-11-01 astra-low-05, A5-3: a module body's own reads, reads through a helper
    module and directory listings are inputs; the import system reading sources is not."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "data.txt").write_text("data", encoding="utf-8")
        Path(tmp, "reader.py").write_text("def read(path):\n    with open(path) as f:\n        return f.read()\n",
                                          encoding="utf-8")
        Path(tmp, "main.py").write_text(textwrap.dedent('''
            import os, reader
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(here, "data.txt")) as f:
                DIRECT = f.read()
            HELPED = reader.read(os.path.join(here, "data.txt"))
            LISTED = os.listdir(here)
        '''), encoding="utf-8")
        out = Path(tmp, "artefact")
        run_module = _load_run()
        run_module.dry_run(out, run_module.phase1_blocked(), ["--entry", str(Path(tmp, "main.py"))])
        import json
        inputs = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["inputs"]
    data = os.path.join(os.path.realpath(tmp), "data.txt")
    main = inputs.get("__main__", [])  # the entry is reported under the name it runs as
    assert sum(1 for i in main if i.startswith("open") and i.endswith("data.txt")) >= 1, inputs
    assert any(i.startswith("os.listdir") for i in main), inputs
    assert not any(i.endswith(".py") for v in inputs.values() for i in v), inputs
    assert "reader" not in inputs, "a helper's read belongs to the body that called it"
    assert any(i == f"open {data}" or i.endswith("data.txt") for i in main), inputs


def _load_run() -> Any:
    import importlib.util
    spec = importlib.util.spec_from_file_location("bella_run", RUN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_evidence_gate_fails_on_a_crashed_harness() -> None:
    """Review 2026-11-01 astra-low-05, A5-4: a non-zero exit with partial output, or no output,
    fails the gate."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bella_check", ROOT / "pipeline" / "staging" / "check.py")
    assert spec is not None and spec.loader is not None
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    crashed = subprocess.CompletedProcess([], 1, "PASS  earlier_case\n", "Traceback (most recent call last):\n  boom\n")
    assert check.judge_corpus(crashed), "a crash after a PASS must fail the gate"
    assert check.judge_corpus(subprocess.CompletedProcess([], 0, "", "")), "no output must fail the gate"
    assert not check.judge_corpus(subprocess.CompletedProcess([], 0, "PASS  a\n\n1/1 passed\n", ""))


REVIEW_PROBES: dict[str, tuple[str, dict[str, str], tuple[str, ...]]] = {
    # review 2026-11-01 gemini-4-argon-high-04: each prints under the replay what CPython prints
    "3.1 a quoted reference in a typing form": (
        "from dataclasses import dataclass\nfrom typing import Optional\n@dataclass\nclass Node:\n"
        "    next: Optional['Node'] = None\nprint(Node())\n", {}, ()),
    "3.1 a NamedTuple with a quoted field": (
        "from typing import NamedTuple\nclass N(NamedTuple):\n    x: 'int'\nprint(N(1))\n", {}, ()),
    "3.1 NamedTuple and TypedDict under PEP 563": (
        "from __future__ import annotations\nfrom typing import NamedTuple, TypedDict\n"
        "class N(NamedTuple):\n    x: list[int]\nclass T(TypedDict):\n    y: int\nprint(N([1]), T(y=1))\n", {}, ()),
    "3.1 an invalid quoted reference is still a SyntaxError": (
        "import typing\ntry:\n    typing.Optional['not valid(']\nexcept SyntaxError as e:\n    print(type(e).__name__, e)\n", {}, ()),
    "3.2B a ForwardRef with a resolved name, repr": (
        "import dataclasses\n@dataclasses.dataclass\nclass Node:\n    x: Node | int = 1\n"
        "print(repr(dataclasses.fields(Node)[0].type), dataclasses.fields(Node)[0].type.__resolved_str__)\n", {}, ()),
    "3.3a exec in a decorator of the entry module": (
        "def dec(c):\n    ns = {}\n    exec('def f(s): return 7', {}, ns)\n    c.f = ns['f']\n    return c\n"
        "@dec\nclass C: pass\nprint(C().f())\n", {}, ()),
    "3.3b an entry named like the module it imports, with -P": (
        "import calendar\nfrom dataclasses import dataclass\n@dataclass\nclass D:\n    m: int = calendar.JANUARY\n"
        "print(D())\n", {"__name__": "calendar.py"}, ("-P",)),
    "3.4a a sibling module without a lock": (
        "import annotationlib, helper\nprint(annotationlib.get_annotations(helper.f, format=annotationlib.Format.STRING), helper.f(1))\n",
        {"helper.py": "import collections\ndef f(x: int) -> str:\n    P = collections.namedtuple('P', 'u v')\n    return str(P(x, x))\n"}, ()),
    "3.4b a lazy import of a module with a dataclass": (
        "lazy import lazy_mod\nif __name__ == '__main__':\n    print(lazy_mod.Cfg())\n",
        {"lazy_mod.py": "from dataclasses import dataclass\n@dataclass\nclass Cfg:\n    host: str = 'localhost'\n"}, ()),
    "3.5c a hand-written annotate, FORWARDREF": (
        "import annotationlib\ndef ann(fmt):\n    if fmt == 1:\n        return {'x': int}\n    raise NotImplementedError\n"
        "print(annotationlib.call_annotate_function(ann, annotationlib.Format.FORWARDREF))\n", {}, ()),
    "3.5c a type alias, FORWARDREF and STRING": (
        "import annotationlib\ntype Alias = int | Later\nF = annotationlib.Format\n"
        "print(annotationlib.call_evaluate_function(Alias.evaluate_value, F.STRING))\n"
        "print(annotationlib.call_evaluate_function(Alias.evaluate_value, F.FORWARDREF).__forward_arg__)\n", {}, ()),
    "3.5d namedtuple fields by keyword, inside a function": (
        "import collections\ndef make():\n    return collections.namedtuple('Pt', field_names='u v')\n"
        "if __name__ == '__main__':\n    print(make()(1, 2))\n", {}, ()),
    # review 2026-11-02 astra-low-06
    "A6-1 two aliases with one name on one line": (
        "import annotationlib\ntype A = int; Old = A; type A = str\nif __name__ == '__main__':\n"
        "    print(annotationlib.call_evaluate_function(Old.evaluate_value, annotationlib.Format.STRING))\n"
        "    print(annotationlib.call_evaluate_function(A.evaluate_value, annotationlib.Format.STRING))\n", {}, ()),
    "A6-2 exec in the caller's context, without PEP 563": (
        "from collections import namedtuple\nns = {}\nexec('def f(x: Missing): pass', ns)\ntry:\n"
        "    ns['f'].__annotations__\n    fields = 'present'\nexcept NameError:\n    fields = 'absent'\n"
        "T = namedtuple('T', fields)\nif __name__ == '__main__':\n    print(T(1))\n", {}, ()),
    "A6-2 exec in the caller's context, with PEP 563": (
        "from __future__ import annotations\nfrom collections import namedtuple\nns = {}\n"
        "exec('def f(x: Missing): pass', ns)\ntry:\n    ns['f'].__annotations__\n    fields = 'present'\n"
        "except NameError:\n    fields = 'absent'\nT = namedtuple('T', fields)\nif __name__ == '__main__':\n    print(T(1))\n", {}, ()),
    "A6-3 eval strips leading spaces": ("value = eval('  1 + 2')\nif __name__ == '__main__':\n    print(value)\n", {}, ()),
    "A6-3 eval of bytes with an encoding declaration": (
        "value = eval(b'# coding: latin-1\\n\"\\xe9\"')\nif __name__ == '__main__':\n    print(value)\n", {}, ()),
    "A6-3 compile of bytes with an encoding declaration": (
        "code = compile(b'# coding: latin-1\\nx = \"\\xe9\"', '<s>', 'exec')\nns = {}\nexec(code, ns)\n"
        "if __name__ == '__main__':\n    print(ns['x'])\n", {}, ()),
    "A6-4 a private attribute with an unbound companion": (
        "import annotationlib\nclass C:\n    __v = int\n    def f(x: C.__v, y: Missing):\n        pass\n"
        "if __name__ == '__main__':\n    ann = annotationlib.get_annotations(C.f, format=annotationlib.Format.FORWARDREF)\n"
        "    print(ann['x'] is int, ann['y'].__forward_arg__)\n", {}, ()),
    # review 2026-11-02 gemini-4-argon-high-05
    "G5 3.1 lazy imports under FORWARDREF": (
        "import annotationlib\nlazy from decimal import Decimal\nlazy from nonexistent_mod import Missing\n"
        "def f(z: Later, x: Decimal, y: list[Decimal]) -> None: ...\ndef g(x: Missing, y: Later) -> None: ...\n"
        "a = annotationlib.get_annotations(f, format=annotationlib.Format.FORWARDREF)\n"
        "print(a['x'].__name__, a['y'])\nb = annotationlib.get_annotations(g, format=annotationlib.Format.FORWARDREF)\n"
        "print(type(b['x']).__name__, b['x'].__forward_arg__)\n", {}, ()),
    "G5 3.2 a bound and a default on one line": (
        "import annotationlib\ntype Alias[T: int = str] = list[T]\nT = Alias.__type_params__[0]\nF = annotationlib.Format\n"
        "print(annotationlib.call_evaluate_function(T.evaluate_bound, F.STRING), "
        "annotationlib.call_evaluate_function(T.evaluate_default, F.STRING))\n", {}, ()),
    "G5 3.3 PEP 563 and PEP 695": (
        "from __future__ import annotations\nimport annotationlib\ntype Alias[T: Bound = Default] = list[T] | Unbound\n"
        "print(annotationlib.call_evaluate_function(Alias.evaluate_value, annotationlib.Format.STRING))\n", {}, ()),
    "G5 3.4 a starred TypeVarTuple default": (
        "import annotationlib\ntype Alias[*Ts = *tuple[int, str]] = tuple[*Ts]\n"
        "print(annotationlib.call_evaluate_function(Alias.__type_params__[0].evaluate_default, annotationlib.Format.STRING))\n", {}, ()),
    "G5 3.5 an IfExp annotation": (
        "import dataclasses\ncond = True\n@dataclasses.dataclass\nclass Box:\n    x: Later if cond else int = 1\n"
        "class Later:\n    pass\nprint(Box(2))\n", {}, ()),
    "G5 3.5 private names bound in a method": (
        "import annotationlib\nclass Outer:\n    def m(self, __p=int):\n        __loc = str\n"
        "        def inner(x: __loc, y: __p, z: Missing): ...\n        return inner\n"
        "print(annotationlib.get_annotations(Outer().m(), format=annotationlib.Format.STRING))\n", {}, ()),
    "G5 3.5 private type parameters": (
        "import annotationlib\nclass Outer:\n    type Alias[__T: int] = list[__T] | Missing\n    class Inner[T: __Secret = int]:\n"
        "        x: T\nF = annotationlib.Format\nprint(annotationlib.call_evaluate_function(Outer.Alias.evaluate_value, F.STRING))\n"
        "print(annotationlib.call_evaluate_function(Outer.Inner.__type_params__[0].evaluate_bound, F.STRING))\n", {}, ()),
    "G5 3.5 global in a class body": (
        "import annotationlib\nG = int\ndef outer():\n    G = str\n    class C:\n        global G\n        x: G\n"
        "        y: Missing\n        def m(self, a: G, b: Missing): ...\n    return C\nC = outer()\nF = annotationlib.Format\n"
        "print(annotationlib.get_annotations(C, format=F.FORWARDREF)['x'], annotationlib.get_annotations(C.m, format=F.FORWARDREF)['a'])\n",
        {}, ()),
    "G5 3.5 a walrus in a lambda in a comprehension": (
        "import annotationlib\ndef outer():\n    fs = [lambda: (w := int) for _ in (1,)]\n    def inner(a: w, b: Missing): ...\n"
        "    return inner\nprint(annotationlib.get_annotations(outer(), format=annotationlib.Format.STRING))\n", {}, ()),
    "G5 3.7 a parenthesised NamedTuple target": (
        "import typing\ndef make():\n    class N(typing.NamedTuple):\n        a: int\n        (b): int = 2\n    return N\n"
        "if __name__ == '__main__':\n    print(make()(1))\n", {}, ()),
    "3.5d exec of a text with closure=": (
        "if __name__ == '__main__':\n    try:\n        exec('x = 1', {}, closure=())\n"
        "    except TypeError as e:\n        print('TypeError', e)\n", {}, ()),
}


def test_the_review_probes_print_what_cpython_prints() -> None:
    for label, (source, files, options) in REVIEW_PROBES.items():
        with tempfile.TemporaryDirectory() as tmp:
            name = files.get("__name__", "prog.py")
            for file, text in files.items():
                if file != "__name__":
                    Path(tmp, file).write_text(text, encoding="utf-8")
            Path(tmp, name).write_text(source, encoding="utf-8")
            env = dict(os.environ, PYTHONHASHSEED="0")
            cpython = subprocess.run([sys.executable, *options, name], cwd=tmp, capture_output=True, text=True, env=env, check=False)
            replay = subprocess.run([sys.executable, str(RUN), *options, name], cwd=tmp, capture_output=True, text=True,
                                    env=env, check=False)
        assert (replay.returncode, replay.stdout) == (cpython.returncode, cpython.stdout), (label, replay.stderr[-300:])


def test_the_entry_scripts_texts_survive_a_closure_lock() -> None:
    """Review 2026-11-01 gemini-4-argon-high-04, 3.3c: with --modules-from and --entry together,
    the entry's own texts are kept, under __main__."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp, "artefact")
        run_module = _load_run()
        run_module.dry_run(out, run_module.phase1_blocked(),
                           ["--modules-from", str(ROOT / "closure.lock.json"), "--entry", str(CASES / "C-8-08_staged_dataclass.py")])
        texts = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["texts"]
    assert any("__main__" in t["by"] for t in texts), "the entry's dataclass texts were dropped"


def test_unsupported_functions_are_refused() -> None:
    """The replay refuses what the closure lock lists as unsupported, as phase 1 does."""
    proc = _replay('''
        import pathlib
        if __name__ == "__main__":
            print(pathlib.Path("/x").as_uri())
    ''')
    assert proc.returncode == 70 and "[P2+] pathlib.Path.as_uri" in proc.stderr, proc.stderr


def test_a_refused_function_is_refused_on_entry() -> None:
    """Review 2026-11-02 astra-low-06, on S-4: gettext.c2py is refused when it is called, before
    its parser could raise a catchable ValueError for malformed input."""
    proc = _replay('''
        import gettext
        if __name__ == "__main__":
            try:
                gettext.c2py("bad_token")
            except ValueError:
                print("caught")
    ''')
    assert proc.returncode == 70 and proc.stdout == "" and "[P2+] gettext" in proc.stderr, (proc.stdout, proc.stderr)


def test_two_annotate_functions_never_share_an_entry_point() -> None:
    """Review 2026-11-02 astra-low-06, A6-1: every compiler-generated annotate or evaluate function
    of the closure and the corpus has its own identity."""
    import json
    keys: list[str] = []
    for path in [*sorted(CASES.glob("*.py")), *sorted((ROOT / "pipeline" / "tests").glob("*.py"))]:
        keys += entries.evaluators_for_source(str(path))[0]
    assert len(keys) == len(set(keys))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "aliases.py")
        path.write_text("type A = int; Old = A; type A = str\n", encoding="utf-8")
        found, declined = entries.evaluators_for_source(str(path))
    assert len(found) == 2 and declined == [], (found, declined)
    del json


def test_artefacts_are_per_script_and_per_optimisation_level() -> None:
    """Review 2026-11-02 gemini-4-argon-high-05, 3.6: two scripts with the same text in two
    directories get their own artefacts, and so does -O."""
    main = "import annotationlib, helper\nprint(annotationlib.get_annotations(helper.f, format=annotationlib.Format.STRING))\n"
    outputs = []
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        for tmp, annotation in ((tmp1, "int"), (tmp2, "bytes")):
            Path(tmp, "main.py").write_text(main, encoding="utf-8")
            Path(tmp, "helper.py").write_text(f"def f(x: {annotation}): pass\n", encoding="utf-8")
            outputs.append(subprocess.run([sys.executable, str(RUN), "main.py"], cwd=tmp, capture_output=True, text=True,
                                          check=False).stdout)
    assert outputs == ["{'x': 'int'}\n", "{'x': 'bytes'}\n"], outputs
    optimised = _replay("import collections, sys\nprint(collections.namedtuple('P', 'a b')(1, 2), sys.flags.optimize)\n", "-O")
    assert (optimised.returncode, optimised.stdout) == (0, "P(a=1, b=2) 1\n"), optimised.stderr


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
        if __name__ == "__main__":     # at runtime: a module body's compile() is staged, like exec
            code = compile("1", "<s>", "eval")
    ''')
    assert proc.returncode == 70 and "E-01: compile at __main__:<module>:3" in proc.stderr, proc.stderr


def test_intrinsics_alone_do_not_cover_dataclasses() -> None:
    proc = subprocess.run([sys.executable, str(RUN), "--mechanism", "intrinsics", "C-8-08_staged_dataclass.py"],
                          cwd=CASES, capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="0"), check=False)
    assert proc.returncode == 70 and "no compiler intrinsic" in proc.stderr, proc.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
