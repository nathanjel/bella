# clause: C-7-85
# spec: section 7
# status: P1
# source: Modules/_sre/sre_lib.h (MAYBE_CHECK_SIGNALS: every 4096 steps of a match), Objects/longobject.c (SIGCHECK in x_mul, x_divrem and long_to_decimal_string_internal),
#         Objects/object.c (PyObject_Str and PyObject_Repr begin with PyErr_CheckSignals), Modules/signalmodule.c (PyErr_CheckSignals, _PyErr_CheckSignalsTstate),
#         Python/ceval_gil.c (handle_signals), deviation D-25 (e)
"""Signals where the interpreter looks for them inside long work of its own, and not only between a program's statements.
A regular expression that would run for seconds, or for ever, is left when a timer's handler raises, and goes on after a
handler that returns; the pattern serves again afterwards. The same for arithmetic on very large integers: a product, a
quotient, a remainder, a power, and the conversions to and from decimal digits. And str(), repr(), ascii(), print and the
formatting that asks an object for its text look before they ask: a handler that is owed runs there, before the object's
own __str__ or __repr__, in the frame that made the call, and what it raises comes out of the call. What does not ask an
object for its text through them (its __str__ called by hand, a __format__ of its own, len, int) does not look."""
# ruff: noqa: E501, UP018, UP031, UP032  # str() of a literal, % and str.format are what the rows are about
# A clock is involved in the first half, so nothing is printed that depends on when the signal came: a timer that came
# before the work began ends it at the work's first look, with the same line. Work that no handler ended runs to its end
# (seconds) and says so. The second half has no clock: SIGUSR1 and SIGUSR2 are let in together, handlers run lowest number
# first, the first raises, and the second's is owed until something calls the C's own check; the evaluation loop does not
# see it (its note was taken down when the first handler's frame began).
import io
import os
import re
import signal
import sys
import traceback
import types
from collections.abc import Callable

SOON = 0.01              # the timer's first arrival
EVERY = 0.01             # and how often it comes again
U1, U2 = signal.SIGUSR1, signal.SIGUSR2


class Interrupted(Exception):
    """What the timer's handler raises, and SIGUSR1's."""


class Second(Exception):
    """What SIGUSR2's handler raises when it is told to."""


arrivals = 0
wanted = 1
armed = False


def on_timer(signum: int, frame: types.FrameType | None) -> None:
    global arrivals, armed
    if not armed:
        return                               # an arrival that was on its way when the work was over
    arrivals += 1
    if arrivals < wanted:
        return
    armed = False
    signal.setitimer(signal.ITIMER_REAL, 0)
    raise Interrupted


def cut_short(work: Callable[[], object], after: int = 1) -> str:
    """Run `work`, which takes seconds by itself, under a timer whose handler raises at its `after`th arrival."""
    global arrivals, wanted, armed
    arrivals, wanted, armed = 0, after, True
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    try:
        work()
    except Interrupted:
        return f"left at arrival {arrivals}"
    finally:
        armed = False
        signal.setitimer(signal.ITIMER_REAL, 0)
    return "ran to its end"


signal.signal(signal.SIGALRM, on_timer)
runaway = re.compile(r"(a+)+$")
text = "a" * 28 + "b"
print("a match:", cut_short(lambda: runaway.match(text)), "|", cut_short(lambda: runaway.match(text), after=3), "|", cut_short(lambda: runaway.fullmatch(text)))
print("a search:", cut_short(lambda: re.search(r"(x+x+)+y", "x" * 32)), "|", cut_short(lambda: runaway.search(text), after=2))
print("the functions over a match:", cut_short(lambda: runaway.sub("-", text)), "|", cut_short(lambda: runaway.findall(text)), "|", cut_short(lambda: runaway.split(text)), "|",
      cut_short(lambda: list(runaway.finditer(text))), "|", cut_short(lambda: runaway.subn("-", text)))
print("bytes:", cut_short(lambda: re.match(rb"(a+)+$", b"a" * 28 + b"b")), "|", cut_short(lambda: re.search(rb"(x+x+)+y", bytearray(b"x" * 32))))
print("the pattern afterwards:", runaway.match("aaa") is not None, runaway.match("aab"), runaway.sub("-", "aaa b"), runaway.findall("b aa"), re.search(r"(x+x+)+y", "xxxy") is not None)

