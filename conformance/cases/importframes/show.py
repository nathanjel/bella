"""The running stack as base names of files, lines and functions, and a traceback's entries."""
import traceback


def where(filename: str) -> str:
    return filename.rsplit("/", 1)[-1]


def stack(label: str) -> None:
    print(label, [(where(e.filename), e.lineno, e.name) for e in traceback.extract_stack()[:-1]])


def entries(label: str, e: BaseException) -> None:
    print(label, type(e).__name__, [(where(t.filename), t.lineno, t.name) for t in traceback.extract_tb(e.__traceback__)])
