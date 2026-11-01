# clause: C-8-01
# spec: section 8
# status: P1
# source: review round 2, finding 6 (a.x raises AttributeError, from a import x raises ImportError)
"""Import cycle: the partially initialised module is returned; unbound names raise per access form."""
import cycpkg.a

print("main: X =", cycpkg.a.X)
