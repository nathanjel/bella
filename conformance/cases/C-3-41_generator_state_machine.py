# clause: C-3-41
# spec: section 3
# status: P1
# source: dialect specification section 3, Objects/genobject.c, Python/bytecodes.c
"""A generator's body resumed at every yield, whatever encloses it: each shape below is driven by next, send, throw, close
and dropping the last reference at each of its yields, and the log says which blocks ran, in which order, what each
exception's context is, and when what the frame holds dies."""
# ruff: noqa: ANN001, ANN002, ANN201, ANN202, B007, B012, B018, B023, B901, B904, C416, E722, F821, PLR0133, PLW0120, RET503, RUF015, S110, SIM105, SIM109, TRY002, TRY301, TRY302, UP028
import sys

log: list[str] = []


def note(*items):  # type: ignore[no-untyped-def]
    log.append(" ".join([str(i) for i in items]))


class Tracked:
    def __init__(self, name):  # type: ignore[no-untyped-def]
        self.name = name

    def __del__(self):  # type: ignore[no-untyped-def]
        note("dies", self.name)  # type: ignore[no-untyped-call]

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "Tracked(" + self.name + ")"


class E1(Exception):
    pass


class E2(Exception):
    pass


class Manager:
    def __init__(self, name, swallow=False):  # type: ignore[no-untyped-def]
        self.name = name
        self.swallow = swallow

    def __enter__(self):  # type: ignore[no-untyped-def]
        note("enter", self.name)  # type: ignore[no-untyped-call]
        return self.name

    def __exit__(self, t, v, tb):  # type: ignore[no-untyped-def]
        note("exit", self.name, t.__name__ if t is not None else None)  # type: ignore[no-untyped-call]
        return self.swallow


def plain():  # type: ignore[no-untyped-def]
    yield 1
    yield 2


def returns():  # type: ignore[no-untyped-def]
    yield 1
    return "value"


def returns_tuple():  # type: ignore[no-untyped-def]
    yield 1
    return (1, 2)


def locals_die():  # type: ignore[no-untyped-def]
    a = Tracked("a")  # type: ignore[no-untyped-call]
    yield a.name
    b = Tracked("b")  # type: ignore[no-untyped-call]
    yield b.name
    note("end", a.name, b.name)  # type: ignore[no-untyped-call]


def temp_across_yield():  # type: ignore[no-untyped-def]
    print_args = (Tracked("held"), (yield 1), (yield 2))  # type: ignore[no-untyped-call]
    note("made", len(print_args))  # type: ignore[no-untyped-call]
    yield 3


def in_call():  # type: ignore[no-untyped-def]
    note("sum", max((yield 1), (yield 2)))  # type: ignore[no-untyped-call]


def unpacks():  # type: ignore[no-untyped-def]
    a, b = yield 1
    note("a b", a, b)  # type: ignore[no-untyped-call]
    *c, d = yield 2
    note("c d", c, d)  # type: ignore[no-untyped-call]


def in_try_except():  # type: ignore[no-untyped-def]
    try:
        yield 1
        note("body")  # type: ignore[no-untyped-call]
    except E1 as e:
        note("caught", type(e).__name__, e.args)  # type: ignore[no-untyped-call]
        yield 2
        note("handler")  # type: ignore[no-untyped-call]
    note("after")  # type: ignore[no-untyped-call]
    yield 3


def in_try_except_no_name():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except E1:
        note("caught", sys.exc_info()[0].__name__)  # type: ignore[no-untyped-call,union-attr]
        yield 2
        note("still", sys.exc_info()[0].__name__)  # type: ignore[no-untyped-call,union-attr]
    note("after", sys.exc_info()[0])  # type: ignore[no-untyped-call]
    yield 3


def in_else():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except E1:
        note("caught")  # type: ignore[no-untyped-call]
    else:
        note("else")  # type: ignore[no-untyped-call]
        yield 2
        note("else end")  # type: ignore[no-untyped-call]
    yield 3


