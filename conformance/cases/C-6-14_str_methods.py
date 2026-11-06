# clause: C-6-14
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/unicodeobject.c, Objects/unicodectype.c
"""str's methods on ASCII text: casing, padding, the predicates, removeprefix, splitlines and its line breaks,
expandtabs, and translate with what it asks a mapping and how often. Which of them hand back the same object is
visible too. A str beyond ASCII needs the Unicode database for most of this, and stays out of the case."""
# ruff: noqa: B015, B018, B023, RUF015, SIM300

def codes(v: object) -> object:
    return [ord(c) for c in v] if isinstance(v, str) else [codes(x) for x in v]  # type: ignore[attr-defined]


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- case
for s in ("", "a", "A", "1", " ", "abc", "ABC", "aBc", "Abc", "abC", "hello world", "HELLO WORLD", "Hello World", "hello-world's_x1y", "a1b2", "1a", "1A", "  leading", "trailing  ", "tab\tsep", "new\nline", "they're", "o'neil", "ÀB"[1:], "__dunder__", "x" * 3, "aA aA", "..a..", "\x00a", "a\x00b"):
    print(repr(s), repr(s.lower()), repr(s.upper()), repr(s.swapcase()), repr(s.capitalize()), repr(s.title()), repr(s.casefold()), s.islower(), s.isupper(), s.istitle(), s.isalpha(), s.isalnum(), s.isdigit(), s.isdecimal(), s.isnumeric(), s.isspace(), s.isprintable(), s.isidentifier(), s.isascii())

# ---- each ASCII character through every predicate and case
table = []
for c in range(128):
    ch = chr(c)
    table.append((c, ch.isalpha(), ch.isalnum(), ch.isdigit(), ch.isdecimal(), ch.isnumeric(), ch.isspace(), ch.isprintable(), ch.isidentifier(), ("a" + ch).isidentifier(), ch.islower(), ch.isupper(), ch.istitle(), ch.lower(), ch.upper(), ch.swapcase(), ch.title(), ch.capitalize(), ch.casefold(), len(("a" + ch + "b").splitlines()), ("a" + ch + "b").title()))
print(table)

# ---- padding
for s in ("", "a", "abc", "abcd", "é", "éè"):
    print(repr(s.center(0)), repr(s.center(1)), repr(s.center(2)), repr(s.center(5)), repr(s.center(6, "*")), repr(s.center(7, "é")), repr(s.ljust(0)), repr(s.ljust(5)), repr(s.ljust(5, "*")), repr(s.rjust(0)), repr(s.rjust(5)), repr(s.rjust(5, "é")), repr(s.zfill(0)), repr(s.zfill(5)))
print("-1".zfill(5), "+1".zfill(5), "--1".zfill(5), "1-".zfill(5), "-".zfill(5), "+".zfill(1), "".zfill(3), "é".zfill(3), "abc".center(-5), "abc".ljust(-5), "abc".rjust(-5), "abc".zfill(-5), "abc".center(True + 3), "abc".ljust(True + 3))
same = "abcdef"
print(same.center(3) is same, same.ljust(6) is same, same.rjust(1) is same, same.zfill(6) is same, same.removeprefix("x") is same, same.removesuffix("x") is same, same.removeprefix("") is same, same.removesuffix("") is same, same.expandtabs() is same, same.splitlines()[0] is same, same.translate({}) is same, same.lower() is same, same.upper() == same.upper(), same.__str__() is same, str(same) is same)
for f in (lambda: "a".center(), lambda: "a".center(1, 2, 3), lambda: "a".center("a"), lambda: "a".center(1.5), lambda: "a".center(2**70), lambda: "a".center(1, "ab"), lambda: "a".center(1, ""), lambda: "a".center(1, 1), lambda: "a".center(x=1), lambda: "a".ljust(), lambda: "a".ljust(1, "ab"), lambda: "a".ljust(1, 1), lambda: "a".rjust(), lambda: "a".rjust(1, 1), lambda: "a".zfill(), lambda: "a".zfill("a"), lambda: "a".zfill(1, 2), lambda: "a".zfill(x=1), lambda: "a".lower(1), lambda: "a".upper(1), lambda: "a".title(1), lambda: "a".capitalize(1), lambda: "a".casefold(1), lambda: "a".swapcase(1), lambda: "a".islower(1), lambda: "a".isupper(1), lambda: "a".isalpha(1), lambda: "a".isdigit(1), lambda: "a".isspace(1), lambda: "a".isidentifier(1), lambda: "a".isprintable(1), lambda: str.lower(1), lambda: str.lower(), lambda: str.isalpha(1), lambda: str.center(1, 1)):  # type: ignore[arg-type,call-arg]
    print(failed(f), end=" ")
print()

# ---- removeprefix, removesuffix
print("abc".removeprefix("a"), "abc".removeprefix("abc"), "abc".removeprefix("abcd"), "abc".removeprefix("b"), "abc".removesuffix("c"), "abc".removesuffix("abc"), "abc".removesuffix("zabc"), "abc".removesuffix("b"), "".removeprefix(""), "".removesuffix(""), "é1".removeprefix("é"), "1é".removesuffix("é"), failed(lambda: "a".removeprefix()), failed(lambda: "a".removeprefix(1)), failed(lambda: "a".removeprefix(b"a")), failed(lambda: "a".removesuffix(1)), failed(lambda: "a".removeprefix("a", "b")), failed(lambda: "a".removesuffix(x="a")))  # type: ignore[arg-type,call-arg]

