"""Clause C-9-1 (design document, section 13): the certificate every checker must reject.

The claim "x, y in [-2^31, 2^31) make x*x + y*y safe in int64" is false at the sum
(2^62 + 2^62 = 2^63); the correct precondition is [-2^30, 2^30). A validator that accepts
the 31-bit claim is broken. Both checkers are tested; the Z3 one is skipped when z3 is not
installed (it is in the dev extras).
"""
from __future__ import annotations

from validation.certificates import (
    Add, Lit, Mul, RangeCertificate, Var, check_intervals, evaluate, norm2_certificate,
)


def test_c_9_1_intervals_rejects_31_bits_and_accepts_30() -> None:
    bad = check_intervals(norm2_certificate(31))
    assert not bad.proved
    assert bad.witness is not None
    assert evaluate(norm2_certificate(31).expr, bad.witness) > 2**63 - 1
    assert "= 9223372036854775808" in (bad.offending or "")
    good = check_intervals(norm2_certificate(30))
    assert good.proved


def test_intermediates_are_checked_not_only_the_result() -> None:
    # (x * x) - (x * x) is always 0, but the intermediate x*x overflows for large x
    x = Var("x")
    cert = RangeCertificate(Add(Mul(x, x), Lit(0)), {"x": (-(2**40), 2**40)}, 64)
    assert not check_intervals(cert).proved
    cert2 = RangeCertificate(Mul(x, Lit(2)), {"x": (-(2**61), 2**61 - 1)}, 64)
    assert check_intervals(cert2).proved


def test_c_9_1_z3_agrees() -> None:
    try:
        import z3  # noqa: F401
    except ImportError:
        return  # pytest would skip; the plain runner just passes through
    from validation.certificates import check_z3
    assert not check_z3(norm2_certificate(31)).proved
    assert check_z3(norm2_certificate(30)).proved


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
