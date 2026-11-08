# clause: C-7-49
# spec: section 7
# status: P1
# source: dialect specification section 7, Lib/configparser.py (admitted 2026-11-08, docs/targets.md section 5 item 3)
"""configparser, as pycodestyle reads its project files and more: RawConfigParser and ConfigParser over strings and files
(read_string, read_file, read_dict, read of a list of paths, present and absent), sections and options, the mapping protocol,
the typed getters with fallbacks, defaults and the DEFAULT section, basic and extended interpolation (and its errors),
comments, multi-line values, empty values, strict mode's duplicates, optionxform and case, write back, remove, and the error
classes with their messages."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import configparser
import io
import os
import tempfile
from configparser import ConfigParser, ExtendedInterpolation, RawConfigParser


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


TOX = """
# a project's tox.ini
[tox]
envlist = py315
skipsdist = True

[pycodestyle]
max-line-length = 88
exclude = .git,
    build ,
    dist
select =
ignore = W6,E24  ; trailing comment
count = yes
statistics = off

[flake8]
max-complexity = 10
"""

config = RawConfigParser()
print("read:", config.read_string(TOX), config.sections(), config.has_section("pycodestyle"), config.has_section("nope"), config.has_option("pycodestyle", "count"), config.has_option("pycodestyle", "nope"), config.has_option("nope", "x"), sorted(config.options("pycodestyle")), config.defaults(), config.default_section)  # type: ignore[func-returns-value]
print("values:", repr(config.get("pycodestyle", "max-line-length")), repr(config.get("pycodestyle", "exclude")), repr(config.get("pycodestyle", "select")), repr(config.get("pycodestyle", "ignore")), config.getint("pycodestyle", "max-line-length"), config.getboolean("pycodestyle", "count"), config.getboolean("pycodestyle", "statistics"), config.getfloat("flake8", "max-complexity"), config.get("tox", "skipsdist"), config.getboolean("tox", "skipsdist"))
print("items:", config.items("tox"), sorted(config.items("flake8")), list(config["pycodestyle"]), config["pycodestyle"]["count"], config["tox"].get("envlist"), config["tox"].get("missing", "dflt"), "tox" in config, "nope" in config, len(config), sorted(config)[:2], config["pycodestyle"].name, type(config["pycodestyle"]).__name__)
print("fallbacks:", config.get("pycodestyle", "nope", fallback="fb"), config.getint("pycodestyle", "nope", fallback=-1), config.getboolean("nope", "x", fallback=None), config["pycodestyle"].getint("max-line-length"), config["pycodestyle"].getboolean("count"), config["pycodestyle"].getint("nope", 7), config["pycodestyle"].getfloat("max-line-length"))
print("errors:", m(lambda: config.get("nope", "x")), m(lambda: config.get("pycodestyle", "nope")), m(lambda: config.getint("pycodestyle", "exclude")), m(lambda: config.getboolean("pycodestyle", "exclude")), m(lambda: config["nope"]), m(lambda: config["pycodestyle"]["nope"]), m(lambda: config.options("nope")), m(lambda: config.items("nope")), m(lambda: config.add_section("tox")), m(lambda: config.add_section("DEFAULT")), m(lambda: config.set("nope", "a", "b")), m(lambda: config.remove_option("nope", "a")), m(lambda: config.add_section(1)))  # type: ignore[arg-type,no-untyped-call]

# pycodestyle's loop: read([paths]) answers the files it could read; a missing file is skipped
with tempfile.TemporaryDirectory() as tmp:
    setup = os.path.join(tmp, "setup.cfg")
    with open(setup, "w", encoding="utf-8") as f:
        f.write("[pycodestyle]\nmax_line_length = 100\nhang-closing = true\n\n[other]\nkey = value\n")
    c2 = RawConfigParser()
    found = c2.read([os.path.join(tmp, "tox.ini"), setup, os.path.join(tmp, "setup.cfg")])
    print("files:", [os.path.basename(p) for p in found], c2.sections(), c2.get("pycodestyle", "max_line_length"), c2.getboolean("pycodestyle", "hang-closing"), c2.read(os.path.join(tmp, "absent.ini")), c2.read([]))
    c3 = RawConfigParser()
    with open(setup, encoding="utf-8") as f:
        c3.read_file(f, source="setup.cfg")
    print("read_file:", c3.sections(), c3["other"]["key"], m(lambda: RawConfigParser().read_file(io.StringIO("no section\n"), source="s")), m(lambda: RawConfigParser().read_file(io.StringIO("[a]\nbad line\n"))), m(lambda: RawConfigParser().read_string("[a]\nk = 1\nk = 2\n")), m(lambda: RawConfigParser().read_string("[a]\n[a]\n")), m(lambda: RawConfigParser().read_string("[unclosed\n")))  # type: ignore[no-untyped-call]
    out = io.StringIO()
    c3.set("other", "added", "1")
    c3["other"]["spaced"] = "two words"
    c3.write(out)
    print("write:", out.getvalue())
    out2 = io.StringIO()
    c3.write(out2, space_around_delimiters=False)
    print("write tight:", out2.getvalue().splitlines()[:3])

# ConfigParser: interpolation, DEFAULT and case
cp = ConfigParser(defaults={"home": "/h", "shell": "%(home)s/sh"})
cp.read_dict({"paths": {"bin": "%(home)s/bin", "log": "%(bin)s/log", "pct": "100%%"}, "Case": {"MixedKey": "v"}})
print("basic:", cp.get("paths", "bin"), cp.get("paths", "log"), cp.get("paths", "pct"), cp.get("paths", "shell"), cp.get("paths", "log", raw=True), cp.get("paths", "home", vars={"home": "/x"}), cp.get("paths", "bin", vars={"home": "/x"}), cp["paths"]["log"], sorted(cp["paths"]), cp.sections(), cp.get("Case", "mixedkey"), cp.has_option("Case", "MIXEDKEY"), cp.optionxform("ABC"), cp.getint("paths", "missing", fallback=0))
print("interpolation errors:", m(lambda: ConfigParser().read_dict({"s": {"a": "%(nope)s"}}) or ConfigParser), m(lambda: (lambda c: (c.read_dict({"s": {"a": "%(nope)s"}}), c.get("s", "a")))(ConfigParser())), m(lambda: (lambda c: (c.read_dict({"s": {"a": "%(b)s", "b": "%(a)s"}}), c.get("s", "a")))(ConfigParser())), m(lambda: (lambda c: (c.read_dict({"s": {"a": "50%"}}), c.get("s", "a")))(ConfigParser())), m(lambda: (lambda c: (c.read_dict({"s": {"a": "%z"}}), c.get("s", "a")))(ConfigParser())), m(lambda: ConfigParser().set("DEFAULT", "a", "%(x")), m(lambda: ConfigParser().set("DEFAULT", "a", 1)), m(lambda: RawConfigParser().set("DEFAULT", "a", 1)))  # type: ignore[arg-type,func-returns-value,no-untyped-call]
ext = ConfigParser(interpolation=ExtendedInterpolation())
ext.read_string("[common]\nroot = /srv\n[app]\nhome = ${common:root}/app\nlogs = ${home}/logs\nliteral = $$5\n")
print("extended:", ext["app"]["home"], ext["app"]["logs"], ext["app"]["literal"], ext.get("app", "logs", raw=True), m(lambda: ext.get("app", "x", vars={"x": "${common:nope}"})), m(lambda: ext.get("app", "x", vars={"x": "${a:b:c}"})), m(lambda: ext.get("app", "x", vars={"x": "$x"})))  # type: ignore[no-untyped-call]
nocase = ConfigParser()
nocase.optionxform = str  # type: ignore[assignment,method-assign]
nocase.read_string("[S]\nKey = 1\nkey = 2\n")
print("case kept:", list(nocase["S"]), nocase["S"]["Key"], nocase["S"]["key"])
lax = RawConfigParser(strict=False, allow_no_value=True, delimiters=("=", ":"), comment_prefixes=("#", ";"), inline_comment_prefixes=("#",), empty_lines_in_values=False)
lax.read_string("[a]\nk = 1\nk = 2\nflag\nc: 3 # note\nmulti = one\n  two\n\n  three\n[a]\nk = 4\n")
print("lax:", dict(lax["a"]), lax.get("a", "flag"), lax.getint("a", "k"))
cv = RawConfigParser()
cv.read_string("[b]\nt1 = 1\nt2 = yes\nt3 = TRUE\nt4 = On\nf1 = 0\nf2 = no\nf3 = False\nf4 = OFF\nbad = maybe\n")
print("booleans:", [cv.getboolean("b", k) for k in ("t1", "t2", "t3", "t4", "f1", "f2", "f3", "f4")], m(lambda: cv.getboolean("b", "bad")), sorted(cv.BOOLEAN_STATES), sorted(cv.converters.keys()), type(cv.converters).__name__)  # type: ignore[no-untyped-call]
custom = RawConfigParser(converters={"list": lambda v: [x.strip() for x in v.split(",")]})
custom.read_string("[c]\nitems = a, b ,c\n")
print("converters:", custom.getlist("c", "items"), custom["c"].getlist("items"), custom.getlist("c", "nope", fallback=[]), m(lambda: custom.getlist("c", "nope")))  # type: ignore[attr-defined,no-untyped-call]
print("remove:", config.remove_option("pycodestyle", "count"), config.remove_option("pycodestyle", "count"), config.has_option("pycodestyle", "count"), config.remove_section("flake8"), config.remove_section("flake8"), config.sections())
del config["tox"]
print("del:", config.sections(), m(lambda: config.__delitem__("tox")), m(lambda: config.__delitem__("DEFAULT")), m(lambda: config.__setitem__("DEFAULT", {"a": "1"})), config.defaults(), config.get("pycodestyle", "a"))  # type: ignore[no-untyped-call]
print("exceptions:", [c.__name__ for c in (configparser.Error, configparser.NoSectionError, configparser.DuplicateSectionError, configparser.DuplicateOptionError, configparser.NoOptionError, configparser.InterpolationError, configparser.InterpolationDepthError, configparser.InterpolationMissingOptionError, configparser.InterpolationSyntaxError, configparser.ParsingError, configparser.MissingSectionHeaderError, configparser.MultilineContinuationError, configparser.UnnamedSectionDisabledError, configparser.InvalidWriteError)], configparser.MAX_INTERPOLATION_DEPTH, configparser.DEFAULTSECT, configparser.UNNAMED_SECTION, configparser.ConfigParser.__mro__[1].__name__, repr(configparser.NoSectionError("s").section), repr(configparser.NoOptionError("o", "s").args))
