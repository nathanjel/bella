"""Review F48 (Claude workflows, 2026-11-26) of Questions 33 to 48 and of the code of 2026-11-24 and 25.

144 subjects, RL-958 to RL-1101; `docs/reviews/review-log.md` has each with its verdict. The fixed ones are held here, each
the reviewer's sweep of the defect's class (`review_f48/<probe>/*.txt`, read as modules beside `prog.py`; `rows.txt` has one
argument list a line), one row a process, compared on standard output, standard error and the exit status:

* A module name that is not a str does not end the program: 22 entry points of the import system, each handed nine kinds of
  name (`entrynames`: RL-1033). The rows in `STOPS` stop by name, where a compiled program has no source or frozen code to
  run; what `FrozenImporter.exec_module` does for a module that is not frozen is registered (D-34).
* What a handler given to `os.register_at_fork` reaches is finalised at the exit, and the three lists of handlers are let go
  of in CPython's order (`atfork`: RL-1070; logging, threading and random register theirs when imported, so a filter, a
  handler or a formatter of the program's own kept the main module's globals from being finalised, a file left open with
  them).
* A class with a long chain of bases is made in time in proportion to it (`basechain`: RL-1039; a chain of 300, a ladder of
  40 diamonds, 60 class statements, and what `__base__` is with slots and built-in bases).
* What only a built-in module's state holds of the program's is finalised at the exit (`modulestate`: RL-987, the class of
  RL-1070): a subclass of `_csv.Dialect` kept by `csv.register_dialect`, a str subclass's object kept by struct's cache,
  and what the program or a late finaliser stored in sys, which CPython lets go of when it clears sys's dict last.
* A view wherever bytes-like data is taken (`views`, 564 rows, and `viewsmore`, 48: the q40 reviewer's sweeps, RL-992):
  `int()` and `float()` of a view, a bytearray compared with one, and `os.setxattr` agree now; what is not written yet
  stops by name (codecs outside phase 1, six functions of binascii, a view written into), and a buffered writer's raw
  write() waits for Question 40 (RL-991).
* The fourteen names of the lock machinery, every way a program reaches one (`locknames`, the c07 reviewer's 467 rows, whose
  289 stops are its own `stops.txt`; RL-1065 to RL-1068): a read, a delete and a store stop with D-33's words; the import
  system's functions are the importlib module's attributes at each call (`importcalls`, 8 rows: a replaced `_find_and_load`,
  `_handle_fromlist`, `_lock_unlock_module` or `_module_repr` is called, a deleted one is an AttributeError), and a name the
  module had and the program deleted is absent as in CPython.
* A class over a base still making its MRO (`incomplete`, 56 rows, and `mrohooks`, 16, the c02 reviewer's; RL-1043): type.mro()
  refuses the base, and a class an explicit mro() made over one cannot make instances; a module type's subclass adds no
  `__dict__` (`moduletype`, RL-1094), and `_io._IOBase.__subclasses__()` stops (RL-1025).
* A failed import's kept traceback entry lets its module's namespace go with the entry's frame (`tbhold`, 10 rows of the q44
  reviewer's, with a package; RL-1012).
* The import system's frames have CPython's lines where the closed world rewrote its text (`importlines`, 5 rows: the exit's
  import and `_find_spec`'s raise, `ModuleSpec.cached`'s getter, `PathFinder.discover` suspended, a frozen module's body as
  a hook sees its stack; RL-1058, RL-1063).
* An argument by name and position, a second built-in module, a key in a built-in type's dict, a module's class, and
  `dir()`'s sort (`lookups`, 8 rows: RL-965, RL-1013, RL-1048, RL-1050, RL-1052).
* Five defects of a class's shape and a call's message (`shapes`, 5 rows, each with the neighbours of the reviewer's
  example): `fromhex` on a subclass of bytes or bytearray calls the subclass with the result (RL-1037); assigning a class's
  `__module__` drops its `__firstlineno__` (RL-1044); `repr()` of a class, and the default `repr()` of its instance, say the
  type's `__name__` where its module is not a str or is builtins (RL-1054); an argument error names the function by its own
  `__qualname__`, which `functools.wraps` and an assignment change (RL-1060); and `split` and `rsplit` of bytes and
  bytearray refuse an unknown keyword before they convert `maxsplit` (RL-1075).
* The tests that did not hold what they say (RL-1010, RL-1018, RL-1055), with the reviewers' probes: the keeping half of
  the import system's trimming rule (`trimrules`, 12 rows of the q43 reviewer's: a module's `__getattr__` raising under a
  from-import, a from-list or `__all__` item that is no str; `getframe` stops, E-02); what a read sees of a class's dict
  handed out (`classdict`, 18 rows, and `classstate`, 2, of the q45 reviewer's: one object by each way, following the class,
  `object.__getstate__` of a class; the writes are E-05's); and the A45 fixes' two halves (`a45text` 12 rows, `a45suggest`
  10, `a45more` 11, `a45dir` 18, of the c04 reviewer's: a text's locals through a frame object, the suggestions read from
  them, `dir()` of a module). `a45dir`'s `descriptor` row found two messages: `object.__getattribute__` of a module words
  its AttributeError as `PyObject_GenericGetAttr` does, and five native methods check their arguments as their calling
  convention does (`nativeargs`: a slot wrapper's `__repr__` of a module, a lazy import and a capsule, METH_NOARGS
  `module.__dir__`, `dir`'s PyArg_UnpackTuple). A C method bound to a module keeps its type's name in the message where
  CPython's has its own name alone (D-08's wording: `nativeargs`'s `bound`, `a45dir`'s `descriptor`).

* What is made inside a generator expression is named `<genexpr>.<lambda>` and `<genexpr>.<genexpr>`, with no `.<locals>`
  (`qualnames`: RL-1053; at module level, in a function, in a class body and a method).
* Each write and name E-04 lists, under CPython and compiled (`e04writes`, 16 rows; RL-1102): `sys.path_hooks`,
  `sys.set_lazy_imports` and `sys.set_lazy_imports_filter` stop with E-04's words, as `importlib.reload` does; writes to
  `sys.modules` (a module put in, one replaced, one deleted and imported again, `None`) and `__import__` replaced through
  `setattr` do what CPython does; a write to `sys.meta_path` or `sys.path` is neither refused nor stopped, and the import
  after it finds the module where CPython asks the program's finder or finds nothing (`OPEN`, the author's).

And one registered difference is held as D-17 words it (the author's decision of 2026-11-26, Question 49: A; RL-980):

* The frames CPython enters without checking the recursion limit (`unchecked`): 1,200 generators chained by `yield from` or
  by `for`, and a recursion 1,200 deep through `*args`, `**kwargs` or a bound method object called with a keyword, end
  under CPython and raise RecursionError compiled (`REGISTERED`); at 900 both end, and a recursive generator, the lazy
  sieve and a decorated recursion raise on both sides at 1,200.

And one decision's step (the author's, 2026-11-26, Question 50: B; RL-983):

* `decimal` and `datetime` are CPython's Python versions here, and the frames of their functions are none a program sees, as
  CPython's C modules have none (`cmodules`, 60 rows): 33 operations that raise, each with the entries of its traceback; an
  uncaught one; 13 ways the two modules call the program back (a tzinfo's methods, a Rational's numerator), with the stack
  there and a warning charged two levels up; a recursion that ends in an operation, counted; the two deprecation warnings
  of `datetime`, charged to the caller's line. What stays the Python version's is registered (D-20): what a signal of
  `decimal` carries, and a rounding mode's name that is not checked.

And a registered difference that came back (the author's decision of 2026-11-26, Question 51: A; RL-1011):

* The runtime's own modules live to the end of the process (D-19), where CPython frees the modules it writes in C at the
  exit (`ownmodules`, 132 rows, a module each): the callback of a weak reference that sys holds is called at the exit for
  42 of them under CPython and never compiled (`OWN_MODULES`); for 89 (the modules compiled from Python, which die on both
  sides, and the ones CPython does not free either) the two agree; `marshal` is not ported yet and stops by name.

And an exclusion (the author's decision of 2026-11-27, Question 52: A; RL-954, RL-955, RL-1099):

* An import by a name whose class overrides a method of str stops by name (E-04), where CPython's import system calls the
  name's methods (`importnames`, 117 rows: `__import__`, `importlib.__import__` and `importlib.import_module`, each handed
  thirteen kinds of name for a module to be found, one already imported and a missing one). The 42 rows of the first two
  entries with a name that overrides `__hash__`, `__eq__`, `__add__`, `rpartition`, `upper` or `startswith`, or a StrEnum
  member that does, stop; an exact str, a subclass that overrides nothing, only `__new__` or only `__repr__` (as every
  StrEnum member's class does), and every name through `import_module` (which makes an exact str of it first) agree.

And the import system's text (RL-955, RL-1057, RL-1059; the step before Question 48's words):

* 22 functions of the import system are CPython's text again, and do what CPython's do on what a program can hand them
  (`importtext`, 11 rows: the path helpers and `_write_atomic` on real paths; `spec_from_file_location`; the Windows
  registry finder, a NameError on posix and its DeprecationWarning; `_bless_my_loader` over eight namespaces;
  `_fix_up_module`, which sets no `__cached__`; `_classify_pyc`; `_verbose_message`; the built-in importer's methods; and
  the two warnings of a relative import whose package cannot be told, charged to the caller's line as CPython's stack
  level has it). `cache_from_source` and `source_from_cache` raise as D-16 says.

A row of `STOPS` must stop with its words, a row of `OPEN` must differ, and a row of `REGISTERED` must give what its entry
says: one that comes to agree with CPython is to leave its table.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_26_f48
"""
from __future__ import annotations

