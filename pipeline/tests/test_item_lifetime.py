"""An item goes before the next one is asked for: what a consumer written in C lets go of, and when.

Review A35 (RL-782): the generator RL-765 had put between a loop of a prelude and an iterator of the program's kept the
item it had yielded, so an item's finaliser ran one `__next__` later than under CPython, and a program whose items count
the live ones got another sum. The class is wider than that wrapper. A `for` of a prelude keeps the item in its variable
across the next `__next__`, and a loop of the runtime's `for (Ref v = for_next(it); ...; v = for_next(it))` kept it across
the call in its step; the C lets go of the item first (`Py_DECREF(item)` at the end of the loop's body). 44 of the 119
consumers below differed before: `bytes`, the set methods, `in`, `filter`, `sum`, `min`, `max`, `any`, `all`, `reduce`,
`deque` with no room, `_count_elements`, `OrderedDict`, the csv writer, four `writelines`, `math.fsum`, `prod`, `sumprod`.

The rule: the wrapper hands the item on and keeps nothing; a loop of a prelude over an iterator of the program's ends
each turn with `del`; a loop of the runtime's steps with `next_after`; and where the C does something between the last
item and letting go of the iterator (`reduce`'s tuple, `min`'s value), the prelude holds the iterator and asks it with
`next()`.

The row that is not here: a generator expression of the program's lets go of its iterator when its frame ends, where
CPython 3.15 lets go of it at the loop's end (the expression's `.0` is the iterable there; RL-488, open).

Run under pytest or directly: python3 -m pipeline.tests.test_item_lifetime
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.build import build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRELUDE = ROOT / "runtime" / "prelude"
RUNTIME = ROOT / "runtime" / "src"


def _run(command: list[str], folder: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout + ("" if done.returncode in (0, 70) else done.stderr[-300:])


def test_an_item_goes_before_the_next_is_asked_for() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-lifetime-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "item_lifetime_sweep.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        count = int(_run([sys.executable, str(program), "count"], folder)[1])
        assert count >= 118, count
        with ThreadPoolExecutor(max_workers=4) as pool:
            reference = list(pool.map(lambda row: _run([sys.executable, str(program), str(row)], folder), range(count)))
            compiled = list(pool.map(lambda row: _run([binary, str(row)], folder), range(count)))
        wrong: list[str] = []
        for row, (want, got) in enumerate(zip(reference, compiled, strict=True)):
            assert want[0] == 0, (row, want)
            if got != want:
                wrong.append(f"{row}: compiled {got[1].split()!r} (status {got[0]}), CPython {want[1].split()!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_a_loop_over_a_taken_iterator_ends_each_turn_with_del() -> None:
    """The rule in the source. A prelude's `for` over what `_tp_iter` gave lets go of its variable in its body, and the
    wrapper yields what it has popped; no loop of the runtime's asks for the next item in its step while it holds one."""
    missing: list[str] = []
    for path in sorted(PRELUDE.glob("*.py")):
        lines = path.read_text(encoding="utf-8").split("\n")
        if not any(line.startswith("def _tp_iter(") for line in lines):
            continue
        assert any(line.strip() == "yield held.pop()" for line in lines), path.name
        for at, line in enumerate(lines):
            found = re.match(r"( *)for (\w+) in (?:_tp_iter\(.*\)|it):", line)
            if not found:
                continue
            indent, name = len(found.group(1)), found.group(2)
            body: list[str] = []
            for later in lines[at + 1:]:
                if later.strip() and len(later) - len(later.lstrip()) <= indent:
                    break
                body.append(later.split("#")[0])
            if not any(re.search(rf"\bdel (?:\w+, )*{name}\b", text) for text in body):
                missing.append(f"{path.name}:{at + 1}")
    assert not missing, missing
    kept = [f"{path.name}:{at + 1}" for path in sorted(RUNTIME.glob("*.cpp"))
            for at, line in enumerate(path.read_text(encoding="utf-8").split("\n"))
            if re.search(r"; \w+ = for_next\(", line)]
    assert not kept, kept


if __name__ == "__main__":
    test_a_loop_over_a_taken_iterator_ends_each_turn_with_del()
    test_an_item_goes_before_the_next_is_asked_for()
    print("ok")
