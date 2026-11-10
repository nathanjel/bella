// runtime/src/str.cpp -- the str methods the import system and the standard library call first
// (bella/runtime.hpp): searching, splitting, stripping and replacing, as Objects/unicodeobject.c
// and Objects/stringlib do them (CPython 3.15.2). Indices are code points; start and end are
// slice indices adjusted as ADJUST_INDICES does; whitespace is Py_UNICODE_ISSPACE; each argument
// error is CPython's for the method's calling convention. Where CPython returns the string itself
// (an exact str left unchanged: unicode_result_unchanged, a split or partition that finds
// nothing), so does this.
#include "bella/runtime.hpp"

#include <algorithm>
#include <cstdint>

namespace bella {

namespace {
using Cps = std::u32string;

Ref unchanged(Obj self) { return is_exact_str(self) ? Ref::share(self) : str_new(as_str(self)->text); }   // unicode_result_unchanged

const Str* self_str(Obj self, const char* method) {
    const Str* s = as_str(self);
    if (s == nullptr)
        raise_new("TypeError", std::string("descriptor '") + method + "' for 'str' objects doesn't apply to a '" +
                                   type_of(self)->name + "' object");
    return s;
}
Cps cps_of(const Str* s) {
    Cps out;
    out.reserve(s->length);
    for (std::size_t i = 0; i < s->length; ++i) out.push_back(s->at(i));
    return out;
}
Ref make(std::u32string_view cps) { return str_from_codepoints(cps); }
// The text of a str as searches read it, nothing copied: a call costs what it scans, as CPython's
struct Text {
    const Str* s;
    std::size_t size() const { return s->length; }
    char32_t operator[](std::size_t i) const { return s->at(i); }
};
template <class T, class U>
bool match_at(const T& s, const U& sub, std::int64_t at) {
    for (std::size_t k = 0; k < sub.size(); ++k)
        if (s[static_cast<std::size_t>(at) + k] != sub[k]) return false;
    return true;
}
// a piece of the string: the string itself when it is all of an exact str
Ref piece(Obj self, const Cps& cps, std::size_t from, std::size_t to) {
    if (from == 0 && to == cps.size() && is_exact_str(self)) return Ref::share(self);
    return make(std::u32string_view(cps).substr(from, to - from));
}

// Py_UNICODE_ISSPACE: the ASCII whitespace table, else _PyUnicode_IsWhitespace (Unicode 17.0.0's
// White_Space characters, as CPython's tables list them)
bool is_space(char32_t c) {
    if (c < 128) return c == ' ' || (c >= 0x09 && c <= 0x0D) || (c >= 0x1C && c <= 0x1F);
    switch (c) {
        case 0x85: case 0xA0: case 0x1680: case 0x2028: case 0x2029: case 0x202F: case 0x205F: case 0x3000: return true;
        default: return c >= 0x2000 && c <= 0x200A;
    }
}

void no_keywords(Args a, const char* method) {
    if (a.nkw != 0) raise_new("TypeError", std::string("str.") + method + "() takes no keyword arguments");
}
void check_positional(Args a, const char* name, std::size_t lo, std::size_t hi) {   // _PyArg_CheckPositional
    auto plural = [](std::size_t n) { return n == 1 ? " argument" : " arguments"; };
    if (a.npos < lo)
        raise_new("TypeError", std::string(name) + " expected " + (lo == hi ? "" : "at least ") + std::to_string(lo) + plural(lo) +
                                   ", got " + std::to_string(a.npos));
    if (a.npos > hi)
        raise_new("TypeError", std::string(name) + " expected " + (lo == hi ? "" : "at most ") + std::to_string(hi) + plural(hi) +
                                   ", got " + std::to_string(a.npos));
}
const Str* str_argument(Obj v, const char* name, const char* which) {      // _PyArg_BadArgument
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", std::string(name) + "() " + which + " must be str, not " + (v == None() ? "None" : type_of(v)->name));
    return s;
}
// _PyEval_SliceIndex: None keeps the default; an int, or an object with __index__
std::int64_t slice_index(Obj v, std::int64_t dflt) {
    if (v == None()) return dflt;
    std::int64_t x;
    if (as_int(v, x)) return x;
    if (type_lookup(type_of(v), intern("__index__")).is_unset())
        raise_new("TypeError", "slice indices must be integers or have an __index__ method");
    return clipped_index(v);
}
void adjust_indices(std::int64_t& start, std::int64_t& end, std::int64_t len) {   // ADJUST_INDICES
    if (end > len) end = len;
    else if (end < 0) {
        end += len;
        if (end < 0) end = 0;
    }
    if (start < 0) {
        start += len;
        if (start < 0) start = 0;
    }
}
// the arguments of find, rfind, index, rindex and count: (sub[, start[, end]], /)
struct Span {
    const Str* sub;
    std::int64_t start = 0, end = INT64_MAX;
};
Span find_args(Args a, const char* name) {
    no_keywords(a, name);
    check_positional(a, name, 1, 3);
    Span s{str_argument(a.pos(0), name, "argument 1")};
    if (a.npos > 1) s.start = slice_index(a.pos(1), 0);
    if (a.npos > 2) s.end = slice_index(a.pos(2), INT64_MAX);
    return s;
}
// any_find_slice: the index of sub in s[start:end], -1 if absent
template <class T, class U>
std::int64_t find_in(const T& s, const U& sub, std::int64_t start, std::int64_t end, int direction) {
    auto len = static_cast<std::int64_t>(s.size()), n = static_cast<std::int64_t>(sub.size());
    adjust_indices(start, end, len);
    if (end - start < n) return -1;
    if (n == 0) return direction > 0 ? start : end;
    if (direction > 0) {
        for (std::int64_t i = start; i + n <= end; ++i)
            if (match_at(s, sub, i)) return i;
    } else {
        for (std::int64_t i = end - n; i >= start; --i)
            if (match_at(s, sub, i)) return i;
    }
    return -1;
}

Ref find_like(Obj self, Args a, const char* name, int direction, bool raises) {
    const Str* s = self_str(self, name);
    Span sp = find_args(a, name);
    std::int64_t r = find_in(Text{s}, Text{sp.sub}, sp.start, sp.end, direction);
    if (r < 0 && raises) raise_new("ValueError", "substring not found");
    return Ref::steal(Obj::small(r));
}

// tailmatch: whether s[start:end] starts (direction < 0) or ends (> 0) with sub
bool tailmatch(Text s, Text sub, std::int64_t start, std::int64_t end, int direction) {
    adjust_indices(start, end, static_cast<std::int64_t>(s.size()));
    end -= static_cast<std::int64_t>(sub.size());
    if (end < start) return false;
    if (sub.size() == 0) return true;
    return match_at(s, sub, direction > 0 ? end : start);
}
Ref starts_ends(Obj self, Args a, const char* name, int direction) {
    const Str* s = self_str(self, name);
    no_keywords(a, name);
    check_positional(a, name, 1, 3);
    std::int64_t start = a.npos > 1 ? slice_index(a.pos(1), 0) : 0;
    std::int64_t end = a.npos > 2 ? slice_index(a.pos(2), INT64_MAX) : INT64_MAX;
    Text text{s};
    Obj sub = a.pos(0);
    if (is_kind(sub, Kind::Tuple)) {
        for (Obj item : static_cast<Tuple*>(sub.object())->items) {
            const Str* p = as_str(item);
            if (p == nullptr)
                raise_new("TypeError", std::string("tuple for ") + name + " must only contain str, not " + type_of(item)->name);
            if (tailmatch(text, Text{p}, start, end, direction)) return Ref::steal(boolean(true));
        }
        return Ref::steal(boolean(false));
    }
    const Str* p = as_str(sub);
    if (p == nullptr)
        raise_new("TypeError", std::string(name) + " first arg must be str or a tuple of str, not " + type_of(sub)->name);
    return Ref::steal(boolean(tailmatch(text, Text{p}, start, end, direction)));
}

// METH_O: (sep, /)
Obj one_argument(Args a, const char* name) {
    no_keywords(a, name);
    if (a.npos != 1)
        raise_new("TypeError", std::string("str.") + name + "() takes exactly one argument (" + std::to_string(a.npos) + " given)");
    return a.pos(0);
}
Ref partition_like(Obj self, Args a, const char* name, int direction) {
    const Str* s = self_str(self, name);
    Obj sep = one_argument(a, name);
    const Str* sp = as_str(sep);
    if (sp == nullptr) raise_new("TypeError", "must be str, not " + type_of(sep)->name);
    Cps text = cps_of(s), cut = cps_of(sp);
    Ref empty = str_new("");
    if (text.size() < cut.size())
        return direction > 0 ? tuple_new({self, empty.get(), empty.get()}) : tuple_new({empty.get(), empty.get(), self});
    if (cut.empty()) raise_new("ValueError", "empty separator");
    std::int64_t at = find_in(text, cut, 0, INT64_MAX, direction);
    if (at < 0) {
        return direction > 0 ? tuple_new({self, empty.get(), empty.get()})   // stringlib's: the object itself, of a subclass too
                             : tuple_new({empty.get(), empty.get(), self});
    }
    auto pos = static_cast<std::size_t>(at);
    Ref before = piece(self, text, 0, pos), after = piece(self, text, pos + cut.size(), text.size());
    return tuple_new({before.get(), sep, after.get()});
}

// _PyArg_UnpackKeywords' counts, in its order: all the arguments, the positional ones, then those
// that can only be positional
void unpack_check(Args a, const char* name, std::size_t minposonly, std::size_t maxpos, std::size_t maxargs) {
    std::size_t given = a.npos + a.nkw;
    if (given > maxargs)
        raise_new("TypeError", std::string(name) + "() takes at most " + std::to_string(maxargs) + " " +
                                   (a.npos == 0 ? "keyword " : "") + "argument" + (maxargs == 1 ? "" : "s") + " (" +
                                   std::to_string(given) + " given)");
    if (a.npos > maxpos)
        raise_new("TypeError", std::string(name) + "() takes at most " + std::to_string(maxpos) + " positional argument" +
                                   (maxpos == 1 ? "" : "s") + " (" + std::to_string(a.npos) + " given)");
    if (a.npos < minposonly)
        raise_new("TypeError", std::string(name) + "() takes " + (minposonly < maxpos ? "at least " : "exactly ") +
                                   std::to_string(minposonly) + " positional argument" + (minposonly == 1 ? "" : "s") + " (" +
                                   std::to_string(a.npos) + " given)");
}

// split and rsplit: (sep=None, maxsplit=-1), positional or by keyword
void split_args(Args a, const char* name, Obj& sep, std::int64_t& maxsplit) {
    static const char* const params[] = {"sep", "maxsplit"};
    Obj given[2] = {};
    unpack_check(a, name, 0, 2, 2);
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::size_t j = a.kwnames[k]->text == params[0] ? 0 : a.kwnames[k]->text == params[1] ? 1 : 2;
        if (j == 2)                  // CPython's message may suggest a keyword (_Py_CalculateSuggestions)
            throw NotImplemented(std::string("str.") + name + "() with an unexpected keyword argument (the suggestion in its message)");
        if (!given[j].is_unset())
            raise_new("TypeError", std::string("argument for ") + name + "() given by name ('" + params[j] + "') and position (" +
                                       std::to_string(j + 1) + ")");
        given[j] = a.kw(k);
    }
    sep = given[0].is_unset() ? None() : given[0];
    maxsplit = given[1].is_unset() ? -1 : ssize_arg(given[1]);
}
Ref split_like(Obj self, Args a, const char* name, int direction) {
    const Str* s = self_str(self, name);
    Obj sep;
    std::int64_t maxsplit;
    split_args(a, name, sep, maxsplit);
    if (sep != None() && as_str(sep) == nullptr) raise_new("TypeError", "must be str or None, not " + type_of(sep)->name);
    if (maxsplit < 0) maxsplit = INT64_MAX;
    Cps text = cps_of(s);
    std::vector<Ref> parts;
    auto n = static_cast<std::int64_t>(text.size());
    if (sep == None()) {                         // split_whitespace, rsplit_whitespace
        if (direction > 0) {
            std::int64_t i = 0;
            while (maxsplit-- > 0) {
                while (i < n && is_space(text[i])) ++i;
                if (i == n) break;
                std::int64_t j = i;
                ++i;
                while (i < n && !is_space(text[i])) ++i;
                parts.push_back(piece(self, text, j, i));
            }
            if (i < n) {
                while (i < n && is_space(text[i])) ++i;
                if (i != n) parts.push_back(make(std::u32string_view(text).substr(static_cast<std::size_t>(i))));   // SPLIT_ADD: a new string
            }
        } else {
            std::int64_t i = n - 1;
            while (maxsplit-- > 0) {
                while (i >= 0 && is_space(text[i])) --i;
                if (i < 0) break;
                std::int64_t j = i;
                --i;
                while (i >= 0 && !is_space(text[i])) --i;
                parts.push_back(piece(self, text, i + 1, j + 1));
            }
            if (i >= 0) {
                while (i >= 0 && is_space(text[i])) --i;
                if (i >= 0) parts.push_back(make(std::u32string_view(text).substr(0, static_cast<std::size_t>(i + 1))));
            }
            std::reverse(parts.begin(), parts.end());
        }
    } else {
        Cps cut = cps_of(as_str(sep));
        if (cut.empty()) raise_new("ValueError", "empty separator");
        auto m = static_cast<std::int64_t>(cut.size());
        if (direction > 0) {
            std::int64_t i = 0;
            while (maxsplit-- > 0) {
                std::int64_t at = find_in(text, cut, i, n, 1);
                if (at < 0) break;
                parts.push_back(piece(self, text, i, at));
                i = at + m;
            }
            parts.push_back(piece(self, text, i, n));
        } else {
            std::int64_t j = n;
            while (maxsplit-- > 0) {
                std::int64_t at = find_in(text, cut, 0, j, -1);
                if (at < 0) break;
                parts.push_back(piece(self, text, at + m, j));
                j = at;
            }
            parts.push_back(piece(self, text, 0, j));
            std::reverse(parts.begin(), parts.end());
        }
    }
    Ref out = list_new({});
    for (Ref& p : parts) list_append(out.get(), p.get());
    return out;
}

// strip, lstrip, rstrip: (chars=None, /); which: -1 left, 1 right, 0 both
Ref strip_like(Obj self, Args a, const char* name, int which) {
    const Str* s = self_str(self, name);
    no_keywords(a, name);
    check_positional(a, name, 0, 1);
    Obj chars = a.npos == 1 ? a.pos(0) : None();
    Cps text = cps_of(s), set;
    bool whitespace = chars == None();
    if (!whitespace) {
        const Str* c = as_str(chars);
        if (c == nullptr) raise_new("TypeError", std::string(name) + " arg must be None or str");
        set = cps_of(c);
    }
    auto strips = [&](char32_t ch) { return whitespace ? is_space(ch) : set.find(ch) != Cps::npos; };
    std::size_t i = 0, j = text.size();
    if (which <= 0)
        while (i < j && strips(text[i])) ++i;
    if (which >= 0)
        while (j > i && strips(text[j - 1])) --j;
    return piece(self, text, i, j);
}
}  // namespace

