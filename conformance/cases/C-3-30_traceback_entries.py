# clause: C-3-30
# spec: section 3 (exceptions), section 8 (an uncaught exception's report), D-06
# status: P1
# source: review log RL-221, RL-223, RL-224, RL-226 (found while writing examples)
"""The frames a traceback lists, and at which lines: a frame is recorded where the exception
arrives in it (a raise, or a call that failed), never where it leaves; the frame's own
re-raises (the end of a finally, a bare raise) add nothing, `raise e` adds an entry, and a bare
raise in a function called from a handler lists the handler's frame twice. A C function
(list.__repr__) and an inlined comprehension (PEP 709) have no frame. The report prints the
chain: the context, then the cause, each with its traceback."""


class Loud:
    def __repr__(self) -> str:
        raise KeyError("repr")


def through_finally() -> None:
    try:
        repr([Loud()])                  # recorded here, not at the finally's last line
    finally:
        done = True
        print("finally ran:", done)


def bare_reraise() -> None:
    try:
        through_finally()
    except KeyError:
        note = "handled"
        print("bare_reraise:", note)
        raise                           # adds nothing: the entry stays at the call


def reraise_in_callee() -> None:
    raise                               # re-raises the caller's exception; no entry here


def raise_e() -> None:
    try:
        bare_reraise()
    except KeyError as e:
        try:
            reraise_in_callee()         # the caller's frame is recorded again, at this call
        except KeyError:
            raise e  # noqa: B904 -- the same object again: one more entry, nothing chained


def comprehension(values: tuple[int, ...]) -> list[int]:
    return [10 // v for v in values]    # no frame of its own


try:
    raise_e()
except KeyError:
    try:
        comprehension((1, 0))
    except ZeroDivisionError as z:
        raise RuntimeError("end") from z
