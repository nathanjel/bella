# clause: C-3-45
# spec: section 3
# status: P1
# source: Objects/unicodeobject.c (unicode_subtype_new, PyObject_Str, PyUnicode_Format), Objects/dictobject.c, Python/getargs.c
"""Subclasses of str: what they make, what the built-in operations read past a subclass's methods and what they ask it first; what
str's own methods return (an exact str); as a key, a name, a format and a value to print."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B009, B018, B023, E501, F501, F509, E731, F507, PLR0133, SLF001, UP018, UP031, UP032
import copyreg
import sys


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def of(value):  # type: ignore[no-untyped-def]
    return (type(value).__name__, value)


class S(str):
    pass


class WithInit(str):
    def __init__(self, text):  # type: ignore[no-untyped-def]
        self.extra = len(text)


class WithNew(str):
    def __new__(cls, text, extra=0):  # type: ignore[no-untyped-def]
        self = super().__new__(cls, text.upper())
        self.extra = extra  # type: ignore[attr-defined]
        return self


class Shown(str):
    def __str__(self):  # type: ignore[no-untyped-def]
        return "str:" + str.__str__(self)

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "repr:" + str.__repr__(self)

    def __format__(self, spec):  # type: ignore[no-untyped-def]
        return "format:" + spec


class Ops(str):
    def __add__(self, other):  # type: ignore[no-untyped-def]
        return "add"

    def __radd__(self, other):  # type: ignore[no-untyped-def]
        return "radd"

    def __mul__(self, other):  # type: ignore[no-untyped-def]
        return "mul"

    def __rmul__(self, other):  # type: ignore[no-untyped-def]
        return "rmul"

    def __mod__(self, other):  # type: ignore[no-untyped-def]
        return "mod"

    def __rmod__(self, other):  # type: ignore[no-untyped-def]
        return "rmod"

    def __eq__(self, other):  # type: ignore[no-untyped-def]
        return "eq"

    def __ne__(self, other):  # type: ignore[no-untyped-def]
        return "ne"

    def __lt__(self, other):  # type: ignore[no-untyped-def]
        return "lt"

    def __gt__(self, other):  # type: ignore[no-untyped-def]
        return "gt"

    def __le__(self, other):  # type: ignore[no-untyped-def]
        return "le"

    def __ge__(self, other):  # type: ignore[no-untyped-def]
        return "ge"

    def __hash__(self):  # type: ignore[no-untyped-def]
        return 7

    def __contains__(self, item):  # type: ignore[no-untyped-def]
        return True

    def __len__(self):  # type: ignore[no-untyped-def]
        return 99

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        return "item"

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(("i", "t"))

    def __bool__(self):  # type: ignore[no-untyped-def]
        return False

    def __int__(self):  # type: ignore[no-untyped-def]
        return 11

    def __float__(self):  # type: ignore[no-untyped-def]
        return 1.5


class Insensitive(str):
    def __eq__(self, other):  # type: ignore[no-untyped-def]
        return str.lower(self) == str.lower(other)

    def __hash__(self):  # type: ignore[no-untyped-def]
        return hash(str.lower(self))


class Unhashable(str):
    __hash__ = None  # type: ignore[assignment]


class BadStr(str):
    def __str__(self):  # type: ignore[no-untyped-def]
        return 1


class BadRepr(str):
    def __repr__(self):  # type: ignore[no-untyped-def]
        return 1


class StrGivesSub(str):
    def __str__(self):  # type: ignore[no-untyped-def]
        return S("sub")


class Slotted(str):
    __slots__ = ()


class WithSlots(str):
    __slots__ = ("a", "b")


class Sub2(S):
    pass


class Named:
    pass


# ---- making one
value = S("text")
print(type(value).__name__, value, repr(value), len(value), value == "text", "text" == value, value != "text", hash(value) == hash("text"), bool(value), bool(S()), isinstance(value, str), issubclass(S, str), S.__mro__[1] is str, S.__base__ is str, S.__name__, S.__qualname__, S.__module__)
print(of(S()), of(S("")), of(S(1)), of(S(1.5)), of(S(None)), of(S(b"a", "ascii")), of(S(b"a", encoding="ascii")), of(S(b"a", errors="ignore")), of(S(object=2)), of(S(S("x"))), of(Sub2("y")), of(S(Shown("z"))), of(str(Shown("z"))), of(str(S("x"))), of(str.__new__(S, "n")), of(str.__new__(S)), of(str.__new__(S, b"a", "ascii")))  # type: ignore[no-untyped-call]
print(failed(lambda: S(1, 2)), failed(lambda: S(1, 2, 3, 4)), failed(lambda: S(b"a", 1)), failed(lambda: S("a", "ascii")), failed(lambda: str.__new__(int)), failed(lambda: str.__new__(1)), failed(lambda: str.__new__()), failed(lambda: object.__new__(S)), failed(lambda: int.__new__(S)), failed(lambda: S(nothing=1)))  # type: ignore[call-overload,no-untyped-call,type-var]
print(failed(lambda: WithInit("a", extra=1)), failed(lambda: WithInit("a", 5)), of(WithInit("a")), WithInit("ab").extra, of(WithNew("a", 3)), WithNew("b").extra, failed(lambda: WithInit()), failed(lambda: S.__init__(S("a"), 1)))  # type: ignore[attr-defined,call-arg,no-untyped-call]
value.attr = 1  # type: ignore[attr-defined]
print(value.attr, vars(value), value.__dict__, "attr" in dir(value), hasattr(value, "attr"), failed(lambda: value.nothing))  # type: ignore[attr-defined,no-untyped-call]
del value.attr  # type: ignore[attr-defined]
print(hasattr(value, "attr"), vars(value), hasattr("a", "__dict__"), failed(lambda: setattr("a", "x", 1)), failed(lambda: vars("a")))  # type: ignore[no-untyped-call]
print(failed(lambda: type("X", (str, int), {})), failed(lambda: type("X", (str, bytes), {})), failed(lambda: type("X", (str, list), {})), failed(lambda: type("X", (str, tuple), {})), failed(lambda: type("X", (S, dict), {})), type("X", (S, Named), {}).__mro__[1] is S, type("X", (Named, S), {}).__mro__[1] is Named)  # type: ignore[no-untyped-call]
print(failed(lambda: Slotted("a").__dict__), failed(lambda: setattr(Slotted("a"), "x", 1)), of(Slotted("a")), of(WithSlots("a")), failed(lambda: WithSlots("a").a))  # type: ignore[attr-defined,no-untyped-call]
slots = WithSlots("a")
slots.a = 1  # type: ignore[attr-defined]
print(slots.a, failed(lambda: slots.b), failed(lambda: setattr(slots, "c", 1)), sorted(k for k in vars(WithSlots) if k in ("a", "b", "__dict__", "__weakref__", "__slots__")), sorted(k for k in vars(S) if k in ("__dict__", "__weakref__")))  # type: ignore[attr-defined,no-untyped-call]

# ---- what str's methods return
for name, args in (("upper", ()), ("lower", ()), ("strip", ()), ("lstrip", ()), ("rstrip", ()), ("capitalize", ()), ("title", ()), ("swapcase", ()), ("casefold", ()), ("replace", ("zz", "y")), ("center", (2,)), ("ljust", (2,)), ("rjust", (2,)), ("zfill", (2,)), ("expandtabs", ()), ("removeprefix", ("zz",)), ("removesuffix", ("zz",)), ("format", ()), ("__str__", ()), ("__format__", ("",))):
    print(name, of(getattr(S("text"), name)(*args)))  # type: ignore[no-untyped-call]
print(of(S("a b").split()), of(S("a b").rsplit()), of(S("a\nb").splitlines()), of(S("ab").partition("x")), of(S("ab").rpartition("x")), of(S("ab").partition("a")), [type(p).__name__ for p in S("a b").split()], [type(p).__name__ for p in S("ab").partition("x")], of(S("ab").encode()), of(S("ab").translate({})), S("ab").find("b"), S("ab").index("b"), S("ab").count("a"), S("ab").startswith("a"), S("ab").endswith(S("b")), S("ab").isalpha(), S("ab").isdigit(), S("ab").isidentifier())  # type: ignore[no-untyped-call]
print(of(S("ab") + "c"), of("c" + S("ab")), of(S("ab") + S("c")), of(S("ab") * 2), of(2 * S("ab")), of(S("ab") * 1), of(S("") * 2), of(S("ab")[0]), of(S("ab")[0:1]), of(S("ab")[:]), of(S("ab") % ()), of("%s" % S("ab")), of(S("%s") % "x"), of(S("ab").join(["x", "y"])), of("-".join([S("x"), "y"])), of("-".join([S("x")])), of("".join([S("x"), S("y")])), of(str.join(S("-"), ["a", "b"])), [type(c).__name__ for c in S("ab")], [c for c in reversed(S("ab"))], list(S("ab")), tuple(S("ab")), sorted(S("ba")), set(S("a")), of(max(S("ab"))))  # type: ignore[no-untyped-call]
print(of(str(S("x"))), of(S("x").__str__()), of(str.__str__(S("x"))), of(S("x").__repr__()), of(repr(S("x"))), of(format(S("x"))), of(format(S("x"), "3")), of(f"{S('x')}"), of(f"{S('x'):>3}"), of(f"{S('x')!r}"), of(f"{S('x')!s}"), of(ascii(S("é"))), of("%s %r" % (S("x"), S("y"))), of("{} {!r}".format(S("x"), S("y"))), of(S("{}").format(1)), of(S("x").__format__("")), of(S("x").__format__("3")), of(S("x").__add__("y")), of(S("x").__mul__(2)), of(S("x").__rmul__(2)), of(S("x").__mod__(())), of(S("x").__getitem__(0)), S("x").__len__(), S("x").__contains__("x"), S("x").__eq__("x"), S("x").__ne__("x"), S("x").__lt__("y"), S("x").__hash__() == hash("x"))  # type: ignore[no-untyped-call]
print(of(int(S("5"))), of(float(S("1.5"))), of(complex(S("1j"))), of(bytes(S("a"), "ascii")), of(bytearray(S("a"), "ascii")), of(str(b"a", S("ascii"))), of(int(S("10"), 2)), of(int("10", base=2)), of(bytes.fromhex(S("61"))), of(getattr(str, S("upper"))("a")), hasattr("a", S("upper")), of(ord(S("a"))), of(sys.intern("a")), failed(lambda: sys.intern(S("a"))), failed(lambda: ord(S("ab"))), of(chr(97)), of(S("a").isascii()), of(sorted([S("b"), "a", S("c")])), of(min(S("b"), "a")), of(sum([1], 0)))  # type: ignore[no-untyped-call]

# ---- what a subclass overrides
ops = Ops("ab")
print(ops + "x", "x" + ops, ops * 2, 2 * ops, ops % 1, "%s" % ops, ops == "ab", "ab" == ops, ops != "ab", "ab" != ops, ops < "b", "b" < ops, ops > "b", "b" > ops, ops <= "b", "b" <= ops, ops >= "b", "b" >= ops, hash(ops), "q" in ops, len(ops), ops[0], list(ops), bool(ops), int(ops), float(ops))
print(str.__add__(ops, "x"), str.__mul__(ops, 2), str.__eq__(ops, "ab"), str.__hash__(ops) == hash("ab"), str.__contains__(ops, "q"), str.__len__(ops), str.__getitem__(ops, 0), list(str.__iter__(ops)), str.__str__(ops), str.__repr__(ops), str.__lt__(ops, "b"), ops.upper(), ops.find("b"), ops.split(), ops.join(["1", "2"]), "-".join([ops, "x"]), "-".join(ops), str(ops), repr(ops), ops.__class__.__name__, ops.startswith("a"), "ab".startswith(ops), "a".join(ops), sorted(ops), tuple(ops), set(ops) == {"i", "t"}, dict.fromkeys(ops) == {"i": None, "t": None}, ascii(ops), f"{ops}", format(ops, ""))
print("ab".__eq__(ops), "ab".__ne__(ops), "ab" in {ops: 1}, ops in {"ab": 1}, {ops: 1}.get("ab"), {ops: 1}.get(ops), {"ab": 1}.get(ops), {ops: 1}[ops], failed(lambda: {ops: 1}["ab"]), {ops}, ops in {ops}, "ab" in {ops}, len({ops, "ab"}), len({ops, Ops("cd")}), ops in [1, "ab"], "ab" in [ops], (ops,) == ("ab",), ("ab",) == (ops,), [ops] == ["ab"], ops in ("ab",), {ops: 1} == {"ab": 1})  # type: ignore[call-overload,index,no-untyped-call]
shown = Shown("x")
print(shown, str(shown), repr(shown), f"{shown}", f"{shown!s}", f"{shown!r}", f"{shown:5}", format(shown), format(shown, "s"), "%s" % shown, "%r" % shown, "{}".format(shown), "{:3}".format(shown), "{!r}".format(shown), "".join([shown]), shown + "", ascii(shown), str(shown).__class__.__name__, [shown], (shown,), {shown: shown}, {shown}, list([shown]), shown.upper(), shown.__str__(), shown.__repr__(), shown.__format__("q"))  # type: ignore[no-untyped-call]
print(sys.stdout.write(shown), sys.stdout.write("\n"))
print(shown, shown, sep=shown, end=shown + "\n")
print(of(str(StrGivesSub("x"))), of(StrGivesSub("x").__str__()), of(f"{StrGivesSub('x')}"), of("%s" % StrGivesSub("x")), of("%s" % (StrGivesSub("x"),)), of("%5s" % (StrGivesSub("x"),)), of("%s%%" % (StrGivesSub("x"),)), ("%s" % ("a",)) == "a", "%-3s|%3s|%.1s|%r|%a" % ("a", "b", "cd", "e", "é"), "%d" % (1,), "%s %d" % ("a", 1), failed(lambda: "%s %s" % ("a",)), failed(lambda: "%s" % ("a", "b")), failed(lambda: "%y" % ("a",)), failed(lambda: "%" % ("a",)), "abc" % (), "%%" % (), "%%%s" % ("a",), "%s" % (*"a",), failed(lambda: str(BadStr("x"))), failed(lambda: print(BadStr("x"))), failed(lambda: "%s" % BadStr("x")), failed(lambda: f"{BadStr('x')}"), failed(lambda: repr(BadRepr("x"))), failed(lambda: "%r" % BadRepr("x")), failed(lambda: [BadRepr("x")].__repr__()), of(str(BadRepr("x"))))  # type: ignore[no-untyped-call,str-format]
print(failed(lambda: hash(Unhashable("a"))), failed(lambda: {Unhashable("a"): 1}), failed(lambda: {Unhashable("a")}), Unhashable("a") == "a", "a" == Unhashable("a"), Unhashable.__hash__, failed(lambda: {"a": 1}.get(Unhashable("a"))), failed(lambda: Unhashable("a") in {"a"}))  # type: ignore[no-untyped-call]
print(Insensitive("A") == "a", "a" == Insensitive("A"), "A" == Insensitive("a"), hash(Insensitive("A")) == hash("a"), {Insensitive("A"): 1}.get("a"), {"a": 1}.get(Insensitive("A")), Insensitive("A") in {"a"}, "a" in {Insensitive("A")}, "A" in {Insensitive("a")}, {Insensitive("A"): 1, "a": 2}, {"a": 1, Insensitive("A"): 2}, len({Insensitive("A"), "a"}), [Insensitive("A")].index("a"), ["a"].index(Insensitive("A")), ["a"].count(Insensitive("A")), Insensitive("A") in ["a"], "a" in [Insensitive("A")])  # type: ignore[arg-type,call-overload]

# ---- as a key, and as a name
key = S("key")
table = {key: 1}
print(table, table["key"], table[key], "key" in table, key in table, {"key": 1}[key], {"key": 1} == {key: 1}, list(table)[0] is key, type(list(table)[0]).__name__, list({"key": 1, key: 2}.items()), type(list({"key": 1, key: 2})[0]).__name__, type(list({key: 1, "key": 2})[0]).__name__, {key} == {"key"}, type(next(iter({key}))).__name__, frozenset({key}) == frozenset({"key"}), key in {"key"}, "key" in {key})  # type: ignore[index]
holder = Named()
holder.field = 1  # type: ignore[attr-defined]
print(holder.field, getattr(holder, S("field")), hasattr(holder, S("field")), vars(holder), failed(lambda: getattr(holder, S("nothing"))), getattr(holder, S("nothing"), "d"), vars(holder)[S("field")])  # type: ignore[attr-defined,no-untyped-call]
delattr(holder, S("field"))
print(vars(holder))
vars(holder)[S("late")] = 2
print(holder.late, getattr(holder, "late"), getattr(holder, S("late")), type(next(iter(vars(holder)))).__name__, vars(holder))  # type: ignore[attr-defined]


def keywords(**kwds):  # type: ignore[no-untyped-def]
    return [(type(k).__name__, k) for k in kwds]


print(keywords(**{"a": 1}), failed(lambda: keywords(**{1: 1})))  # type: ignore[arg-type,no-untyped-call]
print(print.__name__, [i for i in map(S, "ab")], [type(i).__name__ for i in map(S, "ab")], tuple(sorted(map(S, "ba"))), "".join(map(S, "ab")), failed(lambda: "".join([1])), failed(lambda: S("a").join([1])), failed(lambda: S("a") + 1), failed(lambda: 1 + S("a")), failed(lambda: S("a") * "b"), failed(lambda: S("a") < 1), failed(lambda: S("a")[5]), failed(lambda: S("a")["b"]), failed(lambda: S("a").__setitem__), failed(lambda: S("a").upper(1)), failed(lambda: str.upper(1)), failed(lambda: str.upper()))  # type: ignore[arg-type,call-arg,index,list-item,no-untyped-call,operator]
print(copyreg.__name__, of(S("a").__reduce_ex__(2)[1]), of(S("a").__getnewargs__()), S("a").__reduce_ex__(2)[2:], S("a").__getstate__())  # type: ignore[no-untyped-call]
extra = S("a")
extra.x = 1  # type: ignore[attr-defined]
print(extra.__reduce_ex__(2)[2], extra.__getstate__())
