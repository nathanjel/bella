# clause: C-6-15
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/unicode_formatter.c, Objects/stringlib/unicode_format.h, Python/pystrtod.c
"""The format mini-language on int, bool, float and str, through format(), f-strings and str.format; str.format's own
language of fields, attributes, items, conversions, nesting and numbering; format_map; __format__ of a class; and
string.Formatter over _string, which is the same parser taken one step at a time."""
# ruff: noqa: B015, B018, B023, E742, F521, F523, F541, F632, PLR0124, RUF015, UP030, UP031, UP032
import string


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- int
for spec in ("", "d", "5", "<5", ">5", "^5", "=5", "05", "*<5", "*>5", "*^5", "*=5", "+", "-", " ", "+5", " 5", "+05", "+=5", "x", "X", "o", "b", "c", "n", "#x", "#X", "#o", "#b", "#d", "#010x", "#10x", "#<10x", "#^10x", "*=#10x", "_", ",", "_d", ",d", "_x", "_X", "_o", "_b", "#_x", "010,", "010_", "020_x", "011,d", "012,d", "013,", "e", "E", "f", "F", "g", "G", "%", ".2f", ".0f", ".2e", ".3g", ".1%", ",.2f", "_.2f", "010.2f", "é<5", "é^5"):
    print(repr(spec), [format(v, spec) for v in (0, 1, -1, 255, -255, 1234567, 10**12, -(10**12)) if not (spec == "c" and not 0 <= v <= 0x10FFFF)])
print(format(2**70, "x"), format(-(2**70), "#b"), format(2**70, ","), format(2**70, "_"), format(2**70, "e"), format(2**70, ".3f"), format(10**30, "040,"), format(10**30, "%"), format(True), format(True, ""), format(True, "d"), format(True, "5"), format(False, "x"), format(True, "f"), format(True, "c"), format(65, "c"), format(0x65E5, "c") == chr(0x65E5), format(65, "5c"), format(65, "<5c"), format(65, "*^5c"), format(65, "05c"), format(65, ",d"))
for spec, v in ((".2", 1), (".2d", 1), ("z", 1), ("zd", 1), ("+c", 65), (" c", 65), ("#c", 65), (",c", 65), ("_c", 65), ("s", 1), ("a", 1), ("y", 1), ("5s", 1), ("xx", 1), ("<<", 1), ("c", -1), ("c", 0x110000), ("c", 2**70), (",x", 1), (",b", 1), (",o", 1), (",X", 1), (",n", 1), ("_n", 1), ("_c", 1), (",_", 1), ("_,", 1), ("99999999999999999999", 1), (".99999999999999999999f", 1), (".", 1), (".f", 1), ("\x00", 1), ("\x7f", 1), (" ", 1), ("n", 1)):
    print(repr(spec), failed(lambda: format(v, spec)), end="; ")
print()

# ---- float
values = (0.0, -0.0, 1.0, -1.0, 0.5, 1.5, 2.5, 1234.5678, -1234.5678, 1e-5, 1e16, 1.5e300, 5e-324, 0.1, 100.0, 1e100, float("inf"), float("-inf"), float("nan"))
for spec in ("", "e", "E", "f", "F", "g", "G", "n", "%", ".0f", ".1f", ".2f", ".3f", ".10f", ".0e", ".1e", ".3e", ".0g", ".1g", ".3g", ".10g", ".0%", ".1%", ".3", ".0", ".1", ".17", "10", "<10", ">10", "^10", "=10", "010", "*<10", "*>10", "*^10", "*=10", "+", " ", "-", "+.2f", " .2f", "-.2f", "+010.2f", "010.2f", "#", "#.0f", "#.0e", "#g", "#.3g", "#.0g", "#e", "#%", ",", "_", ",.2f", "_.2f", "012,.2f", "012_.2f", ",e", ",g", "_e", ".3,", ".3_", ".6,f", ".6_f", ",.6,f", "_.6_f", ",.6_f", "_.6,f", ".,f", "._f", ".,", "._", "z", "z.2f", "z.0f", "z.1e", "z%", "z,.1f", "+z.1f", " z.1f"):
    print(repr(spec), [format(v, spec) for v in values])
