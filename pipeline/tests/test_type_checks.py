"""The type tests of CPython's C against an object whose `__class__` says otherwise (RL-655).

Where a C function asks whether its argument is a str, an int, a tuple or a dict, it reads the object's type
(PyUnicode_Check, PyLong_Check, PyTuple_Check, PyObject_TypeCheck). The preludes that stand for those functions asked
`isinstance(x, str)`, which is true for an object whose `__class__` property says str, and reads that property. Review
A30 found it in `open` (RL-651); 169 such calls stood in 16 preludes. They ask `issubclass(type(x), T)` now, except the
three that stand for a real PyObject_IsInstance (`deque + other`, a class pattern of a match statement) or are CPython's
own stand-in.

The sweep calls each function with such an object as an argument, or as what a callback of the program's hands back. A
process for each row, compiled against CPython: the outcome and how often `__class__` was read, which is never for the
C's type tests. Before the change 151 of the 191 rows differed and one ended the program (`codecs.utf_8_encode`).

Run under pytest or directly: python3 -m pipeline.tests.test_type_checks
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import same

SWEEP = r'''
"""Each row calls one function of the standard library that CPython writes in C, with an argument (or with a value a
callback of the program's hands back) whose `__class__` says it is a str, an int, a tuple and so on, and is none. The C
tests the object's type (PyUnicode_Check, PyLong_Check, PyTuple_Check, PyObject_TypeCheck), which no `__class__` answers
for. One row a process: the row's name is argv[1]."""
import ast
import codecs
import collections
import csv
import grp
import io
import json
import json.decoder
import json.encoder
import json.scanner
import pwd
import re
import string.templatelib
import sys
import typing
import warnings
import _imp
import _locale

asked: list[str] = []


def liar(kind: type) -> object:
    """An object whose `__class__` is `kind`, and whose type is not."""
    class Liar:
        @property
        def __class__(self) -> type:  # type: ignore[override]
            asked.append(kind.__name__)
            return kind
    return Liar()


def codec(encode: object = None, decode: object = None, inc_decoder: object = None) -> str:
    """A codec of the program's under a name of its own, with the given parts."""
    name = "liar_codec"

    def search(asked_for: str) -> object:
        if asked_for != name:
            return None
        return codecs.CodecInfo(encode or codecs.lookup("ascii").encode, decode or codecs.lookup("ascii").decode,  # type: ignore[arg-type]
                                incrementaldecoder=inc_decoder, name=name)  # type: ignore[arg-type]
    codecs.register(search)
    return name


def decoder(result: object = None, state: object = None) -> type:
    """An incremental decoder whose decode() gives `result` and whose getstate() gives `state`."""
    class Decoder(codecs.IncrementalDecoder):
        def decode(self, data: object, final: bool = False) -> object:  # type: ignore[override]
            return "x" if result is None else result

        def getstate(self) -> object:  # type: ignore[override]
            return (b"", 0) if state is None else state

        def setstate(self, given: object) -> None:  # type: ignore[override]
            pass

        def reset(self) -> None:
            pass
    return Decoder


def text(inc_decoder: type) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(b"abc\ndef\n"), encoding=codec(inc_decoder=inc_decoder))


def with_filters(item: object) -> object:
    warnings.filters.insert(0, item)  # type: ignore[arg-type]
    warnings.warn("text", UserWarning)
    return "warned"


def with_attribute(name: str, value: object) -> object:
    setattr(warnings, name, value)
    warnings.warn("text", UserWarning)
    return "warned"


def from_stdin(line: object) -> object:
    class Stdin:
        def readline(self) -> object:
            return line
    sys.stdin = Stdin()  # type: ignore[assignment]
    return input()


def raw_returning(n: object) -> io.BufferedReader:
    class Raw(io.RawIOBase):
        def readable(self) -> bool:
            return True

        def readinto(self, b: object) -> object:
            return n
    return io.BufferedReader(Raw())


def raw_writing(n: object) -> io.BufferedWriter:
    class Raw(io.RawIOBase):
        def writable(self) -> bool:
            return True

        def write(self, b: object) -> object:  # type: ignore[override]
            return n
    return io.BufferedWriter(Raw())


def lines_of(kind: type, line: object) -> object:
    class Lines(kind):  # type: ignore[misc, valid-type]
        def readline(self, size: int = -1) -> object:  # type: ignore[override]
            return line
    return Lines(io.BytesIO(b"x\n")) if kind is io.TextIOWrapper else Lines("x\n")