def in_finally():  # type: ignore[no-untyped-def]
    try:
        yield 1
        note("body")  # type: ignore[no-untyped-call]
    finally:
        note("finally")  # type: ignore[no-untyped-call]
        yield 2
        note("finally end")  # type: ignore[no-untyped-call]
    note("after")  # type: ignore[no-untyped-call]
    yield 3


def except_then_finally():  # type: ignore[no-untyped-def]
    try:
        try:
            yield 1
        except E1 as e:
            note("except", e.args)  # type: ignore[no-untyped-call]
            yield 2
            raise E2("from handler")
        finally:
            note("finally")  # type: ignore[no-untyped-call]
            yield 3
    except E2 as e:
        note("outer", e.args, type(e.__context__).__name__)  # type: ignore[no-untyped-call]
        yield 4
    yield 5


def nested_tries():  # type: ignore[no-untyped-def]
    try:
        try:
            try:
                yield 1
            except E2:
                note("inner never")  # type: ignore[no-untyped-call]
            yield 2
        finally:
            note("f1")  # type: ignore[no-untyped-call]
    except E1:
        note("e1")  # type: ignore[no-untyped-call]
        yield 3
    finally:
        note("f2")  # type: ignore[no-untyped-call]
    yield 4


def reraises():  # type: ignore[no-untyped-def]
    try:
        try:
            yield 1
        except E1:
            note("first")  # type: ignore[no-untyped-call]
            yield 2
            raise
    except E1 as e:
        note("again", e.args)  # type: ignore[no-untyped-call]
    yield 3


def new_in_handler():  # type: ignore[no-untyped-def]
    try:
        try:
            yield 1
        except E1:
            raise E2("new") from None
    except E2 as e:
        note("new", e.__cause__, e.__suppress_context__, type(e.__context__).__name__)  # type: ignore[no-untyped-call]
    yield 2


def return_in_try():  # type: ignore[no-untyped-def]
    try:
        yield 1
        return "from try"
    finally:
        note("finally")  # type: ignore[no-untyped-call]
        yield 2


def return_in_handler():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except E1 as e:
        note("handler", e.args)  # type: ignore[no-untyped-call]
        yield 2
        return "from handler"
    finally:
        note("finally")  # type: ignore[no-untyped-call]
    yield 3


def return_overridden():  # type: ignore[no-untyped-def]
    try:
        return "first"
    finally:
        yield 1
        note("still returning")  # type: ignore[no-untyped-call]


def loop_with_yield():  # type: ignore[no-untyped-def]
    for i in range(3):
        yield i
    else:
        note("else")  # type: ignore[no-untyped-call]
        yield "else"
    yield "end"


def while_else():  # type: ignore[no-untyped-def]
    i = 0
    while i < 2:
        yield i
        i += 1
    else:
        yield "else"


def break_through_finally():  # type: ignore[no-untyped-def]
    for i in range(3):
        try:
            yield i
            if i == 1:
                break
        finally:
            note("f", i)  # type: ignore[no-untyped-call]
            yield "f" + str(i)
    else:
        note("no break")  # type: ignore[no-untyped-call]
    yield "end"


def continue_through_finally():  # type: ignore[no-untyped-def]
    for i in range(3):
        try:
            if i == 1:
                continue
            yield i
        finally:
            note("f", i)  # type: ignore[no-untyped-call]
    yield "end"


def break_in_handler():  # type: ignore[no-untyped-def]
    for i in range(3):
        try:
            yield i
            raise E1(i)
        except E1 as e:
            note("h", e.args)  # type: ignore[no-untyped-call]
            yield "h"
            if i == 1:
                break
            continue
        finally:
            note("f", i)  # type: ignore[no-untyped-call]
    yield "end"


def nested_loops():  # type: ignore[no-untyped-def]
    for i in range(2):
        for j in range(2):
            yield i, j
            if j == 0:
                continue
            break
        else:
            note("inner else")  # type: ignore[no-untyped-call]
    yield "end"


