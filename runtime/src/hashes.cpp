// The digests behind _md5, _sha1, _sha2, _sha3, _blake2 and _hmac (runtime/prelude/*.py), written from their specifications:
// MD5 (RFC 1321), SHA-1 (RFC 3174), SHA-2 (FIPS 180-4), SHA-3 and SHAKE (FIPS 202), BLAKE2b and BLAKE2s (RFC 7693 with the
// full parameter block). A hash's state travels as bytes (a tag, then the algorithm's record), so a prelude object copies
// by copying bytes and the runtime keeps no object kind for it.
//   _hash_new(name, params) -> state      params: None, or blake2's (digest_size, key, salt, person, fanout, depth, leaf_size,
//                                         node_offset, node_depth, inner_size, last_node)
//   _hash_update(state, data) -> state
//   _hash_digest(state) -> bytes          the digest of the state as it stands (the state itself is not finalised)
//   _hash_xof(state, length) -> bytes     SHAKE's output of that length
#include "bella/runtime.hpp"

#include <array>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

namespace bella {
namespace {
enum class Algo : std::uint8_t { md5 = 1, sha1, sha224, sha256, sha384, sha512, sha3_224, sha3_256, sha3_384, sha3_512, shake_128, shake_256, blake2b, blake2s };

inline std::uint32_t rol32(std::uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }
inline std::uint32_t ror32(std::uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
inline std::uint64_t rol64(std::uint64_t x, int n) { return (x << n) | (x >> (64 - n)); }
inline std::uint64_t ror64(std::uint64_t x, int n) { return (x >> n) | (x << (64 - n)); }
inline std::uint32_t load32le(const std::uint8_t* p) { return p[0] | (std::uint32_t(p[1]) << 8) | (std::uint32_t(p[2]) << 16) | (std::uint32_t(p[3]) << 24); }
inline std::uint32_t load32be(const std::uint8_t* p) { return (std::uint32_t(p[0]) << 24) | (std::uint32_t(p[1]) << 16) | (std::uint32_t(p[2]) << 8) | p[3]; }
inline std::uint64_t load64le(const std::uint8_t* p) { return load32le(p) | (std::uint64_t(load32le(p + 4)) << 32); }
inline std::uint64_t load64be(const std::uint8_t* p) { return (std::uint64_t(load32be(p)) << 32) | load32be(p + 4); }
inline void store32le(std::uint8_t* p, std::uint32_t v) { for (int i = 0; i < 4; ++i) p[i] = static_cast<std::uint8_t>(v >> (8 * i)); }
inline void store32be(std::uint8_t* p, std::uint32_t v) { for (int i = 0; i < 4; ++i) p[3 - i] = static_cast<std::uint8_t>(v >> (8 * i)); }
inline void store64le(std::uint8_t* p, std::uint64_t v) { for (int i = 0; i < 8; ++i) p[i] = static_cast<std::uint8_t>(v >> (8 * i)); }
inline void store64be(std::uint8_t* p, std::uint64_t v) { for (int i = 0; i < 8; ++i) p[7 - i] = static_cast<std::uint8_t>(v >> (8 * i)); }

// ---- MD5 -----------------------------------------------------------------------------------------------------------------
struct Md5 {
    std::uint32_t h[4];
    std::uint64_t length;                        // bytes so far
    std::uint8_t buffer[64];
    std::uint32_t buffered;
};
const std::uint32_t MD5_K[64] = {
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501, 0x698098d8, 0x8b44f7af, 0xffff5bb1,
    0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821, 0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453,
    0xd8a1e681, 0xe7d3fbc8, 0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a, 0xfffa3942,
    0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70, 0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
    0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665, 0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d,
    0x85845dd1, 0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391};
const int MD5_S[64] = {7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
                       4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21};
void md5_init(Md5& s) { s.h[0] = 0x67452301; s.h[1] = 0xefcdab89; s.h[2] = 0x98badcfe; s.h[3] = 0x10325476; s.length = 0; s.buffered = 0; }
void md5_block(Md5& s, const std::uint8_t* p) {
    std::uint32_t m[16];
    for (int i = 0; i < 16; ++i) m[i] = load32le(p + 4 * i);
    std::uint32_t a = s.h[0], b = s.h[1], c = s.h[2], d = s.h[3];
    for (int i = 0; i < 64; ++i) {
        std::uint32_t f; int g;
        if (i < 16) { f = (b & c) | (~b & d); g = i; }
        else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
        else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
        else { f = c ^ (b | ~d); g = (7 * i) % 16; }
        std::uint32_t t = d; d = c; c = b;
        b = b + rol32(a + f + MD5_K[i] + m[g], MD5_S[i]);
        a = t;
    }
    s.h[0] += a; s.h[1] += b; s.h[2] += c; s.h[3] += d;
}

// ---- SHA-1 ------------------------------------------------------------------------------------------------------------------
struct Sha1 { std::uint32_t h[5]; std::uint64_t length; std::uint8_t buffer[64]; std::uint32_t buffered; };
void sha1_init(Sha1& s) { s.h[0] = 0x67452301; s.h[1] = 0xEFCDAB89; s.h[2] = 0x98BADCFE; s.h[3] = 0x10325476; s.h[4] = 0xC3D2E1F0; s.length = 0; s.buffered = 0; }
void sha1_block(Sha1& s, const std::uint8_t* p) {
    std::uint32_t w[80];
    for (int i = 0; i < 16; ++i) w[i] = load32be(p + 4 * i);
    for (int i = 16; i < 80; ++i) w[i] = rol32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    std::uint32_t a = s.h[0], b = s.h[1], c = s.h[2], d = s.h[3], e = s.h[4];
    for (int i = 0; i < 80; ++i) {
        std::uint32_t f, k;
        if (i < 20) { f = (b & c) | (~b & d); k = 0x5A827999; }
        else if (i < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
        else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
        else { f = b ^ c ^ d; k = 0xCA62C1D6; }
        std::uint32_t t = rol32(a, 5) + f + e + k + w[i];
        e = d; d = c; c = rol32(b, 30); b = a; a = t;
    }
    s.h[0] += a; s.h[1] += b; s.h[2] += c; s.h[3] += d; s.h[4] += e;
}

// ---- SHA-256 / SHA-224 --------------------------------------------------------------------------------------------------------
struct Sha256 { std::uint32_t h[8]; std::uint64_t length; std::uint8_t buffer[64]; std::uint32_t buffered; };
const std::uint32_t SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be,
    0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa,
    0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85,
    0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
    0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
void sha256_init(Sha256& s, bool is224) {
    static const std::uint32_t iv256[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    static const std::uint32_t iv224[8] = {0xc1059ed8, 0x367cd507, 0x3070dd17, 0xf70e5939, 0xffc00b31, 0x68581511, 0x64f98fa7, 0xbefa4fa4};
    std::memcpy(s.h, is224 ? iv224 : iv256, sizeof s.h);
    s.length = 0; s.buffered = 0;
}
void sha256_block(Sha256& s, const std::uint8_t* p) {
    std::uint32_t w[64];
    for (int i = 0; i < 16; ++i) w[i] = load32be(p + 4 * i);
    for (int i = 16; i < 64; ++i) {
        std::uint32_t s0 = ror32(w[i - 15], 7) ^ ror32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        std::uint32_t s1 = ror32(w[i - 2], 17) ^ ror32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    std::uint32_t a = s.h[0], b = s.h[1], c = s.h[2], d = s.h[3], e = s.h[4], f = s.h[5], g = s.h[6], h = s.h[7];
    for (int i = 0; i < 64; ++i) {
        std::uint32_t S1 = ror32(e, 6) ^ ror32(e, 11) ^ ror32(e, 25);
        std::uint32_t ch = (e & f) ^ (~e & g);
        std::uint32_t t1 = h + S1 + ch + SHA256_K[i] + w[i];
        std::uint32_t S0 = ror32(a, 2) ^ ror32(a, 13) ^ ror32(a, 22);
        std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        std::uint32_t t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    s.h[0] += a; s.h[1] += b; s.h[2] += c; s.h[3] += d; s.h[4] += e; s.h[5] += f; s.h[6] += g; s.h[7] += h;
}

// ---- SHA-512 / SHA-384 --------------------------------------------------------------------------------------------------------
struct Sha512 { std::uint64_t h[8]; std::uint64_t length_lo, length_hi; std::uint8_t buffer[128]; std::uint32_t buffered; };
const std::uint64_t SHA512_K[80] = {
    0x428a2f98d728ae22ULL, 0x7137449123ef65cdULL, 0xb5c0fbcfec4d3b2fULL, 0xe9b5dba58189dbbcULL, 0x3956c25bf348b538ULL, 0x59f111f1b605d019ULL,
    0x923f82a4af194f9bULL, 0xab1c5ed5da6d8118ULL, 0xd807aa98a3030242ULL, 0x12835b0145706fbeULL, 0x243185be4ee4b28cULL, 0x550c7dc3d5ffb4e2ULL,
    0x72be5d74f27b896fULL, 0x80deb1fe3b1696b1ULL, 0x9bdc06a725c71235ULL, 0xc19bf174cf692694ULL, 0xe49b69c19ef14ad2ULL, 0xefbe4786384f25e3ULL,
    0x0fc19dc68b8cd5b5ULL, 0x240ca1cc77ac9c65ULL, 0x2de92c6f592b0275ULL, 0x4a7484aa6ea6e483ULL, 0x5cb0a9dcbd41fbd4ULL, 0x76f988da831153b5ULL,
    0x983e5152ee66dfabULL, 0xa831c66d2db43210ULL, 0xb00327c898fb213fULL, 0xbf597fc7beef0ee4ULL, 0xc6e00bf33da88fc2ULL, 0xd5a79147930aa725ULL,
    0x06ca6351e003826fULL, 0x142929670a0e6e70ULL, 0x27b70a8546d22ffcULL, 0x2e1b21385c26c926ULL, 0x4d2c6dfc5ac42aedULL, 0x53380d139d95b3dfULL,
    0x650a73548baf63deULL, 0x766a0abb3c77b2a8ULL, 0x81c2c92e47edaee6ULL, 0x92722c851482353bULL, 0xa2bfe8a14cf10364ULL, 0xa81a664bbc423001ULL,
    0xc24b8b70d0f89791ULL, 0xc76c51a30654be30ULL, 0xd192e819d6ef5218ULL, 0xd69906245565a910ULL, 0xf40e35855771202aULL, 0x106aa07032bbd1b8ULL,
    0x19a4c116b8d2d0c8ULL, 0x1e376c085141ab53ULL, 0x2748774cdf8eeb99ULL, 0x34b0bcb5e19b48a8ULL, 0x391c0cb3c5c95a63ULL, 0x4ed8aa4ae3418acbULL,
    0x5b9cca4f7763e373ULL, 0x682e6ff3d6b2b8a3ULL, 0x748f82ee5defb2fcULL, 0x78a5636f43172f60ULL, 0x84c87814a1f0ab72ULL, 0x8cc702081a6439ecULL,
    0x90befffa23631e28ULL, 0xa4506cebde82bde9ULL, 0xbef9a3f7b2c67915ULL, 0xc67178f2e372532bULL, 0xca273eceea26619cULL, 0xd186b8c721c0c207ULL,
    0xeada7dd6cde0eb1eULL, 0xf57d4f7fee6ed178ULL, 0x06f067aa72176fbaULL, 0x0a637dc5a2c898a6ULL, 0x113f9804bef90daeULL, 0x1b710b35131c471bULL,
    0x28db77f523047d84ULL, 0x32caab7b40c72493ULL, 0x3c9ebe0a15c9bebcULL, 0x431d67c49c100d4cULL, 0x4cc5d4becb3e42b6ULL, 0x597f299cfc657e2aULL,
    0x5fcb6fab3ad6faecULL, 0x6c44198c4a475817ULL};
void sha512_init(Sha512& s, bool is384) {
    static const std::uint64_t iv512[8] = {0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL, 0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
                                           0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL, 0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL};
    static const std::uint64_t iv384[8] = {0xcbbb9d5dc1059ed8ULL, 0x629a292a367cd507ULL, 0x9159015a3070dd17ULL, 0x152fecd8f70e5939ULL,
                                           0x67332667ffc00b31ULL, 0x8eb44a8768581511ULL, 0xdb0c2e0d64f98fa7ULL, 0x47b5481dbefa4fa4ULL};
    std::memcpy(s.h, is384 ? iv384 : iv512, sizeof s.h);
    s.length_lo = 0; s.length_hi = 0; s.buffered = 0;
}
void sha512_block(Sha512& s, const std::uint8_t* p) {
    std::uint64_t w[80];
    for (int i = 0; i < 16; ++i) w[i] = load64be(p + 8 * i);
    for (int i = 16; i < 80; ++i) {
        std::uint64_t s0 = ror64(w[i - 15], 1) ^ ror64(w[i - 15], 8) ^ (w[i - 15] >> 7);
        std::uint64_t s1 = ror64(w[i - 2], 19) ^ ror64(w[i - 2], 61) ^ (w[i - 2] >> 6);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    std::uint64_t a = s.h[0], b = s.h[1], c = s.h[2], d = s.h[3], e = s.h[4], f = s.h[5], g = s.h[6], h = s.h[7];
    for (int i = 0; i < 80; ++i) {
        std::uint64_t S1 = ror64(e, 14) ^ ror64(e, 18) ^ ror64(e, 41);
        std::uint64_t ch = (e & f) ^ (~e & g);
        std::uint64_t t1 = h + S1 + ch + SHA512_K[i] + w[i];
        std::uint64_t S0 = ror64(a, 28) ^ ror64(a, 34) ^ ror64(a, 39);
        std::uint64_t maj = (a & b) ^ (a & c) ^ (b & c);
        std::uint64_t t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    s.h[0] += a; s.h[1] += b; s.h[2] += c; s.h[3] += d; s.h[4] += e; s.h[5] += f; s.h[6] += g; s.h[7] += h;
}

// ---- Keccak-f[1600]: SHA-3 and SHAKE ----------------------------------------------------------------------------------------------
struct Keccak { std::uint64_t a[25]; std::uint32_t rate; std::uint32_t buffered; std::uint8_t suffix; std::uint8_t buffer[168]; };
const std::uint64_t KECCAK_RC[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808aULL, 0x8000000080008000ULL, 0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008aULL, 0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL, 0x8000000000008089ULL, 0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL, 0x8000000080008081ULL, 0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL};
const int KECCAK_ROT[25] = {0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14};
void keccak_f(std::uint64_t* a) {
    for (int round = 0; round < 24; ++round) {
        std::uint64_t c[5], d[5];
        for (int x = 0; x < 5; ++x) c[x] = a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20];
        for (int x = 0; x < 5; ++x) d[x] = c[(x + 4) % 5] ^ rol64(c[(x + 1) % 5], 1);
        for (int i = 0; i < 25; ++i) a[i] ^= d[i % 5];
        std::uint64_t b[25];
        for (int x = 0; x < 5; ++x)
            for (int y = 0; y < 5; ++y) {
                int i = x + 5 * y;
                int nx = y, ny = (2 * x + 3 * y) % 5;
                int r = KECCAK_ROT[i];
                b[nx + 5 * ny] = r == 0 ? a[i] : rol64(a[i], r);
            }
        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x) a[x + 5 * y] = b[x + 5 * y] ^ (~b[(x + 1) % 5 + 5 * y] & b[(x + 2) % 5 + 5 * y]);
        a[0] ^= KECCAK_RC[round];
    }
}
void keccak_init(Keccak& s, std::uint32_t rate, std::uint8_t suffix) { std::memset(s.a, 0, sizeof s.a); s.rate = rate; s.buffered = 0; s.suffix = suffix; }
void keccak_absorb_block(Keccak& s, const std::uint8_t* p) {
    for (std::uint32_t i = 0; i < s.rate / 8; ++i) s.a[i] ^= load64le(p + 8 * i);
    keccak_f(s.a);
}
void keccak_update(Keccak& s, const std::uint8_t* p, std::size_t n) {
    while (n > 0) {
        std::size_t take = std::min<std::size_t>(n, s.rate - s.buffered);
        std::memcpy(s.buffer + s.buffered, p, take);
        s.buffered += static_cast<std::uint32_t>(take); p += take; n -= take;
        if (s.buffered == s.rate) { keccak_absorb_block(s, s.buffer); s.buffered = 0; }
    }
}
std::string keccak_squeeze(Keccak s, std::size_t length) {   // on a copy: the state itself goes on
    std::memset(s.buffer + s.buffered, 0, s.rate - s.buffered);
    s.buffer[s.buffered] ^= s.suffix;
    s.buffer[s.rate - 1] ^= 0x80;
    keccak_absorb_block(s, s.buffer);
    std::string out;
    out.reserve(length);
    while (out.size() < length) {
        std::uint8_t block[200];
        for (int i = 0; i < 25; ++i) store64le(block + 8 * i, s.a[i]);
        std::size_t take = std::min<std::size_t>(length - out.size(), s.rate);
        out.append(reinterpret_cast<const char*>(block), take);
        if (out.size() < length) keccak_f(s.a);
    }
    return out;
}

// ---- BLAKE2b and BLAKE2s (RFC 7693, with the tree parameters) -------------------------------------------------------------------------
const std::uint8_t BLAKE2_SIGMA[12][16] = {
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}, {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3},
    {11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4}, {7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8},
    {9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13}, {2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9},
    {12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11}, {13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10},
    {6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5}, {10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}, {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3}};
const std::uint64_t BLAKE2B_IV[8] = {0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL, 0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
                                     0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL, 0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL};
const std::uint32_t BLAKE2S_IV[8] = {0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19};

struct Blake2b { std::uint64_t h[8]; std::uint64_t t[2]; std::uint8_t buffer[128]; std::uint32_t buffered; std::uint8_t digest_size; std::uint8_t last_node; };
struct Blake2s { std::uint32_t h[8]; std::uint32_t t[2]; std::uint8_t buffer[64]; std::uint32_t buffered; std::uint8_t digest_size; std::uint8_t last_node; };

void blake2b_compress(Blake2b& s, const std::uint8_t* block, bool last) {
    std::uint64_t m[16], v[16];
    for (int i = 0; i < 16; ++i) m[i] = load64le(block + 8 * i);
    for (int i = 0; i < 8; ++i) { v[i] = s.h[i]; v[i + 8] = BLAKE2B_IV[i]; }
    v[12] ^= s.t[0]; v[13] ^= s.t[1];
    if (last) { v[14] = ~v[14]; if (s.last_node) v[15] = ~v[15]; }
    auto g = [&](int r, int i, int a, int b, int c, int d) {
        v[a] = v[a] + v[b] + m[BLAKE2_SIGMA[r][2 * i]]; v[d] = ror64(v[d] ^ v[a], 32); v[c] = v[c] + v[d]; v[b] = ror64(v[b] ^ v[c], 24);
        v[a] = v[a] + v[b] + m[BLAKE2_SIGMA[r][2 * i + 1]]; v[d] = ror64(v[d] ^ v[a], 16); v[c] = v[c] + v[d]; v[b] = ror64(v[b] ^ v[c], 63);
    };
    for (int r = 0; r < 12; ++r) {
        g(r, 0, 0, 4, 8, 12); g(r, 1, 1, 5, 9, 13); g(r, 2, 2, 6, 10, 14); g(r, 3, 3, 7, 11, 15);
        g(r, 4, 0, 5, 10, 15); g(r, 5, 1, 6, 11, 12); g(r, 6, 2, 7, 8, 13); g(r, 7, 3, 4, 9, 14);
    }
    for (int i = 0; i < 8; ++i) s.h[i] ^= v[i] ^ v[i + 8];
}
void blake2s_compress(Blake2s& s, const std::uint8_t* block, bool last) {
    std::uint32_t m[16], v[16];
    for (int i = 0; i < 16; ++i) m[i] = load32le(block + 4 * i);
    for (int i = 0; i < 8; ++i) { v[i] = s.h[i]; v[i + 8] = BLAKE2S_IV[i]; }
    v[12] ^= s.t[0]; v[13] ^= s.t[1];
    if (last) { v[14] = ~v[14]; if (s.last_node) v[15] = ~v[15]; }
    auto g = [&](int r, int i, int a, int b, int c, int d) {
        v[a] = v[a] + v[b] + m[BLAKE2_SIGMA[r][2 * i]]; v[d] = ror32(v[d] ^ v[a], 16); v[c] = v[c] + v[d]; v[b] = ror32(v[b] ^ v[c], 12);
        v[a] = v[a] + v[b] + m[BLAKE2_SIGMA[r][2 * i + 1]]; v[d] = ror32(v[d] ^ v[a], 8); v[c] = v[c] + v[d]; v[b] = ror32(v[b] ^ v[c], 7);
    };
    for (int r = 0; r < 10; ++r) {
        g(r, 0, 0, 4, 8, 12); g(r, 1, 1, 5, 9, 13); g(r, 2, 2, 6, 10, 14); g(r, 3, 3, 7, 11, 15);
        g(r, 4, 0, 5, 10, 15); g(r, 5, 1, 6, 11, 12); g(r, 6, 2, 7, 8, 13); g(r, 7, 3, 4, 9, 14);
    }
    for (int i = 0; i < 8; ++i) s.h[i] ^= v[i] ^ v[i + 8];
}
struct Blake2Params {                              // the parameter block's fields, as _blake2 takes them
    std::size_t digest_size; std::string key, salt, person;
    std::uint64_t fanout, depth, leaf_size, node_offset, node_depth, inner_size; bool last_node;
};
void blake2b_init(Blake2b& s, const Blake2Params& p) {
    std::uint8_t block[64] = {};
    block[0] = static_cast<std::uint8_t>(p.digest_size); block[1] = static_cast<std::uint8_t>(p.key.size());
    block[2] = static_cast<std::uint8_t>(p.fanout); block[3] = static_cast<std::uint8_t>(p.depth);
    store32le(block + 4, static_cast<std::uint32_t>(p.leaf_size)); store64le(block + 8, p.node_offset);
    block[16] = static_cast<std::uint8_t>(p.node_depth); block[17] = static_cast<std::uint8_t>(p.inner_size);
    std::memcpy(block + 32, p.salt.data(), p.salt.size()); std::memcpy(block + 48, p.person.data(), p.person.size());
    for (int i = 0; i < 8; ++i) s.h[i] = BLAKE2B_IV[i] ^ load64le(block + 8 * i);
    s.t[0] = s.t[1] = 0; s.buffered = 0; s.digest_size = static_cast<std::uint8_t>(p.digest_size); s.last_node = p.last_node;
    if (!p.key.empty()) { std::memset(s.buffer, 0, 128); std::memcpy(s.buffer, p.key.data(), p.key.size()); s.buffered = 128; }
}
void blake2s_init(Blake2s& s, const Blake2Params& p) {
    std::uint8_t block[32] = {};
    block[0] = static_cast<std::uint8_t>(p.digest_size); block[1] = static_cast<std::uint8_t>(p.key.size());
    block[2] = static_cast<std::uint8_t>(p.fanout); block[3] = static_cast<std::uint8_t>(p.depth);
    store32le(block + 4, static_cast<std::uint32_t>(p.leaf_size));
    for (int i = 0; i < 6; ++i) block[8 + i] = static_cast<std::uint8_t>(p.node_offset >> (8 * i));
    block[14] = static_cast<std::uint8_t>(p.node_depth); block[15] = static_cast<std::uint8_t>(p.inner_size);
    std::memcpy(block + 16, p.salt.data(), p.salt.size()); std::memcpy(block + 24, p.person.data(), p.person.size());
    for (int i = 0; i < 8; ++i) s.h[i] = BLAKE2S_IV[i] ^ load32le(block + 4 * i);
    s.t[0] = s.t[1] = 0; s.buffered = 0; s.digest_size = static_cast<std::uint8_t>(p.digest_size); s.last_node = p.last_node;
    if (!p.key.empty()) { std::memset(s.buffer, 0, 64); std::memcpy(s.buffer, p.key.data(), p.key.size()); s.buffered = 64; }
}
void blake2b_update(Blake2b& s, const std::uint8_t* p, std::size_t n) {   // a full buffer is compressed only once more data follows
    while (n > 0) {
        if (s.buffered == 128) {
            s.t[0] += 128; if (s.t[0] < 128) s.t[1] += 1;
            blake2b_compress(s, s.buffer, false); s.buffered = 0;
        }
        std::size_t take = std::min<std::size_t>(n, 128 - s.buffered);
        std::memcpy(s.buffer + s.buffered, p, take); s.buffered += static_cast<std::uint32_t>(take); p += take; n -= take;
    }
}
void blake2s_update(Blake2s& s, const std::uint8_t* p, std::size_t n) {
    while (n > 0) {
        if (s.buffered == 64) {
            s.t[0] += 64; if (s.t[0] < 64) s.t[1] += 1;
            blake2s_compress(s, s.buffer, false); s.buffered = 0;
        }
        std::size_t take = std::min<std::size_t>(n, 64 - s.buffered);
        std::memcpy(s.buffer + s.buffered, p, take); s.buffered += static_cast<std::uint32_t>(take); p += take; n -= take;
    }
}
std::string blake2b_final(Blake2b s) {
    s.t[0] += s.buffered; if (s.t[0] < s.buffered) s.t[1] += 1;
    std::memset(s.buffer + s.buffered, 0, 128 - s.buffered);
    blake2b_compress(s, s.buffer, true);
    std::uint8_t out[64];
    for (int i = 0; i < 8; ++i) store64le(out + 8 * i, s.h[i]);
    return std::string(reinterpret_cast<const char*>(out), s.digest_size);
}
std::string blake2s_final(Blake2s s) {
    s.t[0] += s.buffered; if (s.t[0] < s.buffered) s.t[1] += 1;
    std::memset(s.buffer + s.buffered, 0, 64 - s.buffered);
    blake2s_compress(s, s.buffer, true);
    std::uint8_t out[32];
    for (int i = 0; i < 8; ++i) store32le(out + 4 * i, s.h[i]);
    return std::string(reinterpret_cast<const char*>(out), s.digest_size);
}

// ---- the Merkle-Damgard family's buffering and finalisation ------------------------------------------------------------------------
template <typename S, std::size_t Block, typename Compress>
void md_feed(S& s, const std::uint8_t* p, std::size_t n, Compress compress) {   // into the buffer, a full block compressed
    if (s.buffered > 0) {
        std::size_t take = std::min<std::size_t>(n, Block - s.buffered);
        std::memcpy(s.buffer + s.buffered, p, take); s.buffered += static_cast<std::uint32_t>(take); p += take; n -= take;
        if (s.buffered == Block) { compress(s, s.buffer); s.buffered = 0; }
    }
    while (n >= Block) { compress(s, p); p += Block; n -= Block; }
    if (n > 0) { std::memcpy(s.buffer, p, n); s.buffered = static_cast<std::uint32_t>(n); }
}
template <typename S, std::size_t Block, typename Compress>
void md_update(S& s, const std::uint8_t* p, std::size_t n, Compress compress) {
    s.length += n;
    md_feed<S, Block>(s, p, n, compress);
}
template <typename S, std::size_t Block, typename Compress>
void md_finish(S& s, bool big_endian_length, Compress compress) {   // 0x80, zeros to eight short of a block, the bit length
    std::uint64_t bits = s.length * 8;
    std::uint8_t tail[Block * 2];
    std::size_t n = 0;
    tail[n++] = 0x80;
    while ((s.buffered + n) % Block != Block - 8) tail[n++] = 0;
    if (big_endian_length) store64be(tail + n, bits); else store64le(tail + n, bits);
    n += 8;
    md_feed<S, Block>(s, tail, n, compress);
}
void sha512_feed(Sha512& s, const std::uint8_t* p, std::size_t n) {
    if (s.buffered > 0) {
        std::size_t take = std::min<std::size_t>(n, 128 - s.buffered);
        std::memcpy(s.buffer + s.buffered, p, take); s.buffered += static_cast<std::uint32_t>(take); p += take; n -= take;
        if (s.buffered == 128) { sha512_block(s, s.buffer); s.buffered = 0; }
    }
    while (n >= 128) { sha512_block(s, p); p += 128; n -= 128; }
    if (n > 0) { std::memcpy(s.buffer, p, n); s.buffered = static_cast<std::uint32_t>(n); }
}
void sha512_update(Sha512& s, const std::uint8_t* p, std::size_t n) {
    std::uint64_t before = s.length_lo;
    s.length_lo += n; if (s.length_lo < before) s.length_hi += 1;
    sha512_feed(s, p, n);
}
void sha512_finish(Sha512& s) {                  // the 128-bit bit length
    std::uint64_t bits_lo = s.length_lo << 3, bits_hi = (s.length_hi << 3) | (s.length_lo >> 61);
    std::uint8_t tail[256];
    std::size_t n = 0;
    tail[n++] = 0x80;
    while ((s.buffered + n) % 128 != 112) tail[n++] = 0;
    store64be(tail + n, bits_hi); store64be(tail + n + 8, bits_lo);
    n += 16;
    sha512_feed(s, tail, n);
}

// ---- the state as bytes -------------------------------------------------------------------------------------------------------------
template <typename S> Ref pack_state(Algo algo, const S& s) {
    std::string out(1 + sizeof(S), '\0');
    out[0] = static_cast<char>(algo);
    std::memcpy(out.data() + 1, &s, sizeof(S));
    return bytes_new(out);
}
template <typename S> S unpack_state(const std::string& state) {
    S s;
    if (state.size() != 1 + sizeof(S)) raise_new("ValueError", "a hash state of the wrong size");
    std::memcpy(&s, state.data() + 1, sizeof(S));
    return s;
}
Algo algo_of(const std::string& state) {
    if (state.empty()) raise_new("ValueError", "an empty hash state");
    return static_cast<Algo>(static_cast<std::uint8_t>(state[0]));
}
Algo algo_by_name(std::string_view name) {
    if (name == "md5") return Algo::md5;
    if (name == "sha1") return Algo::sha1;
    if (name == "sha224") return Algo::sha224;
    if (name == "sha256") return Algo::sha256;
    if (name == "sha384") return Algo::sha384;
    if (name == "sha512") return Algo::sha512;
    if (name == "sha3_224") return Algo::sha3_224;
    if (name == "sha3_256") return Algo::sha3_256;
    if (name == "sha3_384") return Algo::sha3_384;
    if (name == "sha3_512") return Algo::sha3_512;
    if (name == "shake_128") return Algo::shake_128;
    if (name == "shake_256") return Algo::shake_256;
    if (name == "blake2b") return Algo::blake2b;
    if (name == "blake2s") return Algo::blake2s;
    raise_new("ValueError", "_hash_new(): no such algorithm " + std::string(name));
}
const std::string& data_of(Obj v) {
    if (is_kind(v, Kind::Bytes)) return bytes_data(v);
    raise_new("TypeError", "a hash primitive needs bytes");
}
}  // namespace

Ref i_hash_new(Obj, Args a) {
    positional_only(a, "_hash_new", 2, 2);
    Algo algo = algo_by_name(as_str(a.pos(0))->text);
    switch (algo) {
        case Algo::md5: { Md5 s; md5_init(s); return pack_state(algo, s); }
        case Algo::sha1: { Sha1 s; sha1_init(s); return pack_state(algo, s); }
        case Algo::sha224: case Algo::sha256: { Sha256 s; sha256_init(s, algo == Algo::sha224); return pack_state(algo, s); }
        case Algo::sha384: case Algo::sha512: { Sha512 s; sha512_init(s, algo == Algo::sha384); return pack_state(algo, s); }
        case Algo::sha3_224: { Keccak s; keccak_init(s, 144, 0x06); return pack_state(algo, s); }
        case Algo::sha3_256: { Keccak s; keccak_init(s, 136, 0x06); return pack_state(algo, s); }
        case Algo::sha3_384: { Keccak s; keccak_init(s, 104, 0x06); return pack_state(algo, s); }
        case Algo::sha3_512: { Keccak s; keccak_init(s, 72, 0x06); return pack_state(algo, s); }
        case Algo::shake_128: { Keccak s; keccak_init(s, 168, 0x1f); return pack_state(algo, s); }
        case Algo::shake_256: { Keccak s; keccak_init(s, 136, 0x1f); return pack_state(algo, s); }
        case Algo::blake2b: case Algo::blake2s: {
            Obj params = a.pos(1);
            if (!is_kind(params, Kind::Tuple)) raise_new("TypeError", "_hash_new(): blake2 needs its parameters");
            auto* t = static_cast<Tuple*>(params.object());
            if (t->items.size() != 11) raise_new("TypeError", "_hash_new(): blake2 needs eleven parameters");
            Blake2Params p;
            p.digest_size = static_cast<std::size_t>(index_value(t->items[0]));
            p.key = data_of(t->items[1]); p.salt = data_of(t->items[2]); p.person = data_of(t->items[3]);
            p.fanout = static_cast<std::uint64_t>(index_value(t->items[4])); p.depth = static_cast<std::uint64_t>(index_value(t->items[5]));
            p.leaf_size = static_cast<std::uint64_t>(index_value(t->items[6]));
            const std::string& offset = data_of(t->items[7]);   // eight little-endian bytes: up to 2**64 - 1
            if (offset.size() != 8) raise_new("ValueError", "_hash_new(): node_offset needs eight bytes");
            p.node_offset = load64le(reinterpret_cast<const std::uint8_t*>(offset.data()));
            p.node_depth = static_cast<std::uint64_t>(index_value(t->items[8])); p.inner_size = static_cast<std::uint64_t>(index_value(t->items[9]));
            p.last_node = truth(t->items[10]);
            if (algo == Algo::blake2b) { Blake2b s; blake2b_init(s, p); return pack_state(algo, s); }
            Blake2s s; blake2s_init(s, p); return pack_state(algo, s);
        }
    }
    raise_new("ValueError", "_hash_new(): no such algorithm");
}

Ref i_hash_update(Obj, Args a) {
    positional_only(a, "_hash_update", 2, 2);
    const std::string& state = data_of(a.pos(0));
    const std::string& data = data_of(a.pos(1));
    const auto* p = reinterpret_cast<const std::uint8_t*>(data.data());
    Algo algo = algo_of(state);
    switch (algo) {
        case Algo::md5: { auto s = unpack_state<Md5>(state); md_update<Md5, 64>(s, p, data.size(), md5_block); return pack_state(algo, s); }
        case Algo::sha1: { auto s = unpack_state<Sha1>(state); md_update<Sha1, 64>(s, p, data.size(), sha1_block); return pack_state(algo, s); }
        case Algo::sha224: case Algo::sha256: { auto s = unpack_state<Sha256>(state); md_update<Sha256, 64>(s, p, data.size(), sha256_block); return pack_state(algo, s); }
        case Algo::sha384: case Algo::sha512: { auto s = unpack_state<Sha512>(state); sha512_update(s, p, data.size()); return pack_state(algo, s); }
        case Algo::sha3_224: case Algo::sha3_256: case Algo::sha3_384: case Algo::sha3_512: case Algo::shake_128: case Algo::shake_256: {
            auto s = unpack_state<Keccak>(state); keccak_update(s, p, data.size()); return pack_state(algo, s);
        }
        case Algo::blake2b: { auto s = unpack_state<Blake2b>(state); blake2b_update(s, p, data.size()); return pack_state(algo, s); }
        case Algo::blake2s: { auto s = unpack_state<Blake2s>(state); blake2s_update(s, p, data.size()); return pack_state(algo, s); }
    }
    raise_new("ValueError", "a hash state of an unknown algorithm");
}

Ref i_hash_digest(Obj, Args a) {
    positional_only(a, "_hash_digest", 1, 1);
    const std::string& state = data_of(a.pos(0));
    Algo algo = algo_of(state);
    switch (algo) {
        case Algo::md5: {
            auto s = unpack_state<Md5>(state); md_finish<Md5, 64>(s, false, md5_block);
            std::uint8_t out[16]; for (int i = 0; i < 4; ++i) store32le(out + 4 * i, s.h[i]);
            return bytes_new(std::string(reinterpret_cast<const char*>(out), 16));
        }
        case Algo::sha1: {
            auto s = unpack_state<Sha1>(state); md_finish<Sha1, 64>(s, true, sha1_block);
            std::uint8_t out[20]; for (int i = 0; i < 5; ++i) store32be(out + 4 * i, s.h[i]);
            return bytes_new(std::string(reinterpret_cast<const char*>(out), 20));
        }
        case Algo::sha224: case Algo::sha256: {
            auto s = unpack_state<Sha256>(state); md_finish<Sha256, 64>(s, true, sha256_block);
            std::uint8_t out[32]; for (int i = 0; i < 8; ++i) store32be(out + 4 * i, s.h[i]);
            return bytes_new(std::string(reinterpret_cast<const char*>(out), algo == Algo::sha224 ? 28 : 32));
        }
        case Algo::sha384: case Algo::sha512: {
            auto s = unpack_state<Sha512>(state); sha512_finish(s);
            std::uint8_t out[64]; for (int i = 0; i < 8; ++i) store64be(out + 8 * i, s.h[i]);
            return bytes_new(std::string(reinterpret_cast<const char*>(out), algo == Algo::sha384 ? 48 : 64));
        }
        case Algo::sha3_224: return bytes_new(keccak_squeeze(unpack_state<Keccak>(state), 28));
        case Algo::sha3_256: return bytes_new(keccak_squeeze(unpack_state<Keccak>(state), 32));
        case Algo::sha3_384: return bytes_new(keccak_squeeze(unpack_state<Keccak>(state), 48));
        case Algo::sha3_512: return bytes_new(keccak_squeeze(unpack_state<Keccak>(state), 64));
        case Algo::shake_128: case Algo::shake_256: raise_new("ValueError", "a SHAKE digest needs a length (_hash_xof)");
        case Algo::blake2b: return bytes_new(blake2b_final(unpack_state<Blake2b>(state)));
        case Algo::blake2s: return bytes_new(blake2s_final(unpack_state<Blake2s>(state)));
    }
    raise_new("ValueError", "a hash state of an unknown algorithm");
}

Ref i_hash_xof(Obj, Args a) {
    positional_only(a, "_hash_xof", 2, 2);
    const std::string& state = data_of(a.pos(0));
    std::int64_t length = index_value(a.pos(1));
    if (length < 0) raise_new("ValueError", "length cannot be negative");
    Algo algo = algo_of(state);
    if (algo != Algo::shake_128 && algo != Algo::shake_256) raise_new("ValueError", "_hash_xof(): not a SHAKE state");
    return bytes_new(keccak_squeeze(unpack_state<Keccak>(state), static_cast<std::size_t>(length)));
}
}  // namespace bella
