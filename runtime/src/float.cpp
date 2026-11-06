// runtime/src/float.cpp -- float, from Objects/floatobject.c, with its digits from <charconv> (decision of
// 2026-11-02, `make float-diff`): what the C keeps in dtoa.c, the layout around the digits is Python's and here.
// The conversions that need an int's limbs are in bigint.cpp (int_as_double, int_from_double, int_true_divide).
#include <cerrno>
#include <cfloat>
#include <charconv>
#include <climits>
#include <cmath>
#include <cstring>

#include "bella/runtime.hpp"

namespace bella {
namespace {
const Str* N(const char* s) { return intern(s); }
Ref declined() { return Ref::steal(Obj::of(NOTIMPLEMENTED)); }

// CONVERT_TO_DOUBLE: a float, or an int through PyLong_AsDouble; anything else declines
bool to_double(Obj v, double& out) {
    if (is_float(v)) {
        out = float_value(v);
        return true;
    }
    if (is_int(v)) {
        out = int_as_double(v);
        return true;
    }
    return false;
}
bool odd_integer(double x) { return std::fabs(std::fmod(x, 2.0)) == 1.0; }   // DOUBLE_IS_ODD_INTEGER

// _float_div_mod
void div_mod(double vx, double wx, double& floordiv, double& mod) {
    mod = std::fmod(vx, wx);
    double div = (vx - mod) / wx;                // an exact multiple of wx, as nearly as a double can say
    if (mod != 0.0) {
        if ((wx < 0) != (mod < 0)) {             // the remainder has the denominator's sign
            mod += wx;
            div -= 1.0;
        }
    } else {
        mod = std::copysign(0.0, wx);
    }
    if (div != 0.0) {                            // snap the quotient to the nearest integral value
        floordiv = std::floor(div);
        if (div - floordiv > 0.5) floordiv += 1.0;
    } else {
        floordiv = std::copysign(0.0, vx / wx);
    }
}

Ref float_pow(double iv, double iw) {            // float_pow, whose special cases are its own and not libm's
    bool negate_result = false;
    if (iw == 0) return float_ref(1.0);
    if (std::isnan(iv)) return float_ref(iv);
    if (std::isnan(iw)) return float_ref(iv == 1.0 ? 1.0 : iw);
    if (std::isinf(iw)) {
        iv = std::fabs(iv);
        if (iv == 1.0) return float_ref(1.0);
        if ((iw > 0.0) == (iv > 1.0)) return float_ref(std::fabs(iw));
        return float_ref(0.0);
    }
    if (std::isinf(iv)) {
        bool odd = odd_integer(iw);
        if (iw > 0.0) return float_ref(odd ? iv : std::fabs(iv));
        return float_ref(odd ? std::copysign(0.0, iv) : 0.0);
    }
    if (iv == 0.0) {
        bool odd = odd_integer(iw);
        if (iw < 0.0) raise_new("ZeroDivisionError", "zero to a negative power");
        return float_ref(odd ? iv : 0.0);
    }
    if (iv < 0.0) {
        if (iw != std::floor(iw)) return complex_power(float_ref(iv).get(), float_ref(iw).get(), None());   // nb_power of complex
        iv = -iv;
        negate_result = odd_integer(iw);
    }
    if (iv == 1.0) return float_ref(negate_result ? -1.0 : 1.0);
    errno = 0;
    double ix = std::pow(iv, iw);
    if (ix == 0.0 || std::isinf(ix)) {           // _Py_ADJUST_ERANGE1: an underflow to zero is no error
        if (std::isinf(ix)) errno = ERANGE;
        else if (errno == ERANGE) errno = 0;
    }
    if (negate_result) ix = -ix;
    if (errno == ERANGE) {                       // PyErr_SetFromErrno: (errno, strerror)
        Ref number = int_from_i64(ERANGE), message = str_new(std::strerror(ERANGE));
        Ref exc = invoke(Obj::of(exception_class("OverflowError")), {number.get(), message.get()});
        raise(exc.get());
    }
    return float_ref(ix);
}

bool ordered_double(CmpOp op, double a, double b) {
    switch (op) {
        case CmpOp::Lt: return a < b;
        case CmpOp::Le: return a <= b;
        case CmpOp::Eq: return a == b;
        case CmpOp::Ne: return a != b;
        case CmpOp::Gt: return a > b;
        default: return a >= b;
    }
}

// PyOS_string_to_double on [s, last), with no error for what it cannot read: `end` says where it stopped
double parse_double(const char* s, const char* last, const char*& end) {
    const char* p = s;
    bool negative = false;
    if (p < last && (*p == '-' || *p == '+')) negative = *p++ == '-';
    const char* start = p;
    auto digits = [&] {
        const char* from = p;
        while (p < last && *p >= '0' && *p <= '9') ++p;
        return p - from;
    };
    auto int_digits = digits();
    auto frac_digits = std::ptrdiff_t{0};
    if (p < last && *p == '.') {
        const char* dot = p++;
        frac_digits = digits();
        if (int_digits == 0 && frac_digits == 0) p = dot;
    }
    if (int_digits == 0 && frac_digits == 0) {   // _Py_parse_inf_or_nan
        auto word = [&](const char* w) {
            std::size_t n = std::strlen(w);
            if (static_cast<std::size_t>(last - p) < n) return false;
            for (std::size_t k = 0; k < n; ++k)
                if ((p[k] >= 'A' && p[k] <= 'Z' ? p[k] + 32 : p[k]) != w[k]) return false;
            p += n;
            return true;
        };
        p = start;
        if (word("inf")) {
            word("inity");
            end = p;
            return negative ? -HUGE_VAL : HUGE_VAL;
        }
        if (word("nan")) {
            end = p;
            return negative ? -std::fabs(std::nan("")) : std::fabs(std::nan(""));
        }
        end = s;
        return -1.0;
    }
    const char* mantissa_end = p;
    long long exponent = 0;
    if (p < last && (*p == 'e' || *p == 'E')) {
        const char* q = p + 1;
        bool exp_negative = false;
        if (q < last && (*q == '-' || *q == '+')) exp_negative = *q++ == '-';
        if (q < last && *q >= '0' && *q <= '9') {
            while (q < last && *q >= '0' && *q <= '9') {
                if (exponent < 1000000000000LL) exponent = exponent * 10 + (*q - '0');
                ++q;
            }
            if (exp_negative) exponent = -exponent;
            p = q;
        }
    }
    end = p;
    double value = 0.0;
    auto [ptr, ec] = std::from_chars(start, p, value);
    if (ec == std::errc::result_out_of_range) {  // beyond a double's range: an infinity or a zero
        long long point = int_digits;            // where the first significant digit falls
        for (const char* q = start; q < mantissa_end; ++q) {
            if (*q == '.') continue;
            if (*q != '0') break;
            --point;
        }
        value = point + exponent > 0 ? HUGE_VAL : 0.0;
    }
    return negative ? -value : value;
}

[[noreturn]] void cannot_convert(Obj shown) {
    Ref r = repr_of(shown);
    raise_new("ValueError", "could not convert string to float: " + as_str(r.get())->text);
}

// _Py_string_to_number_with_underscores around float_from_string_inner
Ref float_from_text(const std::string& given, Obj shown) {
    std::string text = without_underscores(given, "float", shown);
    auto space = [](char c) { return c == ' ' || (c >= '\t' && c <= '\r'); };   // Py_ISSPACE
    const char* s = text.data();
    const char* last = s + text.size();
    while (s < last && space(*s)) ++s;
    if (s == last) cannot_convert(shown);
    while (s < last - 1 && space(last[-1])) --last;
    const char* end = s;
    double x = parse_double(s, last, end);
    if (end != last || end == s) cannot_convert(shown);
    return float_ref(x);
}

Ref float_from_string(Obj v) {                   // PyFloat_FromString
    if (const Str* s = as_str(v)) {
        if (!s->ascii) throw NotImplemented("float() of a str beyond ASCII (its digits and spaces need the Unicode database)");
        return float_from_text(s->text, v);
    }
    if (is_bytes_like(v)) return float_from_text(bytes_data(v), v);
    raise_new("TypeError", "float() argument must be a string or a real number, not '" + type_of(v)->name + "'");
}

bool has_special(Obj v, const char* name) { return !type_lookup(type_of(v), N(name)).is_unset(); }

// a method's result where the C wants a float: an instance of a strict subclass is deprecated
void check_float_result(Obj o, Obj res) {
    if (is_kind(res, Kind::Float)) return;
    if (!is_float(res))
        raise_new("TypeError", fully_qualified_name(type_of(o)) + ".__float__() must return a float, not " + fully_qualified_name(type_of(res)));
    throw NotImplemented("__float__ returning an instance of a subclass of float (a DeprecationWarning in CPython)");
}

Ref float_new_impl(Obj x) {                      // float_new_impl for float itself
    if (x.is_unset()) return float_ref(0.0);
    if (is_kind(x, Kind::Str) && type_lookup(type_of(x), intern("__float__")).is_unset()) return float_from_string(x);
    return number_float(x);
}
Ref float_new_m(Obj, Args a) {                   // float.__new__(cls, x=0, /)
    ClassObject* cls = new_wrapper_class(a, types().float_);
    std::size_t npos = a.npos - 1;
    if (a.nkw != 0) raise_new("TypeError", "float() takes no keyword arguments");
    if (npos > 1) raise_new("TypeError", "float expected at most 1 argument, got " + std::to_string(npos));
    Obj x = npos == 1 ? a.pos(1) : Obj{};
    Ref value = float_new_impl(x);
    if (cls == types().float_) return value;
    auto* instance = new FloatInstance(cls, float_value(value.get()));   // float_subtype_new
    return own(instance);
}

Ref exact_copy(Obj self) {                       // float_float
    return is_kind(self, Kind::Float) ? Ref::share(self) : float_ref(float_value(self));
}

// _Py_dg_dtoa's mode 3 and back: x rounded half to even, on its exact value, at 10**-ndigits
Ref double_round(double x, int ndigits) {
    static thread_local char buf[1600];
    std::string text;
    if (ndigits >= 0) {
        auto [end, ec] = std::to_chars(buf, buf + sizeof buf, x, std::chars_format::fixed, ndigits);
        text.assign(buf, end);
    } else {                                     // left of the point: its exact digits, and the rounding by hand
        auto [end, ec] = std::to_chars(buf, buf + sizeof buf, x, std::chars_format::fixed, 1074);
        std::string_view all(buf, static_cast<std::size_t>(end - buf));
        bool negative = all[0] == '-';
        if (negative) all.remove_prefix(1);
        std::size_t point = all.find('.');
        std::string whole(all.substr(0, point));
        bool fraction = all.substr(point + 1).find_first_not_of('0') != std::string_view::npos;
        auto k = static_cast<std::size_t>(-ndigits);
        if (whole.size() <= k) whole.insert(0, k + 1 - whole.size(), '0');
        std::size_t cut = whole.size() - k;
        char key = whole[cut];
        bool rest = fraction || whole.find_first_not_of('0', cut + 1) != std::string::npos;
        std::string kept = whole.substr(0, cut);
        if (key > '5' || (key == '5' && (rest || (kept.back() - '0') % 2 == 1))) {
            std::size_t i = kept.size();
            while (i > 0 && kept[i - 1] == '9') kept[--i] = '0';
            if (i == 0) kept.insert(0, 1, '1');
            else ++kept[i - 1];
        }
        text = (negative ? "-" : "") + kept + std::string(k, '0');
    }
    bool negative = text[0] == '-';
    const char* first = text.data() + (negative ? 1 : 0);
    double rounded = 0.0;
    auto [ptr, ec] = std::from_chars(first, text.data() + text.size(), rounded);
    if (ec == std::errc::result_out_of_range) {
        if (std::fabs(x) >= 1.0) raise_new("OverflowError", "rounded value too large to represent");
        rounded = 0.0;
    }
    return float_ref(negative ? -rounded : rounded);
}

Ref round_m(Obj self, Args a) {                  // float.__round__(ndigits=None, /)
    clinic(a, "__round__", "float.__round__", 0, 1);
    double x = float_value(self);
    Obj o_ndigits = a.npos == 1 ? a.pos(0) : None();
    if (o_ndigits == None()) {
        double rounded = std::round(x);
        if (std::fabs(x - rounded) == 0.5) rounded = 2.0 * std::round(x / 2.0);
        return int_from_double(rounded);
    }
    std::int64_t ndigits = clipped_index(o_ndigits);
    if (!std::isfinite(x)) return float_ref(x);
    constexpr std::int64_t NDIGITS_MAX = 323, NDIGITS_MIN = -308;   // (DBL_MANT_DIG-DBL_MIN_EXP)*0.30103, -(DBL_MAX_EXP+1)*0.30103
    if (ndigits > NDIGITS_MAX) return float_ref(x);
    if (ndigits < NDIGITS_MIN) return float_ref(0.0 * x);
    return double_round(x, static_cast<int>(ndigits));
}
Ref trunc_m(Obj self, Args a) { noargs(a, "float.__trunc__"); return int_from_double(float_value(self)); }
Ref floor_m(Obj self, Args a) { noargs(a, "float.__floor__"); return int_from_double(std::floor(float_value(self))); }
Ref ceil_m(Obj self, Args a) { noargs(a, "float.__ceil__"); return int_from_double(std::ceil(float_value(self))); }
Ref conjugate_m(Obj self, Args a) { noargs(a, "float.conjugate"); return exact_copy(self); }
Ref getnewargs_m(Obj self, Args a) {
    noargs(a, "float.__getnewargs__");
    return tuple_new({float_ref(float_value(self)).get()});
}
Ref is_integer_m(Obj self, Args a) {
    noargs(a, "float.is_integer");
    double x = float_value(self);
    return Ref::steal(boolean(std::isfinite(x) && std::floor(x) == x));
}
Ref as_integer_ratio_m(Obj self, Args a) {
    noargs(a, "float.as_integer_ratio");
    double x = float_value(self);
    if (std::isinf(x)) raise_new("OverflowError", "cannot convert Infinity to integer ratio");
    if (std::isnan(x)) raise_new("ValueError", "cannot convert NaN to integer ratio");
    int exponent = 0;
    double part = std::frexp(x, &exponent);
    for (int i = 0; i < 300 && part != std::floor(part); ++i) {
        part *= 2.0;
        --exponent;
    }
    Ref numerator = int_from_double(part), denominator = int_from_i64(1);
    Ref shift = int_from_i64(std::abs(exponent));
    if (exponent > 0) numerator = native_binary(BinOp::LShift, numerator.get(), shift.get());
    else denominator = native_binary(BinOp::LShift, denominator.get(), shift.get());
    return tuple_new({numerator.get(), denominator.get()});
}
Ref hex_m(Obj self, Args a) {                    // float_hex_impl
    noargs(a, "float.hex");
    double x = float_value(self);
    if (std::isnan(x) || std::isinf(x)) return str_new(float_text(x));
    if (x == 0.0) return str_new(std::copysign(1.0, x) == -1.0 ? "-0x0.0p+0" : "0x0.0p+0");
    int e = 0;
    double m = std::frexp(std::fabs(x), &e);
    int shift = 1 - std::max(DBL_MIN_EXP - e, 0);
    m = std::ldexp(m, shift);
    e -= shift;
    static const char* digit = "0123456789abcdef";
    std::string s(1, digit[static_cast<int>(m)]);
    m -= static_cast<int>(m);
    s += '.';
    for (int i = 0; i < (DBL_MANT_DIG - 1) / 4; ++i) {
        m *= 16.0;
        s += digit[static_cast<int>(m)];
        m -= static_cast<int>(m);
    }
    return str_new((x < 0.0 ? "-0x" : "0x") + s + "p" + (e < 0 ? "-" : "+") + std::to_string(std::abs(e)));
}
int hex_from_char(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
double fromhex_value(const std::string& text) {  // float_fromhex_impl, as it stands in the C
    auto space = [](char c) { return c == ' ' || (c >= '\t' && c <= '\r'); };
    auto parse_error = []() -> double { raise_new("ValueError", "invalid hexadecimal floating-point string"); };
    auto overflow_error = []() -> double { raise_new("OverflowError", "hexadecimal value too large to represent as a float"); };
    const char* s = text.c_str();
    const char* s_end = s + text.size();
    double x = 0.0;
    bool negate = false;
    while (space(*s)) ++s;
    const char* inf_end = s;
    double special = parse_double(s, s_end, inf_end);
    bool numeric_start = inf_end != s && !((s[0] >= '0' && s[0] <= '9') || ((s[0] == '+' || s[0] == '-' || s[0] == '.') && (s[1] == '.' || (s[1] >= '0' && s[1] <= '9'))) || s[0] == '.');
    auto finished = [&](double value) -> double {
        while (space(*s)) ++s;
        if (s != s_end) parse_error();
        return negate ? -value : value;
    };
    if (numeric_start) {                         // infinities and nans, read with their sign
        s = inf_end;
        return finished(special);
    }
    if (*s == '-') {
        ++s;
        negate = true;
    } else if (*s == '+') {
        ++s;
    }
    const char* s_store = s;
    if (*s == '0') {
        ++s;
        if (*s == 'x' || *s == 'X') ++s;
        else s = s_store;
    }
    const char* coeff_start = s;
    while (hex_from_char(*s) >= 0) ++s;
    s_store = s;
    const char* coeff_end;
    if (*s == '.') {
        ++s;
        while (hex_from_char(*s) >= 0) ++s;
        coeff_end = s - 1;
    } else {
        coeff_end = s;
    }
    long ndigits = coeff_end - coeff_start;
    long fdigits = coeff_end - s_store;
    if (ndigits == 0) parse_error();
    if (ndigits > std::min(DBL_MIN_EXP - DBL_MANT_DIG - LONG_MIN / 2, LONG_MAX / 2 + 1 - DBL_MAX_EXP) / 4)
        raise_new("ValueError", "hexadecimal string too long to convert");
    long exp = 0;
    if (*s == 'p' || *s == 'P') {
        ++s;
        const char* exp_start = s;
        if (*s == '-' || *s == '+') ++s;
        if (!(*s >= '0' && *s <= '9')) parse_error();
        ++s;
        while (*s >= '0' && *s <= '9') ++s;
        exp = std::strtol(exp_start, nullptr, 10);
    }
    auto hex_digit = [&](long j) { return hex_from_char(*(j < fdigits ? coeff_end - j : coeff_end - 1 - j)); };
    while (ndigits > 0 && hex_digit(ndigits - 1) == 0) --ndigits;
    if (ndigits == 0 || exp < LONG_MIN / 2) return finished(0.0);
    if (exp > LONG_MAX / 2) overflow_error();
    exp -= 4 * fdigits;
    long top_exp = exp + 4 * (ndigits - 1);
    for (int digit = hex_digit(ndigits - 1); digit != 0; digit /= 2) ++top_exp;
    if (top_exp < DBL_MIN_EXP - DBL_MANT_DIG) return finished(0.0);
    if (top_exp > DBL_MAX_EXP) overflow_error();
    long lsb = std::max(top_exp, static_cast<long>(DBL_MIN_EXP)) - DBL_MANT_DIG;
    if (exp >= lsb) {
        for (long i = ndigits - 1; i >= 0; --i) x = 16.0 * x + hex_digit(i);
        return finished(std::ldexp(x, static_cast<int>(exp)));
    }
    int half_eps = 1 << static_cast<int>((lsb - exp - 1) % 4);
    long key_digit = (lsb - exp - 1) / 4;
    for (long i = ndigits - 1; i > key_digit; --i) x = 16.0 * x + hex_digit(i);
    int digit = hex_digit(key_digit);
    x = 16.0 * x + static_cast<double>(digit & (16 - 2 * half_eps));
    if ((digit & half_eps) != 0) {
        bool round_up = false;
        if ((digit & (3 * half_eps - 1)) != 0 || (half_eps == 8 && key_digit + 1 < ndigits && (hex_digit(key_digit + 1) & 1) != 0)) {
            round_up = true;
        } else {
            for (long i = key_digit - 1; i >= 0; --i)
                if (hex_digit(i) != 0) {
                    round_up = true;
                    break;
                }
        }
        if (round_up) {
            x += 2 * half_eps;
            if (top_exp == DBL_MAX_EXP && x == std::ldexp(static_cast<double>(2 * half_eps), DBL_MANT_DIG)) overflow_error();
        }
    }
    return finished(std::ldexp(x, static_cast<int>(exp + 4 * key_digit)));
}
Ref fromhex_m(Obj cls, Args a) {                 // a classmethod, METH_O
    onearg(a, "float.fromhex");
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "bad argument type for built-in operation");   // PyUnicode_AsUTF8AndSize
    Ref result = float_ref(fromhex_value(s->text));
    if (cls == Obj::of(types().float_)) return result;
    return invoke(cls, {result.get()});
}
Ref from_number_m(Obj cls, Args a) {             // float_from_number_impl
    onearg(a, "float.from_number");
    Obj number = a.pos(0);
    if (is_kind(number, Kind::Float) && cls == Obj::of(types().float_)) return Ref::share(number);
    Ref result = float_ref(float_as_double(number));
    if (cls == Obj::of(types().float_)) return result;
    return invoke(cls, {result.get()});
}
Ref getformat_m(Obj, Args a) {
    onearg(a, "float.__getformat__");
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "__getformat__() argument must be str, not " + type_of(a.pos(0))->name);
    if (s->text.find('\0') != std::string::npos) raise_new("ValueError", "embedded null character");
    if (s->text != "double" && s->text != "float") raise_new("ValueError", "__getformat__() argument 1 must be 'double' or 'float'");
    return str_new("IEEE, little-endian");
}
Ref real_get(Obj self) { return exact_copy(self); }
Ref imag_get(Obj) { return float_ref(0.0); }
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
}  // namespace

