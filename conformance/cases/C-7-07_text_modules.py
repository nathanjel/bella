# clause: C-7-07
# spec: section 7
# status: P1
# source: dialect specification section 7, Text (string, re, textwrap, difflib, json, csv, struct, base64, binascii, codecs, html, urllib.parse)
"""Text modules: the results phase 1 must reproduce exactly."""
import base64
import binascii
import codecs
import csv
import difflib
import html
import io
import json
import re
import string
import struct
import textwrap
import urllib.parse

print(string.Template("$who likes ${what}").substitute(who="Tim", what="kung pao"), string.capwords("hello  world"))
print(string.Formatter().format("{0:>5}|{name:^7}|{1:.3f}", "ab", 3.14159, name="mid"))

m = re.match(r"(?P<key>\w+)=(?P<value>\d+)", "size=42 rest")
print(m and (m.group("key"), m.group("value"), m.span(), m.groupdict()))
print(re.sub(r"\d+", lambda mo: str(int(mo.group()) * 2), "a1 b22 c333"), re.split(r"[,;]\s*", "a, b;c"))
print([mo.group() for mo in re.finditer(r"\b\w{4}\b", "this is some text with four")], re.findall(r"(\w)(\d)", "a1b2"))
print(re.fullmatch(r"[a-z]+", "abc", re.I) is not None, re.compile(r"^x", re.M).findall("x\nx\ny"), re.escape("a.b*c"))

text = "The quick brown fox jumps over the lazy dog and keeps running far away."
print(textwrap.wrap(text, 24), textwrap.shorten(text, 30), repr(textwrap.dedent("    a\n      b\n")))
diff = difflib.unified_diff(["a\n", "b\n", "c\n"], ["a\n", "c\n", "d\n"], "old", "new", lineterm="")
print(list(diff), round(difflib.SequenceMatcher(None, "abcd", "bcde").ratio(), 3), difflib.get_close_matches("appel", ["apple", "ape", "peach"]))

data = {"b": [1, 2.5, None, True], "a": "é", "c": {"x": 1e100}}
print(json.dumps(data, sort_keys=True), json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True))
print(json.loads('{"n": 1.0, "big": 12345678901234567890, "u": "\\u00e9"}'), json.dumps(0.1 + 0.2), json.dumps(float("1e16")))
buf = io.StringIO()
writer = csv.writer(buf)
writer.writerows([["name", "note"], ["a", "x,y"], ["b", 'say "hi"']])
print(repr(buf.getvalue()), list(csv.DictReader(io.StringIO(buf.getvalue()))))

packed = struct.pack("<hIq?3s", -2, 7, -(2**40), True, b"ab")
print(packed.hex(), struct.unpack("<hIq?3s", packed), struct.calcsize("@iq"), struct.calcsize("<iq"))
print(base64.b64encode(b"\x00\xffhello"), base64.urlsafe_b64encode(b"\xfb\xff"), base64.b32encode(b"ab"), base64.b16decode(b"6869"))
print(binascii.hexlify(b"\x01\xab", "-"), binascii.crc32(b"hello"), binascii.unhexlify("ff00"))
print(codecs.encode("é€", "utf-16-le"), codecs.decode(b"\xc3\xa9", "utf-8"), "é".encode("latin-1"), "x".encode("ascii"))
print(html.escape('<a href="x">&</a>'), html.unescape("&lt;&eacute;&#x263A;&gt;"))
parts = urllib.parse.urlsplit("https://user@example.com:8080/a b/c?q=1&r=x y#frag")
print(parts.scheme, parts.hostname, parts.port, parts.path, parts.query, parts.fragment)
print(urllib.parse.quote("a b/é"), urllib.parse.unquote("a%20b"), urllib.parse.urlencode({"q": "a b", "n": 1}))
print(urllib.parse.parse_qs("a=1&a=2&b=x"), urllib.parse.urljoin("http://h/a/b", "../c"))
