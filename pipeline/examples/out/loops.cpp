// loops.py, compiled by Bella (L2 -> C++26). Generated: do not edit.
#include "bella/runtime.hpp"

namespace bella::m_main {
namespace rt = ::bella;
using rt::Obj;
using rt::Ref;

static bool constants_made = false;      // made once, by the module's first run
static const rt::Str* const S_gcd = rt::intern("gcd");
static const rt::Str* const S_int = rt::intern("int");
static const rt::Str* const S_k = rt::intern("k");
static const rt::Str* const S_n = rt::intern("n");
static const rt::Str* const S_print = rt::intern("print");
static const rt::Str* const S_range = rt::intern("range");
static const rt::Str* const S_signs = rt::intern("signs");
static const rt::Str* const S_total = rt::intern("total");
static Obj K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9, K_10;

static const rt::Code code_module{"<module>", "<module>", "loops.py", 1, 0, 0, 0, false, false, {}, nullptr};
static const rt::Code code_gcd_annotate{"__annotate__", "gcd.__annotate__", "loops.py", 4, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_gcd{"gcd", "gcd", "loops.py", 4, 2, 0, 0, false, false, {"a", "b"}, nullptr};
static const rt::Code code_signs_annotate{"__annotate__", "signs.__annotate__", "loops.py", 12, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_signs{"signs", "signs", "loops.py", 12, 2, 0, 0, false, false, {"a", "b"}, nullptr};

static Ref f_gcd_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_gcd(rt::PyFunction* fn, rt::Args args);
static Ref f_signs_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_signs(rt::PyFunction* fn, rt::Args args);

static void init_constants() {
    if (constants_made) return;
    constants_made = true;
    K_1 = Obj::of(rt::intern("never printed: the loop broke"));
    K_2 = Obj::of(rt::intern("total"));
    K_3 = Obj::of(rt::intern("gcd"));
    K_4 = Obj::of(rt::intern("while-else runs when the loop ends normally"));
    K_5 = Obj::of(rt::intern("and/or return operands:"));
    K_6 = Obj::of(rt::intern("bool ops:"));
    K_7 = Obj::of(rt::intern("shifts and bits:"));
    K_8 = Obj::of(rt::intern("a"));
    K_9 = Obj::of(rt::intern("b"));
    K_10 = Obj::of(rt::intern("return"));
}

// the module body of loops.py
rt::Ref module_body(rt::Module* m) {
    rt::Module* M = m;
    init_constants();
    Obj ns = Obj::of(m->dict);
    rt::FrameGuard frame(code_module, M);
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t21, t22, t23, t24, t25, t26, t27, t29, t30, t31, t32, t33, t34, t35, t37, t38, t39, t40, t41, t42, t43, t44, t45, t47, t48, t49, t50, t51, t52, t53, t54, t55, t57, t58, t59, t60, t62, t63, t64, t65, t66, t67, t69, t70, t71, t72, t73, t74, t75, t76, t77, t78, t79, t80, t81, t82, t83, t84;
    frame.line = 4;
    t1 = rt::make_function(code_gcd_annotate, f_gcd_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t2 = rt::make_function(code_gcd, f_gcd, M, Obj{}, Obj{}, {}, t1.get());
    t1 = Ref{};
    rt::store_name(ns, S_gcd, std::move(t2));
    frame.line = 12;
    t3 = rt::make_function(code_signs_annotate, f_signs_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t4 = rt::make_function(code_signs, f_signs, M, Obj{}, Obj{}, {}, t3.get());
    t3 = Ref{};
    rt::store_name(ns, S_signs, std::move(t4));
    frame.line = 17;
    rt::store_name(ns, S_total, Ref::share(Obj::small(0)));
    frame.line = 18;
    t5 = rt::load_name(ns, M, S_range);
    t6 = rt::invoke(t5.get(), {Obj::small(1), Obj::small(50)});
    t5 = Ref{};
    t7 = rt::iter(t6.get());
    t6 = Ref{};
    bool ended1 = false;
    for (;;) {
        t8 = rt::for_next(t7.get());
        if (rt::is_end(t8)) {
            t7 = Ref{};
            ended1 = true;
            break;
        } else {
            rt::store_name(ns, S_n, std::move(t8));
            frame.line = 19;
            t9 = rt::load_name(ns, M, S_n);
            t10 = rt::binary(rt::BinOp::Mod, t9.get(), Obj::small(7));
            t9 = Ref{};
            t11 = rt::compare(rt::CmpOp::Eq, t10.get(), Obj::small(0));
            t10 = Ref{};
            t12 = rt::truth_ref(t11.get());
            t11 = Ref{};
            if (rt::test(t12)) {
                frame.line = 20;
                continue;
            }
            frame.line = 21;
            t13 = rt::load_name(ns, M, S_n);
            t14 = rt::compare(rt::CmpOp::Gt, t13.get(), Obj::small(40));
            t13 = Ref{};
            t15 = rt::truth_ref(t14.get());
            t14 = Ref{};
            if (rt::test(t15)) {
                frame.line = 22;
                t7 = Ref{};
                break;
            }
            frame.line = 23;
            t16 = rt::load_name(ns, M, S_total);
            t17 = rt::load_name(ns, M, S_n);
            t18 = rt::inplace(rt::BinOp::Add, t16.get(), t17.get());
            t17 = Ref{};
            t16 = Ref{};
            rt::store_name(ns, S_total, std::move(t18));
        }
    }
    if (ended1) {
        frame.line = 25;
        t19 = rt::load_name(ns, M, S_print);
        t84 = rt::invoke(t19.get(), {K_1});
        t19 = Ref{};
        t84 = Ref{};
    }
    frame.line = 26;
    t21 = rt::load_name(ns, M, S_print);
    t22 = rt::load_name(ns, M, S_total);
    t23 = rt::load_name(ns, M, S_gcd);
    t24 = rt::invoke(t23.get(), {Obj::small(1071), Obj::small(462)});
    t23 = Ref{};
    t25 = rt::load_name(ns, M, S_gcd);
    t26 = rt::unary_neg(Obj::small(48));
    t27 = rt::invoke(t25.get(), {t26.get(), Obj::small(18)});
    t26 = Ref{};
    t25 = Ref{};
    t83 = rt::invoke(t21.get(), {K_2, t22.get(), K_3, t24.get(), t27.get()});
    t27 = Ref{};
    t24 = Ref{};
    t22 = Ref{};
    t21 = Ref{};
    t83 = Ref{};
    frame.line = 28;
    rt::store_name(ns, S_k, Ref::share(Obj::small(0)));
    frame.line = 29;
    bool ended2 = false;
    for (;;) {
        t29 = rt::load_name(ns, M, S_k);
        t30 = rt::compare(rt::CmpOp::Lt, t29.get(), Obj::small(10));
        t29 = Ref{};
        t31 = rt::truth_ref(t30.get());
        t30 = Ref{};
        if (rt::test(t31)) {
            frame.line = 30;
            t32 = rt::load_name(ns, M, S_k);
            t33 = rt::inplace(rt::BinOp::Add, t32.get(), Obj::small(3));
            t32 = Ref{};
            rt::store_name(ns, S_k, std::move(t33));
        } else {
            ended2 = true;
            break;
        }
    }
    if (ended2) {
        frame.line = 32;
        t34 = rt::load_name(ns, M, S_print);
        t35 = rt::load_name(ns, M, S_k);
        t82 = rt::invoke(t34.get(), {K_4, t35.get()});
        t35 = Ref{};
        t34 = Ref{};
        t82 = Ref{};
    }
    frame.line = 34;
    t37 = rt::load_name(ns, M, S_print);
    t38 = rt::load_name(ns, M, S_signs);
    t39 = rt::invoke(t38.get(), {Obj::small(7), Obj::small(2)});
    t38 = Ref{};
    t40 = rt::load_name(ns, M, S_signs);
    t41 = rt::unary_neg(Obj::small(7));
    t42 = rt::invoke(t40.get(), {t41.get(), Obj::small(2)});
    t41 = Ref{};
    t40 = Ref{};
    t43 = rt::load_name(ns, M, S_signs);
    t44 = rt::unary_neg(Obj::small(2));
    t45 = rt::invoke(t43.get(), {Obj::small(7), t44.get()});
    t44 = Ref{};
    t43 = Ref{};
    t81 = rt::invoke(t37.get(), {t39.get(), t42.get(), t45.get()});
    t45 = Ref{};
    t42 = Ref{};
    t39 = Ref{};
    t37 = Ref{};
    t81 = Ref{};
    frame.line = 35;
    t47 = rt::load_name(ns, M, S_print);
    t49 = rt::truth_ref(Obj::small(0));
    if (rt::test(t49)) {
        t48 = Ref::share(Obj::small(0));
    } else {
        t48 = Ref::share(Obj::small(5));
    }
    t51 = rt::truth_ref(Obj::small(3));
    if (rt::test(t51)) {
        t50 = Ref::share(Obj::small(0));
    } else {
        t50 = Ref::share(Obj::small(3));
    }
    t53 = rt::truth_ref(Obj::small(2));
    if (rt::test(t53)) {
        t52 = Ref::share(Obj::small(4));
    } else {
        t52 = Ref::share(Obj::small(2));
    }
    t55 = rt::truth_ref(Obj::small(0));
    if (rt::test(t55)) {
        t54 = Ref::share(Obj::small(0));
    } else {
        t54 = Ref::share(Obj::small(0));
    }
    t80 = rt::invoke(t47.get(), {K_5, t48.get(), t50.get(), t52.get(), t54.get()});
    t54 = Ref{};
    t52 = Ref{};
    t50 = Ref{};
    t48 = Ref{};
    t47 = Ref{};
    t80 = Ref{};
    frame.line = 36;
    t57 = rt::load_name(ns, M, S_print);
    t59 = rt::compare(rt::CmpOp::Lt, Obj::small(1), Obj::small(2));
    t60 = rt::truth_ref(t59.get());
    if (rt::test(t60)) {
        t59 = Ref{};
        t58 = rt::compare(rt::CmpOp::Gt, Obj::small(3), Obj::small(2));
    } else {
        t58 = Ref::share(t59.get());
        t59 = Ref{};
    }
    t62 = rt::compare(rt::CmpOp::Lt, Obj::small(1), Obj::small(2));
    t63 = rt::truth_ref(t62.get());
    t62 = Ref{};
    t64 = Ref::steal(rt::boolean(!rt::is_true_obj(t63.get())));
    t63 = Ref{};
    t66 = rt::compare(rt::CmpOp::Gt, Obj::small(2), Obj::small(1));
    t67 = rt::truth_ref(t66.get());
    t66 = Ref{};
    if (rt::test(t67)) {
        t65 = Ref::share(Obj::small(5));
    } else {
        t65 = Ref::share(Obj::small(6));
    }
    t79 = rt::invoke(t57.get(), {K_6, t58.get(), t64.get(), t65.get()});
    t65 = Ref{};
    t64 = Ref{};
    t58 = Ref{};
    t57 = Ref{};
    t79 = Ref{};
    frame.line = 37;
    t69 = rt::load_name(ns, M, S_print);
    t70 = rt::binary(rt::BinOp::LShift, Obj::small(1), Obj::small(40));
    t71 = rt::unary_neg(Obj::small(1));
    t72 = rt::binary(rt::BinOp::RShift, t71.get(), Obj::small(3));
    t71 = Ref{};
    t73 = rt::binary(rt::BinOp::And, Obj::small(6), Obj::small(3));
    t74 = rt::binary(rt::BinOp::Or, Obj::small(6), Obj::small(3));
    t75 = rt::binary(rt::BinOp::Xor, Obj::small(6), Obj::small(3));
    t76 = rt::unary_invert(Obj::small(5));
    t77 = rt::binary(rt::BinOp::Pow, Obj::small(2), Obj::small(20));
    t78 = rt::invoke(t69.get(), {K_7, t70.get(), t72.get(), t73.get(), t74.get(), t75.get(), t76.get(), t77.get()});
    t77 = Ref{};
    t76 = Ref{};
    t75 = Ref{};
    t74 = Ref{};
    t73 = Ref{};
    t72 = Ref{};
    t70 = Ref{};
    t69 = Ref{};
    t78 = Ref{};
    return rt::none_ref();
}

// function gcd.__annotate__  (loops.py:4)
static Ref f_gcd_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format6;
    Ref _ann7;
    rt::FrameGuard frame(code_gcd_annotate, M, _format6, _ann7);
    rt::StackValues stack_values(_ann7, _format6);
    rt::bind(fn, args, {&_format6});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12;
    frame.line = 4;
    t1 = rt::load_fast(_format6, "_format6");
    t2 = rt::compare(rt::CmpOp::Gt, t1.get(), Obj::small(2));
    t1 = Ref{};
    t3 = rt::truth_ref(t2.get());
    t2 = Ref{};
    if (rt::test(t3)) {
        t4 = rt::builtin("NotImplementedError");
        rt::raise_type(t4.get(), Obj{}, false);
    }
    t5 = rt::build_map({}, {});
    _ann7 = std::move(t5);
    t6 = rt::load_global(M, S_int);
    t7 = rt::load_fast(_ann7, "_ann7");
    rt::setitem(t7.get(), K_8, t6.get());
    t7 = Ref{};
    t6 = Ref{};
    t8 = rt::load_global(M, S_int);
    t9 = rt::load_fast(_ann7, "_ann7");
    rt::setitem(t9.get(), K_9, t8.get());
    t9 = Ref{};
    t8 = Ref{};
    t10 = rt::load_global(M, S_int);
    t11 = rt::load_fast(_ann7, "_ann7");
    rt::setitem(t11.get(), K_10, t10.get());
    t11 = Ref{};
    t10 = Ref{};
    t12 = rt::load_fast(_ann7, "_ann7");
    return std::move(t12);
}

// function gcd  (loops.py:4)
static Ref f_gcd(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref a;
    Ref b;
    Ref r;
    rt::FrameGuard frame(code_gcd, M, a, b, r);
    rt::bind(fn, args, {&a, &b});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9;
    frame.line = 5;
    for (;;) {
        t1 = rt::load_fast(b, "b");
        t2 = rt::compare(rt::CmpOp::Ne, t1.get(), Obj::small(0));
        t1 = Ref{};
        t3 = rt::truth_ref(t2.get());
        t2 = Ref{};
        if (rt::test(t3)) {
            frame.line = 6;
            t4 = rt::load_fast(a, "a");
            t5 = rt::load_fast(b, "b");
            t6 = rt::binary(rt::BinOp::Mod, t4.get(), t5.get());
            t5 = Ref{};
            t4 = Ref{};
            r = std::move(t6);
            frame.line = 7;
            t7 = rt::load_fast(b, "b");
            a = std::move(t7);
            frame.line = 8;
            t8 = rt::load_fast(r, "r");
            b = std::move(t8);
        } else {
            break;
        }
    }
    frame.line = 9;
    t9 = rt::load_fast(a, "a");
    return std::move(t9);
}

// function signs.__annotate__  (loops.py:12)
static Ref f_signs_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format9;
    Ref _ann10;
    rt::FrameGuard frame(code_signs_annotate, M, _format9, _ann10);
    rt::StackValues stack_values(_ann10, _format9);
    rt::bind(fn, args, {&_format9});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12;
    frame.line = 12;
    t1 = rt::load_fast(_format9, "_format9");
    t2 = rt::compare(rt::CmpOp::Gt, t1.get(), Obj::small(2));
    t1 = Ref{};
    t3 = rt::truth_ref(t2.get());
    t2 = Ref{};
    if (rt::test(t3)) {
        t4 = rt::builtin("NotImplementedError");
        rt::raise_type(t4.get(), Obj{}, false);
    }
    t5 = rt::build_map({}, {});
    _ann10 = std::move(t5);
    t6 = rt::load_global(M, S_int);
    t7 = rt::load_fast(_ann10, "_ann10");
    rt::setitem(t7.get(), K_8, t6.get());
    t7 = Ref{};
    t6 = Ref{};
    t8 = rt::load_global(M, S_int);
    t9 = rt::load_fast(_ann10, "_ann10");
    rt::setitem(t9.get(), K_9, t8.get());
    t9 = Ref{};
    t8 = Ref{};
    t10 = rt::load_global(M, S_int);
    t11 = rt::load_fast(_ann10, "_ann10");
    rt::setitem(t11.get(), K_10, t10.get());
    t11 = Ref{};
    t10 = Ref{};
    t12 = rt::load_fast(_ann10, "_ann10");
    return std::move(t12);
}

// function signs  (loops.py:12)
static Ref f_signs(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref a;
    Ref b;
    rt::FrameGuard frame(code_signs, M, a, b);
    rt::bind(fn, args, {&a, &b});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25, t27, t28, t29, t30, t31, t32, t33, t34;
    frame.line = 13;
    t1 = rt::load_global(M, S_print);
    t2 = rt::load_fast(a, "a");
    t3 = rt::load_fast(b, "b");
    t4 = rt::load_fast(a, "a");
    t5 = rt::load_fast(b, "b");
    t6 = rt::binary(rt::BinOp::FloorDiv, t4.get(), t5.get());
    t5 = Ref{};
    t4 = Ref{};
    t7 = rt::load_fast(a, "a");
    t8 = rt::load_fast(b, "b");
    t9 = rt::binary(rt::BinOp::Mod, t7.get(), t8.get());
    t8 = Ref{};
    t7 = Ref{};
    t10 = rt::load_fast(a, "a");
    t11 = rt::unary_neg(t10.get());
    t10 = Ref{};
    t12 = rt::load_fast(b, "b");
    t13 = rt::binary(rt::BinOp::FloorDiv, t11.get(), t12.get());
    t12 = Ref{};
    t11 = Ref{};
    t14 = rt::load_fast(a, "a");
    t15 = rt::unary_neg(t14.get());
    t14 = Ref{};
    t16 = rt::load_fast(b, "b");
    t17 = rt::binary(rt::BinOp::Mod, t15.get(), t16.get());
    t16 = Ref{};
    t15 = Ref{};
    t18 = rt::load_fast(a, "a");
    t19 = rt::load_fast(b, "b");
    t20 = rt::unary_neg(t19.get());
    t19 = Ref{};
    t21 = rt::binary(rt::BinOp::FloorDiv, t18.get(), t20.get());
    t20 = Ref{};
    t18 = Ref{};
    t22 = rt::load_fast(a, "a");
    t23 = rt::load_fast(b, "b");
    t24 = rt::unary_neg(t23.get());
    t23 = Ref{};
    t25 = rt::binary(rt::BinOp::Mod, t22.get(), t24.get());
    t24 = Ref{};
    t22 = Ref{};
    t34 = rt::invoke(t1.get(), {t2.get(), t3.get(), t6.get(), t9.get(), t13.get(), t17.get(), t21.get(), t25.get()});
    t25 = Ref{};
    t21 = Ref{};
    t17 = Ref{};
    t13 = Ref{};
    t9 = Ref{};
    t6 = Ref{};
    t3 = Ref{};
    t2 = Ref{};
    t1 = Ref{};
    t34 = Ref{};
    frame.line = 14;
    t27 = rt::load_fast(a, "a");
    t28 = rt::load_fast(b, "b");
    t29 = rt::binary(rt::BinOp::FloorDiv, t27.get(), t28.get());
    t28 = Ref{};
    t27 = Ref{};
    t30 = rt::load_fast(a, "a");
    t31 = rt::load_fast(b, "b");
    t32 = rt::binary(rt::BinOp::Mod, t30.get(), t31.get());
    t31 = Ref{};
    t30 = Ref{};
    t33 = rt::binary(rt::BinOp::Add, t29.get(), t32.get());
    t32 = Ref{};
    t29 = Ref{};
    return std::move(t33);
}

}  // namespace bella::m_main
