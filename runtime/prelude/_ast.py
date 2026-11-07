"""_ast, in Python: the node classes of the pin's Python.asdl as Python/Python-ast.c makes them, each with its _fields, _attributes,
__match_args__, docstring, _field_types and the class attributes that are its optional fields' defaults, generated from CPython 3.15.2
(tools: the table in this file is the pin's; regenerate it there when the pin moves). AST's own methods are the C's: ast_type_init,
ast_type_reduce, ast_type_replace and ast_repr. Instantiating an abstract node class is a DeprecationWarning in CPython and stops by name here.
The parser is not here: compile() with PyCF_ONLY_AST, and so ast.parse(), stop by name."""

__all__ = ["AST", "Add", "And", "AnnAssign", "Assert", "Assign", "AsyncFor", "AsyncFunctionDef", "AsyncWith", "Attribute", "AugAssign", "Await", "BinOp", "BitAnd", "BitOr", "BitXor", "BoolOp", "Break", "Call", "ClassDef", "Compare", "Constant", "Continue", "Del", "Delete", "Dict", "DictComp", "Div", "Eq", "ExceptHandler", "Expr", "Expression", "FloorDiv", "For", "FormattedValue", "FunctionDef", "FunctionType", "GeneratorExp", "Global", "Gt", "GtE", "If", "IfExp", "Import", "ImportFrom", "In", "Interactive", "Interpolation", "Invert", "Is", "IsNot", "JoinedStr", "LShift", "Lambda", "List", "ListComp", "Load", "Lt", "LtE", "MatMult", "Match", "MatchAs", "MatchClass", "MatchMapping", "MatchOr", "MatchSequence", "MatchSingleton", "MatchStar", "MatchValue", "Mod", "Module", "Mult", "Name", "NamedExpr", "Nonlocal", "Not", "NotEq", "NotIn", "Or", "ParamSpec", "Pass", "Pow", "PyCF_ALLOW_TOP_LEVEL_AWAIT", "PyCF_ONLY_AST", "PyCF_OPTIMIZED_AST", "PyCF_TYPE_COMMENTS", "RShift", "Raise", "Return", "Set", "SetComp", "Slice", "Starred", "Store", "Sub", "Subscript", "TemplateStr", "Try", "TryStar", "Tuple", "TypeAlias", "TypeIgnore", "TypeVar", "TypeVarTuple", "UAdd", "USub", "UnaryOp", "While", "With", "Yield", "YieldFrom", "alias", "arg", "arguments", "boolop", "cmpop", "comprehension", "excepthandler", "expr", "expr_context", "keyword", "match_case", "mod", "operator", "pattern", "stmt", "type_ignore", "type_param", "unaryop", "withitem"]

__name__ = "_ast"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing
    _tp_name: Callable[..., str] = _missing

PyCF_ONLY_AST = 1024
PyCF_TYPE_COMMENTS = 4096
PyCF_ALLOW_TOP_LEVEL_AWAIT = 8192
PyCF_OPTIMIZED_AST = 33792

_GENERIC_ALIAS = type(list[int])                # Py_GenericAliasType
_UNION = type(int | None)                        # _PyUnion_Type
_ABSTRACT: frozenset[str] = frozenset(('boolop', 'cmpop', 'excepthandler', 'expr', 'expr_context', 'mod', 'operator', 'pattern', 'stmt', 'type_ignore', 'type_param', 'unaryop'))
_NO_REPR_DEPTH = 3


def _full_name(value: object) -> str:            # %T
    cls = type(value)
    return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__


def _format_missing(missing: set[str], fields: tuple[str, ...]) -> str:   # format_missing: in the fields' order, with and and commas
    total = left = len(missing)
    out: list[str] = []
    for name in fields:
        if name not in missing:
            continue
        if left == 1:
            out.append("'" + name + "'")
        elif total == 2:
            out.append("'" + name + "' and ")
        elif left == 2:
            out.append("'" + name + "', and ")
        else:
            out.append("'" + name + "', ")
        left -= 1
    return "".join(out)


def _repr_list(value: object, depth: int) -> str:   # ast_repr_list: the first and the last item, an ellipsis between
    items: list[object] = list(value)  # type: ignore[call-overload]
    if not items:
        return repr(value)
    is_list = isinstance(value, list)
    parts = [("[" if is_list else "(")]
    shown = items[:1] + (items[-1:] if len(items) > 1 else [])
    for i, item in enumerate(shown):
        if i > 0:
            parts.append(", ")
        parts.append(_repr_depth(item, depth - 1) if isinstance(item, AST) else repr(item))
        if i == 0 and len(items) > 2:
            parts.append(", ...")
    parts.append("]" if is_list else ")")
    return "".join(parts)


def _repr_depth(self: object, depth: int) -> str:   # ast_repr_max_depth
    name = type(self).__name__
    if depth <= 0:
        return name + "(...)"
    if any(entry is self for entry in _in_repr):   # Py_ReprEnter: by identity, never by __eq__ (A13 #7, G13 #3)
        return name + "(...)"
    fields = type(self)._fields  # type: ignore[attr-defined]
    if len(fields) == 0:
        return name + "()"
    _in_repr.append(self)
    try:
        parts = [name, "("]
        for i, field in enumerate(fields):
            value = getattr(self, field)
            if isinstance(value, (list, tuple)):
                shown = _repr_list(value, depth)
            elif isinstance(value, AST):
                shown = _repr_depth(value, depth - 1)
            else:
                shown = repr(value)
            if i > 0:
                parts.append(", ")
            parts.append(field + "=" + shown)
        parts.append(")")
        return "".join(parts)
    finally:
        _in_repr.pop()


