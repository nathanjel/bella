"""Regression tests for the reviews of compiled super(), metaclasses, subclasses and imports,
`e827a47..62d083b` (gemini-4-argon-high 10 and the swarm of Sonnet reviewers S1;
docs/reviews/review-log.md, RL-256 on).

Each reviewer's program is compiled (pipeline/build.py) and run; stdout and the exit status must be
CPython's, with PYTHONHASHSEED=0 in both, and for the reports stderr too (with the harness's D-06
mask). A program of several modules goes through test_compiled_imports.same.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_04
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pipeline.build as build_module
from pipeline.build import build
from pipeline.closed_world import find_program_modules
from pipeline.tests.test_compiled import same_report
from pipeline.tests.test_compiled_imports import same as same_files
from pipeline.tests.test_review_2026_11_03 import same

# One module: (finding, name, program).
FINDINGS: list[tuple[str, str, str]] = [
    # ---- module type, ImportError, the bootstrap's presentation
    ('RL-270', 'module_dict_readonly', "import sys\nm = type(sys)('x')\ntry:\n    m.__dict__ = {}\nexcept AttributeError as e:\n    print(e)\nprint(list(vars(m)))\ntry:\n    del m.__dict__\nexcept (AttributeError, TypeError) as e:\n    print(type(e).__name__, e)\n"),
    ('RL-270', 'module_class_assignment', "import sys\nm = type(sys)('x')\nfor v in (5, int):\n    try:\n        m.__class__ = v\n    except TypeError as e:\n        print(e)\nprint(list(vars(m)), type(m).__name__)\n"),
    ('RL-271', 'relative_import_msg', "try:\n    from . import x\nexcept ImportError as e:\n    print(e.msg, e.args, e.name, e.path)\ntry:\n    __import__('x', {'__package__': 'a'}, None, [], 2)\nexcept ImportError as e:\n    print(e.msg, e.args, e.name, e.path)\n"),
    ('RL-271', 'missing_name_msg', "import sys\ntry:\n    from sys import nothing_here\nexcept ImportError as e:\n    print(e.msg == e.args[0], e.name, e.name_from)\ntry:\n    import no_such_module_here\nexcept ImportError as e:\n    print(e.msg, e.name, e.path)\n"),
    ('RL-272', 'module_docs', "import sys, builtins\nprint(type(sys).__doc__)\nprint(sys.__doc__)\nprint(builtins.__doc__)\nprint('__doc__' in vars(sys), '__doc__' in vars(builtins))\nprint(list(vars(sys))[:5])\nprint(list(vars(builtins))[:5])\n"),
    ('RL-273', 'namespace_attribute', "import types\nn = types.SimpleNamespace(a=1)\ntry:\n    n.q\nexcept AttributeError as e:\n    print(e)\ntry:\n    hash(n)\nexcept TypeError as e:\n    print(e)\ntry:\n    n < n\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-273', 'namespace_dict_readonly', "import types\nn = types.SimpleNamespace(a=1)\ntry:\n    n.__dict__ = {}\nexcept AttributeError as e:\n    print(e)\nprint(n)\n"),
    ('RL-273', 'namespace_arguments', "import types\nN = types.SimpleNamespace\nfor f in (lambda: N({}, {}), lambda: N(5), lambda: N({1: 2}), lambda: N(a=1).__replace__(5), lambda: N.__repr__(5), lambda: N.__init__(object())):\n    try:\n        print(f())\n    except Exception as e:\n        print(type(e).__name__, e)\n"),
    ('RL-276', 'lazy_import_other_globals', "if False:\n    import modx\ng = dict(globals())\nz = __lazy_import__('sys', g)\nprint(type(globals()['z']).__name__)\n"),
    ('RL-278', 'lazy_resolve_argument', "lazy import sys\nH = [globals()['sys']]\ntry:\n    H[0].resolve(1)\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-279', 'lazy_docs', "lazy import sys\nH = [globals()['sys']]\nprint(type(H[0]).__doc__)\nprint(H[0].__doc__)\n"),
    ('RL-280', 'read_only_builtin_attribute', "for v, name in (([], 'append'), ('', 'find'), ({}, 'get'), ((), 'count'), (set(), 'add')):\n    try:\n        setattr(v, name, 1)\n    except AttributeError as e:\n        print(e)\n    try:\n        delattr(v, name)\n    except AttributeError as e:\n        print(e)\ntry:\n    [].nothing = 1\nexcept AttributeError as e:\n    print(e)\n"),
    ('RL-280', 'read_only_int_real', "try:\n    (1).real = 1\nexcept AttributeError as e:\n    print(e)\ntry:\n    (1).__class__ = int\nexcept TypeError as e:\n    print(e)\n"),
    # ---- a hash is one number wherever it is read
    ('RL-321', 'hash_of_a_proxy_key', "class K:\n    def __init__(self, s):\n        self.s = s\n    def __hash__(self):\n        return hash(self.s)\n    def __eq__(self, other):\n        return self.s == other\nfound = missed = 0\nfor i in range(2000):\n    s = 'key' + str(i)\n    for ok in ({s: i}.get(K(s)) == i, {K(s): i}.get(s) == i, K(s) in {s}, s in {K(s)}, hash((K(s), 1)) == hash((s, 1)), hash(frozenset({K(s)})) == hash(frozenset({s}))):\n        if ok:\n            found += 1\n        else:\n            missed += 1\nprint(found, missed)\n"),
    ('RL-321', 'hash_of_a_hash_is_stable', "values = ['key' + str(i) for i in range(2000)]\nbad = 0\nfor v in values:\n    if hash(v) != hash(v) or hash(v) == -1:\n        bad += 1\nprint(bad, len({hash(v) for v in values}))\nprint(hash(''), hash(0), hash(-1), hash(True), hash(None))\n"),
    ('RL-321', 'hash_returns_an_int_subclass', "class I(int):\n    pass\nclass K:\n    def __init__(self, v):\n        self.v = v\n    def __hash__(self):\n        return self.v\nprint(hash(K(I(5))), hash(K(I(-1))), hash(K(True)), hash(K(-1)))\n"),
    # ---- sys.exit, SystemExit
    ('RL-282', 'exit_str_raises', "import sys\nclass X:\n    def __str__(self):\n        raise ValueError('no str')\nprint('before')\nsys.exit(X())\n"),
    ('RL-283', 'exit_code_attribute_subclass', "class E(SystemExit):\n    code = 13\n    def __init__(self):\n        pass\nraise E()\n"),
    ('RL-283', 'exit_args_rebound', "e = SystemExit(3)\ne.args = (11,)\nraise e\n"),
    ('RL-283', 'exit_code_rebound', "e = SystemExit(3)\ne.code = 9\nraise e\n"),
    ('RL-283', 'exit_code_read', "import sys\nfor a in ((), (1,), ('x',), (1, 2), (None,)):\n    e = SystemExit(*a)\n    print(e.code, e.args)\ntry:\n    sys.exit(4)\nexcept SystemExit as e:\n    print(e.code)\nprint(list(vars(SystemExit(1))))\n"),
    ('RL-283', 'exit_code_none', "class E(SystemExit):\n    code = None\nraise E(3)\n"),
    # ---- import *
    ('RL-286', 'range_index', "r = range(1, 7, 2)\nprint(r[0], r[-1], r[1:], r[::-1], r[:0])\ntry:\n    r[9]\nexcept IndexError as e:\n    print(e)\ntry:\n    r['a']\nexcept TypeError as e:\n    print(e)\nprint(list(r), len(r), 3 in r, r.index(3), r.count(3), r.start, r.stop, r.step)\n"),
    # ---- module(), lowering
    ('RL-288', 'module_arguments', "import sys\nM = type(sys)\nfor f in (lambda: M('a', name='b'), lambda: M(nme='n'), lambda: M(), lambda: M(1), lambda: M('a', 'd', 'x')):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\nprint(M('a', doc='d').__doc__, M('a').__doc__)\n"),
    ('RL-290', 'try_else_after_return', "def g():\n    return 1\ndef f():\n    try:\n        return g()\n    except ValueError:\n        print('v')\n    else:\n        print('else')\n    return 0\nprint(f())\n"),
    ('RL-290', 'try_else_after_raise', "def f():\n    try:\n        raise KeyError('k')\n    except KeyError:\n        print('k')\n    else:\n        print('else')\n    print('after')\n    return 0\nprint(f())\n"),
    ('RL-290', 'try_else_after_continue', "for i in (1, 2):\n    try:\n        continue\n    except ValueError:\n        print('v')\n    else:\n        print('else')\n    print('after')\nprint('end')\n"),
    ('RL-290', 'try_else_after_break_finally', "for i in (1, 2):\n    try:\n        break\n    except ValueError:\n        print('v')\n    else:\n        print('else')\n    finally:\n        print('f')\n    print('after')\nprint('end')\n"),
    ('RL-291', 'local_named_match', "def f():\n    match = 5\n    try:\n        raise ValueError()\n    except ValueError:\n        print(match)\n    return match\nprint(f())\n"),
    ('RL-291', 'global_named_match', "match = 7\ntry:\n    raise ValueError()\nexcept ValueError:\n    print(match)\ndef g(match):\n    try:\n        raise KeyError()\n    except KeyError:\n        return match\nprint(g(3))\n"),
    ('RL-292', 'contract_assert', "def f(contract_assert):\n    return contract_assert + 1\nprint(f(1))\npre = 1\npost = 2\nprint(pre + post)\n"),
    # ---- str
    ('RL-295', 'bad_argument_none', "for f in (lambda: 'abc'.find(None), lambda: 'abc'.rfind(None), lambda: 'abc'.index(None), lambda: 'abc'.rindex(None), lambda: 'abc'.count(None), lambda: 'abc'.replace(None, 'a'), lambda: 'abc'.replace('a', None), lambda: 'abc'.partition(None), lambda: 'abc'.split(1), lambda: 'abc'.strip(1), lambda: 'abc'.find(1)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-296', 'index_returns_non_int', "class B:\n    def __index__(self):\n        return 'x'\nfor f in (lambda: 'abc'.find('a', B()), lambda: [1][B()], lambda: 'ab' * B(), lambda: [1, 2][B():]):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-297', 'small_strings_shared', "print('a'.strip('a') is '', 'a'.partition('a')[0] is '', 'ab'.split('b')[0] is 'a', 'ab'.strip('b') is 'a', 'a'.replace('a', '') is '')\n"),
    ('RL-297', 'split_no_shortcut', "x = ''.join(['ab', 'c'])\nprint(x.split(None, 0)[0] is x, x.rsplit(maxsplit=0)[0] is x, x.split(maxsplit=0)[0] is x, x.split()[0] is x, x.split('q')[0] is x)\n"),
    ('RL-297', 'replace_one_char', "x = ''.join(['ab', 'c'])\nprint(x.replace('a', ''.join(['a'])) is x)\n"),
    ('RL-297', 'partition_empty', "e = ''.join([])\na = e.partition('a')\nb = e.rpartition('a')\nprint(a[0] is e, a[1] is e, a[2] is e, b[0] is e, b[1] is e, b[2] is e)\n"),
    # ---- dicts, lists, sets
    ('RL-298', 'popitem_compares_nothing', "yes = []\nclass M:\n    def __init__(self, n):\n        self.n = n\n    def __hash__(self):\n        return 7\n    def __eq__(self, o):\n        return True if yes else self is o\n    def __repr__(self):\n        return 'M' + str(self.n)\nd = {M(1): 1, M(2): 2}\nyes.append(1)\nprint(d.popitem())\nprint(d)\n"),
    ('RL-298', 'popitem_eq_raises', "class M:\n    armed = False\n    def __hash__(self):\n        return 7\n    def __eq__(self, o):\n        if M.armed:\n            raise ValueError('eq')\n        return self is o\na = M()\nd = {a: 1}\nM.armed = True\nprint(d.popitem()[1], len(d))\ntry:\n    {}.popitem()\nexcept KeyError as e:\n    print(e)\n"),
    ('RL-299', 'in_iterator', "print(1 in iter([1, 2]), 3 in iter([1, 2]), 'a' in iter('abc'), 1 in iter((1,)), 1 in iter({1: 2}), 2 in iter({1}), 2 in range(3), 'x' in {'x': 1}.keys(), 1 in {'x': 1}.values(), ('x', 1) in {'x': 1}.items())\n"),
    ('RL-299', 'in_mappingproxy', "class C:\n    x = 1\nprint('x' in C.__dict__, 'y' in vars(C), len(C.__dict__) > 0, C.__dict__['x'], C.__dict__.get('x'), C.__dict__.get('y', 9))\ntry:\n    [] in C.__dict__\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-300', 'set_key_in_set', "fs = frozenset({1, 2})\nprint({1, 2} in {fs}, {1} in {fs}, {1, 2} in frozenset({fs}), {1} in set(), {1} in frozenset())\ns = {fs}\ns.remove({1, 2})\nprint(s)\ns = {fs}\ns.discard({1, 2})\nprint(s)\ns = {fs}\ns.discard({1})\nprint(len(s))\ntry:\n    s.remove({1})\nexcept KeyError as e:\n    print(type(e).__name__, e.args)\nfor f in (lambda: [] in {1}, lambda: {1}.remove([]), lambda: {1}.discard([]), lambda: {1: 2}.get(set())):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-301', 'comprehension_in_lambda_in_loop', "def t(f):\n    print(f())\nfor n in (1, 2):\n    t(lambda: [i for i in range(3)])\nk = 0\nwhile k < 2:\n    t(lambda: {i: n for i in range(k)})\n    k += 1\n"),
    ('RL-301', 'comprehension_in_lambda_in_function_loop', "def g():\n    out = []\n    for n in (1, 2):\n        out.append(lambda m=n: [i * m for i in range(n)])\n        out.append((lambda: [[j for j in range(i)] for i in range(n)]))\n    return [f() for f in out]\nprint(g())\nclass C:\n    for n in (1, 2):\n        h = lambda self: [i for i in range(2)]\nprint(C().h())\n"),
    ('RL-302', 'del_list_slice', "l = [1, 2, 3, 4]\ndel l[:1]\nprint(l)\nl = list(range(8))\ndel l[::2]\nprint(l)\ndel l[10:]\nprint(l)\nl = list(range(5))\ndel l[::-1]\nprint(l)\nl = list(range(5))\ndel l[-1:]\nprint(l)\nl = list(range(5))\ndel l[1:3]\nprint(l)\nl = [1]\ntry:\n    del l['a']\nexcept TypeError as e:\n    print(e)\nl = [1]\ntry:\n    del l[5]\nexcept IndexError as e:\n    print(e)\n"),
    ('RL-302', 'del_slice_finalisers', "class D:\n    def __init__(self, n):\n        self.n = n\n    def __del__(self):\n        print('del', self.n)\nl = [D(0), D(1), D(2)]\ndel l[:2]\nprint('after', len(l))\n"),
    ('RL-303', 'keywords_before_positional_count', "def f(a):\n    pass\ndef g(a, *, k):\n    pass\nclass W:\n    def __init__(self, a):\n        pass\n    def m(self, a):\n        pass\nfor c in (lambda: f(1, 2, z=1), lambda: f(1, 2, a=1), lambda: g(1, 2, k=1, z=2), lambda: g(1, 2, k=1), lambda: W(1, z=1), lambda: W(1).m(1, 2, z=1), lambda: f(1, 2), lambda: f(), lambda: g(1)):\n    try:\n        c()\n    except TypeError as e:\n        print(e)\n"),
    ('RL-304', 'builtin_new_checks', "class Ex(Exception):\n    pass\nfor f in (lambda: ValueError.__new__(Ex), lambda: KeyError.__new__(ValueError), lambda: object.__new__(Ex), lambda: int.__new__(bool), lambda: bool.__new__(int), lambda: type.__new__(type, 1), lambda: list.__new__(), lambda: list.__new__(1), lambda: int.__new__(str), lambda: dict.__new__(list)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-304', 'builtin_new_works', "print(list.__new__(list), tuple.__new__(tuple), str.__new__(str, 5), dict.__new__(dict), int.__new__(int, 3), bool.__new__(bool, 1), set.__new__(set), frozenset.__new__(frozenset, [1]))\nprint(type(dict.__new__(type('D', (dict,), {}))).__name__)\n"),
    ('RL-305', 'attribute_error_keywords', "e = AttributeError('m', name='n', obj=3)\nprint(e.name, e.obj, e.args)\nn = NameError('m', name='q')\nprint(n.name, n.args)\ntry:\n    AttributeError('m', zz=1)\nexcept TypeError as t:\n    print(t)\ntry:\n    NameError('m', obj=1)\nexcept TypeError as t:\n    print(t)\nclass A:\n    def __getattr__(self, name):\n        raise AttributeError('no ' + name, name=name, obj=self)\ntry:\n    A().q\nexcept AttributeError as x:\n    print(x.name, type(x.obj).__name__, x.args)\ne = AttributeError('x')\ne.__init__('y', name='z')\nprint(e.args, e.name)\nclass S(AttributeError):\n    pass\nprint(S('a', name='b').name)\n"),
    ('RL-306', 'bool_none', "class L:\n    __bool__ = None\ntry:\n    bool(L())\nexcept TypeError as e:\n    print(e)\ntry:\n    if L():\n        pass\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-306', 'next_none', "class K:\n    __next__ = None\n    def __iter__(self):\n        return self\ntry:\n    next(K())\nexcept TypeError as e:\n    print(e)\ntry:\n    for x in K():\n        pass\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-307', 'star_not_iterable', "class X:\n    __iter__ = None\nclass Y:\n    pass\nfor v in (X(), Y(), 1):\n    try:\n        print([*v])\n    except TypeError as e:\n        print(e)\n    try:\n        print((*v,))\n    except TypeError as e:\n        print(e)\n    try:\n        print({*v})\n    except TypeError as e:\n        print(e)\n"),
    ('RL-307', 'join_not_iterable', "class Y:\n    pass\nfor v in (Y(), 1, None):\n    try:\n        print(''.join(v))\n    except TypeError as e:\n        print(e)\ntry:\n    ''.join([1])\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-307', 'index_not_integer', "class O:\n    pass\nfor f in (lambda: [1][O()], lambda: (1,)[O()], lambda: 'a'[O()], lambda: [1]['a'], lambda: (1,)['a'], lambda: 'a'['a']):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-307', 'iter_returns_non_iterator', "class I:\n    def __iter__(self):\n        return 1\ntry:\n    iter(I())\nexcept TypeError as e:\n    print(e)\ntry:\n    for x in I():\n        pass\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-307', 'update_keys_not_iterable', "class K:\n    def keys(self):\n        return 1\ntry:\n    {}.update(K())\nexcept TypeError as e:\n    print(e)\ntry:\n    dict(K())\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-307', 'dict_getattr_none', "class Oc:\n    __getattr__ = None\ntry:\n    dict(Oc())\nexcept TypeError as e:\n    print(e)\n"),
    # ---- classes
    ('RL-309', 'metaclass_repr_super', "class M(type):\n    def __repr__(cls):\n        return '<' + super().__repr__() + '>'\nclass C(metaclass=M):\n    pass\nprint(repr(C))\nprint(type.__repr__(C))\nprint(C)\n"),
    ('RL-310', 'int_subclass_super', "class H(int):\n    def __hash__(self):\n        return super().__hash__() + 1\n    def __repr__(self):\n        return 'H(' + super().__repr__() + ')'\n    def __str__(self):\n        return 's' + super().__str__()\n    def __neg__(self):\n        return 'n' + str(super().__neg__())\n    def __add__(self, o):\n        return 'a' + str(super().__add__(o))\n    def __eq__(self, o):\n        return 'e' + str(super().__eq__(o))\n    def __lt__(self, o):\n        return 'l' + str(super().__lt__(o))\n    def __bool__(self):\n        return not super().__bool__()\n    def __index__(self):\n        return super().__index__() + 1\nh = H(5)\nprint(hash(h), repr(h), str(h), -h, h + 1, h == 5, h < 6, bool(h), [0] * 7 and [1, 2, 3, 4, 5, 6, 7][h])\n"),
    ('RL-310', 'dict_list_subclass_super', "class D(dict):\n    def __repr__(self):\n        return 'D' + super().__repr__()\n    def __eq__(self, o):\n        return 'e' + str(super().__eq__(o))\n    def __len__(self):\n        return super().__len__() + 1\n    def __iter__(self):\n        return super().__iter__()\n    def __contains__(self, k):\n        return not super().__contains__(k)\n    def __hash__(self):\n        return 3\nd = D(a=1)\nprint(repr(d), d == {'a': 1}, len(d), list(d), 'a' in d, hash(d))\n"),
    ('RL-311', 'inplace_dunders', "class I(int):\n    def __iadd__(self, o):\n        return 'iadd'\n    def __imul__(self, o):\n        return 'imul'\n    def __ior__(self, o):\n        return 'ior'\nclass D(dict):\n    def __ior__(self, o):\n        return 'dior'\nx = I(1)\nx += 1\nprint(x)\nx = I(1)\nx *= 1\nprint(x)\nx = I(1)\nx |= 1\nprint(x)\nd = D()\nd |= {}\nprint(d)\nl = [I(1)]\nl[0] += 1\nprint(l)\nclass R(int):\n    def __radd__(self, o):\n        return 'radd'\ny = 1\ny += R(1)\nprint(y)\n"),
    ('RL-312', 'repeat_and_index_int_subclass', "class K(int):\n    pass\nprint('ab' * K(2), [1] * K(2), K(2) * (1,), K(2) * 'x')\nprint(range(3)[K(1)], [1, 2][K(1)], (1, 2)[K(1)], 'ab'[K(1)], [1, 2, 3][K(1):], list(range(K(2))), 'abc'.find('c', K(1)))\nl = [1]\nl *= K(2)\nprint(l)\n"),
    ('RL-313', 'mixin_after_builtin_base', "class M:\n    def __repr__(self):\n        return 'M.repr'\n    def __hash__(self):\n        return 77\n    def __eq__(self, o):\n        return 'M.eq'\n    def __add__(self, o):\n        return 'M.add'\n    def __neg__(self):\n        return 'M.neg'\n    def __bool__(self):\n        return False\n    def __str__(self):\n        return 'M.str'\nclass X(int, M):\n    pass\nx = X(5)\nprint(repr(x), hash(x), x == 5, x + 1, -x, bool(x), str(x))\nclass Y(dict, M):\n    pass\nprint(Y(a=1) == {'a': 1}, repr(Y(a=1)), str(Y()), bool(Y()))\nclass Z(M, int):\n    pass\nz = Z(5)\nprint(repr(z), hash(z), z == 5, z + 1, -z, bool(z), str(z))\n"),
    ('RL-314', 'metaclass_mro', "class O1:\n    x = 'O1'\nclass O2:\n    x = 'O2'\nclass M(type):\n    def mro(cls):\n        print('mro called', cls.__name__)\n        return [cls, O2, O1, object]\nclass T(O1, O2, metaclass=M):\n    pass\nprint(T.__mro__[1].__name__, T.x)\nclass Sub(T):\n    pass\nprint([c.__name__ for c in Sub.__mro__])\n"),
    ('RL-314', 'metaclass_mro_bad', "class A:\n    pass\nclass M1(type):\n    def mro(cls):\n        return 1\nclass M2(type):\n    def mro(cls):\n        return [cls, 1, object]\nclass M3(type):\n    def mro(cls):\n        return [object]\nfor m in (M1, M2, M3):\n    try:\n        print(m('T', (A,), {}).__mro__)\n    except TypeError as e:\n        print(e)\n"),
    ('RL-315', 'layout_conflict', "class E(int):\n    pass\nclass F(dict):\n    pass\nclass X:\n    __slots__ = ('a',)\nclass Y:\n    __slots__ = ('b',)\nclass P:\n    pass\nfor bases in ((E, F), (X, Y), (Exception, dict), (E, X), (int, dict), (P, X), (X, P), (ValueError, KeyError), (AttributeError, NameError)):\n    try:\n        print(type('J', bases, {}).__bases__[0].__name__)\n    except TypeError as e:\n        print(e)\nclass Empty:\n    __slots__ = ()\nprint(type('Z', (X, Empty), {}).__name__, type('Z2', (Empty, int), {}).__name__)\n"),
    ('RL-316', 'dict_subclass_iter_in_constructors', "class D(dict):\n    def __iter__(self):\n        return iter(['x'])\nd = D(a=1)\nprint(set(d), frozenset(d), {*d}, dict.fromkeys(d), list(d), tuple(d))\ns = set()\ns.update(d)\nprint(s)\nprint({1} | set(d))\nf = set()\nf |= set(d)\nprint(f)\n"),
    ('RL-317', 'type_call_module', "X = type('X', (), {})\nprint(X.__module__)\nprint(repr(X))\nY = type('Y', (), {'__module__': 'm'})\nprint(Y.__module__, repr(Y))\nprint(type(X()).__module__, X().__class__.__qualname__)\ndef f():\n    return type('L', (), {})\nprint(f().__module__, f().__qualname__)\nclass Q(type):\n    pass\nprint(Q('R', (), {}).__module__, repr(Q('R', (), {})))\nprint(repr(Q))\n"),
    ('RL-317', 'type_subclass_one_argument', "class Y(type):\n    pass\ntry:\n    print(Y(3))\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-318', 'local_class_with_super', "class A:\n    def f(self):\n        return 1\nclass B(A):\n    def f(self):\n        __class__ = int\n        return super().f()\ntry:\n    B().f()\nexcept RuntimeError as e:\n    print(e)\nclass C(A):\n    def f(self, __class__=3):\n        return super().f()\ntry:\n    C().f()\nexcept RuntimeError as e:\n    print(e)\n"),
    ('RL-319', 'super_without_arguments', "class A:\n    def f(self):\n        pass\nclass C(A):\n    def f():\n        super()\ntry:\n    C.f()\nexcept RuntimeError as e:\n    print(e)\n"),
    ('RL-320', 'init_subclass_kwargs', "class Z:\n    pass\ntry:\n    class Z2(Z, k=1):\n        pass\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-320', 'set_name_note', "class BadSN:\n    def __set_name__(self, o, n):\n        raise ValueError('bad')\ntry:\n    class Z3:\n        a = BadSN()\nexcept ValueError as e:\n    print(e.args, e.__notes__)\n"),
    ('RL-320', 'mro_conflict_names', "class O:\n    pass\nclass P1(O):\n    pass\nclass P2(O):\n    pass\ntry:\n    class T(O, P2):\n        pass\nexcept TypeError as e:\n    print(e)\ntry:\n    class T2(P1, O, P2):\n        pass\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-320', 'super_get_none_none', "class B:\n    pass\ntry:\n    super(B).__get__(None, None)\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-320', 'type_arguments', "for f in (lambda: type('a\\0b', (), {}), lambda: type('X', (), {}, 3), lambda: type('X', (), []), lambda: type('X', [], {}), lambda: type(1, (), {}), lambda: type('X', ()), lambda: type()):\n    try:\n        print(f().__name__)\n    except (TypeError, ValueError) as e:\n        print(type(e).__name__, e)\n"),
    ('RL-320', 'int_too_many_arguments', "class E(int):\n    pass\nfor f in (lambda: E(1, 2, 3), lambda: int(1, 2, 3)):\n    try:\n        print(f())\n    except TypeError as e:\n        print(e)\n"),
    ('RL-320', 'index_on_metaclass', "class M(type):\n    def __index__(cls):\n        return 1\nclass C(metaclass=M):\n    pass\nprint([1, 2, 3][C], 'abc'[C], (1, 2)[C], 'ab' * C)\n"),
    ('RL-320', 'del_int_real', "try:\n    del int.real\nexcept TypeError as e:\n    print(e)\ntry:\n    int.real = 1\nexcept TypeError as e:\n    print(e)\ntry:\n    int.foo = 1\nexcept TypeError as e:\n    print(e)\n"),
    ('RL-320', 'slice_repr', "print(repr(slice(1, 2)), slice(None), str(slice(1, 2, 3)), slice(1) == slice(1), slice(1, 2).start, slice(1, 2).stop, slice(1, 2).step)\n"),
]

# Several modules: (finding, name, files, sort stdout: an order D-07 leaves unspecified).
MODULES: list[tuple[str, str, dict[str, str], bool]] = [
    ('RL-256', 'star_all_submodule', {'main.py': "from mypkg import *\nprint('sub:', sub.SUB_VAL)\n", 'mypkg/__init__.py': "__all__ = ['sub', 'other']\n", 'mypkg/sub.py': "print('sub loaded')\nSUB_VAL = 42\n", 'mypkg/other.py': "print('other loaded')\n", 'mypkg/never.py': "print('never loaded')\n"}, False),
    ('RL-256', 'star_all_forms', {'main.py': "from p1 import *\nprint(a.X, b.X, c.X, d.X)\n", 'p1/__init__.py': "__all__ = ['a']\n__all__ += ['b']\n__all__.extend(['c'])\n__all__.append('d')\n", 'p1/a.py': "X = 'a'\n", 'p1/b.py': "X = 'b'\n", 'p1/c.py': "X = 'c'\n", 'p1/d.py': "X = 'd'\n"}, False),
    ('RL-256', 'star_all_computed', {'main.py': "from p2 import *\nprint(s1.X, s2.X)\n", 'p2/__init__.py': "NAMES = ['s1']\nNAMES.append('s2')\n__all__ = NAMES\n", 'p2/s1.py': "X = 1\n", 'p2/s2.py': "X = 2\n"}, False),
    ('RL-256', 'star_import_dunder', {'main.py': "import sys\nm = __import__('p3', fromlist=['*'])\nprint(list(sys.modules.keys())[-2:], m.q.X)\n", 'p3/__init__.py': "__all__ = ['q']\n", 'p3/q.py': "X = 1\n"}, False),
    ('RL-261', 'dunder_import_fromlist', {'main.py': "m = __import__('pkg', fromlist=['a'])\nprint(m.a.__name__)\nn = __import__('pkg', None, None, ('b',))\nprint(n.b.__name__)\n", 'pkg/__init__.py': "", 'pkg/a.py': "", 'pkg/b.py': ""}, False),
    ('RL-261', 'dunder_import_level', {'main.py': "import pkg\nprint(pkg.m.__name__, pkg.n.__name__)\n", 'pkg/__init__.py': "m = __import__('sub', globals(), None, ['x'], 1)\nn = __import__('sib', level=1, globals=globals(), fromlist=('y',))\n", 'pkg/sub.py': "x = 1\n", 'pkg/sib.py': "y = 1\n"}, False),
    ('RL-261', 'builtins_dunder_import', {'main.py': "import builtins\nprint(builtins.__import__('d').X)\n", 'd.py': "X = 1\n"}, False),
    ('RL-262', 'directory_does_not_shadow_stdlib', {'main.py': "import types\nprint(types.SimpleNamespace(a=1))\n", 'types/data.txt': "x\n"}, False),
    ('RL-263', 'pep263_cookie', {'main.py': "import lat\n", 'lat.py': "# -*- coding: utf-8 -*-\nprint('caf\u00e9')\n"}, False),
    ('RL-270', 'module_setattr_other_module', {'main.py': "import m\ntry:\n    m.__class__ = int\nexcept TypeError as e:\n    print(e)\ntry:\n    m.__dict__ = {'a': 1}\nexcept AttributeError as e:\n    print(e)\nprint(list(vars(m)))\n", 'm.py': "X = 1\n"}, False),
    ('RL-274', 'source_file_loader_shape', {'main.py': "import m\nL = m.__spec__.loader\nT = type(L)\nprint([c.__name__ for c in T.__bases__], [c.__name__ for c in T.__mro__], hasattr(L, 'load_module'), L.get_filename.__qualname__, T.__init__.__module__, T.__init__.__qualname__)\nprint(L.get_filename('m').rsplit('/', 1)[-1], L.is_package('m'), L.name, L.path.rsplit('/', 1)[-1], L.create_module(None))\nprint(T.__module__, T.__qualname__, T.__bases__[0].__module__)\n", 'm.py': ""}, False),
    ('RL-281', 'exit_del_sees_globals', {'main.py': "import sys\nLABEL = 'res'\ndef helper():\n    return 'helper'\nclass D:\n    def __del__(self):\n        print('del', LABEL, helper(), type(sys).__name__, __name__)\nd = D()\n"}, False),
    ('RL-281', 'exit_del_defined_before', {'main.py': "import sys\nclass D:\n    def __init__(self, n):\n        self.n = n\n    def __del__(self):\n        print('del', self.n, TAIL, type(sys).__name__)\na = D('a')\nholder = {'k': [D('in list')]}\nclass O:\n    pass\no = O()\no.d = D('in attribute')\nt = (D('in tuple'),)\nTAIL = 'tail'\n"}, True),
    ('RL-281', 'exit_del_state_of_sys', {'main.py': "import sys\nclass D:\n    def __del__(self):\n        print(sys.path, sys.argv, len(sys.modules), sys.stdout is sys.__stdout__)\nd = D()\n"}, False),
    ('RL-281', 'exit_del_in_other_module', {'main.py': "import other\nd = other.D()\nv = 'mainv'\n", 'other.py': "W = 'otherw'\ndef h():\n    return 'h'\nclass D:\n    def __del__(self):\n        print('del', W, h())\n"}, False),
    ('RL-281', 'exit_del_module_without_functions', {'main.py': "import other\nprint('start')\n", 'other.py': "import third\nd = third.D('held by other')\nW = 'w'\n", 'third.py': "T = 't'\nclass D:\n    def __init__(self, n):\n        self.n = n\n    def __del__(self):\n        print('del', self.n, T)\n"}, False),
    ('RL-281', 'exit_del_raises_and_exits', {'main.py': "import sys\nclass D:\n    def __del__(self):\n        print('running')\n        sys.exit(9)\nd = D()\nprint('end')\n"}, False),
    ('RL-281', 'exit_del_after_sys_exit', {'main.py': "import sys\nN = 'n'\nclass D:\n    def __del__(self):\n        print('del', N)\nd = D()\nsys.exit(3)\n"}, False),
    ('RL-281', 'exit_del_after_uncaught', {'main.py': "N = 'n'\nclass D:\n    def __del__(self):\n        print('del', N)\nd = D()\nraise KeyError('k')\n"}, False),
    ('RL-281', 'exit_del_once', {'main.py': "G = []\nclass D:\n    def __del__(self):\n        print('del once')\n        G.append(self)\nd = D()\nd2 = d\nl = [d, d]\n"}, False),
    ('RL-286', 'star_bad_all', {'main.py': "try:\n    import star_m_int\n    print('int', 'ok', hasattr(star_m_int, 'a'))\nexcept Exception as e:\n    print('int', type(e).__name__, e)\ntry:\n    import star_m_none\n    print('none', 'ok', hasattr(star_m_none, 'a'))\nexcept Exception as e:\n    print('none', type(e).__name__, e)\ntry:\n    import star_m_set\n    print('set', 'ok', hasattr(star_m_set, 'a'))\nexcept Exception as e:\n    print('set', type(e).__name__, e)\ntry:\n    import star_m_dict\n    print('dict', 'ok', hasattr(star_m_dict, 'a'))\nexcept Exception as e:\n    print('dict', type(e).__name__, e)\ntry:\n    import star_m_iter\n    print('iter', 'ok', hasattr(star_m_iter, 'a'))\nexcept Exception as e:\n    print('iter', type(e).__name__, e)\ntry:\n    import star_m_range\n    print('range', 'ok', hasattr(star_m_range, 'a'))\nexcept Exception as e:\n    print('range', type(e).__name__, e)\ntry:\n    import star_m_tuple\n    print('tuple', 'ok', hasattr(star_m_tuple, 'a'))\nexcept Exception as e:\n    print('tuple', type(e).__name__, e)\ntry:\n    import star_m_str\n    print('str', 'ok', hasattr(star_m_str, 'a'))\nexcept Exception as e:\n    print('str', type(e).__name__, e)\ntry:\n    import star_m_items\n    print('items', 'ok', hasattr(star_m_items, 'a'))\nexcept Exception as e:\n    print('items', type(e).__name__, e)\ntry:\n    import star_m_getitem\n    print('getitem', 'ok', hasattr(star_m_getitem, 'a'))\nexcept Exception as e:\n    print('getitem', type(e).__name__, e)\n", 'm_int.py': '__all__ = 5\n', 'star_m_int.py': 'from m_int import *\n', 'm_none.py': '__all__ = None\n', 'star_m_none.py': 'from m_none import *\n', 'm_set.py': "__all__ = {'a'}\na = 1\n", 'star_m_set.py': 'from m_set import *\n', 'm_dict.py': "__all__ = {'a': 0}\na = 1\n", 'star_m_dict.py': 'from m_dict import *\n', 'm_iter.py': "class I:\n    def __iter__(self):\n        return iter(['a'])\n__all__ = I()\na = 1\n", 'star_m_iter.py': 'from m_iter import *\n', 'm_range.py': '__all__ = range(3)\n', 'star_m_range.py': 'from m_range import *\n', 'm_tuple.py': "__all__ = ('a', 1)\na = 1\n", 'star_m_tuple.py': 'from m_tuple import *\n', 'm_str.py': "__all__ = 'a'\na = 1\n", 'star_m_str.py': 'from m_str import *\n', 'm_items.py': "__all__ = ['a', 'nope']\na = 1\n", 'star_m_items.py': 'from m_items import *\n', 'm_getitem.py': "class G:\n    def __getitem__(self, i):\n        if i > 0:\n            raise IndexError(i)\n        return 'a'\n__all__ = G()\na = 1\n", 'star_m_getitem.py': 'from m_getitem import *\n'}, False),
    ('RL-287', 'dunder_import_empty_part', {'main.py': "try:\n    print(__import__('pkg..sub').__name__)\nexcept ImportError as e:\n    print(type(e).__name__, e.args, e.name)\ntry:\n    print(__import__('pkg.sub.').__name__)\nexcept ImportError as e:\n    print(type(e).__name__, e.args, e.name)\ntry:\n    print(__import__('pkg.').__name__)\nexcept ImportError as e:\n    print(type(e).__name__, e.args, e.name)\ntry:\n    __import__('')\nexcept ValueError as e:\n    print(e)\n", 'pkg/__init__.py': "print('init')\n", 'pkg/sub.py': ""}, False),
    ('RL-281', 'exit_del_import_fails', {'main.py': "class D:\n    def __del__(self):\n        try:\n            import later\n            print('imported')\n        except ImportError as e:\n            print(type(e).__name__, e)\nd = D()\n", 'later.py': ""}, False),
]

# Reports: stderr compared too.
REPORTS: list[tuple[str, str, str]] = [
    ('RL-282', 'exit_str_raises_report', "import sys\nclass X:\n    def __str__(self):\n        raise ValueError('no str')\nsys.exit(X())\n"),
    ('RL-282', 'exit_values_report', "import sys\nsys.exit('message')\n"),
    ('RL-281', 'exit_del_report', "import sys\nN = 'n'\nclass D:\n    def __del__(self):\n        print('del', N)\n        raise ValueError(N)\nd = D()\n"),
    ('RL-293', 'for_next_line', "class It:\n    def __init__(self):\n        self.n = 0\n    def __iter__(self):\n        return self\n    def __next__(self):\n        self.n += 1\n        if self.n == 3:\n            raise KeyError('it')\n        return self.n\n\ndef f():\n    t = 0\n    for x in It():\n        t += x\n        t += 1\n    return t\n\nf()\n"),
    ('RL-293', 'while_test_line', "def g(i):\n    if i == 2:\n        raise KeyError(i)\n    return True\n\ndef f():\n    i = 0\n    while g(i):\n        i += 1\n        i += 0\n\nf()\n"),
    ('RL-293', 'for_module_line', "class It:\n    def __iter__(self):\n        return self\n    def __next__(self):\n        raise KeyError('it')\nfor x in It():\n    print(x)\n"),
    ('RL-293', 'while_else_line', "def g(i):\n    if i == 1:\n        raise KeyError(i)\n    return True\nn = 0\nwhile g(n):\n    n += 1\n    n += 0\nelse:\n    print('else')\n"),
    ('RL-308', 'non_string_module_report', "class E(Exception):\n    pass\nE.__module__ = 5\nraise E('x')\n"),
]


# Found while fixing them.
FINDINGS += [
    ('RL-300', 'frozenset_hash_by_content', "a = frozenset({1, 2})\nb = frozenset([2, 1])\nprint(hash(a) == hash(b), a == b, {a: 1}[b], b in {a}, hash(frozenset()) == hash(frozenset()), hash(frozenset({'x'})) == hash(frozenset(['x'])))\nprint(hash(frozenset()), hash(frozenset({1})), hash(frozenset({1, 2, 3})))\nprint(hash(range(0)) == hash(range(5, 5)), hash(range(1, 2)) == hash(range(1, 2, 9)), hash(range(3)) == hash(range(0, 3, 1)), hash(range(3)) == hash((3, 0, 1)), hash(range(0)) == hash((0, None, None)))\nprint(hash(slice(1, 2)) == hash(slice(1, 2, None)), hash(slice(1, 2)) == hash(slice(1, 2)), slice(1) == slice(None, 1), None.__class__, hash(None), hash(None) == None.__hash__())\n"),
    ('RL-306', 'next_of_an_iterator_class', "class It:\n    def __init__(self):\n        self.n = 0\n    def __next__(self):\n        self.n += 1\n        if self.n > 1:\n            raise StopIteration('done')\n        return self.n\ni = It()\nprint(next(i))\nprint(next(i, 'dflt'))\ntry:\n    next(i)\nexcept StopIteration as e:\n    print(e.args)\n"),
    ('RL-310', 'builtin_methods_as_attributes', "print((5).__repr__(), (5).__hash__(), (5).__ne__(6), (5).__lt__(6), (5).__add__(1), (5).__radd__(1), (5).__add__('a'), (5).__eq__('a'), (5).__neg__(), (5).__bool__(), (5).__index__(), (5).__int__(), (5).__divmod__(2), (2).__pow__(3), (5).__abs__(), (5).__invert__(), (5).__floor__(), (5).__ceil__(), (5).__trunc__(), (5).__round__())\nprint(True.__repr__(), True.__and__(False), True.__add__(1), int.__repr__(True), bool.__repr__(False))\nprint('a'.__repr__(), 'a'.__eq__('a'), 'a'.__lt__('b'), 'a'.__add__('b'), 'ab'.__len__(), 'ab'.__getitem__(0), 'a'.__contains__('a'), 'a'.__hash__() == hash('a'), 'a'.__mul__(2), 'a'.__rmul__(2))\nprint([1].__eq__([1]), [1].__len__(), [1].__getitem__(0), [1].__add__([2]), [1].__mul__(2), [1].__contains__(1), [1].__lt__([2]), [1].__repr__())\nprint((1,).__eq__((1,)), (1,).__len__(), (1,).__getitem__(0), (1,).__add__((2,)), (1,).__hash__() == hash((1,)), (1,).__repr__())\nprint({1}.__eq__({1}), {1}.__len__(), {1}.__contains__(1), {1}.__or__({2}), {1}.__and__({1}), frozenset({1}).__or__({2}), {1}.__repr__())\nprint({}.__eq__({}), {}.__len__(), {}.__or__({1: 2}), {}.__repr__(), {}.__ne__({}))\nprint(None.__repr__(), None.__bool__(), range(2).__len__(), range(2).__eq__(range(2)), range(2).__getitem__(1), range(2).__repr__(), range(2).__contains__(1), slice(1).__repr__(), slice(1).__eq__(slice(1)))\n"),
    ('RL-272', 'builtin_type_docs', "print(int.__doc__)\nprint((5).__doc__ == int.__doc__, str.__doc__ == ''.__doc__, list.__doc__[:4], dict.__doc__[:4], ValueError.__doc__, KeyError('k').__doc__, object.__doc__, type.__doc__[:4], range.__doc__[:5])\nclass C:\n    pass\nprint(C.__doc__, C().__doc__)\nclass D:\n    'doc'\nprint(D.__doc__, D().__doc__)\nclass E(int):\n    pass\nprint(E.__doc__, E(1).__doc__)\n"),
    ('RL-258', 'function_module_rebound', "def f():\n    pass\nprint(f.__module__)\nf.__module__ = 'elsewhere'\nprint(f.__module__)\ndel f.__module__\nprint(f.__module__)\n"),
    ('RL-309', 'class_str_and_repr', "class M(type):\n    def __str__(cls):\n        return 'str ' + super().__repr__()\nclass C(metaclass=M):\n    pass\nprint(str(C), repr(C), type.__repr__(M), type.__repr__(int))\n"),
]


def test_finds_import_module_by_any_name() -> None:
    """RL-258, RL-261: `importlib` itself is refused until it runs, so the scanner is asked."""
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("dyn", "al", "sub_abs", "pk/__init__", "pk/rel", "pk/kw"):
            Path(tmp, name).parent.mkdir(parents=True, exist_ok=True)
            Path(tmp, f"{name}.py").write_text("X = 1\n", encoding="utf-8")
        main = Path(tmp, "main.py")
        main.write_text("from importlib import import_module\nimport importlib as il\nimport_module('dyn')\nil.import_module('al')\n"
                        "import importlib\nimportlib.import_module('.rel', 'pk')\nimport_module('.kw', package='pk')\nimport_module(name='sub_abs')\n",
                        encoding="utf-8")
        found = {m.name for m in find_program_modules(main)}
    assert {"dyn", "al", "pk", "pk.rel", "pk.kw", "sub_abs"} <= found, found


def _cli(program: Path, cwd: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "build.py"), *flags, str(program)],
                          capture_output=True, text=True, check=False, cwd=cwd)


def test_source_encodings() -> None:
    """RL-263: a PEP 263 cookie and a BOM, as CPython reads a source."""
    if shutil.which("g++") is None:
        return
    for raw in ("# -*- coding: latin-1 -*-\nprint(len('caf\xe9'), ord('caf\xe9'[3]))\n".encode("latin-1"),
                b"\xef\xbb\xbfprint('bom')\n", b"print('crlf')\r\nprint('x')\r\n"):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "lat.py").write_bytes(raw)
            main = Path(tmp, "main.py")
            main.write_text("import lat\n", encoding="utf-8")
            Path(tmp, "own.py").write_bytes(raw)
            for program in (main, Path(tmp, "own.py")):
                ref = subprocess.run([sys.executable, program.name], capture_output=True, text=True, check=False, cwd=tmp, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                got = subprocess.run([str(build(program, str(program)))], capture_output=True, text=True, check=False, cwd=tmp)
                assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (raw, got, ref)


def test_a_bad_encoding_is_refused() -> None:
    """RL-263: bytes the cookie cannot decode stop the build with the refusal, not a traceback."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "bad.py").write_bytes(b"print('\xff')\n")
        got = _cli(Path(tmp, "bad.py"), Path(tmp))
    assert got.returncode == 70 and "bella: refused" in got.stderr, got


