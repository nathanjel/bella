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

// a number's text, parsed for its sign, digits, fraction and remainder (parse_number), then laid out
Ref float_text_field(std::string_view view, const FormatSpec& f) {
    char32_t sign_char = 0;
    if (view[0] == '-') {
        sign_char = U'-';
        view.remove_prefix(1);
    }
    auto is_digit = [](char c) { return c >= '0' && c <= '9'; };
    std::size_t pos = 0;
    while (pos < view.size() && is_digit(view[pos])) ++pos;
    std::string_view digits = view.substr(0, pos);
    bool has_decimal = pos < view.size() && view[pos] == '.';
    if (has_decimal) ++pos;
    std::size_t frac_start = pos;
    while (pos < view.size() && is_digit(view[pos])) ++pos;
    return number_field(f, sign_char, "", digits, has_decimal, view.substr(frac_start, pos - frac_start), widen(view.substr(pos)), false);
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
    return float_text_field(buf, f);
}
Ref format_complex_field(double re, double im, const FormatSpec& format) {   // format_complex_internal
    if (format.precision > INT_MAX) raise_new("ValueError", "precision too big");
    auto precision = static_cast<int>(format.precision);
    if (format.fill == U'0') raise_new("ValueError", "Zero padding is not allowed in complex format specifier");
    if (format.align == U'=') raise_new("ValueError", "'=' alignment flag is not allowed in complex format specifier");
    int flags = 0, default_precision = 6;
    char32_t type = format.type;
    bool add_parens = false, skip_re = false;
    if (format.alternate) flags |= DTSF_ALT;
    if (format.no_neg_0) flags |= DTSF_NO_NEG_0;
    if (type == 0) {                             // like str(self)
        type = U'r';
        default_precision = 0;
        if (re == 0.0 && std::copysign(1.0, re) == 1.0) skip_re = true;
        else add_parens = true;
    }
    if (type == U'n') type = U'g';
    if (precision < 0) precision = default_precision;
    else if (type == U'r') type = U'g';
    FormatSpec part = format;                    // the padding comes after both are composed
    part.fill = 0;
    part.align = U'<';
    part.width = -1;
    Cps re_text = cps_of(as_str(float_text_field(double_to_string(re, static_cast<char>(type), precision, flags), part).get()));
    if (!skip_re) part.sign = U'+';              // the imaginary part's sign always, unless it is all there is
    Cps im_text = cps_of(as_str(float_text_field(double_to_string(im, static_cast<char>(type), precision, flags), part).get()));
    Cps body;
    if (add_parens) body += U'(';
    if (!skip_re) body += re_text;
    body += im_text;
    body += U'j';
    if (add_parens) body += U')';
    auto nchars = static_cast<std::int64_t>(body.size());   // calc_padding
    std::int64_t total = format.width >= 0 ? std::max(nchars, format.width) : nchars;
    std::int64_t lpad = format.align == U'>' ? total - nchars : format.align == U'^' ? (total - nchars) / 2 : 0;
    std::int64_t rpad = total - nchars - lpad;
    Cps out(static_cast<std::size_t>(lpad), format.fill);
    out += body;
    out.append(static_cast<std::size_t>(rpad), format.fill);
    return str_from_codepoints(out);
}

// the __format__s: (format_spec, /)
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
Ref complex_format_field(Obj self, const Str* spec) {   // _PyComplex_FormatAdvancedWriter
    if (spec->length == 0) return str_of(self);
    FormatSpec f = parse_spec(self, spec, 0, U'>');
    switch (f.type) {
        case 0: case U'e': case U'E': case U'f': case U'F': case U'g': case U'G': case U'n': {
            auto* c = static_cast<const Complex*>(self.object());
            return format_complex_field(c->real, c->imag, f);
        }
        default: unknown_type(f.type, type_of(self));
    }
}
std::string complex_text(double real, double imag) {   // complex_repr
    std::string im = double_to_string(imag, 'r', 0, 0);
    if (real == 0.0 && std::copysign(1.0, real) == 1.0) return im + "j";
    if (im[0] != '-') im.insert(0, 1, '+');      // Py_DTSF_SIGN
    return "(" + double_to_string(real, 'r', 0, 0) + im + "j)";
}
Ref complex_format_dunder(Obj self, Args a) { return complex_format_field(self, spec_argument(a, "complex.__format__")); }
Ref str_format_dunder(Obj self, Args a) { return str_format_field(self, spec_argument(a, "str.__format__")); }
Ref int_format_dunder(Obj self, Args a) { return int_format_field(self, spec_argument(a, "int.__format__")); }
Ref float_format_dunder(Obj self, Args a) { return float_format_field(self, spec_argument(a, "float.__format__")); }

