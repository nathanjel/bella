// bytes and bytearray (Objects/bytesobject.c, bytearrayobject.c, bytes_methods.c, stringlib), the
// codecs between them and str (Objects/unicodeobject.c, Objects/stringlib/codecs.h), and the Unicode
// errors they raise (Objects/exceptions.c).
//
// Phase 1's codecs in the runtime, as CPython has its fast paths: UTF-8, ASCII, Latin-1 and utf-8-sig.
// A name no phase-1 codec answers to is a LookupError (D-20); UTF-16 and UTF-32 are phase 1 and not
// written yet, so they stop by name. `%` comes with str's. A class derived from these two is refused
// until str's and list's are written. The buffer protocol and memoryview are [P2+].
#include <algorithm>
#include <array>
#include <cstring>
#include <optional>
#include <string>

#include "bella/runtime.hpp"

namespace bella {

BytesObject::BytesObject(Kind k, std::string d) : Object(k), data(std::move(d)) {
    cls = k == Kind::Bytes ? types().bytes : types().bytearray;
}

bool is_bytes_like(Obj v) { return is_kind(v, Kind::Bytes) || is_kind(v, Kind::ByteArray); }
std::string& bytes_data(Obj v) { return static_cast<BytesObject*>(v.object())->data; }

namespace {
const Str* N(const char* s) { return intern(s); }
bool is_bytearray(Obj v) { return is_kind(v, Kind::ByteArray); }
Ref small(std::int64_t v) { return Ref::steal(Obj::small(v)); }
Ref yes_no(bool b) { return Ref::steal(boolean(b)); }
unsigned char u(char c) { return static_cast<unsigned char>(c); }

Ref new_bytearray(std::string s) { return own(new BytesObject(Kind::ByteArray, std::move(s))); }
bool exact_bytes(Obj v) { return is_kind(v, Kind::Bytes) && !has_attributes(v.object()); }   // PyBytes_CheckExact
Ref make_like(Obj self, std::string_view s) {     // what a method of either returns: its own kind
    return is_bytearray(self) ? new_bytearray(std::string(s)) : bytes_new(s);
}
// return_self: an exact bytes is its own copy; a bytearray never is, nor a subclass's instance (STRINGLIB_CHECK_EXACT)
Ref self_or_copy(Obj self) { return exact_bytes(self) ? Ref::share(self) : make_like(self, bytes_data(self)); }
Ref piece_of(Obj self, std::string_view p) {
    return exact_bytes(self) && p.size() == bytes_data(self).size() ? Ref::share(self) : make_like(self, p);
}

std::string_view buffer_of(Obj arg) {             // PyObject_GetBuffer
    if (is_bytes_like(arg)) return bytes_data(arg);
    if (!type_lookup(type_of(arg), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    raise_new("TypeError", "a bytes-like object is required, not '" + type_of(arg)->name + "'");
}
bool has_index(Obj v) {                           // _PyIndex_Check
    return is_int(v) || !type_lookup(type_of(v), N("__index__")).is_unset();
}
int byte_value(Obj item, const char* message = "byte must be in range(0, 256)") {   // _getbytevalue
    Ref value = int_index_of(item);
    std::int64_t v;
    if (!int_fits_i64(value.get(), v) || v < 0 || v > 255) raise_new("ValueError", message);
    return static_cast<int>(v);
}
std::int64_t slice_arg(Obj v, std::int64_t dflt) {   // _PyEval_SliceIndex
    if (v == None()) return dflt;
    if (!has_index(v)) raise_new("TypeError", "slice indices must be integers or have an __index__ method");
    return clipped_index(v);
}

// ---- the range a find, count or tailmatch works on (ADJUST_INDICES) ----
struct Range2 { std::int64_t start, end; };
Range2 adjusted(std::int64_t len, Args a, std::size_t first) {
    std::int64_t start = a.npos > first ? slice_arg(a.pos(first), 0) : 0;
    std::int64_t end = a.npos > first + 1 ? slice_arg(a.pos(first + 1), len) : len;
    if (end > len) end = len;
    else if (end < 0) { end += len; if (end < 0) end = 0; }
    if (start < 0) { start += len; if (start < 0) start = 0; }
    return {start, end};
}
// parse_args_finds_byte: bytes-like, or an int that is one byte
std::string sub_argument(Obj arg) {
    if (is_bytes_like(arg)) return bytes_data(arg);
    if (!type_lookup(type_of(arg), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    if (!has_index(arg))
        raise_new("TypeError", "argument should be integer or bytes-like object, not '" + type_of(arg)->name + "'");
    return std::string(1, static_cast<char>(byte_value(arg)));
}
std::string who(Obj self, const char* method) { return std::string(is_bytearray(self) ? "bytearray." : "bytes.") + method; }
std::int64_t find_in(std::string_view s, const std::string& sub, Range2 r, bool reverse) {
    if (r.end - r.start < static_cast<std::int64_t>(sub.size())) return -1;
    std::string_view window = s.substr(static_cast<std::size_t>(r.start), static_cast<std::size_t>(r.end - r.start));
    std::size_t at = reverse ? window.rfind(sub) : window.find(sub);
    return at == std::string_view::npos ? -1 : r.start + static_cast<std::int64_t>(at);
}
template <bool reverse>
Ref find_m(Obj self, Args a) {
    clinic(a, reverse ? "rfind" : "find", who(self, reverse ? "rfind" : "find"), 1, 3);
    std::string sub = sub_argument(a.pos(0));
    Range2 r = adjusted(static_cast<std::int64_t>(bytes_data(self).size()), a, 1);
    return small(find_in(bytes_data(self), sub, r, reverse));
}
template <bool reverse>
Ref index_m(Obj self, Args a) {
    clinic(a, reverse ? "rindex" : "index", who(self, reverse ? "rindex" : "index"), 1, 3);
    std::string sub = sub_argument(a.pos(0));
    Range2 r = adjusted(static_cast<std::int64_t>(bytes_data(self).size()), a, 1);
    std::int64_t at = find_in(bytes_data(self), sub, r, reverse);
    if (at < 0) raise_new("ValueError", "subsection not found");
    return small(at);
}
Ref count_m(Obj self, Args a) {
    clinic(a, "count", who(self, "count"), 1, 3);
    std::string sub = sub_argument(a.pos(0));
    std::string_view s = bytes_data(self);
    Range2 r = adjusted(static_cast<std::int64_t>(s.size()), a, 1);
    if (r.end - r.start < 0) return small(0);
    std::string_view window = s.substr(static_cast<std::size_t>(r.start), static_cast<std::size_t>(r.end - r.start));
    if (sub.empty()) return small(static_cast<std::int64_t>(window.size()) + 1);
    std::int64_t n = 0;
    for (std::size_t at = window.find(sub); at != std::string_view::npos; at = window.find(sub, at + sub.size())) ++n;
    return small(n);
}
bool tail_one(std::string_view s, Obj sub, Range2 r, bool at_end) {
    std::string_view t = buffer_of(sub);
    auto size = static_cast<std::int64_t>(t.size());
    if (r.end - r.start < size || r.start > static_cast<std::int64_t>(s.size())) return false;
    std::int64_t from = at_end ? r.end - size : r.start;
    return s.compare(static_cast<std::size_t>(from), t.size(), t) == 0;
}
template <bool at_end>
Ref tailmatch_m(Obj self, Args a) {               // _Py_bytes_tailmatch
    const char* name = at_end ? "endswith" : "startswith";
    clinic(a, name, who(self, name), 1, 3);
    std::string s = bytes_data(self);
    Range2 r = adjusted(static_cast<std::int64_t>(s.size()), a, 1);
    if (is_kind(a.pos(0), Kind::Tuple)) {
        for (Obj sub : static_cast<Tuple*>(a.pos(0).object())->items)
            if (tail_one(s, sub, r, at_end)) return yes_no(true);
        return yes_no(false);
    }
    if (!is_bytes_like(a.pos(0)) && type_lookup(type_of(a.pos(0)), N("__buffer__")).is_unset())
        raise_new("TypeError", std::string(name) + " first arg must be bytes or a tuple of bytes, not " + type_of(a.pos(0))->name);
    return yes_no(tail_one(s, a.pos(0), r, at_end));
}

// ---- case and classes of bytes (Py_ISALPHA and the others: ASCII only) ----
bool is_space(char c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
bool is_lower(char c) { return c >= 'a' && c <= 'z'; }
bool is_upper(char c) { return c >= 'A' && c <= 'Z'; }
bool is_alpha(char c) { return is_lower(c) || is_upper(c); }
bool is_digit(char c) { return c >= '0' && c <= '9'; }
char to_lower(char c) { return is_upper(c) ? static_cast<char>(c + 32) : c; }
char to_upper(char c) { return is_lower(c) ? static_cast<char>(c - 32) : c; }

template <char (*f)(char)>
Ref map_m(Obj self, Args a) {
    noargs(a, who(self, f == to_lower ? "lower" : "upper"));
    std::string out = bytes_data(self);
    for (char& c : out) c = f(c);
    return make_like(self, out);
}
Ref swapcase_m(Obj self, Args a) {
    noargs(a, who(self, "swapcase"));
    std::string out = bytes_data(self);
    for (char& c : out) c = is_lower(c) ? to_upper(c) : to_lower(c);
    return make_like(self, out);
}
Ref capitalize_m(Obj self, Args a) {
    noargs(a, who(self, "capitalize"));
    std::string out = bytes_data(self);
    for (std::size_t i = 0; i < out.size(); ++i) out[i] = i == 0 ? to_upper(out[i]) : to_lower(out[i]);
    return make_like(self, out);
}
Ref title_m(Obj self, Args a) {
    noargs(a, who(self, "title"));
    std::string out = bytes_data(self);
    bool previous_cased = false;
    for (char& c : out) {
        if (is_lower(c) && !previous_cased) c = to_upper(c);
        else if (is_upper(c) && previous_cased) c = to_lower(c);
        previous_cased = is_alpha(c);
    }
    return make_like(self, out);
}
template <bool (*test)(char)>
Ref all_m(Obj self, Args a) {
    noargs(a, who(self, test == is_alpha ? "isalpha" : test == is_digit ? "isdigit" : test == is_space ? "isspace" : "isalnum"));
    const std::string& s = bytes_data(self);
    return yes_no(!s.empty() && std::all_of(s.begin(), s.end(), test));
}
bool is_alnum(char c) { return is_alpha(c) || is_digit(c); }
Ref isascii_m(Obj self, Args a) {
    noargs(a, who(self, "isascii"));
    const std::string& s = bytes_data(self);
    return yes_no(std::all_of(s.begin(), s.end(), [](char c) { return u(c) < 128; }));
}
Ref islower_m(Obj self, Args a) {
    noargs(a, who(self, "islower"));
    const std::string& s = bytes_data(self);
    return yes_no(std::any_of(s.begin(), s.end(), is_lower) && std::none_of(s.begin(), s.end(), is_upper));
}
Ref isupper_m(Obj self, Args a) {
    noargs(a, who(self, "isupper"));
    const std::string& s = bytes_data(self);
    return yes_no(std::any_of(s.begin(), s.end(), is_upper) && std::none_of(s.begin(), s.end(), is_lower));
}
Ref istitle_m(Obj self, Args a) {
    noargs(a, who(self, "istitle"));
    bool cased = false, previous_cased = false;
    for (char c : bytes_data(self)) {
        if (is_upper(c)) {
            if (previous_cased) return yes_no(false);
            previous_cased = cased = true;
        } else if (is_lower(c)) {
            if (!previous_cased) return yes_no(false);
            previous_cased = cased = true;
        } else {
            previous_cased = false;
        }
    }
    return yes_no(cased);
}

// ---- strip, split, partition, join ----
template <int side>                               // 0 left, 1 right, 2 both
Ref strip_m(Obj self, Args a) {
    const char* name = side == 0 ? "lstrip" : side == 1 ? "rstrip" : "strip";
    clinic(a, name, who(self, name), 0, 1);
    const std::string& s = bytes_data(self);
    std::string chars;
    bool whitespace = a.npos == 0 || a.pos(0) == None();
    if (!whitespace) chars = std::string(buffer_of(a.pos(0)));
    auto strip = [&](char c) { return whitespace ? is_space(c) : chars.find(c) != std::string::npos; };
    std::size_t i = 0, j = s.size();
    if (side != 1) while (i < j && strip(s[i])) ++i;
    if (side != 0) while (j > i && strip(s[j - 1])) --j;
    return piece_of(self, std::string_view(s).substr(i, j - i));
}
// sep and maxsplit, by position or by name
void split_args(Obj self, Args a, const char* name, Obj& sep, std::int64_t& maxsplit) {
    (void)self;
    if (a.npos + a.nkw > 2) raise_new("TypeError", std::string(name) + "() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    sep = a.npos > 0 ? a.pos(0) : None();
    maxsplit = a.npos > 1 ? ssize_arg(a.pos(1)) : -1;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("sep") && a.npos < 1) sep = a.kw(k);
        else if (a.kwnames[k] == N("maxsplit") && a.npos < 2) maxsplit = ssize_arg(a.kw(k));
        else unexpected_keyword(std::string(name) + "()", a.kwnames[k], {"sep", "maxsplit"});
    }
    if (maxsplit < 0) maxsplit = INT64_MAX;
}
Ref split_m(Obj self, Args a) {
    Obj sep;
    std::int64_t maxsplit;
    split_args(self, a, "split", sep, maxsplit);
    std::string_view s = bytes_data(self);
    Ref out = list_new({});
    auto add = [&](std::string_view p) { Ref r = piece_of(self, p); list_append(out.get(), r.get()); };
    if (sep == None()) {
        std::size_t i = 0, n = s.size();
        while (maxsplit-- > 0) {
            while (i < n && is_space(s[i])) ++i;
            if (i == n) break;
            std::size_t j = i;
            while (i < n && !is_space(s[i])) ++i;
            add(s.substr(j, i - j));
        }
        if (i < n) {                              // only when maxsplit ran out: the rest as it is, but for its first spaces
            while (i < n && is_space(s[i])) ++i;
            if (i != n) add(s.substr(i));
        }
        return out;
    }
    std::string d(buffer_of(sep));
    if (d.empty()) raise_new("ValueError", "empty separator");
    std::size_t i = 0;
    while (maxsplit-- > 0) {
        std::size_t at = s.find(d, i);
        if (at == std::string_view::npos) break;
        add(s.substr(i, at - i));
        i = at + d.size();
    }
    add(s.substr(i));
    return out;
}
Ref rsplit_m(Obj self, Args a) {
    Obj sep;
    std::int64_t maxsplit;
    split_args(self, a, "rsplit", sep, maxsplit);
    std::string_view s = bytes_data(self);
    std::vector<std::string_view> parts;
    if (sep == None()) {
        std::size_t i = s.size();
        while (maxsplit-- > 0) {
            while (i > 0 && is_space(s[i - 1])) --i;
            if (i == 0) break;
            std::size_t j = i;
            while (i > 0 && !is_space(s[i - 1])) --i;
            parts.push_back(s.substr(i, j - i));
        }
        if (i > 0) {                              // only when maxsplit ran out: the rest as it is, but for its last spaces
            while (i > 0 && is_space(s[i - 1])) --i;
            if (i > 0) parts.push_back(s.substr(0, i));
        }
    } else {
        std::string d(buffer_of(sep));
        if (d.empty()) raise_new("ValueError", "empty separator");
        std::size_t end = s.size();
        while (maxsplit-- > 0) {
            if (end < d.size()) break;
            std::size_t at = s.substr(0, end).rfind(d);
            if (at == std::string_view::npos) break;
            parts.push_back(s.substr(at + d.size(), end - at - d.size()));
            end = at;
        }
        parts.push_back(s.substr(0, end));
    }
    Ref out = list_new({});
    for (auto it = parts.rbegin(); it != parts.rend(); ++it) {
        Ref r = piece_of(self, *it);
        list_append(out.get(), r.get());
    }
    return out;
}
Ref splitlines_m(Obj self, Args a) {
    if (a.npos + a.nkw > 1) raise_new("TypeError", "splitlines() takes at most 1 argument (" + std::to_string(a.npos + a.nkw) + " given)");
    bool keepends = a.npos == 1 && truth(a.pos(0));
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("keepends") && a.npos == 0) keepends = truth(a.kw(k));
        else unexpected_keyword("splitlines()", a.kwnames[k], {"keepends"});
    }
    std::string_view s = bytes_data(self);
    Ref out = list_new({});
    std::size_t i = 0;
    while (i < s.size()) {
        std::size_t j = i;
        while (i < s.size() && s[i] != '\n' && s[i] != '\r') ++i;
        std::size_t eol = i;
        if (i < s.size()) i += s[i] == '\r' && i + 1 < s.size() && s[i + 1] == '\n' ? 2 : 1;
        Ref r = piece_of(self, s.substr(j, (keepends ? i : eol) - j));
        list_append(out.get(), r.get());
    }
    return out;
}
template <bool reverse>
Ref partition_m(Obj self, Args a) {
    onearg(a, who(self, reverse ? "rpartition" : "partition"));
    std::string d(buffer_of(a.pos(0)));
    if (d.empty()) raise_new("ValueError", "empty separator");
    std::string_view s = bytes_data(self);
    std::size_t at = reverse ? s.rfind(d) : s.find(d);
    Ref empty = make_like(self, "");
    if (at == std::string_view::npos) {
        Ref whole = is_bytearray(self) ? make_like(self, s) : Ref::share(self);   // stringlib_partition: the object itself, a subclass's too
        Ref empty2 = make_like(self, "");
        return reverse ? tuple_new({empty.get(), empty2.get(), whole.get()}) : tuple_new({whole.get(), empty.get(), empty2.get()});
    }
    Ref left = make_like(self, s.substr(0, at));
    Ref mid = is_bytearray(self) ? make_like(self, d) : Ref::share(a.pos(0));   // a bytes hands back the object it was given
    Ref right = make_like(self, s.substr(at + d.size()));
    return tuple_new({left.get(), mid.get(), right.get()});
}
Ref join_m(Obj self, Args a) {                    // stringlib_bytes_join
    onearg(a, who(self, "join"));
    Ref seq;
    if (is_exact_list(a.pos(0)) || is_exact_tuple(a.pos(0))) {   // PySequence_Fast
        seq = Ref::share(a.pos(0));
    } else {
        Ref it;
        try {
            it = iter(a.pos(0));
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            raise_new("TypeError", "can only join an iterable");
        }
        seq = list_new({});
        list_extend(seq.get(), it.get());
    }
    const auto& items = is_kind(seq.get(), Kind::List) ? static_cast<List*>(seq.get().object())->items : static_cast<Tuple*>(seq.get().object())->items;
    if (items.size() == 1 && !is_bytearray(self) && exact_bytes(items[0])) return Ref::share(items[0]);   // PyBytes_CheckExact
    std::string out;
    const std::string sep = bytes_data(self);
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (!is_bytes_like(items[i]) && type_lookup(type_of(items[i]), N("__buffer__")).is_unset())
            raise_new("TypeError", "sequence item " + std::to_string(i) + ": expected a bytes-like object, " + type_of(items[i])->name + " found");
        if (i != 0) out += sep;
        out += buffer_of(items[i]);
    }
    return make_like(self, out);
}

// ---- replace, padding, removing, translating ----
Ref replace_m(Obj self, Args a) {                 // stringlib_replace
    if (a.npos < 2) raise_new("TypeError", "replace() takes at least 2 positional arguments (" + std::to_string(a.npos) + " given)");
    if (a.npos + a.nkw > 3) raise_new("TypeError", "replace() takes at most 3 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    std::int64_t count = a.npos == 3 ? ssize_arg(a.pos(2)) : -1;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("count") && a.npos < 3) count = ssize_arg(a.kw(k));
        else unexpected_keyword("replace()", a.kwnames[k], {"count"});
    }
    std::string from(buffer_of(a.pos(0))), to(buffer_of(a.pos(1)));
    std::string_view s = bytes_data(self);
    if (s.size() < from.size() || count == 0 || (from.empty() && to.empty())) return self_or_copy(self);
    if (count < 0) count = INT64_MAX;
    std::string out;
    if (from.empty()) {                           // the new bytes between all the old
        std::size_t i = 0;
        for (; count > 0; --count) {
            out += to;
            if (i == s.size()) { ++i; break; }
            out += s[i++];
        }
        if (i < s.size()) out += s.substr(i);
        return make_like(self, out);
    }
    std::size_t i = 0;
    bool found = false;
    for (; count > 0; --count) {
        std::size_t at = s.find(from, i);
        if (at == std::string_view::npos) break;
        found = true;
        out += s.substr(i, at - i);
        out += to;
        i = at + from.size();
    }
    if (!found) return self_or_copy(self);
    out += s.substr(i);
    return make_like(self, out);
}
char fill_argument(Obj arg, const char* name) {
    if (!is_bytes_like(arg)) raise_new("TypeError", std::string(name) + "() argument 2 must be a byte string of length 1, not " + type_of(arg)->name);
    if (bytes_data(arg).size() != 1)
        raise_new("TypeError", std::string(name) + "(): argument 2 must be a byte string of length 1, not a " + type_of(arg)->name +
                                   " object of length " + std::to_string(bytes_data(arg).size()));
    return bytes_data(arg)[0];
}
Ref padded(Obj self, std::int64_t left, std::int64_t right, char fill) {
    std::string out(static_cast<std::size_t>(left), fill);
    out += bytes_data(self);
    out.append(static_cast<std::size_t>(right), fill);
    return make_like(self, out);
}
template <int how>                                // 0 left, 1 right, 2 centre
Ref pad_m(Obj self, Args a) {
    const char* name = how == 0 ? "ljust" : how == 1 ? "rjust" : "center";
    clinic(a, name, who(self, name), 1, 2);
    std::int64_t width = ssize_arg(a.pos(0));
    char fill = a.npos > 1 ? fill_argument(a.pos(1), name) : ' ';
    auto len = static_cast<std::int64_t>(bytes_data(self).size());
    if (width <= len) return self_or_copy(self);
    std::int64_t margin = width - len;
    if (how == 0) return padded(self, 0, margin, fill);
    if (how == 1) return padded(self, margin, 0, fill);
    std::int64_t left = margin / 2 + (margin & width & 1);
    return padded(self, left, margin - left, fill);
}
Ref zfill_m(Obj self, Args a) {
    onearg(a, who(self, "zfill"));
    std::int64_t width = ssize_arg(a.pos(0));
    const std::string& s = bytes_data(self);
    auto fill = width - static_cast<std::int64_t>(s.size());
    if (fill <= 0) return self_or_copy(self);
    std::string out(static_cast<std::size_t>(fill), '0');
    out += s;
    auto at = static_cast<std::size_t>(fill);
    if (at < out.size() && (out[at] == '+' || out[at] == '-')) {
        out[0] = out[at];
        out[at] = '0';
    }
    return make_like(self, out);
}
Ref expandtabs_m(Obj self, Args a) {
    if (a.npos + a.nkw > 1) raise_new("TypeError", "expandtabs() takes at most 1 argument (" + std::to_string(a.npos + a.nkw) + " given)");
    std::int64_t tabsize = a.npos == 1 ? c_int_arg(a.pos(0)) : 8;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("tabsize") && a.npos == 0) tabsize = c_int_arg(a.kw(k));
        else unexpected_keyword("expandtabs()", a.kwnames[k], {"tabsize"});
    }
    const std::string& s = bytes_data(self);
    std::string out;
    std::int64_t column = 0;
    for (char c : s) {
        if (c == '\t') {
            if (tabsize > 0) {
                std::int64_t incr = tabsize - (column % tabsize);
                out.append(static_cast<std::size_t>(incr), ' ');
                column += incr;
            }
        } else {
            out += c;
            ++column;
            if (c == '\n' || c == '\r') column = 0;
        }
    }
    return make_like(self, out);
}
Ref removeprefix_m(Obj self, Args a) {
    onearg(a, who(self, "removeprefix"));
    std::string p(buffer_of(a.pos(0)));
    std::string_view s = bytes_data(self);
    if (!p.empty() && s.starts_with(p)) return make_like(self, s.substr(p.size()));
    return self_or_copy(self);
}
Ref removesuffix_m(Obj self, Args a) {
    onearg(a, who(self, "removesuffix"));
    std::string p(buffer_of(a.pos(0)));
    std::string_view s = bytes_data(self);
    if (!p.empty() && s.ends_with(p)) return make_like(self, s.substr(0, s.size() - p.size()));
    return self_or_copy(self);
}
Ref translate_m(Obj self, Args a) {
    if (a.npos < 1) raise_new("TypeError", "translate() takes at least 1 positional argument (" + std::to_string(a.npos) + " given)");
    if (a.npos + a.nkw > 2) raise_new("TypeError", "translate() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    Obj del = a.npos == 2 ? a.pos(1) : Obj{};
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("delete") && a.npos < 2) del = a.kw(k);
        else unexpected_keyword("translate()", a.kwnames[k], {"delete"});
    }
    std::string table;
    bool has_table = a.pos(0) != None();
    if (has_table) {
        table = std::string(buffer_of(a.pos(0)));
        if (table.size() != 256) raise_new("ValueError", "translation table must be 256 characters long");
    }
    std::array<bool, 256> deleted{};
    if (!del.is_unset())
        for (char c : buffer_of(del)) deleted[u(c)] = true;
    std::string out;
    bool changed = false;
    for (char c : bytes_data(self)) {
        if (deleted[u(c)]) { changed = true; continue; }
        char t = has_table ? table[u(c)] : c;
        changed = changed || t != c;
        out += t;
    }
    return changed ? make_like(self, out) : self_or_copy(self);
}
Ref maketrans_m(Obj, Args a) {
    clinic(a, "maketrans", "maketrans", 2, 2);
    std::string from(buffer_of(a.pos(0))), to(buffer_of(a.pos(1)));
    if (from.size() != to.size()) raise_new("ValueError", "maketrans arguments must have same length");
    std::string table(256, '\0');
    for (int i = 0; i < 256; ++i) table[static_cast<std::size_t>(i)] = static_cast<char>(i);
    for (std::size_t i = 0; i < from.size(); ++i) table[u(from[i])] = to[i];
    return bytes_new(table);
}

