"""Review A40 (Codex Astra, low effort) of c1a3dbd..98d8f3f, four steps in one review: the fixes of review A39, a slot named
twice, how a Struct gets its format in 3.15, and the minimal memoryview.

17 findings, RL-886 to RL-902, and one from its saved outputs, RL-903; `docs/reviews/review-log.md` has each with its
verdict. The programs are the reviewer's own probes (`review_a40/<probe>.txt`, one row a process): the rows that differed
between CPython and the compiled program and agree now. Not here: rows of a comprehension helper's lifetime (TODO), rows
where a consumer of bytes-like data holds no buffer of a view while it runs (RL-702, RL-583: TODO), and `binascii`'s
functions that stop by name.

What the rows and the tests hold:

* A view checks for a release where CPython does: again after an index's `__index__` (`view/sub`, `view/set`: RL-891),
  after an assigned value's conversion, and after every read (`unpack_single`); a slice holds the buffer before its bounds
  are converted, so a bound that releases the view leaves the slice whole (`view/slice`: RL-892); the exporter's hash is
  asked while the view holds a buffer of itself, so the hash cannot release it (`surface/forhash-plain`: RL-898); the hash
  is kept once computed and answered after a release (`view/cache`: RL-886).
* A view's keys and arguments are read as the C reads them: a tuple's own cells, not its class's `__bool__` or iteration
  (`view/tuple`: RL-888); `tobytes`' order as UTF-8 characters, converted before the release check (`view/order`,
  `surface/surrogate-*`: RL-889); a slice's stride a Py_ssize_t (`view/stride`: RL-890); an assigned octet's conversion
  errors through `fix_error_int` (`conversion/*`: RL-902), and a wrong key a TypeError.
* A view's end lets its hold go before its weak references are told (`view/weak`: RL-887).
* The consumers: TextIOWrapper's chunk, `bytearray.extend` and binascii's ASCII converter word a failed buffer as their own
  TypeError (`consumers/text-*`, `extend-*`, `hexlify-*`: RL-893, RL-894, RL-896); `fromhex` takes a view (RL-895);
  `re.sub` reads a view replacement's own octets (`consumers/sub-contiguous`: RL-897), and retries one whose step is not 1
  as bytes; bytearray's `partition` and `rpartition` copy the separator (`extra/*`, `methods/rpartition-stride`: RL-901).
* `memory_iterator` is presented as CPython's: final, with slot wrappers (`construct/*`, `conversion/metadata`,
  `conversion/iterwrong`: RL-900, from the names table).
* What stops by name: a class over bytes or bytearray with a `__buffer__` or `__release_buffer__` of its own (RL-899, the
  buffer protocol on a program's class, [P2+]), and a `__getattribute__` stored in a class after it was made (RL-903).
* `sweep.txt` is the session's sweep of the classes: every operation of a view whose argument runs the program's code, with
  code that releases the view, another view of the exporter, both, or lets the exporter go; every kind of value an item
  assignment can be given, and of key; and the death order of views of every shape. 269 rows in one process a side.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a40
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent

ROWS: dict[str, tuple[str, ...]] = {
    "construct": ("itersub", "next"),
    "consumers": ("afromhex-contiguous", "afromhex-released", "afromhex-stride", "extend-released", "extend-stride", "fromhex-contiguous",
                  "fromhex-released", "fromhex-stride", "hexlify-released", "hexlify-stride", "sub-contiguous", "text-released", "text-stride"),
    "conversion": ("iterwrong", "metadata", "myoverflow", "mytype", "myvalue", "overflow"),
    "extra": ("partition-partition", "partition-rpartition"),
    "methods": ("rpartition-stride",),
    "minimal": ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "15", "16", "17"),
    "surface": ("forhash-plain", "surrogate-empty", "surrogate-gone", "surrogate-plain", "surrogate-reverse", "surrogate-slice"),
    "view": ("cache", "order", "set", "slice", "stride", "sub", "tuple", "weak"),
}

BUFFER_HOOK = "[P2+] the buffer protocol of a class over bytes or bytearray"
GETATTRIBUTE = "[P2+] a class that overrides __getattribute__"
STOPS: dict[str, tuple[str, str]] = {
    "a __buffer__ in the class statement": ("class B(bytes):\n    def __buffer__(self, flags):\n        raise LookupError\n", BUFFER_HOOK),
    "a __release_buffer__": ("class B(bytearray):\n    def __release_buffer__(self, view):\n        pass\n", BUFFER_HOOK),
    "from a base of the program's": ("class H:\n    def __buffer__(self, flags):\n        raise LookupError\nclass B(H, bytes):\n    pass\n",
                                     BUFFER_HOOK),
    "stored afterwards": ("class B(bytes):\n    pass\nB.__buffer__ = lambda self, flags: None\n", BUFFER_HOOK),
    "stored in a base afterwards": ("class A(bytes):\n    pass\nclass B(A):\n    pass\nA.__release_buffer__ = len\n", BUFFER_HOOK),
    "a __getattribute__ stored afterwards": ("class X:\n    pass\nx = X()\nX.__getattribute__ = lambda self, name: 1\nprint(x.y)\n",
                                             GETATTRIBUTE),
    "a built-in stored as __getattribute__": ("class X:\n    pass\nx = X()\nX.__getattribute__ = len\nprint(x.y)\n", GETATTRIBUTE),
}


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a40" / f"{probe}.txt", ROWS[probe])


def stops_by_name(name: str) -> None:
    source, words = STOPS[name]
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("print('start')\n" + source + "print('went on')\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr and words in got.stderr, (name, got)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))
    if "stop" in metafunc.fixturenames:
        metafunc.parametrize("stop", sorted(STOPS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_stops(stop: str) -> None:
    stops_by_name(stop)


def test_what_is_not_a_hook_goes_on() -> None:
    """A class over bytes that defines other names, and a class with `__buffer__` over no octets (whose use stops where the
    octets are taken, as before), are made as CPython makes them."""
    same("class B(bytes):\n    def __len__(self):\n        return 7\nclass H:\n    def __buffer__(self, flags):\n        return None\n"
         "print(len(B(b'a')), memoryview(B(b'ab')).tolist(), H.__name__)\n")


def test_sweep() -> None:
    same((HERE / "review_a40" / "sweep.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    for probe in sorted(ROWS):
        rows_agree(probe)
    for stop in sorted(STOPS):
        stops_by_name(stop)
    test_what_is_not_a_hook_goes_on()
    test_sweep()
    print("ok")
