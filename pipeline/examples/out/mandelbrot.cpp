// mandelbrot.py, compiled by Bella (L2 -> C++26). Generated: do not edit.
#include "bella/runtime.hpp"

namespace bella::m_main {
namespace rt = ::bella;
using rt::Obj;
using rt::Ref;

static bool constants_made = false;      // made once, by the module's first run
static const rt::Str* const S_ci = rt::intern("ci");
static const rt::Str* const S_cr = rt::intern("cr");
static const rt::Str* const S_escape_time = rt::intern("escape_time");
static const rt::Str* const S_height = rt::intern("height");
static const rt::Str* const S_inside = rt::intern("inside");
static const rt::Str* const S_int = rt::intern("int");
static const rt::Str* const S_limit = rt::intern("limit");
static const rt::Str* const S_n = rt::intern("n");
static const rt::Str* const S_print = rt::intern("print");
static const rt::Str* const S_range = rt::intern("range");
static const rt::Str* const S_row = rt::intern("row");
static const rt::Str* const S_total = rt::intern("total");
static const rt::Str* const S_width = rt::intern("width");
static const rt::Str* const S_x = rt::intern("x");
static const rt::Str* const S_y = rt::intern("y");
static Obj K_1, K_2, K_3, K_4, K_5, K_6;

static const rt::Code code_module{"<module>", "<module>", "mandelbrot.py", 1, 0, 0, 0, false, false, {}, nullptr};
static const rt::Code code_escape_time_annotate{"__annotate__", "escape_time.__annotate__", "mandelbrot.py", 7, 1, 1, 0, false, false, {"format"}, nullptr};
static const rt::Code code_escape_time{"escape_time", "escape_time", "mandelbrot.py", 7, 3, 0, 0, false, false, {"cr", "ci", "limit"}, nullptr};

static Ref f_escape_time_annotate(rt::PyFunction* fn, rt::Args args);
static Ref f_escape_time(rt::PyFunction* fn, rt::Args args);

static void init_constants() {
    if (constants_made) return;
    constants_made = true;
    K_1 = Obj::of(rt::intern("points inside:"));
    K_2 = Obj::of(rt::intern("total escape time:"));
    K_3 = Obj::of(rt::intern("cr"));
    K_4 = Obj::of(rt::intern("ci"));
    K_5 = Obj::of(rt::intern("limit"));
    K_6 = Obj::of(rt::intern("return"));
}

// the module body of mandelbrot.py
rt::Ref module_body(rt::Module* m) {
    rt::Module* M = m;
    init_constants();
    Obj ns = Obj::of(m->dict);
    rt::FrameGuard frame(code_module, M);
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25, t26, t27, t28, t29, t30, t31, t32, t33, t34, t35, t36, t37, t38, t39, t40, t41, t42, t43, t44, t46, t47, t48, t49, t50;
    frame.line = 7;
    t1 = rt::make_function(code_escape_time_annotate, f_escape_time_annotate, M, Obj{}, Obj{}, {}, Obj{});
    t2 = rt::make_function(code_escape_time, f_escape_time, M, Obj{}, Obj{}, {}, t1.get());
    t1 = Ref{};
    rt::store_name(ns, S_escape_time, std::move(t2));
    frame.line = 22;
    rt::store_name(ns, S_width, Ref::share(Obj::small(64)));
    frame.line = 23;
    rt::store_name(ns, S_height, Ref::share(Obj::small(24)));
    frame.line = 24;
    rt::store_name(ns, S_limit, Ref::share(Obj::small(100)));
    frame.line = 25;
    rt::store_name(ns, S_total, Ref::share(Obj::small(0)));
    frame.line = 26;
    rt::store_name(ns, S_inside, Ref::share(Obj::small(0)));
    frame.line = 27;
    t3 = rt::load_name(ns, M, S_range);
    t4 = rt::load_name(ns, M, S_height);
    t5 = rt::invoke(t3.get(), {t4.get()});
    t4 = Ref{};
    t3 = Ref{};
    t6 = rt::iter(t5.get());
    t5 = Ref{};
    for (;;) {
        t7 = rt::for_next(t6.get());
        if (rt::is_end(t7)) {
            t6 = Ref{};
            break;
        } else {
            rt::store_name(ns, S_y, std::move(t7));
            frame.line = 28;
            t8 = rt::load_name(ns, M, S_y);
            t9 = rt::binary(rt::BinOp::Mul, t8.get(), Obj::small(8192));
            t8 = Ref{};
            t10 = rt::load_name(ns, M, S_height);
            t11 = rt::binary(rt::BinOp::Sub, t10.get(), Obj::small(1));
            t10 = Ref{};
            t12 = rt::binary(rt::BinOp::FloorDiv, t9.get(), t11.get());
            t11 = Ref{};
            t9 = Ref{};
            t13 = rt::binary(rt::BinOp::Sub, t12.get(), Obj::small(4096));
            t12 = Ref{};
            rt::store_name(ns, S_ci, std::move(t13));
            frame.line = 29;
            rt::store_name(ns, S_row, Ref::share(Obj::small(0)));
            frame.line = 30;
            t14 = rt::load_name(ns, M, S_range);
            t15 = rt::load_name(ns, M, S_width);
            t16 = rt::invoke(t14.get(), {t15.get()});
            t15 = Ref{};
            t14 = Ref{};
            t17 = rt::iter(t16.get());
            t16 = Ref{};
            for (;;) {
                t18 = rt::for_next(t17.get());
                if (rt::is_end(t18)) {
                    t17 = Ref{};
                    break;
                } else {
                    rt::store_name(ns, S_x, std::move(t18));
                    frame.line = 31;
                    t19 = rt::load_name(ns, M, S_x);
                    t20 = rt::binary(rt::BinOp::Mul, t19.get(), Obj::small(12288));
                    t19 = Ref{};
                    t21 = rt::load_name(ns, M, S_width);
                    t22 = rt::binary(rt::BinOp::Sub, t21.get(), Obj::small(1));
                    t21 = Ref{};
                    t23 = rt::binary(rt::BinOp::FloorDiv, t20.get(), t22.get());
                    t22 = Ref{};
                    t20 = Ref{};
                    t24 = rt::binary(rt::BinOp::Sub, t23.get(), Obj::small(8192));
                    t23 = Ref{};
                    rt::store_name(ns, S_cr, std::move(t24));
                    frame.line = 32;
                    t25 = rt::load_name(ns, M, S_escape_time);
                    t26 = rt::load_name(ns, M, S_cr);
                    t27 = rt::load_name(ns, M, S_ci);
                    t28 = rt::load_name(ns, M, S_limit);
                    t29 = rt::invoke(t25.get(), {t26.get(), t27.get(), t28.get()});
                    t28 = Ref{};
                    t27 = Ref{};
                    t26 = Ref{};
                    t25 = Ref{};
                    rt::store_name(ns, S_n, std::move(t29));
                    frame.line = 33;
                    t30 = rt::load_name(ns, M, S_total);
                    t31 = rt::load_name(ns, M, S_n);
                    t32 = rt::inplace(rt::BinOp::Add, t30.get(), t31.get());
                    t31 = Ref{};
                    t30 = Ref{};
                    rt::store_name(ns, S_total, std::move(t32));
                    frame.line = 34;
                    t33 = rt::load_name(ns, M, S_n);
                    t34 = rt::load_name(ns, M, S_limit);
                    t35 = rt::compare(rt::CmpOp::Eq, t33.get(), t34.get());
                    t34 = Ref{};
                    t33 = Ref{};
                    t36 = rt::truth_ref(t35.get());
                    t35 = Ref{};
                    if (rt::test(t36)) {
                        frame.line = 35;
                        t37 = rt::load_name(ns, M, S_row);
                        t38 = rt::inplace(rt::BinOp::Add, t37.get(), Obj::small(1));
                        t37 = Ref{};
                        rt::store_name(ns, S_row, std::move(t38));
                    }
                }
            }
            frame.line = 36;
            t39 = rt::load_name(ns, M, S_inside);
            t40 = rt::load_name(ns, M, S_row);
            t41 = rt::inplace(rt::BinOp::Add, t39.get(), t40.get());
            t40 = Ref{};
            t39 = Ref{};
            rt::store_name(ns, S_inside, std::move(t41));
            frame.line = 37;
            t42 = rt::load_name(ns, M, S_print);
            t43 = rt::load_name(ns, M, S_y);
            t44 = rt::load_name(ns, M, S_row);
            t50 = rt::invoke(t42.get(), {t43.get(), t44.get()});
            t44 = Ref{};
            t43 = Ref{};
            t42 = Ref{};
            t50 = Ref{};
        }
    }
    frame.line = 38;
    t46 = rt::load_name(ns, M, S_print);
    t47 = rt::load_name(ns, M, S_inside);
    t48 = rt::load_name(ns, M, S_total);
    t49 = rt::invoke(t46.get(), {K_1, t47.get(), K_2, t48.get()});
    t48 = Ref{};
    t47 = Ref{};
    t46 = Ref{};
    t49 = Ref{};
    return rt::none_ref();
}

// function escape_time.__annotate__  (mandelbrot.py:7)
static Ref f_escape_time_annotate(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref _format3;
    Ref _ann4;
    rt::FrameGuard frame(code_escape_time_annotate, M, _format3, _ann4);
    rt::StackValues stack_values(_ann4, _format3);
    rt::bind(fn, args, {&_format3});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14;
    frame.line = 7;
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
    t10 = rt::load_global(M, S_int);
    t11 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t11.get(), K_5, t10.get());
    t11 = Ref{};
    t10 = Ref{};
    t12 = rt::load_global(M, S_int);
    t13 = rt::load_fast(_ann4, "_ann4");
    rt::setitem(t13.get(), K_6, t12.get());
    t13 = Ref{};
    t12 = Ref{};
    t14 = rt::load_fast(_ann4, "_ann4");
    return std::move(t14);
}

