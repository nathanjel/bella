// runtime/src/ops.cpp -- operators, truth, str() and repr(), attributes, items, iteration and
// unpacking on the C++ types (bella/runtime.hpp). User classes' special methods come with step 3a.2.
#include "bella/runtime.hpp"

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <tuple>

namespace bella {

// an int's value when it is an immediate's size: an immediate, a bool, or an int subclass's instance
// holding one. A big int answers false here, and is_int true: a path that takes every int asks is_int.
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
        auto* i = static_cast<IntInstance*>(v.object());
        if (!i->limbs.empty()) return false;
        out = i->value;
        return true;
    }
    return false;
}
namespace {
// an int whose type is the runtime's (an immediate or a bool): what may skip the dispatch
bool as_exact_int(Obj v, std::int64_t& out) { return !is_kind(v, Kind::IntInstance) && as_int(v, out); }

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

// int.hpp holds the immediates' semantics, differentially tested against CPython (make int-test); its
// C++ errors become the Python exceptions they stand for. A result it cannot hold, and a negative
// power, are bigint.cpp's.
Ref int_binary(BinOp op, std::int64_t a, std::int64_t b, bool both_bool) {
    Int x = Int::from_small(a), y = Int::from_small(b), r;
    bool fits = true;
    try {
        switch (op) {
            case BinOp::Add: fits = try_add(x, y, r); break;
            case BinOp::Sub: fits = try_sub(x, y, r); break;
            case BinOp::Mul: fits = try_mul(x, y, r); break;
            case BinOp::FloorDiv: fits = try_floordiv(x, y, r); break;
            case BinOp::Mod: r = int_mod(x, y); break;
            case BinOp::Pow: fits = b >= 0 && try_pow(x, y, r); break;
            case BinOp::LShift: fits = try_lshift(x, y, r); break;
            case BinOp::RShift: r = int_rshift(x, y); break;
            case BinOp::And:
                if (both_bool) return Ref::steal(boolean((a & b) != 0));
                r = int_and(x, y);
                break;
            case BinOp::Or:
                if (both_bool) return Ref::steal(boolean((a | b) != 0));
                r = int_or(x, y);
                break;
            case BinOp::Xor:
                if (both_bool) return Ref::steal(boolean((a ^ b) != 0));
                r = int_xor(x, y);
                break;
            case BinOp::TrueDiv:
                return int_true_divide(int_from_i64(a).get(), int_from_i64(b).get());
            case BinOp::MatMul:
                raise_new("TypeError", std::string("unsupported operand type(s) for ") + symbol(op) + ": 'int' and 'int'");
        }
    } catch (const bella::ZeroDivisionError& e) {
        raise_new("ZeroDivisionError", e.what());
    } catch (const bella::ValueError& e) {
        raise_new("ValueError", e.what());
    }
    if (fits) return Ref::steal(Obj::small(r.small()));
    return big_binary(op, Obj::small(a), Obj::small(b));
}

Ref concat_str(Obj a, Obj b) {                   // PyUnicode_Concat: with an empty one, PyUnicode_FromObject of the other
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (sb->text.empty()) return is_exact_str(a) ? Ref::share(a) : str_new(sa->text);
    if (sa->text.empty()) return is_exact_str(b) ? Ref::share(b) : str_new(sb->text);
    return str_new(sa->text + sb->text);
}
}  // namespace

// The C++ types' own binary operations: NotImplemented when the operands are not theirs.
// The C++ types' number slots (nb_add, nb_or, ...): NotImplemented for operands they do not know.
// Concatenation and repetition are sequence slots, tried after both operands' number slots
// declined (sequence_op below), as PyNumber_Add and PyNumber_Multiply do.
bool set_like_view(Obj v);
namespace { bool set_like_operator(BinOp op); }
Ref native_binary(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (op == BinOp::MatMul) return Ref::steal(Obj::of(NOTIMPLEMENTED));   // no built-in type has nb_matrix_multiply
    if (as_int(a, x) && as_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    if (is_int(a) && is_int(b)) return big_binary(op, a, b);
    if (op == BinOp::Mod && as_str(a) != nullptr) return str_mod(a, b);   // unicode_mod, whatever b is
    if (op == BinOp::Or && (is_kind(a, Kind::Class) || is_kind(b, Kind::Class))) return type_or(a, b);   // type_or, on either side
    if (is_complex(a) || is_complex(b)) return complex_binary(op, a, b);
    if (is_float(a) || is_float(b)) return float_binary(op, a, b);
    if (is_kind(a, Kind::Set) && is_kind(b, Kind::Set)) return set_binary(op, a, b);
    if ((set_like_view(a) || set_like_view(b)) && set_like_operator(op)) return dictview_binary(op, a, b);   // dictviews_as_number: the view's own slot, on either side
    if (op == BinOp::Or && is_kind(a, Kind::Dict) && is_kind(b, Kind::Dict)) {   // frozendict_or, _PyDict_Or: a copy, updated
        if (is_exact_frozendict(a)) {
            if (static_cast<Dict*>(a.object())->used == 0 && is_exact_frozendict(b)) return Ref::share(b);
            if (!is_subclass_instance(b) && static_cast<Dict*>(b.object())->used == 0) return Ref::share(a);
        }
        Ref out = is_frozendict(a) ? frozendict_copy(a) : dict_copy(static_cast<Dict*>(a.object()));
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
}  // namespace
const char* binop_dunder(BinOp op, bool reflected) { return BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0]; }
namespace {
// an object whose type is a class of the program's: an instance, or a class whose metaclass is one
bool is_heap_obj(Obj v) { return (v.is_object() && v.object()->kind == Kind::Instance) || has_python_type(v); }
// a subclass instance of a built-in whose class overrides this special method (decision 2026-11-03)
bool overridden(Obj v, const char* name) { return is_subclass_instance(v) && overrides_builtin(v, name); }
// what PyIndex_Check asks of an object that is not an int: nb_index, which a class that defines __index__ has, a built-in's
// subclass included
bool has_index_method(Obj v) {
    return (is_heap_obj(v) || is_subclass_instance(v)) && !type_lookup(type_of(v), intern("__index__")).is_unset();
}
bool not_implemented(const Ref& r) { return r.get() == Obj::of(NOTIMPLEMENTED); }

// a method a C type has as a sequence slot, where the C has no number slot: the first class to name it says
bool sequence_slot_of(Obj v, const char* name) {
    if (!v.is_object()) return false;
    const Str* n = intern(name);
    for (ClassObject* c : type_of(v)->mro)
        if (c->attrs.contains(n)) return c->sequence_slots;
    return false;
}

bool repeatable(Obj v);
// A built-in sequence's dunders for + and * are its sequence slots' wrappers (sq_concat, sq_repeat), which update_one_slot
// cannot take for a subclass's number slot: a subclass has nb_add (nb_multiply) only when a class of its own defines
// __add__ or __radd__ (__mul__ or __rmul__), and that slot calls the method by name, the built-in's wrapper included
bool generic_number_slot(Obj self, BinOp op) {
    return overridden(self, BIN_NAMES[static_cast<int>(op)][0]) || overridden(self, BIN_NAMES[static_cast<int>(op)][1]);
}

// one operand's method: a class's dunder (absent: *has false), or the C++ type's operation
Ref operand_method(Obj self, Obj other, BinOp op, bool reflected, bool& has) {
    if ((op == BinOp::Add || op == BinOp::Mul) && sequence_slot_of(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0])) {
        has = false;
        return Ref{};
    }
    if ((op == BinOp::Add || op == BinOp::Mul) && repeatable(self) && is_subclass_instance(self)) {
        if (!generic_number_slot(self, op)) {    // list's own: no number slot, the sequence step answers
            has = false;
            return Ref{};
        }
        return call_special(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0], {other}, &has);
    }
    if (is_heap_obj(self) || overridden(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0])) {
        Ref r = call_special(self, BIN_NAMES[static_cast<int>(op)][reflected ? 1 : 0], {other}, &has);
        return r;
    }
    has = true;
    if (is_int(self) && is_float(other)) return Ref::steal(Obj::of(NOTIMPLEMENTED));   // an int's slots know ints; the float answers from its side
    if ((is_int(self) || is_float(self)) && is_complex(other)) return Ref::steal(Obj::of(NOTIMPLEMENTED));   // and a complex from its own
    if (op == BinOp::Or && is_kind(other, Kind::Class) && !is_kind(self, Kind::Class)) return Ref::steal(Obj::of(NOTIMPLEMENTED));   // type_or is a class's slot
    return reflected ? native_binary(op, other, self) : native_binary(op, self, other);
}
}  // namespace

