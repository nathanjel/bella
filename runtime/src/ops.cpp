// runtime/src/ops.cpp -- operators, truth, str() and repr(), attributes, items, iteration and
// unpacking on the C++ types (bella/runtime.hpp). User classes' special methods come with step 3a.2.
#include "bella/runtime.hpp"

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <tuple>

namespace bella {

namespace {
constexpr std::int64_t SMALL_MIN = -(std::int64_t{1} << 62);
constexpr std::int64_t SMALL_MAX = (std::int64_t{1} << 62) - 1;

// an int the C++ core computes on: a small int or a bool
bool as_int(Obj v, std::int64_t& out) {
    if (v.is_small()) {
        out = v.small_value();
        return true;
    }
    if (is_kind(v, Kind::Bool)) {
        out = static_cast<BoolObject*>(v.object())->value ? 1 : 0;
        return true;
    }
    return false;
}

Ref small(std::int64_t v) {
    if (v < SMALL_MIN || v > SMALL_MAX) throw NotImplemented("BigInt: a result left the 63-bit immediate range");
    return Ref::steal(Obj::small(v));
}

[[noreturn]] void unsupported(const char* sym, Obj a, Obj b) {
    raise_new("TypeError", std::string("unsupported operand type(s) for ") + sym + ": '" + type_of(a)->name + "' and '" +
                               type_of(b)->name + "'");
}

const char* symbol(BinOp op) {
    switch (op) {
        case BinOp::Add: return "+";
        case BinOp::Sub: return "-";
        case BinOp::Mul: return "*";
        case BinOp::TrueDiv: return "/";
        case BinOp::FloorDiv: return "//";
        case BinOp::Mod: return "%";
        case BinOp::Pow: return "** or pow()";
        case BinOp::LShift: return "<<";
        case BinOp::RShift: return ">>";
        case BinOp::And: return "&";
        case BinOp::Or: return "|";
        case BinOp::Xor: return "^";
        case BinOp::MatMul: return "@";
    }
    return "?";
}

// int.hpp holds the int semantics, differentially tested against CPython (make int-test); its
// C++ errors become the Python exceptions they stand for
Ref int_binary(BinOp op, std::int64_t a, std::int64_t b, bool both_bool) {
    Int x = Int::from_small(a), y = Int::from_small(b);
    try {
        switch (op) {
            case BinOp::Add: return small(int_add(x, y).small());
            case BinOp::Sub: return small(int_sub(x, y).small());
            case BinOp::Mul: return small(int_mul(x, y).small());
            case BinOp::FloorDiv: return small(int_floordiv(x, y).small());
            case BinOp::Mod: return small(int_mod(x, y).small());
            case BinOp::Pow: return small(int_pow(x, y).small());
            case BinOp::LShift: return small(int_lshift(x, y).small());
            case BinOp::RShift: return small(int_rshift(x, y).small());
            case BinOp::And: return both_bool ? Ref::steal(boolean((a & b) != 0)) : small(int_and(x, y).small());
            case BinOp::Or: return both_bool ? Ref::steal(boolean((a | b) != 0)) : small(int_or(x, y).small());
            case BinOp::Xor: return both_bool ? Ref::steal(boolean((a ^ b) != 0)) : small(int_xor(x, y).small());
            case BinOp::TrueDiv:
                if (b == 0) raise_new("ZeroDivisionError", "division by zero");
                throw NotImplemented("float: int / int");
            case BinOp::MatMul:
                break;
        }
    } catch (const bella::ZeroDivisionError& e) {
        raise_new("ZeroDivisionError", e.what());
    } catch (const bella::ValueError& e) {
        raise_new("ValueError", e.what());
    }
    raise_new("TypeError", std::string("unsupported operand type(s) for ") + symbol(op) + ": 'int' and 'int'");
}

Ref concat_str(const Str* a, const Str* b) { return str_new(a->text + b->text); }
}  // namespace

// The C++ types' own binary operations: NotImplemented when the operands are not theirs.
Ref native_binary(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (op == BinOp::Add && sa != nullptr && sb != nullptr) return concat_str(sa, sb);
    if (op == BinOp::Mul && (sa != nullptr) != (sb != nullptr)) {
        const Str* s = sa != nullptr ? sa : sb;
        std::int64_t n;
        if (as_int(sa != nullptr ? b : a, n)) {
            std::string out;
            for (std::int64_t i = 0; i < n; ++i) out += s->text;
            return str_new(out);
        }
    }
    if (op == BinOp::Add && is_kind(a, Kind::Tuple) && is_kind(b, Kind::Tuple)) {
        std::vector<Obj> items;
        for (Obj v : static_cast<Tuple*>(a.object())->items) { incref(v); items.push_back(v); }
        for (Obj v : static_cast<Tuple*>(b.object())->items) { incref(v); items.push_back(v); }
        return tuple_steal(std::move(items));
    }
    if (op == BinOp::Add && is_kind(a, Kind::List) && is_kind(b, Kind::List)) {
        auto* l = new List;
        Ref r = own(l);
        for (Obj v : static_cast<List*>(a.object())->items) { incref(v); l->items.push_back(v); }
        for (Obj v : static_cast<List*>(b.object())->items) { incref(v); l->items.push_back(v); }
        return r;
    }
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}

namespace {
const char* const BIN_NAMES[][3] = {
    {"__add__", "__radd__", "__iadd__"}, {"__sub__", "__rsub__", "__isub__"}, {"__mul__", "__rmul__", "__imul__"},
    {"__truediv__", "__rtruediv__", "__itruediv__"}, {"__floordiv__", "__rfloordiv__", "__ifloordiv__"},
    {"__mod__", "__rmod__", "__imod__"}, {"__pow__", "__rpow__", "__ipow__"}, {"__lshift__", "__rlshift__", "__ilshift__"},
    {"__rshift__", "__rrshift__", "__irshift__"}, {"__and__", "__rand__", "__iand__"}, {"__or__", "__ror__", "__ior__"},
    {"__xor__", "__rxor__", "__ixor__"}, {"__matmul__", "__rmatmul__", "__imatmul__"}};
bool is_heap_obj(Obj v) { return v.is_object() && v.object()->kind == Kind::Instance; }
bool not_implemented(const Ref& r) { return r.get() == Obj::of(NOTIMPLEMENTED); }

// one operand's method: a class's dunder (absent: *has false), or the C++ type's operation
Ref operand_method(Obj self, Obj other, BinOp op, bool reflected, bool& has) {
    if (is_heap_obj(self)) {
        Ref r = call_special(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0], {other}, &has);
        return r;
    }
    has = true;
    return reflected ? native_binary(op, other, self) : native_binary(op, self, other);
}
}  // namespace

