// runtime/src/format.cpp -- the format mini-language (Objects/unicode_formatter.c), str.format and format_map
// (Objects/stringlib/unicode_format.h), PyObject_Format, and PyOS_double_to_string's layout around <charconv>'s digits
// (Python/pystrtod.c). Text is held as code points while it is taken apart and put together.
#include <charconv>
#include <climits>
#include <cmath>
#include <cstring>

#include "bella/runtime.hpp"

namespace bella {
namespace {
using Cps = std::u32string;

Cps cps_of(const Str* s) {
    Cps out;
    out.reserve(s->length);
    for (std::size_t i = 0; i < s->length; ++i) out += s->at(i);
    return out;
}
Cps widen(std::string_view ascii) { return Cps(ascii.begin(), ascii.end()); }
std::string hex_text(std::uint32_t v) {
    char buf[16];
    auto [end, ec] = std::to_chars(buf, buf + sizeof buf, v, 16);
    return std::string(buf, end);
}
// what a message shows of a presentation type: %c when it can
std::string shown_type(char32_t c) {
    if (c > 32 && c < 128) return std::string(1, static_cast<char>(c));
    return "\\x" + hex_text(static_cast<std::uint32_t>(c));
}

// ---- PyOS_double_to_string ----
constexpr int DTSF_ADD_DOT_0 = 2, DTSF_ALT = 4, DTSF_NO_NEG_0 = 8;
struct Digits {
    std::string text;
    int decpt = 0;
};
void trim_trailing_zeros(std::string& s) {
    while (!s.empty() && s.back() == '0') s.pop_back();
}
// _Py_dg_dtoa: mode 0 the shortest digits; mode 2 at most `ndigits` significant ones, mode 3 through `ndigits` past
// the point, both correctly rounded and with trailing zeros left off. The value is finite and not negative here.
Digits dtoa_digits(double value, int mode, int ndigits) {
    Digits d;
    if (value == 0.0) {
        d.text = "0";
        d.decpt = 1;
        return d;
    }
    std::vector<char> buf(static_cast<std::size_t>(std::max(ndigits, 0)) + 400);
    char* first = buf.data();
    char* last = buf.data() + buf.size();
    if (mode == 3) {
        auto [end, ec] = std::to_chars(first, last, value, std::chars_format::fixed, ndigits);
        std::string_view all(first, static_cast<std::size_t>(end - first));
        std::size_t point = all.find('.');
        std::string whole(all.substr(0, point));
        std::string fraction = point == std::string_view::npos ? std::string() : std::string(all.substr(point + 1));
        std::string joined = whole + fraction;
        std::size_t leading = joined.find_first_not_of('0');
        if (leading == std::string::npos) {      // rounded to nothing: no digits, at the place asked for
            d.decpt = -ndigits;
            return d;
        }
        d.decpt = static_cast<int>(whole.size()) - static_cast<int>(leading);
        d.text = joined.substr(leading);
        trim_trailing_zeros(d.text);
        return d;
    }
    std::to_chars_result r = mode == 0 ? std::to_chars(first, last, value, std::chars_format::scientific)
                                       : std::to_chars(first, last, value, std::chars_format::scientific, std::max(ndigits, 1) - 1);
    std::string_view all(first, static_cast<std::size_t>(r.ptr - first));
    std::size_t e = all.find('e');
    d.text.assign(1, all[0]);
    if (e > 2) d.text += all.substr(2, e - 2);
    trim_trailing_zeros(d.text);
    int exponent = 0;
    std::string_view written = all.substr(e + 1);
    if (written[0] == '+') written.remove_prefix(1);
    std::from_chars(written.data(), written.data() + written.size(), exponent);
    d.decpt = exponent + 1;
    return d;
}
std::string double_to_string(double val, char code, int precision, int flags) {
    bool upper = code == 'E' || code == 'F' || code == 'G';
    char format_code = upper ? static_cast<char>(code + 32) : code;
    int mode = 0;
    switch (format_code) {
        case 'e': mode = 2; ++precision; break;
        case 'f': mode = 3; break;
        case 'g': mode = 2; if (precision == 0) precision = 1; break;
        default: break;                          // 'r': the shortest, and no precision
    }
    bool add_dot_0 = (flags & DTSF_ADD_DOT_0) != 0, alt = (flags & DTSF_ALT) != 0;
    bool negative = std::signbit(val);
    if (std::isnan(val)) return upper ? "NAN" : "nan";
    if (std::isinf(val)) return std::string(negative ? "-" : "") + (upper ? "INF" : "inf");
    Digits d = dtoa_digits(std::fabs(val), mode, precision);
    auto digits_len = static_cast<std::int64_t>(d.text.size());
    std::int64_t decpt = d.decpt;
    if ((flags & DTSF_NO_NEG_0) != 0 && negative && (digits_len == 0 || (digits_len == 1 && d.text[0] == '0'))) negative = false;
    std::int64_t vdigits_end = digits_len;
    bool use_exp = false;
    int exp = 0;
    switch (format_code) {
        case 'e': use_exp = true; vdigits_end = precision; break;
        case 'f': vdigits_end = decpt + precision; break;
        case 'g':
            if (decpt <= -4 || decpt > (add_dot_0 ? precision - 1 : precision)) use_exp = true;
            if (alt) vdigits_end = precision;
            break;
        default:
            if (decpt <= -4 || decpt > 16) use_exp = true;
            break;
    }
    if (use_exp) {
        exp = static_cast<int>(decpt) - 1;
        decpt = 1;
    }
    std::int64_t vdigits_start = decpt <= 0 ? decpt - 1 : 0;
    if (!use_exp && add_dot_0) vdigits_end = std::max(vdigits_end, decpt + 1);
    else vdigits_end = std::max(vdigits_end, decpt);
    std::string p;
    if (negative) p += '-';
    if (decpt <= 0) {                            // zeros on the left of the digits
        p.append(static_cast<std::size_t>(decpt - vdigits_start), '0');
        p += '.';
        p.append(static_cast<std::size_t>(-decpt), '0');
    } else {
        p.append(static_cast<std::size_t>(-vdigits_start), '0');
    }
    if (0 < decpt && decpt <= digits_len) {      // the digits, with the point among them
        p.append(d.text, 0, static_cast<std::size_t>(decpt));
        p += '.';
        p.append(d.text, static_cast<std::size_t>(decpt));
    } else {
        p += d.text;
    }
    if (digits_len < decpt) {                    // and zeros on the right
        p.append(static_cast<std::size_t>(decpt - digits_len), '0');
        p += '.';
        p.append(static_cast<std::size_t>(vdigits_end - decpt), '0');
    } else {
        p.append(static_cast<std::size_t>(vdigits_end - digits_len), '0');
    }
    if (p.back() == '.' && !alt) p.pop_back();
    if (use_exp) {
        p += upper ? 'E' : 'e';
        p += exp < 0 ? '-' : '+';
        int shown = std::abs(exp);
        if (shown < 10) p += '0';
        p += std::to_string(shown);
    }
    return p;
}

// ---- the mini-language ----
enum LocaleType : char { LT_NO_LOCALE = 0, LT_CURRENT_LOCALE = 1, LT_UNDER_FOUR_LOCALE = 2, LT_DEFAULT_LOCALE = ',', LT_UNDERSCORE_LOCALE = '_' };
struct FormatSpec {
    char32_t fill = U' ';
    char32_t align = 0;
    bool alternate = false, no_neg_0 = false;
    char32_t sign = 0;
    std::int64_t width = -1;
    LocaleType thousands = LT_NO_LOCALE, frac_thousands = LT_NO_LOCALE;
    std::int64_t precision = -1;
    char32_t type = 0;
};
bool is_alignment(char32_t c) { return c == U'<' || c == U'>' || c == U'=' || c == U'^'; }
bool is_sign(char32_t c) { return c == U' ' || c == U'+' || c == U'-'; }
[[noreturn]] void comma_and_underscore() { raise_new("ValueError", "Cannot specify both ',' and '_'."); }
[[noreturn]] void bad_thousands(char specifier, char32_t type) {
    raise_new("ValueError", std::string("Cannot specify '") + specifier + "' with '" + shown_type(type) + "'.");
}
[[noreturn]] void unknown_type(char32_t type, const ClassObject* cls) {
    raise_new("ValueError", "Unknown format code '" + shown_type(type) + "' for object of type '" + cls->name + "'");
}
std::int64_t spec_integer(const Cps& s, std::size_t& pos, std::int64_t& result) {   // get_integer: how many it read
    std::int64_t accumulator = 0, consumed = 0;
    while (pos < s.size()) {
        char32_t c = s[pos];
        if (c > 127) throw NotImplemented("a format specification with a character beyond ASCII where a number may be (the Unicode database)");
        if (c < U'0' || c > U'9') break;
        std::int64_t digit = static_cast<std::int64_t>(c) - '0';
        if (accumulator > (INT64_MAX - digit) / 10) raise_new("ValueError", "Too many decimal digits in format string");
        accumulator = accumulator * 10 + digit;
        ++pos;
        ++consumed;
    }
    result = accumulator;
    return consumed;
}
FormatSpec parse_spec(Obj obj, const Str* spec_str, char32_t default_type, char32_t default_align) {   // parse_internal_render_format_spec
    Cps s = cps_of(spec_str);
    FormatSpec f;
    f.align = default_align;
    f.type = default_type;
    std::size_t pos = 0, end = s.size();
    bool align_specified = false, fill_specified = false;
    if (end - pos >= 2 && is_alignment(s[pos + 1])) {
        f.align = s[pos + 1];
        f.fill = s[pos];
        fill_specified = align_specified = true;
        pos += 2;
    } else if (end - pos >= 1 && is_alignment(s[pos])) {
        f.align = s[pos];
        align_specified = true;
        ++pos;
    }
    if (end - pos >= 1 && is_sign(s[pos])) f.sign = s[pos++];
    if (end - pos >= 1 && s[pos] == U'z') {
        f.no_neg_0 = true;
        ++pos;
    }
    if (end - pos >= 1 && s[pos] == U'#') {
        f.alternate = true;
        ++pos;
    }
    if (!fill_specified && end - pos >= 1 && s[pos] == U'0') {
        f.fill = U'0';
        if (!align_specified && default_align == U'>') f.align = U'=';
        ++pos;
    }
    std::int64_t consumed = spec_integer(s, pos, f.width);
    if (consumed == 0) f.width = -1;
    if (end - pos && s[pos] == U',') {
        f.thousands = LT_DEFAULT_LOCALE;
        ++pos;
    }
    if (end - pos && s[pos] == U'_') {
        if (f.thousands != LT_NO_LOCALE) comma_and_underscore();
        f.thousands = LT_UNDERSCORE_LOCALE;
        ++pos;
    }
    if (end - pos && s[pos] == U',' && f.thousands == LT_UNDERSCORE_LOCALE) comma_and_underscore();
    if (end - pos && s[pos] == U'.') {
        ++pos;
        consumed = spec_integer(s, pos, f.precision);
        if (end - pos && s[pos] == U',') {
            if (consumed == 0) f.precision = -1;
            f.frac_thousands = LT_DEFAULT_LOCALE;
            ++pos;
            ++consumed;
        }
        if (end - pos && s[pos] == U'_') {
            if (f.frac_thousands != LT_NO_LOCALE) comma_and_underscore();
            if (consumed == 0) f.precision = -1;
            f.frac_thousands = LT_UNDERSCORE_LOCALE;
            ++pos;
            ++consumed;
        }
        if (end - pos && s[pos] == U',' && f.frac_thousands == LT_UNDERSCORE_LOCALE) comma_and_underscore();
        if (consumed == 0) raise_new("ValueError", "Format specifier missing precision");
    }
    if (end - pos > 1) raise_new("ValueError", "Invalid format specifier '" + spec_str->text + "' for object of type '" + type_of(obj)->name + "'");
    if (end - pos == 1) f.type = s[pos++];
    if (f.thousands != LT_NO_LOCALE) {
        switch (f.type) {
            case U'd': case U'e': case U'f': case U'g': case U'E': case U'G': case U'%': case U'F': case 0:
                break;
            case U'b': case U'o': case U'x': case U'X':
                if (f.thousands == LT_UNDERSCORE_LOCALE) {
                    f.thousands = LT_UNDER_FOUR_LOCALE;
                    break;
                }
                [[fallthrough]];
            default:
                bad_thousands(static_cast<char>(f.thousands), f.type);
        }
    }
    if (f.type == U'n' && f.frac_thousands != LT_NO_LOCALE) bad_thousands(static_cast<char>(f.frac_thousands), f.type);
    return f;
}
// _PyUnicode_InsertThousandsGrouping: every `every` digits from the right, or from the left for what follows a
// point; `every` 0 is no grouping. With a minimum width, zeros are added on the left, in groups as well.
std::string grouped(std::string_view digits, std::int64_t min_width, int every, std::string_view sep, bool forward) {
    min_width = std::max<std::int64_t>(0, min_width);
    auto remaining = static_cast<std::int64_t>(digits.size());
    bool use_separator = false, broken = false;
    std::vector<std::string> pieces;
    std::size_t from = forward ? 0 : digits.size();
    auto piece = [&](std::int64_t n_chars, std::int64_t n_zeros) {
        std::string run;
        if (forward) {
            if (use_separator) run += sep;
            run.append(digits.substr(from, static_cast<std::size_t>(n_chars)));
            run.append(static_cast<std::size_t>(n_zeros), '0');
            from += static_cast<std::size_t>(n_chars);
        } else {
            from -= static_cast<std::size_t>(n_chars);
            run.append(static_cast<std::size_t>(n_zeros), '0');
            run.append(digits.substr(from, static_cast<std::size_t>(n_chars)));
            if (use_separator) run += sep;
        }
        pieces.push_back(std::move(run));
    };
    while (every > 0) {
        std::int64_t len = std::min<std::int64_t>(every, std::max<std::int64_t>(std::max(remaining, min_width), 1));
        std::int64_t n_zeros = std::max<std::int64_t>(0, len - remaining);
        std::int64_t n_chars = std::max<std::int64_t>(0, std::min(remaining, len));
        piece(n_chars, n_zeros);
        use_separator = true;
        remaining -= n_chars;
        min_width -= len;
        if (remaining <= 0 && min_width <= 0) {
            broken = true;
            break;
        }
        min_width -= static_cast<std::int64_t>(sep.size());
    }
    if (!broken) {
        std::int64_t len = std::max<std::int64_t>(std::max(remaining, min_width), 1);
        std::int64_t n_zeros = std::max<std::int64_t>(0, len - remaining);
        std::int64_t n_chars = std::max<std::int64_t>(0, std::min(remaining, len));
        piece(n_chars, n_zeros);
    }
    std::string out;
    if (forward) for (const std::string& p : pieces) out += p;
    else for (auto it = pieces.rbegin(); it != pieces.rend(); ++it) out += *it;
    return out;
}
int group_width(LocaleType t) { return t == LT_DEFAULT_LOCALE || t == LT_UNDERSCORE_LOCALE ? 3 : t == LT_UNDER_FOUR_LOCALE ? 4 : 0; }
std::string_view group_separator(LocaleType t) { return t == LT_DEFAULT_LOCALE ? "," : t == LT_UNDERSCORE_LOCALE || t == LT_UNDER_FOUR_LOCALE ? "_" : ""; }

// calc_number_widths and fill_number, of a number already in pieces. 'n' asks for the current locale's grouping,
// which is the C locale's, none, as the runtime never leaves it.
Ref number_field(const FormatSpec& f, char32_t sign_char, std::string_view prefix, std::string_view digits, bool has_decimal,
                 std::string_view frac, const Cps& remainder, bool to_upper) {
    LocaleType thousands = f.type == U'n' ? LT_CURRENT_LOCALE : f.thousands;
    int every = group_width(thousands);
    if (f.frac_thousands != LT_NO_LOCALE && every == 0) every = 3;
    std::string_view sep = group_separator(thousands);
    std::string frac_text = frac.empty() ? std::string() : grouped(frac, static_cast<std::int64_t>(frac.size()), every, group_separator(f.frac_thousands), true);
    char32_t sign = 0;
    if (f.sign == U'+') sign = sign_char == U'-' ? U'-' : U'+';
    else if (f.sign == U' ') sign = sign_char == U'-' ? U'-' : U' ';
    else if (sign_char == U'-') sign = U'-';
    auto n_sign = static_cast<std::int64_t>(sign != 0 ? 1 : 0);
    auto n_prefix = static_cast<std::int64_t>(prefix.size());
    auto n_decimal = static_cast<std::int64_t>(has_decimal ? 1 : 0);
    auto n_frac = static_cast<std::int64_t>(frac.size());
    auto n_remainder = static_cast<std::int64_t>(remainder.size());
    auto n_grouped_frac = static_cast<std::int64_t>(frac_text.size());
    std::int64_t non_digit = n_sign + n_prefix + n_decimal + n_frac + n_remainder;
    std::int64_t min_width = f.fill == U'0' && f.align == U'=' ? f.width - non_digit + n_frac - n_grouped_frac : 0;
    std::string digit_text = digits.empty() ? std::string() : grouped(digits, min_width, every, sep, false);
    std::int64_t n_padding = f.width - (non_digit + static_cast<std::int64_t>(digit_text.size()) + n_grouped_frac - n_frac);
    std::int64_t lpad = 0, spad = 0, rpad = 0;
    if (n_padding > 0) {
        switch (f.align) {
            case U'<': rpad = n_padding; break;
            case U'^': lpad = n_padding / 2; rpad = n_padding - lpad; break;
            case U'=': spad = n_padding; break;
            default: lpad = n_padding; break;
        }
    }
    auto upper = [&](std::string s) {
        if (to_upper) for (char& c : s) if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 32);
        return s;
    };
    Cps out(static_cast<std::size_t>(lpad), f.fill);
    if (sign != 0) out += sign;
    out += widen(upper(std::string(prefix)));
    out.append(static_cast<std::size_t>(spad), f.fill);
    out += widen(upper(digit_text));
    if (has_decimal) out += U'.';
    out += widen(frac_text);
    out += remainder;
    out.append(static_cast<std::size_t>(rpad), f.fill);
    return str_from_codepoints(out);
}

Ref format_string_field(Obj value, const FormatSpec& f) {   // format_string_internal
    if (f.sign != 0) raise_new("ValueError", f.sign == U' ' ? "Space not allowed in string format specifier" : "Sign not allowed in string format specifier");
    if (f.no_neg_0) raise_new("ValueError", "Negative zero coercion (z) not allowed in string format specifier");
    if (f.alternate) raise_new("ValueError", "Alternate form (#) not allowed in string format specifier");
    if (f.align == U'=') raise_new("ValueError", "'=' alignment not allowed in string format specifier");
    const Str* s = as_str(value);
    auto len = static_cast<std::int64_t>(s->length);
    if ((f.width == -1 || f.width <= len) && (f.precision == -1 || f.precision >= len)) return Ref::share(value);
    if (f.precision >= 0 && len >= f.precision) len = f.precision;
    std::int64_t total = f.width >= 0 ? std::max(len, f.width) : len;
    std::int64_t lpad = f.align == U'>' ? total - len : f.align == U'^' ? (total - len) / 2 : 0;
    std::int64_t rpad = total - len - lpad;
    Cps out(static_cast<std::size_t>(lpad), f.fill);
    for (std::int64_t i = 0; i < len; ++i) out += s->at(static_cast<std::size_t>(i));
    out.append(static_cast<std::size_t>(rpad), f.fill);
    return str_from_codepoints(out);
}

Ref format_long_field(Obj value, const FormatSpec& f) {   // format_long_internal
    if (f.precision != -1) raise_new("ValueError", "Precision not allowed in integer format specifier");
    if (f.no_neg_0) raise_new("ValueError", "Negative zero coercion (z) not allowed in integer format specifier");
    if (f.type == U'c') {
        if (f.sign != 0) raise_new("ValueError", "Sign not allowed with integer format specifier 'c'");
        if (f.alternate) raise_new("ValueError", "Alternate form (#) not allowed with integer format specifier 'c'");
        std::int64_t x = 0;
        if (!as_int(value, x) || x < 0 || x > 0x10ffff) {
            if (!as_int(value, x)) raise_new("OverflowError", "Python int too large to convert to C long");
            raise_new("OverflowError", "%c arg not in range(0x110000)");
        }
        return number_field(f, 0, "", "", false, "", Cps(1, static_cast<char32_t>(x)), false);
    }
    int base = f.type == U'b' ? 2 : f.type == U'o' ? 8 : f.type == U'x' || f.type == U'X' ? 16 : 10;
    std::string text = base == 10 ? big_text(value) : int_in_base(value, base);
    std::string_view view = text;
    char32_t sign_char = 0;
    if (view[0] == '-') {
        sign_char = U'-';
        view.remove_prefix(1);
    }
    std::string_view prefix;
    if (base != 10) {
        if (f.alternate) prefix = view.substr(0, 2);
        view.remove_prefix(2);
    }
    return number_field(f, sign_char, prefix, view, false, "", Cps(), f.type == U'X');
}

Ref format_float_field(double val, const FormatSpec& f) {   // format_float_internal
    if (f.precision > INT_MAX) raise_new("ValueError", "precision too big");
    auto precision = static_cast<int>(f.precision);
    int default_precision = 6, flags = 0;
    char32_t type = f.type;
    if (f.alternate) flags |= DTSF_ALT;
    if (f.no_neg_0) flags |= DTSF_NO_NEG_0;
    if (type == 0) {
        flags |= DTSF_ADD_DOT_0;
        type = U'r';
        default_precision = 0;
    }
    if (type == U'n') type = U'g';
    bool add_pct = false;
    if (type == U'%') {
        type = U'f';
        val *= 100;
        add_pct = true;
    }
    if (precision < 0) precision = default_precision;
    else if (type == U'r') type = U'g';
    std::string buf = double_to_string(val, static_cast<char>(type), precision, flags);
    if (add_pct) buf += '%';
    std::string_view view = buf;
    char32_t sign_char = 0;
    if (view[0] == '-') {
        sign_char = U'-';
        view.remove_prefix(1);
    }
    auto is_digit = [](char c) { return c >= '0' && c <= '9'; };     // parse_number
    std::size_t pos = 0;
    while (pos < view.size() && is_digit(view[pos])) ++pos;
    std::string_view digits = view.substr(0, pos);
    bool has_decimal = pos < view.size() && view[pos] == '.';
    if (has_decimal) ++pos;
    std::size_t frac_start = pos;
    while (pos < view.size() && is_digit(view[pos])) ++pos;
    return number_field(f, sign_char, "", digits, has_decimal, view.substr(frac_start, pos - frac_start), widen(view.substr(pos)), false);
}

// the three __format__s: (format_spec, /)
const Str* spec_argument(Args a, const char* qualname) {
    onearg(a, qualname);
    const Str* spec = as_str(a.pos(0));
    if (spec == nullptr) raise_new("TypeError", "__format__() argument must be str, not " + (a.pos(0) == None() ? std::string("None") : type_of(a.pos(0))->name));
    return spec;
}
}  // namespace

