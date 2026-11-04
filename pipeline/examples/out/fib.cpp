// fib.py, compiled by Bella (L2 -> C++26). Generated: do not edit.
#include "bella/runtime.hpp"

namespace bella::m_main {
namespace rt = ::bella;
using rt::Obj;
using rt::Ref;

static bool constants_made = false;      // made once, by the module's first run
static const rt::Str* const S_fib = rt::intern("fib");
static const rt::Str* const S_i = rt::intern("i");
static const rt::Str* const S_int = rt::intern("int");
static const rt::Str* const S_print = rt::intern("print");
static const rt::Str* const S_range = rt::intern("range");
static Obj K_1, K_2, K_3;

static const rt::Code code_module{"<module>", "<module>", "fib.py", 1, 0, 0, 0, false, false, {}, nullptr};
static const rt::Code code_fib_annotate{"__annotate__", "fib.__annotate__", "fib.py", 4, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_fib{"fib", "fib", "fib.py", 4, 1, 0, 0, false, false, {"n"}, nullptr};

static Ref f_fib_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_fib(rt::PyFunction* fn, rt::Args args);

static void init_constants() {
    if (constants_made) return;
    constants_made = true;
    K_1 = Obj::of(rt::intern("fib(60) fits the 63-bit immediate:"));
    K_2 = Obj::of(rt::intern("n"));
    K_3 = Obj::of(rt::intern("return"));
}

// the module body of fib.py
rt::Ref module_body(rt::Module* m) {
    rt::Module* M = m;
    init_constants();
    Obj ns = Obj::of(m->dict);
    rt::FrameGuard frame(code_module, M);
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t13, t14, t15, t16, t17, t18, t19;
    frame.line = 4;
    t1 = rt::make_function(code_fib_annotate, f_fib_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t2 = rt::make_function(code_fib, f_fib, M, Obj{}, Obj{}, {}, t1.get());
    t1 = Ref{};
    rt::store_name(ns, S_fib, std::move(t2));
    frame.line = 10;
    t3 = rt::load_name(ns, M, S_range);
    t4 = rt::invoke(t3.get(), {Obj::small(0), Obj::small(25)});
    t3 = Ref{};
    t5 = rt::iter(t4.get());
    t4 = Ref{};
    for (;;) {
        frame.line = 10;
        t6 = rt::for_next(t5.get());
        if (rt::is_end(t6)) {
            t5 = Ref{};
            break;
        } else {
            rt::store_name(ns, S_i, std::move(t6));
            frame.line = 11;
            t7 = rt::load_name(ns, M, S_print);
            t8 = rt::load_name(ns, M, S_i);
            t9 = rt::load_name(ns, M, S_fib);
            t10 = rt::load_name(ns, M, S_i);
            t11 = rt::invoke(t9.get(), {t10.get()});
            t10 = Ref{};
            t9 = Ref{};
            t19 = rt::invoke(t7.get(), {t8.get(), t11.get()});
            t11 = Ref{};
            t8 = Ref{};
            t7 = Ref{};
            t19 = Ref{};
        }
    }
    frame.line = 12;
    t13 = rt::load_name(ns, M, S_print);
    t14 = rt::load_name(ns, M, S_fib);
    t15 = rt::invoke(t14.get(), {Obj::small(30)});
    t14 = Ref{};
    t16 = rt::binary(rt::BinOp::Mul, t15.get(), Obj::small(1000));
    t15 = Ref{};
    t17 = rt::compare(rt::CmpOp::Gt, Obj::small(60), Obj::small(30));
    t18 = rt::invoke(t13.get(), {K_1, t16.get(), t17.get()});
    t17 = Ref{};
    t16 = Ref{};
    t13 = Ref{};
    t18 = Ref{};
    return rt::none_ref();
}

// function fib.__annotate__  (fib.py:4)
static Ref f_fib_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format3;
    Ref _ann4;
    rt::FrameGuard frame(code_fib_annotate, M, _format3, _ann4);
    rt::StackValues stack_values(_ann4, _format3);
    rt::bind(fn, args, {&_format3});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10;
    frame.line = 4;
    t1 = rt::load_fast(_format3, "_format3");
    t2 = rt::compare(rt::CmpOp::Gt, t1.get(), Obj::small(2));
    t1 = Ref{};
    t3 = rt::truth_ref(t2.get());
    t2 = Ref{};
    if (rt::test(t3)) {
        t4 = rt::builtin("NotImplementedError");
        rt::raise_type(t4.get(), Obj{}, false);
    }
    t5 = rt::build_map({}, {});
    _ann4 = std::move(t5);
    t6 = rt::load_global(M, S_int);
    t7 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t7.get(), K_2, t6.get());
    t7 = Ref{};
    t6 = Ref{};
    t8 = rt::load_global(M, S_int);
    t9 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t9.get(), K_3, t8.get());
    t9 = Ref{};
    t8 = Ref{};
    t10 = rt::load_fast(_ann4, "_ann4");
    return std::move(t10);
}

// function fib  (fib.py:4)
static Ref f_fib(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref n;
    rt::FrameGuard frame(code_fib, M, n);
    rt::bind(fn, args, {&n});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13;
    frame.line = 5;
    t1 = rt::load_fast(n, "n");
    t2 = rt::compare(rt::CmpOp::Lt, t1.get(), Obj::small(2));
    t1 = Ref{};
    t3 = rt::truth_ref(t2.get());
    t2 = Ref{};
    if (rt::test(t3)) {
        frame.line = 6;
        t4 = rt::load_fast(n, "n");
        return std::move(t4);
    }
    frame.line = 7;
    t5 = rt::load_global(M, S_fib);
    t6 = rt::load_fast(n, "n");
    t7 = rt::binary(rt::BinOp::Sub, t6.get(), Obj::small(1));
    t6 = Ref{};
    t8 = rt::invoke(t5.get(), {t7.get()});
    t7 = Ref{};
    t5 = Ref{};
    t9 = rt::load_global(M, S_fib);
    t10 = rt::load_fast(n, "n");
    t11 = rt::binary(rt::BinOp::Sub, t10.get(), Obj::small(2));
    t10 = Ref{};
    t12 = rt::invoke(t9.get(), {t11.get()});
    t11 = Ref{};
    t9 = Ref{};
    t13 = rt::binary(rt::BinOp::Add, t8.get(), t12.get());
    t12 = Ref{};
    t8 = Ref{};
    return std::move(t13);
}

}  // namespace bella::m_main