// binary_op1: the left operand's method, unless the right operand's type is a subclass that
// overrides the reflected method, which then goes first; the reflected method last
bool set_like_view(Obj v) { return is_kind(v, Kind::DictView) && static_cast<DictView*>(v.object())->which != DictView::Values; }

Ref binary(BinOp op, Obj a, Obj b) {
    if ((set_like_view(a) || set_like_view(b)) &&
        (op == BinOp::And || op == BinOp::Or || op == BinOp::Sub || op == BinOp::Xor))
        throw NotImplemented("set operations on dict keys and items views");
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    if (!is_heap_obj(a) && !is_heap_obj(b)) {
        Ref r = native_binary(op, a, b);
        if (!not_implemented(r)) return r;
        if (op == BinOp::Add && as_str(a) != nullptr)
            raise_new("TypeError", "can only concatenate str (not \"" + type_of(b)->name + "\") to str");
        unsupported(symbol(op), a, b);
    }
    ClassObject *ta = type_of(a), *tb = type_of(b);
    const char* rname = BIN_NAMES[static_cast<int>(op)][1];
    bool tried_reflected = false, has = false;
    if (ta != tb && is_heap_obj(b) && is_subclass(tb, ta)) {
        Obj rb = type_lookup(tb, intern(rname));
        Obj ra = is_heap_obj(a) ? type_lookup(ta, intern(rname)) : Obj{};
        if (!rb.is_unset() && rb != ra) {
            tried_reflected = true;
            Ref r = call_special(b, rname, {a});
            if (!not_implemented(r)) return r;
        }
    }
    Ref r = operand_method(a, b, op, false, has);
    if (has && !not_implemented(r)) return r;
    if (ta != tb && !tried_reflected) {
        r = operand_method(b, a, op, true, has);
        if (has && !not_implemented(r)) return r;
    }
    unsupported(symbol(op), a, b);
}

Ref inplace(BinOp op, Obj a, Obj b) {
    if (is_kind(a, Kind::List) && op == BinOp::Add) {
        list_extend(a, b);
        return Ref::share(a);
    }
    if (is_heap_obj(a)) {
        bool has = false;
        Ref r = call_special(a, BIN_NAMES[static_cast<int>(op)][2], {b}, &has);
        if (has && !not_implemented(r)) return r;
    }
    return binary(op, a, b);
}

namespace {
Ref unary_special(Obj a, const char* dunder, const char* sym) {
    bool has = false;
    if (is_heap_obj(a)) {
        Ref r = call_special(a, dunder, {}, &has);
        if (has) return r;
    }
    raise_new("TypeError", std::string("bad operand type for unary ") + sym + ": '" + type_of(a)->name + "'");
}
}  // namespace

Ref unary_neg(Obj a) {
    std::int64_t x;
    if (as_int(a, x)) return small(int_neg(Int::from_small(x)).small());
    return unary_special(a, "__neg__", "-");
}
Ref unary_pos(Obj a) {
    std::int64_t x;
    if (as_int(a, x)) return small(x);
    return unary_special(a, "__pos__", "+");
}
Ref unary_invert(Obj a) {
    std::int64_t x;
    if (is_kind(a, Kind::Bool)) throw NotImplemented("~ on a bool (a DeprecationWarning in CPython 3.15)");
    if (as_int(a, x)) return small(~x);
    return unary_special(a, "__invert__", "~");
}

