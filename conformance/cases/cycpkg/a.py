print("a: start")
import cycpkg.b  # noqa: E402,F401  -- re-enters this module while it is initialising

print("a: after importing b")
X = 1
print("a: end")
