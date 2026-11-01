"""A stand-in for the compiler refusing a [P2+] construct (used by test_harness.py)."""
import sys

print(f"{sys.argv[1]}: error: comprehension unpacking (PEP 798) is [P2+]", file=sys.stderr)
raise SystemExit(1)
