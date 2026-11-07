"""pwd, grp, _locale, zlib, _ast and the t-string types, compiled, against CPython: the messages the cases do not compare, the conversions'
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


def test_what_is_absent_stops_by_name() -> None:
    cases = (("import zlib\nzlib.compress(b'a')", "zlib"), ("import zlib\nzlib.ZLIB_VERSION", "ZLIB_VERSION"), ("import ast\nast.parse('1')", "compile()"),
             ("import ast\nast.expr()", "abstract AST node class"), ("import ast\nast.dump(ast.Constant(1))", "typealias"))
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
    test_what_is_absent_stops_by_name()
