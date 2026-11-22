"""The cycle collector of the reference model (step 3c): trial deletion over candidate roots (the author's decision of
2026-11-14), then CPython 3.15.2's Python/gc.c for what a collection does with what it found, over the model's objects
(``refmodel.objects``: ``RefObject``, ``RefDict``, ``RefWeak``). The header's collector is written from this.

What a collection does (every collection is a full one; ``gc.collect(generation)``'s argument is checked and ignored):

1. ``trial_deletion``: the candidates the buffer holds are the roots (``GcState.possible_root``: an object a release
   left above nought), in the order buffered, and the buffer is emptied. From each root, every tracked object it
   reaches has its count lessened by each reference among them (``mark_gray``); what still has a count above nought
   is held from outside, and so is all it reaches, which gets its counts back (``scan``, ``scan_black``); the rest is
   unreachable: it is taken, from each root in turn, in the order a walk of the references first meets it
   (``collect_white``). A group nothing outside holds always has a candidate: the release that cut it off left the
   member it was made to with a count above nought. The order is the collector's; CPython's is its list's, and a
   group's order is left open (section 9, D-04).
2. ``handle_weakref_callbacks``: every weak reference with a callback to an unreachable object is cleared; the callback
   of each that is not itself unreachable runs, in the list's order, the reference held meanwhile. Weak references
   without callbacks stay (3.15: they resolve inside finalisers and survive a resurrection).
3. ``finalize_garbage``: each unreachable object's finaliser, once in its life, in the list's order.
4. ``handle_resurrected_objects``: gc.c's reckoning over the unreachable list again (``deduce_unreachable``); what a
   finaliser made reachable again, and what that reaches, lives on.
5. ``clear_weakrefs``: what is still unreachable loses its weak references, without callbacks, and a weak reference
   that is itself unreachable is cleared.
6. ``delete_garbage``: each object's clear function (``tp_clear``), in the list's order, the object held meanwhile;
   reference counting frees them as the cycles break. A release in these steps that leaves an object above nought makes
   it a candidate of the next collection.

The number returned is what step 6 found plus the weak references step 2 freed (no object of the model has a legacy
``tp_del``, so nothing is uncollectable): the runtime's own number, which D-04 lists.
"""
from __future__ import annotations

from typing import Any

from refmodel.objects import GcList, GcState, Heap, ModelError, RefObject, RefWeak, decref, incref

GENERATION_AUTO = -1


def collect(heap: Heap, generation: int = 2) -> int:
    """A collection, full whatever `generation` says (GENERATION_AUTO: the one a look runs); the number found. A
    collection asked for while one runs does nothing and finds 0."""
    gc = heap.gc
    if gc.collecting:
        return 0
    gc.collecting = True
    try:
        return _collect(gc)
    finally:
        gc.collecting = False


def look(heap: Heap) -> int:
    """The runtime's look (CPython's eval breaker points): the collection the buffer scheduled, if the collector is enabled."""
    gc = heap.gc
    if not gc.scheduled:
        return 0
    gc.scheduled = False
    if not gc.enabled:
        return 0
    return collect(heap, GENERATION_AUTO)


def _collect(gc: GcState) -> int:
    gc.scheduled = False                         # the buffer the schedule counted is taken now
    roots = [obj for obj in gc.candidates.values() if gc.is_tracked(obj)]
    gc.candidates.clear()
    survivors = GcList("survivors")
    unreachable = trial_deletion(gc, roots)
    collected = handle_weakref_callbacks(gc, unreachable, survivors)
    finalize_garbage(gc, unreachable)
    final = handle_resurrected_objects(gc, unreachable, survivors)
    clear_weakrefs(final)
    collected += len(final)
    delete_garbage(gc, final, survivors)
    for lst in (survivors, unreachable, final):
        for obj in lst:
            gc.unlist(obj)
    gc.alive_after = len(gc.tracked)
    gc.collections += 1
    gc.collected += collected
    return collected


def _children(gc: GcState, obj: Any) -> list[Any]:
    """What the object holds that the collector walks: the tracked objects of its traverse, in its order."""
    return [r for r in obj.traverse() if gc.is_tracked(r)]


def trial_deletion(gc: GcState, roots: list[Any]) -> GcList:
    """mark_gray, scan and collect_white from the roots: the list of what nothing outside holds, in the order taken."""
    counts: dict[int, int] = {}
    color: dict[int, str] = {}
    for root in roots:                           # mark_gray: each reference among the reached lessens a count once
        if id(root) in color:
            continue
        if root.refs <= 0:
            raise ModelError(f"{root!r} is a candidate with no count")
        counts[id(root)] = root.refs
        color[id(root)] = "gray"
        stack = [root]
        while stack:
            for child in _children(gc, stack.pop()):
                if id(child) not in counts:
                    counts[id(child)] = child.refs
                counts[id(child)] -= 1
                if id(child) not in color:
                    color[id(child)] = "gray"
                    stack.append(child)

    def scan_black(obj: Any) -> None:            # held from outside: it and all it reaches get their counts back
        color[id(obj)] = "black"
        stack = [obj]
        while stack:
            for child in _children(gc, stack.pop()):
                counts[id(child)] += 1
                if color[id(child)] != "black":
                    color[id(child)] = "black"
                    stack.append(child)

    for root in roots:                           # scan
        stack = [root]
        while stack:
            obj = stack.pop()
            if color.get(id(obj)) != "gray":
                continue
            if counts[id(obj)] > 0:
                scan_black(obj)
            else:
                color[id(obj)] = "white"
                stack.extend(reversed(_children(gc, obj)))
    unreachable = GcList("unreachable")
    for root in roots:                           # collect_white: from each root, in the order a walk first meets them
        stack = [root]
        while stack:
            obj = stack.pop()
            if color.get(id(obj)) != "white":
                continue
            color[id(obj)] = "taken"
            gc.move(obj, unreachable)
            stack.extend(reversed(_children(gc, obj)))
    return unreachable