// ---- comparison ----
namespace {
const char* symbol(CmpOp op) {
    switch (op) {
        case CmpOp::Lt: return "<";
        case CmpOp::Le: return "<=";
        case CmpOp::Eq: return "==";
        case CmpOp::Ne: return "!=";
        case CmpOp::Gt: return ">";
        case CmpOp::Ge: return ">=";
        default: return "?";
    }
}
template <class T>
bool ordered(CmpOp op, const T& a, const T& b) {
    switch (op) {
        case CmpOp::Lt: return a < b;
        case CmpOp::Le: return a <= b;
        case CmpOp::Eq: return a == b;
        case CmpOp::Ne: return a != b;
        case CmpOp::Gt: return a > b;
        case CmpOp::Ge: return a >= b;
        default: return false;
    }
}
bool contains(Obj container, Obj item) {
    auto equal = [&](Obj v) { return v == item || truth(compare(CmpOp::Eq, v, item).get()); };
    if (is_kind(container, Kind::DictView)) {    // dictkeys_contains, dictitems_contains; values by iteration
        auto* view = static_cast<DictView*>(container.object());
        auto* d = static_cast<Dict*>(view->dict.object());
        if (view->which == DictView::Keys) return !dict_get(d, item).is_unset();
        if (view->which == DictView::Items) {
            if (!is_kind(item, Kind::Tuple) || static_cast<Tuple*>(item.object())->items.size() != 2) return false;
            Ref pair = Ref::share(item);
            Obj found = dict_get(d, static_cast<Tuple*>(item.object())->items[0]);
            if (found.is_unset()) return false;
            Ref held = Ref::share(found);
            Obj want = static_cast<Tuple*>(item.object())->items[1];
            return held.get() == want || truth(compare(CmpOp::Eq, held.get(), want).get());
        }
        Ref it = iter(container);
        for (;;) {
            Ref v = for_next(it.get());
            if (is_end(v)) return false;
            if (equal(v.get())) return true;
        }
    }
    if (is_kind(container, Kind::Tuple)) {
        for (Obj v : static_cast<Tuple*>(container.object())->items) if (equal(v)) return true;
        return false;
    }
    if (is_kind(container, Kind::List)) {
        auto& items = static_cast<List*>(container.object())->items;
        for (std::size_t i = 0; i < items.size(); ++i) {
            Obj v = items[i];
            incref(v);
            bool eq = equal(v);
            decref(v);
            if (eq) return true;
        }
        return false;
    }
    if (is_kind(container, Kind::Dict)) return !dict_get(static_cast<Dict*>(container.object()), item).is_unset();
    if (is_kind(container, Kind::Set)) return set_contains(static_cast<SetObject*>(container.object()), item);
    if (const Str* s = as_str(container)) {
        const Str* sub = as_str(item);
        if (sub == nullptr)
            raise_new("TypeError", "'in <string>' requires string as left operand, not " + type_of(item)->name);
        return s->text.find(sub->text) != std::string::npos;
    }
    if (is_kind(container, Kind::Range)) {
        auto* r = static_cast<Range*>(container.object());
        std::int64_t x;
        if (!as_int(item, x)) throw NotImplemented("`in` on a range with a value that is not an int");
        if (r->step > 0 ? (x < r->start || x >= r->stop) : (x > r->start || x <= r->stop)) return false;
        return (x - r->start) % r->step == 0;
    }
    if (is_kind(container, Kind::Instance)) {
        bool has = false;
        Ref r = call_special(container, "__contains__", {item}, &has);
        if (has) return truth(r.get());
        Ref it = iter(container);                // _PySequence_IterSearch
        for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
            if (equal(v.get())) return true;
        return false;
    }
    raise_new("TypeError", "argument of type '" + type_of(container)->name + "' is not a container or iterable");
}
// list_richcompare and tuplerichcompare (Objects/listobject.c, tupleobject.c): a list's lengths
// first for == and !=; the first position whose items differ, the items held while user code
// runs and the current lengths read again at every step, since __eq__ may change a list; then
// the lengths, or the ordering of those items, whose result object is returned as it is
// (review 2026-11-03, A9-1, A9-13).
Ref sequence_compare(CmpOp op, Obj v, Obj w, bool lists) {
    auto items = [&](Obj x) -> const std::vector<Obj>& {
        return lists ? static_cast<List*>(x.object())->items : static_cast<Tuple*>(x.object())->items;
    };
    if (lists && items(v).size() != items(w).size() && (op == CmpOp::Eq || op == CmpOp::Ne))
        return Ref::steal(boolean(op == CmpOp::Ne));
    std::size_t i = 0;
    for (; i < items(v).size() && i < items(w).size(); ++i) {
        Ref vi = Ref::share(items(v)[i]), wi = Ref::share(items(w)[i]);
        if (vi.get() == wi.get()) continue;
        Ref eq = compare(CmpOp::Eq, vi.get(), wi.get());
        if (!truth(eq.get())) break;
    }
    std::size_t vn = items(v).size(), wn = items(w).size();
    if (i >= vn || i >= wn) return Ref::steal(boolean(ordered(op, vn, wn)));
    if (op == CmpOp::Eq) return Ref::steal(boolean(false));
    if (op == CmpOp::Ne) return Ref::steal(boolean(true));
    Ref vi = Ref::share(items(v)[i]), wi = Ref::share(items(w)[i]);
    return compare(op, vi.get(), wi.get());
}
}  // namespace

// The C++ types' own comparisons: NotImplemented when the operands are not theirs.
Ref native_compare(CmpOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return Ref::steal(boolean(ordered(op, x, y)));
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (sa != nullptr && sb != nullptr)                // code point order: UTF-8 byte order is code point order
        return Ref::steal(boolean(ordered(op, std::string_view(sa->text), std::string_view(sb->text))));
    if (is_kind(a, Kind::Tuple) && is_kind(b, Kind::Tuple)) return sequence_compare(op, a, b, false);
    if (is_kind(a, Kind::List) && is_kind(b, Kind::List)) return sequence_compare(op, a, b, true);
    if ((op == CmpOp::Eq || op == CmpOp::Ne) && a == b && !is_heap_obj(a)) return Ref::steal(boolean(op == CmpOp::Eq));
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}

namespace {
const char* cmp_name(CmpOp op) {
    switch (op) {
        case CmpOp::Lt: return "__lt__";
        case CmpOp::Le: return "__le__";
        case CmpOp::Eq: return "__eq__";
        case CmpOp::Ne: return "__ne__";
        case CmpOp::Gt: return "__gt__";
        default: return "__ge__";
    }
}
CmpOp swapped(CmpOp op) {
    switch (op) {
        case CmpOp::Lt: return CmpOp::Gt;
        case CmpOp::Le: return CmpOp::Ge;
        case CmpOp::Gt: return CmpOp::Lt;
        case CmpOp::Ge: return CmpOp::Le;
        default: return op;
    }
}
Ref compare_side(Obj self, Obj other, CmpOp op) {
    if (is_heap_obj(self)) return call_special(self, cmp_name(op), {other});
    return native_compare(op, self, other);
}
}  // namespace

