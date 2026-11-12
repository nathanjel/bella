"""pwd, grp, _locale, zlib, _ast, _typing, _json and the t-string types, compiled, against CPython: the messages the cases do not compare, the conversions'
edges, and what stops by name. The locale facts are the C locale's and C.UTF-8's; what reads the environment's locale is the same environment on
both sides."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from conformance.harness import mask_stderr
from pipeline.build import build
from pipeline.tests.test_compiled_imports import same as same_streams
from pipeline.tests.test_review_2026_11_03 import same

SYSTEM_MODULES = r"""
import pwd, grp, _locale, locale, zlib
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: pwd.getpwuid(-2)), m(lambda: pwd.getpwuid("a")), m(lambda: pwd.getpwuid(2**70)), m(lambda: pwd.getpwuid(1.5)), m(lambda: pwd.getpwnam("no such user, surely")), m(lambda: pwd.getpwnam(1)), m(lambda: pwd.getpwnam("a\0b")), m(lambda: pwd.getpwnam()), m(lambda: pwd.getpwuid(0, 1)), m(lambda: pwd.getpwnam(name="root")), m(lambda: pwd.getpwall(1)), m(lambda: pwd.struct_passwd(range(2))), m(lambda: pwd.getpwuid(2**32)), m(lambda: pwd.getpwuid(-1)), m(lambda: pwd.getpwuid(True).pw_uid), m(lambda: pwd.getpwuid(None)))
print(m(lambda: grp.getgrgid(-2)), m(lambda: grp.getgrgid("a")), m(lambda: grp.getgrnam("no such group, surely")), m(lambda: grp.getgrnam(1)), m(lambda: grp.getgrgid(1.5)), m(lambda: grp.getgrgid()), m(lambda: grp.getgrgid(0, 1)), m(lambda: grp.getgrgid(x=1)), m(lambda: grp.getgrgid(2**70)), m(lambda: grp.getgrgid(2**64)), m(lambda: grp.getgrgid(2**32)), m(lambda: grp.getgrgid(-1)), m(lambda: grp.getgrnam("a\0b")), m(lambda: grp.getgrnam()), m(lambda: grp.getgrall(1)), m(lambda: grp.struct_group((1, 2, 3))))
print(pwd.getpwuid(0), grp.getgrgid(0), repr(pwd.struct_passwd(range(7))), pwd.struct_passwd.__doc__[:30], grp.struct_group.__doc__[:20], pwd.__doc__[:40], grp.__doc__[:40], pwd.getpwuid.__doc__[:30], grp.getgrgid.__doc__[:30], pwd.getpwuid.__module__, pwd.getpwuid.__qualname__, type(pwd.getpwuid).__name__, pwd.struct_passwd.__module__, pwd.struct_passwd.__mro__, m(lambda: pwd.struct_passwd.__init__), pwd.getpwuid(0)._asdict() if hasattr(pwd.getpwuid(0), "_asdict") else None)
print(m(lambda: _locale.setlocale(_locale.LC_ALL, "surely_no_such_locale.XYZ")), m(lambda: _locale.setlocale(99)), m(lambda: _locale.setlocale("a")), m(lambda: _locale.setlocale(6, 1)), m(lambda: _locale.setlocale()), m(lambda: _locale.setlocale(6, "a\0b")), m(lambda: _locale.setlocale(category=6, locale="C")), m(lambda: _locale.localeconv(1)), m(lambda: _locale.strcoll("a", 1)), m(lambda: _locale.strcoll("a")), m(lambda: _locale.strxfrm(1)), m(lambda: _locale.strxfrm("a\0b")), m(lambda: _locale.nl_langinfo(999999)), m(lambda: _locale.nl_langinfo("a")), m(lambda: _locale.nl_langinfo(-1)), m(lambda: _locale.getencoding(1)), m(lambda: locale.setlocale(locale.LC_ALL, "xx")), m(lambda: _locale.strcoll("a\0b", "a")), m(lambda: _locale.nl_langinfo()), m(lambda: _locale.setlocale(-1, "C")), m(lambda: _locale.setlocale(2**40, "C")))
print(m(lambda: _locale.gettext(1)), m(lambda: _locale.textdomain(1)), m(lambda: _locale.bindtextdomain(1, None)), m(lambda: _locale.bind_textdomain_codeset(1, None)), m(lambda: _locale.dgettext(1, "m")), m(lambda: _locale.dcgettext("d", "m", "x")), m(lambda: _locale.gettext("a\0b")), m(lambda: _locale.bindtextdomain("d", 1)), m(lambda: _locale.dgettext("d")), m(lambda: _locale.gettext()), m(lambda: _locale.textdomain()), m(lambda: _locale.bindtextdomain("d")), m(lambda: _locale.textdomain("a\0b")), _locale.__doc__, _locale.setlocale.__doc__[:40], _locale.Error.__qualname__, m(lambda: _locale.Error("x").args), locale.Error.__module__)
print(m(lambda: _locale.setlocale(_locale.LC_ALL, "C")), _locale.setlocale(0), m(lambda: _locale.setlocale(6, None)), m(lambda: _locale.setlocale(6, "")), _locale.setlocale(6, "C"), m(lambda: _locale.localeconv()["grouping"]), m(lambda: _locale.localeconv()["thousands_sep"]), m(lambda: _locale.strcoll("", "")), m(lambda: _locale.strxfrm("a")), m(lambda: _locale.nl_langinfo(_locale.ERA)), m(lambda: _locale.nl_langinfo(_locale.CRNCYSTR)), m(lambda: _locale.nl_langinfo(_locale.NOEXPR)), m(lambda: _locale.nl_langinfo(0)), m(lambda: _locale.nl_langinfo(2**40)), sorted(n for n in dir(_locale) if not n.startswith("_")))
print(zlib.error, zlib.error.__module__, zlib.error.__mro__, zlib.MAX_WBITS, zlib.DEFLATED, zlib.DEF_MEM_LEVEL, zlib.DEF_BUF_SIZE, zlib.Z_BEST_COMPRESSION, zlib.Z_DEFAULT_COMPRESSION, zlib.Z_FINISH, zlib.Z_NO_FLUSH, zlib.Z_SYNC_FLUSH, zlib.Z_FULL_FLUSH, zlib.Z_BLOCK, zlib.Z_TREES, zlib.Z_FILTERED, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED, zlib.Z_DEFAULT_STRATEGY, zlib.Z_NO_COMPRESSION, zlib.Z_BEST_SPEED, zlib.__doc__[:40], m(lambda: zlib.nope), zlib.compress.__module__, zlib.compress.__qualname__, type(zlib.compress).__name__, m(lambda: zlib.error("x").args), sorted(n for n in dir(zlib) if not n.startswith("_") and n[0].islower()))
"""

TEMPLATE_TYPES = r"""
from string.templatelib import Template, Interpolation
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: Template(1)), m(lambda: Template(x=1)), m(lambda: Interpolation()), m(lambda: Interpolation(1, 2)), m(lambda: Interpolation(1, "e", "x")), m(lambda: Interpolation(1, "e", "rr")), m(lambda: Interpolation(1, "e", None, 3)), m(lambda: Interpolation(1, "e", 5)), m(lambda: Interpolation(1, 2, 3, 4, 5)), m(lambda: Interpolation(value=1, expression="e", conversion="r", format_spec="f")), m(lambda: Interpolation(1, format_spec="s")), m(lambda: Interpolation(1, bad=2)))
t = Template("a", Interpolation(1, "x"), Interpolation(2, "y"), "b", "c")
print(repr(t), t.strings, t.interpolations, t.values, list(t), m(lambda: t + "s"), m(lambda: "s" + t), m(lambda: t + t), m(lambda: Template() + Template()), list(Template()), list(Template(Interpolation(1, "x"))), t.__reduce__()[1], Interpolation(1, "x").__reduce__(), m(lambda: Template.__new__(Template, kw=1)), m(lambda: Template.__new__(int)), m(lambda: Interpolation.__new__(int, 1)), Template[int], m(lambda: iter(t).__next__()), type(iter(t)), m(lambda: type(iter(t))()), m(lambda: Template.__iter__(1)), m(lambda: Template.__add__(t, 1)))
print(m(lambda: type("S", (Template,), {})), m(lambda: Interpolation(1, "e", "s") == Interpolation(1, "e", "s")), hash(t) is not None, m(lambda: t == t), bool(Template()), m(lambda: len(t)), m(lambda: t[0]), Interpolation(1, "x").conversion, Interpolation(1, "x").format_spec, Interpolation(1, "x").expression, m(lambda: Interpolation(1, "x").value), repr(Interpolation(None, "x", "a", "spec")), t"a{1!r:>3}b".interpolations, t"{1}{2}".strings, t"".strings, t"a" + t"b", m(lambda: t"a" + "b"), type(t"") is Template, Template.__module__, Template.__qualname__, repr(Template), Template.__flags__ & (1 << 10), Template.__mro__, Interpolation.__match_args__, Template.__doc__, Interpolation.__doc__, type(iter(t"")).__doc__, type(vars(Template)["strings"]).__name__, type(vars(Template)["values"]).__name__, type(vars(Template)["__new__"]).__name__, type(vars(Template)["__add__"]).__name__)
x = 5
tt = t"v={x!r:>4} and {x + 1}"
print(tt, tt.values, [i.expression for i in tt.interpolations], [(i.conversion, i.format_spec) for i in tt.interpolations], list(tt), m(lambda: setattr(t, "strings", 1)), m(lambda: delattr(t, "strings")), m(lambda: Template.strings.__set__(t, 1)), m(lambda: Interpolation.value.__get__(1)), m(lambda: t.nope), m(lambda: Interpolation(1).nope))
import string.templatelib
print(string.templatelib.convert(1, "r"), string.templatelib.convert("a", None), m(lambda: string.templatelib.convert(1, "x")), string.templatelib._template_unpickle(("a", "b"), (Interpolation(1, "x"),)), m(lambda: string.templatelib._template_unpickle(1)))
"""

TYPING_OBJECTS = r"""
import typing, annotationlib
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
def f[T: int, *Ts, **P = [int], U: (str, bytes) = str](x: T) -> T: return x
T, Ts, P, U = f.__type_params__
print(type(T.evaluate_bound).__name__, T.evaluate_bound.__qualname__, T.evaluate_bound.__name__, m(lambda: T.evaluate_bound()), m(lambda: T.evaluate_bound(1)), m(lambda: T.evaluate_bound(2)), m(lambda: T.evaluate_bound(3)), m(lambda: T.evaluate_bound(4)), T.evaluate_bound.__module__, T.evaluate_bound.__defaults__, T.evaluate_bound.__kwdefaults__)
print(T.__bound__, T.evaluate_constraints, U.evaluate_constraints(1), U.__constraints__, U.evaluate_default(1), U.__default__, P.__default__, P.evaluate_default.__name__, Ts.evaluate_default, Ts.__default__, T.has_default(), U.has_default(), repr(T), repr(Ts), repr(P), T.__module__, T.__infer_variance__, T.__covariant__, m(lambda: vars(T)), m(lambda: T.__dict__), T.__name__, U.evaluate_constraints.__qualname__)
type A[X] = list[X]
type B = int | str
print(A, A.__name__, A.__qualname__, A.__module__, A.__type_params__, A.__parameters__, A.__value__, A.evaluate_value.__name__, A.evaluate_value.__qualname__, m(lambda: A.evaluate_value(1)), m(lambda: A.evaluate_value(4)), A[int], m(lambda: B[int]), B | None, m(lambda: B()), repr(B), B.__value__, type(A), list(A), m(lambda: A.__module__ == "__main__"), A.__reduce__(), A.__module__)
class C[T2]: pass
print(C.__type_params__, C.__orig_bases__, C.__mro__, C.__parameters__, C[int], m(lambda: C[int, str]), typing.Generic, typing.Generic.__module__, type(typing.Generic).__name__, typing.Generic.__mro__, type(typing.Generic()).__name__, m(lambda: typing.Generic[int]), typing.Generic[C.__type_params__[0]], type(typing.Generic.__class_getitem__).__name__)
E = typing.TypeVar("E", bound=int, default=str)
print(E.evaluate_bound, E.evaluate_bound(1), E.evaluate_bound(4), E.evaluate_default, type(E.evaluate_bound), type(E.evaluate_bound).__module__, m(lambda: type(E.evaluate_bound)()), E.__module__, repr(E), typing.TypeVar("F", covariant=True), typing.TypeVar("G", contravariant=True), typing.TypeVar("H", infer_variance=True), m(lambda: typing.TypeVar("I", covariant=True, contravariant=True)), m(lambda: typing.TypeVar("I", covariant=True, infer_variance=True)), m(lambda: typing.TypeVar("I", int)), m(lambda: typing.TypeVar("I", int, str, bound=int)), m(lambda: typing.TypeVar(1)), m(lambda: typing.TypeVar("J", bound=1)), typing.TypeVar("K", bound=None).__bound__, m(lambda: typing.TypeVar()), m(lambda: typing.TypeVar("L", nope=1)), E | None, typing.NoDefault, type(typing.NoDefault), m(lambda: type(typing.NoDefault)()), m(lambda: type(typing.NoDefault)(1)), typing.NoDefault.__reduce__(), m(lambda: type("S", (E,), {})), E.__reduce__(), type(E.__mro_entries__).__name__)
import _typing
print(_typing.Union is typing.Union, _typing._idfunc, _typing._idfunc(5), m(lambda: _typing._idfunc()), _typing.__doc__, sorted(n for n in dir(_typing) if not n.startswith("__")), typing.TypeAliasType("N", int), typing.TypeAliasType("N", int, type_params=(T,)).__type_params__, m(lambda: typing.TypeAliasType("N", int, type_params=[T])), m(lambda: typing.TypeAliasType("N", int, type_params=(U, T))), typing.TypeAliasType("N", int, qualname="Q.N").__qualname__, m(lambda: typing.TypeAliasType("N", int, qualname=1)), typing.TypeAliasType("N", int).__module__, typing.TypeAliasType("N", int).evaluate_value)
"""

EXEC_LOCALS_AND_OFFSETS = r"""
g = {"base": 10}
l = {}
exec("y = base + 1\ndef f():\n    return base, y if 'y' in globals() else 'no y'\nz = f()", g, l)
print(sorted(l), l["y"], l["z"], sorted(k for k in g if not k.startswith("__")), l["f"].__module__, l["f"].__globals__ is g, "y" in g)
exec("w = y * 2", g, l)
print(l["w"])
try:
    exec("q = missing", g, l)