Ref number_float(Obj o) {                        // PyNumber_Float
    if (is_kind(o, Kind::Float)) return Ref::share(o);
    if (has_special(o, "__float__")) {
        Ref res = call_special(o, "__float__", {});
        check_float_result(o, res.get());
        return res;
    }
    if (has_special(o, "__index__")) {
        Ref i = int_index_of(o);
        return float_ref(int_as_double(i.get()));
    }
    return float_from_string(o);
}
Ref float_ref(double v) {
    auto* f = new Float(v);
    f->cls = types().float_;
    return own(f);
}
Obj float_constant(double v) { return float_ref(v).release(); }

// float_repr: the shortest digits that read back the same, laid out as format_float_short does for 'r'
std::string float_text(double v) {
    if (std::isnan(v)) return "nan";
    if (std::isinf(v)) return v > 0 ? "inf" : "-inf";
    char buf[64];
    auto [end, ec] = std::to_chars(buf, buf + sizeof buf, v, std::chars_format::scientific);
    std::string_view s(buf, static_cast<std::size_t>(end - buf));
    std::string out;
    if (s[0] == '-') {
        out = "-";
        s.remove_prefix(1);
    }
    std::size_t e = s.find('e');
    std::string digits(1, s[0]);
    if (e > 2) digits += s.substr(2, e - 2);
    int exponent = 0;
    std::string_view written = s.substr(e + 1);
    if (written[0] == '+') written.remove_prefix(1);
    std::from_chars(written.data(), written.data() + written.size(), exponent);
    int decpt = exponent + 1;
    auto n = static_cast<int>(digits.size());
    if (decpt <= -4 || decpt > 16) {
        out += digits[0];
        if (n > 1) out += "." + digits.substr(1);
        out += exponent < 0 ? "e-" : "e+";
        int shown = std::abs(exponent);
        if (shown < 10) out += '0';
        out += std::to_string(shown);
    } else if (decpt <= 0) {
        out += "0." + std::string(static_cast<std::size_t>(-decpt), '0') + digits;
    } else if (decpt >= n) {
        out += digits + std::string(static_cast<std::size_t>(decpt - n), '0') + ".0";
    } else {
        out += digits.substr(0, static_cast<std::size_t>(decpt)) + "." + digits.substr(static_cast<std::size_t>(decpt));
    }
    return out;
}

