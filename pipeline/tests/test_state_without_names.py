"""RL-507 (the author's decision of 2026-11-20, case C-3-76): what a built-in type keeps for its own work has no name.

The prelude writes about 120 of CPython's C types in Python, and each keeps its state in `__slots__`. Those slots are fields
with no name in the compiled program: the sweep here asks every such type, by the modules that hold them and by an object of
each, for every name any class of the prelude declares, under CPython and compiled. The compiled program may show no name
that CPython does not, and must show every one of them that CPython does (partial's func, a buffered stream's _finalizing).
After review A23 (RL-538, RL-544, RL-554) it also asks each type for what a class statement leaves (`__slots__` and its kin)
and for a `__module__` entry, and each member a type shows for what a store of its own value says (a read-only one refuses).

Run under pytest or directly: python3 -m pipeline.tests.test_state_without_names
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build, prelude_state

SWEEP = r'''
import _collections, _contextvars, _csv, _functools, _io, _json, _operator, _random, _sre, _string, _struct, _thread, _weakref
import collections, contextvars, csv, functools, hashlib, hmac, io, itertools, json, operator, os, random, re, string, struct
import sys, tempfile, threading, types, typing, unicodedata, weakref, zlib

NAMES = sorted(sys.argv[1].split(","))


def private(name):
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def left(cls):
    """What a class statement leaves in a class, and what the prelude says of its members: none of it is a C type's."""
    return ",".join(n for n in ("__slots__", "__static_attributes__", "__firstlineno__", "__readonly__", "__boolean__") if n in vars(cls))


print("---- the types the modules hold")
for module in (_collections, _contextvars, _csv, _functools, _io, _json, _operator, _random, _sre, _string, _struct, _thread, _weakref,
               collections, contextvars, csv, functools, io, itertools, operator, random, re, struct, threading, types, typing,
               unicodedata, weakref, zlib, __builtins__):
    for attr, value in sorted(vars(module).items()):
        if isinstance(value, type):
            print(module.__name__ + "." + attr, "|", ",".join(sorted(n for n in vars(value) if private(n))), "|", left(value))


class Thing:
    pass


def keyed(a, b):
    return 0


@functools.lru_cache(maxsize=4)
def cached(x):
    return x