except NameError as e:
    print("NameError", e)
d = dict(g)
exec("def h(): return sorted(k for k in globals() if not k.startswith('__'))\nk = h()", d, d)
print(d["k"], d["h"]())
import dataclasses
@dataclasses.dataclass
class S:
    a: int
    b: str = "x"
    def twice(self):
        return self.a * 2
s = S(2)
print(s, s.twice(), S.__dictoffset__, S.__weakrefoffset__, hasattr(s, "__dict__"), dataclasses.fields(S)[1].default, S.__init__.__module__, S.__init__.__qualname__)
class A: pass
class B(A): __slots__ = ("y",)
class C(int): pass
print(A.__dictoffset__, A.__weakrefoffset__, B.__dictoffset__, B.__weakrefoffset__, C.__dictoffset__, C.__weakrefoffset__, int.__dictoffset__, Exception.__dictoffset__, type.__weakrefoffset__)
m = sentinel("M")
print(hash(m) == object.__hash__(m), m == m, m != m, {m: 1}[m], m == sentinel("M"))
"""

JSON = r"""
import json, _json
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e) + ("  notes=" + repr(e.__notes__) if getattr(e, "__notes__", None) else "")
class Foo: pass
class S(str): pass
class I(int):
    def __repr__(self): return "I!"
class F(float):
    def __repr__(self): return "F!"
class D(dict): pass
print(m(lambda: _json.scanstring(1, 0)), m(lambda: _json.scanstring("abc")), m(lambda: _json.scanstring("abc", "x")), m(lambda: _json.scanstring("abc", 5)), m(lambda: _json.scanstring("abc", -1)), m(lambda: _json.scanstring('"abc', 1)), _json.scanstring('"a\\u00e9\\ud83d\\ude00b"x', 1), m(lambda: _json.scanstring('"a\\ud83dq"', 1)), m(lambda: _json.scanstring('"a\\x"', 1)), m(lambda: _json.scanstring('"a\\u12"', 1)), m(lambda: _json.scanstring('"a\\u12zz"', 1)), m(lambda: _json.scanstring('"a\nb"', 1)), _json.scanstring('"a\nb"', 1, False), m(lambda: _json.scanstring("abc", 0, 1, 2)), m(lambda: _json.scanstring(pystr="abc", end=0)))
print(_json.encode_basestring_ascii('a"\\/\b\f\n\r\t\x01\x7f\x80é😀'), _json.encode_basestring('a"\\/\b\f\n\r\t\x01\x7f\x80é😀'), m(lambda: _json.encode_basestring_ascii(1)), m(lambda: _json.encode_basestring(b"a")), m(lambda: _json.encode_basestring_ascii()), m(lambda: _json.encode_basestring("a", "b")), _json.encode_basestring_ascii(S("x")), type(_json.encode_basestring_ascii(S("x"))).__name__, _json.encode_basestring(S("é")), type(_json.encode_basestring(S("é"))).__name__, _json.encode_basestring_ascii(""), _json.encode_basestring(""))
print(m(lambda: _json.make_scanner()), m(lambda: _json.make_scanner(1)), type(_json.make_scanner(context=json.JSONDecoder())).__name__, m(lambda: _json.make_scanner(json.JSONDecoder(), 2)), m(lambda: _json.make_encoder()), m(lambda: _json.make_encoder(1, 2, 3, 4, "a", "b", 1, 1, 1)), m(lambda: _json.make_encoder(None, 2, 3, 4, 5, "b", 1, 1, 1)), type(_json.make_encoder(None, 2, 3, 4, "a", "b", 1, 1, 1)).__name__, m(lambda: _json.make_encoder(None, 2, 3, 4, "a", "b", 1, 1)), type(_json.make_encoder(markers=None, default=2, encoder=3, indent=4, key_separator="a", item_separator="b", sort_keys=1, skipkeys=1, allow_nan=1)).__name__)
s = json.JSONDecoder().scan_once
print(m(lambda: s()), m(lambda: s(1, 0)), m(lambda: s("1", "x")), m(lambda: s("1", -1)), m(lambda: s("1", 5)), m(lambda: s("", 0)), s("12 ", 0), s(" 12", 1), m(lambda: s(" 12", 0)), s('"a"', 0), s("[1, 2]", 0), s("{}", 0), s('{"a": {"b": [1.5, -2e3, 1E+2, 0, -0, 0.0, 10]}}', 0), m(lambda: s("[1,]", 0)), m(lambda: s('{"a":1,}', 0)), m(lambda: s("[1 2]", 0)), m(lambda: s('{"a" 1}', 0)), m(lambda: s('{a:1}', 0)), m(lambda: s("[", 0)), m(lambda: s("{", 0)), m(lambda: s("-", 0)), m(lambda: s("-x", 0)), s("01", 0), s("1.", 0), s("1e", 0), s("1e5x", 0), s("1.5e-3", 0), s("NaN", 0), s("-Infinity", 0), s("Infinity", 0), m(lambda: s("nul", 0)), s("truex", 0), s(string="false", idx=0), m(lambda: s("1" * 5000, 0)))
d = json.JSONDecoder(parse_float=lambda x: ("f", x), parse_int=lambda x: ("i", x), parse_constant=lambda x: ("c", x), object_hook=lambda o: ("o", sorted(o)), object_pairs_hook=None, strict=False)
print(d.scan_once('[1, 2.5, NaN, {"k": "v\n"}, -1e1]', 0), json.loads('{"a": 1, "a": 2}'), type(json.loads("1")), m(lambda: json.loads("")), m(lambda: json.loads("[1] x")), m(lambda: json.loads('{"a": }')), m(lambda: json.loads("﻿[]")), json.loads(b'[1]'), json.loads(bytearray(b'[1]')), m(lambda: json.loads(1)), repr(json.loads('"\\ud800"')), repr(json.loads('"\\ud800\\u0041"')), json.loads(' \t\n\r[1]\n'), json.JSONDecoder(object_pairs_hook=lambda p: p).decode('{"b": 1, "a": 2}'))
print(json.dumps({"a": [1, 2.5, True, None, "x"], "b": {"c": (1,)}}), json.dumps([1.0, 1e100, 1e16, 1e-7, 0.1, -0.0, 1e22]), json.dumps("é😀"), json.dumps("é😀", ensure_ascii=False), json.dumps({1: 2, 2.5: 3, True: 4, None: 5, False: 6, "s": 7}), m(lambda: json.dumps({(1, 2): 3})), json.dumps({(1, 2): 3}, skipkeys=True), json.dumps({"b": 1, "a": 2}, sort_keys=True), m(lambda: json.dumps({"b": 1, 2: 2}, sort_keys=True)), m(lambda: json.dumps(float("nan"), allow_nan=False)), json.dumps([float("nan"), float("inf"), -float("inf")]), m(lambda: json.dumps(Foo())), m(lambda: json.dumps([Foo()])), m(lambda: json.dumps({"k": Foo()})), m(lambda: json.dumps({"k": [1, {"z": Foo()}]})), json.dumps(Foo(), default=lambda o: {"foo": 1}), json.dumps(S("x")), json.dumps([I(5), F(2.5)]), json.dumps({I(5): F(2.5)}), json.dumps(D(a=1)), json.dumps({}), json.dumps([]), json.dumps(()), json.dumps({"a": {}, "b": []}, indent=2), json.dumps([1, [2, [3]]], indent="\t"), json.dumps({"a": 1}, indent=0), json.dumps([1, 2], separators=(",", ":")), json.dumps({"a": 1, "b": 2}, indent=1, separators=(" ;", " = ")), json.dumps(123456789012345678901234567890), json.dumps(-0.0), json.dumps(1e300 * 1e300), json.dumps(True), json.dumps(None))
l = []; l.append(l)
dd = {}; dd["x"] = dd
print(m(lambda: json.dumps(l)), m(lambda: json.dumps(dd)), m(lambda: json.dumps({"a": [dd]})), m(lambda: json.JSONEncoder(check_circular=False).encode([1])), m(lambda: json.dumps([Foo()], default=lambda o: o)), json.JSONEncoder().encode("s"), list(json.JSONEncoder().iterencode([1, "a", {"b": 2.5}])), list(json.JSONEncoder(indent=1).iterencode({"a": [1]})), json.JSONEncoder(default=lambda o: list(o)).encode({1, 2} if False else (1, 2)), m(lambda: json.dumps([1], indent=1.5)), json.dumps({"k": "v"}, indent=None), m(lambda: json.dumps("x", cls=None)))
enc = _json.make_encoder(None, lambda o: "D", lambda s: "E", None, ": ", ", ", False, False, True)
print(enc([1, "a", {"b": None}, Foo()], 0), m(lambda: enc("x")), m(lambda: enc("x", "y")), m(lambda: enc(obj="x", _current_indent_level=0)), m(lambda: _json.make_encoder(None, lambda o: "D", lambda s: 5, None, ": ", ", ", False, False, True)(["a"], 0)), m(lambda: _json.make_encoder(None, lambda o: "D", lambda s: 5, None, ": ", ", ", False, False, True)([1], 0)), enc.markers, enc.indent, enc.key_separator, enc.item_separator, enc.sort_keys, enc.skipkeys, type(enc.default).__name__, m(lambda: setattr(enc, "indent", 1)), m(lambda: enc.allow_nan))
sc = _json.make_scanner(json.JSONDecoder()); print(sc.strict, sc.object_hook, sc.object_pairs_hook, sc.array_hook, sc.parse_float, sc.parse_int, type(sc.parse_constant).__name__, m(lambda: setattr(sc, "strict", 0)), type(sc).__name__, type(sc).__module__, type(enc).__module__, repr(type(sc)), m(lambda: type(sc)()), _json.__doc__, sorted(n for n in dir(_json) if not n.startswith("__")))
class M(dict):
    def items(self): return [("z", 1), ("y", 2)]
class M2(dict):
    def items(self): return [("z",)]
class M3(dict):
    def items(self): return [(1, 2), ("a", 3)]
print(json.dumps(M(a=1)), m(lambda: json.dumps(M2(a=1))), json.dumps(M3(a=1)), m(lambda: json.dumps(M3(a=1), sort_keys=True)), json.dumps({"b": 1, "a": 2}, sort_keys=True, indent=1), json.dumps({"a": 1}, indent=3, separators=(",", ":")))
"""

AST_NODES = r"""
import _ast, ast
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(len([n for n in dir(_ast) if not n.startswith("__")]), _ast.AST.__module__, sorted(k for k in vars(_ast.AST) if not k.startswith("__")), _ast.AST._fields, _ast.BinOp._fields, _ast.BinOp.__match_args__, _ast.BinOp._field_types, _ast.BinOp.__doc__, _ast.BinOp.__mro__)
c = ast.Constant(1); print(repr(c), vars(c), c.value, c.kind, m(lambda: c.lineno), m(lambda: ast.Constant()), m(lambda: ast.Constant(1, 2, 3)), m(lambda: ast.Constant(1, value=2)), m(lambda: ast.Constant(1, foo=2)), ast.Constant(value=1, kind="u").kind, ast.Constant(1, lineno=3).lineno, m(lambda: ast.BinOp()))
print(m(lambda: ast.Name("x")), vars(ast.Name("x")), m(lambda: ast.Name()), vars(ast.Module()), repr(ast.Module()), m(lambda: ast.FunctionDef("f")), m(lambda: vars(ast.FunctionDef("f", ast.arguments()))), repr(ast.Load()), ast.Load() is ast.Load(), m(lambda: ast.AST(1)), m(lambda: ast.BinOp(1, 2, 3, 4)), m(lambda: ast.stmt.__init__))
b = ast.BinOp(ast.Name("a", ast.Load()), ast.Add(), ast.Constant(1))
print(c.__reduce__(), m(lambda: ast.Constant(1).__replace__(value=2)), m(lambda: ast.Constant(1).__replace__(nope=2)), m(lambda: ast.Constant(1).__replace__()), m(lambda: ast.Constant(1).__replace__(lineno=5)), _ast.PyCF_ONLY_AST, _ast.PyCF_TYPE_COMMENTS, _ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, _ast.PyCF_OPTIMIZED_AST, type(_ast.AST.__dict__.get("_fields")).__name__, _ast.stmt.__dict__.get("_attributes"), _ast.Constant._attributes, _ast.AST.__init__, _ast.AST.__reduce__, _ast.AST.__replace__, _ast.AST.__repr__)
print(repr(b), repr(ast.Expr(ast.Constant("s"))), repr(ast.Dict([None], [ast.Constant(2)])), repr(ast.arguments()), ast.arguments().args, repr(ast.Compare(ast.Constant(1), [ast.Lt()], [ast.Constant(2)])), repr(ast.Call(ast.Name("f"), [ast.Constant(i) for i in range(4)], [])), repr(ast.Module([ast.Expr(ast.Constant(1))], [])), vars(ast.Module([], [])))
class Sub(ast.expr):
    _fields = ("a", "b")
