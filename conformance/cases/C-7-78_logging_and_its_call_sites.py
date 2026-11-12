# clause: C-7-78
# spec: section 7 (logging, [P1]: findCaller takes call-site information the compiler supplies), E-02
# status: P1
# source: Lib/logging/__init__.py (CPython 3.15.2: Logger.findCaller, _is_internal_frame, LogRecord, the three styles,
#         lastResort), manifest.toml [adaptations] and [replaced]
"""logging as a program uses it: each record names the call site (file, function, line, module) wherever the call is, in a
function, a method, a generator, a closure, a comprehension or the module's body, and the frame stacklevel asks for, past
logging's own; formatting in the three styles, levels, the hierarchy and propagation, a filter, an adapter, a record made
by hand, and the last-resort handler. Frames themselves stay out of reach (E-02): sys._getframe exists and is not called,
and neither stack_info nor exc_info is asked for, since both print source lines (D-06)."""
import logging
import sys
from collections.abc import Iterator

print("sys has _getframe:", hasattr(sys, "_getframe"))
logging.getLogger("early").warning("before any handler: the last resort, on standard error")

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format="%(levelname)s %(name)s %(module)s.%(funcName)s:%(lineno)d %(filename)s | %(message)s")
log = logging.getLogger("case")


def inner() -> None:
    log.info("in a function")


def wrapper(message: str) -> None:
    log.warning(message, stacklevel=2)


def deeper(message: str) -> None:
    wrapper(message)


class Service:
    def method(self) -> None:
        log.error("in a method, %d argument", 1)

    @staticmethod
    def static() -> None:
        log.critical("in a static method")


def generator() -> Iterator[int]:
    log.info("in a generator")
    yield 1


def outer() -> None:
    count = 2

    def closure() -> None:
        log.debug("in a closure over %d", count)
    closure()


inner()
wrapper("one level up, by stacklevel")
deeper("from deeper, one level up")
log.warning("as far up as there is", stacklevel=50)
Service().method()
Service.static()
for _ in generator():
    pass
outer()
[log.info("in a comprehension") for _ in range(1)]  # type: ignore[func-returns-value]
log.debug("in the module's body")
print("findCaller here:", logging.getLogger().findCaller()[1:3])

child = logging.getLogger("case.child")
child.setLevel(logging.WARNING)
child.info("not shown: below the child's level")
child.warning("shown through the parent's handler")
quiet = logging.getLogger("quiet")
quiet.propagate = False
quiet.error("no handler and no propagation: the last resort again")


class OnlyOdd(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return isinstance(record.args, tuple) and bool(record.args) and isinstance(record.args[0], int) and record.args[0] % 2 == 1


odd = logging.getLogger("odd")
odd.addFilter(OnlyOdd())
for n in range(3):
    odd.warning("number %d", n)

for style, fmt in (("%", "%(levelname)s/%(funcName)s/%(lineno)d: %(message)s"),
                   ("{", "{levelname}/{funcName}/{lineno}: {message}"),
                   ("$", "$levelname/$funcName/$lineno: $message")):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, style=style))  # type: ignore[arg-type]
    styled = logging.getLogger("style" + style)
    styled.propagate = False
    styled.addHandler(handler)
    styled.warning("a %s message", style)

adapter = logging.LoggerAdapter(log, {"user": "u1"})
adapter.warning("through an adapter")
record = log.makeRecord("case", logging.INFO, "made.py", 7, "made %s", ("by hand",), None, func="maker")
print("a record made by hand:", record.getMessage(), record.filename, record.funcName, record.lineno, record.module)
print("levels:", logging.getLevelName(logging.WARNING), logging.getLevelName(15), logging.getLevelName("ERROR"))
logging.shutdown()
