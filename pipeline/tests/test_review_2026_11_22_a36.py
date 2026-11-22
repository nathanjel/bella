"""Review A36 (Codex Astra, low effort) of d558f52..55c6f6d: the argument-count sweep and the fixes of review A35.

37 findings, RL-803 to RL-839, and one more from the reviewer's saved outputs (RL-840); `docs/reviews/review-log.md` has
each with its verdict. As for A35, the programs are the reviewer's own probes (`review_a36/<probe>.txt`, one row a
process): the 141 rows that differed between CPython and the compiled program and agree now. `reduced` has one row a
finding. RL-825, the order of two stores in `a, b = X(), Y()`, was the compiler's and came a step later (case C-3-79;
`reduced/23`, `reentrant/assign` and four rows of `exceptionstate`). What is not here: two rows whose objects are in a
cycle that CPython's collector finalises at exit (`owned/exc`, `owned/tb`: D-04, D-07).

What the rows hold:

* What is let go of when a consumer fails or ends early (`early`, `edges`, `ends`, `failure`, `consumers`, `typeitems`,
  `owned`): unpacking (RL-803, RL-815), `PySequence_Tuple` in one place with its two orders (RL-804; `e.args = iterable`
  leaked, RL-821; a metaclass's `mro()`, RL-822; `__slots__`, RL-823), dict from pairs (RL-817), OrderedDict's pairs
  (RL-818), `reduce` (RL-828), `writelines` (RL-829), `map` (RL-805), `pairwise`, `islice` and `chain` (RL-812, RL-813).
  A prelude catches the error, leaves its handler, lets go in the C's order and sends the error on with `_raise_as_is`:
  the C does that work with the error pending, so a finaliser sees what was handled around the call.
* Loops the item-lifetime sweep did not have (`loops`, `jsonloop`, `compare`): RL-807, RL-816, RL-830, RL-831, RL-835,
  RL-837; and one loop where letting go early was wrong, the names of an abstract class (`abstract`, RL-836).
* `tp_new` is a state of the class with a history (`construct`, `slots`, `machinery`: RL-810, RL-833), and
  `ALLOCATOR_HISTORY` below, 22 rows measured against CPython.
* `dict.update` from a mapping (RL-808), the sequence protocol in `TypeVar`'s substitution and in ast (`protocol`,
  `protocol2`, `concrete`: RL-809, RL-814, RL-820, RL-839), `deque` comparison (RL-838), a Context's mapping (RL-811).
* TextIOWrapper (`iomethods`, `reinit`, `streams`, `holders`): the buffer wherever there is one (RL-806), the encoder before
  the decoder (RL-819), `ok` cleared before `errors` is looked at (RL-824), the cached raw FileIO (RL-832); and the object a
  struct iterator's bytes came from, held until the iterator is done (RL-840).
* Exceptions' fields (`exceptionstate`, `reentrant`): RL-826, RL-827, RL-834.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a36
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent

ROWS: dict[str, tuple[str, ...]] = {
    "abstract": ('iter-error', 'ok', 'sort-error'),
    "compare": ('eq', 'life', 'lt', 'ne'),
    "concrete": ('ast-init-dict', 'ast-reduce-dict', 'ast-replace-dict', 'ast-repr-dict'),
    "construct": ('BufferedRandom', 'BufferedReader', 'BufferedWriter', 'list', 'object', 'TextIOWrapper'),
    "consumers": ('affinity', 'dictpair', 'odpair'),
    "early": ('few', 'few-err', 'many', 'product-err', 'tuple-err'),
    "edges": ('chain', 'hint', 'livekeys', 'mapshort', 'pair', 'params', 'star'),
    "ends": ('map-free', 'map-held', 'slice-one', 'slice-zero'),
    "exceptionstate": ('StopIteration-again', 'SyntaxError-omit', 'SyntaxError-partial', 'AttributeError-omit', 'ImportError-omit',
                       'ModuleNotFoundError-omit', 'NameError-omit'),   # the last four are RL-825's
    "failure": ('reduce', 'writelines'),
    "fields": ('map',),
    "holders": ('struct-it',),
    "iomethods": ('TextIOWrapper-errors', 'TextIOWrapper-invalidbuf', 'TextIOWrapper-invalidnl', 'TextIOWrapper-readable', 'TextIOWrapper-seekable', 'TextIOWrapper-tell', 'TextIOWrapper-writable'),
    "jsonloop": ('list', 'pairs'),
    "loops": ('csv', 'raw-buffer', 'raw-text', 'sigmask', 'sigtimedwait', 'sigwait', 'sigwaitinfo', 'spawn-default', 'spawn-mask', 'write-buffer', 'write-string', 'write-text'),
    "machinery": ('csvr-first', 'csvr-second', 'csvw-first', 'csvw-second', 'os-one', 'os-six', 'os-zero'),
    "owned": ('ctx',),
    "protocol": ('keys', 'od', 'typevar-index'),
    "protocol2": ('raw-closed', 'subst-len'),
    "reduced": ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37'),
    "reentrant": ('stop', 'syntax', 'assign'),
    "reinit": ('Text-badnewline', 'Text-badraw', 'Text-closedraw'),
    "slots": ('list', 'object', 'objectalias', 'random', 'reader', 'text', 'writer'),
    "streams": ('again', 'close', 'detach', 'fail', 'fresh'),
    "typeitems": ('args-fail', 'mro-fail', 'mro-ok', 'slots-fail', 'slots-ok'),
}

# RL-810, RL-833: what CPython's update_one_slot leaves in tp_new, as a program can tell
ALLOCATOR_HISTORY = r'''
import csv
import io


def show(label: str, make: object) -> None:
    try:
        print(label, make())  # type: ignore[operator]
    except Exception as e:
        print(label, type(e).__name__)


class C:
    pass


C.__new__ = staticmethod(lambda cls: object.__new__(cls))  # type: ignore[method-assign, assignment]
del C.__new__
show("assigned and deleted, __init__ with an argument:", lambda: object.__init__(C(), 1))
show("its call with an argument:", lambda: type(C(1)).__name__)
show("object.__new__ with an argument:", lambda: type(object.__new__(C, 1)).__name__)


class D:
    pass


D.__new__ = object.__new__  # type: ignore[method-assign, assignment]
show("object's own stored:", lambda: object.__init__(D(), 1))
show("its call with an argument:", lambda: type(D(1)).__name__)


class Base:
    pass


class Sub(Base):
    pass


Base.__new__ = staticmethod(lambda cls, *a: object.__new__(cls))  # type: ignore[method-assign, assignment]
del Base.__new__
show("a base's assigned and deleted, the subclass:", lambda: object.__init__(Sub(), 1))


class Later(Base):
    pass


show("a class made after it:", lambda: object.__init__(Later(), 1))


class Own(Base):
    def __new__(cls) -> "Own":
        return object.__new__(cls)


class Under(Own):
    pass


Base.__new__ = staticmethod(lambda cls, *a: 7)  # type: ignore[method-assign, assignment]
show("a subclass with its own is not reached:", lambda: type(Under()).__name__)
show("one without is:", lambda: Sub())


class M:
    def __new__(cls) -> int:  # type: ignore[misc]
        return 17


Reader = type(csv.reader([]))
Writer = type(csv.writer(io.StringIO()))
for label, bases in (("reader first", (Reader, M)), ("mixin first", (M, Reader)), ("writer first", (Writer, M)), ("reader alone", (Reader,))):
    K = type("K", bases, {})
    show(label + ":", lambda: K())
    show(label + ", object.__new__:", lambda: type(object.__new__(K)).__name__)


class Plain:
    pass


show("a plain class, an argument:", lambda: type(Plain(1)).__name__)
show("a plain class, __init__ with an argument:", lambda: object.__init__(Plain(), 1))


class WithInit:
    def __init__(self, *a: object) -> None:
        pass


show("with __init__:", lambda: type(WithInit(1)).__name__)
WithInit.__new__ = staticmethod(lambda cls, *a: object.__new__(cls))  # type: ignore[method-assign, assignment]
del WithInit.__new__
show("with __init__, assigned and deleted:", lambda: type(WithInit(1)).__name__)
print("end")
'''


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a36" / f"{probe}.txt", ROWS[probe])


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_the_allocator_slot_has_a_history() -> None:
    same(ALLOCATOR_HISTORY)


if __name__ == "__main__":
    test_the_allocator_slot_has_a_history()
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