def _frames(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("  File")]


def test_paths_as_cpython_keeps_them() -> None:
    """RL-264, RL-268: a relative program path's frames say the absolute path; a link's __file__ is
    the link, and sys.path[0] the directory of what it leads to."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        (root / "real").mkdir()
        (root / "link").mkdir()
        prog = root / "real" / "main.py"
        prog.write_text("import sys\nprint(__file__, sys.path[0])\nraise KeyError(1)\n", encoding="utf-8")
        (root / "link" / "main.py").symlink_to(prog)
        for where, program in ((root / "real", Path("main.py")), (root / "link", Path("main.py")), (root, Path("link/main.py"))):
            ref = subprocess.run([sys.executable, str(program)], capture_output=True, text=True, check=False, cwd=where)
            got = _cli(program, where, "--run")
            assert got.stdout.splitlines()[0].split()[0] == ref.stdout.splitlines()[0].split()[0], (got, ref)
            assert got.stdout.splitlines()[0].split()[1] == ref.stdout.splitlines()[0].split()[1], (got, ref)
            assert _frames(got.stderr) == _frames(ref.stderr), (got.stderr, ref.stderr)


def test_build_cache_keys() -> None:
    """RL-259, RL-265, RL-266: what changes the result is in the key."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "p.py")
        prog.write_text("print('hi')\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "BELLA_KEEP_DEBUG"}
        stripped = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "build.py"), str(prog)], capture_output=True, text=True, check=True, env=env).stdout.strip()
        size = Path(stripped).stat().st_size
        kept = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "build.py"), str(prog)], capture_output=True, text=True, check=True, env=dict(env, BELLA_KEEP_DEBUG="1")).stdout.strip()
        assert kept != stripped and Path(kept).stat().st_size > size, (stripped, kept)
    source = Path(build_module.__file__).read_text(encoding="utf-8")
    assert 'f.relative_to(ROOT).parts' in source and "header_macros()" in source


