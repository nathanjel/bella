"""_opcode, in Python (Modules/_opcode.c): the opcode predicates and the compiler's descriptive tables, as CPython 3.15.2 has them,
read off the pinned interpreter by tools/opcode_tables.py (`make verify` checks them). opcode imports it while it loads (dis and inspect come through there),
and these are the calls its module body makes. stack_effect and get_executor are about code objects a compiled program does not
have and stop by name."""

__all__ = ["ENABLE_SPECIALIZATION", "get_executor", "get_intrinsic1_descs", "get_intrinsic2_descs", "get_nb_ops",
           "get_special_method_names", "get_specialization_stats", "has_arg", "has_const", "has_exc", "has_free", "has_jump",
           "has_local", "has_name", "is_valid", "stack_effect"]

__name__ = "_opcode"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _number_index                                # noqa: B018  # PyNumber_Index
except NameError:
    import operator
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing
    _number_index: Callable[[object], int] = operator.index

ENABLE_SPECIALIZATION = 1

# ---- the tables (tools/opcode_tables.py; the pin's _opcode over every opcode number) --------------------------------------------
_IS_VALID = frozenset([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266])
_HAS_ARG = frozenset([42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 128, 144, 145, 146, 147, 148, 149, 150, 152, 154, 155, 156, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 201, 202, 203, 204, 207, 216, 217, 218, 236, 238, 240, 241, 242, 243, 244, 246, 247, 248, 249, 250, 252, 254, 255, 257, 258, 259, 260, 261, 263, 264, 265, 266])
_HAS_CONST = frozenset([81])
_HAS_NAME = frozenset([59, 62, 63, 71, 72, 79, 90, 91, 92, 95, 109, 114, 115, 185, 195, 198, 199, 207, 248])
_HAS_JUMP = frozenset([66, 68, 74, 75, 76, 99, 100, 101, 102, 105, 175, 176, 177, 178, 181, 182, 202, 204, 236, 247, 257, 258, 259, 260])
_HAS_FREE = frozenset([60, 89, 96, 110])
_HAS_LOCAL = frozenset([3, 61, 82, 83, 84, 85, 86, 87, 88, 111, 112, 113, 261, 266])
_HAS_EXC = frozenset([263, 264, 265])
_INTRINSIC_1 = ['INTRINSIC_1_INVALID', 'INTRINSIC_PRINT', 'INTRINSIC_IMPORT_STAR', 'INTRINSIC_STOPITERATION_ERROR', 'INTRINSIC_ASYNC_GEN_WRAP', 'INTRINSIC_UNARY_POSITIVE', 'INTRINSIC_LIST_TO_TUPLE', 'INTRINSIC_TYPEVAR', 'INTRINSIC_PARAMSPEC', 'INTRINSIC_TYPEVARTUPLE', 'INTRINSIC_SUBSCRIPT_GENERIC', 'INTRINSIC_TYPEALIAS']
_INTRINSIC_2 = ['INTRINSIC_2_INVALID', 'INTRINSIC_PREP_RERAISE_STAR', 'INTRINSIC_TYPEVAR_WITH_BOUND', 'INTRINSIC_TYPEVAR_WITH_CONSTRAINTS', 'INTRINSIC_SET_FUNCTION_TYPE_PARAMS', 'INTRINSIC_SET_TYPEPARAM_DEFAULT']
_NB_OPS = [('NB_ADD', '+'), ('NB_AND', '&'), ('NB_FLOOR_DIVIDE', '//'), ('NB_LSHIFT', '<<'), ('NB_MATRIX_MULTIPLY', '@'), ('NB_MULTIPLY', '*'), ('NB_REMAINDER', '%'), ('NB_OR', '|'), ('NB_POWER', '**'), ('NB_RSHIFT', '>>'), ('NB_SUBTRACT', '-'), ('NB_TRUE_DIVIDE', '/'), ('NB_XOR', '^'), ('NB_INPLACE_ADD', '+='), ('NB_INPLACE_AND', '&='), ('NB_INPLACE_FLOOR_DIVIDE', '//='), ('NB_INPLACE_LSHIFT', '<<='), ('NB_INPLACE_MATRIX_MULTIPLY', '@='), ('NB_INPLACE_MULTIPLY', '*='), ('NB_INPLACE_REMAINDER', '%='), ('NB_INPLACE_OR', '|='), ('NB_INPLACE_POWER', '**='), ('NB_INPLACE_RSHIFT', '>>='), ('NB_INPLACE_SUBTRACT', '-='), ('NB_INPLACE_TRUE_DIVIDE', '/='), ('NB_INPLACE_XOR', '^='), ('NB_SUBSCR', '[]')]
_SPECIAL_METHODS = ['__enter__', '__exit__', '__aenter__', '__aexit__']
# ---- end of the tables ---------------------------------------------------------------------------------------------------------