// do_richcompare: a subclass's reflected method first, then the left operand's, then the
// reflected; == and != fall back to identity, the orderings fail
Ref compare(CmpOp op, Obj a, Obj b) {
    switch (op) {
        case CmpOp::Is: return Ref::steal(boolean(a == b));
        case CmpOp::IsNot: return Ref::steal(boolean(a != b));
        case CmpOp::In: return Ref::steal(boolean(contains(b, a)));
        case CmpOp::NotIn: return Ref::steal(boolean(!contains(b, a)));
        default: break;
    }
    if (set_like_view(a) || set_like_view(b)) throw NotImplemented("comparing dict keys and items views (as sets)");
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return Ref::steal(boolean(ordered(op, x, y)));
    ClassObject *ta = type_of(a), *tb = type_of(b);
    bool checked_reverse = false;
    if (ta != tb && is_heap_obj(b) && is_subclass(tb, ta)) {
        checked_reverse = true;
        Ref r = compare_side(b, a, swapped(op));
        if (!not_implemented(r)) return r;
    }
    Ref r = compare_side(a, b, op);
    if (!not_implemented(r)) return r;
    if (!checked_reverse) {
        r = compare_side(b, a, swapped(op));
        if (!not_implemented(r)) return r;
    }
    if (op == CmpOp::Eq) return Ref::steal(boolean(a == b));
    if (op == CmpOp::Ne) return Ref::steal(boolean(a != b));
    raise_new("TypeError", std::string("'") + symbol(op) + "' not supported between instances of '" + type_of(a)->name +
                               "' and '" + type_of(b)->name + "'");
}

bool truth(Obj v) {
    if (v.is_small()) return v.small_value() != 0;
    Object* o = v.object();
    switch (o->kind) {
        case Kind::Bool: return static_cast<BoolObject*>(o)->value;
        case Kind::Singleton:
            if (o == NOTIMPLEMENTED)                 // TypeError since 3.14 (A9-21)
                raise_new("TypeError", "NotImplemented should not be used in a boolean context");
            return o != NONE;
        case Kind::Str: return static_cast<Str*>(o)->length != 0;
        case Kind::Tuple: return !static_cast<Tuple*>(o)->items.empty();
        case Kind::List: return !static_cast<List*>(o)->items.empty();
        case Kind::Dict: return static_cast<Dict*>(o)->used != 0;
        case Kind::DictView: return static_cast<Dict*>(static_cast<DictView*>(o)->dict.object())->used != 0;
        case Kind::Range: return static_cast<Range*>(o)->length != 0;
        case Kind::Set: return static_cast<SetObject*>(o)->used != 0;
        case Kind::Instance: {
            // __bool__ (a bool, nothing else), else __len__, else true
            bool has = false;
            Ref r = call_special(v, "__bool__", {}, &has);
            if (has) {
                if (!is_kind(r.get(), Kind::Bool))
                    raise_new("TypeError", "__bool__ should return bool, returned " + type_of(r.get())->name);
                return static_cast<BoolObject*>(r.get().object())->value;
            }
            r = call_special(v, "__len__", {}, &has);
            if (has) return length_value(r.get()) != 0;      // as len() takes it (A9-14)
            return true;
        }
        default: return true;
    }
}

// operator.index (PyNumber_Index): an int, a bool, or an object with __index__ returning one
std::int64_t index_value(Obj v) {
    std::int64_t x;
    if (as_int(v, x)) return x;
    if (is_kind(v, Kind::Instance)) {
        bool has = false;
        Ref r = call_special(v, "__index__", {}, &has);
        if (has) {
            if (as_int(r.get(), x) && !is_kind(r.get(), Kind::Bool)) return x;
            raise_new("TypeError", "__index__ returned non-int (type " + type_of(r.get())->name + ")");
        }
    }
    raise_new("TypeError", "'" + type_of(v)->name + "' object cannot be interpreted as an integer");
}

// slot_sq_length: a __len__ result converted as an index, never negative
std::int64_t length_value(Obj v) {
    std::int64_t n = index_value(v);
    if (n < 0) raise_new("ValueError", "__len__() should return >= 0");
    return n;
}

// ---- str() and repr() ----
namespace {
std::string int_text(std::int64_t v) {
    char buf[32];
    auto [end, ec] = std::to_chars(buf, buf + sizeof buf, v);
    return std::string(buf, end);
}
std::string hex(char32_t c, int digits) {
    static const char* d = "0123456789abcdef";
    std::string out;
    for (int i = digits - 1; i >= 0; --i) out += d[(c >> (4 * i)) & 0xF];
    return out;
}
std::string address(Obj v) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%p", static_cast<void*>(v.object()));
    return buf;
}
std::string str_repr(const Str* s) {
    // unicode_repr: single quotes unless the text has ' and no "
    bool has_single = false, has_double = false;
    for (std::size_t i = 0; i < s->length; ++i) {
        char32_t c = s->at(i);
        has_single |= c == '\'';
        has_double |= c == '"';
    }
    char quote = has_single && !has_double ? '"' : '\'';
    std::string out(1, quote);
    for (std::size_t i = 0; i < s->length; ++i) {
        char32_t c = s->at(i);
        if (c == static_cast<char32_t>(quote) || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c == '\t') out += "\\t";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c < 0x20 || c == 0x7f) out += "\\x" + hex(c, 2);
        else if (c < 0x7f) out += static_cast<char>(c);
        else if (c <= 0xA0 || c == 0xAD) out += "\\x" + hex(c, 2);      // Latin-1's non-printable code points
        else if (c < 0x100) Str::append_utf8(out, c);
        else throw NotImplemented("repr() of text beyond Latin-1 needs the Unicode database (unicodedata, D-8)");
    }
    out += quote;
    return out;
}
}  // namespace