// function escape_time  (mandelbrot.py:7)
static Ref f_escape_time(rt::PyFunction* fn, rt::Args args) {
    [[maybe_unused]] rt::Module* M = fn->module;
    Ref cr;
    Ref ci;
    Ref limit;
    Ref zr;
    Ref zi;
    Ref n;
    Ref zr2;
    Ref zi2;
    rt::FrameGuard frame(code_escape_time, M, cr, ci, limit, zr, zi, n, zr2, zi2);
    rt::bind(fn, args, {&cr, &ci, &limit});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25, t26, t27, t28, t29, t30, t31, t32, t33;
    frame.line = 8;
    zr = Ref::share(Obj::small(0));
    frame.line = 9;
    zi = Ref::share(Obj::small(0));
    frame.line = 10;
    n = Ref::share(Obj::small(0));
    frame.line = 11;
    for (;;) {
        t1 = rt::load_fast(n, "n");
        t2 = rt::load_fast(limit, "limit");
        t3 = rt::compare(rt::CmpOp::Lt, t1.get(), t2.get());
        t2 = Ref{};
        t1 = Ref{};
        t4 = rt::truth_ref(t3.get());
        t3 = Ref{};
        if (rt::test(t4)) {
            frame.line = 12;
            t5 = rt::load_fast(zr, "zr");
            t6 = rt::load_fast(zr, "zr");
            t7 = rt::binary(rt::BinOp::Mul, t5.get(), t6.get());
            t6 = Ref{};
            t5 = Ref{};
            t8 = rt::binary(rt::BinOp::FloorDiv, t7.get(), Obj::small(4096));
            t7 = Ref{};
            zr2 = std::move(t8);
            frame.line = 13;
            t9 = rt::load_fast(zi, "zi");
            t10 = rt::load_fast(zi, "zi");
            t11 = rt::binary(rt::BinOp::Mul, t9.get(), t10.get());
            t10 = Ref{};
            t9 = Ref{};
            t12 = rt::binary(rt::BinOp::FloorDiv, t11.get(), Obj::small(4096));
            t11 = Ref{};
            zi2 = std::move(t12);
            frame.line = 14;
            t13 = rt::load_fast(zr2, "zr2");
            t14 = rt::load_fast(zi2, "zi2");
            t15 = rt::binary(rt::BinOp::Add, t13.get(), t14.get());
            t14 = Ref{};
            t13 = Ref{};
            t16 = rt::compare(rt::CmpOp::Gt, t15.get(), Obj::small(16384));
            t15 = Ref{};
            t17 = rt::truth_ref(t16.get());
            t16 = Ref{};
            if (rt::test(t17)) {
                frame.line = 15;
                t18 = rt::load_fast(n, "n");
                return std::move(t18);
            }
            frame.line = 16;
            t19 = rt::load_fast(zr, "zr");
            t20 = rt::binary(rt::BinOp::Mul, Obj::small(2), t19.get());
            t19 = Ref{};
            t21 = rt::load_fast(zi, "zi");
            t22 = rt::binary(rt::BinOp::Mul, t20.get(), t21.get());
            t21 = Ref{};
            t20 = Ref{};
            t23 = rt::binary(rt::BinOp::FloorDiv, t22.get(), Obj::small(4096));
            t22 = Ref{};
            t24 = rt::load_fast(ci, "ci");
            t25 = rt::binary(rt::BinOp::Add, t23.get(), t24.get());
            t24 = Ref{};
            t23 = Ref{};
            zi = std::move(t25);
            frame.line = 17;
            t26 = rt::load_fast(zr2, "zr2");
            t27 = rt::load_fast(zi2, "zi2");
            t28 = rt::binary(rt::BinOp::Sub, t26.get(), t27.get());
            t27 = Ref{};
            t26 = Ref{};
            t29 = rt::load_fast(cr, "cr");
            t30 = rt::binary(rt::BinOp::Add, t28.get(), t29.get());
            t29 = Ref{};
            t28 = Ref{};
            zr = std::move(t30);
            frame.line = 18;
            t31 = rt::load_fast(n, "n");
            t32 = rt::inplace(rt::BinOp::Add, t31.get(), Obj::small(1));
            t31 = Ref{};
            n = std::move(t32);
        } else {
            break;
        }
    }
    frame.line = 19;
    t33 = rt::load_fast(limit, "limit");
    return std::move(t33);
}

}  // namespace bella::m_main