def loop_iterator_dies():  # type: ignore[no-untyped-def]
    class It:
        def __iter__(self):  # type: ignore[no-untyped-def]
            return self

        def __next__(self):  # type: ignore[no-untyped-def]
            yield_count.append(1)
            if len(yield_count) > 2:
                raise StopIteration
            return len(yield_count)

        def __del__(self):  # type: ignore[no-untyped-def]
            note("iterator dies")  # type: ignore[no-untyped-call]

    yield_count = []
    for x in It():
        yield x
    note("loop done")  # type: ignore[no-untyped-call]
    yield "end"


def with_yield():  # type: ignore[no-untyped-def]
    with Manager("m") as n:  # type: ignore[no-untyped-call]
        yield n
        note("in with")  # type: ignore[no-untyped-call]
    note("out")  # type: ignore[no-untyped-call]
    yield "end"


def with_swallow():  # type: ignore[no-untyped-def]
    with Manager("s", True):  # type: ignore[no-untyped-call]
        yield 1
        raise E2("swallowed")
    note("swallowed")  # type: ignore[unreachable]
    yield 2


def two_withs():  # type: ignore[no-untyped-def]
    with Manager("a"), Manager("b"):  # type: ignore[no-untyped-call]
        yield 1
    yield 2


def with_return():  # type: ignore[no-untyped-def]
    with Manager("r"):  # type: ignore[no-untyped-call]
        yield 1
        return "out of with"


def delegate_inner():  # type: ignore[no-untyped-def]
    try:
        got = yield "inner 1"
        note("inner got", got)  # type: ignore[no-untyped-call]
        got = yield "inner 2"
        note("inner got", got)  # type: ignore[no-untyped-call]
    except E1 as e:
        note("inner caught", e.args)  # type: ignore[no-untyped-call]
        yield "inner handler"
    finally:
        note("inner finally")  # type: ignore[no-untyped-call]
    return "inner value"


def delegates():  # type: ignore[no-untyped-def]
    r = yield from delegate_inner()  # type: ignore[no-untyped-call]
    note("r", r)  # type: ignore[no-untyped-call]
    yield "after"


def delegates_twice():  # type: ignore[no-untyped-def]
    a = yield from plain()  # type: ignore[no-untyped-call]
    b = yield from returns()  # type: ignore[no-untyped-call]
    note("a b", a, b)  # type: ignore[no-untyped-call]


def delegates_list():  # type: ignore[no-untyped-def]
    r = yield from [1, 2]  # type: ignore[func-returns-value]
    note("r", r)  # type: ignore[no-untyped-call]


def delegates_in_try():  # type: ignore[no-untyped-def]
    try:
        yield from delegate_inner()  # type: ignore[no-untyped-call]
    except E2 as e:
        note("outer", e.args)  # type: ignore[no-untyped-call]
        yield "outer handler"
    finally:
        note("outer finally")  # type: ignore[no-untyped-call]


def delegates_range():  # type: ignore[no-untyped-def]
    yield from range(2)
    yield from "ab"
    yield from (1, 2)
    yield from {1: 2}


class Custom:
    def __init__(self, *items):  # type: ignore[no-untyped-def]
        self.items = list(items)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return self

    def __next__(self):  # type: ignore[no-untyped-def]
        note("next")  # type: ignore[no-untyped-call]
        if not self.items:
            raise StopIteration("custom value")
        return self.items.pop(0)

    def send(self, v):  # type: ignore[no-untyped-def]
        note("send", v)  # type: ignore[no-untyped-call]
        return self.__next__()  # type: ignore[no-untyped-call]

    def throw(self, e):  # type: ignore[no-untyped-def]
        note("throw", type(e).__name__ if not isinstance(e, type) else e.__name__)  # type: ignore[no-untyped-call]
        return "thrown back"

    def close(self):  # type: ignore[no-untyped-def]
        note("close")  # type: ignore[no-untyped-call]


class NoMethods:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.n = 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        return self

    def __next__(self):  # type: ignore[no-untyped-def]
        self.n += 1
        if self.n > 2:
            raise StopIteration
        return self.n