Ref str_format_field(Obj self, const Str* spec) {   // _PyUnicode_FormatAdvancedWriter
    if (spec->length == 0) return str_of(self);
    FormatSpec f = parse_spec(self, spec, U's', U'<');
    if (f.type != U's') unknown_type(f.type, type_of(self));
    return format_string_field(self, f);
}
Ref int_format_field(Obj self, const Str* spec) {   // _PyLong_FormatAdvancedWriter
    if (spec->length == 0) return str_of(self);
    FormatSpec f = parse_spec(self, spec, U'd', U'>');
    switch (f.type) {
        case U'b': case U'c': case U'd': case U'o': case U'x': case U'X': case U'n':
            return format_long_field(self, f);
        case U'e': case U'E': case U'f': case U'F': case U'g': case U'G': case U'%': {
            Ref as_float = number_float(self);
            return format_float_field(float_value(as_float.get()), f);
        }
        default: unknown_type(f.type, type_of(self));
    }
}
Ref float_format_field(Obj self, const Str* spec) {   // _PyFloat_FormatAdvancedWriter
    if (spec->length == 0) return str_of(self);
    FormatSpec f = parse_spec(self, spec, 0, U'>');
    switch (f.type) {
        case 0: case U'e': case U'E': case U'f': case U'F': case U'g': case U'G': case U'n': case U'%':
            return format_float_field(float_value(self), f);
        default: unknown_type(f.type, type_of(self));
    }
}
Ref str_format_dunder(Obj self, Args a) { return str_format_field(self, spec_argument(a, "str.__format__")); }
Ref int_format_dunder(Obj self, Args a) { return int_format_field(self, spec_argument(a, "int.__format__")); }
Ref float_format_dunder(Obj self, Args a) { return float_format_field(self, spec_argument(a, "float.__format__")); }

