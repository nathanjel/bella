"""Reviews A13 (Codex astra-low) and G13 (gemini-3.8-flash-high) of 2026-11-07, RL-347 to RL-357: every finding's program and what
stands around it, compiled, against CPython; the locale guard and the exit flush separately, since one needs an environment and the
other the exit's streams."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

TELL_AND_COOKIES = r"""
import _io
t = _io.TextIOWrapper(_io.BytesIO(b'\rc\n'), encoding='utf-8')
print(repr(t.read(1)))
t.seek(t.tell())
print(repr(t.read(1)))
p = t.tell()
print(repr(t.read()))
t.seek(p)
print(repr(t.read()))
t2 = _io.TextIOWrapper(_io.BytesIO(b'\rc'), encoding='utf-8')
t2.read(1)
print(t2.tell())
def fields(c):
    rest, position = divmod(c, 1 << 64); rest, dec_flags = divmod(rest, 1 << 32); rest, btf = divmod(rest, 1 << 32); need_eof, cts = divmod(rest, 1 << 32)
    return (position, dec_flags, btf, cts, need_eof)
t = _io.TextIOWrapper(_io.BytesIO(b'\rc\n'), encoding='utf-8')
print(repr(t.read(1)), fields(t.tell()), t._CHUNK_SIZE)
c = t.tell(); t.seek(c); print("after seek", fields(t.tell()))
print(repr(t.read(1)), fields(t.tell()))
p = t.tell()
print(repr(t.read()), fields(t.tell()))
t.seek(p)
print(repr(t.read()))
for data in (b'\rc', b'a\rb', b'ab\r\ncd', b'\r\n'):
    u = _io.TextIOWrapper(_io.BytesIO(data), encoding='utf-8')
    out = []
    for _ in range(4):
        out.append((repr(u.read(1)), fields(u.tell())))
    print(data, out)
"""

REINIT = r"""
import _io
a = _io.BytesIO(b"abc")
t = _io.TextIOWrapper(a, encoding="utf-8")
print(t.read(1))
b = _io.BytesIO(b"XYZ")
t.__init__(b, encoding="utf-8")
print(t.read(2))
w = _io.BytesIO()
tw = _io.TextIOWrapper(w, encoding="utf-8")
tw.write("old")
w2 = _io.BytesIO()
tw.__init__(w2, encoding="utf-8")
tw.write("new")
tw.flush()
print(w.getvalue(), w2.getvalue())
"""

LAZY_BOUND_TEMPLATE_AST = r"""
counter = 0
def bound() -> object:
    global counter
    counter += 1
    return None
def f[T: bound()]() -> None:
    pass
t = f.__type_params__[0]
print(t.__bound__, t.__bound__, counter)
class S(str):
    def __len__(self) -> int:
        return 0
Template = type(t"")
print(list(Template(S("hello"))))
import _ast
class Node(_ast.AST):
    _fields = ("child",)
    def __eq__(self, other: object) -> bool:
        return True
print(Node(Node(None)))
"""

STARRED_DEFAULT_SEQUENCE_CONCAT = r"""
import typing
import string.templatelib as st
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class D[*Ts = *tuple[int, str]]: pass
class E[*Ts = tuple[int, str]]: pass
p = D.__type_params__[0]; q = E.__type_params__[0]
print(p.__default__, q.__default__, p.evaluate_default.__name__, p.evaluate_default(1), p.has_default())
def bad(): return 5
class F[*Ts = *bad()]: pass
print(m(lambda: F.__type_params__[0].__default__))
def two(): return (1, 2)
class G[*Ts = *two()]: pass
print(m(lambda: G.__type_params__[0].__default__))
class Custom:
    def __radd__(self, other):
        return "custom"
    def __rmul__(self, other):
        return "rmul"
t = st.Template()
print(t + Custom(), m(lambda: t * Custom()), m(lambda: t + 1), m(lambda: 1 + t), t + st.Template("x"))
import collections
d = collections.deque([1])
print(d + Custom(), d * Custom(), m(lambda: d + [1]))
import _ast
class Node(_ast.AST):
    _fields = ("child",)
    def __eq__(self, other):
        return isinstance(other, Node)
