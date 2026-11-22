# clause: C-7-92
# spec: section 7 (struct)
# status: P1
# source: Modules/_struct.c (s_new, Struct_impl, s_init, Struct___init___impl, set_format, ENSURE_STRUCT_IS_READY)
"""How a Struct gets its format in 3.15: from `__new__`, or from `__init__` where a class has one of its own, with the
warnings that say which of the two ways will go. A Struct made without a format has no `format`, a size of -1, and methods
that raise RuntimeError; one initialised again with another format warns and takes it; a class over Struct works as Struct
does. Warnings are shown by their category."""
import struct
import warnings
from collections.abc import Callable


def tried(make: Callable[[], object]) -> str:
    """What the call gives, or the class of what it raises, and the categories of the warnings it gave."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = make()
            text = state(result) if isinstance(result, struct.Struct) else repr(result)
        except Exception as error:
            text = type(error).__name__
    return text + " " + str([type(w.message).__name__ for w in caught])


def strictly(make: Callable[[], object]) -> str:
    """The same with every warning an error."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            result = make()
            return state(result) if isinstance(result, struct.Struct) else repr(result)
        except Exception as error:
            return type(error).__name__
        except Warning as given:
            return type(given).__name__


def state(s: struct.Struct) -> str:
    out: list[str] = []
    try:
        out.append(s.format)
    except AttributeError:
        out.append("no format")
    out.append(str(s.size))
    for call in (lambda: s.pack(1), lambda: repr(s), lambda: s.unpack(b"\x01")):
        try:
            out.append(str(call()))
        except RuntimeError:
            out.append("RuntimeError")
        except struct.error:
            out.append("struct.error")
    return "<" + ", ".join(out) + ">"


class Plain(struct.Struct):
    pass


class WithInit(struct.Struct):
    def __init__(self, *args: object, **kwds: object) -> None:
        pass


class InitCalls(struct.Struct):
    def __init__(self, format: str = "b") -> None:
        super().__init__(format)


class WithNew(struct.Struct):
    def __new__(cls, *args: object, **kwds: object) -> WithNew:
        return super().__new__(cls, *args, **kwds)


class NewFixed(struct.Struct):
    def __new__(cls, *args: object, **kwds: object) -> NewFixed:
        return super().__new__(cls, "b")  # type: ignore[call-arg]


class Shadow(struct.Struct):
    size = 99
    format = "zz"


def again(s: struct.Struct, *args: object, **kwds: object) -> struct.Struct:
    s.__init__(*args, **kwds)  # type: ignore[misc]
    return s


def base_init(s: struct.Struct, *formats: str) -> struct.Struct:
    for format in formats:
        struct.Struct.__init__(s, format)
    return s


S = struct.Struct
print("Struct('b'):", tried(lambda: S("b")), "| format='b':", tried(lambda: S(format="b")), "| b'b':", tried(lambda: S(b"b")))
print("Struct():", tried(lambda: S()), "| two arguments:", tried(lambda: S("b", 1)),  # type: ignore[call-arg]
      "| another keyword:", tried(lambda: S(fmt="b")), "| a bad format:", tried(lambda: S("zz")), "| no str:", tried(lambda: S(1)))  # type: ignore[call-arg, arg-type]
print("__new__ alone:", tried(lambda: S.__new__(S)), "| with two:", tried(lambda: S.__new__(S, "b", 1)),  # type: ignore[call-arg]
      "| for a subclass:", tried(lambda: S.__new__(Plain, "b")), "| for one with __init__:", tried(lambda: S.__new__(WithInit)),  # type: ignore[call-arg]
      "| for int:", tried(lambda: S.__new__(int)))
print("then __init__:", tried(lambda: again(S.__new__(S), "b")))
print("__init__ again, the same format:", tried(lambda: again(S("b"), "b")), "| as bytes:", tried(lambda: again(S("b"), b"b")),
      "| by keyword:", tried(lambda: again(S("b"), format="b")))
print("__init__ again, another format:", tried(lambda: again(S("b"), "h")), "| and back:", tried(lambda: again(again(S("b"), "h"), "b")),
      "| a bad one:", tried(lambda: again(S("b"), "zz")), "| no str:", tried(lambda: again(S("b"), 1)),
      "| nothing:", tried(lambda: again(S("b"))), "| two:", tried(lambda: again(S("b"), "b", 1)))
kept = S("b")
print("a bad format leaves the Struct as it was:", tried(lambda: again(kept, "zz")), state(kept))
print("a class over Struct:", tried(lambda: Plain("b")), "| without a format:", tried(lambda: Plain()),  # type: ignore[call-arg]
      "| initialised again:", tried(lambda: again(Plain("b"), "h")))
print("with an __init__ of its own:", tried(lambda: WithInit("b")), "| without a format:", tried(lambda: WithInit()),
      "| two arguments:", tried(lambda: WithInit("b", 1)), "| a bad format:", tried(lambda: WithInit("zz")), "| no str:", tried(lambda: WithInit(1)))
print("its __init__ gives the format:", tried(lambda: InitCalls()), "| the same as __new__'s:", tried(lambda: InitCalls("h")),
      "| another than __new__'s:", tried(lambda: base_init(WithInit("b"), "h")), "| the same twice:", tried(lambda: base_init(WithInit("b"), "b", "b")))
print("with a __new__ of its own:", tried(lambda: WithNew("b")), "| by keyword:", tried(lambda: WithNew(format="b")),
      "| without a format:", tried(lambda: WithNew()), "| two arguments:", tried(lambda: WithNew("b", 1)),
      "| one that fixes the format:", tried(lambda: NewFixed("h")), tried(lambda: NewFixed()))

bare = S.__new__(S)
print("without a format | unpack:", tried(lambda: bare.unpack(5)), tried(lambda: bare.unpack(b"x")),  # type: ignore[arg-type]
      "| unpack_from:", tried(lambda: bare.unpack_from(b"x", "a")), tried(lambda: bare.unpack_from(b"x")),  # type: ignore[arg-type]
      "| pack_into:", tried(lambda: bare.pack_into(5, 0)), tried(lambda: bare.pack_into(bytearray(1), 0, 1)),  # type: ignore[arg-type]
      "| iter_unpack:", tried(lambda: bare.iter_unpack(5)), "| pack:", tried(lambda: bare.pack()),  # type: ignore[arg-type]
      "| __sizeof__:", tried(lambda: bare.__sizeof__()))

shadow = Shadow("b")
print("names a class has over the fields:", shadow.pack(1), shadow.unpack(b"\x01"), shadow.size, shadow.format, repr(shadow))
print("with warnings as errors:", strictly(lambda: WithInit()), strictly(lambda: WithInit("zz")), strictly(lambda: WithInit("b", 1)),
      strictly(lambda: again(S("b"), "h")), strictly(lambda: Plain("b")), strictly(lambda: InitCalls("h")))
print("the module's functions:", struct.pack("b", 1), struct.unpack("b", b"\x01"), struct.calcsize("h"))
