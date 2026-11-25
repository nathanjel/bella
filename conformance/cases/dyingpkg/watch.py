"""C-9-14's log, shared by the case and the modules it imports: a marker whose finaliser says it died, what the failing
imports keep, and how often an import that fails at its first attempt was tried."""
import weakref
from collections.abc import Callable

deaths: list[str] = []
kept: list[Callable[[], int]] = []
modules: list[weakref.ref[object]] = []
attempts: list[int] = []


class Marker:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        deaths.append(self.name)


def watched(module: object, name: str) -> None:
    """A weak reference to a module, whose callback says it died."""
    modules.append(weakref.ref(module, lambda ref: deaths.append(name + " callback")))