a = Node.__new__(Node); b = Node.__new__(Node); b.child = None; a.child = b
print(repr(a))
"""

UNPACKING = r"""
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
def u1(v):
    [a] = v
    return a
def u2(v):
    a, b = v
    return a, b
def u3(v):
    a, *b = v
    return a, b
class Seq:
    def __getitem__(self, i):
        if i < 3: return i
        raise IndexError
class NoIter:
    pass

print(m(lambda: u1(5)), m(lambda: u1((1, 2))), m(lambda: u1([1, 2, 3])), m(lambda: u1({1: 2, 3: 4})), m(lambda: u1(iter([1, 2]))), m(lambda: u2((1,))), m(lambda: u2(1)), m(lambda: u2(None)), m(lambda: u2(Seq())), m(lambda: u2(NoIter())), m(lambda: u3(5)), m(lambda: u3([])), m(lambda: u1("ab")), m(lambda: u1(b"ab")), m(lambda: u1(range(3))), m(lambda: u1(set([1, 2]))), u1([7]), u2("ab"), u3(range(4)))
"""

STDOUT_WITHOUT_CLOSED = r"""
import sys
class Output:
    def write(self, text: str) -> int:
        return sys.__stdout__.write(text)
    def flush(self) -> None:
        sys.__stdout__.write("flushed\n")
sys.stdout = Output()
print("hello")
"""


def test_tell_after_a_seek_and_the_cookie_layout_rl_347_354() -> None:
    same(TELL_AND_COOKIES)


def test_a_second_init_clears_the_wrapper_rl_349() -> None:
    same(REINIT)


def test_lazy_bound_template_len_and_ast_repr_rl_351_352_353() -> None:
    same(LAZY_BOUND_TEMPLATE_AST)


def test_starred_default_and_sequence_concat_rl_355_356() -> None:
    same(STARRED_DEFAULT_SEQUENCE_CONCAT)


def test_unpacking_messages_rl_357() -> None:
    same(UNPACKING)


def test_a_replacement_stdout_without_closed_rl_348() -> None:
    """Both streams and the exit status: flush_io after the module, then flush_std_files at exit, so the replacement's flush runs twice."""
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(STDOUT_WITHOUT_CLOSED, encoding="utf-8")
        ref = subprocess.run([sys.executable, "-P", str(prog)], capture_output=True, text=True, check=False, cwd=tmp)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.stdout, got.stderr, got.returncode) == (ref.stdout, ref.stderr, ref.returncode), (got, ref)


def test_lc_all_is_not_coerced_rl_350() -> None:
    src = "import _locale\nprint(_locale.setlocale(_locale.LC_CTYPE))\n"
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(src, encoding="utf-8")
        exe = build(prog, "prog.py")
        for env in ({"LC_ALL": "C"}, {"LC_ALL": "POSIX", "LANG": "en_US.UTF-8"}, {"LANG": "C"}, {"LC_CTYPE": "C"}, {"LC_ALL": ""}):
            full = {"PATH": os.environ.get("PATH", ""), **env}
            ref = subprocess.run([sys.executable, "-P", str(prog)], capture_output=True, text=True, check=False, cwd=tmp, env=full)
            got = subprocess.run([str(exe)], capture_output=True, text=True, check=False, cwd=tmp, env=full)
            assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (env, got, ref)


if __name__ == "__main__":
    test_tell_after_a_seek_and_the_cookie_layout_rl_347_354()
    test_a_second_init_clears_the_wrapper_rl_349()
    test_lazy_bound_template_len_and_ast_repr_rl_351_352_353()
    test_starred_default_and_sequence_concat_rl_355_356()
    test_unpacking_messages_rl_357()
    test_a_replacement_stdout_without_closed_rl_348()
    test_lc_all_is_not_coerced_rl_350()
