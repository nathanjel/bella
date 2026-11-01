# clause: C-8-02
# spec: section 8
# status: P1
# source: review round 2, finding 6 (global lookup falls through to builtins after a global is deleted)
"""A module global shadows a builtin; deleting it makes the builtin visible again."""


def measure() -> int:
    return len([1, 2, 3])


print(measure())
len = lambda seq: -1  # noqa: E731  -- shadow the builtin with a module global
print(measure())
del len
print(measure())
try:
    print(undefined_name)  # noqa: F821
except NameError as exc:
    print("unbound global:", type(exc).__name__, exc.name)


def local_unbound() -> None:
    try:
        print(value)
    except UnboundLocalError as exc:
        print("unbound local:", type(exc).__name__, exc.name)
    value = 1  # noqa: F841


local_unbound()
