"""Review A27 of 2026-11-21 (range 369abde..ebf460e), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read the bounded lru_cache's links (RL-600) and the fixes of review A26; the review log has
its seven findings as RL-614 to RL-620. Held here: the order in which the cache lets go when a store fails after the
oldest link was taken out (RL-614), the warnings the runtime gives itself against a program that replaces the names
of `_warnings` (RL-615), `maxsize` as an index by its type's slot (RL-616), and the program that reaches the pop of the
oldest link, which RL-600's row did not (RL-619). RL-618 and RL-620 are the harness's own
(conformance/tests/test_harness.py); RL-617 is open.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21_a27
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_start_up_environment import _plain_environment, _sides

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-614', 'a store that fails after the oldest link went lets go of the link, the old key, the old result', r'''
import functools
class K:
    def __init__(self,n): self.n=n
    def __hash__(self): return 0
    def __eq__(self,o):
        if armed and self.n==1 and o.n==2:
            count.append(1)
            if len(count)==3: raise ValueError
        return self.n==o.n
    def __del__(self): print('key',self.n)
class R:
    def __init__(self,n): self.n=n
    def __del__(self): print('result',self.n)
@functools.lru_cache(2)
def f(k): return R(k.n)
armed=False
count=[]
f(K(0))
f(K(1))
armed=True
try: f(K(2))
except ValueError: print('caught',tuple(f.cache_info()))   # reaches: caught (0, 3, 2, 1)
f.cache_clear()
print('---- and where the function itself raises, or the first store does')
@functools.lru_cache(2)
def g(k):
    if k.n == 9: raise KeyError(k.n)
    return R(k.n * 10)
armed=False
g(K(5))
try: g(K(9))
except KeyError: print('caught', tuple(g.cache_info()))
count.clear()
class First(K):
    __hash__ = K.__hash__
    def __eq__(self,o):
        if armed:
            count.append(1)
            if len(count)==2: raise ValueError
        return self.n==o.n
@functools.lru_cache(3)
def h(k): return R(k.n * 100)
h(First(1))
armed=True
try: h(First(2))
except ValueError: print('caught', tuple(h.cache_info()))   # reaches: caught (0, 2, 3, 1)
armed=False
print('---- cleared')
g.cache_clear()
h.cache_clear()
print('---- the end')
'''),
    ('RL-616', 'maxsize is an index by its type\'s slot: no metaclass is asked', r'''
from functools import lru_cache
from _functools import _lru_cache_wrapper
class Meta(type):
    def __getattr__(cls,name):
        print('lookup',name)
        return 1
class Size(metaclass=Meta): pass
try: _lru_cache_wrapper(len, Size(), False, tuple)
except Exception as e: print(type(e).__name__,str(e))
class Raising(type):
    @property
    def __index__(cls):
        raise ValueError('class lookup')
class Two(int, metaclass=Raising): pass
try: print(lru_cache(Two(2))(len)('a'))       # reaches: 1
except Exception as e: print(type(e).__name__,str(e))
class Index:
    def __index__(self): return 3
try: print(_lru_cache_wrapper(len, Index(), False, tuple).cache_info())
except Exception as e: print(type(e).__name__,str(e))
class Late: pass
late = Late()
late.__index__ = lambda: 3                    # on the object: no slot of the type's
try: _lru_cache_wrapper(len, late, False, tuple)
except Exception as e: print(type(e).__name__,str(e))
'''),
    ('RL-619', 'a comparison that fails inside the pop of the oldest link puts it back as the oldest', r'''
from functools import lru_cache
class K:
    def __init__(self,n): self.n=n
    def __hash__(self): return 0
    def __eq__(self,other):
        if armed and self.n=='a' and other.n==target:
            print('raise',self.n,other.n)
            raise ValueError
        return self.n==other.n
@lru_cache(2)
def f(k): return k.n
a,b,c=K('a'),K('b'),K('c')
for target in ('c','b'):
    armed=False
    f(a); f(b); f(a)
    armed=True
    try: f(c)
    except ValueError: print('caught',tuple(f.cache_info()))
    armed=False
    f(c); f(a)
    print('after retry',tuple(f.cache_info()))
    f.cache_clear()
# the miss count at the catch says where the comparison failed: 2 at the lookup, 3 inside the pop
# reaches: caught (1, 3, 2, 2)
# reaches: after retry (2, 4, 2, 2)
'''),
    ('RL-615', 'the warnings the runtime gives itself are not the names a program put into _warnings', r'''
import _warnings, warnings
def replacement(*args, **kwds): print("the replacement was called")
with warnings.catch_warnings(record=True) as seen:
    warnings.simplefilter("always")
    _warnings.warn = replacement
    _warnings.warn_explicit = replacement
    f = open(__file__)
    del f                                      # a ResourceWarning, by the C's own function
    print("recorded:", [(w.category.__name__, str(w.message).split("<")[0]) for w in seen])   # reaches: recorded: [('ResourceWarning'
    _warnings.warn("by the name")              # and the name is the program's
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


def test_the_starts_warnings_are_given_by_the_function_the_runtime_kept() -> None:
    """RL-615, the report's two files: a warnings.py of the program's own, imported for the first of the compiler's
    warnings, puts another function under `_warnings.warn_explicit`. CPython's parser calls the C function and gives the
    second warning as it gave the first; so does the start."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("a='\\q'\nb='\\z'\nimport _warnings\nprint('body', _warnings.warn_explicit.__name__)\n", encoding="utf-8")
        Path(tmp, "warnings.py").write_text("import _warnings\ndef replacement(*args): print('replacement', args[3])\n"
                                            "_warnings.warn_explicit = replacement\n", encoding="utf-8")
        reference, compiled = _sides(str(build(prog, "prog.py", notes=False)), _plain_environment(), tmp)
        assert compiled == reference, (compiled, reference)
        assert reference[:2] == (0, b"body replacement\n") and reference[2].count(b"SyntaxWarning: ") == 2, reference


if __name__ == "__main__":
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
    test_the_starts_warnings_are_given_by_the_function_the_runtime_kept()