// ---- the case and category tables (runtime/src/unicode.cpp, Objects/unicodectype.c): an ASCII str by its bytes, which the
// tables agree with, anything else by its code points, as Objects/unicodeobject.c's do_* functions walk them ----
namespace {
bool is_lower(char c) { return c >= 'a' && c <= 'z'; }
bool is_upper(char c) { return c >= 'A' && c <= 'Z'; }
char to_lower(char c) { return is_upper(c) ? static_cast<char>(c + 32) : c; }
char to_upper(char c) { return is_lower(c) ? static_cast<char>(c - 32) : c; }
bool is_digit(char c) { return c >= '0' && c <= '9'; }
// handle_capital_sigma: U+03A3 is final after a cased letter (case-ignorable ones passed over) and not before one
std::uint32_t capital_sigma(const Str* s, std::size_t i) {
    std::size_t j = i;
    std::uint32_t c = 0;
    bool found = false;
    while (j > 0) {
        c = s->at(--j);
        if (!unicode_is_case_ignorable(c)) {
            found = true;
            break;
        }
    }
    bool final_sigma = found && unicode_is_cased(c);
    if (final_sigma) {
        std::size_t k = i + 1;
        for (; k < s->length; ++k) {
            c = s->at(k);
            if (!unicode_is_case_ignorable(c)) break;
        }
        final_sigma = k == s->length || !unicode_is_cased(c);
    }
    return final_sigma ? 0x3C2 : 0x3C3;
}
int lower_ucs4(const Str* s, std::size_t i, std::uint32_t c, std::uint32_t* mapped) {   // lower_ucs4: the obscure special case
    if (c == 0x3A3) {
        mapped[0] = capital_sigma(s, i);
        return 1;
    }
    return unicode_lower_full(c, mapped);
}
void put(std::u32string& out, const std::uint32_t* mapped, int n) {
    for (int k = 0; k < n; ++k) out.push_back(static_cast<char32_t>(mapped[k]));
}
// case_operation: a new str, the ASCII one by its bytes (ascii_upper_or_lower and the others), the rest by `perform`
template <class Ascii, class Perform>
Ref case_operation(Obj self, Args a, const char* method, Ascii ascii, Perform perform) {
    noargs(a, std::string("str.") + method);
    const Str* s = self_str(self, method);
    if (s->ascii) {
        std::string out = s->text;
        ascii(out);
        return str_new(out);
    }
    std::u32string out;
    out.reserve(s->length);
    perform(s, out);
    return str_from_codepoints(out);
}
// a predicate true of every character, and false of none at all
template <class Ascii, class Unicode>
Ref every(Obj self, Args a, const char* method, Ascii ascii, Unicode unicode) {
    noargs(a, std::string("str.") + method);
    const Str* s = self_str(self, method);
    if (s->length == 0) return Ref::steal(boolean(false));
    if (s->ascii) return Ref::steal(boolean(std::all_of(s->text.begin(), s->text.end(), ascii)));
    for (std::size_t i = 0; i < s->length; ++i)
        if (!unicode(static_cast<std::uint32_t>(s->at(i)))) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}
bool is_ascii_space(char c) { return c == ' ' || (c >= '\t' && c <= '\r') || (c >= '\x1c' && c <= '\x1f'); }
// the fill character's converter, convert_uc
char32_t fill_character(Obj v) {
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "The fill character must be a unicode character, not " + type_of(v)->name);
    if (s->length != 1) raise_new("TypeError", "The fill character must be exactly one character long");
    return s->at(0);
}
Ref padded(const Str* s, std::size_t left, std::size_t right, char32_t fill) {   // pad
    std::size_t total = left + s->length + right;
    if (total > (std::size_t{1} << 32)) throw NotImplemented("a str of more than 2**32 characters");
    std::u32string out(left, fill);
    for (std::size_t i = 0; i < s->length; ++i) out += s->at(i);
    out.append(right, fill);
    return str_from_codepoints(out);
}
template <int mode>
Ref justify(Obj self, Args a) {                  // center, ljust, rjust: (width, fillchar=' ', /)
    const char* method = mode == 0 ? "center" : mode < 0 ? "ljust" : "rjust";
    clinic(a, method, std::string("str.") + method, 1, 2);
    const Str* s = self_str(self, method);
    std::int64_t width = ssize_arg(a.pos(0));
    char32_t fill = a.npos == 2 ? fill_character(a.pos(1)) : U' ';
    auto length = static_cast<std::int64_t>(s->length);
    if (length >= width) return unchanged(self);
    std::int64_t margin = width - length;
    std::int64_t left = mode == 0 ? margin / 2 + (margin & width & 1) : mode < 0 ? 0 : margin;
    return padded(s, static_cast<std::size_t>(left), static_cast<std::size_t>(margin - left), fill);
}
// PyMapping_GetOptionalItem and charmaptranslate_lookup: a LookupError means "as it is"
enum class Translated { AsItIs, Deleted, Char, Text };
Translated translate_lookup(char32_t c, Obj mapping, Ref& item, char32_t& replace) {
    Ref key = int_from_i64(static_cast<std::int64_t>(c));
    try {
        item = getitem(mapping, key.get());
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("LookupError"))) throw;
        item = Ref{};
        return Translated::AsItIs;
    }
    if (item.get() == None()) return Translated::Deleted;
    if (is_int(item.get())) {
        std::int64_t value = 0;
        // PyLong_AsLong says -1 of what it cannot hold, and this error replaces its own
        if (!as_int(item.get(), value) || value < 0 || value > 0x10FFFF) raise_new("ValueError", "character mapping must be in range(0x110000)");
        replace = static_cast<char32_t>(value);
        return Translated::Char;
    }
    if (as_str(item.get()) != nullptr) return Translated::Text;
    raise_new("TypeError", "character mapping must return integer, None or str");
}
}  // namespace

