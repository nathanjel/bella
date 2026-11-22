"""The order in which the names a `match` case captures are stored.

CPython leaves the captured values on its stack while a pattern is matched and stores them once the whole pattern has
matched (Python/codegen.c, codegen_match_inner). Its code generator emits the stores in the order of capture, each value
having been rotated under what the stack held when it was captured (codegen_pattern_helper_store_name: SWAPs); its
optimizer then removes the SWAPs that stand right before the stores by exchanging the stores themselves
(Python/flowgraph.c: swaptimize, apply_static_swaps). The values end where they belong either way. What differs is the
order in which the names are bound, and so the order in which what they held is let go of: `case [a, [b, c]]` stores b, c
and then a.

Two halves, as the question has two:

* `capture_plan(pattern)` is the code generator's: the names in the order of capture, and the instructions that stand
  between the last instruction the optimizer cannot move (or the start of the basic block) and the stores. Only SWAP and
  POP_TOP can stand there, and each has the line of the pattern it was emitted for, since the optimizer exchanges nothing
  across a line. Everything before that point is beyond the optimizer's reach for these stores, so it is not kept.
* `store_order(captures, fast)` is the optimizer's, run on those instructions and the stores. It needs to know which
  names are fast locals (STORE_FAST is the one store the optimizer moves), which is a matter of scopes and so of the next
  level (pipeline/l2/resolve.py); the lowering and eval1 call it with what the resolver says.

Both are ports, function by function, of CPython 3.15.2; pipeline/tests/test_match_stores.py compares them with what
`dis` shows for generated patterns.
"""
from __future__ import annotations

import ast
from collections.abc import Sequence

from pipeline.l1 import grammar as L

_SWAP, _POP, _STORE, _HELD, _NOP = "swap", "pop", "store", "held", "nop"
_VISITED = -1


class _Codegen:
    """codegen_pattern and its helpers, for what they leave on the stack: `on_top` and `stores` are pattern_context's, and
    `tail` is what was emitted since the last instruction that is neither a SWAP nor a POP_TOP, or since the last jump or
    label (a basic block ends there)."""

    def __init__(self) -> None:
        self.on_top = 0
        self.stores: list[str] = []
        self.tail: list[tuple[int, int]] = []     # (depth, line): SWAP depth, or POP_TOP where the depth is 0

    def other(self) -> None:
        self.tail.clear()

    def pop(self, line: int) -> None:
        self.tail.append((0, line))

    def rotate(self, count: int, line: int) -> None:          # codegen_pattern_helper_rotate
        while 1 < count:
            self.tail.append((count, line))
            count -= 1

    def store_name(self, name: str | None, line: int) -> None:  # codegen_pattern_helper_store_name
        if name is None:
            self.pop(line)
            return
        self.rotate(self.on_top + len(self.stores) + 1, line)
        self.stores.append(name)

    def pattern(self, p: ast.pattern) -> None:
        if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
            self.other()                                      # the value, the comparison, the jump
        elif isinstance(p, ast.MatchSequence):
            self.sequence(p)
        elif isinstance(p, ast.MatchMapping):
            self.mapping(p)
        elif isinstance(p, ast.MatchClass):
            self.class_(p)
        elif isinstance(p, ast.MatchStar):
            self.store_name(p.name, p.lineno)
        elif isinstance(p, ast.MatchAs):
            if p.pattern is None:
                self.store_name(p.name, p.lineno)
            else:
                self.on_top += 1
                self.other()                                  # COPY 1
                self.pattern(p.pattern)
                self.on_top -= 1
                self.store_name(p.name, p.lineno)
        elif isinstance(p, ast.MatchOr):
            self.or_(p)
        else:
            raise L.Unsupported(f"pattern {type(p).__name__} (line {p.lineno})")

    def sequence(self, p: ast.MatchSequence) -> None:         # codegen_pattern_sequence
        size = len(p.patterns)
        star = next((i for i, x in enumerate(p.patterns) if isinstance(x, ast.MatchStar)), -1)
        star_wildcard = star >= 0 and _wildcard_star(p.patterns[star])
        only_wildcard = all(_wildcard(x) or _wildcard_star(x) for x in p.patterns)
        self.on_top += 1
        self.other()                                          # MATCH_SEQUENCE, the length, their jumps
        self.on_top -= 1
        if only_wildcard:
            self.pop(p.lineno)
        elif star_wildcard:                                   # pattern_helper_sequence_subscr
            self.on_top += 1
            for i, sub in enumerate(p.patterns):
                if _wildcard(sub) or i == star:
                    continue
                self.other()                                  # COPY 1, the index, BINARY_OP
                self.pattern(sub)
            self.on_top -= 1
            self.pop(p.lineno)
        else:                                                 # pattern_helper_sequence_unpack
            self.other()                                      # UNPACK_SEQUENCE or UNPACK_EX
            self.on_top += size
            for sub in p.patterns:
                self.on_top -= 1
                self.pattern(sub)

    def mapping(self, p: ast.MatchMapping) -> None:           # codegen_pattern_mapping
        size = len(p.keys)
        self.on_top += 1
        self.other()                                          # MATCH_MAPPING and its jump
        if not size and p.rest is None:
            self.on_top -= 1
            self.pop(p.lineno)
            return
        self.on_top += 2
        self.other()                                          # the length, the keys, MATCH_KEYS, UNPACK_SEQUENCE
        self.on_top += size - 1
        for sub in p.patterns:
            self.on_top -= 1
            self.pattern(sub)
        self.on_top -= 2
        if p.rest is not None:
            self.other()                                      # BUILD_MAP, SWAP 3, DICT_UPDATE, UNPACK_SEQUENCE, the deletions
            self.store_name(p.rest, p.lineno)
        else:
            self.pop(p.lineno)                                # the tuple of keys
            self.pop(p.lineno)                                # the subject

    def class_(self, p: ast.MatchClass) -> None:              # codegen_pattern_class
        self.other()                                          # the class, MATCH_CLASS, the jump, UNPACK_SEQUENCE
        subs = [*p.patterns, *p.kwd_patterns]
        self.on_top += 1
        self.on_top += len(subs) - 1
        for sub in subs:
            self.on_top -= 1
            if _wildcard(sub):
                self.pop(p.lineno)                            # the class pattern's line, not the wildcard's
                continue
            self.pattern(sub)

    def or_(self, p: ast.MatchOr) -> None:                    # codegen_pattern_or
        # Each alternative is matched on a copy of the subject and ends with a jump, so none of what it emits reaches
        # the stores; where an alternative captured in another order than the first, it rotates the values into the
        # first's order before that jump. What is left for the stores is the first alternative's names in its order.
        first = _Codegen()
        first.pattern(p.patterns[0])
        control = first.stores
        self.other()                                          # the label `end`: a new basic block
        rotations = len(control) + 1 + self.on_top + len(self.stores)
        for name in control:
            self.rotate(rotations, p.lineno)
            self.stores.append(name)
        self.pop(p.lineno)                                    # the copy of the subject


