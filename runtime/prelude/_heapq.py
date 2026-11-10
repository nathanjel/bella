"""_heapq, in Python (Modules/_heapqmodule.c): the min and max heaps' siftdown and siftup as the C has them (the comparisons made, their
order, the RuntimeError when a comparison changes the list's size), heapify's bottom-up pass (the cache-friendly order above 2500
items makes the same heap), and the clinic's parsing: a list, or a subclass, and the item, positional only. heapq imports * from
here; __about__ is the module's essay."""

__all__ = ["__about__", "heapify", "heapify_max", "heappop", "heappop_max", "heappush", "heappush_max", "heappushpop", "heappushpop_max",
           "heapreplace", "heapreplace_max"]

__name__ = "_heapq"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__


__about__ = 'Heap queues\n\n[explanation by François Pinard]\n\nHeaps are arrays for which a[k] <= a[2*k+1] and a[k] <= a[2*k+2] for\nall k, counting elements from 0.  For the sake of comparison,\nnon-existing elements are considered to be infinite.  The interesting\nproperty of a heap is that a[0] is always its smallest element.\n\nThe strange invariant above is meant to be an efficient memory\nrepresentation for a tournament.  The numbers below are \'k\', not a[k]:\n\n                                   0\n\n                  1                                 2\n\n          3               4                5               6\n\n      7       8       9       10      11      12      13      14\n\n    15 16   17 18   19 20   21 22   23 24   25 26   27 28   29 30\n\n\nIn the tree above, each cell \'k\' is topping \'2*k+1\' and \'2*k+2\'.  In\na usual binary tournament we see in sports, each cell is the winner\nover the two cells it tops, and we can trace the winner down the tree\nto see all opponents s/he had.  However, in many computer applications\nof such tournaments, we do not need to trace the history of a winner.\nTo be more memory efficient, when a winner is promoted, we try to\nreplace it by something else at a lower level, and the rule becomes\nthat a cell and the two cells it tops contain three different items,\nbut the top cell "wins" over the two topped cells.\n\nIf this heap invariant is protected at all time, index 0 is clearly\nthe overall winner.  The simplest algorithmic way to remove it and\nfind the "next" winner is to move some loser (let\'s say cell 30 in the\ndiagram above) into the 0 position, and then percolate this new 0 down\nthe tree, exchanging values, until the invariant is re-established.\nThis is clearly logarithmic on the total number of items in the tree.\nBy iterating over all items, you get an O(n ln n) sort.\n\nA nice feature of this sort is that you can efficiently insert new\nitems while the sort is going on, provided that the inserted items are\nnot "better" than the last 0\'th element you extracted.  This is\nespecially useful in simulation contexts, where the tree holds all\nincoming events, and the "win" condition means the smallest scheduled\ntime.  When an event schedule other events for execution, they are\nscheduled into the future, so they can easily go into the heap.  So, a\nheap is a good structure for implementing schedulers (this is what I\nused for my MIDI sequencer :-).\n\nVarious structures for implementing schedulers have been extensively\nstudied, and heaps are good for this, as they are reasonably speedy,\nthe speed is almost constant, and the worst case is not much different\nthan the average case.  However, there are other representations which\nare more efficient overall, yet the worst cases might be terrible.\n\nHeaps are also very useful in big disk sorts.  You most probably all\nknow that a big sort implies producing "runs" (which are pre-sorted\nsequences, which size is usually related to the amount of CPU memory),\nfollowed by a merging passes for these runs, which merging is often\nvery cleverly organised[1].  It is very important that the initial\nsort produces the longest runs possible.  Tournaments are a good way\nto that.  If, using all the memory available to hold a tournament, you\nreplace and percolate items that happen to fit the current run, you\'ll\nproduce runs which are twice the size of the memory for random input,\nand much better for input fuzzily ordered.\n\nMoreover, if you output the 0\'th item on disk and get an input which\nmay not fit in the current tournament (because the value "wins" over\nthe last output value), it cannot fit in the heap, so the size of the\nheap decreases.  The freed memory could be cleverly reused immediately\nfor progressively building a second heap, which grows at exactly the\nsame rate the first heap is melting.  When the first heap completely\nvanishes, you switch heaps and start a new run.  Clever and quite\neffective!\n\nIn a word, heaps are useful memory structures to know.  I use them in\na few applications, and I think it is good to keep a \'heap\' module\naround. :-)\n\n--------------------\n[1] The disk balancing algorithms which are current, nowadays, are\nmore annoying than clever, and this is a consequence of the seeking\ncapabilities of the disks.  On devices which cannot seek, like big\ntape drives, the story was quite different, and one had to be very\nclever to ensure (far in advance) that each tape movement will be the\nmost effective possible (that is, will best participate at\n"progressing" the merge).  Some tapes were even able to read\nbackwards, and this was also used to avoid the rewinding time.\nBelieve me, real good tape sorts were quite spectacular to watch!\nFrom all times, sorting has always been a Great Art! :-)\n'