print(format(1.5, ".1000f")[:20], len(format(1.5, ".1000f")), len(format(1.5, ".400e")), format(1e300, "f")[:20], len(format(1e300, "f")), format(0.1, ".60f"), format(5e-324, ".1100f")[-30:], format(1.7976931348623157e308, ".0f")[:20])
for spec in ("d", "x", "X", "o", "b", "c", "s", "y", "5d", ",d", "_x", ",n", "_n", ".,n", "._n", "ff", "<<", ".", ".f", "99999999999999999999", ".99999999999999999999f", ".2147483648f", ",_", "_,", ".,_", "._,", ",_f"):
    print(repr(spec), failed(lambda: format(1.5, spec)), end="; ")
print()

# ---- str
for spec in ("", "s", "5", "<5", ">5", "^5", "*<5", "*>5", "*^5", "é^5", ".0", ".1", ".2", ".5s", "5.1", "<5.1", "^7.2", "*^7.2s", "05", "010", "*>05", "00"):
    print(repr(spec), [format(v, spec) for v in ("", "a", "ab", "abcdef", "éè")])
for spec in ("d", "x", "f", "e", "c", "y", "=5", "*=5", "+", "-", " ", "+5", "#", "#5", "z", ",", "_", ".,", "._", "ss", "5d", "<<", ".", "99999999999999999999", ".99999999999999999999"):
    print(repr(spec), failed(lambda: format("a", spec)), end="; ")
print()

# ---- other types, a class's __format__, and format()
print(format(None), format([1]), format((1,)), format({1: 2}), format({1}), format(b"a"), format(int), format(print)[:9], failed(lambda: format(None, "x")), failed(lambda: format([1], "x")), failed(lambda: format(object(), "x")), failed(lambda: format(int, "x")), failed(lambda: format(b"a", "x")), format(range(1)), failed(lambda: format(range(1), "x")))


class Own:
    def __format__(self, spec: str) -> str:
        return "own[" + spec + "]"


class Bad:
    def __format__(self, spec: str) -> object:  # type: ignore[override]
        return 1


class Plain:
    def __str__(self) -> str:
        return "plain str"


class NoStr:
    pass


class I(int):
    pass


class F(float):
    pass


class FO(float):
    def __format__(self, spec: str) -> str:
        return "fo"

    def __float__(self) -> float:
        return 9.5


class IO(int):
    def __str__(self) -> str:
        return "io str"

    def __float__(self) -> float:
        return 9.5


print(format(Own()), format(Own(), "x"), f"{Own()}", f"{Own():y}", f"{Own()!s:.3}", failed(lambda: format(Bad())), format(Plain()), failed(lambda: format(Plain(), "x")), f"{Plain()}", format(I(5)), format(I(5), "x"), format(I(5), ""), format(F(1.5)), format(F(1.5), ".2f"), format(FO(1.5), "x"), format(IO(5)), format(IO(5), ""), format(IO(5), "d"), format(IO(5), "f"), format(IO(5), ".1e"), failed(lambda: format(1, 2)), failed(lambda: format(1, b"x")), failed(lambda: format(1, None)), failed(lambda: format()), failed(lambda: format(1, "", 2)), failed(lambda: format(1, format_spec="")), (5).__format__("x"), (5).__format__(""), (1.5).__format__(".2f"), "a".__format__("5"), True.__format__("d"), failed(lambda: (5).__format__(1)), failed(lambda: "a".__format__(1)), failed(lambda: (1.5).__format__(1)), failed(lambda: (5).__format__()), failed(lambda: int.__format__("a", "")), failed(lambda: str.__format__(1, "")), failed(lambda: float.__format__(1, "")), ascii("a"), ascii("é"), ascii(1), ascii([1, "é"]), ascii("Ā\U0001F600") if False else 0, failed(lambda: ascii()), failed(lambda: ascii(1, 2)))  # type: ignore[arg-type,call-arg]
x = 3.14159
w = 10
print(f"{x}", f"{x:.2f}", f"{x:{w}}", f"{x:{w}.{2}f}", f"{x!r}", f"{x!s}", f"{x!a}", f"{x!r:>10}", f"{'a':*^5}", f"{5:x}", f"{5:#x}", f"{5:05}", f"{1 + 1}", f"{x=}", f"{x=:.1f}", f"{x = }", f"{{}}", f"{{{5}}}", f"a{5}b{6}c", f"{'é':é^5}", f"{True}", f"{None}", f"{[1, 2]}", f"{(1,)}", f"{w:{'x'}}", f"{w:{'#'}{'x'}}")