def delegates_custom():  # type: ignore[no-untyped-def]
    r = yield from Custom(1, 2)  # type: ignore[no-untyped-call]
    note("r", r)  # type: ignore[no-untyped-call]


def delegates_no_methods():  # type: ignore[no-untyped-def]
    r = yield from NoMethods()  # type: ignore[no-untyped-call]
    note("r", r)  # type: ignore[no-untyped-call]


def stop_iteration_in_body():  # type: ignore[no-untyped-def]
    yield 1
    raise StopIteration("inside")


def stop_iteration_caught():  # type: ignore[no-untyped-def]
    try:
        yield 1
        raise StopIteration("inside")
    except StopIteration as e:
        note("caught", e.args)  # type: ignore[no-untyped-call]
    yield 2


def generator_exit_caught():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except GeneratorExit:
        note("exit caught")  # type: ignore[no-untyped-call]
        raise
    finally:
        note("finally")  # type: ignore[no-untyped-call]


def generator_exit_ignored():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except GeneratorExit:
        note("ignoring")  # type: ignore[no-untyped-call]
        yield 2
    yield 3


def generator_exit_returns():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except GeneratorExit:
        return "closed value"


def generator_exit_replaced():  # type: ignore[no-untyped-def]
    try:
        yield 1
    except GeneratorExit:
        raise E2("instead")


def exception_context():  # type: ignore[no-untyped-def]
    try:
        raise E1("first")
    except E1:
        yield 1
        try:
            raise E2("second")
        except E2 as e:
            note("context", type(e.__context__).__name__)  # type: ignore[no-untyped-call]
            yield 2
    yield 3


def closure_cell():  # type: ignore[no-untyped-def]
    x = 1

    def read():  # type: ignore[no-untyped-def]
        return x

    yield read()  # type: ignore[no-untyped-call]
    x = 2
    yield read()  # type: ignore[no-untyped-call]


def arguments(a, b=2, *c, d=4, **e):  # type: ignore[no-untyped-def]
    yield a, b, c, d, e
    a = "changed"
    yield a


def in_conditional():  # type: ignore[no-untyped-def]
    x = yield 1
    if x:
        yield "true"
    else:
        yield "false"
    y = (yield 2) if x else (yield 3)
    note("y", y)  # type: ignore[no-untyped-call]
    z = x and (yield 4)
    note("z", z)  # type: ignore[no-untyped-call]
    w = x or (yield 5)
    note("w", w)  # type: ignore[no-untyped-call]


def comprehension_uses():  # type: ignore[no-untyped-def]
    yield [i for i in range(2)]
    yield {k: 1 for k in "a"}
    r = [(yield 1), (yield 2)]
    note("r", r)  # type: ignore[no-untyped-call]


def assert_and_delete():  # type: ignore[no-untyped-def]
    a = yield 1
    del a
    try:
        note(a)  # type: ignore[misc,no-untyped-call]
    except NameError:
        note("unbound")  # type: ignore[no-untyped-call]
    yield 2


def yields_nothing_ever():  # type: ignore[no-untyped-def]
    if False:
        yield  # type: ignore[unreachable]
    note("ran")  # type: ignore[no-untyped-call]
    return "nothing"


SHAPES = [plain, returns, returns_tuple, locals_die, temp_across_yield, in_call, unpacks, in_try_except, in_try_except_no_name, in_else, in_finally, except_then_finally, nested_tries, reraises, new_in_handler, return_in_try, return_in_handler, return_overridden, loop_with_yield, while_else, break_through_finally, continue_through_finally, break_in_handler, nested_loops, loop_iterator_dies, with_yield, with_swallow, two_withs, with_return, delegates, delegates_twice, delegates_list, delegates_in_try, delegates_range, delegates_custom, delegates_no_methods, stop_iteration_in_body, stop_iteration_caught, generator_exit_caught, generator_exit_ignored, generator_exit_returns, generator_exit_replaced, exception_context, closure_cell, arguments, in_conditional, comprehension_uses, assert_and_delete, yields_nothing_ever]


