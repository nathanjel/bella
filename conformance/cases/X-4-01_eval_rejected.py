# clause: X-4-01
# spec: section 4
# status: X
# expect: E-01
# source: dialect specification section 4 (eval/exec of source text is a compile-time error)
"""The compiler must reject this file with E-01 at the line of the eval call; CPython runs it."""
value = eval("1 + 1")  # noqa: S307
print(value)
