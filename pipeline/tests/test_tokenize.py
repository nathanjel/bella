"""CPython's tokenizer compiled, against CPython (runtime/src/tokenizer.cpp; C-7-53 is the case): what a TokenizerIter answers
after an error (the C leaves it in the state the error left, a MemoryError out of a freed buffer included), what readline may
be and return, every message the lexer has, with and without the extra tokens, the limits (nesting, indentation, long lines
and strings that grow the buffer), and every token of real source files, by digest."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

STATES = r"""
import _tokenize, io
def attempt(label, it, n=3):
    for i in range(n):
        try:
            print(label, i, next(it))
        except BaseException as e:
            print(label, i, type(e).__name__, e.args, getattr(e, "lineno", "-"), getattr(e, "offset", "-"), getattr(e, "text", "-"))
def rl():
    raise ValueError("x")
attempt("raises", _tokenize.TokenizerIter(rl, extra_tokens=True))
attempt("stopiter", _tokenize.TokenizerIter(iter([]).__next__, extra_tokens=True), 4)
attempt("nonstr", _tokenize.TokenizerIter(lambda: 5, extra_tokens=True))
attempt("bytes for str", _tokenize.TokenizerIter(lambda: b"x\n", extra_tokens=True))
attempt("str for bytes", _tokenize.TokenizerIter(lambda: "x\n", extra_tokens=True, encoding="utf-8"))
attempt("bytearray", _tokenize.TokenizerIter(lambda: bytearray(b"x\n"), extra_tokens=True, encoding="utf-8"))
attempt("unterminated", _tokenize.TokenizerIter(io.StringIO("x = 'a\n").readline, extra_tokens=True), 7)
attempt("dedent", _tokenize.TokenizerIter(io.StringIO("if a:\n    b\n  c\n").readline, extra_tokens=True), 11)
attempt("tabs", _tokenize.TokenizerIter(io.StringIO("if a:\n        b\n\tc\n").readline, extra_tokens=True), 11)
attempt("surrogate", _tokenize.TokenizerIter(io.StringIO("x = '\udc80'\n").readline, extra_tokens=True), 3)
attempt("null", _tokenize.TokenizerIter(io.StringIO("x = 1\ny\x00z\nw\n").readline, extra_tokens=True), 8)
attempt("eof in paren", _tokenize.TokenizerIter(io.StringIO("x = (1,\n").readline, extra_tokens=True), 9)
attempt("continuation", _tokenize.TokenizerIter(io.StringIO("x = 1 \\ y\nz\n").readline, extra_tokens=True), 8)
attempt("continuation at eof", _tokenize.TokenizerIter(io.StringIO("x = 1 \\\n").readline, extra_tokens=True), 6)
lines = iter(["a = 1\n", "b = 2"])
attempt("iter", _tokenize.TokenizerIter(lines.__next__, extra_tokens=True), 11)
attempt("empty-then", _tokenize.TokenizerIter(iter(["", "x\n"]).__next__, extra_tokens=True), 3)
attempt("two lines in one", _tokenize.TokenizerIter(iter(["a\nb\n", "c\n"]).__next__, extra_tokens=True), 8)
attempt("cr only", _tokenize.TokenizerIter(iter(["x\r"]).__next__, extra_tokens=True), 4)
attempt("unknown encoding", _tokenize.TokenizerIter(lambda: b"x\n", extra_tokens=True, encoding="no-such-codec"), 2)
attempt("latin-1", _tokenize.TokenizerIter(iter([b"s = '\xe9\xff'\n"]).__next__, extra_tokens=True, encoding="latin-1"), 6)
attempt("bad utf-8 replaced", _tokenize.TokenizerIter(iter([b"s = '\xff\xfe' # \x80\n"]).__next__, extra_tokens=True, encoding="utf-8"), 6)
class S(str):
    pass
attempt("str subclass", _tokenize.TokenizerIter(iter([S("q = 1\n")]).__next__, extra_tokens=True), 5)
inner = _tokenize.TokenizerIter(iter(["inner_name\n"]).__next__, extra_tokens=True)
def nested():
    return next(inner)[1] + " = 0\n"
attempt("nested", _tokenize.TokenizerIter(nested, extra_tokens=True), 9)
for kw in ({"encoding": "utf\0-8"}, {"encoding": "\udc80"}, {"encoding": 5}, {}):
    try:
        print(type(_tokenize.TokenizerIter(lambda: "", **kw)).__name__)
    except (TypeError, ValueError) as e:
        print(type(e).__name__, e.args[0] if not isinstance(e, UnicodeError) else e.reason)