def outcome(f):  # type: ignore[no-untyped-def]
    try:
        return "value " + repr(f())
    except StopIteration as e:
        return "StopIteration " + repr(e.value) + " " + repr(e.args)
    except (E1, E2) as e:
        return type(e).__name__ + " " + repr(e.args) + " cause " + repr(e.__cause__) + " context " + type(e.__context__).__name__
    except BaseException as e:
        return type(e).__name__ + " context " + type(e.__context__).__name__ + " cause " + type(e.__cause__).__name__


def flush(title):  # type: ignore[no-untyped-def]
    print(title, log)
    log.clear()


def call(shape):  # type: ignore[no-untyped-def]
    return shape("a") if shape is arguments else shape()  # type: ignore[no-untyped-call]


def run_all(shape, send):  # type: ignore[no-untyped-def]
    g = call(shape)  # type: ignore[no-untyped-call]
    steps = []
    steps.append(outcome(lambda: next(g)))  # type: ignore[no-untyped-call]
    for i in range(40):
        if steps[-1].startswith(("StopIteration", "E1", "E2", "RuntimeError", "TypeError", "ValueError", "AttributeError")):
            break
        if send:
            steps.append(outcome(lambda: g.send((i, i + 1))))  # type: ignore[no-untyped-call]
        else:
            steps.append(outcome(lambda: next(g)))  # type: ignore[no-untyped-call]
    print(shape.__name__, "send" if send else "next", steps, g.gi_running, g.gi_suspended, g.gi_yieldfrom is None, g.gi_state)
    del g
    flush("  log")  # type: ignore[no-untyped-call]


def run_at(shape, k, act):  # type: ignore[no-untyped-def]
    g = call(shape)  # type: ignore[no-untyped-call]
    steps = []
    for i in range(k):
        steps.append(outcome(lambda: next(g)))  # type: ignore[no-untyped-call]
    if act == "close":
        steps.append(outcome(lambda: g.close()))  # type: ignore[no-untyped-call]
    elif act == "throw":
        steps.append(outcome(lambda: g.throw(E1("thrown"))))  # type: ignore[no-untyped-call]
    elif act == "throw class":
        steps.append(outcome(lambda: g.throw(E1)))  # type: ignore[no-untyped-call]
    elif act == "throw exit":
        steps.append(outcome(lambda: g.throw(GeneratorExit)))  # type: ignore[no-untyped-call]
    elif act == "throw stop":
        steps.append(outcome(lambda: g.throw(StopIteration("given"))))  # type: ignore[no-untyped-call]
    elif act == "throw handled":
        def inside():  # type: ignore[no-untyped-def]
            try:
                raise E2("handled by the caller")
            except E2:
                return g.throw(E1("thrown"))
        steps.append(outcome(inside))  # type: ignore[no-untyped-call]
    if act != "drop":
        for i in range(6):
            steps.append(outcome(lambda: next(g)))  # type: ignore[no-untyped-call]
            if steps[-1].startswith("StopIteration None ()") and i > 2:
                break
    else:
        steps.append("dropped")
    print(shape.__name__, k, act, steps, g.gi_state if act != "drop" else "")
    del g
    flush("  log")  # type: ignore[no-untyped-call]


# a close that fails when the last reference goes is reported on stderr, with the generator's address
FAILS_ON_DROP = (in_finally, except_then_finally, return_in_try, break_through_finally, with_swallow, generator_exit_ignored, generator_exit_replaced)
for shape in SHAPES:
    run_all(shape, False)  # type: ignore[no-untyped-call]
    run_all(shape, True)  # type: ignore[no-untyped-call]
    for k in range(0, 5):
        for act in ("close", "throw", "throw class", "throw exit", "throw stop", "throw handled", "drop"):
            if act != "drop" or shape not in FAILS_ON_DROP:
                run_at(shape, k, act)  # type: ignore[no-untyped-call]
