# clause: C-8-03
# spec: section 8 (PEP 667)
# status: P1
# source: review round 2, finding 6 (locals() in a function is a fresh mutable dictionary)
"""locals() returns a new mutable snapshot each time; writes to it do not change variables."""


def probe() -> None:
    x = 1
    snapshot = locals()
    snapshot["x"] = 2
    snapshot["y"] = 3
    print("variable unchanged:", x, "snapshot mutated:", snapshot["x"], snapshot["y"])
    print("fresh object each call:", locals() is snapshot)
    print("fresh snapshot sees current value:", locals()["x"])


probe()
