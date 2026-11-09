# clause: C-3-49
# spec: section 3
# status: P1
# source: dialect specification section 3 (exception groups), PEP 654, Objects/exceptions.c (BaseExceptionGroup)
"""BaseExceptionGroup and ExceptionGroup without except* (the arity errors through the descriptor, whose words CPython gives on every
call path; a bound method's name its own type's): construction (the class chosen by what is nested, the argument checks
and their messages), str and repr (a list, a tuple, a custom sequence and a list mutated afterwards), the read-only members,
derive, split and subgroup by a type, a tuple of types and a predicate over nested groups, what the parts keep of the original
(traceback, cause, context, suppress_context, a copy of the notes), a subclass's derive, the classes' shape (ExceptionGroup is
a heap type made by PyErr_NewException), __class_getitem__, copy and weak references, catching a group by its class, and
contextlib.suppress over a group. traceback's format of a group is C-3-50."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import contextlib
import copy
import weakref


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except BaseException as e:  # noqa: BLE001
        return type(e).__name__ + ": " + str(e)


BEG, EG = BaseExceptionGroup, ExceptionGroup


def shape(g):  # type: ignore[no-untyped-def]
    """A group's tree: the class, the message and the leaves, nested as the group is."""
    if g is None:
        return None
    if isinstance(g, BaseExceptionGroup):
        return (type(g).__name__, g.message, [shape(e) for e in g.exceptions])  # type: ignore[no-untyped-call]
    return repr(g)


print("classes:", [c.__name__ for c in EG.__mro__], [c.__name__ for c in BEG.__mro__], EG.__module__, BEG.__module__, EG.__qualname__, sorted(vars(EG)), sorted(vars(BEG)), EG.__doc__, BEG.__doc__, EG.__bases__ == (BEG, Exception))
print("kinds:", [type(vars(BEG)[n]).__name__ for n in ("__new__", "__init__", "__str__", "__repr__", "derive", "split", "subgroup", "__class_getitem__", "message", "exceptions")], BEG.message.__doc__, BEG.exceptions.__doc__, BEG.derive.__qualname__)
print("mutable:", m(lambda: setattr(EG, "extra", 1)), getattr(EG, "extra", None), m(lambda: setattr(BEG, "extra", 1)), m(lambda: delattr(EG, "extra")))  # type: ignore[no-untyped-call]

# construction
print("chosen:", type(BEG("m", [ValueError()])).__name__, type(BEG("m", [KeyboardInterrupt()])).__name__, type(BEG("m", (ValueError(), SystemExit()))).__name__, type(EG("m", [ValueError()])).__name__, type(BEG("m", [EG("i", [ValueError()])])).__name__, type(BEG("m", [BEG("i", [KeyboardInterrupt()])])).__name__)


class MyEG(ExceptionGroup):
    pass


class MyBEG(BaseExceptionGroup):
    pass


class Both(BaseExceptionGroup, ValueError):
    pass


print("subclasses:", type(MyEG("m", [ValueError()])).__name__, type(MyBEG("m", [ValueError()])).__name__, type(MyBEG("m", [KeyboardInterrupt()])).__name__, m(lambda: MyEG("m", [KeyboardInterrupt()])), m(lambda: Both("m", [KeyboardInterrupt()])), [c.__name__ for c in Both.__mro__], type(Both("m", [ValueError()])).__name__)  # type: ignore[list-item,no-untyped-call]
print("errors:", m(lambda: BEG()), m(lambda: BEG("m")), m(lambda: BEG("m", [ValueError()], 3)), m(lambda: BEG(1, [ValueError()])), m(lambda: BEG(None, [ValueError()])), m(lambda: BEG("m", 5)), m(lambda: BEG("m", [])), m(lambda: BEG("m", ())), m(lambda: BEG("m", [1])), m(lambda: BEG("m", [ValueError(), 2])), m(lambda: BEG("m", [ValueError], )), m(lambda: EG("m", [KeyboardInterrupt()])), m(lambda: EG("m", [ValueError()], x=1)), m(lambda: BEG("m", exceptions=[ValueError()])), m(lambda: BEG(message="m", exceptions=[ValueError()])), m(lambda: BEG("m", "ab")), m(lambda: BEG.__new__(int, "m", [ValueError()])), m(lambda: BEG.__new__(ValueError, "m", [ValueError()])))  # type: ignore[arg-type,call-arg,no-untyped-call,type-var]