Ref str_lower_m(Obj self, Args a) {               // do_lower
    return case_operation(self, a, "lower", [](std::string& t) { std::transform(t.begin(), t.end(), t.begin(), to_lower); },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              for (std::size_t i = 0; i < s->length; ++i) put(out, mapped, lower_ucs4(s, i, s->at(i), mapped));
                          });
}
Ref str_casefold_m(Obj self, Args a) {            // do_casefold
    return case_operation(self, a, "casefold", [](std::string& t) { std::transform(t.begin(), t.end(), t.begin(), to_lower); },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              for (std::size_t i = 0; i < s->length; ++i) put(out, mapped, unicode_fold_full(s->at(i), mapped));
                          });
}
Ref str_upper_m(Obj self, Args a) {               // do_upper
    return case_operation(self, a, "upper", [](std::string& t) { std::transform(t.begin(), t.end(), t.begin(), to_upper); },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              for (std::size_t i = 0; i < s->length; ++i) put(out, mapped, unicode_upper_full(s->at(i), mapped));
                          });
}
Ref str_swapcase_m(Obj self, Args a) {            // do_swapcase
    return case_operation(self, a, "swapcase",
                          [](std::string& t) { std::transform(t.begin(), t.end(), t.begin(), [](char c) { return is_upper(c) ? to_lower(c) : to_upper(c); }); },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              for (std::size_t i = 0; i < s->length; ++i) {
                                  std::uint32_t c = s->at(i);
                                  if (unicode_is_uppercase(c)) put(out, mapped, lower_ucs4(s, i, c, mapped));
                                  else if (unicode_is_lowercase(c)) put(out, mapped, unicode_upper_full(c, mapped));
                                  else out.push_back(static_cast<char32_t>(c));
                              }
                          });
}
Ref str_capitalize_m(Obj self, Args a) {          // do_capitalize: the first character's titlecase, the rest lowered
    return case_operation(self, a, "capitalize",
                          [](std::string& t) { for (std::size_t i = 0; i < t.size(); ++i) t[i] = i == 0 ? to_upper(t[i]) : to_lower(t[i]); },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              if (s->length == 0) return;
                              put(out, mapped, unicode_title_full(s->at(0), mapped));
                              for (std::size_t i = 1; i < s->length; ++i) put(out, mapped, lower_ucs4(s, i, s->at(i), mapped));
                          });
}
Ref str_title_m(Obj self, Args a) {               // do_title: a letter after a cased one is lowered
    return case_operation(self, a, "title",
                          [](std::string& t) {
                              bool previous_is_cased = false;
                              for (char& c : t) {
                                  c = previous_is_cased ? to_lower(c) : to_upper(c);
                                  previous_is_cased = is_lower(c) || is_upper(c);
                              }
                          },
                          [](const Str* s, std::u32string& out) {
                              std::uint32_t mapped[3];
                              bool previous_is_cased = false;
                              for (std::size_t i = 0; i < s->length; ++i) {
                                  std::uint32_t c = s->at(i);
                                  put(out, mapped, previous_is_cased ? lower_ucs4(s, i, c, mapped) : unicode_title_full(c, mapped));
                                  previous_is_cased = unicode_is_cased(c);
                              }
                          });
}
Ref str_isalpha_m(Obj self, Args a) { return every(self, a, "isalpha", [](char c) { return is_lower(c) || is_upper(c); }, unicode_is_alpha); }
Ref str_isalnum_m(Obj self, Args a) { return every(self, a, "isalnum", [](char c) { return is_lower(c) || is_upper(c) || is_digit(c); }, unicode_is_alnum); }
Ref str_isdigit_m(Obj self, Args a) { return every(self, a, "isdigit", is_digit, unicode_is_digit); }
Ref str_isdecimal_m(Obj self, Args a) { return every(self, a, "isdecimal", is_digit, unicode_is_decimal); }
Ref str_isnumeric_m(Obj self, Args a) { return every(self, a, "isnumeric", is_digit, unicode_is_numeric); }
Ref str_isspace_m(Obj self, Args a) { return every(self, a, "isspace", is_ascii_space, unicode_is_space); }
Ref str_isprintable_m(Obj self, Args a) {        // true of nothing at all
    noargs(a, "str.isprintable");
    const Str* s = self_str(self, "isprintable");
    if (s->ascii) return Ref::steal(boolean(std::all_of(s->text.begin(), s->text.end(), [](char c) { return c >= ' ' && c <= '~'; })));
    for (std::size_t i = 0; i < s->length; ++i)
        if (!unicode_is_printable(s->at(i))) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}
