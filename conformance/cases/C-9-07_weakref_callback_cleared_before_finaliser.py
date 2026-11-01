# clause: C-9-07
# spec: section 9
# status: P1
# source: CPython 3.15 change found by re-recording C-9-02 on 2026-11-01 (DECISIONS, finding 5)
"""Cyclic garbage: weak references with callbacks are cleared, and their callbacks run, before any
finaliser; weak references without callbacks still resolve inside __del__ and survive resurrection."""
import gc
import weakref

events: list[str] = []
keep: list[Node] = []
refs: list[weakref.ref[Node]] = []


class Node:
    def __init__(self, resurrect: bool) -> None:
        self.resurrect = resurrect
        self.me: Node | None = None

    def __del__(self) -> None:
        events.append(f"__del__ sees plain dead={refs[0]() is None} callback dead={refs[1]() is None}")
        if self.resurrect:
            keep.append(self)


def on_clear(_: weakref.ref[Node]) -> None:
    events.append("callback")


def run(resurrect: bool) -> None:
    events.clear()
    keep.clear()
    refs.clear()
    n = Node(resurrect)
    n.me = n
    refs.append(weakref.ref(n))
    refs.append(weakref.ref(n, on_clear))
    del n
    gc.collect()
    events.append(f"after collect: plain dead={refs[0]() is None} callback dead={refs[1]() is None} resurrected={len(keep)}")
    keep.clear()
    gc.collect()
    events.append(f"after release: plain dead={refs[0]() is None}")
    print(f"resurrect={resurrect}:", " | ".join(events))


run(False)
run(True)
