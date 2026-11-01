# clause: C-7-03
# spec: section 7
# status: P1
# deviation: D-20
# source: review log D-6 and RL-57 (deviation D-20: what the phase-1 omissions make observable)
"""What phase 1 omits shows here, and only here: hashlib without OpenSSL, shutil without bz2,
lzma and zstd, and codec lookup outside the phase-1 codecs. CPython's trace is the reference;
the compiled program must match the trace recorded under the D-20 simulation."""
import codecs
import hashlib
import shutil

print("pbkdf2_hmac:", hasattr(hashlib, "pbkdf2_hmac"), "| scrypt:", hasattr(hashlib, "scrypt"))
print("beyond the guaranteed set:", sorted(hashlib.algorithms_available - hashlib.algorithms_guaranteed))
print("archive formats:", [name for name, _ in shutil.get_archive_formats()])
for name in ("utf-8", "latin1", "ascii", "utf-16-le", "utf_32", "utf-8-sig", "cp1252", "koi8_r", "shift_jis"):
    try:
        print(name, "->", codecs.lookup(name).name)
    except LookupError as exc:
        print(name, "->", type(exc).__name__)