class Odd(ast.AST):
    _fields = ("x",)
print(repr(_ast.mod.__doc__[:40]), _ast.Load.__doc__, _ast.FunctionDef._field_types, _ast.expr_context.__mro__, sorted(set(dir(ast.Constant(1))) - set(dir(object))), ast.Constant.__name__, ast.Constant.__qualname__)

"""


def test_pwd_grp_locale_zlib() -> None:
    same(SYSTEM_MODULES)


def test_the_t_string_types() -> None:
    same(TEMPLATE_TYPES)


def test_ast_nodes() -> None:
    same(AST_NODES)


def test_exec_with_a_locals_mapping_offsets_and_sentinel() -> None:
    """A staged text run against a locals mapping of its own (dataclasses' methods), type.__dictoffset__ and __weakrefoffset__
    (dataclasses' slots=True reads them), and sentinel's hash and comparisons as its own slots."""
    same(EXEC_LOCALS_AND_OFFSETS)

BINASCII = r"""
import binascii, base64
def m(f):
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: binascii.a2b_base64(b"Zg==", b"x")), m(lambda: binascii.a2b_base64()), m(lambda: binascii.a2b_base64(b"", data=1)), m(lambda: binascii.a2b_base64(b"", paddd=1)),
      m(lambda: binascii.a2b_base64(b"", 1, 2, 3, 4, 5, 6)), m(lambda: binascii.a2b_base64(padded=1)), m(lambda: binascii.a2b_base64(b"", strict_mode=1, padded=1, alphabet=binascii.BASE64_ALPHABET, ignorechars=b"", canonical=1, x=2)))
print(m(lambda: binascii.crc32()), m(lambda: binascii.crc32(b"", 1, 2)), m(lambda: binascii.crc32(b"", crc=1)), m(lambda: binascii.hexlify(b"a", ":", 2, 3)), m(lambda: binascii.hexlify()), m(lambda: binascii.hexlify(b"a", data=b"b")),
      m(lambda: binascii.hexlify(data=b"a", bytes_per_sep=2, sep=":")), m(lambda: binascii.hexlify(b"a", sepp=":")), m(lambda: binascii.hexlify(b"ab", ":", bytes_per_sep=1.5)), m(lambda: binascii.hexlify(b"ab", [1])), m(lambda: binascii.unhexlify(b"00", b" ")))
print(m(lambda: binascii.b2a_base64(b"x", wrapcol=-5)), m(lambda: binascii.b2a_base64(b"x", wrapcol=2**64)), m(lambda: binascii.b2a_base64(b"x", wrapcol="3")), m(lambda: binascii.b2a_base64(b"x", alphabet=b"abc")), m(lambda: binascii.a2b_base64(b"Zg==", alphabet="A" * 64)),
      m(lambda: binascii.a2b_base64(b"Zg==", alphabet=bytearray(64))), m(lambda: binascii.a2b_base64("Zm9v\xe9")), m(lambda: binascii.a2b_base64(1)), m(lambda: binascii.b2a_base64("x")))
class I:
    def __index__(self):
        return 8
print(binascii.b2a_base64(bytes(range(12)), wrapcol=I()), binascii.crc32(b"a", I()), binascii.hexlify(b"abcd", ":", I()), m(lambda: binascii.hexlify(b"abcd", ":", 2**63)), m(lambda: binascii.b2a_base64(b"a", wrapcol=True, newline=0, padded=None)))
for text in (b"Zg==", b"Zg==Zg==", b"Zg=x=", b"=Zg==", b"Zm9v====", b"Z=g==", b"Zh==", b"Zg", b"Z", b"Zg=", b"Zm8=", b"Zm8", b"Zm8==", b"Zm9", b"Zm9=", b"Zm9v==", b"Zg==\n", b"\nZg==", b"Zg =="):
    print(text, m(lambda: binascii.a2b_base64(text)), m(lambda: binascii.a2b_base64(text, strict_mode=True)), m(lambda: binascii.a2b_base64(text, strict_mode=True, padded=False)), m(lambda: binascii.a2b_base64(text, canonical=True)),
          m(lambda: binascii.a2b_base64(text, ignorechars=b"\n =")), m(lambda: binascii.a2b_base64(text, ignorechars=b"\n")))
print(base64.b64encode(bytes(range(100)), wrapcol=20), base64.b64decode(b"  Zm9v\nYmFy  "), base64.urlsafe_b64decode("-_8-"), m(lambda: base64.b64decode(b"Zm9v", validate=True, padded=False)), base64.b16encode(b"\xb9\x01"), base64.b16decode(b"B901"), m(lambda: base64.b16decode(b"b901")), base64.b16decode(b"b901", casefold=True))
"""

STRUCT = r"""
import struct
def m(f):
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
class Sub(complex):
    @property
    def real(self):
        return 99.0
class C:
    def __complex__(self):
        return 1 + 1j
class F(float):
    def __float__(self):
        return 7.0
print(struct.pack("<D", Sub(1, 2)), struct.pack("<F", C()), struct.pack("<F", 2), struct.pack("<F", F(1.0)), struct.pack("<d", F(1.0)), struct.pack("<F", 1e40), m(lambda: struct.pack(">F", 1e40)), struct.pack("F", 1e40), struct.pack("=F", -1e40), struct.unpack("<F", b"\x01\x00\x80\x7f\x00\x00\x00\x00"), struct.unpack(">F", b"\x7f\x80\x00\x01\x00\x00\x00\x00"), struct.pack("F", -1e40), struct.pack("<F", C())[4:], m(lambda: struct.pack("<D", "x")))
print(struct.unpack("<e", struct.pack("<e", 0.1)), struct.unpack("<f", struct.pack("<f", 0.1)), struct.pack("<e", 2**-24), struct.pack("<e", 2**-25), struct.pack("<e", 2**-25 * 1.0000001), struct.pack("<e", 65519.99), m(lambda: struct.pack("<e", 65520.0)), m(lambda: struct.pack(">e", -1e5)), struct.pack("<e", 2047.5), struct.pack("<e", 2048.5), struct.pack("<e", 2049.5))
print(struct.pack("<f", 3.4028235e38), m(lambda: struct.pack("<f", 3.5e38)), struct.pack("<f", float("-nan")), struct.unpack("<f", b"\x00\x00\x80\xff"), struct.unpack(">e", b"\x7e\x00"), struct.unpack("<e", b"\x00\x80"), struct.pack(">d", -0.0), struct.unpack("<d", struct.pack("<d", 1e-320)))
s = struct.Struct("<2h")
print(s.pack(1, 2), s.unpack(b"\x01\x00\x02\x00"), list(s.iter_unpack(b"\x01\x00\x02\x00\x03\x00\x04\x00")), s.unpack_from(b"xx\x01\x00\x02\x00", 2), s.unpack_from(buffer=b"xx\x01\x00\x02\x00", offset=2), m(lambda: s.unpack_from(b"", buffer=b"")), m(lambda: s.unpack_from(b"", offset=0, x=1)), m(lambda: s.unpack_from(b"", offsett=0)))
print(m(lambda: struct.pack("<hh", 1, 2, 3)), m(lambda: struct.pack("<h", 1.0)), m(lambda: struct.pack("<h", True)), m(lambda: struct.pack("<h", 2**100)), m(lambda: struct.pack("P", 2**100)), m(lambda: struct.pack("<e", 2**100)), m(lambda: struct.pack("<f", 2**1000)), m(lambda: struct.pack("<d", 2**1024)), m(lambda: struct.pack("<d", 2**1023)))
print(struct.calcsize("@ciqdFD"), struct.calcsize("=ciqdFD"), struct.calcsize("ci"), struct.calcsize("ic"), struct.calcsize("c0i"), struct.calcsize("0c0i"), struct.calcsize("xxi"), struct.calcsize("ie"), struct.calcsize("cP"), struct.calcsize("3sq"), struct.calcsize("3pq"), struct.calcsize("< h  h "), m(lambda: struct.calcsize(" <h")), struct.calcsize("Zd"), struct.calcsize("Zf"), m(lambda: struct.calcsize("Zx")), m(lambda: struct.calcsize("Z")), m(lambda: struct.calcsize("<P")), m(lambda: struct.calcsize("<n")))
print(struct.pack("5p", b""), struct.pack("1p", b"abc"), struct.pack("0p", b"abc"), struct.pack("2s", b""), struct.pack("0s", b"abc"), struct.unpack("2p", b"\x09x"), struct.unpack("5s", b"abcde"), m(lambda: struct.pack("2s", 1)), m(lambda: struct.pack("2p", "ab")), m(lambda: struct.pack("c", b"")), m(lambda: struct.pack("c", 97)))
it = struct.Struct("b").iter_unpack(b"abc")
print(type(it).__name__, it.__length_hint__(), [next(it), next(it)], it.__length_hint__(), next(it), it.__length_hint__(), m(lambda: next(it)), it.__length_hint__(), m(lambda: struct.Struct("b").iter_unpack(bytearray(b"ab")).__length_hint__()))
print(struct.Struct(b"<h").format, struct.Struct("<h") is not struct.Struct("<h"), m(lambda: struct.Struct("<h", 1)), m(lambda: struct.Struct(format=1)), m(lambda: struct.Struct(b"\x80")), m(lambda: struct.Struct("\x00")), m(lambda: struct.Struct("")), struct.Struct("").size, struct.Struct("").pack(), struct.Struct("").unpack(b""), m(lambda: struct.Struct("").unpack(b"x")))
"""

TIME = r"""
import os, time
os.environ["TZ"] = "CET-1CEST,M3.5.0,M10.5.0/3"
time.tzset()
def m(f):
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
class Idx:
    def __index__(self):
        return 86400
class Fl:
    def __float__(self):
        return 3600.5
print(time.gmtime(Idx()), time.gmtime(Fl()), time.gmtime(1.9999), time.gmtime(-0.5), m(lambda: time.gmtime(2**63)), m(lambda: time.gmtime(-2**63 - 1)), m(lambda: time.gmtime(9.3e18)), m(lambda: time.gmtime(-9.3e18)), m(lambda: time.gmtime(1j)), m(lambda: time.localtime([])))
print(time.strftime("%Y-%m-%d", (2000, 2, 29, 0, 0, 0, 0, 60, 0)), time.strftime("%j", (2000, 12, 31, 0, 0, 0, 0, 366, 0)), time.strftime("%%%Y%%", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%Y%", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%Y%Y%Y" * 100, (2000, 1, 1, 0, 0, 0, 0, 1, 0))[:12], len(time.strftime("%Y%Y%Y" * 100, (2000, 1, 1, 0, 0, 0, 0, 1, 0))), time.strftime("é", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("\x00%Y\x00", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%Y\x00%m\x00%%", (2000, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("日%Y本%m語", (2000, 1, 1, 0, 0, 0, 0, 1, 0)))
print(time.asctime((2000, 1, 1, 0, 0, 0, 0, 0, 0)), time.asctime((2000, 0, 0, 0, 0, 0, 0, 0, 0)), time.asctime((99999, 1, 1, 0, 0, 0, 0, 1, 0)), time.asctime((-1, 1, 1, 0, 0, 0, 0, 1, 0)), time.asctime((2000, 1, 1, 0, 0, 0, 7, 1, 0)), m(lambda: time.asctime((2000, 1, 1, 0, 0, 0, -8, 1, 0))), time.asctime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, None, None))))
print(time.mktime((2000, 1, 1, 0, 0, 0, 0, 0, -1)), time.mktime((2000, 7, 1, 0, 0, 0, 0, 0, -1)), time.mktime((2000, 7, 1, 0, 0, 0, 0, 0, 0)), time.mktime((2000, 7, 1, 0, 0, 0, 0, 0, 1)), time.mktime((1900, 1, 1, 0, 0, 0, 0, 0, 0)), time.mktime((1, 1, 1, 0, 0, 0, 0, 0, 0)), time.mktime((9999, 12, 31, 23, 59, 59, 0, 0, 0)), m(lambda: time.mktime((2**31 - 1, 1, 1, 0, 0, 0, 0, 0, 0))), time.mktime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, "UTC", 0))), time.mktime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, None, 7200))), m(lambda: time.mktime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, 5, 0)))), m(lambda: time.mktime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, "X", "0")))))
print(m(lambda: time.sleep(0.0000001)), m(lambda: time.sleep(Fl() if False else 0)), m(lambda: time.sleep(1j)), m(lambda: time.sleep(-1e-10)), m(lambda: time.sleep(9.3e9)), m(lambda: time.sleep(2**63 // 10**9 + 1)), m(lambda: time.sleep(None)), time.sleep(Idx() * 0), m(lambda: time.sleep([])))
print(time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9, "Z")).tm_gmtoff, time.struct_time(range(9)).tm_isdst, time.struct_time(iter([1, 2, 3, 4, 5, 6, 7, 8, 9])), m(lambda: time.struct_time(5)), m(lambda: time.struct_time()), m(lambda: time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9), {"tm_zone": "Q"})), time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9), {"tm_zone": "Q"}).tm_zone, time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9))[:3], time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)).count(1), m(lambda: time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)).tm_year.__class__), hash(time.gmtime(0)) == hash(tuple(time.gmtime(0))))
print(time.get_clock_info("time").resolution, m(lambda: time.get_clock_info(b"time")), m(lambda: time.get_clock_info("")), m(lambda: time.clock_gettime(-1)), m(lambda: time.clock_gettime(True)), m(lambda: time.clock_gettime_ns(2**31)), m(lambda: time.clock_getres(2**31)), m(lambda: time.clock_getres(-5)), m(lambda: time.clock_settime(0, Fl())), m(lambda: time.clock_settime(2**31, 1)), m(lambda: time.pthread_getcpuclockid(True)), m(lambda: time.pthread_getcpuclockid(2**70)))
import datetime
print(datetime.datetime.fromtimestamp(1700000000, tz=datetime.timezone.utc), datetime.datetime.fromtimestamp(1700000000, tz=datetime.timezone.utc).timestamp(), datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc).timestamp(), datetime.date.fromtimestamp(1700000000), datetime.datetime.fromtimestamp(1700000000), datetime.datetime.fromtimestamp(1700000000).astimezone(), datetime.datetime(2023, 7, 1).timestamp())
"""

MATH = r"""
import math
def m(f):
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
class Fl:
    def __float__(self):
        return 0.25