def test_a_frozen_name_is_not_a_program_file() -> None:
    """RL-257: FrozenImporter takes `importlib.machinery` whatever the parent's path says, so the
    program's file of that name never runs. Since 2026-11-09 the frozen one is compiled and runs; over a program's own
    `importlib` package its `from ._bootstrap import` reaches the frozen alias `importlib._bootstrap`, a second copy of the
    import system in CPython, which stops by name."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "importlib").mkdir()
        Path(tmp, "importlib", "__init__.py").write_text("print('user importlib')\n", encoding="utf-8")
        Path(tmp, "importlib", "machinery.py").write_text("print('user machinery')\n", encoding="utf-8")
        main = Path(tmp, "main.py")
        main.write_text("import importlib.machinery\n", encoding="utf-8")
        assert not any(m.name == "importlib.machinery" and m.path is not None and m.path.is_relative_to(Path(tmp).resolve()) for m in find_program_modules(main))
        got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False, cwd=tmp)
    assert got.stdout == "user importlib\n" and got.returncode == 70 and "importlib._bootstrap" in got.stderr, got


def _compiled(tmp: str, text: str, seed: str = "0") -> str:
    main = Path(tmp, "main.py")
    main.write_text(text, encoding="utf-8")
    got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False,
                         env=dict(os.environ, PYTHONHASHSEED=seed), cwd=tmp)
    assert got.returncode == 0, got
    return got.stdout


def test_a_hash_is_cpythons_under_a_seed() -> None:
    """Under one seed two runs agree on every hash, and it is CPython's own (D-22 ended with big ints)."""
    if shutil.which("g++") is None:
        return
    text = "for s in ('', 'a', 'key1', 'key2', 'key3', 'key4', 'key5', 'key6', 'key7', 'key8'):\n    print(s, hash(s))\n"
    with tempfile.TemporaryDirectory() as tmp:
        ours = _compiled(tmp, text)
        assert ours == _compiled(tmp, text)
        ref = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, check=False,
                             env=dict(os.environ, PYTHONHASHSEED="0"), cwd=tmp)
    assert ours == ref.stdout


