# clause: C-7-53
# spec: section 7
# status: P1
# source: Parser/lexer/lexer.c, Parser/tokenizer/readline_tokenizer.c and Python/Python-tokenize.c (the tokenizer under Lib/tokenize.py)
"""tokenize over CPython's own tokenizer (_tokenize.TokenizerIter, which generate_tokens and tokenize wrap): every token's
type, text, start, end and line for names, numbers in every base and form, strings with their prefixes over one line and
several, f-strings and t-strings (nested, with conversions, format specifications, the = form and nested quotes), every
operator, indentation and its DEDENTs, continuation lines, comments, blank lines, a last line without a newline, CRLF line
ends, characters beyond ASCII (columns count characters), a form feed; exact_type; what an error raises and where
(an unterminated string, a dedent to no outer level, tabs against spaces, a character after a line continuation, EOF inside a
bracket or a statement, a null byte); tokenize() over bytes with its ENCODING token (the default, a coding cookie, a BOM);
untokenize of what was read; and the tokenizer called directly without the extra tokens, where it numbers each operator."""
import io
import token
import tokenize
import warnings

import _tokenize  # type: ignore[import-not-found]

SOURCES: list[str] = [
    "x = 1\n",
    "def f(a, b=2, *c, **d):\n    return a + b\n\nclass K(object):\n    pass\n",
    "0 7 42 1_000 0x1F 0XdeadBEEF 0o17 0O7 0b101 0B1_0 1.5 .5 5. 1e10 1E-3 1_0.0_1e+0_2 3j 2.5J 0j 1e3j 0xfj\n",
    "'a' \"b\" '''c''' \"\"\"d\"\"\" r'\\d' R\"x\" b'y' B\"z\" rb'w' Rb'v' bR'u' BR\"t\" u'old' U'OLD' 'it\\'s' \"a\\\"b\" ''\n",
    "s = '''first\nsecond \\\n third'''\nt = \"\"\"a\n\nb\"\"\" + 'c'\n",
    "f'plain' f'{x}' f'a{x}b{y!r}c{z:>10}d' F\"{x=}\" rf'{a}\\d' fr'{a}' Rf'{a}' f'{x:{width}.{prec}}' f'{{literal}}'\n",
    "f'''multi\n{line}\nend''' f\"{d['key']}\" f'{f\"{inner}\"}' f'{x!s:^{w}}' f'{a + b = }' f'{x:%Y-%m-%d}' f''\n",
    "t'plain' t'{x}' T\"{x!r:>{w}}\" rt'{a}\\n' tr'{a}' t'''a\n{b}''' t'{x=}'\n",
    "+ - * / // % @ ** << >> & | ^ ~ < > <= >= == != -> := += -= *= /= //= %= @= &= |= ^= >>= <<= **= ... . , : ; ( ) [ ] { } ! =\n",
    "if a:\n    b\n    if c:\n        d\n    e\nf\n",
    "if a:\n\tb\n\tif c:\n\t\td\nx\n",
    "total = (1 +\n         2 +  # inside\n         3)\nlong = 1 + \\\n    2\nitems = [\n    1,\n\n    2,\n]\n",
    "# leading comment\n\nx = 1  # trailing\n    # indented comment\n\n\ny = 2\n",
    "last = 'no newline'",
    "a = 1\r\nb = 2\r\nif a:\r\n    c\r\n",
    "naïve = 'café' + \"日本語\"  # ünïcödé\nπ = 3.14\nf'{naïve}→{π}'\n",
    "x = 1\n\x0cy = 2\n",
    "async def g():\n    await h()\n    async with a as b: pass\nmatch x:\n    case 1: pass\ntype Alias = int\n",
    "$ ? `\n",
    "x = 1 if y else 2; lambda: (yield)\n",
    "",
    "\n",
    "   \n\t\n# only\n",
    "pass\n\n\n",
]