def _wildcard(p: ast.pattern) -> bool:                        # WILDCARD_CHECK
    return isinstance(p, ast.MatchAs) and p.name is None


def _wildcard_star(p: ast.pattern) -> bool:                   # WILDCARD_STAR_CHECK
    return isinstance(p, ast.MatchStar) and p.name is None


def capture_plan(pattern: ast.pattern) -> tuple[list[str], L.Captures]:
    """The names a case's pattern captures, in the order of capture (pc->stores), and what stands before their stores."""
    gen = _Codegen()
    gen.pattern(pattern)
    return gen.stores, L.Captures(tuple(gen.tail), pattern.lineno)


def store_order(captures: L.Captures, fast: Sequence[bool]) -> tuple[int, ...]:
    """The order in which the captures are stored, as indices into the order of capture. `fast[i]` says whether the i-th
    name is a fast local of its function; no other store is one the optimizer moves, or looks past.

    optimize_basic_block's last loop: each run of SWAPs is made the shortest with the same effect (swaptimize), and then,
    from its last instruction leftwards, every SWAP that has enough movable instructions after it on one line is removed
    by exchanging two of them (apply_static_swaps)."""
    code: list[list[object]] = [[_SWAP if depth else _POP, depth, line] for depth, line in captures.before]
    code += [[_STORE if is_fast else _HELD, i, captures.line] for i, is_fast in enumerate(fast)]
    i = 0
    while i < len(code):
        if code[i][0] == _SWAP:
            i = _swaptimize(code, i)
            _apply_static_swaps(code, i)
        i += 1
    return tuple(_int(instr[1]) for instr in code if instr[0] in (_STORE, _HELD))


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _swaptimize(code: list[list[object]], ix: int) -> int:
    """flowgraph.c swaptimize: the run of SWAPs and NOPs that starts at `ix` becomes the shortest run with the same
    effect, written from the run's end backwards, NOPs in front. Returns the index the caller goes on from."""
    depth = _int(code[ix][1])
    length = 0
    more = False
    limit = len(code) - ix
    while True:
        length += 1
        if not length < limit:
            break
        kind = code[ix + length][0]
        if kind == _SWAP:
            depth = max(depth, _int(code[ix + length][1]))
            more = True
        elif kind != _NOP:
            break
    if not more:
        return ix
    stack = list(range(depth))
    for i in range(length):
        if code[ix + i][0] == _SWAP:
            oparg = _int(code[ix + i][1])
            stack[0], stack[oparg - 1] = stack[oparg - 1], stack[0]
    current = length - 1
    for i in range(depth):
        if stack[i] == _VISITED or stack[i] == i:
            continue
        j = i
        while True:
            if j:
                code[ix + current][0] = _SWAP
                code[ix + current][1] = j + 1
                current -= 1
            if stack[j] == _VISITED:
                break
            following = stack[j]
            stack[j] = _VISITED
            j = following
    while 0 <= current:
        code[ix + current][0] = _NOP
        code[ix + current][1] = 0
        current -= 1
    return ix + length - 1


def _next_swappable(code: list[list[object]], i: int, line: int) -> int:
    """flowgraph.c next_swappable_instruction: the next STORE_FAST or POP_TOP, NOPs skipped; -1 where something else comes
    first, or an instruction of another line than `line` (given as -1, any line will do)."""
    while True:
        i += 1
        if not i < len(code):
            return -1
        if 0 <= line and code[i][2] != line:
            return -1
        if code[i][0] == _NOP:
            continue
        return i if code[i][0] in (_STORE, _POP) else -1


def _apply_static_swaps(code: list[list[object]], i: int) -> None:
    """flowgraph.c apply_static_swaps. Its check that the two instructions do not store to one variable, nor any between
    them to the variable of either, is not here: the names of one pattern are different names."""
    while 0 <= i:
        if code[i][0] != _SWAP:
            if code[i][0] in (_NOP, _STORE, _POP):
                i -= 1
                continue
            return
        j = _next_swappable(code, i, -1)
        if j < 0:
            return
        k = j
        line = _int(code[j][2])
        for _ in range(_int(code[i][1]) - 1):
            k = _next_swappable(code, k, line)
            if k < 0:
                return
        code[i][0] = _NOP
        code[i][1] = 0
        code[j], code[k] = code[k], code[j]
        i -= 1
