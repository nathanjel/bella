// int beyond the immediates (Objects/longobject.c, Objects/rangeobject.c, Python/bltinmodule.c), the
// Python layer on a copy of SEL's bn (runtime/src/bn.inc; decision of 2026-11-02).
//
// A value that fits an immediate is an immediate, always: a BigInt is outside [-2**62, 2**62), so a
// result is made through make_int. Everything here takes any int: an immediate, a bool, a BigInt, or
// an instance of a subclass.
#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <limits>
#include <memory>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__)) && !defined(SEL_NO_ASM)
#define SEL_BN_ADX 1
#include <cpuid.h>
#else
#define SEL_BN_ADX 0
#endif

#include <cfloat>
#include <cmath>

#include "bella/runtime.hpp"

namespace bella {
__extension__ typedef unsigned __int128 u128;
#include "bn.inc"

BigInt::BigInt(bool neg, std::vector<std::uint64_t> mag) : Object(Kind::BigInt), negative(neg), limbs(std::move(mag)) {
    cls = types().int_;
}

bool is_int(Obj v) {
    if (v.is_small()) return true;
    if (!v.is_object()) return false;
    Kind k = v.object()->kind;
    return k == Kind::BigInt || k == Kind::Bool || k == Kind::IntInstance;
}

namespace {
const Str* N(const char* s) { return intern(s); }
constexpr std::int64_t SMALL_MAX_VALUE = (std::int64_t{1} << 62) - 1;
constexpr std::uint64_t TOP_BIT = std::uint64_t{1} << 63;

// An int's sign and magnitude, however it is held. Not to be copied: mag may point at `one`.
struct IntView {
    bool neg = false;
    std::uint64_t one = 0;
    bn::Span mag;
    explicit IntView(Obj v) {
        if (is_kind(v, Kind::BigInt)) {
            auto* b = static_cast<const BigInt*>(v.object());
            neg = b->negative;
            mag = b->limbs;
            return;
        }
        if (is_kind(v, Kind::IntInstance)) {
            auto* i = static_cast<const IntInstance*>(v.object());
            if (!i->limbs.empty()) {
                neg = i->negative;
                mag = i->limbs;
                return;
            }
        }
        std::int64_t x = 0;
        as_int(v, x);
        neg = x < 0;
        one = neg ? static_cast<std::uint64_t>(-(x + 1)) + 1 : static_cast<std::uint64_t>(x);
        if (one != 0) mag = bn::Span(&one, 1);
    }
    IntView(const IntView&) = delete;
    IntView& operator=(const IntView&) = delete;
    bool zero() const { return mag.empty(); }
    bool odd() const { return !mag.empty() && (mag[0] & 1) != 0; }
};

Ref make_int(bool neg, bn::Nat mag) {
    bn::normalize(mag);
    if (mag.empty()) return Ref::steal(Obj::small(0));
    if (mag.size() == 1) {
        if (!neg && mag[0] <= static_cast<std::uint64_t>(SMALL_MAX_VALUE)) return Ref::steal(Obj::small(static_cast<std::int64_t>(mag[0])));
        if (neg && mag[0] <= static_cast<std::uint64_t>(SMALL_MAX_VALUE) + 1) return Ref::steal(Obj::small(-static_cast<std::int64_t>(mag[0])));
    }
    return own(new BigInt(neg, std::move(mag)));
}
bn::Nat nat(bn::Span s) { return bn::Nat(s.begin(), s.end()); }
Ref add_signed(bool an, bn::Span a, bool bneg, bn::Span b) {
    if (an == bneg) return make_int(an, bn::add(a, b));
    int c = bn::cmp(a, b);
    if (c == 0) return make_int(false, {});
    return c > 0 ? make_int(an, bn::sub(a, b)) : make_int(bneg, bn::sub(b, a));
}
bn::Nat multiply(bn::Span a, bn::Span b) {
    if (a.empty() || b.empty()) return {};
    return bn::mul(a, b);
}
// floor division: the quotient rounds down and the remainder takes the divisor's sign
std::pair<Ref, Ref> floor_divmod(Obj a, Obj b) {
    IntView x(a), y(b);
    if (y.zero()) raise_new("ZeroDivisionError", "division by zero");
    auto [q, r] = bn::div_rem(x.mag, y.mag, nullptr);
    bn::normalize(q);
    bn::normalize(r);
    bool qneg = x.neg != y.neg;
    if (qneg && !r.empty()) {
        const std::array<std::uint64_t, 1> unit{1};
        q = bn::add(q, unit);
        r = bn::sub(y.mag, r);
    }
    Ref quotient = make_int(qneg, std::move(q));
    Ref remainder = make_int(y.neg, std::move(r));
    return {std::move(quotient), std::move(remainder)};
}
std::size_t bit_length_of(bn::Span m) { return m.empty() ? 0 : bn::bit_len(m); }
Ref power(Obj a, Obj b) {                        // long_pow without a modulus
    IntView x(a), e(b);
    if (e.neg) return float_binary(BinOp::Pow, a, b);   // long_pow's negative exponent: float_pow, of both as doubles
    std::size_t bits = bit_length_of(e.mag);
    bool base_is_unit = x.mag.empty() || (x.mag.size() == 1 && x.mag[0] == 1);
    if (!base_is_unit && (bits > 40 || static_cast<u128>(bit_length_of(x.mag) - 1) * (e.mag.empty() ? 0 : e.mag[0]) > (u128{1} << 40)))
        throw NotImplemented("a power of over 2**40 bits");
    bn::Nat result{1};
    for (std::size_t i = bits; i-- > 0;) {
        result = result.empty() ? result : bn::sqr(result);
        if ((e.mag[i / 64] >> (i % 64)) & 1) result = multiply(result, x.mag);
        bn::normalize(result);
    }
    bool negative = x.neg && e.odd();
    return make_int(negative, std::move(result));
}
Ref inverse_mod(Obj a, Obj m) {                  // long_invmod: Euclid's algorithm with Python's own arithmetic
    Ref r0 = Ref::share(m), r1 = big_binary(BinOp::Mod, a, m);
    Ref t0 = Ref::steal(Obj::small(0)), t1 = Ref::steal(Obj::small(1));
    while (!IntView(r1.get()).zero()) {
        Ref q = big_binary(BinOp::FloorDiv, r0.get(), r1.get());
        Ref r2 = big_binary(BinOp::Sub, r0.get(), big_binary(BinOp::Mul, q.get(), r1.get()).get());
        Ref t2 = big_binary(BinOp::Sub, t0.get(), big_binary(BinOp::Mul, q.get(), t1.get()).get());
        r0 = std::move(r1);
        r1 = std::move(r2);
        t0 = std::move(t1);
        t1 = std::move(t2);
    }
    IntView gcd(r0.get());
    if (!(gcd.mag.size() == 1 && gcd.mag[0] == 1)) raise_new("ValueError", "base is not invertible for the given modulus");
    return big_binary(BinOp::Mod, t0.get(), m);
}
Ref power_mod(Obj a, Obj b, Obj c) {
    IntView m(c);
    if (m.zero()) raise_new("ValueError", "pow() 3rd argument cannot be 0");
    if (m.mag.size() == 1 && m.mag[0] == 1) return Ref::steal(Obj::small(0));
    Ref modulus = make_int(false, nat(m.mag));
    Ref base = big_binary(BinOp::Mod, a, modulus.get());
    Ref exponent = Ref::share(b);
    if (IntView(b).neg) {
        base = inverse_mod(base.get(), modulus.get());
        exponent = big_negate(b);
    }
    IntView e(exponent.get());
    IntView bv(base.get());
    bn::Nat result{1};
    for (std::size_t i = bit_length_of(e.mag); i-- > 0;) {
        result = bn::div_rem(result.empty() ? result : bn::sqr(result), m.mag, nullptr).second;
        bn::normalize(result);
        if ((e.mag[i / 64] >> (i % 64)) & 1) {
            result = bn::div_rem(multiply(result, bv.mag), m.mag, nullptr).second;
            bn::normalize(result);
        }
    }
    Ref out = make_int(false, std::move(result));
    if (m.neg && !IntView(out.get()).zero()) return big_binary(BinOp::Sub, out.get(), modulus.get());
    return out;
}
Ref left_shift(Obj a, Obj b) {                   // long_lshift
    IntView x(a), n(b);
    if (n.neg) raise_new("ValueError", "negative shift count");
    if (x.zero()) return Ref::steal(Obj::small(0));
    if (n.zero()) return make_int(x.neg, nat(x.mag));
    // MAX_LONG_DIGITS, in CPython's 30-bit digits: past it, an OverflowError; below it, memory decides
    constexpr u128 MAX_LONG_DIGITS = (INT64_MAX - 1) / 30;
    u128 digits = (static_cast<u128>(bit_length_of(x.mag)) + 29) / 30 + n.mag[0] / 30 + (n.mag[0] % 30 != 0 ? 1 : 0);
    if (n.mag.size() > 1 || digits > MAX_LONG_DIGITS) raise_new("OverflowError", "too many digits in integer");
    if (n.mag[0] > (std::uint64_t{1} << 40)) throw NotImplemented("a left shift of over 2**40 bits");
    return make_int(x.neg, bn::shl(x.mag, static_cast<std::size_t>(n.mag[0])));
}
Ref right_shift(Obj a, Obj b) {                  // long_rshift: toward minus infinity
    IntView x(a), n(b);
    if (n.neg) raise_new("ValueError", "negative shift count");
    if (x.zero()) return Ref::steal(Obj::small(0));
    bool huge = n.mag.size() > 1 || (!n.mag.empty() && n.mag[0] >= bit_length_of(x.mag));
    auto count = huge ? std::size_t{0} : (n.mag.empty() ? std::size_t{0} : static_cast<std::size_t>(n.mag[0]));
    if (!x.neg) return huge ? Ref::steal(Obj::small(0)) : make_int(false, bn::shr(x.mag, count));
    if (huge) return Ref::steal(Obj::small(-1));
    const std::array<std::uint64_t, 1> unit{1};
    bn::Nat lessened = bn::sub(x.mag, unit);
    bn::Nat shifted = lessened.empty() ? bn::Nat{} : bn::shr(lessened, count);
    return make_int(true, bn::add(shifted, unit));
}
bn::Nat twos_complement(const IntView& v, std::size_t n) {
    bn::Nat out(n, 0);
    std::copy(v.mag.begin(), v.mag.end(), out.begin());
    if (v.neg) {
        for (auto& w : out) w = ~w;
        for (auto& w : out)
            if (++w != 0) break;
    }
    return out;
}
Ref bitwise(BinOp op, Obj a, Obj b) {            // infinite two's complement, one word past the longer
    IntView x(a), y(b);
    std::size_t n = std::max(x.mag.size(), y.mag.size()) + 1;
    bn::Nat l = twos_complement(x, n), r = twos_complement(y, n), out(n, 0);
    for (std::size_t i = 0; i < n; ++i) out[i] = op == BinOp::And ? l[i] & r[i] : op == BinOp::Or ? l[i] | r[i] : l[i] ^ r[i];
    bool neg = (out.back() & TOP_BIT) != 0;
    if (neg) {
        for (auto& w : out) w = ~w;
        for (auto& w : out)
            if (++w != 0) break;
    }
    return make_int(neg, std::move(out));
}

int& max_str_digits_setting() {
    static int digits = 4300;                    // _PY_LONG_DEFAULT_MAX_STR_DIGITS
    return digits;
}
[[noreturn]] void too_many_digits() {
    raise_new("ValueError", "Exceeds the limit (" + std::to_string(max_str_digits_setting()) +
                                " digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit");
}
std::string to_text(Obj v) {
    std::int64_t small;
    if (as_int(v, small)) return std::to_string(small);
    IntView x(v);
    int limit = max_str_digits_setting();
    if (limit > 0 && bn::digits(x.mag) > static_cast<std::size_t>(limit)) too_many_digits();
    std::string digits = bn::to_decimal(x.mag);
    return x.neg ? "-" + digits : digits;
}
std::string in_base(Obj v, int base) {           // PyNumber_ToBase: bases 2, 8, 16, with the prefix
    IntView x(v);
    const char* prefix = base == 2 ? "0b" : base == 8 ? "0o" : "0x";
    if (x.zero()) return std::string(prefix) + "0";
    int bits = base == 2 ? 1 : base == 8 ? 3 : 4;
    std::size_t total = bit_length_of(x.mag);
    std::string digits;
    for (std::size_t at = 0; at < total; at += static_cast<std::size_t>(bits)) {
        std::uint64_t word = x.mag[at / 64] >> (at % 64);
        if (at % 64 + static_cast<std::size_t>(bits) > 64 && at / 64 + 1 < x.mag.size()) word |= x.mag[at / 64 + 1] << (64 - at % 64);
        digits += "0123456789abcdef"[word & ((std::uint64_t{1} << bits) - 1)];
    }
    std::reverse(digits.begin(), digits.end());
    return (x.neg ? "-" : "") + std::string(prefix) + digits;
}
}  // namespace

// ---- what the runtime calls ----
Ref big_from_i64(std::int64_t v) {
    bool neg = v < 0;
    std::uint64_t m = neg ? static_cast<std::uint64_t>(-(v + 1)) + 1 : static_cast<std::uint64_t>(v);
    return own(new BigInt(neg, {m}));
}
bool int_is_negative(Obj v) { return IntView(v).neg; }
bool int_is_zero(Obj v) { return IntView(v).zero(); }
bool int_fits_i64(Obj v, std::int64_t& out) {
    if (as_int(v, out)) return true;
    if (!is_int(v)) return false;
    IntView x(v);
    if (x.mag.size() != 1) return false;
    if (!x.neg && x.mag[0] < TOP_BIT) { out = static_cast<std::int64_t>(x.mag[0]); return true; }
    if (x.neg && x.mag[0] <= TOP_BIT) { out = static_cast<std::int64_t>(~x.mag[0] + 1); return true; }
    return false;
}
std::string big_text(Obj v) { return to_text(v); }
Ref big_pow_mod(Obj a, Obj b, Obj mod) { return power_mod(a, b, mod); }
Ref big_binary(BinOp op, Obj a, Obj b) {
    switch (op) {
        case BinOp::Add: { IntView x(a), y(b); return add_signed(x.neg, x.mag, y.neg, y.mag); }
        case BinOp::Sub: { IntView x(a), y(b); return add_signed(x.neg, x.mag, !y.neg, y.mag); }
        case BinOp::Mul: { IntView x(a), y(b); return make_int(x.neg != y.neg, multiply(x.mag, y.mag)); }
        case BinOp::FloorDiv: return floor_divmod(a, b).first;
        case BinOp::Mod: return floor_divmod(a, b).second;
        case BinOp::Pow: return power(a, b);
        case BinOp::LShift: return left_shift(a, b);
        case BinOp::RShift: return right_shift(a, b);
        case BinOp::And: case BinOp::Or: case BinOp::Xor: return bitwise(op, a, b);
        case BinOp::TrueDiv: return int_true_divide(a, b);
        default: break;
    }
    raise_new("TypeError", "unsupported operand type(s): 'int' and 'int'");
}
// PyLong_AsDouble, rounded half to even: the top 64 bits with a sticky bit below them round as the whole does
double int_as_double(Obj v) {
    IntView x(v);
    std::size_t bits = bit_length_of(x.mag);
    if (bits > DBL_MAX_EXP) raise_new("OverflowError", "int too large to convert to float");
    double d = 0.0;
    if (bits <= 64) {
        d = x.mag.empty() ? 0.0 : static_cast<double>(x.mag[0]);
    } else {
        std::size_t drop = bits - 64;
        bn::Nat top = bn::shr(x.mag, drop);
        bool sticky = !bn::trimmed(bn::low_bits(x.mag, drop)).empty();
        d = std::ldexp(static_cast<double>(top[0] | (sticky ? 1 : 0)), static_cast<int>(drop));
    }
    if (std::isinf(d)) raise_new("OverflowError", "int too large to convert to float");
    return x.neg ? -d : d;
}
Ref int_from_double(double v) {                  // PyLong_FromDouble: its truncation
    if (std::isinf(v)) raise_new("OverflowError", "cannot convert float infinity to integer");
    if (std::isnan(v)) raise_new("ValueError", "cannot convert float NaN to integer");
    double t = std::trunc(v);
    if (std::fabs(t) < 0x1p62) return int_from_i64(static_cast<std::int64_t>(t));
    int e = 0;
    double m = std::frexp(std::fabs(t), &e);
    auto mantissa = static_cast<std::uint64_t>(std::ldexp(m, DBL_MANT_DIG));
    const std::array<std::uint64_t, 1> one{mantissa};
    bn::Nat shifted = bn::shl(one, static_cast<std::size_t>(e - DBL_MANT_DIG));
    bn::normalize(shifted);
    return make_int(t < 0, std::move(shifted));
}
Ref int_true_divide(Obj a, Obj b) {              // long_true_divide: exact until the last step
    IntView x(a), y(b);
    if (y.zero()) raise_new("ZeroDivisionError", "division by zero");
    bool negate = x.neg != y.neg;
    auto signed_zero = [&] { return float_ref(negate ? -0.0 : 0.0); };
    if (x.zero()) return signed_zero();
    std::size_t a_bits = bit_length_of(x.mag), b_bits = bit_length_of(y.mag);
    if (a_bits <= DBL_MANT_DIG && b_bits <= DBL_MANT_DIG) {   // both exact as doubles: the division rounds correctly
        double q = static_cast<double>(x.mag[0]) / static_cast<double>(y.mag[0]);
        return float_ref(negate ? -q : q);
    }
    auto overflow = []() -> Ref { raise_new("OverflowError", "integer division result too large for a float"); };
    auto diff = static_cast<std::int64_t>(a_bits) - static_cast<std::int64_t>(b_bits);
    if (diff > DBL_MAX_EXP) return overflow();
    if (diff < DBL_MIN_EXP - DBL_MANT_DIG - 1) return signed_zero();
    std::int64_t shift = std::max<std::int64_t>(diff, DBL_MIN_EXP) - DBL_MANT_DIG - 2;
    bool inexact = false;
    bn::Nat scaled;
    if (shift <= 0) {
        scaled = bn::shl(x.mag, static_cast<std::size_t>(-shift));
    } else {
        scaled = bn::shr(x.mag, static_cast<std::size_t>(shift));
        inexact = !bn::trimmed(bn::low_bits(x.mag, static_cast<std::size_t>(shift))).empty();
    }
    auto [q, r] = bn::div_rem(scaled, y.mag, nullptr);
    bn::normalize(q);
    bn::normalize(r);
    if (!r.empty()) inexact = true;
    std::uint64_t low = q.empty() ? 0 : q[0];    // at most DBL_MANT_DIG + 3 bits
    auto x_bits = static_cast<std::int64_t>(std::bit_width(low));
    std::int64_t extra_bits = std::max<std::int64_t>(x_bits, DBL_MIN_EXP - shift) - DBL_MANT_DIG;
    std::uint64_t mask = std::uint64_t{1} << (extra_bits - 1);
    std::uint64_t value = low | (inexact ? 1 : 0);
    if ((value & mask) != 0 && (value & (3 * mask - 1)) != 0) value += mask;
    value &= ~(2 * mask - 1);
    auto dx = static_cast<double>(value);
    if (shift + x_bits >= DBL_MAX_EXP && (shift + x_bits > DBL_MAX_EXP || dx == std::ldexp(1.0, static_cast<int>(x_bits)))) return overflow();
    double result = std::ldexp(dx, static_cast<int>(shift));
    return float_ref(negate ? -result : result);
}
Ref big_negate(Obj v) { IntView x(v); return make_int(!x.neg, nat(x.mag)); }
Ref big_absolute(Obj v) { IntView x(v); return make_int(false, nat(x.mag)); }
Ref big_plain(Obj v) { IntView x(v); return make_int(x.neg, nat(x.mag)); }
Ref big_invert(Obj v) {                          // ~x == -x - 1
    IntView x(v);
    const std::array<std::uint64_t, 1> unit{1};
    return add_signed(!x.neg, x.mag, true, unit);
}
int big_compare(Obj a, Obj b) {
    IntView x(a), y(b);
    if (x.neg != y.neg) return x.neg ? -1 : 1;
    int c = bn::cmp(x.mag, y.mag);
    return x.neg ? -c : c;
}
std::int64_t big_hash(Obj v) {                   // long_hash: modulo 2**61 - 1, with the sign; -1 is reserved
    IntView x(v);
    constexpr std::uint64_t M = (std::uint64_t{1} << 61) - 1;
    u128 acc = 0;
    for (std::size_t i = x.mag.size(); i-- > 0;) acc = ((acc << 64) | x.mag[i]) % M;
    auto h = static_cast<std::int64_t>(acc);
    if (x.neg) h = -h;
    return h == -1 ? -2 : h;
}
Ref int_from_digits(bool negative, std::string_view digits, int base) {
    auto value = [](char c) { return c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10; };
    if (digits.size() <= (base == 10 ? 18u : 12u)) {    // 10**18 and 36**12 fit 63 bits
        std::int64_t small = 0;
        for (char c : digits) small = small * base + value(c);
        return int_from_i64(negative ? -small : small);
    }
    bn::Nat acc;
    if (base == 10) {
        acc = bn::from_decimal(digits);
    } else if ((base & (base - 1)) == 0) {
        int bits = 0;
        while ((1 << bits) < base) ++bits;
        acc.assign(digits.size() * static_cast<std::size_t>(bits) / 64 + 1, 0);
        std::size_t at = 0;
        for (std::size_t i = digits.size(); i-- > 0; at += static_cast<std::size_t>(bits)) {
            auto d = static_cast<std::uint64_t>(value(digits[i]));
            acc[at / 64] |= d << (at % 64);
            if (at % 64 + static_cast<std::size_t>(bits) > 64) acc[at / 64 + 1] |= d >> (64 - at % 64);
        }
    } else {
        for (char c : digits) {
            std::uint64_t carry = acc.empty() ? 0 : bn::mul_1(acc, static_cast<std::uint64_t>(base));
            if (carry != 0) acc.push_back(carry);
            auto d = static_cast<std::uint64_t>(value(c));
            if (d != 0) {
                if (acc.empty()) acc.push_back(0);
                const std::array<std::uint64_t, 1> word{d};
                if (bn::add_in(acc, word)) acc.push_back(1);
            }
        }
    }
    return make_int(negative, std::move(acc));
}
int max_str_digits() { return max_str_digits_setting(); }
Obj big_int_constant(const char* literal) {       // a module's constant; the module's table keeps the count
    std::string_view text(literal);
    bool neg = text.starts_with('-');
    if (neg) text.remove_prefix(1);
    int base = text.starts_with("0x") ? 16 : 10;
    if (base == 16) text.remove_prefix(2);
    return int_from_digits(neg, text, base).release();
}

// ---- the builtins ----
namespace {
// _PyArg_UnpackKeywords for these names, the first npos positional; what is absent stays unset
void unpack(Args a, const std::string& name, std::initializer_list<const char*> params, std::size_t npos, std::vector<Obj>& given) {
    if (a.npos > npos) {
        if (npos == params.size())
            raise_new("TypeError", name + "() takes at most " + std::to_string(npos) + " argument" + (npos == 1 ? "" : "s") + " (" + std::to_string(a.npos + a.nkw) + " given)");
        raise_new("TypeError", name + "() takes at most " + std::to_string(npos) + " positional argument" + (npos == 1 ? "" : "s") + " (" + std::to_string(a.npos) + " given)");
    }
    if (a.npos + a.nkw > params.size())
        raise_new("TypeError", name + "() takes at most " + std::to_string(params.size()) + " arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    given.assign(params.size(), Obj{});
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::size_t j = 0;
        for (const char* p : params) {
            if (a.kwnames[k]->text == p) break;
            ++j;
        }
        if (j == params.size())      // CPython's message may suggest a keyword (_Py_CalculateSuggestions)
            throw NotImplemented(name + "() with an unexpected keyword argument (the suggestion in its message)");
        if (!given[j].is_unset())
            raise_new("TypeError", "argument for " + name + "() given by name ('" + a.kwnames[k]->text + "') and position (" + std::to_string(j + 1) + ")");
        given[j] = a.kw(k);
    }
}
template <int base>
Ref to_base(Obj, Args a) {                       // bin, oct, hex
    onearg(a, base == 2 ? "bin" : base == 8 ? "oct" : "hex");
    Ref i = int_index_of(a.pos(0));
    return str_new(in_base(i.get(), base));
}
Ref b_divmod(Obj, Args a) {                      // PyNumber_Divmod: binary_op1 over nb_divmod
    clinic(a, "divmod", "divmod", 2, 2);
    Obj x = a.pos(0), y = a.pos(1);
    ClassObject* tx = type_of(x);
    ClassObject* ty = type_of(y);
    bool found = false, reversed_first = false;
    if (tx != ty && is_subclass(ty, tx) && type_lookup(ty, N("__rdivmod__")) != type_lookup(tx, N("__rdivmod__"))) {
        reversed_first = true;
        Ref r = call_special(y, "__rdivmod__", {x}, &found);
        if (found && r.get() != Obj::of(NOTIMPLEMENTED)) return r;
    }
    Ref left = call_special(x, "__divmod__", {y}, &found);
    if (found && left.get() != Obj::of(NOTIMPLEMENTED)) return left;
    if (!reversed_first && tx != ty) {
        Ref r = call_special(y, "__rdivmod__", {x}, &found);
        if (found && r.get() != Obj::of(NOTIMPLEMENTED)) return r;
    }
    raise_new("TypeError", "unsupported operand type(s) for divmod(): '" + tx->name + "' and '" + ty->name + "'");
}
Ref b_pow(Obj, Args a) {                         // builtin_pow_impl: pow(base, exp, mod=None)
    std::vector<Obj> given;
    unpack(a, "pow", {"base", "exp", "mod"}, 3, given);
    if (given[0].is_unset()) raise_new("TypeError", "pow() missing required argument 'base' (pos 1)");
    if (given[1].is_unset()) raise_new("TypeError", "pow() missing required argument 'exp' (pos 2)");
    if (given[2].is_unset() || given[2] == None()) return binary(BinOp::Pow, given[0], given[1]);
    // ternary_op: a three-argument power is the first operand's alone (slot_nb_power never reflects)
    bool found = false;
    Ref r = call_special(given[0], "__pow__", {given[1], given[2]}, &found);
    if (found && r.get() != Obj::of(NOTIMPLEMENTED)) return r;
    for (Obj other : {given[1], given[2]}) {        // but a built-in's slot takes its turn: float_pow says no for all three, complex_pow if it may
        if (is_complex(other)) {
            Ref power = complex_power(given[0], given[1], given[2]);
            if (power.get() != Obj::of(NOTIMPLEMENTED)) return power;
        } else if (is_float(other)) {
            raise_new("TypeError", "pow() 3rd argument not allowed unless all arguments are integers");
        }
    }
    raise_new("TypeError", "unsupported operand type(s) for ** or pow(): '" + type_of(given[0])->name + "', '" + type_of(given[1])->name + "', '" + type_of(given[2])->name + "'");
}
Ref b_round(Obj, Args a) {                       // builtin_round_impl
    std::vector<Obj> given;
    unpack(a, "round", {"number", "ndigits"}, 2, given);
    if (given[0].is_unset()) raise_new("TypeError", "round() missing required argument 'number' (pos 1)");
    if (type_lookup(type_of(given[0]), N("__round__")).is_unset()) {
        refuse_absent_attribute(given[0], N("__round__"));
        raise_new("TypeError", "type " + type_of(given[0])->name + " doesn't define __round__ method");
    }
    if (given[1].is_unset() || given[1] == None()) return call_special(given[0], "__round__", {});
    return call_special(given[0], "__round__", {given[1]});
}

// ---- int's own methods ----
Ref plain_m(Obj self, Args a) {
    noargs(a, "int.conjugate");
    return big_plain(self);
}
Ref real_get(Obj self) { return big_plain(self); }
Ref imag_get(Obj) { return Ref::steal(Obj::small(0)); }
Ref denominator_get(Obj) { return Ref::steal(Obj::small(1)); }
Ref bit_length_m(Obj self, Args a) {
    noargs(a, "int.bit_length");
    IntView x(self);
    return int_from_i64(static_cast<std::int64_t>(bit_length_of(x.mag)));
}
Ref bit_count_m(Obj self, Args a) {
    noargs(a, "int.bit_count");
    IntView x(self);
    std::int64_t n = 0;
    for (std::uint64_t w : x.mag) n += std::popcount(w);
    return int_from_i64(n);
}
Ref is_integer_m(Obj, Args a) {
    noargs(a, "int.is_integer");
    return Ref::steal(boolean(true));
}
Ref as_integer_ratio_m(Obj self, Args a) {
    noargs(a, "int.as_integer_ratio");
    Ref plain = big_plain(self);
    return tuple_new({plain.get(), Obj::small(1)});
}
Ref getnewargs_m(Obj self, Args a) {
    noargs(a, "int.__getnewargs__");
    Ref plain = big_plain(self);
    return tuple_new({plain.get()});
}
bool little_order(Obj order, const char* name) {
    if (order.is_unset()) return false;          // byteorder="big"
    const Str* t = as_str(order);
    if (t == nullptr) raise_new("TypeError", std::string(name) + "() argument 'byteorder' must be str, not " + type_of(order)->name);
    if (t->text == "little") return true;
    if (t->text == "big") return false;
    raise_new("ValueError", "byteorder must be either 'little' or 'big'");
}
Ref to_bytes_m(Obj self, Args a) {               // int_to_bytes_impl: (length=1, byteorder='big', *, signed=False)
    std::vector<Obj> given;
    unpack(a, "to_bytes", {"length", "byteorder", "signed"}, 2, given);
    std::int64_t size = given[0].is_unset() ? 1 : ssize_arg(given[0]);
    if (size < 0) raise_new("ValueError", "length cannot be negative");
    bool little = little_order(given[1], "to_bytes");
    bool is_signed = !given[2].is_unset() && truth(given[2]);
    IntView x(self);
    if (x.neg && !is_signed) raise_new("OverflowError", "can't convert negative int to unsigned");
    auto n = static_cast<std::size_t>(size);
    bn::Nat words = twos_complement(x, std::max(n / 8 + 1, x.mag.size() + 1));
    std::string out(n, '\0');
    for (std::size_t i = 0; i < n; ++i) out[i] = static_cast<char>(words[i / 8] >> (8 * (i % 8)));
    // what is left above the bytes must be the sign's extension, and a signed top byte must say the same sign
    bool fits = true;
    unsigned char fill = x.neg ? 0xFF : 0;
    for (std::size_t i = n; i < words.size() * 8; ++i)
        if (static_cast<unsigned char>(words[i / 8] >> (8 * (i % 8))) != fill) fits = false;
    if (is_signed && (n == 0 ? !x.zero() : (static_cast<unsigned char>(out[n - 1]) >= 0x80) != x.neg)) fits = false;
    if (!fits) raise_new("OverflowError", "int too big to convert");
    if (!little) std::reverse(out.begin(), out.end());
    return bytes_new(out);
}
Ref object_bytes(Obj v) {                         // PyObject_Bytes: what bytes() takes, but a number is no count here
    if (is_bytes_like(v)) return Ref::share(v);
    if (!type_lookup(type_of(v), N("__bytes__")).is_unset()) return invoke(Obj::of(types().bytes), {v});
    if (as_str(v) == nullptr) {
        Ref it;
        try {
            it = iter(v);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        }
        if (!it.get().is_unset()) {
            Ref items = invoke(Obj::of(types().list), {it.get()});
            return invoke(Obj::of(types().bytes), {items.get()});
        }
    }
    raise_new("TypeError", "cannot convert '" + type_of(v)->name + "' object to bytes");
}
Ref from_bytes_m(Obj cls, Args a) {              // int_from_bytes_impl: (bytes, byteorder='big', *, signed=False)
    std::vector<Obj> given;
    unpack(a, "from_bytes", {"bytes", "byteorder", "signed"}, 2, given);
    if (given[0].is_unset()) raise_new("TypeError", "from_bytes() missing required argument 'bytes' (pos 1)");
    bool little = little_order(given[1], "from_bytes");
    bool is_signed = !given[2].is_unset() && truth(given[2]);
    Ref data = object_bytes(given[0]);
    std::string text = bytes_data(data.get());
    if (!little) std::reverse(text.begin(), text.end());
    bn::Nat words(text.size() / 8 + 1, 0);
    for (std::size_t i = 0; i < text.size(); ++i) words[i / 8] |= static_cast<std::uint64_t>(static_cast<unsigned char>(text[i])) << (8 * (i % 8));
    bool neg = is_signed && !text.empty() && static_cast<unsigned char>(text.back()) >= 0x80;
    if (neg) {                                   // two's complement of the n bytes: 2**(8n) - value
        bn::normalize(words);
        bn::Nat top(text.size() / 8 + 1, 0);
        top[text.size() / 8] = std::uint64_t{1} << (8 * (text.size() % 8));
        words = bn::sub(top, words);
    }
    Ref value = make_int(neg, std::move(words));
    if (cls == Obj::of(types().int_)) return value;
    return invoke(cls, {value.get()});
}

// ---- sys ----
Ref set_digits(Obj, Args a) {                    // sys.set_int_max_str_digits(maxdigits)
    std::vector<Obj> given;
    unpack(a, "set_int_max_str_digits", {"maxdigits"}, 1, given);
    if (given[0].is_unset()) raise_new("TypeError", "set_int_max_str_digits() missing required argument 'maxdigits' (pos 1)");
    Ref i = int_index_of(given[0]);
    std::int64_t n;
    if (!int_fits_i64(i.get(), n) || n > INT32_MAX || n < INT32_MIN) raise_new("OverflowError", "Python int too large to convert to C int");
    if (n != 0 && n < 640) raise_new("ValueError", "maxdigits must be >= 640 or 0 for unlimited");
    max_str_digits_setting() = static_cast<int>(n);
    return none_ref();
}
Ref get_digits(Obj, Args a) {
    noargs(a, "get_int_max_str_digits");
    return int_from_i64(max_str_digits_setting());
}
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
}  // namespace

Ref big_divmod(Obj a, Obj b) {
    auto [q, r] = floor_divmod(a, b);
    return tuple_new({q.get(), r.get()});
}
Ref int_round(Obj self, Obj ndigits) {           // long_round: half to even at 10**-ndigits
    Ref plain = big_plain(self);
    if (ndigits.is_unset() || ndigits == None()) return plain;
    Ref digits = int_index_of(ndigits);
    if (!IntView(digits.get()).neg) return plain;
    Ref ten = Ref::steal(Obj::small(10));
    Ref p = power(ten.get(), big_negate(digits.get()).get());
    auto [q, r] = floor_divmod(plain.get(), p.get());
    Ref twice = big_binary(BinOp::Mul, r.get(), Ref::steal(Obj::small(2)).get());
    int c = big_compare(twice.get(), p.get());
    Ref down = big_binary(BinOp::Sub, plain.get(), r.get());
    if (c > 0 || (c == 0 && IntView(q.get()).odd())) return big_binary(BinOp::Add, down.get(), p.get());
    return down;
}
static void put_function(Dict* d, const char* name, NativeFn fn) {
    Ref f = own(new Builtin(name, fn));
    dict_set(d, Obj::of(N(name)), f.get());
}
Ref slice_indices_m(Obj self, Args a);
void fill_int_builtins(Dict* builtins) {
    put_function(builtins, "bin", to_base<2>);
    put_function(builtins, "oct", to_base<8>);
    put_function(builtins, "hex", to_base<16>);
    put_function(builtins, "divmod", b_divmod);
    put_function(builtins, "pow", b_pow);
    put_function(builtins, "round", b_round);
}
void fill_int_sys(Dict* sys) {
    put_function(sys, "set_int_max_str_digits", set_digits);
    put_function(sys, "get_int_max_str_digits", get_digits);
}
std::string int_in_base(Obj v, int base) { return in_base(v, base); }
void init_bigint() {
    ClassObject* i = types().int_;
    method(i, "__format__", int_format_dunder);
    method(types().slice, "indices", slice_indices_m);
    method(i, "conjugate", plain_m);
    method(i, "bit_length", bit_length_m);
    method(i, "bit_count", bit_count_m);
    method(i, "is_integer", is_integer_m);
    method(i, "as_integer_ratio", as_integer_ratio_m);
    method(i, "__getnewargs__", getnewargs_m);
    method(i, "to_bytes", to_bytes_m);
    method(i, "from_bytes", from_bytes_m, Binding::ClassMethod);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{
             {"real", real_get}, {"imag", imag_get}, {"numerator", real_get}, {"denominator", denominator_get}})
        i->attrs.set(N(name), Obj::of(new GetSet(name, i, get, nullptr)));
}

