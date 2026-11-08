"""binascii, in Python (Modules/binascii.c): base64 both ways with 3.15's parameters (padded, wrapcol, newline, alphabet; strict_mode,
ignorechars, canonical), hex both ways, crc32, the two exceptions and the alphabets, each the C's rules and messages. uu, quoted-printable,
crc_hqx, base32, ascii85 and base85 stop by name until a target needs them. The converters are the clinic's: an `ascii_buffer` takes an
ASCII str or a bytes-like object, a `Py_buffer` a bytes-like object only."""

__all__ = ["ASCII85_ALPHABET", "BASE32HEX_ALPHABET", "BASE32_ALPHABET", "BASE64_ALPHABET", "BASE85_ALPHABET", "BINHEX_ALPHABET",
           "CRYPT_ALPHABET", "Error", "Incomplete", "URLSAFE_BASE64_ALPHABET", "UU_ALPHABET", "Z85_ALPHABET", "a2b_ascii85", "a2b_base32",
           "a2b_base64", "a2b_base85", "a2b_hex", "a2b_qp", "a2b_uu", "b2a_ascii85", "b2a_base32", "b2a_base64", "b2a_base85", "b2a_hex",
           "b2a_qp", "b2a_uu", "crc32", "crc_hqx", "hexlify", "unhexlify"]

__name__ = "binascii"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__


ASCII85_ALPHABET = b'!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstu'
BASE32HEX_ALPHABET = b"0123456789ABCDEFGHIJKLMNOPQRSTUV"
BASE32_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
BASE85_ALPHABET = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
BINHEX_ALPHABET = b'!"#$%&\'()*+,-012345689@ABCDEFGHIJKLMNPQRSTUVXYZ[`abcdefhijklmpqr'
CRYPT_ALPHABET = b"./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
URLSAFE_BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
UU_ALPHABET = b' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_'
Z85_ALPHABET = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#"


class Error(ValueError):                         # PyErr_NewException("binascii.Error", PyExc_ValueError, NULL)
    pass


class Incomplete(Exception):                     # PyErr_NewException("binascii.Incomplete", NULL, NULL)
    pass


Error.__module__ = "binascii"
Incomplete.__module__ = "binascii"


# ---- the clinic's converters ----------------------------------------------------------------------------------------------

def _is_bytes_like(value: object) -> bool:
    if issubclass(type(value), (bytes, bytearray)):
        return True
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    return False


def _buffer(value: object) -> bytes:             # Py_buffer: PyObject_GetBuffer, read-only
    if not _is_bytes_like(value):
        raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")
    return bytes(value)  # type: ignore[arg-type]


def _ascii_buffer(value: object) -> bytes:       # ascii_buffer_converter
    if issubclass(type(value), str):
        if not str.isascii(value):  # type: ignore[arg-type]
            raise ValueError("string argument should contain only ASCII characters")
        return str.encode(value, "ascii")  # type: ignore[arg-type]
    if not _is_bytes_like(value):
        raise TypeError("argument should be bytes, buffer or ASCII string, not '" + _tp_name(value) + "'")
    return bytes(value)  # type: ignore[arg-type]


def _bytes_arg(function: str, name: str, value: object) -> bytes:   # PyBytesObject: bytes or a subclass
    if not issubclass(type(value), bytes):
        raise TypeError(function + "() argument '" + name + "' must be bytes, not " + _tp_name(value))
    return value  # type: ignore[return-value]


def _index(value: object) -> int:                # PyNumber_Index
    if issubclass(type(value), int):
        return int.__index__(value)  # type: ignore[arg-type]
    index = getattr(type(value), "__index__", None)
    if index is None:
        raise TypeError("'" + _tp_name(value) + "' object cannot be interpreted as an integer")
    result = index(value)
    if not issubclass(type(result), int):
        raise TypeError("__index__ returned non-int (type " + _tp_name(result) + ")")
    return int.__index__(result)


def _ssize(value: object) -> int:                # the clinic's Py_ssize_t converter
    n = _index(value)
    if n < -(2**63) or n >= 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return n