class Seq:
    def __len__(self):  # type: ignore[no-untyped-def]
        return 2

    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        if i < 2:
            return ValueError(i)
        raise IndexError

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "Seq()"


class Msg(str):
    def __str__(self):  # type: ignore[no-untyped-def]
        return "shown"


e = EG("msg", [ValueError(1), TypeError(2)])
items = [ValueError(1)]
mutated = EG("l", items)
items.append(TypeError())  # type: ignore[arg-type]
print("str:", str(e), str(EG("one", [ValueError()])), str(EG(Msg("m"), [ValueError()])), repr(EG(Msg("m"), [ValueError()])), str(BEG("b", [KeyboardInterrupt(), ValueError()])))
print("repr:", repr(e), repr(EG("t", (ValueError(),))), repr(EG("s", Seq())), repr(mutated), mutated.exceptions, mutated.args[1] is items, repr(MyEG("sub", [ValueError()])))  # type: ignore[arg-type]
e.args = ("changed", (ValueError(),))
print("args rebound:", repr(e), e.message, e.args)
e = EG("msg", [ValueError(1), TypeError(2)])
print("members:", e.message, e.exceptions, type(e.exceptions).__name__, e.args, EG("s", Seq()).exceptions, m(lambda: setattr(e, "message", "x")), m(lambda: delattr(e, "message")), m(lambda: setattr(e, "exceptions", ())), vars(e), e.__dict__)  # type: ignore[arg-type,no-untyped-call]

# derive, split, subgroup
d = e.derive([KeyError(3)])
print("derive:", shape(d), type(e.derive([KeyboardInterrupt()])).__name__, d.__traceback__, d.__cause__, d.__context__, m(lambda: BEG.derive(e)), m(lambda: e.derive([])), m(lambda: BEG.derive(e, 1, 2)), m(lambda: BEG.derive(e, excs=[])))  # type: ignore[call-overload,no-untyped-call]
tree = EG("outer", [ValueError(1), EG("inner", [TypeError(2), ValueError(3), EG("deep", [KeyError(4)])]), OSError(5)])
for matcher in (ValueError, TypeError, (KeyError, OSError), Exception, ExceptionGroup, KeyboardInterrupt, lambda x: isinstance(x, ValueError) and x.args[0] > 1, lambda x: isinstance(x, BaseExceptionGroup) and x.message == "deep", lambda x: False):
    match, rest = tree.split(matcher)  # type: ignore[arg-type,type-var]
    print("split:", shape(match), shape(rest), match is tree, rest is tree, shape(tree.subgroup(matcher)))  # type: ignore[no-untyped-call]
print("split errors:", m(lambda: BEG.split(tree)), m(lambda: BEG.split(tree, 1, 2)), m(lambda: BEG.split(tree, x=1)), m(lambda: tree.split(1)), m(lambda: tree.split((ValueError, 1))), m(lambda: tree.split([ValueError])), m(lambda: tree.split(ValueError())), m(lambda: tree.subgroup(int)), m(lambda: BEG.split(ValueError(), ValueError)), m(lambda: tree.split(lambda x: 1 / 0)))  # type: ignore[arg-type,call-overload,no-untyped-call,return-value,type-var]

# what the parts keep
try:
    try:
        raise KeyError("ctx")
    except KeyError:
        raise EG("raised", [ValueError(1), TypeError(2)]) from OSError("why")
except EG as caught:
    caught.add_note("note one")
    match, rest = caught.split(ValueError)
    print("kept:", match.__traceback__ is caught.__traceback__, rest.__traceback__ is caught.__traceback__, repr(match.__cause__), repr(rest.__context__), match.__suppress_context__, match.__notes__, rest.__notes__, match.__notes__ is caught.__notes__, match.__notes__ is rest.__notes__)  # type: ignore[union-attr]
    match.__notes__.append("only in match")  # type: ignore[union-attr]
    print("notes copied:", caught.__notes__, rest.__notes__, match.__notes__)  # type: ignore[union-attr]