Ref repr_of(Obj v) {
    if (v.is_small()) return str_new(int_text(v.small_value()));
    Object* o = v.object();
    switch (o->kind) {
        case Kind::Bool: return str_new(static_cast<BoolObject*>(o)->value ? "True" : "False");
        case Kind::Singleton: return str_new(static_cast<Singleton*>(o)->repr);
        case Kind::Str: return str_new(str_repr(static_cast<Str*>(o)));
        case Kind::Class: {
            auto* c = static_cast<ClassObject*>(o);
            Obj mod = Obj{};
            if (const Obj* m = c->attrs.find(intern("__module__"))) mod = *m;
            const Str* ms = as_str(mod);
            std::string prefix = ms == nullptr || ms->text == "builtins" ? "" : ms->text + ".";
            return str_new("<class '" + prefix + c->qualname + "'>");
        }
        case Kind::Range: {
            auto* r = static_cast<Range*>(o);
            return str_new("range(" + int_text(r->start) + ", " + int_text(r->stop) +
                           (r->step == 1 ? "" : ", " + int_text(r->step)) + ")");
        }
        case Kind::Builtin: {
            auto* b = static_cast<Builtin*>(o);
            std::string_view kind = b->owner != nullptr ? cpython_attribute_kind(b->owner, b->name) : std::string_view{};
            if (kind == "wrapper_descriptor")            // a slot wrapper or method-wrapper in CPython
                throw NotImplemented("the repr of " + b->owner->name + "." + b->name + ", a slot wrapper in CPython");
            if (b->self.is_unset() && b->binding != Binding::Function)
                return str_new("<method '" + b->name + "' of '" + (b->owner ? b->owner->name : "object") + "' objects>");
            if (b->self.is_unset() && kind == "builtin_function_or_method")      // object.__new__, bound to its type
                return str_new("<built-in method " + b->name + " of type object at " + address(Obj::of(b->owner)) + ">");
            if (!b->self.is_unset() && !is_kind(b->self, Kind::Module))
                return str_new("<built-in method " + b->name + " of " + type_of(b->self)->name + " object at " + address(b->self) + ">");
            return str_new("<built-in function " + b->name + ">");
        }
        case Kind::PyFunction:
            if (presents_as_builtin(v))
                return str_new("<built-in function " + as_str(static_cast<PyFunction*>(o)->name.get())->text + ">");
            return str_new("<function " + as_str(static_cast<PyFunction*>(o)->qualname.get())->text + " at " + address(v) + ">");
        case Kind::Method: {
            auto* m = static_cast<Method*>(o);
            Ref fname = getattr(m->func, intern("__qualname__"));
            Ref self = repr_of(m->self);
            return str_new("<bound method " + as_str(fname.get())->text + " of " + as_str(self.get())->text + ">");
        }
        case Kind::Instance: {
            Ref r = call_special(v, "__repr__", {});
            if (as_str(r.get()) == nullptr)
                raise_new("TypeError", "__repr__ returned non-string (type " + type_of(r.get())->name + ")");
            return r;
        }
        default: break;
    }
    // the containers' repr is the prelude's (installed as their __repr__), as are the rest
    bool has = false;
    Ref r = call_special(v, "__repr__", {}, &has);
    if (has) return r;
    throw NotImplemented("repr() of '" + type_of(v)->name + "' objects");
}

Ref str_of(Obj v) {
    if (as_str(v) != nullptr) return Ref::share(v);
    if (is_kind(v, Kind::Instance)) {
        Ref r = call_special(v, "__str__", {});
        if (as_str(r.get()) == nullptr)
            raise_new("TypeError", "__str__ returned non-string (type " + type_of(r.get())->name + ")");
        return r;
    }
    return repr_of(v);
}

// ---- attributes ----
namespace {
bool overrides(Obj obj, const char* name) {
    return type_lookup(type_of(obj), intern(name)) != type_lookup(types().object, intern(name));
}
}  // namespace

Ref getattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Instance)) {
        try {
            return bella::getattr(static_cast<Instance*>(obj.object()), name);
        } catch (const bella::AttributeError&) {
            raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        } catch (const bella::TypeError& e) {
            raise_new("TypeError", e.what());
        }
    }
    if (is_kind(obj, Kind::Class)) return type_getattr(static_cast<ClassObject*>(obj.object()), name);
    return generic_getattr(obj, name);
}

void setattr(Obj obj, const Str* name, Obj value) {
    if (is_kind(obj, Kind::Instance)) {
        if (overrides(obj, "__setattr__")) {
            call_special(obj, "__setattr__", {Obj::of(name), value});
            return;
        }
        try {
            bella::setattr(static_cast<Instance*>(obj.object()), name, value);
        } catch (const bella::AttributeError& e) {
            raise_attribute_error(obj, name, std::string(e.what()).find(' ') == std::string::npos
                                                 ? "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'"
                                                 : std::string(e.what()));
        }
        return;
    }
    if (is_kind(obj, Kind::Class)) {
        type_setattr(static_cast<ClassObject*>(obj.object()), name, value);
        return;
    }
    if (is_kind(obj, Kind::Module)) {
        dict_set(static_cast<Module*>(obj.object())->dict, Obj::of(name), value);
        return;
    }
    Obj found = type_lookup(type_of(obj), name);
    if (is_kind(found, Kind::GetSet)) {
        auto* g = static_cast<GetSet*>(found.object());
        if (g->set == nullptr)
            raise_attribute_error(obj, name, "attribute '" + name->text + "' of '" + type_of(obj)->name + "' objects is not writable");
        g->set(obj, value);
        return;
    }
    if (is_kind(obj, Kind::PyFunction) && !presents_as_builtin(obj)) {
        Ref d = generic_getattr(obj, intern("__dict__"));
        dict_set(static_cast<Dict*>(d.get().object()), Obj::of(name), value);
        return;
    }
    raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text +
                                         "' and no __dict__ for setting new attributes");
}

void delattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Instance)) {
        if (overrides(obj, "__delattr__")) {
            call_special(obj, "__delattr__", {Obj::of(name)});
            return;
        }
        try {
            bella::delattr(static_cast<Instance*>(obj.object()), name);
        } catch (const bella::AttributeError&) {
            raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        }
        return;
    }
    if (is_kind(obj, Kind::Class)) {
        type_delattr(static_cast<ClassObject*>(obj.object()), name);
        return;
    }
    if (is_kind(obj, Kind::Module)) {
        if (!dict_del(static_cast<Module*>(obj.object())->dict, Obj::of(name)))
            raise_attribute_error(obj, name, "module has no attribute '" + name->text + "'");
        return;
    }
    throw NotImplemented("del of an attribute of a '" + type_of(obj)->name + "' object");
}

