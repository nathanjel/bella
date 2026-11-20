# clause: C-8-17
# spec: section 8 (Environment), D-15
# status: P1
# source: Python/initconfig.c (config_init_stdio_encoding), Objects/unicodeobject.c (init_stdio_encoding, config_get_codec_name),
#         Python/pylifecycle.c (create_stdio, fatal_error, _Py_FatalError_PrintExc), Python/traceback.c (write_thread_id)
"""PYTHONIOENCODING, "encoding:errors" with either part left out, says how the three standard streams encode and decode:
an encoding alone makes the errors strict, the errors of standard error stay backslashreplace, and each stream gives the
name the codec has for itself. The program starts itself again under each value, with bytes to read, and prints the
bytes the second one wrote. A name that is no encoding ends the second one before its first line: status 1, what went
wrong and the thread it went wrong in on standard error."""
import os
import sys
import tempfile

SHOW = "BELLA_CASE_SHOW"


def show() -> None:
    out = sys.stdout
    out.write(f"{sys.stdin.encoding} {sys.stdin.errors} | {out.encoding} {out.errors} | {sys.stderr.encoding} {sys.stderr.errors}\n")
    for text in ("café", "€", "\udc80"):
        try:
            out.write(text + "\n")
        except UnicodeEncodeError as e:
            out.write(f"[{e.encoding} cannot]\n")
        except LookupError:
            out.write("[no such way with errors]\n")
    out.flush()
    sys.stderr.write("café € \udc80\n")
    try:
        out.write("read " + ascii(sys.stdin.readline()) + "\n")
    except UnicodeDecodeError as e:
        out.write(f"[{e.encoding} cannot read]\n")
    except LookupError:
        out.write("[no such way with errors]\n")


def again(given: str, **setting: str) -> None:
    """Start this program again with the given file as its standard input and both outputs in one pipe; print the bytes."""
    here, there = os.pipe()
    child = os.posix_spawn(sys.executable, sys.orig_argv, {"PYTHONHASHSEED": "0", SHOW: "yes"} | setting,
                           file_actions=[(os.POSIX_SPAWN_OPEN, 0, given, os.O_RDONLY, 0), (os.POSIX_SPAWN_DUP2, there, 1),
                                         (os.POSIX_SPAWN_DUP2, there, 2), (os.POSIX_SPAWN_CLOSE, here)])
    os.close(there)
    wrote = b""
    while chunk := os.read(here, 65536):
        wrote += chunk
    os.close(here)
    status = os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    thread = wrote.find(b"Current thread 0x")       # its number and its name are the process's own
    if thread >= 0:
        wrote = wrote[:thread] + b"Current thread (a number and a name)" + wrote[wrote.index(b" (most recent", thread):]
    print(", ".join(f"{name}={value!r}" for name, value in setting.items()) or "not set", "-> status", status)
    for line in wrote.split(b"\n")[:-1] if status else [wrote[at:at + 96] for at in range(0, len(wrote), 96)]:
        print("   ", line)


def main() -> None:
    folder = tempfile.mkdtemp()
    given = os.path.join(folder, "given")
    with open(given, "wb") as f:
        f.write(b"caf\xe9 \xc3\xa9\nmore\n")
    again(given)
    for value in ("utf-8", "UTF-8", "utf8", "U8", "utf_8:strict", "utf 8", "latin-1", "latin1:replace", "ISO-8859-1:xmlcharrefreplace",
                  "iso8859_1:ignore", "ascii", "us-ascii:backslashreplace", "646:surrogateescape", ":replace", ":", "utf-8:", ":strict",
                  "utf-8:surrogatepass", "utf-8-sig", "utf-16", "UTF-16LE:replace", "utf-32", "utf_32_be", "utf-8:no such way", "utf8:replace:strict",
                  "utf-8 ", ""):
        again(given, PYTHONIOENCODING=value)
    print("---- what is no encoding")
    for value in ("nonsense", "nonsense:replace", "utf-9", "latin-1,utf-8"):
        again(given, PYTHONIOENCODING=value)
    print("---- with the streams unbuffered")
    again(given, PYTHONIOENCODING="latin-1:replace", PYTHONUNBUFFERED="1")
    again(given, PYTHONIOENCODING="nonsense", PYTHONUNBUFFERED="1")
    os.remove(given)
    os.rmdir(folder)


if SHOW in os.environ:
    show()
else:
    main()
