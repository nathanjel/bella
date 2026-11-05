// runtime/src/slots.cpp -- the special methods of the built-in types as attributes: what a program
// reaches through `(5).__add__`, `int.__repr__` or super() in a subclass. CPython keeps them in each
// type's own dict (slot wrappers); the operators themselves never come here (runtime/src/ops.cpp).
// A name CPython's type defines and this file does not is refused where it is read, not answered
// by a base class's method (refuse_shadowed, RL-310).
#include "bella/runtime.hpp"

namespace bella {
namespace {
void wrapper_args(Args a, const char* name, std::size_t n) {     // wrapper_call, check_num_args
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos != n)
        raise_new("TypeError", "expected " + std::to_string(n) + " argument" + (n == 1 ? "" : "s") + ", got " + std::to_string(a.npos));
}
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
Ref not_implemented() { return Ref::steal(Obj::of(NOTIMPLEMENTED)); }

template <CmpOp op>
Ref cmp_slot(Obj self, Args a) {
    wrapper_args(a, cmp_name(op), 1);
    return native_compare(op, self, a.pos(0));
}
// long_add and its kin: NotImplemented unless both are ints; the reflected form swaps them
template <BinOp op, bool reflected>
Ref int_slot(Obj self, Args a) {
    wrapper_args(a, "__add__", 1);
    if (!is_int(a.pos(0))) return not_implemented();
    return reflected ? native_binary(op, a.pos(0), self) : native_binary(op, self, a.pos(0));
}
template <bool reflected>
Ref int_pow(Obj self, Args a) {                  // __pow__(value, mod=None)
    if (a.nkw != 0) raise_new("TypeError", "wrapper __pow__() takes no keyword arguments");
    if (a.npos < 1 || a.npos > 2) raise_new("TypeError", "expected 1 or 2 arguments, got " + std::to_string(a.npos));
    if (!is_int(a.pos(0))) return not_implemented();
    if (a.npos == 2 && a.pos(1) != None()) {         // long_pow with a modulus; wrap_ternaryfunc_r swaps the first two
        if (!is_int(a.pos(1))) return not_implemented();
        return reflected ? big_pow_mod(a.pos(0), self, a.pos(1)) : big_pow_mod(self, a.pos(0), a.pos(1));
    }
    return reflected ? native_binary(BinOp::Pow, a.pos(0), self) : native_binary(BinOp::Pow, self, a.pos(0));
}
template <bool reflected>
Ref int_divmod(Obj self, Args a) {
    wrapper_args(a, "__divmod__", 1);
    if (!is_int(a.pos(0))) return not_implemented();
    return reflected ? big_divmod(a.pos(0), self) : big_divmod(self, a.pos(0));
}
Ref int_neg(Obj self, Args a) { wrapper_args(a, "__neg__", 0); return big_negate(self); }
Ref int_pos(Obj self, Args a) { wrapper_args(a, "__pos__", 0); return big_plain(self); }
Ref int_abs(Obj self, Args a) { wrapper_args(a, "__abs__", 0); return big_absolute(self); }
Ref int_invert(Obj self, Args a) { wrapper_args(a, "__invert__", 0); return big_invert(self); }
Ref int_bool(Obj self, Args a) { wrapper_args(a, "__bool__", 0); return Ref::steal(boolean(!int_is_zero(self))); }
Ref int_int(Obj self, Args a) { wrapper_args(a, "__int__", 0); return big_plain(self); }
Ref int_index(Obj self, Args a) { wrapper_args(a, "__index__", 0); return big_plain(self); }
Ref int_trunc(Obj self, Args a) {                // __trunc__, __floor__, __ceil__: METH_NOARGS
    if (a.npos != 0 || a.nkw != 0) raise_new("TypeError", "int method takes no arguments (" + std::to_string(a.npos) + " given)");
    return big_plain(self);
}
Ref int_round_m(Obj self, Args a) {              // long_round(self, ndigits=None, /)
    clinic(a, "__round__", "int.__round__", 0, 1);
    return int_round(self, a.npos == 1 ? a.pos(0) : Obj{});
}
Ref int_repr(Obj self, Args a) {
    wrapper_args(a, "__repr__", 0);
    return str_new(big_text(self));
}
Ref int_hash(Obj self, Args a) {
    wrapper_args(a, "__hash__", 0);
    return int_from_i64(big_hash(self));
}
Ref own_repr(Obj self, Args a) { wrapper_args(a, "__repr__", 0); return repr_of(self); }
Ref own_hash(Obj self, Args a) { wrapper_args(a, "__hash__", 0); return int_from_i64(hash_of(self)); }
Ref own_bool(Obj self, Args a) { wrapper_args(a, "__bool__", 0); return Ref::steal(boolean(truth(self))); }
Ref own_iter(Obj self, Args a) { wrapper_args(a, "__iter__", 0); return iter(self); }
Ref own_contains(Obj self, Args a) { wrapper_args(a, "__contains__", 1); return compare(CmpOp::In, a.pos(0), self); }
Ref own_getitem(Obj self, Args a) { wrapper_args(a, "__getitem__", 1); return getitem(self, a.pos(0)); }
Ref own_add(Obj self, Args a) { wrapper_args(a, "__add__", 1); return sequence_concat(self, a.pos(0)); }
Ref own_mul(Obj self, Args a) { wrapper_args(a, "__mul__", 1); return sequence_repeat(self, a.pos(0)); }
Ref list_reversed(Obj self, Args a) {
    noargs(a, "list.__reversed__");
    Ref it = own(new Iterator(Iterator::ListRevIt, self));
    static_cast<Iterator*>(it.get().object())->pos = static_cast<std::int64_t>(static_cast<List*>(self.object())->items.size()) - 1;
    return it;
}
Ref range_reversed(Obj self, Args a) {           // range_reverse: the iterator of the same values backwards
    noargs(a, "range.__reversed__");
    auto* r = static_cast<Range*>(self.object());
    // the int version if each of start, stop, step, -step, start-step and the length is a C long
    if (r->big || r->step == INT64_MIN || (r->step > 0 ? r->start < INT64_MIN + r->step : r->start > INT64_MAX + r->step))
        return big_range_reversed(self);
    auto last = static_cast<std::uint64_t>(r->start) + static_cast<std::uint64_t>(r->length - 1) * static_cast<std::uint64_t>(r->step);
    Ref back = own(new Range(static_cast<std::int64_t>(last), r->start - r->step, -r->step));
    return own(new Iterator(Iterator::RangeIt, back.get()));
}
Ref own_len(Obj self, Args a) {
    wrapper_args(a, "__len__", 0);
    Ref len = builtin("len");
    return invoke(len.get(), {self});
}
template <BinOp op, bool reflected>
Ref set_slot(Obj self, Args a) {
    wrapper_args(a, "__or__", 1);
    if (!is_kind(a.pos(0), Kind::Set)) return not_implemented();
    return reflected ? native_binary(op, a.pos(0), self) : native_binary(op, self, a.pos(0));
}
template <bool reflected>
Ref dict_or_slot(Obj self, Args a) {
    wrapper_args(a, "__or__", 1);
    if (!is_kind(a.pos(0), Kind::Dict)) return not_implemented();
    return reflected ? native_binary(BinOp::Or, a.pos(0), self) : native_binary(BinOp::Or, self, a.pos(0));
}
Ref dict_ior_slot(Obj self, Args a) {
    wrapper_args(a, "__ior__", 1);
    dict_update_arg(self, a.pos(0));
    return Ref::share(self);
}

// range: start, stop, step, and the sequence methods (Objects/rangeobject.c)
Range* range_of(Obj v) { return static_cast<Range*>(v.object()); }
Ref range_start(Obj self) { return range_field(self, 0); }
Ref range_stop(Obj self) { return range_field(self, 1); }
Ref range_step(Obj self) { return range_field(self, 2); }
bool exact_or_bool(Obj v) { return v.is_small() || is_kind(v, Kind::Bool) || is_kind(v, Kind::BigInt); }
Ref range_count(Obj self, Args a) {
    if (a.npos != 1 || a.nkw != 0) raise_new("TypeError", "range.count() takes exactly one argument (" + std::to_string(a.npos) + " given)");
    if (exact_or_bool(a.pos(0))) return Ref::steal(Obj::small(range_contains_int(self, a.pos(0)) ? 1 : 0));
    std::int64_t n = 0;                          // _PySequence_IterSearch: a subclass's __eq__ may say anything
    Ref it = iter(self);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (truth(compare(CmpOp::Eq, v.get(), a.pos(0)).get())) ++n;
    return int_from_i64(n);
}
Ref range_index(Obj self, Args a) {
    if (a.npos != 1 || a.nkw != 0) raise_new("TypeError", "range.index() takes exactly one argument (" + std::to_string(a.npos) + " given)");
    Obj x = a.pos(0);
    if (exact_or_bool(x)) {
        if (!range_contains_int(self, x)) raise_new("ValueError", "range.index(x): x not in range");
        Ref start = range_field(self, 0), step = range_field(self, 2);
        return big_binary(BinOp::FloorDiv, big_binary(BinOp::Sub, x, start.get()).get(), step.get());
    }
    std::int64_t n = 0;
    Ref it = iter(self);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()), ++n)
        if (truth(compare(CmpOp::Eq, v.get(), x).get())) return int_from_i64(n);
    raise_new("ValueError", "sequence.index(x): x not in sequence");
}