// ---- items ----
namespace {
std::size_t index_of(Obj key, std::size_t size, const char* what) {
    std::int64_t i;
    if (is_kind(key, Kind::Instance)) i = index_value(key);       // __index__
    else if (!as_int(key, i))
        raise_new("TypeError", std::string(what) + " indices must be integers or slices, not " + type_of(key)->name);
    if (i < 0) i += static_cast<std::int64_t>(size);
    if (i < 0 || i >= static_cast<std::int64_t>(size)) raise_new("IndexError", std::string(what) + " index out of range");
    return static_cast<std::size_t>(i);
}
}  // namespace

namespace {
// PySlice_GetIndicesEx over small ints: (start, stop, step, length)
std::array<std::int64_t, 4> slice_indices(Obj sl, std::int64_t length) {
    auto* s = static_cast<SliceObject*>(sl.object());
    auto value = [](Obj v, std::int64_t dflt) {
        if (v == None()) return dflt;
        std::int64_t x;
        if (!as_int(v, x)) raise_new("TypeError", "slice indices must be integers or None or have an __index__ method");
        return x;
    };
    std::int64_t step = value(s->step, 1);
    if (step == 0) raise_new("ValueError", "slice step cannot be zero");
    std::int64_t lower = step < 0 ? -1 : 0, upper = step < 0 ? length - 1 : length;
    auto clamp = [&](Obj v, std::int64_t dflt) {
        if (v == None()) return dflt;
        std::int64_t x = value(v, 0);
        if (x < 0) { x += length; if (x < lower) x = lower; }
        else if (x > upper) x = upper;
        return x;
    };
    std::int64_t start = clamp(s->start, step < 0 ? upper : lower), stop = clamp(s->stop, step < 0 ? lower : upper);
    std::int64_t n = 0;
    if (step < 0 ? stop < start : start < stop) n = step < 0 ? (start - stop - 1) / -step + 1 : (stop - start - 1) / step + 1;
    return {start, stop, step, n};
}
template <class F>
void each_index(Obj sl, std::int64_t length, F f) {
    auto [start, stop, step, n] = slice_indices(sl, length);
    for (std::int64_t i = 0, k = start; i < n; ++i, k += step) f(static_cast<std::size_t>(k));
}
}  // namespace

Ref getitem(Obj obj, Obj key) {
    bool slice = is_kind(key, Kind::Slice);
    if (is_kind(obj, Kind::Tuple)) {
        auto& items = static_cast<Tuple*>(obj.object())->items;
        if (!slice) return Ref::share(items[index_of(key, items.size(), "tuple")]);
        std::vector<Obj> out;
        each_index(key, static_cast<std::int64_t>(items.size()), [&](std::size_t i) { incref(items[i]); out.push_back(items[i]); });
        return tuple_steal(std::move(out));
    }
    if (is_kind(obj, Kind::List)) {
        auto& items = static_cast<List*>(obj.object())->items;
        if (!slice) return Ref::share(items[index_of(key, items.size(), "list")]);
        auto* l = new List;
        Ref r = own(l);
        each_index(key, static_cast<std::int64_t>(items.size()), [&](std::size_t i) { incref(items[i]); l->items.push_back(items[i]); });
        return r;
    }
    if (const Str* s = as_str(obj)) {
        if (!slice) {
            std::size_t i = index_of(key, s->length, "string");
            return str_from_codepoints(std::u32string(1, s->at(i)));
        }
        std::u32string out;
        each_index(key, static_cast<std::int64_t>(s->length), [&](std::size_t i) { out += s->at(i); });
        return str_from_codepoints(out);
    }
    if (is_kind(obj, Kind::Dict)) {
        Obj v = dict_get(static_cast<Dict*>(obj.object()), key);
        if (v.is_unset()) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
            raise(exc.get());
        }
        return Ref::share(v);
    }
    bool has = false;
    Ref r = call_special(obj, "__getitem__", {key}, &has);
    if (has) return r;
    if (is_kind(obj, Kind::Class)) throw NotImplemented("subscripting a class (__class_getitem__)");
    raise_new("TypeError", "'" + type_of(obj)->name + "' object is not subscriptable");
}

void setitem(Obj obj, Obj key, Obj value) {
    if (is_kind(obj, Kind::List)) {
        if (is_kind(key, Kind::Slice)) throw NotImplemented("slice assignment to a list");
        auto& items = static_cast<List*>(obj.object())->items;
        std::size_t i = index_of(key, items.size(), "list assignment");
        incref(value);
        Obj old = std::exchange(items[i], value);
        decref(old);
        return;
    }
    if (is_kind(obj, Kind::Dict)) {
        dict_set(static_cast<Dict*>(obj.object()), key, value);
        return;
    }
    bool has = false;
    call_special(obj, "__setitem__", {key, value}, &has);
    if (has) return;
    raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support item assignment");
}

void delitem(Obj obj, Obj key) {
    if (is_kind(obj, Kind::Dict)) {
        if (!dict_del(static_cast<Dict*>(obj.object()), key)) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
            raise(exc.get());
        }
        return;
    }
    if (is_kind(obj, Kind::List)) {
        auto& items = static_cast<List*>(obj.object())->items;
        std::size_t i = index_of(key, items.size(), "list assignment");
        Obj old = items[i];
        items.erase(items.begin() + static_cast<std::ptrdiff_t>(i));
        decref(old);
        return;
    }
    bool has = false;
    call_special(obj, "__delitem__", {key}, &has);
    if (has) return;
    raise_new("TypeError", "'" + type_of(obj)->name + "' object doesn't support item deletion");
}

