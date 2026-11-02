"""pipeline/l1/pretty.py renders every L1 node: the slice examples, the dialect cases and the
target drivers print without an error, and a sample reads as documented.

Run under pytest or directly: python3 -m pipeline.tests.test_l1_pretty
"""
from __future__ import annotations

from pathlib import Path

from pipeline.l1.frontend import lower
from pipeline.l1.grammar import Unsupported
from pipeline.l1.pretty import render
from pipeline.tests.test_frontend_eval1 import both

ROOT = Path(__file__).resolve().parents[2]


def test_every_program_that_lowers_renders() -> None:
    sources = [*sorted((ROOT / "pipeline" / "examples").glob("*.py")), *sorted((ROOT / "conformance" / "cases").glob("C-*.py")),
               *sorted((ROOT / "targets" / "drivers").glob("*.py"))]
    rendered = 0
    for path in sources:
        try:
            module = lower(path.read_text(encoding="utf-8"), str(path))
        except (Unsupported, SyntaxError):
            continue
        assert render(module).strip(), path
        rendered += 1
    assert rendered > 50


def test_a_sample_reads_as_documented() -> None:
    text = render(lower("class C:\n    def m(self):\n        with open('x') as f:\n            return super().m()\n", "<t>"))
    for needle in ("C = %build_class(<classbody C>, 'C')", "classbody C:  # classcell, classdict",
                   "%special(", "%super(super, %classcell, self).m()", "__classcell__ = %classcell"):
        assert needle in text, (needle, text)


def test_with_does_not_reach_a_program_binding_of_special() -> None:
    got, ref = both("""
__special__ = "not the lookup"
class M:
    def __enter__(self):
        return 1
    def __exit__(self, *a):
        return False
with M() as v:
    print(v, __special__)
""")
    assert got == ref, (got, ref)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