sys.set_int_max_str_digits(0)
big = (1 << 300_000_000) - 1
half = (1 << 150_000_000) + 12345
print("a product:", cut_short(lambda: big * big), "|", cut_short(lambda: big * half, after=2), "|", cut_short(lambda: big ** 2))
print("a quotient:", cut_short(lambda: big // half), "|", cut_short(lambda: big % half), "|", cut_short(lambda: divmod(big, half)))
print("a power:", cut_short(lambda: 3 ** 400_000_000), "|", cut_short(lambda: pow(3, 400_000_000)))
print("to decimal:", cut_short(lambda: str(1 << 30_000_000)), "|", cut_short(lambda: repr(big >> 250_000_000)), "|", cut_short(lambda: f"{big >> 250_000_000}"))
print("from decimal:", cut_short(lambda: int("7" * 9_000_000)))
print("the numbers afterwards:", big.bit_length(), half % 1000, (big >> 299_999_990) * 3, str(half)[:1] if False else "kept")
big = half = 0                           # the long ones are let go
signal.signal(signal.SIGALRM, signal.SIG_DFL)


# ---- a handler that is owed ----
log: list[str] = []
fails = False


def first(signum: int, frame: types.FrameType | None) -> None:
    raise Interrupted


def second(signum: int, frame: types.FrameType | None) -> None:
    log.append("the handler in " + "/".join(entry.name for entry in traceback.extract_stack()[:-1]))
    if fails:
        raise Second


def leave_one_owed() -> None:
    """Both signals arrive as they are let in. The call looks for them itself, the first handler raises, and the second
    signal stays noted where only the C's own check reads it."""
    signal.pthread_sigmask(signal.SIG_BLOCK, {U1, U2})
    os.kill(os.getpid(), U1)
    os.kill(os.getpid(), U2)
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {U1, U2})
    except Interrupted:
        pass


def owed(work: Callable[[], object], failing: bool = False) -> str:
    """What happens, in order, when `work` runs while a handler is owed."""
    global fails
    fails = failing
    log.clear()
    leave_one_owed()
    try:
        work()
        log.append("done")
        signal.pthread_sigmask(signal.SIG_BLOCK, ())     # a call that looks for itself: a handler still owed runs here
    except Second:
        log.append("Second came out")
    return ", ".join(log)


class Says:
    def __str__(self) -> str:
        log.append("__str__")
        return "said"

    def __repr__(self) -> str:
        log.append("__repr__")
        return "Says()"


class Formats(Says):
    def __format__(self, spec: str) -> str:
        log.append("__format__")
        return "formatted"


def nothing() -> None:
    return None


signal.signal(U1, first)
signal.signal(U2, second)
says = Says()
formats = Formats()
huge = 1 << 100
wide = (1 << 70) + 1
buffer = io.StringIO()
rows: list[tuple[str, Callable[[], object]]] = [
    ("str(obj)", lambda: str(says)),
    ("repr(obj)", lambda: repr(says)),
    ("ascii(obj)", lambda: ascii(says)),
    ("print(obj)", lambda: print(says, file=buffer)),
    ("print(a str)", lambda: print("text", file=buffer)),
    ("print(obj, obj)", lambda: print(says, says, sep="", end="", file=buffer)),
    ("%s", lambda: "%s" % (says,)),
    ("%r", lambda: "%r" % (says,)),
    ("%a", lambda: "%a" % (says,)),
    ("!s", lambda: f"{says!s}"),
    ("!r", lambda: f"{says!r}"),
    ("!a", lambda: f"{says!a}"),
    ("an f-string, object's __format__", lambda: f"{says}"),
    ("format(obj)", lambda: format(says)),
    ("str.format", lambda: "{}".format(says)),
    ("str.format !r", lambda: "{!r}".format(says)),
    ("str(int)", lambda: str(5)),
    ("repr(int)", lambda: repr(5)),
    ("str(str)", lambda: str("plain")),
    ("repr(str)", lambda: repr("plain")),
    ("str(None)", lambda: str(None)),
    ("str(float)", lambda: str(1.5)),
    ("repr(list)", lambda: repr([says])),
    ("str(dict)", lambda: str({1: says})),
    ("str(tuple)", lambda: str((says,))),
    ("str(set)", lambda: str({says})),
    ("map(str)", lambda: ", ".join(map(str, [1, 2]))),
    ("a comprehension", lambda: [str(v) for v in (1,)]),
    ("key=repr", lambda: sorted([3, 1], key=repr)),
    ("str(exception)", lambda: str(ValueError(says))),
    ("repr(exception)", lambda: repr(ValueError(says))),
    ("str.__call__", lambda: str.__call__(says)),
    ("a method on the text", lambda: str(says).upper()),
    ("obj.__str__()", lambda: says.__str__()),
    ("obj.__repr__()", lambda: says.__repr__()),
    ("object.__str__", lambda: object.__str__(says)),
    ("object.__repr__", lambda: object.__repr__(says)),
    ("a __format__ of its own", lambda: f"{formats}"),
    ("format() of an int", lambda: format(5)),
    ("an f-string of an int", lambda: f"{5}"),
    ("%d", lambda: "%d" % (5,)),
    ("%s of a str", lambda: "%s" % ("plain",)),
    ("str.join", lambda: ", ".join(["a", "b"])),
    ("len", lambda: len("abc")),
    ("int(text)", lambda: int("12")),
    ("a call", lambda: nothing()),
    ("a loop", lambda: [n for n in range(3)]),
    ("write", lambda: buffer.write("w")),
    ("print()", lambda: print(file=buffer)),
    # ints: the C looks in the loops over an int's digits. The rows have operands of 2**64 and more on both sides, or of one
    # digit: between the two CPython's digits (30 bits) and a compiled program's words (64) part ways (D-25 (e))
    ("the text of an int by its own method", lambda: (5).__str__()),
    ("the text of zero by its own method", lambda: (0).__str__()),
    ("%d of zero", lambda: "%d" % (0,)),
    ("a width", lambda: "%5d" % (5,)),
    ("format d", lambda: f"{5:d}"),
    ("format d of zero", lambda: f"{0:d}"),
    ("format x", lambda: f"{255:x}"),
    ("%x", lambda: "%x" % (255,)),
    ("hex", lambda: hex(255)),
    ("a product of two long ones", lambda: huge * wide),
    ("a product with zero", lambda: huge * 0),
    ("a square", lambda: huge * huge),
    ("a quotient of two long ones", lambda: huge // wide),
    ("a remainder of two long ones", lambda: huge % wide),
    ("divmod of two long ones", lambda: divmod(huge, wide)),
    ("a quotient by a short one", lambda: huge // 7),
    ("a remainder by a short one", lambda: huge % 7),
    ("a quotient by a longer one", lambda: wide // huge),
    ("a true quotient of two long ones", lambda: huge / wide),
    ("a true quotient by a short one", lambda: huge / 3),
    ("a power", lambda: huge ** 2),
    ("the power zero", lambda: huge ** 0),
    ("a small power", lambda: 3 ** 5),
    ("a longer power", lambda: huge ** 5),
    ("a power of a short one that grows long", lambda: 3 ** 100),
    ("a sum", lambda: huge + wide),
    ("a shift", lambda: huge << 5),
    ("a comparison", lambda: huge > wide),
    ("bits", lambda: huge & wide),
    ("the sign", lambda: -huge),
    ("a float", lambda: float(huge)),
    ("a hash", lambda: hash(huge)),
    ("int() of a hundred digits", lambda: int("9" * 100)),
    ("int() of hexadecimal digits", lambda: int("f" * 7000, 16)),
]
for label, work in rows:
    print(f"{label}: {owed(work)}")
for label, work in rows[:6]:
    print(f"{label}, a handler that raises: {owed(work, failing=True)}")
print("what was printed:", ascii(buffer.getvalue()))
signal.signal(U1, signal.SIG_DFL)
signal.signal(U2, signal.SIG_DFL)