// ---- iteration ----
Ref iter(Obj obj) {
    if (is_kind(obj, Kind::Range)) return own(new Iterator(Iterator::RangeIt, obj));
    if (is_kind(obj, Kind::Tuple)) return own(new Iterator(Iterator::TupleIt, obj));
    if (is_kind(obj, Kind::List)) return own(new Iterator(Iterator::ListIt, obj));
    if (as_str(obj) != nullptr) return own(new Iterator(Iterator::StrIt, obj));
    if (is_kind(obj, Kind::Set)) {
        auto* it = new Iterator(Iterator::SetIt, obj);
        Ref r = own(it);
        it->size = static_cast<std::int64_t>(static_cast<SetObject*>(obj.object())->used);
        return r;
    }
    if (is_kind(obj, Kind::Dict) || is_kind(obj, Kind::DictView)) {
        Obj d = obj;
        Iterator::Of of = Iterator::DictKeysIt;
        if (is_kind(obj, Kind::DictView)) {
            auto* view = static_cast<DictView*>(obj.object());
            d = view->dict;
            of = view->which == DictView::Keys ? Iterator::DictKeysIt : view->which == DictView::Values ? Iterator::DictValuesIt
                                                                                                          : Iterator::DictItemsIt;
        }
        auto* it = new Iterator(of, d);
        Ref r = own(it);
        it->size = static_cast<std::int64_t>(static_cast<Dict*>(d.object())->used);
        return r;
    }
    if (is_kind(obj, Kind::Iterator)) return Ref::share(obj);
    bool has = false;
    Ref r = call_special(obj, "__iter__", {}, &has);
    if (has) {
        if (type_lookup(type_of(r.get()), intern("__next__")).is_unset() && !is_kind(r.get(), Kind::Iterator))
            raise_new("TypeError", "iter() returned non-iterator of type '" + type_of(r.get())->name + "'");
        return r;
    }
    if (!type_lookup(type_of(obj), intern("__getitem__")).is_unset()) return own(new Iterator(Iterator::SeqIt, obj));
    raise_new("TypeError", "'" + type_of(obj)->name + "' object is not iterable");
}

Ref for_next(Obj itv) {
    if (!is_kind(itv, Kind::Iterator)) {
        // __next__; StopIteration ends the loop and is consumed here, as FOR_ITER consumes it
        bool has = false;
        try {
            Ref v = call_special(itv, "__next__", {}, &has);
            if (has) return v;
        } catch (const PyError& e) {
            if (isinstance(e.exc.get(), exception_class("StopIteration"))) return Ref{};
            throw;
        }
        raise_new("TypeError", "'" + type_of(itv)->name + "' object is not an iterator");
    }
    auto* it = static_cast<Iterator*>(itv.object());
    if (it->seq.is_unset()) return Ref{};
    auto finish = [&]() { decref(std::exchange(it->seq, Obj{})); return Ref{}; };
    switch (it->of) {
        case Iterator::RangeIt: {
            auto* r = static_cast<Range*>(it->seq.object());
            if (it->pos >= r->length) return finish();
            return Ref::steal(Obj::small(r->start + r->step * it->pos++));
        }
        case Iterator::TupleIt: {
            auto& items = static_cast<Tuple*>(it->seq.object())->items;
            if (static_cast<std::size_t>(it->pos) >= items.size()) return finish();
            return Ref::share(items[static_cast<std::size_t>(it->pos++)]);
        }
        case Iterator::ListIt: {
            auto& items = static_cast<List*>(it->seq.object())->items;
            if (static_cast<std::size_t>(it->pos) >= items.size()) return finish();
            return Ref::share(items[static_cast<std::size_t>(it->pos++)]);
        }
        case Iterator::StrIt: {
            auto* s = static_cast<Str*>(it->seq.object());
            if (static_cast<std::size_t>(it->pos) >= s->length) return finish();
            return str_from_codepoints(std::u32string(1, s->at(static_cast<std::size_t>(it->pos++))));
        }
        case Iterator::SetIt: {                  // table order; a change of size fails, and keeps failing (A9-12)
            auto* st = static_cast<SetObject*>(it->seq.object());
            if (it->size == -2 || static_cast<std::int64_t>(st->used) != it->size) {
                it->size = -2;
                raise_new("RuntimeError", "Set changed size during iteration");
            }
            while (static_cast<std::size_t>(it->pos) < st->table.size() && st->table[static_cast<std::size_t>(it->pos)].key.is_unset())
                ++it->pos;
            if (static_cast<std::size_t>(it->pos) >= st->table.size()) return finish();
            return Ref::share(st->table[static_cast<std::size_t>(it->pos++)].key);
        }
        case Iterator::SeqIt: {                  // the old protocol: __getitem__(0), (1)... until IndexError
            Ref index = Ref::steal(Obj::small(it->pos));
            try {
                Ref v = getitem(it->seq, index.get());
                ++it->pos;
                return v;
            } catch (const PyError& e) {
                if (isinstance(e.exc.get(), exception_class("IndexError")) ||
                    isinstance(e.exc.get(), exception_class("StopIteration")))
                    return finish();
                throw;
            }
        }
        case Iterator::DictKeysIt:
        case Iterator::DictValuesIt:
        case Iterator::DictItemsIt: {
            auto* d = static_cast<Dict*>(it->seq.object());
            if (it->size == -2 || static_cast<std::int64_t>(d->used) != it->size) {
                it->size = -2;
                raise_new("RuntimeError", "dictionary changed size during iteration");
            }
            while (static_cast<std::size_t>(it->pos) < d->entries.size() &&
                   d->entries[static_cast<std::size_t>(it->pos)].key.is_unset()) ++it->pos;
            if (static_cast<std::size_t>(it->pos) >= d->entries.size()) return finish();
            auto& e = d->entries[static_cast<std::size_t>(it->pos++)];
            if (it->of == Iterator::DictKeysIt) return Ref::share(e.key);
            if (it->of == Iterator::DictValuesIt) return Ref::share(e.value);
            return tuple_new({e.key, e.value});
        }
    }
    return Ref{};
}