Ref object_format(Obj obj, const Str* spec) {     // PyObject_Format
    if (spec->length == 0) {
        if (is_kind(obj, Kind::Str)) return Ref::share(obj);
        if (obj.is_small() || is_kind(obj, Kind::BigInt)) return str_of(obj);
    }
    Obj found = type_lookup(type_of(obj), intern("__format__"));
    if (found.is_unset()) {
        refuse_absent_attribute(obj, intern("__format__"));
        raise_new("TypeError", "Type " + type_of(obj)->name + " doesn't define __format__");
    }
    Ref result = call_special(obj, "__format__", {Obj::of(spec)});
    if (as_str(result.get()) == nullptr)
        raise_new("TypeError", fully_qualified_name(type_of(obj)) + ".__format__() must return a str, not " + fully_qualified_name(type_of(result.get())));
    return result;
}

// ---- str.format ----
namespace {
struct SubString {
    const Cps* str = nullptr;
    std::size_t start = 0, end = 0;
    bool present() const { return str != nullptr; }
    Ref object() const {
        if (str == nullptr) return none_ref();
        return str_from_codepoints(std::u32string_view(*str).substr(start, end - start));
    }
    Ref object_or_empty() const { return str == nullptr ? str_new("") : object(); }
};
enum class AutoState { Init, Auto, Manual };
struct AutoNumber {
    AutoState state = AutoState::Init;
    std::int64_t field_number = 0;
};
std::int64_t field_integer(const SubString& s) {  // get_integer of unicode_format.h: -1 when it is not all digits
    if (s.start >= s.end) return -1;
    std::int64_t accumulator = 0;
    for (std::size_t i = s.start; i < s.end; ++i) {
        char32_t c = (*s.str)[i];
        if (c > 127) throw NotImplemented("a format field name beyond ASCII (whether it is a number needs the Unicode database)");
        if (c < U'0' || c > U'9') return -1;
        std::int64_t digit = static_cast<std::int64_t>(c) - '0';
        if (accumulator > (INT64_MAX - digit) / 10) raise_new("ValueError", "Too many decimal digits in format string");
        accumulator = accumulator * 10 + digit;
    }
    return accumulator;
}
struct FieldNameIterator {
    SubString str;
    std::size_t index = 0;
    // 1: nothing left; 2: an item
    int next(bool& is_attribute, std::int64_t& name_idx, SubString& name) {
        if (index >= str.end) return 1;
        char32_t c = (*str.str)[index++];
        name.str = str.str;
        name.start = index;
        if (c == U'.') {
            is_attribute = true;
            while (index < str.end) {
                char32_t k = (*str.str)[index++];
                if (k == U'[' || k == U'.') {
                    --index;
                    break;
                }
            }
            name.end = index;
            name_idx = -1;
        } else if (c == U'[') {
            is_attribute = false;
            bool bracket_seen = false;
            while (index < str.end) {
                if ((*str.str)[index++] == U']') {
                    bracket_seen = true;
                    break;
                }
            }
            if (!bracket_seen) raise_new("ValueError", "Missing ']' in format string");
            name.end = index - 1;
            name_idx = field_integer(name);
        } else {
            raise_new("ValueError", "Only '.' or '[' may follow ']' in format field specifier");
        }
        if (name.start == name.end) raise_new("ValueError", "Empty attribute in format string");
        return 2;
    }
};
void field_name_split(const SubString& input, SubString& first, std::int64_t& first_idx, FieldNameIterator& rest, AutoNumber* auto_number) {
    std::size_t i = input.start;
    while (i < input.end) {
        char32_t c = (*input.str)[i++];
        if (c == U'[' || c == U'.') {
            --i;
            break;
        }
    }
    first = {input.str, input.start, i};
    rest.str = {input.str, i, input.end};
    rest.index = i;
    first_idx = field_integer(first);
    bool empty = first.start >= first.end;
    bool numeric = empty || first_idx != -1;
    if (auto_number != nullptr) {
        if (auto_number->state == AutoState::Init && numeric) auto_number->state = empty ? AutoState::Auto : AutoState::Manual;
        if (numeric) {
            if (auto_number->state == AutoState::Manual && empty)
                raise_new("ValueError", "cannot switch from manual field specification to automatic field numbering");
            if (auto_number->state != AutoState::Manual && !empty)
                raise_new("ValueError", "cannot switch from automatic field numbering to manual field specification");
        }
        if (empty) first_idx = auto_number->field_number++;
    }
}
Ref get_field_object(const SubString& input, Obj args, Obj kwargs, AutoNumber* auto_number) {
    SubString first, name;
    std::int64_t index = -1;
    FieldNameIterator rest;
    field_name_split(input, first, index, rest, auto_number);
    Ref obj;
    if (index == -1) {
        Ref key = first.object();
        if (kwargs.is_unset()) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key.get()});
            raise(exc.get());
        }
        obj = getitem(kwargs, key.get());
    } else {
        if (args.is_unset()) raise_new("ValueError", "Format string contains positional fields");
        const auto& items = static_cast<Tuple*>(args.object())->items;
        if (static_cast<std::size_t>(index) >= items.size())
            raise_new("IndexError", "Replacement index " + std::to_string(index) + " out of range for positional args tuple");
        obj = Ref::share(items[static_cast<std::size_t>(index)]);
    }
    bool is_attribute = false;
    while (rest.next(is_attribute, index, name) == 2) {
        if (is_attribute) {
            Ref attr = name.object();
            obj = getattr(obj.get(), intern(as_str(attr.get())->text));
        } else if (index == -1) {
            Ref key = name.object();
            obj = getitem(obj.get(), key.get());
        } else {
            Ref key = int_from_i64(index);
            obj = getitem(obj.get(), key.get());
        }
    }
    return obj;
}
struct Markup {
    SubString str;
    // MarkupIterator_next: 1 at the end, 2 with a literal, a field, or both
    int next(SubString& literal, bool& field_present, SubString& field_name, SubString& format_spec, char32_t& conversion, bool& needs_expanding) {
        literal = field_name = format_spec = SubString{};
        conversion = 0;
        needs_expanding = false;
        field_present = false;
        if (str.start >= str.end) return 1;
        const Cps& s = *str.str;
        std::size_t start = str.start;
        char32_t c = 0;
        bool markup_follows = false;
        while (str.start < str.end) {
            c = s[str.start++];
            if (c == U'{' || c == U'}') {
                markup_follows = true;
                break;
            }
        }
        bool at_end = str.start >= str.end;
        std::size_t len = str.start - start;
        if (c == U'}' && (at_end || c != s[str.start])) raise_new("ValueError", "Single '}' encountered in format string");
        if (at_end && c == U'{') raise_new("ValueError", "Single '{' encountered in format string");
        if (!at_end) {
            if (c == s[str.start]) {             // escaped: this literal ends with the brace, and no field follows
                ++str.start;
                markup_follows = false;
            } else {
                --len;
            }
        }
        literal = {str.str, start, start + len};
        if (!markup_follows) return 2;
        field_present = true;
        parse_field(field_name, format_spec, needs_expanding, conversion);
        return 2;
    }
    void parse_field(SubString& field_name, SubString& format_spec, bool& needs_expanding, char32_t& conversion) {
        const Cps& s = *str.str;
        char32_t c = 0;
        field_name.str = str.str;
        field_name.start = str.start;
        bool stop = false;
        while (str.start < str.end && !stop) {
            c = s[str.start++];
            switch (c) {
                case U'{': raise_new("ValueError", "unexpected '{' in field name");
                case U'[':
                    for (; str.start < str.end; ++str.start)
                        if (s[str.start] == U']') break;
                    break;
                case U'}': case U':': case U'!':
                    stop = true;
                    break;
                default: break;
            }
        }
        field_name.end = str.start - 1;
        if (c == U'!' || c == U':') {
            if (c == U'!') {
                if (str.start >= str.end) raise_new("ValueError", "end of string while looking for conversion specifier");
                conversion = s[str.start++];
                if (str.start < str.end) {
                    c = s[str.start++];
                    if (c == U'}') return;
                    if (c != U':') raise_new("ValueError", "expected ':' after conversion specifier");
                }
            }
            format_spec.str = str.str;
            format_spec.start = str.start;
            std::int64_t count = 1;
            while (str.start < str.end) {
                c = s[str.start++];
                if (c == U'{') {
                    needs_expanding = true;
                    ++count;
                } else if (c == U'}' && --count == 0) {
                    format_spec.end = str.start - 1;
                    return;
                }
            }
            raise_new("ValueError", "unmatched '{' in format spec");
        }
        if (c != U'}') raise_new("ValueError", "expected '}' before end of string");
    }
};
Ref convert_field(Obj obj, char32_t conversion) {  // do_conversion
    switch (conversion) {
        case U'r': return repr_of(obj);
        case U's': return str_of(obj);
        case U'a': return ascii_of(obj);
        default:
            raise_new("ValueError", "Unknown conversion specifier " + (conversion > 32 && conversion < 127 ? std::string(1, static_cast<char>(conversion)) : "\\x" + hex_text(static_cast<std::uint32_t>(conversion))));
    }
}
Ref build_string(const SubString& input, Obj args, Obj kwargs, int depth, AutoNumber* auto_number) {
    if (depth <= 0) raise_new("ValueError", "Max string recursion exceeded");
    Markup iter{input};
    Cps out;
    SubString literal, field_name, format_spec;
    bool field_present = false, needs_expanding = false;
    char32_t conversion = 0;
    while (iter.next(literal, field_present, field_name, format_spec, conversion, needs_expanding) == 2) {
        if (literal.end != literal.start) out.append(*literal.str, literal.start, literal.end - literal.start);
        if (!field_present) continue;
        Ref field = get_field_object(field_name, args, kwargs, auto_number);
        if (conversion != 0) field = convert_field(field.get(), conversion);
        Ref spec = needs_expanding ? build_string(format_spec, args, kwargs, depth - 1, auto_number) : format_spec.object_or_empty();
        Ref rendered = object_format(field.get(), as_str(spec.get()));
        const Str* text = as_str(rendered.get());
        for (std::size_t i = 0; i < text->length; ++i) out += text->at(i);
    }
    return str_from_codepoints(out);
}
Ref do_string_format(const Str* self, Obj args, Obj kwargs) {
    Cps text = cps_of(self);
    AutoNumber auto_number;
    return build_string(SubString{&text, 0, text.size()}, args, kwargs, 2, &auto_number);
}
}  // namespace

