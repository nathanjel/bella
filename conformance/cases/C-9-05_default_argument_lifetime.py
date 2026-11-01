# clause: C-9-05
# spec: section 9 (D-19 is limited to module objects)
# status: P1
# source: review round 3, finding 5 (a function's defaults die with the function)
"""Deleting a function releases its default values: functions are ordinary reference-counted objects."""


class Resource:
    def __del__(self) -> None:
        print("resource released")


def consume(resource: Resource = Resource()) -> None:
    pass


print("before del")
del consume
print("after del")
