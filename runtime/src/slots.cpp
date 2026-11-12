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
Ref int_float(Obj self, Args a) { wrapper_args(a, "__float__", 0); return float_ref(int_as_double(self)); }
// float's slots: an int on either side, NotImplemented for the rest; the reflected form swaps them
template <BinOp op, bool reflected>
Ref float_slot(Obj self, Args a) {
    wrapper_args(a, "__add__", 1);
    return reflected ? float_binary(op, a.pos(0), self) : float_binary(op, self, a.pos(0));
}
template <bool reflected>
Ref float_pow_slot(Obj self, Args a) {           // wrap_ternaryfunc: __pow__(value, mod=None)
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + (reflected ? "__rpow__" : "__pow__") + "() takes no keyword arguments");
    if (a.npos < 1 || a.npos > 2) raise_new("TypeError", "expected 1 or 2 arguments, got " + std::to_string(a.npos));
    if (a.npos == 2 && a.pos(1) != None()) raise_new("TypeError", "pow() 3rd argument not allowed unless all arguments are integers");
    return reflected ? float_binary(BinOp::Pow, a.pos(0), self) : float_binary(BinOp::Pow, self, a.pos(0));
}
template <bool reflected>
Ref float_divmod_slot(Obj self, Args a) {
    wrapper_args(a, "__divmod__", 1);
    return reflected ? float_divmod(a.pos(0), self) : float_divmod(self, a.pos(0));
}
Ref float_self(Obj self) { return is_kind(self, Kind::Float) ? Ref::share(self) : float_ref(float_value(self)); }   // float_float
Ref float_neg(Obj self, Args a) { wrapper_args(a, "__neg__", 0); return float_ref(-float_value(self)); }
Ref float_pos(Obj self, Args a) { wrapper_args(a, "__pos__", 0); return float_self(self); }
Ref float_abs(Obj self, Args a) { wrapper_args(a, "__abs__", 0); return float_ref(std::fabs(float_value(self))); }
Ref float_bool(Obj self, Args a) { wrapper_args(a, "__bool__", 0); return Ref::steal(boolean(float_value(self) != 0.0)); }
Ref float_int(Obj self, Args a) { wrapper_args(a, "__int__", 0); return int_from_double(float_value(self)); }
Ref float_float(Obj self, Args a) { wrapper_args(a, "__float__", 0); return float_self(self); }
Ref float_repr(Obj self, Args a) { wrapper_args(a, "__repr__", 0); return str_new(float_text(float_value(self))); }
Ref float_hash_slot(Obj self, Args a) { wrapper_args(a, "__hash__", 0); return int_from_i64(float_hash(self)); }
Ref str_mod_slot(Obj self, Args a) {             // unicode_mod: wrap_binaryfunc_l
    wrapper_args(a, "__mod__", 1);
    if (as_str(self) == nullptr) raise_new("TypeError", "descriptor '__mod__' requires a 'str' object but received a '" + type_of(self)->name + "'");
    return str_mod(self, a.pos(0));
}
Ref str_rmod_slot(Obj self, Args a) {            // wrap_binaryfunc_r: a left operand that is no str declines
    wrapper_args(a, "__rmod__", 1);
    if (as_str(self) == nullptr) raise_new("TypeError", "descriptor '__rmod__' requires a 'str' object but received a '" + type_of(self)->name + "'");
    if (as_str(a.pos(0)) == nullptr) return not_implemented();
    return str_mod(a.pos(0), self);
}
template <Kind K>
Ref bytes_mod_slot(Obj self, Args a) {           // bytes_mod, bytearray_mod: wrap_binaryfunc_l
    const char* name = K == Kind::Bytes ? "bytes" : "bytearray";
    wrapper_args(a, "__mod__", 1);
    if (!is_kind(self, K)) raise_new("TypeError", std::string("descriptor '__mod__' requires a '") + name + "' object but received a '" + type_of(self)->name + "'");
    return bytes_format(self, a.pos(0), K == Kind::ByteArray);
}
template <Kind K>
Ref bytes_rmod_slot(Obj self, Args a) {          // wrap_binaryfunc_r: a left operand of another kind declines
    const char* name = K == Kind::Bytes ? "bytes" : "bytearray";
    wrapper_args(a, "__rmod__", 1);
    if (!is_kind(self, K)) raise_new("TypeError", std::string("descriptor '__rmod__' requires a '") + name + "' object but received a '" + type_of(self)->name + "'");
    if (!is_kind(a.pos(0), K)) return not_implemented();
    return bytes_format(a.pos(0), self, K == Kind::ByteArray);
}
Ref own_repr(Obj self, Args a) { wrapper_args(a, "__repr__", 0); return repr_of(self); }
Ref tuple_hash_slot(Obj self, Args a) { wrapper_args(a, "__hash__", 0); return int_from_i64(tuple_hash(static_cast<Tuple*>(self.object()))); }
Ref tuple_getitem_slot(Obj self, Args a) { wrapper_args(a, "__getitem__", 1); return tuple_subscript(self, a.pos(0)); }
Ref tuple_contains_slot(Obj self, Args a) { wrapper_args(a, "__contains__", 1); return Ref::steal(boolean(tuple_contains(self, a.pos(0)))); }
Ref tuple_iter_slot(Obj self, Args a) { wrapper_args(a, "__iter__", 0); return own(new Iterator(Iterator::TupleIt, self)); }
// list's own __delitem__: its items, whatever a subclass says (list.__delitem__(self, i) inside a __delitem__)
Ref list_delitem_slot(Obj self, Args a) { wrapper_args(a, "__delitem__", 1); list_ass_subscript(self, a.pos(0), Obj{}); return none_ref(); }
Ref tuple_len_slot(Obj self, Args a) { wrapper_args(a, "__len__", 0); return int_from_i64(static_cast<std::int64_t>(static_cast<Tuple*>(self.object())->items.size())); }
Ref type_or_slot(Obj self, Args a) { wrapper_args(a, "__or__", 1); return type_or(self, a.pos(0)); }
Ref type_ror_slot(Obj self, Args a) { wrapper_args(a, "__ror__", 1); return type_or(a.pos(0), self); }
// str's own: its text, whatever a subclass says
Ref str_repr_slot(Obj self, Args a) { wrapper_args(a, "__repr__", 0); return str_new(str_repr_of(as_str(self))); }
Ref str_hash_slot(Obj self, Args a) { wrapper_args(a, "__hash__", 0); return int_from_i64(str_hash(as_str(self))); }
Ref str_len_slot(Obj self, Args a) { wrapper_args(a, "__len__", 0); return int_from_i64(static_cast<std::int64_t>(as_str(self)->length)); }
Ref str_iter_slot(Obj self, Args a) { wrapper_args(a, "__iter__", 0); return own(new Iterator(Iterator::StrIt, self)); }
Ref str_contains_slot(Obj self, Args a) { wrapper_args(a, "__contains__", 1); return Ref::steal(boolean(str_contains(self, a.pos(0)))); }
Ref str_getitem_slot(Obj self, Args a) { wrapper_args(a, "__getitem__", 1); return str_subscript(self, a.pos(0)); }
Ref own_hash(Obj self, Args a) { wrapper_args(a, "__hash__", 0); return int_from_i64(hash_of(self)); }
Ref own_bool(Obj self, Args a) { wrapper_args(a, "__bool__", 0); return Ref::steal(boolean(truth(self))); }
Ref own_iter(Obj self, Args a) { wrapper_args(a, "__iter__", 0); return iter(self); }
Ref own_next(Obj self, Args a) {                 // the C++ iterators' tp_iternext as a slot wrapper: StopIteration at the end
    wrapper_args(a, "__next__", 0);
    Ref v = for_next(self);
    if (!is_end(v)) return v;
    Ref exc = invoke(Obj::of(exception_class("StopIteration")), {});
    raise(exc.get());
}
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
    wrapper_args(a, binop_dunder(op, reflected), 1);
    if (!is_kind(a.pos(0), Kind::Set)) return not_implemented();
    return reflected ? native_binary(op, a.pos(0), self) : native_binary(op, self, a.pos(0));
}
template <BinOp op, bool reflected>
Ref dictview_slot(Obj self, Args a) {           // dictviews_sub and its kin: the other side any iterable, the view on either side
    wrapper_args(a, binop_dunder(op, reflected), 1);
    return reflected ? dictview_binary(op, a.pos(0), self) : dictview_binary(op, self, a.pos(0));
}
template <CmpOp op>
Ref dictview_cmp_slot(Obj self, Args a) {
    wrapper_args(a, cmp_name(op), 1);
    return dictview_compare(op, self, a.pos(0));
}
template <bool reflected>
Ref dict_or_slot(Obj self, Args a) {
    wrapper_args(a, "__or__", 1);
    if (!is_kind(a.pos(0), Kind::Dict)) return not_implemented();
    return reflected ? native_binary(BinOp::Or, a.pos(0), self) : native_binary(BinOp::Or, self, a.pos(0));
}
Ref frozendict_hash_slot(Obj self, Args a) {     // a subclass's __hash__ may ask for this one by name
    wrapper_args(a, "__hash__", 0);
    return int_from_i64(frozendict_hash(self));
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
    slot(i, "__float__", int_float);
    slot(i, "__repr__", int_repr);
    slot(i, "__hash__", int_hash);
    slot(t.tuple, "__hash__", tuple_hash_slot);
    comparisons(t.code);                         // code_richcompare, code_hash
    slot(t.code, "__hash__", own_hash);
    slot(t.tuple, "__len__", tuple_len_slot);
    slot(t.tuple, "__getitem__", tuple_getitem_slot);
    slot(t.tuple, "__contains__", tuple_contains_slot);
    slot(t.tuple, "__iter__", tuple_iter_slot);
    slot(t.type, "__or__", type_or_slot);
    slot(t.type, "__ror__", type_ror_slot);
    slot(t.str, "__mod__", str_mod_slot);
    slot(t.str, "__rmod__", str_rmod_slot);
    slot(t.bytes, "__mod__", bytes_mod_slot<Kind::Bytes>);
    slot(t.bytes, "__rmod__", bytes_rmod_slot<Kind::Bytes>);
    slot(t.bytearray, "__mod__", bytes_mod_slot<Kind::ByteArray>);
    slot(t.bytearray, "__rmod__", bytes_rmod_slot<Kind::ByteArray>);
    ClassObject* fl = t.float_;
    comparisons(fl);
    slot(fl, "__add__", float_slot<BinOp::Add, false>);
    slot(fl, "__radd__", float_slot<BinOp::Add, true>);
    slot(fl, "__sub__", float_slot<BinOp::Sub, false>);
    slot(fl, "__rsub__", float_slot<BinOp::Sub, true>);
    slot(fl, "__mul__", float_slot<BinOp::Mul, false>);
    slot(fl, "__rmul__", float_slot<BinOp::Mul, true>);
    slot(fl, "__truediv__", float_slot<BinOp::TrueDiv, false>);
    slot(fl, "__rtruediv__", float_slot<BinOp::TrueDiv, true>);
    slot(fl, "__floordiv__", float_slot<BinOp::FloorDiv, false>);
    slot(fl, "__rfloordiv__", float_slot<BinOp::FloorDiv, true>);
    slot(fl, "__mod__", float_slot<BinOp::Mod, false>);
    slot(fl, "__rmod__", float_slot<BinOp::Mod, true>);
    slot(fl, "__pow__", float_pow_slot<false>);
    slot(fl, "__rpow__", float_pow_slot<true>);
    slot(fl, "__divmod__", float_divmod_slot<false>);
    slot(fl, "__rdivmod__", float_divmod_slot<true>);
    slot(fl, "__neg__", float_neg);
    slot(fl, "__pos__", float_pos);
    slot(fl, "__abs__", float_abs);
    slot(fl, "__bool__", float_bool);
    slot(fl, "__int__", float_int);
    slot(fl, "__float__", float_float);
    slot(fl, "__repr__", float_repr);
    slot(fl, "__hash__", float_hash_slot);
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
    ClassObject* fd = t.frozendict;
    comparisons(fd);
    slot(fd, "__or__", dict_or_slot<false>);
    slot(fd, "__ror__", dict_or_slot<true>);
    slot(fd, "__hash__", frozendict_hash_slot);
    for (ClassObject* c : {t.str, t.list, t.tuple, t.range, t.set, t.frozenset, t.slice, t.bytes, t.bytearray}) comparisons(c);
    for (ClassObject* c : {t.tuple, t.range, t.frozenset, t.slice, t.bytes}) slot(c, "__hash__", own_hash);
    for (ClassObject* c : {t.list, t.tuple, t.range, t.set, t.frozenset, t.bytes, t.bytearray}) {
        slot(c, "__len__", own_len);
        slot(c, "__iter__", own_iter);
        slot(c, "__contains__", own_contains);
    }
    for (ClassObject* c : {t.list, t.tuple, t.range, t.bytes, t.bytearray}) slot(c, "__getitem__", own_getitem);
    for (ClassObject* c : {t.range_iterator, t.longrange_iterator, t.tuple_iterator, t.list_iterator, t.list_reverseiterator, t.str_iterator,
                           t.dict_keyiterator, t.dict_valueiterator, t.dict_itemiterator, t.dict_reversekeyiterator, t.dict_reversevalueiterator,
                           t.dict_reverseitemiterator, t.bytes_iterator, t.bytearray_iterator, t.iterator, t.set_iterator}) {
        slot(c, "__iter__", own_iter);           // PyObject_SelfIter and tp_iternext, as the attributes it.__iter__ and it.__next__
        slot(c, "__next__", own_next);
    }
    slot(t.str, "__repr__", str_repr_slot);
    slot(t.str, "__hash__", str_hash_slot);
    slot(t.str, "__len__", str_len_slot);
    slot(t.str, "__iter__", str_iter_slot);
    slot(t.str, "__contains__", str_contains_slot);
    slot(t.str, "__getitem__", str_getitem_slot);
    for (ClassObject* c : {t.str, t.list, t.tuple, t.bytes, t.bytearray}) {
        slot(c, "__add__", own_add);
        slot(c, "__mul__", own_mul);
        slot(c, "__rmul__", own_mul);
    }
    for (ClassObject* c : {t.range, t.slice, t.none, t.bytes, t.bytearray}) slot(c, "__repr__", own_repr);
    slot(t.list, "__reversed__", list_reversed);
    slot(t.list, "__delitem__", list_delitem_slot);  // its other item methods are call.cpp's (method_descriptor and wrappers)
    slot(t.range, "__reversed__", range_reversed);
    slot(t.list, "sort", list_sort_m);
    slot(t.none, "__bool__", own_bool);
    slot(t.none, "__hash__", own_hash);
    for (ClassObject* c : {t.dict_keys, t.dict_items}) {   // dictviews_as_number and dictview_richcompare
        slot(c, "__or__", dictview_slot<BinOp::Or, false>);
        slot(c, "__ror__", dictview_slot<BinOp::Or, true>);
        slot(c, "__and__", dictview_slot<BinOp::And, false>);
        slot(c, "__rand__", dictview_slot<BinOp::And, true>);
        slot(c, "__sub__", dictview_slot<BinOp::Sub, false>);
        slot(c, "__rsub__", dictview_slot<BinOp::Sub, true>);
        slot(c, "__xor__", dictview_slot<BinOp::Xor, false>);
        slot(c, "__rxor__", dictview_slot<BinOp::Xor, true>);
        slot(c, "__eq__", dictview_cmp_slot<CmpOp::Eq>);
        slot(c, "__ne__", dictview_cmp_slot<CmpOp::Ne>);
        slot(c, "__lt__", dictview_cmp_slot<CmpOp::Lt>);
        slot(c, "__le__", dictview_cmp_slot<CmpOp::Le>);
        slot(c, "__gt__", dictview_cmp_slot<CmpOp::Gt>);
        slot(c, "__ge__", dictview_cmp_slot<CmpOp::Ge>);
    }
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