Ref str_isidentifier_m(Obj self, Args a) {
    noargs(a, "str.isidentifier");
    const Str* s = self_str(self, "isidentifier");   // PyUnicode_IsIdentifier
    if (s->length == 0) return Ref::steal(boolean(false));
    if (s->at(0) != U'_' && !unicode_is_xid_start(s->at(0))) return Ref::steal(boolean(false));
    for (std::size_t i = 1; i < s->length; ++i)
        if (!unicode_is_xid_continue(s->at(i))) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}
Ref str_islower_m(Obj self, Args a) {            // unicode_islower_impl
    noargs(a, "str.islower");
    const Str* s = self_str(self, "islower");
    bool cased = false;
    for (std::size_t i = 0; i < s->length; ++i) {
        std::uint32_t c = s->at(i);
        if (unicode_is_uppercase(c) || unicode_is_titlecase(c)) return Ref::steal(boolean(false));
        cased = cased || unicode_is_lowercase(c);
    }
    return Ref::steal(boolean(cased));
}
Ref str_isupper_m(Obj self, Args a) {            // unicode_isupper_impl
    noargs(a, "str.isupper");
    const Str* s = self_str(self, "isupper");
    bool cased = false;
    for (std::size_t i = 0; i < s->length; ++i) {
        std::uint32_t c = s->at(i);
        if (unicode_is_lowercase(c) || unicode_is_titlecase(c)) return Ref::steal(boolean(false));
        cased = cased || unicode_is_uppercase(c);
    }
    return Ref::steal(boolean(cased));
}
Ref str_istitle_m(Obj self, Args a) {            // unicode_istitle_impl
    noargs(a, "str.istitle");
    const Str* s = self_str(self, "istitle");
    bool cased = false, previous_is_cased = false;
    for (std::size_t i = 0; i < s->length; ++i) {
        std::uint32_t c = s->at(i);
        if (unicode_is_uppercase(c) || unicode_is_titlecase(c)) {
            if (previous_is_cased) return Ref::steal(boolean(false));
            previous_is_cased = cased = true;
        } else if (unicode_is_lowercase(c)) {
            if (!previous_is_cased) return Ref::steal(boolean(false));
            previous_is_cased = cased = true;
        } else {
            previous_is_cased = false;
        }
    }
    return Ref::steal(boolean(cased));
}
Ref str_center_m(Obj self, Args a) { return justify<0>(self, a); }
Ref str_ljust_m(Obj self, Args a) { return justify<-1>(self, a); }
Ref str_rjust_m(Obj self, Args a) { return justify<1>(self, a); }
Ref str_zfill_m(Obj self, Args a) {              // unicode_zfill_impl: METH_O
    onearg(a, "str.zfill");
    const Str* s = self_str(self, "zfill");
    std::int64_t width = ssize_arg(a.pos(0));
    if (static_cast<std::int64_t>(s->length) >= width) return unchanged(self);
    auto fill = static_cast<std::size_t>(width - static_cast<std::int64_t>(s->length));
    std::u32string out(fill, U'0');
    for (std::size_t i = 0; i < s->length; ++i) out += s->at(i);
    if (out[fill] == U'+' || out[fill] == U'-') {   // the sign goes first
        out[0] = out[fill];
        out[fill] = U'0';
    }
    return str_from_codepoints(out);
}
Ref str_removeprefix_m(Obj self, Args a) {
    onearg(a, "str.removeprefix");
    const Str* s = self_str(self, "removeprefix");
    const Str* p = as_str(a.pos(0));
    if (p == nullptr) raise_new("TypeError", "removeprefix() argument must be str, not " + (a.pos(0) == None() ? std::string("None") : type_of(a.pos(0))->name));
    if (p->text.empty() || !s->text.starts_with(p->text)) return unchanged(self);
    return str_new(std::string_view(s->text).substr(p->text.size()));
}
Ref str_removesuffix_m(Obj self, Args a) {
    onearg(a, "str.removesuffix");
    const Str* s = self_str(self, "removesuffix");
    const Str* p = as_str(a.pos(0));
    if (p == nullptr) raise_new("TypeError", "removesuffix() argument must be str, not " + (a.pos(0) == None() ? std::string("None") : type_of(a.pos(0))->name));
    if (p->text.empty() || !s->text.ends_with(p->text)) return unchanged(self);
    return str_new(std::string_view(s->text).substr(0, s->text.size() - p->text.size()));
}
Ref str_splitlines_m(Obj self, Args a) {         // unicode_splitlines_impl(keepends=False)
    const Str* s = self_str(self, "splitlines");
    std::size_t total = a.npos + a.nkw;
    if (total > 1) raise_new("TypeError", std::string("splitlines() takes at most 1 ") + (a.npos != 0 ? "" : "keyword ") + "argument (" + std::to_string(total) + " given)");
    bool keepends = false;
    if (a.npos == 1) keepends = truth(a.pos(0));
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k]->text != "keepends") unexpected_keyword("splitlines()", a.kwnames[k], {"keepends"});
        keepends = truth(a.kw(k));
    }
    auto is_break = [](char32_t c) {             // Py_UNICODE_ISLINEBREAK
        return c == U'\n' || c == U'\v' || c == U'\f' || c == U'\r' || c == 0x1c || c == 0x1d || c == 0x1e || c == 0x85 || c == 0x2028 || c == 0x2029;
    };
    Ref out = list_new({});
    std::size_t n = s->length;
    std::u32string line;
    for (std::size_t i = 0; i < n;) {
        std::size_t j = i;
        while (i < n && !is_break(s->at(i))) ++i;
        std::size_t eol = i;
        if (i < n) {
            i += s->at(i) == U'\r' && i + 1 < n && s->at(i + 1) == U'\n' ? 2 : 1;
            if (keepends) eol = i;
        }
        if (j == 0 && eol == n && is_exact_str(self)) {   // no line break, or one line whole: the object itself, when it is exactly a str (STRINGLIB_CHECK_EXACT; review F17 #13)
            list_append(out.get(), self);
            break;
        }
        line.clear();
        for (std::size_t k = j; k < eol; ++k) line += s->at(k);
        Ref item = str_from_codepoints(line);
        list_append(out.get(), item.get());
    }
    return out;
}
Ref str_expandtabs_m(Obj self, Args a) {         // unicode_expandtabs_impl(tabsize=8)
    const Str* s = self_str(self, "expandtabs");
    std::size_t total = a.npos + a.nkw;
    if (total > 1) raise_new("TypeError", std::string("expandtabs() takes at most 1 ") + (a.npos != 0 ? "" : "keyword ") + "argument (" + std::to_string(total) + " given)");
    Obj given = a.npos == 1 ? a.pos(0) : Obj{};
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k]->text != "tabsize") unexpected_keyword("expandtabs()", a.kwnames[k], {"tabsize"});
        given = a.kw(k);
    }
    int tabsize = given.is_unset() ? 8 : c_int_arg(given);
    bool found = false;
    std::int64_t line_pos = 0;
    std::u32string out;
    for (std::size_t i = 0; i < s->length; ++i) {
        char32_t ch = s->at(i);
        if (ch == U'\t') {
            found = true;
            if (tabsize > 0) {
                std::int64_t incr = tabsize - (line_pos % tabsize);
                if (static_cast<std::int64_t>(out.size()) + incr > (std::int64_t{1} << 32)) throw NotImplemented("a str of more than 2**32 characters");
                line_pos += incr;
                out.append(static_cast<std::size_t>(incr), U' ');
            }
        } else {
            ++line_pos;
            out += ch;
            if (ch == U'\n' || ch == U'\r') line_pos = 0;
        }
    }
    return found ? str_from_codepoints(out) : unchanged(self);
}
Ref str_translate_m(Obj self, Args a) {          // _PyUnicode_TranslateCharmap with "ignore"
    onearg(a, "str.translate");
    const Str* s = self_str(self, "translate");
    Obj mapping = a.pos(0);
    std::u32string out;
    std::size_t i = 0, n = s->length;
    Ref item;
    char32_t replace = 0;
    if (s->ascii) {                              // unicode_fast_translate: an answer it can keep, it keeps
        unsigned char table[128];
        std::fill(std::begin(table), std::end(table), 0xff);
        bool all = true;
        for (; i < n; ++i) {
            auto ch = static_cast<unsigned char>(s->text[i]);
            if (table[ch] == 0xff) {
                Translated t = translate_lookup(ch, mapping, item, replace);
                if (t == Translated::Deleted) table[ch] = 0xfe;
                else if (t == Translated::AsItIs) table[ch] = ch;
                else if (t == Translated::Char && replace <= 127) table[ch] = static_cast<unsigned char>(replace);
                else if (t == Translated::Text && as_str(item.get())->length == 1 && as_str(item.get())->at(0) <= 127) table[ch] = static_cast<unsigned char>(as_str(item.get())->at(0));
                else {
                    all = false;
                    break;
                }
            }
            if (table[ch] == 0xfe) continue;
            out += static_cast<char32_t>(table[ch]);
        }
        if (all) return str_from_codepoints(out);
    }
    while (i < n) {
        Translated t = translate_lookup(s->at(i), mapping, item, replace);
        if (t == Translated::AsItIs) {
            out += s->at(i);
        } else if (t == Translated::Char) {
            out += replace;
        } else if (t == Translated::Text) {
            const Str* text = as_str(item.get());
            for (std::size_t k = 0; k < text->length; ++k) out += text->at(k);
        } else {                                 // deleted, with every deleted character after it
            ++i;
            while (i < n) {
                Ref x;
                char32_t ignored = 0;
                if (translate_lookup(s->at(i), mapping, x, ignored) != Translated::Deleted) break;
                ++i;
            }
            continue;
        }
        ++i;
    }
    return str_from_codepoints(out);
}
Ref str_getnewargs_m(Obj self, Args a) {
    noargs(a, "str.__getnewargs__");
    self_str(self, "__getnewargs__");
    Ref copy = str_new(as_str(self)->text);
    return tuple_new({copy.get()});
}
Ref str_str_m(Obj self, Args a) {                // object_str: a wrapper, of a str itself
    if (a.nkw != 0) raise_new("TypeError", "wrapper __str__() takes no keyword arguments");
    if (a.npos != 0) raise_new("TypeError", "expected 0 arguments, got " + std::to_string(a.npos));
    if (as_str(self) == nullptr) raise_new("TypeError", "descriptor '__str__' requires a 'str' object but received a '" + type_of(self)->name + "'");
    return unchanged(self);
}
Ref str_maketrans_m(Obj, Args a) {               // unicode_maketrans_impl(x, y=NULL, z=NULL, /), a static method
    clinic(a, "maketrans", "str.maketrans", 1, 3);
    Ref out = dict_new();
    auto* made = static_cast<Dict*>(out.get().object());
    auto ord = [](const Str* s, std::size_t i) { return int_from_i64(static_cast<std::int64_t>(s->at(i))); };
    Obj x = a.pos(0);
    if (a.npos > 1) {
        const Str* first = as_str(x);
        const Str* second = as_str(a.pos(1));
        if (second == nullptr) raise_new("TypeError", "maketrans() argument 2 must be str, not " + type_of(a.pos(1))->name);
        const Str* third = nullptr;
        if (a.npos > 2) {
            third = as_str(a.pos(2));
            if (third == nullptr) raise_new("TypeError", "maketrans() argument 3 must be str, not " + type_of(a.pos(2))->name);
        }
        if (first == nullptr) raise_new("TypeError", "first maketrans argument must be a string if there is a second argument");
        if (first->length != second->length) raise_new("ValueError", "the first two maketrans arguments must have equal length");
        for (std::size_t i = 0; i < first->length; ++i) dict_set(made, ord(first, i).get(), ord(second, i).get());
        if (third != nullptr)
            for (std::size_t i = 0; i < third->length; ++i) dict_set(made, ord(third, i).get(), None());
        return out;
    }
    if (!is_exact_dict(x)) raise_new("TypeError", "if you give only one argument to maketrans it must be a dict");
    for (auto& e : static_cast<Dict*>(x.object())->entries) {
        if (e.key.is_unset()) continue;
        if (const Str* key = as_str(e.key)) {
            if (key->length != 1) raise_new("ValueError", "string keys in translatetable must be of length 1");   // as the C has it
            dict_set(made, ord(key, 0).get(), e.value);
        } else if (is_int(e.key)) {
            dict_set(made, e.key, e.value);
        } else {
            raise_new("TypeError", "keys in translate table mustbe strings or integers");   // as the C has it
        }
    }
    return out;
}
Ref str_find_m(Obj self, Args a) { return find_like(self, a, "find", 1, false); }
Ref str_rfind_m(Obj self, Args a) { return find_like(self, a, "rfind", -1, false); }
Ref str_index_m(Obj self, Args a) { return find_like(self, a, "index", 1, true); }
Ref str_rindex_m(Obj self, Args a) { return find_like(self, a, "rindex", -1, true); }
Ref str_count_m(Obj self, Args a) {              // unicode_count_impl: non-overlapping occurrences
    const Str* s = self_str(self, "count");
    Span sp = find_args(a, "count");
    Text text{s}, sub{sp.sub};
    std::int64_t start = sp.start, end = sp.end;
    adjust_indices(start, end, static_cast<std::int64_t>(text.size()));
    if (end - start < static_cast<std::int64_t>(sub.size())) return Ref::steal(Obj::small(0));
    if (sub.size() == 0) return Ref::steal(Obj::small(end - start + 1));
    std::int64_t count = 0;
    for (std::int64_t i = start; i + static_cast<std::int64_t>(sub.size()) <= end;) {
        if (match_at(text, sub, i)) {
            ++count;
            i += static_cast<std::int64_t>(sub.size());
        } else {
            ++i;
        }
    }
    return Ref::steal(Obj::small(count));
}
Ref str_isascii_m(Obj self, Args a) {             // unicode_isascii_impl
    noargs(a, "str.isascii");
    return Ref::steal(boolean(self_str(self, "isascii")->ascii));
}
Ref str_startswith_m(Obj self, Args a) { return starts_ends(self, a, "startswith", -1); }
Ref str_endswith_m(Obj self, Args a) { return starts_ends(self, a, "endswith", 1); }
Ref str_partition_m(Obj self, Args a) { return partition_like(self, a, "partition", 1); }
Ref str_rpartition_m(Obj self, Args a) { return partition_like(self, a, "rpartition", -1); }
Ref str_split_m(Obj self, Args a) { return split_like(self, a, "split", 1); }
Ref str_rsplit_m(Obj self, Args a) { return split_like(self, a, "rsplit", -1); }
Ref str_strip_m(Obj self, Args a) { return strip_like(self, a, "strip", 0); }
Ref str_lstrip_m(Obj self, Args a) { return strip_like(self, a, "lstrip", -1); }
Ref str_rstrip_m(Obj self, Args a) { return strip_like(self, a, "rstrip", 1); }