BROKEN: list[str] = [
    "x = 'unterminated\n",
    "x = '''never closed\nmore\n",
    "if a:\n        b\n    c\n",
    "if a:\n        b\n\tc\n",
    "x = 1 \\ y\n",
    "x = (1,\n     2\n",
    "x = [1, 2\n",
    "def f():\n    return 1\n  bad\n",
    "x = 1\ny = \x00\n",
    "f'{x'\n",
    "f'{x!}'\n",
    "f'{}'\n",
    "x = )\n",
    "x = (]\n",
    "1__0\n",
    "0x\n",
    "x = 1 +\n",
    "'abc\\\n",
]


def show(tok: tokenize.TokenInfo) -> str:
    return f"{token.tok_name[tok.type]} {tok.string!r} {tok.start}-{tok.end} {tok.line!r} {token.tok_name[tok.exact_type]}"


def run(source: str) -> None:
    print("SOURCE", repr(source))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            print("  ", show(tok))
    except tokenize.TokenError as e:
        print("   TokenError", e.args)
    except SyntaxError as e:
        print("  ", type(e).__name__, e.msg, e.lineno, e.offset, repr(e.text), e.end_lineno, e.end_offset)


for src in SOURCES:
    run(src)
for src in BROKEN:
    run(src)

for data in (b"x = 1\n", b"# -*- coding: latin-1 -*-\ns = '\xe9'\n", b"\xef\xbb\xbfy = '\xc3\xa9'\n", b"#!/usr/bin/python\n# vim: set fileencoding=utf-8 :\nz\n", b""):
    print("BYTES", data)
    toks = list(tokenize.tokenize(io.BytesIO(data).readline))
    for tok in toks:
        print("  ", show(tok))
    print("   untokenize", tokenize.untokenize(toks))
for bad in (b"# coding: nope\nx\n", b"\xef\xbb\xbf# coding: latin-1\nx\n", b"x = '\xff'\n"):
    try:
        print(len(list(tokenize.tokenize(io.BytesIO(bad).readline))))
    except SyntaxError as e:
        print("SyntaxError", e.msg)

for src in ("x = 1\nif x:\n    y = [1,\n         2]\n", "a  +  b\n", "f'{x}' 'y'\n"):
    read = list(tokenize.generate_tokens(io.StringIO(src).readline))
    print(repr(tokenize.untokenize(read)), repr(tokenize.untokenize([(t.type, t.string) for t in read])))

print("DIRECT")
for src in ("x += f(a)[1] -> y  # c\n\nif z:\n    w = 'q' f'{e!r}'\n", "1if 2else 3\n", "0_7 1_000j 0b1 if x else 0o7or 1\n", "x = (\n",
            "f'\\d{x}\\q' '\\d'\n", "x = 1 # type: int\ny = 2 # type: ignore\n", "é1 = ῑ + x·y\n", "a ‽ b\n", "x = 0777\n", "1.5e\n", "f'{x!z}' \n"):
    lines = io.StringIO(src)
    print("  SOURCE", repr(src))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            for row in _tokenize.TokenizerIter(lines.readline, extra_tokens=False):
                print("    ", token.tok_name[row[0]], row[1:])
        except SyntaxError as e:
            print("    ", type(e).__name__, e.msg, e.lineno, e.offset, repr(e.text), e.end_lineno, e.end_offset)
    for w in caught:
        print("     warned", w.category.__name__, w.message, w.filename, w.lineno)
with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        print(len(list(_tokenize.TokenizerIter(io.StringIO("1if x else 2\n").readline, extra_tokens=False))))
    except SyntaxError as e:
        print("  as an error:", type(e).__name__, e.msg, e.lineno, e.offset, repr(e.text))
encoded = io.BytesIO("é = 'ó'\nx\n".encode("latin-1"))
print([row[:4] for row in _tokenize.TokenizerIter(encoded.readline, extra_tokens=True, encoding="latin-1")])
for readline, kwargs in ((io.BytesIO(b"x\n").readline, {}), (io.StringIO("x\n").readline, {"encoding": "utf-8"}), (lambda: 5, {})):
    try:
        print(len(list(_tokenize.TokenizerIter(readline, extra_tokens=True, **kwargs))))
    except TypeError as e:
        print("TypeError", len(e.args))
it = _tokenize.TokenizerIter(io.StringIO("a\n").readline, extra_tokens=True)
print(iter(it) is it, [token.tok_name[r[0]] for r in it], list(it), type(it).__name__, type(it).__module__)