it = _tokenize.TokenizerIter(iter(["z\n"]).__next__, extra_tokens=False)
print(list(it), list(it), next(it, "done"), iter(it) is it, hasattr(it, "__next__"), type(it).__name__)
"""

MESSAGES = r"""
import _tokenize, io, tokenize, warnings
BAD = ["0x", "0xg", "0x_", "0x1_", "0o", "0o8", "0o1_", "0o18", "0b", "0b2", "0b1_", "0b12", "1_", "1__0", "1_.5", "1.5_", "1e", "1e+", "1e5_", "0_", "00_",
       "012", "0_7", "1.2.3", "1.e", "5j_", "1if x else 2", "1and 2", "1or 2", "1in x", "1is x", "1not in x", "1for", "1else", "0x1for x in y", "1abc", "1.5abc",
       "0b1c", "0o7z", "1_000_j", "1jx", "x = 'abc", 'x = "abc', "x = '''abc", 'x = ' + 3 * '"' + 'abc\n\n', "x = 'abc\\", "x = 'abc\\'", "ub''", "bu''", "ur''", "ru''", "uf''",
       "fu''", "ut''", "bf''", "fb''", "bt''", "tb''", "ft''", "tf''", "rb''", "br''", "rf''", "fr''", "rt''", "tr''", "f'{", "f'{x", "f'{x!", "f'{x!r", "f'{x:",
       "f'{x:{y", "f'}'", "f'{x}}'", "f'{{}'", "f'{x'", "f\"{x\"", "f'{(}'", "f'{)}'", "f'{]}'", "f'{[)}'", "f'{x:\n}'", "f'''{x:\n}'''", "f'{x!r:\n}'",
       "f'{\n}'", "f'{x\n}'", "f'''{\nx\n}'''", "f'{x=!r:>{w}}'", "f'{a.b['c']}'", "f'{'a' 'b'}'", "f'{'''x'''}'", "f'\\N{DIGIT ONE}'", "f'\\N{'", "f'\\{x}'",
       "f'{x:\\{}'", "rf'\\{x}'", "f'{x!}'", "f'{!r}'", "f'{=}'", "f'{x!r=}'", "f'{x # c\n}'", "f'''{x # c\n}'''", "f'{x:=5}'", "f'{(x:=5)}'", "f'{lambda x: 1}'",
       "f'{x:!r}'", "f'{x:{y:{z:{w}}}}'", "f'{x:{y!r}}'", "t'{", "t'}'", "t'{x!}'", "t'{x:\n}'", ")", "]", "}", "(]", "[}", "{)", "((]", "(\n]", "x = (1,\n  2]",
       "$", "x = 1 ?", "`x`", "x = 1 \\ y", "x \\", "\\", "\\\n", "x = \x7f", "x = \x01", "\xa0x", "x\xa0= 1", "x = '\x00'", "\x00", "é = 1", "x = €", "a\u200bb",
       "x = 1\n  y", "if x:\n  y\n z", "if x:\n\ty\n        z", "if x:\n        y\n\tz", "\tx\n        y", "x\n\ty", "a <> b", "a != b", "a := b", "...", "..", "a->b",
       "x = 1 # c\n# d\n\n", "'a' 'b'", "x = 'a' \"b\"", "'''a\nb''' x", "x = 1;", ";", ":", "@", "@=", "a @ b", "a ** = b", "a //= b", "a >>= b", "a <<=b", "!", "!=", "!x",
       "\f", "\fx = 1", "x\f= 1", "  \f x", "if x:\n  \f  y", "x = 1\r", "x = 1\r\r\n", "x = (1\r\n)", "'a\rb'", "#\r", "# c", "#", " ", "  # c", "\t", "\n\n", "x\n\n\ny",
       "async", "await x", "match x:\n  case _: pass", "type X = int", "print 1", "exec 'x'", "lambda: 0", "x = yield", "\\\nx", "x = (\\\n1)", "'a\\\nb'", "f'a\\\nb{x}'"]
def tokens(make):
    out = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            for row in make():
                out.append(tuple(row)[:4])
            end = "ok"
        except (SyntaxError, tokenize.TokenError) as e:
            end = (type(e).__name__, e.args if isinstance(e, tokenize.TokenError) else (e.msg, e.lineno, e.offset, e.text, e.end_lineno, e.end_offset))
        except Exception as e:
            end = (type(e).__name__, e.args)
    return len(out), out[-3:], end, [(w.category.__name__, str(w.message), w.lineno) for w in caught]
for src in BAD:
    for text in (src, src + "\n"):
        print(repr(text))
        print("   extra ", tokens(lambda: tokenize.generate_tokens(io.StringIO(text, newline="").readline)))
        print("   plain ", tokens(lambda: _tokenize.TokenizerIter(io.StringIO(text, newline="").readline, extra_tokens=False)))