// ---- hex ----
Ref hex_m(Obj self, Args a) {                     // _Py_strhex_with_sep
    if (a.npos + a.nkw > 2) raise_new("TypeError", "hex() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    Obj sep = a.npos > 0 ? a.pos(0) : Obj{};
    std::int64_t per = a.npos > 1 ? ssize_arg(a.pos(1)) : 1;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("sep") && a.npos < 1) sep = a.kw(k);
        else if (a.kwnames[k] == N("bytes_per_sep") && a.npos < 2) per = ssize_arg(a.kw(k));
        else unexpected_keyword("hex()", a.kwnames[k], {"sep", "bytes_per_sep"});
    }
    char sep_char = 0;
    if (!sep.is_unset()) {
        Ref length = invoke(dict_get(builtins_module()->dict, Obj::of(N("len"))), {sep});   // PyObject_Length, whatever sep is
        if (length.get() != Obj::small(1)) raise_new("ValueError", "sep must be length 1.");
        if (const Str* t = as_str(sep)) {
            if (t->at(0) > 127) raise_new("ValueError", "sep must be ASCII.");
            sep_char = static_cast<char>(t->at(0));
        } else if (is_kind(sep, Kind::Bytes)) {
            if (u(bytes_data(sep)[0]) > 127) raise_new("ValueError", "sep must be ASCII.");
            sep_char = bytes_data(sep)[0];
        } else {
            raise_new("TypeError", "sep must be str or bytes.");
        }
    }
    const std::string& s = bytes_data(self);
    static const char* digits = "0123456789abcdef";
    std::string out;
    std::int64_t group = per < 0 ? -per : per;
    auto n = static_cast<std::int64_t>(s.size());
    for (std::int64_t i = 0; i < n; ++i) {
        // positive: the groups counted from the right; negative: from the left
        if (i != 0 && sep_char != 0 && group != 0 && (per > 0 ? (n - i) % group == 0 : i % group == 0)) out += sep_char;
        out += digits[u(s[static_cast<std::size_t>(i)]) >> 4];
        out += digits[u(s[static_cast<std::size_t>(i)]) & 15];
    }
    return str_new(out);
}
int hex_digit(char32_t c) {
    if (c >= '0' && c <= '9') return static_cast<int>(c - '0');
    if (c >= 'a' && c <= 'f') return static_cast<int>(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return static_cast<int>(c - 'A' + 10);
    return -1;
}
Ref fromhex_m(Obj cls, Args a) {                  // _PyBytes_FromHex
    onearg(a, static_cast<ClassObject*>(cls.object())->name + ".fromhex");
    std::u32string text;
    if (const Str* t = as_str(a.pos(0))) {
        for (std::size_t i = 0; i < t->length; ++i) text += t->at(i);
    } else if (is_bytes_like(a.pos(0))) {
        for (char c : bytes_data(a.pos(0))) text += static_cast<char32_t>(u(c));
    } else {
        raise_new("TypeError", "fromhex() argument must be str or bytes-like, not " + type_of(a.pos(0))->name);
    }
    std::string out;
    std::size_t i = 0;
    auto bad = [&](std::size_t at) { raise_new("ValueError", "non-hexadecimal number found in fromhex() arg at position " + std::to_string(at)); };
    while (i < text.size()) {
        if (text[i] < 128 && is_space(static_cast<char>(text[i]))) { ++i; continue; }
        int top = hex_digit(text[i]);
        if (top < 0) bad(i);
        ++i;
        if (i == text.size()) raise_new("ValueError", "fromhex() arg must contain an even number of hexadecimal digits");
        int bottom = hex_digit(text[i]);
        if (bottom < 0) bad(i);
        ++i;
        out += static_cast<char>(top * 16 + bottom);
    }
    return cls == Obj::of(types().bytearray) ? new_bytearray(out) : bytes_new(out);
}

// ---- codecs ----
// The registry is _codecs.py's (Python/codecs.c); these are the hooks it gives the runtime when it has run: _PyCodec_EncodeText,
// _PyCodec_DecodeText, PyCodec_LookupError for a name the codecs here have no code for, and _PyCodec_InitRegistry's end.
enum class Codec { Utf8, Ascii, Latin1, Utf16, Utf32, Registry };
// the shortcuts of PyUnicode_Decode and PyUnicode_AsEncodedString: _Py_normalize_encoding into ten characters, then these names alone
Codec fast_codec(const std::string& name) {
    std::string lower;
    bool punct = false;
    for (char c : name) {
        if (is_alnum(c) || c == '.') {
            if (punct && !lower.empty()) lower += '_';
            punct = false;
            lower += to_lower(c);
            if (lower.size() > 10) return Codec::Registry;
        } else {
            punct = true;
        }
    }
    std::string_view l = lower;
    if (l.starts_with("utf")) {
        l.remove_prefix(3);
        if (l.starts_with("_")) l.remove_prefix(1);
        if (l == "8") return Codec::Utf8;
        if (l == "16") return Codec::Utf16;
        if (l == "32") return Codec::Utf32;
        return Codec::Registry;
    }
    if (l == "ascii" || l == "us_ascii") return Codec::Ascii;
    if (l == "latin1" || l == "latin_1" || l == "iso_8859_1" || l == "iso8859_1") return Codec::Latin1;
    return Codec::Registry;
}
void no_null(const std::string& text) {           // a C string: clinic's str converter
    if (text.find('\0') != std::string::npos) raise_new("ValueError", "embedded null character");
}
[[noreturn]] void unknown_handler(const std::string& errors) {
    if (errors == "namereplace") throw NotImplemented("the error handler namereplace (it needs the Unicode database)");
    if (!codec_hooks().unknown_handler.get().is_unset()) {   // the registry: LookupError, or a handler the program registered
        Ref name = str_new(errors);
        invoke(codec_hooks().unknown_handler.get(), {name.get()});
    }
    raise_new("LookupError", "unknown error handler name '" + errors + "'");
}
void put_utf8(std::string& out, char32_t c) {
    if (c < 0x80) out += static_cast<char>(c);
    else if (c < 0x800) { out += static_cast<char>(0xC0 | (c >> 6)); out += static_cast<char>(0x80 | (c & 63)); }
    else if (c < 0x10000) { out += static_cast<char>(0xE0 | (c >> 12)); out += static_cast<char>(0x80 | ((c >> 6) & 63)); out += static_cast<char>(0x80 | (c & 63)); }
    else { out += static_cast<char>(0xF0 | (c >> 18)); out += static_cast<char>(0x80 | ((c >> 12) & 63)); out += static_cast<char>(0x80 | ((c >> 6) & 63)); out += static_cast<char>(0x80 | (c & 63)); }
}
std::string hex_text(std::uint32_t v, int digits) {
    static const char* d = "0123456789abcdef";
    std::string out;
    for (int i = digits - 1; i >= 0; --i) out += d[(v >> (4 * i)) & 15];
    return out;
}
std::string backslashed(char32_t c) {
    if (c <= 0xFF) return "\\x" + hex_text(c, 2);
    if (c <= 0xFFFF) return "\\u" + hex_text(c, 4);
    return "\\U" + hex_text(c, 8);
}
[[noreturn]] void raise_encode_error(const char* encoding, Obj text, std::size_t start, std::size_t end, const char* reason) {
    Ref enc = str_new(encoding);
    Ref why = str_new(reason);
    Ref exc = invoke(Obj::of(exception_class("UnicodeEncodeError")),
                     {enc.get(), text, Obj::small(static_cast<std::int64_t>(start)), Obj::small(static_cast<std::int64_t>(end)), why.get()});
    raise(exc.get());
}
[[noreturn]] void raise_decode_error(const char* encoding, std::string_view input, std::size_t start, std::size_t end, const char* reason) {
    Ref enc = str_new(encoding);
    Ref why = str_new(reason);
    Ref object = bytes_new(input);
    Ref exc = invoke(Obj::of(exception_class("UnicodeDecodeError")),
                     {enc.get(), object.get(), Obj::small(static_cast<std::int64_t>(start)), Obj::small(static_cast<std::int64_t>(end)), why.get()});
    raise(exc.get());
}

// what a handler writes for [start, end) of an encode, shared by the codecs
void encode_fallback(std::string& out, const Str* s, std::size_t start, std::size_t end, const std::string& errors) {
    if (errors == "backslashreplace") {
        for (std::size_t k = start; k < end; ++k) out += backslashed(s->at(k));
    } else {                                      // xmlcharrefreplace
        for (std::size_t k = start; k < end; ++k) out += "&#" + std::to_string(static_cast<std::uint32_t>(s->at(k))) + ";";
    }
}
// unicode_encode_ucs1, for a limit of 128 or 256
std::string encode_ucs1(const Str* s, Obj text, char32_t limit, const std::string& errors) {
    const char* encoding = limit == 128 ? "ascii" : "latin-1";
    const char* reason = limit == 128 ? "ordinal not in range(128)" : "ordinal not in range(256)";
    std::string out;
    std::size_t i = 0, n = s->length;
    while (i < n) {
        char32_t c = s->at(i);
        if (c < limit) { out += static_cast<char>(c); ++i; continue; }
        std::size_t end = i;
        while (end < n && s->at(end) >= limit) ++end;
        if (errors == "replace") out.append(end - i, '?');
        else if (errors == "ignore") { }
        else if (errors == "backslashreplace" || errors == "xmlcharrefreplace") encode_fallback(out, s, i, end, errors);
        else if (errors == "surrogateescape") {
            std::size_t k = i;
            while (k < end && s->at(k) >= 0xDC80 && s->at(k) <= 0xDCFF) { out += static_cast<char>(s->at(k) - 0xDC00); ++k; }
            if (k < end) raise_encode_error(encoding, text, k, end, reason);
        } else {
            if (errors != "strict" && errors != "surrogatepass") unknown_handler(errors);
            raise_encode_error(encoding, text, i, end, reason);
        }
        i = end;
    }
    return out;
}
std::string encode_utf8(const Str* s, Obj text, const std::string& errors) {
    std::string out;
    std::size_t i = 0, n = s->length;
    auto surrogate = [](char32_t c) { return c >= 0xD800 && c <= 0xDFFF; };
    while (i < n) {
        char32_t c = s->at(i);
        if (!surrogate(c)) { put_utf8(out, c); ++i; continue; }
        std::size_t end = i;
        while (end < n && surrogate(s->at(end))) ++end;
        if (errors == "replace") out.append(end - i, '?');
        else if (errors == "ignore") { }
        else if (errors == "surrogatepass") for (std::size_t k = i; k < end; ++k) put_utf8(out, s->at(k));
        else if (errors == "backslashreplace" || errors == "xmlcharrefreplace") encode_fallback(out, s, i, end, errors);
        else if (errors == "surrogateescape") {
            std::size_t k = i;
            while (k < end && s->at(k) >= 0xDC80 && s->at(k) <= 0xDCFF) { out += static_cast<char>(s->at(k) - 0xDC00); ++k; }
            if (k < end) raise_encode_error("utf-8", text, k, end, "surrogates not allowed");
        } else {
            if (errors != "strict") unknown_handler(errors);
            raise_encode_error("utf-8", text, i, end, "surrogates not allowed");
        }
        i = end;
    }
    return out;
}
// one sequence of utf8_decode (stringlib/codecs.h): its code point and width, or how it fails
struct Utf8Step { char32_t c = 0; std::size_t width = 0; int error = 0; };   // error: 1 invalid start, 2-4 continuation, 5 end of data
Utf8Step utf8_step(std::string_view s, std::size_t at) {
    auto cont = [](unsigned char x) { return x >= 0x80 && x < 0xC0; };
    unsigned char ch = u(s[at]);
    std::size_t left = s.size() - at;
    auto b = [&](std::size_t k) { return u(s[at + k]); };
    if (ch < 0x80) return {ch, 1, 0};
    if (ch < 0xC2) return {0, 0, 1};
    if (ch < 0xE0) {
        if (left < 2) return {0, 0, 5};
        if (!cont(b(1))) return {0, 0, 2};
        return {static_cast<char32_t>(((ch & 0x1F) << 6) | (b(1) & 0x3F)), 2, 0};
    }
    if (ch < 0xF0) {
        if (left < 3) {
            if (left < 2) return {0, 0, 5};
            unsigned char c2 = b(1);
            if (!cont(c2) || (c2 < 0xA0 ? ch == 0xE0 : ch == 0xED)) return {0, 0, 2};
            return {0, 0, 5};
        }
        unsigned char c2 = b(1), c3 = b(2);
        if (!cont(c2)) return {0, 0, 2};
        if (ch == 0xE0 ? c2 < 0xA0 : (ch == 0xED && c2 >= 0xA0)) return {0, 0, 2};
        if (!cont(c3)) return {0, 0, 3};
        return {static_cast<char32_t>(((ch & 0x0F) << 12) | ((c2 & 0x3F) << 6) | (c3 & 0x3F)), 3, 0};
    }
    if (ch < 0xF5) {
        if (left < 4) {
            if (left < 2) return {0, 0, 5};
            unsigned char c2 = b(1);
            if (!cont(c2) || (c2 < 0x90 ? ch == 0xF0 : ch == 0xF4)) return {0, 0, 2};
            if (left < 3) return {0, 0, 5};
            if (!cont(b(2))) return {0, 0, 3};
            return {0, 0, 5};
        }
        unsigned char c2 = b(1), c3 = b(2), c4 = b(3);
        if (!cont(c2)) return {0, 0, 2};
        if (ch == 0xF0 ? c2 < 0x90 : (ch == 0xF4 && c2 >= 0x90)) return {0, 0, 2};
        if (!cont(c3)) return {0, 0, 3};
        if (!cont(c4)) return {0, 0, 4};
        return {static_cast<char32_t>(((ch & 0x07) << 18) | ((c2 & 0x3F) << 12) | ((c3 & 0x3F) << 6) | (c4 & 0x3F)), 4, 0};
    }
    return {0, 0, 1};
}
// what a handler makes of [start, end) of a decode; the position to go on from
std::size_t decode_fallback(std::u32string& out, std::string_view s, std::size_t start, std::size_t end, const std::string& errors,
                            const char* encoding, const char* reason) {
    if (errors == "ignore") return end;
    if (errors == "replace") { out += U'\xFFFD'; return end; }
    if (errors == "surrogateescape") {           // PyCodec_SurrogateEscapeErrors: at most four bytes, each 0x80 or more
        std::size_t k = start;
        for (; k < end && k - start < 4 && u(s[k]) >= 0x80; ++k) out += static_cast<char32_t>(0xDC00 + u(s[k]));
        if (k == start) raise_decode_error(encoding, s, start, end, reason);
        return k;
    }
    if (errors == "backslashreplace") {
        for (std::size_t k = start; k < end; ++k)
            for (char c : "\\x" + hex_text(u(s[k]), 2)) out += static_cast<char32_t>(u(c));
        return end;
    }
    if (errors == "surrogatepass" && std::string_view(encoding) == "utf-8" && s.size() - start >= 3 && u(s[start]) == 0xED &&
        u(s[start + 1]) >= 0xA0 && u(s[start + 1]) <= 0xBF && u(s[start + 2]) >= 0x80 && u(s[start + 2]) <= 0xBF) {
        out += static_cast<char32_t>(((u(s[start]) & 0x0F) << 12) | ((u(s[start + 1]) & 0x3F) << 6) | (u(s[start + 2]) & 0x3F));
        return start + 3;
    }
    if (errors == "surrogatepass") {             // PyCodec_SurrogatePassErrors: one surrogate, in the order the codec's name gives
        std::string_view name(encoding);
        std::size_t width = name.starts_with("utf-32") ? 4 : name.starts_with("utf-16") ? 2 : 0;
        if (width != 0 && s.size() - start >= width) {
            bool little = name.ends_with("-le");
            std::uint32_t ch = 0;
            for (std::size_t k = 0; k < width; ++k) ch |= static_cast<std::uint32_t>(u(s[start + k])) << (8 * (little ? k : width - 1 - k));
            if (ch >= 0xD800 && ch <= 0xDFFF) {
                out += static_cast<char32_t>(ch);
                return start + width;
            }
        }
    }
    if (errors == "xmlcharrefreplace") raise_new("TypeError", "don't know how to handle UnicodeDecodeError in error callback");
    if (errors != "strict" && errors != "surrogatepass") unknown_handler(errors);
    raise_decode_error(encoding, s, start, end, reason);
}
Ref decode_utf8(std::string_view s, const std::string& errors, std::size_t* consumed = nullptr) {
    std::u32string out;
    std::size_t i = 0;
    while (i < s.size()) {
        Utf8Step step = utf8_step(s, i);
        if (step.error == 0) { out += step.c; i += step.width; continue; }
        if (consumed != nullptr) {                // PyUnicode_DecodeUTF8Stateful: a sequence the data ends inside waits for more, a truncated surrogate too
            if (step.error == 5) break;
            if (step.error == 2 && u(s[i]) == 0xED && s.size() - i == 2 && u(s[i + 1]) >= 0xA0 && u(s[i + 1]) <= 0xBF) break;
        }
        std::size_t end = step.error == 5 ? s.size() : step.error == 1 ? i + 1 : i + static_cast<std::size_t>(step.error) - 1;
        const char* reason = step.error == 5 ? "unexpected end of data" : step.error == 1 ? "invalid start byte" : "invalid continuation byte";
        i = decode_fallback(out, s, i, end, errors, "utf-8", reason);
    }
    if (consumed != nullptr) *consumed = i;
    return str_from_codepoints(out);
}
// UTF-16 and UTF-32 (Objects/unicodeobject.c: _PyUnicode_EncodeUTF16 and 32, PyUnicode_DecodeUTF16Stateful and 32; stringlib's
// utf16_decode). byteorder: 0 the native order with a byte order mark, which the encoder writes and the decoder reads to choose
// the order; below 0 little-endian, above 0 big-endian. This host is little-endian, as the reference's build is.
namespace {
bool is_surrogate(std::uint32_t c) { return c >= 0xD800 && c <= 0xDFFF; }
void put_unit(std::string& out, std::uint32_t unit, std::size_t width, bool little) {
    for (std::size_t k = 0; k < width; ++k) out += static_cast<char>((unit >> (8 * (little ? k : width - 1 - k))) & 0xFF);
}
std::uint32_t read_unit(std::string_view s, std::size_t at, std::size_t width, bool little) {
    std::uint32_t v = 0;
    for (std::size_t k = 0; k < width; ++k) v |= static_cast<std::uint32_t>(u(s[at + k])) << (8 * (little ? k : width - 1 - k));
    return v;
}
}  // namespace
// the encoders call the handler for one character at a time, (pos, pos + 1), with "surrogates not allowed": bytes it gives must be
// whole units, text must be ASCII (each character a unit of the stream's order), or the encoder raises for that character
std::string encode_utf_wide(const Str* s, Obj text, const std::string& errors, int byteorder, std::size_t width) {
    bool little = byteorder <= 0;
    std::string name = width == 2 ? (byteorder < 0 ? "utf-16-le" : byteorder > 0 ? "utf-16-be" : "utf-16")
                                  : (byteorder == -1 ? "utf-32-le" : byteorder == 1 ? "utf-32-be" : "utf-32");
    std::string out;
    if (byteorder == 0) put_unit(out, 0xFEFF, width, little);
    for (std::size_t i = 0, n = s->length; i < n; ++i) {
        std::uint32_t c = s->at(i);
        if (!is_surrogate(c)) {
            if (width == 2 && c >= 0x10000) {
                put_unit(out, 0xD800 | ((c - 0x10000) >> 10), 2, little);
                put_unit(out, 0xDC00 | ((c - 0x10000) & 0x3FF), 2, little);
            } else {
                put_unit(out, c, width, little);
            }
            continue;
        }
        if (errors == "ignore") continue;
        if (errors == "replace") { put_unit(out, '?', width, little); continue; }
        if (errors == "backslashreplace" || errors == "xmlcharrefreplace") {
            std::string rep;
            encode_fallback(rep, s, i, i + 1, errors);
            for (char ch : rep) put_unit(out, u(ch), width, little);
            continue;
        }
        if (errors == "surrogatepass") {          // the handler's bytes are in the order of the codec's name ("utf-32": the native one)
            std::string_view n(name);
            put_unit(out, c, width, n.ends_with("-be") ? false : true);
            continue;
        }
        // surrogateescape gives one byte, no whole unit (or refuses a surrogate below U+DC80 with the same exception); strict raises
        if (errors != "strict" && errors != "surrogateescape") unknown_handler(errors);
        raise_encode_error(name.c_str(), text, i, i + 1, "surrogates not allowed");
    }
    return out;
}
Ref decode_utf16(std::string_view s, const std::string& errors, int* byteorder, std::size_t* consumed) {
    std::size_t q = 0, e = s.size();
    int bo = byteorder != nullptr ? *byteorder : 0;
    if (bo == 0 && e >= 2) {                      // a leading byte order mark decides the order, and is skipped
        std::uint32_t bom = (static_cast<std::uint32_t>(u(s[1])) << 8) | u(s[0]);
        if (bom == 0xFEFF) { q = 2; bo = -1; }
        else if (bom == 0xFFFE) { q = 2; bo = 1; }
        if (byteorder != nullptr) *byteorder = bo;
    }
    if (q == e) {
        if (consumed != nullptr) *consumed = e;
        return str_new("");
    }
    bool little = bo <= 0;
    const char* encoding = little ? "utf-16-le" : "utf-16-be";
    std::u32string out;
    for (;;) {
        int code = 0;                             // utf16_decode: 0 fewer than two bytes left, 1 a high surrogate at the end,
        while (e - q >= 2) {                      // 2 a low surrogate first, 3 a high one not followed by a low one
            std::uint32_t ch = read_unit(s, q, 2, little);
            q += 2;
            if (!is_surrogate(ch)) { out += static_cast<char32_t>(ch); continue; }
            if (ch >= 0xDC00) { code = 2; break; }
            if (e - q < 2) { code = 1; break; }
            std::uint32_t ch2 = read_unit(s, q, 2, little);
            q += 2;
            if (ch2 < 0xDC00 || ch2 > 0xDFFF) { code = 3; break; }
            out += static_cast<char32_t>(0x10000 + (((ch & 0x3FF) << 10) | (ch2 & 0x3FF)));
        }
        std::size_t start = 0, end = 0;
        const char* reason = nullptr;
        if (code == 0) {
            if (q == e || consumed != nullptr) break;
            reason = "truncated data", start = q, end = e;
        } else if (code == 1) {
            q -= 2;
            if (consumed != nullptr) break;
            reason = "unexpected end of data", start = q, end = e;
        } else if (code == 2) {
            reason = "illegal encoding", start = q - 2, end = start + 2;
        } else {
            reason = "illegal UTF-16 surrogate", start = q - 4, end = start + 2;
        }
        q = decode_fallback(out, s, start, end, errors, encoding, reason);
    }
    if (consumed != nullptr) *consumed = q;
    return str_from_codepoints(out);
}
Ref decode_utf32(std::string_view s, const std::string& errors, int* byteorder, std::size_t* consumed) {
    std::size_t q = 0, e = s.size();
    int bo = byteorder != nullptr ? *byteorder : 0;
    if (bo == 0 && e >= 4) {
        std::uint32_t bom = read_unit(s, 0, 4, true);
        if (bom == 0x0000FEFF) { bo = -1; q = 4; }
        else if (bom == 0xFFFE0000) { bo = 1; q = 4; }
        if (byteorder != nullptr) *byteorder = bo;
    }
    if (q == e) {
        if (consumed != nullptr) *consumed = e;
        return str_new("");
    }
    bool little = bo <= 0;
    const char* encoding = little ? "utf-32-le" : "utf-32-be";
    std::u32string out;
    for (;;) {
        const char* reason = nullptr;
        std::size_t start = 0, end = 0;
        while (e - q >= 4) {
            std::uint32_t ch = read_unit(s, q, 4, little);
            if (is_surrogate(ch)) { reason = "code point in surrogate code point range(0xd800, 0xe000)", start = q, end = q + 4; break; }
            if (ch >= 0x110000) { reason = "code point not in range(0x110000)", start = q, end = q + 4; break; }
            out += static_cast<char32_t>(ch);
            q += 4;
        }
        if (reason == nullptr) {
            if (q == e || consumed != nullptr) break;
            reason = "truncated data", start = q, end = e;
        }
        q = decode_fallback(out, s, start, end, errors, encoding, reason);
    }
    if (consumed != nullptr) *consumed = q;
    return str_from_codepoints(out);
}
Ref decode_ascii(std::string_view s, const std::string& errors) {
    std::u32string out;
    std::size_t i = 0;
    while (i < s.size()) {
        if (u(s[i]) < 128) { out += static_cast<char32_t>(u(s[i])); ++i; continue; }
        i = decode_fallback(out, s, i, i + 1, errors, "ascii", "ordinal not in range(128)");
    }
    return str_from_codepoints(out);
}
Ref decode_latin1(std::string_view s) {
    std::u32string out;
    for (char c : s) out += static_cast<char32_t>(u(c));
    return str_from_codepoints(out);
}
// the registry's hook with (value, encoding, errors or None): errors is a C string CPython leaves NULL when it was not given
Ref registry_call(const Ref& hook, Obj value, const std::string& encoding, const std::string* errors) {
    ensure_codecs();
    Ref enc = str_new(encoding);
    Ref err = errors == nullptr ? none_ref() : str_new(*errors);
    return invoke(hook.get(), {value, enc.get(), err.get()});
}
Ref decode_with(std::string_view s, const std::string* encoding, const std::string* errors) {   // PyUnicode_Decode
    if (s.empty()) return str_new("");
    const std::string e = errors == nullptr ? "strict" : *errors;
    if (encoding == nullptr) return decode_utf8(s, e);
    switch (fast_codec(*encoding)) {
        case Codec::Utf8: return decode_utf8(s, e);
        case Codec::Ascii: return decode_ascii(s, e);
        case Codec::Latin1: return decode_latin1(s);
        case Codec::Utf16: return decode_utf16(s, e, nullptr, nullptr);
        case Codec::Utf32: return decode_utf32(s, e, nullptr, nullptr);
        case Codec::Registry: break;
    }
    Ref data = bytes_new(s);
    return registry_call(codec_hooks().text_decode, data.get(), *encoding, errors);
}
Ref encode_with(Obj text, const std::string* encoding, const std::string* errors) {   // PyUnicode_AsEncodedString
    const Str* s = as_str(text);
    const std::string e = errors == nullptr ? "strict" : *errors;
    if (encoding == nullptr) return bytes_new(encode_utf8(s, text, e));
    switch (fast_codec(*encoding)) {
        case Codec::Utf8: return bytes_new(encode_utf8(s, text, e));
        case Codec::Ascii: return bytes_new(encode_ucs1(s, text, 128, e));
        case Codec::Latin1: return bytes_new(encode_ucs1(s, text, 256, e));
        case Codec::Utf16: return bytes_new(encode_utf_wide(s, text, e, 0, 2));
        case Codec::Utf32: return bytes_new(encode_utf_wide(s, text, e, 0, 4));
        case Codec::Registry: break;
    }
    return registry_call(codec_hooks().text_encode, text, *encoding, errors);
}
std::string text_argument(Obj v, const std::string& function, const char* name) {
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", function + "() argument '" + name + "' must be str, not " + type_of(v)->name);
    no_null(s->text);
    return s->text;
}
// (encoding='utf-8', errors='strict'), by position or by name; one not given stays unset, as the C string stays NULL
void codec_args(Args a, const std::string& function, std::optional<std::string>& encoding, std::optional<std::string>& errors) {
    if (a.npos > 2) raise_new("TypeError", function + "() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    if (a.npos > 0) encoding = text_argument(a.pos(0), function, "encoding");
    if (a.npos > 1) errors = text_argument(a.pos(1), function, "errors");
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k] == N("encoding") && a.npos < 1) encoding = text_argument(a.kw(k), function, "encoding");
        else if (a.kwnames[k] == N("errors") && a.npos < 2) errors = text_argument(a.kw(k), function, "errors");
        else unexpected_keyword(function + "()", a.kwnames[k], {"encoding", "errors"});
    }
}
Ref decode_m(Obj self, Args a) {
    std::optional<std::string> encoding, errors;
    codec_args(a, "decode", encoding, errors);
    std::string copy = bytes_data(self);
    return decode_with(copy, encoding ? &*encoding : nullptr, errors ? &*errors : nullptr);
}
Ref str_encode_m(Obj self, Args a) {
    std::optional<std::string> encoding, errors;
    codec_args(a, "encode", encoding, errors);
    return encode_with(self, encoding ? &*encoding : nullptr, errors ? &*errors : nullptr);
}

