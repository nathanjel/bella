# clause: C-3-15
# spec: section 3
# status: P1
# source: TODO task 2 (generator close()/throw()); review rounds (generators are [P1])
"""send, throw and close on generators: a thrown exception is raised at the paused yield and may
be handled there; close raises GeneratorExit at the yield, runs finally blocks and returns the
generator's return value if it returns; a generator that yields after GeneratorExit makes close
raise RuntimeError; StopIteration carries the return value."""
from collections.abc import Generator


def worker(log: list[str]) -> Generator[int, str | None, str]:
    try:
        received = yield 1
        log.append(f"received {received!r}")
        yield 2
    except ValueError as exc:
        log.append(f"caught {exc.args}")
        yield 3
    finally:
        log.append("finally")
    return "done"


log: list[str] = []
g = worker(log)
print(next(g), g.send("hi"), g.throw(ValueError("boom")))
try:
    next(g)
except StopIteration as stop:
    print("stop value:", stop.value)
print("close after the end:", g.close(), log)


def closable(log: list[str]) -> Generator[int, None, str]:
    try:
        yield 1
    except GeneratorExit:
        log.append("GeneratorExit")
        return "returned on close"
    finally:
        log.append("finally")
    return "never"


log = []
c = closable(log)
next(c)
print("close returns:", c.close(), log)


def stubborn() -> Generator[int]:
    try:
        yield 1
    finally:
        yield 2


s = stubborn()
next(s)
try:
    s.close()
except RuntimeError as exc:
    print("stubborn close:", type(exc).__name__)

fresh = worker([])
try:
    fresh.throw(KeyError("early"))
except KeyError as exc:
    print("throw before start:", type(exc).__name__, exc.args)
print("fresh is finished:", next(fresh, "exhausted"))
