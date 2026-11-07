// fact_big.py, compiled by Bella (L2 -> C++26). Generated: do not edit.
#include "bella/runtime.hpp"

namespace bella::m_main {
namespace rt = ::bella;
using rt::Obj;
using rt::Ref;

static bool constants_made = false;      // made once, by the module's first run
static const rt::Str* const S_factorial = rt::intern("factorial");
static const rt::Str* const S_int = rt::intern("int");
static const rt::Str* const S_print = rt::intern("print");
static const rt::Str* const S_range = rt::intern("range");
static Obj K_1, K_2;

static const rt::Code code_module{"<module>", "<module>", "fact_big.py", 1, 0, 0, 0, false, false, {}, nullptr};
static const rt::Code code_factorial_annotate{"__annotate__", "factorial.__annotate__", "fact_big.py", 4, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_factorial{"factorial", "factorial", "fact_big.py", 4, 1, 0, 0, false, false, {"n"}, nullptr};

static Ref f_factorial_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_factorial(rt::PyFunction* fn, rt::Args args);

static void init_constants() {
    if (constants_made) return;
    constants_made = true;
    K_1 = Obj::of(rt::intern("n"));
    K_2 = Obj::of(rt::intern("return"));
}

// the module body of fact_big.py
rt::Ref module_body(rt::Module* m) {
    rt::Module* M = m;
    init_constants();
    Obj ns = Obj::of(m->locals != nullptr ? m->locals : m->dict);
    rt::FrameGuard frame(code_module, M);
    Ref t1, t2, t3, t4, t5, t7, t8, t9, t11, t12, t13, t14, t15, t16, t17, t18, t19;
    frame.line = 4;
    t1 = rt::make_function(code_factorial_annotate, f_factorial_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t2 = rt::make_function(code_factorial, f_factorial, M, Obj{}, Obj{}, {}, t1.get());
    t1 = Ref{};
    rt::store_name(ns, S_factorial, std::move(t2));
    frame.line = 11;
    t3 = rt::load_name(ns, M, S_print);
    t4 = rt::load_name(ns, M, S_factorial);
    t5 = rt::invoke(t4.get(), {Obj::small(20)});
    t4 = Ref{};
    t19 = rt::invoke(t3.get(), {t5.get()});
    t5 = Ref{};
    t3 = Ref{};
    t19 = Ref{};
    frame.line = 12;
    t7 = rt::load_name(ns, M, S_print);
    t8 = rt::load_name(ns, M, S_factorial);
    t9 = rt::invoke(t8.get(), {Obj::small(25)});
    t8 = Ref{};
    t18 = rt::invoke(t7.get(), {t9.get()});
    t9 = Ref{};
    t7 = Ref{};
    t18 = Ref{};
    frame.line = 13;
    t11 = rt::load_name(ns, M, S_print);
    t12 = rt::load_name(ns, M, S_factorial);
    t13 = rt::invoke(t12.get(), {Obj::small(30)});
    t12 = Ref{};
    t14 = rt::load_name(ns, M, S_factorial);
    t15 = rt::invoke(t14.get(), {Obj::small(28)});
    t14 = Ref{};
    t16 = rt::binary(rt::BinOp::FloorDiv, t13.get(), t15.get());
    t15 = Ref{};
    t13 = Ref{};
    t17 = rt::invoke(t11.get(), {t16.get()});
    t16 = Ref{};
    t11 = Ref{};
    t17 = Ref{};
    return rt::none_ref();
}

// function factorial.__annotate__  (fact_big.py:4)
static Ref f_factorial_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format3;
    Ref _ann4;
    rt::FrameGuard frame(code_factorial_annotate, M, _format3, _ann4);
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
    rt::setitem(t7.get(), K_1, t6.get());
    t7 = Ref{};
    t6 = Ref{};
    t8 = rt::load_global(M, S_int);
    t9 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t9.get(), K_2, t8.get());
    t9 = Ref{};
    t8 = Ref{};
    t10 = rt::load_fast(_ann4, "_ann4");
    return std::move(t10);
}

// function factorial  (fact_big.py:4)
static Ref f_factorial(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref n;
    Ref result;
    Ref i;
    rt::FrameGuard frame(code_factorial, M, n, result, i);
    rt::bind(fn, args, {&n});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10;
    frame.line = 5;
    result = Ref::share(Obj::small(1));
    frame.line = 6;
    t1 = rt::load_global(M, S_range);
    t2 = rt::load_fast(n, "n");
    t3 = rt::binary(rt::BinOp::Add, t2.get(), Obj::small(1));
    t2 = Ref{};
    t4 = rt::invoke(t1.get(), {Obj::small(2), t3.get()});
    t3 = Ref{};
    t1 = Ref{};
    t5 = rt::iter(t4.get());
    t4 = Ref{};
    for (;;) {
        frame.line = 6;
        t6 = rt::for_next(t5.get());
        if (rt::is_end(t6)) {
            t5 = Ref{};
            break;
        } else {
            i = std::move(t6);
            frame.line = 7;
            t7 = rt::load_fast(result, "result");
            t8 = rt::load_fast(i, "i");
            t9 = rt::inplace(rt::BinOp::Mul, t7.get(), t8.get());
            t8 = Ref{};
            t7 = Ref{};
            result = std::move(t9);
        }
    }
    frame.line = 8;
    t10 = rt::load_fast(result, "result");
    return std::move(t10);
}

}  // namespace bella::m_main
