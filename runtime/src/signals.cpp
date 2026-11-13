// runtime/src/signals.cpp -- signals (bella/runtime.hpp): what Modules/signalmodule.c keeps outside its module's functions (the
// C handler and trip_signal, the table of handlers, the wakeup descriptor, _PyErr_CheckSignalsTstate, _PySignal_Fini), the
// evaluation loop's side of it (Python/ceval_gil.c: handle_signals, and the pending call that reports a failed wakeup write),
// and the system calls under runtime/prelude/_signal.py. CPython 3.15.2; one thread, which is the main one.
//
// Two notes, as CPython has (docs/DECISIONS.md, 2026-11-11):
//   is_tripped                 "a signal's handler is to be called": read and cleared by check_signals() alone.
//   detail::signal_breaker     the eval breaker as generated code tests it (BELLA_LOOK): one word for CPython's two bits, the
//                              signals bit (_PY_SIGNALS_PENDING_BIT) and the pending calls' (_PY_CALLS_TO_DO_BIT). The second is
//                              "a failed wakeup write waits to be reported", which is wakeup_error_count != 0, so the word is
//                              set while either is; only the C handler and a raising handler set it, and a look clears the
//                              signals bit alone by storing what the calls' bit is.
// A signal sets tripped[sig], then is_tripped, then the breaker, then writes its byte to the wakeup descriptor, in that order
// and nothing else. Three ways into the handlers:
//   check_signals()            PyErr_CheckSignals: where the C calls it itself. It reads is_tripped and never touches the breaker.
//   look_for_signals()         the evaluation loop's (_Py_HandlePending), the breaker already tested: the signals bit cleared,
//                              check_signals(), the bit set again if a handler raised; then, if a report was queued when the look
//                              began, the reports (make_pending_calls). The calls' bit stays set while the handlers run, so a
//                              Python handler's own entry look prints the report first, in the handler's frame, as CPython's does.
//   look_for_signals_now()     Py_MakePendingCalls: the same, whatever the breaker says (before and after the program, lock waits).
// The difference shows when a handler raises with another signal tripped: after look_for_signals() the next look of generated
// code runs the rest; after check_signals() the rest waits for the next check_signals(), as in CPython.
//
// The flags are namespace-scope objects with constant initialisation: the C handler may be the first to touch them, and it must
// meet no initialisation guard (the house's function-local statics have one). The table of handlers holds counts of its own
// and is touched by the handler never.
//
// The primitives are one function, `_signals(name, ...)`, as posix.cpp's `_sys` is; runtime/prelude/_signal.py has checked the
// arguments in the C's words. One call each: the value, or a negative errno (an int, where the value is a tuple or a list).
//   "rt" -> (SIGRTMIN, SIGRTMAX)                      "exec", default_int_handler: the table from the dispositions; SIGINT's handler
//   "check" / "look" / "look_lean": check_signals, look_if_noted, look_if_lean     "handler", signum -> the entry, None for an empty one
//   "signal", signum, how, handler -> (old,)          how: 0 SIG_DFL, 1 SIG_IGN, 2 the C handler; -errno with nothing changed
//   "interrupt", signum: PyErr_SetInterruptEx         "alarm", seconds -> int        "pause"        "raise", signum -> 0
//   "strsignal", signum -> str or None                "siginterrupt", signum, flag -> 0
//   "fstat", fd -> 0      "blocking", fd -> 1 or 0    "wakeup", fd, warn -> the old descriptor
//   "setitimer", which, sec, usec, sec, usec -> (sec, usec, sec, usec) of the old timer        "getitimer", which -> the same
//   "sigaddset", number -> 0 or the errno (positive)  "sigmask", how, numbers -> [the old mask's numbers]
//   "sigpending" -> [numbers]    "sigfillset" -> [numbers]    "sigwait", numbers -> the number
//   "sigwaitinfo", numbers -> siginfo_t's seven       "sigtimedwait", numbers, sec, nsec -> the same (one call each: EINTR is
//                                                     the prelude's to loop on, with check_signals between)
//   "pthread_kill", the id's 64 bits as a C long, signum -> 0; another thread's id stops by name
//   "pidfd_send_signal", pidfd, signum, flags -> 0    "strerror", code -> str        "monotonic" -> nanoseconds
//   "wait", deadline -> 0 at the deadline, 1 after a signal ended the wait and look_for_signals_now() ran (a lock's wait,
//                       runtime/prelude/_thread.py, which tests the lock again); -1, no deadline, a wait only a signal ends
#include <fcntl.h>
#include <linux/futex.h>
#include <pthread.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <map>
#include <string_view>
#include <type_traits>
#include <utility>