// ---- construction ----
struct SourceArgs { Obj source, encoding, errors; };
SourceArgs source_args(Args a, const char* function) {
    SourceArgs out;
    if (a.npos + a.nkw > 3) raise_new("TypeError", std::string(function) + "() takes at most 3 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    if (a.npos > 0) out.source = a.pos(0);
    if (a.npos > 1) out.encoding = a.pos(1);
    if (a.npos > 2) out.errors = a.pos(2);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        Obj* slot = a.kwnames[k] == N("source") ? &out.source : a.kwnames[k] == N("encoding") ? &out.encoding : a.kwnames[k] == N("errors") ? &out.errors : nullptr;
        if (slot == nullptr) unexpected_keyword(std::string(function) + "()", a.kwnames[k], {"source", "encoding", "errors"});
        if (!slot->is_unset())
            raise_new("TypeError", "argument for " + std::string(function) + "() given by name ('" + a.kwnames[k]->text + "') and position (" +
                                       std::to_string(a.kwnames[k] == N("source") ? 1 : a.kwnames[k] == N("encoding") ? 2 : 3) + ")");
        *slot = a.kw(k);
    }
    if (!out.encoding.is_unset() && as_str(out.encoding) == nullptr)
        raise_new("TypeError", std::string(function) + "() argument 'encoding' must be str, not " + type_of(out.encoding)->name);
    if (!out.encoding.is_unset()) no_null(as_str(out.encoding)->text);
    if (!out.errors.is_unset() && as_str(out.errors) == nullptr)
        raise_new("TypeError", std::string(function) + "() argument 'errors' must be str, not " + type_of(out.errors)->name);
    if (!out.errors.is_unset()) no_null(as_str(out.errors)->text);
    return out;
}
std::string encoded_source(const SourceArgs& s) {
    std::optional<std::string> encoding, errors;
    if (!s.encoding.is_unset()) encoding = as_str(s.encoding)->text;
    if (!s.errors.is_unset()) errors = as_str(s.errors)->text;
    Ref made = encode_with(s.source, encoding ? &*encoding : nullptr, errors ? &*errors : nullptr);
    return bytes_data(made.get());
}
std::string from_iterator(Obj it, const char* range_message) {
    std::string out;
    for (Ref v = for_next(it); !is_end(v); v = for_next(it)) out += static_cast<char>(byte_value(v.get(), range_message));
    return out;
}
Ref bytes_new_exact(Args rest);
Ref bytes_new_m(Obj self, Args a) {               // bytes_new_impl, and bytes_subtype_new for a subclass: the octets copied into its instance
    ClassObject* cls = new_wrapper_class(a, static_cast<ClassObject*>(self.object()));
    Ref made = bytes_new_exact(Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
    if (cls == types().bytes) return made;
    return own(new BytesInstance(cls, Kind::Bytes, bytes_data(made.get())));
}
Ref bytes_new_exact(Args rest) {
    SourceArgs s = source_args(rest, "bytes");
    if (s.source.is_unset()) {
        if (!s.encoding.is_unset()) raise_new("TypeError", "encoding without a string argument");
        if (!s.errors.is_unset()) raise_new("TypeError", "errors without a string argument");
        return bytes_new("");
    }
    Obj x = s.source;
    if (!s.encoding.is_unset()) {
        if (as_str(x) == nullptr) raise_new("TypeError", "encoding without a string argument");
        return bytes_new(encoded_source(s));
    }
    if (!s.errors.is_unset())
        raise_new("TypeError", as_str(x) != nullptr ? "string argument without an encoding" : "errors without a string argument");
    if (Obj special = type_lookup(type_of(x), N("__bytes__")); !special.is_unset()) {
        bool found = false;
        Ref r = call_special(x, "__bytes__", {}, &found);
        if (!is_kind(r.get(), Kind::Bytes))
            raise_new("TypeError", fully_qualified_name(type_of(x)) + ".__bytes__() must return a bytes, not " + fully_qualified_name(type_of(r.get())));
        return r;
    }
    if (as_str(x) != nullptr) raise_new("TypeError", "string argument without an encoding");
    if (has_index(x)) {
        std::int64_t size = 0;
        bool is_count = true;
        try {
            size = index_value(x);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            is_count = false;
        }
        if (is_count) {
            if (size < 0) raise_new("ValueError", "negative count");
            return bytes_new(std::string(static_cast<std::size_t>(size), '\0'));
        }
    }
    if (exact_bytes(x)) return Ref::share(x);   // PyBytes_FromObject: an exact bytes is itself; a subclass's octets are copied
    if (is_bytes_like(x)) return bytes_new(bytes_data(x));
    if (!type_lookup(type_of(x), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    Ref it;
    try {
        it = iter(x);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "cannot convert '" + type_of(x)->name + "' object to bytes");
    }
    length_hint(x);                              // _PyBytes_FromIterator: the iterator first, then the hint
    return bytes_new(from_iterator(it.get(), "bytes must be in range(0, 256)"));
}
Ref bytearray_new_m(Obj self, Args a) {           // tp_new: an empty one; __init__ fills it (a subclass's: its storage beside the octets)
    ClassObject* cls = new_wrapper_class(a, static_cast<ClassObject*>(self.object()));
    if (cls != types().bytearray) return own(new BytesInstance(cls, Kind::ByteArray, ""));
    return new_bytearray("");
}
void not_exported(Obj self) {                     // _canresize
    if (static_cast<BytesObject*>(self.object())->exports > 0) raise_new("BufferError", "Existing exports of data: object cannot be re-sized");
}
void can_resize(Obj self, std::size_t size) {     // as PyByteArray_Resize asks it: the same size is no change
    if (static_cast<BytesObject*>(self.object())->data.size() != size) not_exported(self);
}
Ref bytearray_init_m(Obj self, Args a) {          // bytearray___init___impl
    SourceArgs s = source_args(a, "bytearray");
    can_resize(self, 0);                         // Empty previous contents (yes, do this first of all!)
    std::string& out = bytes_data(self);
    if ((!s.encoding.is_unset() || !s.errors.is_unset()) && s.source.is_unset())
        raise_new("TypeError", !s.encoding.is_unset() ? "encoding without a string argument" : "errors without a string argument");
    if (s.source.is_unset()) {
        out.clear();
        return none_ref();
    }
    Obj x = s.source;
    if (as_str(x) != nullptr) {
        if (s.encoding.is_unset()) raise_new("TypeError", "string argument without an encoding");
        out = encoded_source(s);
        return none_ref();
    }
    if (!s.encoding.is_unset() || !s.errors.is_unset())
        raise_new("TypeError", !s.encoding.is_unset() ? "encoding without a string argument" : "errors without a string argument");
    if (has_index(x)) {
        std::int64_t size = 0;
        bool is_count = true;
        try {
            size = index_value(x);
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            is_count = false;
        }
        if (is_count) {
            if (size < 0) raise_new("ValueError", "negative count");
            can_resize(self, static_cast<std::size_t>(size));
            out.assign(static_cast<std::size_t>(size), '\0');
            return none_ref();
        }
    }
    if (is_bytes_like(x)) {
        std::string copy = bytes_data(x);
        can_resize(self, copy.size());
        out = std::move(copy);
        return none_ref();
    }
    if (!type_lookup(type_of(x), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    Ref it;
    try {
        it = iter(x);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "cannot convert '" + type_of(x)->name + "' object to bytearray");
    }
    std::string made = from_iterator(it.get(), "byte must be in range(0, 256)");
    can_resize(self, made.size());
    out = std::move(made);
    return none_ref();
}

// ---- a bytearray changes ----
std::string assigned_values(Obj values) {         // bytearray_ass_subscript's values
    if (is_bytes_like(values)) return bytes_data(values);
    ClassObject* vt = type_of(values);
    if (has_index(values) || as_str(values) != nullptr || !type_lookup(vt, N("__int__")).is_unset() || !type_lookup(vt, N("__float__")).is_unset())   // PyNumber_Check
        raise_new("TypeError", "can assign only bytes, buffers, or iterables of ints in range(0, 256)");
    if (!type_lookup(type_of(values), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    Ref it;
    try {
        it = iter(values);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "cannot convert '" + type_of(values)->name + "' object to bytearray");
    }
    return from_iterator(it.get(), "byte must be in range(0, 256)");
}
bool is_slice(Obj v) { return is_kind(v, Kind::Slice); }
std::size_t byte_index(Obj key, std::size_t size, const char* range_message, const char* type_message) {
    if (!has_index(key)) raise_new("TypeError", std::string(type_message) + " indices must be integers or slices, not " + type_of(key)->name);
    std::int64_t i = index_value(key, "IndexError");
    if (i < 0) i += static_cast<std::int64_t>(size);
    if (i < 0 || i >= static_cast<std::int64_t>(size)) raise_new("IndexError", range_message);
    return static_cast<std::size_t>(i);
}
Ref setitem_m(Obj self, Args a) {
    dunder_args(self, a, "__setitem__", 2);
    std::string& s = bytes_data(self);
    if (!is_slice(a.pos(0))) {
        std::size_t i = byte_index(a.pos(0), s.size(), "bytearray index out of range", "bytearray");
        int v = byte_value(a.pos(1));
        if (i >= s.size()) raise_new("IndexError", "bytearray index out of range");
        s[i] = static_cast<char>(v);
        return none_ref();
    }
    std::string values = assigned_values(a.pos(1));
    auto [start, stop, step, n] = slice_indices(a.pos(0), static_cast<std::int64_t>(s.size()));
    if (step == 1) {
        if (stop < start) stop = start;
        can_resize(self, s.size() - static_cast<std::size_t>(stop - start) + values.size());
        s.replace(static_cast<std::size_t>(start), static_cast<std::size_t>(stop - start), values);
        return none_ref();
    }
    if (static_cast<std::int64_t>(values.size()) != n)
        raise_new("ValueError", "attempt to assign bytes of size " + std::to_string(values.size()) + " to extended slice of size " + std::to_string(n));
    for (std::int64_t k = 0, at = start; k < n; ++k, at += step) s[static_cast<std::size_t>(at)] = values[static_cast<std::size_t>(k)];
    return none_ref();
}
Ref delitem_m(Obj self, Args a) {
    dunder_args(self, a, "__delitem__", 1);
    std::string& s = bytes_data(self);
    if (!is_slice(a.pos(0))) {
        std::size_t at = byte_index(a.pos(0), s.size(), "bytearray index out of range", "bytearray");
        can_resize(self, s.size() - 1);
        s.erase(at, 1);
        return none_ref();
    }
    auto [start, stop, step, n] = slice_indices(a.pos(0), static_cast<std::int64_t>(s.size()));
    if (n == 0) return none_ref();
    can_resize(self, s.size() - static_cast<std::size_t>(n));
    if (step < 0) {
        start = start + step * (n - 1);
        step = -step;
    }
    std::string out;
    std::int64_t next = start, left = n;
    for (std::int64_t i = 0; i < static_cast<std::int64_t>(s.size()); ++i) {
        if (left > 0 && i == next) { next += step; --left; continue; }
        out += s[static_cast<std::size_t>(i)];
    }
    s = std::move(out);
    return none_ref();
}
Ref append_m(Obj self, Args a) {
    onearg(a, "bytearray.append");
    int v = byte_value(a.pos(0));
    can_resize(self, bytes_data(self).size() + 1);
    bytes_data(self) += static_cast<char>(v);
    return none_ref();
}
Ref extend_m(Obj self, Args a) {
    onearg(a, "bytearray.extend");
    Obj x = a.pos(0);
    if (is_bytes_like(x)) {
        std::string copy = bytes_data(x);
        can_resize(self, bytes_data(self).size() + copy.size());
        bytes_data(self) += copy;
        return none_ref();
    }
    if (!type_lookup(type_of(x), N("__buffer__")).is_unset()) throw NotImplemented("[P2+] the buffer protocol (__buffer__)");
    Ref it;
    try {
        it = iter(x);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "can't extend bytearray with " + type_of(x)->name);
    }
    std::string more;
    try {
        more = from_iterator(it.get(), "byte must be in range(0, 256)");
    } catch (const PyError& e) {
        if (as_str(x) == nullptr || !isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "expected iterable of integers; got: 'str'");
    }
    can_resize(self, bytes_data(self).size() + more.size());
    bytes_data(self) += more;
    return none_ref();
}
Ref insert_m(Obj self, Args a) {
    clinic(a, "insert", "bytearray.insert", 2, 2);
    std::int64_t i = ssize_arg(a.pos(0));
    int v = byte_value(a.pos(1));
    std::string& s = bytes_data(self);
    auto n = static_cast<std::int64_t>(s.size());
    if (i < 0) { i += n; if (i < 0) i = 0; }
    if (i > n) i = n;
    can_resize(self, s.size() + 1);
    s.insert(static_cast<std::size_t>(i), 1, static_cast<char>(v));
    return none_ref();
}
Ref common_reduce(Obj self, std::int64_t proto) {   // _common_reduce: the class, the octets as the protocol takes them, the state
    Ref getstate = getattr(self, N("__getstate__"));   // _PyObject_GetState
    Ref state = invoke(getstate.get(), {});
    const std::string& s = bytes_data(self);
    Ref args;
    if (s.empty()) {
        args = tuple_new({});
    } else if (proto < 3) {                      // a str by latin-1, for Python 2's sake
        std::u32string text;
        for (char c : s) text += static_cast<char32_t>(static_cast<unsigned char>(c));
        Ref latin1 = str_from_codepoints(text), codec = str_new("latin-1");
        args = tuple_new({latin1.get(), codec.get()});
    } else {
        Ref octets = bytes_new(s);
        args = tuple_new({octets.get()});
    }
    return tuple_new({Obj::of(type_of(self)), args.get(), state.get()});
}
Ref reduce_m(Obj self, Args a) {                 // bytearray.__reduce__
    noargs(a, "bytearray.__reduce__");
    return common_reduce(self, 2);
}
Ref reduce_ex_m(Obj self, Args a) {              // bytearray.__reduce_ex__(proto=0, /)
    clinic(a, "__reduce_ex__", "bytearray.__reduce_ex__", 0, 1);
    return common_reduce(self, a.npos == 1 ? c_int_arg(a.pos(0)) : 0);
}
Ref pop_m(Obj self, Args a) {
    clinic(a, "pop", "bytearray.pop", 0, 1);
    std::int64_t i = a.npos == 1 ? ssize_arg(a.pos(0)) : -1;
    std::string& s = bytes_data(self);
    if (s.empty()) raise_new("IndexError", "pop from empty bytearray");
    auto n = static_cast<std::int64_t>(s.size());
    if (i < 0) i += n;
    if (i < 0 || i >= n) raise_new("IndexError", "pop index out of range");
    int v = u(s[static_cast<std::size_t>(i)]);
    can_resize(self, s.size() - 1);
    s.erase(static_cast<std::size_t>(i), 1);
    return small(v);
}
Ref remove_m(Obj self, Args a) {
    onearg(a, "bytearray.remove");
    int v = byte_value(a.pos(0));
    std::string& s = bytes_data(self);
    std::size_t at = s.find(static_cast<char>(v));
    if (at == std::string::npos) raise_new("ValueError", "value not found in bytearray");
    can_resize(self, s.size() - 1);
    s.erase(at, 1);
    return none_ref();
}
Ref reverse_m(Obj self, Args a) {
    noargs(a, "bytearray.reverse");
    std::reverse(bytes_data(self).begin(), bytes_data(self).end());
    return none_ref();
}
Ref clear_m(Obj self, Args a) {
    noargs(a, "bytearray.clear");
    can_resize(self, 0);
    bytes_data(self).clear();
    return none_ref();
}
Ref copy_m(Obj self, Args a) {
    noargs(a, "bytearray.copy");
    return new_bytearray(bytes_data(self));
}
Ref resize_m(Obj self, Args a) {
    onearg(a, "bytearray.resize");
    std::int64_t size = ssize_arg(a.pos(0));
    if (size < 0) raise_new("ValueError", "Can only resize to positive sizes, got " + std::to_string(size));
    can_resize(self, static_cast<std::size_t>(size));
    bytes_data(self).resize(static_cast<std::size_t>(size), '\0');
    return none_ref();
}
Ref take_bytes_m(Obj self, Args a) {              // bytearray.take_bytes(n=None): the first n, removed
    clinic(a, "take_bytes", "bytearray.take_bytes", 0, 1);
    std::string& s = bytes_data(self);
    auto size = static_cast<std::int64_t>(s.size());
    if (a.npos == 1 && a.pos(0) != None() && !has_index(a.pos(0))) raise_new("TypeError", "n must be an integer or None");
    std::int64_t n = a.npos == 0 || a.pos(0) == None() ? size : index_value(a.pos(0));
    if (n < 0) n += size;
    if (n < 0 || n > size) raise_new("IndexError", "can't take " + std::to_string(n) + " bytes outside size " + std::to_string(size));
    not_exported(self);                          // asked outright, whatever n is
    Ref out = bytes_new(std::string_view(s).substr(0, static_cast<std::size_t>(n)));
    s.erase(0, static_cast<std::size_t>(n));
    return out;
}
Ref iadd_m(Obj self, Args a) {
    dunder_args(self, a, "__iadd__", 1);
    bytes_iadd(self, a.pos(0));
    return Ref::share(self);
}
Ref imul_m(Obj self, Args a) {
    dunder_args(self, a, "__imul__", 1);
    return bytes_repeat(self, index_value(a.pos(0)), true);
}
Ref bytes_dunder_m(Obj self, Args a) {
    noargs(a, "bytes.__bytes__");
    return exact_bytes(self) ? Ref::share(self) : bytes_new(bytes_data(self));
}
Ref getnewargs_m(Obj self, Args a) {             // bytes___getnewargs___impl: Py_BuildValue("(y#)"), a new bytes of the octets
    noargs(a, "bytes.__getnewargs__");
    Ref copy = bytes_new(bytes_data(self));
    return tuple_new({copy.get()});
}
Ref str_dunder_m(Obj self, Args a) {
    dunder_args(self, a, "__str__", 0);
    return bytes_repr(self);
}

// ---- the Unicode errors (Objects/exceptions.c) ----
Ref unicode_field(Obj self, const char* name) {
    Obj v = exception_field(self, name);
    return v.is_unset() ? none_ref() : Ref::share(v);
}
template <int which>
Ref unicode_get(Obj self) {
    static constexpr std::array<const char*, 5> names{"encoding", "object", "start", "end", "reason"};
    return unicode_field(self, names[static_cast<std::size_t>(which)]);
}
template <int which>
void unicode_set(Obj self, Obj value) {
    static constexpr std::array<const char*, 5> names{"encoding", "object", "start", "end", "reason"};
    set_exception_field(self, names[static_cast<std::size_t>(which)], value);
}
void set_unicode_args(Obj self, Args a) {
    std::vector<Obj> items(a.data, a.data + a.npos);
    Ref args = own(new Tuple);
    for (Obj v : items) {
        incref(v);
        static_cast<Tuple*>(args.get().object())->items.push_back(v);
    }
    set_exception_field(self, "args", args.get());
}
std::int64_t size_argument(Obj v) {
    return index_value(v);
}
Ref unicode_error_init(Obj self, Args a, const char* name, bool decode) {
    if (a.nkw != 0) raise_new("TypeError", std::string(name) + "() takes no keyword arguments");
    set_unicode_args(self, a);
    if (a.npos != 5) raise_new("TypeError", "function takes exactly 5 arguments (" + std::to_string(a.npos) + " given)");
    if (as_str(a.pos(0)) == nullptr) raise_new("TypeError", "argument 1 must be str, not " + type_of(a.pos(0))->name);
    if (decode) {
        if (!is_bytes_like(a.pos(1))) raise_new("TypeError", "a bytes-like object is required, not '" + type_of(a.pos(1))->name + "'");
    } else if (as_str(a.pos(1)) == nullptr) {
        raise_new("TypeError", "argument 2 must be str, not " + type_of(a.pos(1))->name);
    }
    size_argument(a.pos(2));
    size_argument(a.pos(3));
    if (as_str(a.pos(4)) == nullptr) raise_new("TypeError", "argument 5 must be str, not " + type_of(a.pos(4))->name);
    set_exception_field(self, "encoding", a.pos(0));
    if (decode && !is_kind(a.pos(1), Kind::Bytes)) {
        Ref copy = bytes_new(bytes_data(a.pos(1)));
        set_exception_field(self, "object", copy.get());
    } else {
        set_exception_field(self, "object", a.pos(1));
    }
    set_exception_field(self, "start", a.pos(2));
    set_exception_field(self, "end", a.pos(3));
    set_exception_field(self, "reason", a.pos(4));
    return none_ref();
}
Ref encode_error_init(Obj self, Args a) { return unicode_error_init(self, a, "UnicodeEncodeError", false); }
Ref decode_error_init(Obj self, Args a) { return unicode_error_init(self, a, "UnicodeDecodeError", true); }
Ref translate_error_init(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "UnicodeTranslateError() takes no keyword arguments");
    set_unicode_args(self, a);
    if (a.npos != 4) raise_new("TypeError", "function takes exactly 4 arguments (" + std::to_string(a.npos) + " given)");
    if (as_str(a.pos(0)) == nullptr) raise_new("TypeError", "argument 1 must be str, not " + type_of(a.pos(0))->name);
    size_argument(a.pos(1));
    size_argument(a.pos(2));
    if (as_str(a.pos(3)) == nullptr) raise_new("TypeError", "argument 4 must be str, not " + type_of(a.pos(3))->name);
    set_exception_field(self, "object", a.pos(0));
    set_exception_field(self, "start", a.pos(1));
    set_exception_field(self, "end", a.pos(2));
    set_exception_field(self, "reason", a.pos(3));
    return none_ref();
}
std::string text_of(Obj v) {
    Ref s = str_of(v);
    return as_str(s.get())->text;
}
std::string character_shown(const Str* object, std::int64_t start) {
    char32_t c = object->at(static_cast<std::size_t>(start));
    return c <= 0xFF ? "\\x" + hex_text(c, 2) : c <= 0xFFFF ? "\\u" + hex_text(c, 4) : "\\U" + hex_text(c, 8);
}
Ref encode_error_str(Obj self, Args) {            // UnicodeEncodeError_str
    Obj object = exception_field(self, "object");
    if (object.is_unset()) return str_new("");
    std::string encoding = text_of(exception_field(self, "encoding")), reason = text_of(exception_field(self, "reason"));
    std::int64_t start = 0, end = 0;
    as_int(exception_field(self, "start"), start);
    as_int(exception_field(self, "end"), end);
    const Str* text = as_str(object);
    if (text != nullptr && start >= 0 && start < static_cast<std::int64_t>(text->length) && end == start + 1)
        return str_new("'" + encoding + "' codec can't encode character '" + character_shown(text, start) + "' in position " + std::to_string(start) + ": " + reason);
    return str_new("'" + encoding + "' codec can't encode characters in position " + std::to_string(start) + "-" + std::to_string(end - 1) + ": " + reason);
}
Ref decode_error_str(Obj self, Args) {            // UnicodeDecodeError_str
    Obj object = exception_field(self, "object");
    if (object.is_unset()) return str_new("");
    std::string encoding = text_of(exception_field(self, "encoding")), reason = text_of(exception_field(self, "reason"));
    std::int64_t start = 0, end = 0;
    as_int(exception_field(self, "start"), start);
    as_int(exception_field(self, "end"), end);
    if (is_bytes_like(object) && start >= 0 && start < static_cast<std::int64_t>(bytes_data(object).size()) && end == start + 1)
        return str_new("'" + encoding + "' codec can't decode byte 0x" + hex_text(u(bytes_data(object)[static_cast<std::size_t>(start)]), 2) +
                       " in position " + std::to_string(start) + ": " + reason);
    return str_new("'" + encoding + "' codec can't decode bytes in position " + std::to_string(start) + "-" + std::to_string(end - 1) + ": " + reason);
}
Ref translate_error_str(Obj self, Args) {         // UnicodeTranslateError_str
    Obj object = exception_field(self, "object");
    if (object.is_unset()) return str_new("");
    std::string reason = text_of(exception_field(self, "reason"));
    std::int64_t start = 0, end = 0;
    as_int(exception_field(self, "start"), start);
    as_int(exception_field(self, "end"), end);
    const Str* text = as_str(object);
    if (text != nullptr && start >= 0 && start < static_cast<std::int64_t>(text->length) && end == start + 1)
        return str_new("can't translate character '" + character_shown(text, start) + "' in position " + std::to_string(start) + ": " + reason);
    return str_new("can't translate characters in position " + std::to_string(start) + "-" + std::to_string(end - 1) + ": " + reason);
}
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
template <int which>
void unicode_getset(ClassObject* c, const char* name) {
    c->attrs.set(intern(name), Obj::of(new GetSet(name, c, unicode_get<which>, unicode_set<which>)));
}
}  // namespace

// ---- what the operators and the rest of the runtime call ----
CodecHooks& codec_hooks() {
    static CodecHooks hooks;
    return hooks;
}
void ensure_codecs() {
    if (!codec_hooks().text_encode.get().is_unset()) return;
    Ref name = str_new("_codecs");
    import_module_level(name.get(), Obj{}, Obj{}, Obj{}, 0);
    if (codec_hooks().text_encode.get().is_unset()) throw NotImplemented("the codec registry (_codecs gave the runtime no hooks)");
}
Ref bytes_new(std::string_view s) {               // an empty one, and each of one byte, is one object (bytes_empty, characters)
    if (s.size() > 1) return own(new BytesObject(Kind::Bytes, std::string(s)));
    static std::array<Ref, 257> shared;
    std::size_t at = s.empty() ? 256 : u(s[0]);
    if (shared[at].get().is_unset()) shared[at] = own(new BytesObject(Kind::Bytes, std::string(s)));
    return Ref::share(shared[at].get());
}
Obj bytes_constant(const char* data, std::size_t size) { return bytes_new(std::string_view(data, size)).release(); }
Ref bytes_repr(Obj v) {                           // PyBytes_Repr, and bytearray's around it
    const std::string& s = bytes_data(v);
    bool single = s.find('\'') != std::string::npos, dbl = s.find('"') != std::string::npos;
    char quote = single && !dbl ? '"' : '\'';
    std::string out = "b";
    out += quote;
    for (char c : s) {
        if (c == quote || c == '\\') { out += '\\'; out += c; }
        else if (c == '\t') out += "\\t";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (u(c) < 0x20 || u(c) >= 0x7F) out += "\\x" + hex_text(u(c), 2);
        else out += c;
    }
    out += quote;
    return str_new(is_bytearray(v) ? type_of(v)->name + "(" + out + ")" : out);   // bytearray_repr: the class's name
}
Ref bytes_getitem(Obj self, Obj key) {
    const std::string& s = bytes_data(self);
    const char* kind = is_bytearray(self) ? "bytearray" : "byte";
    if (is_kind(key, Kind::Slice)) {
        auto [start, stop, step, n] = slice_indices(key, static_cast<std::int64_t>(s.size()));
        if (exact_bytes(self) && start == 0 && step == 1 && n == static_cast<std::int64_t>(s.size())) return Ref::share(self);
        std::string out;
        for (std::int64_t k = 0, at = start; k < n; ++k, at += step) out += s[static_cast<std::size_t>(at)];
        return make_like(self, out);
    }
    std::size_t i = byte_index(key, s.size(), is_bytearray(self) ? "bytearray index out of range" : "index out of range", kind);
    return small(u(bytes_data(self)[i]));
}
bool bytes_contains(Obj self, Obj item) {         // _Py_bytes_contains
    std::int64_t v = 0;
    bool number = has_index(item);
    if (number) {
        try {
            v = clipped_index(item);                  // PyNumber_AsSsize_t(arg, NULL)
        } catch (const PyError&) {
            number = false;
        }
    }
    if (!number) return bytes_data(self).find(buffer_of(item)) != std::string::npos;
    if (v < 0 || v >= 256) raise_new("ValueError", "byte must be in range(0, 256)");
    return bytes_data(self).find(static_cast<char>(v)) != std::string::npos;
}
Ref bytes_compare(CmpOp op, Obj a, Obj b) {
    int c = bytes_data(a).compare(bytes_data(b));
    switch (op) {
        case CmpOp::Eq: return yes_no(c == 0);
        case CmpOp::Ne: return yes_no(c != 0);
        case CmpOp::Lt: return yes_no(c < 0);
        case CmpOp::Le: return yes_no(c <= 0);
        case CmpOp::Gt: return yes_no(c > 0);
        default: return yes_no(c >= 0);
    }
}
Ref bytes_concat(Obj a, Obj b) {                  // bytes_concat, bytearray_concat
    if (!is_bytes_like(b) && type_lookup(type_of(b), N("__buffer__")).is_unset())
        raise_new("TypeError", "can't concat " + type_of(b)->name + " to " + (is_bytearray(a) ? "bytearray" : "bytes"));
    std::string_view right = buffer_of(b);
    if (!is_bytearray(a)) {                       // an empty side: the other, when it is an exact bytes (the left side asked first)
        if (bytes_data(a).empty() && exact_bytes(b)) return Ref::share(b);
        if (right.empty() && exact_bytes(a)) return Ref::share(a);
    }
    std::string out = bytes_data(a);
    out += right;
    return make_like(a, out);
}
void bytes_iadd(Obj a, Obj b) {
    if (!is_bytes_like(b) && type_lookup(type_of(b), N("__buffer__")).is_unset())
        raise_new("TypeError", "can't concat " + type_of(b)->name + " to bytearray");
    std::string copy(buffer_of(b));
    can_resize(a, bytes_data(a).size() + copy.size());
    bytes_data(a) += copy;
}
Ref bytes_repeat(Obj self, std::int64_t count, bool in_place) {
    const std::string& s = bytes_data(self);
    if (exact_bytes(self) && (count == 1 || s.empty())) return count <= 0 ? bytes_new("") : Ref::share(self);
    std::string out;
    if (count > 0) {
        if (s.size() * static_cast<std::size_t>(count) > (std::size_t{1} << 32)) throw NotImplemented("a bytes object of over 4 GB");
        out.reserve(s.size() * static_cast<std::size_t>(count));
        for (std::int64_t i = 0; i < count; ++i) out += s;
    }
    if (in_place) {
        can_resize(self, out.size());
        bytes_data(self) = std::move(out);
        return Ref::share(self);
    }
    return make_like(self, out);
}
Ref str_from_bytes(Obj source, Obj encoding, Obj errors) {   // str(b, encoding, errors): PyUnicode_FromEncodedObject
    if (!is_bytes_like(source))
        raise_new("TypeError", "decoding to str: need a bytes-like object, " + type_of(source)->name + " found");
    std::string copy = bytes_data(source);
    std::optional<std::string> enc, err;
    if (!encoding.is_unset()) no_null(enc.emplace(as_str(encoding)->text));
    if (!errors.is_unset()) no_null(err.emplace(as_str(errors)->text));
    return decode_with(copy, enc ? &*enc : nullptr, err ? &*err : nullptr);
}

std::string utf8_with_errors(Obj text, const char* errors) { return encode_utf8(as_str(text), text, errors); }
Ref unicode_decode(std::string_view s, const std::string* encoding, const std::string* errors) { return decode_with(s, encoding, errors); }

void init_bytes() {
    destroyer(Kind::Bytes) = [](Object* o) { delete static_cast<BytesObject*>(o); };
    destroyer(Kind::ByteArray) = [](Object* o) { delete static_cast<BytesObject*>(o); };
    Types& t = types();
    auto* make = new Builtin("__new__", bytes_new_m, Obj::of(t.bytes), Binding::Function);
    make->owner = t.bytes;
    make->flags |= IMMORTAL;
    t.bytes->attrs.set(N("__new__"), Obj::of(make));
    make = new Builtin("__new__", bytearray_new_m, Obj::of(t.bytearray), Binding::Function);
    make->owner = t.bytearray;
    make->flags |= IMMORTAL;
    t.bytearray->attrs.set(N("__new__"), Obj::of(make));
    for (ClassObject* c : {t.bytes, t.bytearray}) {
        method(c, "__str__", str_dunder_m);
        method(c, "decode", decode_m);
        method(c, "find", find_m<false>);
        method(c, "rfind", find_m<true>);
        method(c, "index", index_m<false>);
        method(c, "rindex", index_m<true>);
        method(c, "count", count_m);
        method(c, "startswith", tailmatch_m<false>);
        method(c, "endswith", tailmatch_m<true>);
        method(c, "lower", map_m<to_lower>);
        method(c, "upper", map_m<to_upper>);
        method(c, "swapcase", swapcase_m);
        method(c, "capitalize", capitalize_m);
        method(c, "title", title_m);
        method(c, "isalpha", all_m<is_alpha>);
        method(c, "isdigit", all_m<is_digit>);
        method(c, "isspace", all_m<is_space>);
        method(c, "isalnum", all_m<is_alnum>);
        method(c, "isascii", isascii_m);
        method(c, "islower", islower_m);
        method(c, "isupper", isupper_m);
        method(c, "istitle", istitle_m);
        method(c, "strip", strip_m<2>);
        method(c, "lstrip", strip_m<0>);
        method(c, "rstrip", strip_m<1>);
        method(c, "split", split_m);
        method(c, "rsplit", rsplit_m);
        method(c, "splitlines", splitlines_m);
        method(c, "partition", partition_m<false>);
        method(c, "rpartition", partition_m<true>);
        method(c, "join", join_m);
        method(c, "replace", replace_m);
        method(c, "ljust", pad_m<0>);
        method(c, "rjust", pad_m<1>);
        method(c, "center", pad_m<2>);
        method(c, "zfill", zfill_m);
        method(c, "expandtabs", expandtabs_m);
        method(c, "removeprefix", removeprefix_m);
        method(c, "removesuffix", removesuffix_m);
        method(c, "translate", translate_m);
        method(c, "maketrans", maketrans_m, Binding::Function);
        method(c, "hex", hex_m);
        method(c, "fromhex", fromhex_m, Binding::ClassMethod);
    }
    method(t.bytes, "__bytes__", bytes_dunder_m);
    method(t.bytes, "__getnewargs__", getnewargs_m);
    method(t.bytearray, "__init__", bytearray_init_m);
    method(t.bytearray, "__setitem__", setitem_m);
    method(t.bytearray, "__delitem__", delitem_m);
    method(t.bytearray, "__iadd__", iadd_m);
    method(t.bytearray, "__imul__", imul_m);
    method(t.bytearray, "append", append_m);
    method(t.bytearray, "extend", extend_m);
    method(t.bytearray, "insert", insert_m);
    method(t.bytearray, "pop", pop_m);
    method(t.bytearray, "__reduce__", reduce_m);
    method(t.bytearray, "__reduce_ex__", reduce_ex_m);
    method(t.bytearray, "remove", remove_m);
    method(t.bytearray, "reverse", reverse_m);
    method(t.bytearray, "clear", clear_m);
    method(t.bytearray, "copy", copy_m);
    method(t.bytearray, "resize", resize_m);
    method(t.bytearray, "take_bytes", take_bytes_m);
    t.bytearray->attrs.set(N("__hash__"), None());
    method(t.str, "encode", str_encode_m);

    ClassObject* enc = exception_class("UnicodeEncodeError");
    method(enc, "__init__", encode_error_init);
    method(enc, "__str__", encode_error_str);
    ClassObject* dec = exception_class("UnicodeDecodeError");
    method(dec, "__init__", decode_error_init);
    method(dec, "__str__", decode_error_str);
    for (ClassObject* c : {enc, dec}) {
        unicode_getset<0>(c, "encoding");
        unicode_getset<1>(c, "object");
        unicode_getset<2>(c, "start");
        unicode_getset<3>(c, "end");
        unicode_getset<4>(c, "reason");
    }
    ClassObject* trans = exception_class("UnicodeTranslateError");
    method(trans, "__init__", translate_error_init);
    method(trans, "__str__", translate_error_str);
    unicode_getset<1>(trans, "object");
    unicode_getset<2>(trans, "start");
    unicode_getset<3>(trans, "end");
    unicode_getset<4>(trans, "reason");
}

// ---- _codecs.py's primitive: the codecs here, by name, and what it keeps of an exception ----
Ref i_codecs_call(Obj, Args a) {
    const std::string& name = as_str(a.pos(0))->text;
    Args r{a.data + 1, a.npos - 1, nullptr, 0};
    if (name == "decode") {                      // (codec, bytes, errors or None, final): (str, consumed)
        std::string data = bytes_data(r.pos(1));
        std::string errors = r.pos(2) == None() ? "strict" : as_str(r.pos(2))->text;
        bool final = truth(r.pos(3));
        const std::string& codec = as_str(r.pos(0))->text;
        std::size_t consumed = data.size();
        Ref text = codec == "utf-8" ? decode_utf8(data, errors, final ? nullptr : &consumed)
                 : codec == "ascii" ? decode_ascii(data, errors) : decode_latin1(data);
        return tuple_new({text.get(), Obj::small(static_cast<std::int64_t>(consumed))});
    }
    if (name == "encode") {                      // (codec, str, errors or None): bytes
        const std::string& codec = as_str(r.pos(0))->text;
        std::string errors = r.pos(2) == None() ? "strict" : as_str(r.pos(2))->text;
        const Str* s = as_str(r.pos(1));
        return bytes_new(codec == "utf-8" ? encode_utf8(s, r.pos(1), errors) : encode_ucs1(s, r.pos(1), codec == "ascii" ? 128 : 256, errors));
    }
    if (name == "decode_wide") {                 // ("utf-16" or "utf-32", bytes, errors or None, byteorder, final): (str, consumed, byteorder)
        std::string data = bytes_data(r.pos(1));
        std::string errors = r.pos(2) == None() ? "strict" : as_str(r.pos(2))->text;
        int order = static_cast<int>(r.pos(3).small_value());
        bool final = truth(r.pos(4));
        std::size_t consumed = data.size();       // overwritten unless final
        Ref text = as_str(r.pos(0))->text == "utf-16" ? decode_utf16(data, errors, &order, final ? nullptr : &consumed)
                                                      : decode_utf32(data, errors, &order, final ? nullptr : &consumed);
        return tuple_new({text.get(), Obj::small(static_cast<std::int64_t>(consumed)), Obj::small(order)});
    }
    if (name == "encode_wide") {                 // ("utf-16" or "utf-32", str, errors or None, byteorder): bytes
        std::string errors = r.pos(2) == None() ? "strict" : as_str(r.pos(2))->text;
        int order = static_cast<int>(r.pos(3).small_value());
        return bytes_new(encode_utf_wide(as_str(r.pos(1)), r.pos(1), errors, order, as_str(r.pos(0))->text == "utf-16" ? 2 : 4));
    }
    if (name == "buffer") return bytes_new(buffer_of(r.pos(0)));   // PyObject_GetBuffer: the bytes of a bytes-like object
    if (name == "field") {                       // (exc, name, default): what the exception holds, raw
        Obj v = exception_field(r.pos(0), as_str(r.pos(1))->text.c_str());
        return Ref::share(v.is_unset() ? r.pos(2) : v);
    }
    if (name == "builtin") {                     // PyCFunction_NewEx(def, NULL, NULL): a built-in function of no module
        r.pos(0).object()->cls = types().builtin;
        setattr(r.pos(0), N("__module__"), None());
        return none_ref();
    }
    if (name == "refuse") throw NotImplemented(as_str(r.pos(0))->text);
    if (name == "hooks") {                       // (text_encode, text_decode, unknown_handler, start)
        codec_hooks().text_encode = Ref::share(r.pos(0));
        codec_hooks().text_decode = Ref::share(r.pos(1));
        codec_hooks().unknown_handler = Ref::share(r.pos(2));
        codec_hooks().start = Ref::share(r.pos(3));
        codec_hooks().lookup_text = Ref::share(r.pos(4));
        return none_ref();
    }
    throw NotImplemented("_codecs primitive " + name);
}

}  // namespace bella
