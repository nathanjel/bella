"""Review A37 (Codex Astra, low effort) of 55c6f6d..b414387: the tee data link, the fixes of review A36, the order of stores.

18 findings, RL-841 to RL-858; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a37/<probe>.txt`, one row a process): the 154 rows that differed between CPython and the compiled program
and agree now. What is not here: the four rows on the lifetime of a call's arguments (`params`: RL-695, the author's), the
rows whose report text differs (`live`: D-28), a difference at exit (`reentry/pair-bad`: D-07), and the two rows of RL-852
that stop by name now (a `__hash__` written in Python called by CPython with an exception set).

What the rows hold:

* The allocator and the initialiser slots (`alloc`, `special`, `history`, `clinic`, `streams`, `verify`): a built-in's
  `__new__` of another type stored in a class is not what the class's `tp_new` is (RL-841, `stored_new_wrapper`); a
  built-in that is no `__new__` is a callable like any other (RL-848); and the rules the clinic generates ask the slots:
  `tuple`, `float`, `reversed`, `filter` and the itertools types by `tp_init` (RL-842, RL-845, RL-849), `BufferedRWPair`
  by `tp_new` (RL-846).
* Clean-up with the error pending, not handled (`pending`, `handlers`, `morepending`, `cleanup`): `reversed`, `islice`,
  `_IOBase.close`, the lru cache, `BufferedRWPair.__init__`, `FileIO.close` (RL-844, RL-847, RL-850, RL-851, RL-853,
  RL-854); `batched` the same way, which the reviewer named without a row.
* The sequence protocol (`protocol`, `capi`): a class of the program's over dict has `sq_length` (RL-843), frozendict is no
  sequence for `bisect` (RL-855), `PySequence_Repeat` (RL-856); and what `items()` returned is let go of once its iterator
  is had (`methodlist`, RL-857).
* `FileIO.__init__` again adds to the access flags and never clears them (`invalidio`, `rawmode`: RL-858).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a37
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent
PRELUDE = HERE.parent.parent / "runtime" / "prelude"

ROWS: dict[str, tuple[str, ...]] = {
    "alloc": (
        'BufferedIOBase-builtin-empty', 'BufferedIOBase-builtin-obj', 'BufferedIOBase-builtin-reduce',
        'BufferedRandom-builtin-arg', 'BufferedRandom-builtin-obj', 'BufferedRandom-builtin-objarg',
        'BufferedReader-builtin-arg', 'BufferedReader-builtin-obj', 'BufferedReader-builtin-objarg',
        'BufferedRWPair-builtin-obj', 'BufferedRWPair-builtin-objarg', 'BufferedWriter-builtin-arg',
        'BufferedWriter-builtin-obj', 'BufferedWriter-builtin-objarg', 'bytes-builtin-arg', 'bytes-builtin-empty',
        'bytes-builtin-init', 'bytes-builtin-reduce', 'BytesIO-builtin-empty', 'BytesIO-builtin-reduce',
        'defaultdict-builtin-copy', 'defaultdict-builtin-empty', 'defaultdict-builtin-kw', 'defaultdict-builtin-reduce',
        'deque-builtin-copy', 'deque-builtin-empty', 'deque-builtin-reduce', 'dict-builtin-empty', 'dict-builtin-kw',
        'dict-builtin-reduce', 'Exception-builtin-arg', 'Exception-builtin-copy', 'Exception-builtin-empty',
        'Exception-builtin-reduce', 'FileIO-builtin-arg', 'frozenset-builtin-copy', 'frozenset-builtin-empty',
        'frozenset-builtin-init', 'frozenset-builtin-reduce', 'int-builtin-arg', 'int-builtin-empty', 'int-builtin-init',
        'int-builtin-reduce', 'IOBase-builtin-empty', 'IOBase-builtin-obj', 'IOBase-builtin-reduce', 'object-builtin-empty',
        'object-builtin-obj', 'object-builtin-reduce', 'OrderedDict-builtin-copy', 'OrderedDict-builtin-empty',
        'OrderedDict-builtin-kw', 'OrderedDict-builtin-reduce', 'OSError-builtin-arg', 'OSError-builtin-copy',
        'OSError-builtin-empty', 'OSError-builtin-reduce', 'RawIOBase-builtin-empty', 'RawIOBase-builtin-obj',
        'RawIOBase-builtin-reduce', 'set-builtin-copy', 'set-builtin-empty', 'set-builtin-reduce', 'str-builtin-arg',
        'str-builtin-empty', 'str-builtin-init', 'str-builtin-reduce', 'StringIO-builtin-empty', 'StringIO-builtin-reduce',
        'TextIOBase-builtin-empty', 'TextIOBase-builtin-obj', 'TextIOBase-builtin-reduce', 'TextIOWrapper-builtin-arg',
        'TextIOWrapper-builtin-obj', 'TextIOWrapper-builtin-objarg', 'tuple-builtin-empty', 'tuple-builtin-init',
        'tuple-builtin-reduce', 'tuple-init-kw'
    ),
    "capi": ('frozen', 'indentmul', 'items'),
    "cleanup": ('slice-again',),
    "clinic": (
        'chain-meta', 'cycle-meta', 'dropwhile-meta', 'filterfalse-meta', 'filter-meta', 'filter-same', 'float-own',
        'islice-meta', 'pairwise-meta', 'reversed-meta', 'reversed-same', 'starmap-meta', 'takewhile-meta', 'tuple-own'
    ),
    "handlers": ('flush', 'lru', 'setter'),
    "history": ('float', 'meta', 'reverse', 'tuple'),
    "invalidio": ('FileIO-prior-props',),
    "methodlist": ('items-err', 'items-ok', 'keys-err', 'keys-ok', 'values-err', 'values-ok'),
    "morepending": ('file', 'pair'),
    "pending": ('index', 'type'),
    "protocol": ('ast-dictsub',),
    "rawmode": ('a-q', 'a-r', 'a-rx', 'a-w', 'r+-a', 'r-a', 'r+-q', 'r-q', 'r+-r', 'r+-rx', 'r+-w', 'r-w', 'w-r', 'w-rx'),
    "reduced": ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '13', '14'),
    "special": ('bound-deleted', 'bound-init', 'len-deleted', 'len-init', 'other-construct'),
    "streams": ('BufferedRWPair-clinic-release',),
    "verify": ('15', '16', '17', '18', 'meta'),
}


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a37" / f"{probe}.txt", ROWS[probe])


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_no_handler_cleans_up_before_it_raises_again() -> None:
    """The rule in the source (the class of RL-812, RL-847, RL-851): what the C does with an error pending, a prelude does
    after its handler has ended, since a finaliser or a method of the program's that runs inside `except` sees that error
    as the handled one. So an unnamed `except BaseException:` that does anything before its bare `raise` is the pattern
    to look at. Three are left, and none of them lets go of an object or calls the program: a link put back in the lru
    cache's ring, a descriptor closed by the system, a counter set to nought."""
    allowed = {"_functools.py": 1, "_io.py": 1, "itertools.py": 1}
    found: dict[str, int] = {}
    for path in sorted(PRELUDE.glob("*.py")):
        if path.name == "bootstrap_external.py":
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        for at, line in enumerate(lines):
            start = re.match(r"( *)except BaseException:", line)
            if not start:
                continue
            indent = len(start.group(1))
            body: list[str] = []
            for later in lines[at + 1:]:
                if later.strip() and len(later) - len(later.lstrip()) <= indent:
                    break
                code = later.split("#")[0].strip()
                if code:
                    body.append(code)
            if len(body) > 1 and body[-1] == "raise":
                found[path.name] = found.get(path.name, 0) + 1
    assert found == allowed, found


if __name__ == "__main__":
    test_no_handler_cleans_up_before_it_raises_again()
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