// binary_op1: the left operand's method, unless the right operand's type is a subclass that
// overrides the reflected method, which then goes first; the reflected method last
bool set_like_view(Obj v) { return is_kind(v, Kind::DictView) && static_cast<DictView*>(v.object())->which != DictView::Values; }

namespace {
bool repeatable(Obj v) { return as_str(v) != nullptr || is_kind(v, Kind::List) || is_kind(v, Kind::Tuple) || is_bytes_like(v); }
bool has_sequence_methods(Obj v) {               // a type with tp_as_sequence (every class has one)
    return repeatable(v) || ((is_heap_obj(v) || is_subclass_instance(v)) && type_of(v)->heap_type) || is_kind(v, Kind::Dict) || is_kind(v, Kind::Set) || is_kind(v, Kind::Range) ||
           is_kind(v, Kind::DictView);
}
// sequence_repeat: the count through __index__; then str's, tuple's or list's repeat
Ref repeat(Obj seq, Obj n, bool in_place) {
    if (!is_int(n) && !has_index_method(n))
        raise_new("TypeError", "can't multiply sequence by non-int of type '" + type_of(n)->name + "'");
    std::int64_t count = index_value(n);
    if (is_bytes_like(seq)) return bytes_repeat(seq, count, in_place);
    if (const Str* s = as_str(seq)) {
        if (count <= 0) return str_new("");
        if (count == 1) return is_exact_str(seq) ? Ref::share(seq) : str_new(s->text);   // unicode_result_unchanged
        if (s->text.size() * static_cast<std::size_t>(count) > (std::size_t{1} << 32)) throw NotImplemented("a str of more than 2**32 bytes");
        std::string out;
        out.reserve(s->text.size() * static_cast<std::size_t>(count));
        for (std::int64_t i = 0; i < count; ++i) out += s->text;
        return str_new(out);
    }
    if (is_kind(seq, Kind::Tuple)) {                // tuple_repeat: an exact tuple itself when empty or once
        auto& items = static_cast<Tuple*>(seq.object())->items;
        if ((items.empty() || count == 1) && is_exact_tuple(seq)) return Ref::share(seq);
        if (items.empty() || count <= 0) return tuple_steal({});
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
// A built-in sequence's slots, which a subclass keeps while no class of its own defines the method: update_one_slot finds a
// function where it wanted the wrapper, and these slots have no generic form (sq_repeat is both __mul__'s and __rmul__'s)
bool keeps_concat(Obj v) { return repeatable(v) && !overridden(v, "__add__"); }
bool keeps_inplace_concat(Obj v) { return (is_kind(v, Kind::List) || is_kind(v, Kind::ByteArray)) && !overridden(v, "__iadd__"); }
bool keeps_repeat(Obj v) { return repeatable(v) && !overridden(v, "__mul__") && !overridden(v, "__rmul__"); }
bool keeps_inplace_repeat(Obj v) { return (is_kind(v, Kind::List) || is_kind(v, Kind::ByteArray)) && !overridden(v, "__imul__"); }

// sq_concat and sq_inplace_concat of bytes, bytearray, list, tuple and str: what the slot does with the other operand
Ref builtin_concat(Obj a, Obj b, bool in_place) {
    if (is_bytes_like(a)) {
        if (in_place && is_kind(a, Kind::ByteArray)) {
            bytes_iadd(a, b);
            return Ref::share(a);
        }
        return bytes_concat(a, b);
    }
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
        if (static_cast<Tuple*>(a.object())->items.empty() && is_exact_tuple(b)) return Ref::share(b);
        if (!is_kind(b, Kind::Tuple))
            raise_new("TypeError", "can only concatenate tuple (not \"" + type_of(b)->name + "\") to tuple");
        if (static_cast<Tuple*>(b.object())->items.empty() && is_exact_tuple(a)) return Ref::share(a);
        std::vector<Obj> items;
        for (Obj v : static_cast<Tuple*>(a.object())->items) { incref(v); items.push_back(v); }
        for (Obj v : static_cast<Tuple*>(b.object())->items) { incref(v); items.push_back(v); }
        return tuple_steal(std::move(items));
    }
    if (as_str(a) != nullptr) {
        const Str* sb = as_str(b);
        if (sb == nullptr) raise_new("TypeError", "can only concatenate str (not \"" + type_of(b)->name + "\") to str");
        return concat_str(a, b);
    }
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}

// PyNumber_Add's and PyNumber_Multiply's sequence step, once both number slots declined: the left operand's concatenation
// (sq_inplace_concat first for +=), or repetition by the first operand that has sq_repeat (for *=, sq_inplace_repeat first,
// and the right operand only when the left has no sequence methods at all)
Ref sequence_op(BinOp op, Obj a, Obj b, bool in_place) {
    if (op == BinOp::Add && sequence_slot_of(a, in_place ? "__iadd__" : "__add__")) return call_special(a, in_place ? "__iadd__" : "__add__", {b});
    if (op == BinOp::Mul) {                          // sequence_repeat, on the first operand with a slot
        const char* name = in_place ? "__imul__" : "__mul__";
        Obj seq = sequence_slot_of(a, name) ? a : !repeatable(a) && sequence_slot_of(b, "__mul__") ? b : Obj{};
        if (!seq.is_unset()) {
            Obj n = seq == a ? b : a;
            if (type_lookup(type_of(n), intern("__index__")).is_unset())
                raise_new("TypeError", "can't multiply sequence by non-int of type '" + type_of(n)->name + "'");
            return call_special(seq, seq == a ? name : "__mul__", {n});
        }
    }
    if (op == BinOp::Add) {
        bool inplace_slot = in_place && keeps_inplace_concat(a);
        if (inplace_slot || keeps_concat(a)) return builtin_concat(a, b, inplace_slot);
    }
    if (op == BinOp::Mul) {
        bool inplace_slot = in_place && keeps_inplace_repeat(a);
        if (inplace_slot || keeps_repeat(a)) return repeat(a, b, inplace_slot);
        if ((!in_place || !has_sequence_methods(a)) && keeps_repeat(b)) return repeat(b, a, false);
    }
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}
bool set_like_operator(BinOp op) { return op == BinOp::And || op == BinOp::Or || op == BinOp::Sub || op == BinOp::Xor; }
}  // namespace

// list.__add__ and the others: sq_concat and sq_repeat (wrap_binaryfunc, wrap_indexargfunc), which
// raise for an operand they cannot take; only the `+` and `*` operators try its reflected method
Ref sequence_concat(Obj self, Obj other) { return builtin_concat(self, other, false); }
Ref sequence_repeat(Obj self, Obj count) { return repeat(self, int_from_i64(index_value(count)).get(), false); }

// PySequence_Check: a class's __getitem__ gives it sq_item; a mapping's mp_subscript does not
static bool sequence_check(Obj v) {
    if (is_kind(v, Kind::Dict) || is_kind(v, Kind::Proxy)) return false;
    if (v.is_object() && v.object()->cls->weak_proxy) return false;
    return has_sq_item(v);
}
bool is_sequence(Obj v) { return sequence_check(v); }   // PySequence_Check
Ref i_tp_name(Obj, Args a) {                      // a class's tp_name: its module's name in it, for a C type that has one
    positional_only(a, "_tp_name", 1, 1);
    return str_new(type_of(a.pos(0))->name);
}
Ref i_sequence_check(Obj, Args a) {
    positional_only(a, "_sequence_check", 1, 1);
    return Ref::steal(boolean(sequence_check(a.pos(0))));
}
// PySequence_Concat(s, o) and PySequence_InPlaceConcat: a sequence type's own, else nb_add or
// nb_inplace_add if s is a sequence (a class with only __add__), never the reflected sequence path
Ref binary_op1(BinOp op, Obj a, Obj b);
Ref i_sequence_concat(Obj, Args a) {
    positional_only(a, "_sequence_concat", 3, 3);
    Obj s = a.pos(0), o = a.pos(1);
    bool in_place = truth(a.pos(2));
    bool inplace_slot = in_place && keeps_inplace_concat(s);
    if (inplace_slot || keeps_concat(s)) return builtin_concat(s, o, inplace_slot);
    if (sequence_check(s) && sequence_check(o)) {   // both appear to be sequences: BINARY_IOP1 or BINARY_OP1 over nb_add
        if (in_place && (is_heap_obj(s) || overridden(s, "__iadd__"))) {
            bool has = false;
            Ref r = call_special(s, "__iadd__", {o}, &has);
            if (has && !not_implemented(r)) return r;
        }
        Ref r = binary_op1(BinOp::Add, s, o);
        if (!not_implemented(r)) return r;
    }
    raise_new("TypeError", "'" + type_of(s)->name + "' object can't be concatenated");
}

// binary_op1: the operands' number slots, NotImplemented when both decline
Ref binary_op1(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (op != BinOp::MatMul && as_exact_int(a, x) && as_exact_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    if (!is_heap_obj(a) && !is_heap_obj(b) && !is_subclass_instance(a) && !is_subclass_instance(b)) return native_binary(op, a, b);
    ClassObject *ta = type_of(a), *tb = type_of(b);
    const char* rname = BIN_NAMES[static_cast<int>(op)][1];
    bool tried_reflected = false, has = false;
    // a built-in sequence's subclass has a number slot for + or * only when a class of its own defines the pair (operand_method)
    bool sequence_without_slot = (op == BinOp::Add || op == BinOp::Mul) && repeatable(b) && is_subclass_instance(b) && !generic_number_slot(b, op);
    if (ta != tb && (is_heap_obj(b) || is_subclass_instance(b)) && is_subclass(tb, ta) && !sequence_without_slot) {   // a subclass's reflected method first
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
    Ref r = binary_op1(op, a, b);
    if (!not_implemented(r)) return r;
    r = sequence_op(op, a, b, false);
    if (!not_implemented(r)) return r;
    // a class's own method that declined has answered for that operand; the table speaks of the built-ins
    if (!overridden(a, BIN_NAMES[static_cast<int>(op)][0]) && !overridden(b, BIN_NAMES[static_cast<int>(op)][1]))
        refuse_unimplemented_operator("binop", a, symbol(op), b);
    unsupported(symbol(op), a, b);
}

// PyNumber_InPlace*: the left operand's in-place method, then binary_op1, then the sequence step
Ref inplace(BinOp op, Obj a, Obj b) {
    if ((is_heap_obj(a) || overridden(a, BIN_NAMES[static_cast<int>(op)][2])) &&
        !((op == BinOp::Add || op == BinOp::Mul) && sequence_slot_of(a, BIN_NAMES[static_cast<int>(op)][2]))) {
        bool has = false;
        Ref r = call_special(a, BIN_NAMES[static_cast<int>(op)][2], {b}, &has);
        if (has && !not_implemented(r)) return r;
    }
    if (is_kind(a, Kind::Set) && set_like_operator(op)) {
        Ref r = set_inplace(op, a, b);
        if (!not_implemented(r)) return r;
    }
    if (op == BinOp::Or && is_dict(a)) {               // dict_ior: any mapping or pairs
        dict_update_arg(a, b);
        return Ref::share(a);
    }
    Ref r = binary_op1(op, a, b);
    if (!not_implemented(r)) return r;
    r = sequence_op(op, a, b, true);
    if (!not_implemented(r)) return r;
    std::string sym = op == BinOp::Pow ? "**=" : std::string(symbol(op)) + "=";
    // a class's own method that declined has answered for that operand, as in binary(); the table speaks of the built-ins
    const char* const* names = BIN_NAMES[static_cast<int>(op)];
    // and a heap subclass's own sequence methods, empty, keep the right operand's repetition away (PyNumber_InPlaceMultiply
    // tries the right operand only when the left has none), where the built-in it derives from has none
    bool own_sequence_methods = op == BinOp::Mul && is_subclass_instance(a) && !repeatable(a) && keeps_repeat(b);
    if (!overridden(a, names[2]) && !overridden(a, names[0]) && !overridden(b, names[1]) && !own_sequence_methods)
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
    if (is_float(a) && !overridden(a, "__neg__")) return float_ref(-float_value(a));
    if (is_complex(a) && !overridden(a, "__neg__")) return complex_ref(-static_cast<Complex*>(a.object())->real, -static_cast<Complex*>(a.object())->imag);
    if (as_int(a, x) && !overridden(a, "__neg__")) return int_from_i64(-x);
    if (is_int(a) && !overridden(a, "__neg__")) return big_negate(a);
    return unary_special(a, "__neg__", "-");
}
Ref unary_pos(Obj a) {
    std::int64_t x;
    if (is_float(a) && !overridden(a, "__pos__")) return is_kind(a, Kind::Float) ? Ref::share(a) : float_ref(float_value(a));   // float_float
    if (is_complex(a) && !overridden(a, "__pos__"))    // complex_pos
        return is_kind(a, Kind::Complex) ? Ref::share(a) : complex_ref(static_cast<Complex*>(a.object())->real, static_cast<Complex*>(a.object())->imag);
    if (as_int(a, x) && !overridden(a, "__pos__")) return int_from_i64(x);
    if (is_int(a) && !overridden(a, "__pos__")) return big_plain(a);
    return unary_special(a, "__pos__", "+");
}
Ref unary_invert(Obj a) {
    std::int64_t x;
    if (is_kind(a, Kind::Bool)) throw NotImplemented("~ on a bool (a DeprecationWarning in CPython 3.15)");
    if (as_int(a, x) && !overridden(a, "__invert__")) return int_from_i64(~x);
    if (is_int(a) && !overridden(a, "__invert__")) return big_invert(a);
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
bool tuple_items_contain(Obj container, Obj item) {   // tuple_contains: the items, whatever a subclass says
    for (Obj v : static_cast<Tuple*>(container.object())->items)
        if (v == item || truth(compare(CmpOp::Eq, v, item).get())) return true;
    return false;
}
}  // namespace
bool str_contains(Obj self, Obj item) {
    const Str* sub = as_str(item);
    if (sub == nullptr) raise_new("TypeError", "'in <string>' requires string as left operand, not " + type_of(item)->name);
    return as_str(self)->text.find(sub->text) != std::string::npos;
}
namespace {
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
    if (is_kind(container, Kind::Tuple) && !overridden(container, "__contains__")) return tuple_items_contain(container, item);
    if (is_kind(container, Kind::List) && !overridden(container, "__contains__")) return list_contains(container, item);
    if (is_kind(container, Kind::Dict) && !overridden(container, "__contains__"))
        return !dict_get(static_cast<Dict*>(container.object()), item).is_unset();
    if (is_kind(container, Kind::Dict)) return truth(call_special(container, "__contains__", {item}).get());
    if (is_kind(container, Kind::Set)) return set_contains(static_cast<SetObject*>(container.object()), item);
    if (is_bytes_like(container)) return bytes_contains(container, item);
    if (as_str(container) != nullptr && !overridden(container, "__contains__")) return str_contains(container, item);
    if (is_kind(container, Kind::Range)) {           // range_contains: arithmetic for an exact int or a bool, else the search
        if (item.is_small() || is_kind(item, Kind::Bool) || is_kind(item, Kind::BigInt)) return range_contains_int(container, item);
        Ref it = iter(container);
        for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
            if (equal(v.get())) return true;
        return false;
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
    if (is_int(a) && is_int(b)) return Ref::steal(boolean(ordered(op, big_compare(a, b), 0)));
    if (is_float(a)) return float_compare(op, a, b);
    if (is_complex(a)) return complex_compare(op, a, b);
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
    // bytes_richcompare takes bytes alone, so a bytearray answers from its side; bytearray_richcompare takes either
    if ((is_kind(a, Kind::ByteArray) && is_bytes_like(b)) || (is_kind(a, Kind::Bytes) && is_kind(b, Kind::Bytes))) return bytes_compare(op, a, b);
    if (is_kind(a, Kind::Range) && is_kind(b, Kind::Range)) {   // range_richcompare: == and != only
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        return Ref::steal(boolean((a == b || range_equal(a, b)) == (op == CmpOp::Eq)));
    }
    if (is_kind(a, Kind::Method) && is_kind(b, Kind::Method)) {   // method_richcompare: == and != only
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        auto *m0 = static_cast<Method*>(a.object()), *m1 = static_cast<Method*>(b.object());
        Ref same = compare(CmpOp::Eq, m0->func, m1->func);
        bool eq = (m0->func == m1->func || truth(same.get())) && m0->self == m1->self;
        return Ref::steal(boolean(eq == (op == CmpOp::Eq)));
    }
    if (is_kind(a, Kind::Builtin) && is_kind(b, Kind::Builtin) &&
        (a.object()->cls == types().builtin || a.object()->cls == types().builtin_method || a.object()->cls == types().method_wrapper) &&
        (b.object()->cls == types().builtin || b.object()->cls == types().builtin_method || b.object()->cls == types().method_wrapper)) {   // meth_richcompare, wrapper_richcompare: the same function of the same object
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        auto *b0 = static_cast<Builtin*>(a.object()), *b1 = static_cast<Builtin*>(b.object());
        bool eq = b0->fn == b1->fn && b0->written.get() == b1->written.get() && b0->self == b1->self;
        if (b0->cls == types().method_wrapper || b1->cls == types().method_wrapper)   // wrapper_richcompare: the same descriptor, which one C function may serve twice
            eq = eq && b0->cls == b1->cls && b0->owner == b1->owner && b0->name == b1->name;
        return Ref::steal(boolean(eq == (op == CmpOp::Eq)));
    }
    if (is_kind(a, Kind::Slice) && is_kind(b, Kind::Slice)) {   // slice_richcompare: as (start, stop, step)
        auto *s0 = static_cast<SliceObject*>(a.object()), *s1 = static_cast<SliceObject*>(b.object());
        Ref t0 = tuple_new({s0->start, s0->stop, s0->step}), t1 = tuple_new({s1->start, s1->stop, s1->step});
        return sequence_compare(op, t0.get(), t1.get(), false);
    }
    if (is_kind(a, Kind::CodeKind) && is_kind(b, Kind::CodeKind)) {   // code_richcompare: == and != only
        if (op != CmpOp::Eq && op != CmpOp::Ne) return Ref::steal(Obj::of(NOTIMPLEMENTED));
        // a staged compile's code objects compare as the ones CPython made did (the build groups them); a function's
        // is one per code record, as is CPython's
        const StagedCompile* s0 = static_cast<CodeObject*>(a.object())->staged;
        const StagedCompile* s1 = static_cast<CodeObject*>(b.object())->staged;
        bool eq = a == b || (s0 != nullptr && s1 != nullptr && s0->group == s1->group);
        return Ref::steal(boolean(eq == (op == CmpOp::Eq)));
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

Ref compare_one_side(Obj self, Obj other, CmpOp op) { return compare_side(self, other, op); }

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
    if (set_like_view(a)) {                      // dictview_richcompare: the view's own slot (nothing subclasses a view)
        Ref r = dictview_compare(op, a, b);
        if (!not_implemented(r)) return r;
    }
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
    if (set_like_view(b)) {                      // the reflected slot of a view on the right (a set's own declined it)
        r = dictview_compare(swapped(op), b, a);
        if (!not_implemented(r)) return r;
    }
    if (!checked_reverse) {
        r = compare_side(b, a, swapped(op));
        if (!not_implemented(r)) return r;
    }
    if ((op == CmpOp::Eq || op == CmpOp::Ne) && (presents_as_builtin(a) || presents_as_builtin(b)) && a.is_object() && b.is_object() &&
        a.object()->cls == types().builtin && b.object()->cls == types().builtin)   // the prelude's print and another built-in function
        return Ref::steal(boolean((a == b) == (op == CmpOp::Eq)));
    refuse_unimplemented_operator("cmp", a, symbol(op), b);
    if (op == CmpOp::Eq) return Ref::steal(boolean(a == b));
    if (op == CmpOp::Ne) return Ref::steal(boolean(a != b));
    raise_new("TypeError", std::string("'") + symbol(op) + "' not supported between instances of '" + type_of(a)->name +
                               "' and '" + type_of(b)->name + "'");
}

// __bool__ (a bool, nothing else), else __len__, else true
static bool truth_by_methods(Obj v) {
    bool has = false;
    if (type_lookup(type_of(v), intern("__bool__")) == None())    // slot_nb_bool (RL-306)
        raise_new("TypeError", "'" + type_of(v)->name + "' cannot be interpreted as a boolean");
    Ref r = call_special(v, "__bool__", {}, &has);
    if (has) {
        if (!is_kind(r.get(), Kind::Bool))
            raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__bool__() must return a bool, not " + fully_qualified_name(type_of(r.get())));
        return static_cast<BoolObject*>(r.get().object())->value;
    }
    r = call_special(v, "__len__", {}, &has);
    if (has) return length_value(r.get()) != 0;      // as len() takes it (A9-14)
    return true;
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
        case Kind::Str:
            if (!overridden(v, "__bool__") && !overridden(v, "__len__")) return static_cast<Str*>(o)->length != 0;
            return truth_by_methods(v);
        case Kind::Tuple:
            if (!is_subclass_instance(v)) return !static_cast<Tuple*>(o)->items.empty();
            if (!overridden(v, "__bool__") && !overridden(v, "__len__")) return !static_cast<Tuple*>(o)->items.empty();
            return truth_by_methods(v);
        case Kind::List:
            if (!is_subclass_instance(v)) return !static_cast<List*>(o)->items.empty();
            if (!overridden(v, "__bool__") && !overridden(v, "__len__")) return !static_cast<List*>(o)->items.empty();
            return truth_by_methods(v);
        case Kind::Bytes:
        case Kind::ByteArray: return !bytes_data(v).empty();
        case Kind::DictView: return static_cast<Dict*>(static_cast<DictView*>(o)->dict.object())->used != 0;
        case Kind::Range: return static_cast<Range*>(o)->length != 0;
        case Kind::BigInt: return true;
        case Kind::Set: return static_cast<SetObject*>(o)->used != 0;
        case Kind::IntInstance:
            if (!overridden(v, "__bool__")) return !int_is_zero(v);
            return truth_by_methods(v);
        case Kind::Float: return static_cast<Float*>(o)->value != 0.0;
        case Kind::FloatInstance:
            if (!overridden(v, "__bool__")) return static_cast<Float*>(o)->value != 0.0;
            return truth_by_methods(v);
        case Kind::Complex: return complex_truth(v);
        case Kind::ComplexInstance:
            if (!overridden(v, "__bool__")) return complex_truth(v);
            return truth_by_methods(v);
        case Kind::Dict:                             // a dict subclass's instance asks its class
            if (!is_subclass_instance(v)) return static_cast<Dict*>(o)->used != 0;
            [[fallthrough]];
        case Kind::Class:                            // a class whose metaclass is a Python class
            if (o->kind == Kind::Class && !has_python_type(v)) return true;
            [[fallthrough]];
        case Kind::Instance:
        case Kind::Proxy: return truth_by_methods(v);
        default: return true;
    }
}

// PyNumber_Index: an int as an exact int, or what __index__ returns
Ref int_index_of(Obj v) {
    if (v.is_small() || is_kind(v, Kind::BigInt)) return Ref::share(v);
    if (is_int(v)) return big_plain(v);
    if (is_heap_obj(v) || is_subclass_instance(v)) {   // nb_index: a class's __index__, a built-in's subclass's too
        bool has = false;
        Ref r = call_special(v, "__index__", {}, &has);
        if (has) {                                   // _PyNumber_Index
            if (r.get().is_small() || is_kind(r.get(), Kind::BigInt)) return r;
            if (is_int(r.get())) throw NotImplemented("__index__ returning a strict subclass of int (a DeprecationWarning in CPython)");
            raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__index__() must return an int, not " +
                                       fully_qualified_name(type_of(r.get())));
        }
    }
    raise_new("TypeError", "'" + type_of(v)->name + "' object cannot be interpreted as an integer");
}
std::int64_t index_value(Obj v, const char* overflow) {
    std::int64_t x;
    if (as_int(v, x)) return x;
    Ref i = int_index_of(v);
    if (int_fits_i64(i.get(), x)) return x;
    raise_new(overflow, "cannot fit '" + type_of(v)->name + "' into an index-sized integer");
}
std::int64_t ssize_arg(Obj v) {
    Ref i = int_index_of(v);
    std::int64_t x;
    if (!int_fits_i64(i.get(), x)) raise_new("OverflowError", "Python int too large to convert to C ssize_t");
    return x;
}
int c_int_arg(Obj v) {
    Ref i = int_index_of(v);
    std::int64_t x;
    if (!int_fits_i64(i.get(), x) || x < INT32_MIN || x > INT32_MAX) raise_new("OverflowError", "Python int too large to convert to C int");
    return static_cast<int>(x);
}
std::int64_t clipped_index(Obj v) {
    Ref i = int_index_of(v);
    std::int64_t x;
    if (int_fits_i64(i.get(), x)) return x;
    return int_is_negative(i.get()) ? INT64_MIN : INT64_MAX;
}

// slot_sq_length: a __len__ result converted as an index, never negative
std::int64_t length_value(Obj v) {
    Ref i = int_index_of(v);
    if (int_is_negative(i.get())) raise_new("ValueError", "__len__() should return >= 0");
    return index_value(i.get());
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
        else if (unicode_is_printable(c)) Str::append_utf8(out, c);
        else if (c > 0xFFFF) out += "\\U" + hex(c, 8);
        else out += "\\u" + hex(c, 4);
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
    if (ms == nullptr && c->name_prefix > 0 && c_type(c)) prefix = c->name.substr(0, c->name_prefix);   // its tp_name's
    return str_new("<class '" + prefix + c->qualname + "'>");
}

// tp_repr, whatever it gives; what asks for a str says which method failed to give one
// descr_repr: of object's own, the name alone
static std::string descr_repr(const char* kind, const std::string& name, const ClassObject* owner) {
    if (owner == nullptr || owner == types().object) return std::string("<") + kind + " '" + name + "'>";
    return std::string("<") + kind + " '" + name + "' of '" + owner->name + "' objects>";
}
std::string str_repr_of(const Str* s) { return str_repr(s); }
Ref repr_unchecked(Obj v) {
    if (v.is_small()) return str_new(int_text(v.small_value()));
    Object* o = v.object();
    switch (o->kind) {
        case Kind::Bool: return str_new(static_cast<BoolObject*>(o)->value ? "True" : "False");
        case Kind::Singleton: return str_new(static_cast<Singleton*>(o)->repr);
        case Kind::Str:
            if (overridden(v, "__repr__")) return call_special(v, "__repr__", {});
            return str_new(str_repr(static_cast<Str*>(o)));
        case Kind::Class: {
            if (has_python_type(v) && type_lookup(type_of(v), intern("__repr__")) != type_lookup(types().type, intern("__repr__"))) {
                return call_special(v, "__repr__", {});        // the metaclass's __repr__
            }
            return type_repr_of(v);
        }
        case Kind::Bytes:
        case Kind::ByteArray: return bytes_repr(v);
        case Kind::IntInstance:
            if (!overridden(v, "__repr__")) return str_new(big_text(v));
            break;
        case Kind::BigInt: return str_new(big_text(v));
        case Kind::FloatInstance:
            if (overridden(v, "__repr__")) break;
            [[fallthrough]];
        case Kind::Float: return str_new(float_text(float_value(v)));
        case Kind::ComplexInstance:
            if (overridden(v, "__repr__")) break;
            [[fallthrough]];
        case Kind::Complex: {
            auto* c = static_cast<Complex*>(o);
            return str_new(complex_text(c->real, c->imag));
        }
        case Kind::SlotDescriptor: {             // member_repr
            auto* d = static_cast<SlotDescriptor*>(o);
            return str_new("<member '" + d->name->text + "' of '" + d->owner->name + "' objects>");
        }
        case Kind::Range: {
            auto* r = static_cast<Range*>(o);
            if (r->big) return str_new(big_range_repr(v));
            return str_new("range(" + int_text(r->start) + ", " + int_text(r->stop) +
                           (r->step == 1 ? "" : ", " + int_text(r->step)) + ")");
        }
        case Kind::GetSet: {                         // getset_repr, member_repr
            auto* g = static_cast<GetSet*>(o);
            std::string shown = std::string(o->cls == types().member_descriptor ? "<member '" : "<attribute '") + g->name + "'";
            return str_new(g->owner == types().object ? shown + ">" : shown + " of '" + g->owner->name + "' objects>");   // descr_repr
        }
        case Kind::Slice: {                          // slice_repr
            auto* s = static_cast<SliceObject*>(o);
            Ref a = repr_of(s->start), b = repr_of(s->stop), c = repr_of(s->step);
            return str_new("slice(" + as_str(a.get())->text + ", " + as_str(b.get())->text + ", " + as_str(c.get())->text + ")");
        }
        case Kind::Builtin: {
            auto* b = static_cast<Builtin*>(o);
            std::string_view kind = b->owner != nullptr ? cpython_attribute_kind(b->owner, b->name) : std::string_view{};
            if (b->cls == types().wrapper_descriptor) return str_new(descr_repr("slot wrapper", b->name, b->owner));
            if (b->cls == types().method_wrapper)        // wrapper_repr
                return str_new("<method-wrapper '" + b->name + "' of " + type_of(b->self)->name + " object at " + address(b->self) + ">");
            if (kind == "wrapper_descriptor")            // made some other way than method(): no such object yet
                throw NotImplemented("the repr of " + b->owner->name + "." + b->name + ", a slot wrapper in CPython");
            if (b->self.is_unset() && b->binding != Binding::Function)
                return str_new(descr_repr("method", b->name, b->owner));
            if (b->self.is_unset() && kind == "builtin_function_or_method")      // object.__new__, bound to its type
                return str_new("<built-in method " + b->name + " of type object at " + address(Obj::of(b->owner)) + ">");
            if (!b->self.is_unset() && !is_kind(b->self, Kind::Module))
                return str_new("<built-in method " + b->name + " of " + type_of(b->self)->name + " object at " + address(b->self) + ">");
            return str_new("<built-in function " + b->name + ">");
        }
        case Kind::CodeKind: {                   // code_repr
            const Code* c = static_cast<CodeObject*>(o)->code;
            return str_new(std::string("<code object ") + c->name + " at " + address(v) + ", file \"" + c->filename + "\", line " +
                           std::to_string(c->first_line) + ">");
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
        case Kind::Instance: return call_special(v, "__repr__", {});
        default: break;
    }
    // the containers' repr is the prelude's (installed as their __repr__), as are the rest
    bool has = false;
    Ref r = call_special(v, "__repr__", {}, &has);
    if (has) return r;
    throw NotImplemented("repr() of '" + type_of(v)->name + "' objects");
}

Ref repr_of(Obj v) {                             // PyObject_Repr
    Ref r = repr_unchecked(v);
    if (as_str(r.get()) == nullptr)
        raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__repr__() must return a str, not " + fully_qualified_name(type_of(r.get())));
    return r;
}
Ref str_of(Obj v) {                              // PyObject_Str
    if (is_exact_str(v)) return Ref::share(v);
    bool own_str = is_kind(v, Kind::Instance) || is_kind(v, Kind::Proxy) ||
                   ((has_python_type(v) || is_subclass_instance(v)) &&
                    type_lookup(type_of(v), intern("__str__")) != type_lookup(types().object, intern("__str__")));
    Ref r = own_str ? call_special(v, "__str__", {}) : repr_unchecked(v);
    if (as_str(r.get()) == nullptr)
        raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__str__() must return a str, not " + fully_qualified_name(type_of(r.get())));
    return r;
}

// ---- attributes ----
namespace {
bool overrides(Obj obj, const char* name) {
    return type_lookup(type_of(obj), intern(name)) != type_lookup(types().object, intern(name));
}
}  // namespace

// the built-in a subclass instance is an object of (its kind's class)
ClassObject* builtin_of(Obj v) {
    if (is_kind(v, Kind::Str)) return types().str;
    switch (v.object()->kind) {
        case Kind::Dict: return is_frozendict(v) ? types().frozendict : types().dict;
        case Kind::IntInstance: return types().int_;
        case Kind::FloatInstance: return types().float_;
        case Kind::ComplexInstance: return types().complex_;
        case Kind::Tuple: return types().tuple;
        case Kind::List: return types().list;
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
// ga_getattro: what types.GenericAlias keeps for itself; attr_exceptions and attr_blocked
bool alias_keeps(const Str* name) {
    static const std::vector<const Str*> kept = [] {
        std::vector<const Str*> out;
        for (const char* n : {"__class__", "__origin__", "__args__", "__unpacked__", "__parameters__", "__typing_unpacked_tuple_args__",
                              "__mro_entries__", "__reduce_ex__", "__reduce__", "__bases__", "__copy__", "__deepcopy__"})
            out.push_back(intern(n));
        return out;
    }();
    return std::find(kept.begin(), kept.end(), name) != kept.end();
}
Ref instance_member(Obj obj, const Str* name) {
    Ref out;
    with_attribute_storage(obj, [&](auto* inst) {
        try {
            out = bella::getattr(inst, name);
        } catch (const bella::AttributeError&) {
            raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        } catch (const bella::TypeError& e) {
            raise_new("TypeError", e.what());
        }
    });
    return out;
}
Ref getattr_impl(Obj obj, const Str* name) {
    if (obj.is_object() && obj.object()->cls->dict_without_getset && name == intern("__dict__"))   // local_getattro
        return instance_dict_of(obj);
    if (obj.is_object() && obj.object()->cls->weak_proxy) {   // proxy_getattr
        WeakRecord* r = weak_record(obj.object());
        if (r == nullptr || r->target == nullptr) raise_new("ReferenceError", "weakly-referenced object no longer exists");
        Ref target = Ref::share(Obj::of(r->target));
        return getattr(target.get(), name);
    }
    if (obj.is_object() && obj.object()->cls->forwards_attributes && !alias_keeps(name)) {
        Ref origin = instance_member(obj, intern("__origin__"));
        return getattr(origin.get(), name);
    }
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

// object.__getattribute__: PyObject_GenericGetAttr, so never a class's __getattr__, which the
// instances' path runs and has no way to skip yet
Ref object_getattribute(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "wrapper __getattribute__() takes no keyword arguments");
    if (a.npos != 1) raise_new("TypeError", "expected 1 argument, got " + std::to_string(a.npos));
    const Str* n = as_str(a.pos(0));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(0))->name + "'");
    if (is_kind(self, Kind::Class)) throw NotImplemented("object.__getattribute__ of a class");
    if (!type_lookup(type_of(self), intern("__getattr__")).is_unset())
        throw NotImplemented("object.__getattribute__ of an object whose class has __getattr__");
    if (is_kind(self, Kind::Instance) || is_subclass_instance(self)) return instance_member(self, intern(n->text));
    return generic_getattr(self, intern(n->text));
}
Ref i_bella_ga_get(Obj, Args a) {                // bootstrap.py's: a generic alias's own member
    positional_only(a, "_bella_ga_get", 2, 2);
    return instance_member(a.pos(0), intern(as_str(a.pos(1))->text));
}

// a getset with no setter says "not writable"; a member (PyMemberDef) "readonly attribute"
static std::string not_writable(Obj obj, const Str* name) {
    Obj found = type_lookup(type_of(obj), name);
    if (found.is_object() && found.object()->cls == types().member_descriptor) return "readonly attribute";
    std::string owner = is_kind(found, Kind::GetSet) ? static_cast<GetSet*>(found.object())->owner->name : type_of(obj)->name;
    return "attribute '" + name->text + "' of '" + owner + "' objects is not writable";
}

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
        raise_attribute_error(obj, name, not_writable(obj, name));
    if (!found.is_unset() || !kind.empty())
        raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object attribute '" + name->text + "' is read-only");
}
}  // namespace

// a delete the header refused: its own words when it has them; member_delete says the name alone
void raise_delete_failed(Obj obj, const Str* name, const std::string& what) {
    if (what.find(' ') != std::string::npos) raise_attribute_error(obj, name, what);
    if (is_kind(type_lookup(type_of(obj), name), Kind::SlotDescriptor)) raise_attribute_error(obj, name, name->text);
    raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
}

// a field of a C type written in Python, which the C type does not show: no subclass's __setattr__ runs when
// its own code stores one (a name CPython's type has, as GenericAlias's __parameters__, is a program's to set)
static bool native_slot(Obj obj, const Str* name) {
    Obj found = type_lookup(type_of(obj), name);
    if (!is_kind(found, Kind::SlotDescriptor)) return false;
    auto* owner = static_cast<SlotDescriptor*>(found.object())->owner;
    return c_type(owner) && cpython_attribute_kind(owner, name->text.c_str()).empty();
}
void setattr(Obj obj, const Str* name, Obj value) {
    if (is_kind(obj, Kind::Instance) || is_subclass_instance(obj)) {
        if (overrides(obj, "__setattr__") && !native_slot(obj, name)) {
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
            raise_attribute_error(obj, name, not_writable(obj, name));
        g->set(obj, value);
        return;
    }
    if (is_kind(obj, Kind::PyFunction) && !presents_as_builtin(obj)) {
        refuse_absent_data_descriptor(obj, name);   // a field of the C type the runtime lacks is no attribute to make (RL-255)
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
            } catch (const bella::AttributeError& e) {
                raise_delete_failed(obj, name, e.what());
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
            raise_attribute_error(obj, name, not_writable(obj, name));
        g->set(obj, Obj{});
        return;
    }
    if (is_kind(obj, Kind::PyFunction) && type_lookup(type_of(obj), name).is_unset()) refuse_absent_data_descriptor(obj, name);
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
        if (!is_int(key) && !has_index_method(key)) {
            if (std::string_view(what) == "string")
                raise_new("TypeError", "string indices must be integers, not '" + type_of(key)->name + "'");
            raise_new("TypeError", std::string(what) + " indices must be integers or slices, not " + type_of(key)->name);
        }
        i = index_value(key, "IndexError");
    }
    if (i < 0) i += static_cast<std::int64_t>(size);
    if (i < 0 || i >= static_cast<std::int64_t>(size))
        raise_new("IndexError", std::string(range_what != nullptr ? range_what : what) + " index out of range");
    return static_cast<std::size_t>(i);
}
}  // namespace

namespace {
// PySlice_GetIndicesEx over small ints: (start, stop, step, length)
}  // namespace
std::array<std::int64_t, 4> slice_indices(Obj sl, std::int64_t length, const char* message) {
    auto* s = static_cast<SliceObject*>(sl.object());
    auto value = [message](Obj v, std::int64_t dflt) {   // _PyEval_SliceIndex
        if (v == None()) return dflt;
        std::int64_t x;
        if (as_int(v, x)) return x;
        if (!is_int(v) && !has_index_method(v))
            raise_new("TypeError", message);
        return clipped_index(v);
    };
    std::int64_t step = value(s->step, 1);
    if (step == 0) raise_new("ValueError", "slice step cannot be zero");
    // PySlice_Unpack guards `step = -step`; a walk over a sequence cannot tell a step beyond its
    // length from another, so this one also leaves room for `k += step` past the end
    step = std::clamp(step, -SMALL_MAX, SMALL_MAX);
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
namespace {
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

// PyObject_GetItem and its kin on a type with sq_item alone: the key must be an index, and an index that does
// not fit is an IndexError here, where the slot wrapper itself says OverflowError
static void check_sequence_key(Obj obj, Obj key, const char* name) {
    if (!sequence_slot_of(obj, name)) return;
    if (type_lookup(type_of(key), intern("__index__")).is_unset())
        raise_new("TypeError", "sequence index must be integer, not '" + type_of(key)->name + "'");
    index_value(key, "IndexError");
}
bool tuple_contains(Obj container, Obj item) { return tuple_items_contain(container, item); }
bool list_contains(Obj container, Obj item) {    // list_contains: the items, each held, also when == raises
    auto& items = static_cast<List*>(container.object())->items;
    for (std::size_t i = 0; i < items.size(); ++i) {
        Ref held = Ref::share(items[i]);
        if (held.get() == item || truth(compare(CmpOp::Eq, held.get(), item).get())) return true;
    }
    return false;
}
Ref list_subscript(Obj obj, Obj key) {           // list_subscript: the items, whatever a subclass says; a slice an exact list
    auto& items = static_cast<List*>(obj.object())->items;
    if (!is_kind(key, Kind::Slice)) return Ref::share(items[index_of(key, items.size(), "list")]);
    auto* l = new List;
    Ref r = own(l);
    each_index(key, static_cast<std::int64_t>(items.size()), [&](std::size_t i) { incref(items[i]); l->items.push_back(items[i]); });
    return r;
}
Ref tuple_subscript(Obj obj, Obj key) {          // tuple_subscript: the items, whatever a subclass says
    auto& items = static_cast<Tuple*>(obj.object())->items;
    if (!is_kind(key, Kind::Slice)) return Ref::share(items[index_of(key, items.size(), "tuple")]);
    auto [start, stop, step, n] = slice_indices(key, static_cast<std::int64_t>(items.size()));
    if (start == 0 && step == 1 && n == static_cast<std::int64_t>(items.size()) && is_exact_tuple(obj)) return Ref::share(obj);
    std::vector<Obj> out;
    for (std::int64_t i = 0, k = start; i < n; ++i, k += step) {
        incref(items[static_cast<std::size_t>(k)]);
        out.push_back(items[static_cast<std::size_t>(k)]);
    }
    return tuple_steal(std::move(out));
}
Ref str_subscript(Obj self, Obj key) {
    const Str* s = as_str(self);
    if (!is_kind(key, Kind::Slice)) {
        std::size_t i = index_of(key, s->length, "string");
        return str_from_codepoints(std::u32string(1, s->at(i)));
    }
    auto [start, stop, step, n] = slice_indices(key, static_cast<std::int64_t>(s->length));
    if (start == 0 && step == 1 && n == static_cast<std::int64_t>(s->length) && is_exact_str(self)) return Ref::share(self);   // unicode_result_unchanged
    std::u32string out;
    for (std::int64_t i = 0, k = start; i < n; ++i, k += step) out += s->at(static_cast<std::size_t>(k));
    return str_from_codepoints(out);
}
Ref getitem(Obj obj, Obj key) {
    check_sequence_key(obj, key, "__getitem__");
    bool slice = is_kind(key, Kind::Slice);
    if (is_kind(obj, Kind::Tuple) && !overridden(obj, "__getitem__")) return tuple_subscript(obj, key);
    if (is_kind(obj, Kind::List) && !overridden(obj, "__getitem__")) return list_subscript(obj, key);
    if (as_str(obj) != nullptr && !overridden(obj, "__getitem__")) return str_subscript(obj, key);
    if (is_bytes_like(obj)) return bytes_getitem(obj, key);
    if (is_kind(obj, Kind::Range)) {                 // range_subscript
        if (slice) return range_slice(obj, key);
        if (!is_int(key) && !has_index_method(key))
            raise_new("TypeError", "range indices must be integers or slices, not " + type_of(key)->name);
        return range_item(obj, int_index_of(key).get());
    }
    if (is_kind(obj, Kind::Dict) && !overridden(obj, "__getitem__")) return dict_subscript(obj, key);
    bool has = false;
    Ref r = call_special(obj, "__getitem__", {key}, &has);
    if (has) return r;
    if (is_kind(obj, Kind::Class)) {                 // PyObject_GetItem
        if (obj == Obj::of(types().type)) return generic_alias(obj, key);   // type[int], but not str[int]
        Ref meth = optional_getattr(obj, intern("__class_getitem__"));
        if (!meth.get().is_unset() && meth.get() != None()) return invoke(meth.get(), {key});
        raise_new("TypeError", "type '" + static_cast<ClassObject*>(obj.object())->name + "' is not subscriptable");
    }
    raise_new("TypeError", "'" + type_of(obj)->name + "' object is not subscriptable");
}

Ref sequence_fast(Obj v, const char* message) {
    if (is_exact_list(v) || is_exact_tuple(v)) return Ref::share(v);   // PySequence_Fast: an exact list or tuple as it is
    Ref it;
    try {
        it = iter(v);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", message);
    }
    Ref items = list_new({});
    list_extend(items.get(), it.get());
    return items;
}

// list_ass_subscript with a value. What goes out dies once the list is whole again: a slice's items last to
// first (list_ass_slice), an extended slice's first to last. The slice's bounds are read before the value is
// iterated and fitted to the list as that left it.
static void list_assign_slice(Obj obj, Obj key, Obj value) {
    auto& items = static_cast<List*>(obj.object())->items;
    auto size = static_cast<std::int64_t>(items.size());
    auto bounds = slice_indices(key, size);
    Ref seq;
    if (value == obj) {                          // a[::-1] = a
        seq = list_new({});
        list_extend(seq.get(), obj);
    } else {
        seq = sequence_fast(value, "must assign iterable to extended slice");
    }
    if (static_cast<std::int64_t>(items.size()) != size) bounds = slice_indices(key, static_cast<std::int64_t>(items.size()));
    auto [start, stop, step, n] = bounds;
    const std::vector<Obj>& in = is_kind(seq.get(), Kind::List) ? static_cast<List*>(seq.get().object())->items : static_cast<Tuple*>(seq.get().object())->items;
    std::vector<Obj> garbage;
    if (step == 1) {
        stop = std::max(stop, start);
        auto low = items.begin() + start, high = items.begin() + stop;
        garbage.assign(low, high);
        for (Obj v : in) incref(v);
        std::vector<Obj> added(in);              // `in` may be a list that a finaliser changes later
        items.erase(low, high);
        items.insert(items.begin() + start, added.begin(), added.end());
        for (auto it = garbage.rbegin(); it != garbage.rend(); ++it) decref(*it);
        return;
    }
    if (static_cast<std::int64_t>(in.size()) != n)
        raise_new("ValueError", "attempt to assign sequence of size " + std::to_string(in.size()) + " to extended slice of size " + std::to_string(n));
    garbage.reserve(static_cast<std::size_t>(n));
    for (std::int64_t i = 0, k = start; i < n; ++i, k += step) {
        Obj v = in[static_cast<std::size_t>(i)];
        incref(v);
        garbage.push_back(std::exchange(items[static_cast<std::size_t>(k)], v));
    }
    for (Obj old : garbage) decref(old);
}

void list_ass_subscript(Obj obj, Obj key, Obj value) {   // list_ass_subscript: the items, whatever a subclass says; Unset deletes
    auto& items = static_cast<List*>(obj.object())->items;
    if (value.is_unset()) {
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
    if (is_kind(key, Kind::Slice)) {
        list_assign_slice(obj, key, value);
        return;
    }
    std::size_t i = index_of(key, items.size(), "list", "list assignment");
    incref(value);
    Obj old = std::exchange(items[i], value);
    decref(old);
}
void setitem(Obj obj, Obj key, Obj value) {
    check_sequence_key(obj, key, "__setitem__");
    if (is_kind(obj, Kind::List) && !overridden(obj, "__setitem__")) {
        list_ass_subscript(obj, key, value);
        return;
    }
    if (is_dict(obj) && !overridden(obj, "__setitem__")) {
        dict_set(static_cast<Dict*>(obj.object()), key, value);
        return;
    }
    bool has = false;
    call_special(obj, "__setitem__", {key, value}, &has);
    if (has) return;
    raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support item assignment");
}

void delitem(Obj obj, Obj key) {
    check_sequence_key(obj, key, "__delitem__");
    if (is_dict(obj) && !overridden(obj, "__delitem__")) {
        if (!dict_del(static_cast<Dict*>(obj.object()), key)) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
            raise(exc.get());
        }
        return;
    }
    if (is_kind(obj, Kind::List) && !overridden(obj, "__delitem__")) {
        list_ass_subscript(obj, key, Obj{});
        return;
    }
    bool has = false;
    call_special(obj, "__delitem__", {key}, &has);
    if (has) return;
    // PyObject_DelItem: an index goes to PySequence_DelItem, which words it otherwise
    if (has_sequence_methods(obj) && (is_int(key) || has_index_method(key))) {
        index_value(key, "IndexError");
        raise_new("TypeError", "'" + type_of(obj)->name + "' object doesn't support item deletion");
    }
    raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support item deletion");
}

// ---- iteration ----
Ref dict_iter(Obj self) {
    auto* it = new Iterator(Iterator::DictKeysIt, self);
    Ref r = own(it);
    it->size = it->len = static_cast<std::int64_t>(static_cast<Dict*>(self.object())->used);
    return r;
}
Ref dict_reversed(Obj d, int which) {
    auto* it = new Iterator(which == 0 ? Iterator::DictRevKeysIt : which == 1 ? Iterator::DictRevValuesIt : Iterator::DictRevItemsIt, d);
    Ref r = own(it);
    auto* table = static_cast<Dict*>(d.object());
    it->pos = static_cast<std::int64_t>(table->entries.size()) - 1;
    it->size = it->len = static_cast<std::int64_t>(table->used);
    return r;
}
Ref iter(Obj obj) {
    if (is_kind(obj, Kind::Range)) return range_iter(obj);
    if (is_kind(obj, Kind::Tuple) && !overridden(obj, "__iter__")) return own(new Iterator(Iterator::TupleIt, obj));
    if (is_kind(obj, Kind::List) && !overridden(obj, "__iter__")) return own(new Iterator(Iterator::ListIt, obj));
    if (as_str(obj) != nullptr && !overridden(obj, "__iter__")) return own(new Iterator(Iterator::StrIt, obj));
    if (is_bytes_like(obj)) return own(new Iterator(Iterator::BytesIt, obj));
    if (is_kind(obj, Kind::Set)) {
        auto* it = new Iterator(Iterator::SetIt, obj);
        Ref r = own(it);
        it->size = static_cast<std::int64_t>(static_cast<SetObject*>(obj.object())->used);
        return r;
    }
    // a view of the dict's own types: an OrderedDict's (odict_keys, a C subtype) is iterated as its type says
    bool own_view = is_kind(obj, Kind::DictView) && (obj.object()->cls == types().dict_keys || obj.object()->cls == types().dict_values ||
                                                     obj.object()->cls == types().dict_items);
    if ((is_kind(obj, Kind::Dict) && !overridden(obj, "__iter__")) || own_view) {
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
    if (has_sq_item(obj)) return own(new Iterator(Iterator::SeqIt, obj));
    raise_new("TypeError", "'" + type_of(obj)->name + "' object is not iterable");
}

Ref for_next(Obj itv) {
    if (is_kind(itv, Kind::Generator)) {         // gen_iternext, without a StopIteration when it ended with None
        try {
            return gen_next(itv);
        } catch (const PyError& e) {
            if (isinstance(e.exc.get(), exception_class("StopIteration"))) return Ref{};
            throw;
        }
    }
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
            auto at = static_cast<std::uint64_t>(r->start) + static_cast<std::uint64_t>(r->step) * static_cast<std::uint64_t>(it->pos++);
            return int_from_i64(static_cast<std::int64_t>(at));   // range_iter has seen that each value fits
        }
        case Iterator::LongRangeIt: {
            Ref v = long_range_next(static_cast<List*>(it->seq.object())->items);
            if (v.get().is_unset()) return finish();
            return v;
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
        case Iterator::ListRevIt: {                  // listreviter_next: the list as it is at each step
            auto& items = static_cast<List*>(it->seq.object())->items;
            if (it->pos < 0 || static_cast<std::size_t>(it->pos) >= items.size()) { it->pos = -1; return finish(); }
            return Ref::share(items[static_cast<std::size_t>(it->pos--)]);
        }
        case Iterator::BytesIt: {                    // a bytearray's as it is at each step
            const std::string& s = bytes_data(it->seq);
            if (static_cast<std::size_t>(it->pos) >= s.size()) return finish();
            return Ref::steal(Obj::small(static_cast<unsigned char>(s[static_cast<std::size_t>(it->pos++)])));
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
        case Iterator::DictRevKeysIt:                // dictreviter_iter_lock_held
        case Iterator::DictRevValuesIt:
        case Iterator::DictRevItemsIt: {
            auto* d = static_cast<Dict*>(it->seq.object());
            if (it->size == -2 || static_cast<std::int64_t>(d->used) != it->size) {
                it->size = -2;
                raise_new("RuntimeError", "dictionary changed size during iteration");
            }
            std::int64_t i = std::min(it->pos, static_cast<std::int64_t>(d->entries.size()) - 1);
            while (i >= 0 && d->entries[static_cast<std::size_t>(i)].key.is_unset()) --i;
            if (i < 0) return finish();
            it->pos = i - 1;
            --it->len;
            auto& e = d->entries[static_cast<std::size_t>(i)];
            if (it->of == Iterator::DictRevKeysIt) return Ref::share(e.key);
            if (it->of == Iterator::DictRevValuesIt) return Ref::share(e.value);
            return tuple_new({e.key, e.value});
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
    if (is_exact_tuple(value) || is_exact_list(value)) {   // UNPACK_SEQUENCE's exact list and tuple; anything else iterates
        auto& src = is_kind(value, Kind::Tuple) ? static_cast<Tuple*>(value.object())->items
                                                : static_cast<List*>(value.object())->items;
        for (Obj v : src) items.push_back(Ref::share(v));
    } else {
        // unpack_iterable: without a star, as many items as targets and one more to tell "too many"; a value with no
        // __iter__ that is no sequence either says so instead of iter()'s message
        Ref it;
        try {
            it = iter(value);
        } catch (const PyError& e) {
            if (isinstance(e.exc.get(), exception_class("TypeError")) && type_lookup(type_of(value), intern("__iter__")).is_unset()
                && !sequence_check(value))
                raise_new("TypeError", "cannot unpack non-iterable " + type_of(value)->name + " object");
            throw;
        }
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
        if (items.size() > n) {                  // an exact list, tuple or dict tells how many it had
            std::size_t have = is_exact_tuple(value) ? static_cast<Tuple*>(value.object())->items.size()
                               : is_kind(value, Kind::List) && !has_attributes(value.object()) ? static_cast<List*>(value.object())->items.size()
                               : is_exact_dict(value) ? static_cast<Dict*>(value.object())->used : 0;
            if (have > n) raise_new("ValueError", "too many values to unpack (expected " + std::to_string(n) + ", got " + std::to_string(have) + ")");
            raise_new("ValueError", "too many values to unpack (expected " + std::to_string(n) + ")");
        }
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
std::string callable_name(Obj func) {            // _PyObject_FunctionStr
    if (is_kind(func, Kind::Builtin)) return static_cast<Builtin*>(func.object())->name + "()";
    Ref qualname = optional_getattr(func, intern("__qualname__"));
    if (qualname.get().is_unset()) return as_str(str_of(func).get())->text;
    std::string q = as_str(str_of(qualname.get()).get())->text;
    Ref module = optional_getattr(func, intern("__module__"));
    if (!module.get().is_unset() && module.get() != None()) {
        const Str* m = as_str(module.get());
        if (m == nullptr || m->text != "builtins") return as_str(str_of(module.get()).get())->text + "." + q + "()";
    }
    return q + "()";
}
}  // namespace

// dict.copy() (copy_lock_held): an empty dict's copy is new; a split dict's shares its keys; a
// combined one at most a third deleted is cloned, table and all; any other is merged into a new
// dict, which compacts it. Only the merge compares keys.
Ref frozendict_copy(Obj v) {
    Ref out = dict_copy(static_cast<Dict*>(v.object()));
    out.get().object()->cls = types().frozendict;
    out.get().object()->flags |= FROZEN_DICT;
    return out;
}
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
        if (!is_exact_str(k)) throw NotImplemented("a subclass of str as a keyword's name (CPython has it; the runtime does not yet)");
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
    if (is_int(r.get()) && !int_fits_i64(r.get(), n)) raise_new("OverflowError", "Python int too large to convert to C ssize_t");
    if (!int_fits_i64(r.get(), n))
        raise_new("TypeError", fully_qualified_name(type_of(v)) + ".__length_hint__() must return an int, not " +
                                   fully_qualified_name(type_of(r.get())));
    if (n < 0) raise_new("ValueError", fully_qualified_name(type_of(v)) + ".__length_hint__() must return a non-negative int");
}

// LIST_EXTEND ([*x], (*x,)): iter()'s TypeError is reworded for an object with neither __iter__ nor
// a sequence's __getitem__
void list_extend_star(Obj list, Obj value) {
    try {
        list_extend(list, value);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        if (is_kind(value, Kind::Iterator) || !type_lookup(type_of(value), intern("__iter__")).is_unset() || has_sq_item(value))
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
