"""Regression tests for the reviews of tracebacks, dicts and operators, `f12af86..e827a47`
(astra-low 10 and gemini-4-argon-high 09; docs/reviews/review-log.md, RL-228 on).

Each reviewer's program is compiled (pipeline/build.py) and run; stdout and the exit status must be
CPython's, with PYTHONHASHSEED=0 in both, and for the reports stderr too (with the harness's D-06
mask). The programs found while fixing them follow, under the ids the review log gives them.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_03b
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_compiled import same_report
from pipeline.tests.test_review_2026_11_03 import same

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-229', 'context_reuse', "e=ValueError('v')\nfor cls in (KeyError,TypeError):\n    try:\n        try: raise cls('outer')\n        except Exception: raise e\n    except ValueError as caught:\n        print(type(caught.__context__).__name__)\n"),
    ('RL-229', 'context_cycle', "a=ValueError('a');b=TypeError('b')\ntry:\n    try: raise a\n    except ValueError: raise b\nexcept TypeError:\n    try: raise a\n    except ValueError:\n        print(a.__context__ is b,b.__context__ is None)\n"),
    ('RL-230', 'cause_validation', "try: raise ValueError('v') from 1\nexcept Exception as e: print(type(e).__name__)\n"),
    ('RL-230', 'cause_suppress', "e=ValueError('v')\ne.__cause__=KeyError('k')\nprint(e.__suppress_context__)\n"),
    ('RL-230', 'cause_assign_bad', "e=ValueError('v')\nfor name in ('__cause__','__context__','__traceback__'):\n    try:setattr(e,name,1);print('accepted')\n    except TypeError:print('TypeError')\n"),
    ('RL-230', 'raise_from_int', 'try:\n    raise ValueError("bad") from 123\nexcept TypeError as e:\n    print("Caught TypeError:", e)\nexcept ValueError as e:\n    print("Caught ValueError; cause is:", repr(e.__cause__))\n'),
    ('RL-230', 'fields_not_in_dict', "e=ValueError('x')\nprint(vars(e))\ne.__suppress_context__=True\nprint(vars(e))\ntry: e.__suppress_context__=1\nexcept TypeError as t: print('TypeError', t)\nfor n in ('__cause__','__context__','__traceback__','args','__suppress_context__'):\n    try: delattr(e,n); print('deleted',n)\n    except TypeError as t: print('TypeError',t)\ne.args=[1,2]\nprint(e.args, type(e.args).__name__)\ne.__cause__=None\nprint(e.__suppress_context__)\n"),
    ('RL-230', 'fields_die_after_the_dict', "class D:\n    def __init__(self,n): self.n=n\n    def __del__(self): print('del',self.n)\nclass X(Exception):\n    def __del__(self): print('del',self.args[0])\nclass E(Exception):\n    __slots__=('s',)\ne=E(D('arg'))\ne.s=D('slot')\ne.x=D('dictval')\ne.__cause__=X('cause')\ne.__context__=X('context')\nprint(e.__suppress_context__, list(vars(e)))\ndel e\nprint('end')\n"),
    ('RL-232', 'dict_store_raise', "class V:\n    def __del__(self): print('del value')\nclass K:\n    def __hash__(self): return 1\n    def __eq__(self,o): raise ValueError('eq')\nd={K():1}\ntry: d[K()]=V()\nexcept ValueError: print('caught')\nprint('after')\nd.clear()\n"),
    ('RL-233', 'dict_setdefault_change', "count=0\nclass K:\n    def __hash__(self):return 1\n    def __eq__(self,o):\n        global count\n        count+=1\n        return count==2\nd={K():1}\nprint(d.setdefault(K(),2),list(d.values()),count)\n"),
    ('RL-234', 'dict_pop_effect', "d={};calls=0\nclass K:\n    def __hash__(self):\n        global calls\n        calls+=1\n        if calls==3: raise ValueError('extra hash')\n        return 1\nk=K();d[k]=4\ntry: print(d.pop(k))\nexcept ValueError: print('ValueError')\nprint(len(d))\n"),
    ('RL-234', 'dict_pop_eq', 'd = {}\nmutated = False\nclass Key:\n    def __init__(self, name):\n        self.name = name\n    def __hash__(self):\n        return 42\n    def __eq__(self, other):\n        global mutated\n        if self.name == "k1" and getattr(other, "name", None) == "k2" and not mutated:\n            mutated = True\n            d[self] = "mutated_value"\n            return True\n        return getattr(self, "name", None) == getattr(other, "name", None)\nk1 = Key("k1")\nk2 = Key("k2")\nd[k1] = "orig_val"\nres = d.pop(k2)\nprint("pop:", res, "len:", len(d))\n'),
    ('RL-234', 'empty_pop_hashes_nothing', "for f in (lambda: {}.pop([]), lambda: {}.pop([], 'dflt'), lambda: {1:2}.pop([])):\n    try: print(f())\n    except Exception as e: print(type(e).__name__, e)\n"),
    ('RL-235', 'dict_copy_eq', "class K:\n    def __hash__(self):return 1\n    def __eq__(self,o):print('eq');return False\nd={K():1,K():2}\nprint('copy')\ne=d.copy()\nprint(len(e))\n"),
    ('RL-236', 'dict_fromkeys_hash', "class K:\n    def __hash__(self):print('hash');return 1\nk=K();d={k:1}\nprint('copy')\ne=dict.fromkeys(d,2)\nprint(len(e))\nprint(len(dict.fromkeys({k}, 3)))\n"),
    ('RL-237', 'iter_same_size', "d={'a':1,'b':2};it=iter(d)\nprint(next(it))\ndel d['a'];d['c']=3\nprint(next(it))\ntry:print(next(it))\nexcept Exception as e:print(type(e).__name__)\ntry:print(next(it))\nexcept Exception as e:print(type(e).__name__)\n"),
    ('RL-237', 'dict_version', 'd = {1: "a"}\ntry:\n    for k in d:\n        if k == 1:\n            del d[1]\n            d[2] = "b"\n        print("Saw:", k)\nexcept RuntimeError as e:\n    print("Caught RuntimeError:", e)\nv = {1: 1}\nfor k in v:\n    v[k] = 2\nprint(v)\n'),
    ('RL-238', 'handler_match_error', "try:\n    try: raise ValueError('v')\n    except (ValueError,42): print('matched')\nexcept Exception as e: print(type(e).__name__)\ntry:\n    try: raise ValueError('v')\n    except ((ValueError,),): print('matched')\nexcept Exception as e: print(type(e).__name__)\n"),
    ('RL-239', 'list_contains_raise', "class K:\n    def __eq__(self,o):raise ValueError('v')\n    def __del__(self):print('del')\na=[K()]\ntry: 1 in a\nexcept ValueError: print('caught')\ndel a\nprint('after')\n"),
    ('RL-240', 'keyword_only_count', "def f(a,/,b,*,c):pass\ntry:f(1,2,3,c=4)\nexcept TypeError as e:print(str(e))\ndef g(a,*,c):pass\ntry:g(1,2,c=4)\nexcept TypeError as e:print(str(e))\n"),
    ('RL-241', 'list_remove_uaf', 'a = []\nclass Key:\n    def __init__(self, name):\n        self.name = name\n    def __eq__(self, other):\n        a.clear()\n        return True\nk1 = Key("k1")\nk2 = Key("k2")\na.append(k1)\na.remove(k2)\nprint("Done, len:", len(a))\n'),
    ('RL-242', 'extend_self', 'a = [1, 2]\na.extend(a)\nprint("Done:", a)\nb = [3]\nb += b\nprint(b)\n'),
    ('RL-243', 'count_uaf', 'l = []\nclass Key:\n    def __init__(self, name):\n        self.name = name\n    def __del__(self):\n        print("del", self.name)\n    def __eq__(self, other):\n        print("eq", self.name)\n        l.clear()\n        return False\nk1 = Key("k1")\nk2 = Key("k2")\nl.extend([k1, k2])\ndel k1; del k2\ntarget = Key("target")\nprint("calling count:")\nl.count(target)\nprint("done")\n'),
    ('RL-244', 'new_without_arguments', 'MethodType = type((lambda: None).__get__(1))\nfor t in (MethodType, slice, BaseException):\n    for args in ((), (1,), (int,)):\n        try:\n            t.__new__(*args)\n        except TypeError as e:\n            print(e)\n'),
    ('RL-245', 'iter_none', 'class NotIterable:\n    __iter__ = None\n    def __getitem__(self, i):\n        return i\nclass NotContainer:\n    __contains__ = None\n    def __iter__(self):\n        return iter([1])\nclass Neither:\n    pass\ndef f(*a):\n    return a\nfor thunk in (lambda: iter(NotIterable()), lambda: f(*NotIterable()), lambda: list(NotIterable()), lambda: 1 in NotIterable(), lambda: 1 in NotContainer(), lambda: 1 in Neither()):\n    try:\n        print(thunk())\n    except TypeError as e:\n        print("TypeError", e)\n'),
    ('RL-246', 'qualname_init', 'class Outer:\n    class C: pass\nc = Outer.C()\ntry:\n    object.__init__(c, 1, 2)\nexcept TypeError as e:\n    print(e)\n'),
    ('RL-247', 'pop_empty', 'l = []\nclass Idx:\n    def __index__(self):\n        l.clear()\n        return 0\nl.extend([10, 20])\ntry:\n    l.pop(Idx())\nexcept IndexError as e:\n    print(e)\ntry:\n    [].pop("x")\nexcept TypeError:\n    print("TypeError")\n'),
    ('RL-248', 'containers_unhashable', "for v in ([], {}, set(), {}.keys(), {}.items(), {}.values(), (1, 2)):\n    try:\n        print(type(v).__name__, 'hashable', type(hash(v)).__name__)\n    except TypeError as e:\n        print(type(v).__name__, 'TypeError', e)\nprint(list.__hash__, dict.__hash__, set.__hash__)\n"),
    ('RL-249', 'unhashable_key_words', "class C:\n    __hash__ = None\nfor f in (lambda: {C(): 1}, lambda: {1: 2}[C()], lambda: {C()}, lambda: hash(C()), lambda: {1:2}.get([]), lambda: [] in {1:2}, lambda: {1:2}.setdefault([]), lambda: {1} - {[]} if False else set().add([])):\n    try:\n        f()\n    except TypeError as e:\n        print(e)\n"),
    ('RL-251', 'member_descriptor_type', "class C:\n    __slots__ = ('x',)\nd = C.__dict__['x']\nprint(type(d).__name__, type(d) is type(C.__dict__['x']))\n"),
    ('RL-252', 'resize_compares_once', "calls = 0\nclass K:\n    def __init__(self, n): self.n = n\n    def __hash__(self): return 1\n    def __eq__(self, o):\n        global calls\n        calls += 1\n        return self.n == o.n\nd = {}\nfor i in range(5):\n    d[K(i)] = i\ncalls = 0\nd[K(5)] = 5\nprint(calls)\n"),
    ('RL-253', 'merge_paths', "src = {}\nclass K:\n    def __init__(self, n): self.n = n\n    def __hash__(self): return 1\n    def __eq__(self, o):\n        print('eq', self.n, o.n)\n        src.pop(self, None)\n        return False\ntarget = {K(0): 0}\nsrc[K(1)] = 1\nsrc[K(2)] = 2\ntry:\n    target.update(src)\nexcept RuntimeError as e:\n    print('RuntimeError', e)\nprint(len(target), len(src))\nclean = {K(3): 3, K(4): 4}\nprint('merge into an empty dict')\nm = {**clean}\nprint(len(m), len(clean | {}))\n"),
]


# The reports: stderr compared too (A10-1, A10-4, and the report's type name, RL-250)
REPORTS = {
    'RL-228 a handler header is matched at its line': """
        def f():
            try:
                raise ValueError('v')
            except missing:
                pass
        f()
        """,
    'RL-228 an invalid except tuple fails at its line': """
        def f():
            try:
                raise ValueError('v')
            except (ValueError, 42):
                pass
        f()
        """,
    "RL-231 an exception whose __str__ raises": """
        class E(Exception):
            def __str__(self): raise ValueError('str failed')
        raise E()
        """,
    "RL-231 the unraisable report too, even for a SystemExit from __str__": """
        class E(Exception):
            def __str__(self): raise SystemExit(3)
        class C:
            def __del__(self): raise E()
        c = C()
        del c
        print('after')
        """,
    "RL-250 the report names the class by its qualified name": """
        class Outer:
            class E(Exception):
                pass
        class C:
            def __del__(self):
                raise Outer.E('in del')
        c = C()
        del c
        try:
            raise ValueError('first')
        except ValueError:
            raise Outer.E('top')
        """,
}


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{fid}-{name}" for fid, name, _ in FINDINGS])
    if "report" in metafunc.fixturenames:
        metafunc.parametrize("report", list(REPORTS), ids=list(REPORTS))


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


def test_report(report: str) -> None:
    same_report(REPORTS[report])


def test_stores_to_fields_cpython_has_are_refused() -> None:
    """A field of CPython's type that the runtime lacks is refused when stored or deleted, as when
    read, never put in the __dict__ (RL-255; StopIteration.value was the example until it arrived; __code__ exists since
    v0.14, C-3-46, so a store of a code object is the example: the function from a code object is E-07)."""
    if shutil.which("g++") is None:
        return
    for body in ("def f():\n    pass\ndef g():\n    pass\nf.__code__ = g.__code__",):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr, (body, got)


if __name__ == "__main__":
    for finding in FINDINGS:
        test_finding(finding)
    for report in REPORTS:
        test_report(report)
    test_stores_to_fields_cpython_has_are_refused()
    print("ok")
