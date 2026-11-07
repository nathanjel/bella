# clause: C-7-32
# spec: section 7
# status: P1
# source: dialect specification section 7, Python/Python-ast.c (ast_type_init, ast_type_reduce, ast_type_replace, ast_repr), Lib/ast.py
"""The node classes of _ast as objects: their fields, attributes, defaults and docstrings, the constructor's rules (positional, keyword,
missing, unexpected, abstract), repr at depth, __reduce__ and __replace__, a program's own subclasses, and ast's functions over nodes a
program builds (dump, unparse, literal_eval, iter_fields, walk, copy_location, fix_missing_locations). Parsing source is not here."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001
import _ast
import ast


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


print(len([n for n in dir(_ast) if not n.startswith("__")]), _ast.AST.__module__, sorted(k for k in vars(_ast.AST) if not k.startswith("__")), _ast.AST._fields, _ast.AST._attributes, _ast.BinOp._fields, _ast.BinOp.__match_args__, _ast.BinOp._field_types, _ast.BinOp.__doc__, [c.__name__ for c in _ast.BinOp.__mro__], _ast.stmt._attributes, _ast.expr._attributes, _ast.arguments._attributes, _ast.Load._fields)
c = ast.Constant(1)
print(repr(c), vars(c), c.value, c.kind, failed(lambda: c.lineno), failed(lambda: ast.Constant()), failed(lambda: ast.Constant(1, 2, 3)), failed(lambda: ast.Constant(1, value=2)), failed(lambda: ast.Constant(1, foo=2)), ast.Constant(value=1, kind="u").kind, ast.Constant(1, lineno=3).lineno, failed(lambda: ast.BinOp()), ast.Constant(1, end_lineno=None).end_lineno, hasattr(ast.Constant(1), "end_lineno"))  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
print(failed(lambda: ast.Name("x")), vars(ast.Name("x")), failed(lambda: ast.Name()), vars(ast.Module()), repr(ast.Module()), failed(lambda: ast.FunctionDef("f")), failed(lambda: vars(ast.FunctionDef("f", ast.arguments()))), repr(ast.Load()), ast.Load() is ast.Load(), failed(lambda: ast.BinOp(1, 2, 3, 4)), type(ast.stmt.__init__).__name__)  # type: ignore[arg-type,call-arg,no-untyped-call]
b = ast.BinOp(ast.Name("a", ast.Load()), ast.Add(), ast.Constant(1))
print(c.__reduce__(), repr(ast.Constant(1).__replace__(value=2)), failed(lambda: ast.Constant(1).__replace__(nope=2)), repr(ast.Constant(1).__replace__()), ast.Constant(1).__replace__(lineno=5).lineno, _ast.PyCF_ONLY_AST, _ast.PyCF_TYPE_COMMENTS, _ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, _ast.PyCF_OPTIMIZED_AST, type(_ast.AST.__dict__.get("_fields")).__name__, _ast.stmt.__dict__.get("_attributes"), ast.Module().__reduce__()[2], ast.Constant(1, kind="u", lineno=2).__reduce__()[2])  # type: ignore[call-arg,no-untyped-call]
print(repr(b), repr(ast.Expr(ast.Constant("s"))), repr(ast.Dict([None], [ast.Constant(2)])), repr(ast.arguments()), ast.arguments().args, repr(ast.Compare(ast.Constant(1), [ast.Lt()], [ast.Constant(2)])), repr(ast.Call(ast.Name("f"), [ast.Constant(i) for i in range(4)], [])), repr(ast.Module([ast.Expr(ast.Constant(1))], [])), vars(ast.Module([], [])), repr(ast.Call(ast.Name("f"), [ast.Constant(1), ast.Constant(2)], [ast.keyword("k", ast.Constant(3))])))
deep = ast.UnaryOp(ast.USub(), ast.UnaryOp(ast.USub(), ast.UnaryOp(ast.USub(), ast.UnaryOp(ast.USub(), ast.Constant(1)))))
print(repr(deep), repr(ast.List([ast.Constant(i) for i in range(5)], ast.Load())), repr(ast.Tuple([], ast.Load())), repr(ast.Constant("a\n'b")), repr(ast.Constant(b"x")), repr(ast.Constant(None)), repr(ast.Constant(...)), repr(ast.Constant(1.5)), repr(ast.JoinedStr([ast.Constant("a"), ast.FormattedValue(ast.Name("x"), -1)])), repr(ast.Attribute(ast.Name("a"), "b", ast.Load())))


class Sub(ast.expr):
    _fields = ("a", "b")


class Odd(ast.AST):
    _fields = ("x",)


class Fixed(ast.AST):
    _fields = ("p",)
    _attributes = ("q",)

    def __init__(self, *args, **kw):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kw)
        self.seen = True


print(repr(Sub(1, 2)), vars(Sub(1, 2)), failed(lambda: Sub(1)), failed(lambda: Odd()), vars(Odd()), Odd(1).x, repr(Odd(1)), Sub.__module__, Sub._attributes, failed(lambda: ast.Constant.__init__(c, 5)), c.value, ast.Name("x").ctx, isinstance(ast.Load(), ast.expr_context), isinstance(c, ast.expr), vars(Fixed(3, q=4)), repr(Fixed(p=1)), failed(lambda: Fixed(1, 2)), Sub.__mro__[1].__name__, failed(lambda: Sub(1, 2, lineno=3).lineno), failed(lambda: Sub(c=1)))  # type: ignore[attr-defined,call-arg,misc,no-untyped-call]
print(repr(_ast.mod.__doc__[:40]), _ast.Load.__doc__, _ast.FunctionDef._field_types, [c.__name__ for c in _ast.expr_context.__mro__], sorted(set(dir(ast.Constant(1))) - set(dir(object))), ast.Constant.__name__, ast.Constant.__qualname__, _ast.Constant.__doc__, _ast.arguments.__doc__, _ast.Module._field_types, _ast.Name._field_types, _ast.Dict._field_types, _ast.ImportFrom._field_types, _ast.keyword._field_types, _ast.TypeIgnore._fields, _ast.MatchSingleton._fields)  # type: ignore[index]
print(len([n for n in dir(_ast) if n[:1].isupper()]), [n for n in dir(_ast) if n[:1].isupper()][:12], [n for n in dir(_ast) if n[:1].islower() and not n.startswith("_")], all(getattr(ast, n) is getattr(_ast, n) for n in dir(_ast) if not n.startswith("_")))
n = ast.Name("v", ast.Load())
n.extra = 1  # type: ignore[attr-defined]
del n.id
print(vars(n), failed(lambda: n.id), failed(lambda: repr(n)), failed(lambda: n.__replace__()), failed(lambda: setattr(ast.Name, "x", 1)), ast.Name.x, failed(lambda: delattr(ast.Name, "x")), failed(lambda: setattr(ast.AST, "_fields", ("z",))), ast.AST._fields, ast.AST.__flags__ & 256, ast.Name.__flags__ & 256, type(ast.Name).__name__)  # type: ignore[attr-defined,no-untyped-call]
# ast's functions over nodes a program builds (ast.dump imports _colorize, whose `type` statement needs _typing: the last line)
print(ast.dump(b), ast.unparse(b), ast.literal_eval(ast.Constant(7)), ast.literal_eval(ast.Tuple([ast.Constant(1), ast.Constant("a")], ast.Load())), list(ast.iter_fields(b)), [type(n).__name__ for n in ast.walk(b)], ast.dump(ast.copy_location(ast.Constant(2), ast.Constant(1, lineno=3, col_offset=4)), include_attributes=True), ast.dump(ast.fix_missing_locations(ast.Expr(ast.Constant(1), lineno=1, col_offset=0)), include_attributes=True), ast.dump(ast.Module([ast.Expr(ast.Constant(1))], []), indent=2), ast.dump(b, annotate_fields=False), ast.get_docstring(ast.Module([ast.Expr(ast.Constant("doc"))], [])), ast.unparse(ast.Module([ast.Assign([ast.Name("x", ast.Store())], ast.Constant(1), lineno=1)], [])), ast.unparse(ast.Constant("a'b")), failed(lambda: ast.dump(n)))  # type: ignore[no-untyped-call]
