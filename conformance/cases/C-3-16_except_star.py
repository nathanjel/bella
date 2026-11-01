# clause: C-3-16
# spec: section 3
# status: P1
# source: TODO task 2 (except*); spec section 3 lists try/except* as [P1]
"""except* splits an ExceptionGroup by type: each matching clause runs once with the subgroup it
matched, the unmatched rest propagates as a group, a bare exception is wrapped in a group, and
split() and subgroup() keep the nesting."""


def batch() -> None:
    raise ExceptionGroup("batch", [ValueError(1), TypeError(2), ExceptionGroup("inner", [ValueError(3), KeyError(4)])])


try:
    batch()
except* ValueError as eg:
    inner = eg.exceptions[1]
    print("ValueError:", eg.message, [type(e).__name__ for e in eg.exceptions],
          repr(inner.message) if isinstance(inner, BaseExceptionGroup) else None)
except* (TypeError, KeyError) as eg:
    print("Type/Key:", sorted(type(e).__name__ for e in eg.exceptions))

try:
    try:
        batch()
    except* ValueError:
        print("handled the ValueErrors")
except ExceptionGroup as rest:
    print("rest:", rest.message, [type(e).__name__ for e in rest.exceptions],
          [type(e).__name__ for e in rest.exceptions[1].exceptions])

try:
    raise KeyError("bare")
except* KeyError as eg:
    print("bare:", type(eg).__name__, repr(eg.message), [e.args for e in eg.exceptions])

group = ExceptionGroup("g", [ValueError("a"), OSError("b"), ExceptionGroup("n", [ValueError("c")])])
match_, rest_ = group.split(ValueError)
print("split:", match_ is not None and [type(e).__name__ for e in match_.exceptions],
      rest_ is not None and [type(e).__name__ for e in rest_.exceptions])
sub = group.subgroup(lambda e: isinstance(e, OSError))
print("subgroup:", sub is not None and [e.args for e in sub.exceptions])
