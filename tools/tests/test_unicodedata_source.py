"""The copied Unicode databases (runtime/src/unicode*_db.inc; tools/unicodedata_source.py) are the pin's: each file's first
line names the reference release of manifest.toml, the second the Unicode version the database itself defines, and the
prelude reads that version and the names' longest length from the copied text, through the runtime, with no copy of its own.
The files' contents against the release need the release archive, which the repository does not hold: the tool's --check.

Run under pytest or directly: python3 tools/tests/test_unicodedata_source.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.unicodedata_source import FILES, defined, pinned  # noqa: E402

SRC = ROOT / "runtime" / "src"


def test_the_copies_name_the_pin_and_their_own_unicode_version() -> None:
    unidata = defined((SRC / "unicodedata_db.inc").read_text(encoding="utf-8"), "UNIDATA_VERSION")
    for header, name, _ in FILES:
        first, second = (SRC / name).read_text(encoding="utf-8").split("\n", 2)[:2]
        assert first.startswith(f"// CPython {pinned()}'s {header}, whole"), (name, first)
        assert f"from Unicode {unidata}'s data files" in second, (name, second)


def test_the_prelude_keeps_no_copy_of_the_databases_constants() -> None:
    prelude = (ROOT / "runtime" / "prelude" / "unicodedata.py").read_text(encoding="utf-8")
    assert re.search(r'^unidata_version = _ucd_call\("unidata_version"\)', prelude, re.MULTILINE)
    assert re.search(r'^_NAME_MAXLEN = _ucd_call\("name_maxlen"\)', prelude, re.MULTILINE)
    assert re.search(r"^#define NAME_MAXLEN \d+$", (SRC / "unicodename_db.inc").read_text(encoding="utf-8"), re.MULTILINE)


if __name__ == "__main__":
    test_the_copies_name_the_pin_and_their_own_unicode_version()
    test_the_prelude_keeps_no_copy_of_the_databases_constants()