// ---- range past 64 bits (Objects/rangeobject.c: its fields are Python ints) ----
namespace {
Ref obj_add(Obj a, Obj b) { return big_binary(BinOp::Add, a, b); }
Ref obj_sub(Obj a, Obj b) { return big_binary(BinOp::Sub, a, b); }
Ref obj_mul(Obj a, Obj b) { return big_binary(BinOp::Mul, a, b); }
Ref obj_floordiv(Obj a, Obj b) { return big_binary(BinOp::FloorDiv, a, b); }
Ref one() { return Ref::steal(Obj::small(1)); }
Ref zero() { return Ref::steal(Obj::small(0)); }
Ref range_length_of(Obj start, Obj stop, Obj step) {   // compute_range_length
    bool up = !IntView(step).neg;
    Obj lo = up ? start : stop, hi = up ? stop : start;
    Ref s = up ? Ref::share(step) : big_negate(step);
    if (big_compare(lo, hi) >= 0) return zero();
    Ref diff = obj_sub(obj_sub(hi, lo).get(), one().get());
    return obj_add(obj_floordiv(diff.get(), s.get()).get(), one().get());
}
Range* range_of(Obj v) { return static_cast<Range*>(v.object()); }
Ref long_range_iterator(Obj start, Obj step, Obj length) {
    Ref state = list_new({start, step, length});
    return own(new Iterator(Iterator::LongRangeIt, state.get()));
}
}  // namespace