def dumps_items(item: object) -> str:
    class Items(dict):  # type: ignore[type-arg]
        def items(self) -> object:  # type: ignore[override]
            return [item]
    return json.dumps(Items(a=1), sort_keys=True)


def c_encoder(encoder: object) -> object:
    make = json.encoder.c_make_encoder
    return make(None, lambda o: o, encoder, None, ":", ",", False, False, True)([1.5, "a"], 0)  # type: ignore[misc]


def field_type(kind: object) -> object:
    class Node(ast.AST):
        _fields = ("x",)
        _field_types = {"x": kind}
    return type(Node()).__name__


def rows() -> dict[str, typing.Callable[[], object]]:
    tw = lambda **kw: io.TextIOWrapper(io.BytesIO(), **kw)  # noqa: E731
    return {
        # _ast
        "ast: repr of a field that says list": lambda: repr(ast.Module(body=liar(list), type_ignores=[])),  # type: ignore[arg-type]
        "ast: repr of a field that says AST": lambda: repr(ast.Expr(value=liar(ast.AST))),  # type: ignore[arg-type]
        "ast: repr of a list item that says AST": lambda: repr(ast.Module(body=[liar(ast.AST)], type_ignores=[])),  # type: ignore[list-item]
        "ast: a field type that says type": lambda: field_type(liar(type)),
        # _codecs
        "codecs.lookup": lambda: codecs.lookup(liar(str)),  # type: ignore[arg-type]
        "codecs.encode, the encoding": lambda: codecs.encode("a", liar(str)),  # type: ignore[arg-type]
        "codecs.encode, the errors": lambda: codecs.encode("a", "ascii", liar(str)),  # type: ignore[arg-type]
        "codecs.decode, the encoding": lambda: codecs.decode(b"a", liar(str)),  # type: ignore[arg-type]
        "codecs.lookup_error": lambda: codecs.lookup_error(liar(str)),  # type: ignore[arg-type]
        "codecs.register_error": lambda: codecs.register_error(liar(str), codecs.strict_errors),  # type: ignore[arg-type]
        "codecs.strict_errors": lambda: codecs.strict_errors(liar(UnicodeError)),  # type: ignore[arg-type]
        "codecs.ignore_errors": lambda: codecs.ignore_errors(liar(UnicodeEncodeError)),  # type: ignore[arg-type]
        "codecs.replace_errors": lambda: codecs.replace_errors(liar(UnicodeDecodeError)),  # type: ignore[arg-type]
        "codecs.utf_8_encode": lambda: codecs.utf_8_encode(liar(str)),  # type: ignore[arg-type]
        "codecs.utf_8_decode": lambda: codecs.utf_8_decode(liar(bytes)),  # type: ignore[arg-type]
        "codecs.utf_8_encode, the errors": lambda: codecs.utf_8_encode("a", liar(str)),  # type: ignore[arg-type]
        "codecs.readbuffer_encode": lambda: codecs.readbuffer_encode(liar(str)),  # type: ignore[arg-type]
        "codecs.escape_decode": lambda: codecs.escape_decode(liar(bytes)),  # type: ignore[arg-type]
        "codecs.charmap_build": lambda: codecs.charmap_build(liar(str)),  # type: ignore[arg-type]
        "str.encode, an encoder that gives what says bytes": lambda: "a".encode(codec(encode=lambda s, e="strict": (liar(bytes), 1))),
        "str.encode, an encoder that gives what says tuple": lambda: "a".encode(codec(encode=lambda s, e="strict": liar(tuple))),
        "bytes.decode, a decoder that gives what says str": lambda: b"a".decode(codec(decode=lambda s, e="strict": (liar(str), 1))),
        "bytes.decode, a decoder that gives what says tuple": lambda: b"a".decode(codec(decode=lambda s, e="strict": liar(tuple))),
        "codecs.lookup, a search function that gives what says tuple": lambda: (codecs.register(lambda name: liar(tuple)), codecs.lookup("no-such-codec-a30"))[1],
        "str.encode, the encoding": lambda: "a".encode(liar(str)),  # type: ignore[arg-type]
        "bytes.decode, the errors": lambda: b"\xff".decode("ascii", liar(str)),  # type: ignore[arg-type]
        # _collections
        "OrderedDict.move_to_end, a key that says tuple": lambda: collections.OrderedDict().move_to_end(liar(tuple)),
        "OrderedDict.pop, a key that says tuple": lambda: collections.OrderedDict().pop(liar(tuple)),
        "OrderedDict | what says dict": lambda: collections.OrderedDict(a=1) | liar(dict),  # type: ignore[operator]
        "what says OrderedDict | OrderedDict": lambda: liar(collections.OrderedDict) | collections.OrderedDict(a=1),  # type: ignore[operator]
        "OrderedDict |= what says dict": lambda: collections.OrderedDict(a=1).__ior__(liar(dict)),  # type: ignore[arg-type]
        "OrderedDict == what says dict": lambda: collections.OrderedDict(a=1) == liar(dict),
        "OrderedDict == what says OrderedDict": lambda: collections.OrderedDict(a=1) == liar(collections.OrderedDict),
        "OrderedDict != what says dict": lambda: collections.OrderedDict(a=1) != liar(dict),
        "deque + what says deque (PyObject_IsInstance: asked)": lambda: collections.deque([1]) + liar(collections.deque),  # type: ignore[operator]
        "deque == what says deque": lambda: collections.deque([1]) == liar(collections.deque),
        "deque += what says deque": lambda: collections.deque([1]).__iadd__(liar(collections.deque)),  # type: ignore[arg-type]
        # _csv
        "csv.writer, a dialect that says Dialect": lambda: (s := io.StringIO(), csv.writer(s, dialect=liar(csv.Dialect)).writerow(["a", "b c"]), s.getvalue())[2],  # type: ignore[arg-type]
        "csv.reader, a dialect that says Dialect": lambda: list(csv.reader(["a,b"], dialect=liar(csv.Dialect))),  # type: ignore[arg-type]
        "csv.register_dialect, a name that says str": lambda: csv.register_dialect(liar(str)),  # type: ignore[arg-type]
        "csv.writer, a delimiter that says str": lambda: csv.writer(io.StringIO(), delimiter=liar(str)),  # type: ignore[arg-type]
        "csv.field_size_limit": lambda: csv.field_size_limit(liar(int)),  # type: ignore[arg-type]
        # _imp
        "_imp.is_builtin": lambda: _imp.is_builtin(liar(str)),  # type: ignore[arg-type]
        "_imp.is_frozen": lambda: _imp.is_frozen(liar(str)),  # type: ignore[arg-type]
        "_imp.find_frozen": lambda: _imp.find_frozen(liar(str)),  # type: ignore[arg-type]
        "_imp.get_frozen_object": lambda: _imp.get_frozen_object(liar(str)),  # type: ignore[arg-type]
        "_imp.is_frozen_package": lambda: _imp.is_frozen_package(liar(str)),  # type: ignore[arg-type]
        "_imp.source_hash": lambda: _imp.source_hash(1, liar(bytes)),  # type: ignore[arg-type]
        "_imp.init_frozen": lambda: _imp.init_frozen(liar(str)),  # type: ignore[arg-type]
        # _io
        "open, the mode": lambda: open("/dev/null", liar(str)),  # type: ignore[call-overload]
        "open, the encoding": lambda: open("/dev/null", "r", -1, liar(str)),  # type: ignore[arg-type]
        "open, the errors": lambda: open("/dev/null", "r", -1, "ascii", liar(str)),  # type: ignore[arg-type]
        "open, the newline": lambda: open("/dev/null", "r", -1, "ascii", "strict", liar(str)),  # type: ignore[arg-type]
        "open, the buffering": lambda: open("/dev/null", "rb", liar(int)),  # type: ignore[call-overload]
        "open, an opener that gives what says int": lambda: open("/dev/null", "rb", opener=lambda path, flags: liar(int)),  # type: ignore[arg-type, return-value]
        "io.FileIO, the mode": lambda: io.FileIO("/dev/null", liar(str)),  # type: ignore[arg-type]
        "io.FileIO, an opener that gives what says int": lambda: io.FileIO("/dev/null", opener=lambda path, flags: liar(int)),  # type: ignore[arg-type, return-value]
        "io.open_code": lambda: io.open_code(liar(str)),  # type: ignore[arg-type]
        "FileIO.seek": lambda: io.FileIO("/dev/null").seek(liar(int)),  # type: ignore[arg-type]
        "FileIO.seek, the whence": lambda: io.FileIO("/dev/null").seek(0, liar(int)),  # type: ignore[arg-type]
        "FileIO.read": lambda: io.FileIO("/dev/null").read(liar(int)),  # type: ignore[arg-type]
        "FileIO.truncate": lambda: io.FileIO("/dev/null", "r+").truncate(liar(int)),  # type: ignore[arg-type]
        "BytesIO, its initial bytes": lambda: io.BytesIO(liar(bytes)),  # type: ignore[arg-type]
        "BytesIO.read": lambda: io.BytesIO(b"abc").read(liar(int)),  # type: ignore[arg-type]
        "BytesIO.readline": lambda: io.BytesIO(b"abc").readline(liar(int)),  # type: ignore[arg-type]
        "BytesIO.readlines": lambda: io.BytesIO(b"a\nb\n").readlines(liar(int)),  # type: ignore[arg-type]
        "BytesIO.seek": lambda: io.BytesIO(b"abc").seek(liar(int)),  # type: ignore[arg-type]
        "BytesIO.truncate": lambda: io.BytesIO(b"abc").truncate(liar(int)),  # type: ignore[arg-type]
        "BytesIO.write": lambda: io.BytesIO().write(liar(bytes)),  # type: ignore[arg-type]
        "BytesIO.__setstate__, the state": lambda: io.BytesIO().__setstate__(liar(tuple)),  # type: ignore[arg-type]
        "BytesIO.__setstate__, the position": lambda: io.BytesIO().__setstate__((b"abc", liar(int), None)),  # type: ignore[arg-type]
        "BytesIO.__setstate__, the dict": lambda: io.BytesIO().__setstate__((b"abc", 0, liar(dict))),  # type: ignore[arg-type]
        "StringIO, its initial value": lambda: io.StringIO(liar(str)),  # type: ignore[arg-type]
        "StringIO, its newline": lambda: io.StringIO("", liar(str)),  # type: ignore[arg-type]
        "StringIO.write": lambda: io.StringIO().write(liar(str)),  # type: ignore[arg-type]
        "StringIO.read": lambda: io.StringIO("abc").read(liar(int)),  # type: ignore[arg-type]
        "StringIO.readline": lambda: io.StringIO("abc").readline(liar(int)),  # type: ignore[arg-type]
        "StringIO.seek": lambda: io.StringIO("abc").seek(liar(int)),  # type: ignore[arg-type]
        "StringIO.truncate": lambda: io.StringIO("abc").truncate(liar(int)),  # type: ignore[arg-type]
        "StringIO.__setstate__, the state": lambda: io.StringIO().__setstate__(liar(tuple)),  # type: ignore[arg-type]
        "StringIO.__setstate__, the value": lambda: io.StringIO().__setstate__((liar(str), "\n", 0, None)),  # type: ignore[arg-type]
        "StringIO.__setstate__, the position": lambda: io.StringIO().__setstate__(("abc", "\n", liar(int), None)),  # type: ignore[arg-type]
        "StringIO.__setstate__, the dict": lambda: io.StringIO().__setstate__(("abc", "\n", 0, liar(dict))),  # type: ignore[arg-type]
        "a StringIO subclass whose readline gives what says str": lambda: next(lines_of(io.StringIO, liar(str))),  # type: ignore[call-overload]
        "a TextIOWrapper subclass whose readline gives what says str": lambda: next(lines_of(io.TextIOWrapper, liar(str))),  # type: ignore[call-overload]
        "TextIOWrapper, the encoding": lambda: tw(encoding=liar(str)),
        "TextIOWrapper, the errors": lambda: tw(encoding="ascii", errors=liar(str)),
        "TextIOWrapper, the newline": lambda: tw(encoding="ascii", newline=liar(str)),
        "TextIOWrapper.write": lambda: tw(encoding="ascii").write(liar(str)),  # type: ignore[arg-type]
        "TextIOWrapper.read, the size": lambda: text(decoder()).read(liar(int)),  # type: ignore[arg-type]
        "TextIOWrapper.readline, the size": lambda: text(decoder()).readline(liar(int)),  # type: ignore[arg-type]
        "TextIOWrapper.seek": lambda: text(decoder()).seek(liar(int)),  # type: ignore[arg-type]
        "TextIOWrapper.reconfigure, the encoding": lambda: tw(encoding="ascii").reconfigure(encoding=liar(str)),  # type: ignore[arg-type]
        "TextIOWrapper.read, a decoder that gives what says str": lambda: text(decoder(result=liar(str))).read(),
        "TextIOWrapper.read(1), a decoder that gives what says str": lambda: text(decoder(result=liar(str))).read(1),
        "TextIOWrapper.readline, a decoder that gives what says str": lambda: text(decoder(result=liar(str))).readline(),
        "TextIOWrapper.tell, a state that says tuple": lambda: (t := text(decoder(state=liar(tuple))), t.read(1), t.tell())[2],
        "TextIOWrapper.tell, a state whose buffer says bytes": lambda: (t := text(decoder(state=(liar(bytes), 0))), t.read(1), t.tell())[2],
        "TextIOWrapper.read, a buffer that gives what says bytes": lambda: io.TextIOWrapper(raw_reading(liar(bytes)), encoding="ascii").read(),  # type: ignore[arg-type]
        "IncrementalNewlineDecoder.decode, a decoder that gives what says str": lambda: io.IncrementalNewlineDecoder(decoder(result=liar(str))(), True).decode(b"a"),
        "IncrementalNewlineDecoder.decode, what says str": lambda: io.IncrementalNewlineDecoder(None, True).decode(liar(str)),  # type: ignore[arg-type]
        "IncrementalNewlineDecoder.getstate, a state that says tuple": lambda: io.IncrementalNewlineDecoder(decoder(state=liar(tuple))(), True).getstate(),
        "IncrementalNewlineDecoder.getstate, a flag that says int": lambda: io.IncrementalNewlineDecoder(decoder(state=(b"", liar(int)))(), True).getstate(),
        "IncrementalNewlineDecoder.setstate, what says tuple": lambda: io.IncrementalNewlineDecoder(decoder()(), True).setstate(liar(tuple)),  # type: ignore[arg-type]
        "IncrementalNewlineDecoder.setstate, a flag that says int": lambda: io.IncrementalNewlineDecoder(decoder()(), True).setstate((b"", liar(int))),  # type: ignore[arg-type]
        "BufferedReader.read, a raw readinto that gives what says int": lambda: raw_returning(liar(int)).read(1),
        "BufferedWriter.flush, a raw write that gives what says int": lambda: (w := raw_writing(liar(int)), w.write(b"a"), w.flush())[2],
        "BufferedReader, the buffer size": lambda: io.BufferedReader(io.BytesIO(), liar(int)),  # type: ignore[arg-type]
        "BufferedReader.read, the size": lambda: io.BufferedReader(io.BytesIO(b"abc")).read(liar(int)),  # type: ignore[arg-type]
        "BufferedReader.seek": lambda: io.BufferedReader(io.BytesIO(b"abc")).seek(liar(int)),  # type: ignore[arg-type]
        "io.text_encoding": lambda: io.text_encoding(liar(str)),  # type: ignore[arg-type]
        # _json
        "json.dumps, what says str": lambda: json.dumps(liar(str)),
        "json.dumps, what says int": lambda: json.dumps(liar(int)),
        "json.dumps, what says float": lambda: json.dumps(liar(float)),
        "json.dumps, what says list": lambda: json.dumps(liar(list)),
        "json.dumps, what says dict": lambda: json.dumps(liar(dict)),
        "json.dumps, in a list what says str": lambda: json.dumps([liar(str)]),
        "json.dumps, in a list what says int": lambda: json.dumps([liar(int)]),
        "json.dumps, in a list what says float": lambda: json.dumps([liar(float)]),
        "json.dumps, in a list what says tuple": lambda: json.dumps([liar(tuple)]),
        "json.dumps, in a list what says dict": lambda: json.dumps([liar(dict)]),
        "json.dumps, a key that says str": lambda: json.dumps({liar(str): 1}),
        "json.dumps, a key that says int": lambda: json.dumps({liar(int): 1}),
        "json.dumps, a key that says float": lambda: json.dumps({liar(float): 1}),
        "json.dumps, a key that says str, skipped": lambda: json.dumps({liar(str): 1}, skipkeys=True),
        "json.dumps, items that say tuple": lambda: dumps_items(liar(tuple)),
        "json.dumps, a separator that says str": lambda: json.dumps([1, 2], separators=(liar(str), ":")),  # type: ignore[arg-type]
        "json.dumps, a key separator that says str": lambda: json.dumps({"a": 1}, separators=(",", liar(str))),  # type: ignore[arg-type]
        "json: an encoder that gives what says str": lambda: c_encoder(lambda s: liar(str)),
        "json: a float's text that says str": lambda: json.encoder.c_make_encoder(None, lambda o: o, json.encoder.encode_basestring, None, ":", ",", False, False, True)([1.5], 0),  # type: ignore[misc]
        "json: markers that say dict": lambda: json.encoder.c_make_encoder(liar(dict), lambda o: o, json.encoder.encode_basestring, None, ":", ",", False, False, True),  # type: ignore[misc]
        "json.encoder.c_encode_basestring_ascii": lambda: json.encoder.c_encode_basestring_ascii(liar(str)),  # type: ignore[misc]
        "json.encoder.c_encode_basestring": lambda: json.encoder.c_encode_basestring(liar(str)),  # type: ignore[misc]
        "json.decoder.c_scanstring": lambda: json.decoder.c_scanstring(liar(str), 0),  # type: ignore[misc]
        "json.loads, what says str": lambda: json.loads(liar(str)),  # type: ignore[arg-type]
        "json: a scanner called with what says str": lambda: json.scanner.c_make_scanner(json.JSONDecoder())(liar(str), 0),  # type: ignore[misc]
        "json: a scanner called with an index that says int": lambda: json.scanner.c_make_scanner(json.JSONDecoder())("1", liar(int)),  # type: ignore[misc]
        # _locale
        "_locale.strcoll, the first": lambda: _locale.strcoll(liar(str), "a"),  # type: ignore[arg-type]
        "_locale.strcoll, the second": lambda: _locale.strcoll("a", liar(str)),  # type: ignore[arg-type]
        "_locale.strxfrm": lambda: _locale.strxfrm(liar(str)),  # type: ignore[arg-type]
        "_locale.setlocale, the category": lambda: _locale.setlocale(liar(int)),  # type: ignore[arg-type]
        "_locale.setlocale, the locale": lambda: _locale.setlocale(0, liar(str)),  # type: ignore[arg-type]
        "_locale.gettext": lambda: _locale.gettext(liar(str)),  # type: ignore[arg-type]
        "_locale.dgettext": lambda: _locale.dgettext(liar(str), "a"),  # type: ignore[arg-type]
        "_locale.textdomain": lambda: _locale.textdomain(liar(str)),  # type: ignore[arg-type]
        "_locale.bindtextdomain, the domain": lambda: _locale.bindtextdomain(liar(str), None),  # type: ignore[arg-type]
        "_locale.nl_langinfo": lambda: _locale.nl_langinfo(liar(int)),  # type: ignore[arg-type]
        # _typing and templatelib
        "typing.TypeVar, the name": lambda: typing.TypeVar(liar(str)),  # type: ignore[misc]
        "typing.ParamSpec, the name": lambda: typing.ParamSpec(liar(str)),  # type: ignore[misc]
        "typing.TypeVarTuple, the name": lambda: typing.TypeVarTuple(liar(str)),  # type: ignore[misc]
        "typing.TypeAliasType, the name": lambda: typing.TypeAliasType(liar(str), int),  # type: ignore[misc]
        "typing.TypeAliasType, the parameters": lambda: typing.TypeAliasType("A", int, type_params=liar(tuple)),  # type: ignore[misc]
        "typing.TypeAliasType, the qualified name": lambda: typing.TypeAliasType("A", int, qualname=liar(str)),  # type: ignore[call-arg]
        "typing.TypeVar.evaluate_bound, the format": lambda: typing.TypeVar("T", bound=int).evaluate_bound(liar(int)),  # type: ignore[misc]
        "Template, what says str": lambda: string.templatelib.Template(liar(str)),  # type: ignore[arg-type]
        "Template, a str then what says str": lambda: string.templatelib.Template("a", liar(str)),  # type: ignore[arg-type]
        "Interpolation, the expression": lambda: string.templatelib.Interpolation(1, liar(str)),  # type: ignore[arg-type]
        "Interpolation, the conversion": lambda: string.templatelib.Interpolation(1, "x", liar(str)),  # type: ignore[arg-type]
        "Interpolation, the format": lambda: string.templatelib.Interpolation(1, "x", None, liar(str)),  # type: ignore[arg-type]
        # _warnings
        "warnings.warn, a message that says Warning": lambda: warnings.warn(liar(DeprecationWarning)),  # type: ignore[call-overload]
        "warnings.warn, a category that says type": lambda: warnings.warn("text", liar(type)),  # type: ignore[call-overload]
        "warnings.warn, the stack level": lambda: warnings.warn("text", UserWarning, liar(int)),  # type: ignore[call-overload]
        "warnings.warn, prefixes that say tuple": lambda: warnings.warn("text", UserWarning, 1, skip_file_prefixes=liar(tuple)),  # type: ignore[call-overload]
        "warnings.warn, a prefix that says str": lambda: warnings.warn("text", UserWarning, 1, skip_file_prefixes=(liar(str),)),  # type: ignore[arg-type]
        "warnings.warn_explicit, a message that says Warning": lambda: warnings.warn_explicit(liar(UserWarning), UserWarning, "file.py", 1),  # type: ignore[call-overload]
        "warnings.warn_explicit, the file name": lambda: warnings.warn_explicit("text", UserWarning, liar(str), 1),  # type: ignore[call-overload]
        "warnings.warn_explicit, the line": lambda: warnings.warn_explicit("text", UserWarning, "file.py", liar(int)),  # type: ignore[call-overload]
        "warnings.warn_explicit, the module": lambda: warnings.warn_explicit("text", UserWarning, "file.py", 1, liar(str)),  # type: ignore[call-overload]
        "warnings.warn_explicit, a registry that says dict": lambda: warnings.warn_explicit("text", UserWarning, "file.py", 1, "m", liar(dict)),  # type: ignore[call-overload]
        "warnings.warn_explicit, globals that say dict": lambda: warnings.warn_explicit("text", UserWarning, "file.py", 1, "m", {}, liar(dict)),  # type: ignore[call-overload]
        "warnings: a filter that says tuple": lambda: with_filters(liar(tuple)),
        "warnings: a filter's action that says str": lambda: with_filters((liar(str), None, Warning, None, 0)),
        "warnings: a filter's line that says int": lambda: with_filters(("ignore", None, Warning, None, liar(int))),
        "warnings: a filter's category that says type": lambda: with_filters(("ignore", None, liar(type), None, 0)),
        "warnings: filters that say list": lambda: with_attribute("filters", liar(list)),
        "warnings: a default action that says str": lambda: with_attribute("defaultaction", liar(str)),
        "warnings: a once registry that says dict": lambda: with_attribute("onceregistry", liar(dict)),
        # builtins
        "print, the separator": lambda: print(1, 2, sep=liar(str)),  # type: ignore[call-overload]
        "print, the end": lambda: print(1, end=liar(str)),  # type: ignore[call-overload]
        "input, a line that says str": lambda: from_stdin(liar(str)),
        "input, a line that says bytes": lambda: from_stdin(liar(bytes)),
        "property.__init__ of what says property": lambda: property.__init__(liar(property)),  # type: ignore[arg-type]
        "staticmethod.__repr__ of what says staticmethod": lambda: staticmethod.__repr__(liar(staticmethod)),  # type: ignore[arg-type]
        "the repr of a keys view, of what says so": lambda: type({}.keys()).__repr__(liar(type({}.keys()))),  # type: ignore[arg-type]
        # grp and pwd
        "grp.getgrgid, what says int": lambda: grp.getgrgid(liar(int)),  # type: ignore[arg-type]
        "grp.getgrgid, what says float": lambda: grp.getgrgid(liar(float)),  # type: ignore[arg-type]
        "grp.getgrnam": lambda: grp.getgrnam(liar(str)),  # type: ignore[arg-type]
        "pwd.getpwuid, what says int": lambda: pwd.getpwuid(liar(int)),  # type: ignore[arg-type]
        "pwd.getpwuid, what says float": lambda: pwd.getpwuid(liar(float)),  # type: ignore[arg-type]
        "pwd.getpwnam": lambda: pwd.getpwnam(liar(str)),  # type: ignore[arg-type]
        # the class pattern of a match statement is a real isinstance, and stays one
        "match: a class pattern (isinstance: asked)": lambda: matched(liar(int)),
    }