_in_repr: list[object] = []                      # Py_ReprEnter's stack, by identity


class AST:
    _fields: tuple[str, ...] = ()
    __match_args__ = ()
    _attributes: tuple[str, ...] = ()

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self = args[0]
        cls = type(self)
        if cls.__name__ in _ABSTRACT and cls.__module__ == "ast":
            _bella_refuse("instantiating the abstract AST node class " + _full_name(self) + " (a DeprecationWarning: warnings, step 3b)")
        fields = cls._fields
        numfields = len(fields)
        remaining = set(fields)
        positional = args[1:]
        if numfields < len(positional):
            raise TypeError(cls.__name__ + " constructor takes at most " + str(numfields) + " positional argument" + ("" if numfields == 1 else "s"))
        for i, value in enumerate(positional):
            setattr(self, fields[i], value)
            remaining.discard(fields[i])
        if kwds:
            attributes = None
            for key, value in kwds.items():
                if key in fields:
                    if key not in remaining:
                        raise TypeError(_full_name(self) + " got multiple values for argument " + repr(key))
                    remaining.discard(key)
                else:
                    if attributes is None:
                        attributes = cls._attributes
                    if key not in attributes:
                        raise TypeError(_full_name(self) + ".__init__ got an unexpected keyword argument " + repr(key))
                setattr(self, key, value)
        if remaining:
            field_types = getattr(cls, "_field_types", None)
            if field_types is None:
                return
            missing: set[str] = set()
            for name in list(remaining):
                if name not in field_types:
                    raise TypeError("Field " + repr(name) + " is missing from " + _full_name(self) + "._field_types")
                kind = field_types[name]
                if isinstance(kind, type) and kind is expr_context:
                    setattr(self, name, _load_singleton)
                elif type(kind) is _GENERIC_ALIAS:   # list[expr]: an empty list
                    setattr(self, name, [])
                elif type(kind) is _UNION:           # expr | None: nothing, the class attribute is None
                    pass
                else:
                    missing.add(name)
            if missing:
                raise TypeError(_full_name(self) + ".__init__ missing " + str(len(missing)) + " required positional argument" + ("" if len(missing) == 1 else "s") + ": " + _format_missing(missing, fields))

    def __reduce__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("AST.__reduce__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("AST.__reduce__() takes no arguments (" + str(len(args) - 1) + " given)")
        self = args[0]
        d = getattr(self, "__dict__", None)
        if d is None:
            return type(self), ()
        fields = getattr(type(self), "_fields", None)
        if fields is None:
            return type(self), (), d
        positional: list[object] = []
        for name in fields:
            if name not in d:
                break
            positional.append(None)
        return type(self), tuple(positional), d

    def __replace__(*args: object, **kwds: object) -> object:  # noqa: N805
        if len(args) != 1:
            raise TypeError("__replace__() takes no positional arguments")
        self = args[0]
        cls = type(self)
        payload: dict[str, object] = {}
        d = getattr(self, "__dict__", None)
        if d is not None:
            for keys in (getattr(cls, "_fields", None), getattr(cls, "_attributes", None)):
                if keys is None:
                    continue
                for key in keys:
                    if key in d:
                        payload[key] = d[key]
        payload.update(kwds)
        return cls(**payload)

    def __repr__(self) -> str:
        return _repr_depth(self, _NO_REPR_DEPTH)


class mod(AST):
    __doc__ = 'mod = Module(stmt* body, type_ignore* type_ignores)\n    | Interactive(stmt* body)\n    | Expression(expr body)\n    | FunctionType(expr* argtypes, expr returns)'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class Module(mod):
    __doc__ = 'Module(stmt* body, type_ignore* type_ignores)'
    _fields = ('body', 'type_ignores')
    __match_args__ = ('body', 'type_ignores')


class Interactive(mod):
    __doc__ = 'Interactive(stmt* body)'
    _fields = ('body',)
    __match_args__ = ('body',)


class Expression(mod):
    __doc__ = 'Expression(expr body)'
    _fields = ('body',)
    __match_args__ = ('body',)


class FunctionType(mod):
    __doc__ = 'FunctionType(expr* argtypes, expr returns)'
    _fields = ('argtypes', 'returns')
    __match_args__ = ('argtypes', 'returns')


class stmt(AST):
    __doc__ = 'stmt = FunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)\n     | AsyncFunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)\n     | ClassDef(identifier name, expr* bases, keyword* keywords, stmt* body, expr* decorator_list, type_param* type_params)\n     | Return(expr? value)\n     | Delete(expr* targets)\n     | Assign(expr* targets, expr value, string? type_comment)\n     | TypeAlias(expr name, type_param* type_params, expr value)\n     | AugAssign(expr target, operator op, expr value)\n     | AnnAssign(expr target, expr annotation, expr? value, int simple)\n     | For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)\n     | AsyncFor(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)\n     | While(expr test, stmt* body, stmt* orelse)\n     | If(expr test, stmt* body, stmt* orelse)\n     | With(withitem* items, stmt* body, string? type_comment)\n     | AsyncWith(withitem* items, stmt* body, string? type_comment)\n     | Match(expr subject, match_case* cases)\n     | Raise(expr? exc, expr? cause)\n     | Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)\n     | TryStar(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)\n     | Assert(expr test, expr? msg)\n     | Import(alias* names, int? is_lazy)\n     | ImportFrom(identifier? module, alias* names, int? level, int? is_lazy)\n     | Global(identifier* names)\n     | Nonlocal(identifier* names)\n     | Expr(expr value)\n     | Pass\n     | Break\n     | Continue'
    _fields = ()
    __match_args__ = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None


class FunctionDef(stmt):
    __doc__ = 'FunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)'
    _fields = ('name', 'args', 'body', 'decorator_list', 'returns', 'type_comment', 'type_params')
    __match_args__ = ('name', 'args', 'body', 'decorator_list', 'returns', 'type_comment', 'type_params')
    returns = None
    type_comment = None


class AsyncFunctionDef(stmt):
    __doc__ = 'AsyncFunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)'
    _fields = ('name', 'args', 'body', 'decorator_list', 'returns', 'type_comment', 'type_params')
    __match_args__ = ('name', 'args', 'body', 'decorator_list', 'returns', 'type_comment', 'type_params')
    returns = None
    type_comment = None


class ClassDef(stmt):
    __doc__ = 'ClassDef(identifier name, expr* bases, keyword* keywords, stmt* body, expr* decorator_list, type_param* type_params)'
    _fields = ('name', 'bases', 'keywords', 'body', 'decorator_list', 'type_params')
    __match_args__ = ('name', 'bases', 'keywords', 'body', 'decorator_list', 'type_params')


class Return(stmt):
    __doc__ = 'Return(expr? value)'
    _fields = ('value',)
    __match_args__ = ('value',)
    value = None


class Delete(stmt):
    __doc__ = 'Delete(expr* targets)'
    _fields = ('targets',)
    __match_args__ = ('targets',)


class Assign(stmt):
    __doc__ = 'Assign(expr* targets, expr value, string? type_comment)'
    _fields = ('targets', 'value', 'type_comment')
    __match_args__ = ('targets', 'value', 'type_comment')
    type_comment = None


class TypeAlias(stmt):
    __doc__ = 'TypeAlias(expr name, type_param* type_params, expr value)'
    _fields = ('name', 'type_params', 'value')
    __match_args__ = ('name', 'type_params', 'value')


class AugAssign(stmt):
    __doc__ = 'AugAssign(expr target, operator op, expr value)'
    _fields = ('target', 'op', 'value')
    __match_args__ = ('target', 'op', 'value')


class AnnAssign(stmt):
    __doc__ = 'AnnAssign(expr target, expr annotation, expr? value, int simple)'
    _fields = ('target', 'annotation', 'value', 'simple')
    __match_args__ = ('target', 'annotation', 'value', 'simple')
    value = None


class For(stmt):
    __doc__ = 'For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)'
    _fields = ('target', 'iter', 'body', 'orelse', 'type_comment')
    __match_args__ = ('target', 'iter', 'body', 'orelse', 'type_comment')
    type_comment = None


class AsyncFor(stmt):
    __doc__ = 'AsyncFor(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)'
    _fields = ('target', 'iter', 'body', 'orelse', 'type_comment')
    __match_args__ = ('target', 'iter', 'body', 'orelse', 'type_comment')
    type_comment = None


class While(stmt):
    __doc__ = 'While(expr test, stmt* body, stmt* orelse)'
    _fields = ('test', 'body', 'orelse')
    __match_args__ = ('test', 'body', 'orelse')


class If(stmt):
    __doc__ = 'If(expr test, stmt* body, stmt* orelse)'
    _fields = ('test', 'body', 'orelse')
    __match_args__ = ('test', 'body', 'orelse')


class With(stmt):
    __doc__ = 'With(withitem* items, stmt* body, string? type_comment)'
    _fields = ('items', 'body', 'type_comment')
    __match_args__ = ('items', 'body', 'type_comment')
    type_comment = None


class AsyncWith(stmt):
    __doc__ = 'AsyncWith(withitem* items, stmt* body, string? type_comment)'
    _fields = ('items', 'body', 'type_comment')
    __match_args__ = ('items', 'body', 'type_comment')
    type_comment = None


class Match(stmt):
    __doc__ = 'Match(expr subject, match_case* cases)'
    _fields = ('subject', 'cases')
    __match_args__ = ('subject', 'cases')


class Raise(stmt):
    __doc__ = 'Raise(expr? exc, expr? cause)'
    _fields = ('exc', 'cause')
    __match_args__ = ('exc', 'cause')
    exc = None
    cause = None


class Try(stmt):
    __doc__ = 'Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)'
    _fields = ('body', 'handlers', 'orelse', 'finalbody')
    __match_args__ = ('body', 'handlers', 'orelse', 'finalbody')


class TryStar(stmt):
    __doc__ = 'TryStar(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)'
    _fields = ('body', 'handlers', 'orelse', 'finalbody')
    __match_args__ = ('body', 'handlers', 'orelse', 'finalbody')


class Assert(stmt):
    __doc__ = 'Assert(expr test, expr? msg)'
    _fields = ('test', 'msg')
    __match_args__ = ('test', 'msg')
    msg = None


class Import(stmt):
    __doc__ = 'Import(alias* names, int? is_lazy)'
    _fields = ('names', 'is_lazy')
    __match_args__ = ('names', 'is_lazy')
    is_lazy = None


class ImportFrom(stmt):
    __doc__ = 'ImportFrom(identifier? module, alias* names, int? level, int? is_lazy)'
    _fields = ('module', 'names', 'level', 'is_lazy')
    __match_args__ = ('module', 'names', 'level', 'is_lazy')
    module = None
    level = None
    is_lazy = None


class Global(stmt):
    __doc__ = 'Global(identifier* names)'
    _fields = ('names',)
    __match_args__ = ('names',)


class Nonlocal(stmt):
    __doc__ = 'Nonlocal(identifier* names)'
    _fields = ('names',)
    __match_args__ = ('names',)


class Expr(stmt):
    __doc__ = 'Expr(expr value)'
    _fields = ('value',)
    __match_args__ = ('value',)


class Pass(stmt):
    __doc__ = 'Pass'
    _fields = ()
    __match_args__ = ()


class Break(stmt):
    __doc__ = 'Break'
    _fields = ()
    __match_args__ = ()


class Continue(stmt):
    __doc__ = 'Continue'
    _fields = ()
    __match_args__ = ()


class expr(AST):
    __doc__ = 'expr = BoolOp(boolop op, expr* values)\n     | NamedExpr(expr target, expr value)\n     | BinOp(expr left, operator op, expr right)\n     | UnaryOp(unaryop op, expr operand)\n     | Lambda(arguments args, expr body)\n     | IfExp(expr test, expr body, expr orelse)\n     | Dict(expr?* keys, expr* values)\n     | Set(expr* elts)\n     | ListComp(expr elt, comprehension* generators)\n     | SetComp(expr elt, comprehension* generators)\n     | DictComp(expr key, expr? value, comprehension* generators)\n     | GeneratorExp(expr elt, comprehension* generators)\n     | Await(expr value)\n     | Yield(expr? value)\n     | YieldFrom(expr value)\n     | Compare(expr left, cmpop* ops, expr* comparators)\n     | Call(expr func, expr* args, keyword* keywords)\n     | FormattedValue(expr value, int conversion, expr? format_spec)\n     | Interpolation(expr value, constant str, int conversion, expr? format_spec)\n     | JoinedStr(expr* values)\n     | TemplateStr(expr* values)\n     | Constant(constant value, string? kind)\n     | Attribute(expr value, identifier attr, expr_context ctx)\n     | Subscript(expr value, expr slice, expr_context ctx)\n     | Starred(expr value, expr_context ctx)\n     | Name(identifier id, expr_context ctx)\n     | List(expr* elts, expr_context ctx)\n     | Tuple(expr* elts, expr_context ctx)\n     | Slice(expr? lower, expr? upper, expr? step)'
    _fields = ()
    __match_args__ = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None


class BoolOp(expr):
    __doc__ = 'BoolOp(boolop op, expr* values)'
    _fields = ('op', 'values')
    __match_args__ = ('op', 'values')


class NamedExpr(expr):
    __doc__ = 'NamedExpr(expr target, expr value)'
    _fields = ('target', 'value')
    __match_args__ = ('target', 'value')


class BinOp(expr):
    __doc__ = 'BinOp(expr left, operator op, expr right)'
    _fields = ('left', 'op', 'right')
    __match_args__ = ('left', 'op', 'right')


class UnaryOp(expr):
    __doc__ = 'UnaryOp(unaryop op, expr operand)'
    _fields = ('op', 'operand')
    __match_args__ = ('op', 'operand')


class Lambda(expr):
    __doc__ = 'Lambda(arguments args, expr body)'
    _fields = ('args', 'body')
    __match_args__ = ('args', 'body')


class IfExp(expr):
    __doc__ = 'IfExp(expr test, expr body, expr orelse)'
    _fields = ('test', 'body', 'orelse')
    __match_args__ = ('test', 'body', 'orelse')


class Dict(expr):
    __doc__ = 'Dict(expr?* keys, expr* values)'
    _fields = ('keys', 'values')
    __match_args__ = ('keys', 'values')


class Set(expr):
    __doc__ = 'Set(expr* elts)'
    _fields = ('elts',)
    __match_args__ = ('elts',)


class ListComp(expr):
    __doc__ = 'ListComp(expr elt, comprehension* generators)'
    _fields = ('elt', 'generators')
    __match_args__ = ('elt', 'generators')


class SetComp(expr):
    __doc__ = 'SetComp(expr elt, comprehension* generators)'
    _fields = ('elt', 'generators')
    __match_args__ = ('elt', 'generators')


class DictComp(expr):
    __doc__ = 'DictComp(expr key, expr? value, comprehension* generators)'
    _fields = ('key', 'value', 'generators')
    __match_args__ = ('key', 'value', 'generators')
    value = None


class GeneratorExp(expr):
    __doc__ = 'GeneratorExp(expr elt, comprehension* generators)'
    _fields = ('elt', 'generators')
    __match_args__ = ('elt', 'generators')


class Await(expr):
    __doc__ = 'Await(expr value)'
    _fields = ('value',)
    __match_args__ = ('value',)


class Yield(expr):
    __doc__ = 'Yield(expr? value)'
    _fields = ('value',)
    __match_args__ = ('value',)
    value = None


class YieldFrom(expr):
    __doc__ = 'YieldFrom(expr value)'
    _fields = ('value',)
    __match_args__ = ('value',)


class Compare(expr):
    __doc__ = 'Compare(expr left, cmpop* ops, expr* comparators)'
    _fields = ('left', 'ops', 'comparators')
    __match_args__ = ('left', 'ops', 'comparators')


class Call(expr):
    __doc__ = 'Call(expr func, expr* args, keyword* keywords)'
    _fields = ('func', 'args', 'keywords')
    __match_args__ = ('func', 'args', 'keywords')


class FormattedValue(expr):
    __doc__ = 'FormattedValue(expr value, int conversion, expr? format_spec)'
    _fields = ('value', 'conversion', 'format_spec')
    __match_args__ = ('value', 'conversion', 'format_spec')
    format_spec = None


class Interpolation(expr):
    __doc__ = 'Interpolation(expr value, constant str, int conversion, expr? format_spec)'
    _fields = ('value', 'str', 'conversion', 'format_spec')
    __match_args__ = ('value', 'str', 'conversion', 'format_spec')
    format_spec = None


class JoinedStr(expr):
    __doc__ = 'JoinedStr(expr* values)'
    _fields = ('values',)
    __match_args__ = ('values',)


class TemplateStr(expr):
    __doc__ = 'TemplateStr(expr* values)'
    _fields = ('values',)
    __match_args__ = ('values',)


class Constant(expr):
    __doc__ = 'Constant(constant value, string? kind)'
    _fields = ('value', 'kind')
    __match_args__ = ('value', 'kind')
    kind = None


class Attribute(expr):
    __doc__ = 'Attribute(expr value, identifier attr, expr_context ctx)'
    _fields = ('value', 'attr', 'ctx')
    __match_args__ = ('value', 'attr', 'ctx')


class Subscript(expr):
    __doc__ = 'Subscript(expr value, expr slice, expr_context ctx)'
    _fields = ('value', 'slice', 'ctx')
    __match_args__ = ('value', 'slice', 'ctx')


class Starred(expr):
    __doc__ = 'Starred(expr value, expr_context ctx)'
    _fields = ('value', 'ctx')
    __match_args__ = ('value', 'ctx')


class Name(expr):
    __doc__ = 'Name(identifier id, expr_context ctx)'
    _fields = ('id', 'ctx')
    __match_args__ = ('id', 'ctx')


class List(expr):
    __doc__ = 'List(expr* elts, expr_context ctx)'
    _fields = ('elts', 'ctx')
    __match_args__ = ('elts', 'ctx')


class Tuple(expr):
    __doc__ = 'Tuple(expr* elts, expr_context ctx)'
    _fields = ('elts', 'ctx')
    __match_args__ = ('elts', 'ctx')


class Slice(expr):
    __doc__ = 'Slice(expr? lower, expr? upper, expr? step)'
    _fields = ('lower', 'upper', 'step')
    __match_args__ = ('lower', 'upper', 'step')
    lower = None
    upper = None
    step = None


class expr_context(AST):
    __doc__ = 'expr_context = Load | Store | Del'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class Load(expr_context):
    __doc__ = 'Load'
    _fields = ()
    __match_args__ = ()


class Store(expr_context):
    __doc__ = 'Store'
    _fields = ()
    __match_args__ = ()


class Del(expr_context):
    __doc__ = 'Del'
    _fields = ()
    __match_args__ = ()


class boolop(AST):
    __doc__ = 'boolop = And | Or'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class And(boolop):
    __doc__ = 'And'
    _fields = ()
    __match_args__ = ()


class Or(boolop):
    __doc__ = 'Or'
    _fields = ()
    __match_args__ = ()


class operator(AST):
    __doc__ = 'operator = Add | Sub | Mult | MatMult | Div | Mod | Pow | LShift | RShift | BitOr | BitXor | BitAnd | FloorDiv'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class Add(operator):
    __doc__ = 'Add'
    _fields = ()
    __match_args__ = ()


class Sub(operator):
    __doc__ = 'Sub'
    _fields = ()
    __match_args__ = ()


class Mult(operator):
    __doc__ = 'Mult'
    _fields = ()
    __match_args__ = ()


class MatMult(operator):
    __doc__ = 'MatMult'
    _fields = ()
    __match_args__ = ()


class Div(operator):
    __doc__ = 'Div'
    _fields = ()
    __match_args__ = ()


class Mod(operator):
    __doc__ = 'Mod'
    _fields = ()
    __match_args__ = ()


class Pow(operator):
    __doc__ = 'Pow'
    _fields = ()
    __match_args__ = ()


class LShift(operator):
    __doc__ = 'LShift'
    _fields = ()
    __match_args__ = ()


class RShift(operator):
    __doc__ = 'RShift'
    _fields = ()
    __match_args__ = ()


class BitOr(operator):
    __doc__ = 'BitOr'
    _fields = ()
    __match_args__ = ()


class BitXor(operator):
    __doc__ = 'BitXor'
    _fields = ()
    __match_args__ = ()


class BitAnd(operator):
    __doc__ = 'BitAnd'
    _fields = ()
    __match_args__ = ()


class FloorDiv(operator):
    __doc__ = 'FloorDiv'
    _fields = ()
    __match_args__ = ()


class unaryop(AST):
    __doc__ = 'unaryop = Invert | Not | UAdd | USub'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class Invert(unaryop):
    __doc__ = 'Invert'
    _fields = ()
    __match_args__ = ()


class Not(unaryop):
    __doc__ = 'Not'
    _fields = ()
    __match_args__ = ()


class UAdd(unaryop):
    __doc__ = 'UAdd'
    _fields = ()
    __match_args__ = ()


class USub(unaryop):
    __doc__ = 'USub'
    _fields = ()
    __match_args__ = ()


class cmpop(AST):
    __doc__ = 'cmpop = Eq | NotEq | Lt | LtE | Gt | GtE | Is | IsNot | In | NotIn'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class Eq(cmpop):
    __doc__ = 'Eq'
    _fields = ()
    __match_args__ = ()


class NotEq(cmpop):
    __doc__ = 'NotEq'
    _fields = ()
    __match_args__ = ()


class Lt(cmpop):
    __doc__ = 'Lt'
    _fields = ()
    __match_args__ = ()


class LtE(cmpop):
    __doc__ = 'LtE'
    _fields = ()
    __match_args__ = ()


class Gt(cmpop):
    __doc__ = 'Gt'
    _fields = ()
    __match_args__ = ()


class GtE(cmpop):
    __doc__ = 'GtE'
    _fields = ()
    __match_args__ = ()


class Is(cmpop):
    __doc__ = 'Is'
    _fields = ()
    __match_args__ = ()


class IsNot(cmpop):
    __doc__ = 'IsNot'
    _fields = ()
    __match_args__ = ()


class In(cmpop):
    __doc__ = 'In'
    _fields = ()
    __match_args__ = ()


class NotIn(cmpop):
    __doc__ = 'NotIn'
    _fields = ()
    __match_args__ = ()


class comprehension(AST):
    __doc__ = 'comprehension(expr target, expr iter, expr* ifs, int is_async)'
    _fields = ('target', 'iter', 'ifs', 'is_async')
    __match_args__ = ('target', 'iter', 'ifs', 'is_async')
    _attributes = ()


class excepthandler(AST):
    __doc__ = 'excepthandler = ExceptHandler(expr? type, identifier? name, stmt* body)'
    _fields = ()
    __match_args__ = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None


class ExceptHandler(excepthandler):
    __doc__ = 'ExceptHandler(expr? type, identifier? name, stmt* body)'
    _fields = ('type', 'name', 'body')
    __match_args__ = ('type', 'name', 'body')
    type = None
    name = None


class arguments(AST):
    __doc__ = 'arguments(arg* posonlyargs, arg* args, arg? vararg, arg* kwonlyargs, expr?* kw_defaults, arg? kwarg, expr* defaults)'
    _fields = ('posonlyargs', 'args', 'vararg', 'kwonlyargs', 'kw_defaults', 'kwarg', 'defaults')
    __match_args__ = ('posonlyargs', 'args', 'vararg', 'kwonlyargs', 'kw_defaults', 'kwarg', 'defaults')
    _attributes = ()
    vararg = None
    kwarg = None


class arg(AST):
    __doc__ = 'arg(identifier arg, expr? annotation, string? type_comment)'
    _fields = ('arg', 'annotation', 'type_comment')
    __match_args__ = ('arg', 'annotation', 'type_comment')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    annotation = None
    type_comment = None
    end_lineno = None
    end_col_offset = None


class keyword(AST):
    __doc__ = 'keyword(identifier? arg, expr value)'
    _fields = ('arg', 'value')
    __match_args__ = ('arg', 'value')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    arg = None
    end_lineno = None
    end_col_offset = None


class alias(AST):
    __doc__ = 'alias(identifier name, identifier? asname)'
    _fields = ('name', 'asname')
    __match_args__ = ('name', 'asname')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    asname = None
    end_lineno = None
    end_col_offset = None


class withitem(AST):
    __doc__ = 'withitem(expr context_expr, expr? optional_vars)'
    _fields = ('context_expr', 'optional_vars')
    __match_args__ = ('context_expr', 'optional_vars')
    _attributes = ()
    optional_vars = None


class match_case(AST):
    __doc__ = 'match_case(pattern pattern, expr? guard, stmt* body)'
    _fields = ('pattern', 'guard', 'body')
    __match_args__ = ('pattern', 'guard', 'body')
    _attributes = ()
    guard = None


class pattern(AST):
    __doc__ = 'pattern = MatchValue(expr value)\n        | MatchSingleton(constant value)\n        | MatchSequence(pattern* patterns)\n        | MatchMapping(expr* keys, pattern* patterns, identifier? rest)\n        | MatchClass(expr cls, pattern* patterns, identifier* kwd_attrs, pattern* kwd_patterns)\n        | MatchStar(identifier? name)\n        | MatchAs(pattern? pattern, identifier? name)\n        | MatchOr(pattern* patterns)'
    _fields = ()
    __match_args__ = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')


class MatchValue(pattern):
    __doc__ = 'MatchValue(expr value)'
    _fields = ('value',)
    __match_args__ = ('value',)


class MatchSingleton(pattern):
    __doc__ = 'MatchSingleton(constant value)'
    _fields = ('value',)
    __match_args__ = ('value',)


class MatchSequence(pattern):
    __doc__ = 'MatchSequence(pattern* patterns)'
    _fields = ('patterns',)
    __match_args__ = ('patterns',)


class MatchMapping(pattern):
    __doc__ = 'MatchMapping(expr* keys, pattern* patterns, identifier? rest)'
    _fields = ('keys', 'patterns', 'rest')
    __match_args__ = ('keys', 'patterns', 'rest')
    rest = None


class MatchClass(pattern):
    __doc__ = 'MatchClass(expr cls, pattern* patterns, identifier* kwd_attrs, pattern* kwd_patterns)'
    _fields = ('cls', 'patterns', 'kwd_attrs', 'kwd_patterns')
    __match_args__ = ('cls', 'patterns', 'kwd_attrs', 'kwd_patterns')


class MatchStar(pattern):
    __doc__ = 'MatchStar(identifier? name)'
    _fields = ('name',)
    __match_args__ = ('name',)
    name = None


class MatchAs(pattern):
    __doc__ = 'MatchAs(pattern? pattern, identifier? name)'
    _fields = ('pattern', 'name')
    __match_args__ = ('pattern', 'name')
    pattern = None
    name = None


class MatchOr(pattern):
    __doc__ = 'MatchOr(pattern* patterns)'
    _fields = ('patterns',)
    __match_args__ = ('patterns',)


class type_ignore(AST):
    __doc__ = 'type_ignore = TypeIgnore(int lineno, string tag)'
    _fields = ()
    __match_args__ = ()
    _attributes = ()


class TypeIgnore(type_ignore):
    __doc__ = 'TypeIgnore(int lineno, string tag)'
    _fields = ('lineno', 'tag')
    __match_args__ = ('lineno', 'tag')


class type_param(AST):
    __doc__ = 'type_param = TypeVar(identifier name, expr? bound, expr? default_value)\n           | ParamSpec(identifier name, expr? default_value)\n           | TypeVarTuple(identifier name, expr? default_value)'
    _fields = ()
    __match_args__ = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')


class TypeVar(type_param):
    __doc__ = 'TypeVar(identifier name, expr? bound, expr? default_value)'
    _fields = ('name', 'bound', 'default_value')
    __match_args__ = ('name', 'bound', 'default_value')
    bound = None
    default_value = None


class ParamSpec(type_param):
    __doc__ = 'ParamSpec(identifier name, expr? default_value)'
    _fields = ('name', 'default_value')
    __match_args__ = ('name', 'default_value')
    default_value = None


class TypeVarTuple(type_param):
    __doc__ = 'TypeVarTuple(identifier name, expr? default_value)'
    _fields = ('name', 'default_value')
    __match_args__ = ('name', 'default_value')
    default_value = None


_load_singleton = Load()

Module._field_types = {'body': list[stmt], 'type_ignores': list[type_ignore]}
Interactive._field_types = {'body': list[stmt]}
Expression._field_types = {'body': expr}
FunctionType._field_types = {'argtypes': list[expr], 'returns': expr}
FunctionDef._field_types = {'name': str, 'args': arguments, 'body': list[stmt], 'decorator_list': list[expr], 'returns': expr | None, 'type_comment': str | None, 'type_params': list[type_param]}
AsyncFunctionDef._field_types = {'name': str, 'args': arguments, 'body': list[stmt], 'decorator_list': list[expr], 'returns': expr | None, 'type_comment': str | None, 'type_params': list[type_param]}
ClassDef._field_types = {'name': str, 'bases': list[expr], 'keywords': list[keyword], 'body': list[stmt], 'decorator_list': list[expr], 'type_params': list[type_param]}
Return._field_types = {'value': expr | None}
Delete._field_types = {'targets': list[expr]}
Assign._field_types = {'targets': list[expr], 'value': expr, 'type_comment': str | None}
TypeAlias._field_types = {'name': expr, 'type_params': list[type_param], 'value': expr}
AugAssign._field_types = {'target': expr, 'op': operator, 'value': expr}
AnnAssign._field_types = {'target': expr, 'annotation': expr, 'value': expr | None, 'simple': int}
For._field_types = {'target': expr, 'iter': expr, 'body': list[stmt], 'orelse': list[stmt], 'type_comment': str | None}
AsyncFor._field_types = {'target': expr, 'iter': expr, 'body': list[stmt], 'orelse': list[stmt], 'type_comment': str | None}
While._field_types = {'test': expr, 'body': list[stmt], 'orelse': list[stmt]}
If._field_types = {'test': expr, 'body': list[stmt], 'orelse': list[stmt]}
With._field_types = {'items': list[withitem], 'body': list[stmt], 'type_comment': str | None}
AsyncWith._field_types = {'items': list[withitem], 'body': list[stmt], 'type_comment': str | None}
Match._field_types = {'subject': expr, 'cases': list[match_case]}
Raise._field_types = {'exc': expr | None, 'cause': expr | None}
Try._field_types = {'body': list[stmt], 'handlers': list[excepthandler], 'orelse': list[stmt], 'finalbody': list[stmt]}
TryStar._field_types = {'body': list[stmt], 'handlers': list[excepthandler], 'orelse': list[stmt], 'finalbody': list[stmt]}
Assert._field_types = {'test': expr, 'msg': expr | None}
Import._field_types = {'names': list[alias], 'is_lazy': int | None}
ImportFrom._field_types = {'module': str | None, 'names': list[alias], 'level': int | None, 'is_lazy': int | None}
Global._field_types = {'names': list[str]}
Nonlocal._field_types = {'names': list[str]}
Expr._field_types = {'value': expr}
Pass._field_types = {}
Break._field_types = {}
Continue._field_types = {}
BoolOp._field_types = {'op': boolop, 'values': list[expr]}
NamedExpr._field_types = {'target': expr, 'value': expr}
BinOp._field_types = {'left': expr, 'op': operator, 'right': expr}
UnaryOp._field_types = {'op': unaryop, 'operand': expr}
Lambda._field_types = {'args': arguments, 'body': expr}
IfExp._field_types = {'test': expr, 'body': expr, 'orelse': expr}
Dict._field_types = {'keys': list[expr], 'values': list[expr]}
Set._field_types = {'elts': list[expr]}
ListComp._field_types = {'elt': expr, 'generators': list[comprehension]}
SetComp._field_types = {'elt': expr, 'generators': list[comprehension]}
DictComp._field_types = {'key': expr, 'value': expr | None, 'generators': list[comprehension]}
GeneratorExp._field_types = {'elt': expr, 'generators': list[comprehension]}
Await._field_types = {'value': expr}
Yield._field_types = {'value': expr | None}
YieldFrom._field_types = {'value': expr}
Compare._field_types = {'left': expr, 'ops': list[cmpop], 'comparators': list[expr]}
Call._field_types = {'func': expr, 'args': list[expr], 'keywords': list[keyword]}
FormattedValue._field_types = {'value': expr, 'conversion': int, 'format_spec': expr | None}
Interpolation._field_types = {'value': expr, 'str': object, 'conversion': int, 'format_spec': expr | None}
JoinedStr._field_types = {'values': list[expr]}
TemplateStr._field_types = {'values': list[expr]}
Constant._field_types = {'value': object, 'kind': str | None}
Attribute._field_types = {'value': expr, 'attr': str, 'ctx': expr_context}
Subscript._field_types = {'value': expr, 'slice': expr, 'ctx': expr_context}
Starred._field_types = {'value': expr, 'ctx': expr_context}
Name._field_types = {'id': str, 'ctx': expr_context}
List._field_types = {'elts': list[expr], 'ctx': expr_context}
Tuple._field_types = {'elts': list[expr], 'ctx': expr_context}
Slice._field_types = {'lower': expr | None, 'upper': expr | None, 'step': expr | None}
Load._field_types = {}
Store._field_types = {}
Del._field_types = {}
And._field_types = {}
Or._field_types = {}
Add._field_types = {}
Sub._field_types = {}
Mult._field_types = {}
MatMult._field_types = {}
Div._field_types = {}
Mod._field_types = {}
Pow._field_types = {}
LShift._field_types = {}
RShift._field_types = {}
BitOr._field_types = {}
BitXor._field_types = {}
BitAnd._field_types = {}
FloorDiv._field_types = {}
Invert._field_types = {}
Not._field_types = {}
UAdd._field_types = {}
USub._field_types = {}
Eq._field_types = {}
NotEq._field_types = {}
Lt._field_types = {}
LtE._field_types = {}
Gt._field_types = {}
GtE._field_types = {}
Is._field_types = {}
IsNot._field_types = {}
In._field_types = {}
NotIn._field_types = {}
comprehension._field_types = {'target': expr, 'iter': expr, 'ifs': list[expr], 'is_async': int}
ExceptHandler._field_types = {'type': expr | None, 'name': str | None, 'body': list[stmt]}
arguments._field_types = {'posonlyargs': list[arg], 'args': list[arg], 'vararg': arg | None, 'kwonlyargs': list[arg], 'kw_defaults': list[expr], 'kwarg': arg | None, 'defaults': list[expr]}
arg._field_types = {'arg': str, 'annotation': expr | None, 'type_comment': str | None}
keyword._field_types = {'arg': str | None, 'value': expr}
alias._field_types = {'name': str, 'asname': str | None}
withitem._field_types = {'context_expr': expr, 'optional_vars': expr | None}
match_case._field_types = {'pattern': pattern, 'guard': expr | None, 'body': list[stmt]}
MatchValue._field_types = {'value': expr}
MatchSingleton._field_types = {'value': object}
MatchSequence._field_types = {'patterns': list[pattern]}
MatchMapping._field_types = {'keys': list[expr], 'patterns': list[pattern], 'rest': str | None}
MatchClass._field_types = {'cls': expr, 'patterns': list[pattern], 'kwd_attrs': list[str], 'kwd_patterns': list[pattern]}
MatchStar._field_types = {'name': str | None}
MatchAs._field_types = {'pattern': pattern | None, 'name': str | None}
MatchOr._field_types = {'patterns': list[pattern]}
TypeIgnore._field_types = {'lineno': int, 'tag': str}
TypeVar._field_types = {'name': str, 'bound': expr | None, 'default_value': expr | None}
ParamSpec._field_types = {'name': str, 'default_value': expr | None}
TypeVarTuple._field_types = {'name': str, 'default_value': expr | None}
# add_ast_annotations, and the classes' module: ast, not _ast (the C's tp_name is ast.X)
AST.__module__ = "ast"
for _node in (mod, Module, Interactive, Expression, FunctionType, stmt, FunctionDef, AsyncFunctionDef, ClassDef, Return, Delete, Assign, TypeAlias, AugAssign, AnnAssign, For, AsyncFor, While, If, With, AsyncWith, Match, Raise, Try, TryStar, Assert, Import, ImportFrom, Global, Nonlocal, Expr, Pass, Break, Continue, expr, BoolOp, NamedExpr, BinOp, UnaryOp, Lambda, IfExp, Dict, Set, ListComp, SetComp, DictComp, GeneratorExp, Await, Yield, YieldFrom, Compare, Call, FormattedValue, Interpolation, JoinedStr, TemplateStr, Constant, Attribute, Subscript, Starred, Name, List, Tuple, Slice, expr_context, Load, Store, Del, boolop, And, Or, operator, Add, Sub, Mult, MatMult, Div, Mod, Pow, LShift, RShift, BitOr, BitXor, BitAnd, FloorDiv, unaryop, Invert, Not, UAdd, USub, cmpop, Eq, NotEq, Lt, LtE, Gt, GtE, Is, IsNot, In, NotIn, comprehension, excepthandler, ExceptHandler, arguments, arg, keyword, alias, withitem, match_case, pattern, MatchValue, MatchSingleton, MatchSequence, MatchMapping, MatchClass, MatchStar, MatchAs, MatchOr, type_ignore, TypeIgnore, type_param, TypeVar, ParamSpec, TypeVarTuple):
    _node.__module__ = "ast"
    if "_field_types" in vars(_node):            # the abstract classes have none
        _node.__annotations__ = _node._field_types   # the same dict