with warnings.catch_warnings():
    warnings.simplefilter("error")
    for text in ("1if x else 2\n", "0x1for x in y\n", "x = 1or 2\n"):
        print(repr(text), tokens(lambda: _tokenize.TokenizerIter(io.StringIO(text).readline, extra_tokens=False)))
"""

LIMITS = r"""
import _tokenize, io, tokenize
def run(label, text, extra=True):
    count = 0
    last = None
    try:
        for row in _tokenize.TokenizerIter(io.StringIO(text).readline, extra_tokens=extra):
            count += 1
            last = row[:4]
        end = "ok"
    except SyntaxError as e:
        end = (type(e).__name__, e.msg, e.lineno, e.offset, len(e.text or ""), e.end_lineno, e.end_offset)
    print(label, count, last if last is None or len(str(last)) < 200 else (last[0], len(last[1]), last[2], last[3]), end)
for depth in (199, 200, 201):
    run("parens " + str(depth), "(" * depth + ")" * depth + "\n")
    run("brackets plain " + str(depth), "[" * depth + "]" * depth + "\n", False)
for depth in (98, 99, 100, 101):
    run("indent " + str(depth), "".join(" " * i + "if x:\n" for i in range(depth)) + " " * depth + "pass\n")
for depth in (1, 2, 3, 4, 5, 149, 150, 151):
    text = "x"
    for i in range(depth):
        text = "f" + ('"' if i % 2 else "'") + "{" + text + "}" + ('"' if i % 2 else "'")
    run("fstring depth " + str(depth), text + "\n")
    spec = "f'{x:" + "{y:" * depth + "}" * depth + "}'\n"
    run("spec depth " + str(depth), spec)
run("long line", "x = " + " + ".join("name%d" % i for i in range(5000)) + "\n")
run("long string", "s = '" + "a" * 100000 + "'\n")
run("long triple", "s = '''" + ("line\n" * 20000) + "'''\n")
run("long fstring", "s = f'''" + ("text {value!r:>10} more\n" * 5000) + "'''\n")
run("long comment", "#" + "c" * 70000 + "\nx\n")
run("long continuation", "x = (" + "1,\n" * 30000 + ")\n")
run("wide", "é = '" + "日本語" * 20000 + "' + ünï\n")
run("many lines", "x = 1\n" * 50000)
run("no final newline, long", "y = " + "1 + " * 9000 + "1")
big = "def f():\n" + "".join("    v%d = f'{v%d!r:>{w}}' if v%d else [1, (2, {3: 4})]  # c\n" % (i, i, i) for i in range(4000))
print(len(list(tokenize.generate_tokens(io.StringIO(big).readline))), tokenize.untokenize(tokenize.generate_tokens(io.StringIO(big).readline)) == big)
"""

SOURCES = r"""
import hashlib, io, os, tokenize, token
base = os.path.dirname(os.__file__)
for name in ("tokenize.py", "inspect.py", "typing.py", "dataclasses.py", "string/templatelib.py", "re/_parser.py", "json/decoder.py", "argparse.py",
             "collections/__init__.py", "_pydecimal.py", "locale.py", "textwrap.py", "enum.py", "functools.py", "traceback.py", "ast.py", "os.py"):
    path = os.path.join(base, name)
    if not os.path.exists(path):
        print(name, "absent")
        continue
    with open(path, "rb") as f:
        data = f.read()
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    n = 0
    for tok in tokenize.tokenize(io.BytesIO(data).readline):
        digest.update(repr((tok.type, tok.string, tok.start, tok.end, tok.line, tok.exact_type)).encode())
        counts[token.tok_name[tok.type]] = counts.get(token.tok_name[tok.type], 0) + 1
        n += 1
    text = data.decode("utf-8")
    again = hashlib.sha256()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        again.update(repr(tuple(tok)).encode())
    print(name, n, digest.hexdigest()[:16], again.hexdigest()[:16], sorted(counts.items()))
with tokenize.open(os.path.join(base, "tokenize.py")) as f:
    print(f.encoding, len(f.readline()))
"""


def test_states_after_errors() -> None:
    same(STATES)


def test_every_message_in_both_modes() -> None:
    same(MESSAGES)


def test_limits_and_long_inputs() -> None:
    same(LIMITS)


def test_real_sources_by_digest() -> None:
    same(SOURCES)


if __name__ == "__main__":
    test_states_after_errors()
    test_every_message_in_both_modes()
    test_limits_and_long_inputs()
    test_real_sources_by_digest()
