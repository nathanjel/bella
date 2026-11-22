"""Review A38 (Codex Astra, low effort) of b414387..7f7c267: the frontend's name counter per unit, the fixes of review A37.

16 findings, RL-859 to RL-874; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a38/<probe>.txt`, one row a process): the 490 rows that differed between CPython and the compiled program
and agree now. Its 125 other rows stop by name (112 at a subclass of `super`) and are not here.

What the rows hold:

* What a class stores as `__init__` (`slots`, `reduced`): a function or a method of a built-in type is called with the
  object first, and the object must be of that type (`C.__init__ = list.__init__` is a TypeError, where it ran on a C and
  once ended in a segmentation fault: RL-860); anything else is bound by its own `__get__`, if it has one (a bound
  built-in has none and is called with the arguments alone: RL-859). `init_kinds` is this session's sweep of the kinds
  the reviewer did not run: 23 kinds of thing stored, over 14 base types, called three ways.
* The allocator slot, read where the name was (`history`, `state`, `clinic`, `valid`): `list.__init__`, OSError's choice of
  initialiser and `_random.Random.__init__` (RL-861, RL-863).
* FileIO (`file`, `fileargs`, `opener`): an opener is given `O_CLOEXEC` and what it returns is made non-inheritable (RL-862);
  the path's bytes and the mode's characters are read, not asked of a subclass (RL-868); what the opener returned is let go
  of once its number is read (RL-869).
* Done after the handler, not in it (`eintr`, `handlers`, `reenter`, `closevalue`, `state`): the EINTR test's conversion of an
  errno (RL-871), a warning's second search for its source file and that file's close (RL-866), the release of what a
  buffered stream's raw close returned (RL-873), the pieces of a failed `re.sub` before the subject's buffer (RL-870).
* A store and what it lets go of (`reinit`, `copyattr`, `newline`): `staticmethod` and `classmethod` copy the names of what
  the field holds after the store (RL-865), each name's value is let go of before the next is asked for (RL-872), and a
  newline decoder initialised again is never seen uninitialised (RL-874).
* A class over frozendict is a sequence to `PySequence_Concat` and `PySequence_Repeat` (`sequence`, `substitution`: RL-864);
  `UnicodeDecodeError.__init__` converts its indices before it asks the object for its bytes (`exceptions`: RL-867).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a38
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent
PRELUDE = HERE.parent.parent / "runtime" / "prelude"

ROWS: dict[str, tuple[str, ...]] = {
    "clinic": ('random-del', 'random-new'),
    "closevalue": ('random', 'reader', 'writer'),
    "copyattr": ('class-again', 'class-fail', 'class-new', 'static-again', 'static-fail', 'static-new'),
    "eintr": (
        'all-bad', 'all-ok', 'bread-bad', 'bread-ok', 'bwrite-bad', 'bwrite-ok', 'line-bad', 'line-ok', 'lines-bad',
        'lines-ok', 'peek-bad', 'peek-ok', 'tline-bad', 'tline-ok', 'tread-bad', 'tread-ok', 'twrite-bad', 'twrite-ok'
    ),
    "exceptions": ('decode-both',),
    "file": (
        'a+-', 'a+-+', 'a+-++', 'a+-☀', 'a-', 'a-+', 'a-++', 'a-☀', 'a+-a', 'a-a', 'a+-aa', 'a-aa', 'a+-+ab', 'a-+ab',
        'a+-bb', 'a-bb', 'a+-br', 'a-br', 'a+-bw+', 'a-bw+', 'a+-r', 'a-r', 'a+-R', 'a-R', 'a+-rb', 'a-rb', 'a+-rbbr',
        'a-rbbr', 'a+-rr', 'a-rr', 'a+-rt', 'a-rt', 'a+-rw', 'a-rw', 'a+-rx', 'a-rx', 'a+-u', 'a-u', 'a+-w', 'a-w', 'a+-wb+',
        'a-wb+', 'a+-ww', 'a-ww', 'a+-x', 'a-x', 'a+-+xb', 'a-+xb', 'a+-xx', 'a-xx', 'bb-+r', 'fd-a', 'fd-+ab', 'fd-br',
        'fd-bw+', 'fd-r', 'fd-rb', 'fd-w', 'fd-wb+', 'fd-x', 'fd-+xb', 'path-a', 'path-+ab', 'path-br', 'path-bw+', 'path-r',
        'path-rb', 'path-w', 'path-wb+', 'path-x', 'path-+xb', 'q-a', 'r+-', 'r+-+', 'r+-++', 'r+-☀', 'r-', 'r-+', 'r-++',
        'r-☀', 'r+-a', 'r-a', 'r+-aa', 'r-aa', 'r+-+ab', 'r-+ab', 'r+-bb', 'r-bb', 'r+-br', 'r-br', 'r+-bw+', 'r-bw+',
        'r-path', 'r+-r', 'r-r', 'r-r+', 'r+-R', 'r-R', 'r+-rb', 'r-rb', 'r+-rbbr', 'r-rbbr', 'r+-rr', 'r-rr', 'r+-rt',
        'r-rt', 'r+-rw', 'r-rw', 'r+-rx', 'r-rx', 'r+-u', 'r-u', 'r+-w', 'r-w', 'r+-wb+', 'r-wb+', 'r+-ww', 'r-ww', 'r+-x',
        'r-x', 'r+-+xb', 'r-+xb', 'r+-xx', 'r-xx', 'w+-', 'w+-+', 'w+-++', 'w+-☀', 'w-', 'w-+', 'w-++', 'w-☀', 'w+-a', 'w-a',
        'w+-aa', 'w-aa', 'w+-+ab', 'w-+ab', 'w+-bb', 'w-bb', 'w+-br', 'w-br', 'w+-bw+', 'w-bw+', 'w+-r', 'w-r', 'w+-R', 'w-R',
        'w+-rb', 'w-rb', 'w+-rbbr', 'w-rbbr', 'w+-rr', 'w-rr', 'w+-rt', 'w-rt', 'w+-rw', 'w-rw', 'w+-rx', 'w-rx', 'w+-u',
        'w-u', 'w+-w', 'w-w', 'w+-wb+', 'w-wb+', 'w+-ww', 'w-ww', 'w+-x', 'w-x', 'w+-+xb', 'w-+xb', 'w+-xx', 'w-xx', 'x+-',
        'x+-+', 'x+-++', 'x+-☀', 'x-', 'x-+', 'x-++', 'x-☀', 'x+-a', 'x-a', 'x+-aa', 'x-aa', 'x+-+ab', 'x-+ab', 'x+-bb',
        'x-bb', 'x+-br', 'x-br', 'x+-bw+', 'x-bw+', 'x+-r', 'x-r', 'x+-R', 'x-R', 'x+-rb', 'x-rb', 'x+-rbbr', 'x-rbbr',
        'x+-rr', 'x-rr', 'x+-rt', 'x-rt', 'x+-rw', 'x-rw', 'x+-rx', 'x-rx', 'x+-u', 'x-u', 'x+-w', 'x-w', 'x+-wb+', 'x-wb+',
        'x+-ww', 'x-ww', 'x+-x', 'x-x', 'x+-+xb', 'x-+xb', 'x+-xx', 'x-xx'
    ),
    "fileargs": ('bytes', 'invalid', 'path'),
    "handlers": ('warning-new',),
    "history": (
        'b-list-other-create', 'r-Random-both-del', 'r-Random-both-restore', 'r-Random-both-same', 'r-Random-init-restore',
        'r-Random-new-del', 'r-Random-new-restore', 'r-Random-new-same', 'r-Random-none-restore', 'r-Random-other-restore',
        'r-Random-wrapper-restore'
    ),
    "newline": (
        'decoder-decode', 'decoder-getstate', 'decoder-newlines', 'decoder-reset', 'decoder-setstate', 'errors-decode',
        'errors-getstate', 'errors-newlines', 'errors-reset', 'errors-setstate'
    ),
    "opener": ('failed-store', 'ok'),
    "reduced": ('01', '02', '03', '03-os', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13'),
    "reenter": ('warning-path',),
    "reinit": ('classmethod-reenter', 'staticmethod-reenter'),
    "sequence": ('fd-add-concat', 'fd-all-concat', 'fd-all-indent', 'fd-mul-indent'),
    "slots": (
        'BufferedIOBase-bound-n', 'BufferedIOBase-bound-p', 'BufferedIOBase-otherin-k', 'BufferedIOBase-otherin-n',
        'BufferedRandom-bound-n', 'BufferedRandom-bound-p', 'BufferedRandom-otherin-k', 'BufferedRandom-otherin-n',
        'BufferedRandom-otherin-p', 'BufferedRandom-otherin-pk', 'BufferedReader-bound-n', 'BufferedReader-bound-p',
        'BufferedReader-otherin-k', 'BufferedReader-otherin-n', 'BufferedReader-otherin-p', 'BufferedReader-otherin-pk',
        'BufferedRWPair-bound-n', 'BufferedRWPair-bound-p', 'BufferedRWPair-otherin-k', 'BufferedRWPair-otherin-n',
        'BufferedRWPair-otherin-p', 'BufferedRWPair-otherin-pk', 'BufferedWriter-bound-n', 'BufferedWriter-bound-p',
        'BufferedWriter-otherin-k', 'BufferedWriter-otherin-n', 'BufferedWriter-otherin-p', 'BufferedWriter-otherin-pk',
        'bytearray-bound-n', 'bytearray-bound-p', 'bytearray-otherin-k', 'bytearray-otherin-n', 'bytearray-otherin-p',
        'bytearray-otherin-pk', 'bytes-bound-n', 'bytes-bound-p', 'BytesIO-bound-n', 'BytesIO-bound-p', 'BytesIO-otherin-k',
        'BytesIO-otherin-n', 'BytesIO-otherin-p', 'BytesIO-otherin-pk', 'bytes-otherin-n', 'bytes-otherin-p', 'chain-bound-n',
        'chain-bound-p', 'chain-otherin-k', 'chain-otherin-n', 'chain-otherin-p', 'chain-otherin-pk', 'classmethod-bound-p',
        'classmethod-otherin-p', 'complex-bound-n', 'complex-bound-p', 'complex-otherin-n', 'complex-otherin-p',
        'count-bound-n', 'count-bound-p', 'count-otherin-n', 'count-otherin-p', 'defaultdict-bound-n', 'defaultdict-bound-p',
        'defaultdict-otherin-k', 'defaultdict-otherin-n', 'deque-bound-n', 'deque-bound-p', 'deque-otherin-k',
        'deque-otherin-n', 'deque-otherin-p', 'deque-otherin-pk', 'dict-bound-n', 'dict-bound-p', 'dict-otherin-k',
        'dict-otherin-n', 'Exception-bound-n', 'Exception-bound-p', 'Exception-otherin-k', 'Exception-otherin-n',
        'Exception-otherin-p', 'Exception-otherin-pk', 'FileIO-bound-n', 'FileIO-otherin-k', 'FileIO-otherin-n',
        'FileNotFoundError-bound-n', 'FileNotFoundError-otherin-k', 'FileNotFoundError-otherin-n', 'float-bound-n',
        'float-bound-p', 'float-otherin-k', 'float-otherin-n', 'float-otherin-p', 'float-otherin-pk', 'frozenset-bound-n',
        'frozenset-otherin-k', 'frozenset-otherin-n', 'int-bound-n', 'int-bound-p', 'int-otherin-n', 'int-otherin-p',
        'IOBase-bound-n', 'IOBase-bound-p', 'IOBase-otherin-k', 'IOBase-otherin-n', 'list-bound-n', 'list-bound-p',
        'list-mixin-k', 'list-other-k', 'object-bound-n', 'object-bound-p', 'object-otherin-k', 'object-otherin-n',
        'OrderedDict-bound-n', 'OrderedDict-bound-p', 'OrderedDict-otherin-k', 'OrderedDict-otherin-n', 'OSError-bound-n',
        'OSError-bound-p', 'OSError-otherin-k', 'OSError-otherin-n', 'OSError-otherin-p', 'OSError-otherin-pk',
        'product-bound-n', 'product-otherin-n', 'property-bound-n', 'property-bound-p', 'property-otherin-k',
        'property-otherin-n', 'property-otherin-p', 'property-otherin-pk', 'Random-bound-n', 'Random-bound-p',
        'Random-otherin-k', 'Random-otherin-n', 'Random-otherin-p', 'Random-otherin-pk', 'RawIOBase-bound-n',
        'RawIOBase-bound-p', 'RawIOBase-otherin-k', 'RawIOBase-otherin-n', 'repeat-bound-p', 'repeat-otherin-p',
        'set-bound-n', 'set-bound-p', 'set-otherin-k', 'set-otherin-n', 'SimpleNamespace-bound-n', 'SimpleNamespace-bound-p',
        'SimpleNamespace-otherin-k', 'SimpleNamespace-otherin-n', 'staticmethod-bound-p', 'staticmethod-otherin-p',
        'str-bound-n', 'str-bound-p', 'StringIO-bound-n', 'StringIO-bound-p', 'StringIO-otherin-k', 'StringIO-otherin-n',
        'StringIO-otherin-p', 'StringIO-otherin-pk', 'str-otherin-n', 'str-otherin-p', 'TextIOBase-bound-n',
        'TextIOBase-bound-p', 'TextIOBase-otherin-k', 'TextIOBase-otherin-n', 'TextIOWrapper-bound-n',
        'TextIOWrapper-bound-p', 'TextIOWrapper-otherin-k', 'TextIOWrapper-otherin-n', 'TextIOWrapper-otherin-p',
        'TextIOWrapper-otherin-pk', 'tuple-bound-n', 'tuple-otherin-k', 'tuple-otherin-n', 'zip-bound-n',
        'zip_longest-bound-n', 'zip_longest-otherin-n', 'zip-otherin-n'
    ),
    "state": ('block-again', 'block-pass', 'os-again', 'os-pass', 'sre-fail'),
    "substitution": ('fd-typevar-all',),
    "valid": ('rawrandom-cnw-kw', 'rawrandom-delnew-kw', 'rawrandom-new-kw', 'rawrandom-snw-kw'),
}


WARNINGS_SHOWN = ("handlers", "reenter", "reduced")   # their rows of RL-866 are about what showing a warning calls


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a38" / f"{probe.replace('-', '_')}.txt", ROWS[probe], probe in WARNINGS_SHOWN)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_what_a_class_stores_as_init() -> None:
    """The class of RL-859 and RL-860, beyond the two kinds the reviewer ran: a bound built-in, a built-in function, a
    method, a class method and a slot wrapper of another type and of the class's own, a method-wrapper, a staticmethod, a
    classmethod, an object with `__call__`, a class, None, a partial, a property and a function, each stored as `__init__`
    in a class over 14 types and called with nothing, an argument and a keyword. 966 calls in one process on each side."""
    same((HERE / "review_a38" / "init_kinds.txt").read_text(encoding="utf-8"))


def test_the_errno_of_an_interrupted_call_is_read_after_the_handler() -> None:
    """RL-871 in the source: `_trap_eintr`, which may call an `__index__` of the program's, is called from `_interrupted`
    alone, and `_interrupted` from no `except` clause."""
    lines = (PRELUDE / "_io.py").read_text(encoding="utf-8").split("\n")
    calls = [at for at, line in enumerate(lines) if re.search(r"(?<![A-Za-z0-9_])_trap_eintr\(", line) and not line.startswith("def ")]
    assert len(calls) == 1 and lines[calls[0]].strip() == "if not _trap_eintr(failed):", calls
    for at, line in enumerate(lines):
        if "_interrupted(" not in line or line.startswith("def "):
            continue
        indent = len(line) - len(line.lstrip())
        above = next(prior for prior in reversed(lines[:at]) if prior.strip() and len(prior) - len(prior.lstrip()) < indent)
        assert not above.lstrip().startswith(("except", "finally")), (at + 1, above)


if __name__ == "__main__":
    test_the_errno_of_an_interrupted_call_is_read_after_the_handler()
    test_what_a_class_stores_as_init()
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