def objects():
    thing = Thing()
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "file")
    with open(path, "wb") as f:
        f.write(b"some bytes\n")
    var = contextvars.ContextVar("var", default=1)
    ctx = contextvars.copy_context()
    token = var.set(2)
    od = collections.OrderedDict(a=1)
    T = typing.TypeVar("T")
    P = typing.ParamSpec("P")
    point = collections.namedtuple("point", "x y")
    pattern = re.compile("(a)")
    raw = io.FileIO(path)
    yield "enumerate", enumerate("ab")
    yield "zip", zip("ab", "cd")
    yield "map", map(str, "ab")
    yield "filter", filter(None, "ab")
    yield "reversed", reversed("ab")
    yield "callable_iterator", iter(int, 1)
    yield "property", property()
    yield "staticmethod", staticmethod(len)
    yield "classmethod", classmethod(len)
    yield "itertools.batched", itertools.batched("abc", 2)
    yield "itertools.pairwise", itertools.pairwise("abc")
    yield "itertools.groupby", itertools.groupby("ab")
    yield "itertools._grouper", next(itertools.groupby("ab"))[1]
    yield "itertools._tee", itertools.tee("ab")[0]
    yield "itertools.cycle", itertools.cycle("ab")
    yield "itertools.dropwhile", itertools.dropwhile(bool, "ab")
    yield "itertools.takewhile", itertools.takewhile(bool, "ab")
    yield "itertools.starmap", itertools.starmap(pow, [(1, 2)])
    yield "itertools.filterfalse", itertools.filterfalse(bool, "ab")
    yield "itertools.compress", itertools.compress("ab", [1, 0])
    yield "itertools.islice", itertools.islice("ab", 1)
    yield "itertools.chain", itertools.chain("ab")
    yield "itertools.product", itertools.product("ab")
    yield "itertools.combinations", itertools.combinations("ab", 1)
    yield "itertools.combinations_with_replacement", itertools.combinations_with_replacement("ab", 1)
    yield "itertools.permutations", itertools.permutations("ab")
    yield "itertools.accumulate", itertools.accumulate([1, 2])
    yield "itertools.count", itertools.count()
    yield "itertools.repeat", itertools.repeat(1)
    yield "itertools.zip_longest", itertools.zip_longest("ab", "c")
    yield "deque", collections.deque("ab")
    yield "deque iterator", iter(collections.deque("ab"))
    yield "deque reverse iterator", reversed(collections.deque("ab"))
    yield "defaultdict", collections.defaultdict(list)
    yield "OrderedDict", od
    yield "odict iterator", iter(od)
    yield "a named tuple's field", vars(point)["x"]
    yield "partial", functools.partial(print, 1)
    yield "cmp_to_key's key", functools.cmp_to_key(keyed)(1)
    yield "lru_cache's wrapper", cached
    yield "itemgetter", operator.itemgetter(1)
    yield "attrgetter", operator.attrgetter("a")
    yield "methodcaller", operator.methodcaller("a")
    yield "random.Random", random.Random(1)
    yield "weakref.ref", weakref.ref(thing)
    yield "struct.Struct", struct.Struct("<i")
    yield "struct's iterator", struct.iter_unpack("<i", b"\0\0\0\0")
    yield "a lock", threading.Lock()
    yield "an RLock", threading.RLock()
    yield "threading.local", threading.local()
    yield "re.Pattern", pattern
    yield "re.Match", pattern.match("a")
    yield "re's scanner", pattern.scanner("a")
    yield "a formatter's iterator", _string.formatter_parser("a{b}")
    yield "a field name's iterator", _string.formatter_field_name_split("a.b")[1]
    yield "ContextVar", var
    yield "Context", ctx
    yield "Token", token
    yield "a context's keys", ctx.keys()
    yield "a context's values", ctx.values()
    yield "a context's items", ctx.items()
    yield "csv.reader", csv.reader([])
    yield "csv.writer", csv.writer(io.StringIO())
    yield "a csv dialect", _csv.get_dialect("excel")
    yield "json's scanner", json.decoder.JSONDecoder().scan_once
    yield "FileIO", raw
    yield "BufferedReader", io.BufferedReader(raw)
    yield "BufferedWriter", io.BufferedWriter(io.BytesIO())
    yield "BufferedRandom", io.BufferedRandom(io.BytesIO())
    yield "BufferedRWPair", io.BufferedRWPair(io.BytesIO(), io.BytesIO())
    yield "BytesIO", io.BytesIO(b"ab")
    yield "StringIO", io.StringIO("ab")
    yield "TextIOWrapper", io.TextIOWrapper(io.BytesIO(b"ab"))
    yield "IncrementalNewlineDecoder", io.IncrementalNewlineDecoder(None, True)
    yield "md5", hashlib.md5()
    yield "sha1", hashlib.sha1()
    yield "sha256", hashlib.sha256()
    yield "sha512", hashlib.sha512()
    yield "sha3_256", hashlib.sha3_256()
    yield "shake_128", hashlib.shake_128()
    yield "blake2b", hashlib.blake2b()
    yield "blake2s", hashlib.blake2s()
    yield "zlib's compressor", zlib.compressobj()
    yield "zlib's decompressor", zlib.decompressobj()
    yield "unicodedata's old database", unicodedata.ucd_3_2_0
    yield "TypeVar", T
    yield "ParamSpec", P
    yield "ParamSpec's args", P.args
    yield "ParamSpec's kwargs", P.kwargs
    yield "TypeVarTuple", typing.TypeVarTuple("Ts")
    yield "TypeAliasType", typing.TypeAliasType("Alias", int)
    yield "GenericAlias", list[int]
    yield "a generic alias's iterator", iter(tuple[int, str])
    yield "Union", int | str
    yield "SimpleNamespace", types.SimpleNamespace(a=1)
    with os.scandir(folder) as found:
        yield "os.scandir's iterator", found
        for entry in found:
            yield "DirEntry", entry
    raw.close()
    os.remove(path)
    os.rmdir(folder)


