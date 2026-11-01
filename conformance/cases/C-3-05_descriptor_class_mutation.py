# clause: C-3-05
# spec: section 3
# status: P1
# source: review round 3, finding 3 (adding __set__ to a descriptor's class changes lookup precedence
#         without any change to the class that holds the descriptor)
"""A non-data descriptor shadowed by an instance attribute becomes a data descriptor and wins."""


class Desc:
    def __get__(self, obj: object, owner: object = None) -> int:
        return 1


class Holder:
    attr = Desc()


h = Holder()
h.__dict__["attr"] = 99
print("instance wins over non-data descriptor:", h.attr)


def set_(self: Desc, obj: object, value: object) -> None:
    pass


Desc.__set__ = set_  # type: ignore[attr-defined]  # Desc becomes a data descriptor; Holder does not change
print("data descriptor wins after promotion:", h.attr)
del Desc.__set__  # type: ignore[attr-defined]  # demotion, on purpose
print("instance visible again after demotion:", h.attr)
