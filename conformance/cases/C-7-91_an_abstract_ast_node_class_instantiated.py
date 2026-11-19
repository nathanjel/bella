# clause: C-7-91
# spec: section 7 (ast, warnings)
# status: P1
# source: Python/Python-ast.c (ast_type_init: state->abstract_types, PyErr_WarnFormat), Parser/asdl_c.py
"""The node classes of ast that stand for a kind of node and not for a node: AST itself, and mod, stmt, expr and the other
sums of the grammar. Instantiating one still works in 3.15 and gives a DeprecationWarning that names the class. It is the
class itself that is abstract: a class a program derives from one is not, whatever it is called. The warning comes before
the arguments are looked at, so a wrong call warns and then fails."""
import ast
import warnings

ABSTRACT = [ast.AST, ast.mod, ast.stmt, ast.expr, ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop, ast.excepthandler,
            ast.pattern, ast.type_ignore, ast.type_param]


class Mine(ast.expr):
    pass


class MineOfAST(ast.AST):
    pass


class expr(ast.expr):  # noqa: N801  # the name of an abstract class, in a class that is not one
    pass


expr.__module__ = "ast"

for cls in ABSTRACT:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        made = cls()
    print(f"{cls.__name__}: a {type(made).__name__}, _fields {made._fields}")
    for w in caught:
        print(f"    {w.category.__name__} at line {w.lineno}, this file {w.filename == __file__}: {w.message}")

for cls in (ast.Load, ast.Add, ast.Pass, ast.Module, Mine, MineOfAST, expr):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        made = cls()
    print(f"{cls.__name__}: a {type(made).__name__}, warnings {len(caught)}")

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    placed = ast.expr(lineno=3, col_offset=1)
    print("with its attributes:", placed.lineno, placed.col_offset, len(caught))
    try:
        ast.stmt(5)  # type: ignore[call-arg]
    except TypeError:
        print("a positional argument it has no field for: TypeError, after", len(caught), "warnings")
    try:
        ast.expr(nothing=1)  # type: ignore[call-arg]
        print("a keyword it has no field for:", len(caught), "warnings", [w.category.__name__ for w in caught[2:]])
    except TypeError:
        print("a keyword it has no field for: TypeError, after", len(caught), "warnings")

with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        ast.expr()
    except DeprecationWarning:
        print("as an error: DeprecationWarning, and no node")