def _args(fname: str, args: tuple[object, ...], kwds: dict[str, object], count: int) -> list[object]:   # the clinic: positional only, a list first
    if kwds:
        raise TypeError("_heapq." + fname + "() takes no keyword arguments")
    if len(args) != count:
        if count == 1:
            raise TypeError("_heapq." + fname + "() takes exactly one argument (" + str(len(args)) + " given)")
        raise TypeError(fname + " expected " + str(count) + " arguments, got " + str(len(args)))
    if not issubclass(type(args[0]), list):
        raise TypeError(fname + "() argument" + (" 1" if count > 1 else "") + " must be list, not " + _tp_name(args[0]))
    return list(args)


# PyList_GET_ITEM, PyList_SET_ITEM and PyList_SetSlice: the list's own storage, whatever a subclass's __getitem__, __setitem__ or
# __delitem__ would do (review F17 #5)
_get = list.__getitem__
_set = list.__setitem__
_del = list.__delitem__


def _siftdown(heap: list[object], startpos: int, pos: int, maximum: bool) -> None:   # siftdown / siftdown_max
    size = list.__len__(heap)
    if pos >= size:
        raise IndexError("index out of range")
    newitem = _get(heap, pos)
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = _get(heap, parentpos)
        cmp = (parent < newitem) if maximum else (newitem < parent)
        if size != list.__len__(heap):
            raise RuntimeError("list changed size during iteration")
        if not cmp:
            break
        parent = _get(heap, parentpos)
        newitem = _get(heap, pos)
        _set(heap, parentpos, newitem)
        _set(heap, pos, parent)
        pos = parentpos


def _siftup(heap: list[object], pos: int, maximum: bool) -> None:   # siftup / siftup_max
    endpos = list.__len__(heap)
    startpos = pos
    if pos >= endpos:
        raise IndexError("index out of range")
    limit = endpos >> 1
    while pos < limit:
        childpos = 2 * pos + 1
        if childpos + 1 < endpos:
            if maximum:                          # the larger child: the right one unless it is smaller than the left
                cmp = _get(heap, childpos + 1) < _get(heap, childpos)
            else:                                # the smaller child: the right one unless the left is smaller
                cmp = _get(heap, childpos) < _get(heap, childpos + 1)
            if not cmp:
                childpos += 1
            if endpos != list.__len__(heap):
                raise RuntimeError("list changed size during iteration")
        tmp1 = _get(heap, childpos)
        tmp2 = _get(heap, pos)
        _set(heap, childpos, tmp2)
        _set(heap, pos, tmp1)
        pos = childpos
    _siftdown(heap, startpos, pos, maximum)


def _pop(heap: list[object], maximum: bool) -> object:   # heappop_internal
    n = list.__len__(heap)
    if n == 0:
        raise IndexError("index out of range")
    lastelt = _get(heap, n - 1)
    _del(heap, slice(n - 1, n))
    n -= 1
    if not n:
        return lastelt
    returnitem = _get(heap, 0)
    _set(heap, 0, lastelt)
    _siftup(heap, 0, maximum)
    return returnitem


def _replace(heap: list[object], item: object, maximum: bool) -> object:   # heapreplace_internal
    if list.__len__(heap) == 0:
        raise IndexError("index out of range")
    returnitem = _get(heap, 0)
    _set(heap, 0, item)
    _siftup(heap, 0, maximum)
    return returnitem