// replace(old, new, /, count=-1): count by position or keyword (3.13)
Ref str_replace_m(Obj self, Args a) {
    const Str* s = self_str(self, "replace");
    Obj given[3] = {};
    unpack_check(a, "replace", 2, 3, 3);
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k]->text != "count")
            throw NotImplemented("str.replace() with an unexpected keyword argument (the suggestion in its message)");
        if (!given[2].is_unset()) raise_new("TypeError", "argument for replace() given by name ('count') and position (3)");
        given[2] = a.kw(k);
    }
    const Str* old = str_argument(given[0], "replace", "argument 1");
    const Str* rep = str_argument(given[1], "replace", "argument 2");
    std::int64_t count = given[2].is_unset() ? -1 : ssize_arg(given[2]);
    Cps text = cps_of(s), from = cps_of(old), to = cps_of(rep);
    if (count < 0) count = INT64_MAX;
    bool exact = type_of(self) == types().str;
    if (text.size() < from.size() || count == 0 || given[0] == given[1] || (from.empty() && to.empty()))
        return exact ? Ref::share(self) : make(text);
    Cps out;
    std::int64_t done = 0;
    if (from.empty()) {                          // new before each character and at the end, up to count
        for (std::size_t i = 0; i <= text.size(); ++i) {
            if (done < count) {
                out += to;
                ++done;
            }
            if (i < text.size()) out += text[i];
        }
    } else {
        std::size_t i = 0;
        while (i < text.size()) {
            if (done < count && i + from.size() <= text.size() && std::equal(from.begin(), from.end(), text.begin() + i)) {
                out += to;
                i += from.size();
                ++done;
            } else {
                out += text[i++];
            }
        }
    }
    if (done == 0 && exact) return Ref::share(self);
    return make(out);
}

}  // namespace bella
