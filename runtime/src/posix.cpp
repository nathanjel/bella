// The system calls under runtime/prelude/posix.py. A primitive makes one call and gives back what it gave, or a negative
// errno; the arguments have been checked in Python, in posixmodule.c's words.
#include <dirent.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <sys/times.h>
#include <sys/utsname.h>
#include <grp.h>
#include <langinfo.h>
#include <libintl.h>
#include <pwd.h>
#include <unistd.h>

#include <clocale>
#include <cwchar>

#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <new>
#include <string_view>

#include "bella/runtime.hpp"

extern char** environ;

namespace bella {
namespace {
const char* text_of(Obj v) { return bytes_data(v).c_str(); }   // no null inside: the Python side checked
std::int64_t i64_of(Obj v) {
    std::int64_t out = 0;
    int_fits_i64(v, out);
    return out;
}
int int_of(Obj v) { return static_cast<int>(i64_of(v)); }
Ref failed() { return int_from_i64(-errno); }
Ref int_from_u64(std::uint64_t v) {              // PyLong_FromUnsignedLongLong
    if (v <= static_cast<std::uint64_t>(INT64_MAX)) return int_from_i64(static_cast<std::int64_t>(v));
    Ref half = int_from_i64(static_cast<std::int64_t>(v >> 1)), one = int_from_i64(1);
    Ref doubled = big_binary(BinOp::Add, half.get(), half.get());
    return v & 1 ? big_binary(BinOp::Add, doubled.get(), one.get()) : doubled;
}
Ref result(std::int64_t r) { return r < 0 ? failed() : int_from_i64(r); }

Ref p_stat(Args a) {
    struct stat st{};
    int r;
    if (is_int(a.pos(0))) r = fstat(int_of(a.pos(0)), &st);
    else if (truth(a.pos(1))) r = stat(text_of(a.pos(0)), &st);
    else r = lstat(text_of(a.pos(0)), &st);
    if (r != 0) return failed();
    Ref fields[] = {int_from_u64(st.st_mode), int_from_u64(st.st_ino), int_from_u64(st.st_dev), int_from_u64(st.st_nlink), int_from_u64(st.st_uid),
                    int_from_u64(st.st_gid), int_from_i64(st.st_size), int_from_i64(st.st_atim.tv_sec), int_from_i64(st.st_atim.tv_nsec),
                    int_from_i64(st.st_mtim.tv_sec), int_from_i64(st.st_mtim.tv_nsec), int_from_i64(st.st_ctim.tv_sec), int_from_i64(st.st_ctim.tv_nsec),
                    int_from_i64(st.st_blksize), int_from_i64(st.st_blocks), int_from_u64(st.st_rdev)};
    std::vector<Obj> out;
    for (Ref& f : fields) out.push_back(f.release());
    return tuple_steal(std::move(out));
}
Ref p_getcwd(Args) {
    std::string buf(PATH_MAX, '\0');
    if (getcwd(buf.data(), buf.size()) == nullptr) return failed();
    return bytes_new(buf.c_str());
}
Ref p_listdir(Args a) {                          // _posix_listdir: readdir's order, without . and ..
    bool by_fd = is_int(a.pos(0));
    DIR* d;
    if (by_fd) {
        int fd = int_of(a.pos(0));               // a duplicate, which closedir closes
        d = fdopendir(fd);
        if (d == nullptr) {
            int saved = errno;
            close(fd);
            errno = saved;
        }
    } else {
        d = opendir(text_of(a.pos(0)));
    }
    if (d == nullptr) return failed();
    Ref names = list_new({});
    while (true) {
        errno = 0;
        dirent* e = readdir(d);
        if (e == nullptr) break;
        std::string_view n(e->d_name);
        if (n == "." || n == "..") continue;
        Ref item = bytes_new(n);
        list_append(names.get(), item.get());
    }
    int saved = errno;
    if (by_fd) rewinddir(d);                     // the duplicate shares the offset
    closedir(d);
    if (saved != 0) return int_from_i64(-saved);
    return names;
}
Ref p_dup(Args a) { return result(fcntl(int_of(a.pos(0)), F_DUPFD_CLOEXEC, 0)); }   // _Py_dup: not inheritable
Ref p_rmdir(Args a) { return result(rmdir(text_of(a.pos(0)))); }
Ref p_unlink(Args a) { return result(unlink(text_of(a.pos(0)))); }
Ref p_mkdir(Args a) { return result(mkdir(text_of(a.pos(0)), static_cast<mode_t>(int_of(a.pos(1))))); }
Ref p_rename(Args a) { return result(rename(text_of(a.pos(0)), text_of(a.pos(1)))); }
Ref p_chdir(Args a) {
    if (is_int(a.pos(0))) return result(fchdir(int_of(a.pos(0))));
    return result(chdir(text_of(a.pos(0))));
}
Ref p_access(Args a) { return result(access(text_of(a.pos(0)), int_of(a.pos(1)))); }
Ref p_readlink(Args a) {
    std::string buf(PATH_MAX, '\0');
    ssize_t n = readlink(text_of(a.pos(0)), buf.data(), buf.size());
    if (n < 0) return failed();
    return bytes_new(std::string_view(buf.data(), static_cast<std::size_t>(n)));
}
Ref p_symlink(Args a) { return result(symlink(text_of(a.pos(0)), text_of(a.pos(1)))); }
Ref p_link(Args a) { return result(linkat(AT_FDCWD, text_of(a.pos(0)), AT_FDCWD, text_of(a.pos(1)), truth(a.pos(2)) ? AT_SYMLINK_FOLLOW : 0)); }
Ref p_open(Args a) {                             // _Py_open's: not inheritable (PEP 446), and again after a signal
    int fd;
    do fd = open(text_of(a.pos(0)), int_of(a.pos(1)) | O_CLOEXEC, static_cast<mode_t>(int_of(a.pos(2))));
    while (fd < 0 && errno == EINTR);
    return result(fd);
}
Ref p_close(Args a) { return result(close(int_of(a.pos(0)))); }
Ref p_read(Args a) {
    std::size_t length = static_cast<std::size_t>(i64_of(a.pos(1)));
    std::unique_ptr<char[]> buf;
    try {
        buf = std::make_unique_for_overwrite<char[]>(length);   // as the C's, not touched before the call fills it
    } catch (const std::bad_alloc&) {
        raise_new("MemoryError", "");
    }
    ssize_t n;
    do n = read(int_of(a.pos(0)), buf.get(), length);
    while (n < 0 && errno == EINTR);
    if (n < 0) return failed();
    return bytes_new(std::string_view(buf.get(), static_cast<std::size_t>(n)));
}
Ref p_write(Args a) {
    const std::string& data = bytes_data(a.pos(1));
    ssize_t n;
    do n = write(int_of(a.pos(0)), data.data(), data.size());
    while (n < 0 && errno == EINTR);
    return result(n);
}
Ref p_lseek(Args a) { return result(lseek(int_of(a.pos(0)), i64_of(a.pos(1)), int_of(a.pos(2)))); }
Ref p_isatty(Args a) { return int_from_i64(isatty(int_of(a.pos(0)))); }
Ref p_fsync(Args a) { return result(fsync(int_of(a.pos(0)))); }
Ref p_ftruncate(Args a) { return result(ftruncate(int_of(a.pos(0)), i64_of(a.pos(1)))); }
Ref p_strerror(Args a) { return str_new(std::strerror(int_of(a.pos(0)))); }
Ref p_umask(Args a) { return int_from_i64(umask(static_cast<mode_t>(int_of(a.pos(0))))); }
Ref p_urandom(Args a) {
    std::string buf(static_cast<std::size_t>(i64_of(a.pos(0))), '\0');
    std::size_t done = 0;
    while (done < buf.size()) {
        ssize_t n = getrandom(buf.data() + done, buf.size() - done, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            throw NotImplemented("os.urandom when getrandom fails");
        }
        done += static_cast<std::size_t>(n);
    }
    return bytes_new(buf);
}
Ref p_cpu_count(Args) { return int_from_i64(sysconf(_SC_NPROCESSORS_ONLN)); }
Ref p_terminal_size(Args a) {
    winsize w{};
    if (ioctl(int_of(a.pos(0)), TIOCGWINSZ, &w) != 0) return failed();
    Ref columns = int_from_i64(w.ws_col), lines = int_from_i64(w.ws_row);
    return tuple_new({columns.get(), lines.get()});
}
Ref p_uname(Args) {
    utsname u{};
    if (uname(&u) != 0) return failed();
    Ref a = bytes_new(u.sysname), b = bytes_new(u.nodename), c = bytes_new(u.release), d = bytes_new(u.version), e = bytes_new(u.machine);
    return tuple_new({a.get(), b.get(), c.get(), d.get(), e.get()});
}
Ref p_times(Args) {
    tms t{};
    clock_t elapsed = times(&t);
    if (elapsed == static_cast<clock_t>(-1)) return failed();
    double ticks = static_cast<double>(sysconf(_SC_CLK_TCK));
    Ref a = float_ref(static_cast<double>(t.tms_utime) / ticks), b = float_ref(static_cast<double>(t.tms_stime) / ticks),
        c = float_ref(static_cast<double>(t.tms_cutime) / ticks), d = float_ref(static_cast<double>(t.tms_cstime) / ticks),
        e = float_ref(static_cast<double>(elapsed) / ticks);
    return tuple_new({a.get(), b.get(), c.get(), d.get(), e.get()});
}
Ref p_getpid(Args) { return int_from_i64(getpid()); }
Ref p_getppid(Args) { return int_from_i64(getppid()); }
// the password and group databases (pwdmodule.c, grpmodule.c): an entry's fields as bytes and ints, None when there is none
Ref passwd_entry(const passwd* p) {
    if (p == nullptr) return none_ref();
    Ref name = bytes_new(p->pw_name), passwd = bytes_new(p->pw_passwd == nullptr ? "" : p->pw_passwd), uid = int_from_u64(p->pw_uid), gid = int_from_u64(p->pw_gid),
        gecos = bytes_new(p->pw_gecos == nullptr ? "" : p->pw_gecos), dir = bytes_new(p->pw_dir == nullptr ? "" : p->pw_dir), shell = bytes_new(p->pw_shell == nullptr ? "" : p->pw_shell);
    return tuple_new({name.get(), passwd.get(), uid.get(), gid.get(), gecos.get(), dir.get(), shell.get()});
}
Ref group_entry(const group* g) {
    if (g == nullptr) return none_ref();
    Ref members = list_new({});
    for (char** m = g->gr_mem; m != nullptr && *m != nullptr; ++m) {
        Ref member = bytes_new(*m);
        list_append(members.get(), member.get());
    }
    Ref name = bytes_new(g->gr_name), passwd = bytes_new(g->gr_passwd == nullptr ? "" : g->gr_passwd), gid = int_from_u64(g->gr_gid);
    return tuple_new({name.get(), passwd.get(), gid.get(), members.get()});
}
Ref p_getpwuid(Args a) { errno = 0; return passwd_entry(getpwuid(static_cast<uid_t>(i64_of(a.pos(0))))); }
Ref p_getpwnam(Args a) { errno = 0; return passwd_entry(getpwnam(bytes_data(a.pos(0)).c_str())); }
Ref p_getpwall(Args) {
    Ref out = list_new({});
    setpwent();
    while (const passwd* p = getpwent()) {
        Ref e = passwd_entry(p);
        list_append(out.get(), e.get());
    }
    endpwent();
    return out;
}
Ref p_getgrgid(Args a) { errno = 0; return group_entry(getgrgid(static_cast<gid_t>(i64_of(a.pos(0))))); }
Ref p_getgrnam(Args a) { errno = 0; return group_entry(getgrnam(bytes_data(a.pos(0)).c_str())); }
Ref p_getgrall(Args) {
    Ref out = list_new({});
    setgrent();
    while (const group* g = getgrent()) {
        Ref e = group_entry(g);
        list_append(out.get(), e.get());
    }
    endgrent();
    return out;
}
// the C library's locale (Modules/_localemodule.c): bytes in, bytes out, None for NULL
Ref bytes_or_none(const char* s) { return s == nullptr ? none_ref() : bytes_new(s); }
const char* c_string_or_null(Obj v) { return v == None() ? nullptr : bytes_data(v).c_str(); }
Ref p_setlocale(Args a) { return bytes_or_none(setlocale(int_of(a.pos(0)), c_string_or_null(a.pos(1)))); }
Ref grouping_list(const char* s) {               // copy_grouping: the bytes up to a 0, CHAR_MAX included when it ends the run
    Ref out = list_new({});
    if (s == nullptr || s[0] == '\0') return out;
    for (std::size_t i = 0;; ++i) {
        Ref v = int_from_i64(static_cast<signed char>(s[i]));
        list_append(out.get(), v.get());
        if (s[i] == 0 || s[i] == CHAR_MAX) break;
    }
    return out;
}
Ref p_localeconv(Args) {                         // (name, value) pairs in the order the C module builds its dict
    lconv* l = localeconv();
    Ref out = list_new({});
    auto text = [&](const char* name, const char* value) {
        Ref n = str_new(name), v = bytes_new(value == nullptr ? "" : value), pair = tuple_new({n.get(), v.get()});
        list_append(out.get(), pair.get());
    };
    auto number = [&](const char* name, char value) {
        Ref n = str_new(name), v = int_from_i64(static_cast<signed char>(value)), pair = tuple_new({n.get(), v.get()});
        list_append(out.get(), pair.get());
    };
    auto grouping = [&](const char* name, const char* value) {
        Ref n = str_new(name), v = grouping_list(value), pair = tuple_new({n.get(), v.get()});
        list_append(out.get(), pair.get());
    };
    text("int_curr_symbol", l->int_curr_symbol);
    text("currency_symbol", l->currency_symbol);
    text("mon_decimal_point", l->mon_decimal_point);
    text("mon_thousands_sep", l->mon_thousands_sep);
    grouping("mon_grouping", l->mon_grouping);
    text("positive_sign", l->positive_sign);
    text("negative_sign", l->negative_sign);
    number("int_frac_digits", l->int_frac_digits);
    number("frac_digits", l->frac_digits);
    number("p_cs_precedes", l->p_cs_precedes);
    number("p_sep_by_space", l->p_sep_by_space);
    number("n_cs_precedes", l->n_cs_precedes);
    number("n_sep_by_space", l->n_sep_by_space);
    number("p_sign_posn", l->p_sign_posn);
    number("n_sign_posn", l->n_sign_posn);
    text("decimal_point", l->decimal_point);
    text("thousands_sep", l->thousands_sep);
    grouping("grouping", l->grouping);
    return out;
}
std::wstring wide_of(Obj v) {                    // PyUnicode_AsWideCharString: the code points, wchar_t being UCS-4 here
    const Str* s = as_str(v);
    std::wstring out;
    for (std::size_t i = 0; i < s->length; ++i) out += static_cast<wchar_t>(s->at(i));
    return out;
}
Ref p_strcoll(Args a) { return int_from_i64(wcscoll(wide_of(a.pos(0)).c_str(), wide_of(a.pos(1)).c_str())); }
Ref p_strxfrm(Args a) {
    std::wstring s = wide_of(a.pos(0));
    std::size_t n = wcsxfrm(nullptr, s.c_str(), 0);
    std::wstring out(n + 1, L'\0');
    wcsxfrm(out.data(), s.c_str(), n + 1);
    std::u32string cps;
    for (std::size_t i = 0; i < n; ++i) cps += static_cast<char32_t>(out[i]);
    return str_from_codepoints(cps);
}
Ref p_nl_langinfo(Args a) { return bytes_or_none(nl_langinfo(static_cast<nl_item>(int_of(a.pos(0))))); }
Ref p_gettext(Args a) {                          // (domain or None, msg, category or None): gettext, dgettext, dcgettext
    const char* msg = bytes_data(a.pos(1)).c_str();
    if (a.pos(0) == None()) return bytes_new(gettext(msg));
    if (a.pos(2) == None()) return bytes_new(dgettext(bytes_data(a.pos(0)).c_str(), msg));
    return bytes_new(dcgettext(bytes_data(a.pos(0)).c_str(), msg, int_of(a.pos(2))));
}
Ref p_textdomain(Args a) { return bytes_or_none(textdomain(c_string_or_null(a.pos(0)))); }
Ref p_bindtextdomain(Args a) { return bytes_or_none(bindtextdomain(bytes_data(a.pos(0)).c_str(), c_string_or_null(a.pos(1)))); }
Ref p_bind_textdomain_codeset(Args a) { return bytes_or_none(bind_textdomain_codeset(bytes_data(a.pos(0)).c_str(), c_string_or_null(a.pos(1)))); }
Ref p_getuid(Args) { return int_from_u64(getuid()); }
Ref p_geteuid(Args) { return int_from_u64(geteuid()); }
Ref p_getgid(Args) { return int_from_u64(getgid()); }
Ref p_getegid(Args) { return int_from_u64(getegid()); }
Ref p_putenv(Args a) { return result(setenv(text_of(a.pos(0)), text_of(a.pos(1)), 1)); }
Ref p_unsetenv(Args a) { return result(unsetenv(text_of(a.pos(0)))); }
Ref p_clearenv(Args) { return result(clearenv()); }
Ref p_exit(Args a) { _exit(int_of(a.pos(0))); }
Ref p_environ(Args) {                            // convertenviron: of a name given twice, the first stands
    Ref d = dict_new();
    auto* dict = static_cast<Dict*>(d.get().object());
    for (char** e = environ; e != nullptr && *e != nullptr; ++e) {
        std::string_view entry(*e);
        std::size_t eq = entry.find('=');
        if (eq == std::string_view::npos) continue;
        Ref k = bytes_new(entry.substr(0, eq)), v = bytes_new(entry.substr(eq + 1));
        if (dict_get(dict, k.get()).is_unset()) dict_set(dict, k.get(), v.get());
    }
    return d;
}
Ref p_refuse(Args a) { throw NotImplemented(as_str(a.pos(0))->text + " (CPython has it; the runtime does not yet)"); }

using Primitive = Ref (*)(Args);
const std::map<std::string_view, Primitive>& primitives() {
    static const std::map<std::string_view, Primitive> table{
        {"stat", p_stat}, {"getcwd", p_getcwd}, {"listdir", p_listdir}, {"dup", p_dup}, {"rmdir", p_rmdir}, {"unlink", p_unlink}, {"mkdir", p_mkdir},
        {"rename", p_rename}, {"chdir", p_chdir}, {"access", p_access}, {"readlink", p_readlink}, {"symlink", p_symlink}, {"link", p_link},
        {"open", p_open}, {"close", p_close}, {"read", p_read}, {"write", p_write}, {"lseek", p_lseek}, {"isatty", p_isatty}, {"fsync", p_fsync}, {"ftruncate", p_ftruncate},
        {"strerror", p_strerror}, {"umask", p_umask}, {"urandom", p_urandom}, {"cpu_count", p_cpu_count}, {"terminal_size", p_terminal_size},
        {"uname", p_uname}, {"times", p_times}, {"getpid", p_getpid}, {"getppid", p_getppid}, {"getuid", p_getuid}, {"geteuid", p_geteuid},
        {"getgid", p_getgid}, {"getegid", p_getegid}, {"putenv", p_putenv}, {"unsetenv", p_unsetenv}, {"clearenv", p_clearenv}, {"exit", p_exit},
        {"environ", p_environ}, {"refuse", p_refuse}, {"getpwuid", p_getpwuid}, {"getpwnam", p_getpwnam}, {"getpwall", p_getpwall},
        {"getgrgid", p_getgrgid}, {"getgrnam", p_getgrnam}, {"getgrall", p_getgrall}, {"setlocale", p_setlocale}, {"localeconv", p_localeconv},
        {"strcoll", p_strcoll}, {"strxfrm", p_strxfrm}, {"nl_langinfo", p_nl_langinfo}, {"gettext", p_gettext}, {"textdomain", p_textdomain},
        {"bindtextdomain", p_bindtextdomain}, {"bind_textdomain_codeset", p_bind_textdomain_codeset}};
    return table;
}
}  // namespace

Ref i_posix_sys(Obj, Args a) {                   // _sys(name, ...)
    return primitives().at(as_str(a.pos(0))->text)(Args{a.data + 1, a.npos - 1, nullptr, 0});
}
// _Py_SetLocaleFromEnv(LC_CTYPE), then _Py_CoerceLegacyLocale (PEP 538): the C locale becomes the first of C.UTF-8, C.utf8 and
// UTF-8 the library has, and LC_CTYPE in the environment says so; PYTHONCOERCECLOCALE=0 leaves it
void set_locale_from_environment() {
    const char* set = setlocale(LC_CTYPE, "");
    if (const char* opt = std::getenv("PYTHONCOERCECLOCALE"); opt != nullptr && std::string_view(opt) == "0") return;
    if (const char* all = std::getenv("LC_ALL"); all != nullptr && *all != '\0') return;   // _Py_LegacyLocaleDetected: LC_ALL set is not coerced (A13 #4)
    if (set == nullptr || (std::string_view(set) != "C" && std::string_view(set) != "POSIX")) return;
    for (const char* target : {"C.UTF-8", "C.utf8", "UTF-8"})
        if (setlocale(LC_CTYPE, target) != nullptr) {
            setenv("LC_CTYPE", target, 1);
            return;
        }
}
}  // namespace bella
