# clause: C-7-33
# spec: section 7
# status: P1
# source: dialect specification section 7, Objects/typevarobject.c, Modules/_typingmodule.c, Python/intrinsics.c (PEP 695)
"""typing's objects written in C: TypeVar, ParamSpec, TypeVarTuple, TypeAliasType, Generic, NoDefault and _idfunc, made by the
constructors and by the type parameter syntax (PEP 695): their fields, the lazy bounds, constraints, defaults and values and the
functions that evaluate them, repr, unions, substitution through typing, pickling's reduce, and what refuses. What needs a compiler
at runtime (a string bound's ForwardRef, the STRING and FORWARDREF formats of a lazy function) is not here."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001, UP046, UP047
import _typing  # type: ignore[import-not-found]
import typing


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def f[T: int, *Ts, **P = [int], U: (str, bytes) = str](x: T) -> T:
    return x


T, Ts, P, U = f.__type_params__
print(type(T).__name__, type(T).__module__, T.evaluate_bound.__name__, T.evaluate_bound.__qualname__, T.evaluate_bound(), T.evaluate_bound(1), T.evaluate_bound(2), failed(lambda: T.evaluate_bound(3)), failed(lambda: T.evaluate_bound(4)), T.evaluate_bound.__module__, T.evaluate_bound.__defaults__, T.__bound__, T.evaluate_constraints, T.__constraints__, T.__default__, T.evaluate_default, T.has_default())  # type: ignore[arg-type,call-arg,misc,no-untyped-call,union-attr]
print(U.evaluate_constraints(1), U.__constraints__, U.__bound__, U.evaluate_default(1), U.__default__, U.has_default(), U.evaluate_constraints.__qualname__, U.evaluate_default.__name__, P.__default__, P.evaluate_default.__name__, P.has_default(), Ts.evaluate_default, Ts.__default__, Ts.has_default(), repr(T), repr(Ts), repr(P), repr(U), T.__module__, T.__infer_variance__, T.__covariant__, T.__contravariant__, failed(lambda: vars(T)), failed(lambda: T.__dict__), T.__name__, Ts.__name__, P.__name__, Ts.__bound__, P.__bound__)  # type: ignore[arg-type,misc,no-untyped-call,union-attr]
print(f.__qualname__, f.__name__, f(3), T | None, None | T, P | None, failed(lambda: Ts | None), list(Ts), failed(lambda: Ts.__typing_subst__(1)), T.__reduce__(), P.__reduce__(), Ts.__reduce__(), failed(lambda: T.__mro_entries__(())), failed(lambda: P.__mro_entries__(())), failed(lambda: Ts.__mro_entries__(())), P.args, P.kwargs, P.args.__origin__ is P, P.args == P.args, P.args == P.kwargs, P.args != P.kwargs, failed(lambda: P.args < P.args), failed(lambda: P.args.__mro_entries__(())), typing.ParamSpecArgs(1), typing.ParamSpecKwargs(2), typing.ParamSpecArgs(P) == P.args)  # type: ignore[arg-type,no-untyped-call,operator,union-attr]
type A[X] = list[X]
type B = int | str
print(A, A.__name__, A.__qualname__, A.__module__, A.__type_params__, A.__parameters__, A.__value__, A.evaluate_value.__qualname__, A.evaluate_value(1), failed(lambda: A.evaluate_value(4)), A[int], failed(lambda: B[int]), B | None, None | B, failed(lambda: B()), repr(B), B.__value__, type(A), list(A), A.__reduce__(), B.__type_params__, B.__parameters__, A.evaluate_value.__defaults__)  # type: ignore[arg-type,no-untyped-call,operator]


class C[T2]:
    pass


class D[*Ts2, **P2]:
    pass


print(C.__type_params__, C.__orig_bases__, [c.__name__ for c in C.__mro__], C.__parameters__, C[int], failed(lambda: C[int, str]), failed(lambda: C[()]), D.__parameters__, D.__orig_bases__, D[int, str, [bytes]], typing.Generic, typing.Generic.__module__, type(typing.Generic).__name__, [c.__name__ for c in typing.Generic.__mro__], type(typing.Generic()).__name__, failed(lambda: typing.Generic[int]), typing.Generic[C.__type_params__[0]], failed(lambda: typing.Generic[int]), C.__type_params__[0].__module__)  # type: ignore[attr-defined,index,misc,no-untyped-call]
E = typing.TypeVar("E", bound=int, default=str)  # type: ignore[misc]
print(E.evaluate_bound, E.evaluate_bound(1), E.evaluate_bound(4), E.evaluate_default, E.evaluate_default(4), type(E.evaluate_bound).__name__, type(E.evaluate_bound).__module__, failed(lambda: type(E.evaluate_bound)()), failed(lambda: E.evaluate_bound()), failed(lambda: E.evaluate_bound(1, 2)), failed(lambda: E.evaluate_bound(format=1)), failed(lambda: E.evaluate_bound("a")), E.__module__, repr(E), typing.TypeVar("F", covariant=True), typing.TypeVar("G", contravariant=True), typing.TypeVar("H", infer_variance=True), typing.TypeVar("H2", infer_variance=True).__infer_variance__, failed(lambda: typing.TypeVar("I", covariant=True, contravariant=True)), failed(lambda: typing.TypeVar("I", covariant=True, infer_variance=True)), failed(lambda: typing.TypeVar("I", int)), failed(lambda: typing.TypeVar("I", int, str, bound=int)), failed(lambda: typing.TypeVar(1)), typing.TypeVar("K", bound=None).__bound__, failed(lambda: typing.TypeVar()), failed(lambda: typing.TypeVar("L", nope=1)), typing.TypeVar(name="M"), typing.TypeVar("N", int, str).__constraints__, typing.TypeVar("N", int, str).evaluate_constraints(4), typing.TypeVar("O", bound=list[int]).evaluate_bound(4), typing.TypeVar("O", bound=None | int).evaluate_bound(4), typing.TypeVar("O", bound=...).evaluate_bound(4), E | None, E.has_default(), typing.TypeVar("Q").has_default(), typing.TypeVar("Q").__default__)  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
print(typing.NoDefault, type(typing.NoDefault).__name__, type(typing.NoDefault).__module__, failed(lambda: type(typing.NoDefault)()), type(typing.NoDefault)() is typing.NoDefault, failed(lambda: type(typing.NoDefault)(1)), typing.NoDefault.__reduce__(), failed(lambda: type("S", (E,), {})), _typing.Union is typing.Union, _typing._idfunc(5), failed(lambda: _typing._idfunc()), failed(lambda: _typing._idfunc(1, 2)), _typing._idfunc.__module__, _typing._idfunc.__name__, sorted(n for n in dir(_typing) if not n.startswith("__")), _typing.TypeVar is typing.TypeVar, _typing.Generic is typing.Generic)  # type: ignore[arg-type,call-arg,no-untyped-call]
print(typing.TypeAliasType("N", int), typing.TypeAliasType("N", int).__value__, typing.TypeAliasType("N", int).__module__, typing.TypeAliasType("N", int).evaluate_value, typing.TypeAliasType("N", int).evaluate_value(4), typing.TypeAliasType("N", int, type_params=(T,)).__type_params__, typing.TypeAliasType("N", int, type_params=(T,))[str], failed(lambda: typing.TypeAliasType("N", int, type_params=[T])), failed(lambda: typing.TypeAliasType("N", int, type_params=(U, T))), typing.TypeAliasType("N", int, type_params=(T, U)).__parameters__, typing.TypeAliasType("N", int, type_params=(Ts,)).__parameters__, typing.TypeAliasType("N", int, qualname="Q.N").__qualname__, typing.TypeAliasType("N", int, qualname="Q.N").__name__, failed(lambda: typing.TypeAliasType("N", int, qualname=1)), failed(lambda: typing.TypeAliasType(1, int)), failed(lambda: typing.TypeAliasType("N")), failed(lambda: typing.TypeAliasType("N", int, 1)), typing.TypeAliasType("N", int).__type_params__, typing.TypeAliasType("N", int) | None)  # type: ignore[arg-type,call-arg,no-untyped-call]
ps = typing.ParamSpec("PS", bound=int, default=[str])  # type: ignore[misc]
tvt = typing.TypeVarTuple("TVT", default=typing.Unpack[tuple[int]])  # type: ignore[misc]
print(ps, ps.__bound__, ps.__default__, ps.has_default(), ps.evaluate_default(4), ps.__module__, failed(lambda: typing.ParamSpec(1)), failed(lambda: typing.ParamSpec("P", 1)), failed(lambda: typing.ParamSpec("P", covariant=True, contravariant=True)), typing.ParamSpec("P", covariant=True), tvt, tvt.__default__, tvt.has_default(), tvt.__module__, failed(lambda: typing.TypeVarTuple(1)), failed(lambda: typing.TypeVarTuple("Ts", covariant=True, infer_variance=True)), typing.TypeVarTuple("Ts", contravariant=True), typing.TypeVarTuple("Ts").__default__, typing.TypeVarTuple("Ts").evaluate_default)  # type: ignore[arg-type,call-arg,misc,no-untyped-call]


class Box[V = int]:
    value: V


class Pair(typing.Generic[E]):
    pass


print(Box.__type_params__, Box.__type_params__[0].__default__, Box.__type_params__[0].evaluate_default.__name__, Box[str], Box[()] if False else Box.__parameters__, Pair.__parameters__, Pair[int], Pair.__orig_bases__, failed(lambda: Pair[int, str]), typing.get_args(Pair[int]), typing.get_origin(Pair[int]) is Pair, E.__typing_prepare_subst__(Pair, (int,)), E.__typing_prepare_subst__(Pair, ()), failed(lambda: typing.TypeVar("R").__typing_prepare_subst__(Pair, ())), failed(lambda: C.__type_params__[0].__typing_prepare_subst__(C, ())), Pair[()] if False else failed(lambda: Pair[()]))  # type: ignore[attr-defined,misc,no-untyped-call,type-var,union-attr]


def outer():  # type: ignore[no-untyped-def]
    def g[Z: str]():  # type: ignore[no-untyped-def]
        pass

    type AA[W] = list[W]

    class CC[Y: bytes]:
        pass

    return g, AA, CC


g, AA, CC = outer()  # type: ignore[no-untyped-call]
print(g.__type_params__[0].evaluate_bound.__qualname__, AA.evaluate_value.__qualname__, AA.__qualname__, AA.__type_params__[0].evaluate_bound, CC.__type_params__[0].evaluate_bound.__qualname__, g.__qualname__, g.__type_params__[0].__bound__, CC.__type_params__[0].__bound__, AA[int], AA.__module__)