class Bad:
    def __float__(self):
        return 1
class Idx:
    def __index__(self):
        return 3
class Fs(float):
    def __float__(self):
        return 9.0
print(math.sqrt(Fl()), math.sqrt(Fs(4.0)), m(lambda: math.sqrt(Bad())), math.sqrt(Idx()), math.floor(Fs(2.5)), math.isclose(Fl(), 0.25), math.copysign(Idx(), -1), math.fsum([Fl(), Fs(1.0), Idx()]), math.hypot(Fl(), Idx()), math.prod([Fl(), 4]), m(lambda: math.sqrt(None)), m(lambda: math.acos(1.0000001)), m(lambda: math.asin(-1.5)), m(lambda: math.atanh(1.0)), m(lambda: math.log1p(-1.0)), m(lambda: math.cos(float("inf"))), m(lambda: math.sqrt(-1e-300)), m(lambda: math.log(0.0)), m(lambda: math.log2(-2)), m(lambda: math.log10(2**1024 * -1)))
print([m(lambda: math.gamma(x)) for x in (0.1, 0.9, 1.5, 3.7, 10.5, 50.25, 100.75, 139.9, 140.1, 169.5, -0.1, -0.9, -2.5, -10.5, -50.25, -139.9, -140.1, -169.5, -199.9, -200.5, 1e-10, -1e-10, 1e-19, 1e-21)])
print([math.asinh(x) for x in (0.5, 1.0, -2.5, 1e300, -1e300, 1e-300)], [math.atanh(x) for x in (0.5, -0.5, 0.9999, 1e-300)], [math.acosh(x) for x in (1.0, 1.5, 1e300)], [math.cbrt(x) for x in (2.0, -27.5, 1e-300)], [math.expm1(x) for x in (1e-10, 0.5, -0.5)], [math.log1p(x) for x in (1e-10, 0.5, -0.5)], [math.erf(x) for x in (0.1, 0.5, 2.5)], [math.erfc(x) for x in (0.1, 0.5, 2.5, 10.0)], [math.sinh(x) for x in (0.5, 10.0)], [math.cosh(x) for x in (0.5, 10.0)], [math.tanh(x) for x in (0.5, 10.0)])   # the libm results a host's glibc version decides: compared on the same host, not recorded
print([m(lambda: math.lgamma(x)) for x in (0.1, 0.9, 1.5, 3.7, 10.5, 50.25, 100.75, 1e5, 1e10, 1e100, -0.1, -0.9, -2.5, -10.5, -50.25, -1e5 - 0.5, -1e10 - 0.5, 1e-10, -1e-10, 1e-21, -1e-21, 2.0000001)])
print([m(lambda: math.remainder(a, b)) for a, b in ((3.0, 2.0), (2.5, 1.0), (3.5, 1.0), (-2.5, 1.0), (1e308, 3.0), (5e-324, 1e-323), (1e-323, 5e-324), (7.5, 2.5), (1.0, 2.0), (1.0, -2.0), (-1.0, 2.0), (0.0, 1.0), (-0.0, 1.0), (1e300, 1e-300))])
print([m(lambda: math.fmod(a, b)) for a, b in ((1e308, 3.0), (-1e308, 3.0), (1e-320, 1e-321), (5.0, -0.0), (0.0, 1.0), (-0.0, 1.0), (float("inf"), float("inf")), (1.0, -float("inf")))])
print([m(lambda: math.pow(a, b)) for a, b in ((2.0, 1023.0), (2.0, 1024.0), (-2.0, 1023.0), (-2.0, 1024.0), (2.0, -1074.0), (2.0, -1075.0), (-1.0, 1e300), (-1.0, 1e300 + 1), (1e-300, 2.0), (1e-300, -2.0), (-1e-300, -3.0), (0.0, 0.5), (-0.0, 0.5), (-0.0, -0.5), (0.0, float("-inf")), (-0.0, float("-inf")), (float("-inf"), float("inf")), (float("-inf"), 0.5), (float("nan"), float("nan")))])
print([m(lambda: math.ldexp(a, b)) for a, b in ((0.5, 1024), (0.5, 1025), (1.0, -1074), (1.0, -1075), (1.5, -1074), (-1.0, 1024), (1e-310, 10), (1e-310, 2**31 - 1), (1.0, -(2**31)), (1.0, -(2**31) - 1), (float("nan"), 2**100), (-float("inf"), -(2**100)))])
print([m(lambda: math.frexp(x)) for x in (1.0, 0.5, 0.1, 1e308, 5e-324, 1e-310, -3.0, 2**53, 0.75)], [math.modf(x) for x in (0.5, -0.5, 1e16, 1e17, -1e-5, 123.456)])
print(math.log(2**1000), math.log(2**1000 + 1), math.log(10**400, 10), math.log2(2**1000 + 2**999), math.log10(10**400 + 1), math.log(3**700), math.log2(3**700), math.log10(3**700), math.log(2**1024 - 1), math.log(2**1024), math.log(2**2000, 3), math.log(1, 10**400), m(lambda: math.log(1, 1)), m(lambda: math.log(10, 1.0)), math.log(2.5, 2.5), math.log(2**1030, 2**1029), m(lambda: math.log(0, 10)), m(lambda: math.log(-(10**400))), m(lambda: math.log(10**400, 0)))
print(math.fsum([1e308, 1e308, -1e308, -1e308]), math.fsum([1.0, 1e100, 1.0, -1e100]), math.fsum([0.5, 0.25, 0.125] * 100), m(lambda: math.fsum([1e308, 1e308])), math.fsum([-1e308, -1e308, 1e308]), math.fsum([3.0, 1e-300, -3.0]), math.fsum([2.0**1023, 2.0**1023, -(2.0**1023)]) if False else m(lambda: math.fsum([2.0**1023, 2.0**1023, -(2.0**1023)])), math.fsum([1e16, 1.0, 1.0, 1.0, 1.0]), math.fsum([2**60, 1, -(2**60)]), math.fsum([1e-320, 1e-320, -1e-320]), math.fsum([float("-inf"), 1.0, float("-inf")]), math.fsum([float("nan"), float("inf")]))
print(math.hypot(1e-320, 1e-320, 1e-320), math.hypot(3e-310, 4e-310), math.hypot(1e308, 1e308, 1e308), math.hypot(0.0, 0.0), math.hypot(-0.0), math.hypot(1e-200, 1e200), math.hypot(*range(1, 50)), math.hypot(0.1, 0.2, 0.3, 0.4, 0.5), math.dist([1e-320, 0], [0, 1e-320]), math.dist([1.5], [-2.5]), math.dist((0.1, 0.1), (0.2, 0.2)), math.dist(range(3), range(1, 4)), m(lambda: math.dist([1, 2], [1, "2"])), m(lambda: math.dist(5, [1])))
print(math.sumprod([0.1, 0.2, 0.3], [3.0, 2.0, 1.0]), math.sumprod([1e16, 1.0, 1e-16], [1.0, 1.0, 1.0]), math.sumprod([1e308, 1e308, -1e308], [1.0, 1.0, 1.0]) if False else m(lambda: math.sumprod([1e308, 1e308, -1e308], [1.0, 1.0, 1.0])), math.sumprod([1e308, -1e308, 1e308], [1.0, 1.0, 1.0]), math.sumprod([2**63 - 1, 1], [1, 1]), math.sumprod([2**62, 2**62, 2**62], [2, 2, 2]), math.sumprod([1, 2.0, 3], [4, 5, 6.0]), math.sumprod([1, 2], [3.0, True]), math.sumprod([2**70, 1.0], [1.0, 2.0]), math.sumprod([1e200, 1e200], [1e200, -1e200]), math.sumprod([float("nan")], [1.0]), math.sumprod([float("inf")], [1]), math.sumprod([0.1] * 100, [0.1] * 100))
print(math.nextafter(1.0, float("inf"), steps=2**63), math.nextafter(1.0, -float("inf"), steps=2**63 + 1), math.nextafter(-1.0, 1.0, steps=1), math.nextafter(-1e-320, 1e-320, steps=3), math.nextafter(1e-320, -1e-320, steps=2), math.nextafter(2.0, 1.0, steps=2**52), math.nextafter(1.0, 2.0, steps=2**52), math.nextafter(1.0, 2.0, steps=2**52 + 1), math.nextafter(0.0, -0.0), math.nextafter(-0.0, 0.0), math.nextafter(0.0, -0.0, steps=1), math.nextafter(float("inf"), -float("inf"), steps=2**64), math.nextafter(5.0, 5.0, steps=10**30), m(lambda: math.nextafter(1.0, 2.0, steps=Idx())), math.nextafter(1.0, 2.0, steps=True))
print(math.ulp(5e-324), math.ulp(1e-308), math.ulp(2.0**-1022), math.ulp(0.5), math.ulp(1e16), math.ulp(-1e300), math.ulp(1.7976931348623157e308), math.isclose(1e-300, 2e-300, rel_tol=0.6), math.isclose(1e-300, 2e-300), math.isclose(1e300, 1e300 * (1 + 1e-10)), math.isclose(-float("inf"), -float("inf")), math.isclose(float("inf"), -float("inf")), math.isclose(1, 1.0000000001, rel_tol=1e-9, abs_tol=0), m(lambda: math.isclose(1, 2, abs_tol=-0.0)), math.isclose(1, 2, abs_tol=float("inf")), math.isclose(1, 2, rel_tol=float("nan")))
print(math.gcd(2**200, 3**100 * 2**150), math.lcm(2**100, 3**50), math.gcd(-12, 18), math.gcd(12, -18, 0), math.lcm(6, -4, 10), math.lcm(1, 0, 2), math.gcd(True, False), math.lcm(Idx(), 4), m(lambda: math.lcm(1.5)), math.factorial(50), math.factorial(Idx()), m(lambda: math.factorial(2**63 - 1)), m(lambda: math.factorial(-(2**70))), math.comb(60, 30), math.comb(2**64, 1), math.comb(2**64, 2**64 - 2), math.perm(20, 10), math.perm(2**64, 1), math.perm(10, 10), math.perm(10, 11), math.isqrt(2**200), math.isqrt(2**200 - 1), math.isqrt((2**100 + 1) ** 2 - 1), math.isqrt(Idx()), m(lambda: math.isqrt(-(2**100))), math.comb(Idx(), 2), math.perm(Idx()), m(lambda: math.comb(3, 1.0)), m(lambda: math.perm(2**64, 2**70)), m(lambda: math.comb(2**70, 2**63)))
print(m(lambda: math.sqrt()), m(lambda: math.atan2(1, 2, 3)), m(lambda: math.copysign(1)), m(lambda: math.log(1, 2, 3)), m(lambda: math.fma(1, 2)), m(lambda: math.hypot(1, x=2)), m(lambda: math.dist()), m(lambda: math.sumprod([1])), m(lambda: math.isclose()), m(lambda: math.prod()), m(lambda: math.nextafter()), m(lambda: math.ulp(1, 2)), m(lambda: math.gcd(1, [])), m(lambda: math.lcm(x=1)), m(lambda: math.isqrt()), m(lambda: math.factorial(n=5)), m(lambda: math.comb(5, k=2)), m(lambda: math.perm(5, k=2)), m(lambda: math.ldexp(1)), m(lambda: math.frexp()), m(lambda: math.modf(1, 2)), m(lambda: math.fmod(1)), m(lambda: math.remainder()), m(lambda: math.trunc()), m(lambda: math.floor(1, 2)), m(lambda: math.degrees()), m(lambda: math.isnan(1, 2)), m(lambda: math.fmax(1, 2, 3)), m(lambda: math.erf()), m(lambda: math.gamma(1, 2)), m(lambda: math.exp(x=1)), m(lambda: math.log(x=1)))
"""

DIGESTS = r"""
import _blake2, _hmac, _md5, _sha1, _sha2, _sha3, hashlib, hmac
def m(f):
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
data = bytes(range(256)) * 9
for c in (_md5.md5, _sha1.sha1, _sha2.sha224, _sha2.sha256, _sha2.sha384, _sha2.sha512, _sha3.sha3_224, _sha3.sha3_256, _sha3.sha3_384, _sha3.sha3_512, _blake2.blake2b, _blake2.blake2s):
    whole = c(data).hexdigest()
    piecewise = c()
    for size in (1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 64, 65, 127, 128, 129, 1000):
        piecewise.update(data[:size])
        data = data[size:] + data[:size]
    print(c.__name__ if hasattr(c, "__name__") else c, whole[:16], piecewise.hexdigest()[:16], c(b"").hexdigest()[:16], c(b"a" * 1000000).hexdigest()[:16])