#include "bella/runtime.hpp"

namespace bella {
// runtime.hpp declares the breaker `extern volatile int` so that <csignal>'s macros (SIGINT, SIG_DFL, si_pid, ...) stay out of
// the header every generated unit includes: a Python name spelled like a macro of that header is renamed (pipeline/backend/cpp.py)
static_assert(std::is_same_v<std::sig_atomic_t, int>, "bella/runtime.hpp declares detail::signal_breaker as volatile int");
static_assert(NSIG == 65, "runtime/prelude/_signal.py writes NSIG and its range checks as Linux's 65");
static_assert(std::atomic<int>::is_always_lock_free && std::atomic<unsigned>::is_always_lock_free, "the C handler takes no lock");

namespace detail {
volatile std::sig_atomic_t signal_breaker = 0;   // _PY_SIGNALS_PENDING_BIT | _PY_CALLS_TO_DO_BIT (the one pending call there is)
}

namespace {
constexpr unsigned WAKEUP_ERRORS = 32;           // MAXPENDINGCALLS_MAIN: a report past it is dropped, as _PyEval_AddPendingCall's is

constinit volatile std::sig_atomic_t is_tripped = 0;
constinit volatile std::sig_atomic_t tripped[NSIG] = {};        // Handlers[i].tripped
constinit volatile std::sig_atomic_t wakeup_fd = -1;            // wakeup.fd
constinit volatile std::sig_atomic_t wakeup_warn = 1;           // wakeup.warn_on_full_buffer
constinit std::atomic<unsigned> wakeup_error_count{0};          // the errno of each write that failed, until a look reports it
constinit std::atomic<int> wakeup_errors[WAKEUP_ERRORS]{};
constinit Obj handlers[NSIG]{};                  // Handlers[i].func, owned: Unset (NULL) once the fini has run, else None, the int 0
                                                 // (SIG_DFL) or 1 (SIG_IGN), or a callable
bool lean_build = false;                         // the program's units were compiled with -DBELLA_LEAN: set_lean, before run_main
bool reporting = false;                          // make_pending_calls: "we don't do recursive pending calls"

// posix.cpp's, which are local to it
std::int64_t i64_of(Obj v) {
    std::int64_t out = 0;
    int_fits_i64(v, out);
    return out;
}
int int_of(Obj v) { return static_cast<int>(i64_of(v)); }
Ref failed() { return int_from_i64(-errno); }
Ref result(std::int64_t r) { return r < 0 ? failed() : int_from_i64(r); }

// ---- what a signal does (async-signal-safe: stores, one write, and lock-free atomics)
void queue_wakeup_error(int error) noexcept {    // _PyEval_AddPendingCall(report_wakeup_write_error, errno), with no lock and no allocation
    unsigned n = wakeup_error_count.load();
    do {
        if (n >= WAKEUP_ERRORS) return;
    } while (!wakeup_error_count.compare_exchange_weak(n, n + 1));
    wakeup_errors[n].store(error);               // a handler that came in between took the next place; the reader runs when no handler does
}
void trip(int sig) noexcept {                    // trip_signal, in its order
    tripped[sig] = 1;
    is_tripped = 1;                              // "Set is_tripped after setting .tripped, as it gets cleared in PyErr_CheckSignals() before .tripped."
    detail::signal_breaker = 1;                  // _PyEval_SignalReceived
    int fd = wakeup_fd;                          // "write to the wakeup fd *after* setting all the globals"
    if (fd == -1) return;
    unsigned char byte = static_cast<unsigned char>(sig);
    ssize_t rc;
    do rc = ::write(fd, &byte, 1);               // _Py_write_noraise: again after a signal, and no handler is called
    while (rc < 0 && errno == EINTR);
    if (rc < 0 && (wakeup_warn || (errno != EWOULDBLOCK && errno != EAGAIN))) queue_wakeup_error(errno);
}
extern "C" {
static void bella_signal_handler(int sig) noexcept {   // signal_handler: sigaction keeps it installed
    int saved = errno;                           // "asynchronously executing signal handlers should not mutate errno under the feet of unsuspecting C code"
    trip(sig);
    errno = saved;
}
}

// PyOS_setsig: sigaction with an empty mask and SA_ONSTACK alone. No SA_RESTART, so a blocking call answers EINTR and its
// loop runs the handlers; siginterrupt() reads these flags and writes them back with one bit changed
bool set_disposition(int sig, void (*handler)(int)) {
    struct sigaction context{};
    context.sa_handler = handler;
    sigemptyset(&context.sa_mask);
    context.sa_flags = SA_ONSTACK;
    return ::sigaction(sig, &context, nullptr) == 0;
}
bool is_action(Obj v) { return v == Obj::small(0) || v == Obj::small(1); }   // compare_handler against SIG_DFL and SIG_IGN: the table holds them as these two
bool is_python_handler(Obj v) { return !v.is_unset() && v != None() && !is_action(v); }
Ref exchange_handler(int signum, Obj fresh) {    // set_handler(signum, Py_NewRef(fresh)); what was there is the caller's to release
    incref(fresh);
    return Ref::steal(std::exchange(handlers[signum], fresh));
}

// ---- the frame a handler is given (docs/dialect-spec.md E-02): None when no frame of the program is running, which is CPython's
// rule (_PyThreadState_GetFrame is NULL: a call from the exit path, a built-in called by atexit), and in a lean build; else
// an object of the type types.FrameType is, with nothing in it: what CPython's has is the names table's `frame:` rows, so reading
// f_lineno stops by name
ClassObject* frame_class() {
    return no_instances_yet("frame");            // once, whichever asks first: `_types` when it is filled, or a handler given a frame
}
Ref frame_argument() {
    if (lean_build || detail::current_frame() == nullptr) return none_ref();
    return own(new Native(frame_class()));
}

// ---- the report of a wakeup write that failed: the pending call of trip_signal, run by a look and never by check_signals()
void report_wakeup_error(int error) {            // report_wakeup_write_error
    Obj saved = detail::raising();               // PyErr_GetRaisedException ... PyErr_SetRaisedException: what is in flight stays so
    const void* owner = detail::raising_owner();
    try {
        Ref number = int_from_i64(error), text = str_new(std::strerror(error));
        Ref exc = invoke(Obj::of(exception_class("OSError")), {number.get(), text.get()});   // PyErr_SetFromErrno: errno's own class
        raise(exc.get());
    } catch (const PyError& e) {
        report_unraisable("Exception ignored while trying to write to the signal wakeup fd", e);
    }
    detail::raising() = saved;
    detail::raising_owner() = owner;
}
void report_wakeup_errors() {                    // make_pending_calls over the main thread's queue
    if (reporting || wakeup_error_count.load() == 0) return;
    reporting = true;
    struct Done {
        ~Done() { reporting = false; }
    } done;
    for (unsigned calls = 0; calls < WAKEUP_ERRORS;) {   // "perform a bounded number of calls, in case of recursion"
        int taken[WAKEUP_ERRORS];
        unsigned n = wakeup_error_count.load();
        do {                                     // a handler only appends: once the count goes from n to 0 unchanged, the n copied are all of them
            for (unsigned i = 0; i < n; ++i) taken[i] = wakeup_errors[i].load();
        } while (!wakeup_error_count.compare_exchange_weak(n, 0));
        if (n == 0) return;
        for (unsigned i = 0; i < n; ++i, ++calls) report_wakeup_error(taken[i]);
    }
    if (wakeup_error_count.load() != 0) detail::signal_breaker = 1;   // "We hit pending->maxloop": signal_pending_calls
}
}  // namespace

// ---- the three ways in ------------------------------------------------------------------------------------------------------
bool interrupt_occurred() {                      // _PyOS_InterruptOccurred: a SIGINT that came is taken, and its handler is not called
    if (!tripped[SIGINT]) return false;
    tripped[SIGINT] = 0;
    return true;
}
void check_signals() {                           // PyErr_CheckSignals -> _PyErr_CheckSignalsTstate
    if (!is_tripped) return;
    is_tripped = 0;                              // before the walk: a signal that arrives during it sets the flag again
    Ref frame;                                   // one object for the pass, made at its first handler
    for (int i = 1; i < NSIG; ++i) {
        if (!tripped[i]) continue;
        tripped[i] = 0;                          // before the call: the handler may raise its own signal
        Ref func = Ref::share(handlers[i]);      // get_handler(i), now: one installed while the signal waited is the one called
        if (!is_python_handler(func.get())) {    // "No Python signal handler due to aforementioned race condition"
            try {
                raise_new("OSError", "Signal " + std::to_string(i) + " ignored due to race condition");
            } catch (const PyError& e) {
                report_unraisable("Exception ignored while calling signal handler", e);
            }
            continue;
        }
        if (frame.get().is_unset()) frame = frame_argument();
        Ref number = int_from_i64(i);
        try {
            invoke(func.get(), {number.get(), frame.get()});   // Py_BuildValue("(iO)", i, frame); what it returns is dropped
        } catch (...) {
            is_tripped = 1;                      // "On error, re-schedule a call to _PyErr_CheckSignalsTstate()": the higher numbers stay tripped
            throw;
        }
    }
}
namespace {
void handle_signals() {                          // handle_signals (Python/ceval_gil.c)
    detail::signal_breaker = 0;                  // _Py_unset_eval_breaker_bit(_PY_SIGNALS_PENDING_BIT), and then the calls' bit as it
    if (wakeup_error_count.load() != 0) detail::signal_breaker = 1;   // is: make_pending_calls' to unset, and a handler's entry look sees
    try {                                                              // it. In this order no signal is lost: the C handler only sets the word
        check_signals();
    } catch (...) {
        detail::signal_breaker = 1;              // "On failure, re-schedule a call to handle_signals()"
        throw;
    }
}
}  // namespace
void look_for_signals() {                        // _Py_HandlePending: the breaker read once, then handle_signals, then make_pending_calls
    bool calls = wakeup_error_count.load() != 0; // if (breaker & _PY_CALLS_TO_DO_BIT): a report queued by a signal during the handlers
    handle_signals();                            // set the breaker, and the next look prints it
    if (calls) report_wakeup_errors();
}
void look_for_signals_now() {                    // _PyEval_MakePendingCalls: handle_signals and make_pending_calls, whatever the breaker says
    handle_signals();
    report_wakeup_errors();
}
void finish_pending_calls() {                    // _Py_FinishPendingCalls (pylifecycle.c, between the threads' shutdown and atexit):
    if (reporting) return;                       // make_pending_calls until nothing is queued; no handler runs here
    while (wakeup_error_count.load() != 0) report_wakeup_errors();
}

// ---- the start and the end ----------------------------------------------------------------------------------------------------
void set_lean(bool lean) { lean_build = lean; }
void look_if_lean() {
    if (lean_build) look_if_noted();
}
void signals_init() {                            // _PySignal_Init's signal_install_handlers: "Import _signal to install the Python SIGINT handler"
    Ref name = str_new("_signal");               // (SIGPIPE and SIGXFSZ are ignored at run_main's first line, C-7-73)
    import_module_level(name.get(), Obj{}, Obj{}, Obj{}, 0);
}
void signals_fini() {                            // _PySignal_Fini: "Restore default signals and clear handlers"
    for (int signum = 1; signum < NSIG; ++signum) {
        tripped[signum] = 0;
        Ref func = Ref::steal(std::exchange(handlers[signum], Obj{}));   // the slot is empty before its object goes: getsignal says None in its finaliser
        if (is_python_handler(func.get())) set_disposition(signum, SIG_DFL);
    }                                            // Py_XDECREF(func), with the signal at its default already
}
int exit_by_sigint() {                           // exit_sigint (Modules/main.c): "exit via the SIG_DFL handler for SIGINT if KeyboardInterrupt went unhandled"
    if (set_disposition(SIGINT, SIG_DFL)) ::kill(getpid(), SIGINT);
    else std::perror("signal");                  // "Impossible in normal environments."
    return SIGINT + 128;                         // "If setting SIG_DFL failed, or kill failed to terminate us"
}

// ---- runtime/prelude/_signal.py's primitives ------------------------------------------------------------------------------------
namespace {
void set_of(Obj numbers, sigset_t* set) {        // a tuple the prelude's converter made: every number is one sigaddset takes
    sigemptyset(set);
    for (Obj n : static_cast<Tuple*>(numbers.object())->items) sigaddset(set, int_of(n));
}
Ref members(const sigset_t& mask) {              // sigset_to_set's walk: the members from 1 to 64, in order
    Ref out = list_new({});
    for (int sig = 1; sig < NSIG; ++sig)
        if (sigismember(&mask, sig) == 1) list_append(out.get(), Obj::small(sig));
    return out;
}
Ref siginfo_fields(const siginfo_t& si) {        // fill_siginfo's seven, each member read whatever si_code says, as the C reads them
    Ref signo = int_from_i64(si.si_signo), code = int_from_i64(si.si_code), error = int_from_i64(si.si_errno), pid = int_from_i64(si.si_pid),
        uid = int_from_i64(static_cast<std::int64_t>(si.si_uid)), status = int_from_i64(si.si_status), band = int_from_i64(si.si_band);
    return tuple_new({signo.get(), code.get(), error.get(), pid.get(), uid.get(), status.get(), band.get()});
}
Ref timer_fields(const itimerval& v) {
    Ref sec = int_from_i64(v.it_value.tv_sec), usec = int_from_i64(v.it_value.tv_usec), isec = int_from_i64(v.it_interval.tv_sec),
        iusec = int_from_i64(v.it_interval.tv_usec);
    return tuple_new({sec.get(), usec.get(), isec.get(), iusec.get()});
}

Ref s_rt(Args) {                                 // (SIGRTMIN, SIGRTMAX): the C library's, which keeps some of the kernel's for itself
    Ref low = int_from_i64(SIGRTMIN), high = int_from_i64(SIGRTMAX);
    return tuple_new({low.get(), high.get()});
}
Ref s_exec(Args a) {                             // (default_int_handler): signal_get_set_handlers
    for (int signum = 1; signum < NSIG; ++signum) {
        struct sigaction context{};
        Obj entry = None();                      // "None of our business": another's handler, or a number sigaction refuses (PyOS_getsig's SIG_ERR)
        if (::sigaction(signum, nullptr, &context) == 0) {
            if (context.sa_handler == SIG_DFL) entry = Obj::small(0);
            else if (context.sa_handler == SIG_IGN) entry = Obj::small(1);
        }
        Ref old = exchange_handler(signum, entry);
    }
    // "Install Python SIGINT handler which raises KeyboardInterrupt", unless SIGINT was ignored when the program started. A lean
    // build leaves SIGINT as it found it: nothing in its generated code would look, and ^C must still end the program (docs/deviations.toml, the lean fidelity)
    if (!lean_build && handlers[SIGINT] == Obj::small(0)) {
        Ref old = exchange_handler(SIGINT, a.pos(0));
        set_disposition(SIGINT, bella_signal_handler);
    }
    return none_ref();
}
Ref s_check(Args) {
    check_signals();
    return none_ref();
}
Ref s_look(Args) {
    look_if_noted();
    return none_ref();
}
Ref s_look_lean(Args) {
    look_if_lean();
    return none_ref();
}
Ref s_handler(Args a) {                          // (signum): get_handler, NULL read as None
    Obj v = handlers[int_of(a.pos(0))];
    return v.is_unset() ? none_ref() : Ref::share(v);
}
Ref s_signal(Args a) {                           // (signum, how, handler): PyOS_setsig, then the entry exchanged; (old,) or -errno
    int signum = int_of(a.pos(0)), how = int_of(a.pos(1));
    void (*handler)(int) = SIG_DFL;
    if (how == 1) handler = SIG_IGN;
    else if (how == 2) handler = bella_signal_handler;
    if (!set_disposition(signum, handler)) return failed();
    Ref old = exchange_handler(signum, how == 2 ? a.pos(2) : Obj::small(how));   // SIG_DFL and SIG_IGN as the two ints is_action knows
    if (old.get().is_unset()) old = none_ref();
    return tuple_new({old.get()});
}
Ref s_interrupt(Args a) {                        // (signum, in range): PyErr_SetInterruptEx, for _thread.interrupt_main
    int signum = int_of(a.pos(0));
    if (!is_action(handlers[signum])) trip(signum);   // SIG_DFL and SIG_IGN are passed by in silence; None and an empty slot are not
    return none_ref();
}
Ref s_alarm(Args a) { return int_from_i64(static_cast<long>(::alarm(static_cast<unsigned>(int_of(a.pos(0)))))); }   // (long)alarm(seconds)
Ref s_pause(Args) {
    (void)::pause();
    return none_ref();
}
Ref s_raise(Args a) { return int_from_i64(::raise(int_of(a.pos(0))) != 0 ? -errno : 0); }   // the C library's raise, not kill(getpid()): it refuses 32 and 33
Ref s_strsignal(Args a) {                        // signal_strsignal_impl's three ways to None
    errno = 0;
    const char* text = strsignal(int_of(a.pos(0)));
    if (errno != 0 || text == nullptr || std::strstr(text, "Unknown signal") != nullptr) return none_ref();
    return str_new(text);
}
Ref s_siginterrupt(Args a) {                     // (signum, flag): the flags read, SA_RESTART cleared or set, and written back
    int signum = int_of(a.pos(0));
    struct sigaction act{};
    (void)::sigaction(signum, nullptr, &act);
    if (int_of(a.pos(1)) != 0) act.sa_flags &= ~SA_RESTART;
    else act.sa_flags |= SA_RESTART;
    return result(::sigaction(signum, &act, nullptr));
}
Ref s_fstat(Args a) {                            // _Py_fstat, for its error alone
    struct stat status{};
    return result(fstat(int_of(a.pos(0)), &status));
}
Ref s_blocking(Args a) {                         // _Py_get_blocking
    int flags = fcntl(int_of(a.pos(0)), F_GETFL, 0);
    if (flags < 0) return failed();
    return int_from_i64((flags & O_NONBLOCK) != 0 ? 0 : 1);
}
Ref s_wakeup(Args a) {                           // (fd, warn): the old descriptor
    int old = wakeup_fd;
    wakeup_fd = int_of(a.pos(0));
    wakeup_warn = truth(a.pos(1)) ? 1 : 0;
    return int_from_i64(old);
}
Ref s_setitimer(Args a) {                        // (which, sec, usec, sec, usec): the old timer's four, or -errno
    itimerval fresh{}, old{};
    fresh.it_value.tv_sec = static_cast<time_t>(i64_of(a.pos(1)));
    fresh.it_value.tv_usec = static_cast<suseconds_t>(i64_of(a.pos(2)));
    fresh.it_interval.tv_sec = static_cast<time_t>(i64_of(a.pos(3)));
    fresh.it_interval.tv_usec = static_cast<suseconds_t>(i64_of(a.pos(4)));
    if (setitimer(int_of(a.pos(0)), &fresh, &old) != 0) return failed();   // "Let OS check "which" value"
    return timer_fields(old);
}
Ref s_getitimer(Args a) {
    itimerval old{};
    if (getitimer(int_of(a.pos(0)), &old) != 0) return failed();
    return timer_fields(old);
}
Ref s_sigaddset(Args a) {                        // (number): 0, or the errno of a number the C library does not take (EINVAL for its own two)
    sigset_t set;
    sigemptyset(&set);
    return int_from_i64(sigaddset(&set, int_of(a.pos(0))) != 0 ? errno : 0);
}
Ref s_sigmask(Args a) {                          // (how, numbers): pthread_sigmask gives its error as its value
    sigset_t mask, previous;
    set_of(a.pos(1), &mask);
    int error = pthread_sigmask(int_of(a.pos(0)), &mask, &previous);
    if (error != 0) return int_from_i64(-error);
    return members(previous);
}
Ref s_sigpending(Args) {
    sigset_t mask;
    if (::sigpending(&mask) != 0) return failed();
    return members(mask);
}
Ref s_sigfillset(Args) {                         // signal_valid_signals_impl
    sigset_t mask;
    if (sigemptyset(&mask) != 0 || sigfillset(&mask) != 0) return failed();
    return members(mask);
}
Ref s_sigwait(Args a) {                          // (numbers): the number, or minus the error sigwait gave as its value
    sigset_t set;
    set_of(a.pos(0), &set);
    int signum = 0;
    int error = ::sigwait(&set, &signum);
    return int_from_i64(error != 0 ? -error : signum);
}
Ref s_sigwaitinfo(Args a) {                      // (numbers): one call; EINTR is the prelude's to loop on, with the handlers between
    sigset_t set;
    set_of(a.pos(0), &set);
    siginfo_t si{};
    if (::sigwaitinfo(&set, &si) == -1) return failed();
    return siginfo_fields(si);
}
Ref s_sigtimedwait(Args a) {                     // (numbers, sec, nsec): one call
    sigset_t set;
    set_of(a.pos(0), &set);
    siginfo_t si{};
    timespec ts{};
    ts.tv_sec = static_cast<time_t>(i64_of(a.pos(1)));
    ts.tv_nsec = static_cast<long>(i64_of(a.pos(2)));
    if (::sigtimedwait(&set, &si, &ts) == -1) return failed();
    return siginfo_fields(si);
}
Ref s_pthread_kill(Args a) {                     // (the id's 64 bits as a C long, signum)
    auto thread = static_cast<pthread_t>(static_cast<std::uint64_t>(i64_of(a.pos(0))));
    if (!pthread_equal(thread, pthread_self()))  // any other number is undefined in the C library, and there is no other thread
        throw NotImplemented("signal.pthread_kill to a thread that is not the calling one (the runtime has one thread; CPython hands any "
                             "number to the C library)");
    return int_from_i64(-::pthread_kill(thread, int_of(a.pos(1))));   // its error is its value
}
Ref s_pidfd_send_signal(Args a) {                // (pidfd, signum, flags): siginfo is NULL
    return result(syscall(__NR_pidfd_send_signal, int_of(a.pos(0)), int_of(a.pos(1)), nullptr, int_of(a.pos(2))));
}
Ref s_strerror(Args a) { return str_new(std::strerror(int_of(a.pos(0)))); }
Ref s_monotonic(Args) {                          // PyTime_MonotonicRaw, for _PyDeadline_Init and _PyDeadline_Get: "silently ignore error"
    timespec now{};
    (void)clock_gettime(CLOCK_MONOTONIC, &now);
    return int_from_i64(static_cast<std::int64_t>(now.tv_sec) * 1000000000 + now.tv_nsec);
}
Ref s_wait(Args a) {                             // (deadline): _PyMutex_LockTimed's park, on one thread, to a deadline of the monotonic clock
    std::int64_t deadline = i64_of(a.pos(0));    // in nanoseconds ("monotonic" plus the timeout, stopped at PyTime_MAX); -1 for none
    if (deadline < 0) {                          // untimed: a futex word nothing wakes. The kernel restarts such a wait after a handler
        static constinit int nobody = 0;         // whose signal has SA_RESTART (siginterrupt(sig, False)) and ends it after one without,
        long rc = syscall(SYS_futex, &nobody, FUTEX_WAIT_PRIVATE, 0, nullptr, nullptr, 0);   // as it does CPython's park; a timed wait
        if (rc == -1 && errno == EINTR) look_for_signals_now();   // ends after either (ERESTART_RESTARTBLOCK). 1 either way: a word
        return int_from_i64(1);                  // that woke for nothing (0, EAGAIN) only has the lock tried again
    }
    timespec until{};
    until.tv_sec = static_cast<time_t>(deadline / 1000000000);
    until.tv_nsec = static_cast<long>(deadline % 1000000000);
    int err = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &until, nullptr);
    if (err != EINTR) return int_from_i64(0);    // Py_PARK_TIMEOUT: the deadline is the clock's own, so no other error can come
    look_for_signals_now();                      // Py_PARK_INTR with _PY_LOCK_HANDLE_SIGNALS: Py_MakePendingCalls; what a handler
    return int_from_i64(1);                      // raises leaves the acquire (PY_LOCK_INTR), the lock not taken
}

using Primitive = Ref (*)(Args);
const std::map<std::string_view, Primitive>& primitives() {
    static const std::map<std::string_view, Primitive> table{
        {"rt", s_rt}, {"exec", s_exec}, {"check", s_check}, {"look", s_look}, {"look_lean", s_look_lean}, {"handler", s_handler}, {"signal", s_signal},
        {"interrupt", s_interrupt}, {"alarm", s_alarm}, {"pause", s_pause}, {"raise", s_raise}, {"strsignal", s_strsignal}, {"siginterrupt", s_siginterrupt},
        {"fstat", s_fstat}, {"blocking", s_blocking}, {"wakeup", s_wakeup}, {"setitimer", s_setitimer}, {"getitimer", s_getitimer}, {"sigaddset", s_sigaddset},
        {"sigmask", s_sigmask}, {"sigpending", s_sigpending}, {"sigfillset", s_sigfillset}, {"sigwait", s_sigwait}, {"sigwaitinfo", s_sigwaitinfo},
        {"sigtimedwait", s_sigtimedwait}, {"pthread_kill", s_pthread_kill}, {"pidfd_send_signal", s_pidfd_send_signal}, {"strerror", s_strerror},
        {"monotonic", s_monotonic}, {"wait", s_wait}};
    return table;
}
}  // namespace

Ref i_signals(Obj, Args a) {                     // _signals(name, ...)
    return primitives().at(as_str(a.pos(0))->text)(Args{a.data + 1, a.npos - 1, nullptr, 0});
}
}  // namespace bella
