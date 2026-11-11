"""posix, in Python over the runtime's system calls (runtime/src/posix.cpp), from Modules/posixmodule.c; see itertools.py
beside it. The constants and the tables of names are the pin's, Linux's, written here once, as errno.py's are; the docstrings
are in the runtime's table of CPython's names, which `make verify` holds to the pin.

A primitive makes one system call: it takes bytes and gives what the call gave, or a negative errno. The arguments are checked
here, in the C's words. What the module has in CPython and the runtime does not yet is a function that stops by name when
called (`_absent`), so that `from posix import *` brings what CPython's brings; a keyword argument the runtime cannot do yet,
dir_fd for one, stops by name too.
"""

__all__ = ["AT_NO_AUTOMOUNT", "CLD_CONTINUED", "CLD_DUMPED", "CLD_EXITED", "CLD_KILLED", "CLD_STOPPED", "CLD_TRAPPED", "CLONE_FILES", "CLONE_FS", "CLONE_NEWCGROUP", "CLONE_NEWIPC", "CLONE_NEWNET", "CLONE_NEWNS", "CLONE_NEWPID", "CLONE_NEWTIME", "CLONE_NEWUSER", "CLONE_NEWUTS", "CLONE_SIGHAND", "CLONE_SYSVSEM", "CLONE_THREAD", "CLONE_VM", "DirEntry", "EFD_CLOEXEC", "EFD_NONBLOCK", "EFD_SEMAPHORE", "EX_CANTCREAT", "EX_CONFIG", "EX_DATAERR", "EX_IOERR", "EX_NOHOST", "EX_NOINPUT", "EX_NOPERM", "EX_NOUSER", "EX_OK", "EX_OSERR", "EX_OSFILE", "EX_PROTOCOL", "EX_SOFTWARE", "EX_TEMPFAIL", "EX_UNAVAILABLE", "EX_USAGE", "F_LOCK", "F_OK", "F_TEST", "F_TLOCK", "F_ULOCK", "GRND_NONBLOCK", "GRND_RANDOM", "MFD_ALLOW_SEALING", "MFD_CLOEXEC", "MFD_HUGETLB", "MFD_HUGE_16GB", "MFD_HUGE_16MB", "MFD_HUGE_1GB", "MFD_HUGE_1MB", "MFD_HUGE_256MB", "MFD_HUGE_2GB", "MFD_HUGE_2MB", "MFD_HUGE_32MB", "MFD_HUGE_512KB", "MFD_HUGE_512MB", "MFD_HUGE_64KB", "MFD_HUGE_8MB", "MFD_HUGE_MASK", "MFD_HUGE_SHIFT", "NGROUPS_MAX", "NODEV", "O_ACCMODE", "O_APPEND", "O_ASYNC", "O_CLOEXEC", "O_CREAT", "O_DIRECT", "O_DIRECTORY", "O_DSYNC", "O_EXCL", "O_FSYNC", "O_LARGEFILE", "O_NDELAY", "O_NOATIME", "O_NOCTTY", "O_NOFOLLOW", "O_NONBLOCK", "O_PATH", "O_RDONLY", "O_RDWR", "O_RSYNC", "O_SYNC", "O_TMPFILE", "O_TRUNC", "O_WRONLY", "POSIX_FADV_DONTNEED", "POSIX_FADV_NOREUSE", "POSIX_FADV_NORMAL", "POSIX_FADV_RANDOM", "POSIX_FADV_SEQUENTIAL", "POSIX_FADV_WILLNEED", "POSIX_SPAWN_CLOSE", "POSIX_SPAWN_DUP2", "POSIX_SPAWN_OPEN", "PRIO_PGRP", "PRIO_PROCESS", "PRIO_USER", "P_ALL", "P_PGID", "P_PID", "P_PIDFD", "RTLD_DEEPBIND", "RTLD_GLOBAL", "RTLD_LAZY", "RTLD_LOCAL", "RTLD_NODELETE", "RTLD_NOLOAD", "RTLD_NOW", "R_OK", "SCHED_BATCH", "SCHED_DEADLINE", "SCHED_FIFO", "SCHED_IDLE", "SCHED_NORMAL", "SCHED_OTHER", "SCHED_RESET_ON_FORK", "SCHED_RR", "SEEK_DATA", "SEEK_HOLE", "SPLICE_F_MORE", "SPLICE_F_MOVE", "SPLICE_F_NONBLOCK", "ST_APPEND", "ST_MANDLOCK", "ST_NOATIME", "ST_NODEV", "ST_NODIRATIME", "ST_NOEXEC", "ST_NOSUID", "ST_RDONLY", "ST_RELATIME", "ST_SYNCHRONOUS", "ST_WRITE", "TFD_CLOEXEC", "TFD_NONBLOCK", "TFD_TIMER_ABSTIME", "TMP_MAX", "WCONTINUED", "WCOREDUMP", "WEXITED", "WEXITSTATUS", "WIFCONTINUED", "WIFEXITED", "WIFSIGNALED", "WIFSTOPPED", "WNOHANG", "WNOWAIT", "WSTOPPED", "WSTOPSIG", "WTERMSIG", "WUNTRACED", "W_OK", "XATTR_CREATE", "XATTR_REPLACE", "XATTR_SIZE_MAX", "X_OK", "_clearenv", "_create_environ", "_exit", "_have_functions", "_inputhook", "_is_inputhook_installed", "_path_normpath", "_path_splitroot_ex", "abort", "access", "chdir", "chmod", "chown", "chroot", "close", "closerange", "confstr", "confstr_names", "copy_file_range", "cpu_count", "ctermid", "device_encoding", "dup", "dup2", "environ", "eventfd", "eventfd_read", "eventfd_write", "execv", "execve", "fchdir", "fchmod", "fchown", "fdatasync", "fork", "forkpty", "fpathconf", "fspath", "fstat", "fstatvfs", "fsync", "ftruncate", "get_blocking", "get_inheritable", "get_terminal_size", "getcwd", "getcwdb", "getegid", "geteuid", "getgid", "getgrouplist", "getgroups", "getloadavg", "getlogin", "getpgid", "getpgrp", "getpid", "getppid", "getpriority", "getrandom", "getresgid", "getresuid", "getsid", "getuid", "getxattr", "grantpt", "initgroups", "isatty", "kill", "killpg", "lchown", "link", "listdir", "listxattr", "lockf", "login_tty", "lseek", "lstat", "major", "makedev", "memfd_create", "minor", "mkdir", "mkfifo", "mknod", "nice", "open", "openpty", "pathconf", "pathconf_names", "pidfd_open", "pipe", "pipe2", "posix_fadvise", "posix_fallocate", "posix_openpt", "posix_spawn", "posix_spawnp", "pread", "preadv", "ptsname", "putenv", "pwrite", "pwritev", "read", "readinto", "readlink", "readv", "register_at_fork", "remove", "removexattr", "rename", "replace", "rmdir", "scandir", "sched_get_priority_max", "sched_get_priority_min", "sched_getaffinity", "sched_getparam", "sched_getscheduler", "sched_param", "sched_rr_get_interval", "sched_setaffinity", "sched_setparam", "sched_setscheduler", "sched_yield", "sendfile", "set_blocking", "set_inheritable", "setegid", "seteuid", "setgid", "setgroups", "setns", "setpgid", "setpgrp", "setpriority", "setregid", "setresgid", "setresuid", "setreuid", "setsid", "setuid", "setxattr", "splice", "stat", "stat_result", "statvfs", "statvfs_result", "strerror", "symlink", "sync", "sysconf", "sysconf_names", "system", "tcgetpgrp", "tcsetpgrp", "terminal_size", "timerfd_create", "timerfd_gettime", "timerfd_gettime_ns", "timerfd_settime", "timerfd_settime_ns", "times", "times_result", "truncate", "ttyname", "umask", "uname", "uname_result", "unlink", "unlockpt", "unsetenv", "unshare", "urandom", "utime", "wait", "wait3", "wait4", "waitid", "waitid_result", "waitpid", "waitstatus_to_exitcode", "write", "writev"]

__name__ = "posix"
__hidden_classes__ = ["ScandirIterator"]       # posix.ScandirIterator: a type of the module that is no name of it

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _sequence_check                              # noqa: B018  # PySequence_Check
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _structseq                                   # noqa: B018  # bootstrap.py's: a type of named tuples
    _sys                                         # noqa: B018  # the system calls, by name
    _bella_new_instance                          # noqa: B018  # tp_alloc: an instance of a type a program cannot make
    _unraisable                                  # noqa: B018  # PyErr_FormatUnraisable: a message and the exception
    _resource_warning                            # noqa: B018  # PyErr_ResourceWarning: a message and the object left open
    _warn                                        # noqa: B018  # PyErr_WarnEx(category, message, 1): a message and the category's name
    _as_double                                   # noqa: B018  # PyFloat_AsDouble, with its messages
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _sequence_check: Callable[..., bool] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _structseq: Callable[..., Any] = _missing
    _sys: Callable[..., Any] = _missing
    _bella_new_instance: Callable[..., Any] = _missing
    _unraisable: Callable[..., Any] = _missing
    _resource_warning: Callable[..., Any] = _missing
    _warn: Callable[..., Any] = _missing
    _as_double: Callable[..., float] = _missing

AT_NO_AUTOMOUNT = 2048
CLD_CONTINUED = 6
CLD_DUMPED = 3
CLD_EXITED = 1
CLD_KILLED = 2
CLD_STOPPED = 5
CLD_TRAPPED = 4
CLONE_FILES = 1024
CLONE_FS = 512
CLONE_NEWCGROUP = 33554432
CLONE_NEWIPC = 134217728
CLONE_NEWNET = 1073741824
CLONE_NEWNS = 131072
CLONE_NEWPID = 536870912
CLONE_NEWTIME = 128
CLONE_NEWUSER = 268435456
CLONE_NEWUTS = 67108864
CLONE_SIGHAND = 2048
CLONE_SYSVSEM = 262144
CLONE_THREAD = 65536
CLONE_VM = 256
EFD_CLOEXEC = 524288
EFD_NONBLOCK = 2048
EFD_SEMAPHORE = 1
EX_CANTCREAT = 73
EX_CONFIG = 78
EX_DATAERR = 65
EX_IOERR = 74
EX_NOHOST = 68
EX_NOINPUT = 66
EX_NOPERM = 77
EX_NOUSER = 67
EX_OK = 0
EX_OSERR = 71
EX_OSFILE = 72
EX_PROTOCOL = 76
EX_SOFTWARE = 70
EX_TEMPFAIL = 75
EX_UNAVAILABLE = 69
EX_USAGE = 64
F_LOCK = 1
F_OK = 0
F_TEST = 3
F_TLOCK = 2
F_ULOCK = 0
GRND_NONBLOCK = 1
GRND_RANDOM = 2
MFD_ALLOW_SEALING = 2
MFD_CLOEXEC = 1
MFD_HUGETLB = 4
MFD_HUGE_16GB = 2281701376
MFD_HUGE_16MB = 1610612736
MFD_HUGE_1GB = 2013265920
MFD_HUGE_1MB = 1342177280
MFD_HUGE_256MB = 1879048192
MFD_HUGE_2GB = 2080374784
MFD_HUGE_2MB = 1409286144
MFD_HUGE_32MB = 1677721600
MFD_HUGE_512KB = 1275068416
MFD_HUGE_512MB = 1946157056
MFD_HUGE_64KB = 1073741824
MFD_HUGE_8MB = 1543503872
MFD_HUGE_MASK = 63
MFD_HUGE_SHIFT = 26
NGROUPS_MAX = 65536
NODEV = -1
O_ACCMODE = 3
O_APPEND = 1024
O_ASYNC = 8192
O_CLOEXEC = 524288
O_CREAT = 64
O_DIRECT = 16384
O_DIRECTORY = 65536
O_DSYNC = 4096
O_EXCL = 128
O_FSYNC = 1052672
O_LARGEFILE = 0
O_NDELAY = 2048
O_NOATIME = 262144
O_NOCTTY = 256
O_NOFOLLOW = 131072
O_NONBLOCK = 2048
O_PATH = 2097152
O_RDONLY = 0
O_RDWR = 2
O_RSYNC = 1052672
O_SYNC = 1052672
O_TMPFILE = 4259840
O_TRUNC = 512
O_WRONLY = 1
POSIX_FADV_DONTNEED = 4
POSIX_FADV_NOREUSE = 5
POSIX_FADV_NORMAL = 0
POSIX_FADV_RANDOM = 1
POSIX_FADV_SEQUENTIAL = 2
POSIX_FADV_WILLNEED = 3
POSIX_SPAWN_CLOSE = 1
POSIX_SPAWN_DUP2 = 2
POSIX_SPAWN_OPEN = 0
PRIO_PGRP = 1
PRIO_PROCESS = 0
PRIO_USER = 2
P_ALL = 0
P_PGID = 2
P_PID = 1
P_PIDFD = 3
RTLD_DEEPBIND = 8
RTLD_GLOBAL = 256
RTLD_LAZY = 1
RTLD_LOCAL = 0
RTLD_NODELETE = 4096
RTLD_NOLOAD = 4
RTLD_NOW = 2
R_OK = 4
SCHED_BATCH = 3
SCHED_DEADLINE = 6
SCHED_FIFO = 1
SCHED_IDLE = 5
SCHED_NORMAL = 0
SCHED_OTHER = 0
SCHED_RESET_ON_FORK = 1073741824
SCHED_RR = 2
SEEK_DATA = 3
SEEK_HOLE = 4
SPLICE_F_MORE = 4
SPLICE_F_MOVE = 1
SPLICE_F_NONBLOCK = 2
ST_APPEND = 256
ST_MANDLOCK = 64
ST_NOATIME = 1024
ST_NODEV = 4
ST_NODIRATIME = 2048
ST_NOEXEC = 8
ST_NOSUID = 2
ST_RDONLY = 1
ST_RELATIME = 4096
ST_SYNCHRONOUS = 16
ST_WRITE = 128
TFD_CLOEXEC = 524288
TFD_NONBLOCK = 2048
TFD_TIMER_ABSTIME = 1
TMP_MAX = 238328
WCONTINUED = 8
WEXITED = 4
WNOHANG = 1
WNOWAIT = 16777216
WSTOPPED = 2
WUNTRACED = 2
W_OK = 2
XATTR_CREATE = 1
XATTR_REPLACE = 2
XATTR_SIZE_MAX = 65536
X_OK = 1