# ---- str.format
print("{}".format(1), "{} {}".format(1, 2), "{0} {1}".format(1, 2), "{1} {0}".format(1, 2), "{0} {0}".format(1), "{a}".format(a=1), "{a} {b}".format(a=1, b=2), "{0} {a}".format(1, a=2), "{} {a} {}".format(1, 2, a=3), "".format(), "x".format(), "{{}}".format(), "{{{}}}".format(1), "{{0}}".format(1), "}}{{".format(), "a{}b".format(1), "é{}è".format("ê"), "{:5}".format(1), "{:<5}|{:>5}|{:^5}".format(1, 2, 3), "{0:5}".format(1), "{a:5}".format(a=1), "{!r}".format("a"), "{!s}".format("a"), "{!a}".format("é"), "{!r:>5}".format("a"), "{0!r}".format("a"), "{a!r}".format(a="a"), "{:{}}".format(1, 5), "{:{}{}}".format(1, "*", ">5") if False else 0, "{0:{1}}".format(1, 5), "{0:{a}}".format(1, a=5), "{a:{b}}".format(a=1, b=5), "{:{}.{}f}".format(1.5, 10, 2), "{0:{1}.{2}f}".format(1.5, 10, 2), "{:*^{}}".format("a", 5), "{!r:{}}".format("a", 5))  # type: ignore[str-format]


class Obj:
    attr = "attribute"
    inner = None

    def __init__(self) -> None:
        self.items = {"k": "value", 1: "one"}
        self.seq = [10, 20]

    def __getitem__(self, k: object) -> str:
        return "item " + repr(k)


o = Obj()
o.inner = o  # type: ignore[assignment]
print("{0.attr}".format(o), "{.attr}".format(o), "{a.attr}".format(a=o), "{0.items[k]}".format(o), "{0.items[1]}".format(o), "{0.seq[1]}".format(o), "{0.inner.inner.attr}".format(o), "{0[x]}".format(o), "{0[1]}".format(o), "{0[01]}".format(o), "{0[-1]}".format(o), "{0[1.5]}".format(o), "{0[a b]}".format(o), "{0[:]}".format(o), "{0[a!b]}".format(o), "{0[a:b]}".format(o), "{0[{]}".format(o), "{0.attr!r:>12}".format(o), "{[0]}".format([1]), "{[a]}".format({"a": 1}), "{0[0][0]}".format([[1]]), "{0[0]}".format("abc"), "{0[0]}".format((1,)), "{0[1]}".format({1: "dict int key"}), "{0[a]}".format({"a": "dict str key"}), "{ 0}".format(**{" 0": "space key"}), "{a b}".format(**{"a b": "space"}), "{é}".format(é=1) if False else 0, "{-1}".format(**{"-1": "neg"}), "{1a}".format(**{"1a": "mixed"}), "{0a}".format(**{"0a": 5}))  # type: ignore[attr-defined,str-format]
for s, a, k in (("{", (), {}), ("}", (), {}), ("{}{", (1,), {}), ("}{", (), {}), ("{0", (1,), {}), ("{0!", (1,), {}), ("{0!r", (1,), {}), ("{0!r:", (1,), {}), ("{0:", (1,), {}), ("{0:{", (1,), {}), ("{0:{}", (1, 2), {}), ("{0[", (1,), {}), ("{0[1", (1,), {}), ("{0[}", (1,), {}), ("{0.", (1,), {}), ("{0.}", (1,), {}), ("{0[]}", (1,), {}), ("{0..a}", (1,), {}), ("{0.[a]}", (1,), {}), ("{0[a]b}", ({"a": 1},), {}), ("{0[a].}", ({"a": 1},), {}), ("{0!x}", (1,), {}), ("{0!}", (1,), {}), ("{0!rr}", (1,), {}), ("{0!r x}", (1,), {}), ("{0{}}", (1,), {}), ("{{{}", (1,), {}), ("{}", (), {}), ("{0}", (), {}), ("{1}", (1,), {}), ("{a}", (), {}), ("{a}", (), {"b": 1}), ("{} {0}", (1,), {}), ("{0} {}", (1,), {}), ("{a.b}", (), {"a": 1}), ("{0.nope}", (1,), {}), ("{0[x]}", (1,), {}), ("{0[0]}", (1,), {}), ("{0[5]}", ([1],), {}), ("{0[a]}", ([1],), {}), ("{0[z]}", ({},), {}), ("{0:{1:{2}}}", (1, 2, 3), {}), ("{0:{1:{2:{3}}}}", (1, 2, 3, 4), {}), ("{:d}", ("a",), {}), ("{:s}", (1,), {}), ("{:x}", (1.5,), {}), ("{99999999999999999999}", (), {}), ("{0[99999999999999999999]}", ([],), {}), ("{0:{1}}", (1,), {}), ("{:{a}}", (1,), {}), ("{:{0}}", (1, 2), {})):
    print(repr(s), failed(lambda: s.format(*a, **k)), end="; ")