print(_sha3.shake_128(data).hexdigest(300)[-16:], _sha3.shake_256(data).hexdigest(300)[-16:], _sha3.shake_128(b"").digest(0), _sha3.shake_256(b"x").digest(1).hex())
print(_blake2.blake2b(data, digest_size=1).hexdigest(), _blake2.blake2b(data, key=data[:64], salt=data[:16], person=data[16:32], fanout=255, depth=255, leaf_size=2**32 - 1, node_offset=2**64 - 1, node_depth=255, inner_size=64, last_node=True).hexdigest()[:16], _blake2.blake2s(data, key=data[:32], salt=data[:8], person=data[8:16], fanout=255, depth=255, leaf_size=2**32 - 1, node_offset=2**48 - 1, node_depth=255, inner_size=32, last_node=True).hexdigest()[:16], _blake2.blake2b(b"", key=b"\x00" * 64).hexdigest()[:16], _blake2.blake2s(b"", key=b"\x00" * 32).hexdigest()[:16])
for name in ("md5", "sha1", "sha256", "sha512", "sha3_256", "sha3_512"):
    for klen in (0, 63, 64, 65, 135, 136, 137, 143, 144, 145, 71, 72, 73):
        k = data[:klen]
        assert _hmac.compute_digest(k, data, name) == _hmac.new(k, data, name).digest() == hmac.new(k, data, name).digest() == hmac.digest(k, data, name), (name, klen)
    print(name, _hmac.compute_digest(data[:5], data, name).hex()[:16], hmac.new(data[:200], data, getattr(hashlib, name)).hexdigest()[:16])
print(hmac.new(b"key", b"The quick brown fox jumps over the lazy dog", hashlib.sha256).hexdigest(), hashlib.sha1(b"The quick brown fox jumps over the lazy dog").hexdigest(), hashlib.md5(b"The quick brown fox jumps over the lazy dog").hexdigest(), hashlib.sha3_256(b"").hexdigest(), hashlib.blake2b(b"abc").hexdigest()[:32], hashlib.blake2s(b"abc").hexdigest()[:32], hashlib.shake_128(b"").hexdigest(16), hashlib.sha512(b"abc").hexdigest()[:32], hashlib.sha384(b"abc").hexdigest()[:32], hashlib.sha224(b"abc").hexdigest()[:32])
h = hashlib.sha256(); h.update(b"a"); g = h.copy(); g.update(b"b"); h.update(b"b")
print(h.hexdigest() == g.hexdigest() == hashlib.sha256(b"ab").hexdigest(), h.name, h.digest_size, h.block_size, hashlib.new("SHA1", b"a").name, m(lambda: hmac.new(b"k", b"m", "md5").name), hmac.compare_digest(hashlib.sha1(b"a").digest(), hashlib.sha1(b"a").digest()), m(lambda: hmac.new(b"k", 5, "sha1")), m(lambda: hashlib.sha1(5)), m(lambda: hashlib.sha1("s")))
"""

FUNCTION_ANNOTATIONS = r"""
import annotationlib
def f(x: int, y: "str" = "a") -> list[int]:
    return [x]
def g(): pass
print(f.__annotations__, f.__annotations__ is f.__annotations__, f.__annotate__ is not None, g.__annotations__, g.__annotate__, g.__annotations__ is g.__annotations__)
def m(fn):
    try: return repr(fn())
    except Exception as e: return type(e).__name__ + ": " + str(e)
h = f
print(m(lambda: setattr(h, "__annotations__", 1)), m(lambda: setattr(h, "__annotations__", {"z": 1})), h.__annotations__, h.__annotate__, m(lambda: delattr(h, "__annotations__")), h.__annotations__, h.__annotate__)
def k(a: int): pass
print(m(lambda: setattr(k, "__annotate__", 5)), m(lambda: delattr(k, "__annotate__")), k.__annotations__, m(lambda: setattr(k, "__annotate__", lambda fmt: {"q": fmt})), k.__annotations__, k.__annotate__(2), m(lambda: setattr(k, "__annotate__", None)), k.__annotations__, k.__annotate__)
def bad(a: int): pass
bad.__annotate__ = lambda fmt: 5
print(m(lambda: bad.__annotations__))
def late(a: Undefined): pass  # noqa: F821
print(m(lambda: late.__annotations__))
class C:
    def meth(self, v: int) -> None: pass
print(C.meth.__annotations__, C().meth.__annotations__, type(C.meth.__annotate__).__name__)
"""


def test_json() -> None:
    """_json's scanner and encoder: the messages the case does not compare."""
    same(JSON)


def test_typing_objects() -> None:
    """typing's C types and PEP 695's intrinsics: the messages the case does not compare."""
    same(TYPING_OBJECTS)


def test_binascii() -> None:
    """binascii's calling conventions (the clinic's messages), its converters, every strict-mode message, base64 over it."""
    same(BINASCII)


def test_struct() -> None:
    """_struct's complex and float conversions, the half float's rounding and limits, the standard and native complex paths, Struct's
    methods by keyword, the cache's messages, Pascal and char strings at their edges, the iterator's length hint."""
    same(STRUCT)


def test_time() -> None:
    """time's conversions through __index__ and __float__, strftime's split at non-ASCII and NUL characters and its percent at the end,
    asctime's ranges, mktime with a struct_time's zone and offset, sleep's edges, struct_time's constructor, the clocks' converters;
    datetime over it."""
    same(TIME)


def test_math() -> None:
    """math's conversions (__float__, __index__, float subclasses), gamma and lgamma across their ranges, remainder and fmod at the edges,
    pow's special values, ldexp and frexp at the limits, logs of huge ints, fsum's overflow and special sums, hypot and dist with
    subnormals, sumprod's paths, nextafter's step arithmetic, ulp, isclose, the integer functions with large arguments, and every calling
    convention's message."""
    same(MATH)


def test_function_annotations() -> None:
    """function.__annotations__ under PEP 649: made once from __annotate__ and cached, an empty dict for a bare function, the setter's
    type check and its clearing of __annotate__, the deleter, __annotate__'s own rules, a non-dict answer refused, methods."""
    same(FUNCTION_ANNOTATIONS)


CSV = r"""
import _csv, csv, io
def gen(n):
    x = 4242 + n
    while True:
        x = (x * 1103515245 + 12345) & 0x7fffffff
        yield x
alphabet = ['a', 'b', ' ', ',', '"', ';', '\\', '\n', '\r', '\r\n', '\t', 'é', '\u2603', '']
rows = []
g = gen(7)
for i in range(60):
    row = []
    for j in range(1 + next(g) % 5):
        k = next(g) % 4
        if k == 0:
            row.append(None)
        elif k == 1:
            row.append(next(g) % 1000 if next(g) % 2 else next(g) / 7.0)
        else:
            row.append("".join(alphabet[next(g) % len(alphabet)] for _ in range(next(g) % 6)))
    rows.append(row)
for quoting in (0, 1, 2, 4, 5):
    for kw in ({}, {"escapechar": "\\"}, {"doublequote": False, "escapechar": "\\"}, {"delimiter": ";", "lineterminator": "\n"}, {"skipinitialspace": True, "escapechar": "\\"}):
        out = io.StringIO()
        try:
            w = _csv.writer(out, quoting=quoting, **kw)
            for row in rows:
                w.writerow(row)
            text = out.getvalue()
        except _csv.Error as e:
            print(quoting, sorted(kw.items()), "Error:", e)
            continue
        back = []
        r = _csv.reader(io.StringIO(text, newline=""), quoting=quoting, **kw)
        try:
            for row in r:
                back.append(row)
        except Exception as e:
            print(quoting, sorted(kw.items()), len(text), type(e).__name__, e, r.line_num)
            continue
        print(quoting, sorted(kw.items()), len(text), len(back), r.line_num, sum(len(x) for x in back), back == [[("" if f is None else str(f)) for f in row] for row in rows] if quoting in (0, 1) else back[:3])
text = "id,name,amount,date\r\n1,\"Smith, J\",10.50,2026-01-02\r\n2,\"O\"\"Brien\",7,2026-01-03\r\n3,\"multi\r\nline\",0.5,2026-02-01\r\n"
print(list(csv.DictReader(io.StringIO(text, newline=""))))
r = csv.reader(io.StringIO(text, newline=""))
print([(row, r.line_num) for row in r])
print(csv.Sniffer().sniff(text).delimiter, csv.Sniffer().sniff(text).quotechar, csv.Sniffer().has_header(text))
print(csv.Sniffer().sniff("a|b|c\n1|2|3\n4|5|6\n").delimiter, csv.Sniffer().has_header("a|b|c\n1|2|3\n4|5|6\n"))
try:
    csv.Sniffer().sniff("")
except csv.Error as e:
    print("Error:", e)
for mode in (csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONNUMERIC, csv.QUOTE_NONE, csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL):
    out = io.StringIO()
    try:
        csv.writer(out, quoting=mode, escapechar="\\").writerows([["x", 1, None, 2.5, "a,b"], [], [""], [None]])
        print(mode, repr(out.getvalue()))
    except csv.Error as e:
        print(mode, "Error:", e)
out = io.StringIO()
dw = csv.DictWriter(out, fieldnames=["name", "qty"])
dw.writeheader()
dw.writerow({"name": "n", "qty": 2})
dw.writerows([{"name": "m"}, {"qty": 5, "name": "o"}])
try:
    dw.writerow({"name": "n", "bad": 2})
except ValueError as e:
    print(e)
csv.DictWriter(out, fieldnames=["a"], extrasaction="ignore", restval="-").writerows([{"a": 1, "b": 2}, {}])
print(repr(out.getvalue()), list(csv.DictReader(io.StringIO(out.getvalue(), newline=""))))
"""


def test_digests() -> None:
    """The digests over a long rotating input in every piece size, a million bytes, SHAKE's long output, BLAKE2 with every parameter at its
    limit, HMAC with keys around each block size through _hmac, hmac and hashlib, and the known answers of the quick brown fox."""
    same(DIGESTS)


CONTEXTVARS = r"""
import contextvars
counter = contextvars.ContextVar("counter", default=0)
trail = contextvars.ContextVar("trail")
def bump(n):
    tokens = []
    for i in range(n):
        tokens.append(counter.set(counter.get() + 1))
    seen = [counter.get()]
    for tok in reversed(tokens):
        counter.reset(tok)
        seen.append(counter.get())
    return seen
print(bump(5), counter.get())
def layered(depth):
    ctx = contextvars.copy_context()
    if depth == 0:
        return [counter.get()]
    counter.set(counter.get() + 10)
    inner = ctx.run(layered, depth - 1)
    return [counter.get()] + inner + [ctx[counter] if counter in ctx else None]
print(layered(3), counter.get())
snapshots = []
for i in range(4):
    trail.set(tuple(range(i)))
    snapshots.append(contextvars.copy_context())
print([c[trail] for c in snapshots], [len(c) for c in snapshots], snapshots[0] == snapshots[1], snapshots[3] == contextvars.copy_context())
def run_in(ctx, f, *a):
    return ctx.run(f, *a)
print(run_in(snapshots[1], lambda: (trail.get(), counter.get(), counter.set(7).old_value, counter.get())), counter.get(), snapshots[1][counter])
with counter.set(100) as tok:
    with counter.set(200):
        print(counter.get(), tok.old_value, tok.var.name)
    print(counter.get())
print(counter.get())
try:
    tok.__exit__(None, None, None)
except RuntimeError as e:
    print("RuntimeError", str(e).startswith("<Token used var=<ContextVar name='counter'"))
names = [contextvars.ContextVar("n%d" % i, default=i) for i in range(20)]
for i, v in enumerate(names):
    if i % 2:
        v.set(i * i)
ctx = contextvars.copy_context()
print(sorted((v.name, val) for v, val in ctx.items()), len(ctx), sum(1 for v in names if v in ctx), [v.get() for v in names])
import decimal
from decimal import Decimal, getcontext, localcontext
print(getcontext().prec, Decimal(1) / Decimal(7))
with localcontext() as c:
    c.prec = 5
    print(Decimal(1) / Decimal(7), getcontext().prec)
print(Decimal(1) / Decimal(7), getcontext().prec)
def in_ctx():
    getcontext().prec = 3
    return str(Decimal(1) / Decimal(7))
print(contextvars.copy_context().run(in_ctx), str(Decimal(1) / Decimal(7)), getcontext().prec)
"""


