print("b: start")
import cycpkg.a as a  # the partially initialised module is returned as it stands

try:
    print(a.X)
except AttributeError as exc:
    print("b: attribute access ->", type(exc).__name__, "name =", exc.name)
try:
    from cycpkg.a import X  # noqa: F401
except ImportError as exc:
    print("b: from-import ->", type(exc).__name__, "name =", exc.name)
print("b: end")