import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run, silent

HERE = Path(__file__).resolve().parent / "review_f48"

NOT_COMPILED = "bella: not implemented: executing a module the program does not have compiled"
KINDS = ("int", "none", "bytes", "float", "list", "tuple", "strsub", "strsub2", "str")
HOOKED_NAME = "bella: not implemented: an import by a name whose class overrides str's "

_CODEC = " (not a phase-1 codec: specification section 7)"
_WRITTEN_INTO = "a memoryview as a writable buffer ("
VIEW_STOPS: dict[str, str] = {
    **{"codecs." + name: "_codecs." + name + _CODEC for name in ("escape_decode", "unicode_escape_decode", "raw_unicode_escape_decode", "charmap_decode")},
    **{"binascii." + name: "binascii." + name for name in ("crc_hqx", "b2a_qp", "a2b_qp", "b2a_uu", "b2a_base85", "b2a_ascii85")},
    **{"binascii." + name: "binascii." + made for name, made in (("a2b_uu", "b2a_uu"), ("a2b_base85", "b2a_base85"), ("a2b_ascii85", "b2a_ascii85"))},
    **{"base64." + name: "binascii." + made for name, made in (("b85encode", "b2a_base85"), ("b85decode", "b2a_base85"), ("a85encode", "b2a_ascii85"),
                                                               ("a85decode", "b2a_ascii85"), ("z85encode", "b2a_base85"))},
    **{row: _WRITTEN_INTO + said + ")" for row, said in (
        ("BytesIO.readinto", "readinto() argument"), ("BufferedIOBase.readinto default", "readinto() argument"),
        ("BufferedIOBase.readinto1 default", "readinto1() argument"), ("BufferedRandom.readinto", "readinto() argument"),
        ("BufferedRWPair.readinto", "readinto() argument"), ("FileIO.readinto", "readinto() argument 1"),
        ("os.readinto", "readinto() argument 2"), ("struct.pack_into", "pack_into() argument 2"), ("Struct.pack_into", "pack_into() argument 1"))},
    **{row: "os: a memoryview as a buffer to read into" for row in ("os.readv", "os.preadv")},
}
# rows where the compiled program stops by name, CPython doing what a compiled program cannot
STOPS: dict[tuple[str, tuple[str, ...]], str] = {
    **{("entrynames", ("source.exec_module", kind)): NOT_COMPILED for kind in KINDS},
    **{("entrynames", ("frozen.exec_module", kind)): NOT_COMPILED for kind in KINDS if kind != "strsub2"},
    ("ownmodules", ("marshal",)): "bella: not implemented: importing 'marshal' (the standard library: step 3b)",
    ("lookups", ("module class other",)): "bella: not implemented: [P2+] __class__ assignment (spec section 3)",
    # the subclasses of a type of CPython's a prelude presents name CPython's own classes (RL-1025)
    ("a45dir", ("lazy",)): "bella: not implemented: importing 'colorsys' (the standard library: step 3b)",
    ("a45dir", ("subclass",)): "bella: not implemented: a subclass of the module type (step 3b)",
    ("a45dir", ("subclass_plain",)): "bella: not implemented: a subclass of the module type (step 3b)",
    ("moduletype", ("iobase subclasses",)): "bella: not implemented: the subclasses of the built-in type '_io._IOBase': CPython's list names its own classes",
    ("moduletype", ("ref subclasses",)): "bella: not implemented: the subclasses of the built-in type 'weakref.ReferenceType': CPython's list names its own classes",
    # the view sweep (RL-992): what stops by name there is what is not written yet, whatever the buffer, and a view where a
    # buffer is written into (Question 40's queue)
    **{("views", (row, kind)): "bella: not implemented: " + words for row, words in VIEW_STOPS.items() for kind in "cws"},
    **{("viewsmore", ("os.readinto", kind)): "bella: not implemented: a memoryview as a writable buffer (readinto() argument 2)" for kind in "cw"},
    **{("importnames", (entry, kind, target)): HOOKED_NAME for entry in ("__import__", "importlib.__import__")
       for kind in ("hashed", "equal", "added", "parted", "upper", "starts", "hooked") for target in ("found", "loaded", "missing")},
    # the names of sys that E-04 names stop with its words (RL-1102), as importlib.reload does
    **{("e04writes", (row,)): f"bella: not implemented: sys.{name} (import-system customisation: the closed world is resolved at "
       "build time, E-04)" for row, name in (("path_hooks", "path_hooks"), ("lazy_mode", "set_lazy_imports"),
                                             ("lazy_filter", "set_lazy_imports_filter"))},
    ("e04writes", ("reload",)): "bella: not implemented: importlib.reload (running a module's body again is import-system customisation, E-04)",
}
# the modules CPython writes in C and frees at the exit, which here live to the end of the process (D-19)
OWN_MODULES = ("atexit", "binascii", "cmath", "gc", "grp", "pwd", "time", "unicodedata", "zlib", "_bisect", "_blake2",
               "_collections", "_contextvars", "_csv", "_functools", "_heapq", "_json", "_locale", "_md5", "_opcode",
               "_operator", "_random", "_sha1", "_sha2", "_sha3", "_sre", "_stat", "_statistics", "_string", "_struct",
               "_typing", "math", "_hmac", "_frozen_importlib_external", "_imp", "_signal", "_warnings", "_weakref",
               "_tokenize", "_suggestions", "_ast", "_types")