def test_csv() -> None:
    """_csv's writer and reader round trip sixty generated rows (delimiters, quotes, backslashes, line endings and empty fields) under each
    quoting mode and five dialects, the csv package's DictReader, reader with line_num, Sniffer and writer over them."""
    same(CSV)


BISECT = r"""
import _bisect, bisect
def gen(n):
    x = 99 + n
    while True:
        x = (x * 1103515245 + 12345) & 0x7fffffff
        yield x
g = gen(3)
values = [next(g) % 1000 for _ in range(400)]
sorted_right, sorted_left = [], []
for v in values:
    _bisect.insort_right(sorted_right, v)
    bisect.insort_left(sorted_left, v)
print(sorted_right == sorted(values), sorted_left == sorted(values), len(sorted_right))
probes = [next(g) % 1100 - 50 for _ in range(300)]
ok = True
for x in probes:
    r, l = _bisect.bisect_right(sorted_right, x), _bisect.bisect_left(sorted_right, x)
    ok = ok and all(e <= x for e in sorted_right[:r]) and all(e > x for e in sorted_right[r:]) and all(e < x for e in sorted_right[:l]) and all(e >= x for e in sorted_right[l:])
    lo, hi = sorted((next(g) % 401, next(g) % 401))
    rr = _bisect.bisect_right(sorted_right, x, lo, hi)
    ok = ok and lo <= rr <= hi and all(e <= x for e in sorted_right[lo:rr]) and all(e > x for e in sorted_right[rr:hi])
print(ok, sum(_bisect.bisect_right(sorted_right, x) - _bisect.bisect_left(sorted_right, x) for x in range(1000)))
records = [(next(g) % 50, i) for i in range(200)]
by_key = []
for rec in records:
    _bisect.insort_left(by_key, rec, key=lambda r: r[0])
print([r[0] for r in by_key] == sorted(r[0] for r in records), [_bisect.bisect_right(by_key, k, key=lambda r: r[0]) for k in (0, 10, 25, 49, 50)], [_bisect.bisect_left(by_key, k, key=lambda r: r[0]) for k in (0, 10, 25, 49, 50)])
stable = [r[1] for r in by_key if r[0] == by_key[100][0]]
print(stable == sorted(stable))
words = sorted("the quick brown fox jumps over the lazy dog".split())
print(words, [bisect.bisect(words, w) for w in ("a", "fox", "foxy", "zzz", "")], [bisect.bisect_left(words, w) for w in ("a", "fox", "foxy", "zzz", "")])
def grade(score, breakpoints=[60, 70, 80, 90], grades="FDCBA"):
    return grades[bisect.bisect(breakpoints, score)]
print([grade(s) for s in [33, 99, 77, 70, 89, 90, 60, 59]])
"""


def test_contextvars() -> None:
    """Context variables set and reset in nests, layered copies run with their own variables, snapshots of the current context, the
    token as a context manager, a context's mapping over twenty variables, and decimal's context through contextvars.ContextVar."""
    same(CONTEXTVARS)


RANDOM_STATISTICS_HEAPQ = r"""
import _random, random, statistics, heapq, threading, collections
r = _random.Random(2024)
words = [r.getrandbits(32) for _ in range(2000)]
print(words[:3], words[-3:], sum(words) % 1000003, r.getstate()[-1])
r.seed(2024)
print(all(r.getrandbits(32) == w for w in words), [r.random() for _ in range(3)], r.getrandbits(1000) % 999983)
R = random.Random(99)
sample = [R.randrange(1000) for _ in range(500)]
print(sample[:8], statistics.mean(sample), statistics.median(sample), statistics.pstdev(sample), statistics.quantiles(sample, n=4), statistics.mode(sample), len(statistics.multimode(sample)))
print(R.sample(range(10**6), 5), R.choices("xyz", weights=[1, 2, 7], k=10), R.gauss(0, 1), R.expovariate(2.0), R.shuffle(sample) or sample[:5], R.randbytes(6), R.randint(-5, 5))
nd = statistics.NormalDist.from_samples(sample)
print(nd.mean, nd.stdev, nd.inv_cdf(0.25), nd.inv_cdf(0.999), nd.cdf(500), nd.quantiles(n=4))
d = statistics.NormalDist(10, 2)
print(d.cdf(12), d.pdf(10), d.inv_cdf(0.9), d.inv_cdf(0.1), d.quantiles(), d.quantiles(n=10), d.overlap(statistics.NormalDist(12, 2)), d.overlap(statistics.NormalDist(12, 3)), [d.cdf(x / 4) for x in range(20, 60, 7)], [d.pdf(x / 3) for x in range(20, 60, 7)])
c = collections.Counter(w % 7 for w in words)
print(c.most_common(3), c.most_common(), heapq.nlargest(4, words), heapq.nsmallest(4, words))
heap = list(words[:1000])
heapq.heapify(heap)
out = [heapq.heappop(heap) for _ in range(10)]
heapq.heappush(heap, 5)
print(out, out == sorted(words[:1000])[:10], heapq.heappushpop(heap, 7), heapq.heapreplace(heap, 11), heap[0], len(heap))
hm = list(words[:1000])
heapq.heapify_max(hm)
print([heapq.heappop_max(hm) for _ in range(5)] == sorted(words[:1000], reverse=True)[:5], heapq.heappushpop_max(hm, 2**40), hm[0] == max(hm))
loc = threading.local()
print(getattr(loc, "value", "unset"), threading.current_thread().name, threading.main_thread() is threading.current_thread(), threading.active_count(), threading.get_ident() == threading.main_thread().ident, threading.get_native_id() > 0)
loc.value = [1]
loc.value.append(2)
print(loc.value, vars(loc), threading.local() is not loc)
lock = threading.Lock()
with lock:
    print(lock.locked(), lock.acquire(blocking=False))
rl = threading.RLock()
with rl:
    with rl:
        print(rl._is_owned(), repr(rl).startswith("<locked _thread.RLock object owner="), rl._recursion_count())
ev = threading.Event()
print(ev.is_set(), ev.wait(0.01), ev.set(), ev.is_set(), ev.wait(), ev.clear(), ev.is_set())
cond = threading.Condition()
with cond:
    print(cond.wait(0.01), cond.wait_for(lambda: True))
sem = threading.BoundedSemaphore(2)
print(sem.acquire(), sem.acquire(), sem.acquire(timeout=0.01), sem.release(), sem.release())
try:
    sem.release()
except ValueError as e:
    print(e)
t = threading.Thread(target=print, args=("never",), name="worker")
print(t.name, t.daemon, t.is_alive(), t.ident, repr(t)[:28], threading.Timer(0.1, print).name.startswith("Thread-"))
"""


def test_bisect() -> None:
    """insort keeps four hundred generated values sorted from both sides, bisect's answers bound the slices as the documentation
    says over three hundred probes with random lo and hi, insort with a key is stable, and the bisect module's textbook uses."""
    same(BISECT)


ZLIB = r"""
import zlib, io, base64
def gen(n):
    x = 101 + n
    while True:
        x = (x * 1103515245 + 12345) & 0x7fffffff
        yield x
g = gen(3)
blocks = [bytes(next(g) % 256 for _ in range(1 + next(g) % 3000)) for _ in range(12)] + [bytes([next(g) % 16]) * (next(g) % 5000) for _ in range(6)] + [b"", b"a", b"ab" * 70000]
for level in (-1, 0, 1, 5, 9):
    comps = [zlib.compress(b, level) for b in blocks]
    print(level, [len(c) for c in comps], all(zlib.decompress(c) == b for c, b in zip(comps, blocks)), zlib.crc32(b"".join(comps)), zlib.adler32(b"".join(comps)))
co = zlib.compressobj(7, wbits=31, memLevel=6)
stream = b"".join(co.compress(b) for b in blocks) + co.flush()
d = zlib.decompressobj(31)
got = []
for i in range(0, len(stream), 1000):
    got.append(d.decompress(stream[i:i + 1000]))
got.append(d.flush())
print(len(stream), b"".join(got) == b"".join(blocks), d.eof, zlib.crc32(stream), zlib.decompress(stream, 47) == b"".join(blocks))
d = zlib.decompressobj()
body = zlib.compress(b"".join(blocks))
out = bytearray()
pending = body
sizes = []
while pending or d.unconsumed_tail:
    chunk = d.decompress(pending, 4096)
    out += chunk
    sizes.append(len(chunk))
    pending = d.unconsumed_tail
    if d.eof:
        break
print(bytes(out) == b"".join(blocks), len(sizes), sizes[:3], sizes[-2:], d.eof, d.unused_data, d.flush())
z = zlib._ZlibDecompressor()
out = bytearray()
for i in range(0, len(body), 777):
    out += z.decompress(body[i:i + 777], 2000)
    while not z.needs_input and not z.eof:
        out += z.decompress(b"", 2000)
print(bytes(out) == b"".join(blocks), z.eof, z.needs_input, z.unused_data)
sync = zlib.compressobj(wbits=-15)
parts = [sync.compress(blocks[0]) + sync.flush(zlib.Z_SYNC_FLUSH), sync.compress(blocks[1]) + sync.flush(zlib.Z_FULL_FLUSH), sync.compress(blocks[2]) + sync.flush()]
print([len(p) for p in parts], [p[-4:] for p in parts[:2]], zlib.decompress(b"".join(parts), -15) == b"".join(blocks[:3]))
token = base64.urlsafe_b64encode(zlib.compress(b'{"id": 7, "name": "token"}')).rstrip(b"=")
print(token, zlib.decompress(base64.urlsafe_b64decode(token + b"=" * (-len(token) % 4))))
"""


def test_random_statistics_heapq_threading() -> None:
    """The twister over two thousand words and a thousand bits, random's distributions, statistics over five hundred samples with
    NormalDist.from_samples and the inverse CDF, Counter.most_common and the heaps over the words, and CPython's own threading module
    with one thread: local, Lock, RLock, Event, Condition, BoundedSemaphore and an unstarted Thread."""
    same(RANDOM_STATISTICS_HEAPQ)

OPCODE = r"""
import _opcode, opcode, dis
print(sorted(n for n in dir(_opcode) if not n.startswith("__")))
print([len([op for op in range(300) if getattr(_opcode, n)(op)]) for n in ("is_valid", "has_arg", "has_const", "has_name", "has_jump", "has_free", "has_local", "has_exc")])
print(_opcode.get_nb_ops()[:3], _opcode.get_intrinsic2_descs()[1], _opcode.get_special_method_names(), _opcode.get_specialization_stats())
print(opcode.hasarg[:5], opcode.hasconst, opcode.hasexc, opcode._nb_ops[-1], dis.opname[opcode.opmap["LOAD_CONST"]], dis.hasjump == opcode.hasjump)
for bad in (lambda: _opcode.has_arg(), lambda: _opcode.has_arg(1, 2), lambda: _opcode.has_arg(op=1), lambda: _opcode.has_arg("x"), lambda: _opcode.has_arg(2**31), lambda: _opcode.get_nb_ops(1)):
    try:
        bad()
    except Exception as e:
        print(type(e).__name__, e)
"""

WARNINGS = r"""
import warnings, _warnings, sys, os, io
def shown(rec):
    return [(w.category.__name__, os.path.basename(w.filename), w.lineno, str(w.message), w.module) for w in rec]
def inner(level):
    warnings.warn("inner", stacklevel=level)
with warnings.catch_warnings(record=True) as rec:
    warnings.simplefilter("always")
    for level in (1, 2, 3, 9):
        inner(level)
    warnings.warn(DeprecationWarning("inst"))
    warnings.warn_explicit("explicit", RuntimeWarning, "x.py", 4, "mod", {})
print(shown(rec), warnings.filters is _warnings.filters, warnings.warn is _warnings.warn, warnings.defaultaction, warnings.onceregistry)
with warnings.catch_warnings(record=True) as rec:          # the default filters
    warnings.warn("user"); warnings.warn("dep", DeprecationWarning); warnings.warn("pending", PendingDeprecationWarning); warnings.warn("imp", ImportWarning)
    warnings.warn_explicit("dep elsewhere", DeprecationWarning, "e.py", 1, module="elsewhere")
    for _ in range(3):
        warnings.warn("once per location")
print(shown(rec), sorted(str(k) for k in __warningregistry__))
registry = {}
for action in ("error", "ignore", "always", "default", "once", "module"):
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter(action)
        got = []
        for ln in (1, 1, 2):
            try:
                warnings.warn_explicit("t", UserWarning, "f.py", ln, "m", registry); got.append(".")
            except UserWarning:
                got.append("E")
        print(action, "".join(got), len(rec), sorted(str(k) for k in registry if k != "version"))
err = io.StringIO()
sys.stderr = err
warnings.resetwarnings()
warnings.warn("to stderr")
warnings.warn("to stderr")
sys.stderr = sys.__stderr__
print([line.partition(":")[2] if line.startswith(("/", "prog.py")) else line for line in err.getvalue().splitlines()])   # the path before the first colon is the build's to spell
"""

