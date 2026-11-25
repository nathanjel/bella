"""A module whose body raises at its first import only, after it gave away a function: that function keeps the first
attempt's namespace, which the second attempt's module does not share."""
import sys

from dyingpkg.watch import Marker, attempts, kept, watched

attempt = len(attempts) + 1
attempts.append(attempt)
held = Marker("fails_once.held" + str(attempt))


def which() -> int:
    return attempt


kept.append(which)
watched(sys.modules[__name__], "fails_once" + str(attempt))
if attempt == 1:
    raise ValueError("fails_once")