Ref object_format(Obj obj, const Str* spec) {     // PyObject_Format
    if (spec->length == 0) {
        if (is_exact_str(obj)) return Ref::share(obj);
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
    Ref only;                                    // the one field that is all there is: _PyUnicodeWriter_WriteStr, by reference
    std::size_t fields = 0;
    bool literals = false;
    while (iter.next(literal, field_present, field_name, format_spec, conversion, needs_expanding) == 2) {
        if (literal.end != literal.start) {
            literals = true;
            out.append(*literal.str, literal.start, literal.end - literal.start);
        }
        if (!field_present) continue;
        Ref field = get_field_object(field_name, args, kwargs, auto_number);
        if (conversion != 0) field = convert_field(field.get(), conversion);
        Ref spec = needs_expanding ? build_string(format_spec, args, kwargs, depth - 1, auto_number) : format_spec.object_or_empty();
        Ref rendered = object_format(field.get(), as_str(spec.get()));
        const Str* text = as_str(rendered.get());
        for (std::size_t i = 0; i < text->length; ++i) out += text->at(i);
        only = rendered;
        ++fields;
    }
    if (fields == 1 && !literals) return only;
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
    Ref result = do_string_format(s, args.get(), kwargs.get());
    if (!s->text.empty() && s->text.find_first_of("{}") == std::string::npos) return Ref::share(self);   // all of it one literal, written by reference
    return result;
}
Ref str_format_map_m(Obj self, Args a) {
    onearg(a, "str.format_map");
    const Str* s = as_str(self);
    if (s == nullptr) raise_new("TypeError", "descriptor 'format_map' for 'str' objects doesn't apply to a '" + type_of(self)->name + "' object");
    Ref result = do_string_format(s, Obj{}, a.pos(0));
    if (!s->text.empty() && s->text.find_first_of("{}") == std::string::npos) return Ref::share(self);
    return result;
}

// ---- str % args (Objects/unicode_format.c) ----
namespace {
constexpr int F_LJUST = 1, F_SIGN = 2, F_BLANK = 4, F_ALT = 8, F_ZERO = 16;
struct PercentArg {
    char32_t ch = 0;
    int flags = 0;
    std::int64_t width = -1;
    int prec = -1;
    bool sign = false;
    std::int64_t fmtstart = 0;
    Ref key;
};
// PyMapping_Check: mp_subscript, which a C type with sq_item alone has not
bool mapping_check(Obj v) {
    if (!v.is_object() && !v.is_small()) return false;
    if (type_lookup(type_of(v), intern("__getitem__")).is_unset()) return false;
    for (ClassObject* c : type_of(v)->mro)
        if (c->attrs.contains(intern("__getitem__"))) return !c->sequence_slots;
    return true;
}
struct Percent {
    Cps fmt;
    std::int64_t fmtcnt = 0, fmtpos = 0;
    std::int64_t arglen = 0, argidx = 0;
    Ref args;
    Obj dict;
    Cps out;

    char32_t read() const { return fmt[static_cast<std::size_t>(fmtpos)]; }
    [[noreturn]] void error(const PercentArg& arg, const char* exc, const std::string& message) const {   // FORMAT_ERROR
        if (!arg.key.get().is_unset()) {
            Ref shown = repr_of(arg.key.get());
            raise_new(exc, "format argument " + as_str(shown.get())->text + ": " + message);
        }
        if (argidx >= 0) raise_new(exc, "format argument " + std::to_string(argidx) + ": " + message);
        raise_new(exc, "format argument: " + message);
    }
    Obj next_arg(bool allow_one) {               // unicode_format_getnextarg
        std::int64_t index = argidx;
        if (index < arglen && (allow_one || arglen >= 0)) {
            ++argidx;
            if (arglen >= 0) return static_cast<Tuple*>(args.get().object())->items[static_cast<std::size_t>(index)];
            if (allow_one) return args.get();
        }
        raise_new("TypeError", "not enough arguments for format string (got " + std::to_string(arglen < 0 ? 1 : arglen) + ")");
    }
    void parse(PercentArg& arg) {                // unicode_format_arg_parse
        if (arg.ch == U'(') {
            if (dict.is_unset()) raise_new("TypeError", "format requires a mapping, not " + fully_qualified_name(type_of(args.get())));
            ++fmtpos;
            --fmtcnt;
            std::int64_t keystart = fmtpos;
            int pcount = 1;
            while (pcount > 0 && --fmtcnt >= 0) {
                arg.ch = read();
                if (arg.ch == U')') --pcount;
                else if (arg.ch == U'(') ++pcount;
                ++fmtpos;
            }
            std::int64_t keylen = fmtpos - keystart - 1;
            if (fmtcnt < 0 || pcount > 0) raise_new("ValueError", "stray % or incomplete format key at position " + std::to_string(arg.fmtstart));
            arg.key = str_from_codepoints(std::u32string_view(fmt).substr(static_cast<std::size_t>(keystart), static_cast<std::size_t>(keylen)));
            args = getitem(dict, arg.key.get());
            arglen = -3;
            argidx = -4;
        } else if (arglen < -1) {
            raise_new("ValueError", "format requires a parenthesised mapping key at position " + std::to_string(arg.fmtstart));
        }
        while (--fmtcnt >= 0) {                  // flags
            arg.ch = read();
            ++fmtpos;
            if (arg.ch == U'-') arg.flags |= F_LJUST;
            else if (arg.ch == U'+') arg.flags |= F_SIGN;
            else if (arg.ch == U' ') arg.flags |= F_BLANK;
            else if (arg.ch == U'#') arg.flags |= F_ALT;
            else if (arg.ch == U'0') arg.flags |= F_ZERO;
            else break;
        }
        if (arg.ch == U'*') {                    // width
            if (arglen < -1) raise_new("ValueError", "* cannot be used with a parenthesised mapping key at position " + std::to_string(arg.fmtstart));
            Obj v = next_arg(false);
            if (!is_int(v)) error(arg, "TypeError", "* requires int, not " + fully_qualified_name(type_of(v)));
            std::int64_t width = 0;
            if (!as_int(v, width)) {             // beyond an immediate: PyLong_AsSsize_t
                Ref big = int_from_i64(INT64_MAX);
                Ref small = int_from_i64(INT64_MIN);
                if (big_compare(v, big.get()) > 0 || big_compare(v, small.get()) < 0) error(arg, "OverflowError", "too big for width");
                width = clipped_index(v);
            }
            arg.width = width;
            if (arg.width < 0) {
                if (arg.width == INT64_MIN) error(arg, "OverflowError", "too big for width");
                arg.flags |= F_LJUST;
                arg.width = -arg.width;
            }
            if (--fmtcnt >= 0) {
                arg.ch = read();
                ++fmtpos;
            }
        } else if (arg.ch >= U'0' && arg.ch <= U'9') {
            arg.width = static_cast<std::int64_t>(arg.ch) - '0';
            while (--fmtcnt >= 0) {
                arg.ch = read();
                ++fmtpos;
                if (arg.ch < U'0' || arg.ch > U'9') break;
                std::int64_t digit = static_cast<std::int64_t>(arg.ch) - '0';
                if (arg.width > (INT64_MAX - digit) / 10) raise_new("ValueError", "width too big at position " + std::to_string(arg.fmtstart));
                arg.width = arg.width * 10 + digit;
            }
        }
        if (arg.ch == U'.') {                    // precision
            arg.prec = 0;
            if (--fmtcnt >= 0) {
                arg.ch = read();
                ++fmtpos;
            }
            if (arg.ch == U'*') {
                if (arglen < -1) raise_new("ValueError", "* cannot be used with a parenthesised mapping key at position " + std::to_string(arg.fmtstart));
                Obj v = next_arg(false);
                if (!is_int(v)) error(arg, "TypeError", "* requires int, not " + fully_qualified_name(type_of(v)));
                std::int64_t prec = 0;
                if (!as_int(v, prec) || prec > INT_MAX || prec < INT_MIN) error(arg, "OverflowError", "too big for precision");
                arg.prec = prec < 0 ? 0 : static_cast<int>(prec);
                if (--fmtcnt >= 0) {
                    arg.ch = read();
                    ++fmtpos;
                }
            } else if (arg.ch >= U'0' && arg.ch <= U'9') {
                arg.prec = static_cast<int>(arg.ch) - '0';
                while (--fmtcnt >= 0) {
                    arg.ch = read();
                    ++fmtpos;
                    if (arg.ch < U'0' || arg.ch > U'9') break;
                    int digit = static_cast<int>(arg.ch) - '0';
                    if (arg.prec > (INT_MAX - digit) / 10) raise_new("ValueError", "precision too big at position " + std::to_string(arg.fmtstart));
                    arg.prec = arg.prec * 10 + digit;
                }
            }
        }
        if (fmtcnt >= 0 && (arg.ch == U'h' || arg.ch == U'l' || arg.ch == U'L')) {   // ignored
            if (--fmtcnt >= 0) {
                arg.ch = read();
                ++fmtpos;
            }
        }
        if (fmtcnt < 0) raise_new("ValueError", "stray % at position " + std::to_string(arg.fmtstart));
    }
    Ref format_long(Obj v, PercentArg& arg) {    // mainformatlong, _PyUnicode_FormatLong
        auto type = static_cast<char>(arg.ch);
        auto wrong_type = [&]() {
            if (type == 'o' || type == 'x' || type == 'X') error(arg, "TypeError", std::string("%") + type + " requires an integer, not " + fully_qualified_name(type_of(v)));
            error(arg, "TypeError", std::string("%") + type + " requires a real number, not " + fully_qualified_name(type_of(v)));
        };
        ClassObject* cls = type_of(v);
        bool number = is_int(v) || is_float(v);
        for (const char* name : {"__index__", "__int__", "__float__"})
            if (!type_lookup(cls, intern(name)).is_unset()) number = true;
        if (!number) wrong_type();
        Ref iobj;
        if (is_int(v)) {
            iobj = Ref::share(v);
        } else {
            try {
                iobj = type == 'o' || type == 'x' || type == 'X' ? int_index_of(v) : int_from_number(v);
            } catch (const PyError& e) {
                if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
                wrong_type();
            }
        }
        if (arg.prec > INT_MAX - 3) raise_new("OverflowError", "precision too large");
        int base = type == 'o' ? 8 : type == 'x' || type == 'X' ? 16 : 10;
        std::string text = base == 10 ? big_text(iobj.get()) : int_in_base(iobj.get(), base);
        bool alt = (arg.flags & F_ALT) != 0;
        bool sign = text[0] == '-';
        std::string prefix = sign ? "-" : "";
        std::string_view rest = std::string_view(text).substr(sign ? 1 : 0);
        if (base != 10) {
            if (alt) prefix += rest.substr(0, 2);
            rest.remove_prefix(2);
        }
        std::string body(rest);
        if (arg.prec > static_cast<int>(body.size())) body.insert(0, static_cast<std::size_t>(arg.prec) - body.size(), '0');
        std::string result = prefix + body;
        if (type == 'X') for (char& c : result) if (c >= 'a' && c <= 'x') c = static_cast<char>(c - 32);
        return str_new(result);
    }
    Ref format_float(Obj v, PercentArg& arg) {   // formatfloat
        double x = 0.0;
        try {
            x = float_as_double(v);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            error(arg, "TypeError", std::string("%") + static_cast<char>(arg.ch) + " requires a real number, not " + fully_qualified_name(type_of(v)));
        }
        int prec = arg.prec < 0 ? 6 : arg.prec;
        return str_new(double_to_string(x, static_cast<char>(arg.ch), prec, (arg.flags & F_ALT) != 0 ? DTSF_ALT : 0));
    }
    char32_t format_char(Obj v, PercentArg& arg) {   // formatchar
        if (const Str* s = as_str(v)) {
            if (s->length == 1) return s->at(0);
            error(arg, "TypeError", "%c requires an integer or a unicode character, not a string of length " + std::to_string(s->length));
        }
        Ref index;
        try {
            index = int_index_of(v);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            error(arg, "TypeError", "%c requires an integer or a unicode character, not " + fully_qualified_name(type_of(v)));
        }
        std::int64_t x = 0;
        if (!as_int(index.get(), x) || x < 0 || x > 0x10FFFF) error(arg, "OverflowError", "%c argument not in range(0x110000)");
        return static_cast<char32_t>(x);
    }
    Ref format_one(PercentArg& arg) {            // unicode_format_arg_format
        Obj v = next_arg(true);
        switch (arg.ch) {
            case U's': return str_of(v);
            case U'r': return repr_of(v);
            case U'a': return ascii_of(v);
            case U'i': case U'd': case U'u': case U'o': case U'x': case U'X': {
                Ref r = format_long(v, arg);
                arg.sign = true;
                return r;
            }
            case U'e': case U'E': case U'f': case U'F': case U'g': case U'G': {
                Ref r = format_float(v, arg);
                arg.sign = true;
                return r;
            }
            case U'c': {
                char32_t ch = format_char(v, arg);
                return str_from_codepoints(std::u32string_view(&ch, 1));
            }
            default: break;
        }
        std::string at = std::to_string(arg.fmtstart), here = std::to_string(fmtpos - 1);
        if (arg.ch < 128 && ((arg.ch >= U'a' && arg.ch <= U'z') || (arg.ch >= U'A' && arg.ch <= U'Z')))
            raise_new("ValueError", std::string("unsupported format %") + static_cast<char>(arg.ch) + " at position " + at);
        if (arg.ch == U'\'') raise_new("ValueError", "stray % at position " + at + " or unexpected format character \"'\" at position " + here);
        if (arg.ch >= 32 && arg.ch < 127)
            raise_new("ValueError", "stray % at position " + at + " or unexpected format character '" + static_cast<char>(arg.ch) + "' at position " + here);
        if (arg.ch > 127) throw NotImplemented("a format character beyond ASCII in a % format's error (whether it is printable needs the Unicode database)");
        char code[8];
        std::snprintf(code, sizeof code, "%04X", static_cast<unsigned>(arg.ch));
        raise_new("ValueError", "stray % at position " + at + " or unexpected format character U+" + code + " at position " + here);
    }
    Ref last_text;                               // what the last conversion gave
    void output(PercentArg& arg, Obj value) {    // unicode_format_arg_output
        const Str* s = as_str(value);
        last_text = Ref::share(value);
        char32_t fill = arg.sign && (arg.flags & F_ZERO) != 0 ? U'0' : U' ';
        auto len = static_cast<std::int64_t>(s->length);
        Cps text = cps_of(s);
        if ((arg.width == -1 || arg.width <= len) && (arg.prec == -1 || arg.prec >= len) && (arg.flags & (F_SIGN | F_BLANK)) == 0) {
            out += text;
            return;
        }
        if ((arg.ch == U's' || arg.ch == U'r' || arg.ch == U'a') && arg.prec >= 0 && len > arg.prec) len = arg.prec;
        std::int64_t pindex = 0;
        char32_t signchar = 0;
        if (arg.sign) {
            char32_t ch = text[0];
            if (ch == U'-' || ch == U'+') {
                signchar = ch;
                --len;
                ++pindex;
            } else if ((arg.flags & F_SIGN) != 0) {
                signchar = U'+';
            } else if ((arg.flags & F_BLANK) != 0) {
                signchar = U' ';
            } else {
                arg.sign = false;
            }
        }
        if (arg.width < len) arg.width = len;
        if (arg.sign) {
            if (fill != U' ') out += signchar;
            if (arg.width > len) --arg.width;
        }
        bool prefixed = (arg.flags & F_ALT) != 0 && (arg.ch == U'x' || arg.ch == U'X' || arg.ch == U'o');
        if (prefixed) {
            if (fill != U' ') {
                out += U'0';
                out += arg.ch;
                pindex += 2;
            }
            arg.width -= 2;
            if (arg.width < 0) arg.width = 0;
            len -= 2;
        }
        if (arg.width > len && (arg.flags & F_LJUST) == 0) {
            out.append(static_cast<std::size_t>(arg.width - len), fill);
            arg.width = len;
        }
        if (fill == U' ') {
            if (arg.sign) out += signchar;
            if (prefixed) {
                out += U'0';
                out += arg.ch;
                pindex += 2;
            }
        }
        if (len > 0) out.append(text, static_cast<std::size_t>(pindex), static_cast<std::size_t>(len));
        if (arg.width > len) out.append(static_cast<std::size_t>(arg.width - len), U' ');
    }
    void one_argument() {                        // unicode_format_arg
        PercentArg arg;
        arg.ch = read();
        if (arg.ch == U'%') {
            ++fmtpos;
            --fmtcnt;
            out += U'%';
            return;
        }
        arg.fmtstart = fmtpos - 1;
        parse(arg);
        Ref str = format_one(arg);
        output(arg, str.get());
        if (!dict.is_unset() && argidx < arglen) raise_new("TypeError", "not all arguments converted during string formatting");
    }
};
}  // namespace

namespace {
// bytes % args and bytearray % args (PEP 461; Objects/bytesobject.c, _PyBytes_FormatEx, CPython 3.15.2): the C's loop over the
// format's octets, its conversions (format_obj, formatlong, formatfloat, byte_converter) and its words. A format octet is read
// as the C's `char` where the C reads it so (signed: an octet past 0x7f is no flag, no digit, no letter) and masked where it
// masks it.
struct BytesPercent {
    std::string_view fmt;
    std::size_t at = 0;                          // the C's fmt - format
    std::int64_t fmtcnt = 0;
    std::int64_t arglen = 0, argidx = 0;
    Ref args;
    Obj dict;
    Ref key;                                     // the mapping key being formatted, a bytes
    std::string out;

    int peek() const { return at < fmt.size() ? static_cast<signed char>(fmt[at]) : 0; }   // *fmt (the buffer ends in NUL)
    int next() { int c = peek(); ++at; return c; }                                        // *fmt++
    int next_masked() { int c = peek() & 0xff; ++at; return c; }                         // Py_CHARMASK(*fmt++)
    static bool digit(int c) { return c >= '0' && c <= '9'; }
    [[noreturn]] void error(const char* exc, const std::string& message) const {   // FORMAT_ERROR
        if (!key.get().is_unset()) {
            Ref shown = repr_of(key.get());
            raise_new(exc, "format argument " + as_str(shown.get())->text + ": " + message);
        }
        if (argidx >= 0) raise_new(exc, "format argument " + std::to_string(argidx) + ": " + message);
        raise_new(exc, "format argument: " + message);
    }
    Obj next_arg(bool allow_one) {               // getnextarg
        if (argidx < arglen) {
            std::int64_t index = argidx++;
            if (arglen >= 0) return static_cast<Tuple*>(args.get().object())->items[static_cast<std::size_t>(index)];
            if (allow_one) return args.get();
        }
        raise_new("TypeError", "not enough arguments for format string (got " + std::to_string(arglen < 0 ? 1 : arglen) + ")");
    }
    std::string long_text(Obj iobj, bool alt, int prec, int type) {   // _PyUnicode_FormatLong
        if (prec > INT_MAX - 3) raise_new("OverflowError", "precision too large");
        int base = type == 'o' ? 8 : type == 'x' || type == 'X' ? 16 : 10;
        std::string text = base == 10 ? big_text(iobj) : int_in_base(iobj, base);
        bool negative = text[0] == '-';
        std::string prefix = negative ? "-" : "";
        std::string_view rest = std::string_view(text).substr(negative ? 1 : 0);
        if (base != 10) {
            if (alt) prefix += rest.substr(0, 2);
            rest.remove_prefix(2);
        }
        std::string body(rest);
        if (prec > static_cast<int>(body.size())) body.insert(0, static_cast<std::size_t>(prec) - body.size(), '0');
        std::string result = prefix + body;
        if (type == 'X') for (char& ch : result) if (ch >= 'a' && ch <= 'x') ch = static_cast<char>(ch - 32);
        return result;
    }
    std::string format_long(Obj v, int flags, int prec, int type) {   // formatlong
        if (is_int(v)) return long_text(v, (flags & F_ALT) != 0, prec, type);
        ClassObject* cls = type_of(v);
        bool number = is_float(v) || is_kind(v, Kind::Complex) || is_kind(v, Kind::ComplexInstance);   // PyNumber_Check
        for (const char* name : {"__index__", "__int__", "__float__"})
            if (!type_lookup(cls, intern(name)).is_unset()) number = true;
        if (number) {
            Ref iobj;
            try {
                iobj = type == 'o' || type == 'x' || type == 'X' ? int_index_of(v) : int_from_number(v);
            } catch (const PyError& e) {
                if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            }
            if (!iobj.get().is_unset()) return long_text(iobj.get(), (flags & F_ALT) != 0, prec, type);
        }
        error("TypeError", std::string("%") + static_cast<char>(type) + " requires " +
                               (type == 'o' || type == 'x' || type == 'X' ? "an integer" : "a real number") + ", not " + fully_qualified_name(cls));
    }
    std::string format_float(Obj v, int flags, int prec, int type) {   // formatfloat
        double x = 0.0;
        try {
            x = float_as_double(v);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            error("TypeError", std::string("%") + static_cast<char>(type) + " requires a real number, not " + fully_qualified_name(type_of(v)));
        }
        return double_to_string(x, static_cast<char>(type), prec < 0 ? 6 : prec, (flags & F_ALT) != 0 ? DTSF_ALT : 0);
    }
    char byte_converter(Obj v) {                 // byte_converter
        if (is_bytes_like(v)) {
            const std::string& s = bytes_data(v);
            if (s.size() != 1)
                error("TypeError", std::string("%c requires an integer in range(256) or a single byte, not a ") +
                                       (is_kind(v, Kind::Bytes) ? "bytes" : "bytearray") + " object of length " + std::to_string(s.size()));
            return s[0];
        }
        if (is_int(v) || !type_lookup(type_of(v), intern("__index__")).is_unset()) {   // PyIndex_Check, then PyLong_AsLongAndOverflow
            Ref index = int_index_of(v);
            std::int64_t x = 0;
            if (!as_int(index.get(), x) || x < 0 || x > 255) error("OverflowError", "%c argument not in range(256)");
            return static_cast<char>(x);
        }
        error("TypeError", "%c requires an integer in range(256) or a single byte, not " + fully_qualified_name(type_of(v)));
    }
    std::string format_obj(Obj v) {              // format_obj: the octets of a bytes-like object, or of what __bytes__ gives
        if (is_bytes_like(v)) return bytes_data(v);
        if (!type_lookup(type_of(v), intern("__bytes__")).is_unset()) {
            Ref r = call_special(v, "__bytes__", {});
            if (!is_kind(r.get(), Kind::Bytes))
                raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__bytes__() must return a bytes, not " + fully_qualified_name(type_of(r.get())));
            return bytes_data(r.get());
        }
        if (!type_lookup(type_of(v), intern("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
        error("TypeError", "%b requires a bytes-like object, or an object that implements __bytes__, not " + fully_qualified_name(type_of(v)));
    }
    std::string position(std::size_t fmtstart) const { return std::to_string(fmtstart - 1); }   // the '%''s
    void run() {
        while (--fmtcnt >= 0) {
            if (peek() != '%') {                 // a run of plain octets up to the next %
                std::size_t found = fmt.find('%', at + 1);
                std::size_t limit = at + 1 + static_cast<std::size_t>(fmtcnt);
                std::int64_t len = found != std::string_view::npos && found < limit ? static_cast<std::int64_t>(found - at) : fmtcnt + 1;
                out.append(fmt.substr(at, static_cast<std::size_t>(len)));
                at += static_cast<std::size_t>(len);
                fmtcnt -= len - 1;
                continue;
            }
            int flags = 0;
            std::int64_t width = -1;
            int prec = -1;
            int c = 0;
            ++at;
            if (peek() == '%') {
                out += '%';
                ++at;
                --fmtcnt;
                continue;
            }
            key = Ref{};
            std::size_t fmtstart = at;
            if (peek() == '(') {
                if (dict.is_unset()) raise_new("TypeError", "format requires a mapping, not " + fully_qualified_name(type_of(args.get())));
                ++at;
                --fmtcnt;
                std::size_t keystart = at;
                int pcount = 1;
                while (pcount > 0 && --fmtcnt >= 0) {
                    if (peek() == ')') --pcount;
                    else if (peek() == '(') ++pcount;
                    ++at;
                }
                if (fmtcnt < 0 || pcount > 0) raise_new("ValueError", "stray % or incomplete format key at position " + position(fmtstart));
                key = bytes_new(fmt.substr(keystart, at - keystart - 1));
                args = getitem(dict, key.get());
                arglen = -3;
                argidx = -4;
            } else if (arglen < -1) {
                raise_new("ValueError", "format requires a parenthesised mapping key at position " + position(fmtstart));
            }
            while (--fmtcnt >= 0) {              // flags
                c = next();
                if (c == '-') flags |= F_LJUST;
                else if (c == '+') flags |= F_SIGN;
                else if (c == ' ') flags |= F_BLANK;
                else if (c == '#') flags |= F_ALT;
                else if (c == '0') flags |= F_ZERO;
                else break;
            }
            if (c == '*') {                      // width
                if (arglen < -1) raise_new("ValueError", "* cannot be used with a parenthesised mapping key at position " + position(fmtstart));
                Obj v = next_arg(false);
                if (!is_int(v)) error("TypeError", "* requires int, not " + fully_qualified_name(type_of(v)));
                if (!as_int(v, width) || width == INT64_MIN) error("OverflowError", "too big for width");   // PyLong_AsSsize_t
                if (width < 0) {
                    flags |= F_LJUST;
                    width = -width;
                }
                if (--fmtcnt >= 0) c = next();
            } else if (c >= 0 && digit(c)) {
                width = c - '0';
                while (--fmtcnt >= 0) {
                    c = next_masked();
                    if (!digit(c)) break;
                    if (width > (INT64_MAX - (c - '0')) / 10) raise_new("ValueError", "width too big at position " + position(fmtstart));
                    width = width * 10 + (c - '0');
                }
            }
            if (c == '.') {                      // precision
                prec = 0;
                if (--fmtcnt >= 0) c = next();
                if (c == '*') {
                    if (arglen < -1) raise_new("ValueError", "* cannot be used with a parenthesised mapping key at position " + position(fmtstart));
                    Obj v = next_arg(false);
                    if (!is_int(v)) error("TypeError", "* requires int, not " + fully_qualified_name(type_of(v)));
                    std::int64_t p = 0;
                    if (!as_int(v, p) || p > INT_MAX || p < INT_MIN) error("OverflowError", "too big for precision");   // PyLong_AsInt
                    prec = p < 0 ? 0 : static_cast<int>(p);
                    if (--fmtcnt >= 0) c = next();
                } else if (c >= 0 && digit(c)) {
                    prec = c - '0';
                    while (--fmtcnt >= 0) {
                        c = next_masked();
                        if (!digit(c)) break;
                        if (prec > (INT_MAX - (c - '0')) / 10) raise_new("ValueError", "precision too big at position " + position(fmtstart));
                        prec = prec * 10 + (c - '0');
                    }
                }
            }
            if (fmtcnt >= 0 && (c == 'h' || c == 'l' || c == 'L')) {
                if (--fmtcnt >= 0) c = next();
            }
            if (fmtcnt < 0) raise_new("ValueError", "stray % at position " + position(fmtstart));
            Obj v = next_arg(true);
            int sign = 0;
            char fill = ' ';
            std::string text;
            switch (c) {
                case 'r':
                case 'a': {                      // %r is only for 2/3 code; %a: PyObject_ASCII
                    Ref s = ascii_of(v);
                    text = as_str(s.get())->text;
                    if (prec >= 0 && static_cast<std::int64_t>(text.size()) > prec) text.resize(static_cast<std::size_t>(prec));
                    break;
                }
                case 's':
                case 'b':
                    text = format_obj(v);
                    if (prec >= 0 && static_cast<std::int64_t>(text.size()) > prec) text.resize(static_cast<std::size_t>(prec));
                    break;
                case 'i': case 'd': case 'u': case 'o': case 'x': case 'X':
                    text = format_long(v, flags, prec, c);
                    sign = 1;
                    if (flags & F_ZERO) fill = '0';
                    break;
                case 'e': case 'E': case 'f': case 'F': case 'g': case 'G':
                    text = format_float(v, flags, prec, c);
                    sign = 1;
                    if (flags & F_ZERO) fill = '0';
                    break;
                case 'c':
                    text = std::string(1, byte_converter(v));
                    break;
                default: {
                    std::string here = std::to_string(at - 1);
                    int masked = c & 0xff;
                    if ((masked >= 'a' && masked <= 'z') || (masked >= 'A' && masked <= 'Z'))   // Py_ISALPHA
                        raise_new("ValueError", std::string("unsupported format %") + static_cast<char>(c) + " at position " + position(fmtstart));
                    if (c == '\'') raise_new("ValueError", "stray % at position " + position(fmtstart) + " or unexpected format character \"'\" at position " + here);
                    if (c >= 32 && c < 127)
                        raise_new("ValueError", "stray % at position " + position(fmtstart) + " or unexpected format character '" + static_cast<char>(c) + "' at position " + here);
                    char code[8];
                    std::snprintf(code, sizeof code, "0x%02x", static_cast<unsigned>(masked));
                    raise_new("ValueError", "stray % at position " + position(fmtstart) + " or unexpected format character with code " + code + " at position " + here);
                }
            }
            std::size_t p = 0;
            auto len = static_cast<std::int64_t>(text.size());
            if (sign) {
                if (text[0] == '-' || text[0] == '+') {
                    sign = text[0];
                    ++p;
                    --len;
                } else if (flags & F_SIGN) sign = '+';
                else if (flags & F_BLANK) sign = ' ';
                else sign = 0;
            }
            if (width < len) width = len;
            if (sign) {
                if (fill != ' ') out += static_cast<char>(sign);
                if (width > len) --width;
            }
            bool prefixed = (flags & F_ALT) && (c == 'o' || c == 'x' || c == 'X');
            if (prefixed) {
                if (fill != ' ') {
                    out.append(text, p, 2);
                    p += 2;
                }
                width -= 2;
                if (width < 0) width = 0;
                len -= 2;
            }
            if (width > len && !(flags & F_LJUST)) {
                out.append(static_cast<std::size_t>(width - len), fill);
                width = len;
            }
            if (fill == ' ') {
                if (sign) out += static_cast<char>(sign);
                if (prefixed) {
                    out.append(text, p, 2);
                    p += 2;
                }
            }
            out.append(text, p, static_cast<std::size_t>(len));
            if (width > len) out.append(static_cast<std::size_t>(width - len), ' ');
            if (!dict.is_unset() && argidx < arglen) raise_new("TypeError", "not all arguments converted during bytes formatting");
        }
        if (argidx < arglen && dict.is_unset())
            raise_new("TypeError", "not all arguments converted during bytes formatting (required " + std::to_string(arglen < 0 ? 0 : argidx) +
                                       ", got " + std::to_string(arglen < 0 ? 1 : arglen) + ")");
    }
};
}  // namespace

Ref bytes_format(Obj format, Obj args, bool bytearray) {   // _PyBytes_FormatEx: a bytes, or a bytearray for a bytearray's %
    std::string octets = bytes_data(format);                // a copy: what the conversions run may change a bytearray
    BytesPercent ctx;
    ctx.fmt = octets;
    ctx.fmtcnt = static_cast<std::int64_t>(octets.size());
    ctx.args = Ref::share(args);
    if (is_kind(args, Kind::Tuple)) {
        ctx.arglen = static_cast<std::int64_t>(static_cast<Tuple*>(args.object())->items.size());
        ctx.argidx = 0;
    } else {
        ctx.arglen = -1;
        ctx.argidx = -2;
    }
    // a mapping: mp_subscript, and no tuple, bytes, str or bytearray
    if (!type_lookup(type_of(args), intern("__getitem__")).is_unset() && !is_kind(args, Kind::Tuple) && !is_bytes_like(args) && as_str(args) == nullptr)
        ctx.dict = args;
    ctx.run();
    if (bytearray) return own(new BytesObject(Kind::ByteArray, std::move(ctx.out)));
    return bytes_new(ctx.out);
}

bool is_mapping(Obj v) { return mapping_check(v); }
Ref str_mod(Obj format, Obj args) {              // PyUnicode_Format
    Percent ctx;
    ctx.fmt = cps_of(as_str(format));
    ctx.fmtcnt = static_cast<std::int64_t>(ctx.fmt.size());
    if (is_kind(args, Kind::Tuple)) {
        ctx.arglen = static_cast<std::int64_t>(static_cast<Tuple*>(args.object())->items.size());
        ctx.argidx = 0;
    } else {
        ctx.arglen = -1;
        ctx.argidx = -2;
    }
    if (mapping_check(args) && !is_kind(args, Kind::Tuple) && as_str(args) == nullptr) ctx.dict = args;
    ctx.args = Ref::share(args);
    while (--ctx.fmtcnt >= 0) {
        if (ctx.read() != U'%') {
            std::int64_t start = ctx.fmtpos++;
            while (ctx.fmtcnt >= 0 && ctx.fmtpos < static_cast<std::int64_t>(ctx.fmt.size()) && ctx.read() != U'%') {
                ++ctx.fmtpos;
                --ctx.fmtcnt;
            }
            if (ctx.fmtcnt < 0) --ctx.fmtpos;
            ctx.out.append(ctx.fmt, static_cast<std::size_t>(start), static_cast<std::size_t>(ctx.fmtpos - start));
        } else {
            ++ctx.fmtpos;
            ctx.one_argument();
        }
    }
    if (ctx.argidx < ctx.arglen && ctx.dict.is_unset())
        raise_new("TypeError", "not all arguments converted during string formatting (required " + std::to_string(ctx.arglen < 0 ? 0 : ctx.argidx) +
                                   ", got " + std::to_string(ctx.arglen < 0 ? 1 : ctx.arglen) + ")");
    // _PyUnicodeWriter_WriteStr: what is the whole result is written by reference, so it comes back as itself, of a subclass too
    if (!ctx.fmt.empty() && ctx.fmt.find(U'%') == Cps::npos) return Ref::share(format);
    if (ctx.fmt.size() == 2 && !ctx.last_text.get().is_unset()) return ctx.last_text;
    return str_from_codepoints(ctx.out);
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
