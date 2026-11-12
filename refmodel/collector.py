"""The cycle collector of the reference model (step 3c): CPython 3.15.2's Python/gc.c, rule for rule, over the model's
objects (``refmodel.objects``: ``RefObject``, ``RefDict``, ``RefWeak``). The header's collector is written from this.

What a collection does (``gc_collect_main``), on the generation asked for and the younger ones merged into it:

1. ``deduce_unreachable``: each object's count, less the references the others in the generation hold (``update_refs``,
   ``subtract_refs``), says whether something outside holds it; ``move_unreachable`` then keeps what those reach and
   moves the rest to the unreachable list, in the generation's order.
2. Survivors move to the next generation (all of them stay in the oldest after a full collection).
3. ``handle_weakref_callbacks``: every weak reference with a callback to an unreachable object is cleared; the callback
   of each that is not itself unreachable runs, in the list's order, the reference held meanwhile. Weak references
   without callbacks stay (3.15: they resolve inside finalisers and survive a resurrection).
4. ``finalize_garbage``: each unreachable object's finaliser, once in its life, in the list's order.
5. ``handle_resurrected_objects``: the same reckoning over the unreachable list again; what a finaliser made reachable
   again, and what that reaches, goes to the older generation and lives on.
6. ``clear_weakrefs``: what is still unreachable loses its weak references, without callbacks, and a weak reference
   that is itself unreachable is cleared.
7. ``delete_garbage``: each object's clear function (``tp_clear``), in the list's order, the object held meanwhile;
   reference counting frees them as the cycles break; one that survives its clear moves to the older generation.

The number returned is what step 7 found plus the weak references step 3 freed (no object of the model has a legacy
``tp_del``, so nothing is uncollectable). Scheduling (``GcState.link``) and the generation an automatic collection takes
(``gc_select_generation``, with the 25% rule for a full one) are CPython's too.
"""
from __future__ import annotations

from typing import Any

from refmodel.objects import GcList, GcState, Heap, ModelError, RefObject, RefWeak, decref, incref

GENERATION_AUTO = -1


def collect(heap: Heap, generation: int = 2) -> int:
    """gc_collect_main: a collection of `generation` (GENERATION_AUTO: the one the counts select, or none); the number of
    unreachable objects found. A collection asked for while one runs does nothing and finds 0."""
    gc = heap.gc
    if gc.collecting:
        return 0
    gc.collecting = True
    try:
        if generation == GENERATION_AUTO:
            generation = select_generation(gc)
            if generation < 0:
                return 0
        return _collect(gc, generation)
    finally:
        gc.collecting = False


def look(heap: Heap) -> int:
    """_Py_RunGC at the eval breaker's look: the collection the threshold scheduled, if the collector is enabled."""
    gc = heap.gc
    if not gc.scheduled:
        return 0
    gc.scheduled = False
    if not gc.enabled:
        return 0
    return collect(heap, GENERATION_AUTO)


def select_generation(gc: GcState) -> int:
    """gc_select_generation: the oldest generation whose count passed its threshold; the oldest only while the objects
    that would join it since the last full collection are at least a quarter of those it holds."""
    for i in range(gc.NUM_GENERATIONS - 1, -1, -1):
        if gc.counts[i] > gc.thresholds[i]:
            if i == gc.NUM_GENERATIONS - 1 and gc.long_lived_pending < gc.long_lived_total // 4:
                continue
            return i
    return -1


def _collect(gc: GcState, generation: int) -> int:
    if generation + 1 < gc.NUM_GENERATIONS:
        gc.counts[generation + 1] += 1
    for i in range(generation + 1):
        gc.counts[i] = 0
    for i in range(generation):
        gc.merge(gc.generations[i], gc.generations[generation])
    young = gc.generations[generation]
    old = gc.generations[generation + 1] if generation < gc.NUM_GENERATIONS - 1 else young

    unreachable = deduce_unreachable(gc, young)
    if young is not old:
        if generation == gc.NUM_GENERATIONS - 2:
            gc.long_lived_pending += len(young)
        gc.merge(young, old)
    else:
        gc.long_lived_pending = 0
        gc.long_lived_total = len(young)

    collected = handle_weakref_callbacks(gc, unreachable, old)
    finalize_garbage(gc, unreachable)
    final = handle_resurrected_objects(gc, unreachable, old)
    clear_weakrefs(final)
    collected += len(final)
    delete_garbage(gc, final, old)
    return collected


def deduce_unreachable(gc: GcState, base: GcList) -> GcList:
    """update_refs, subtract_refs, move_unreachable: `base` keeps what is reachable from outside it, in CPython's order
    (each reached object at the end, in the order reached), and the rest moves, in order, to the list returned."""
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
                    continue                 # not in this collection (another generation, or not tracked)
                if gc.where.get(id(r)) is unreachable:
                    gc.untrack(r)            # visit_reachable: back to the end of the generation, scanned again
                    order.append(r)
                    refs[id(r)] = 1
                elif refs[id(r)] == 0:
                    refs[id(r)] = 1
            refs.pop(id(obj))                # gc_clear_collecting: no longer counted in
            kept.append(obj)
        else:
            gc.move(obj, unreachable)
    # what stayed reachable, in the order the scan kept it (CPython relinks the generation the same way)
    for obj in kept:
        gc.move(obj, base)
    return unreachable


def handle_weakref_callbacks(gc: GcState, unreachable: GcList, old: GcList) -> int:
    """Every weak reference with a callback to an unreachable object is cleared, the callback kept; those not
    themselves unreachable are held and, in order, have their callbacks called, then are released; one that lives on
    moves to `old`. The number of those that died meanwhile."""
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
    """The reckoning again over the unreachable list: what is reachable now moves to `old`; the rest is returned."""
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