_have_functions = ['HAVE_EVENTFD', 'HAVE_TIMERFD_CREATE', 'HAVE_FACCESSAT', 'HAVE_FCHDIR', 'HAVE_FCHMOD', 'HAVE_FCHMODAT', 'HAVE_FCHOWN', 'HAVE_FCHOWNAT', 'HAVE_FEXECVE', 'HAVE_FDOPENDIR', 'HAVE_FPATHCONF', 'HAVE_FSTATAT', 'HAVE_FSTATVFS', 'HAVE_FTRUNCATE', 'HAVE_FUTIMENS', 'HAVE_FUTIMES', 'HAVE_FUTIMESAT', 'HAVE_LINKAT', 'HAVE_LCHOWN', 'HAVE_LSTAT', 'HAVE_LUTIMES', 'HAVE_MEMFD_CREATE', 'HAVE_MKDIRAT', 'HAVE_MKFIFOAT', 'HAVE_MKNODAT', 'HAVE_OPENAT', 'HAVE_READLINKAT', 'HAVE_RENAMEAT', 'HAVE_SYMLINKAT', 'HAVE_UNLINKAT', 'HAVE_UTIMENSAT', 'HAVE_PTSNAME_R']
confstr_names = {'CS_GNU_LIBC_VERSION': 2, 'CS_GNU_LIBPTHREAD_VERSION': 3, 'CS_LFS64_CFLAGS': 1004, 'CS_LFS64_LDFLAGS': 1005, 'CS_LFS64_LIBS': 1006, 'CS_LFS64_LINTFLAGS': 1007, 'CS_LFS_CFLAGS': 1000, 'CS_LFS_LDFLAGS': 1001, 'CS_LFS_LIBS': 1002, 'CS_LFS_LINTFLAGS': 1003, 'CS_PATH': 0, 'CS_XBS5_ILP32_OFF32_CFLAGS': 1100, 'CS_XBS5_ILP32_OFF32_LDFLAGS': 1101, 'CS_XBS5_ILP32_OFF32_LIBS': 1102, 'CS_XBS5_ILP32_OFF32_LINTFLAGS': 1103, 'CS_XBS5_ILP32_OFFBIG_CFLAGS': 1104, 'CS_XBS5_ILP32_OFFBIG_LDFLAGS': 1105, 'CS_XBS5_ILP32_OFFBIG_LIBS': 1106, 'CS_XBS5_ILP32_OFFBIG_LINTFLAGS': 1107, 'CS_XBS5_LP64_OFF64_CFLAGS': 1108, 'CS_XBS5_LP64_OFF64_LDFLAGS': 1109, 'CS_XBS5_LP64_OFF64_LIBS': 1110, 'CS_XBS5_LP64_OFF64_LINTFLAGS': 1111, 'CS_XBS5_LPBIG_OFFBIG_CFLAGS': 1112, 'CS_XBS5_LPBIG_OFFBIG_LDFLAGS': 1113, 'CS_XBS5_LPBIG_OFFBIG_LIBS': 1114, 'CS_XBS5_LPBIG_OFFBIG_LINTFLAGS': 1115}
pathconf_names = {'PC_ASYNC_IO': 10, 'PC_CHOWN_RESTRICTED': 6, 'PC_FILESIZEBITS': 13, 'PC_LINK_MAX': 0, 'PC_MAX_CANON': 1, 'PC_MAX_INPUT': 2, 'PC_NAME_MAX': 3, 'PC_NO_TRUNC': 7, 'PC_PATH_MAX': 4, 'PC_PIPE_BUF': 5, 'PC_PRIO_IO': 11, 'PC_SOCK_MAXBUF': 12, 'PC_SYNC_IO': 9, 'PC_VDISABLE': 8, 'PC_ALLOC_SIZE_MIN': 18, 'PC_REC_INCR_XFER_SIZE': 14, 'PC_REC_MAX_XFER_SIZE': 15, 'PC_REC_MIN_XFER_SIZE': 16, 'PC_REC_XFER_ALIGN': 17, 'PC_SYMLINK_MAX': 19}
sysconf_names = {'SC_2_CHAR_TERM': 95, 'SC_2_C_BIND': 47, 'SC_2_C_DEV': 48, 'SC_2_C_VERSION': 96, 'SC_2_FORT_DEV': 49, 'SC_2_FORT_RUN': 50, 'SC_2_LOCALEDEF': 52, 'SC_2_SW_DEV': 51, 'SC_2_UPE': 97, 'SC_2_VERSION': 46, 'SC_AIO_LISTIO_MAX': 23, 'SC_AIO_MAX': 24, 'SC_AIO_PRIO_DELTA_MAX': 25, 'SC_ARG_MAX': 0, 'SC_ASYNCHRONOUS_IO': 12, 'SC_ATEXIT_MAX': 87, 'SC_AVPHYS_PAGES': 86, 'SC_BC_BASE_MAX': 36, 'SC_BC_DIM_MAX': 37, 'SC_BC_SCALE_MAX': 38, 'SC_BC_STRING_MAX': 39, 'SC_CHARCLASS_NAME_MAX': 45, 'SC_CHAR_BIT': 101, 'SC_CHAR_MAX': 102, 'SC_CHAR_MIN': 103, 'SC_CHILD_MAX': 1, 'SC_CLK_TCK': 2, 'SC_COLL_WEIGHTS_MAX': 40, 'SC_DELAYTIMER_MAX': 26, 'SC_EQUIV_CLASS_MAX': 41, 'SC_EXPR_NEST_MAX': 42, 'SC_FSYNC': 15, 'SC_GETGR_R_SIZE_MAX': 69, 'SC_GETPW_R_SIZE_MAX': 70, 'SC_INT_MAX': 104, 'SC_INT_MIN': 105, 'SC_IOV_MAX': 60, 'SC_JOB_CONTROL': 7, 'SC_LINE_MAX': 43, 'SC_LOGIN_NAME_MAX': 71, 'SC_LONG_BIT': 106, 'SC_MAPPED_FILES': 16, 'SC_MB_LEN_MAX': 108, 'SC_MEMLOCK': 17, 'SC_MEMLOCK_RANGE': 18, 'SC_MEMORY_PROTECTION': 19, 'SC_MESSAGE_PASSING': 20, 'SC_MQ_OPEN_MAX': 27, 'SC_MQ_PRIO_MAX': 28, 'SC_NGROUPS_MAX': 3, 'SC_NL_ARGMAX': 119, 'SC_NL_LANGMAX': 120, 'SC_NL_MSGMAX': 121, 'SC_NL_NMAX': 122, 'SC_NL_SETMAX': 123, 'SC_NL_TEXTMAX': 124, 'SC_NPROCESSORS_CONF': 83, 'SC_NPROCESSORS_ONLN': 84, 'SC_NZERO': 109, 'SC_OPEN_MAX': 4, 'SC_PAGESIZE': 30, 'SC_PAGE_SIZE': 30, 'SC_PASS_MAX': 88, 'SC_PHYS_PAGES': 85, 'SC_PII': 53, 'SC_PII_INTERNET': 56, 'SC_PII_INTERNET_DGRAM': 62, 'SC_PII_INTERNET_STREAM': 61, 'SC_PII_OSI': 57, 'SC_PII_OSI_CLTS': 64, 'SC_PII_OSI_COTS': 63, 'SC_PII_OSI_M': 65, 'SC_PII_SOCKET': 55, 'SC_PII_XTI': 54, 'SC_POLL': 58, 'SC_PRIORITIZED_IO': 13, 'SC_PRIORITY_SCHEDULING': 10, 'SC_REALTIME_SIGNALS': 9, 'SC_RE_DUP_MAX': 44, 'SC_RTSIG_MAX': 31, 'SC_SAVED_IDS': 8, 'SC_SCHAR_MAX': 111, 'SC_SCHAR_MIN': 112, 'SC_SELECT': 59, 'SC_SEMAPHORES': 21, 'SC_SEM_NSEMS_MAX': 32, 'SC_SEM_VALUE_MAX': 33, 'SC_SHARED_MEMORY_OBJECTS': 22, 'SC_SHRT_MAX': 113, 'SC_SHRT_MIN': 114, 'SC_SIGQUEUE_MAX': 34, 'SC_SSIZE_MAX': 110, 'SC_STREAM_MAX': 5, 'SC_SYNCHRONIZED_IO': 14, 'SC_THREADS': 67, 'SC_THREAD_ATTR_STACKADDR': 77, 'SC_THREAD_ATTR_STACKSIZE': 78, 'SC_THREAD_DESTRUCTOR_ITERATIONS': 73, 'SC_THREAD_KEYS_MAX': 74, 'SC_THREAD_PRIORITY_SCHEDULING': 79, 'SC_THREAD_PRIO_INHERIT': 80, 'SC_THREAD_PRIO_PROTECT': 81, 'SC_THREAD_PROCESS_SHARED': 82, 'SC_THREAD_SAFE_FUNCTIONS': 68, 'SC_THREAD_STACK_MIN': 75, 'SC_THREAD_THREADS_MAX': 76, 'SC_TIMERS': 11, 'SC_TIMER_MAX': 35, 'SC_TTY_NAME_MAX': 72, 'SC_TZNAME_MAX': 6, 'SC_T_IOV_MAX': 66, 'SC_UCHAR_MAX': 115, 'SC_UINT_MAX': 116, 'SC_UIO_MAXIOV': 60, 'SC_ULONG_MAX': 117, 'SC_USHRT_MAX': 118, 'SC_VERSION': 29, 'SC_WORD_BIT': 107, 'SC_XBS5_ILP32_OFF32': 125, 'SC_XBS5_ILP32_OFFBIG': 126, 'SC_XBS5_LP64_OFF64': 127, 'SC_XBS5_LPBIG_OFFBIG': 128, 'SC_XOPEN_CRYPT': 92, 'SC_XOPEN_ENH_I18N': 93, 'SC_XOPEN_LEGACY': 129, 'SC_XOPEN_REALTIME': 130, 'SC_XOPEN_REALTIME_THREADS': 131, 'SC_XOPEN_SHM': 94, 'SC_XOPEN_UNIX': 91, 'SC_XOPEN_VERSION': 89, 'SC_XOPEN_XCU_VERSION': 90, 'SC_XOPEN_XPG2': 98, 'SC_XOPEN_XPG3': 99, 'SC_XOPEN_XPG4': 100}