IMPORTLIB = r"""
import importlib, importlib.util, importlib.machinery, json, sys, os, _imp
print(importlib.import_module("json") is json, importlib.import_module(".decoder", "json").__name__, importlib.__import__("os.path") is os, importlib.machinery.all_suffixes()[:2], len(importlib.machinery.EXTENSION_SUFFIXES))
spec = importlib.util.spec_from_file_location("m", "/d/m.py")
print(spec.name, type(spec.loader).__name__, spec.origin, spec.parent, importlib.util.module_from_spec(spec).__file__, importlib.util.find_spec("json").name, importlib.util.find_spec("nope"), importlib.util.resolve_name("..x", "a.b.c"))
print(importlib.util.source_hash(b"abc"), importlib.util.decode_source(b"a = 1\r\nb = 2\n"), _imp.is_builtin("math"), _imp.is_frozen("os"), _imp.lock_held(), sys.modules["_frozen_importlib"] is importlib._bootstrap, [c.__name__ for c in sys.meta_path])
print(type(json.__loader__).__module__, json.__spec__.loader is json.__loader__, os.__spec__.origin, inspect_ok := __import__("inspect").getmodulename("x.py"))
class M(type(sys)):
    pass
print(M.__mro__[1].__name__)
try:
    importlib.import_module("no.such")
except ModuleNotFoundError as e:
    print(e.name, e)
"""

EXCEPTION_GROUPS = r"""
import contextlib, copy
def shape(g):
    if g is None:
        return None
    if isinstance(g, BaseExceptionGroup):
        return (type(g).__name__, g.message, [shape(x) for x in g.exceptions])
    return repr(g)
tree = ExceptionGroup("outer", [ValueError(1), ExceptionGroup("inner", [TypeError(2), ValueError(3)]), OSError(4)])
for matcher in (ValueError, (TypeError, OSError), lambda x: isinstance(x, ValueError) and x.args[0] > 1, KeyError):
    match, rest = tree.split(matcher)
    print(shape(match), shape(rest), shape(tree.subgroup(matcher)))
print(type(BaseExceptionGroup("m", [ValueError()])).__name__, type(BaseExceptionGroup("m", [KeyboardInterrupt()])).__name__, str(tree), repr(ExceptionGroup("t", (ValueError(),))))
try:
    raise ExceptionGroup("raised", [ValueError(1), TypeError(2)]) from KeyError("why")
except ExceptionGroup as e:
    e.add_note("n")
    m, r = e.split(ValueError)
    print(m.__traceback__ is e.__traceback__, repr(m.__cause__), m.__suppress_context__, m.__notes__, m.__notes__ is e.__notes__)
with contextlib.suppress(ValueError):
    raise ExceptionGroup("all", [ValueError(1)])
try:
    with contextlib.suppress(ValueError):
        raise ExceptionGroup("partly", [ValueError(1), TypeError(2)])
except ExceptionGroup as left:
    print(shape(left))
print(shape(copy.copy(tree)), ImportError("x", name="n").__reduce__(), AttributeError("a", name="b").__reduce__())
"""


def test_zlib() -> None:
    """zlib 1.3.2 built into the runtime against the pin's: twenty-one blocks (random bytes, runs, empty, a 140 KB repeat) at five
    levels, a gzip stream compressed in pieces and read back in pieces, a bounded decompressobj loop, _ZlibDecompressor's buffering,
    sync and full flushes in a raw stream, and the itsdangerous-style token."""
    same(ZLIB)


def test_opcode() -> None:
    """_opcode's predicates and tables (the pin's, read off by tools/opcode_tables.py) behind opcode and dis, and the clinic's parsing."""
    same(OPCODE)


def test_warnings() -> None:
    """_warnings (the C half of warnings) as a prelude: the frame a warning is charged to by stacklevel, a Warning instance as the
    message, the default filters by category and module, the six actions and their registry entries, and the stderr format with
    the source line through linecache (which reads the program's file)."""
    same(WARNINGS)


def test_importlib() -> None:
    """importlib's package, compiled from CPython's text over the runtime's _frozen_importlib, _frozen_importlib_external and _imp:
    import_module, __import__, the suffixes, spec_from_file_location, find_spec, resolve_name, source_hash, decode_source, the
    frozen modules' identities, sys.meta_path, and a class statement over ModuleType."""
    same(IMPORTLIB)


EXCEPT_STAR = r"""
import sys
def m(f):
    try:
        f()
        return "nothing raised"
    except BaseException as e:
        return type(e).__name__ + ": " + str(e) + " | context " + type(e.__context__).__name__
def star(t, exc):
    def f():
        try:
            raise exc
        except* t:
            pass
    return f
print(m(star(ExceptionGroup, ValueError())), m(star((ValueError, BaseExceptionGroup), ValueError())), m(star(int, ValueError())), m(star((ValueError, 1), ValueError())), m(star("x", ExceptionGroup("g", [ValueError()]))))
class Odd(ExceptionGroup):
    def split(self, t):
        return self.answer
for answer in ([1, 2], (1,), (), None, (None, None, 3)):
    g = Odd("odd", [ValueError(1)])
    g.answer = answer
    print(repr(answer), m(star(ValueError, g)))
class Meta(type):
    def __subclasscheck__(cls, sub):
        return True
class Sneaky(Exception, metaclass=Meta):
    pass
print(m(star(Sneaky, ValueError())))
def gen():
    try:
        raise ExceptionGroup("g", [ValueError(1), TypeError(2)])
    except* ValueError as e:
        yield "in the clause: " + str(type(sys.exception()).__name__) + " " + str([type(x).__name__ for x in e.exceptions])
    except* TypeError:
        yield "second clause"
print(m(lambda: print(list(gen()))))
"""


def test_except_star() -> None:
    """try/except* (the frontend's desugar-try-star over the runtime's eg_match and prep_reraise_star): the words of what a clause's
    type is refused for, a split method that answers what CHECK_EG_MATCH refuses, a __subclasscheck__ that PyObject_IsSubclass asks,
    and clauses that yield."""
    same(EXCEPT_STAR)


def test_exception_groups() -> None:
    """BaseExceptionGroup and ExceptionGroup (Objects/exceptions.c) without except*: split and subgroup by a type, a tuple and a
    predicate, the class chosen by what is nested, the metadata the parts keep, contextlib.suppress over a group, and the
    reduction methods copy reaches (BaseException's, ImportError's, AttributeError's)."""
    same(EXCEPTION_GROUPS)


def test_what_is_absent_stops_by_name() -> None:
    cases = (("import zlib\nzlib.crc32(b'a', -1)", "unsigned 32-bit"), ("import ast\nast.parse('1')", "compile()"),
             ("import ast\nast.expr()", "abstract AST node class"), ("import typing\nif __name__ == '__main__':\n    typing.TypeVar('T', bound='Fwd')", "a ForwardRef built at runtime"),
             ("def f[T: int]():\n    pass\nimport annotationlib\nannotationlib.call_evaluate_function(f.__type_params__[0].evaluate_bound, annotationlib.Format.STRING)", "second entry point"),
             ("import binascii\nbinascii.b2a_uu(b'a')", "binascii.b2a_uu"), ("import binascii\nbinascii.crc32(b'a', -1)", "unsigned 32-bit"), ("import base64\nbase64.b32encode(b'a')", "binascii.b2a_base32"),
             ("import struct\nclass S(struct.Struct):\n    pass\nS('b')", "subclassing _struct.Struct"), ("import struct\ns = struct.Struct('b')\ns.__init__('h')", "another format"),
             ("import _md5\n_md5.md5(string=b'x')", "'string' keyword"), ("import _blake2\n_blake2.blake2s(string=b'x')", "'string' keyword"),
             ("import _opcode\n_opcode.stack_effect(1)", "_opcode.stack_effect"), ("import warnings\nwarnings.warn_explicit('m', UserWarning, 'f', 1, module_globals={'__name__': 'x'})", "module_globals"),
             ("import importlib, json\nimportlib.reload(json)", "importlib.reload"), ("import importlib.machinery\nimportlib.machinery.PathFinder.find_spec('x')", "PathFinder.find_spec"),
             ("import importlib.util, json\nimportlib.util.LazyLoader(json.__loader__).exec_module(json)", "__class__ assignment"), ("import _imp\n_imp.get_frozen_object('os')", "_imp.get_frozen_object"), ("import dis\ndis.get_executor(1, 2)", "_opcode.get_executor"),
             ("import sys\nr = sys.__unraisablehook__\nclass K:\n    def __del__(self): raise ValueError\nkept = []\nsys.unraisablehook = kept.append\nK()\n"
              "r(type(kept[0])((3, 4, None, None, None)))", "an exc_type that is no class"),
             ("import sys\nsys._getframe()", "sys._getframe (a frame object"),
             ("import gc\ngc.collect()", "gc.collect (the cycle collector"), ("import gc\ngc.is_tracked([])", "gc.is_tracked (the cycle collector"),
             ("import gc\ngc.get_objects()", "gc.get_objects (CPython's object graph, E-05)"), ("import gc\ngc.freeze()", "gc.freeze (CPython's object graph, E-05)"),
             ("import threading\nthreading.Thread(target=print).start()", "creating a thread"),
)
    for body, name in cases:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


# atexit on every way out of a program (C-7-54 and C-7-55 are the cases; these are the ways out they do not take)
ATEXIT_WAYS_OUT = {
    "the end of the module": """
        import atexit, sys
        class Kept:
            def __del__(self): print("finaliser, after the handlers")
        kept = Kept()
        atexit.register(print, "handler on stderr", file=sys.stderr)
        atexit.register(print, "handler on stdout")
        print("end")
    """,
    "sys.exit with a text": """
        import atexit, sys
        atexit.register(print, "handler after the text", file=sys.stderr)
        sys.exit("the exit's text")
    """,
    "sys.exit in a function": """
        import atexit, sys
        def leave(): sys.exit(5)
        atexit.register(print, "handler")
        leave()
    """,
    "SystemExit of nothing": """
        import atexit
        atexit.register(print, "handler")
        raise SystemExit
    """,
    "the module dropped from sys.modules": """
        import atexit, sys
        atexit.register(print, "registered before the module was dropped")
        del sys.modules["atexit"]
        import atexit as again
        print(again._ncallbacks(), atexit._ncallbacks())   # the list is the interpreter's, whichever module object asks
        again.register(print, "registered with the second module")
        del sys.modules["atexit"], atexit, again
    """,
    "a handler that runs the handlers": """
        import atexit
        def once():
            print("once", atexit._ncallbacks())
        def runs():
            atexit.unregister(runs)
            print("runs them", atexit._ncallbacks())
            atexit._run_exitfuncs()
            print("after", atexit._ncallbacks())
        atexit.register(once)
        atexit.register(runs)
    """,
    "what stands for threading has no _shutdown": """
        import atexit, sys, threading
        atexit.register(print, "handler, after the report", file=sys.stderr)
        sys.modules["threading"] = None
    """,
    "threading dropped from sys.modules": """
        import atexit, sys, threading
        threading._register_atexit(print, "never called: threading is not among the modules")
        atexit.register(lambda: print("handler; shutting down:", threading._SHUTTING_DOWN))
        del sys.modules["threading"]
    """,
    "the handlers' keywords": """
        import atexit
        def show(*args, **kwargs): print(args, kwargs)
        keywords = {"k": 1}
        atexit.register(show, 1, **keywords)
        atexit.register(show, **{})
        atexit.register(show, func=2, args=3, kwargs=4)
        keywords["k"] = 2
    """,
    "an uncaught exception without sys.excepthook": """
        import atexit, sys
        atexit.register(print, "handler", file=sys.stderr)
        del sys.excepthook
        raise KeyError("uncaught")
    """,
}

# iobase_finalize: close() raising in the finaliser is reported as ignored, with the file's repr unless that raises too
IO_FINALISER = """
    import io, sys
    class F(io.RawIOBase):
        def __repr__(self): return "<F>"
        def close(self): raise ValueError("close fails")
    class G(io.StringIO):
        def __repr__(self): raise RuntimeError("no repr")
        def close(self): raise KeyError("close of a StringIO fails")
    f = F()
    del f
    print("after the first", file=sys.stderr)
    g = G()
    del g
    print("end", file=sys.stderr)
"""


