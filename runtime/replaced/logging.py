"""The functions of logging (CPython 3.15.2, Lib/logging/__init__.py) that its adaptation replaces (manifest.toml
[adaptations] and [replaced]): each def stands for the one of the same qualified name, whose signature it repeats; the
frontend puts its body there and keeps CPython's docstring (pipeline/l1/frontend.py, replace_functions).

findCaller walks the call sites the compiler gives each frame (its file, the line it is at, its function's name), this
frame's first, where CPython walks frame objects (E-02): the same walk, the same test of _is_internal_frame on each file,
and with stack_info the stack as traceback.print_stack prints it, file and line (D-06)."""
# ruff: noqa: N802


class Logger:
    def findCaller(self, stack_info=False, stacklevel=1):  # type: ignore[no-untyped-def]
        sites = __bella_call_sites__()  # type: ignore[name-defined]  # noqa: F821  # [(file, line, name)], this frame's first
        if not sites:
            return "(unknown file)", 0, "(unknown function)", None
        at = 0
        while stacklevel > 0:
            if at + 1 >= len(sites):
                break
            at += 1
            filename = os.path.normcase(sites[at][0])  # type: ignore[name-defined]  # noqa: F821  # _is_internal_frame
            if not (filename == _srcfile or ("importlib" in filename and "_bootstrap" in filename)):  # type: ignore[name-defined]  # noqa: F821
                stacklevel -= 1
        sinfo = None
        if stack_info:
            sinfo = "Stack (most recent call last):\n" + "".join(
                f'  File "{file}", line {line}, in {name}\n' for file, line, name in reversed(sites[at:]))
            if sinfo[-1] == '\n':
                sinfo = sinfo[:-1]
        return sites[at][0], sites[at][1], sites[at][2], sinfo