def _times_from_ints(items: list[object], past: list[object]) -> None:   # statresult_new: st_atime and the others, unset, are the int slots
    for i in range(3):
        if past[i] is None:
            past[i] = items[7 + i]


stat_result = _structseq("stat_result", "os", ["st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid", "st_size", None, None, None,
                                               "st_atime", "st_mtime", "st_ctime", "st_atime_ns", "st_mtime_ns", "st_ctime_ns", "st_blksize", "st_blocks", "st_rdev"], 10, _times_from_ints)
statvfs_result = _structseq("statvfs_result", "os", ["f_bsize", "f_frsize", "f_blocks", "f_bfree", "f_bavail", "f_files", "f_ffree", "f_favail", "f_flag", "f_namemax", "f_fsid"], 10)
terminal_size = _structseq("terminal_size", "os", ["columns", "lines"], 2)
times_result = _structseq("times_result", "posix", ["user", "system", "children_user", "children_system", "elapsed"], 5)
uname_result = _structseq("uname_result", "posix", ["sysname", "nodename", "release", "version", "machine"], 5)
waitid_result = _structseq("waitid_result", "posix", ["si_pid", "si_uid", "si_signo", "si_status", "si_code"], 5)


class DirEntry:
    """os.DirEntry (posixmodule.c): what scandir yields. The name and the path are members; the kind is readdir's d_type
    (0 where the file system does not say), and the two stat results are fetched once each."""

    __slots__ = ("_e_name", "_e_path", "_e_ino", "_e_kind", "_e_dir_fd", "_e_stat", "_e_lstat")
    __module__ = "posix"

    @property
    def name(self) -> object:
        return self._e_name  # type: ignore[attr-defined]

    @property
    def path(self) -> object:
        return self._e_path  # type: ignore[attr-defined]

    def is_symlink(*args: object, **kwds: object) -> bool:  # noqa: N805
        self = _entry_method("is_symlink", args)
        if len(args) > 1 or kwds:
            raise TypeError("is_symlink() takes no arguments")
        if self._e_kind != 0:
            return self._e_kind == 3
        return _entry_test_mode(self, False, 0o120000)

    def is_junction(*args: object, **kwds: object) -> bool:  # noqa: N805
        _entry_noargs("is_junction", args, kwds)
        return False

    def stat(*args: object, **kwds: object) -> object:  # noqa: N805
        self = _entry_method("stat", args)
        follow = _unpack("stat", args[1:], kwds, ("follow_symlinks",), 0, 0)[0]
        return _entry_stat(self, follow is _ABSENT or bool(follow))

    def is_dir(*args: object, **kwds: object) -> bool:  # noqa: N805
        self = _entry_method("is_dir", args)
        follow = _unpack("is_dir", args[1:], kwds, ("follow_symlinks",), 0, 0)[0]
        return _entry_test_mode(self, follow is _ABSENT or bool(follow), 0o040000)

    def is_file(*args: object, **kwds: object) -> bool:  # noqa: N805
        self = _entry_method("is_file", args)
        follow = _unpack("is_file", args[1:], kwds, ("follow_symlinks",), 0, 0)[0]
        return _entry_test_mode(self, follow is _ABSENT or bool(follow), 0o100000)

    def inode(*args: object, **kwds: object) -> int:  # noqa: N805
        return _entry_noargs("inode", args, kwds)._e_ino  # type: ignore[no-any-return]

    def __fspath__(*args: object, **kwds: object) -> object:  # noqa: N805
        return _entry_noargs("__fspath__", args, kwds)._e_path

    def __repr__(self) -> str:
        return "<DirEntry " + repr(self._e_name) + ">"  # type: ignore[attr-defined]