def _size_t(value: object) -> int:               # the clinic's size_t: PyLong_AsNativeBytes, unsigned
    n = _index(value)
    if n < 0:
        raise ValueError("Cannot convert negative int")
    if n >= 2**64:
        raise OverflowError("Python int too large for C size_t")
    return n


def _unsigned_int_mask(value: object) -> int:    # unsigned_int(bitwise=True): PyLong_AsUnsignedLongMask, then the C's unsigned int
    n = _index(value)
    if n < 0 or n >= 2**32:                      # 3.15 masks it and warns (DeprecationWarning "integer value out of range"); not written
        _bella_refuse("binascii.crc32() with a crc outside the unsigned 32-bit range (3.15 masks it with a DeprecationWarning)")
    return n


_ABSENT: object = object()


def _unpack(name: str, args: tuple[object, ...], kwds: dict[str, object], posonly: int, names: tuple[str, ...]) -> list[object]:
    """_PyArg_UnpackKeywords for a function of `posonly` required positional-only parameters followed by keyword-only ones (`names`):
    the values, _ABSENT for a keyword not given."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = posonly + len(names)
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs != posonly:
        raise TypeError(name + "() takes exactly " + str(posonly) + " positional argument" + ("" if posonly == 1 else "s") + " (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * len(names)]
    for keyword, value in kwds.items():
        if keyword not in names:                 # error_unexpected_keyword
            suggestion = _keyword_suggestion(names, keyword)
            if suggestion is not None:
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
            raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
        out[posonly + names.index(keyword)] = value
    return out


def _unpack_positional_or_keyword(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int) -> list[object]:
    """_PyArg_UnpackKeywords with no positional-only parameters (b2a_hex, hexlify)."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = len(names)
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + " positional arguments (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * (maxargs - nargs)]
    if nkw:
        for i in range(nargs):
            if names[i] in kwds:
                raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
    left = nkw
    i = nargs
    while i < maxargs:
        if not left and i >= minpos:
            break
        if left and names[i] in kwds:
            out[i] = kwds[names[i]]
            left -= 1
        elif i < minpos:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        i += 1
    if left > 0:                                 # error_unexpected_keyword
        for keyword in kwds:
            if keyword not in names:
                suggestion = _keyword_suggestion(names, keyword)
                if suggestion is not None:
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # METH_FASTCALL, _PyArg_CheckPositional
    if kwds:
        raise TypeError("binascii." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


# ---- base64 (binascii_a2b_base64_impl, binascii_b2a_base64_impl) ----------------------------------------------------------

_BASE64_PAD = 61                                 # '='
_reverse_tables: dict[bytes, bytes] = {}        # the state's reverse_table_cache


def _reverse_table(alphabet: bytes, size: int, padchar: int) -> bytes:   # get_reverse_table
    if len(alphabet) != size:
        raise ValueError("alphabet must have length " + str(size))
    table = _reverse_tables.get(alphabet)
    if table is None:
        out = bytearray(b"\xff" * 256)
        for i in range(size):
            out[alphabet[i]] = i
        if padchar >= 0:
            out[padchar] = size
        table = bytes(out)
        _reverse_tables[alphabet] = table
    return table


_TABLE_A2B_BASE64 = _reverse_table(BASE64_ALPHABET, 64, _BASE64_PAD)


def a2b_base64(*args: object, **kwds: object) -> bytes:
    """Decode a line of base64 data.

  strict_mode
    When set to true, bytes that are not part of the base64 standard are
    not allowed.  The same applies to excess data after padding (= / ==).
    Set to True by default if ignorechars is specified, False otherwise.
  padded
    When set to false, padding in input is not required.
  ignorechars
    A byte string containing characters to ignore from the input when
    strict_mode is true.
  canonical
    When set to true, reject non-zero padding bits per RFC 4648 section 3.5."""
    data, strict_mode, padded, alphabet, ignorechars, canonical = _unpack("a2b_base64", args, kwds, 1, ("strict_mode", "padded", "alphabet", "ignorechars", "canonical"))
    ascii_data = _ascii_buffer(data)
    strict = bool(strict_mode) if strict_mode is not _ABSENT else -1
    is_padded = True if padded is _ABSENT else bool(padded)
    is_canonical = False if canonical is _ABSENT else bool(canonical)
    ignore: bytes | None = None if ignorechars is _ABSENT else _buffer(ignorechars)
    if strict == -1:
        strict = ignore is not None
    if not strict or ignore is None or len(ignore) == 0:
        ignore = None
    table = _TABLE_A2B_BASE64 if alphabet is _ABSENT else _reverse_table(_bytes_arg("a2b_base64", "alphabet", alphabet), 64, _BASE64_PAD)

    def ignored(c: int) -> bool:                 # ignorechar
        return ignore is not None and c in ignore

    out = bytearray()
    quad_pos = 0
    leftchar = 0
    pads = 0
    for this_ch in ascii_data:
        if is_padded and this_ch == _BASE64_PAD:
            pads += 1
            if quad_pos >= 2 and quad_pos + pads <= 4:
                continue
            # RFC 4648, section 3.3: a pad before the end may be ignored, and so may excess pads
            if not strict or ignored(_BASE64_PAD):
                continue
            if quad_pos == 1:
                break                            # the error below
            raise Error("Leading padding not allowed" if quad_pos == 0 and len(out) == 0 else "Excess padding not allowed")
        v = table[this_ch]
        if v >= 64:
            if strict and not ignored(this_ch):
                raise Error("Padding not allowed" if this_ch == _BASE64_PAD else "Only base64 data is allowed")
            continue
        # data in the middle of the padding (RFC 4648, section 3.3)
        if pads and strict and not ignored(_BASE64_PAD):
            raise Error("Excess data after padding" if quad_pos + pads == 4 else "Discontinuous padding not allowed")
        pads = 0
        if quad_pos == 0:
            quad_pos = 1
            leftchar = v
        elif quad_pos == 1:
            quad_pos = 2
            out.append(((leftchar << 2) | (v >> 4)) & 0xFF)
            leftchar = v & 0x0F
        elif quad_pos == 2:
            quad_pos = 3
            out.append(((leftchar << 4) | (v >> 2)) & 0xFF)
            leftchar = v & 0x03
        else:
            quad_pos = 0
            out.append(((leftchar << 6) | v) & 0xFF)
            leftchar = 0
    if quad_pos == 1:
        # one valid, non-padding character over: no input encodes to that length
        raise Error("Invalid base64-encoded string: number of data characters (" + str(len(out) // 3 * 4 + 1)
                    + ") cannot be 1 more than a multiple of 4")
    if is_padded and quad_pos != 0 and quad_pos + pads < 4:
        raise Error("Incorrect padding")
    if is_canonical and leftchar != 0:           # RFC 4648, section 3.5
        raise Error("Non-zero padding bits")
    return bytes(out)


def _wraplines(data: bytearray, width: int) -> bytearray:   # wraplines: '\n' every width characters
    if len(data) <= width:
        return data
    out = bytearray()
    for start in range(0, len(data), width):
        if start:
            out.append(10)
        out += data[start:start + width]
    return out


def b2a_base64(*args: object, **kwds: object) -> bytes:
    """Base64-code line of data.

  padded
    When set to false, omit padding in the output."""
    data, padded, wrapcol, newline, alphabet = _unpack("b2a_base64", args, kwds, 1, ("padded", "wrapcol", "newline", "alphabet"))
    bin_data = _buffer(data)
    is_padded = True if padded is _ABSENT else bool(padded)
    width = 0 if wrapcol is _ABSENT else _size_t(wrapcol)
    add_newline = True if newline is _ABSENT else bool(newline)
    table = BASE64_ALPHABET if alphabet is _ABSENT else _buffer(alphabet)
    if len(table) != 64:
        raise ValueError("alphabet must have length 64")
    bin_len = len(bin_data)
    out_len = (bin_len + 2) // 3 * 4
    pads = (3 - (bin_len % 3)) % 3 * 4 // 3
    if not is_padded:
        out_len -= pads
        pads = 0
    if width and out_len:
        width = 4 if width < 4 else width // 4 * 4   # each line a whole number of bytes
        out_len += (out_len - 1) // width
    if add_newline:
        out_len += 1
    if out_len > 2**63 - 1:
        raise Error("Too much data for base64")
    out = bytearray()
    i = 0
    while i + 3 <= bin_len:
        combined = (bin_data[i] << 16) | (bin_data[i + 1] << 8) | bin_data[i + 2]
        out.append(table[(combined >> 18) & 0x3F])
        out.append(table[(combined >> 12) & 0x3F])
        out.append(table[(combined >> 6) & 0x3F])
        out.append(table[combined & 0x3F])
        i += 3
    rest = bin_len - i
    if rest == 1:
        val = bin_data[i]
        out.append(table[(val >> 2) & 0x3F])
        out.append(table[(val << 4) & 0x3F])
    elif rest == 2:
        val = (bin_data[i] << 8) | bin_data[i + 1]
        out.append(table[(val >> 10) & 0x3F])
        out.append(table[(val >> 4) & 0x3F])
        out.append(table[(val << 2) & 0x3F])
    for _ in range(pads):
        out.append(_BASE64_PAD)
    if width:
        out = _wraplines(out, width)
    if add_newline:
        out.append(10)                           # a courtesy newline
    return bytes(out)


# ---- crc32 (internal_crc32, or zlib's: the same answer) --------------------------------------------------------------------

def _crc32_table() -> list[int]:
    table: list[int] = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if c & 1 else c >> 1
        table.append(c)
    return table


_CRC32_TAB = _crc32_table()


def crc32(*args: object, **kwds: object) -> int:
    """Compute CRC-32 incrementally."""
    _positional("crc32", args, kwds, 1, 2)
    bin_data = _buffer(args[0])
    value = (_unsigned_int_mask(args[1]) if len(args) > 1 else 0) ^ 0xFFFFFFFF
    for b in bin_data:
        value = _CRC32_TAB[(value ^ b) & 0xFF] ^ (value >> 8)
    return value ^ 0xFFFFFFFF


# ---- hex (binascii_b2a_hex_impl: _Py_strhex_bytes_with_sep, the method's; binascii_a2b_hex_impl) -----------------------------

def b2a_hex(*args: object, **kwds: object) -> bytes:
    """Hexadecimal representation of binary data.

The return value is a bytes object.  This function is also
available as "hexlify()".

Example:
>>> binascii.b2a_hex(b'\\xb9\\x01\\xef')
b'b901ef'
>>> binascii.hexlify(b'\\xb9\\x01\\xef', ':')
b'b9:01:ef'
>>> binascii.b2a_hex(b'\\xb9\\x01\\xef', b'_', 2)
b'b9_01ef'"""
    return _strhex("b2a_hex", args, kwds)


def hexlify(*args: object, **kwds: object) -> bytes:
    """Hexadecimal representation of binary data.

The return value is a bytes object.  This function is also
available as "b2a_hex()"."""
    return _strhex("hexlify", args, kwds)


_HEXDIGITS = b"0123456789abcdef"


def _strhex(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> bytes:
    """_Py_strhex_bytes_with_sep (Python/pystrhex.c): bytes.hex's rules, but a one-character str separator may be any Latin-1
    character when the answer is bytes."""
    data, sep, bytes_per_sep = _unpack_positional_or_keyword(name, args, kwds, ("data", "sep", "bytes_per_sep"), 1)
    bin_data = _buffer(data)
    group = 1 if bytes_per_sep is _ABSENT else _ssize(bytes_per_sep)
    sep_char = 0
    if sep is _ABSENT:
        group = 0
    else:
        if len(sep) != 1:  # type: ignore[arg-type]   # PyObject_Length, then the test
            raise ValueError("sep must be length 1.")
        if issubclass(type(sep), str):
            sep_char = ord(sep)  # type: ignore[arg-type]
            if sep_char > 255:
                raise ValueError("sep must be ASCII.")
        elif issubclass(type(sep), bytes):
            sep_char = sep[0]  # type: ignore[index]
        else:
            raise TypeError("sep must be str or bytes.")
    arglen = len(bin_data)
    if abs(group) >= arglen:
        group = 0
    out = bytearray()
    if group == 0:
        for c in bin_data:
            out.append(_HEXDIGITS[c >> 4])
            out.append(_HEXDIGITS[c & 0x0F])
        return bytes(out)
    width = abs(group)
    chunks = (arglen - 1) // width
    if group < 0:                                # counted from the left
        i = 0
        for _ in range(chunks):
            for _ in range(width):
                c = bin_data[i]
                i += 1
                out.append(_HEXDIGITS[c >> 4])
                out.append(_HEXDIGITS[c & 0x0F])
            out.append(sep_char)
        while i < arglen:
            c = bin_data[i]
            i += 1
            out.append(_HEXDIGITS[c >> 4])
            out.append(_HEXDIGITS[c & 0x0F])
        return bytes(out)
    head = arglen - chunks * width                # counted from the right: the short group first
    i = 0
    while i < head:
        c = bin_data[i]
        i += 1
        out.append(_HEXDIGITS[c >> 4])
        out.append(_HEXDIGITS[c & 0x0F])
    for _ in range(chunks):
        out.append(sep_char)
        for _ in range(width):
            c = bin_data[i]
            i += 1
            out.append(_HEXDIGITS[c >> 4])
            out.append(_HEXDIGITS[c & 0x0F])
    return bytes(out)


_HEX_DIGITS = {c: v for v, c in enumerate(b"0123456789abcdef")} | {c: v for v, c in enumerate(b"0123456789ABCDEF")}   # _PyLong_DigitValue < 16


def a2b_hex(*args: object, **kwds: object) -> bytes:
    """Binary data of hexadecimal representation.

hexstr must contain an even number of hex digits (upper or lower case).
This function is also available as "unhexlify()"."""
    return _a2b_hex("a2b_hex", args, kwds)


def unhexlify(*args: object, **kwds: object) -> bytes:
    """Binary data of hexadecimal representation.

hexstr must contain an even number of hex digits (upper or lower case)."""
    return _a2b_hex("unhexlify", args, kwds)


def _a2b_hex(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> bytes:   # binascii_a2b_hex_impl
    hexstr, ignorechars = _unpack(name, args, kwds, 1, ("ignorechars",))
    ascii_data = _ascii_buffer(hexstr)
    ignore: bytes | None = b"" if ignorechars is _ABSENT else _buffer(ignorechars)
    if len(ignore) == 0:  # type: ignore[arg-type]
        ignore = None
    out = bytearray()
    pair_pos = 0
    leftchar = 0
    for this_ch in ascii_data:
        digit = _HEX_DIGITS.get(this_ch, 37)
        if digit >= 16:
            if ignore is None or this_ch not in ignore:   # RFC 4648, section 3.3
                raise Error("Non-hexadecimal digit found")
            continue
        if not pair_pos:
            pair_pos = 1
            leftchar = digit
        else:
            pair_pos = 0
            out.append((leftchar << 4) | digit)
    if pair_pos:
        raise Error("Odd number of hexadecimal digits")
    return bytes(out)


# ---- the rest, by name ------------------------------------------------------------------------------------------------------

def _unwritten(name: str) -> object:
    def unwritten(*args: object, **kwds: object) -> None:
        _bella_refuse("binascii." + name)
    unwritten.__name__ = unwritten.__qualname__ = name
    return unwritten


a2b_uu = _unwritten("a2b_uu")
b2a_uu = _unwritten("b2a_uu")
a2b_qp = _unwritten("a2b_qp")
b2a_qp = _unwritten("b2a_qp")
crc_hqx = _unwritten("crc_hqx")
a2b_base32 = _unwritten("a2b_base32")
b2a_base32 = _unwritten("b2a_base32")
a2b_ascii85 = _unwritten("a2b_ascii85")
b2a_ascii85 = _unwritten("b2a_ascii85")
a2b_base85 = _unwritten("a2b_base85")
b2a_base85 = _unwritten("b2a_base85")
