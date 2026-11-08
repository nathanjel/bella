"""pwd, grp, _locale, zlib, _ast, _typing, _json and the t-string types, compiled, against CPython: the messages the cases do not compare, the conversions'
edges, and what stops by name. The locale facts are the C locale's and C.UTF-8's; what reads the environment's locale is the same environment on
both sides."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
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
"""


def test_digests() -> None:
    """The digests over a long rotating input in every piece size, a million bytes, SHAKE's long output, BLAKE2 with every parameter at its
    limit, HMAC with keys around each block size through _hmac, hmac and hashlib, and the known answers of the quick brown fox."""
    same(DIGESTS)


def test_csv() -> None:
    """_csv's writer and reader round trip sixty generated rows (delimiters, quotes, backslashes, line endings and empty fields) under each
    quoting mode and five dialects, the csv package's DictReader, reader with line_num, Sniffer and writer over them."""
    same(CSV)


def test_what_is_absent_stops_by_name() -> None:
    cases = (("import zlib\nzlib.compress(b'a')", "zlib"), ("import zlib\nzlib.ZLIB_VERSION", "ZLIB_VERSION"), ("import ast\nast.parse('1')", "compile()"),
             ("import ast\nast.expr()", "abstract AST node class"), ("import typing\ntyping.TypeVar('T', bound='Fwd')", "compile()"),
             ("def f[T: int]():\n    pass\nimport annotationlib\nannotationlib.call_evaluate_function(f.__type_params__[0].evaluate_bound, annotationlib.Format.STRING)", "second entry point"),
             ("import binascii\nbinascii.b2a_uu(b'a')", "binascii.b2a_uu"), ("import binascii\nbinascii.crc32(b'a', -1)", "unsigned 32-bit"), ("import base64\nbase64.b32encode(b'a')", "binascii.b2a_base32"),
             ("import struct\nclass S(struct.Struct):\n    pass\nS('b')", "subclassing _struct.Struct"), ("import struct\ns = struct.Struct('b')\ns.__init__('h')", "another format"),
             ("import _md5\n_md5.md5(string=b'x')", "'string' keyword"), ("import _blake2\n_blake2.blake2s(string=b'x')", "'string' keyword"),
             ("import csv, io\ncsv.DictWriter(io.StringIO(), ['a']).writerow({'a': 1})", "set operations on dict keys"))
    for body, name in cases:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_pwd_grp_locale_zlib()
    test_the_t_string_types()
    test_ast_nodes()
    test_typing_objects()
    test_json()
    test_exec_with_a_locals_mapping_offsets_and_sentinel()
    test_what_is_absent_stops_by_name()
