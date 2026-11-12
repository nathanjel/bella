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
template <std::size_t N>
int mapped_full(const FullMapping (&table)[N], std::uint32_t ch, std::uint32_t* out) {   // the mapping's code points, or ch itself
    std::size_t lo = 0, hi = N;
    while (lo < hi) {
        std::size_t mid = (lo + hi) / 2;
        if (table[mid].from == ch) {
            for (int i = 0; i < table[mid].count; ++i) out[i] = table[mid].to[i];
            return table[mid].count;
        }
        if (ch < table[mid].from) hi = mid;
        else lo = mid + 1;
    }
    out[0] = ch;
    return 1;
}
}  // namespace
bool unicode_is_alpha(std::uint32_t ch) { return in_ranges(UNICODE_ALPHA, ch); }
bool unicode_is_digit(std::uint32_t ch) { return in_ranges(UNICODE_DIGIT, ch); }
bool unicode_is_numeric(std::uint32_t ch) { return in_ranges(UNICODE_NUMERIC, ch); }
bool unicode_is_lowercase(std::uint32_t ch) { return in_ranges(UNICODE_LOWERCASE, ch); }
bool unicode_is_uppercase(std::uint32_t ch) { return in_ranges(UNICODE_UPPERCASE, ch); }
bool unicode_is_titlecase(std::uint32_t ch) { return in_ranges(UNICODE_TITLECASE, ch); }
bool unicode_is_cased(std::uint32_t ch) { return in_ranges(UNICODE_CASED, ch); }
bool unicode_is_case_ignorable(std::uint32_t ch) { return in_ranges(UNICODE_CASE_IGNORABLE, ch); }
int unicode_lower_full(std::uint32_t ch, std::uint32_t* out) { return mapped_full(UNICODE_LOWER_FULL, ch, out); }
int unicode_upper_full(std::uint32_t ch, std::uint32_t* out) { return mapped_full(UNICODE_UPPER_FULL, ch, out); }
int unicode_title_full(std::uint32_t ch, std::uint32_t* out) { return mapped_full(UNICODE_TITLE_FULL, ch, out); }
int unicode_fold_full(std::uint32_t ch, std::uint32_t* out) { return mapped_full(UNICODE_FOLD_FULL, ch, out); }
bool unicode_is_decimal(std::uint32_t ch) { return in_ranges(UNICODE_DECIMAL, ch); }
bool unicode_is_space(std::uint32_t ch) { return in_ranges(UNICODE_SPACE, ch); }
bool unicode_is_linebreak(std::uint32_t ch) { return in_ranges(UNICODE_LINEBREAK, ch); }
bool unicode_is_alnum(std::uint32_t ch) { return in_ranges(UNICODE_ALNUM, ch); }
bool unicode_is_printable(std::uint32_t ch) { return in_ranges(UNICODE_PRINTABLE, ch); }
bool unicode_is_xid_start(std::uint32_t ch) { return in_ranges(UNICODE_XID_START, ch); }
bool unicode_is_xid_continue(std::uint32_t ch) { return in_ranges(UNICODE_XID_CONTINUE, ch); }
std::uint32_t unicode_to_lower(std::uint32_t ch) { return mapped_case(UNICODE_LOWER, ch); }
std::uint32_t unicode_to_upper(std::uint32_t ch) { return mapped_case(UNICODE_UPPER, ch); }
// Objects/unicodeobject.c: what int(), float() and complex() parse a str as. ASCII is itself; past it a Unicode space is a space and a
// decimal digit its ASCII digit, and the first character that is neither (DEL among them) is a '?' that ends the text
const std::string& decimal_and_space_to_ascii(const Str* s, std::string& out) {
    if (s->ascii) return s->text;                // "If the string is already ASCII, just return the same string"
    out.clear();
    out.reserve(s->length);
    for (std::size_t i = 0; i < s->length; ++i) {
        std::uint32_t ch = s->at(i);
        if (ch < 127) {
            out += static_cast<char>(ch);
        } else if (unicode_is_space(ch)) {
            out += ' ';
        } else {
            int decimal = unicode_to_decimal(ch);
            if (decimal < 0) {
                out += '?';
                break;
            }
            out += static_cast<char>('0' + decimal);
        }
    }
    return out;
}
bool is_identifier(const Str* s) {               // PyUnicode_IsIdentifier: XID_Start or '_', then XID_Continue
    if (s->length == 0) return false;
    if (s->at(0) != U'_' && !unicode_is_xid_start(s->at(0))) return false;
    for (std::size_t i = 1; i < s->length; ++i)
        if (!unicode_is_xid_continue(s->at(i))) return false;
    return true;
}
}  // namespace bella