print("---- an object of each")
for label, obj in objects():
    seen = []
    for name in NAMES:
        try:
            if hasattr(obj, name):
                seen.append(name)
        except Exception as e:
            seen.append(name + "!" + type(e).__name__)
    in_classes = sorted({n for c in type(obj).__mro__ for n in vars(c) if private(n) and n in NAMES})
    stores = []
    for name in seen:                            # a member the type shows: what a store of its own value says
        if "!" not in name and type(getattr(type(obj), name, None)).__name__ == "member_descriptor":
            try:
                setattr(obj, name, getattr(obj, name))
                stores.append(name + "=stored")
            except Exception as e:
                stores.append(name + "=" + type(e).__name__)
    print(label, "|", ",".join(seen), "|", ",".join(in_classes), "|", ";".join(left(c) for c in type(obj).__mro__), "|",
          repr(vars(type(obj)).get("__module__")), "|", ",".join(stores))
'''


OPENSSLS = frozenset({"md5", "sha1", "sha256", "sha512", "sha3_256", "shake_128", "blake2b", "blake2s"})


def _table(text: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if " | " in line or line.endswith(" |"):
            key, _, rest = line.partition(" |")
            rows[key] = [part.strip() for part in rest.split("|")]
    return rows


def test_no_built_in_type_shows_the_names_of_its_state() -> None:
    names = ",".join(sorted(prelude_state()))
    folder = Path(tempfile.mkdtemp(prefix="bella-state-"))
    try:
        program = folder / "prog.py"
        program.write_text(SWEEP, encoding="utf-8")
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        reference = subprocess.run([sys.executable, str(program), names], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert reference.returncode == 0, reference.stderr
        compiled = subprocess.run([str(build(program, "prog.py")), names], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert compiled.returncode == 0, compiled.stderr + compiled.stdout[-2000:]
        theirs, ours = _table(reference.stdout), _table(compiled.stdout)
        wrong: list[str] = []
        types_seen = objects_seen = 0
        for key, row in ours.items():
            if key not in theirs:
                continue                             # a name of a module the runtime has and CPython does not: the names list's
            if len(row) == 2:                        # a type a module holds
                if theirs[key][1]:
                    continue                         # written in Python in CPython too: its class statement's names are its own
                types_seen += 1
                extra = sorted(set(filter(None, row[0].split(","))) - set(filter(None, theirs[key][0].split(","))))
                if extra:                            # no private name that CPython's type lacks,
                    wrong.append(f"{key}: the type's dict has {extra}")
                if row[1]:                           # and nothing a class statement leaves (RL-544)
                    wrong.append(f"{key}: the type's dict has {row[1]}")
            else:                                    # an object: the same answers for every name the prelude declares, the same
                objects_seen += 1                    # leavings in its classes, the same __module__ entry, the same stores
                theirs_row = theirs[key]
                if key in OPENSSLS:                  # D-20: the reference's hash objects are OpenSSL's _hashlib.HASH, another
                    row, theirs_row = row[:2] + row[4:], theirs_row[:2] + theirs_row[4:]   # type with another MRO and module
                if row != theirs_row:
                    wrong.append(f"{key}: compiled {row}, CPython {theirs_row}")
        missing = sorted(k for k, row in theirs.items() if len(row) > 2 and k not in ours)
        assert not missing, missing
        assert not wrong, json.dumps(wrong, indent=1)
        assert objects_seen >= 95 and types_seen >= 150, (objects_seen, types_seen)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_no_built_in_type_shows_the_names_of_its_state()
    print("ok")
