# clause: C-7-31
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/pwdmodule.c, Modules/grpmodule.c, Modules/_localemodule.c
"""pwd and grp over the system databases (root exists everywhere), and _locale in the C and C.UTF-8 locales: what the C library answers, the
conversions and the errors. What depends on the environment's locale is set to a known one first."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001
import _locale
import gettext
import grp
import locale
import pwd


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


root = pwd.getpwuid(0)
print(type(root).__name__, type(root).__module__, [c.__name__ for c in type(root).__mro__], type(root).n_fields, type(root).n_sequence_fields, type(root).__match_args__, len(root), root.pw_name, root.pw_uid, root.pw_gid, root[0], root[2], root == pwd.getpwnam("root"), root in pwd.getpwall(), type(pwd.getpwall()).__name__, len(pwd.getpwall()) >= 1)
print(failed(lambda: pwd.getpwuid(-2)), failed(lambda: pwd.getpwuid("a")), failed(lambda: pwd.getpwuid(2**70)), failed(lambda: pwd.getpwuid(1.5)), failed(lambda: pwd.getpwnam("no such user, surely")), failed(lambda: pwd.getpwnam(1)), failed(lambda: pwd.getpwnam("a\0b")), failed(lambda: pwd.getpwnam()), failed(lambda: pwd.getpwuid(0, 1)), failed(lambda: pwd.getpwnam(name="root")), failed(lambda: pwd.getpwall(1)), failed(lambda: pwd.struct_passwd(range(7))), failed(lambda: pwd.struct_passwd(range(2))))  # type: ignore[arg-type,call-arg,no-untyped-call]
rootgroup = grp.getgrgid(0)
print(type(rootgroup).__name__, type(rootgroup).__module__, type(rootgroup).n_fields, type(rootgroup).__match_args__, len(rootgroup), rootgroup.gr_name, rootgroup.gr_gid, type(rootgroup.gr_mem).__name__, rootgroup == grp.getgrnam("root"), rootgroup in grp.getgrall(), grp.getgrgid(id=0).gr_gid, grp.getgrnam(name="root").gr_gid)
print(failed(lambda: grp.getgrgid(-2)), failed(lambda: grp.getgrgid("a")), failed(lambda: grp.getgrnam("no such group, surely")), failed(lambda: grp.getgrnam(1)), failed(lambda: grp.getgrgid(1.5)), failed(lambda: grp.getgrgid()), failed(lambda: grp.getgrgid(0, 1)), failed(lambda: grp.getgrgid(x=1)), failed(lambda: grp.getgrgid(2**70)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(sorted(n for n in dir(pwd) if not n.startswith("__")), sorted(n for n in dir(grp) if not n.startswith("__")))

print(_locale.Error, _locale.Error.__module__, [c.__name__ for c in _locale.Error.__mro__], _locale.CHAR_MAX, _locale.LC_CTYPE, _locale.LC_NUMERIC, _locale.LC_TIME, _locale.LC_COLLATE, _locale.LC_MONETARY, _locale.LC_MESSAGES, _locale.LC_ALL, _locale.CODESET, _locale.D_FMT, _locale.RADIXCHAR, _locale.THOUSEP, _locale.YESEXPR, _locale.NOEXPR, _locale.CRNCYSTR, _locale.ERA, _locale.ALT_DIGITS, _locale.ABDAY_1, _locale.MON_12, locale.Error is _locale.Error)  # type: ignore[attr-defined]
print(_locale.setlocale(_locale.LC_ALL, "C"), _locale.setlocale(_locale.LC_ALL), _locale.setlocale(_locale.LC_CTYPE), _locale.localeconv(), _locale.nl_langinfo(_locale.CODESET), _locale.getencoding(), _locale.nl_langinfo(_locale.D_FMT), _locale.nl_langinfo(_locale.T_FMT), _locale.nl_langinfo(_locale.RADIXCHAR), _locale.nl_langinfo(_locale.THOUSEP), _locale.nl_langinfo(_locale.YESEXPR), _locale.nl_langinfo(_locale.DAY_1), _locale.nl_langinfo(_locale.ABMON_1), _locale.nl_langinfo(_locale.AM_STR))
print(_locale.strcoll("a", "b"), _locale.strcoll("b", "a"), _locale.strcoll("a", "a"), _locale.strcoll("ab", "a"), _locale.strxfrm("abc"), _locale.strxfrm(""), locale.strcoll("x", "y"), locale.strxfrm("q"), locale.getlocale(), locale.getencoding(), locale.getpreferredencoding(), locale.getpreferredencoding(False), locale.normalize("en_us"), locale.normalize("C"), locale.normalize("UTF-8"), locale.localeconv()["decimal_point"], locale.str(1.5), locale.atof("2.5"), locale.atoi("42"), locale.format_string("%d", 1234, grouping=True), locale.format_string("%.2f", 3.14159), locale.delocalize("1.5"), locale.currency(3.5) if False else None)
print(failed(lambda: _locale.setlocale(_locale.LC_ALL, "surely_no_such_locale.XYZ")), failed(lambda: _locale.setlocale(99)), failed(lambda: _locale.setlocale("a")), failed(lambda: _locale.setlocale(6, 1)), failed(lambda: _locale.setlocale()), failed(lambda: _locale.setlocale(6, "a\0b")), failed(lambda: _locale.setlocale(category=6, locale="C")), failed(lambda: _locale.localeconv(1)), failed(lambda: _locale.strcoll("a", 1)), failed(lambda: _locale.strcoll("a")), failed(lambda: _locale.strxfrm(1)), failed(lambda: _locale.strxfrm("a\0b")), failed(lambda: _locale.nl_langinfo(999999)), failed(lambda: _locale.nl_langinfo("a")), failed(lambda: _locale.nl_langinfo(-1)), failed(lambda: _locale.getencoding(1)), failed(lambda: locale.setlocale(locale.LC_ALL, "xx")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(_locale.gettext("msg"), _locale.dgettext("dom", "msg"), _locale.dgettext(None, "msg"), _locale.dcgettext("d", "m", 5), _locale.dcgettext(None, "m", 5), _locale.textdomain(None), _locale.textdomain("mine"), _locale.textdomain(None), _locale.bindtextdomain("dom", None), _locale.bindtextdomain("dom", "/tmp"), _locale.bindtextdomain("dom", None), _locale.bind_textdomain_codeset("dom", None), _locale.bind_textdomain_codeset("dom", "UTF-8"), failed(lambda: _locale.gettext(1)), failed(lambda: _locale.textdomain(1)), failed(lambda: _locale.bindtextdomain(1, None)), failed(lambda: _locale.bind_textdomain_codeset(1, None)), failed(lambda: _locale.dgettext(1, "m")))  # type: ignore[arg-type,no-untyped-call]
print(_locale.setlocale(_locale.LC_ALL, "C.UTF-8"), _locale.nl_langinfo(_locale.CODESET), _locale.getencoding(), locale.getlocale(), locale.getencoding(), _locale.strcoll("a", "b"), _locale.strcoll("é", "f"), _locale.localeconv()["decimal_point"], _locale.setlocale(_locale.LC_ALL, "C"))
print(gettext.gettext("hello"), gettext.ngettext("one", "many", 2), gettext.find("nothing-of-that-name"), gettext.translation("nothing", fallback=True).gettext("x"), gettext.dgettext("d", "y"), gettext.textdomain())
