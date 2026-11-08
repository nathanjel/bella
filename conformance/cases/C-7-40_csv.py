# clause: C-7-40
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_csv.c, Lib/csv.py
"""The _csv module behind csv: the Dialect type (its conversions and checks in the C's order, the reuse of an instance, the
attributes an object or a registered name supplies), the reader's state machine over quoting, escaping, doublequote, strict,
skipinitialspace, line endings inside and across lines, the five quoting modes' conversions, the field size limit and line_num, the
writer's quoting and escaping, the empty-field and single-empty-record rules, the registry and field_size_limit with their messages,
and the csv package's reader, DictReader, writer, Sniffer and dialect classes over them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _csv
import csv
import io


def m(f):  # type: ignore[no-untyped-def]
    try:
        v = f()
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
    return "<a " + type(v).__name__ + ">" if isinstance(v, _csv.Dialect) else repr(v)


def rd(lines, *d, **kw):  # type: ignore[no-untyped-def]
    return m(lambda: list(_csv.reader(lines, *d, **kw)))  # type: ignore[no-untyped-call]


def wr(rows, *d, **kw):  # type: ignore[no-untyped-def]
    def go():  # type: ignore[no-untyped-def]
        s = io.StringIO()
        w = _csv.writer(s, *d, **kw)
        for r in rows:
            w.writerow(r)
        return s.getvalue()
    return m(go)  # type: ignore[no-untyped-call]


print("constants:", _csv.QUOTE_MINIMAL, _csv.QUOTE_ALL, _csv.QUOTE_NONNUMERIC, _csv.QUOTE_NONE, _csv.QUOTE_STRINGS, _csv.QUOTE_NOTNULL, repr(_csv.__doc__))
print("error:", _csv.Error.__mro__[1:], _csv.Error.__module__, _csv.Error.__name__, _csv.Error.__doc__)
print("types:", _csv.Dialect.__name__, _csv.Dialect.__module__, _csv.Dialect.__qualname__, _csv.Reader.__name__, _csv.Reader.__module__, _csv.Writer.__name__, _csv.Writer.__module__, _csv.reader.__name__, _csv.writer.__name__, _csv.reader.__qualname__, _csv.register_dialect.__name__)
print("type docs:", repr(_csv.Dialect.__doc__), repr(_csv.Reader.__doc__), repr(_csv.Writer.__doc__))
print("function docs:", repr(_csv.reader.__doc__), repr(_csv.writer.__doc__), repr(_csv.register_dialect.__doc__), repr(_csv.list_dialects.__doc__), repr(_csv.get_dialect.__doc__), repr(_csv.unregister_dialect.__doc__), repr(_csv.field_size_limit.__doc__))
print("descriptors:", type(_csv.Dialect.doublequote).__name__, type(_csv.Dialect.delimiter).__name__, type(_csv.Reader.line_num).__name__, type(_csv.Writer.writerow).__name__, type(_csv.reader).__name__, type(_csv.field_size_limit).__name__)
class SubStr(str):
    pass


class Num:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 3

    def __str__(self):  # type: ignore[no-untyped-def]
        return "num"


class Attr:
    delimiter = ";"
    quotechar = None


class Bad:
    delimiter = 7


d = _csv.Dialect()
print("defaults:", repr(d.delimiter), d.doublequote, d.escapechar, repr(d.lineterminator), repr(d.quotechar), d.quoting, d.skipinitialspace, d.strict)
print("dialect errors")
for f in [lambda: _csv.Dialect(delimiter="ab"), lambda: _csv.Dialect(delimiter=1), lambda: _csv.Dialect(delimiter=None), lambda: _csv.Dialect(quoting="x"), lambda: _csv.Dialect(quoting=9), lambda: _csv.Dialect(quoting=True), lambda: _csv.Dialect(quotechar=None).quoting, lambda: _csv.Dialect(quotechar=None, quoting=1), lambda: _csv.Dialect(lineterminator=5), lambda: _csv.Dialect(delimiter="\n"), lambda: _csv.Dialect(delimiter=",", escapechar=","), lambda: _csv.Dialect(delimiter=" ", skipinitialspace=True).delimiter, lambda: _csv.Dialect(escapechar=" ", skipinitialspace=True), lambda: _csv.Dialect(quotechar="\r"), lambda: _csv.Dialect(delimiter="x", lineterminator="x"), lambda: _csv.Dialect("nope"), lambda: _csv.Dialect(5), lambda: _csv.Dialect(d) is d, lambda: _csv.Dialect(d, strict=True) is d, lambda: _csv.Dialect(dialect=d) is d, lambda: _csv.Dialect(excel=1), lambda: _csv.Dialect(d, 1), lambda: setattr(d, "delimiter", ";"), lambda: setattr(d, "strict", 1), lambda: delattr(d, "strict"), lambda: delattr(d, "quoting"), lambda: setattr(d, "x", 1), lambda: d.__reduce__(), lambda: d.__reduce_ex__(2), lambda: _csv.Dialect(quoting=2**40), lambda: _csv.Dialect(quoting=-2**40), lambda: _csv.Dialect(doublequote=[]).doublequote, lambda: _csv.Dialect(escapechar="ab"), lambda: _csv.Dialect(escapechar=3), lambda: _csv.Dialect(quotechar=""), lambda: _csv.Dialect(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), lambda: _csv.Dialect(delimiter="\t", quotechar=None).quoting, lambda: _csv.Dialect(delimiter="\t", quotechar=None, escapechar="\\").escapechar, lambda: _csv.Dialect(quotechar=None, quoting=3).quotechar, lambda: _csv.Dialect(d, quoting=2).quoting, lambda: _csv.Dialect(dialect="excel"), lambda: _csv.Dialect(strict="yes").strict, lambda: _csv.Dialect(quoting=2, quotechar='"', skipinitialspace=1, escapechar=" "), lambda: _csv.Dialect(lineterminator="").lineterminator, lambda: _csv.Dialect(lineterminator="\n;", delimiter=";"), lambda: _csv.Dialect(escapechar='"'), lambda: _csv.Dialect(quotechar=","), lambda: _csv.Dialect(delimiter=SubStr(";")).delimiter, lambda: type(_csv.Dialect(delimiter=SubStr(";")).delimiter).__name__, lambda: type(_csv.Dialect(lineterminator=SubStr(";")).lineterminator).__name__, lambda: _csv.Dialect(quoting=Num()), lambda: _csv.Dialect.delimiter.__get__(5), lambda: _csv.Dialect.__reduce__(5), lambda: _csv.Dialect.doublequote.__get__(5), lambda: _csv.Dialect.__new__(_csv.Dialect).quoting]:  # type: ignore[arg-type,attr-defined,call-arg]
    print(" ", m(f))  # type: ignore[no-untyped-call]


print("from an object:", m(lambda: _csv.Dialect(Attr).quoting), m(lambda: _csv.Dialect(Attr).delimiter), m(lambda: _csv.Dialect(Attr, quoting=0)), m(lambda: _csv.Dialect(Bad)), m(lambda: _csv.Dialect(Attr, delimiter="|").delimiter), m(lambda: _csv.Dialect(Attr(), lineterminator="\n").lineterminator))  # type: ignore[arg-type,no-untyped-call]


class Sub(_csv.Dialect):
    pass


s2 = Sub(delimiter=";")
print("subclass:", type(Sub(d)).__name__, type(s2).__name__, Sub(d) is d, Sub(s2) is s2, _csv.Dialect(s2) is s2, s2.delimiter, isinstance(s2, _csv.Dialect))

print("registry:", m(lambda: _csv.list_dialects()), m(lambda: _csv.get_dialect("x")), m(lambda: _csv.unregister_dialect("x")), m(lambda: _csv.register_dialect(1)), m(lambda: _csv.register_dialect()), m(lambda: _csv.register_dialect("a", "b", "c")), m(lambda: _csv.register_dialect("a", delimiter="ab")), m(lambda: _csv.list_dialects()))  # type: ignore[arg-type,call-arg,no-untyped-call]
_csv.register_dialect("semi", delimiter=";")
_csv.register_dialect("semi2", "semi", strict=True)
_csv.register_dialect("semi3", _csv.Dialect(), quoting=1)  # type: ignore[arg-type]
print("registry 2:", m(lambda: _csv.list_dialects()), m(lambda: _csv.get_dialect("semi").delimiter), m(lambda: _csv.get_dialect("semi2").strict), m(lambda: _csv.get_dialect("semi2").delimiter), m(lambda: _csv.get_dialect("semi3").quoting), m(lambda: type(_csv.get_dialect("semi")).__name__), m(lambda: _csv.get_dialect(name="semi") is _csv.get_dialect("semi")), m(lambda: _csv.get_dialect()), m(lambda: _csv.get_dialect("a", "b")), m(lambda: _csv.get_dialect(nm="a")), m(lambda: _csv.unregister_dialect(name="semi3")), m(lambda: _csv.list_dialects()), m(lambda: _csv.unregister_dialect()), m(lambda: _csv.list_dialects(1)), m(lambda: _csv.list_dialects(x=1)), m(lambda: _csv.get_dialect(5)), m(lambda: _csv.get_dialect([])), m(lambda: sorted(_csv._dialects)), m(lambda: _csv.Dialect("semi2").strict), m(lambda: _csv.Dialect("semi2") is _csv.get_dialect("semi2")), m(lambda: _csv.register_dialect(SubStr("s4")) or sorted(_csv._dialects)), m(lambda: _csv.unregister_dialect("s4")))  # type: ignore[arg-type,attr-defined,call-arg,func-returns-value,no-untyped-call]
print("limit:", m(lambda: _csv.field_size_limit()), m(lambda: _csv.field_size_limit(10)), m(lambda: _csv.field_size_limit()), m(lambda: _csv.field_size_limit("x")), m(lambda: _csv.field_size_limit(True)), m(lambda: _csv.field_size_limit(2**70)), m(lambda: _csv.field_size_limit(new_limit=131072)), m(lambda: _csv.field_size_limit(x=1)), m(lambda: _csv.field_size_limit(1, 2)), m(lambda: _csv.field_size_limit(-5)), m(lambda: _csv.field_size_limit(131072)))  # type: ignore[arg-type,call-arg,no-untyped-call]

print("reader")
for i, (lines, kw) in enumerate([(["a,b,c\r\n", "1,2,3\r\n"], {}), (["a,b,c", "1,2,3"], {}), (['a,"b,c",d'], {}), (['a,"b""c",d'], {}), (['a,"b', 'c",d'], {}), (['a,"b\n', 'c",d'], {}), (['a,"b\r\n', 'c",d'], {}), (["", "a", "", "b"], {}), (["\n", "a\n", "\r\n", "\r"], {}), ([","], {}), ([",\n"], {}), (['""'], {}), (['"",'], {}), (['a,b"c"d,e'], {}), (['a,"b"c,d'], {}), (['a,"b"c,d'], {"strict": True}), (['a,"b" ,d'], {"strict": True}), (["a, b, c"], {"skipinitialspace": True}), (['a,  "b", c'], {"skipinitialspace": True}), (["a, b, c"], {}), (["a\\,b,c"], {"escapechar": "\\"}), (["a\\", "b,c"], {"escapechar": "\\"}), (["a\\\n", "b,c"], {"escapechar": "\\"}), (["a\\\r\n", "b,c"], {"escapechar": "\\"}), (['"a\\"b",c'], {"escapechar": "\\"}), (['"a\\', 'b",c'], {"escapechar": "\\"}), (['"a\\\n', 'b",c'], {"escapechar": "\\"}), (["a,b\\"], {"escapechar": "\\"}), (["\\"], {"escapechar": "\\"}), (['a,"b'], {"strict": True}), (['a,"b'], {}), (['"a"'], {}), (['"a"\r\n'], {}), (["a\rb"], {}), (["a\r\nb"], {}), (["a\n\rb"], {}), (["a\n", "\n", "b\n"], {}), (["a,b\r\n\r\n", "c"], {}), (['"a"\rx'], {}), (['"a""', '"'], {}), (['1,2.5,abc,"3"'], {"quoting": 2}), (['1,,"3"'], {"quoting": 2}), (["1,x"], {"quoting": 2}), (['1,2.5,abc,"3",,""'], {"quoting": 4}), (['1,2.5,abc,"3",,""'], {"quoting": 5}), (['1,2.5,abc,"3",,""'], {"quoting": 1}), (['1,"2",a'], {"quoting": 3}), (['1,"2",a'], {"quoting": 3, "quotechar": None}), ([""], {"quoting": 5}), ([","], {"quoting": 5}), (['a,"b"c'], {"quoting": 2}), (['"a"b,c'], {"quoting": 2}), (["inf,nan,1e5,-0"], {"quoting": 2}), (["a;b", "c;d"], {"delimiter": ";"}), (['a"b', "c"], {"quotechar": None}), (['"a"b'], {"doublequote": False}), (['"a""b"'], {"doublequote": False}), (['"a"",b'], {"doublequote": False}), (['"a"x'], {"doublequote": False, "strict": True}), (["a,b"], {"lineterminator": "x"}), (["axb"], {"lineterminator": "x"}), (['"a"\n\n'], {}), (["a,b\r\n", "\r\n", "\n", "c"], {}), (["\r\n"], {}), (["\r"], {}), (["\n"], {}), (["\r\n", "\r\n"], {}), (["  a,b"], {"skipinitialspace": True}), ([" ,b"], {"skipinitialspace": True}), (["a, "], {"skipinitialspace": True}), (["a, "], {"skipinitialspace": True, "quoting": 5}), (['a, "" '], {"skipinitialspace": True}), (['a,"b"  '], {"strict": True}), (['a,"b"  '], {}), (["\\\n"], {"escapechar": "\\"}), (["a\\"], {"escapechar": "\\"}), (["a\\", ""], {"escapechar": "\\"}), (['"\\"'], {"escapechar": "\\"}), (['"\\'], {"escapechar": "\\"}), (['"\\', ""], {"escapechar": "\\"}), (['"\\', ""], {"escapechar": "\\", "strict": True}), (["\\,"], {"escapechar": "\\"}), (["a\\\n"], {"escapechar": "\\"}), (["a\\\r"], {"escapechar": "\\"}), (["a\\\r\n", "b"], {"escapechar": "\\"}), (["a\\\rb"], {"escapechar": "\\"}), (["a\\\r\nb"], {"escapechar": "\\"}), (['"a"\\'], {"escapechar": "\\"}), (['"a"\\'], {"escapechar": "\\", "strict": True}), (["\\x"], {"escapechar": "\\", "quoting": 2}), (["\\", ""], {"escapechar": "\\", "quoting": 2}), (['"a', "b"], {}), (['"a', "b"], {"strict": True}), (['"a', '"'], {}), (['"a', ""], {}), (['"a', ""], {"strict": True}), (["", '"a'], {}), (["", '"a'], {"strict": True}), ([b"a,b"], {}), ([1], {}), (["a,b", 1], {}), (5, {}), (["a,b"], {"quoting": 3, "escapechar": "\\", "quotechar": None}), (['a\\"b'], {"quoting": 3, "escapechar": "\\"}), (['"a\\"b"'], {"quoting": 3, "escapechar": "\\"}), (["é,☃,\U0001f600"], {}), (["a b"], {}), (["a\x85b"], {}), (["a\x0cb"], {}), (["a\x00b"], {}), (["a\tb"], {"delimiter": "\t"}), (["a b  c"], {"delimiter": " "}), (["a b  c"], {"delimiter": " ", "skipinitialspace": True}), (['a b  c "" '], {"delimiter": " ", "skipinitialspace": True}), (['a b  c "" '], {"delimiter": " ", "skipinitialspace": True, "quoting": 5}), (['a b  c "" '], {"delimiter": " ", "skipinitialspace": True, "quoting": 4}), (['1 2 ""'], {"delimiter": " ", "skipinitialspace": True, "quoting": 2}), (['1.5,"a"'], {"quoting": 4}), (['1.5,1_0,"a", 0x10, 1e400'], {"quoting": 2}), (["a"], {"quoting": 2, "strict": True})]):
    print(" ", i, sorted(kw.items()), rd(lines, **kw))  # type: ignore[arg-type,attr-defined,no-untyped-call]
print("reader dialects:", rd(["a;b", "c;d"], "semi"), rd(["a;b", "c;d"], _csv.Dialect(delimiter=";")), rd(["a;b", "c;d"], Attr), rd(["a;b"], "semi", delimiter="|"), rd(["a|b"], "semi", delimiter="|"))  # type: ignore[no-untyped-call]
print("reader errors:", m(lambda: _csv.reader()), m(lambda: _csv.reader([], "excel", "x")), m(lambda: _csv.reader([], delimiter="ab")), m(lambda: _csv.reader([], dialect="semi").dialect.delimiter), m(lambda: _csv.reader([], "nope")), m(lambda: _csv.reader([], bogus=1)))  # type: ignore[call-arg,no-untyped-call]
print("reader type:", m(lambda: type(_csv.reader([])).__name__), m(lambda: type(_csv.reader([])).__module__), m(lambda: _csv.Reader()), m(lambda: _csv.Writer()), m(lambda: _csv.Reader.__new__(_csv.Reader)), m(lambda: type(_csv.reader([])) is _csv.Reader), m(lambda: isinstance(_csv.reader([]), _csv.Reader)), m(lambda: iter(_csv.reader([])) is not None), m(lambda: _csv.Reader.__next__(5)))  # type: ignore[arg-type,no-untyped-call]
r = _csv.reader(["a,b", "c,d", ""])
print("line_num:", r.line_num, next(r), r.line_num, next(r), r.line_num, next(r), r.line_num, m(lambda: next(r)), r.line_num, m(lambda: next(r)), type(r.dialect).__name__)  # type: ignore[no-untyped-call]
print("reader attributes:", m(lambda: setattr(r, "line_num", 5)), m(lambda: setattr(r, "dialect", 5)), m(lambda: setattr(r, "x", 5)))  # type: ignore[no-untyped-call]
r = _csv.reader(iter(["a,b", 5]))  # type: ignore[arg-type]
print("bad line:", m(lambda: next(r)), m(lambda: next(r)), m(lambda: next(r)), r.line_num)  # type: ignore[no-untyped-call]
r = _csv.reader(['a,"b', 'c"', "d"])
print("spanning:", m(lambda: next(r)), r.line_num, m(lambda: next(r)), r.line_num)  # type: ignore[no-untyped-call]
r = _csv.reader(["x" * 20, "yy"])
_csv.field_size_limit(10)
print("limit hit:", m(lambda: next(r)), m(lambda: next(r)), m(lambda: next(r)), r.line_num)  # type: ignore[no-untyped-call]
_csv.field_size_limit(5)
print("limit 5:", rd(["12345"]), rd(["123456"]), rd(['"12345"']), rd(['"123456"']), rd(["1234", "5"]), rd(["1234\\", "5"], escapechar="\\"), _csv.field_size_limit(131072))  # type: ignore[no-untyped-call]


class Fobj:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.lines = []

    def write(self, s):  # type: ignore[no-untyped-def]
        self.lines.append(s)
        return len(s)


class Fl:
    def __float__(self):  # type: ignore[no-untyped-def]
        return 3.0

    def __str__(self):  # type: ignore[no-untyped-def]
        return "fl"


class Strish:
    def __str__(self):  # type: ignore[no-untyped-def]
        return "strish,x"


class BadStr:
    def __str__(self):  # type: ignore[no-untyped-def]
        raise ValueError("no str")


FIELDS = ["a,b", 'c"d', "e\nf", 1, 2.5, None, True, "x"]
ODD = [1 + 2j, b"x", [1], {2: 3}, 1e400, -0.0, 10**30, 1.5, True, Ellipsis]
print("writer")
for i, (rows, kw) in enumerate([([["a", "b", "c"], [1, 2.5, None, True]], {}), ([["a,b", 'c"d', "e\nf", "g\rh", "i\r\nj", "k\r\nl"]], {}), ([["a,b", 'c"d', "e\nf"]], {"quoting": 1}), ([FIELDS], {"quoting": 2}), ([FIELDS], {"quoting": 4}), ([FIELDS], {"quoting": 5}), ([FIELDS], {"quoting": 3}), ([FIELDS], {"quoting": 3, "escapechar": "\\"}), ([FIELDS], {"quoting": 3, "escapechar": "\\", "quotechar": None}), ([FIELDS], {"quoting": 3, "escapechar": "\\", "lineterminator": "\n"}), ([["a,b", 'c"d', "e\nf", "x\\y"]], {"escapechar": "\\"}), ([["a,b", 'c"d', "e\nf", "x\\y"]], {"escapechar": "\\", "doublequote": False}), ([['c"d']], {"doublequote": False}), ([['c"d']], {"doublequote": False, "quoting": 1}), ([['c"d']], {"doublequote": False, "quoting": 1, "escapechar": "\\"}), ([['c"d', "a\\b"]], {"doublequote": True, "quoting": 1, "escapechar": "\\"}), ([["axb"]], {"lineterminator": "x"}), ([["axb"]], {"lineterminator": "x", "quoting": 3}), ([["a\nb"]], {"lineterminator": "x"}), ([[]], {}), ([[], []], {}), ([[""]], {}), ([[""]], {"quoting": 3}), ([[""]], {"quoting": 3, "escapechar": "\\"}), ([[None]], {}), ([[None]], {"quoting": 3}), ([[None]], {"quoting": 4}), ([[None]], {"quoting": 5}), ([[None]], {"quoting": 2}), ([[None]], {"quoting": 1}), ([[""]], {"quoting": 4}), ([[""]], {"quoting": 5}), ([[""]], {"quoting": 2}), ([["", ""]], {"quoting": 3}), ([["", None]], {"quoting": 5}), ([[None, ""]], {"quoting": 5}), ([[None, None]], {"quoting": 5}), ([[None, None]], {"quoting": 4}), ([[None, "a"]], {"quoting": 4}), ([[None, 1]], {"quoting": 4}), ([["a", "", "b"]], {"delimiter": " ", "skipinitialspace": True}), ([["a", "", "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 3}), ([["a", "", "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 3, "escapechar": "\\"}), ([["a", None, "b"]], {"delimiter": " ", "skipinitialspace": True}), ([["a", None, "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 5}), ([["a", None, "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 4}), ([["a", None, "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 2}), ([["a", "", "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 5}), ([["a", "", "b"]], {"delimiter": " ", "skipinitialspace": True, "quoting": 4}), ([[""]], {"delimiter": " ", "skipinitialspace": True}), ([[None]], {"delimiter": " ", "skipinitialspace": True}), ([[None]], {"delimiter": " ", "skipinitialspace": True, "quoting": 5}), ([["a", ""]], {"delimiter": " "}), ([["a b", "c"]], {"delimiter": " "}), ([["a\tb", "c"]], {"delimiter": "\t"}), ([["a;b", "c,d"]], {"delimiter": ";"}), (["ab"], {}), ([5], {}), ([None], {}), ([[1, 2], 7], {}), ([[1, "é", "☃", "\U0001f600"]], {}), ([[1, 2]], {"quoting": 3, "escapechar": ","}), ([["1,2"]], {"quoting": 3, "escapechar": "\\", "delimiter": ","}), ([["\\"]], {"quoting": 3, "escapechar": "\\"}), ([["\\"]], {"escapechar": "\\"}), ([["\\"]], {"escapechar": "\\", "quoting": 1}), ([["\\"]], {}), ([['"']], {}), ([['"']], {"quoting": 3}), ([['"']], {"quoting": 3, "escapechar": "\\"}), ([["a\x85b", "a b", "a\x00b", "a\x0cb"]], {}), ([ODD], {}), ([ODD], {"quoting": 2}), ([ODD], {"quoting": 4}), ([ODD], {"quoting": 5}), ([[Num(), Fl(), SubStr("a,b"), Strish(), (1, 2)]], {"quoting": 2}), ([[Num(), Fl(), SubStr("a,b"), Strish(), (1, 2)]], {"quoting": 4}), ([[Num(), Fl(), SubStr("a,b"), Strish(), (1, 2)]], {"quoting": 0}), ([[BadStr()]], {}), ([["a", BadStr()]], {}), ([(x for x in "abc")], {}), ([{"k": 1, "j": 2}], {}), ([iter([1, 2])], {})]):
    print(" ", i, sorted(kw.items()), wr(rows, **kw))  # type: ignore[arg-type,attr-defined,no-untyped-call]
print("writer dialects:", wr([["a;b", "c,d"]], "semi"), wr([["a;b", "c,d"]], _csv.Dialect(delimiter=";")), wr([["a;b", "c,d"]], Attr), wr([["a;b", "c|d"]], "semi", delimiter="|"))  # type: ignore[no-untyped-call]


def rows_written():  # type: ignore[no-untyped-def]
    f = Fobj()  # type: ignore[no-untyped-call]
    w = _csv.writer(f)
    r = w.writerow(["a", 1])
    r2 = w.writerows([["b", 2], ("c", 3), "de", iter(["f"])])  # type: ignore[func-returns-value]
    r3 = w.writerows([])  # type: ignore[func-returns-value]
    return f.lines, r, r2, r3


def rows_until_error():  # type: ignore[no-untyped-def]
    f = Fobj()  # type: ignore[no-untyped-call]
    w = _csv.writer(f)
    try:
        w.writerows([["a"], 5, ["b"]])  # type: ignore[list-item]
    except _csv.Error as e:
        return f.lines, str(e)
    return None


print("writerows:", m(rows_written), m(rows_until_error))  # type: ignore[no-untyped-call]
print("writer arguments:", m(lambda: _csv.writer(Fobj()).writerows(5)), m(lambda: _csv.writer(Fobj()).writerows()), m(lambda: _csv.writer(Fobj()).writerows([], 1)), m(lambda: _csv.writer(Fobj()).writerow()), m(lambda: _csv.writer(Fobj()).writerow([], [])), m(lambda: _csv.writer(Fobj()).writerow(row=[])), m(lambda: _csv.writer(Fobj()).writerows(rows=[])), m(lambda: _csv.writer(Fobj()).writerows(iter([[1], [2]]))))  # type: ignore[arg-type,call-arg,no-untyped-call]
print("writer construction:", m(lambda: _csv.writer()), m(lambda: _csv.writer(5)), m(lambda: _csv.writer(Fobj(), "excel", "x")), m(lambda: _csv.writer(Fobj(), "nope")), m(lambda: _csv.writer(Fobj(), bogus=1)), m(lambda: _csv.writer(Fobj(), delimiter="ab")), m(lambda: type(_csv.writer(Fobj())).__name__), m(lambda: type(_csv.writer(Fobj())) is _csv.Writer), m(lambda: _csv.writer(Fobj(), "semi").dialect.delimiter), m(lambda: type(_csv.writer(Fobj()).dialect).__name__))  # type: ignore[arg-type,call-arg,no-untyped-call]


class W1:
    write = 5


class W2:
    def __getattr__(self, n):  # type: ignore[no-untyped-def]
        raise KeyError(n)


class W3:
    def __getattr__(self, n):  # type: ignore[no-untyped-def]
        raise AttributeError(n)


class W4:
    def write(self, s):  # type: ignore[no-untyped-def]
        return "ret:" + s


print("write methods:", m(lambda: _csv.writer(W1())), m(lambda: _csv.writer(W2())), m(lambda: _csv.writer(W3())), m(lambda: _csv.writer(W4()).writerow([1, 2])), m(lambda: _csv.writer(W4()).writerows([[1]])))  # type: ignore[arg-type,no-untyped-call]
w = _csv.writer(Fobj())  # type: ignore[no-untyped-call]
print("writer attributes:", m(lambda: setattr(w, "dialect", 5)), m(lambda: setattr(w, "x", 5)), m(lambda: _csv.Writer.writerow(w, [1])), m(lambda: _csv.Writer.writerow(5, [1])))  # type: ignore[arg-type,no-untyped-call]

print("csv package")
text = "name,qty,price\r\nwidget,3,2.50\r\n\"gad,get\",1,10\r\n"
print(" ", list(csv.reader(io.StringIO(text, newline=""))))
print(" ", list(csv.DictReader(io.StringIO(text, newline=""))))
print(" ", list(csv.DictReader(io.StringIO("a,b\r\n1,2,3\r\n4\r\n", newline=""), restkey="rest", restval="-")))
print(" ", list(csv.DictReader(io.StringIO("1,2\r\n", newline=""), fieldnames=["x", "y"])), csv.DictReader(io.StringIO(text, newline="")).fieldnames)
print(" ", sorted(csv.list_dialects()), csv.get_dialect("excel").delimiter, csv.excel_tab.delimiter == "\t", repr(csv.unix_dialect.lineterminator), csv.unix_dialect.quoting == csv.QUOTE_ALL)
out = io.StringIO()
w2 = csv.writer(out)
w2.writerow(["a", 1, 2.5, None])
w2.writerows([["x,y", 'q"r']])
print(" ", repr(out.getvalue()))
print(" ", m(lambda: csv.reader([], delimiter="ab")), m(lambda: csv.register_dialect("x", 5)))  # type: ignore[arg-type,no-untyped-call]


class Semi(csv.Dialect):
    delimiter = ";"
    quotechar = "'"
    lineterminator = "\n"
    quoting = csv.QUOTE_ALL


csv.register_dialect("semi", Semi)
print(" ", csv.get_dialect("semi").delimiter, list(csv.reader(["a;'b;c'"], "semi")), m(lambda: list(csv.reader(["a;b"], Semi))))  # type: ignore[no-untyped-call]


class BadDialect(csv.Dialect):
    delimiter = ",,"
    lineterminator = "\n"


class NoTerminator(csv.Dialect):
    delimiter = ","


print(" ", m(BadDialect), m(NoTerminator), m(lambda: csv.Sniffer().sniff("a;b;c\n1;2;3\n").delimiter), m(lambda: csv.Sniffer().has_header("a;b;c\n1;2;3\n")), m(lambda: csv.Sniffer().sniff("")))  # type: ignore[no-untyped-call]
print(" ", csv.field_size_limit(), csv.Error is _csv.Error, csv.reader is _csv.reader, csv.writer is _csv.writer, csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL)
