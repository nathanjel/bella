# clause: C-7-82
# spec: section 7 (traceback)
# status: P1
# source: Modules/_suggestions.c, Modules/clinic/_suggestions.c.h, Python/suggestions.c (levenshtein_distance,
#         _Py_CalculateSuggestions), Lib/traceback.py (_compute_suggestion_error)
"""_suggestions._generate_suggestions chooses the candidate closest to a name by Levenshtein distance over UTF-8, a move costing
two and a change of ASCII case one: the first of the closest, never the name itself, none when more than a third of the
characters would change, none from 750 candidates on, and none when more than 40 bytes differ once the common prefix and suffix
are trimmed. It takes two arguments, positional only, an exact list of str and a str, and gives back the candidate object itself.
traceback asks it for an AttributeError's attribute, an ImportError's name from a module and a NameError's name."""
import _suggestions  # type: ignore[import-not-found]  # typeshed has no stub for it
import traceback
from collections.abc import Callable

generate = _suggestions._generate_suggestions


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def call(function: object, *args: object, **kwds: object) -> str:
    try:
        result = function(*args, **kwds)  # type: ignore[operator]
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


class Name(str):
    pass


print("choices", call(generate, ["append", "extend", "insert"], "appnd"), call(generate, ["apple", "ample"], "apxle"),
      call(generate, ["Spam", "spam"], "SPAM"), call(generate, ["abc"], "abc"), call(generate, ["abc", "abd"], "abc"),
      call(generate, [], "x"), call(generate, ["xyz"], "abc"), call(generate, ["ab"], "a"), call(generate, ["a"], "b"),
      call(generate, ["café", "cafe"], "cafè"), call(generate, ["ÉTÉ"], "été"), call(generate, ["ab", "ba"], "aa"))
print("a third", *(call(generate, [w], "abcdefghi") for w in ("abcdefxyz", "abcdefgxy", "abcdefghx", "xbcdefghy", "ABCDEFGHI", "abcdefghiXYZ")))
middle = "".join(chr(ord("a") + i % 26) for i in range(40))
flipped = "".join(c.upper() if i % 4 == 0 else c for i, c in enumerate(middle))
print("forty bytes", call(generate, ["<" + flipped + ">"], "<" + middle + ">"), call(generate, ["<" + flipped + "Q>"], "<" + middle + "q>"),
      call(generate, ["<" + flipped + "é>"], "<" + middle + "è>"), call(generate, ["<" + middle[:39] + "é>"], "<" + middle[:39] + "è>"))
many = ["n" + str(i) for i in range(749)]
print("candidates", call(generate, [*many[:-1], "spam"], "spamm"), call(generate, [*many, "spam"], "spamm"), call(generate, ["spam"] * 750, "spamm"))
first = Name("spam")
second = Name("spam")
chosen = generate([first, second, "spaz"], "spamm")
print("the object itself", chosen is first, type(chosen).__name__)
print("arguments", call(generate, ["a"]), call(generate, ["a"], "a", "a"), call(generate, ["a"], item="a"), call(generate, ("a",), "a"),
      call(generate, [Name("a")], Name("b")), call(generate, ["a", 1], "a"), call(generate, [1], 2), call(generate, {"a": 1}, "b"),
      call(generate, ["a"], b"a"), call(generate, [], 5), call(generate, ["a"] * 800 + [1], "a"))
print("surrogates", call(generate, ["a"], "\ud800"), call(generate, ["\ud800"], "a"), call(generate, ["\ud800", "abc"], "\ud800"),
      call(generate, ["\ud800"] * 750, "a"))


def report(exc: BaseException) -> str:      # what traceback adds to the exception's own text, which is not printed
    line = traceback.format_exception_only(exc)[-1].rstrip("\n")
    return ascii(line[len(type(exc).__name__ + ": " + str(exc)):])


print("attribute", report(AttributeError("x", name="appendd", obj=[])), report(AttributeError("x", name="_privat", obj=type("K", (), {"_private": 1}))),
      report(AttributeError("x", name="privat", obj=type("K", (), {"_private": 1}))), report(AttributeError("x", name="zzzzzz", obj=[])))
try:
    from json import dumsp  # type: ignore[attr-defined]  # noqa: F401  # absent on purpose
except ImportError as exc:
    print("from-import", type(exc).__name__, exc.name, exc.name_from, report(exc))
print("name without a frame", report(NameError("x", name="prnt")), report(NameError("x", name="json")))
