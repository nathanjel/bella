// runtime/src/complex.cpp -- complex, from Objects/complexobject.c. Its digits are float's (format.cpp), and what
// goes through the deprecation warnings of the C stops by name until `warnings` is there.
#include <cerrno>
#include <cmath>

#include "bella/runtime.hpp"

namespace bella {
namespace {
const Str* N(const char* s) { return intern(s); }
Ref declined() { return Ref::steal(Obj::of(NOTIMPLEMENTED)); }

struct Cx {
    double real, imag;
};
Cx value_of(Obj v) {
    auto* c = static_cast<const Complex*>(v.object());
    return {c->real, c->imag};
}

Cx c_sum(Cx a, Cx b) { return {a.real + b.real, a.imag + b.imag}; }
Cx cr_sum(Cx a, double b) { return {a.real + b, a.imag}; }
Cx rc_sum(double a, Cx b) { return cr_sum(b, a); }
Cx c_diff(Cx a, Cx b) { return {a.real - b.real, a.imag - b.imag}; }
Cx cr_diff(Cx a, double b) { return {a.real - b, a.imag}; }
Cx rc_diff(double a, Cx b) { return {a - b.real, -b.imag}; }

Cx c_prod(Cx z, Cx w) {                          // _Py_c_prod, with C11's recovery of infinities (Annex G.5.1)
    double a = z.real, b = z.imag, c = w.real, d = w.imag;
    double ac = a * c, bd = b * d, ad = a * d, bc = b * c;
    Cx r = {ac - bd, ad + bc};
    if (std::isnan(r.real) && std::isnan(r.imag)) {
        bool recalc = false;
        if (std::isinf(a) || std::isinf(b)) {
            a = std::copysign(std::isinf(a) ? 1.0 : 0.0, a);
            b = std::copysign(std::isinf(b) ? 1.0 : 0.0, b);
            if (std::isnan(c)) c = std::copysign(0.0, c);
            if (std::isnan(d)) d = std::copysign(0.0, d);
            recalc = true;
        }
        if (std::isinf(c) || std::isinf(d)) {
            c = std::copysign(std::isinf(c) ? 1.0 : 0.0, c);
            d = std::copysign(std::isinf(d) ? 1.0 : 0.0, d);
            if (std::isnan(a)) a = std::copysign(0.0, a);
            if (std::isnan(b)) b = std::copysign(0.0, b);
            recalc = true;
        }
        if (!recalc && (std::isinf(ac) || std::isinf(bd) || std::isinf(ad) || std::isinf(bc))) {
            if (std::isnan(a)) a = std::copysign(0.0, a);
            if (std::isnan(b)) b = std::copysign(0.0, b);
            if (std::isnan(c)) c = std::copysign(0.0, c);
            if (std::isnan(d)) d = std::copysign(0.0, d);
            recalc = true;
        }
        if (recalc) {
            r.real = HUGE_VAL * (a * c - b * d);
            r.imag = HUGE_VAL * (a * d + b * c);
        }
    }
    return r;
}
Cx cr_prod(Cx a, double b) { return {a.real * b, a.imag * b}; }
Cx rc_prod(double a, Cx b) { return cr_prod(b, a); }

Cx c_quot(Cx a, Cx b) {                          // _Py_c_quot: Smith's, and Annex G.5.2 for what comes out nan+nanj
    Cx r;
    const double abs_breal = b.real < 0 ? -b.real : b.real;
    const double abs_bimag = b.imag < 0 ? -b.imag : b.imag;
    if (abs_breal >= abs_bimag) {
        if (abs_breal == 0.0) {
            errno = EDOM;
            r.real = r.imag = 0.0;
        } else {
            const double ratio = b.imag / b.real;
            const double denom = b.real + b.imag * ratio;
            r.real = (a.real + a.imag * ratio) / denom;
            r.imag = (a.imag - a.real * ratio) / denom;
        }
    } else if (abs_bimag >= abs_breal) {
        const double ratio = b.real / b.imag;
        const double denom = b.real * ratio + b.imag;
        r.real = (a.real * ratio + a.imag) / denom;
        r.imag = (a.imag * ratio - a.real) / denom;
    } else {
        r.real = r.imag = std::nan("");
    }
    if (std::isnan(r.real) && std::isnan(r.imag)) {
        if ((std::isinf(a.real) || std::isinf(a.imag)) && std::isfinite(b.real) && std::isfinite(b.imag)) {
            const double x = std::copysign(std::isinf(a.real) ? 1.0 : 0.0, a.real);
            const double y = std::copysign(std::isinf(a.imag) ? 1.0 : 0.0, a.imag);
            r.real = HUGE_VAL * (x * b.real + y * b.imag);
            r.imag = HUGE_VAL * (y * b.real - x * b.imag);
        } else if ((std::isinf(abs_breal) || std::isinf(abs_bimag)) && std::isfinite(a.real) && std::isfinite(a.imag)) {
            const double x = std::copysign(std::isinf(b.real) ? 1.0 : 0.0, b.real);
            const double y = std::copysign(std::isinf(b.imag) ? 1.0 : 0.0, b.imag);
            r.real = 0.0 * (a.real * x + a.imag * y);
            r.imag = 0.0 * (a.imag * x - a.real * y);
        }
    }
    return r;
}
Cx cr_quot(Cx a, double b) {
    Cx r = a;
    if (b != 0.0) {
        r.real /= b;
        r.imag /= b;
    } else {
        errno = EDOM;
        r.real = r.imag = 0.0;
    }
    return r;
}
Cx rc_quot(double a, Cx b) {
    Cx r;
    const double abs_breal = b.real < 0 ? -b.real : b.real;
    const double abs_bimag = b.imag < 0 ? -b.imag : b.imag;
    if (abs_breal >= abs_bimag) {
        if (abs_breal == 0.0) {
            errno = EDOM;
            r.real = r.imag = 0.0;
        } else {
            const double ratio = b.imag / b.real;
            const double denom = b.real + b.imag * ratio;
            r.real = a / denom;
            r.imag = (-a * ratio) / denom;
        }
    } else if (abs_bimag >= abs_breal) {
        const double ratio = b.real / b.imag;
        const double denom = b.real * ratio + b.imag;
        r.real = (a * ratio) / denom;
        r.imag = (-a) / denom;
    } else {
        r.real = r.imag = std::nan("");
    }
    if (std::isnan(r.real) && std::isnan(r.imag) && std::isfinite(a) && (std::isinf(abs_breal) || std::isinf(abs_bimag))) {
        const double x = std::copysign(std::isinf(b.real) ? 1.0 : 0.0, b.real);
        const double y = std::copysign(std::isinf(b.imag) ? 1.0 : 0.0, b.imag);
        r.real = 0.0 * (a * x);
        r.imag = 0.0 * (-a * y);
    }
    return r;
}

void adjust_erange2(double x, double y) {        // _Py_ADJUST_ERANGE2
    if (std::isinf(x) || std::isinf(y)) {
        if (errno == 0) errno = ERANGE;
    } else if (errno == ERANGE) {
        errno = 0;
    }
}
Cx c_pow(Cx a, Cx b) {                           // _Py_c_pow
    Cx r;
    if (b.real == 0.0 && b.imag == 0.0) {
        r.real = 1.0;
        r.imag = 0.0;
    } else if (a.real == 0.0 && a.imag == 0.0) {
        if (b.imag != 0.0 || b.real < 0.0) errno = EDOM;
        r.real = 0.0;
        r.imag = 0.0;
    } else {
        double vabs = std::hypot(a.real, a.imag);
        double len = std::pow(vabs, b.real);
        double at = std::atan2(a.imag, a.real);
        double phase = at * b.real;
        if (b.imag != 0.0) {
            len *= std::exp(-at * b.imag);
            phase += b.imag * std::log(vabs);
        }
        r.real = len * std::cos(phase);
        r.imag = len * std::sin(phase);
        adjust_erange2(r.real, r.imag);
    }
    return r;
}
Cx c_powu(Cx x, long n) {
    Cx r = {1.0, 0.0}, p = x;
    long mask = 1;
    while (mask > 0 && n >= mask) {
        if ((n & mask) != 0) r = c_prod(r, p);
        mask <<= 1;
        p = c_prod(p, p);
    }
    return r;
}
Cx c_powi(Cx x, long n) { return n > 0 ? c_powu(x, n) : c_quot({1.0, 0.0}, c_powu(x, -n)); }
double c_abs(Cx z) {                             // _Py_c_abs
    if (!std::isfinite(z.real) || !std::isfinite(z.imag)) {
        if (std::isinf(z.real)) {
            errno = 0;
            return std::fabs(z.real);
        }
        if (std::isinf(z.imag)) {
            errno = 0;
            return std::fabs(z.imag);
        }
        return std::nan("");
    }
    double result = std::hypot(z.real, z.imag);
    errno = std::isfinite(result) ? 0 : ERANGE;
    return result;
}

// real_to_double: a float's value, or an int's (whose OverflowError goes up); false for anything else
bool real_to_double(Obj v, double& out) {
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
bool to_complex(Obj v, Cx& out) {                // TO_COMPLEX
    if (is_complex(v)) {
        out = value_of(v);
        return true;
    }
    out.imag = 0.0;
    return real_to_double(v, out.real);
}

Ref make(ClassObject* cls, double real, double imag) {   // complex_subtype_from_doubles
    if (cls == types().complex_) return complex_ref(real, imag);
    return own(new ComplexInstance(cls, real, imag));
}

bool has_special(Obj v, const char* name) { return !type_lookup(type_of(v), N(name)).is_unset(); }
bool number_slots(Obj v) { return has_special(v, "__float__") || has_special(v, "__index__"); }   // nb_float, nb_index

// try_complex_special_method: false if op has no __complex__
bool try_special(Obj op, Ref& out) {
    bool found = false;
    Ref res = call_special(op, "__complex__", {}, &found);
    if (!found) return false;
    if (is_kind(res.get(), Kind::Complex)) {
        out = std::move(res);
        return true;
    }
    if (!is_complex(res.get()))
        raise_new("TypeError", fully_qualified_name(type_of(op)) + ".__complex__() must return a complex, not " + fully_qualified_name(type_of(res.get())));
    throw NotImplemented("__complex__ returning an instance of a subclass of complex (a DeprecationWarning in CPython)");
}
Cx as_c_complex(Obj op) {                        // PyComplex_AsCComplex
    if (is_complex(op)) return value_of(op);
    Ref made;
    if (try_special(op, made)) return value_of(made.get());
    return {float_as_double(op), 0.0};
}

Ref from_string_inner(ClassObject* cls, const std::string& text) {   // complex_from_string_inner
    auto space = [](char c) { return c == ' ' || (c >= '\t' && c <= '\r'); };   // Py_ISSPACE
    auto parse_error = []() -> Ref { raise_new("ValueError", "complex() arg is a malformed string"); };
    const char* start = text.c_str();
    const char* last = start + text.size();
    const char* s = start;
    double x = 0.0, y = 0.0, z = 0.0;
    bool got_bracket = false;
    const char* end = nullptr;
    while (space(*s)) ++s;
    if (*s == '(') {
        got_bracket = true;
        ++s;
        while (space(*s)) ++s;
    }
    z = string_to_double(s, last, end);
    if (end != s) {
        s = end;
        if (*s == '+' || *s == '-') {
            x = z;
            y = string_to_double(s, last, end);
            if (end != s) {
                s = end;
            } else {
                y = *s == '+' ? 1.0 : -1.0;
                ++s;
            }
            if (!(*s == 'j' || *s == 'J')) return parse_error();
            ++s;
        } else if (*s == 'j' || *s == 'J') {
            ++s;
            y = z;
        } else {
            x = z;
        }
    } else {
        if (*s == '+' || *s == '-') {
            y = *s == '+' ? 1.0 : -1.0;
            ++s;
        } else {
            y = 1.0;
        }
        if (!(*s == 'j' || *s == 'J')) return parse_error();
        ++s;
    }
    while (space(*s)) ++s;
    if (got_bracket) {
        if (*s != ')') return parse_error();
        ++s;
        while (space(*s)) ++s;
    }
    if (s != last) return parse_error();
    return make(cls, x, y);
}
Ref from_string(ClassObject* cls, Obj v) {       // complex_subtype_from_string
    const Str* s = as_str(v);
    std::string transformed;
    return from_string_inner(cls, without_underscores(decimal_and_space_to_ascii(s, transformed), "complex", v));   // _PyUnicode_TransformDecimalAndSpaceToASCII
}

[[noreturn]] void deprecated_part(const char* part, Obj given) {
    throw NotImplemented(std::string("complex() argument '") + part + "' of type " + fully_qualified_name(type_of(given)) + " (a DeprecationWarning in CPython)");
}
Ref new_impl(ClassObject* cls, Obj r, Obj i) {   // complex_new_impl
    Ref zero = int_from_i64(0);
    if (r.is_unset()) r = zero.get();
    Obj orig_r = r;
    Ref tmp;
    if (try_special(r, tmp)) r = tmp.get();
    if (!number_slots(r) && !is_complex(r))
        raise_new("TypeError", "complex() argument 'real' must be a real number, not " + fully_qualified_name(type_of(r)));
    if (!i.is_unset() && !number_slots(i) && !is_complex(i))
        raise_new("TypeError", "complex() argument 'imag' must be a real number, not " + fully_qualified_name(type_of(i)));
    double real = 0.0, real_imag = 0.0;
    bool real_is_complex = false;
    if (is_complex(r)) {
        Cx c = value_of(r);
        real = c.real;
        real_imag = c.imag;
        real_is_complex = true;
        if (!number_slots(orig_r)) deprecated_part("real", orig_r);
    } else {
        Ref as_float = number_float(r);
        real = float_value(as_float.get());
    }
    double imag = real_imag;
    if (!i.is_unset()) {
        if (is_complex(i)) deprecated_part("imag", i);
        Ref as_float = number_float(i);
        imag = float_value(as_float.get());
        if (real_is_complex) imag += real_imag;
    }
    return make(cls, real, imag);
}
Ref new_m(Obj, Args a) {                         // actual_complex_new, then the clinic's complex_new
    ClassObject* cls = new_wrapper_class(a, types().complex_);
    std::size_t npos = a.npos - 1;
    if (npos > 1 || a.nkw != 0) {
        if (npos + a.nkw > 2) raise_new("TypeError", std::string("complex() takes at most 2 ") + (npos == 0 ? "keyword " : "") + "arguments (" + std::to_string(npos + a.nkw) + " given)");
        Obj r = npos >= 1 ? a.pos(1) : Obj{}, i = npos >= 2 ? a.pos(2) : Obj{};
        for (std::size_t k = 0; k < a.nkw; ++k) {
            const std::string& name = a.kwnames[k]->text;
            if (name == "real") {
                if (npos >= 1) raise_new("TypeError", "argument for complex() given by name ('real') and position (1)");
                r = a.kw(k);
            } else if (name == "imag") {
                if (npos >= 2) raise_new("TypeError", "argument for complex() given by name ('imag') and position (2)");
                i = a.kw(k);
            } else {
                unexpected_keyword("complex()", a.kwnames[k], {"real", "imag"});
            }
        }
        return new_impl(cls, r, i);
    }
    if (npos == 0) return make(cls, 0.0, 0.0);
    Obj arg = a.pos(1);
    if (is_kind(arg, Kind::Complex) && cls == types().complex_) return Ref::share(arg);
    if (as_str(arg) != nullptr) return from_string(cls, arg);
    Ref tmp;
    if (try_special(arg, tmp)) {
        Cx c = value_of(tmp.get());
        return make(cls, c.real, c.imag);
    }
    if (is_complex(arg)) {
        Cx c = value_of(arg);
        return make(cls, c.real, c.imag);
    }
    if (number_slots(arg)) return make(cls, float_as_double(arg), 0.0);
    raise_new("TypeError", "complex() argument must be a string or a number, not " + fully_qualified_name(type_of(arg)));
}

Ref exact_copy(Obj self) {
    if (is_kind(self, Kind::Complex)) return Ref::share(self);
    Cx c = value_of(self);
    return complex_ref(c.real, c.imag);
}
void wrapper_args(Args a, const char* name, std::size_t n) {     // wrapper_call, check_num_args
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos != n)
        raise_new("TypeError", "expected " + std::to_string(n) + " argument" + (n == 1 ? "" : "s") + ", got " + std::to_string(a.npos));
}
template <BinOp op>
const char* slot_name(bool reflected) {
    switch (op) {
        case BinOp::Add: return reflected ? "__radd__" : "__add__";
        case BinOp::Sub: return reflected ? "__rsub__" : "__sub__";
        case BinOp::Mul: return reflected ? "__rmul__" : "__mul__";
        default: return reflected ? "__rtruediv__" : "__truediv__";
    }
}
template <BinOp op, bool reflected>
Ref binary_slot(Obj self, Args a) {
    const char* name = slot_name<op>(reflected);
    wrapper_args(a, name, 1);
    return reflected ? complex_binary(op, a.pos(0), self) : complex_binary(op, self, a.pos(0));
}
template <bool reflected>
Ref pow_slot(Obj self, Args a) {                 // wrap_ternaryfunc, wrap_ternaryfunc_r
    const char* name = reflected ? "__rpow__" : "__pow__";
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos < 1 || a.npos > 2) raise_new("TypeError", "expected 1 or 2 arguments, got " + std::to_string(a.npos));
    Obj mod = a.npos == 2 ? a.pos(1) : None();
    return reflected ? complex_power(a.pos(0), self, mod) : complex_power(self, a.pos(0), mod);
}
Ref neg_slot(Obj self, Args a) {
    wrapper_args(a, "__neg__", 0);
    Cx c = value_of(self);
    return complex_ref(-c.real, -c.imag);
}
Ref pos_slot(Obj self, Args a) {
    wrapper_args(a, "__pos__", 0);
    return exact_copy(self);
}
Ref abs_slot(Obj self, Args a) {
    wrapper_args(a, "__abs__", 0);
    errno = 0;
    double result = c_abs(value_of(self));
    if (errno == ERANGE) raise_new("OverflowError", "absolute value too large");
    return float_ref(result);
}
Ref bool_slot(Obj self, Args a) {
    wrapper_args(a, "__bool__", 0);
    return Ref::steal(boolean(complex_truth(self)));
}
Ref repr_slot(Obj self, Args a) {
    wrapper_args(a, "__repr__", 0);
    Cx c = value_of(self);
    return str_new(complex_text(c.real, c.imag));
}
Ref hash_slot(Obj self, Args a) {
    wrapper_args(a, "__hash__", 0);
    return int_from_i64(complex_hash(self));
}
template <CmpOp op>
const char* cmp_slot_name() {
    switch (op) {
        case CmpOp::Eq: return "__eq__";
        case CmpOp::Ne: return "__ne__";
        case CmpOp::Lt: return "__lt__";
        case CmpOp::Le: return "__le__";
        case CmpOp::Gt: return "__gt__";
        default: return "__ge__";
    }
}
template <CmpOp op>
Ref cmp_slot(Obj self, Args a) {
    const char* name = cmp_slot_name<op>();
    wrapper_args(a, name, 1);
    return complex_compare(op, self, a.pos(0));
}
Ref conjugate_m(Obj self, Args a) {
    noargs(a, "complex.conjugate");
    Cx c = value_of(self);
    return complex_ref(c.real, -c.imag);
}
Ref complex_m(Obj self, Args a) {
    noargs(a, "complex.__complex__");
    return exact_copy(self);
}
Ref getnewargs_m(Obj self, Args a) {
    noargs(a, "complex.__getnewargs__");
    Cx c = value_of(self);
    Ref real = float_ref(c.real), imag = float_ref(c.imag);
    return tuple_new({real.get(), imag.get()});
}
Ref from_number_m(Obj cls, Args a) {             // complex_from_number_impl
    onearg(a, "complex.from_number");
    Obj number = a.pos(0);
    if (is_kind(number, Kind::Complex) && cls == Obj::of(types().complex_)) return Ref::share(number);
    Cx c = as_c_complex(number);
    Ref result = complex_ref(c.real, c.imag);
    if (cls == Obj::of(types().complex_)) return result;
    return invoke(cls, {result.get()});
}
Ref real_get(Obj self) { return float_ref(value_of(self).real); }
Ref imag_get(Obj self) { return float_ref(value_of(self).imag); }
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
}  // namespace

