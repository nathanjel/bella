# clause: C-7-50
# spec: section 7
# status: P1
# source: dialect specification section 7, Python/_warnings.c, Lib/warnings.py, Lib/_py_warnings.py
"""The warnings machinery over its C half (_warnings), apart from what depends on the calling frame (C-7-51): the module's
objects and defaults, the actions (error, ignore, always, all, default, once, module) through warn_explicit and what they leave
in a registry and in the once registry, filterwarnings with message and module patterns and a line, the module filter matched
against a filename when no module is given, resetwarnings, catch_warnings (record, action, category), a replaced showwarning,
formatwarning with the source line, WarningMessage, and the parsing errors of warn and warn_explicit."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, B028, E501, E731, E741, E742, F601, PLR0133, SLF001, UP031
import os
import sys
import warnings

import _warnings

HERE = os.path.dirname(os.path.abspath(__file__))


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def shown(messages):  # type: ignore[no-untyped-def]
    return [(w.category.__name__, os.path.basename(w.filename), w.lineno, str(w.message), w.module, w.line) for w in messages]


def entries(registry):  # type: ignore[no-untyped-def]
    """A registry's items but its version (C-7-51's: the process-wide count of filter changes), the category by name, sorted by their text."""
    return sorted(((((k[0], k[1].__name__, *k[2:]) if isinstance(k, tuple) else k), v) for k, v in registry.items() if k != "version"), key=str)


def inner(level, **kw):  # type: ignore[no-untyped-def]
    warnings.warn("from inner", stacklevel=level, **kw)


def outer(level, **kw):  # type: ignore[no-untyped-def]
    inner(level, **kw)  # type: ignore[no-untyped-call]


print("module:", sorted(n for n in dir(_warnings) if not n.startswith("__")), [type(getattr(_warnings, n)).__name__ for n in ("warn", "warn_explicit", "filters", "_onceregistry", "_defaultaction", "_warnings_context", "_acquire_lock")], _warnings._warnings_context.name, _warnings._defaultaction, _warnings._onceregistry, repr(_warnings.__doc__))  # type: ignore[attr-defined]
print("defaults:", _warnings.filters, warnings.filters is _warnings.filters, warnings.warn is _warnings.warn, warnings.warn_explicit is _warnings.warn_explicit, warnings.defaultaction, warnings.onceregistry is _warnings._onceregistry, warnings._filters_version, type(warnings._lock).__name__, warnings._warnings_context is _warnings._warnings_context)  # type: ignore[attr-defined]
print("docs:", repr(_warnings.warn.__doc__), repr(_warnings.warn_explicit.__doc__), repr(_warnings._acquire_lock.__doc__))  # type: ignore[attr-defined]

for action in ("error", "ignore", "always", "all", "default", "once", "module"):
    registry = {}  # type: ignore[var-annotated]
    once_before = len(warnings.onceregistry)  # type: ignore[attr-defined]
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter(action)  # type: ignore[arg-type]
        outcomes = []
        for lineno in (10, 10, 11):
            for mod in ("a", "b"):
                try:
                    warnings.warn_explicit("text", UserWarning, mod + ".py", lineno, mod, registry)
                    outcomes.append(".")
                except UserWarning as e:
                    outcomes.append("E:" + str(e))
    print("action", action, "".join(outcomes), len(rec), [(w.filename, w.lineno) for w in rec], entries(registry), len(warnings.onceregistry) - once_before)  # type: ignore[attr-defined,no-untyped-call]

with warnings.catch_warnings(record=True) as rec:   # "once" without a registry of the caller's: the module's once registry
    warnings.simplefilter("once")
    for _ in range(2):
        for mod in ("a", "b"):
            warnings.warn_explicit("once text", UserWarning, mod + ".py", 1, mod)
            warnings.warn_explicit("once text", UserWarning, mod + ".py", 2, mod)
            warnings.warn_explicit("other text", UserWarning, mod + ".py", 3, mod)
    print("once registry:", len(rec), [(w.filename, w.lineno) for w in rec], entries(warnings.onceregistry))  # type: ignore[attr-defined,no-untyped-call]
    warnings.onceregistry.clear()  # type: ignore[attr-defined]

with warnings.catch_warnings(record=True) as rec:   # patterns and lines
    warnings.resetwarnings()
    warnings.filterwarnings("ignore", message="^ign")
    warnings.filterwarnings("error", category=FutureWarning, module="^mod[.]sub$")
    warnings.filterwarnings("always", lineno=42)
    warnings.simplefilter("ignore", DeprecationWarning, append=True)
    print("filters:", warnings.filters)
    outcomes = []
    for text, cat, mod, line in (("ignored", UserWarning, "x", 1), ("Ignored?", UserWarning, "x", 1), ("fut", FutureWarning, "mod.sub", 1), ("fut", FutureWarning, "mod.other", 1), ("any", UserWarning, "x", 42), ("any", UserWarning, "x", 42), ("dep", DeprecationWarning, "__main__", 1)):
        try:
            warnings.warn_explicit(text, cat, "f.py", line, mod, {})
            outcomes.append("shown" if rec and str(rec[-1].message) == text and rec[-1].lineno == line else "quiet")
        except FutureWarning as e:
            outcomes.append("error:" + str(e))
    print("patterns:", outcomes, len(rec), shown(rec))  # type: ignore[no-untyped-call]
    warnings.filterwarnings("error", category=UserWarning, module="^mod[.]sub$")   # without a module, matched against the filename
    print("filename match:", [(name, m(lambda: warnings.warn_explicit("t", UserWarning, name, 1, registry={}))) for name in ("mod/sub.py", "/root/mod/sub.py", "mod/sub/__init__.py", "mod/sub.pyw", "mod.sub", "<string>", "", "mod/sub.py.bak")], [(name, m(lambda: warnings.warn_explicit("t", UserWarning, "mod/sub.py", 1, name, {}))) for name in ("mod.sub", "other", "")], len(rec))  # type: ignore[no-untyped-call]
    warnings.resetwarnings()
    print("reset:", warnings.filters, warnings.filters is _warnings.filters)
print("after:", warnings.filters[:2], len(warnings.filters))

print("errors:", m(lambda: warnings.warn()), m(lambda: warnings.warn("m", int)), m(lambda: warnings.warn("m", "cat")), m(lambda: warnings.warn("m", stacklevel="2")), m(lambda: warnings.warn("m", skip_file_prefixes=["x"])), m(lambda: warnings.warn("m", skip_file_prefixes=(1,))), m(lambda: warnings.warn("m", 1, 2, 3, 4)), m(lambda: warnings.warn("m", nope=1)), m(lambda: warnings.warn_explicit("m", UserWarning)), m(lambda: warnings.warn_explicit("m", UserWarning, 1, 1)), m(lambda: warnings.warn_explicit("m", UserWarning, "f", "x")), m(lambda: warnings.warn_explicit("m", UserWarning, "f", 1, registry=3)), m(lambda: warnings.warn_explicit("m", UserWarning, "f", 1, module_globals=3)), m(lambda: warnings.warn_explicit("m", "notatype", "f", 1)), m(lambda: _warnings._release_lock()), m(lambda: _warnings._filters_mutated_lock_held()), m(lambda: _warnings._acquire_lock(1)), m(lambda: warnings.filterwarnings("bogus")), m(lambda: warnings.filterwarnings("ignore", category=int)), m(lambda: warnings.simplefilter("ignore", lineno=-1)), m(lambda: warnings.filterwarnings("ignore", module=3)))  # type: ignore[arg-type,attr-defined,call-overload,no-untyped-call]

captured = []  # type: ignore[var-annotated]
with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.showwarning = lambda message, category, filename, lineno, file=None, line=None: captured.append((str(message), category.__name__, filename, lineno, file is None, line))  # type: ignore[has-type]
    warnings.warn_explicit("explicit", UserWarning, "f.py", 2)
    warnings.warn_explicit(FutureWarning("an instance"), UserWarning, "g.py", 3, "mod")
print("showwarning:", captured, warnings.showwarning is warnings._showwarning_orig)  # type: ignore[attr-defined]
print("formatwarning:", repr(warnings.formatwarning("msg", UserWarning, __file__, 33).replace(__file__, "<file>")), repr(warnings.formatwarning("msg", UserWarning, "nowhere.py", 1)), repr(warnings.formatwarning("msg", UserWarning, "f.py", 1, line="  given\n")), repr(str(warnings.WarningMessage("m", UserWarning, "f.py", 3))))
with warnings.catch_warnings(record=True, action="ignore") as rec:
    warnings.warn_explicit("ignored", UserWarning, "f.py", 1)
    print("catch ignore:", len(rec), warnings.filters[0])
with warnings.catch_warnings(record=True, action="always", category=DeprecationWarning) as rec:
    warnings.warn_explicit("dep", DeprecationWarning, "f.py", 1, "elsewhere")
    warnings.warn_explicit("user", UserWarning, "f.py", 2, "elsewhere")
    print("catch category:", shown(rec), warnings.filters[0])  # type: ignore[no-untyped-call]
with warnings.catch_warnings() as nothing:
    print("catch plain:", nothing, type(warnings.catch_warnings()).__name__)
print("stderr:", sys.stderr is sys.__stderr__)
