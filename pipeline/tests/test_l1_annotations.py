"""Gate 0 task 4, step A6: module and class annotations (PEP 649, desugar-annotations) and PEP
695 generic scopes and aliases (desugar-type-params), eval1 against CPython.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_annotations
"""
from __future__ import annotations

from pipeline.tests.test_frontend_eval1 import both

ANNOTATIONS = '"""module doc"""\nimport sys\nx: int = 1\ny: "later"\ncond = True\nif cond:\n    z: float\nelse:\n    w: str\nprint(__doc__, sorted(k for k in globals() if k.startswith("__") and k not in ("__builtins__", "__loader__", "__spec__", "__package__", "__file__", "__cached__")))\nprint(__annotate__(1), __conditional_annotations__, __annotate__.__qualname__)\nmod = sys.modules[__name__] if __name__ in sys.modules else None\nclass C:\n    """class doc"""\n    a = int\n    b: a\n    __p: str = "private"\n    if cond:\n        c: list\n    def m(self, p: a) -> "ret":\n        pass\n    o = type("O", (), {})()\n    o.attr: int = 5\nprint(C.__annotations__, C.m.__annotations__, C.__annotate__.__qualname__, "__annotate_func__" in vars(C), C.o.attr)\nclass R(dict):\n    def __setitem__(self, k, v):\n        print("store", k)\n        super().__setitem__(k, v)\nclass M(type):\n    @classmethod\n    def __prepare__(m, n, b): return R()\nclass D(metaclass=M):\n    q: int = 1\nclass E:\n    pass\nprint(E.__annotations__)\ndef f():\n    v: int\n    try:\n        return v\n    except UnboundLocalError:\n        return "UnboundLocalError"\nprint(f())\ntry:\n    class Fwd:\n        a: Missing\n    print(Fwd.__annotations__)\nexcept NameError as exc:\n    print("NameError", exc.name)\n'

TYPE_PARAMS = 'def d(f):\n    print("decorating", f.__name__)\n    return f\n@d\ndef f[T: int, *Ts, **P = [int]](x: T) -> T:\n    return x\nprint(f(3), f.__name__, f.__qualname__, [type(t).__name__ for t in f.__type_params__], [t.__name__ for t in f.__type_params__])\nT = f.__type_params__[0]\nprint(T.__bound__, T.__module__, f.__type_params__[2].__default__, f.__annotations__)\ntype A[K] = list[K]\ntype B = dict[str, "later"]\nprint(type(A).__name__, A.__name__, A.__module__, A.__type_params__, A.__value__, B.__value__, B.__type_params__)\nclass Base:\n    pass\nclass C[U](Base):\n    def m[V](self, v: V) -> U:\n        return v\n    type Inner = U\nprint(C.__type_params__, [b.__name__ for b in C.__mro__], C.__orig_bases__, C.m.__qualname__, C.m.__type_params__, C.Inner.__value__)\nprint(C[int], C.m.__annotations__)\nclass W[X: (int, str)]:\n    pass\nprint(W.__type_params__[0].__constraints__)\nlazy_alias_evaluated = []\ndef make():\n    lazy_alias_evaluated.append(1)\n    return int\ntype Lazy = make()\nprint(lazy_alias_evaluated, Lazy.__value__, lazy_alias_evaluated)\n'


ONLY_NESTED = """
TYPE_CHECKING = False
if TYPE_CHECKING:
    pass
else:
    try:
        x: int = 1
    except ImportError:
        pass
print(__annotate__(1), __conditional_annotations__)
class C:
    if True:
        a: str = "s"
print(C.__annotations__)
"""


def check(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_module_and_class_annotations_as_pep_649_compiles_them() -> None:
    check(ANNOTATIONS)


def test_pep_695_generic_scopes_and_aliases() -> None:
    check(TYPE_PARAMS)


def test_a_module_whose_annotations_are_all_nested_still_tracks_them() -> None:
    """Found with data_easy_sales (a vendored module): the conditional set was made only when an
    annotation stood at the top of the module."""
    check(ONLY_NESTED)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
