// runtime/src/ops.cpp -- operators, truth, str() and repr(), attributes, items, iteration and
// unpacking on the C++ types (bella/runtime.hpp). User classes' special methods come with step 3a.2.
#include "bella/runtime.hpp"

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <tuple>

namespace bella {

// an int's value (PyLong_Check): an immediate, a bool, or an int subclass's instance
bool as_int(Obj v, std::int64_t& out) {
    if (v.is_small()) {
        out = v.small_value();
        return true;
    }
    if (is_kind(v, Kind::Bool)) {
        out = static_cast<BoolObject*>(v.object())->value ? 1 : 0;
        return true;
    }
    if (is_kind(v, Kind::IntInstance)) {
        out = static_cast<IntInstance*>(v.object())->value;
        return true;
    }
    return false;
}
namespace {
// an int whose type is the runtime's (an immediate or a bool): what may skip the dispatch
bool as_exact_int(Obj v, std::int64_t& out) { return !is_kind(v, Kind::IntInstance) && as_int(v, out); }

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
// The C++ types' number slots (nb_add, nb_or, ...): NotImplemented for operands they do not know.
// Concatenation and repetition are sequence slots, tried after both operands' number slots
// declined (sequence_op below), as PyNumber_Add and PyNumber_Multiply do.
Ref native_binary(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    if (is_kind(a, Kind::Set) && is_kind(b, Kind::Set)) return set_binary(op, a, b);
    if (op == BinOp::Or && is_kind(a, Kind::Dict) && is_kind(b, Kind::Dict)) {   // dict_or: a copy, updated
        Ref out = dict_copy(static_cast<Dict*>(a.object()));
        dict_update_arg(out.get(), b);
        return out;
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
// an object whose type is a class of the program's: an instance, or a class whose metaclass is one
bool is_heap_obj(Obj v) { return (v.is_object() && v.object()->kind == Kind::Instance) || has_python_type(v); }
// a subclass instance of a built-in whose class overrides this special method (decision 2026-11-03)
bool overridden(Obj v, const char* name) { return is_subclass_instance(v) && overrides_builtin(v, name); }
bool not_implemented(const Ref& r) { return r.get() == Obj::of(NOTIMPLEMENTED); }

// one operand's method: a class's dunder (absent: *has false), or the C++ type's operation
Ref operand_method(Obj self, Obj other, BinOp op, bool reflected, bool& has) {
    if (is_heap_obj(self) || overridden(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0])) {
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

namespace {
bool repeatable(Obj v) { return as_str(v) != nullptr || is_kind(v, Kind::List) || is_kind(v, Kind::Tuple); }
bool has_sequence_methods(Obj v) {               // a type with tp_as_sequence (every class has one)
    return repeatable(v) || is_heap_obj(v) || is_kind(v, Kind::Dict) || is_kind(v, Kind::Set) || is_kind(v, Kind::Range) ||
           is_kind(v, Kind::DictView);
}
// sequence_repeat: the count through __index__; then str's, tuple's or list's repeat
Ref repeat(Obj seq, Obj n, bool in_place) {
    std::int64_t exact;
    if (!as_int(n, exact) && (!is_heap_obj(n) || type_lookup(type_of(n), intern("__index__")).is_unset()))
        raise_new("TypeError", "can't multiply sequence by non-int of type '" + type_of(n)->name + "'");
    std::int64_t count = index_value(n);
    if (const Str* s = as_str(seq)) {
        if (count <= 0) return str_new("");
        if (count == 1) return Ref::share(seq);
        if (s->text.size() * static_cast<std::size_t>(count) > (std::size_t{1} << 32)) throw NotImplemented("a str of more than 2**32 bytes");
        std::string out;
        out.reserve(s->text.size() * static_cast<std::size_t>(count));
        for (std::int64_t i = 0; i < count; ++i) out += s->text;
        return str_new(out);
    }
    if (is_kind(seq, Kind::Tuple)) {                // tuple_repeat: the same tuple when empty or once
        auto& items = static_cast<Tuple*>(seq.object())->items;
        if (items.empty() || count == 1) return Ref::share(seq);
        if (count <= 0) return tuple_steal({});
        if (items.size() * static_cast<std::size_t>(count) > (std::size_t{1} << 28)) throw NotImplemented("a tuple of more than 2**28 items");
        std::vector<Obj> out;
        for (std::int64_t i = 0; i < count; ++i) for (Obj v : items) { incref(v); out.push_back(v); }
        return tuple_steal(std::move(out));
    }
    auto& items = static_cast<List*>(seq.object())->items;
    if (count > 0 && items.size() * static_cast<std::size_t>(count) > (std::size_t{1} << 28))
        throw NotImplemented("a list of more than 2**28 items");
    if (in_place) {                                  // list_inplace_repeat
        if (count < 1) {
            std::vector<Obj> old = std::move(items);
            items.clear();
            for (auto it = old.rbegin(); it != old.rend(); ++it) decref(*it);
        } else if (count > 1) {
            std::vector<Obj> once = items;
            for (std::int64_t i = 1; i < count; ++i) for (Obj v : once) { incref(v); items.push_back(v); }
        }
        return Ref::share(seq);
    }
    auto* l = new List;
    Ref r = own(l);
    for (std::int64_t i = 0; i < count; ++i) for (Obj v : items) { incref(v); l->items.push_back(v); }
    return r;
}
// PyNumber_Add's and PyNumber_Multiply's sequence step, once both number slots declined: the left
// operand's concatenation (+= extends a list), or repetition by either operand
Ref sequence_op(BinOp op, Obj a, Obj b, bool in_place) {
    if (op == BinOp::Add) {
        if (is_kind(a, Kind::List)) {
            if (in_place) {
                list_extend(a, b);
                return Ref::share(a);
            }
            if (!is_kind(b, Kind::List))
                raise_new("TypeError", "can only concatenate list (not \"" + type_of(b)->name + "\") to list");
            auto* l = new List;
            Ref r = own(l);
            for (Obj v : static_cast<List*>(a.object())->items) { incref(v); l->items.push_back(v); }
            for (Obj v : static_cast<List*>(b.object())->items) { incref(v); l->items.push_back(v); }
            return r;
        }
        if (is_kind(a, Kind::Tuple)) {
            if (!is_kind(b, Kind::Tuple))
                raise_new("TypeError", "can only concatenate tuple (not \"" + type_of(b)->name + "\") to tuple");
            std::vector<Obj> items;
            for (Obj v : static_cast<Tuple*>(a.object())->items) { incref(v); items.push_back(v); }
            for (Obj v : static_cast<Tuple*>(b.object())->items) { incref(v); items.push_back(v); }
            return tuple_steal(std::move(items));
        }
        if (const Str* sa = as_str(a)) {
            const Str* sb = as_str(b);
            if (sb == nullptr) raise_new("TypeError", "can only concatenate str (not \"" + type_of(b)->name + "\") to str");
            return concat_str(sa, sb);
        }
    }
    if (op == BinOp::Mul) {
        if (repeatable(a)) return repeat(a, b, in_place && is_kind(a, Kind::List));
        if ((!in_place || !has_sequence_methods(a)) && repeatable(b)) return repeat(b, a, false);
    }
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}
bool set_like_operator(BinOp op) { return op == BinOp::And || op == BinOp::Or || op == BinOp::Sub || op == BinOp::Xor; }
}  // namespace

// binary_op1: the operands' number slots, NotImplemented when both decline
Ref binary_op1(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (as_exact_int(a, x) && as_exact_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    if (!is_heap_obj(a) && !is_heap_obj(b) && !is_subclass_instance(a) && !is_subclass_instance(b)) return native_binary(op, a, b);
    ClassObject *ta = type_of(a), *tb = type_of(b);
    const char* rname = BIN_NAMES[static_cast<int>(op)][1];
    bool tried_reflected = false, has = false;
    if (ta != tb && (is_heap_obj(b) || is_subclass_instance(b)) && is_subclass(tb, ta)) {   // a subclass's reflected method first
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
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}

Ref binary(BinOp op, Obj a, Obj b) {
    if ((set_like_view(a) || set_like_view(b)) && set_like_operator(op))
        throw NotImplemented("set operations on dict keys and items views");
    Ref r = binary_op1(op, a, b);
    if (!not_implemented(r)) return r;
    r = sequence_op(op, a, b, false);
    if (!not_implemented(r)) return r;
    refuse_unimplemented_operator("binop", a, symbol(op), b);
    unsupported(symbol(op), a, b);
}

// PyNumber_InPlace*: the left operand's in-place method, then binary_op1, then the sequence step
Ref inplace(BinOp op, Obj a, Obj b) {
    if (set_like_view(a) && set_like_operator(op)) throw NotImplemented("set operations on dict keys and items views");
    if (is_heap_obj(a) || overridden(a, BIN_NAMES[static_cast<int>(op)][2])) {
        bool has = false;
        Ref r = call_special(a, BIN_NAMES[static_cast<int>(op)][2], {b}, &has);
        if (has && !not_implemented(r)) return r;
    }
    if (is_kind(a, Kind::Set) && set_like_operator(op)) {
        Ref r = set_inplace(op, a, b);
        if (!not_implemented(r)) return r;
    }
    if (op == BinOp::Or && is_kind(a, Kind::Dict)) {   // dict_ior: any mapping or pairs
        dict_update_arg(a, b);
        return Ref::share(a);
    }
    Ref r = binary_op1(op, a, b);
    if (!not_implemented(r)) return r;
    r = sequence_op(op, a, b, true);
    if (!not_implemented(r)) return r;
    std::string sym = std::string(symbol(op)) + "=";
    refuse_unimplemented_operator("iop", a, sym, b);
    unsupported(sym.c_str(), a, b);
}

namespace {
Ref unary_special(Obj a, const char* dunder, const char* sym) {
    bool has = false;
    if (is_heap_obj(a) || is_subclass_instance(a)) {
        Ref r = call_special(a, dunder, {}, &has);
        if (has) return r;
    }
    raise_new("TypeError", std::string("bad operand type for unary ") + sym + ": '" + type_of(a)->name + "'");
}
}  // namespace

Ref unary_neg(Obj a) {
    std::int64_t x;
    if (as_int(a, x) && !overridden(a, "__neg__")) return small(int_neg(Int::from_small(x)).small());
    return unary_special(a, "__neg__", "-");
}
Ref unary_pos(Obj a) {
    std::int64_t x;
    if (as_int(a, x) && !overridden(a, "__pos__")) return small(x);
    return unary_special(a, "__pos__", "+");
}
Ref unary_invert(Obj a) {
    std::int64_t x;
    if (is_kind(a, Kind::Bool)) throw NotImplemented("~ on a bool (a DeprecationWarning in CPython 3.15)");
    if (as_int(a, x) && !overridden(a, "__invert__")) return small(~x);
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
        for (std::size_t i = 0; i < items.size(); ++i) {   // list_contains: each item held, also when == raises
            Ref item = Ref::share(items[i]);
            if (equal(item.get())) return true;
        }
        return false;
    }
    if (is_kind(container, Kind::Dict) && !overridden(container, "__contains__"))
        return !dict_get(static_cast<Dict*>(container.object()), item).is_unset();
    if (is_kind(container, Kind::Dict)) return truth(call_special(container, "__contains__", {item}).get());
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
    // PySequence_Contains: the type's __contains__ (slot_sq_contains: None says it is no container,
    // G9 2.8), else _PySequence_IterSearch, whose iter()'s TypeError is reworded; an iterator or a
    // mappingproxy goes this way as an instance does (RL-299)
    if (type_lookup(type_of(container), intern("__contains__")) == None())
        raise_new("TypeError", "'" + type_of(container)->name + "' object is not a container");
    bool has = false;
    Ref r = call_special(container, "__contains__", {item}, &has);
    if (has) return truth(r.get());
    Ref it;
    try {
        it = iter(container);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "argument of type '" + type_of(container)->name + "' is not a container or iterable");
    }
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (equal(v.get())) return true;
    return false;
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
    if (is_kind(a, Kind::Dict) && is_kind(b, Kind::Dict)) {   // dict_richcompare: == and != only
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        return Ref::steal(boolean(dict_equal(static_cast<Dict*>(a.object()), static_cast<Dict*>(b.object())) == (op == CmpOp::Eq)));
    }
    if (is_kind(a, Kind::Set) && is_kind(b, Kind::Set)) return set_compare(op, a, b);
    if (is_kind(a, Kind::Range) && is_kind(b, Kind::Range)) {   // range_richcompare: == and != only
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        auto *r0 = static_cast<Range*>(a.object()), *r1 = static_cast<Range*>(b.object());
        bool eq = r0 == r1 || (r0->length == r1->length &&
                               (r0->length == 0 || (r0->start == r1->start && (r0->length == 1 || r0->step == r1->step))));
        return Ref::steal(boolean(eq == (op == CmpOp::Eq)));
    }
    if (is_kind(a, Kind::Slice) && is_kind(b, Kind::Slice)) {   // slice_richcompare: as (start, stop, step)
        auto *s0 = static_cast<SliceObject*>(a.object()), *s1 = static_cast<SliceObject*>(b.object());
        Ref t0 = tuple_new({s0->start, s0->stop, s0->step}), t1 = tuple_new({s1->start, s1->stop, s1->step});
        return sequence_compare(op, t0.get(), t1.get(), false);
    }
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
    if (is_heap_obj(self) || overridden(self, cmp_name(op)) ||
        (is_kind(self, Kind::Proxy) && (op == CmpOp::Eq || op == CmpOp::Ne)))
        return call_special(self, cmp_name(op), {other});
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
    if (as_exact_int(a, x) && as_exact_int(b, y)) return Ref::steal(boolean(ordered(op, x, y)));
    ClassObject *ta = type_of(a), *tb = type_of(b);
    bool checked_reverse = false;
    if (ta != tb && (is_heap_obj(b) || is_subclass_instance(b)) && is_subclass(tb, ta)) {
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
    refuse_unimplemented_operator("cmp", a, symbol(op), b);
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
        case Kind::DictView: return static_cast<Dict*>(static_cast<DictView*>(o)->dict.object())->used != 0;
        case Kind::Range: return static_cast<Range*>(o)->length != 0;
        case Kind::Set: return static_cast<SetObject*>(o)->used != 0;
        case Kind::IntInstance:
            if (!overridden(v, "__bool__")) return static_cast<IntInstance*>(o)->value != 0;
            return truth(call_special(v, "__bool__", {}).get());
        case Kind::Dict:                             // a dict subclass's instance asks its class
            if (!is_subclass_instance(v)) return static_cast<Dict*>(o)->used != 0;
            [[fallthrough]];
        case Kind::Class:                            // a class whose metaclass is a Python class
            if (o->kind == Kind::Class && !has_python_type(v)) return true;
            [[fallthrough]];
        case Kind::Instance: {
            // __bool__ (a bool, nothing else), else __len__, else true
            bool has = false;
            if (type_lookup(type_of(v), intern("__bool__")) == None())    // slot_nb_bool (RL-306)
                raise_new("TypeError", "'" + type_of(v)->name + "' cannot be interpreted as a boolean");
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
    if (is_heap_obj(v)) {
        bool has = false;
        Ref r = call_special(v, "__index__", {}, &has);
        if (has) {                                   // _PyNumber_Index
            if (r.get().is_small()) return r.get().small_value();
            if (as_int(r.get(), x)) throw NotImplemented("__index__ returning a strict subclass of int (a DeprecationWarning in CPython)");
            raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__index__() must return an int, not " +
                                       fully_qualified_name(type_of(r.get())));
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

// dict_equal: the same size, and each of a's entries found in b with an equal value; a's entries
// read again at every step, each key and value held while user code runs
bool dict_equal(Dict* a, Dict* b) {
    if (a->used != b->used) return false;
    for (std::size_t i = 0; i < a->entries.size(); ++i) {
        auto& e = a->entries[i];
        if (e.key.is_unset()) continue;
        Ref aval = Ref::share(e.value), key = Ref::share(e.key);
        Obj found = dict_find(b, key.get(), e.hash);
        if (found.is_unset()) return false;
        Ref bval = Ref::share(found);
        key = Ref{};
        if (!(aval.get() == bval.get() || truth(compare(CmpOp::Eq, aval.get(), bval.get()).get()))) return false;
    }
    return true;
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

// type_repr: type's own formatter, which a metaclass's __repr__ reaches through super()
Ref type_repr_of(Obj v) {
    auto* c = static_cast<ClassObject*>(v.object());
    Obj mod = Obj{};
    if (const Obj* m = c->attrs.find(intern("__module__"))) mod = *m;
    const Str* ms = as_str(mod);
    std::string prefix = ms == nullptr || ms->text == "builtins" ? "" : ms->text + ".";
    return str_new("<class '" + prefix + c->qualname + "'>");
}

Ref repr_of(Obj v) {
    if (v.is_small()) return str_new(int_text(v.small_value()));
    Object* o = v.object();
    switch (o->kind) {
        case Kind::Bool: return str_new(static_cast<BoolObject*>(o)->value ? "True" : "False");
        case Kind::Singleton: return str_new(static_cast<Singleton*>(o)->repr);
        case Kind::Str: return str_new(str_repr(static_cast<Str*>(o)));
        case Kind::Class: {
            if (has_python_type(v) && type_lookup(type_of(v), intern("__repr__")) != type_lookup(types().type, intern("__repr__"))) {
                Ref r = call_special(v, "__repr__", {});       // the metaclass's __repr__
                if (as_str(r.get()) == nullptr)
                    raise_new("TypeError", "__repr__ returned non-string (type " + type_of(r.get())->name + ")");
                return r;
            }
            return type_repr_of(v);
        }
        case Kind::IntInstance:
            if (!overridden(v, "__repr__")) return str_new(int_text(static_cast<IntInstance*>(o)->value));
            break;
        case Kind::Range: {
            auto* r = static_cast<Range*>(o);
            return str_new("range(" + int_text(r->start) + ", " + int_text(r->stop) +
                           (r->step == 1 ? "" : ", " + int_text(r->step)) + ")");
        }
        case Kind::Slice: {                          // slice_repr
            auto* s = static_cast<SliceObject*>(o);
            Ref a = repr_of(s->start), b = repr_of(s->stop), c = repr_of(s->step);
            return str_new("slice(" + as_str(a.get())->text + ", " + as_str(b.get())->text + ", " + as_str(c.get())->text + ")");
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
    if (is_kind(v, Kind::Instance) || is_kind(v, Kind::Proxy) ||
        ((has_python_type(v) || is_subclass_instance(v)) &&
         type_lookup(type_of(v), intern("__str__")) != type_lookup(types().object, intern("__str__")))) {
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

// the built-in a subclass instance is an object of (its kind's class)
ClassObject* builtin_of(Obj v) {
    switch (v.object()->kind) {
        case Kind::Dict: return types().dict;
        case Kind::IntInstance: return types().int_;
        default: return types().object;
    }
}
// The MRO decides: a class before the built-in base overrides it; the built-in's own slot wins over
// whatever comes after it, whether the runtime has the method yet or not (RL-313), and a name the
// built-in does not define in CPython goes on to the classes after it.
bool overrides_builtin(Obj v, const char* name) {
    const Str* n = intern(name);
    ClassObject* builtin = builtin_of(v);
    for (ClassObject* c : type_of(v)->mro) {
        if (c == builtin) {
            if (c->attrs.contains(n) || cpython_has(c->name, name)) return false;
            continue;
        }
        if (c == types().object) return false;
        if (c->attrs.contains(n)) return true;
    }
    return false;
}

namespace {
Ref getattr_impl(Obj obj, const Str* name);
}  // namespace

// PyObject_GetAttr: an AttributeError that leaves the lookup without a name and an object gets
// both (set_attribute_error_context), as the suggestions in CPython's report read them
Ref getattr(Obj obj, const Str* name) {
    try {
        return getattr_impl(obj, name);
    } catch (const PyError& e) {
        Obj exc = e.exc.get();
        if (isinstance(exc, exception_class("AttributeError")) && exception_field(exc, "name").is_unset() &&
            exception_field(exc, "obj").is_unset()) {
            set_exception_field(exc, "name", Obj::of(name));
            set_exception_field(exc, "obj", obj);
        }
        rethrow(e);
    }
}

namespace {
Ref getattr_impl(Obj obj, const Str* name) {
    Ref out;
    if (with_attribute_storage(obj, [&](auto* inst) {
            try {
                out = bella::getattr(inst, name);
            } catch (const bella::AttributeError&) {
                raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
            } catch (const bella::TypeError& e) {
                raise_new("TypeError", e.what());
            }
        }))
        return out;
    if (is_kind(obj, Kind::Class)) return type_getattr(static_cast<ClassObject*>(obj.object()), name);
    if (is_kind(obj, Kind::Super)) return super_getattr(obj, name);
    if (is_kind(obj, Kind::Module)) return module_getattr(obj, name);
    if (is_kind(obj, Kind::LazyImport)) return lazy_getattr(obj, name);
    return generic_getattr(obj, name);
}
}  // namespace

// PyObject_GetOptionalAttr: a module answers without raising (_Py_module_getattro_impl with
// suppress, which treats a pending lazy submodule and a resolving placeholder differently);
// anything else raises, and an AttributeError means absent
Ref optional_getattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Module)) return module_getattr(obj, name, true);
    try {
        return getattr(obj, name);
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
        return Ref{};
    }
}

namespace {
// _PyObject_GenericSetAttrWithDict on an object with no dict: a name its type has, as a getset the
// runtime lacks or as anything else
void read_only_attribute(Obj obj, const Str* name, Obj found) {
    std::string_view kind;
    for (const ClassObject* c : type_of(obj)->mro)
        if (kind.empty()) kind = cpython_attribute_kind(c, name->text);
    if (kind == "getset_descriptor" || kind == "member_descriptor")
        raise_attribute_error(obj, name, "attribute '" + name->text + "' of '" + type_of(obj)->name + "' objects is not writable");
    if (!found.is_unset() || !kind.empty())
        raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object attribute '" + name->text + "' is read-only");
}
}  // namespace

void setattr(Obj obj, const Str* name, Obj value) {
    if (is_kind(obj, Kind::Instance) || is_subclass_instance(obj)) {
        if (overrides(obj, "__setattr__")) {
            call_special(obj, "__setattr__", {Obj::of(name), value});
            return;
        }
        if (type_lookup(type_of(obj), name).is_unset()) refuse_absent_data_descriptor(obj, name);
        with_attribute_storage(obj, [&](auto* inst) {
            try {
                bella::setattr(inst, name, value);
            } catch (const bella::AttributeError& e) {
                raise_attribute_error(obj, name, std::string(e.what()).find(' ') == std::string::npos
                                                     ? "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'"
                                                     : std::string(e.what()));
            }
        });
        return;
    }
    if (is_kind(obj, Kind::Class)) {
        type_setattr(static_cast<ClassObject*>(obj.object()), name, value);
        return;
    }
    if (is_kind(obj, Kind::Module)) {
        if (name == intern("__dict__")) raise_attribute_error(obj, name, "readonly attribute");
        if (name == intern("__class__")) {
            if (!is_kind(value, Kind::Class))
                raise_new("TypeError", "__class__ must be set to a class, not '" + type_of(value)->name + "' object");
            auto* c = static_cast<ClassObject*>(value.object());
            if (!c->heap_type || !is_subclass(c, types().module))
                raise_new("TypeError", "__class__ assignment only supported for mutable types or ModuleType subclasses");
            throw NotImplemented("[P2+] __class__ assignment (spec section 3)");
        }
        dict_set(static_cast<Module*>(obj.object())->dict, Obj::of(name), value);
        return;
    }
    Obj found = type_lookup(type_of(obj), name);
    if (name == intern("__class__")) {
        if (!is_kind(value, Kind::Class))
            raise_new("TypeError", "__class__ must be set to a class, not '" + type_of(value)->name + "' object");
        if (!type_of(obj)->heap_type) raise_new("TypeError", "__class__ assignment only supported for mutable types or ModuleType subclasses");
    }
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
    read_only_attribute(obj, name, found);
    raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text +
                                         "' and no __dict__ for setting new attributes");
}

void delattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Instance) || is_subclass_instance(obj)) {
        if (overrides(obj, "__delattr__")) {
            call_special(obj, "__delattr__", {Obj::of(name)});
            return;
        }
        if (type_lookup(type_of(obj), name).is_unset()) refuse_absent_data_descriptor(obj, name);
        with_attribute_storage(obj, [&](auto* inst) {
            try {
                bella::delattr(inst, name);
            } catch (const bella::AttributeError&) {
                raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
            }
        });
        return;
    }
    if (is_kind(obj, Kind::Class)) {
        type_delattr(static_cast<ClassObject*>(obj.object()), name);
        return;
    }
    if (is_kind(obj, Kind::Module)) {            // _PyObject_GenericSetAttrWithDict's deletion
        if (name == intern("__dict__")) raise_attribute_error(obj, name, "readonly attribute");
        if (!dict_del(static_cast<Module*>(obj.object())->dict, Obj::of(name)))
            raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        return;
    }
    // a C++ type's getset (a member): deleted through its setter when it allows that (super's
    // members say `readonly attribute`), else not writable
    if (Obj found = type_lookup(type_of(obj), name); is_kind(found, Kind::GetSet)) {
        auto* g = static_cast<GetSet*>(found.object());
        if (!g->deletable)
            raise_attribute_error(obj, name, "attribute '" + name->text + "' of '" + type_of(obj)->name + "' objects is not writable");
        g->set(obj, Obj{});
        return;
    }
    read_only_attribute(obj, name, type_lookup(type_of(obj), name));
    if (!is_kind(obj, Kind::PyFunction))
        raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text +
                                             "' and no __dict__ for setting new attributes");
    throw NotImplemented("del of an attribute of a '" + type_of(obj)->name + "' object");
}

// ---- items ----
namespace {
// `what`: the type's name in the messages; `range_what`: where the out-of-range message differs
// ("list assignment"). A key with __index__ is an index (_PyIndex_Check); str words it differently.
std::size_t index_of(Obj key, std::size_t size, const char* what, const char* range_what = nullptr) {
    std::int64_t i;
    if (!as_int(key, i)) {
        if (!is_heap_obj(key) || type_lookup(type_of(key), intern("__index__")).is_unset()) {
            if (std::string_view(what) == "string")
                raise_new("TypeError", "string indices must be integers, not '" + type_of(key)->name + "'");
            raise_new("TypeError", std::string(what) + " indices must be integers or slices, not " + type_of(key)->name);
        }
        i = index_value(key);
    }
    if (i < 0) i += static_cast<std::int64_t>(size);
    if (i < 0 || i >= static_cast<std::int64_t>(size))
        raise_new("IndexError", std::string(range_what != nullptr ? range_what : what) + " index out of range");
    return static_cast<std::size_t>(i);
}
}  // namespace

namespace {
// PySlice_GetIndicesEx over small ints: (start, stop, step, length)
std::array<std::int64_t, 4> slice_indices(Obj sl, std::int64_t length) {
    auto* s = static_cast<SliceObject*>(sl.object());
    auto value = [](Obj v, std::int64_t dflt) {       // _PyEval_SliceIndex
        if (v == None()) return dflt;
        std::int64_t x;
        if (as_int(v, x)) return x;
        if (!is_heap_obj(v) || type_lookup(type_of(v), intern("__index__")).is_unset())
            raise_new("TypeError", "slice indices must be integers or None or have an __index__ method");
        return index_value(v);
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

// dict_subscript: the value under key; a missing key is a subclass's __missing__, else KeyError
Ref dict_subscript(Obj self, Obj key) {
    Obj v = dict_get(static_cast<Dict*>(self.object()), key);
    if (!v.is_unset()) return Ref::share(v);
    if (is_subclass_instance(self))                  // !PyDict_CheckExact: _PyObject_LookupSpecial(__missing__)
        if (Obj missing = type_lookup(type_of(self), intern("__missing__")); !missing.is_unset()) {
            Ref m = Ref::share(missing);
            Ref bound = descr_get(m.get(), self, Obj::of(type_of(self)));
            return invoke(bound.get(), {key});
        }
    Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
    raise(exc.get());
}

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
    if (is_kind(obj, Kind::Range)) {                 // range_subscript, over small ints
        auto* r = static_cast<Range*>(obj.object());
        if (slice) {
            auto [start, stop, step, n] = slice_indices(key, r->length);
            return own(new Range(r->start + start * r->step, r->start + stop * r->step, r->step * step));
        }
        std::size_t i = index_of(key, static_cast<std::size_t>(r->length), "range", "range object");
        return Ref::steal(Obj::small(r->start + static_cast<std::int64_t>(i) * r->step));
    }
    if (is_kind(obj, Kind::Dict) && !overridden(obj, "__getitem__")) return dict_subscript(obj, key);
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
        std::size_t i = index_of(key, items.size(), "list", "list assignment");
        incref(value);
        Obj old = std::exchange(items[i], value);
        decref(old);
        return;
    }
    if (is_kind(obj, Kind::Dict) && !overridden(obj, "__setitem__")) {
        dict_set(static_cast<Dict*>(obj.object()), key, value);
        return;
    }
    bool has = false;
    call_special(obj, "__setitem__", {key, value}, &has);
    if (has) return;
    raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support item assignment");
}

void delitem(Obj obj, Obj key) {
    if (is_kind(obj, Kind::Dict) && !overridden(obj, "__delitem__")) {
        if (!dict_del(static_cast<Dict*>(obj.object()), key)) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
            raise(exc.get());
        }
        return;
    }
    if (is_kind(obj, Kind::List)) {
        auto& items = static_cast<List*>(obj.object())->items;
        if (is_kind(key, Kind::Slice)) {             // list_ass_subscript with no value
            auto [start, stop, step, n] = slice_indices(key, static_cast<std::int64_t>(items.size()));
            if (n == 0) return;
            if (step < 0) {                          // the same items, ascending
                start = start + step * (n - 1);
                step = -step;
            }
            std::vector<Obj> garbage;
            std::vector<Obj> kept;
            kept.reserve(items.size() - static_cast<std::size_t>(n));
            for (std::int64_t i = 0, next = start, left = n; i < static_cast<std::int64_t>(items.size()); ++i) {
                if (left > 0 && i == next) {
                    garbage.push_back(items[static_cast<std::size_t>(i)]);
                    next += step;
                    --left;
                } else {
                    kept.push_back(items[static_cast<std::size_t>(i)]);
                }
            }
            items = std::move(kept);
            // list_ass_slice releases a contiguous run last to first; the extended loop first to last
            if (step == 1) for (auto it = garbage.rbegin(); it != garbage.rend(); ++it) decref(*it);
            else for (Obj v : garbage) decref(v);
            return;
        }
        std::size_t i = index_of(key, items.size(), "list", "list assignment");
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
Ref dict_iter(Obj self) {
    auto* it = new Iterator(Iterator::DictKeysIt, self);
    Ref r = own(it);
    it->size = it->len = static_cast<std::int64_t>(static_cast<Dict*>(self.object())->used);
    return r;
}
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
    if ((is_kind(obj, Kind::Dict) && !overridden(obj, "__iter__")) || is_kind(obj, Kind::DictView)) {
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
        it->size = it->len = static_cast<std::int64_t>(static_cast<Dict*>(d.object())->used);
        return r;
    }
    if (is_kind(obj, Kind::Iterator)) return Ref::share(obj);
    // slot_tp_iter: __iter__ = None makes it not iterable, __getitem__ or not (G9 2.8)
    if (type_lookup(type_of(obj), intern("__iter__")) == None())
        raise_new("TypeError", "'" + type_of(obj)->name + "' object is not iterable");
    bool has = false;
    Ref r = call_special(obj, "__iter__", {}, &has);
    if (has) {
        if (type_lookup(type_of(r.get()), intern("__next__")).is_unset() && !is_kind(r.get(), Kind::Iterator))
            raise_new("TypeError", fully_qualified_name(type_of(obj)) + ".__iter__() must return an iterator, not " +
                                       fully_qualified_name(type_of(r.get())));
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
            // an entry the iterator did not expect: a key was deleted and another added, the size
            // the same; the iterator is exhausted as it fails (dictiter_iternextkey, A10-10)
            if (it->len == 0) {
                finish();
                raise_new("RuntimeError", "dictionary keys changed during iteration");
            }
            --it->len;
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
    if (is_kind(mapping, Kind::Dict) && !overridden(mapping, "__iter__")) {
        auto* d = static_cast<Dict*>(mapping.object());
        std::vector<std::pair<Ref, Ref>> items;
        for (auto& e : d->entries) if (!e.key.is_unset()) items.emplace_back(Ref::share(e.key), Ref::share(e.value));
        for (auto& [k, v] : items) f(k.get(), v.get());
        return;
    }
    // PyMapping_Keys: keys() made a list first, then each key's __getitem__
    Ref keys = invoke(getattr(mapping, intern("keys")).get(), {});
    std::vector<Ref> listed;
    Ref it;
    try {                                            // method_output_as_list
        it = iter(keys.get());
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", fully_qualified_name(type_of(mapping)) + ".keys() must return an iterable, not " +
                                   fully_qualified_name(type_of(keys.get())));
    }
    for (Ref k = for_next(it.get()); !is_end(k); k = for_next(it.get())) listed.push_back(std::move(k));
    for (Ref& k : listed) {
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

// dict.copy() (copy_lock_held): an empty dict's copy is new; a split dict's shares its keys; a
// combined one at most a third deleted is cloned, table and all; any other is merged into a new
// dict, which compacts it. Only the merge compares keys.
Ref dict_copy(Dict* d) {
    Ref out = dict_new();
    auto* to = static_cast<Dict*>(out.get().object());
    if (overridden(Obj::of(d), "__iter__")) {      // a subclass's own iteration: merged through keys()
        each_item(Obj::of(d), [&](Obj k, Obj v) { dict_set(to, k, v); });
        return out;
    }
    if (d->used == 0) return out;
    if (d->split || d->used >= d->entries.size() * 2 / 3) {
        dict_clone_into(to, d);
        return out;
    }
    dict_merge_dict(to, d);
    return out;
}

// dict_dict_merge with override (DICT_UPDATE, dict.update): into an empty dict, a clean other
// (no deleted entries, at the smallest size or more than half its usable entries in use) is
// cloned; otherwise one resize first, then each entry inserted with its stored hash, in order. An
// insert that changes other's size fails, as CPython says.
void dict_merge_dict(Dict* mp, Dict* other) {
    if (other == mp || other->used == 0) return;
    if (mp->used == 0 && !mp->split && !other->split && other->used == other->entries.size() &&
        (other->indices.size() == 8 || (other->indices.size() / 2) * 2 / 3 < other->used)) {
        dict_clone_into(mp, other);                  // mp holds no entry: nothing to release
        return;
    }
    if (dict_usable(mp) < other->used) dict_resize_estimate(mp, mp->used + other->used);
    std::size_t orig = other->used;
    for (std::size_t pos = 0; pos < other->entries.size(); ++pos) {   // _PyDict_Next over the live table
        const auto& e = other->entries[pos];
        if (e.key.is_unset()) continue;
        std::int64_t hash = e.hash;
        Ref k = Ref::share(e.key), v = Ref::share(e.value);
        dict_set_hashed(mp, k.get(), hash, v.get());
        if (orig != other->used) raise_new("RuntimeError", "dict mutated during update");
    }
}

void dict_update(Obj target, Obj mapping) {
    auto* d = static_cast<Dict*>(target.object());
    if (is_kind(mapping, Kind::Dict) && !overridden(mapping, "__iter__")) {   // dict_merge's fast path (A9-15)
        dict_merge_dict(d, static_cast<Dict*>(mapping.object()));
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
// PyObject_LengthHint, for the generic extend (list(x), tuple(x)): __len__ (a TypeError from it
// set aside), else __length_hint__ (a TypeError or NotImplemented: no hint); only an object of a
// Python class can tell it was asked, so only such objects are
void length_hint(Obj v) {
    if (!is_heap_obj(v) && !is_subclass_instance(v)) return;
    if (!type_lookup(type_of(v), intern("__len__")).is_unset()) {
        try {
            Ref r = call_special(v, "__len__", {});
            length_value(r.get());
            return;
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        }
    }
    bool has = false;
    Ref r;
    try {
        r = call_special(v, "__length_hint__", {}, &has);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        return;
    }
    if (!has || r.get() == Obj::of(NOTIMPLEMENTED)) return;
    std::int64_t n;
    if (!as_int(r.get(), n))
        raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__length_hint__() must return an int, not " +
                                   fully_qualified_name(type_of(r.get())));
    if (n < 0) raise_new("ValueError", "__length_hint__() should return >= 0");
}

// LIST_EXTEND ([*x], (*x,)): iter()'s TypeError is reworded for an object with neither __iter__ nor
// a sequence's __getitem__
void list_extend_star(Obj list, Obj value) {
    try {
        list_extend(list, value);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        if (is_kind(value, Kind::Iterator) || !type_lookup(type_of(value), intern("__iter__")).is_unset() ||
            !type_lookup(type_of(value), intern("__getitem__")).is_unset())
            throw;
        raise_new("TypeError", "Value after * must be an iterable, not " + type_of(value)->name);
    }
}

void list_extend(Obj list, Obj value) {
    if (list == value) {                          // _list_extend: a.extend(a) and a += a repeat the list (G9 2.2)
        auto& items = static_cast<List*>(list.object())->items;
        std::size_t n = items.size();
        items.reserve(2 * n);
        for (std::size_t i = 0; i < n; ++i) {
            Obj v = items[i];
            incref(v);
            items.push_back(v);
        }
        return;
    }
    Ref it = iter(value);
    length_hint(value);                           // list_extend_iter: the iterator first, then the hint
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
