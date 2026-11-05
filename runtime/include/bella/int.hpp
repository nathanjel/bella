// bella/int.hpp -- exact Python int: 63-bit tagged immediates with promotion (dialect spec, section 6;
// design document, section 6, as corrected by review round one, finding 5).
//
// The immediate fast paths, differentially tested against CPython (runtime/tests/int_differential.py).
// An operation whose result leaves [kMin, kMax] has two faces: try_add and its kin say so by returning
// false, and the runtime then computes it in runtime/src/bigint.cpp (no exception on a path a program
// may take in a loop); int_add and its kin, which the differential test drives, throw "promote".
#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

namespace bella {

struct NotImplemented : std::logic_error {
    using std::logic_error::logic_error;
};
struct ZeroDivisionError : std::runtime_error {
    using std::runtime_error::runtime_error;
};
struct ValueError : std::runtime_error {      // Python's ValueError (e.g. a negative shift count)
    using std::runtime_error::runtime_error;
};

class Int {
    std::uintptr_t w_;   // bit 0 = 1: signed 63-bit immediate (value << 1 | 1); bit 0 = 0: BigInt* (unused yet)
    explicit constexpr Int(std::uintptr_t raw) : w_(raw) {}
public:
    static constexpr std::int64_t kMin = -(std::int64_t{1} << 62);
    static constexpr std::int64_t kMax = (std::int64_t{1} << 62) - 1;

    constexpr Int() : w_(1u) {}                                   // 0
    constexpr Int(std::int64_t v) : w_(from_small(v).w_) {}       // NOLINT: implicit on purpose for literals
    constexpr Int(int v) : Int(static_cast<std::int64_t>(v)) {}
    constexpr Int(bool v) : w_(v ? 3u : 1u) {}
    static constexpr Int from_small(std::int64_t v) {
        if (v < kMin || v > kMax) throw NotImplemented("BigInt: value outside the 63-bit immediate range");
        return Int{(static_cast<std::uintptr_t>(v) << 1) | 1u};
    }
    static constexpr Int raw(std::int64_t tagged) { return Int{static_cast<std::uintptr_t>(tagged)}; }

    constexpr bool is_small() const { return w_ & 1u; }
    constexpr std::int64_t small() const { return static_cast<std::int64_t>(w_) >> 1; }
    constexpr std::int64_t tagged() const { return static_cast<std::int64_t>(w_); }

