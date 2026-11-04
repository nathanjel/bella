// collatz.py, compiled by Bella (L2 -> C++26). Generated: do not edit.
#include "bella/runtime.hpp"

namespace bella::m_main {
namespace rt = ::bella;
using rt::Obj;
using rt::Ref;

static bool constants_made = false;      // made once, by the module's first run
static const rt::Str* const S_arg = rt::intern("arg");
static const rt::Str* const S_int = rt::intern("int");
static const rt::Str* const S_longest = rt::intern("longest");
static const rt::Str* const S_print = rt::intern("print");
static const rt::Str* const S_range = rt::intern("range");
static const rt::Str* const S_s = rt::intern("s");
static const rt::Str* const S_start = rt::intern("start");
static const rt::Str* const S_steps = rt::intern("steps");
static Obj K_1, K_2, K_3, K_4;

static const rt::Code code_module{"<module>", "<module>", "collatz.py", 1, 0, 0, 0, false, false, {}, nullptr};
static const rt::Code code_steps_annotate{"__annotate__", "steps.__annotate__", "collatz.py", 4, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_steps{"steps", "steps", "collatz.py", 4, 1, 0, 0, false, false, {"n"}, nullptr};

static Ref f_steps_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_steps(rt::PyFunction* fn, rt::Args args);

static void init_constants() {
    if (constants_made) return;
    constants_made = true;
    K_1 = Obj::of(rt::intern("longest collatz chain below 300:"));
    K_2 = Obj::of(rt::intern("evaluation order:"));
    K_3 = Obj::of(rt::intern("n"));
    K_4 = Obj::of(rt::intern("return"));
}

// the module body of collatz.py
rt::Ref module_body(rt::Module* m) {
    rt::Module* M = m;
    init_constants();
    Obj ns = Obj::of(m->dict);
    rt::FrameGuard frame(code_module, M);
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t20, t21, t22, t23, t24, t25, t26, t27, t28, t29, t30, t31, t32;
    frame.line = 4;
    t1 = rt::make_function(code_steps_annotate, f_steps_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t2 = rt::make_function(code_steps, f_steps, M, Obj{}, Obj{}, {}, t1.get());
    t1 = Ref{};
    rt::store_name(ns, S_steps, std::move(t2));
    frame.line = 15;
    rt::store_name(ns, S_longest, Ref::share(Obj::small(0)));
    frame.line = 16;
    rt::store_name(ns, S_arg, Ref::share(Obj::small(0)));
    frame.line = 17;
    t3 = rt::load_name(ns, M, S_range);
    t4 = rt::invoke(t3.get(), {Obj::small(1), Obj::small(300)});
    t3 = Ref{};
    t5 = rt::iter(t4.get());
    t4 = Ref{};
    for (;;) {
        frame.line = 17;
        t6 = rt::for_next(t5.get());
        if (rt::is_end(t6)) {
            t5 = Ref{};
            break;
        } else {
            rt::store_name(ns, S_start, std::move(t6));
            frame.line = 18;
            t7 = rt::load_name(ns, M, S_steps);
            t8 = rt::load_name(ns, M, S_start);
            t9 = rt::invoke(t7.get(), {t8.get()});
            t8 = Ref{};
            t7 = Ref{};
            rt::store_name(ns, S_s, std::move(t9));
            frame.line = 19;
            t10 = rt::load_name(ns, M, S_s);
            t11 = rt::load_name(ns, M, S_longest);
            t12 = rt::compare(rt::CmpOp::Gt, t10.get(), t11.get());
            t11 = Ref{};
            t10 = Ref{};
            t13 = rt::truth_ref(t12.get());
            t12 = Ref{};
            if (rt::test(t13)) {
                frame.line = 20;
                t14 = rt::load_name(ns, M, S_s);
                rt::store_name(ns, S_longest, std::move(t14));
                frame.line = 21;
                t15 = rt::load_name(ns, M, S_start);
                rt::store_name(ns, S_arg, std::move(t15));
            }
        }
    }
    frame.line = 22;
    t16 = rt::load_name(ns, M, S_print);
    t17 = rt::load_name(ns, M, S_arg);
    t18 = rt::load_name(ns, M, S_longest);
    t32 = rt::invoke(t16.get(), {K_1, t17.get(), t18.get()});
    t18 = Ref{};
    t17 = Ref{};
    t16 = Ref{};
    t32 = Ref{};
    frame.line = 23;
    t20 = rt::load_name(ns, M, S_print);
    t21 = rt::load_name(ns, M, S_steps);
    t22 = rt::invoke(t21.get(), {Obj::small(27)});
    t21 = Ref{};
    t23 = rt::load_name(ns, M, S_steps);
    t24 = rt::invoke(t23.get(), {Obj::small(9)});
    t23 = Ref{};
    t25 = rt::binary(rt::BinOp::Sub, t22.get(), t24.get());
    t24 = Ref{};
    t22 = Ref{};
    t26 = rt::load_name(ns, M, S_steps);
    t27 = rt::invoke(t26.get(), {Obj::small(97)});
    t26 = Ref{};
    t28 = rt::load_name(ns, M, S_steps);
    t29 = rt::invoke(t28.get(), {Obj::small(871)});
    t28 = Ref{};
    t30 = rt::binary(rt::BinOp::Add, t27.get(), t29.get());
    t29 = Ref{};
    t27 = Ref{};
    t31 = rt::invoke(t20.get(), {K_2, t25.get(), t30.get()});
    t30 = Ref{};
    t25 = Ref{};
    t20 = Ref{};
    t31 = Ref{};
    return rt::none_ref();
}

// function steps.__annotate__  (collatz.py:4)
static Ref f_steps_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format3;
    Ref _ann4;
    rt::FrameGuard frame(code_steps_annotate, M, _format3, _ann4);
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
    rt::setitem(t7.get(), K_3, t6.get());
    t7 = Ref{};
    t6 = Ref{};
    t8 = rt::load_global(M, S_int);
    t9 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t9.get(), K_4, t8.get());
    t9 = Ref{};
    t8 = Ref{};
    t10 = rt::load_fast(_ann4, "_ann4");
    return std::move(t10);
}

// function steps  (collatz.py:4)
static Ref f_steps(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref n;
    Ref count;
    rt::FrameGuard frame(code_steps, M, n, count);
    rt::bind(fn, args, {&n});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15;
    frame.line = 5;
    count = Ref::share(Obj::small(0));
    frame.line = 6;
    for (;;) {
        frame.line = 6;
        t1 = rt::load_fast(n, "n");
        t2 = rt::compare(rt::CmpOp::Ne, t1.get(), Obj::small(1));
        t1 = Ref{};
        t3 = rt::truth_ref(t2.get());
        t2 = Ref{};
        if (rt::test(t3)) {
            frame.line = 7;
            t4 = rt::load_fast(n, "n");
            t5 = rt::binary(rt::BinOp::Mod, t4.get(), Obj::small(2));
            t4 = Ref{};
            t6 = rt::compare(rt::CmpOp::Eq, t5.get(), Obj::small(0));
            t5 = Ref{};
            t7 = rt::truth_ref(t6.get());
            t6 = Ref{};
            if (rt::test(t7)) {
                frame.line = 8;
                t8 = rt::load_fast(n, "n");
                t9 = rt::inplace(rt::BinOp::FloorDiv, t8.get(), Obj::small(2));
                t8 = Ref{};
                n = std::move(t9);
            } else {
                frame.line = 10;
                t10 = rt::load_fast(n, "n");
                t11 = rt::binary(rt::BinOp::Mul, Obj::small(3), t10.get());
                t10 = Ref{};
                t12 = rt::binary(rt::BinOp::Add, t11.get(), Obj::small(1));
                t11 = Ref{};
                n = std::move(t12);
            }
            frame.line = 11;
            t13 = rt::load_fast(count, "count");
            t14 = rt::inplace(rt::BinOp::Add, t13.get(), Obj::small(1));
            t13 = Ref{};
            count = std::move(t14);
        } else {
            break;
        }
    }
    frame.line = 12;
    t15 = rt::load_fast(count, "count");
    return std::move(t15);
}

}  // namespace bella::m_main