def raw_reading(chunk: object) -> object:
    class Buffer(io.BufferedIOBase):
        def readable(self) -> bool:
            return True

        def read(self, n: int = -1) -> object:  # type: ignore[override]
            return chunk

        def read1(self, n: int = -1) -> object:  # type: ignore[override]
            return chunk
    return Buffer()


def matched(value: object) -> str:
    match value:
        case int():
            return "an int"
        case _:
            return "no int"


def run(name: str) -> None:
    try:
        outcome = re.sub(r" at 0x[0-9a-f]+", "", repr(rows()[name]()))
    except Exception as exc:                     # which exception, by its class
        outcome = type(exc).__name__
    print(name, "|", outcome, "| __class__ was read:", len(asked), file=sys.__stdout__)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        for label in rows():
            print(label)
'''


# rows whose function stops by name; the row then holds only that it is one that stops
STOPS = {
    "codecs.escape_decode": "bella: not implemented: _codecs.escape_decode",
    "codecs.charmap_build": "bella: not implemented: _codecs.charmap_build",
    "bytes.decode, a decoder that gives what says str": "bella: not implemented: decoding with a codec the program registered",
    "bytes.decode, a decoder that gives what says tuple": "bella: not implemented: decoding with a codec the program registered",
    "TextIOWrapper.reconfigure, the encoding": "bella: not implemented: TextIOWrapper.reconfigure",
}
# the rows that stand for a real PyObject_IsInstance: there CPython reads __class__ too
ASKED = {"deque + what says deque (PyObject_IsInstance: asked)", "match: a class pattern (isinstance: asked)"}

# found with the sweep: what a buffered writer makes of a raw write() whose result is no number
RAW_RESULTS = r'''
import io
class Index:
    def __init__(self, n): self.n = n
    def __index__(self):
        if isinstance(self.n, BaseException): raise self.n
        return self.n
