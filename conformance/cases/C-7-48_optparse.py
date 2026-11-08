# clause: C-7-48
# spec: section 7
# status: P1
# source: dialect specification section 7, Lib/optparse.py (admitted 2026-11-08, docs/targets.md section 5 item 3)
"""optparse, as pycodestyle drives it: an OptionParser with the action kinds (store, store_true, store_false, count, append,
callback, a choice, a typed value), option groups, defaults and %default in help, parse_args over a given list (not sys.argv),
the Values object (attributes, __dict__.update, read_module's absence is not exercised, ensure_value, __eq__, repr), the help and
usage texts, version, errors (an unknown option, a missing value, a bad integer, an ambiguous abbreviation) raised through
parser.error as SystemExit with the message on stderr, conflicts and OptionError, and set_defaults."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import io
import optparse
import sys
from optparse import OptionGroup, OptionParser, OptionValueError, Values


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except SystemExit as e:
        return "SystemExit: " + repr(e.code)
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def with_stderr(f):  # type: ignore[no-untyped-def]
    """(result, what went to stderr) with stderr captured, as a program's user sees parser.error."""
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        return m(f), sys.stderr.getvalue()  # type: ignore[no-untyped-call]
    finally:
        sys.stderr = old


def callback(option, opt, value, parser):  # type: ignore[no-untyped-def]
    parser.values.seen.append((opt, value))


parser = OptionParser(prog="check", version="check 1.2.3", usage="%prog [options] input ...", description="A checker.", epilog="The end.")
parser.config_options = ["exclude", "select", "max-line-length"]  # type: ignore[attr-defined]
parser.add_option("-v", "--verbose", default=0, action="count", help="print status messages, or debug with -vv")
parser.add_option("-q", "--quiet", default=0, action="count", help="report only file names, or nothing with -qq")
parser.add_option("-r", "--repeat", default=True, action="store_true", help="(obsolete) show all occurrences of the same error")
parser.add_option("--first", action="store_false", dest="repeat", help="show first occurrence of each error")
parser.add_option("--exclude", metavar="patterns", default="E24,W503", help="exclude patterns (default: %default)")
parser.add_option("--select", metavar="errors", default="", help="select errors and warnings (e.g. E,W6)")
parser.add_option("--max-line-length", type="int", metavar="n", default=79, help="set maximum allowed line length (default: %default)")
parser.add_option("--indent-size", type="int", metavar="n", default=4, help="set how many spaces make up an indent (default: %default)")
parser.add_option("--format", metavar="format", default="default", help="set the error format [default|pylint|<custom>]")
parser.add_option("--level", type="choice", choices=["low", "high"], default="low", help="a level")
parser.add_option("--ratio", type="float", default=0.5)
parser.add_option("--tag", action="append", dest="tags", default=[])
parser.add_option("--mark", action="callback", callback=callback, type="string")
parser.add_option("--flag", action="store_const", const=42, dest="flag")
group = OptionGroup(parser, "Configuration", description="The project options are read from the [check] section of the tox.ini file.")
group.add_option("--config", metavar="path", default="~/.config/check", help="user config file location")
parser.add_option_group(group)
parser.set_defaults(seen=[])