def test_no_bytecode_cache_d_16() -> None:
    """A compiled program has no .pyc: `__spec__.cached` is None, as under CPython with no cache tag."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "mod.py").write_text("X = 1\n", encoding="utf-8")
        Path(tmp, "pkg").mkdir()
        Path(tmp, "pkg", "__init__.py").write_text("", encoding="utf-8")
        got = _compiled(tmp, "import mod\nimport pkg\nimport types\nprint(mod.__spec__.cached, pkg.__spec__.cached, types.__spec__.cached)\n"
                             "mod.__spec__.cached = 'x'\nprint(mod.__spec__.cached)\n")
    assert got == "None None None\nx\n"


def test_del_of_the_first_argument_with_super_is_refused() -> None:
    """RL-319: CPython's RuntimeError reads the frame's first slot; the build refuses by name."""
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "p.py")
        prog.write_text("class A:\n    def f(self):\n        pass\nclass B(A):\n    def f(self):\n        del self\n        super()\n", encoding="utf-8")
        got = _cli(prog, Path(tmp))
    assert got.returncode == 70 and "first argument" in got.stderr, got


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{fid}-{name}" for fid, name, _ in FINDINGS])
    if "modules" in metafunc.fixturenames:
        metafunc.parametrize("modules", MODULES, ids=[f"{fid}-{name}" for fid, name, _, _ in MODULES])
    if "report" in metafunc.fixturenames:
        metafunc.parametrize("report", REPORTS, ids=[f"{fid}-{name}" for fid, name, _ in REPORTS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


def test_modules(modules: tuple[str, str, dict[str, str], bool]) -> None:
    same_files(modules[2], sort_stdout=modules[3])


def test_report(report: tuple[str, str, str]) -> None:
    same_report(report[2])


if __name__ == "__main__":
    for finding in FINDINGS:
        test_finding(finding)
    for modules in MODULES:
        test_modules(modules)
    for report in REPORTS:
        test_report(report)
    test_finds_import_module_by_any_name()
    test_source_encodings()
    test_a_bad_encoding_is_refused()
    test_paths_as_cpython_keeps_them()
    test_build_cache_keys()
    test_a_frozen_name_is_not_a_program_file()
    test_del_of_the_first_argument_with_super_is_refused()
    print("ok")