plain = EG("plain", [ValueError(), TypeError()])
pm, pr = plain.split(ValueError)
print("plain parts:", pm.__traceback__, pm.__cause__, pm.__context__, pm.__suppress_context__, plain.__suppress_context__, hasattr(pm, "__notes__"))  # type: ignore[union-attr]
plain.__notes__ = "not a list"  # type: ignore[assignment]
print("odd notes:", plain.split(ValueError)[0].__notes__ if hasattr(plain.split(ValueError)[0], "__notes__") else "absent", m(lambda: plain.split(ValueError)[0].__notes__))  # type: ignore[no-untyped-call,union-attr]
plain.__notes__ = ("a", "b")  # type: ignore[assignment]
print("tuple notes:", plain.split(ValueError)[0].__notes__)  # type: ignore[union-attr]


class Derived(ExceptionGroup):
    def __new__(cls, message, excs, extra="x"):  # type: ignore[no-untyped-def]
        self = super().__new__(cls, message, excs)
        self.extra = extra  # type: ignore[attr-defined]
        return self

    def __init__(self, message, excs, extra="x"):  # type: ignore[no-untyped-def]
        super().__init__(message, excs)

    def derive(self, excs):  # type: ignore[no-untyped-def]
        return Derived(self.message + "!", excs, self.extra)  # type: ignore[attr-defined,no-untyped-call]


class Bad(ExceptionGroup):
    def derive(self, excs):  # type: ignore[no-untyped-def]
        return ValueError("not a group")


dg = Derived("d", [ValueError(1), TypeError(2)], extra="kept")  # type: ignore[no-untyped-call]
dm, dr = dg.split(ValueError)
print("derived:", shape(dm), shape(dr), dm.extra, dr.extra, type(dg.subgroup(TypeError)).__name__, dg.subgroup(lambda x: True) is dg, m(lambda: Bad("b", [ValueError(), TypeError()]).split(ValueError)), shape(Bad("b", [ValueError()]).split(ExceptionGroup)[0]))  # type: ignore[no-untyped-call,union-attr]

# generic, copy, weakref, catching
print("generic:", BEG[ValueError], EG[ValueError | TypeError], type(EG[int]).__name__, EG[int].__origin__ is EG, m(lambda: BEG.__class_getitem__()), BEG.__class_getitem__(int))  # type: ignore[call-arg,no-untyped-call]
c = copy.copy(e)
dc = copy.deepcopy(EG("deep", [ValueError([1])]))
print("copy:", type(c).__name__, shape(c), c.exceptions is e.exceptions, shape(dc), dc.exceptions[0].args[0], type(copy.copy(BEG("b", [KeyboardInterrupt()]))).__name__, e.__reduce__()[0] is EG, e.__reduce__()[1])  # type: ignore[no-untyped-call]
ref = weakref.ref(e)
print("weakref:", ref() is e, m(lambda: weakref.ref(BEG("b", [KeyboardInterrupt()]))))  # type: ignore[no-untyped-call]
for raised in (EG("e", [ValueError()]), BEG("b", [KeyboardInterrupt()])):
    try:
        raise raised
    except ExceptionGroup as caught_eg:
        print("caught as ExceptionGroup:", type(caught_eg).__name__)
    except BaseExceptionGroup as caught_beg:
        print("caught as BaseExceptionGroup:", type(caught_beg).__name__)
try:
    raise EG("ve", [ValueError()])
except Exception as caught_exc:
    print("caught as Exception:", isinstance(caught_exc, ExceptionGroup), isinstance(caught_exc, BaseExceptionGroup))

# contextlib.suppress splits a group (3.12)
with contextlib.suppress(ValueError):
    raise EG("all suppressed", [ValueError(1), ValueError(2)])
print("suppressed all")
try:
    with contextlib.suppress(ValueError):
        raise EG("partly", [ValueError(1), TypeError(2)])
except EG as left:
    print("suppress left:", shape(left), left.__context__)  # type: ignore[no-untyped-call]
try:
    with contextlib.suppress(KeyError):
        raise ValueError("plain")
except ValueError as v:
    print("suppress plain:", repr(v))