print("parser:", parser.prog, parser.version, parser.get_usage().rstrip(), parser.get_version(), len(parser.option_list), parser.has_option("--select"), parser.has_option("--nope"), parser.get_option("--select").dest, parser.get_option("-v").action, parser.get_option("--max-line-length").type, parser.get_option("--exclude").default, parser.defaults["repeat"], sorted(parser.defaults)[:6])  # type: ignore[union-attr]
options, args = parser.parse_args(["-vv", "--first", "--select", "E,W6", "--max-line-length=100", "--tag", "a", "--tag=b", "--mark", "x", "--flag", "--level", "high", "--ratio", "1.5", "--", "-f", "file.py"])
print("parsed:", args, options.verbose, options.quiet, options.repeat, options.select, options.max_line_length, options.indent_size, options.exclude, options.format, options.tags, options.seen, options.flag, options.level, options.ratio, options.config)
print("values:", type(options).__name__, type(options).__module__, options == Values(options.__dict__), options != Values(), options.ensure_value("extra", [1]), options.ensure_value("extra", [2]), sorted(options.__dict__)[:5], len(vars(options)))
options.__dict__.update({"select": ["E1"], "paths": ["x"], "reporter": None})
print("updated:", options.select, options.paths, options.reporter, "select" in options.__dict__, getattr(options, "max_line_" + "length"), getattr(options, "missing", "default"))
print("str:", str(Values({"a": 1, "b": "two"})), str(Values()), repr(Values({"z": 0})).partition(": ")[2], repr(Values()).startswith("<Values at 0x"))
print("empty:", parser.parse_args([])[0].__dict__, parser.parse_args([])[1], parser.parse_args(["only", "args"])[1], parser.parse_args(["-v"])[0].verbose)
print("abbrev:", parser.parse_args(["--max=50"])[0].max_line_length, parser.parse_args(["--ind", "2"])[0].indent_size, parser.parse_args(["--sel=E"])[0].select)
print("help:", parser.format_help().splitlines()[:3], len(parser.format_help().splitlines()), "default: 79" in parser.format_help(), "default: E24,W503" in parser.format_help(), parser.format_option_help().splitlines()[0], parser.format_description(parser.formatter).rstrip(), parser.format_epilog(parser.formatter).rstrip(), parser.expand_prog_name("%prog here"))
print("full help:", parser.format_help())
for argv in (["--nope"], ["--max-line-length"], ["--max-line-length", "ten"], ["--level", "mid"], ["--ratio", "x"], ["-x"], ["--f"], ["--select"], ["--version"], ["--help"]):
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result, err = with_stderr(lambda: parser.parse_args(argv))  # type: ignore[no-untyped-call]
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old
    print("argv", argv, result, repr(err), repr(out[:60]), len(out))
print("errors:", m(lambda: parser.add_option("--select")), m(lambda: parser.add_option("-v", "--other")), m(lambda: parser.add_option("--bad", type="nope")), m(lambda: parser.add_option("--bad", action="nope")), m(lambda: parser.add_option("--bad", type="choice")), m(lambda: parser.add_option("--bad", action="store_const").dest), m(lambda: parser.add_option("bad")), m(lambda: optparse.check_choice(parser.get_option("--level"), "--level", "mid")), m(lambda: optparse.check_builtin(parser.get_option("--ratio"), "--ratio", "1e400")))  # type: ignore[arg-type,no-untyped-call]
parser.set_conflict_handler("resolve")
parser.add_option("-v", "--volume", action="store", type="int", default=3)
print("resolved:", parser.get_option("-v").dest, parser.has_option("--verbose"), parser.parse_args(["-v", "7"])[0].volume, m(lambda: parser.parse_args(["-v", "7"])[0].verbose))  # type: ignore[no-untyped-call,union-attr]
print("exception types:", [c.__name__ for c in (optparse.OptParseError, optparse.OptionError, optparse.OptionConflictError, OptionValueError, optparse.BadOptionError, optparse.AmbiguousOptionError)], issubclass(optparse.BadOptionError, optparse.OptParseError), optparse.SUPPRESS_HELP, optparse.SUPPRESS_USAGE, optparse.NO_DEFAULT, optparse.Option.ACTIONS[:4], optparse.Option.TYPES)
print("values module:", Values.__module__, OptionParser.__module__, optparse.make_option is optparse.Option, optparse.OptionParser.__mro__[1].__name__, str(optparse.Option("-a", "--alpha", action="store_true")), optparse.Option("-a", "--alpha").get_opt_string(), optparse.Option("--beta", type="int").takes_value(), optparse.Option("-a").takes_value())