Ref i_as_c_complex(Obj, Args a) {                // PyComplex_AsCComplex for a prelude (cmath): (real, imag)
    positional_only(a, "_as_c_complex", 1, 1);
    Cx c = as_c_complex(a.pos(0));
    Ref re = float_ref(c.real), im = float_ref(c.imag);
    return tuple_new({re.get(), im.get()});
}

Ref complex_ref(double real, double imag) {
    auto* c = new Complex(real, imag);
    c->cls = types().complex_;
    return own(c);
}
Obj complex_constant(double real, double imag) { return complex_ref(real, imag).release(); }
bool complex_truth(Obj v) {
    Cx c = value_of(v);
    return c.real != 0.0 || c.imag != 0.0;
}
std::int64_t complex_hash(Obj self) {            // complex_hash
    Cx c = value_of(self);
    auto hashreal = static_cast<std::uint64_t>(double_hash(c.real, self.object()));
    auto hashimag = static_cast<std::uint64_t>(double_hash(c.imag, self.object()));
    std::uint64_t combined = hashreal + 1000003ULL * hashimag;   // PyHASH_IMAG
    if (combined == static_cast<std::uint64_t>(-1)) combined = static_cast<std::uint64_t>(-2);
    return static_cast<std::int64_t>(combined);
}
Ref complex_binary(BinOp op, Obj v, Obj w) {     // COMPLEX_BINOP: complex_add and its kin; nothing else is a complex's
    if (op == BinOp::Pow) return complex_power(v, w, None());
    if (op != BinOp::Add && op != BinOp::Sub && op != BinOp::Mul && op != BinOp::TrueDiv) return declined();
    errno = 0;
    Cx a;
    if (is_complex(w)) {
        Cx b = value_of(w);
        if (is_complex(v)) {
            Cx x = value_of(v);
            a = op == BinOp::Add ? c_sum(x, b) : op == BinOp::Sub ? c_diff(x, b) : op == BinOp::Mul ? c_prod(x, b) : c_quot(x, b);
        } else {
            double x = 0.0;
            if (!real_to_double(v, x)) return declined();
            a = op == BinOp::Add ? rc_sum(x, b) : op == BinOp::Sub ? rc_diff(x, b) : op == BinOp::Mul ? rc_prod(x, b) : rc_quot(x, b);
        }
    } else if (!is_complex(v)) {
        return declined();
    } else {
        Cx x = value_of(v);
        double b = 0.0;
        if (!real_to_double(w, b)) return declined();
        a = op == BinOp::Add ? cr_sum(x, b) : op == BinOp::Sub ? cr_diff(x, b) : op == BinOp::Mul ? cr_prod(x, b) : cr_quot(x, b);
    }
    if (errno == EDOM) raise_new("ZeroDivisionError", "division by zero");
    return complex_ref(a.real, a.imag);
}
Ref complex_power(Obj v, Obj w, Obj z) {         // complex_pow
    Cx a, b, p;
    if (!to_complex(v, a) || !to_complex(w, b)) return declined();
    if (z != None()) raise_new("ValueError", "complex modulo");
    errno = 0;
    if (b.imag == 0.0 && b.real == std::floor(b.real) && std::fabs(b.real) <= 100.0) {   // small integers: faster, more accurate
        p = c_powi(a, static_cast<long>(b.real));
        adjust_erange2(p.real, p.imag);
    } else {
        p = c_pow(a, b);
    }
    if (errno == EDOM) raise_new("ZeroDivisionError", "zero to a negative or complex power");
    if (errno == ERANGE) raise_new("OverflowError", "complex exponentiation");
    return complex_ref(p.real, p.imag);
}
Ref complex_compare(CmpOp op, Obj v, Obj w) {    // complex_richcompare
    if (op != CmpOp::Eq && op != CmpOp::Ne) return declined();
    Cx i = value_of(v);
    bool equal = false;
    if (is_int(w)) {
        if (i.imag == 0.0) {                     // the float against the int, exactly
            Ref j = float_ref(i.real);
            return float_compare(op, j.get(), w);
        }
    } else if (is_float(w)) {
        equal = i.real == float_value(w) && i.imag == 0.0;
    } else if (is_complex(w)) {
        Cx j = value_of(w);
        equal = i.real == j.real && i.imag == j.imag;
    } else {
        return declined();
    }
    return Ref::steal(boolean(equal == (op == CmpOp::Eq)));
}