Ref range_from_ints(Obj start, Obj stop, Obj step) {   // make_range_object; a zero step is validate_step's
    if (IntView(step).zero()) raise_new("ValueError", "range() arg 3 must not be zero");
    std::int64_t a, b, c;
    bool fit = int_fits_i64(start, a) && int_fits_i64(stop, b) && int_fits_i64(step, c);
    if (fit) {
        using Wide = __int128;
        Wide n = 0;
        if (c > 0 && a < b) n = (Wide{b} - a - 1) / c + 1;
        else if (c < 0 && a > b) n = (Wide{a} - b - 1) / -Wide{c} + 1;
        if (n <= INT64_MAX) return own(new Range(a, b, c));
    }
    Ref length = range_length_of(start, stop, step);
    auto* r = new Range(0, 0, 1);
    Ref out = own(r);
    std::int64_t n;
    r->big = true;
    r->bstart = big_plain(start);
    r->bstop = big_plain(stop);
    r->bstep = big_plain(step);
    r->blength = length;
    r->length = int_fits_i64(length.get(), n) ? n : INT64_MAX;
    return out;
}
Ref range_field(Obj self, int which) {
    auto* r = range_of(self);
    if (r->big) return Ref::share((which == 0 ? r->bstart : which == 1 ? r->bstop : r->bstep).get());
    return int_from_i64(which == 0 ? r->start : which == 1 ? r->stop : r->step);
}
Ref range_length_big(Obj self) {
    auto* r = range_of(self);
    return r->big ? Ref::share(r->blength.get()) : int_from_i64(r->length);
}
Ref range_item(Obj self, Obj index) {            // compute_range_item: start + i * step, against the length
    auto* r = range_of(self);
    Ref length = range_length_big(self);
    Ref i = Ref::share(index);
    if (IntView(i.get()).neg) i = obj_add(length.get(), i.get());
    if (IntView(i.get()).neg || big_compare(i.get(), length.get()) >= 0)
        raise_new("IndexError", "range object index out of range");
    std::int64_t k;
    if (!r->big && as_int(i.get(), k)) {         // the common case, with no int made along the way
        auto at = static_cast<std::uint64_t>(r->start) + static_cast<std::uint64_t>(r->step) * static_cast<std::uint64_t>(k);
        return int_from_i64(static_cast<std::int64_t>(at));
    }
    Ref start = range_field(self, 0), step = range_field(self, 2);
    return obj_add(start.get(), obj_mul(i.get(), step.get()).get());
}
// _PySlice_GetLongIndices: (start, stop, step) for a sequence of this length, over Python ints
static std::array<Ref, 3> long_indices(Obj slice, Obj length) {
    auto* s = static_cast<SliceObject*>(slice.object());
    auto index = [](Obj v) {                     // evaluate_slice_index
        if (!is_int(v) && type_lookup(type_of(v), N("__index__")).is_unset())
            raise_new("TypeError", "slice indices must be integers or None or have an __index__ method");
        return int_index_of(v);
    };
    Ref step = s->step == None() ? one() : index(s->step);
    if (IntView(step.get()).zero()) raise_new("ValueError", "slice step cannot be zero");
    bool backwards = IntView(step.get()).neg;
    Ref lower = backwards ? Ref::steal(Obj::small(-1)) : zero();
    Ref upper = backwards ? obj_add(length, lower.get()) : Ref::share(length);
    auto bound = [&](Obj v, Obj dflt) -> Ref {
        if (v == None()) return Ref::share(dflt);
        Ref x = index(v);
        if (IntView(x.get()).neg) {
            x = obj_add(x.get(), length);
            if (big_compare(x.get(), lower.get()) < 0) return Ref::share(lower.get());
            return x;
        }
        if (big_compare(x.get(), upper.get()) > 0) return Ref::share(upper.get());
        return x;
    };
    Ref first = bound(s->start, backwards ? upper.get() : lower.get());
    Ref last = bound(s->stop, backwards ? lower.get() : upper.get());
    return {std::move(first), std::move(last), std::move(step)};
}
Ref range_slice(Obj self, Obj slice) {           // compute_slice
    Ref start_f = range_field(self, 0), step_f = range_field(self, 2), length = range_length_big(self);
    auto [first, last, step] = long_indices(slice, length.get());
    Ref new_step = obj_mul(step_f.get(), step.get());
    Ref new_start = obj_add(start_f.get(), obj_mul(first.get(), step_f.get()).get());
    Ref new_stop = obj_add(start_f.get(), obj_mul(last.get(), step_f.get()).get());
    return range_from_ints(new_start.get(), new_stop.get(), new_step.get());
}
Ref slice_indices_m(Obj self, Args a) {          // slice_indices
    onearg(a, "slice.indices");
    Ref length = int_index_of(a.pos(0));
    if (IntView(length.get()).neg) raise_new("ValueError", "length should not be negative");
    auto [first, last, step] = long_indices(self, length.get());
    return tuple_new({first.get(), last.get(), step.get()});
}
bool range_contains_int(Obj self, Obj item) {    // range_contains_long
    auto* r = range_of(self);
    std::int64_t x;
    if (!r->big && as_int(item, x)) {
        if (r->step > 0 ? (x < r->start || x >= r->stop) : (x > r->start || x <= r->stop)) return false;
        return (static_cast<__int128>(x) - r->start) % r->step == 0;
    }
    Ref start = range_field(self, 0), stop = range_field(self, 1), step = range_field(self, 2);
    bool up = !IntView(step.get()).neg;
    if (up ? (big_compare(start.get(), item) > 0 || big_compare(item, stop.get()) >= 0)
           : (big_compare(stop.get(), item) >= 0 || big_compare(item, start.get()) > 0))
        return false;
    Ref rem = big_binary(BinOp::Mod, obj_sub(item, start.get()).get(), step.get());
    return IntView(rem.get()).zero();
}
std::string big_range_repr(Obj self) {
    auto* r = range_of(self);
    std::string out = "range(" + to_text(r->bstart.get()) + ", " + to_text(r->bstop.get());
    if (big_compare(r->bstep.get(), one().get()) != 0) out += ", " + to_text(r->bstep.get());
    return out + ")";
}
bool range_equal(Obj a, Obj b) {                 // range_equals: by the values they produce
    Ref la = range_length_big(a), lb = range_length_big(b);
    if (big_compare(la.get(), lb.get()) != 0) return false;
    if (IntView(la.get()).zero()) return true;
    Ref sa = range_field(a, 0), sb = range_field(b, 0);
    if (big_compare(sa.get(), sb.get()) != 0) return false;
    if (big_compare(la.get(), one().get()) == 0) return true;
    Ref ta = range_field(a, 2), tb = range_field(b, 2);
    return big_compare(ta.get(), tb.get()) == 0;
}
Ref big_range_reversed(Obj self) {               // range_reverse's long_range
    Ref start = range_field(self, 0), step = range_field(self, 2), length = range_length_big(self);
    Ref last = obj_add(start.get(), obj_mul(obj_sub(length.get(), one().get()).get(), step.get()).get());
    return long_range_iterator(last.get(), big_negate(step.get()).get(), length.get());
}
Ref range_iter(Obj self) {
    auto* r = range_of(self);
    // the int version when the fields and the length are C longs and no value overflows one
    if (!r->big && (r->length == 0 || (r->step > 0 ? r->stop <= INT64_MAX - (r->step - 1) : r->stop >= INT64_MIN + (-1 - r->step))))
        return own(new Iterator(Iterator::RangeIt, self));
    Ref start = range_field(self, 0), step = range_field(self, 2), length = range_length_big(self);
    return long_range_iterator(start.get(), step.get(), length.get());
}
Ref long_range_next(std::vector<Obj>& state) {
    if (IntView(state[2]).zero()) return Ref{};
    Ref value = Ref::share(state[0]);
    Ref next = obj_add(state[0], state[1]);
    Ref left = obj_sub(state[2], one().get());
    decref(std::exchange(state[0], next.release()));
    decref(std::exchange(state[2], left.release()));
    return value;
}

}  // namespace bella