// the number slots of float: either operand may be the int
Ref float_binary(BinOp op, Obj a, Obj b) {
    switch (op) {
        case BinOp::Add: case BinOp::Sub: case BinOp::Mul: case BinOp::TrueDiv: case BinOp::FloorDiv: case BinOp::Mod: case BinOp::Pow:
            break;
        default:
            return declined();
    }
    double x = 0.0, y = 0.0;
    if (!to_double(a, x) || !to_double(b, y)) return declined();
    switch (op) {
        case BinOp::Add: return float_ref(x + y);
        case BinOp::Sub: return float_ref(x - y);
        case BinOp::Mul: return float_ref(x * y);
        case BinOp::TrueDiv:
            if (y == 0.0) raise_new("ZeroDivisionError", "division by zero");
            return float_ref(x / y);
        case BinOp::FloorDiv: {
            if (y == 0.0) raise_new("ZeroDivisionError", "division by zero");
            double q = 0.0, r = 0.0;
            div_mod(x, y, q, r);
            return float_ref(q);
        }
        case BinOp::Mod: {                       // float_rem
            if (y == 0.0) raise_new("ZeroDivisionError", "division by zero");
            double mod = std::fmod(x, y);
            if (mod != 0.0) {
                if ((y < 0) != (mod < 0)) mod += y;
            } else {
                mod = std::copysign(0.0, y);
            }
            return float_ref(mod);
        }
        default: return float_pow(x, y);
    }
}
Ref float_divmod(Obj a, Obj b) {
    double x = 0.0, y = 0.0;
    if (!to_double(a, x) || !to_double(b, y)) return declined();
    if (y == 0.0) raise_new("ZeroDivisionError", "division by zero");
    double q = 0.0, r = 0.0;
    div_mod(x, y, q, r);
    return tuple_new({float_ref(q).get(), float_ref(r).get()});
}