# rows that differ as a registered deviation says: what the compiled program prints there
REGISTERED: dict[tuple[str, tuple[str, ...]], tuple[str, str]] = {
    **{("unchecked", (shape, "1200")): ("D-17", "RecursionError\n") for shape in ("yield from", "for", "*args", "**kwargs", "bound method")},
    **{("ownmodules", (name,)): ("D-19", "the end\n") for name in OWN_MODULES},
    # FrozenImporter.exec_module runs the compiled body of any module the program has, where CPython's raises ImportError
    # for one that is not frozen (Question 48: A)
    ("entrynames", ("frozen.exec_module", "strsub2")): ("D-34", "helper body runs\nfrozen.exec_module strsub2\nhelper body runs\nreturns None\n"),
    # a compiled program has no bytecode cache: sys.implementation.cache_tag is None, and CPython's text raises for it
    ("importtext", ("cache",)): ("D-16", "NotImplementedError NotImplementedError TypeError\n"),
    # a C method bound to a module is named by its own name alone in its argument error (meth_get__qualname__), and the
    # runtime's names it as its type's: the wording of a built-in message (RL-1055)
    ("nativeargs", ("bound",)): ("D-08", "__dir__, one TypeError module.__dir__() takes no arguments (1 given)\n"
                                         "__dir__, keyword TypeError module.__dir__() takes no keyword arguments\n"
                                         "__format__, two TypeError object.__format__() takes exactly one argument (2 given)\n"
                                         "__reduce_ex__, two TypeError object.__reduce_ex__() takes exactly one argument (2 given)\n"),
    ("a45dir", ("descriptor",)): ("D-08", "method_descriptor __dir__ module.__dir__\nunbound True\nwrong raised TypeError descriptor "
                                          "'__dir__' for 'module' objects doesn't apply to a 'int' object\nargs raised TypeError "
                                          "module.__dir__() takes no arguments (1 given)\nkw raised TypeError module.__dir__() takes no "
                                          "keyword arguments\nobject True\ngetattribute raised AttributeError 'module' object has no "
                                          "attribute 'nope'\nplain raised AttributeError module 'sample' has no attribute 'nope'\nis True\n"),
    # decimal is CPython's _pydecimal: its signals carry a text where the C module's carry the conditions, and it takes a
    # rounding mode's name unchecked
    ("cmodules", ("frames", "16")): ("D-20", "Decimal(1).to_integral_value(rounding='up') -> no error: Decimal\n"),
    ("cmodules", ("args", "0")): ("D-20", "Decimal('x') -> InvalidOperation (\"Invalid literal for Decimal: 'x'\",)\n"),
    ("cmodules", ("args", "1")): ("D-20", "Decimal(1) / Decimal(0) -> DivisionByZero ('x / 0',)\n"),
    ("cmodules", ("args", "2")): ("D-20", "Decimal(0) / Decimal(0) -> InvalidOperation ('0 / 0',)\n"),
    ("cmodules", ("args", "3")): ("D-20", "Decimal(-1).sqrt() -> InvalidOperation ('sqrt(-x), x > 0',)\n"),
    ("cmodules", ("args", "6")): ("D-20", "Decimal('1e999999999') * 10 -> Overflow ('above Emax',)\n"),
    ("cmodules", ("args", "7")): ("D-20", "Decimal('NaN') < 1 -> InvalidOperation ('comparison involving NaN',)\n"),
    ("cmodules", ("args", "12")): ("D-20", "Decimal(1).quantize(Decimal('1e-400'), context) -> InvalidOperation "
                                           "('quantize result has too many digits for current context',)\n"),
}
# rows that differ until the author has decided: a buffered writer hands a program's raw write() a bytes where CPython hands
# a read-only memoryview (RL-991, with Question 40); a second module object of a built-in module, which CPython makes at each
# _imp.create_builtin and the runtime does not (RL-1013); a write to sys.meta_path or sys.path, which E-04 excludes and
# nothing refuses or stops, and which an import after it does not see (RL-1102)
OPEN: frozenset[tuple[str, tuple[str, ...]]] = frozenset({("viewsmore", ("BufferedRandom.write", kind)) for kind in "bacw"} |
                                                          {("lookups", (row,)) for row in ("builtin second", "builtin again")} |
                                                          {("a45more", ("native_direct",))} |   # sys's and builtins' order: RL-1061
                                                          {("e04writes", (row,)) for row in ("meta_insert", "meta_clear", "meta_assign",
                                                                                             "path_clear", "path_assign")})


