"""_suggestions, in Python (Modules/_suggestions.c): the module traceback asks for the closest name when it reports an
AttributeError, a NameError, an ImportError or a ModuleNotFoundError. Its one function takes the clinic's arguments as the C does
(two, positional only, the second a str), checks the candidates as the C does (an exact list of str), and chooses with
Python/suggestions.c's _Py_CalculateSuggestions, which the runtime has (`_keyword_suggestion`, the choice every "Did you mean"
of a keyword argument makes): no more than 750 candidates, no more than 40 bytes of UTF-8 left once the common prefix and suffix
are trimmed, a third of the characters changed at most. A name the UTF-8 encoder refuses (a lone surrogate) raises its error
where PyUnicode_AsUTF8AndSize raises it: the item first, then each candidate that is not equal to it, in order."""

__all__ = ["_generate_suggestions"]

__name__ = "_suggestions"

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions over a tuple of str
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    def _tp_name(o: object) -> str:
        return type(o).__name__

    _keyword_suggestion: Callable[..., Any] = _missing


def _generate_suggestions(*args: object, **kwds: object) -> object:
    """Returns the candidate in candidates that's closest to item"""
    if kwds:                                     # METH_FASTCALL
        raise TypeError("_suggestions._generate_suggestions() takes no keyword arguments")
    if len(args) != 2:                           # _PyArg_CheckPositional
        raise TypeError("_generate_suggestions expected 2 arguments, got " + str(len(args)))
    candidates, item = args
    if not issubclass(type(item), str):          # PyUnicode_Check
        raise TypeError("_generate_suggestions() argument 2 must be str, not " + _tp_name(item))
    if type(candidates) is not list:             # PyList_CheckExact
        raise TypeError("candidates must be a list")
    for elem in candidates:
        if not issubclass(type(elem), str):
            raise TypeError("all elements in 'candidates' must be strings")
    if len(candidates) >= 750:                   # MAX_CANDIDATE_ITEMS
        return None
    str.encode(item, "utf-8")                    # PyUnicode_AsUTF8AndSize's errors, in the C's order
    for elem in candidates:
        if not str.__eq__(elem, item):           # _PyUnicode_Equal: an equal candidate is skipped before it is encoded
            str.encode(elem, "utf-8")
    known = tuple(str.__str__(elem) for elem in candidates)   # the values, as the C reads them through any subclass
    suggestion = _keyword_suggestion(known, str.__str__(item))
    if suggestion is None:
        return None
    for elem in candidates:                      # the candidate itself, as the C returns it (Py_XNewRef of the list's item)
        if str.__eq__(elem, suggestion):
            return elem
    return suggestion