def writer(n):
    class Raw(io.RawIOBase):
        calls = 0
        def writable(self): return True
        def write(self, b):
            self.calls += 1
            return n if self.calls == 1 else len(b)
    return io.BufferedWriter(Raw())
def reader(n):
    class Raw(io.RawIOBase):
        def readable(self): return True
        def readinto(self, b): return n
    return io.BufferedReader(Raw())
ROWS = (("a str", "1"), ("a float", 1.0), ("an index of 1", Index(1)), ("an index that raises", Index(ValueError("index"))),
        ("an index that stops", Index(KeyboardInterrupt())), ("2**70", 2**70), ("-2**70", -2**70), ("-1", -1), ("5", 5), ("True", True))
for label, n in ROWS:
    w = writer(n)
    w.write(b"a")
    try: print("write:", label, "->", w.flush())
    except BaseException as e: print("write:", label, "->", type(e).__name__, type(e.__context__).__name__, type(e.__cause__).__name__)
    w.close()
    if label in ("an index of 1", "5", "True"): continue     # a count of bytes the raw stream never wrote: the buffer's old bytes
    try: print("read:", label, "->", reader(n).read(1))
    except BaseException as e: print("read:", label, "->", type(e).__name__, type(e.__context__).__name__, type(e.__cause__).__name__)