Ref str_format_m(Obj self, Args a) {              // METH_VARARGS | METH_KEYWORDS
    const Str* s = as_str(self);
    if (s == nullptr) raise_new("TypeError", "descriptor 'format' for 'str' objects doesn't apply to a '" + type_of(self)->name + "' object");
    std::vector<Obj> items;
    for (std::size_t i = 0; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    Ref kwargs;
    if (a.nkw != 0) {
        kwargs = dict_new();
        for (std::size_t k = 0; k < a.nkw; ++k) dict_set(static_cast<Dict*>(kwargs.get().object()), Obj::of(a.kwnames[k]), a.kw(k));
    }
    return do_string_format(s, args.get(), kwargs.get());
}
Ref str_format_map_m(Obj self, Args a) {
    onearg(a, "str.format_map");
    const Str* s = as_str(self);
    if (s == nullptr) raise_new("TypeError", "descriptor 'format_map' for 'str' objects doesn't apply to a '" + type_of(self)->name + "' object");
    return do_string_format(s, Obj{}, a.pos(0));
}

// PyObject_ASCII: the repr, and what is beyond ASCII in it escaped
Ref ascii_of(Obj v) {
    Ref r = repr_of(v);
    const Str* s = as_str(r.get());
    if (s->ascii) return r;
    std::string out;
    static const char* digit = "0123456789abcdef";
    auto hex = [&](char32_t c, int n) {
        for (int i = n - 1; i >= 0; --i) out += digit[(c >> (4 * i)) & 0xF];
    };
    for (std::size_t i = 0; i < s->length; ++i) {
        char32_t c = s->at(i);
        if (c < 128) {
            out += static_cast<char>(c);
        } else if (c < 256) {
            out += "\\x";
            hex(c, 2);
        } else if (c < 0x10000) {
            out += "\\u";
            hex(c, 4);
        } else {
            out += "\\U";
            hex(c, 8);
        }
    }
    return str_new(out);
}

// ---- _string: the same two machines, one step at a time, for string.Formatter (runtime/prelude/_string.py) ----
Ref i_markup_next(Obj, Args a) {                  // formatteriter_next, of a str from a position: (next, its 4 items) or None
    positional_only(a, "_markup_next", 2, 2);
    Cps text = cps_of(as_str(a.pos(0)));
    Markup iter{SubString{&text, static_cast<std::size_t>(a.pos(1).small_value()), text.size()}};
    SubString literal, field_name, format_spec;
    bool field_present = false, needs_expanding = false;
    char32_t conversion = 0;
    if (iter.next(literal, field_present, field_name, format_spec, conversion, needs_expanding) != 2) return none_ref();
    Ref first = literal.object();
    Ref name = field_name.object();
    Ref spec = field_present ? format_spec.object_or_empty() : format_spec.object();
    Ref conv = conversion == 0 ? none_ref() : str_from_codepoints(std::u32string_view(&conversion, 1));
    Ref next_pos = int_from_i64(static_cast<std::int64_t>(iter.str.start));
    Ref item = tuple_new({first.get(), name.get(), spec.get(), conv.get()});
    return tuple_new({next_pos.get(), item.get()});
}
Ref i_field_split(Obj, Args a) {                  // formatter_field_name_split: (first, where the rest begins)
    positional_only(a, "_field_split", 1, 1);
    Cps text = cps_of(as_str(a.pos(0)));
    SubString first;
    std::int64_t index = -1;
    FieldNameIterator rest;
    field_name_split(SubString{&text, 0, text.size()}, first, index, rest, nullptr);
    Ref first_obj = index != -1 ? int_from_i64(index) : first.object();
    Ref where = int_from_i64(static_cast<std::int64_t>(rest.index));
    return tuple_new({first_obj.get(), where.get()});
}
Ref i_field_next(Obj, Args a) {                   // fieldnameiter_next: (next, (is_attribute, name)) or None
    positional_only(a, "_field_next", 2, 2);
    Cps text = cps_of(as_str(a.pos(0)));
    FieldNameIterator it;
    it.index = static_cast<std::size_t>(a.pos(1).small_value());
    it.str = {&text, it.index, text.size()};
    bool is_attribute = false;
    std::int64_t index = -1;
    SubString name;
    if (it.next(is_attribute, index, name) != 2) return none_ref();
    Ref name_obj = index != -1 ? int_from_i64(index) : name.object();
    Ref is_attr = Ref::steal(boolean(is_attribute));
    Ref item = tuple_new({is_attr.get(), name_obj.get()});
    Ref next_pos = int_from_i64(static_cast<std::int64_t>(it.index));
    return tuple_new({next_pos.get(), item.get()});
}
}  // namespace bella
