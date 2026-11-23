"""A frame's values outlive the frame while its frame object is held, compiled against CPython (RL-222; D-12, part 2).

CPython gives a frame one frame object at most, made at the first asking (_PyFrame_GetFrameObject: the frame's first
traceback entry), and its entries share it as tb_frame. When the frame is over (it returned, an exception left it, a
generator ended or was closed or deallocated) and something else holds the object, the object takes the frame's values
(_PyFrame_ClearExceptCode, take_ownership), and with them the frame object of the frame's caller as f_back, so the caller's
values outlive its own end the same way. They go when the object dies or is cleared, and a frame object in a cycle (an
exception kept in a local of its own frame) waits for the collector.

`kept_frames.txt` is one program a side, each row printing when the values go against what it does:

* a frame that caught an exception and returned it, and its caller, which called no more than that;
* an exception that passed two frames and was caught by a third, all three kept;
* a generator that kept its exception in an earlier resume: its frame is one across its resumes, so the values last until the
  list holding the exception is cleared, after the generator is gone; the same for one closed while suspended, whose frame
  object takes its stack values too (take_ownership copies the whole frame);
* a bare `raise` after a `yield` adds no second entry of the generator's frame;
* an exception kept in a local of its own frame (a function's and a generator's): a cycle, freed by `gc.collect()`;
* two exceptions of one frame kept, let go of in either order: the values go with the second;
* a cell variable, after the closure is gone; a class body's namespace, after the class attribute is deleted;
* `traceback.clear_frames` after the frame returned, which releases the values then;
* the suggestions of traceback for a frame that caught and returned, a class body's, and the first of two exceptions of one
  frame, which read the frame object's values (until this step they stopped by name).

Run under pytest or directly: python3 -m pipeline.tests.test_kept_frames
"""
from __future__ import annotations

from pathlib import Path

from pipeline.tests.test_review_2026_11_19 import same

HERE = Path(__file__).resolve().parent


def test_kept_frames() -> None:
    same((HERE / "kept_frames.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    test_kept_frames()
    print("ok")
