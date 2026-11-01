# clause: C-2-01
# spec: section 2
# status: P1
# source: review round 1, finding 6 (left-to-right evaluation, each operand once, chained comparisons)
"""Evaluation order is observable: left to right, each operand once, including in chained comparisons."""
trace: list[str] = []


def v(name: str, value: int) -> int:
    trace.append(name)
    return value


print(v("a", 1) < v("b", 2) < v("c", 3), trace)
trace.clear()
print(v("a", 3) < v("b", 2) < v("c", 1), trace)       # short-circuits: c never evaluated
trace.clear()


def call(*args: int, **kwargs: int) -> list[str]:
    return list(trace)


print(call(v("p", 1), v("q", 2), k=v("r", 3)))
trace.clear()
print([v("x", 1) + v("y", 2) for _ in range(1)], trace)
trace.clear()
print(v("l", 1) or v("never", 2), v("f", 0) and v("never", 2), trace)
