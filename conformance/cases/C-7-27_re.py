# clause: C-7-27
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_sre/sre.c, Modules/_sre/sre_lib.h, Lib/re
"""re over _sre: what each construct of the syntax matches, greedy, lazy and possessive; groups, references and lookaround; flags; str and bytes;
beyond ASCII; Pattern and Match with everything they say of themselves; sub with templates and callables; split, findall, finditer, the scanner; and
what a bad pattern raises, with what its error carries."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, RUF001, RUF003, SLF001
import _sre  # type: ignore[import-not-found]
import copy
import re


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def shown(match):  # type: ignore[no-untyped-def]
    if match is None:
        return None
    return (match.span(), match.group(), match.groups(), match.groupdict(), match.lastindex, match.lastgroup, match.regs)


TEXTS = ["", "a", "abc", "aaa", "abcabc", "foo bar", "foo\nbar\n", "Hello, World!", "12 34", "a1b2", "x_y z", "aXbXc", "ab\ncd", "   ", "\t\n", "é", "Éa", "日本語 text", "ÀÉÎ", "ß", "ſ", "K", "٣", "a٣", "\u2028x", "\x85y", "(a)", "a.b", "a|b"]
PATTERNS = ["", "a", "abc", ".", ".*", ".+", ".?", "a*", "a+", "a?", "a{2}", "a{2,}", "a{,2}", "a{1,2}", "a*?", "a+?", "a??", "a{1,2}?", "a*+", "a++", "a?+", "a{1,2}+", "^", "$", "^a", "a$", r"\A", r"\Z", r"\z", r"\Aa", r"a\Z", r"\b", r"\B", r"\ba", r"a\b", r"\d", r"\D", r"\s", r"\S", r"\w", r"\W", r"\d+", r"\w+", r"\s+", "[abc]", "[^abc]", "[a-c]", "[^a-c]", "[a-]", "[]a]", "[^]a]", r"[\d]", r"[\w]", r"[\s]", r"[\D]", r"[\W]", r"[\S]", r"[\d\s]", "[a-zA-Z]", "[é]", "[à-ÿ]", "[日本]", "a|b", "a|b|c", "ab|cd", "(a)", "(a)(b)", "(a)|(b)", "(a)?", "(a)*", "(a)+", "(a|b)+", "(?:a)", "(?:a|b)+", "(?P<x>a)", "(?P<x>a)(?P<y>b)?", r"(a)\1", r"(?P<x>a)(?P=x)", r"(a)|\1", "(?=a)", "(?!a)", "(?<=a)", "(?<!a)", "(?<=a)b", "(?<!a)b", "a(?=b)", "a(?!b)", "(a)?(?(1)b|c)", "(?P<n>a)?(?(n)b)", "(?>a+)", "(?>a|ab)c", "(a+)+", "(a*)*", "(a*)+", "(a|b)*?c", "(?i)a", "(?i:a)b", "(?-i:a)", "(?s).", "(?m)^b", "(?x) a b", "(?a)\\w", "(?s:.)", "(?m:^)b", "(?a:\\w)", "(?u)\\w", "\\.", "\\(", "\\|", "\\x61", "\\141", "\\u0061", "\\U00000061", "\\n", "\\t", "\\s\\S", ".{2}", "(.)\\1", "(.)(.)\\2\\1", "\\w+\\s\\w+", "(\\w+) (\\w+)", "^(\\w+)$", "a.c", "a.*c", "a.*?c", "[a-c]+", "[a-c]+?", "(?:[a-c]){2}", "(ab)+", "(ab){2}", "(ab)*c"]
for pattern in PATTERNS:
    compiled = re.compile(pattern)
    print(repr(pattern), compiled.groups, dict(compiled.groupindex))
    for text in TEXTS:
        print(repr(text), shown(compiled.match(text)), shown(compiled.fullmatch(text)), shown(compiled.search(text)), compiled.findall(text), compiled.split(text), compiled.subn("<>", text))  # type: ignore[no-untyped-call]

# ---- flags
FLAGGED = [("a", re.I), ("A", re.I), ("é", re.I), ("É", re.I), ("ß", re.I), ("ſ", re.I), ("s", re.I), ("K", re.I), ("K", re.I), ("k", re.I), ("[a-c]", re.I), ("[A-C]", re.I), ("[é]", re.I), ("[^a]", re.I), (r"\w", re.A), (r"\W", re.A), (r"\d", re.A), (r"\s", re.A), (r"\b", re.A), ("a", re.A | re.I), ("é", re.A | re.I), ("k", re.A | re.I), ("^a", re.M), ("a$", re.M), ("$", re.M), ("^", re.M), (".", re.S), (".+", re.S), ("a b # c\n d", re.X), ("[ ] a", re.X), (r"a\ b", re.X), ("(a)", re.I | re.M | re.S | re.X), (r"(a)\1", re.I), (r"(é)\1", re.I), (r"(a)(?i:\1)", 0), (r"\w+", re.I)]
FLAG_TEXTS = ["a", "A", "é", "É", "ß", "ẞ", "s", "S", "ſ", "k", "K", "K", "b", "\n", "a\nb", "b\na", "aA", "éÉ", " ", "ab d", "a b", "٣", "_"]
for pattern, flags in FLAGGED:
    compiled = re.compile(pattern, flags)
    print(repr(pattern), flags, compiled.flags, repr(compiled))
    for text in FLAG_TEXTS:
        print(repr(text), shown(compiled.search(text)), compiled.findall(text))  # type: ignore[no-untyped-call]

# ---- bytes
BYTE_PATTERNS = [b"", b"a", b".", b"a*", b"[a-c]+", rb"\d+", rb"\w+", rb"\s+", rb"\b", rb"\W", b"(a)(b)?", rb"(?P<x>a)(?P=x)", b"^a$", b"\xe9", b"[\xe0-\xff]", rb"\x61", b"(?i)A", b"(?i)\xc9", b"(?L)a", b"(?a)a"]
BYTE_TEXTS = [b"", b"a", b"abc", b"12 34", b"foo\nbar", b"\xe9", b"\xc9a", b"aa", b"aXb"]
for pattern in BYTE_PATTERNS:  # type: ignore[assignment]
    compiled = re.compile(pattern)
    print(pattern, compiled.flags, compiled.groups, repr(compiled))
    for text in BYTE_TEXTS:  # type: ignore[assignment]
        print(text, shown(compiled.search(text)), compiled.findall(text), compiled.split(text), compiled.subn(b"<>", text), shown(compiled.search(bytearray(text))), compiled.sub(b"x", bytearray(text)))  # type: ignore[arg-type,call-overload,no-untyped-call]
print(re.compile(rb"\w", re.L).flags, re.compile(rb"\w", re.L).search(b"a").group(), re.compile(b"a", re.I | re.L).search(b"A").group(), re.compile(rb"\b", re.L).search(b" a").span(), re.compile(rb"[a]", re.I | re.L).search(b"A").group())  # type: ignore[union-attr]
print(failed(lambda: re.compile("a").search(b"a")), failed(lambda: re.compile(b"a").search("a")), failed(lambda: re.compile("a").search(1)), failed(lambda: re.compile("a", re.L)), failed(lambda: re.compile(b"a", re.U)), failed(lambda: re.compile("a", re.A | re.U)), failed(lambda: re.compile(1)), failed(lambda: re.compile("a", "b")), failed(lambda: re.compile(re.compile("a"), re.I)), re.compile(re.compile("a")).pattern, failed(lambda: re.compile("a").sub(b"x", "a")), failed(lambda: re.compile(b"a").sub("x", b"a")), failed(lambda: re.compile("a").search(bytearray(b"a"))))  # type: ignore[call-overload,no-untyped-call]

# ---- what a pattern says of itself
pattern = re.compile(r"(?P<first>\w+) (?P<second>\w+)?", re.I | re.M)  # type: ignore[assignment]
print(pattern.pattern, pattern.flags, pattern.groups, pattern.groupindex, type(pattern.groupindex).__name__, repr(pattern), str(pattern), type(pattern).__name__, type(pattern).__module__, type(pattern).__qualname__, type(pattern), re.Pattern is type(pattern), failed(lambda: re.Pattern()), failed(lambda: type("X", (re.Pattern,), {})), failed(lambda: setattr(pattern, "flags", 1)), failed(lambda: setattr(pattern, "x", 1)), failed(lambda: pattern.nothing))  # type: ignore[attr-defined,comparison-overlap,no-untyped-call]
print(hash(pattern) == hash(re.compile(r"(?P<first>\w+) (?P<second>\w+)?", re.I | re.M)), pattern == re.compile(r"(?P<first>\w+) (?P<second>\w+)?", re.I | re.M), pattern != re.compile(r"(?P<first>\w+) (?P<second>\w+)?", re.I), pattern == 1, pattern != 1, failed(lambda: pattern < pattern), copy.copy(pattern) is pattern, copy.deepcopy(pattern) is pattern, pattern is re.compile(pattern), re.Pattern[str], re.Match[bytes], {pattern: 1}[pattern], re.compile("a", re.I) == re.compile("A", re.I), re.compile("a") == re.compile(b"a"))  # type: ignore[comparison-overlap,no-untyped-call]
for flags in (0, re.I, re.M, re.S, re.X, re.A, re.I | re.M, re.DEBUG if False else 0):
    print(repr(re.compile("a", flags)))
print(repr(re.compile(b"a", re.L)), repr(re.compile(b"a")), repr(re.compile("x" * 300)), repr(re.compile("é")), repr(re.compile("a'b")), re.compile("a'b").pattern)
print(re.I, re.IGNORECASE, re.M, re.S, re.X, re.A, re.U, re.L, re.NOFLAG, repr(re.I), repr(re.I | re.M), str(re.I | re.M), int(re.I), re.I | 1, type(re.I).__name__, re.RegexFlag.IGNORECASE, re.I in (re.I | re.M), re.I & re.M, ~re.I & re.I, list(re.RegexFlag)[:3], re.RegexFlag(2), re.RegexFlag(10), failed(lambda: re.RegexFlag("x")))  # type: ignore[arg-type,no-untyped-call]

# ---- what a match says of itself
match = re.compile(r"(?P<a>a)(?P<b>x)?(c)").search("zzacz", 1)
print(repr(match), str(match), type(match).__name__, type(match).__module__, re.Match is type(match), match.string, match.re is not None, match.pos, match.endpos, match.lastindex, match.lastgroup, match.regs, match.group(), match.group(0), match.group(1), match.group(2), match.group(3), match.group("a"), match.group("b"), match.group(1, 2), match.group("a", 3), match[0], match[1], match["a"], match["b"], match.groups(), match.groups("d"), match.groups(default="e"), match.groupdict(), match.groupdict("d"), match.groupdict(default="e"), match.start(), match.end(), match.span(), match.start(1), match.end(1), match.span(1), match.start(2), match.end(2), match.span(2), match.start("a"), match.span("a"), match.span("b"), match.expand(r"\1|\g<a>|\g<3>"), match.expand(r"\n\t\\"), bool(match), copy.copy(match) is match, copy.deepcopy(match) is match)  # type: ignore[index,union-attr]
print(failed(lambda: match.group(4)), failed(lambda: match.group("z")), failed(lambda: match.group(-1)), failed(lambda: match.group(1.5)), failed(lambda: match.group(None)), failed(lambda: match[4]), failed(lambda: match["z"]), failed(lambda: match.start(4)), failed(lambda: match.span("z")), failed(lambda: match.end(9)), failed(lambda: match.expand(r"\9")), failed(lambda: match.expand(r"\g<z>")), failed(lambda: match.expand(1)), failed(lambda: match.expand(rb"a")), match.expand("plain"), failed(lambda: setattr(match, "pos", 1)), failed(lambda: setattr(match, "x", 1)), failed(lambda: setattr(match, "regs", 1)), failed(lambda: re.Match()), failed(lambda: match.groups(1, 2)), failed(lambda: match.groupdict(1, 2)), failed(lambda: match.nothing), failed(lambda: type("X", (re.Match,), {})), failed(lambda: len(match)), failed(lambda: iter(match)), failed(lambda: match[0:1]), failed(lambda: match.start(1, 2)), failed(lambda: match.__copy__(1)), failed(lambda: match.__deepcopy__()), match.__copy__() is match, match.__deepcopy__({}) is match)  # type: ignore[arg-type,call-arg,call-overload,index,no-untyped-call,union-attr]


class Index:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 1


print(match.group(Index()), match[Index()], match.start(Index()), match.group(True), match.group(False))  # type: ignore[arg-type,call-overload,index,union-attr]
for text, pos, endpos in (("abcabc", 0, 6), ("abcabc", 1, 6), ("abcabc", 3, 6), ("abcabc", 0, 3), ("abcabc", -1, 3), ("abcabc", 100, 200), ("abcabc", 5, 2), ("abcabc", 0, -1), ("abcabc", 2**70 if False else 3, 4)):
    compiled = re.compile("a|b|^c|c$")
    print(shown(compiled.search(text, pos, endpos)), shown(compiled.match(text, pos, endpos)), shown(compiled.fullmatch(text, pos, endpos)), compiled.findall(text, pos, endpos), [m.span() for m in compiled.finditer(text, pos, endpos)], repr(compiled.search(text, pos, endpos)), None if compiled.search(text, pos, endpos) is None else (compiled.search(text, pos, endpos).pos, compiled.search(text, pos, endpos).endpos))  # type: ignore[no-untyped-call,union-attr]
compiled = re.compile("a")
print(shown(compiled.search(string="a", pos=0, endpos=1)), shown(compiled.match("a", endpos=1)), shown(compiled.fullmatch("a", pos=0)), compiled.findall("a", pos=0), failed(lambda: compiled.search()), failed(lambda: compiled.search("a", "b")), failed(lambda: compiled.search("a", 2**70)), failed(lambda: compiled.search("a", 0, 1, 2)), failed(lambda: compiled.search("a", nothing=1)), failed(lambda: compiled.search("a", string="a")), failed(lambda: compiled.match()), failed(lambda: compiled.fullmatch()), failed(lambda: compiled.findall()), failed(lambda: compiled.finditer()), failed(lambda: compiled.split()), failed(lambda: compiled.sub("a")), failed(lambda: compiled.subn("a")), failed(lambda: compiled.split("a", "b")), failed(lambda: compiled.sub("a", "b", "c")), failed(lambda: compiled.scanner()))  # type: ignore[attr-defined,call-overload,no-untyped-call]

# ---- sub
for pattern, repl, text in (("a", "x", "banana"), ("a", "", "banana"), ("", "-", "abc"), ("x*", "-", "abxd"), (r"\b", "|", "foo bar"), (r"(\w+) (\w+)", r"\2 \1", "hello world"), (r"(?P<f>\w+) (?P<s>\w+)", r"\g<s> \g<f>", "hello world"), (r"(a)", r"\g<1>0", "a"), (r"(a)", r"\g<0>\g<0>", "a"), ("a", r"\n\t\\", "a"), ("a", r"\x" if False else "b", "a"), (r"(a)|b", r"\1", "ab"), (r"(a)|b", "[\\1]", "ab"), ("é", "e", "été"), ("e", "é", "ete"), ("日", "月", "日本日"), (r"\s+", " ", "a  b\t\nc"), ("a", "\\\\", "a"), ("(?m)^", "> ", "a\nb"), ("$", "!", "a\n"), (r"(?<=a)", "-", "aab"), ("a|", "x", "baac"), ("(a)|(b)", r"\2\1", "ab")):
    print(repr(pattern), repr(repl), repr(text), re.sub(pattern, repl, text), re.subn(pattern, repl, text), re.sub(pattern, repl, text, count=1), re.subn(pattern, repl, text, count=2), type(re.sub(pattern, repl, text)).__name__)
print(re.sub("a", lambda m: m.group().upper(), "banana"), re.sub("a", lambda m: "", "banana"), re.sub("a", lambda m: None, "banana"), re.subn(r"(\w)", lambda m: m.group(1) * 2, "ab"), re.sub("(a)", lambda m: str(m.span()), "aa"), failed(lambda: re.sub("a", lambda m: 1, "a")), failed(lambda: re.sub("a", lambda m: b"x", "a")), failed(lambda: re.sub("a", 1, "a")), failed(lambda: re.sub("a", None, "a")), failed(lambda: re.sub("a", "x", 1)), failed(lambda: re.sub("a", r"\9", "a")), failed(lambda: re.sub("a", r"\g<z>", "a")), failed(lambda: re.sub("a", r"\g<", "a")), failed(lambda: re.sub("a", "\\", "a")), failed(lambda: re.sub("a", r"\q", "a")), failed(lambda: re.sub("a", r"\g<-1>", "a")), failed(lambda: re.sub("(a)", r"\2", "a")), failed(lambda: re.sub("a", lambda m: 1 / 0, "a")), re.sub(b"a", b"x", b"banana"), re.sub(b"a", lambda m: b"y", b"banana"), re.sub(b"(a)", rb"\1\1", b"a"), re.sub(b"a", bytearray(b"z"), b"a"), re.sub(b"a", b"x", bytearray(b"a")), type(re.sub(b"z", b"x", b"a")).__name__, type(re.sub(b"z", b"x", bytearray(b"a"))).__name__, re.sub("z", "x", "abc") is not None, re.sub("a", "x", "abc", count=0), re.subn("a", "x", "aaa", count=-1), re.sub(pattern="a", repl="b", string="a"), re.compile("a").sub(repl="b", string="a"), re.compile("a").subn(repl="b", string="a", count=1))  # type: ignore[arg-type,call-overload,no-untyped-call,return-value]


class Text(str):
    pass


print(type(re.sub("z", "x", Text("abc"))).__name__, type(re.sub("a", "x", Text("abc"))).__name__, type(re.search("a", Text("abc")).group()).__name__, type(re.search("a", Text("abc")).string).__name__, type(re.split("z", Text("abc"))[0]).__name__, type(re.findall("abc", Text("abc"))[0]).__name__, type(re.sub("a", Text("x"), "a")).__name__, type(re.sub("a", Text("x"), "ab")).__name__, re.search(Text("a"), "a").group(), re.compile(Text("a")).pattern.__class__.__name__, type(re.search("(a)", Text("a")).group(1)).__name__)  # type: ignore[union-attr]

# ---- split, findall, finditer, the scanner
for pattern, text in ((r"\s+", "a b  c"), (",", "a,b,c"), (",", ""), (",", ",a,"), (r"(,)", "a,b"), (r"(,)|(;)", "a,b;c"), (r"\b", "a b"), ("", "abc"), ("x*", "axbc"), ("(x)*", "axb"), ("^", "a\nb"), ("(?m)^", "a\nb"), ("$", "a"), ("é", "aéb")):
    print(repr(pattern), repr(text), re.split(pattern, text), re.split(pattern, text, maxsplit=1), re.findall(pattern, text), [m.span() for m in re.finditer(pattern, text)])
iterator = re.finditer("a", "aa")
print(type(iterator).__name__, iter(iterator) is iterator, next(iterator).span(), next(iterator).span(), failed(lambda: next(iterator)), list(iterator), list(re.finditer("a", "b")), [m.group() for m in re.compile("a").finditer("aXa", 1)], [m.pos for m in re.compile("a").finditer("aXa", 1, 3)], [m.endpos for m in re.compile("a").finditer("aXa", 1, 3)])  # type: ignore[no-untyped-call]
print(re.findall("(a)(b)?", "ab a"), re.findall("(a)", "aa"), re.findall("a", "aa"), re.findall("(?:a)", "a"), re.findall("()", "a"), re.findall("(a)|(b)", "ab"), re.findall(b"(a)(b)?", b"ab a"), re.findall(b"a", bytearray(b"a")), type(re.findall(b"a", bytearray(b"a"))[0]).__name__)
scanner = re.compile("a").scanner("aXa")  # type: ignore[attr-defined]
print(type(scanner).__name__, type(scanner).__module__, repr(type(scanner)), scanner.pattern.pattern, scanner.match().span(), scanner.match(), scanner.search(), scanner.search(), scanner.match(), failed(lambda: type(scanner)()), failed(lambda: scanner.search(1)), failed(lambda: scanner.match(1)), failed(lambda: scanner.search(x=1)), failed(lambda: setattr(scanner, "pattern", 1)))  # type: ignore[no-untyped-call]
scanner = re.compile("a*").scanner("aab")  # type: ignore[attr-defined]
print(scanner.search().span(), scanner.search().span(), scanner.search().span(), scanner.search(), scanner.search())
scanner = re.compile("a").scanner("aXa", 1, 2)  # type: ignore[attr-defined]
print(scanner.search(), scanner.search())
lexer = re.Scanner([(r"\d+", lambda s, t: ("n", t)), (r"\s+", None), (r"\w+", lambda s, t: ("w", t))])  # type: ignore[attr-defined]
print(lexer.scan("12 ab !"))
print(re.escape("a.b*c"), re.escape(b"a.b"), re.escape("é ü"), re.escape("-_ "), failed(lambda: re.escape(1)), re.purge(), re.match("a", "a").group(), re.fullmatch("a", "a").group(), re.search("a", "a").group(), re.prefixmatch("a", "a").group(), re.compile("a").prefixmatch("a").group(), re.template if False else 0, re.match("(?i)A", "a").group(), re.match("A", "a", re.I).group(), re.match("A", "a", flags=re.I).group(), re.findall("A", "a", re.I), re.split("A", "bab", flags=re.I), re.sub("A", "x", "a", flags=re.I), re.subn("A", "x", "a", flags=re.I), [m.group() for m in re.finditer("A", "a", re.I)])  # type: ignore[func-returns-value,no-untyped-call,type-var,union-attr]

# ---- what a bad pattern raises
for bad in ("(", ")", "[", "a{2,1}", "*", "+", "?", "a**", "a{1}{2}", "(?P<a>a)(?P<a>b)", "(?P<1a>a)", "(?P<>a)", "(?P=b)", "\\", "\\q", r"\1", r"(a)\2", "(?z)", "(?", "(?P", "(?<=a*)", "(?<=(a))(?P=z)", "[z-a]", "[\\d-a]", r"\x", r"\x1", r"\u12", r"\U0011FFFF", r"\400", "(?i)(?-i)", "(?-z:a)", "(?(1)a|b|c)", "(?(1)a)", "(?(x)a)", "(?#", "a(?i)", "(?a)(?u)", "(?aL)", "(?aL:a)", "(?-a:a)", "(?P<a>", "(?P<é>a)", "é(", "\n(", "a\nb\n("):
    try:
        re.compile(bad)
        print(repr(bad), "compiled")
    except re.error as exc:
        print(repr(bad), type(exc).__name__, exc.msg, exc.pattern == bad, exc.pos, exc.lineno, exc.colno)
    except Exception as exc:
        print(repr(bad), type(exc).__name__)
print(re.error is re.PatternError, re.error.__name__, re.error.__module__, re.error.__mro__[1].__name__, failed(lambda: re.compile(b"(")), failed(lambda: re.error("m")), re.error("m").msg, re.error("m").pattern, re.error("m").pos, re.error("m", "p", 0).lineno, re.error("m", "a\nb", 2).lineno, re.error("m", "a\nb", 2).colno, re.error("m", b"a\nb", 2).colno, failed(lambda: re.compile("a{99999999999}")))  # type: ignore[no-untyped-call]

# ---- _sre itself
print(_sre.MAGIC, _sre.CODESIZE, _sre.MAXREPEAT, _sre.MAXGROUPS, _sre.getcodesize(), _sre.copyright, sorted(n for n in vars(_sre) if not n.startswith("__")), _sre.compile.__name__, type(_sre.compile).__name__, _sre.compile.__module__, type(_sre.template).__name__)
for c in (65, 97, 48, 0xC9, 0xE9, 0xDF, 0x130, 0x131, 0x17F, 0x212A, 0x1E9E, 0x10400, 0x10428, -1):
    print(c, _sre.ascii_iscased(c), _sre.unicode_iscased(c), _sre.ascii_tolower(c), _sre.unicode_tolower(c))
print(failed(lambda: _sre.ascii_iscased()), failed(lambda: _sre.ascii_iscased("a")), failed(lambda: _sre.unicode_tolower(2**70)), failed(lambda: _sre.getcodesize(1)), failed(lambda: _sre.compile()), failed(lambda: _sre.compile("a", 0, 1, 0, {}, ())), failed(lambda: _sre.compile("a", 0, [], "b", {}, ())), failed(lambda: _sre.compile("a", 0, [], 0, 1, ())), failed(lambda: _sre.compile("a", 0, [], 0, {}, 1)), failed(lambda: _sre.compile("a", "b", [1], 0, {}, ())), failed(lambda: _sre.compile("a", 0, [1], 0, {}, ())), failed(lambda: _sre.compile("a", 0, [1 << 40], 0, {}, ())), failed(lambda: _sre.compile("a", 0, ["x"], 0, {}, ())), failed(lambda: _sre.compile("a", 0, [-1], 0, {}, ())), failed(lambda: _sre.compile(1, 0, [1], 0, {}, ())), failed(lambda: _sre.template()), failed(lambda: _sre.template("a", 1)), failed(lambda: _sre.template("a", [])), failed(lambda: _sre.template("a", ["x", 1])), failed(lambda: _sre.template("a", ["x", "y", "z"])), failed(lambda: _sre.template("a", ["x", -1, "z"])), type(_sre.template("a", ["x", 1, "z"])).__name__, type(_sre.template("a", ["x", 1, "z"])).__module__, repr(type(_sre.template("a", ["x"]))))  # type: ignore[no-untyped-call]
copied = _sre.compile("a", 32, list(re.compile("a")._code if False else [14, 4, 0, 1, 1, 16, 97, 1]), 0, {}, ())
print(copied.flags, copied.groups, copied.pattern, repr(copied), copied.match("a").group(), copied.match("b"))
