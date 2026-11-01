"""Translation-validation checkers (design document, section 9, rung 2).

A pass that removes a check (overflow, bounds, zero-divisor) emits a *certificate*: the claim
it relied on, in a form a checker can verify independently of the pass. The checkers here
decide range certificates for integer expressions: `intervals` is a small sound checker with
corner-point refutation; `z3_check` uses Z3 (MIT) when installed. Clause C-9-1 (design
document, section 13) is the standing example: the certificate a broken checker accepts.
"""
