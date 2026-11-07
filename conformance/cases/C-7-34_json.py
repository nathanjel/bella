# clause: C-7-34
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_json.c, Lib/json
"""json over _json: the scanner (strings and their escapes, numbers, constants, objects and arrays, the hooks, the memo, every
JSONDecodeError with its position) and the encoder (every type, the keys a dict may have, sort_keys, skipkeys, allow_nan, indent and
separators, circular references, default, the notes a failing item adds), plus the module's functions and types."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _json
import json


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except json.JSONDecodeError as exc:
        return ("JSONDecodeError", exc.msg, exc.pos, exc.lineno, exc.colno)
    except StopIteration as exc:
        return ("StopIteration", exc.value)
    except Exception as exc:
        return (type(exc).__name__, list(getattr(exc, "__notes__", ())))
    return "no error"


class Foo:
    pass


class S(str):
    pass


class I(int):
    def __repr__(self):  # type: ignore[no-untyped-def]
        return "I!"


class F(float):
    def __repr__(self):  # type: ignore[no-untyped-def]
        return "F!"


class D(dict):  # type: ignore[type-arg]
    pass


print(failed(lambda: _json.scanstring(1, 0)), failed(lambda: _json.scanstring("abc")), failed(lambda: _json.scanstring("abc", "x")), failed(lambda: _json.scanstring("abc", 5)), failed(lambda: _json.scanstring("abc", -1)), failed(lambda: _json.scanstring('"abc', 1)), _json.scanstring('"a\\u00e9\\ud83d\\ude00b"x', 1), repr(_json.scanstring('"a\\ud83dq"', 1)), failed(lambda: _json.scanstring('"a\\x"', 1)), failed(lambda: _json.scanstring('"a\\u12"', 1)), failed(lambda: _json.scanstring('"a\\u12zz"', 1)), failed(lambda: _json.scanstring('"a\nb"', 1)), _json.scanstring('"a\nb"', 1, False), failed(lambda: _json.scanstring("abc", 0, 1, 2)), failed(lambda: _json.scanstring(pystr="abc", end=0)), _json.scanstring('"\\"\\\\\\/\\b\\f\\n\\r\\t"', 1), _json.scanstring('""', 1), failed(lambda: _json.scanstring('"', 1)), repr(_json.scanstring('"\\ud800\\udc00"', 1)), repr(_json.scanstring('"\\udc00\\ud800"', 1)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(_json.encode_basestring_ascii('a"\\/\b\f\n\r\t\x01\x7f\x80é😀'), _json.encode_basestring('a"\\/\b\f\n\r\t\x01\x7f\x80é😀'), failed(lambda: _json.encode_basestring_ascii(1)), failed(lambda: _json.encode_basestring(b"a")), failed(lambda: _json.encode_basestring_ascii()), failed(lambda: _json.encode_basestring("a", "b")), _json.encode_basestring_ascii(S("x")), type(_json.encode_basestring_ascii(S("x"))).__name__, _json.encode_basestring(S("é")), type(_json.encode_basestring(S("é"))).__name__, _json.encode_basestring_ascii(""), _json.encode_basestring(""), json.encoder.encode_basestring_ascii is _json.encode_basestring_ascii, json.encoder.c_make_encoder is _json.make_encoder, json.scanner.make_scanner is _json.make_scanner, json.decoder.scanstring is _json.scanstring)  # type: ignore[arg-type,attr-defined,call-arg,no-untyped-call]
print(failed(lambda: _json.make_scanner()), failed(lambda: _json.make_scanner(1)), type(_json.make_scanner(context=json.JSONDecoder())).__name__, failed(lambda: _json.make_scanner(json.JSONDecoder(), 2)), failed(lambda: _json.make_scanner(x=1)), failed(lambda: _json.make_encoder()), failed(lambda: _json.make_encoder(1, 2, 3, 4, "a", "b", 1, 1, 1)), failed(lambda: _json.make_encoder(None, 2, 3, 4, 5, "b", 1, 1, 1)), type(_json.make_encoder(None, 2, 3, 4, "a", "b", 1, 1, 1)).__name__, failed(lambda: _json.make_encoder(None, 2, 3, 4, "a", "b", 1, 1)), type(_json.make_encoder(markers=None, default=2, encoder=3, indent=4, key_separator="a", item_separator="b", sort_keys=1, skipkeys=1, allow_nan=1)).__name__, failed(lambda: _json.make_encoder(None, 1, 2, 3, "a", "b", 1, 1, 1, 2)), failed(lambda: _json.make_encoder(None, 1, 2, 3, "a", "b", 1, 1, 1, zz=2)))  # type: ignore[arg-type,call-arg,no-untyped-call]
s = json.JSONDecoder().scan_once  # type: ignore[attr-defined]
print(failed(lambda: s()), failed(lambda: s(1, 0)), failed(lambda: s("1", "x")), failed(lambda: s("1", -1)), failed(lambda: s("1", 5)), failed(lambda: s("", 0)), s("12 ", 0), s(" 12", 1), failed(lambda: s(" 12", 0)), s('"a"', 0), s("[1, 2]", 0), s("{}", 0), s('{"a": {"b": [1.5, -2e3, 1E+2, 0, -0, 0.0, 10]}}', 0), failed(lambda: s("[1,]", 0)), failed(lambda: s('{"a":1,}', 0)), failed(lambda: s("[1 2]", 0)), failed(lambda: s('{"a" 1}', 0)), failed(lambda: s("{a:1}", 0)), failed(lambda: s("[", 0)), failed(lambda: s("{", 0)), failed(lambda: s("-", 0)), failed(lambda: s("-x", 0)), s("01", 0), s("1.", 0), s("1e", 0), s("1e5x", 0), s("1.5e-3", 0), s("NaN", 0), s("-Infinity", 0), s("Infinity", 0), failed(lambda: s("nul", 0)), s("truex", 0), s(string="false", idx=0), failed(lambda: s("1" * 5000, 0)), failed(lambda: s("1", 0, 3)), s("[]", 0), s("[ ]", 0), s("{ }", 0), s('{"a":1}', 0), failed(lambda: s("[1", 0)), failed(lambda: s('{"a":1', 0)), failed(lambda: s("[1,", 0)), s("1.5E3", 0), s("-0.5", 0), s("0e0", 0))  # type: ignore[no-untyped-call]
d = json.JSONDecoder(parse_float=lambda x: ("f", x), parse_int=lambda x: ("i", x), parse_constant=lambda x: ("c", x), object_hook=lambda o: ("o", sorted(o)), object_pairs_hook=None, strict=False)
print(d.scan_once('[1, 2.5, NaN, {"k": "v\n"}, -1e1]', 0), json.loads('{"a": 1, "a": 2}'), type(json.loads("1")), failed(lambda: json.loads("")), failed(lambda: json.loads("[1] x")), failed(lambda: json.loads('{"a": }')), failed(lambda: json.loads("﻿[]")), json.loads(b"[1]"), json.loads(bytearray(b"[1]")), failed(lambda: json.loads(1)), repr(json.loads('"\\ud800"')), repr(json.loads('"\\ud800\\u0041"')), json.loads(" \t\n\r[1]\n"), json.JSONDecoder(object_pairs_hook=lambda p: p).decode('{"b": 1, "a": 2}'), json.loads('{"x": {"x": 1}}'), json.loads("[[[]]]"), json.loads('{"a":\n[1,\n2]}'), failed(lambda: json.loads('{"a":\n[1,\n2}')), json.loads("3"), json.loads("1e3"), json.loads('"\\u0041\\u00e9"'))  # type: ignore[arg-type,attr-defined,no-untyped-call]
keys = json.loads('[{"k": 1}, {"k": 2}]')
print(list(keys[0])[0] is list(keys[1])[0], json.loads("[1.0, 2]", parse_float=str), json.loads("[1.0, 2]", parse_int=str), json.loads("[NaN]", parse_constant=str), json.JSONDecoder(strict=False).decode('"a\tb"'), failed(lambda: json.loads('"a\tb"')), json.loads('{"a": [1, {"b": null}], "c": true}'))  # type: ignore[no-untyped-call]
print(json.dumps({"a": [1, 2.5, True, None, "x"], "b": {"c": (1,)}}), json.dumps([1.0, 1e100, 1e16, 1e-7, 0.1, -0.0, 1e22]), json.dumps("é😀"), json.dumps("é😀", ensure_ascii=False), json.dumps({1: 2, 2.5: 3, True: 4, None: 5, False: 6, "s": 7}), failed(lambda: json.dumps({(1, 2): 3})), json.dumps({(1, 2): 3}, skipkeys=True), json.dumps({"b": 1, "a": 2}, sort_keys=True), failed(lambda: json.dumps({"b": 1, 2: 2}, sort_keys=True)), failed(lambda: json.dumps(float("nan"), allow_nan=False)), json.dumps([float("nan"), float("inf"), -float("inf")]), failed(lambda: json.dumps(Foo())), failed(lambda: json.dumps([Foo()])), failed(lambda: json.dumps({"k": Foo()})), failed(lambda: json.dumps({"k": [1, {"z": Foo()}]})), json.dumps(Foo(), default=lambda o: {"foo": 1}), json.dumps(S("x")), json.dumps([I(5), F(2.5)]), json.dumps({I(5): F(2.5)}), json.dumps(D(a=1)), json.dumps({}), json.dumps([]), json.dumps(()), json.dumps(123456789012345678901234567890), json.dumps(-0.0), json.dumps(1e300 * 1e300), json.dumps(True), json.dumps(None), failed(lambda: json.dumps(D(k=Foo()))), failed(lambda: json.dumps([(Foo(),)])), failed(lambda: json.dumps({1.5: 1, "a": Foo()})))  # type: ignore[no-untyped-call]
print(json.dumps({"a": {}, "b": []}, indent=2))
print(json.dumps([1, [2, [3]]], indent="\t"))
print(json.dumps({"a": 1}, indent=0), json.dumps([1, 2], separators=(",", ":")), json.dumps({"a": 1, "b": 2}, indent=1, separators=(" ;", " = ")), json.dumps({"b": 1, "a": 2}, sort_keys=True, indent=1), json.dumps({"a": 1}, indent=3, separators=(",", ":")), json.dumps([[], {}, [{}], {"x": []}], indent=1), json.dumps({"k": "v"}, indent=None), json.dumps("x", cls=None), failed(lambda: json.dumps([1], indent=1.5)))  # type: ignore[arg-type,no-untyped-call]
l = []  # type: ignore[var-annotated]
l.append(l)
dd = {}  # type: ignore[var-annotated]
dd["x"] = dd
print(failed(lambda: json.dumps(l)), failed(lambda: json.dumps(dd)), failed(lambda: json.dumps({"a": [dd]})), json.JSONEncoder(check_circular=False).encode([1]), failed(lambda: json.dumps([Foo()], default=lambda o: o)), failed(lambda: json.dumps([Foo()], default=lambda o: 1 / 0)), json.JSONEncoder().encode("s"), list(json.JSONEncoder().iterencode([1, "a", {"b": 2.5}])), list(json.JSONEncoder(indent=1).iterencode({"a": [1]})), json.JSONEncoder(default=lambda o: list(o)).encode((1, 2)))  # type: ignore[no-untyped-call]
enc = _json.make_encoder(None, lambda o: "D", lambda s: "E", None, ": ", ", ", False, False, True)
print(enc([1, "a", {"b": None}, Foo()], 0), failed(lambda: enc("x")), failed(lambda: enc("x", "y")), enc(obj="x", _current_indent_level=0), failed(lambda: _json.make_encoder(None, lambda o: "D", lambda s: 5, None, ": ", ", ", False, False, True)(["a"], 0)), _json.make_encoder(None, lambda o: "D", lambda s: 5, None, ": ", ", ", False, False, True)([1], 0), enc.markers, enc.indent, enc.key_separator, enc.item_separator, enc.sort_keys, enc.skipkeys, type(enc.default).__name__, failed(lambda: setattr(enc, "indent", 1)), failed(lambda: enc.allow_nan), type(enc([1], 0)).__name__)  # type: ignore[arg-type,attr-defined,call-arg,no-untyped-call,return-value]
e2 = _json.make_encoder(None, lambda o: "D", _json.encode_basestring_ascii, None, ": ", ", ", False, False, True)
print(e2([S("é")], 0), e2(["é"], 0), e2([1.5e300 * 1e300], 0), failed(lambda: _json.make_encoder(None, lambda o: "D", _json.encode_basestring_ascii, None, ": ", ", ", False, False, False)([1e400], 0)), e2([{True: 1}], 0), e2([{1.5: 1}], 0), e2({1.5: 1, "x": Foo()}, 0), _json.make_encoder(None, lambda o: "D", _json.encode_basestring, None, ": ", ", ", False, False, True)(["é\n"], 0), _json.make_encoder(None, lambda o: "D", _json.encode_basestring_ascii, "  ", ": ", ", ", True, False, True)({"b": [1, {"a": 2.5}], "a": None}, 1), _json.make_encoder(None, lambda o: "D", _json.encode_basestring_ascii, "-", ": ", ",", False, False, True)([[]], 2))  # type: ignore[no-untyped-call]
sc = _json.make_scanner(json.JSONDecoder())  # type: ignore[arg-type]
print(sc.strict, sc.object_hook, sc.object_pairs_hook, sc.array_hook, sc.parse_float, sc.parse_int, type(sc.parse_constant).__name__, failed(lambda: setattr(sc, "strict", 0)), type(sc).__name__, type(sc).__module__, type(enc).__module__, repr(type(sc)), failed(lambda: type(sc)()), _json.__doc__, sorted(n for n in dir(_json) if not n.startswith("__")), _json.make_scanner.__doc__, _json.make_encoder.__doc__, _json.scanstring.__doc__[:30], _json.encode_basestring.__doc__, _json.encode_basestring_ascii.__doc__)  # type: ignore[call-arg,index,no-untyped-call]


class M(dict):  # type: ignore[type-arg]
    def items(self):  # type: ignore[no-untyped-def]
        return [("z", 1), ("y", 2)]


class M2(dict):  # type: ignore[type-arg]
    def items(self):  # type: ignore[no-untyped-def]
        return [("z",)]


class M3(dict):  # type: ignore[type-arg]
    def items(self):  # type: ignore[no-untyped-def]
        return [(1, 2), ("a", 3)]


print(json.dumps(M(a=1)), failed(lambda: json.dumps(M2(a=1))), json.dumps(M3(a=1)), failed(lambda: json.dumps(M3(a=1), sort_keys=True)), json.dumps(frozendict({"a": 1})), json.dumps({"k": frozendict({"b": [frozendict()]})}), json.dumps(frozendict({"b": 1, "a": 2}), sort_keys=True))  # type: ignore[no-untyped-call]
