"""The import system's fixture package (C-8-10): its body runs when an import first reaches it."""
print("imppkg: body runs;", __name__, __package__, __spec__.name, type(__path__).__name__, len(__path__))
from . import plain  # noqa: E402  -- after the print on purpose: the submodule loads while the package initialises

print("imppkg: plain bound:", plain.X, "| plain in the package namespace:", "plain" in globals())
