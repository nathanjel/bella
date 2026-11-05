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
    if (from == 0 && to == cps.size() && type_of(self) == types().str) return Ref::share(self);
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
        Ref whole = piece(self, text, 0, text.size());
        return direction > 0 ? tuple_new({whole.get(), empty.get(), empty.get()})
                             : tuple_new({empty.get(), empty.get(), whole.get()});
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

Ref str_maketrans_m(Obj, Args a) {               // unicode_maketrans_impl(x, y=NULL, z=NULL, /), a static method
    clinic(a, "maketrans", "maketrans", 1, 3);
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
            if (key->length != 1) raise_new("ValueError", "string keys in translate table must be of length 1");
            dict_set(made, ord(key, 0).get(), e.value);
        } else if (is_int(e.key)) {
            dict_set(made, e.key, e.value);
        } else {
            raise_new("TypeError", "keys in translate table must be strings or integers");
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
