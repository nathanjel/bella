import sys


def down(n: int) -> int:
    try:
        return down(n + 1)
    except RecursionError:
        return n


limit = sys.getrecursionlimit()
sys.setrecursionlimit(60)
reached = down(0)
sys.setrecursionlimit(limit)
print("depth", reached)
