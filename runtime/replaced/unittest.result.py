"""The function of unittest.result (CPython 3.15.2, Lib/unittest/result.py) that its adaptation replaces (manifest.toml
[adaptations] and [replaced]): the def stands for the one of the same qualified name, whose signature it repeats; the
frontend puts its body there and keeps CPython's docstring (pipeline/l1/frontend.py, replace_functions).

TestResult._is_relevant_tb_level tells unittest's own entries of a traceback by the globals of the frame each stands for,
which CPython reads off the frame (E-02): the entry's module's dict (`__bella_traceback_globals__`). What is no
traceback's entry is read as CPython reads it."""


class TestResult:
    def _is_relevant_tb_level(self, tb):  # type: ignore[no-untyped-def]
        f_globals = __bella_traceback_globals__(tb)  # type: ignore[name-defined]  # noqa: F821  # the entry's module's dict, else None
        return '__unittest' in (f_globals if f_globals is not None else tb.tb_frame.f_globals)