void init_complex() {
    ClassObject* c = types().complex_;
    method(c, "__new__", new_m, Binding::Function);
    method(c, "__add__", binary_slot<BinOp::Add, false>);
    method(c, "__radd__", binary_slot<BinOp::Add, true>);
    method(c, "__sub__", binary_slot<BinOp::Sub, false>);
    method(c, "__rsub__", binary_slot<BinOp::Sub, true>);
    method(c, "__mul__", binary_slot<BinOp::Mul, false>);
    method(c, "__rmul__", binary_slot<BinOp::Mul, true>);
    method(c, "__truediv__", binary_slot<BinOp::TrueDiv, false>);
    method(c, "__rtruediv__", binary_slot<BinOp::TrueDiv, true>);
    method(c, "__pow__", pow_slot<false>);
    method(c, "__rpow__", pow_slot<true>);
    method(c, "__neg__", neg_slot);
    method(c, "__pos__", pos_slot);
    method(c, "__abs__", abs_slot);
    method(c, "__bool__", bool_slot);
    method(c, "__repr__", repr_slot);
    method(c, "__hash__", hash_slot);
    method(c, "__eq__", cmp_slot<CmpOp::Eq>);
    method(c, "__ne__", cmp_slot<CmpOp::Ne>);
    method(c, "__lt__", cmp_slot<CmpOp::Lt>);
    method(c, "__le__", cmp_slot<CmpOp::Le>);
    method(c, "__gt__", cmp_slot<CmpOp::Gt>);
    method(c, "__ge__", cmp_slot<CmpOp::Ge>);
    method(c, "conjugate", conjugate_m);
    method(c, "__complex__", complex_m);
    method(c, "__getnewargs__", getnewargs_m);
    method(c, "__format__", complex_format_dunder);
    method(c, "from_number", from_number_m, Binding::ClassMethod);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{{"real", real_get}, {"imag", imag_get}}) {
        auto* m = new GetSet(name, c, get, nullptr);
        m->cls = types().member_descriptor;
        c->attrs.set(N(name), Obj::of(m));
    }
}
}  // namespace bella
