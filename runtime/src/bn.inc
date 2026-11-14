// bn: unsigned big numbers in 64-bit words, for `int` (runtime/src/bigint.cpp is the Python layer).
//
// A copy of SEL's `bn`, sel/cpp/sel.cpp at commit f6df7ff, the author's own code under MIT (decision of
// 2026-11-02, docs/licences.md L-05). Each change is named here, so that fixes can be ported back.
// Included into `namespace bella` by bigint.cpp.
//   2026-11-14  BN_LOOK(): a host's hook in the loops whose work can be long (a row of a basecase product or
//               square, a word of a long division's quotient); nothing unless the includer defines it. Bella looks
//               for signals there, where CPython's x_mul and x_divrem do (D-25 (e)); it may throw, and every
//               caller holds what it owns in objects that give it back.

#ifndef BN_LOOK
#define BN_LOOK() ((void)0)
#endif

namespace bn {

using Nat = std::vector<std::uint64_t>;
using Span = std::span<const std::uint64_t>;
using Out = std::span<std::uint64_t>;

constexpr std::size_t KARATSUBA = 32;
constexpr std::size_t KARATSUBA_SQR = 48;
// Divisor and quotient both at least this long: Barrett reduction, when the
// divisor's reciprocal is cached (a power of five) ...
constexpr std::size_t BARRETT_CACHED = 160;
// ... or has to be computed for this one division.
constexpr std::size_t BARRETT_FRESH = 2560;
// Newton's recursion for a reciprocal ends in long division below this.
constexpr std::size_t RECIP_BASE = 32;
// Decimal conversion below this many words (digits) is word by word.
constexpr std::size_t DEC_LEAF_WORDS = 12;
constexpr std::size_t DEC_LEAF_DIGITS = 19 * DEC_LEAF_WORDS;
// 10^19, the largest power of ten in a word.
constexpr std::uint64_t TEN19 = 10000000000000000000ULL;
// floor(log10(2) * 2^64).
constexpr u128 LOG10_2_Q64 = 5553023288523357132ULL;
// Cached powers of five, in words, before the cache starts over.
constexpr std::size_t POW5_CACHE_WORDS = std::size_t{1} << 21;
constexpr u128 WORD_MAX = std::numeric_limits<std::uint64_t>::max();

// ---- words

inline Span trimmed(Span a) {
  std::size_t n = a.size();
  while (n > 0 && a[n - 1] == 0) --n;
  return a.first(n);
}

inline void normalize(Nat& v) {
  while (!v.empty() && v.back() == 0) v.pop_back();
}

// Orders two trimmed magnitudes.
inline int cmp(Span a, Span b) {
  if (a.size() != b.size()) return a.size() < b.size() ? -1 : 1;
  for (std::size_t i = a.size(); i-- > 0;) {
    if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return 0;
}

// acc += b, acc at least as long as b; whether a carry left acc.
inline bool add_in(Out acc, Span b) {
  std::uint64_t carry = 0;
  for (std::size_t i = 0; i < b.size(); ++i) {
    const u128 t = static_cast<u128>(acc[i]) + b[i] + carry;
    acc[i] = static_cast<std::uint64_t>(t);
    carry = static_cast<std::uint64_t>(t >> 64);
  }
  for (std::size_t i = b.size(); carry != 0 && i < acc.size(); ++i) {
    acc[i] += 1;
    carry = acc[i] == 0;
  }
  return carry != 0;
}

// acc -= b, acc at least as long as b; whether a borrow left acc.
inline bool sub_in(Out acc, Span b) {
  std::uint64_t borrow = 0;
  for (std::size_t i = 0; i < b.size(); ++i) {
    // Wrapping: a borrow leaves the high half all ones.
    const u128 t = static_cast<u128>(acc[i]) - b[i] - borrow;
    acc[i] = static_cast<std::uint64_t>(t);
    borrow = static_cast<std::uint64_t>(t >> 127);
  }
  for (std::size_t i = b.size(); borrow != 0 && i < acc.size(); ++i) {
    borrow = acc[i] == 0;
    acc[i] -= 1;
  }
  return borrow != 0;
}

Nat add(Span a, Span b) {
  const Span lng = a.size() >= b.size() ? a : b;
  const Span sht = a.size() >= b.size() ? b : a;
  Nat out;
  out.reserve(lng.size() + 1);
  out.assign(lng.begin(), lng.end());
  if (add_in(out, sht)) out.push_back(1);
  return out;
}

// a - b, for a >= b.
Nat sub(Span a, Span b) {
  Nat out(a.begin(), a.end());
  if (sub_in(out, b)) throw std::logic_error("unsigned mantissa subtraction underflow");
  normalize(out);
  return out;
}

#if SEL_BN_ADX
// Whether the CPU has MULX (BMI2) and ADCX/ADOX (ADX): CPUID leaf 7, EBX bits 8
// and 19. Read once, at load time; before that it is zero-initialised, and
// false is the portable loop, so even a product computed from another
// translation unit's static initialiser is correct.
const bool HAVE_ADX = [] {
  unsigned eax = 0, ebx = 0, ecx = 0, edx = 0;
  if (__get_cpuid_count(7, 0, &eax, &ebx, &ecx, &edx) == 0) return false;
  return (ebx & (1u << 8)) != 0 && (ebx & (1u << 19)) != 0;
}();

// acc[0..8) += a[0..8) * m + carry; the word carried out. The product's low
// words and the previous high word go in on the CF chain (ADCX), acc on the
// OF chain (ADOX): two independent carry chains, which is what makes this
// about 1.5 times the portable loop's speed. The sum fits: acc + a m + carry
// < 2^(64*9), so the carry out is one word and both chains end in it.
inline std::uint64_t addmul_8_adx(std::uint64_t* acc, const std::uint64_t* a, std::uint64_t m,
                                  std::uint64_t carry) {
  std::uint64_t l0, h0, l1, h1, z;
  __asm__(
      "xorl %k[z], %k[z]\n\t"
      "mulxq 0(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[c], %[l0]\n\t"
      "adoxq 0(%[acc]), %[l0]\n\t"
      "movq %[l0], 0(%[acc])\n\t"
      "mulxq 8(%[a]), %[l1], %[h1]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 8(%[acc]), %[l1]\n\t"
      "movq %[l1], 8(%[acc])\n\t"
      "mulxq 16(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[h1], %[l0]\n\t"
      "adoxq 16(%[acc]), %[l0]\n\t"
      "movq %[l0], 16(%[acc])\n\t"
      "mulxq 24(%[a]), %[l1], %[h1]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 24(%[acc]), %[l1]\n\t"
      "movq %[l1], 24(%[acc])\n\t"
      "mulxq 32(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[h1], %[l0]\n\t"
      "adoxq 32(%[acc]), %[l0]\n\t"
      "movq %[l0], 32(%[acc])\n\t"
      "mulxq 40(%[a]), %[l1], %[h1]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 40(%[acc]), %[l1]\n\t"
      "movq %[l1], 40(%[acc])\n\t"
      "mulxq 48(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[h1], %[l0]\n\t"
      "adoxq 48(%[acc]), %[l0]\n\t"
      "movq %[l0], 48(%[acc])\n\t"
      "mulxq 56(%[a]), %[l1], %[c]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 56(%[acc]), %[l1]\n\t"
      "movq %[l1], 56(%[acc])\n\t"
      "adcxq %[z], %[c]\n\t"
      "adoxq %[z], %[c]\n\t"
      : [l0] "=&r"(l0), [h0] "=&r"(h0), [l1] "=&r"(l1), [h1] "=&r"(h1), [z] "=&r"(z), [c] "+&r"(carry),
        "+m"(*reinterpret_cast<std::uint64_t(*)[8]>(acc))
      : [a] "r"(a), [acc] "r"(acc), "d"(m), "m"(*reinterpret_cast<const std::uint64_t(*)[8]>(a))
      : "cc");
  return carry;
}

// The same for four words.
inline std::uint64_t addmul_4_adx(std::uint64_t* acc, const std::uint64_t* a, std::uint64_t m,
                                  std::uint64_t carry) {
  std::uint64_t l0, h0, l1, h1, z;
  __asm__(
      "xorl %k[z], %k[z]\n\t"
      "mulxq 0(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[c], %[l0]\n\t"
      "adoxq 0(%[acc]), %[l0]\n\t"
      "movq %[l0], 0(%[acc])\n\t"
      "mulxq 8(%[a]), %[l1], %[h1]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 8(%[acc]), %[l1]\n\t"
      "movq %[l1], 8(%[acc])\n\t"
      "mulxq 16(%[a]), %[l0], %[h0]\n\t"
      "adcxq %[h1], %[l0]\n\t"
      "adoxq 16(%[acc]), %[l0]\n\t"
      "movq %[l0], 16(%[acc])\n\t"
      "mulxq 24(%[a]), %[l1], %[c]\n\t"
      "adcxq %[h0], %[l1]\n\t"
      "adoxq 24(%[acc]), %[l1]\n\t"
      "movq %[l1], 24(%[acc])\n\t"
      "adcxq %[z], %[c]\n\t"
      "adoxq %[z], %[c]\n\t"
      : [l0] "=&r"(l0), [h0] "=&r"(h0), [l1] "=&r"(l1), [h1] "=&r"(h1), [z] "=&r"(z), [c] "+&r"(carry),
        "+m"(*reinterpret_cast<std::uint64_t(*)[4]>(acc))
      : [a] "r"(a), [acc] "r"(acc), "d"(m), "m"(*reinterpret_cast<const std::uint64_t(*)[4]>(a))
      : "cc");
  return carry;
}
#endif

// acc[..a.size()] += a * m; the word carried out.
inline std::uint64_t addmul_1(Out acc, Span a, std::uint64_t m) {
  std::uint64_t carry = 0;
  std::size_t i = 0;
#if SEL_BN_ADX
  if (HAVE_ADX) {
    for (; i + 8 <= a.size(); i += 8) carry = addmul_8_adx(&acc[i], &a[i], m, carry);
    if (i + 4 <= a.size()) {
      carry = addmul_4_adx(&acc[i], &a[i], m, carry);
      i += 4;
    }
  }
#endif
  for (; i < a.size(); ++i) {
    const u128 t = static_cast<u128>(a[i]) * m + acc[i] + carry;
    acc[i] = static_cast<std::uint64_t>(t);
    carry = static_cast<std::uint64_t>(t >> 64);
  }
  return carry;
}

// Where Karatsuba takes over from the schoolbook rows: the thresholds above
// (the Rust host's) for the portable rows; with the ADX rows, which are about
// 1.5 times as fast, the crossover moves up to 64 words for a product and 96
// for a square (measured in-process, best of 15, from 32 to 266 words: the
// 133-word square 8% and product 10% faster than at 48 and 32).
inline std::size_t karatsuba_mul_at() {
#if SEL_BN_ADX
  if (HAVE_ADX) return 64;
#endif
  return KARATSUBA;
}

inline std::size_t karatsuba_sqr_at() {
#if SEL_BN_ADX
  if (HAVE_ADX) return 96;
#endif
  return KARATSUBA_SQR;
}

// acc[..a.size()] -= a * m; the word borrowed out.
inline std::uint64_t submul_1(Out acc, Span a, std::uint64_t m) {
  std::uint64_t borrow = 0;
  for (std::size_t i = 0; i < a.size(); ++i) {
    const u128 t = static_cast<u128>(a[i]) * m + borrow;
    const std::uint64_t lo = static_cast<std::uint64_t>(t);
    const std::uint64_t under = acc[i] < lo;
    acc[i] -= lo;
    borrow = static_cast<std::uint64_t>(t >> 64) + under;
  }
  return borrow;
}

// a *= m; the word carried out.
inline std::uint64_t mul_1(Out a, std::uint64_t m) {
  std::uint64_t carry = 0;
  for (std::uint64_t& x : a) {
    const u128 t = static_cast<u128>(x) * m + carry;
    x = static_cast<std::uint64_t>(t);
    carry = static_cast<std::uint64_t>(t >> 64);
  }
  return carry;
}

// (hi:lo) / d and its remainder, for hi < d (so the quotient is one word). One
// divq on x86-64, where GCC would lower the u128 division to a library call;
// the portable expression elsewhere.
inline std::uint64_t div_2by1(std::uint64_t hi, std::uint64_t lo, std::uint64_t d, std::uint64_t& rem) {
#if defined(__x86_64__)
  std::uint64_t q, r;
  __asm__("divq %4" : "=a"(q), "=d"(r) : "a"(lo), "d"(hi), "rm"(d));
  rem = r;
  return q;
#else
  const u128 t = static_cast<u128>(hi) << 64 | lo;
  rem = static_cast<std::uint64_t>(t % d);
  return static_cast<std::uint64_t>(t / d);
#endif
}

// a /= d (d > 0); the remainder.
inline std::uint64_t div_1(Out a, std::uint64_t d) {
  std::uint64_t r = 0;
  for (std::size_t i = a.size(); i-- > 0;) {
    std::uint64_t next;
    a[i] = div_2by1(r, a[i], d, next);
    r = next;
  }
  return r;
}

// a mod d (d > 0).
inline std::uint64_t rem_1(Span a, std::uint64_t d) {
  std::uint64_t r = 0;
  for (std::size_t i = a.size(); i-- > 0;) {
    std::uint64_t next;
    div_2by1(r, a[i], d, next);
    r = next;
  }
  return r;
}

// a << bits for bits < 64: one word longer, not trimmed.
Nat shl_bits(Span a, unsigned bits) {
  Nat out;
  out.reserve(a.size() + 1);
  if (bits == 0) {
    out.assign(a.begin(), a.end());
    out.push_back(0);
    return out;
  }
  std::uint64_t carry = 0;
  for (const std::uint64_t x : a) {
    out.push_back(x << bits | carry);
    carry = x >> (64 - bits);
  }
  out.push_back(carry);
  return out;
}

// a >> bits for bits < 64, trimmed.
Nat shr_bits(Span a, unsigned bits) {
  Nat out(a.begin(), a.end());
  if (bits != 0) {
    for (std::size_t i = 0; i < out.size(); ++i) {
      const std::uint64_t high = i + 1 < a.size() ? a[i + 1] << (64 - bits) : 0;
      out[i] = a[i] >> bits | high;
    }
  }
  normalize(out);
  return out;
}

// a << k, trimmed.
Nat shl(Span a, std::size_t k) {
  if (a.empty()) return {};
  // One allocation: the zero words, then a shifted in place after them.
  const std::size_t words = k / 64;
  const unsigned bits = static_cast<unsigned>(k % 64);
  Nat out(words + a.size() + 1, 0);
  if (bits == 0) {
    std::copy(a.begin(), a.end(), out.begin() + static_cast<std::ptrdiff_t>(words));
  } else {
    std::uint64_t carry = 0;
    for (std::size_t i = 0; i < a.size(); ++i) {
      out[words + i] = a[i] << bits | carry;
      carry = a[i] >> (64 - bits);
    }
    out[words + a.size()] = carry;
  }
  normalize(out);
  return out;
}

// a >> k, trimmed.
Nat shr(Span a, std::size_t k) {
  if (k / 64 >= a.size()) return {};
  return shr_bits(a.subspan(k / 64), static_cast<unsigned>(k % 64));
}

// a mod 2^k, trimmed.
Nat low_bits(Span a, std::size_t k) {
  const std::size_t words = k / 64, bits = k % 64;
  Nat out(a.begin(), a.begin() + std::min(a.size(), words + 1));
  if (out.size() > words) {
    if (bits == 0) {
      out.resize(words);
    } else {
      out[words] &= (std::uint64_t{1} << bits) - 1;
    }
  }
  normalize(out);
  return out;
}

inline std::size_t bit_len(Span a) {
  return a.empty() ? 0 : a.size() * 64 - static_cast<std::size_t>(__builtin_clzll(a.back()));
}

// For a nonzero a.
inline std::size_t trailing_zero_bits(Span a) {
  std::size_t i = 0;
  while (a[i] == 0) ++i;
  return i * 64 + static_cast<std::size_t>(__builtin_ctzll(a[i]));
}

// ---- multiplication

// Karatsuba's temporaries, reused from product to product.
thread_local Nat scratch_cache;

// Words of scratch a product of `n` result words may need: each Karatsuba
// level holds under 2.5n words and hands its children at most 2n/3.
inline std::size_t scratch_len(std::size_t n) { return 8 * n + 512; }

template <class F>
void with_scratch(std::size_t len, F&& f) {
  // Taken out of the cache, so a nested product (none today) would simply
  // allocate its own. Every user zeroes the part it uses.
  Nat buf = std::move(scratch_cache);
  scratch_cache = Nat();
  if (buf.size() < len) buf.resize(len);
  struct GiveBack {
    Nat& b;
    ~GiveBack() {
      if (scratch_cache.size() < b.size()) scratch_cache = std::move(b);
    }
  } give_back{buf};
  f(Out(buf.data(), len));
}

// out = a * b by rows; out zeroed and at least a.size() + b.size() long.
void basecase_mul(Out out, Span a, Span b) {
  for (std::size_t j = 0; j < b.size(); ++j) {
    BN_LOOK();
    if (b[j] != 0) out[j + a.size()] = addmul_1(out.subspan(j), a, b[j]);
  }
}

// out = a^2; out zeroed and at least 2 a.size() long. Each cross product once,
// doubled, then the squares of the words on the diagonal.
void basecase_sqr(Out out, Span a) {
  const std::size_t n = a.size();
  for (std::size_t i = 0; i + 1 < n; ++i) {
    BN_LOOK();
    out[i + n] = addmul_1(out.subspan(2 * i + 1), a.subspan(i + 1), a[i]);
  }
  std::uint64_t top = 0;
  for (std::size_t i = 0; i < 2 * n; ++i) {
    const std::uint64_t x = out[i];
    out[i] = x << 1 | top;
    top = x >> 63;
  }
  std::uint64_t carry = 0;
  for (std::size_t i = 0; i < n; ++i) {
    const u128 sq = static_cast<u128>(a[i]) * a[i];
    const u128 lo = static_cast<u128>(out[2 * i]) + static_cast<std::uint64_t>(sq) + carry;
    out[2 * i] = static_cast<std::uint64_t>(lo);
    const u128 hi = static_cast<u128>(out[2 * i + 1]) + static_cast<std::uint64_t>(sq >> 64) +
                    static_cast<std::uint64_t>(lo >> 64);
    out[2 * i + 1] = static_cast<std::uint64_t>(hi);
    carry = static_cast<std::uint64_t>(hi >> 64);
  }
}

// d = |a - b| in d.size() == a.size() >= b.size() words; how a compares to b.
int abs_diff_into(Out d, Span a, Span b) {
  a = trimmed(a);
  b = trimmed(b);
  const int ord = cmp(a, b);
  std::fill(d.begin(), d.end(), 0);
  if (ord == 0) return 0;
  const Span big = ord > 0 ? a : b;
  const Span small = ord > 0 ? b : a;
  std::copy(big.begin(), big.end(), d.begin());
  sub_in(d, small);
  return ord;
}

void karatsuba(Out out, Span x, Span y, Out scratch);

// out = a * b. out is zeroed and one word longer than the product (Karatsuba's
// intermediate sums use it and leave it zero); `scratch` holds the rest.
void mul_into(Out out, Span a, Span b, Out scratch) {
  if (a.size() < b.size()) std::swap(a, b);
  if (b.empty()) return;
  if (b.size() < karatsuba_mul_at()) {
    basecase_mul(out, a, b);
  } else if (a.size() >= 2 * b.size()) {
    // Unbalanced: the long factor in pieces as long as the short one.
    const std::size_t n = b.size();
    const Out tmp = scratch.first(2 * n + 1);
    const Out rest = scratch.subspan(2 * n + 1);
    for (std::size_t k = 0; k * n < a.size(); ++k) {
      const Span piece = trimmed(a.subspan(k * n, std::min(n, a.size() - k * n)));
      if (piece.empty()) continue;
      const Out t = tmp.first(piece.size() + n + 1);
      std::fill(t.begin(), t.end(), 0);
      mul_into(t, piece, b, rest);
      add_in(out.subspan(k * n), trimmed(t));
    }
  } else {
    karatsuba(out, a, b, scratch);
  }
}

// x * y for y.size() <= x.size() < 2 y.size(): with x = x0 + x1 B^h and
// y = y0 + y1 B^h, xy = x0 y0 (1 + B^h) + x1 y1 (B^h + B^2h) - (x1 - x0)(y1 - y0) B^h.
void karatsuba(Out out, Span x, Span y, Out scratch) {
  const std::size_t h = y.size() / 2;
  const Span x0 = trimmed(x.first(h)), x1 = x.subspan(h);
  const Span y0 = trimmed(y.first(h)), y1 = y.subspan(h);
  const Out t0 = scratch.first(2 * h + 1);
  const Out t2 = scratch.subspan(2 * h + 1, x1.size() + y1.size() + 1);
  const Out rest = scratch.subspan(2 * h + 1 + x1.size() + y1.size() + 1);
  std::fill(t0.begin(), t0.end(), 0);
  std::fill(t2.begin(), t2.end(), 0);
  mul_into(t0, x0, y0, rest);
  mul_into(t2, x1, y1, rest);
  const Span s0 = trimmed(t0), s2 = trimmed(t2);
  std::copy(s0.begin(), s0.end(), out.begin());
  std::copy(s2.begin(), s2.end(), out.begin() + static_cast<std::ptrdiff_t>(2 * h));
  add_in(out.subspan(h), s0);
  add_in(out.subspan(h), s2);
  const Out dx = rest.first(x1.size());
  const Out dy = rest.subspan(x1.size(), y1.size());
  const int sx = abs_diff_into(dx, x1, x0);
  const int sy = abs_diff_into(dy, y1, y0);
  if (sx == 0 || sy == 0) return;
  const Span dxt = trimmed(dx), dyt = trimmed(dy);
  const Out after = rest.subspan(x1.size() + y1.size());
  const Out p = after.first(dxt.size() + dyt.size() + 1);
  std::fill(p.begin(), p.end(), 0);
  mul_into(p, dxt, dyt, after.subspan(p.size()));
  if (sx == sy) {
    sub_in(out.subspan(h), trimmed(p));
  } else {
    add_in(out.subspan(h), trimmed(p));
  }
}

// out = a^2, out zeroed and 2 a.size() + 1 long: Karatsuba's squaring,
// a^2 = a0^2 (1 + B^h) + a1^2 (B^h + B^2h) - (a1 - a0)^2 B^h.
void sqr_into(Out out, Span a, Out scratch) {
  if (a.size() < karatsuba_sqr_at()) {
    basecase_sqr(out, a);
    return;
  }
  const std::size_t h = a.size() / 2;
  const Span a0 = trimmed(a.first(h)), a1 = a.subspan(h);
  const Out t0 = scratch.first(2 * h + 1);
  const Out t2 = scratch.subspan(2 * h + 1, 2 * a1.size() + 1);
  const Out rest = scratch.subspan(2 * h + 1 + 2 * a1.size() + 1);
  std::fill(t0.begin(), t0.end(), 0);
  std::fill(t2.begin(), t2.end(), 0);
  sqr_into(t0, a0, rest);
  sqr_into(t2, a1, rest);
  const Span s0 = trimmed(t0), s2 = trimmed(t2);
  std::copy(s0.begin(), s0.end(), out.begin());
  std::copy(s2.begin(), s2.end(), out.begin() + static_cast<std::ptrdiff_t>(2 * h));
  add_in(out.subspan(h), s0);
  add_in(out.subspan(h), s2);
  const Out d = rest.first(a1.size());
  if (abs_diff_into(d, a1, a0) == 0) return;
  const Span dt = trimmed(d);
  const Out after = rest.subspan(a1.size());
  const Out p = after.first(2 * dt.size() + 1);
  std::fill(p.begin(), p.end(), 0);
  sqr_into(p, dt, after.subspan(p.size()));
  sub_in(out.subspan(h), trimmed(p));
}

// The last two squares of large operands, per thread. Squaring the same value
// twice in a row is common -- `x * x` in a test and again in the expression it
// guards, as in an escape-time loop -- and recognising the operand costs one
// pass over it where the square costs a quadratic one (or Karatsuba's).
// Bounded: operands of SQR_MEMO_MIN to SQR_MEMO_MAX words only, two of them;
// below the minimum a square costs about what the lookup and the copy would.
constexpr std::size_t SQR_MEMO_MIN = 16;
constexpr std::size_t SQR_MEMO_MAX = std::size_t{1} << 14;

struct SqrMemo {
  Nat operand;
  Nat square;
};

thread_local std::array<SqrMemo, 2> sqr_memo;
thread_local unsigned sqr_memo_next = 0;

Nat sqr(Span a) {
  a = trimmed(a);
  const bool memo = a.size() >= SQR_MEMO_MIN && a.size() <= SQR_MEMO_MAX;
  if (memo) {
    for (const SqrMemo& m : sqr_memo) {
      if (m.operand.size() == a.size() && std::equal(a.begin(), a.end(), m.operand.begin())) return m.square;
    }
  }
  const std::size_t n = 2 * a.size() + 1;
  Nat out(n, 0);
  if (a.size() < karatsuba_sqr_at()) {
    basecase_sqr(out, a);
  } else {
    with_scratch(scratch_len(n), [&](Out s) { sqr_into(out, a, s); });
  }
  normalize(out);
  if (memo) {
    SqrMemo& m = sqr_memo[sqr_memo_next];
    sqr_memo_next ^= 1;
    m.operand.assign(a.begin(), a.end());
    m.square = out;
  }
  return out;
}

Nat mul(Span a, Span b) {
  a = trimmed(a);
  b = trimmed(b);
  if (a.empty() || b.empty()) return {};
  // A square costs about half a product: a value times an equal one (zr * zr,
  // reading the same variable twice) takes that road.
  if (a.size() == b.size() && std::equal(a.begin(), a.end(), b.begin())) return sqr(a);
  if (a.size() == 1 || b.size() == 1) {
    const Span lng = b.size() == 1 ? a : b;
    const std::uint64_t m = b.size() == 1 ? b[0] : a[0];
    Nat out(lng.begin(), lng.end());
    const std::uint64_t carry = mul_1(out, m);
    if (carry != 0) out.push_back(carry);
    return out;
  }
  const std::size_t n = a.size() + b.size() + 1;
  Nat out(n, 0);
  if (std::min(a.size(), b.size()) < karatsuba_mul_at()) {
    if (a.size() >= b.size()) {
      basecase_mul(out, a, b);
    } else {
      basecase_mul(out, b, a);
    }
  } else {
    with_scratch(scratch_len(n), [&](Out s) { mul_into(out, a, b, s); });
  }
  normalize(out);
  return out;
}

// ---- division

// Knuth's algorithm D (TAOCP 4.3.1) for a divisor of two words or more and
// u.size() >= v.size(): quotient and remainder, trimmed.
std::pair<Nat, Nat> knuth_div(Span u, Span v) {
  const unsigned shift = static_cast<unsigned>(__builtin_clzll(v.back()));
  Nat vn = shl_bits(v, shift);
  vn.pop_back();
  Nat un = shl_bits(u, shift);
  const std::size_t n = vn.size();
  const std::size_t m = un.size() - n - 1;
  Nat q(m + 1, 0);
  const u128 vtop = vn[n - 1], vnext = vn[n - 2];
  for (std::size_t j = m + 1; j-- > 0;) {
    BN_LOOK();
    // The estimate from the top two words: a one-word division while the top
    // word is below the divisor's (the normalised top word bounds it), else
    // B - 1 (Hacker's Delight's divmnu; the same answers as dividing the
    // 128-bit numerator and stepping down from B).
    u128 qhat, rhat;
    if (un[j + n] < vn[n - 1]) {
      std::uint64_t r64;
      qhat = div_2by1(un[j + n], un[j + n - 1], vn[n - 1], r64);
      rhat = r64;
    } else {
      qhat = WORD_MAX;
      rhat = static_cast<u128>(un[j + n - 1]) + vn[n - 1];
    }
    while (rhat <= WORD_MAX && qhat * vnext > (rhat << 64 | un[j + n - 2])) {
      --qhat;
      rhat += vtop;
    }
    const std::uint64_t borrow = submul_1(Out(un).subspan(j, n), vn, static_cast<std::uint64_t>(qhat));
    const bool under = un[j + n] < borrow;
    un[j + n] -= borrow;
    if (under) {
      --qhat;
      const bool carry = add_in(Out(un).subspan(j, n), vn);
      un[j + n] += carry ? 1 : 0;
    }
    q[j] = static_cast<std::uint64_t>(qhat);
  }
  normalize(q);
  return {std::move(q), shr_bits(Span(un).first(n), shift)};
}

// A divisor prepared for Barrett reduction: shifted until its top bit is set
// (`v`, n words), with r = floor(B^2n / v).
struct Recip {
  unsigned shift = 0;
  Nat v;
  Nat r;
};

Nat shl_words(Span a, std::size_t k) {
  if (a.empty()) return {};
  Nat out(k, 0);
  out.insert(out.end(), a.begin(), a.end());
  return out;
}

Nat shr_words(Span a, std::size_t k) {
  if (k >= a.size()) return {};
  return Nat(a.begin() + static_cast<std::ptrdiff_t>(k), a.end());
}

// floor(B^2n / v) for v of n words with its top bit set. Newton's iteration
// from the reciprocal of v's top half: x1 = x0 + x0 (B^2n - v x0) / B^2n
// doubles the correct words, then a product fixes the last unit or two.
Nat reciprocal(Span v) {
  const std::size_t n = v.size();
  Nat b2n(2 * n + 1, 0);
  b2n[2 * n] = 1;
  if (n <= RECIP_BASE) return knuth_div(b2n, v).first;
  const std::size_t h = n / 2 + 1;
  const Nat rh = reciprocal(v.subspan(n - h));
  // x0 = rh B^(n-h): its low n-h words are zero, so v x0 = (v rh) B^(n-h).
  Nat x = shl_words(rh, n - h);
  const Nat vx = shl_words(mul(v, rh), n - h);
  const bool negative = cmp(vx, b2n) > 0;
  const Nat e = negative ? sub(vx, b2n) : sub(b2n, vx);
  // x0 e / B^2n = rh e / B^(n+h); e's low words cannot move the result by a unit.
  const Nat t = shr_words(mul(rh, shr_words(e, n - 1)), h + 1);
  x = negative ? sub(x, t) : add(x, t);
  const Nat one{1};
  Nat p = mul(v, x);
  while (cmp(p, b2n) > 0) {
    x = sub(x, one);
    p = sub(p, v);
  }
  for (;;) {
    const Nat rest = sub(b2n, p);
    if (cmp(rest, v) < 0) break;
    x = add(x, one);
    p = add(p, v);
  }
  return x;
}

Recip make_recip(Span d) {
  Recip rec;
  rec.shift = static_cast<unsigned>(__builtin_clzll(d.back()));
  rec.v = shl_bits(d, rec.shift);
  rec.v.pop_back();
  rec.r = reciprocal(rec.v);
  return rec;
}

// x < v B^n for the prepared v of n words: floor(x / v) and x mod v. Barrett
// (HAC 14.42): the estimate is at most two short.
std::pair<Nat, Nat> barrett_step(Span x, const Recip& rec) {
  const std::size_t n = rec.v.size();
  if (cmp(x, rec.v) < 0) return {Nat{}, Nat(x.begin(), x.end())};
  const Span q1 = x.subspan(std::min(n - 1, x.size()));
  Nat q = shr_words(mul(q1, rec.r), n + 1);
  Nat r = sub(x, mul(q, rec.v));
  const Nat one{1};
  while (cmp(r, rec.v) >= 0) {
    r = sub(r, rec.v);
    q = add(q, one);
  }
  return {std::move(q), std::move(r)};
}

// u / d with d prepared: long division in base B^n, one Barrett step per block.
std::pair<Nat, Nat> barrett_div(Span u, const Recip& rec) {
  const std::size_t n = rec.v.size();
  Nat us = shl_bits(u, rec.shift);
  normalize(us);
  const std::size_t blocks = (us.size() + n - 1) / n;
  Nat q(blocks * n, 0);
  Nat r;
  for (std::size_t b = blocks; b-- > 0;) {
    const std::size_t lo = b * n;
    const std::size_t hi = std::min(lo + n, us.size());
    Nat x(us.begin() + static_cast<std::ptrdiff_t>(lo), us.begin() + static_cast<std::ptrdiff_t>(hi));
    x.resize(n, 0);
    x.insert(x.end(), r.begin(), r.end());
    normalize(x);
    auto [qb, rb] = barrett_step(x, rec);
    std::copy(qb.begin(), qb.end(), q.begin() + static_cast<std::ptrdiff_t>(lo));
    r = std::move(rb);
  }
  normalize(q);
  return {std::move(q), shr_bits(r, rec.shift)};
}

// 5^k, trimmed, with its reciprocal made on first use.
struct Power {
  Nat value;
  mutable std::optional<Recip> recip;
  const Recip& rec() const {
    if (!recip) recip = make_recip(value);
    return *recip;
  }
};

// Quotient and remainder of trimmed u and v, v nonzero; `power` supplies a
// cached reciprocal when v is a power of five.
std::pair<Nat, Nat> div_rem(Span u, Span v, const Power* power) {
  if (v.empty()) throw std::logic_error("unsigned mantissa division by zero");
  if (cmp(u, v) < 0) return {Nat{}, Nat(u.begin(), u.end())};
  if (v.size() == 1) {
    Nat q(u.begin(), u.end());
    const std::uint64_t r = div_1(q, v[0]);
    normalize(q);
    return {std::move(q), r == 0 ? Nat{} : Nat{r}};
  }
  const std::size_t n = v.size(), m = u.size() - v.size();
  if (power != nullptr && n >= BARRETT_CACHED && m >= BARRETT_CACHED) return barrett_div(u, power->rec());
  if (power == nullptr && n >= BARRETT_FRESH && m >= BARRETT_FRESH) return barrett_div(u, make_recip(v));
  return knuth_div(u, v);
}

// ---- powers of five and ten

struct Pow5Cache {
  std::unordered_map<std::size_t, std::shared_ptr<const Power>> map;
  std::size_t words = 0;
};

thread_local Pow5Cache pow5_cache;

// 5^k, cached with its halves.
std::shared_ptr<const Power> pow5(std::size_t k) {
  if (const auto it = pow5_cache.map.find(k); it != pow5_cache.map.end()) return it->second;
  auto p = std::make_shared<Power>();
  if (k <= 27) {
    std::uint64_t v = 1;
    for (std::size_t i = 0; i < k; ++i) v *= 5;
    p->value = {v};
  } else {
    const std::shared_ptr<const Power> half = pow5(k / 2);
    p->value = sqr(half->value);
    if (k % 2 == 1) {
      const std::uint64_t carry = mul_1(p->value, 5);
      if (carry != 0) p->value.push_back(carry);
    }
  }
  if (pow5_cache.words + p->value.size() > POW5_CACHE_WORDS) {
    pow5_cache.map.clear();
    pow5_cache.words = 0;
  }
  pow5_cache.words += p->value.size();
  pow5_cache.map.emplace(k, p);
  return p;
}

// 10^k for k <= 19.
constexpr std::uint64_t pow10_word(std::size_t k) {
  std::uint64_t p = 1;
  for (std::size_t i = 0; i < k; ++i) p *= 10;
  return p;
}

// a * 10^k = (a * 5^k) << k.
Nat mul_pow10(Span a, std::size_t k) {
  if (a.empty() || k == 0) return Nat(a.begin(), a.end());
  if (k <= 19) {
    Nat out(a.begin(), a.end());
    const std::uint64_t carry = mul_1(out, pow10_word(k));
    if (carry != 0) out.push_back(carry);
    return out;
  }
  return shl(mul(a, pow5(k)->value), k);
}

// a / 5^k and a mod 5^k.
std::pair<Nat, Nat> divmod_pow5(Span a, std::size_t k) {
  if (k <= 27) {
    std::uint64_t p = 1;
    for (std::size_t i = 0; i < k; ++i) p *= 5;
    Nat q(a.begin(), a.end());
    const std::uint64_t r = div_1(q, p);
    normalize(q);
    return {std::move(q), r == 0 ? Nat{} : Nat{r}};
  }
  const std::shared_ptr<const Power> p = pow5(k);
  return div_rem(a, p->value, p.get());
}

// a / 10^k and a mod 10^k: a >> k divided by 5^k, the low k bits kept.
std::pair<Nat, Nat> divmod_pow10(Span a, std::size_t k) {
  if (a.empty() || k == 0) return {Nat(a.begin(), a.end()), Nat{}};
  if (k <= 19) {
    Nat q(a.begin(), a.end());
    const std::uint64_t r = div_1(q, pow10_word(k));
    normalize(q);
    return {std::move(q), r == 0 ? Nat{} : Nat{r}};
  }
  auto [q, r5] = divmod_pow5(shr(a, k), k);
  const Nat low = low_bits(a, k);
  Nat r = shl(r5, k);
  if (r.size() < low.size()) r.resize(low.size(), 0);
  for (std::size_t i = 0; i < low.size(); ++i) r[i] |= low[i];
  normalize(r);
  return {std::move(q), std::move(r)};
}

// Whether a < 10^k: 10^k = 5^k 2^k, so a < 10^k exactly when a >> k < 5^k.
bool below_pow10(Span a, std::size_t k) {
  if (k <= 19) return a.size() <= 1 && (a.empty() ? 0 : a[0]) < pow10_word(k);
  if (bit_len(a) <= k) return true;
  return cmp(shr(a, k), pow5(k)->value) < 0;
}

// floor(b log10 2), and whether the Q64 constant proves it (it does unless
// b log10 2 lies within b / 2^64 of an integer).
std::pair<std::size_t, bool> floor_log10_pow2(std::size_t b) {
  const u128 f = static_cast<u128>(b) * LOG10_2_Q64;
  const bool exact = static_cast<u128>(static_cast<std::uint64_t>(f)) + b < (static_cast<u128>(1) << 64);
  return {static_cast<std::size_t>(f >> 64), exact};
}

// Bounds on the decimal digit count of a nonzero a from its bit length alone:
// 2^(b-1) <= a < 2^b.
std::pair<std::size_t, std::size_t> digit_bounds(Span a) {
  const std::size_t b = bit_len(a);
  const auto [lo, lo_exact] = floor_log10_pow2(b - 1);
  const auto [hi, hi_exact] = floor_log10_pow2(b);
  return {lo + 1, hi + 1 + ((lo_exact && hi_exact) ? 0 : 1)};
}

// The exact decimal digit count of a nonzero a.
std::size_t digits(Span a) {
  const auto [lo, hi] = digit_bounds(a);
  std::size_t d = lo;
  while (d < hi && !below_pow10(a, d)) ++d;
  return d;
}

// The number of decimal zeros ending a nonzero a, at most `cap`: the lesser of
// its factors of two (free, the low zero bits) and of five (found in strides
// that double while they divide).
std::size_t trailing_decimal_zeros(Span a, std::size_t cap) {
  cap = std::min(cap, trailing_zero_bits(a));
  if (cap == 0 || rem_1(a, 5) != 0) return 0;
  Nat x(a.begin(), a.end());
  std::size_t t = 0, stride = 1;
  for (;;) {
    if (t + stride <= cap) {
      auto [q, r] = divmod_pow5(x, stride);
      if (r.empty()) {
        x = std::move(q);
        t += stride;
        stride *= 2;
        continue;
      }
    }
    if (stride == 1) return t;
    stride /= 2;
  }
}

// ---- decimal text

// Where a decimal conversion of `len` digits splits: the largest 19 * 2^j that
// leaves the high part at least as long as the low one, so every split point is
// a power of ten the cache already holds.
std::size_t split_digits(std::size_t len) {
  std::size_t k = 19;
  while (4 * k <= len) k *= 2;
  return k;
}

// ASCII digits (validated by the caller) as a magnitude.
Nat from_decimal(std::string_view digits) {
  if (digits.size() <= DEC_LEAF_DIGITS) {
    Nat acc;
    std::size_t len = std::min(digits.size() % 19 == 0 ? std::size_t{19} : digits.size() % 19, digits.size());
    for (std::size_t start = 0; start < digits.size(); start += len, len = 19) {
      std::uint64_t chunk = 0;
      for (std::size_t i = start; i < start + len; ++i) chunk = chunk * 10 + static_cast<std::uint64_t>(digits[i] - '0');
      const std::uint64_t carry = mul_1(acc, pow10_word(len));
      if (carry != 0) acc.push_back(carry);
      if (chunk != 0) {
        if (acc.empty()) acc.push_back(0);
        const std::array<std::uint64_t, 1> word{chunk};
        if (add_in(acc, word)) acc.push_back(1);
      }
    }
    normalize(acc);
    return acc;
  }
  const std::size_t k = split_digits(digits.size());
  const Nat high = from_decimal(digits.substr(0, digits.size() - k));
  const Nat low = from_decimal(digits.substr(digits.size() - k));
  return add(mul_pow10(high, k), low);
}

// The digits of a < 10^len into out[0, len) (filled with '0' by the caller),
// right-aligned.
void write_decimal(Span a, char* out, std::size_t len) {
  if (a.size() <= DEC_LEAF_WORDS) {
    Nat cur(a.begin(), a.end());
    std::size_t end = len;
    while (!cur.empty()) {
      std::uint64_t r = div_1(cur, TEN19);
      normalize(cur);
      const std::size_t start = end >= 19 ? end - 19 : 0;
      for (std::size_t i = end; i-- > start;) {
        out[i] = static_cast<char>('0' + r % 10);
        r /= 10;
      }
      end = start;
    }
    return;
  }
  const std::size_t k = split_digits(len);
  const auto [q, r] = divmod_pow10(a, k);
  write_decimal(q, out, len - k);
  write_decimal(r, out + (len - k), k);
}

std::string to_decimal(Span a) {
  if (a.empty()) return "0";
  std::string out(digits(a), '0');
  write_decimal(a, out.data(), out.size());
  return out;
}

}  // namespace bn