# ---- splitlines
for s in ("", "a", "\n", "\r", "\r\n", "\n\r", "a\nb", "a\rb", "a\r\nb", "a\n", "\na", "a\n\nb", "a\vb", "a\fb", "a\x1cb", "a\x1db", "a\x1eb", "a\x1fb", "a\x85b", "a b", "a b", "a\x0bb\x0cc", "\r\r\n\n", "é\nè", "line1\nline2\r\nline3\rline4\n"):
    print(codes(s), codes(s.splitlines()), codes(s.splitlines(True)), codes(s.splitlines(keepends=True)), codes(s.splitlines(False)), codes(s.splitlines(1)), codes(s.splitlines(0)), codes(s.splitlines("")), codes(s.splitlines("x")), codes(s.splitlines([])))  # type: ignore[arg-type]
print(failed(lambda: "a".splitlines(1, 2)), failed(lambda: "a".splitlines(x=1)), failed(lambda: "a".splitlines(True, keepends=True)))  # type: ignore[arg-type,call-arg,misc]

# ---- expandtabs
for s in ("", "a", "\t", "a\tb", "ab\tc", "abcdefgh\ti", "abcdefghi\tj", "\t\t", "a\nb\tc", "a\rb\tc", "ab\n\tc", "é\tb", "éè\tb", "a\t", "\ta", "12345678\t"):
    print(repr(s.expandtabs()), repr(s.expandtabs(4)), repr(s.expandtabs(1)), repr(s.expandtabs(0)), repr(s.expandtabs(-1)), repr(s.expandtabs(tabsize=3)), repr(s.expandtabs(True)))
print(failed(lambda: "a".expandtabs("a")), failed(lambda: "a".expandtabs(1.5)), failed(lambda: "a".expandtabs(1, 2)), failed(lambda: "a".expandtabs(x=1)), failed(lambda: "a\t".expandtabs(2**70)), failed(lambda: "a".expandtabs(2**31)))  # type: ignore[arg-type,call-arg]

# ---- maketrans and translate
print(str.maketrans("ab", "cd"), str.maketrans("ab", "cd", "e"), str.maketrans({"a": 1, 98: "x", "c": None}), str.maketrans("", ""), str.maketrans("", "", "é"), "".maketrans("a", "b"), failed(lambda: str.maketrans("a")), failed(lambda: str.maketrans("a", "bc")), failed(lambda: str.maketrans(1, "b")), failed(lambda: str.maketrans("a", 1)), failed(lambda: str.maketrans("a", "b", 1)), failed(lambda: str.maketrans({"ab": 1})), failed(lambda: str.maketrans({1.5: 1})), failed(lambda: str.maketrans()), failed(lambda: str.maketrans("a", "b", "c", "d")), failed(lambda: str.maketrans(x=1)), failed(lambda: str.maketrans([])))  # type: ignore[arg-type,call-overload]
t = str.maketrans("abc", "xyz", "d")
print("abcdabcd".translate(t), "".translate(t), "ee".translate(t), "é".translate(t), "aéd".translate(t), "abc".translate({97: "long", 98: "", 99: None}), codes("abc".translate({97: "é", 98: 0x65E5})), "abc".translate({97: 98, 98: 97}), "abc".translate({97: True}), "abc".translate([]), "abc".translate({}), "\x61".translate({97: 0}), "abc".translate(["x"] * 98), failed(lambda: "abc".translate({97: 1.5})), failed(lambda: "abc".translate({97: -1})), failed(lambda: "abc".translate({97: 0x110000})), failed(lambda: "abc".translate({97: 2**70})), failed(lambda: "abc".translate({97: []})), failed(lambda: "abc".translate(1)), failed(lambda: "abc".translate(None)), failed(lambda: "abc".translate()), failed(lambda: "abc".translate(1, 2)), failed(lambda: "".translate(1)))  # type: ignore[arg-type,call-arg,dict-item]


class Asks:
    def __init__(self, answers: dict[int, object]) -> None:
        self.answers = answers
        self.asked: list[int] = []

    def __getitem__(self, k: int) -> object:
        self.asked.append(k)
        if k in self.answers:
            return self.answers[k]
        raise LookupError(k)


# the ASCII path remembers an answer it can keep; what leaves it goes on one lookup at a time
for s, answers in (("aabbaa", {}), ("aabbaa", {97: 98}), ("aabbaa", {97: None}), ("aabbaa", {97: "x"}), ("aabbaa", {97: "xy"}), ("aabbaa", {98: "xy"}), ("aabbaa", {97: 0x65E5}), ("aabbaa", {98: "é"}), ("aabbcc", {98: "xy", 97: None}), ("aaxbbxaa", {120: None, 97: "pq"}), ("xxaxx", {120: None, 97: "pq"}), ("éaéa", {97: None}), ("éaéa", {233: None}), ("éaéb", {233: None, 97: None, 98: "z"}), ("ab", {97: 200})):
    asks = Asks(answers)  # type: ignore[arg-type]
    print(codes(s.translate(asks)), asks.asked)  # type: ignore[arg-type]


class Raises:
    def __getitem__(self, k: int) -> object:
        raise KeyError(k)


class Fails:
    def __getitem__(self, k: int) -> object:
        raise ValueError(k)


class IndexFails:
    def __getitem__(self, k: int) -> object:
        raise IndexError(k)


print("ab".translate(Raises()), "ab".translate(IndexFails()), failed(lambda: "ab".translate(Fails())), "é".translate(Raises()), failed(lambda: "é".translate(Fails())))  # type: ignore[arg-type]
print(sorted(set(vars(str)) & {"__getnewargs__", "__str__"}), "abc".__getnewargs__(), "abc".__str__(), failed(lambda: "a".__getnewargs__(1)), failed(lambda: "a".__str__(1)), failed(lambda: str.__str__(1)), failed(lambda: str.__getnewargs__(1)))  # type: ignore[arg-type,call-arg]
