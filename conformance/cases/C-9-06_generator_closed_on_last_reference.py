# clause: C-9-06
# spec: section 9
# status: P1
# source: dialect specification section 9 (generators are closed when their last reference is dropped)
"""A suspended generator is closed when its last reference goes: GeneratorExit, finally runs."""
from collections.abc import Iterator


def gen() -> Iterator[int]:
    try:
        yield 1
        yield 2
    except GeneratorExit:
        print("GeneratorExit delivered at the suspension point")
        raise
    finally:
        print("finally ran")


g = gen()
print("first:", next(g))
del g
print("after del")
