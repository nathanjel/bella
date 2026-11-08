# clause: C-7-47
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_opcode.c, Lib/opcode.py, Lib/dis.py
"""The _opcode module behind opcode and dis: the eight predicates over every opcode number (and the lists opcode builds from them),
the descriptive tables (the intrinsics, the binary operators, the special method names), what a non-stats build answers for the
specialization stats, the clinic's parsing (one argument by position or by name, __index__, the C int's range) and the names dis
exports from them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _opcode  # type: ignore[import-not-found]
import dis
import opcode


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


class Index:
    def __init__(self, n):  # type: ignore[no-untyped-def]
        self.n = n

    def __index__(self):  # type: ignore[no-untyped-def]
        return self.n


PREDICATES = ("is_valid", "has_arg", "has_const", "has_name", "has_jump", "has_free", "has_local", "has_exc")
print("module:", [(n, type(getattr(_opcode, n)).__name__) for n in sorted(dir(_opcode)) if not n.startswith("__")], repr(_opcode.__doc__), _opcode.ENABLE_SPECIALIZATION)
print("docs:", [repr(getattr(_opcode, n).__doc__) for n in (*PREDICATES, "get_intrinsic1_descs", "get_intrinsic2_descs", "get_nb_ops", "get_special_method_names", "get_specialization_stats", "get_executor", "stack_effect")])
for name in PREDICATES:
    f = getattr(_opcode, name)
    ops = [op for op in range(-4, 600) if f(op)]
    print(name, len(ops), ops[:12], ops[-6:], f(Index(ops[0])) if ops else None, f(True), f(opcode=ops[-1]) if ops else None)  # type: ignore[no-untyped-call]
print("tables:", _opcode.get_intrinsic1_descs(), _opcode.get_intrinsic2_descs(), _opcode.get_nb_ops(), _opcode.get_special_method_names(), _opcode.get_specialization_stats())
print("fresh lists:", _opcode.get_nb_ops() is _opcode.get_nb_ops(), _opcode.get_nb_ops() == _opcode.get_nb_ops(), type(_opcode.get_nb_ops()[0]).__name__)
print("arguments:", m(lambda: _opcode.has_arg()), m(lambda: _opcode.has_arg(1, 2)), m(lambda: _opcode.has_arg(1, opcode=2)), m(lambda: _opcode.has_arg(op=1)), m(lambda: _opcode.has_arg("x")), m(lambda: _opcode.has_arg(1.0)), m(lambda: _opcode.has_arg(2**31)), m(lambda: _opcode.has_arg(-(2**31))), m(lambda: _opcode.has_arg(-(2**31) - 1)), m(lambda: _opcode.is_valid(None)), m(lambda: _opcode.get_nb_ops(1)), m(lambda: _opcode.get_nb_ops(x=1)), m(lambda: _opcode.get_specialization_stats(None)), m(lambda: _opcode.get_intrinsic1_descs(1, 2)))  # type: ignore[no-untyped-call]

# what opcode builds from the predicates, and dis exports
print("opcode:", opcode.hasarg == [op for op in opcode.opmap.values() if _opcode.has_arg(op)], len(opcode.hasarg), opcode.hasconst, opcode.hasname[:6], opcode.hasjump[:6], opcode.hasjrel is opcode.hasjump, opcode.hasjabs, opcode.hasfree, opcode.haslocal, opcode.hasexc, opcode.hascompare)
print("opcode tables:", opcode._intrinsic_1_descs == _opcode.get_intrinsic1_descs(), opcode._intrinsic_2_descs[:3], opcode._nb_ops[:4], opcode._special_method_names, opcode.stack_effect is _opcode.stack_effect, opcode.HAVE_ARGUMENT, opcode.MIN_INSTRUMENTED_OPCODE, opcode.EXTENDED_ARG)  # type: ignore[attr-defined]
print("opnames:", [opcode.opname[op] for op in (opcode.HAVE_ARGUMENT, opcode.hasconst[0], opcode.hasfree[0], opcode.hasexc[0])], opcode.opmap["LOAD_CONST"], opcode.opmap["BINARY_OP"], opcode.opmap["CALL"], len(opcode.opname), opcode.opname[0], opcode.opname[255])
print("dis:", dis.hasarg is opcode.hasarg, dis.hasjump == opcode.hasjump, dis.COMPILER_FLAG_NAMES[1], dis.opmap["RETURN_VALUE"], dis.opname[dis.opmap["RETURN_VALUE"]], sorted(dis.__all__)[:6], len(dis.__all__), dis.get_executor is _opcode.get_executor)  # type: ignore[attr-defined]