def _entry_method(name: str, args: tuple[object, ...]) -> DirEntry:   # a method descriptor's check of its receiver
    if not args:
        raise TypeError("unbound method DirEntry." + name + "() needs an argument")
    if not issubclass(type(args[0]), DirEntry):
        raise TypeError("descriptor '" + name + "' for 'posix.DirEntry' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
    return args[0]  # type: ignore[return-value]


def _entry_noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> DirEntry:   # METH_NOARGS
    self = _entry_method(name, args)
    if kwds:
        raise TypeError("DirEntry." + name + "() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("DirEntry." + name + "() takes no arguments (" + str(len(args) - 1) + " given)")
    return self


def _entry_fetch_stat(self: DirEntry, follow: bool) -> object:   # DirEntry_fetch_stat: fstatat under the directory's descriptor, else stat or lstat
    path = self._e_path  # type: ignore[attr-defined]
    data = str.encode(path, "utf-8", "surrogateescape") if issubclass(type(path), str) else path
    result = _sys("stat", data, follow, self._e_dir_fd)  # type: ignore[attr-defined]
    if type(result) is int:
        _fail(-result, path)                     # path_object_error(self->path)
    return _stat_result(result)


def _entry_stat(self: DirEntry, follow: bool) -> object:   # os_DirEntry_stat_impl: each of the two results is fetched once
    if not follow:
        if self._e_lstat is None:  # type: ignore[attr-defined]
            _entry_set(self, "_e_lstat", _entry_fetch_stat(self, False))
        return self._e_lstat  # type: ignore[attr-defined]
    if self._e_stat is None:  # type: ignore[attr-defined]
        if DirEntry.is_symlink(self):
            _entry_set(self, "_e_stat", _entry_fetch_stat(self, True))
        else:
            _entry_set(self, "_e_stat", _entry_stat(self, False))
    return self._e_stat  # type: ignore[attr-defined]


def _entry_test_mode(self: DirEntry, follow: bool, mode_bits: int) -> bool:   # DirEntry_test_mode
    kind = self._e_kind  # type: ignore[attr-defined]
    is_symlink = kind == 3
    if kind == 0 or (follow and is_symlink):     # the file system did not say, or the link's target is asked about
        try:
            found = _entry_stat(self, follow)
        except FileNotFoundError:
            return False                         # the file is not there (any more): neither a file nor a directory
        return (found.st_mode & 0o170000) == mode_bits  # type: ignore[attr-defined,no-any-return]
    if is_symlink:
        return False
    return kind == 1 if mode_bits == 0o040000 else kind == 2


_entry_set = object.__setattr__


class ScandirIterator:
    """posix.ScandirIterator: a directory stream that yields its entries as DirEntry objects. The stream is the runtime's, by
    number (None once closed); a descriptor's is a duplicate, rewound when it is closed."""

    __slots__ = ("_s_stream", "_s_path", "_s_shown", "_s_bytes", "_s_fd")
    __module__ = "posix"

    def __iter__(self) -> ScandirIterator:
        return self

    def __next__(self) -> DirEntry:               # ScandirIterator_iternext
        stream = self._s_stream  # type: ignore[attr-defined]
        if stream is not None:                   # None: iterated to the end before, or closed
            got = _sys("readdir", stream)
            if type(got) is tuple:
                return _entry_from_posix_info(self, got[0], got[1], got[2])
            _scandir_close(self)                 # an error, or no more files
            if got is not None:
                _fail(-got, self._s_shown)  # type: ignore[attr-defined]  # path_error(&iterator->path)
        raise StopIteration

    def close(*args: object, **kwds: object) -> None:  # noqa: N805
        _scandir_close(_scandir_noargs("close", args, kwds))

    def __enter__(*args: object, **kwds: object) -> object:  # noqa: N805
        return _scandir_noargs("__enter__", args, kwds)

    def __exit__(*args: object, **kwds: object) -> None:  # noqa: N805  # METH_VARARGS: whatever it is given
        if not args:
            raise TypeError("unbound method ScandirIterator.__exit__() needs an argument")
        if not issubclass(type(args[0]), ScandirIterator):
            raise TypeError("descriptor '__exit__' for 'posix.ScandirIterator' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
        if kwds:
            raise TypeError("ScandirIterator.__exit__() takes no keyword arguments")
        _scandir_close(args[0])  # type: ignore[arg-type]

    def __del__(self) -> None:                   # ScandirIterator_finalize
        was_closed = self._s_stream is None  # type: ignore[attr-defined]
        _scandir_close(self)
        if not was_closed:
            try:
                shown = repr(self)
            except BaseException:  # noqa: BLE001  # %R failed: PyErr_ResourceWarning returns its error, which is no Warning: dropped
                return
            try:                                 # PyErr_ResourceWarning(op, 1, "unclosed scandir iterator %R", iterator)
                _resource_warning("unclosed scandir iterator " + shown, self)
            except Warning as e:                 # spurious errors can appear at shutdown: only a warning made an error is reported
                _unraisable("Exception ignored while finalizing scandir iterator " + shown, e)
            except BaseException:  # noqa: BLE001, S110
                pass


def _scandir_noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> ScandirIterator:   # METH_NOARGS
    if not args:
        raise TypeError("unbound method ScandirIterator." + name + "() needs an argument")
    if not issubclass(type(args[0]), ScandirIterator):
        raise TypeError("descriptor '" + name + "' for 'posix.ScandirIterator' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")
    if kwds:
        raise TypeError("ScandirIterator." + name + "() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("ScandirIterator." + name + "() takes no arguments (" + str(len(args) - 1) + " given)")
    return args[0]  # type: ignore[return-value]


def _scandir_close(self: ScandirIterator) -> None:   # ScandirIterator_closedir
    stream = self._s_stream  # type: ignore[attr-defined]
    if stream is not None:
        _entry_set(self, "_s_stream", None)
        _sys("closedir", stream, self._s_fd is not None)  # type: ignore[attr-defined]


def _entry_from_posix_info(iterator: ScandirIterator, name: bytes, ino: int, kind: int) -> DirEntry:   # DirEntry_from_posix_info
    entry: DirEntry = _bella_new_instance(DirEntry)
    as_bytes = iterator._s_bytes  # type: ignore[attr-defined]
    shown_name = name if as_bytes else bytes.decode(name, "utf-8", "surrogateescape")
    if iterator._s_fd is not None:  # type: ignore[attr-defined]
        path: object = shown_name                # under a descriptor the path is the name, and stat goes through the descriptor
    else:
        directory = iterator._s_path  # type: ignore[attr-defined]  # join_path_filename: "." for no path, one separator between
        joined = (directory if bytes.endswith(directory, b"/") or not directory else directory + b"/") + name
        path = joined if as_bytes else bytes.decode(joined, "utf-8", "surrogateescape")
    _entry_set(entry, "_e_name", shown_name)
    _entry_set(entry, "_e_path", path)
    _entry_set(entry, "_e_ino", ino)
    _entry_set(entry, "_e_kind", kind)
    _entry_set(entry, "_e_dir_fd", iterator._s_fd)  # type: ignore[attr-defined]
    _entry_set(entry, "_e_stat", None)
    _entry_set(entry, "_e_lstat", None)
    return entry


class sched_param(tuple):  # noqa: N801, SLOT001
    __slots__ = ()
    __module__ = "posix"

    def __new__(*args: object, **kwds: object) -> object:  # noqa: N805
        _refuse("os.sched_param")


# ---- arguments

_ABSENT = object()


def _refuse(what: str) -> None:
    _sys("refuse", what)


def _absent(name: str) -> object:
    """What the module has in CPython and the runtime does not yet: a program may name it, and stops when it calls it."""
    def absent(*args: object, **kwds: object) -> object:
        _refuse("os." + name)

    absent.__name__ = name
    absent.__qualname__ = name
    return absent


def _unpack(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int, maxpos: int) -> list[object]:
    """_PyArg_UnpackKeywords with no positional-only parameters: the values, or _ABSENT for one not given."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = len(names)
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs > maxpos:
        if maxpos == 0:
            raise TypeError(name + "() takes no positional arguments")
        raise TypeError(name + "() takes " + ("at most" if minpos < maxpos else "exactly") + " " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * (maxargs - nargs)]
    if nkw:
        i = 0
        while i < nargs:
            if names[i] in kwds:
                raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
            i += 1
    left = nkw
    i = nargs
    while i < maxargs:
        if not left and i >= minpos:
            break
        if left and names[i] in kwds:
            out[i] = kwds[names[i]]
            left -= 1
        elif i < minpos:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        i += 1
    if left > 0:                                 # error_unexpected_keyword
        for keyword in kwds:
            if keyword not in names:
                suggestion = _keyword_suggestion(names, keyword)
                if suggestion is not None:
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("posix." + name + "() takes no keyword arguments")
    if args:
        raise TypeError("posix." + name + "() takes no arguments (" + str(len(args)) + " given)")


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("posix." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("posix." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], count: int) -> None:   # METH_FASTCALL, _PyArg_CheckPositional
    if kwds:
        raise TypeError("posix." + name + "() takes no keyword arguments")
    if len(args) != count:
        raise TypeError(name + " expected " + str(count) + " arguments, got " + str(len(args)))


def _type_lookup(value: object, name: str) -> object:   # _PyType_Lookup on its type: _ABSENT when it has none
    for klass in type(value).__mro__:
        found = vars(klass)
        if name in found:
            return found[name]
    return _ABSENT


def _special(value: object, name: str) -> object:   # _PyObject_LookupSpecial: None when it has none
    found = _type_lookup(value, name)
    if found is _ABSENT:
        return None
    get = _type_lookup(found, "__get__")
    return found if get is _ABSENT else get(found, value, type(value))  # type: ignore[operator]


def _int(value: object) -> int:                  # PyLong_AsInt
    out = _number_index(value)
    if not -2147483648 <= out <= 2147483647:
        raise OverflowError("Python int too large to convert to C int")
    return out


def _ssize(value: object) -> int:                # Py_ssize_t's converter
    out = _number_index(value)
    if not -(2**63) <= out < 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return out


def _off(value: object) -> int:                  # Py_off_t_converter
    out = _number_index(value)
    if not -(2**63) <= out < 2**63:
        raise OverflowError("Python int too large to convert to C long")
    return out


def _dev(value: object) -> int:                  # _Py_Dev_Converter: a dev_t as 64 bits, read as signed (-1 is NODEV)
    n = int(value) if issubclass(type(value), int) else _number_index(value)  # type: ignore[call-overload]
    if n < 0:
        if n == -1:                              # NODEV
            return -1
        raise OverflowError("can't convert negative int to unsigned")
    if n > 18446744073709551615:
        raise OverflowError("int too big to convert")
    return n - 18446744073709551616 if n >= 9223372036854775808 else n  # type: ignore[no-any-return]


def _major_minor(value: int) -> int:             # major_minor_conv: the unsigned int that is NODEV's reads as -1
    return -1 if value == 4294967295 else value


def _wait_status(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> int:   # status: int, by position or by name
    return _sys("wstatus", str.encode(name[1:]), _int(_unpack(name, args, kwds, ("status",), 1, 1)[0]))  # type: ignore[no-any-return]


def _id(kind: str, value: object) -> int:        # _Py_Uid_Converter, _Py_Gid_Converter: -1 ("leave it") or 32 bits
    failed = False
    n = 0
    try:
        n = _number_index(value)
    except BaseException:  # noqa: BLE001  # whatever __index__ raised is replaced, not chained
        failed = True
    if failed:
        raise TypeError(kind + " should be integer, not " + type(value).__name__)
    if -9223372036854775808 <= n <= 9223372036854775807:
        if n == -1:
            return -1
        if n < 0 or n > 4294967295:              # too large for the type goes to the C's "underflow" label too
            raise OverflowError(kind + " is less than minimum")
        return n
    if n < 0:
        raise OverflowError(kind + " is less than minimum")
    raise OverflowError(kind + " is greater than maximum")


def _from_id(value: int) -> int:                 # _PyLong_FromUid, _PyLong_FromGid: the all-ones id reads as -1
    return -1 if value == 4294967295 else value


def _confname(value: object, table: object) -> int:   # conv_confname: a name of the module's table as it is now, or the number
    if issubclass(type(value), str):
        value = dict.get(table, value, _ABSENT)  # type: ignore[arg-type]
        if value is _ABSENT:
            raise ValueError("unrecognized configuration name")
    if _type_lookup(value, "__index__") is _ABSENT:
        raise TypeError("configuration names must be strings or integers")
    return _int(value)


def _between(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # _PyArg_CheckPositional with a range
    if kwds:
        raise TypeError("posix." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected at least " + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected at most " + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _unsigned(value: object, kind: str, bits: int) -> int:   # _PyLong_UnsignedInt_Converter, _PyLong_UnsignedLongLong_Converter
    out = _number_index(value)
    if out < 0:
        raise ValueError("Cannot convert negative int")
    if out >= 1 << bits:
        raise OverflowError("Python int too large for C " + kind)
    return out


def _unsigned_bits(value: object) -> int:        # unsigned_int(bitwise=True): the low 32 bits; what neither a C int nor an unsigned holds is deprecated
    out = _number_index(value)
    if not -2147483648 <= out <= 4294967295:
        _warn("integer value out of range", "DeprecationWarning")
    return out & 0xFFFFFFFF


def _buffers(buffers: object, count: int, writable: bool) -> list[object]:   # iov_setup: each item's buffer, in the sequence's order
    out: list[object] = []
    for i in range(count):
        item = buffers[i]  # type: ignore[index]
        if issubclass(type(item), bytearray) or (not writable and issubclass(type(item), bytes)):
            out.append(item)
        elif issubclass(type(item), bytes):
            raise BufferError("Object is not writable.")
        elif _type_lookup(item, "__buffer__") is not _ABSENT:
            _refuse("os: a buffer that is not bytes or bytearray")
        else:
            raise TypeError("a bytes-like object is required, not '" + type(item).__name__ + "'")
    return out


def _read_vector(shown: str, fd: int, buffers: object, offset: int | None, flags: int) -> int:   # os_readv_impl, os_preadv_impl
    if not _sequence_check(buffers):
        raise TypeError(shown + "() arg 2 must be a sequence")
    count = len(buffers)  # type: ignore[arg-type]
    if flags != 0:                               # the pinned build has no preadv2
        raise NotImplementedError("preadv2: flags unavailable on this platform")
    targets = _buffers(buffers, count, True)
    sizes = tuple([bytearray.__len__(b) for b in targets])  # type: ignore[arg-type]
    result = _sys("readv", fd, sizes) if offset is None else _sys("readv", fd, sizes, offset)
    if type(result) is int:
        _fail(-result)
    at = 0
    total = len(result)
    for b in targets:                            # as the kernel fills them: each to its end before the next
        if at >= total:
            break
        size = min(bytearray.__len__(b), total - at)  # type: ignore[arg-type]
        bytearray.__setitem__(b, slice(0, size), result[at:at + size])  # type: ignore[arg-type]
        at += size
    return total


def _write_vector(shown: str, fd: int, buffers: object, offset: int | None, flags: int) -> int:   # os_writev_impl, os_pwritev_impl
    if not _sequence_check(buffers):
        raise TypeError(shown + "() arg 2 must be a sequence")
    count = len(buffers)  # type: ignore[arg-type]
    if flags != 0:                               # the pinned build has no pwritev2
        raise NotImplementedError("pwritev2: flags unavailable on this platform")
    parts = tuple([bytes(b) for b in _buffers(buffers, count, False)])  # type: ignore[call-overload]
    result = _sys("writev", fd, parts) if offset is None else _sys("writev", fd, parts, offset)
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def _fd_converter(value: object) -> int:         # _fd_converter
    if type(value) is bool:
        _warn("bool is used as a file descriptor", "RuntimeWarning")   # PyErr_WarnEx(PyExc_RuntimeWarning, ..., 1)
    out = _number_index(value)
    if out > 2147483647:
        raise OverflowError("fd is greater than maximum")
    if out < -2147483648:
        raise OverflowError("fd is less than minimum")
    return out


def _fildes(value: object) -> int:               # PyObject_AsFileDescriptor
    if issubclass(type(value), int):
        if issubclass(type(value), bool):
            _warn("bool is used as a file descriptor", "RuntimeWarning")
        fd = _int(value)
    else:
        method = getattr(value, "fileno", None)
        if method is None:
            raise TypeError("argument must be an int, or have a fileno() method.")
        given = method()  # type: ignore[operator]
        if not issubclass(type(given), int):
            raise TypeError(_full_name(value) + ".fileno() must return an int, not " + _full_name(given))
        fd = _int(given)
    if fd < 0:
        raise ValueError("file descriptor cannot be a negative integer (" + str(fd) + ")")
    return fd


def _full_name(value: object) -> str:            # %T
    cls = type(value)
    return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__


def _fspath(path: object) -> object:             # PyOS_FSPath
    if issubclass(type(path), (str, bytes)):
        return path
    func = _special(path, "__fspath__")
    if func is None:
        raise TypeError("expected str, bytes or os.PathLike object, not " + _tp_name(path))
    result = func()  # type: ignore[operator]
    if not issubclass(type(result), (str, bytes)):
        raise TypeError("expected " + type(path).__name__ + ".__fspath__() to return str or bytes, not " + type(result).__name__)
    return result


def _fsconverter(value: object) -> bytes:        # PyUnicode_FSConverter
    path = _fspath(value)
    data = str.encode(path, "utf-8", "surrogateescape") if issubclass(type(path), str) else path  # type: ignore[arg-type]
    if 0 in data:  # type: ignore[operator]
        raise ValueError("embedded null byte")
    return data  # type: ignore[return-value]


def _path(function: str, argument: str, value: object, allow_fd: bool = False, nullable: bool = False) -> tuple[object, object]:
    """path_converter: what the system call takes, and what an OSError carries as the file name (the result of
    __fspath__, not the object that gave it)."""
    if value is None and nullable:
        return None, None
    is_index = allow_fd and _type_lookup(value, "__index__") is not _ABSENT
    o = value
    if not is_index and not issubclass(type(value), (str, bytes)):
        func = _special(value, "__fspath__")
        if func is None:
            if allow_fd and nullable:
                expected = "string, bytes, os.PathLike, integer or None"
            elif allow_fd:
                expected = "string, bytes, os.PathLike or integer"
            elif nullable:
                expected = "string, bytes, os.PathLike or None"
            else:
                expected = "string, bytes or os.PathLike"
            raise TypeError(function + ": " + argument + " should be " + expected + ", not " + type(value).__name__)
        o = func()  # type: ignore[operator]
        if not issubclass(type(o), (str, bytes)):
            raise TypeError("expected " + type(value).__name__ + ".__fspath__() to return str or bytes, not " + type(o).__name__)
    if is_index:
        return _fd_converter(o), o
    data = str.encode(o, "utf-8", "surrogateescape") if issubclass(type(o), str) else o  # type: ignore[arg-type]
    if 0 in data:  # type: ignore[operator]
        raise ValueError(function + ": embedded null character in " + argument)
    return data, o


def _fail(code: int, filename: object = _ABSENT, filename2: object = _ABSENT) -> None:   # PyErr_SetFromErrnoWithFilenameObjects
    if filename is _ABSENT:
        raise OSError(code, _sys("strerror", code))
    if filename2 is _ABSENT:
        raise OSError(code, _sys("strerror", code), filename)
    raise OSError(code, _sys("strerror", code), filename, None, filename2)


def _dir_fd(value: object) -> int | None:        # dir_fd_converter: None for the default (AT_FDCWD)
    if value is None or value is _ABSENT:
        return None
    if _type_lookup(value, "__index__") is _ABSENT:
        raise TypeError("argument should be integer or None, not " + type(value).__name__)
    return _fd_converter(value)


# ---- stat

def _stat_result(values: tuple[int, ...]) -> object:   # _pystat_fromstructstat, fill_time
    mode, ino, dev, nlink, uid, gid, size, atime, atime_ns, mtime, mtime_ns, ctime, ctime_ns, blksize, blocks, rdev = values
    return stat_result([mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime,
                        atime + 1e-9 * atime_ns, mtime + 1e-9 * mtime_ns, ctime + 1e-9 * ctime_ns,
                        atime * 1000000000 + atime_ns, mtime * 1000000000 + mtime_ns, ctime * 1000000000 + ctime_ns, blksize, blocks, rdev])


def stat(*args: object, **kwds: object) -> object:
    path, dir_fd, follow = _unpack("stat", args, kwds, ("path", "dir_fd", "follow_symlinks"), 1, 1)
    data, shown = _path("stat", "path", path, allow_fd=True)
    under = _dir_fd(dir_fd)
    follows = follow is _ABSENT or bool(follow)
    if type(data) is int:                        # posix_do_stat: path_and_dir_fd_invalid, fd_and_follow_symlinks_invalid
        if under is not None:
            raise ValueError("stat: can't specify dir_fd without matching path")
        if not follows:
            raise ValueError("stat: cannot use fd and follow_symlinks together")
    result = _sys("stat", data, follows, under)
    if type(result) is int:
        _fail(-result, shown)
    return _stat_result(result)


def lstat(*args: object, **kwds: object) -> object:
    path, dir_fd = _unpack("lstat", args, kwds, ("path", "dir_fd"), 1, 1)
    data, shown = _path("lstat", "path", path)
    result = _sys("stat", data, False, _dir_fd(dir_fd))
    if type(result) is int:
        _fail(-result, shown)
    return _stat_result(result)


def fstat(*args: object, **kwds: object) -> object:
    fd = _int(_unpack("fstat", args, kwds, ("fd",), 1, 1)[0])
    result = _sys("stat", fd, True)
    if type(result) is int:
        _fail(-result)
    return _stat_result(result)


# ---- directories and names

def getcwd(*args: object, **kwds: object) -> str:
    _noargs("getcwd", args, kwds)
    result = _sys("getcwd")
    if type(result) is int:
        _fail(-result)
    return bytes.decode(result, "utf-8", "surrogateescape")


def getcwdb(*args: object, **kwds: object) -> bytes:
    _noargs("getcwdb", args, kwds)
    result = _sys("getcwd")
    if type(result) is int:
        _fail(-result)
    return result


def listdir(*args: object, **kwds: object) -> list[object]:
    path = _unpack("listdir", args, kwds, ("path",), 0, 1)[0]
    data, shown = _path("listdir", "path", None if path is _ABSENT else path, allow_fd=True, nullable=True)
    if type(data) is int:                        # closedir closes it, so a duplicate: _Py_dup's error has no file name
        data = _sys("dup", data)
        if data < 0:
            _fail(-data)
    result = _sys("listdir", b"." if data is None else data)
    if type(result) is int:
        _fail(-result, shown)
    if type(data) is not int and issubclass(type(shown), bytes):   # only a bytes object says bytes
        return result
    return [bytes.decode(entry, "utf-8", "surrogateescape") for entry in result]


def _named(primitive: str, name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    path, dir_fd = _unpack(name, args, kwds, ("path", "dir_fd"), 1, 1)
    data, shown = _path(name, "path", path)
    code = _sys(primitive, data, _dir_fd(dir_fd))    # unlinkat, with AT_REMOVEDIR for rmdir
    if code < 0:
        _fail(-code, shown)


def rmdir(*args: object, **kwds: object) -> None:
    _named("rmdir", "rmdir", args, kwds)


def unlink(*args: object, **kwds: object) -> None:
    _named("unlink", "unlink", args, kwds)


def remove(*args: object, **kwds: object) -> None:
    _named("unlink", "remove", args, kwds)


def mkdir(*args: object, **kwds: object) -> None:
    path, mode, dir_fd = _unpack("mkdir", args, kwds, ("path", "mode", "dir_fd"), 1, 2)
    data, shown = _path("mkdir", "path", path)
    bits = 0o777 if mode is _ABSENT else _int(mode)
    code = _sys("mkdir", data, bits, _dir_fd(dir_fd))   # mkdirat
    if code < 0:
        _fail(-code, shown)


def _rename(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # internal_rename
    src, dst, src_fd, dst_fd = _unpack(name, args, kwds, ("src", "dst", "src_dir_fd", "dst_dir_fd"), 2, 2)
    a, shown_a = _path(name, "src", src)
    b, shown_b = _path(name, "dst", dst)
    under_a = _dir_fd(src_fd)
    code = _sys("rename", a, b, under_a, _dir_fd(dst_fd))   # renameat
    if code < 0:
        _fail(-code, shown_a, shown_b)


def rename(*args: object, **kwds: object) -> None:
    _rename("rename", args, kwds)


def replace(*args: object, **kwds: object) -> None:
    _rename("replace", args, kwds)


def chdir(*args: object, **kwds: object) -> None:
    path = _unpack("chdir", args, kwds, ("path",), 1, 1)[0]
    data, shown = _path("chdir", "path", path, allow_fd=True)
    code = _sys("chdir", data)
    if code < 0:
        _fail(-code, shown)


def access(*args: object, **kwds: object) -> bool:
    path, mode, dir_fd, effective_ids, follow = _unpack("access", args, kwds, ("path", "mode", "dir_fd", "effective_ids", "follow_symlinks"), 2, 2)
    data, _shown = _path("access", "path", path)
    bits = _int(mode)
    under = _dir_fd(dir_fd)
    effective = effective_ids is not _ABSENT and bool(effective_ids)
    follows = follow is _ABSENT or bool(follow)
    return _sys("access", data, bits, under, effective, follows) == 0   # faccessat when any of the three is given


def readlink(*args: object, **kwds: object) -> object:
    path, dir_fd = _unpack("readlink", args, kwds, ("path", "dir_fd"), 1, 1)
    data, shown = _path("readlink", "path", path)
    result = _sys("readlink", data, _dir_fd(dir_fd))   # readlinkat
    if type(result) is int:
        _fail(-result, shown)
    return result if issubclass(type(shown), bytes) else bytes.decode(result, "utf-8", "surrogateescape")


def symlink(*args: object, **kwds: object) -> None:
    src, dst, is_dir, dir_fd = _unpack("symlink", args, kwds, ("src", "dst", "target_is_directory", "dir_fd"), 2, 3)
    a, shown_a = _path("symlink", "src", src)
    b, shown_b = _path("symlink", "dst", dst)
    if is_dir is not _ABSENT:
        bool(is_dir)
    code = _sys("symlink", a, b, _dir_fd(dir_fd))   # symlinkat
    if code < 0:
        _fail(-code, shown_a, shown_b)


def link(*args: object, **kwds: object) -> None:
    src, dst, src_fd, dst_fd, follow = _unpack("link", args, kwds, ("src", "dst", "src_dir_fd", "dst_dir_fd", "follow_symlinks"), 2, 2)
    a, shown_a = _path("link", "src", src)
    b, shown_b = _path("link", "dst", dst)
    under_a = _dir_fd(src_fd)
    under_b = _dir_fd(dst_fd)
    code = _sys("link", a, b, follow is _ABSENT or bool(follow), under_a, under_b)   # linkat
    if code < 0:
        _fail(-code, shown_a, shown_b)


# ---- file descriptors

def open(*args: object, **kwds: object) -> int:  # noqa: A001
    path, flags, mode, dir_fd = _unpack("open", args, kwds, ("path", "flags", "mode", "dir_fd"), 2, 3)
    data, shown = _path("open", "path", path)
    bits = _int(flags)
    perms = 0o777 if mode is _ABSENT else _int(mode)
    fd = _sys("open", data, bits, perms, _dir_fd(dir_fd))   # openat
    if fd < 0:
        _fail(-fd, shown)
    return fd


def close(*args: object, **kwds: object) -> None:
    code = _sys("close", _int(_unpack("close", args, kwds, ("fd",), 1, 1)[0]))
    if code < 0:
        _fail(-code)


def read(*args: object, **kwds: object) -> bytes:
    _positional("read", args, kwds, 2)
    fd = _int(args[0])
    length = _ssize(args[1])
    if length < 0:
        _fail(22)
    result = _sys("read", fd, length)
    if type(result) is int:
        _fail(-result)
    return result


def write(*args: object, **kwds: object) -> int:
    _positional("write", args, kwds, 2)
    fd = _int(args[0])
    data = args[1]
    if not issubclass(type(data), (bytes, bytearray)):
        if _type_lookup(data, "__buffer__") is not _ABSENT:
            _refuse("os.write() of a buffer that is not bytes or bytearray")
        raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")
    result = _sys("write", fd, data)
    if result < 0:
        _fail(-result)
    return result


def lseek(*args: object, **kwds: object) -> int:
    _positional("lseek", args, kwds, 3)
    fd = _int(args[0])
    position = _off(args[1])
    result = _sys("lseek", fd, position, _int(args[2]))
    if result < 0:
        _fail(-result)
    return result


def isatty(*args: object, **kwds: object) -> bool:
    return _sys("isatty", _int(_one("isatty", args, kwds))) == 1


def fsync(*args: object, **kwds: object) -> None:
    code = _sys("fsync", _fildes(_unpack("fsync", args, kwds, ("fd",), 1, 1)[0]))
    if code < 0:
        _fail(-code)


def get_terminal_size(*args: object, **kwds: object) -> object:
    if kwds:
        raise TypeError("posix.get_terminal_size() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("get_terminal_size expected at most 1 argument, got " + str(len(args)))
    result = _sys("terminal_size", _int(args[0]) if args else 1)
    if type(result) is int:
        _fail(-result)
    return terminal_size(result)


# ---- the process and the system

def strerror(*args: object, **kwds: object) -> str:
    return _sys("strerror", _int(_one("strerror", args, kwds)))


def umask(*args: object, **kwds: object) -> int:
    return _sys("umask", _int(_one("umask", args, kwds)))


def urandom(*args: object, **kwds: object) -> bytes:
    size = _ssize(_one("urandom", args, kwds))
    if size < 0:
        raise ValueError("size cannot be negative")
    return _sys("urandom", size)


def cpu_count(*args: object, **kwds: object) -> object:
    _noargs("cpu_count", args, kwds)
    count = _sys("cpu_count")
    return count if count >= 1 else None


def uname(*args: object, **kwds: object) -> object:
    _noargs("uname", args, kwds)
    result = _sys("uname")
    if type(result) is int:
        _fail(-result)
    return uname_result([bytes.decode(part, "utf-8", "surrogateescape") for part in result])


def times(*args: object, **kwds: object) -> object:
    _noargs("times", args, kwds)
    return times_result(_sys("times"))


def getpid(*args: object, **kwds: object) -> int:
    _noargs("getpid", args, kwds)
    return _sys("getpid")


def getppid(*args: object, **kwds: object) -> int:
    _noargs("getppid", args, kwds)
    return _sys("getppid")


def getuid(*args: object, **kwds: object) -> int:
    _noargs("getuid", args, kwds)
    return _sys("getuid")


def geteuid(*args: object, **kwds: object) -> int:
    _noargs("geteuid", args, kwds)
    return _sys("geteuid")


def getgid(*args: object, **kwds: object) -> int:
    _noargs("getgid", args, kwds)
    return _sys("getgid")


def getegid(*args: object, **kwds: object) -> int:
    _noargs("getegid", args, kwds)
    return _sys("getegid")


def putenv(*args: object, **kwds: object) -> None:
    _positional("putenv", args, kwds, 2)
    name = _fsconverter(args[0])
    value = _fsconverter(args[1])
    if 61 in name:
        raise ValueError("illegal environment variable name")
    code = _sys("putenv", name, value)
    if code < 0:
        _fail(-code)


def unsetenv(*args: object, **kwds: object) -> None:
    code = _sys("unsetenv", _fsconverter(_one("unsetenv", args, kwds)))
    if code < 0:
        _fail(-code)


def _clearenv(*args: object, **kwds: object) -> None:
    _noargs("_clearenv", args, kwds)
    _sys("clearenv")


def _create_environ(*args: object, **kwds: object) -> dict[bytes, bytes]:
    _noargs("_create_environ", args, kwds)
    return _sys("environ")


def _exit(*args: object, **kwds: object) -> None:
    _sys("exit", _int(_unpack("_exit", args, kwds, ("status",), 1, 1)[0]))


_at_fork: list[object] = []                      # nothing runs them until the runtime can fork, which stops by name


def register_at_fork(*args: object, **kwds: object) -> None:
    before, child, parent = _unpack("register_at_fork", args, kwds, ("before", "after_in_child", "after_in_parent"), 0, 0)
    if before is _ABSENT and child is _ABSENT and parent is _ABSENT:
        raise TypeError("At least one argument is required.")
    for value, name in ((before, "before"), (child, "after_in_child"), (parent, "after_in_parent")):
        if value is not _ABSENT and not callable(value):
            raise TypeError("'" + name + "' must be callable, not " + _tp_name(value))
    _at_fork.append((before, child, parent))


# ---- paths

def fspath(*args: object, **kwds: object) -> object:
    return _fspath(_unpack("fspath", args, kwds, ("path",), 1, 1)[0])


def _pure_path(function: str, value: object) -> object:   # path_t(make_wide=True, nonstrict=True): no check for a null
    if issubclass(type(value), (str, bytes)):
        return value
    func = _special(value, "__fspath__")
    if func is None:
        raise TypeError(function + ": path should be string, bytes or os.PathLike, not " + type(value).__name__)
    o = func()  # type: ignore[operator]
    if not issubclass(type(o), (str, bytes)):
        raise TypeError("expected " + type(value).__name__ + ".__fspath__() to return str or bytes, not " + type(o).__name__)
    return o


def _splitroot(path: object) -> tuple[object, object, object]:   # _Py_skiproot
    slash = b"/" if issubclass(type(path), bytes) else "/"
    empty = path[:0]  # type: ignore[index]
    if path[:1] != slash:  # type: ignore[index]
        return empty, empty, path
    if path[1:2] != slash or path[2:3] == slash:  # type: ignore[index]
        return empty, path[:1], path[1:]  # type: ignore[index]
    return empty, path[:2], path[2:]  # type: ignore[index]


def _path_splitroot_ex(*args: object, **kwds: object) -> tuple[object, object, object]:
    return _splitroot(_pure_path("_path_splitroot_ex", _one("_path_splitroot_ex", args, kwds)))


def _path_normpath(*args: object, **kwds: object) -> object:   # _Py_normpath_and_size
    path = _pure_path("_path_normpath", _unpack("_path_normpath", args, kwds, ("path",), 1, 1)[0])
    if issubclass(type(path), bytes):
        sep, dot, dotdot = b"/", b".", b".."
    else:
        sep, dot, dotdot = "/", ".", ".."  # type: ignore[assignment]
    _empty, initial, rest = _splitroot(path)
    parts: list[object] = []
    for part in rest.split(sep):  # type: ignore[attr-defined]
        if not part or part == dot:
            continue
        if part != dotdot or (not initial and not parts) or (parts and parts[-1] == dotdot):
            parts.append(part)
        elif parts:
            parts.pop()
    return (initial + sep.join(parts)) or dot  # type: ignore[operator, arg-type]


environ = _sys("environ")


def WCOREDUMP(*args: object, **kwds: object) -> bool:  # noqa: N802  # by position only
    return _sys("wstatus", b"COREDUMP", _int(_one("WCOREDUMP", args, kwds))) != 0  # type: ignore[no-any-return]


def WEXITSTATUS(*args: object, **kwds: object) -> int:  # noqa: N802
    return _wait_status("WEXITSTATUS", args, kwds)


def WIFCONTINUED(*args: object, **kwds: object) -> bool:  # noqa: N802
    return _wait_status("WIFCONTINUED", args, kwds) != 0


def WIFEXITED(*args: object, **kwds: object) -> bool:  # noqa: N802
    return _wait_status("WIFEXITED", args, kwds) != 0


def WIFSIGNALED(*args: object, **kwds: object) -> bool:  # noqa: N802
    return _wait_status("WIFSIGNALED", args, kwds) != 0


def WIFSTOPPED(*args: object, **kwds: object) -> bool:  # noqa: N802
    return _wait_status("WIFSTOPPED", args, kwds) != 0


def WSTOPSIG(*args: object, **kwds: object) -> int:  # noqa: N802
    return _wait_status("WSTOPSIG", args, kwds)


def WTERMSIG(*args: object, **kwds: object) -> int:  # noqa: N802
    return _wait_status("WTERMSIG", args, kwds)


_inputhook = _absent("_inputhook")
_is_inputhook_installed = _absent("_is_inputhook_installed")
abort = _absent("abort")


def chmod(*args: object, **kwds: object) -> None:   # os_chmod_impl: fchmod for a descriptor, fchmodat under dir_fd or for the link itself, else chmod
    path, mode, dir_fd, follow = _unpack("chmod", args, kwds, ("path", "mode", "dir_fd", "follow_symlinks"), 2, 2)
    data, shown = _path("chmod", "path", path, allow_fd=True)
    bits = _int(mode)
    under = _dir_fd(dir_fd)
    follows = follow is _ABSENT or bool(follow)
    code = _sys("chmod", data, bits, under, follows)
    if code < 0:
        if type(data) is not int and not follows and -code == 95:   # ENOTSUP: fchmodat cannot change a link's own mode here
            if under is not None:
                raise ValueError("chmod: cannot use dir_fd and follow_symlinks together")
            raise NotImplementedError("chmod: follow_symlinks unavailable on this platform")
        _fail(-code, shown)


def chown(*args: object, **kwds: object) -> None:   # os_chown_impl
    path, uid, gid, dir_fd, follow = _unpack("chown", args, kwds, ("path", "uid", "gid", "dir_fd", "follow_symlinks"), 3, 3)
    data, shown = _path("chown", "path", path, allow_fd=True)
    u = _id("uid", uid)
    g = _id("gid", gid)
    under = _dir_fd(dir_fd)
    follows = follow is _ABSENT or bool(follow)
    if type(data) is int:
        if under is not None:
            raise ValueError("chown: can't specify both dir_fd and fd")
        if not follows:
            raise ValueError("chown: cannot use fd and follow_symlinks together")
    code = _sys("chown", b"chown", data, u, g, under, follows)
    if code < 0:
        _fail(-code, shown)


chroot = _absent("chroot")


def closerange(*args: object, **kwds: object) -> None:   # os_closerange_impl: up to, not including, the second
    _positional("closerange", args, kwds, 2)
    low = _int(args[0])
    high = _int(args[1])
    _sys("closerange", low, high - 1)


def confstr(*args: object, **kwds: object) -> str | None:   # os_confstr_impl
    result = _sys("conf", b"confstr", _confname(_one("confstr", args, kwds), confstr_names))
    if result is None:
        return None
    if type(result) is int:
        _fail(-result)
    return bytes.decode(result, "utf-8", "surrogateescape")


def copy_file_range(*args: object, **kwds: object) -> int:   # os_copy_file_range_impl
    src, dst, count, offset_src, offset_dst = _unpack("copy_file_range", args, kwds, ("src", "dst", "count", "offset_src", "offset_dst"), 3, 5)
    source, target = _int(src), _int(dst)
    size = _ssize(count)
    if size < 0:
        raise ValueError("count cannot be negative")
    start = None if offset_src is _ABSENT or offset_src is None else _off(offset_src)
    place = None if offset_dst is _ABSENT or offset_dst is None else _off(offset_dst)
    result = _sys("copy_file_range", source, target, size, start, place)
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]
ctermid = _absent("ctermid")
device_encoding = _absent("device_encoding")


def dup(*args: object, **kwds: object) -> int:   # os_dup_impl: _Py_dup, a descriptor that is not inherited
    result = _sys("dup", _int(_one("dup", args, kwds)))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def dup2(*args: object, **kwds: object) -> int:   # os_dup2_impl
    fd, fd2, inheritable = _unpack("dup2", args, kwds, ("fd", "fd2", "inheritable"), 2, 3)
    a = _int(fd)
    b = _int(fd2)
    result = _sys("dup2", a, b, inheritable is _ABSENT or bool(inheritable))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def eventfd(*args: object, **kwds: object) -> int:   # os_eventfd_impl
    initval, flags = _unpack("eventfd", args, kwds, ("initval", "flags"), 1, 2)
    start = _unsigned(initval, "unsigned int", 32)
    result = _sys("eventfd", b"make", start, EFD_CLOEXEC if flags is _ABSENT else _int(flags))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def eventfd_read(*args: object, **kwds: object) -> int:   # os_eventfd_read_impl
    result = _sys("eventfd", b"read", _fildes(_unpack("eventfd_read", args, kwds, ("fd",), 1, 1)[0]))
    if type(result) is int:
        _fail(-result)
    return result[0]  # type: ignore[no-any-return]


def eventfd_write(*args: object, **kwds: object) -> None:   # os_eventfd_write_impl
    fd, value = _unpack("eventfd_write", args, kwds, ("fd", "value"), 2, 2)
    descriptor = _fildes(fd)
    count = _unsigned(value, "unsigned long long", 64)
    code = _sys("eventfd", b"write", descriptor, count - 2**64 if count >= 2**63 else count)
    if code < 0:
        _fail(-code)


execv = _absent("execv")
execve = _absent("execve")


def fchdir(*args: object, **kwds: object) -> None:   # os_fchdir_impl: fildes_converter, posix_fildes_fd
    code = _sys("fildes", b"fchdir", _fildes(_unpack("fchdir", args, kwds, ("fd",), 1, 1)[0]))
    if code < 0:
        _fail(-code)


def fchmod(*args: object, **kwds: object) -> None:   # os_fchmod_impl
    fd, mode = _unpack("fchmod", args, kwds, ("fd", "mode"), 2, 2)
    descriptor = _int(fd)
    code = _sys("chmod", descriptor, _int(mode), None, True)
    if code < 0:
        _fail(-code)


def fchown(*args: object, **kwds: object) -> None:   # os_fchown_impl
    fd, uid, gid = _unpack("fchown", args, kwds, ("fd", "uid", "gid"), 3, 3)
    descriptor = _int(fd)
    u = _id("uid", uid)
    code = _sys("chown", b"fchown", descriptor, u, _id("gid", gid))
    if code < 0:
        _fail(-code)


def fdatasync(*args: object, **kwds: object) -> None:   # os_fdatasync_impl
    code = _sys("fildes", b"fdatasync", _fildes(_unpack("fdatasync", args, kwds, ("fd",), 1, 1)[0]))
    if code < 0:
        _fail(-code)


fork = _absent("fork")
forkpty = _absent("forkpty")


def fpathconf(*args: object, **kwds: object) -> int:   # os_fpathconf_impl
    _positional("fpathconf", args, kwds, 2)
    fd = _fildes(args[0])
    error, value = _sys("conf", b"pathconf", _confname(args[1], pathconf_names), fd)
    if error:
        _fail(error)
    return value  # type: ignore[no-any-return]


def fstatvfs(*args: object, **kwds: object) -> object:   # os_fstatvfs_impl
    result = _sys("statvfs", _int(_one("fstatvfs", args, kwds)), True)
    if type(result) is int:
        _fail(-result)
    return statvfs_result(result)


def ftruncate(*args: object, **kwds: object) -> None:   # os_ftruncate_impl
    _positional("ftruncate", args, kwds, 2)
    fd = _int(args[0])
    code = _sys("truncate", fd, _off(args[1]))
    if code < 0:
        _fail(-code)


def get_blocking(*args: object, **kwds: object) -> bool:   # os_get_blocking_impl
    result = _sys("blocking", _int(_one("get_blocking", args, kwds)))
    if result < 0:
        _fail(-result)
    return result == 1  # type: ignore[no-any-return]


def get_inheritable(*args: object, **kwds: object) -> bool:   # os_get_inheritable_impl
    result = _sys("inheritable", _int(_one("get_inheritable", args, kwds)))
    if result < 0:
        _fail(-result)
    return result == 1  # type: ignore[no-any-return]


getgrouplist = _absent("getgrouplist")


def getgroups(*args: object, **kwds: object) -> list[int]:   # os_getgroups_impl
    _noargs("getgroups", args, kwds)
    result = _sys("ids", b"getgroups")
    if type(result) is int:
        _fail(-result)
    return [_from_id(g) for g in result]


def getloadavg(*args: object, **kwds: object) -> tuple[float, float, float]:   # os_getloadavg_impl
    _noargs("getloadavg", args, kwds)
    result = _sys("loadavg")
    if result is None:
        raise OSError("Load averages are unobtainable")
    return result  # type: ignore[no-any-return]


getlogin = _absent("getlogin")


def getpgid(*args: object, **kwds: object) -> int:   # os_getpgid_impl
    result = _sys("ids", b"getpgid", _int(_unpack("getpgid", args, kwds, ("pid",), 1, 1)[0]))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def getpgrp(*args: object, **kwds: object) -> int:   # os_getpgrp_impl
    _noargs("getpgrp", args, kwds)
    return _sys("ids", b"getpgrp")  # type: ignore[no-any-return]


def getpriority(*args: object, **kwds: object) -> int:   # os_getpriority_impl: errno says whether it failed, any value is a priority
    which, who = _unpack("getpriority", args, kwds, ("which", "who"), 2, 2)
    a = _int(which)
    error, value = _sys("ids", b"getpriority", a, _int(who))
    if error:
        _fail(error)
    return value  # type: ignore[no-any-return]


def getrandom(*args: object, **kwds: object) -> bytes:   # os_getrandom_impl
    size, flags = _unpack("getrandom", args, kwds, ("size", "flags"), 1, 2)
    length = _ssize(size)
    bits = 0 if flags is _ABSENT else _int(flags)
    if length < 0:
        _fail(22)
    result = _sys("getrandom", length, bits)
    if type(result) is int:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def getresgid(*args: object, **kwds: object) -> tuple[int, int, int]:   # os_getresgid_impl
    _noargs("getresgid", args, kwds)
    result = _sys("ids", b"getresgid")
    if type(result) is int:
        _fail(-result)
    return (_from_id(result[0]), _from_id(result[1]), _from_id(result[2]))


def getresuid(*args: object, **kwds: object) -> tuple[int, int, int]:   # os_getresuid_impl
    _noargs("getresuid", args, kwds)
    result = _sys("ids", b"getresuid")
    if type(result) is int:
        _fail(-result)
    return (_from_id(result[0]), _from_id(result[1]), _from_id(result[2]))


def getsid(*args: object, **kwds: object) -> int:   # os_getsid_impl
    result = _sys("ids", b"getsid", _int(_one("getsid", args, kwds)))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def _xattr_follow(function: str, data: object, follow: object) -> bool:
    """follow_symlinks of an extended-attribute function, and fd_and_follow_symlinks_invalid. It is the last parameter of
    each and is converted last: after the attribute, whose __fspath__ runs before this __bool__ (review R20, RL-429)."""
    follows = follow is _ABSENT or bool(follow)
    if type(data) is int and not follows:
        raise ValueError(function + ": cannot use fd and follow_symlinks together")
    return follows


def getxattr(*args: object, **kwds: object) -> bytes:   # os_getxattr_impl
    path, attribute, follow = _unpack("getxattr", args, kwds, ("path", "attribute", "follow_symlinks"), 2, 2)
    data, shown = _path("getxattr", "path", path, allow_fd=True)
    name = _path("getxattr", "attribute", attribute)[0]
    follows = _xattr_follow("getxattr", data, follow)
    result = _sys("xattr", b"get", data, follows, name)
    if type(result) is int:
        _fail(-result, shown)
    return result  # type: ignore[no-any-return]
grantpt = _absent("grantpt")
initgroups = _absent("initgroups")
kill = _absent("kill")
killpg = _absent("killpg")


def lchown(*args: object, **kwds: object) -> None:   # os_lchown_impl
    path, uid, gid = _unpack("lchown", args, kwds, ("path", "uid", "gid"), 3, 3)
    data, shown = _path("lchown", "path", path)
    u = _id("uid", uid)
    code = _sys("chown", b"lchown", data, u, _id("gid", gid))
    if code < 0:
        _fail(-code, shown)


def listxattr(*args: object, **kwds: object) -> list[str]:   # os_listxattr_impl: the names are str whatever the path is
    path, follow = _unpack("listxattr", args, kwds, ("path", "follow_symlinks"), 0, 1)
    data, shown = _path("listxattr", "path", None if path is _ABSENT else path, allow_fd=True, nullable=True)
    follows = _xattr_follow("listxattr", data, follow)
    result = _sys("xattr", b"list", b"." if data is None else data, follows)
    if type(result) is int:
        _fail(-result, shown)
    return [bytes.decode(name, "utf-8", "surrogateescape") for name in result]


def lockf(*args: object, **kwds: object) -> None:   # os_lockf_impl
    _positional("lockf", args, kwds, 3)
    fd = _int(args[0])
    command = _int(args[1])
    code = _sys("lockf", fd, command, _off(args[2]))
    if code < 0:
        _fail(-code)


login_tty = _absent("login_tty")


def major(*args: object, **kwds: object) -> int:   # os_major_impl
    return _major_minor(_sys("dev", b"major", _dev(_one("major", args, kwds))))


def makedev(*args: object, **kwds: object) -> int:   # os_makedev_impl: each part NODEV or an unsigned int (major_minor_check)
    _positional("makedev", args, kwds, 2)
    a = _dev(args[0])
    b = _dev(args[1])
    if not (-1 <= a <= 4294967295 and -1 <= b <= 4294967295):
        raise OverflowError("Python int too large to convert to C unsigned int")
    device = _sys("dev", b"make", a, b)
    return -1 if device == 18446744073709551615 else device  # type: ignore[no-any-return]  # _PyLong_FromDev


def memfd_create(*args: object, **kwds: object) -> int:   # os_memfd_create_impl
    name, flags = _unpack("memfd_create", args, kwds, ("name", "flags"), 1, 2)
    data = _fsconverter(name)
    result = _sys("memfd", data, MFD_CLOEXEC if flags is _ABSENT else _unsigned_bits(flags))
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def minor(*args: object, **kwds: object) -> int:   # os_minor_impl
    return _major_minor(_sys("dev", b"minor", _dev(_one("minor", args, kwds))))


def mkfifo(*args: object, **kwds: object) -> None:   # os_mkfifo_impl: posix_error, which names no file
    path, mode, dir_fd = _unpack("mkfifo", args, kwds, ("path", "mode", "dir_fd"), 1, 2)
    data, _shown = _path("mkfifo", "path", path)
    bits = 0o666 if mode is _ABSENT else _int(mode)
    code = _sys("mknod", data, bits, None, _dir_fd(dir_fd))
    if code < 0:
        _fail(-code)


def mknod(*args: object, **kwds: object) -> None:   # os_mknod_impl
    path, mode, device, dir_fd = _unpack("mknod", args, kwds, ("path", "mode", "device", "dir_fd"), 1, 3)
    data, _shown = _path("mknod", "path", path)
    bits = 0o600 if mode is _ABSENT else _int(mode)
    number = 0 if device is _ABSENT else _dev(device)
    code = _sys("mknod", data, bits, number, _dir_fd(dir_fd))
    if code < 0:
        _fail(-code)


def nice(*args: object, **kwds: object) -> int:   # os_nice_impl: the new priority, which may be -1 without an error
    error, value = _sys("ids", b"nice", _int(_one("nice", args, kwds)))
    if error:
        _fail(error)
    return value  # type: ignore[no-any-return]


openpty = _absent("openpty")


def pathconf(*args: object, **kwds: object) -> int:   # os_pathconf_impl: EINVAL may be the name's, so it carries no file name
    path, name = _unpack("pathconf", args, kwds, ("path", "name"), 2, 2)
    data, shown = _path("pathconf", "path", path, allow_fd=True)
    error, value = _sys("conf", b"pathconf", _confname(name, pathconf_names), data)
    if error:
        if error == 22:
            _fail(error)
        _fail(error, shown)
    return value  # type: ignore[no-any-return]


pidfd_open = _absent("pidfd_open")


def pipe(*args: object, **kwds: object) -> tuple[int, int]:   # os_pipe_impl: pipe2 with O_CLOEXEC
    _noargs("pipe", args, kwds)
    result = _sys("pipe", O_CLOEXEC)
    if type(result) is int:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def pipe2(*args: object, **kwds: object) -> tuple[int, int]:   # os_pipe2_impl
    result = _sys("pipe", _int(_one("pipe2", args, kwds)))
    if type(result) is int:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def posix_fadvise(*args: object, **kwds: object) -> None:   # os_posix_fadvise_impl
    _positional("posix_fadvise", args, kwds, 4)
    fd = _int(args[0])
    offset = _off(args[1])
    length = _off(args[2])
    code = _sys("posix_f", b"fadvise", fd, offset, length, _int(args[3]))
    if code < 0:
        _fail(-code)


def posix_fallocate(*args: object, **kwds: object) -> None:   # os_posix_fallocate_impl
    _positional("posix_fallocate", args, kwds, 3)
    fd = _int(args[0])
    offset = _off(args[1])
    code = _sys("posix_f", b"fallocate", fd, offset, _off(args[2]))
    if code < 0:
        _fail(-code)


posix_openpt = _absent("posix_openpt")
posix_spawn = _absent("posix_spawn")
posix_spawnp = _absent("posix_spawnp")


def pread(*args: object, **kwds: object) -> bytes:   # os_pread_impl
    _positional("pread", args, kwds, 3)
    fd = _int(args[0])
    length = _ssize(args[1])
    offset = _off(args[2])
    if length < 0:
        _fail(22)
    result = _sys("pread", fd, length, offset)
    if type(result) is int:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def preadv(*args: object, **kwds: object) -> int:   # os_preadv_impl
    _between("preadv", args, kwds, 3, 4)
    fd = _int(args[0])
    offset = _off(args[2])
    return _read_vector("preadv2", fd, args[1], offset, _int(args[3]) if len(args) > 3 else 0)


ptsname = _absent("ptsname")


def pwrite(*args: object, **kwds: object) -> int:   # os_pwrite_impl
    _positional("pwrite", args, kwds, 3)
    fd = _int(args[0])
    data = args[1]
    if not issubclass(type(data), (bytes, bytearray)):   # the Py_buffer converter
        if _type_lookup(data, "__buffer__") is not _ABSENT:
            _refuse("os.pwrite() of a buffer that is not bytes or bytearray")
        raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")
    result = _sys("pwrite", fd, bytes(data), _off(args[2]))  # type: ignore[arg-type]
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def pwritev(*args: object, **kwds: object) -> int:   # os_pwritev_impl
    _between("pwritev", args, kwds, 3, 4)
    fd = _int(args[0])
    offset = _off(args[2])
    return _write_vector("pwritev", fd, args[1], offset, _int(args[3]) if len(args) > 3 else 0)


def readinto(*args: object, **kwds: object) -> int:   # os_readinto_impl
    _positional("readinto", args, kwds, 2)
    fd = _int(args[0])
    buffer = args[1]
    if not issubclass(type(buffer), bytearray):  # Py_buffer(accept={rwbuffer})
        if not issubclass(type(buffer), bytes) and _type_lookup(buffer, "__buffer__") is not _ABSENT:
            _refuse("os.readinto() into a buffer that is not a bytearray")
        raise TypeError("readinto() argument 2 must be read-write bytes-like object, not " + _tp_name(buffer))
    result = _sys("read", fd, bytearray.__len__(buffer))  # type: ignore[arg-type]
    if type(result) is int:
        _fail(-result)
    bytearray.__setitem__(buffer, slice(0, len(result)), result)  # type: ignore[arg-type]
    return len(result)


def readv(*args: object, **kwds: object) -> int:   # os_readv_impl
    _positional("readv", args, kwds, 2)
    return _read_vector("readv", _int(args[0]), args[1], None, 0)


def removexattr(*args: object, **kwds: object) -> None:   # os_removexattr_impl
    path, attribute, follow = _unpack("removexattr", args, kwds, ("path", "attribute", "follow_symlinks"), 2, 2)
    data, shown = _path("removexattr", "path", path, allow_fd=True)
    name = _path("removexattr", "attribute", attribute)[0]
    follows = _xattr_follow("removexattr", data, follow)
    code = _sys("xattr", b"remove", data, follows, name)
    if code < 0:
        _fail(-code, shown)


def scandir(*args: object, **kwds: object) -> ScandirIterator:   # os_scandir_impl
    path = _unpack("scandir", args, kwds, ("path",), 0, 1)[0]
    data, shown = _path("scandir", "path", None if path is _ABSENT else path, allow_fd=True, nullable=True)
    iterator: ScandirIterator = _bella_new_instance(ScandirIterator)
    _entry_set(iterator, "_s_stream", None)
    _entry_set(iterator, "_s_shown", shown)
    _entry_set(iterator, "_s_bytes", type(data) is not int and data is not None and issubclass(type(shown), bytes))   # only a bytes object says bytes
    _entry_set(iterator, "_s_fd", data if type(data) is int else None)
    _entry_set(iterator, "_s_path", b"." if data is None else data)
    if type(data) is int:                        # closedir closes it, so a duplicate: _Py_dup's error has no file name
        opened = _sys("dup", data)
        if opened < 0:
            _fail(-opened)
        stream = _sys("opendir", opened)
    else:
        stream = _sys("opendir", b"." if data is None else data)
    if stream < 0:
        _fail(-stream, shown)                    # path_error(&iterator->path)
    _entry_set(iterator, "_s_stream", stream)
    return iterator
sched_get_priority_max = _absent("sched_get_priority_max")
sched_get_priority_min = _absent("sched_get_priority_min")
sched_getaffinity = _absent("sched_getaffinity")
sched_getparam = _absent("sched_getparam")
sched_getscheduler = _absent("sched_getscheduler")
sched_rr_get_interval = _absent("sched_rr_get_interval")
sched_setaffinity = _absent("sched_setaffinity")
sched_setparam = _absent("sched_setparam")
sched_setscheduler = _absent("sched_setscheduler")


def sched_yield(*args: object, **kwds: object) -> None:   # os_sched_yield_impl
    _noargs("sched_yield", args, kwds)
    code = _sys("sched_yield")
    if code < 0:
        _fail(-code)


def sendfile(*args: object, **kwds: object) -> int:   # os_sendfile_impl, as Linux has it: no offset means the input's own position
    out_fd, in_fd, offset, count = _unpack("sendfile", args, kwds, ("out_fd", "in_fd", "offset", "count"), 4, 4)
    target, source = _int(out_fd), _int(in_fd)
    size = _ssize(count)
    if size < 0:
        raise ValueError("count cannot be negative")
    result = _sys("sendfile", target, source, None if offset is None else _off(offset), size)
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def set_blocking(*args: object, **kwds: object) -> None:   # os_set_blocking_impl
    _positional("set_blocking", args, kwds, 2)
    fd = _int(args[0])
    code = _sys("blocking", fd, bool(args[1]))
    if code < 0:
        _fail(-code)


def set_inheritable(*args: object, **kwds: object) -> None:   # os_set_inheritable_impl: the flag is an int, not a truth
    _positional("set_inheritable", args, kwds, 2)
    fd = _int(args[0])
    code = _sys("inheritable", fd, _int(args[1]) != 0)
    if code < 0:
        _fail(-code)


setegid = _absent("setegid")
seteuid = _absent("seteuid")
setgid = _absent("setgid")
setgroups = _absent("setgroups")
setns = _absent("setns")
setpgid = _absent("setpgid")
setpgrp = _absent("setpgrp")
setpriority = _absent("setpriority")
setregid = _absent("setregid")
setresgid = _absent("setresgid")
setresuid = _absent("setresuid")
setreuid = _absent("setreuid")
setsid = _absent("setsid")
setuid = _absent("setuid")


def setxattr(*args: object, **kwds: object) -> None:   # os_setxattr_impl
    path, attribute, value, flags, follow = _unpack("setxattr", args, kwds, ("path", "attribute", "value", "flags", "follow_symlinks"), 3, 4)
    data, shown = _path("setxattr", "path", path, allow_fd=True)
    name = _path("setxattr", "attribute", attribute)[0]
    if not issubclass(type(value), (bytes, bytearray)):   # the Py_buffer converter
        if _type_lookup(value, "__buffer__") is not _ABSENT:
            _refuse("os.setxattr() of a buffer that is not bytes or bytearray")
        raise TypeError("a bytes-like object is required, not '" + type(value).__name__ + "'")
    bits = 0 if flags is _ABSENT else _int(flags)
    follows = _xattr_follow("setxattr", data, follow)
    code = _sys("xattr", b"set", data, follows, name, bytes(value), bits)  # type: ignore[arg-type]
    if code < 0:
        _fail(-code, shown)


def splice(*args: object, **kwds: object) -> int:   # os_splice_impl: the offsets convert in the function, after the flags
    src, dst, count, offset_src, offset_dst, flags = _unpack("splice", args, kwds, ("src", "dst", "count", "offset_src", "offset_dst", "flags"), 3, 6)
    source, target = _int(src), _int(dst)
    size = _ssize(count)
    if size < 0:
        raise ValueError("count cannot be negative")
    bits = 0 if flags is _ABSENT else _unsigned(flags, "unsigned int", 32)
    start = None if offset_src is _ABSENT or offset_src is None else _off(offset_src)
    place = None if offset_dst is _ABSENT or offset_dst is None else _off(offset_dst)
    result = _sys("splice", source, target, size, start, place, bits)
    if result < 0:
        _fail(-result)
    return result  # type: ignore[no-any-return]


def statvfs(*args: object, **kwds: object) -> object:   # os_statvfs_impl
    data, shown = _path("statvfs", "path", _unpack("statvfs", args, kwds, ("path",), 1, 1)[0], allow_fd=True)
    result = _sys("statvfs", data, False)
    if type(result) is int:
        _fail(-result, shown)
    return statvfs_result(result)


def sync(*args: object, **kwds: object) -> None:   # os_sync_impl
    _noargs("sync", args, kwds)
    _sys("sync")


def sysconf(*args: object, **kwds: object) -> int:   # os_sysconf_impl
    error, value = _sys("conf", b"sysconf", _confname(_one("sysconf", args, kwds), sysconf_names))
    if error:
        _fail(error)
    return value  # type: ignore[no-any-return]


system = _absent("system")
tcgetpgrp = _absent("tcgetpgrp")
tcsetpgrp = _absent("tcsetpgrp")
timerfd_create = _absent("timerfd_create")
timerfd_gettime = _absent("timerfd_gettime")
timerfd_gettime_ns = _absent("timerfd_gettime_ns")
timerfd_settime = _absent("timerfd_settime")
timerfd_settime_ns = _absent("timerfd_settime_ns")


def truncate(*args: object, **kwds: object) -> None:   # os_truncate_impl: by name, or by a descriptor as ftruncate
    path, length = _unpack("truncate", args, kwds, ("path", "length"), 2, 2)
    data, shown = _path("truncate", "path", path, allow_fd=True)
    code = _sys("truncate", data, _off(length))
    if code < 0:
        if type(data) is int:
            _fail(-code)
        _fail(-code, shown)


ttyname = _absent("ttyname")
unlockpt = _absent("unlockpt")
unshare = _absent("unshare")


def _time_t(value: object) -> int:               # _PyLong_AsTime_t
    seconds = _number_index(value)
    if not -(2**63) <= seconds < 2**63:
        raise OverflowError("timestamp out of range for platform time_t")
    return seconds


def _timespec(value: object) -> tuple[int, int]:   # pytime_object_to_denominator(obj, &sec, &nsec, 1e9, _PyTime_ROUND_FLOOR)
    if _type_lookup(value, "__index__") is not _ABSENT:   # PyIndex_Check: whole seconds
        return _time_t(value), 0
    d = _as_double(value)                        # PyFloat_AsDouble: a float, or what has __float__; "must be real number" otherwise
    if d != d:
        raise ValueError("Invalid value NaN (not a number)")
    if d - d != 0.0:                             # an infinity: modf leaves it whole, and no time_t holds it
        raise OverflowError("timestamp out of range for platform time_t")
    whole = float(int(d))                        # modf: the integral part, towards zero
    part = (d - whole) * 1e9
    floor = float(int(part))                     # _PyTime_ROUND_FLOOR
    if part < floor:
        floor -= 1.0
    if floor >= 1e9:
        floor -= 1e9
        whole += 1.0
    elif floor < 0:
        floor += 1e9
        whole -= 1.0
    if not -9223372036854775808.0 <= whole < 9223372036854775808.0:
        raise OverflowError("timestamp out of range for platform time_t")
    return int(whole), int(floor)


def _split_ns(value: object) -> tuple[int, int]:   # split_py_long_to_s_and_ns: the object's own divmod by a billion
    pair = divmod(value, 1000000000)  # type: ignore[operator]
    if not issubclass(type(pair), tuple) or tuple.__len__(pair) != 2:
        raise TypeError(type(value).__name__ + ".__divmod__() must return a 2-tuple, not " + type(pair).__name__)
    seconds = _time_t(tuple.__getitem__(pair, 0))
    nanoseconds = _number_index(tuple.__getitem__(pair, 1))
    if not -(2**63) <= nanoseconds < 2**63:
        raise OverflowError("Python int too large to convert to C long")
    return seconds, nanoseconds


def utime(*args: object, **kwds: object) -> None:   # os_utime_impl
    path, times, ns, dir_fd, follow = _unpack("utime", args, kwds, ("path", "times", "ns", "dir_fd", "follow_symlinks"), 1, 2)
    data, shown = _path("utime", "path", path, allow_fd=True)
    under = _dir_fd(dir_fd)
    follows = follow is _ABSENT or bool(follow)
    given = times is not _ABSENT and times is not None
    if given and ns is not _ABSENT:
        raise ValueError("utime: you may specify either 'times' or 'ns' but not both")
    when: tuple[int, int, int, int] | None = None   # None: now
    if given:
        if type(times) is not tuple or len(times) != 2:
            raise TypeError("utime: 'times' must be either a tuple of two numbers or None")
        when = (*_timespec(times[0]), *_timespec(times[1]))
    elif ns is not _ABSENT:
        if type(ns) is not tuple or len(ns) != 2:
            raise TypeError("utime: 'ns' must be a tuple of two ints")
        when = (*_split_ns(ns[0]), *_split_ns(ns[1]))
    if type(data) is int:                        # path_and_dir_fd_invalid, fd_and_follow_symlinks_invalid
        if under is not None:
            raise ValueError("utime: can't specify dir_fd without matching path")
        if not follows:
            raise ValueError("utime: cannot use fd and follow_symlinks together")
    code = _sys("utime", data, when, under, follows)
    if code < 0:
        _fail(-code, shown)
wait = _absent("wait")
wait3 = _absent("wait3")
wait4 = _absent("wait4")
waitid = _absent("waitid")
waitpid = _absent("waitpid")


def waitstatus_to_exitcode(*args: object, **kwds: object) -> int:   # os_waitstatus_to_exitcode_impl
    status = _int(_unpack("waitstatus_to_exitcode", args, kwds, ("status",), 1, 1)[0])
    if _sys("wstatus", b"IFEXITED", status):
        return _sys("wstatus", b"EXITSTATUS", status)  # type: ignore[no-any-return]
    if _sys("wstatus", b"IFSIGNALED", status):
        signum = _sys("wstatus", b"TERMSIG", status)
        if signum <= 0:
            raise ValueError("invalid WTERMSIG: " + str(signum))
        return -signum  # type: ignore[no-any-return]
    if _sys("wstatus", b"IFSTOPPED", status):
        raise ValueError("process stopped by delivery of signal " + str(_sys("wstatus", b"STOPSIG", status)))
    raise ValueError("invalid wait status: " + str(status))


def writev(*args: object, **kwds: object) -> int:   # os_writev_impl
    _positional("writev", args, kwds, 2)
    return _write_vector("writev", _int(args[0]), args[1], None, 0)


