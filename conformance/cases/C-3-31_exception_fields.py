# clause: C-3-31
# spec: section 3 (exceptions), section 9 (lifetimes)
# status: P1
# source: review log RL-228 on (astra-low 10: A10-2, A10-3, A10-11; gemini-4-argon-high 09: 2.4)
"""An exception's args, __traceback__, __cause__, __context__ and __suppress_context__ are fields
of BaseException, not entries of its __dict__: vars() shows none of them, their descriptors check
what they are given, and they die after the __dict__'s values, in BaseException_clear's order (a
subclass's __slots__ first, then the dict, args, the cause, the context). A raise sets __context__
to the exception being handled, replacing an earlier context and cutting a link back to the new
exception that would close a cycle. `raise ... from` takes an exception class, an instance or
None, and sets __suppress_context__; so does assigning __cause__. An except clause's types are all
checked before any is matched."""


class Probe:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print("dies", self.name)


class Linked(Exception):
    def __del__(self) -> None:
        print("dies", self.args[0])


class Slotted(Exception):
    __slots__ = ("s",)


class NotAnException:
    pass


# the fields are not in the __dict__
e = ValueError("v", 2)
print("vars of a new exception:", list(vars(e)))
e.extra = 1  # type: ignore[attr-defined]  # an exception has a __dict__; the checker cannot see it
print("vars after a store:", list(vars(e)))
e.args = [3, 4]  # type: ignore[assignment]  # any sequence is accepted and made a tuple
print("args from a list:", e.args, type(e.args).__name__)

# each descriptor checks its value; none can be deleted
for name in ("__cause__", "__context__", "__traceback__", "__suppress_context__"):
    try:
        setattr(e, name, 1)
        print(name, "= 1 accepted")
    except TypeError:
        print(name, "= 1 TypeError")
for name in ("args", "__cause__", "__context__", "__traceback__", "__suppress_context__"):
    try:
        delattr(e, name)
        print("del", name, "accepted")
    except TypeError:
        print("del", name, "TypeError")

# assigning a cause, even None, suppresses the context
f = KeyError("f")
print("suppressed before:", f.__suppress_context__)
f.__cause__ = None
print("suppressed after __cause__ = None:", f.__suppress_context__, f.__cause__)
f.__suppress_context__ = False
f.__cause__ = ValueError("c")
print("after a cause:", f.__suppress_context__, type(f.__cause__).__name__)

# raise ... from: an exception class is called, an instance taken, None clears; else TypeError
for cause in (1, NotAnException, KeyError, KeyError("k"), None):
    try:
        try:
            raise ValueError("raised") from cause  # type: ignore[misc]  # non-exceptions on purpose
        except ValueError as raised:
            print("from", type(cause).__name__, "->", type(raised.__cause__).__name__, raised.__suppress_context__)
    except TypeError:
        print("from", type(cause).__name__, "-> TypeError")

# a raise replaces an earlier context with the exception being handled
reused = ValueError("reused")
for cls in (KeyError, TypeError):
    try:
        try:
            raise cls("outer")
        except Exception:
            raise reused  # noqa: B904 -- the same object again: its context is replaced
    except ValueError as caught:
        print("context of the reused exception:", type(caught.__context__).__name__)

# ... and cuts a link back to the new exception, which would make a cycle
a = ValueError("a")
b = TypeError("b")
try:
    try:
        raise a
    except ValueError:
        raise b  # noqa: B904 -- b's context is a
except TypeError:
    try:
        raise a  # noqa: B904 -- a's context becomes b; b's link back to a is cut
    except ValueError:
        print("a's context is b:", a.__context__ is b, "b's context cut:", b.__context__ is None)

# an except clause's types are checked before any is matched
for spec in ((ValueError, 42), ((ValueError,),), ValueError):
    try:
        try:
            raise ValueError("matched?")
        except spec:  # type: ignore[misc]  # noqa: B030 -- an invalid clause on purpose
            print("matched", type(spec).__name__)
    except TypeError:
        print("invalid clause", type(spec).__name__)

# AttributeError's name and obj are fields too
class Plain:
    pass


try:
    Plain().missing  # type: ignore[attr-defined]  # noqa: B018 -- a missing attribute on purpose
except AttributeError as err:
    print("AttributeError vars:", list(vars(err)), err.name, type(err.obj).__name__)

# the fields die after the slots and the dict, in BaseException_clear's order
s = Slotted(Probe("arg"))
s.s = Probe("slot")  # type: ignore[attr-defined]  # the slot exists at runtime
s.x = Probe("dict value")  # type: ignore[attr-defined]  # the dict Exception gives it
s.__cause__ = Linked("cause")
s.__context__ = Linked("context")
print("suppressed:", s.__suppress_context__)
del s
print("end")
