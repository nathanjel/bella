"""The functions of re._compiler (CPython 3.15.2, Lib/re/_compiler.py) that its adaptation replaces (manifest.toml
[adaptations] and [replaced]): each def stands for the one of the same qualified name, whose signature it repeats; the
frontend puts its body there (pipeline/l1/frontend.py, replace_functions).

_bytes_to_codes reads a charset's bitmap as the engine's code words, which CPython does through memoryview(b).cast('I'),
a [P2+] facility (spec section 3); the same words come from the bytes themselves, CODESIZE each, in the order of the
platform, which is little-endian on every target (manifest.toml [platform]). The list is the same, so the compiled
pattern is."""


def _bytes_to_codes(b):  # type: ignore[no-untyped-def]
    size = _sre.CODESIZE  # type: ignore[name-defined]  # noqa: F821
    assert len(b) % size == 0
    return [int.from_bytes(b[i:i + size], "little") for i in range(0, len(b), size)]