void slot(ClassObject* c, const char* name, NativeFn fn) {
    if (c->attrs.contains(intern(name))) return;
    auto* f = new Builtin(name, fn, Obj{}, Binding::Method);   // its class comes from its binding: this one binds
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(f));
}
void comparisons(ClassObject* c) {
    slot(c, "__eq__", cmp_slot<CmpOp::Eq>);
    slot(c, "__ne__", cmp_slot<CmpOp::Ne>);
    slot(c, "__lt__", cmp_slot<CmpOp::Lt>);
    slot(c, "__le__", cmp_slot<CmpOp::Le>);
    slot(c, "__gt__", cmp_slot<CmpOp::Gt>);
    slot(c, "__ge__", cmp_slot<CmpOp::Ge>);
}
}  // namespace

void init_slots() {
    Types& t = types();
    ClassObject* i = t.int_;
    comparisons(i);
    slot(i, "__add__", int_slot<BinOp::Add, false>);
    slot(i, "__radd__", int_slot<BinOp::Add, true>);
    slot(i, "__sub__", int_slot<BinOp::Sub, false>);
    slot(i, "__rsub__", int_slot<BinOp::Sub, true>);
    slot(i, "__mul__", int_slot<BinOp::Mul, false>);
    slot(i, "__rmul__", int_slot<BinOp::Mul, true>);
    slot(i, "__truediv__", int_slot<BinOp::TrueDiv, false>);
    slot(i, "__rtruediv__", int_slot<BinOp::TrueDiv, true>);
    slot(i, "__floordiv__", int_slot<BinOp::FloorDiv, false>);
    slot(i, "__rfloordiv__", int_slot<BinOp::FloorDiv, true>);
    slot(i, "__mod__", int_slot<BinOp::Mod, false>);
    slot(i, "__rmod__", int_slot<BinOp::Mod, true>);
    slot(i, "__lshift__", int_slot<BinOp::LShift, false>);
    slot(i, "__rlshift__", int_slot<BinOp::LShift, true>);
    slot(i, "__rshift__", int_slot<BinOp::RShift, false>);
    slot(i, "__rrshift__", int_slot<BinOp::RShift, true>);
    slot(i, "__and__", int_slot<BinOp::And, false>);
    slot(i, "__rand__", int_slot<BinOp::And, true>);
    slot(i, "__or__", int_slot<BinOp::Or, false>);
    slot(i, "__ror__", int_slot<BinOp::Or, true>);
    slot(i, "__xor__", int_slot<BinOp::Xor, false>);
    slot(i, "__rxor__", int_slot<BinOp::Xor, true>);
    slot(i, "__pow__", int_pow<false>);
    slot(i, "__rpow__", int_pow<true>);
    slot(i, "__divmod__", int_divmod<false>);
    slot(i, "__rdivmod__", int_divmod<true>);
    slot(i, "__neg__", int_neg);
    slot(i, "__pos__", int_pos);
    slot(i, "__abs__", int_abs);
    slot(i, "__invert__", int_invert);
    slot(i, "__bool__", int_bool);
    slot(i, "__int__", int_int);
    slot(i, "__index__", int_index);
    slot(i, "__trunc__", int_trunc);
    slot(i, "__floor__", int_trunc);
    slot(i, "__ceil__", int_trunc);
    slot(i, "__round__", int_round_m);
    slot(i, "__repr__", int_repr);
    slot(i, "__hash__", int_hash);
    // bool's own: its repr, and & | ^ that keep a bool
    ClassObject* b = t.bool_;
    slot(b, "__repr__", own_repr);
    slot(b, "__and__", int_slot<BinOp::And, false>);
    slot(b, "__rand__", int_slot<BinOp::And, true>);
    slot(b, "__or__", int_slot<BinOp::Or, false>);
    slot(b, "__ror__", int_slot<BinOp::Or, true>);
    slot(b, "__xor__", int_slot<BinOp::Xor, false>);
    slot(b, "__rxor__", int_slot<BinOp::Xor, true>);
    ClassObject* d = t.dict;
    comparisons(d);
    slot(d, "__or__", dict_or_slot<false>);
    slot(d, "__ror__", dict_or_slot<true>);
    slot(d, "__ior__", dict_ior_slot);
    for (ClassObject* c : {t.str, t.list, t.tuple, t.range, t.set, t.frozenset, t.slice, t.bytes, t.bytearray}) comparisons(c);
    for (ClassObject* c : {t.str, t.tuple, t.range, t.frozenset, t.slice, t.bytes}) slot(c, "__hash__", own_hash);
    for (ClassObject* c : {t.str, t.list, t.tuple, t.range, t.set, t.frozenset, t.bytes, t.bytearray}) {
        slot(c, "__len__", own_len);
        slot(c, "__iter__", own_iter);
        slot(c, "__contains__", own_contains);
    }
    for (ClassObject* c : {t.str, t.list, t.tuple, t.range, t.bytes, t.bytearray}) slot(c, "__getitem__", own_getitem);
    for (ClassObject* c : {t.str, t.list, t.tuple, t.bytes, t.bytearray}) {
        slot(c, "__add__", own_add);
        slot(c, "__mul__", own_mul);
        slot(c, "__rmul__", own_mul);
    }
    for (ClassObject* c : {t.str, t.range, t.slice, t.none, t.bytes, t.bytearray}) slot(c, "__repr__", own_repr);
    slot(t.list, "__reversed__", list_reversed);
    slot(t.range, "__reversed__", range_reversed);
    slot(t.list, "sort", list_sort_m);
    slot(t.none, "__bool__", own_bool);
    slot(t.none, "__hash__", own_hash);
    for (ClassObject* c : {t.set, t.frozenset}) {
        slot(c, "__or__", set_slot<BinOp::Or, false>);
        slot(c, "__ror__", set_slot<BinOp::Or, true>);
        slot(c, "__and__", set_slot<BinOp::And, false>);
        slot(c, "__rand__", set_slot<BinOp::And, true>);
        slot(c, "__sub__", set_slot<BinOp::Sub, false>);
        slot(c, "__rsub__", set_slot<BinOp::Sub, true>);
        slot(c, "__xor__", set_slot<BinOp::Xor, false>);
        slot(c, "__rxor__", set_slot<BinOp::Xor, true>);
    }
    ClassObject* r = t.range;
    auto member = [r](const char* name, Ref (*get)(Obj)) { auto* m = new GetSet(name, r, get, nullptr);
        m->cls = types().member_descriptor;
        r->attrs.set(intern(name), Obj::of(m)); };
    member("start", range_start);
    member("stop", range_stop);
    member("step", range_step);
    slot(r, "count", range_count);
    slot(r, "index", range_index);
}

}  // namespace bella
