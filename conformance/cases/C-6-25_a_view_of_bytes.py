# clause: C-6-25
# spec: section 6 (built-in types: memoryview)
# status: P1
# source: Objects/memoryobject.c (memoryview_impl, memory_item, memory_subscript, memoryview_tobytes_impl, memoryview_release_impl,
#         mbuf_release), Objects/bytearrayobject.c (bytearray_getbuffer, _canresize)
"""A memoryview of bytes or of a bytearray, as far as phase 1 has it: a one-dimensional view of octets. What it is made of
and what refuses; its length, items and slices, which are views of the same octets; what it says of itself; `tobytes`;
the places that take bytes-like data; `release` and the context manager, after which the view answers nothing; and the
hold it has on a bytearray, which cannot change its size while a view of it lives."""
import binascii
import hashlib
import io
import struct
import zlib
from collections.abc import Callable


class Octets(bytes):
    pass


def tried(make: Callable[[], object]) -> str:
    try:
        return repr(make())
    except (TypeError, ValueError, IndexError, BufferError) as error:
        return type(error).__name__


def says(m: memoryview) -> str:
    return " ".join([str(len(m)), m.format, str(m.ndim), str(m.itemsize), str(m.readonly)])


print("made of bytes:", says(memoryview(b"abcdef")), "| of a bytearray:", says(memoryview(bytearray(b"abc"))),
      "| of a class over bytes:", says(memoryview(Octets(b"ab"))), "| of a view:", says(memoryview(memoryview(b"abcd"))),
      "| of nothing:", says(memoryview(b"")))
print("refused:", tried(lambda: memoryview("text")), tried(lambda: memoryview(5)), tried(lambda: memoryview([1, 2])),  # type: ignore[arg-type]
      tried(lambda: memoryview(None)), tried(lambda: memoryview()), tried(lambda: memoryview(b"a", b"b")),  # type: ignore[arg-type, call-arg]
      "| by keyword:", says(memoryview(object=b"ab")))  # type: ignore[call-arg]

view = memoryview(b"abcdef")
print("items:", view[0], view[5], view[-1], view[-6], "| out of range:", tried(lambda: view[6]), tried(lambda: view[-7]),
      "| no index:", tried(lambda: view["a"]), tried(lambda: view[1.5]), "| type:", type(view[0]).__name__)  # type: ignore[call-overload]
print("slices:", view[1:3].tobytes(), view[:2].tobytes(), view[4:].tobytes(), view[::2].tobytes(), view[::-1].tobytes(),
      view[5:1:-2].tobytes(), view[10:].tobytes(), view[2:2].tobytes(), "| a slice is a view:", type(view[1:3]).__name__, says(view[1:3]))
print("slices of slices:", view[1:5][1:3].tobytes(), view[::2][1:].tobytes(), view[::-1][::2].tobytes(), view[1:5][-1],
      "| a step of nothing:", tried(lambda: view[::0]))
print("tobytes:", view.tobytes(), type(view.tobytes()).__name__, memoryview(bytearray(b"xy")).tobytes(),
      "| of a class over bytes:", type(memoryview(Octets(b"ab")).tobytes()).__name__)

taken = memoryview(b"\x01\x02\x03\x04")
out = io.BytesIO()
out.write(taken)
print("taken as bytes:", bytes(taken), bytearray(taken), b"-".join([taken, taken[:1]]), b"ab" + taken[:1], out.getvalue(),
      int.from_bytes(taken, "big"), struct.unpack("<HH", taken), binascii.hexlify(taken), zlib.crc32(taken),
      hashlib.sha256(taken).hexdigest()[:8], str(memoryview(b"text"), "ascii"), bytes(taken[::2]), bytes(taken[::-1]))

held = bytearray(b"abc")
over = memoryview(held)
print("a view of a bytearray:", says(over), over[0], "| the bytearray changed in place is seen:", end=" ")
held[0] = 120
print(over[0], over.tobytes(), over[:1].tobytes())
print("its size is held:", tried(lambda: held.append(1)), tried(lambda: held.extend(b"x")), tried(lambda: held.clear()),
      tried(lambda: held.pop()), tried(lambda: held.__delitem__(0)), tried(lambda: held.__iadd__(b"z")),
      tried(lambda: held.insert(0, 1)), "| what keeps the size goes on:", tried(lambda: held.reverse()), held)
part = over[1:]
over.release()
print("a slice holds it too:", tried(lambda: held.append(1)), "| until it is released:", end=" ")
part.release()
held.append(33)
print(held)
again = memoryview(held)
del again
held.append(34)
print("a view that is gone holds nothing:", held)
first = memoryview(held)
second = memoryview(first)
first.release()
print("a view of a view holds it:", tried(lambda: held.append(1)), end=" ")
second.release()
held.append(35)
print("| then:", held)

gone = memoryview(b"abc")
gone.release()
gone.release()
print("released:", tried(lambda: len(gone)), tried(lambda: gone[0]), tried(lambda: gone[:1]), tried(lambda: gone.tobytes()),
      tried(lambda: bytes(gone)), tried(lambda: gone.format), tried(lambda: gone.readonly), tried(lambda: memoryview(gone)))
with memoryview(bytearray(b"xyz")) as inside:
    print("in a with statement:", inside.tobytes(), says(inside), end=" ")
print("| after it:", tried(lambda: inside.tobytes()))
with memoryview(b"q") as kept:
    kept.release()
print("released inside the with:", tried(lambda: kept[0]))
