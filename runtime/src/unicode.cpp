// What CPython's Objects/unicodectype.c answers, from the tables generated from the pin (tools/unicode_tables.py, licence register L-03).
#include <cstdint>

#include "bella/runtime.hpp"

#include "unicode_tables.inc"

namespace bella {
namespace {
template <std::size_t N>
bool in_ranges(const CodePointRange (&table)[N], std::uint32_t ch) {
    std::size_t lo = 0, hi = N;
    while (lo < hi) {
        std::size_t mid = (lo + hi) / 2;
        if (ch < table[mid].first) hi = mid;
        else if (ch > table[mid].last) lo = mid + 1;
        else return true;
    }
    return false;
}
template <std::size_t N>
std::uint32_t mapped_case(const CaseMapping (&table)[N], std::uint32_t ch) {
    std::size_t lo = 0, hi = N;
    while (lo < hi) {
        std::size_t mid = (lo + hi) / 2;
        if (table[mid].from == ch) return table[mid].to;
        if (ch < table[mid].from) hi = mid;
        else lo = mid + 1;
    }
    return ch;
}
}  // namespace
bool unicode_is_decimal(std::uint32_t ch) { return in_ranges(UNICODE_DECIMAL, ch); }
bool unicode_is_space(std::uint32_t ch) { return in_ranges(UNICODE_SPACE, ch); }
bool unicode_is_linebreak(std::uint32_t ch) { return in_ranges(UNICODE_LINEBREAK, ch); }
bool unicode_is_alnum(std::uint32_t ch) { return in_ranges(UNICODE_ALNUM, ch); }
bool unicode_is_printable(std::uint32_t ch) { return in_ranges(UNICODE_PRINTABLE, ch); }
bool unicode_is_xid_start(std::uint32_t ch) { return in_ranges(UNICODE_XID_START, ch); }
bool unicode_is_xid_continue(std::uint32_t ch) { return in_ranges(UNICODE_XID_CONTINUE, ch); }
std::uint32_t unicode_to_lower(std::uint32_t ch) { return mapped_case(UNICODE_LOWER, ch); }
std::uint32_t unicode_to_upper(std::uint32_t ch) { return mapped_case(UNICODE_UPPER, ch); }
}  // namespace bella