def deduce_unreachable(gc: GcState, base: GcList) -> GcList:
    """gc.c's update_refs, subtract_refs, move_unreachable, over a collection's own list: `base` keeps what is reachable
    from outside it, in CPython's order (each reached object at the end, in the order reached), and the rest moves, in
    order, to the list returned (handle_resurrected_objects' reckoning)."""
    refs: dict[int, int] = {}
    for obj in base:
        if obj.refs <= 0:
            raise ModelError(f"{obj!r} is tracked with no count")
        refs[id(obj)] = obj.refs
    for obj in base:
        for r in obj.traverse():
            if id(r) in refs:
                refs[id(r)] -= 1
    unreachable = GcList("unreachable")
    order = list(base)                       # the scan; an object reached again is scanned again at the end
    kept: list[Any] = []
    i = 0
    while i < len(order):
        obj = order[i]
        i += 1
        if gc.where.get(id(obj)) is unreachable:
            continue                         # moved away at its first place and not reached since
        if refs[id(obj)] > 0:
            for r in obj.traverse():
                if id(r) not in refs:
                    continue                 # not in this list (not tracked, or held by what is not unreachable)
                if gc.where.get(id(r)) is unreachable:
                    gc.unlist(r)             # visit_reachable: back to the end of the list, scanned again
                    order.append(r)
                    refs[id(r)] = 1
                elif refs[id(r)] == 0:
                    refs[id(r)] = 1
            refs.pop(id(obj))                # gc_clear_collecting: no longer counted in
            kept.append(obj)
        else:
            gc.move(obj, unreachable)
    # what stayed reachable, in the order the scan kept it (CPython relinks the list the same way)
    for obj in kept:
        gc.move(obj, base)
    return unreachable


def handle_weakref_callbacks(gc: GcState, unreachable: GcList, old: GcList) -> int:
    """Every weak reference with a callback to an unreachable object is cleared, the callback kept; those not
    themselves unreachable are held and, in order, have their callbacks called, then are released; one that lives on
    moves to `old`, the collection's survivors. The number of those that died meanwhile."""
    to_call = GcList("weakref callbacks")
    for op in unreachable:
        if not isinstance(op, RefObject):
            continue
        for wr in list(op.weakrefs):
            if wr.callback is None:
                continue
            wr.clear_ref()
            if gc.where.get(id(wr)) is unreachable:
                continue                     # both go: the reference is taken to go first, its callback never runs
            incref(wr)
            gc.move(wr, to_call)
    freed = 0
    while len(to_call):
        wr = to_call.first()
        callback = wr.callback
        assert callback is not None
        callback(wr)                         # handle_callback; what it raises is the unraisable hook's (not modelled)
        decref(wr)
        if gc.where.get(id(wr)) is to_call:
            gc.move(wr, old)
        else:
            freed += 1
    return freed


def finalize_garbage(gc: GcState, collectable: GcList) -> None:
    """The finaliser of each object, in order, once in its life (it is marked before the call), the object held; an
    object that dies meanwhile has left the list."""
    seen = GcList("seen")
    while len(collectable):
        op = collectable.first()
        gc.move(op, seen)
        if isinstance(op, RefObject) and not op.finalized and op.has_finalizer():
            incref(op)
            op.finalize()
            decref(op)
    gc.merge(seen, collectable)


def handle_resurrected_objects(gc: GcState, unreachable: GcList, old: GcList) -> GcList:
    """gc.c's reckoning again over the unreachable list: what is reachable now moves to `old`; the rest is returned."""
    still = deduce_unreachable(gc, unreachable)
    gc.merge(unreachable, old)
    return still


def clear_weakrefs(unreachable: GcList) -> None:
    """No unreachable object is weakly referenced any more, and no callback runs; an unreachable weak reference is
    cleared too."""
    for op in unreachable:
        if isinstance(op, RefWeak):
            op.clear_ref()
        if isinstance(op, RefObject):
            while op.weakrefs:
                op.weakrefs[0].clear_ref()


def delete_garbage(gc: GcState, collectable: GcList, old: GcList) -> None:
    """Each object's clear function, the object held; one that is still first in the list afterwards lives on and moves
    to `old`."""
    while len(collectable):
        op = collectable.first()
        if op.refs <= 0:
            raise ModelError(f"{op!r}: refcount is too small")
        incref(op)
        op.gc_clear()
        decref(op)
        if len(collectable) and collectable.first() is op:
            gc.move(op, old)
