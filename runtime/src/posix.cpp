// The system calls under runtime/prelude/posix.py. A primitive makes one call and gives back what it gave, or a negative
// errno; the arguments have been checked in Python, in posixmodule.c's words.
#include <dirent.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <sys/times.h>
#include <sys/utsname.h>
#include <unistd.h>

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
        {"environ", p_environ}, {"refuse", p_refuse}};
    return table;
}
}  // namespace

Ref i_posix_sys(Obj, Args a) {                   // _sys(name, ...)
    return primitives().at(as_str(a.pos(0))->text)(Args{a.data + 1, a.npos - 1, nullptr, 0});
}
}  // namespace bella
