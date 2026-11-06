# clause: C-6-16
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/unicode_format.c
"""str % args: every conversion with its flags, width and precision; * from the arguments; mappings and keys; what
counts as a mapping and what is left over; and the order in which the arguments are asked for what they are."""
# ruff: noqa: B015, B018, B023, E742, F501, F503, F504, F506, F507, F508, F509, PLE1300, RUF015, UP031


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- conversions, with each flag
for conv in "sradiuoxXeEfFgGc":
    for flags in ("", "-", "+", " ", "#", "0", "-0", "+0", " 0", "#0", "-#", "+#", "+ ", "- ", "+-"):
        for rest in ("", "5", "10", ".0", ".2", ".5", "8.3", "2.1", "012.3"):
            fmt = "%" + flags + rest + conv
            row = []
            for v in ((65, -65, 0, 2**70, True, 1.5, -1.5, 0.0, "a", "ab", [1], None) if conv in "sra" else (65, -65, 0, 255, 2**70, -(2**70), True) if conv in "oxX" else (65, -65, 0, 255, 2**70, True, 1.5, -1.5, 0.0, 1e20) if conv in "diu" else (1.5, -1.5, 0.0, -0.0, 1e20, 1e-20, 2.5, 65, -65, True, float("inf"), float("-inf"), float("nan")) if conv in "eEfFgG" else (65, 0x10FFFF if False else 90, "a", "é", True)):
                try:
                    row.append(fmt % (v,))
                except (TypeError, ValueError, OverflowError) as exc:
                    row.append(type(exc).__name__)
            print(repr(fmt), row)

# ---- what is plain text
print("" % (), "a" % (), "%%" % (), "a%%b" % (), "%%%%" % (), "é%%è" % (), "%s%%" % 1, "%%%s" % 1, "%s %s" % (1, 2), "%s" % 1, "%s" % (1,), "%s" % ((1, 2),), "%s" % [1, 2], "%s" % {"a": 1}, "%s" % None, "a%sb%sc" % (1, 2), "%d%s" % (1, "a"), "é%sè" % "ê", "%s" % "é", "%5s|" % "é", "%-5s|" % "é", "%.1s" % "éè", "%c" % "é", "%c" % 233, "%5c|" % 65, "%-5c|" % 65, "%05c|" % 65, "%.0c|" % 65, "%ld" % 1, "%hd" % 1, "%Ld" % 1, "%ls" % "a", "%hs" % "a", "%l5d" % 1 if False else 0)

# ---- * from the arguments
print("%*d" % (5, 1), "%-*d|" % (5, 1), "%*d|" % (-5, 1), "%.*f" % (2, 1.5), "%.*f" % (-2, 1.5), "%*.*f" % (8, 2, 1.5), "%*s" % (3, "a"), "%.*s" % (1, "ab"), "%*c" % (3, "a"), "%*d" % (True, 1), "%0*d" % (5, 1), "%+*d" % (5, 1), failed(lambda: "%*d" % ("a", 1)), failed(lambda: "%*d" % (1.5, 1)), failed(lambda: "%.*f" % ("a", 1.5)), failed(lambda: "%*d" % (2**70, 1)), failed(lambda: "%.*f" % (2**70, 1.5)), failed(lambda: "%.*f" % (2**31, 1.5)), failed(lambda: "%*d" % (5,)), failed(lambda: "%*d" % 5), failed(lambda: "%*" % (5,)), failed(lambda: "%.*" % (5,)))  # type: ignore[str-format]

# ---- mappings
m = {"a": 1, "b": "x", "c": 1.5, "(n)": "nested", "": "empty", "é": "accent"}
print("%(a)d" % m, "%(b)s" % m, "%(c).2f" % m, "%(a)5d|" % m, "%(a)-5d|" % m, "%(a)05d" % m, "%(b)r" % m, "%(a)s %(b)s %(a)s" % m, "%((n))s" % m, "%()s" % m, "%(é)s" % m, "%%" % m, "x" % m, "%(a)s%%" % m, "%(a)x" % m, "%(c)e" % m, "%(a)c" % {"a": 65}, "%(a)c" % {"a": "z"})  # type: ignore[str-format]
for fmt, arg in (("%(a)s", {}), ("%(a)s", 1), ("%(a)s", (1,)), ("%(a)s", "a"), ("%(a)s", [1]), ("%(a", {"a": 1}), ("%(", {"a": 1}), ("%(a)", {"a": 1}), ("%(a)s %s", {"a": 1}), ("%s %(a)s", {"a": 1}), ("%(a)*d", {"a": 1}), ("%(a).*f", {"a": 1}), ("%(a)d", {"a": "x"}), ("%(a)x", {"a": 1.5}), ("%(a)f", {"a": "x"}), ("%(a)c", {"a": "xy"}), ("%(a)c", {"a": -1})):
    print(repr(fmt), failed(lambda: fmt % arg), end="; ")
print()


class Getter:
    def __getitem__(self, k: object) -> str:
        return "got " + repr(k)


class Seqish:
    def __len__(self) -> int:
        return 1


class Str:
    def __str__(self) -> str:
        return "as str"

    def __repr__(self) -> str:
        return "as repr"


class Idx:
    def __index__(self) -> int:
        return 66


class Flt:
    def __float__(self) -> float:
        return 2.5


class Int:
    def __int__(self) -> int:
        return 7


class IntIdx:
    def __int__(self) -> int:
        return 7

    def __index__(self) -> int:
        return 8


class Rmod:
    def __rmod__(self, o: object) -> str:
        return "rmod " + repr(o)