def rows_of(probe: str) -> list[tuple[str, ...]]:
    return [tuple(shlex.split(line)) for line in (HERE / probe / "rows.txt").read_text(encoding="utf-8").splitlines()]


def stops_of(probe: str) -> dict[tuple[str, ...], str]:
    """A probe's own table of the rows that stop by name (`row => words`, a line each), for a probe with too many to list here."""
    path = HERE / probe / "stops.txt"
    if not path.exists():
        return {}
    out: dict[tuple[str, ...], str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row, words = line.split(" => ", 1)
            out[tuple(shlex.split(row))] = words
    return out


def rows_agree(probe: str) -> None:
    """A probe's files copied as modules beside its prog.py (a folder of them as a package), built once; each row under
    CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-f48-"))
    try:
        for source in sorted((HERE / probe).rglob("*.txt")):   # a folder in the probe is a package of the program's
            if source not in (HERE / probe / "rows.txt", HERE / probe / "stops.txt"):
                target = folder / source.relative_to(HERE / probe).with_suffix(".py")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        rows = rows_of(probe)
        assert rows, f"{probe}: no rows"
        own_stops = stops_of(probe)
        wrong: list[str] = [f"{probe}/{row}: in stops.txt and no row" for row in sorted(set(own_stops) - set(rows))]
        for row in rows:
            want = _run([sys.executable, "prog.py", *row], folder)
            got = _run([binary, *row], folder)
            stop = STOPS.get((probe, row), own_stops.get(row))
            if silent(want):
                wrong.append(f"{probe}/{row}: prints nothing under CPython (RL-1077)")
            elif stop is not None:
                if got[2] != 70 or stop not in "\n".join(got[1]):
                    wrong.append(f"{probe}/{row}: compiled {got!r}, where it is to stop with {stop!r}")
            elif (probe, row) in REGISTERED:
                entry, printed = REGISTERED[(probe, row)]
                if got == want:
                    wrong.append(f"{probe}/{row} agrees now: take it out of REGISTERED and narrow {entry}")
                elif got != (printed, [], 0) or want[1:] != ([], 0):
                    wrong.append(f"{probe}/{row}: compiled {got!r}, CPython {want!r}, where {entry} says {printed!r} against a run that ends")
            elif (probe, row) in OPEN:
                if got == want:
                    wrong.append(f"{probe}/{row} agrees now: take it out of OPEN")
            elif got != want:
                wrong.append(f"{probe}/{row}: compiled {got!r}, CPython {want!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(p.name for p in HERE.iterdir() if p.is_dir()))


def test_rows(probe: str) -> None:
    rows_agree(probe)


if __name__ == "__main__":
    for folder in sorted(p for p in HERE.iterdir() if p.is_dir()):
        rows_agree(folder.name)
    print("ok")