def _pushpop(heap: list[object], item: object, maximum: bool) -> object:   # heappushpop and heappushpop_max
    if list.__len__(heap) == 0:
        return item
    top = _get(heap, 0)
    cmp = (item < top) if maximum else (top < item)
    if not cmp:
        return item
    if list.__len__(heap) == 0:
        raise IndexError("index out of range")
    returnitem = _get(heap, 0)
    _set(heap, 0, item)
    _siftup(heap, 0, maximum)
    return returnitem


def _keep_top_bit(n: int) -> int:
    i = 0
    while n > 1:
        n >>= 1
        i += 1
    return n << i


def _heapify(heap: list[object], maximum: bool) -> None:   # heapify_internal: the cache-friendly order past 2500 makes the same heap
    n = list.__len__(heap)
    if n > 2500:
        m = n >> 1
        leftmost = _keep_top_bit(m + 1) - 1
        mhalf = m >> 1
        for i in range(leftmost - 1, mhalf - 1, -1):
            j = i
            while True:
                _siftup(heap, j, maximum)
                if not (j & 1):
                    break
                j >>= 1
        for i in range(m - 1, leftmost - 1, -1):
            j = i
            while True:
                _siftup(heap, j, maximum)
                if not (j & 1):
                    break
                j >>= 1
        return
    for i in range((n >> 1) - 1, -1, -1):
        _siftup(heap, i, maximum)


def heappush(*args: object, **kwds: object) -> None:
    """Push item onto heap, maintaining the heap invariant."""
    heap, item = _args("heappush", args, kwds, 2)
    list.append(heap, item)  # type: ignore[arg-type]
    _siftdown(heap, 0, list.__len__(heap) - 1, False)  # type: ignore[arg-type]


def heappushpop(*args: object, **kwds: object) -> object:
    """Push item on the heap, then pop and return the smallest item from the heap.

The combined action runs more efficiently than heappush() followed by
a separate call to heappop()."""
    heap, item = _args("heappushpop", args, kwds, 2)
    return _pushpop(heap, item, False)  # type: ignore[arg-type]


def heappop(*args: object, **kwds: object) -> object:
    """Pop the smallest item off the heap, maintaining the heap invariant."""
    (heap,) = _args("heappop", args, kwds, 1)
    return _pop(heap, False)  # type: ignore[arg-type]


def heapreplace(*args: object, **kwds: object) -> object:
    """Pop and return the current smallest value, and add the new item.

This is more efficient than heappop() followed by heappush(), and can be
more appropriate when using a fixed-size heap.  Note that the value
returned may be larger than item!  That constrains reasonable uses of
this routine unless written as part of a conditional replacement:

    if item > heap[0]:
        item = heapreplace(heap, item)"""
    heap, item = _args("heapreplace", args, kwds, 2)
    return _replace(heap, item, False)  # type: ignore[arg-type]


def heapify(*args: object, **kwds: object) -> None:
    """Transform list into a heap, in-place, in O(len(heap)) time."""
    (heap,) = _args("heapify", args, kwds, 1)
    _heapify(heap, False)  # type: ignore[arg-type]


def heappush_max(*args: object, **kwds: object) -> None:
    """Push item onto max heap, maintaining the heap invariant."""
    heap, item = _args("heappush_max", args, kwds, 2)
    list.append(heap, item)  # type: ignore[arg-type]
    _siftdown(heap, 0, list.__len__(heap) - 1, True)  # type: ignore[arg-type]


def heappushpop_max(*args: object, **kwds: object) -> object:
    """Maxheap variant of heappushpop.

The combined action runs more efficiently than heappush_max()
followed by a separate call to heappop_max()."""
    heap, item = _args("heappushpop_max", args, kwds, 2)
    return _pushpop(heap, item, True)  # type: ignore[arg-type]


def heappop_max(*args: object, **kwds: object) -> object:
    """Maxheap variant of heappop."""
    (heap,) = _args("heappop_max", args, kwds, 1)
    return _pop(heap, True)  # type: ignore[arg-type]


def heapreplace_max(*args: object, **kwds: object) -> object:
    """Maxheap variant of heapreplace."""
    heap, item = _args("heapreplace_max", args, kwds, 2)
    return _replace(heap, item, True)  # type: ignore[arg-type]


def heapify_max(*args: object, **kwds: object) -> None:
    """Maxheap variant of heapify."""
    (heap,) = _args("heapify_max", args, kwds, 1)
    _heapify(heap, True)  # type: ignore[arg-type]
