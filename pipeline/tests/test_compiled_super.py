"""super() compiled against CPython (step 3b of the C++ leg starts with it; docs/emitter.md).

The zero-argument form is the frontend's `super` intrinsic, checked against CPython under eval1 by
pipeline/tests/test_l1_classes.py; here the same program runs compiled, with the super objects of
runtime/src/super.cpp, and so do the patterns real code uses: cooperative __init__ and
__init_subclass__, object's methods through super (whose binding found object.__setattr__ and
__delattr__ unbindable), properties, the empty __class__ cell, and a super that outlives the
object it names. The runtime's words are part of what is compared (stdout, as the review tests
do), with the exit status.

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_super
"""
from __future__ import annotations

from pipeline.tests.test_l1_classes import SUPER
from pipeline.tests.test_review_2026_11_03 import same

PATTERNS = """
class D:
    def __init__(self, n): self.n = n
    def __del__(self): print('del', self.n)
class Base:
    def __init_subclass__(cls, **kw):
        print('init_subclass', cls.__name__, kw)
        super().__init_subclass__()
    def __setattr__(self, k, v):
        print('setattr', k)
        super().__setattr__(k, v)
    def __repr__(self):
        return 'Base:' + super().__repr__()[:9]
    def __eq__(self, o):
        return super().__eq__(o)
    __hash__ = object.__hash__
class Kid(Base, tag='t'):
    def __init__(self):
        self.x = D('x')
        super().__init__()
k = Kid()
print(k.x.n, repr(k)[:14], k == k, k == 1, type(super(Kid, k).__eq__(1)).__name__)
class Prop:
    @property
    def v(self): return 1
class PropKid(Prop):
    @property
    def v(self): return super().v + 1
print(PropKid().v, super(PropKid, PropKid()).v)
class Early:
    def m(self):
        try:
            return super()
        except RuntimeError as e:
            print('RuntimeError', e)
    m(None)
s = super(Kid, k)
del k
print('k deleted, super still holds it:', type(s.__self__).__name__)
del s
print('end')
"""

OBJECT_SETATTR = """
class C:
    pass
c = C()
object.__setattr__(c, 'x', 1)
print(c.x)
object.__delattr__(c, 'x')
print(hasattr(c, 'x'))
for f in (lambda: object.__setattr__(c), lambda: object.__setattr__(c, 1, 2), lambda: object.__delattr__(c, 'nope'), lambda: c.__setattr__('y', 2)):
    try:
        print(f())
    except Exception as e:
        print(type(e).__name__, e)
print(vars(c))
class Guard:
    def __setattr__(self, k, v):
        print('guard', k)
        super().__setattr__(k, v)
    def __delattr__(self, k):
        print('guard del', k)
        super().__delattr__(k)
g = Guard()
g.a = 1
del g.a
print(vars(g))
"""

ERRORS = """
class A:
    pass
s = super(int, 1)
for f in (lambda: super(int, 1, 2), lambda: super(int, obj=1), lambda: super.__init__(s, 1, 2, 3), lambda: super.__init__(s, 1),
          lambda: super(1), lambda: setattr(s, '__self__', 2), lambda: delattr(s, '__thisclass__'), lambda: setattr(s, 'x', 1),
          lambda: super(A, 1), lambda: super(A, int), lambda: super.__new__(super)):
    try:
        print(repr(f()))
    except Exception as e:
        print(type(e).__name__, e)
"""


def test_zero_argument_super_compiled() -> None:
    same(SUPER)


def test_super_in_cooperative_code() -> None:
    same(PATTERNS)


def test_object_setattr_binds_as_a_method() -> None:
    same(OBJECT_SETATTR)


def test_super_errors_are_cpythons() -> None:
    same(ERRORS)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