void unpack(Obj value, std::span<Ref> targets, int star) {
    std::vector<Ref> items;
    if (is_kind(value, Kind::Tuple) || is_kind(value, Kind::List)) {
        auto& src = is_kind(value, Kind::Tuple) ? static_cast<Tuple*>(value.object())->items
                                                : static_cast<List*>(value.object())->items;
        for (Obj v : src) items.push_back(Ref::share(v));
    } else {
        // unpack_iterable: without a star, as many items as targets and one more to tell "too many"
        Ref it = iter(value);
        std::size_t limit = star < 0 ? targets.size() + 1 : SIZE_MAX;
        while (items.size() < limit) {
            Ref v = for_next(it.get());
            if (is_end(v)) break;
            items.push_back(std::move(v));
        }
    }
    std::size_t n = targets.size();
    if (star < 0) {
        if (items.size() < n)
            raise_new("ValueError", "not enough values to unpack (expected " + std::to_string(n) + ", got " +
                                        std::to_string(items.size()) + ")");
        if (items.size() > n) raise_new("ValueError", "too many values to unpack (expected " + std::to_string(n) + ")");
        for (std::size_t i = 0; i < n; ++i) targets[i] = std::move(items[i]);
        return;
    }
    std::size_t before = static_cast<std::size_t>(star), after = n - before - 1;
    if (items.size() < before + after)
        raise_new("ValueError", "not enough values to unpack (expected at least " + std::to_string(before + after) +
                                    ", got " + std::to_string(items.size()) + ")");
    for (std::size_t i = 0; i < before; ++i) targets[i] = std::move(items[i]);
    auto* middle = new List;
    targets[before] = own(middle);
    for (std::size_t i = before; i < items.size() - after; ++i) middle->items.push_back(items[i].release());
    for (std::size_t i = 0; i < after; ++i) targets[before + 1 + i] = std::move(items[items.size() - after + i]);
}

// ---- displays ----
Ref build_list(std::initializer_list<Obj> items) { return list_new(items); }
Ref build_tuple(std::initializer_list<Obj> items) { return tuple_new(items); }
Ref build_map(std::initializer_list<Obj> keys, std::initializer_list<Obj> values) {
    Ref d = dict_new();
    auto k = keys.begin();
    for (Obj v : values) dict_set(static_cast<Dict*>(d.get().object()), *k++, v);
    return d;
}
namespace {
// the (key, value) pairs of a mapping: a dict's entries, else keys() and __getitem__
template <class F>
void each_item(Obj mapping, F f) {
    if (is_kind(mapping, Kind::Dict)) {
        auto* d = static_cast<Dict*>(mapping.object());
        std::vector<std::pair<Ref, Ref>> items;
        for (auto& e : d->entries) if (!e.key.is_unset()) items.emplace_back(Ref::share(e.key), Ref::share(e.value));
        for (auto& [k, v] : items) f(k.get(), v.get());
        return;
    }
    Ref keys = invoke(getattr(mapping, intern("keys")).get(), {});
    Ref it = iter(keys.get());
    for (Ref k = for_next(it.get()); !is_end(k); k = for_next(it.get())) {
        Ref v = getitem(mapping, k.get());
        f(k.get(), v.get());
    }
}
std::string callable_name(Obj func) {
    if (is_kind(func, Kind::PyFunction)) return as_str(static_cast<PyFunction*>(func.object())->qualname.get())->text + "()";
    if (is_kind(func, Kind::Builtin)) return static_cast<Builtin*>(func.object())->name + "()";
    if (is_kind(func, Kind::Class)) return static_cast<ClassObject*>(func.object())->name + "()";
    return type_of(func)->name + " object";
}
}  // namespace

void dict_update(Obj target, Obj mapping) {
    auto* d = static_cast<Dict*>(target.object());
    if (is_kind(mapping, Kind::Dict)) {           // dict_merge's fast path: the stored hashes (A9-15)
        std::vector<std::tuple<Ref, std::int64_t, Ref>> items;
        for (auto& e : static_cast<Dict*>(mapping.object())->entries)
            if (!e.key.is_unset()) items.emplace_back(Ref::share(e.key), e.hash, Ref::share(e.value));
        for (auto& [k, h, v] : items) dict_set_hashed(d, k.get(), h, v.get());
        return;
    }
    if (type_lookup(type_of(mapping), intern("keys")).is_unset())
        raise_new("TypeError", "'" + type_of(mapping)->name + "' object is not a mapping");
    each_item(mapping, [&](Obj k, Obj v) { dict_set(d, k, v); });
}

void dict_merge(Obj target, Obj mapping, Obj func) {
    if (!is_kind(mapping, Kind::Dict) && type_lookup(type_of(mapping), intern("keys")).is_unset())
        raise_new("TypeError", callable_name(func) + " argument after ** must be a mapping, not " + type_of(mapping)->name);
    auto* d = static_cast<Dict*>(target.object());
    each_item(mapping, [&](Obj k, Obj v) {
        const Str* name = as_str(k);
        if (name == nullptr) raise_new("TypeError", "keywords must be strings");
        if (!dict_get(d, k).is_unset())
            raise_new("TypeError", callable_name(func) + " got multiple values for keyword argument '" + name->text + "'");
        dict_set(d, k, v);
    });
}

void list_append(Obj list, Obj value) {
    incref(value);
    static_cast<List*>(list.object())->items.push_back(value);
}
void list_extend(Obj list, Obj value) {
    Ref it = iter(value);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        static_cast<List*>(list.object())->items.push_back(v.release());
}
Ref list_to_tuple(Obj list) {
    std::vector<Obj> items;
    for (Obj v : static_cast<List*>(list.object())->items) {
        incref(v);
        items.push_back(v);
    }
    return tuple_steal(std::move(items));
}
Ref make_cell(Obj value) {
    auto* c = new Cell;
    incref(value);
    c->value = value;
    return own(c);
}

}  // namespace bella