# what becomes of an uncaught exception under each hook (C-7-56 is the case; these are the hooks it does not install)
EXCEPTHOOK_WAYS = {
    "a hook that raises": """
        import atexit, sys
        def hook(kind, value, tb):
            print("the hook", kind.__name__)
            raise RuntimeError("from the hook")
        sys.excepthook = hook
        atexit.register(print, "handler", file=sys.stderr)
        raise KeyError("uncaught")
    """,
    "a hook that exits with a number": """
        import sys
        def hook(kind, value, tb): sys.exit(5)
        sys.excepthook = hook
        raise KeyError("uncaught")
    """,
    "a hook that exits with a text": """
        import sys
        def hook(kind, value, tb): raise SystemExit("the hook's text")
        sys.excepthook = hook
        raise KeyError("uncaught")
    """,
    "None for a hook": """
        import sys
        sys.excepthook = None
        raise KeyError("uncaught")
    """,
    "the built-in hook, and what an atexit handler reads": """
        import atexit, sys
        def handler():
            print(repr(sys.last_exc), sys.last_type.__name__, sys.last_value is sys.last_exc, type(sys.last_traceback).__name__, sys.last_traceback.tb_next)
        atexit.register(handler)
        print([hasattr(sys, n) for n in ("last_exc", "last_type", "last_value", "last_traceback")])
        raise KeyError("uncaught")
    """,
    "SystemExit is no business of the hook's": """
        import atexit, sys
        sys.excepthook = lambda *args: print("never called")
        atexit.register(lambda: print([hasattr(sys, n) for n in ("last_exc", "last_type")]))
        sys.exit(4)
    """,
    "a hook that is the built-in one of another name": """
        import sys
        sys.excepthook = sys.__excepthook__
        def f(): raise ValueError("uncaught", 1)
        f()
    """,
    "a hook that prints and one that is a method": """
        import sys
        class Reporter:
            def report(self, kind, value, tb):
                print("reported:", kind.__name__, value.args, tb.tb_lineno, tb.tb_next is None, file=sys.stderr)
        sys.excepthook = Reporter().report
        print("before")
        raise LookupError("uncaught", 2)
    """,
    "the unraisable hook at the end of the program": """
        import atexit, sys
        class Named:
            def __repr__(self): return "<Named>"
            def __call__(self): raise ValueError("from the handler")
        def hook(u):
            print("hook:", type(u).__name__, u.exc_type.__name__, u.exc_value, u.err_msg, u.object)
        sys.unraisablehook = hook
        atexit.register(Named())
        atexit.register(int, "x")
        print("end")
    """,
    "the built-in unraisable hook for an exception with no frame of its own": """
        import atexit, weakref
        class Referent: pass
        referent = Referent()
        reference = weakref.ref(referent, int)
        del referent
        atexit.register(int, "x")
    """,
}


def test_an_uncaught_exception_under_each_hook() -> None:
    for name, program in EXCEPTHOOK_WAYS.items():
        try:
            same_streams({"main.py": program}, stderr=True)
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None


GC_MODULE = r"""
import gc, weakref
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: gc.set_threshold()), m(lambda: gc.set_threshold(1, 2, 3, 4)), m(lambda: gc.set_threshold("x")), m(lambda: gc.set_threshold(1.5)), m(lambda: gc.set_threshold(2**31)), m(lambda: gc.set_threshold(-2**31 - 1)), m(lambda: gc.set_threshold(2**70)), m(lambda: gc.set_threshold(-2**70)), m(lambda: gc.set_threshold(1, a=2)), m(lambda: gc.set_threshold(1, "x")), gc.get_threshold())
print(m(lambda: gc.set_debug()), m(lambda: gc.set_debug("x")), m(lambda: gc.set_debug(2**40)), m(lambda: gc.set_debug(flags=1)), m(lambda: gc.set_debug(1, 2)), m(lambda: gc.set_debug(-2**31)), gc.get_debug(), m(lambda: gc.set_debug(0)))
print(m(lambda: gc.collect(3)), m(lambda: gc.collect(-1)), m(lambda: gc.collect("x")), m(lambda: gc.collect(1.0)), m(lambda: gc.collect(generation=5)), m(lambda: gc.collect(gen=1)), m(lambda: gc.collect(1, 2)), m(lambda: gc.collect(2**40)), m(lambda: gc.collect(1, generation=1)))
print(m(lambda: gc.isenabled(1)), m(lambda: gc.enable(a=1)), m(lambda: gc.disable(0)), m(lambda: gc.get_threshold(1)), m(lambda: gc.get_debug(None)), m(lambda: gc.get_count(1)), m(lambda: gc.get_stats(1)), m(lambda: gc.freeze(1)), m(lambda: gc.unfreeze(x=1)), m(lambda: gc.get_freeze_count(1)))
print(m(lambda: gc.is_tracked()), m(lambda: gc.is_tracked(1, 2)), m(lambda: gc.is_finalized()), m(lambda: gc.is_finalized(obj=1)), m(lambda: gc.get_referrers(a=1)), m(lambda: gc.get_referents(a=1)))
print(m(lambda: gc.get_objects(3)), m(lambda: gc.get_objects(-2)), m(lambda: gc.get_objects("x")), m(lambda: gc.get_objects(1.5)), m(lambda: gc.get_objects(2**70)), m(lambda: gc.get_objects(1, 2)), m(lambda: gc.get_objects(gen=1)))
print(gc.collect.__doc__, gc.set_threshold.__doc__, gc.__doc__, type(gc.collect).__name__, gc.collect.__module__, gc.collect.__qualname__, repr(gc.isenabled), gc.isenabled.__self__ is gc)
class K:
    pass
k = K()
weakref.finalize(k, lambda: print("at exit:", gc.isenabled(), gc.get_threshold()))
gc.disable()
weakref.finalize(K(), print, "made with automatic collection off")
gc.enable()
"""


def test_gc() -> None:
    """The gc module's words, the clinic's and the C's, and weakref.finalize at exit, which turns automatic collection off."""
    same(GC_MODULE)


def test_atexit_on_every_way_out() -> None:
    for name, program in ATEXIT_WAYS_OUT.items():
        try:
            same_streams({"main.py": program}, stderr=True)
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None


def test_a_file_whose_close_raises_in_its_finaliser() -> None:
    same_streams({"main.py": IO_FINALISER}, stderr=True)


# beside C-7-62: what the unclosed-file warning puts on standard error. In flight the warnings module shows it, with the line that
# dropped the file; made an error it is reported as ignored, about the raw file; and a Python __del__ that drops a file is charged
UNCLOSED_SHOWN = """
    import io, os, sys, warnings
    warnings.simplefilter("always")
    open(__file__, "rb")
    open(__file__, encoding="utf-8")
    def leaves():
        local = open(__file__, "rb", buffering=0)
        return local.fileno() > 2
    leaves()
    class Owner:
        def __init__(self):
            self.f = open(__file__, "rb")
        def __del__(self):
            self.f = None
            warnings.warn("from __del__", UserWarning)
    o = Owner()
    del o
    sys.stderr.write("--- default: once a line\\n")
    warnings.simplefilter("default")
    for _ in range(2):
        open(__file__, "rb")
    sys.stderr.write("--- no filters\\n")
    warnings.resetwarnings()
    open(__file__, "rb")
    sys.stderr.write("--- an error\\n")
    warnings.simplefilter("error")
    open(__file__, "rb")
    open(__file__, encoding="utf-8")
    sys.stderr.write("--- the C's own printing, with no warnings._showwarnmsg to ask\\n")
    warnings.simplefilter("always")
    del warnings._showwarnmsg
    warnings.warn_explicit("explicit", UserWarning, "<made up>", 7)
    class Err:
        def write(self, text):
            sys.__stderr__.write("[" + text.replace("\\n", "\\\\n") + "]\\n")
    sys.stderr = Err()
    warnings.warn_explicit("part by part", DeprecationWarning, "<made up>", 9)
    sys.stderr = None
    warnings.warn_explicit("nowhere to go", UserWarning, "<made up>", 10)
    sys.stderr = sys.__stderr__
    warnings.simplefilter("ignore")
    print("end")
"""

# On the way out a file a module still holds is finalized with no frame to charge ("<sys>", line 0) and no warnings module to ask
# (sys.modules is empty by then), so the C prints the line itself: for whatever holds the file, on every way out, and whatever
# showwarning the program had put in. A program that never touched the filters says nothing.
UNCLOSED_AT_EXIT = {
    "a global": """
        import warnings
        warnings.simplefilter("always")
        kept = open(__file__, "rb")
        def a_function():
            pass
        print("ending")
    """,
    "no function in the module": """
        import warnings
        warnings.simplefilter("always")
        kept = open(__file__, encoding="utf-8")
        print("ending")
    """,
    "an error": """
        import warnings
        warnings.simplefilter("error")
        kept = open(__file__, encoding="utf-8")
        def a_function():
            pass
        print("ending")
    """,
    "sys.exit": """
        import sys, warnings
        warnings.simplefilter("always")
        kept = open(__file__, "rb", buffering=0)
        def a_function():
            pass
        print("ending")
        sys.exit(3)
    """,
    "an uncaught exception": """
        import warnings
        warnings.simplefilter("always")
        kept = open(__file__, "rb")
        def a_function():
            pass
        print("ending")
        raise ValueError("uncaught")
    """,
    "a closure": """
        import warnings
        warnings.simplefilter("always")
        def make():
            f = open(__file__, "rb")
            def inner():
                return f
            return inner
        keep = make()
        print("ending")
    """,
    "a generator": """
        import warnings
        warnings.simplefilter("always")
        def gen():
            f = open(__file__, "rb")
            yield 1
            yield f
        g = gen()
        next(g)
        print("ending")
    """,
    "a showwarning of the program's": """
        import sys, warnings
        def show(message, category, filename, lineno, file=None, line=None):
            sys.__stdout__.write("the program's showwarning: %s %s:%s\\n" % (category.__name__, filename, lineno))
        warnings.showwarning = show
        warnings.simplefilter("always")
        open(__file__, "rb")
        kept = open(__file__, "rb")
        print("ending")
    """,
    "an atexit handler": """
        import atexit, warnings
        warnings.simplefilter("always")
        kept = open(__file__, "rb")
        def last():
            global kept
            print("handler")
            kept = None
        atexit.register(last)
        print("ending")
    """,
    "the default filters": """
        import sys
        kept = open(__file__, "rb")
        other = open(__file__, "rb", buffering=0)
        def a_function():
            pass
        print("ending")
    """,
    "the default filters, warnings imported": """
        import warnings
        kept = open(__file__, "rb")
        def a_function():
            pass
        print("ending")
    """,
}
# CPython's default hook adds this line beneath a warning that has a source, when tracemalloc can be imported and is not tracing.
# tracemalloc is excluded (E-03) and the manifest leaves it out of warnings' imports, so the compiled program takes the hook's
# other path and has no such line: open with the author (docs/DECISIONS.md, C-7-62). Compared without it, and its absence checked.
TRACEMALLOC_HINT = "ResourceWarning: Enable tracemalloc to get the object allocation traceback\n"


def same_but_for_the_tracemalloc_hint(program: str) -> None:
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp, "main.py")
        main.write_text(textwrap.dedent(program), encoding="utf-8")
        ref = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, check=False, env=env, cwd=tmp)
        got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    assert TRACEMALLOC_HINT not in got.stderr, got.stderr
    want = (ref.stdout, ref.returncode, mask_stderr(ref.stderr.replace(TRACEMALLOC_HINT, "")))
    have = (got.stdout, got.returncode, mask_stderr(got.stderr))
    assert have == want, (f"\n--- compiled (exit {got.returncode})\n{got.stdout}{got.stderr}\n"
                          f"--- CPython (exit {ref.returncode})\n{ref.stdout}{ref.stderr}")


def test_an_unclosed_file_shown_on_standard_error() -> None:
    same_but_for_the_tracemalloc_hint(UNCLOSED_SHOWN)


# beside C-7-63: the two RuntimeWarnings of io and os as the default filters show them, once for a line, and as errors uncaught
RUNTIME_WARNINGS_SHOWN = {
    "shown": """
        import io, os, sys
        for _ in range(2):
            open(__file__, "rb", buffering=1).close()
        io.FileIO(False, closefd=False)
        os.stat(True)
        os.stat(__file__, dir_fd=False)
        os.fsync(sys.__stderr__) if False else os.stat(False)
        print("end")
    """,
    "line buffering, an error": """
        import warnings
        warnings.simplefilter("error")
        print("start")
        open(__file__, "rb", buffering=1)
    """,
    "a bool, an error": """
        import os, warnings
        warnings.simplefilter("error")
        print("start")
        os.stat(True)
    """,
}


def test_the_runtime_warnings_of_io_and_os_on_standard_error() -> None:
    for name, program in RUNTIME_WARNINGS_SHOWN.items():
        try:
            same_streams({"main.py": program}, stderr=True)
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None


def test_a_file_still_open_on_the_way_out() -> None:
    for name, program in UNCLOSED_AT_EXIT.items():
        try:
            same_but_for_the_tracemalloc_hint(program)
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None


if __name__ == "__main__":
    test_pwd_grp_locale_zlib()
    test_the_t_string_types()
    test_ast_nodes()
    test_typing_objects()
    test_json()
    test_exec_with_a_locals_mapping_offsets_and_sentinel()
    test_zlib()
    test_opcode()
    test_warnings()
    test_importlib()
    test_exception_groups()
    test_atexit_on_every_way_out()
    test_an_uncaught_exception_under_each_hook()
    test_a_file_whose_close_raises_in_its_finaliser()
    test_an_unclosed_file_shown_on_standard_error()
    test_a_file_still_open_on_the_way_out()
    test_the_runtime_warnings_of_io_and_os_on_standard_error()
    test_what_is_absent_stops_by_name()
