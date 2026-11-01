# clause: C-7-13
# spec: section 7
# status: P1
# source: dialect specification section 7, Internationalisation (the C and UTF-8 subset of locale; gettext)
"""The phase-1 subset: the C locale and gettext without catalogues (NullTranslations and the
fallback path argparse uses)."""
import gettext
import locale

print(locale.setlocale(locale.LC_ALL, "C"), locale.localeconv()["decimal_point"], repr(locale.localeconv()["thousands_sep"]))
print(locale.format_string("%.2f", 1234.5, grouping=True), locale.str(2.5), locale.atof("3.25"), locale.atoi("12"))
print(locale.strcoll("a", "b") < 0, locale.strxfrm("abc"), locale.normalize("c.utf8"))
null = gettext.NullTranslations()
print(null.gettext("hello"), null.ngettext("one file", "{n} files", 2), null.pgettext("menu", "Open"))
t = gettext.translation("bella_no_such_domain", localedir="/nonexistent", fallback=True)
print(type(t).__name__, t.gettext("text"), gettext.gettext("plain"), gettext.ngettext("a", "b", 1))
try:
    gettext.translation("bella_no_such_domain", localedir="/nonexistent")
except FileNotFoundError as exc:
    print("no catalogue:", type(exc).__name__)
