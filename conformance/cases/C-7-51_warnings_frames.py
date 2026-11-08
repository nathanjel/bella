# clause: C-7-51
# spec: section 7
# status: P1
# source: dialect specification section 7, Python/_warnings.c, Lib/warnings.py, Lib/_py_warnings.py
"""Warnings charged to a frame, which warn() finds through the frame chain: stacklevel from 0 past the outermost frame (then
<sys>), skip_file_prefixes, a Warning instance as the message, the default filters by category and by the frame's module
(DeprecationWarning shown from __main__ only), what "default" leaves in the module's __warningregistry__, a replaced showwarning,
catch_warnings with a category, the deprecated decorator on a function and a class, and messages that are not strings. eval1 and
eval2 see their own frames here, so this case is for CPython and the compiled program."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, B028, E501, E731, E741, E742, F601, PLR0133, SLF001, UP031
import os
import warnings


HERE = os.path.dirname(os.path.abspath(__file__))


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def shown(messages):  # type: ignore[no-untyped-def]
    return [(w.category.__name__, os.path.basename(w.filename), w.lineno, str(w.message), w.module, w.line) for w in messages]


def entries(registry):  # type: ignore[no-untyped-def]
    """A registry's items, the category by name, sorted by their text."""
    return sorted(((((k[0], k[1].__name__, *k[2:]) if isinstance(k, tuple) else k), v) for k, v in registry.items()), key=str)


def inner(level, **kw):  # type: ignore[no-untyped-def]
    warnings.warn("from inner", stacklevel=level, **kw)


def outer(level, **kw):  # type: ignore[no-untyped-def]
    inner(level, **kw)  # type: ignore[no-untyped-call]


with warnings.catch_warnings(record=True) as rec:
    warnings.simplefilter("always")
    for level in (0, 1, 2, 3, 4, 99):
        outer(level)  # type: ignore[no-untyped-call]
    outer(2, skip_file_prefixes=(HERE,))  # type: ignore[no-untyped-call]
    outer(1, skip_file_prefixes=(HERE,))  # type: ignore[no-untyped-call]
    warnings.warn(DeprecationWarning("an instance"), UserWarning)
    warnings.warn("plain")
    warnings.warn("typed", FutureWarning, 1, None)
print("frames:", shown(rec))  # type: ignore[no-untyped-call]
print("registry:", entries(globals()["__warningregistry__"]))  # type: ignore[no-untyped-call]

with warnings.catch_warnings(record=True) as rec:   # the default filters, by category and by module
    warnings.warn("user", UserWarning)
    warnings.warn("deprecated in __main__", DeprecationWarning)
    warnings.warn("pending", PendingDeprecationWarning)
    warnings.warn("import", ImportWarning)
    warnings.warn("resource", ResourceWarning)
    warnings.warn("syntax", SyntaxWarning)
    warnings.warn("runtime", RuntimeWarning)
    warnings.warn_explicit("deprecated elsewhere", DeprecationWarning, "elsewhere.py", 3, module="elsewhere")
    warnings.warn_explicit("deprecated in main by name", DeprecationWarning, "x.py", 4, module="__main__")
    warnings.warn_explicit("deprecated, no module", DeprecationWarning, "x.py", 5)
    warnings.warn_explicit("user elsewhere", UserWarning, "elsewhere.py", 6, module="elsewhere")
    warnings.warn("user", UserWarning)             # the same text at another line: shown again under "default"
    for _ in range(3):
        warnings.warn("repeated", UserWarning)     # one location: once under "default"
print("default filters:", shown(rec))  # type: ignore[no-untyped-call]
print("registry after:", entries(globals()["__warningregistry__"]))  # type: ignore[no-untyped-call]

captured = []  # type: ignore[var-annotated]
with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.showwarning = lambda message, category, filename, lineno, file=None, line=None: captured.append((str(message), category.__name__, os.path.basename(filename), lineno, file is None, line))  # type: ignore[has-type]
    warnings.warn("to showwarning")
    warnings.warn_explicit("explicit", UserWarning, "f.py", 2)
print("showwarning:", captured, warnings.showwarning is warnings._showwarning_orig)  # type: ignore[attr-defined]
print("formatwarning:", repr(warnings.formatwarning("msg", UserWarning, __file__, 33).replace(__file__, "<file>")), repr(warnings.formatwarning("msg", UserWarning, "nowhere.py", 1)), repr(warnings.formatwarning("msg", UserWarning, "f.py", 1, line="  given\n")), repr(str(warnings.WarningMessage("m", UserWarning, "f.py", 3))))

with warnings.catch_warnings(record=True, action="ignore") as rec:
    warnings.warn("ignored")
    print("catch ignore:", len(rec), warnings.filters[0])
with warnings.catch_warnings(record=True, action="always", category=DeprecationWarning) as rec:
    warnings.warn("dep", DeprecationWarning)
    warnings.warn("user")
    print("catch category:", shown(rec), warnings.filters[0])  # type: ignore[no-untyped-call]
with warnings.catch_warnings() as nothing:
    print("catch plain:", nothing, type(warnings.catch_warnings()).__name__)


@warnings.deprecated("use g() instead")
def f(x):  # type: ignore[no-untyped-def]
    return x * 2


@warnings.deprecated("old class", category=FutureWarning, stacklevel=1)
class Old:
    def __init__(self, v):  # type: ignore[no-untyped-def]
        self.v = v


with warnings.catch_warnings(record=True) as rec:
    warnings.simplefilter("always")
    print("deprecated:", f(21), Old(1).v, f.__deprecated__, Old.__deprecated__, shown(rec))  # type: ignore[attr-defined,no-untyped-call]

with warnings.catch_warnings(record=True) as rec:
    warnings.simplefilter("always")
    warnings.warn("message is an int: %d" % 3)
    warnings.warn(42)  # type: ignore[call-overload]
    print("odd messages:", shown(rec), [type(w.message).__name__ for w in rec])  # type: ignore[no-untyped-call]
