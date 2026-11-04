# clause: C-9-09
# spec: section 9
# status: P1
# source: review 2026-11-04, RL-281 (finalize_modules: the collector runs finalisers while the namespaces are whole)
"""At exit a finaliser reads its module's globals, functions and classes, as they stand."""
import sys

LABEL: str = "label"


def helper() -> str:
    return "helper"


class Held:
    def __del__(self) -> None:
        print("finaliser", LABEL, helper(), type(sys).__name__, __name__, type(self).__name__, sys.path, sys.argv, len(sys.modules))


held: Held = Held()
print("end of module")
