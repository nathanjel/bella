# clause: C-3-06
# spec: section 3
# status: P1
# source: review round 3, finding 3 (an attribute assigned into an inline field shadows a cached class attribute)
"""Instance storage shadows a plain class attribute; deletion reveals the class attribute again."""


class C:
    x = 1


def read(obj: C) -> int:
    return obj.x


c = C()
print(read(c))
c.x = 2
print(read(c))
del c.x
print(read(c))
try:
    del c.x
except AttributeError as exc:
    print("second delete:", type(exc).__name__, exc.name)
