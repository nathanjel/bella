// The C library's floating-point functions for the math prelude (runtime/prelude/math.py): one call, with errno as the C
// left it, so the prelude applies Modules/mathmodule.c's rules (math_1, math_1a, math_2, is_error) in Python.
#include "bella/runtime.hpp"

#include <cerrno>
#include <cmath>
#include <string_view>

namespace bella {
namespace {
using Unary = double (*)(double);
using Binary = double (*)(double, double);

Unary unary_of(std::string_view name) {
    if (name == "acos") return [](double x) { return std::acos(x); };
    if (name == "acosh") return [](double x) { return std::acosh(x); };
    if (name == "asin") return [](double x) { return std::asin(x); };
    if (name == "asinh") return [](double x) { return std::asinh(x); };
    if (name == "atan") return [](double x) { return std::atan(x); };
    if (name == "atanh") return [](double x) { return std::atanh(x); };
    if (name == "cbrt") return [](double x) { return std::cbrt(x); };
    if (name == "cos") return [](double x) { return std::cos(x); };
    if (name == "cosh") return [](double x) { return std::cosh(x); };
    if (name == "erf") return [](double x) { return std::erf(x); };
    if (name == "erfc") return [](double x) { return std::erfc(x); };
    if (name == "exp") return [](double x) { return std::exp(x); };
    if (name == "exp2") return [](double x) { return std::exp2(x); };
    if (name == "expm1") return [](double x) { return std::expm1(x); };
    if (name == "fabs") return [](double x) { return std::fabs(x); };
    if (name == "log") return [](double x) { return std::log(x); };
    if (name == "log2") return [](double x) { return std::log2(x); };
    if (name == "log10") return [](double x) { return std::log10(x); };
    if (name == "log1p") return [](double x) { return std::log1p(x); };
    if (name == "sin") return [](double x) { return std::sin(x); };
    if (name == "sinh") return [](double x) { return std::sinh(x); };
    if (name == "sqrt") return [](double x) { return std::sqrt(x); };
    if (name == "tan") return [](double x) { return std::tan(x); };
    if (name == "tanh") return [](double x) { return std::tanh(x); };
    if (name == "floor") return [](double x) { return std::floor(x); };
    if (name == "ceil") return [](double x) { return std::ceil(x); };
    if (name == "round") return [](double x) { return std::round(x); };
    return nullptr;
}

Binary binary_of(std::string_view name) {
    if (name == "atan2") return [](double y, double x) { return std::atan2(y, x); };
    if (name == "fmod") return [](double x, double y) { return std::fmod(x, y); };
    if (name == "pow") return [](double x, double y) { return std::pow(x, y); };
    if (name == "copysign") return [](double x, double y) { return std::copysign(x, y); };
    if (name == "nextafter") return [](double x, double y) { return std::nextafter(x, y); };
    // fmax and fmin as GCC expands the C's: a NaN yields the other, else the first argument where they compare equal (so
    // fmax(-0.0, 0.0) is -0.0, as CPython's build has it); the library call itself answers the second
    if (name == "fmax") return [](double x, double y) { return std::isnan(x) ? y : std::isnan(y) ? x : (x >= y ? x : y); };
    if (name == "fmin") return [](double x, double y) { return std::isnan(x) ? y : std::isnan(y) ? x : (x <= y ? x : y); };
    return nullptr;
}

Ref pair(double r, int err) {
    Ref value = float_ref(r), code = int_from_i64(err);
    return tuple_new({value.get(), code.get()});
}
}  // namespace

// _libm(name, *floats) -> (result, errno): the library's function by name; ldexp takes (x, int), frexp answers ((m, e), errno),
// modf ((fraction, integral), errno), fma takes three
Ref i_libm(Obj, Args a) {
    positional_only(a, "_libm", 2, 4);
    const std::string& name = as_str(a.pos(0))->text;
    double x = float_as_double(a.pos(1));
    errno = 0;
    if (name == "ldexp") {
        int e = static_cast<int>(index_value(a.pos(2)));
        double r = std::ldexp(x, e);
        return pair(r, errno);
    }
    if (name == "frexp") {
        int e = 0;
        double m = std::frexp(x, &e);
        int err = errno;
        Ref mant = float_ref(m), exp = int_from_i64(e);
        Ref both = tuple_new({mant.get(), exp.get()});
        Ref code = int_from_i64(err);
        return tuple_new({both.get(), code.get()});
    }
    if (name == "modf") {
        double whole = 0.0;
        double frac = std::modf(x, &whole);
        int err = errno;
        Ref f = float_ref(frac), w = float_ref(whole);
        Ref both = tuple_new({f.get(), w.get()});
        Ref code = int_from_i64(err);
        return tuple_new({both.get(), code.get()});
    }
    if (name == "fma") {
        double y = float_as_double(a.pos(2)), z = float_as_double(a.pos(3));
        double r = std::fma(x, y, z);
        return pair(r, errno);
    }
    if (a.npos == 2) {
        Unary f = unary_of(name);
        if (f == nullptr) raise_new("ValueError", "_libm(): no such function " + name);
        double r = f(x);
        return pair(r, errno);
    }
    Binary g = binary_of(name);
    if (g == nullptr) raise_new("ValueError", "_libm(): no such function " + name);
    double y = float_as_double(a.pos(2));
    double r = g(x, y);
    return pair(r, errno);
}

}  // namespace bella