// float_richcompare, a is the float: a comparison with an int is exact, whatever the int's size. Below
// 2**53 the int is a double; beyond, the float's floor is an int, and what is left of it breaks a tie.
Ref float_compare(CmpOp op, Obj a, Obj b) {
    double x = float_value(a);
    if (is_float(b)) return Ref::steal(boolean(ordered_double(op, x, float_value(b))));
    if (!is_int(b)) return declined();
    std::int64_t small = 0;
    constexpr std::int64_t EXACT = std::int64_t{1} << 53;
    if (as_int(b, small) && small >= -EXACT && small <= EXACT)
        return Ref::steal(boolean(ordered_double(op, x, static_cast<double>(small))));
    if (std::isnan(x)) return Ref::steal(boolean(op == CmpOp::Ne));
    if (std::isinf(x)) return Ref::steal(boolean(ordered_double(op, x, 0.0)));
    double whole = std::floor(x);
    Ref floor_int = int_from_double(whole);
    int c = big_compare(floor_int.get(), b);
    if (c == 0 && x != whole) c = 1;
    return Ref::steal(boolean(ordered_double(op, c, 0)));
}

std::int64_t float_hash(Obj self) { return double_hash(float_value(self), self.object()); }
double string_to_double(const char* s, const char* last, const char*& end) { return parse_double(s, last, end); }
std::string without_underscores(const std::string& given, const char* what, Obj shown) {
    if (std::strchr(given.c_str(), '_') == nullptr) return given;
    auto wrong = [&] {
        Ref r = repr_of(shown);
        raise_new("ValueError", std::string("could not convert string to ") + what + ": " + as_str(r.get())->text);
    };
    std::string text;
    char prev = '\0';
    for (char c : given) {
        if (c == '\0') wrong();                  // no embedded NUL once there is an underscore
        if (c == '_') {                          // only after a digit, and before one
            if (!(prev >= '0' && prev <= '9')) wrong();
        } else {
            text += c;
            if (prev == '_' && !(c >= '0' && c <= '9')) wrong();
        }
        prev = c;
    }
    if (prev == '_') wrong();
    return text;
}
std::int64_t double_hash(double v, const void* instance) {   // _Py_HashDouble
    constexpr int BITS = 61;
    constexpr std::uint64_t MODULUS = (std::uint64_t{1} << BITS) - 1;
    if (!std::isfinite(v)) {
        if (std::isinf(v)) return v > 0 ? 314159 : -314159;
        std::int64_t h = pointer_hash(instance);
        return h == -1 ? -2 : h;
    }
    int e = 0;
    double m = std::frexp(v, &e);
    int sign = 1;
    if (m < 0) {
        sign = -1;
        m = -m;
    }
    std::uint64_t x = 0;
    while (m != 0.0) {                           // 28 bits at a time
        x = ((x << 28) & MODULUS) | x >> (BITS - 28);
        m *= 268435456.0;
        e -= 28;
        auto y = static_cast<std::uint64_t>(m);
        m -= static_cast<double>(y);
        x += y;
        if (x >= MODULUS) x -= MODULUS;
    }
    e = e >= 0 ? e % BITS : BITS - 1 - ((-1 - e) % BITS);
    x = ((x << e) & MODULUS) | x >> (BITS - e);
    auto h = static_cast<std::int64_t>(x * static_cast<std::uint64_t>(static_cast<std::int64_t>(sign)));
    return h == -1 ? -2 : h;
}