    friend constexpr bool operator==(Int a, Int b) { return a.w_ == b.w_; }
    friend constexpr bool operator!=(Int a, Int b) { return a.w_ != b.w_; }
    friend constexpr bool operator<(Int a, Int b) { return a.small() < b.small(); }
    friend constexpr bool operator<=(Int a, Int b) { return a.small() <= b.small(); }
    friend constexpr bool operator>(Int a, Int b) { return a.small() > b.small(); }
    friend constexpr bool operator>=(Int a, Int b) { return a.small() >= b.small(); }
};

namespace bigint {
[[noreturn]] inline Int promote(const char* op) {
    throw NotImplemented(std::string("BigInt: ") + op + " left the 63-bit immediate range");
}
}  // namespace bigint

inline bool try_add(Int a, Int b, Int& out) {
    // (2x+1) + (2y+1) - 1 = 2(x+y)+1: one add on the tagged words, one overflow check
    std::int64_t r;
    if (__builtin_add_overflow(a.tagged(), b.tagged() - 1, &r)) return false;
    out = Int::raw(r);
    return true;
}
inline bool try_sub(Int a, Int b, Int& out) {
    std::int64_t r;
    if (__builtin_sub_overflow(a.tagged(), b.tagged() - 1, &r)) return false;
    out = Int::raw(r);
    return true;
}
inline bool try_mul(Int a, Int b, Int& out) {
    std::int64_t r;
    if (__builtin_mul_overflow(a.small(), b.small(), &r) || r < Int::kMin || r > Int::kMax) return false;
    out = Int::from_small(r);
    return true;
}
inline Int int_add(Int a, Int b) { Int r; return try_add(a, b, r) ? r : bigint::promote("add"); }
inline Int int_sub(Int a, Int b) { Int r; return try_sub(a, b, r) ? r : bigint::promote("sub"); }
inline Int int_mul(Int a, Int b) { Int r; return try_mul(a, b, r) ? r : bigint::promote("mul"); }
inline Int int_neg(Int a) {
    if (a.small() == Int::kMin) return bigint::promote("neg");   // -kMin = 2^62 does not fit
    return Int::from_small(-a.small());
}
inline bool try_floordiv(Int a, Int b, Int& out) {
    const std::int64_t x = a.small(), y = b.small();
    if (y == 0) throw ZeroDivisionError("division by zero");      // CPython 3.15's text
    if (x == Int::kMin && y == -1) return false;                  // quotient 2^62 leaves the tagged range
    std::int64_t q = x / y;
    const std::int64_t r = x % y;
    if (r != 0 && ((r < 0) != (y < 0))) --q;   // floor toward minus infinity
    out = Int::from_small(q);                  // fits once the kMin / -1 case is excluded above
    return true;
}
inline Int int_floordiv(Int a, Int b) { Int r; return try_floordiv(a, b, r) ? r : bigint::promote("floordiv"); }
inline Int int_mod(Int a, Int b) {
    const std::int64_t x = a.small(), y = b.small();
    if (y == 0) throw ZeroDivisionError("division by zero");
    if (y == -1) return Int::from_small(0);    // also avoids kMin % -1, which traps in C++
    std::int64_t r = x % y;
    if (r != 0 && ((r < 0) != (y < 0))) r += y;   // sign follows the divisor
    return Int::from_small(r);
}
inline bool try_lshift(Int a, Int b, Int& out) {
    const std::int64_t x = a.small(), n = b.small();
    if (n < 0) throw ValueError("negative shift count");
    if (x == 0) {
        out = Int::from_small(0);
        return true;
    }
    if (n >= 64) return false;
    const __int128 r = static_cast<__int128>(x) << n;          // GCC extension; the project is GCC-only
    if (r < Int::kMin || r > Int::kMax) return false;
    out = Int::from_small(static_cast<std::int64_t>(r));
    return true;
}
inline Int int_lshift(Int a, Int b) { Int r; return try_lshift(a, b, r) ? r : bigint::promote("lshift"); }
inline Int int_rshift(Int a, Int b) {
    const std::int64_t n = b.small();
    if (n < 0) throw ValueError("negative shift count");
    return Int::from_small(n >= 63 ? (a.small() < 0 ? -1 : 0) : (a.small() >> n));
}
inline Int int_and(Int a, Int b) { return Int::from_small(a.small() & b.small()); }
inline Int int_or(Int a, Int b)  { return Int::from_small(a.small() | b.small()); }
inline Int int_xor(Int a, Int b) { return Int::from_small(a.small() ^ b.small()); }
inline Int int_invert(Int a)     { return Int::from_small(~a.small()); }
inline bool try_pow(Int a, Int b, Int& out) {    // a square that overflows is a factor of the result, unless a is 0
    std::int64_t e = b.small();
    if (e < 0) throw NotImplemented("int ** negative exponent returns float");
    Int result = Int::from_small(1), base = a;
    while (e > 0) {
        if ((e & 1) && !try_mul(result, base, result)) return false;
        e >>= 1;
        if (e > 0 && !try_mul(base, base, base)) return false;
    }
    out = result;
    return true;
}
inline Int int_pow(Int a, Int b) { Int r; return try_pow(a, b, r) ? r : bigint::promote("pow"); }

inline bool truth(Int a) { return a.small() != 0; }
inline bool truth(bool b) { return b; }
inline std::string to_string(Int a) { return std::to_string(a.small()); }

// Operators so that generated code reads like the Python it came from.
inline Int operator+(Int a, Int b) { return int_add(a, b); }
inline Int operator-(Int a, Int b) { return int_sub(a, b); }
inline Int operator*(Int a, Int b) { return int_mul(a, b); }
inline Int operator-(Int a) { return int_neg(a); }
inline Int operator&(Int a, Int b) { return int_and(a, b); }
inline Int operator|(Int a, Int b) { return int_or(a, b); }
inline Int operator^(Int a, Int b) { return int_xor(a, b); }
inline Int operator~(Int a) { return int_invert(a); }
inline Int operator<<(Int a, Int b) { return int_lshift(a, b); }
inline Int operator>>(Int a, Int b) { return int_rshift(a, b); }

}  // namespace bella