def _arguments(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    """_PyArg_UnpackKeywords for ($module, /, opcode): one argument, by position or by name."""
    if len(args) + len(kwds) > 1:
        raise TypeError(fname + "() takes at most 1 argument (" + str(len(args) + len(kwds)) + " given)")
    if args:
        return args[0]
    if "opcode" in kwds:
        return kwds["opcode"]
    raise TypeError(fname + "() missing required argument 'opcode' (pos 1)")   # before any unexpected keyword


def _int(value: object) -> int:                  # the clinic's int: PyLong_AsInt after __index__
    n = _number_index(value)
    if n > 2**31 - 1 or n < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return n


def _noargs(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("_opcode." + fname + "() takes no keyword arguments")
    if args:
        raise TypeError("_opcode." + fname + "() takes no arguments (" + str(len(args)) + " given)")


def is_valid(*args: object, **kwds: object) -> bool:
    """Return True if opcode is valid, False otherwise."""
    return _int(_arguments("is_valid", args, kwds)) in _IS_VALID


def has_arg(*args: object, **kwds: object) -> bool:
    """Return True if the opcode uses its oparg, False otherwise."""
    return _int(_arguments("has_arg", args, kwds)) in _HAS_ARG


def has_const(*args: object, **kwds: object) -> bool:
    """Return True if the opcode accesses a constant, False otherwise."""
    return _int(_arguments("has_const", args, kwds)) in _HAS_CONST


def has_name(*args: object, **kwds: object) -> bool:
    """Return True if the opcode accesses an attribute by name, False otherwise."""
    return _int(_arguments("has_name", args, kwds)) in _HAS_NAME


def has_jump(*args: object, **kwds: object) -> bool:
    """Return True if the opcode has a jump target, False otherwise."""
    return _int(_arguments("has_jump", args, kwds)) in _HAS_JUMP


def has_free(*args: object, **kwds: object) -> bool:
    """Return True if the opcode accesses a free variable, False otherwise.

Note that 'free' in this context refers to names in the current scope
that are referenced by inner scopes or names in outer scopes that are
referenced from this scope. It does not include references to global
or builtin scopes."""
    return _int(_arguments("has_free", args, kwds)) in _HAS_FREE


def has_local(*args: object, **kwds: object) -> bool:
    """Return True if the opcode accesses a local variable, False otherwise."""
    return _int(_arguments("has_local", args, kwds)) in _HAS_LOCAL


def has_exc(*args: object, **kwds: object) -> bool:
    """Return True if the opcode sets an exception handler, False otherwise."""
    return _int(_arguments("has_exc", args, kwds)) in _HAS_EXC


def get_intrinsic1_descs(*args: object, **kwds: object) -> list[str]:
    """Return a list of names of the unary intrinsics."""
    _noargs("get_intrinsic1_descs", args, kwds)
    return list(_INTRINSIC_1)


def get_intrinsic2_descs(*args: object, **kwds: object) -> list[str]:
    """Return a list of names of the binary intrinsics."""
    _noargs("get_intrinsic2_descs", args, kwds)
    return list(_INTRINSIC_2)


def get_nb_ops(*args: object, **kwds: object) -> list[tuple[str, str]]:
    """Return array of symbols of binary ops.

Indexed by the BINARY_OP oparg value."""
    _noargs("get_nb_ops", args, kwds)
    return list(_NB_OPS)


def get_special_method_names(*args: object, **kwds: object) -> list[str]:
    """Return a list of special method names."""
    _noargs("get_special_method_names", args, kwds)
    return list(_SPECIAL_METHODS)


def get_specialization_stats(*args: object, **kwds: object) -> None:
    """Return the specialization stats"""
    _noargs("get_specialization_stats", args, kwds)
    return None                                  # a build without Py_STATS


def get_executor(*args: object, **kwds: object) -> object:
    """Return the executor object at offset in code if exists, None otherwise."""
    _bella_refuse("_opcode.get_executor (the executors of a code object: a compiled program has none)")


def stack_effect(*args: object, **kwds: object) -> int:
    """Compute the stack effect of the opcode."""
    _bella_refuse("_opcode.stack_effect (the compiler's stack-effect metadata: step 3b)")
