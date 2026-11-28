# clause: X-4-01
# spec: section 4
# status: X
# expect: E-01
# source: dialect specification v0.52 section 4 (eval of a text the dry run did not stage; Question 57)
"""The program must stop by name with E-01 at the eval: the call is in the `if __name__ == "__main__":` block, which the
dry run does not run (it imports the program under another name), so no dry run staged its text; CPython runs it. A
staged text runs (C-8-24)."""
if __name__ == "__main__":
    value = eval("1 + 1")  # noqa: S307
    print(value)