class I(int):
    def __str__(self) -> str:
        return "i str"

    def __repr__(self) -> str:
        return "i repr"

    def __index__(self) -> int:
        return 99


class F(float):
    def __float__(self) -> float:
        return 9.5

    def __str__(self) -> str:
        return "f str"


print("%(a)s" % Getter(), "%s" % Getter() != "", "x" % Getter(), "%%" % Getter(), failed(lambda: "%s %s" % Getter()), "x" % [], "x" % [1], "x" % {}, "x" % {"a": 1}, "x" % range(1), "x" % b"", "x" % bytearray(), "x" % Getter(), failed(lambda: "x" % 1), failed(lambda: "x" % "a"), failed(lambda: "x" % (1,)), failed(lambda: "x" % (1, 2)), failed(lambda: "x" % None), failed(lambda: "x" % Seqish()), failed(lambda: "%s" % ()), failed(lambda: "%s %s" % (1,)), failed(lambda: "%s %s" % 1), failed(lambda: "%s" % (1, 2)), failed(lambda: "%d %d" % (1, 2, 3)), failed(lambda: "x" % 1.5), failed(lambda: "x" % ((),)))  # type: ignore[str-format]
print("%s" % Str(), "%r" % Str(), "%a" % Str(), "%d" % Idx(), "%x" % Idx(), "%c" % Idx(), "%f" % Idx(), "%d" % Flt() if False else 0, "%f" % Flt(), "%e" % Flt(), "%d" % Int(), "%d" % IntIdx(), "%x" % IntIdx(), "%f" % IntIdx() if False else 0, failed(lambda: "%x" % Int()), failed(lambda: "%f" % Int()), failed(lambda: "%c" % Int()), failed(lambda: "%x" % Flt()), failed(lambda: "%c" % Flt()), "%s" % I(1), "%r" % I(1), "%d" % I(1), "%x" % I(1), "%c" % I(65), "%f" % I(1), "%s" % F(1.5), "%f" % F(1.5), "%d" % F(1.5), "%s" % True, "%d" % True, "%x" % True, "%f" % True, "%c" % True, "%d" % 1.9, "%d" % -1.9, "%i" % 1e20, "%u" % 2.5, failed(lambda: "%d" % float("inf")), failed(lambda: "%d" % float("nan")), failed(lambda: "%x" % 1.5), failed(lambda: "%o" % 1.5), failed(lambda: "%c" % 1.5), failed(lambda: "%d" % "1"), failed(lambda: "%x" % "1"), failed(lambda: "%f" % "1"), failed(lambda: "%c" % "ab"), failed(lambda: "%c" % ""), failed(lambda: "%c" % -1), failed(lambda: "%c" % 0x110000), failed(lambda: "%c" % 2**70), failed(lambda: "%d" % None), failed(lambda: "%f" % None), failed(lambda: "%d" % [1]), 1 % Rmod(), failed(lambda: 1 % "a"), failed(lambda: None % "a"), failed(lambda: [] % "a"))  # type: ignore[operator,str-format]
for fmt in ("%", "%5", "%-", "%.", "%.5", "%(a", "%y", "%Y", "%k", "%z", "%!", "%,", "%'", '%"', "%\n", "%\x00", "%\x7f", "%l", "%h", "%L", "%ll", "%99999999999999999999d", "%.99999999999999999999f", "%.2147483648f", "% ", "%+", "%#", "%0", "%5.", "%5.2", "%5.2l", "%1$s", "%v"):
    print(repr(fmt), failed(lambda: fmt % (1,)), end="; ")
print()
print("abc".__mod__(()), "%s".__mod__(1), "%s".__rmod__("x") if False else 0, "x".__rmod__("%s"), "x".__rmod__(1), "%d".__mod__(1), failed(lambda: "a".__mod__()), failed(lambda: "a".__mod__(1, 2)), failed(lambda: str.__mod__(1, 2)), failed(lambda: "a".__rmod__()), failed(lambda: str.__rmod__(1, 2)))  # type: ignore[attr-defined,call-arg,operator]
s = "%s"
s %= 1
t = "%d %d"
t %= (1, 2)
print(s, t, "%.3s" % "abcdef", "%10.3s|" % "abcdef", "%-10.3s|" % "abcdef", "%.0s|" % "abc", "%.3r" % "abc", "%.3a" % "é", "%010s" % "a", "%-010s|" % "a", "%+s" % "a", "% s" % "a", "%#s" % "a", "%5r" % 1, "%-5a|" % 1, "%+5s|" % 1, "%.2d" % 5, "%.5d" % -5, "%.5x" % 255, "%#.5x" % 255, "%#.5o" % 8, "%#10.5x" % 255, "%-#10.5x|" % 255, "%0#10x" % 255, "%0#10.5x" % 255, "%+#x" % 255, "% #x" % 255, "%+#X" % 255, "%#o" % -8, "%#x" % -255, "%#X" % -255, "%0#10x" % -255, "%+010.3f" % 1.5, "%-+10.3f|" % 1.5, "%- 10.3f|" % 1.5, "%#.0f" % 1.0, "%#.0e" % 1.0, "%#g" % 1.0, "%#.3g" % 1.0, "%g" % 1e20, "%g" % 1e-5, "%.0g" % 1.5, "%G" % 1e20, "%E" % 1.5, "%F" % float("inf"), "%E" % float("nan"), "%.1000f" % 1.5 == format(1.5, ".1000f"), "%010f" % float("inf"), "%-10f|" % float("nan"), "%+f" % float("inf"), "%+f" % float("nan"), "% f" % float("nan"), "%f" % -0.0, "%g" % -0.0, "%e" % -0.0, "%d" % -0.0)