double float_as_double(Obj op) {                 // PyFloat_AsDouble
    if (is_float(op)) return float_value(op);
    if (has_special(op, "__float__")) {
        Ref res = call_special(op, "__float__", {});
        check_float_result(op, res.get());
        return float_value(res.get());
    }
    if (has_special(op, "__index__")) {
        Ref i = int_index_of(op);
        return int_as_double(i.get());
    }
    raise_new("TypeError", "must be real number, not " + type_of(op)->name);
}

void init_float() {
    ClassObject* f = types().float_;
    method(f, "__new__", float_new_m, Binding::Function);
    method(f, "__round__", round_m);
    method(f, "__trunc__", trunc_m);
    method(f, "__floor__", floor_m);
    method(f, "__ceil__", ceil_m);
    method(f, "__getnewargs__", getnewargs_m);
    method(f, "__format__", float_format_dunder);
    method(f, "__getformat__", getformat_m, Binding::ClassMethod);
    method(f, "conjugate", conjugate_m);
    method(f, "is_integer", is_integer_m);
    method(f, "as_integer_ratio", as_integer_ratio_m);
    method(f, "hex", hex_m);
    method(f, "fromhex", fromhex_m, Binding::ClassMethod);
    method(f, "from_number", from_number_m, Binding::ClassMethod);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{{"real", real_get}, {"imag", imag_get}})
        f->attrs.set(N(name), Obj::of(new GetSet(name, f, get, nullptr)));
}
}  // namespace bella
