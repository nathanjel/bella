# clause: C-6-04
# spec: section 6
# status: P1
# source: review round 1, finding 6 (sorted is stable and evaluates key once per element)
"""sorted(key=) calls the key exactly once per element and keeps the order of equal keys."""
calls = 0


def key(item: tuple[int, str]) -> int:
    global calls
    calls += 1
    return item[0]


data = [(1, "a"), (0, "b"), (1, "c"), (0, "d"), (1, "e")]
print(sorted(data, key=key))
print("key calls:", calls, "== len:", calls == len(data))
print("reverse keeps stability:", sorted(data, key=key, reverse=True))