print()
print(failed(lambda: str.format()), failed(lambda: str.format(1)), str.format("{}", 1), "{} {}".format(*[1, 2]), "{a}".format(**{"a": 1}), failed(lambda: "{a}".format(**{1: 2})) if False else 0)  # type: ignore[arg-type,call-arg]

# ---- format_map
print("{a}".format_map({"a": 1}), "{a.real}".format_map({"a": 1}), "".format_map({}), "{{}}".format_map({}), "x".format_map(1), failed(lambda: "{a}".format_map(1)), failed(lambda: "{a}".format_map({})), failed(lambda: "{}".format_map({})), failed(lambda: "{0}".format_map({})), failed(lambda: "{}".format_map()), failed(lambda: "{}".format_map({}, {})), failed(lambda: "{}".format_map(a=1)), failed(lambda: str.format_map(1, {})))  # type: ignore[arg-type,call-arg]


class Missing(dict):  # type: ignore[type-arg]
    def __missing__(self, k: str) -> str:
        return "missing " + k


class Getter:
    def __getitem__(self, k: str) -> str:
        return "got " + k


print("{a}".format_map(Missing()), "{a:>12}".format_map(Missing()), "{a}".format_map(Getter()), "{a!r}".format_map(Getter()))

# ---- string.Formatter, and what _string gives it
import _string  # type: ignore[import-not-found]  # noqa: E402

print(list(_string.formatter_parser("")), list(_string.formatter_parser("a")), list(_string.formatter_parser("{}")), list(_string.formatter_parser("a{}b")), list(_string.formatter_parser("a{{b")), list(_string.formatter_parser("a}}b")), list(_string.formatter_parser("{0}")), list(_string.formatter_parser("{a.b[c]!r:>{w}}")), list(_string.formatter_parser("x{a}y{b}z")), list(_string.formatter_parser("{a:}")), list(_string.formatter_parser("{!r}")), type(_string.formatter_parser("")).__name__, failed(lambda: list(_string.formatter_parser("{"))), failed(lambda: list(_string.formatter_parser("}"))), failed(lambda: _string.formatter_parser(1)), failed(lambda: _string.formatter_parser()))
first, rest = _string.formatter_field_name_split("a.b[0][c].d")
print(first, list(rest), type(rest).__name__, _string.formatter_field_name_split("0")[0], _string.formatter_field_name_split("")[0], list(_string.formatter_field_name_split("")[1]), _string.formatter_field_name_split("0.a")[0], list(_string.formatter_field_name_split("0.a")[1]), failed(lambda: _string.formatter_field_name_split(1)), failed(lambda: list(_string.formatter_field_name_split("a[")[1])), failed(lambda: list(_string.formatter_field_name_split("a.")[1])), failed(lambda: list(_string.formatter_field_name_split("a[0]b")[1])))
f = string.Formatter()
print(f.format("{0} {a} {0.real}", 1, a=2), f.format("{:>5}", 1), f.format("{!r}", "a"), f.vformat("{0} {b}", (1,), {"b": 2}), list(f.parse("a{b}c")), f.get_field("0.real", (1,), {}), f.convert_field("a", "r"), f.format_field(1, "x"), failed(lambda: f.format("{0} {}", 1)), failed(lambda: f.format("{!x}", 1)), failed(lambda: f.format("{a}")), f.format("{{}}"), f.format("{:{}}", 1, 5), failed(lambda: f.format("{:{:{:{}}}}", 1, 2, 3, 4)))
print(string.ascii_letters, string.digits, string.hexdigits, string.octdigits, string.punctuation, repr(string.whitespace), repr(string.printable), string.capwords("hello  wORLD x"), string.capwords("a-b c-d", "-"), failed(lambda: string.capwords(1)))  # type: ignore[type-var]