'''


def test_a_type_test_does_not_ask_the_objects_class() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-types-"))
    try:
        program = folder / "prog.py"
        program.write_text(SWEEP, encoding="utf-8")
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        listed = subprocess.run([sys.executable, str(program)], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert listed.returncode == 0, listed.stderr
        labels = listed.stdout.splitlines()
        assert len(labels) == 191, len(labels)
        binary = str(build(program, "prog.py", notes=False))
        wrong: list[str] = []
        stopped: list[str] = []
        for label in labels:                     # a process for each row: one that stops takes no other with it
            sides = [subprocess.run([*command, label], capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
                     for command in ([sys.executable, str(program)], [binary])]
            reference, compiled = sides
            read = "1" if label in ASKED else "0"
            if label.startswith("json.dumps, ") or label == "json.loads, what says str":
                read = reference.stdout.rstrip("\n").rsplit(" ", 1)[-1]   # json's own Python asks isinstance before the C is reached
            assert reference.returncode == 0 and reference.stdout.endswith("| __class__ was read: " + read + "\n"), (label, reference)
            if compiled.returncode == 70 and compiled.stdout == "" and STOPS.get(label, "\0") in compiled.stderr:
                stopped.append(label)
            elif (compiled.returncode, compiled.stdout) != (reference.returncode, reference.stdout):
                wrong.append(f"{label}: compiled {compiled.stdout.strip()!r} (status {compiled.returncode}, {compiled.stderr.strip()[-200:]!r}), "
                             f"CPython {reference.stdout.strip()!r}")
        assert not wrong, "\n".join(wrong)
        assert stopped == list(STOPS), stopped
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_no_prelude_asks_isinstance_where_the_c_tests_the_type() -> None:
    """The three calls that stay are the ones that stand for PyObject_IsInstance, or CPython's stand-in; the two files of
    importlib's own Python keep theirs."""
    prelude = Path(__file__).resolve().parents[2] / "runtime" / "prelude"
    kept = {"_collections.py": 1, "match.py": 1, "iterating.py": 1}
    found = {p.name: n for p in sorted(prelude.glob("*.py")) if p.name not in ("bootstrap.py", "bootstrap_external.py")
             if (n := sum(1 for line in p.read_text(encoding="utf-8").splitlines() if "isinstance(" in line.split("#")[0] and '"""' not in line))}
    assert found == kept, found


def test_a_raw_result_that_is_no_number() -> None:
    same(RAW_RESULTS)


if __name__ == "__main__":
    test_no_prelude_asks_isinstance_where_the_c_tests_the_type()
    test_a_type_test_does_not_ask_the_objects_class()
    test_a_raw_result_that_is_no_number()
    print("ok")
