# clause: C-7-14
# spec: section 7
# status: P1
# source: dialect specification section 7, Development (logging, argparse, warnings, unittest, pprint)
"""Development modules with deterministic output: logging into a StringIO handler, argparse at
a fixed width, warnings recorded, unittest results counted (not timed), pprint."""
import argparse
import io
import logging
import os
import pprint
import unittest
import warnings

stream = io.StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(funcName)s:%(message)s"))
log = logging.getLogger("bella.case")
log.addHandler(handler)
log.setLevel(logging.INFO)
log.propagate = False


def work() -> None:
    log.debug("hidden")
    log.info("value %d", 42)
    log.warning("careful %s", "now")


work()
log.getChild("child").error("from the child")
print(repr(stream.getvalue()), logging.getLevelName(25), logging.getLevelName("WARNING"))

os.environ["COLUMNS"] = "60"
parser = argparse.ArgumentParser(prog="tool", description="A tool.")
parser.add_argument("path")
parser.add_argument("-n", "--count", type=int, default=1, help="how many")
parser.add_argument("--verbose", action="store_true")
group = parser.add_mutually_exclusive_group()
group.add_argument("--fast", action="store_true")
group.add_argument("--slow", action="store_true")
print(vars(parser.parse_args(["x", "-n", "3", "--fast"])))
print(parser.format_help())
err = io.StringIO()
try:
    import contextlib
    with contextlib.redirect_stderr(err):
        parser.parse_args(["--fast", "--slow", "x"])
except SystemExit as exc:
    print("exit code:", exc.code, "| usage line:", err.getvalue().splitlines()[0])

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    warnings.warn("old API", DeprecationWarning, stacklevel=1)
    warnings.warn("odd value", UserWarning, stacklevel=1)
print([(w.category.__name__, str(w.message)) for w in caught])


class Sample(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertEqual(1 + 1, 2)

    def test_fails(self) -> None:
        self.assertIn(3, [1, 2])

    @unittest.skip("not today")
    def test_skipped(self) -> None:
        pass


result = unittest.TestResult()
unittest.defaultTestLoader.loadTestsFromTestCase(Sample).run(result)
print(result.testsRun, len(result.failures), len(result.skipped), result.wasSuccessful(), [t.id().split(".")[-1] for t, _ in result.failures])
print(pprint.pformat({"key": list(range(12)), "nested": {"a": [1, 2], "b": "x" * 30}}, width=40))
