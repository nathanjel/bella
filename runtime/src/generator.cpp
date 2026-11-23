// runtime/src/generator.cpp -- generators, from Objects/genobject.c. The body is the state machine the emitter writes
// (pipeline/backend/cpp.py, `generator`): one resume runs it from g->pc to the next yield, with everything that must
// outlive the C++ stack in g->slots. What is here is the object and its protocol: send, throw, close, yield from and
// finalisation on the last reference.
#include "bella/runtime.hpp"

namespace bella {
namespace {
const Str* N(const char* s) { return intern(s); }
Generator* gen_self(Obj v) { return static_cast<Generator*>(v.object()); }
void wrapper_args(Args a, const char* name, std::size_t n) {     // wrapper_call, check_num_args
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos != n)
        raise_new("TypeError", "expected " + std::to_string(n) + " argument" + (n == 1 ? "" : "s") + ", got " + std::to_string(a.npos));
}

void clear_frame(Generator* g) {                 // gen_clear_frame: the frame's values last to first, then its function
    g->state = GenState::Finished;
    for (auto it = g->slots.rbegin(); it != g->slots.rend(); ++it) *it = Ref{};
    g->sent = Ref{};
    g->pending = Ref{};
    g->delegate = Ref{};
    g->delegate_shown = Ref{};
    for (Obj e : g->handled) decref(e);
    g->handled.clear();
    g->errors.clear();
    g->function = Ref{};
}
void restore_handled(Generator* g) {             // gen_send_ex2: this frame's exc_info above the caller's
    for (Obj e : g->handled) handled_exceptions().push_back(e);
    g->handling = g->handled.size();
    g->handled.clear();
}
void save_handled(Generator* g) {                // and off again when it leaves
    auto& stack = handled_exceptions();
    g->handled.assign(stack.end() - static_cast<std::ptrdiff_t>(g->handling), stack.end());
    stack.resize(stack.size() - g->handling);
    g->handling = 0;
}

// gen_send_ex2: one resume. A value yielded, or, with `returned` set, what the frame returned
Ref resume(Generator* g, bool& returned) {
    restore_handled(g);
    g->state_before_resume = g->state;
    g->state = GenState::Executing;
    Ref value;
    try {
        value = g->resume(g);
    } catch (...) {
        auto& stack = handled_exceptions();
        for (std::size_t i = 0; i < g->handling; ++i) {
            decref(stack.back());
            stack.pop_back();
        }
        g->handling = 0;
        clear_frame(g);
        throw;
    }
    if (g->pc == GEN_RETURNED) {
        returned = true;
        save_handled(g);
        clear_frame(g);
        return value;
    }
    save_handled(g);
    g->state = GenState::Suspended;
    return value;
}
[[noreturn]] void already_executing() { raise_new("ValueError", "generator already executing"); }

// gen_send_ex: `arg` unset for gen_iternext. Unset back: an exhausted generator, asked by __next__
Ref send_ex(Generator* g, Obj arg, bool& returned) {
    if (g->state == GenState::Created && !arg.is_unset() && arg != None())
        raise_new("TypeError", "can't send non-None value to a just-started generator");
    if (g->state == GenState::Executing) already_executing();
    if (g->state == GenState::Finished) {
        if (!arg.is_unset()) {
            returned = true;
            return none_ref();
        }
        return Ref{};
    }
    g->sent = arg.is_unset() ? none_ref() : Ref::share(arg);
    return resume(g, returned);
}
[[noreturn]] void set_stop_iteration(Obj value) {   // PyErr_SetNone, or _PyGen_SetStopIterationValue: never as a tuple's items
    if (value == None()) {
        Ref stop = invoke(Obj::of(exception_class("StopIteration")), {});
        raise(stop.get());
    }
    throw PyError(invoke(Obj::of(exception_class("StopIteration")), {value}));
}
Ref returned_or_value(Ref result, bool returned) {  // gen_send: its return is StopIteration's value
    if (returned) set_stop_iteration(result.get());
    return result;
}

bool is_exception_class(Obj v) { return is_kind(v, Kind::Class) && is_subclass(static_cast<ClassObject*>(v.object()), exception_class("BaseException")); }
// _PyErr_CreateException: the class called with the value, which is no argument, a tuple's items or the one argument
Ref create_exception(Obj typ, Obj val) {
    Ref made;
    if (val.is_unset() || val == None()) {
        made = invoke(typ, {});
    } else if (is_kind(val, Kind::Tuple)) {      // PyTuple_Check: a subclass's instance too
        made = call_ex(typ, val, Obj{});
    } else {
        made = invoke(typ, {val});
    }
    if (!is_exception_instance(made.get())) {
        Ref shown = repr_of(typ);
        raise_new("TypeError", "calling " + as_str(shown.get())->text + " should have returned an instance of BaseException, not " + type_of(made.get())->name);
    }
    return made;
}
// gen_set_exception: what throw(typ, val, tb) raises in the generator. What cannot be thrown fails here, in the caller, and
// the generator stays where it was: a third argument that is no traceback, an instance with a value beside it, what is no
// exception. A class is made of the value as PyErr_NormalizeException makes it (the value itself when it is an instance of
// the class), and when the making fails, what it raised is thrown in its place, with the traceback given if it has none
Ref exception_of(Obj typ, Obj val = Obj{}, Obj tb = Obj{}) {
    if (!tb.is_unset() && tb == None()) tb = Obj{};
    if (!tb.is_unset() && !is_kind(tb, Kind::Traceback)) raise_new("TypeError", "throw() third argument must be a traceback object");
    Ref exc;
    if (is_exception_class(typ)) {
        try {
            // PyObject_IsSubclass, so a metaclass's __subclasscheck__ is asked, and what it raises is what is thrown (RL-479)
            if (!val.is_unset() && is_exception_instance(val) && object_issubclass(Obj::of(type_of(val)), typ))
                exc = Ref::share(val);
            else
                exc = create_exception(typ, val);
            // PyErr_Restore: a value that is not of the class itself is given to the class once more. That is the first
            // making's result when the class's __new__ answers with another class's instance (RL-480); a value that came
            // as an instance of a subclass has made its own class the type, and is left
            if (Obj::of(type_of(exc.get())) != typ && (val.is_unset() || exc.get() != val)) exc = create_exception(typ, exc.get());
        } catch (const PyError& e) {
            if (!tb.is_unset() && traceback_of(e.exc.get()).is_unset()) set_exception_field(e.exc.get(), "__traceback__", tb);
            return e.exc;
        }
    } else if (is_exception_instance(typ)) {
        if (!val.is_unset() && val != None()) raise_new("TypeError", "instance exception may not have a separate value");
        exc = Ref::share(typ);
    } else {
        raise_new("TypeError", "exceptions must be classes or instances deriving from BaseException, not " + type_of(typ)->name);
    }
    if (!tb.is_unset()) set_exception_field(exc.get(), "__traceback__", tb);   // PyErr_Restore with a traceback: the exception's own from here
    return exc;
}
Ref throw_current(Generator* g) {                 // gen_throw_current_exception
    bool returned = false;
    Ref result = resume(g, returned);
    return returned_or_value(std::move(result), returned);
}
bool matches_exit(Obj typ) {                      // PyErr_GivenExceptionMatches(typ, GeneratorExit): a class's or an instance's
    ClassObject* e = exception_class("GeneratorExit");
    if (is_exception_class(typ)) return is_subclass(static_cast<ClassObject*>(typ.object()), e);
    return is_exception_instance(typ) && is_subclass(type_of(typ), e);
}
// gen_close_iter: its close(), whatever it is; an AttributeError means it has none
void close_iter(Obj yf) {
    if (is_kind(yf, Kind::Generator)) {
        gen_close(gen_self(yf));
        return;
    }
    Ref meth;
    try {
        meth = optional_getattr(yf, N("close"));
    } catch (const PyError& e) {                 // PyErr_FormatUnraisable, and no close is called (RL-481)
        report_unraisable("Exception ignored while closing generator ", yf, e);
        return;
    }
    if (!meth.get().is_unset()) Ref ignored = invoke(meth.get(), {});
}
// gen_set_exception as _gen_throw calls it: with the frame marked as executing, so that the making of the exception cannot
// close or resume the generator it is for (a call of the class's __init__ that tries gets "generator already executing",
// which is then what is thrown in; RL-454). The state is put back whether it fails or not
void pend_exception(Generator* g, GenState back, Obj typ, Obj val, Obj tb) {
    g->state = GenState::Executing;
    try {
        g->pending = exception_of(typ, val, tb);
    } catch (...) {
        g->state = back;
        throw;
    }
    g->state = back;
}
// "Link frame into the stack to enable complete backtraces": while what a generator delegates to is thrown into, the
// generator's frame is the running one, so the stack listed there has it and a warning there is charged to its line (RL-456)
struct LinkedFrame {
    detail::FrameRecord record;
    explicit LinkedFrame(Generator* g) : record{g->code, g->module, detail::current_frame(), g->line} { detail::current_frame() = &record; }
    ~LinkedFrame() { detail::current_frame() = record.caller; }
    LinkedFrame(const LinkedFrame&) = delete;
    LinkedFrame& operator=(const LinkedFrame&) = delete;
};
Ref gen_throw_impl(Generator* g, Obj typ, Obj val = Obj{}, Obj tb = Obj{}) {   // _gen_throw
    if (g->state == GenState::Executing) already_executing();
    if (g->state == GenState::Finished) throw PyError(exception_of(typ, val, tb));
    if (g->delegate.get().is_unset() || g->state != GenState::Suspended) {
        pend_exception(g, g->state, typ, val, tb);
        return throw_current(g);
    }
    Ref yf = g->delegate;
    g->state = GenState::Executing;
    if (matches_exit(typ)) {
        bool failed = false;
        try {
            close_iter(yf.get());
        } catch (const PyError& e) {
            g->pending = e.exc;
            failed = true;
        }
        if (!failed) pend_exception(g, GenState::Suspended, typ, val, tb);
        g->state = GenState::Suspended;
        return throw_current(g);
    }
    Ref ret;
    Ref meth;
    bool has_throw = true;
    bool failed = false;
    if (!is_kind(yf.get(), Kind::Generator)) {
        try {                                    // the lookup's own error is the caller's, and the generator stays suspended (RL-455)
            meth = optional_getattr(yf.get(), N("throw"));
        } catch (...) {
            g->state = GenState::Suspended;
            throw;
        }
        has_throw = !meth.get().is_unset();
    }
    try {
        LinkedFrame linked(g);
        if (is_kind(yf.get(), Kind::Generator)) {
            ret = gen_throw_impl(gen_self(yf.get()), typ, val, tb);
        } else if (has_throw) {                      // PyObject_CallFunctionObjArgs(meth, typ, val, tb, NULL): as many as were given
            if (val.is_unset()) ret = invoke(meth.get(), {typ});
            else if (tb.is_unset()) ret = invoke(meth.get(), {typ, val});
            else ret = invoke(meth.get(), {typ, val, tb});
        }
    } catch (const PyError& e) {
        g->pending = e.exc;
        failed = true;
    }
    if (failed) {
        g->state = GenState::Suspended;
        return throw_current(g);
    }
    if (!has_throw) {                            // throw_here
        pend_exception(g, GenState::Suspended, typ, val, tb);
        return throw_current(g);
    }
    g->state = GenState::Suspended;
    return ret;
}

Ref iter_slot(Obj self, Args a) { wrapper_args(a, "__iter__", 0); return Ref::share(self); }
Ref next_slot(Obj self, Args a) {                 // gen_iternext, as tp_iternext's wrapper says: StopIteration
    wrapper_args(a, "__next__", 0);
    Ref v = gen_next(self);
    if (is_end(v)) set_stop_iteration(None());
    return v;
}
Ref send_m(Obj self, Args a) {                    // gen_send
    onearg(a, "generator.send");
    bool returned = false;
    Ref result = send_ex(gen_self(self), a.pos(0), returned);
    return returned_or_value(std::move(result), returned);
}
Ref close_m(Obj self, Args a) {
    noargs(a, "generator.close");
    return gen_close(gen_self(self));
}
Ref throw_m(Obj self, Args a) {                   // gen_throw
    if (a.nkw != 0) raise_new("TypeError", "generator.throw() takes no keyword arguments");
    if (a.npos < 1) raise_new("TypeError", "throw expected at least 1 argument, got 0");
    if (a.npos > 3) raise_new("TypeError", "throw expected at most 3 arguments, got " + std::to_string(a.npos));
    if (a.npos > 1) warn_ex("DeprecationWarning", "the (type, exc, tb) signature of throw() is deprecated, use the single-arg signature instead.");
    return gen_throw_impl(gen_self(self), a.pos(0), a.npos > 1 ? a.pos(1) : Obj{}, a.npos > 2 ? a.pos(2) : Obj{});
}
Ref del_m(Obj self, Args a) {                     // tp_finalize's wrapper
    wrapper_args(a, "__del__", 0);
    Generator* g = gen_self(self);
    if (g->state == GenState::Finished) return none_ref();
    try {
        gen_close(g);
    } catch (const PyError& e) {
        report_unraisable("Exception ignored while closing generator ", self, e);
    }
    return none_ref();
}
Ref repr_slot(Obj self, Args a) {
    wrapper_args(a, "__repr__", 0);
    char buf[32];
    std::snprintf(buf, sizeof buf, "%p", static_cast<void*>(self.object()));
    return str_new("<generator object " + as_str(gen_self(self)->qualname.get())->text + " at " + buf + ">");
}
Ref get_name(Obj self) { return gen_self(self)->name; }
void set_name(Obj self, Obj v) {
    if (v.is_unset() || as_str(v) == nullptr) raise_new("TypeError", "__name__ must be set to a string object");
    gen_self(self)->name = Ref::share(v);
}
Ref get_qualname(Obj self) { return gen_self(self)->qualname; }
void set_qualname(Obj self, Obj v) {
    if (v.is_unset() || as_str(v) == nullptr) raise_new("TypeError", "__qualname__ must be set to a string object");
    gen_self(self)->qualname = Ref::share(v);
}
Ref get_running(Obj self) { return Ref::steal(boolean(gen_self(self)->state == GenState::Executing)); }
Ref get_suspended(Obj self) { return Ref::steal(boolean(gen_self(self)->state == GenState::Suspended)); }
Ref get_yieldfrom(Obj self) {
    Generator* g = gen_self(self);
    if (g->state != GenState::Suspended || g->delegate.get().is_unset()) return none_ref();
    return g->delegate_shown.get().is_unset() ? g->delegate : g->delegate_shown;
}
Ref get_state(Obj self) {
    switch (gen_self(self)->state) {
        case GenState::Created: return Ref::share(Obj::of(N("GEN_CREATED")));
        case GenState::Suspended: return Ref::share(Obj::of(N("GEN_SUSPENDED")));
        case GenState::Executing: return Ref::share(Obj::of(N("GEN_RUNNING")));
        default: return Ref::share(Obj::of(N("GEN_CLOSED")));
    }
}
void method(ClassObject* c, const char* name, NativeFn fn) {
    auto* f = new Builtin(name, fn, Obj{}, Binding::Method);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
}  // namespace

Generator::Generator(PyFunction* fn, const Code& c, Ref (*r)(Generator*), std::size_t nslots, std::size_t nints, std::size_t nerrors)
    : Object(Kind::Generator), code(&c), module(fn->module), resume(r), slots(nslots), ints(nints, 0), errors(nerrors), line(c.first_line),
      function(Ref::share(Obj::of(fn))), name(fn->name), qualname(fn->qualname) {
    cls = types().generator;
}
Ref make_generator(PyFunction* fn, const Code& c, Ref (*r)(Generator*), std::size_t nslots, std::size_t nints, std::size_t nerrors) {
    return own(new Generator(fn, c, r, nslots, nints, nerrors));
}
Ref gen_next(Obj gen) {                           // gen_iternext: unset when it ended with None
    bool returned = false;
    Ref result = send_ex(gen_self(gen), Obj{}, returned);
    if (returned) {
        if (result.get() != None()) set_stop_iteration(result.get());
        return Ref{};
    }
    return result;
}
Ref gen_close(Generator* g) {                     // gen_close
    if (g->state == GenState::Created) {
        clear_frame(g);
        return none_ref();
    }
    if (g->state == GenState::Finished) return none_ref();
    if (g->state == GenState::Executing) already_executing();
    bool delegating = !g->delegate.get().is_unset();
    bool failed = false;
    if (delegating) {
        Ref yf = g->delegate;
        g->state = GenState::Executing;
        try {
            close_iter(yf.get());
        } catch (const PyError& e) {
            g->pending = e.exc;
            failed = true;
        }
        g->state = GenState::Suspended;
    }
    // RESUME after a yield at exception depth 1: nothing could catch it, so the frame is simply cleared
    if (!delegating && g->handler == 0) {
        clear_frame(g);
        return none_ref();
    }
    if (!failed) {
        g->pending = invoke(Obj::of(exception_class("GeneratorExit")), {});
        // PyErr_SetNone(PyExc_GeneratorExit): set while the caller's exception is the one being handled, which it so takes
        // as its context; the generator's own, if it is in a handler, replaces it when the exception is raised there (RL-678)
        auto& stack = handled_exceptions();
        if (!stack.empty()) set_exception_field(g->pending.get(), "__context__", stack.back());
    }
    bool returned = false;
    Ref value;
    try {
        value = resume(g, returned);
    } catch (const PyError& e) {
        if (isinstance(e.exc.get(), exception_class("GeneratorExit"))) return none_ref();
        rethrow(e);
    }
    if (returned) return value;
    raise_new("RuntimeError", "generator ignored GeneratorExit");
}
// _PyGen_FetchStopIterationValue: the value the exception's struct holds, not an attribute named `value`, which a class
// deriving from StopIteration may define as it likes (review A35, RL-779)
static Ref stop_iteration_value(Obj exc) {
    Obj v = exception_field(exc, "value");
    return v.is_unset() ? none_ref() : Ref::share(v);
}
void gen_raise_pending(Generator* g) {
    if (g->pending.get().is_unset()) return;
    Ref exc = std::move(g->pending);
    g->pending = Ref{};
    if (!g->delegate.get().is_unset()) {          // CLEANUP_THROW: its StopIteration is the delegation's end
        g->delegate = Ref{};
        if (isinstance(exc.get(), exception_class("StopIteration"))) {
            g->sent = stop_iteration_value(exc.get());
            g->delegate_ended = true;
            return;
        }
    }
    g->thrown_unstarted = g->state_before_resume == GenState::Created;   // no try of the frame's covers its first instruction
    if (g->handling != 0) raise(exc.get());       // _PyErr_ChainStackItem: this frame's own exception only
    throw PyError(std::move(exc));
}
void gen_delegate_to(Generator* g, Obj iterable) {   // GET_YIELD_FROM_ITER
    g->delegate = iter(iterable);
    // _PyEval_GetIter: exact list, tuple, str and bytes stay on the stack with an index, with no iterator to show
    bool virtual_iterator = is_exact_list(iterable) || is_exact_tuple(iterable) || is_kind(iterable, Kind::Str) || is_kind(iterable, Kind::Bytes);
    g->delegate_shown = virtual_iterator ? Ref::share(iterable) : Ref{};
    g->sent = none_ref();
}
// SEND: one step of `yield from`. Unset back: the delegation ended, and g->sent is its value
Ref gen_delegate_step(Generator* g) {
    if (g->delegate_ended) {
        g->delegate_ended = false;
        return Ref{};
    }
    Ref sent = std::move(g->sent);
    g->sent = Ref{};
    Ref yf = g->delegate;
    Ref value;
    if (is_kind(yf.get(), Kind::Generator)) {     // PyIter_Send: gen_am_send
        bool returned = false;
        value = send_ex(gen_self(yf.get()), sent.get(), returned);
        if (returned) {
            g->sent = std::move(value);
            g->delegate = Ref{};
            return Ref{};
        }
        return value;
    }
    if (is_kind(yf.get(), Kind::Iterator) && sent.get() == None()) {   // tp_iternext, which says no value
        value = for_next(yf.get());
        if (!is_end(value)) return value;
        g->sent = none_ref();
        g->delegate = Ref{};
        return Ref{};
    }
    try {
        if (sent.get() == None() && !type_lookup(type_of(yf.get()), N("__next__")).is_unset()) value = call_special(yf.get(), "__next__", {});
        else value = invoke(getattr(g->delegate_shown.get().is_unset() ? yf.get() : g->delegate_shown.get(), N("send")).get(), {sent.get()});
    } catch (const PyError& e) {                  // _PyGen_FetchStopIterationValue
        if (!isinstance(e.exc.get(), exception_class("StopIteration"))) {
            g->delegate = Ref{};
            rethrow(e);
        }
        g->sent = stop_iteration_value(e.exc.get());
        g->delegate = Ref{};
        return Ref{};
    }
    return value;
}
[[noreturn]] void gen_uncaught(Generator* g, PyError& e) {   // INTRINSIC_STOPITERATION_ERROR: PEP 479
    if (g->thrown_unstarted || !isinstance(e.exc.get(), exception_class("StopIteration"))) throw;
    Ref message = str_new("generator raised StopIteration");
    Ref error = invoke(Obj::of(exception_class("RuntimeError")), {message.get()});
    setattr(error.get(), N("__cause__"), e.exc.get());
    setattr(error.get(), N("__context__"), e.exc.get());
    // RERAISE, which does not pass the `error:` label: the generator's frame adds no entry to the error made here, so its
    // traceback starts at the caller, and the StopIteration behind it has the generator's (RL-452). The frame recorded `e`
    // when it arrived, and the new error is marked as that frame's own
    throw PyError(std::move(error), e.recorded);
}
void gen_caught(Generator* g, int k, const PyError& e) { g->errors[static_cast<std::size_t>(k)] = std::make_unique<PyError>(e); }
void gen_handling_push(Generator* g, int k) {     // the except clause's PUSH_EXC_INFO
    Obj exc = g->errors[static_cast<std::size_t>(k)]->exc.get();
    incref(exc);
    handled_exceptions().push_back(exc);
    ++g->handling;
}
void gen_handling_pop(Generator* g, int k) {      // POP_EXCEPT
    Obj exc = handled_exceptions().back();
    handled_exceptions().pop_back();
    --g->handling;
    decref(exc);
    g->errors[static_cast<std::size_t>(k)].reset();
}
[[noreturn]] void gen_rethrow(Generator* g, int k) {
    std::unique_ptr<PyError> taken = std::move(g->errors[static_cast<std::size_t>(k)]);
    throw PyError(taken->exc, taken->recorded);
}
// _PyGen_Finalize for the collection's pass (finalize_garbage): the flag first, then the close of one that has not ended,
// what it raises reported; the collection holds the generator meanwhile
void gen_finalize(Object* o) {
    auto* g = static_cast<Generator*>(o);
    o->flags |= FINALIZED;
    if (g->state == GenState::Finished) return;
    Obj saved = detail::raising();
    const void* owner = detail::raising_owner();
    try {
        Ref ignored = gen_close(g);
    } catch (const PyError& e) {
        Ref self = Ref::share(Obj::of(o));
        report_unraisable("Exception ignored while closing generator ", self.get(), e);
    }
    detail::raising() = saved;
    detail::raising_owner() = owner;
}
const bool gen_finalizer_registered = (detail::finalizer(Kind::Generator) = gen_finalize, true);
void gen_die(Object* o) {                         // gen_dealloc: finalised once; a close may resurrect it
    auto* g = static_cast<Generator*>(o);
    if (g->state != GenState::Finished && (o->flags & FINALIZED) == 0) {
        o->flags &= ~DEAD;
        o->flags |= FINALIZED;
        o->refs = 1;
        Obj saved = detail::raising();
        const void* owner = detail::raising_owner();
        try {
            Ref ignored = gen_close(g);
        } catch (const PyError& e) {
            Ref self = Ref::share(Obj::of(o));
            report_unraisable("Exception ignored while closing generator ", self.get(), e);
        }
        detail::raising() = saved;
        detail::raising_owner() = owner;
        if (--o->refs != 0) {                    // revived by its close: the release left it above nought (a candidate)
            detail::released_above_nought(o);
            return;
        }
        o->flags |= DEAD;
    }
    if (g->state != GenState::Finished) clear_frame(g);
    g->name = Ref{};
    g->qualname = Ref{};
    detail::free_object(g);
}
void init_generator() {
    ClassObject* c = types().generator;
    method(c, "__iter__", iter_slot);
    method(c, "__next__", next_slot);
    method(c, "send", send_m);
    method(c, "throw", throw_m);
    method(c, "close", close_m);
    method(c, "__del__", del_m);
    method(c, "__repr__", repr_slot);
    for (auto [name, get, set] : std::initializer_list<std::tuple<const char*, Ref (*)(Obj), void (*)(Obj, Obj)>>{
             {"__name__", get_name, set_name}, {"__qualname__", get_qualname, set_qualname}}) {
        auto* d = new GetSet(name, c, get, set);
        d->deletable = true;
        c->attrs.set(N(name), Obj::of(d));
    }
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{
             {"gi_running", get_running}, {"gi_suspended", get_suspended}, {"gi_yieldfrom", get_yieldfrom}, {"gi_state", get_state}})
        c->attrs.set(N(name), Obj::of(new GetSet(name, c, get, nullptr)));
}
}  // namespace bella
