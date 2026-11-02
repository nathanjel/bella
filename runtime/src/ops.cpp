// runtime/src/ops.cpp -- operators, truth, str() and repr(), attributes, items, iteration and
// unpacking on the C++ types (bella/runtime.hpp). User classes' special methods come with step 3a.2.
#include "bella/runtime.hpp"

#include <algorithm>
#include <charconv>

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

Ref binary(BinOp op, Obj a, Obj b) {
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return int_binary(op, x, y, is_kind(a, Kind::Bool) && is_kind(b, Kind::Bool));
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (op == BinOp::Add && sa != nullptr) {
        if (sb == nullptr)
            raise_new("TypeError", "can only concatenate str (not \"" + type_of(b)->name + "\") to str");
        return concat_str(sa, sb);
    }
    if (op == BinOp::Mul && (sa != nullptr || sb != nullptr)) {
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
    if (is_kind(a, Kind::Instance) || is_kind(b, Kind::Instance))
        throw NotImplemented("binary operators on instances of user classes (step 3a.2)");
    unsupported(symbol(op), a, b);
}

Ref inplace(BinOp op, Obj a, Obj b) {
    if (is_kind(a, Kind::List) && op == BinOp::Add) {
        list_extend(a, b);
        return Ref::share(a);
    }
    if (is_kind(a, Kind::Instance)) throw NotImplemented("augmented assignment on instances of user classes (step 3a.2)");
    return binary(op, a, b);
}

Ref unary_neg(Obj a) {
    std::int64_t x;
    if (as_int(a, x)) return small(int_neg(Int::from_small(x)).small());
    raise_new("TypeError", "bad operand type for unary -: '" + type_of(a)->name + "'");
}
Ref unary_pos(Obj a) {
    std::int64_t x;
    if (as_int(a, x)) return small(x);
    raise_new("TypeError", "bad operand type for unary +: '" + type_of(a)->name + "'");
}
Ref unary_invert(Obj a) {
    std::int64_t x;
    if (is_kind(a, Kind::Bool)) throw NotImplemented("~ on a bool (a DeprecationWarning in CPython 3.15)");
    if (as_int(a, x)) return small(~x);
    raise_new("TypeError", "bad operand type for unary ~: '" + type_of(a)->name + "'");
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
    if (is_kind(container, Kind::PyDict)) return !dict_get(static_cast<Dict*>(container.object()), item).is_unset();
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
    if (is_kind(container, Kind::Instance)) throw NotImplemented("`in` on instances of user classes (step 3a.2)");
    raise_new("TypeError", "argument of type '" + type_of(container)->name + "' is not a container or iterable");
}
bool sequence_compare(CmpOp op, const std::vector<Obj>& a, const std::vector<Obj>& b) {
    std::size_t n = std::min(a.size(), b.size());
    std::size_t i = 0;
    for (; i < n; ++i)
        if (!(a[i] == b[i] || truth(compare(CmpOp::Eq, a[i], b[i]).get()))) break;
    if (i >= n) return ordered(op, a.size(), b.size());
    if (op == CmpOp::Eq) return false;
    if (op == CmpOp::Ne) return true;
    return truth(compare(op, a[i], b[i]).get());
}
}  // namespace

Ref compare(CmpOp op, Obj a, Obj b) {
    switch (op) {
        case CmpOp::Is: return Ref::steal(boolean(a == b));
        case CmpOp::IsNot: return Ref::steal(boolean(a != b));
        case CmpOp::In: return Ref::steal(boolean(contains(b, a)));
        case CmpOp::NotIn: return Ref::steal(boolean(!contains(b, a)));
        default: break;
    }
    std::int64_t x, y;
    if (as_int(a, x) && as_int(b, y)) return Ref::steal(boolean(ordered(op, x, y)));
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (sa != nullptr && sb != nullptr) {
        // code point order: UTF-8 byte order is code point order
        return Ref::steal(boolean(ordered(op, std::string_view(sa->text), std::string_view(sb->text))));
    }
    if (is_kind(a, Kind::Tuple) && is_kind(b, Kind::Tuple))
        return Ref::steal(boolean(sequence_compare(op, static_cast<Tuple*>(a.object())->items, static_cast<Tuple*>(b.object())->items)));
    if (is_kind(a, Kind::List) && is_kind(b, Kind::List))
        return Ref::steal(boolean(sequence_compare(op, static_cast<List*>(a.object())->items, static_cast<List*>(b.object())->items)));
    if (is_kind(a, Kind::Instance) || is_kind(b, Kind::Instance))
        throw NotImplemented("comparison of instances of user classes (step 3a.2)");
    // no rich comparison applies: == and != fall back to identity, the orderings fail
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
        case Kind::Singleton: return o != NONE;
        case Kind::Str: return static_cast<Str*>(o)->length != 0;
        case Kind::Tuple: return !static_cast<Tuple*>(o)->items.empty();
        case Kind::List: return !static_cast<List*>(o)->items.empty();
        case Kind::PyDict: return static_cast<Dict*>(o)->used != 0;
        case Kind::Range: return static_cast<Range*>(o)->length != 0;
        case Kind::Instance: throw NotImplemented("truth of instances of user classes (step 3a.2)");
        default: return true;
    }
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
    std::int64_t x;
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
            return str_new("<class '" + prefix + c->name + "'>");
        }
        case Kind::Range: {
            auto* r = static_cast<Range*>(o);
            return str_new("range(" + int_text(r->start) + ", " + int_text(r->stop) +
                           (r->step == 1 ? "" : ", " + int_text(r->step)) + ")");
        }
        case Kind::Builtin: return str_new("<built-in function " + static_cast<Builtin*>(o)->name + ">");
        default: break;
    }
    (void)x;
    // containers and the rest: the prelude's repr (step 3a.2), and __repr__ of user classes
    throw NotImplemented("repr() of '" + type_of(v)->name + "' objects (step 3a.2: the prelude's container repr)");
}

Ref str_of(Obj v) {
    if (const Str* s = as_str(v)) {
        (void)s;
        return Ref::share(v);
    }
    if (is_kind(v, Kind::Instance)) {
        ClassObject* base = exception_class("BaseException");
        if (std::find(v.object()->cls->mro.begin(), v.object()->cls->mro.end(), base) != v.object()->cls->mro.end()) {
            // BaseException.__str__: '' with no args, str(args[0]) with one, str(args) with more
            Ref args = getattr(v, intern("args"));
            auto& items = static_cast<Tuple*>(args.get().object())->items;
            if (items.empty()) return str_new("");
            if (items.size() == 1) return str_of(items[0]);
            return repr_of(args.get());
        }
        throw NotImplemented("str() of instances of user classes (step 3a.2)");
    }
    return repr_of(v);
}

// ---- attributes ----
Ref getattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Instance)) {
        try {
            return bella::getattr(static_cast<Instance*>(obj.object()), name);
        } catch (const bella::AttributeError&) {
            raise_new("AttributeError", "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        }
    }
    if (is_kind(obj, Kind::Module)) {
        auto* m = static_cast<Module*>(obj.object());
        Obj v = dict_get(m->dict, Obj::of(name));
        if (!v.is_unset()) return Ref::share(v);
        raise_new("AttributeError", "module '" + as_str(m->name.get())->text + "' has no attribute '" + name->text + "'");
    }
    if (is_kind(obj, Kind::Class)) {
        auto* c = static_cast<ClassObject*>(obj.object());
        if (name->text == "__name__") return str_new(c->name);
        if (auto hit = c->lookup(name)) return Ref::share(hit->first);
        raise_new("AttributeError", "type object '" + c->name + "' has no attribute '" + name->text + "'");
    }
    if (is_kind(obj, Kind::PyFunction)) {
        auto* f = static_cast<PyFunction*>(obj.object());
        if (name->text == "__name__") return f->name;
        if (name->text == "__qualname__") return f->qualname;
    }
    // a C++ type's attribute: a function is bound to the object (a method descriptor's __get__)
    ClassObject* c = type_of(obj);
    if (auto hit = c->lookup(name)) {
        Obj found = hit->first;
        if (is_kind(found, Kind::Builtin) && static_cast<Builtin*>(found.object())->self.is_unset()) {
            auto* b = static_cast<Builtin*>(found.object());
            return own(new Builtin(b->name, b->fn, obj));
        }
        return Ref::share(found);
    }
    raise_new("AttributeError", "'" + c->name + "' object has no attribute '" + name->text + "'");
}

void setattr(Obj obj, const Str* name, Obj value) {
    if (is_kind(obj, Kind::Instance)) {
        bella::setattr(static_cast<Instance*>(obj.object()), name, value);
        return;
    }
    if (is_kind(obj, Kind::Module)) {
        dict_set(static_cast<Module*>(obj.object())->dict, Obj::of(name), value);
        return;
    }
    if (is_kind(obj, Kind::Class)) throw NotImplemented("setting a class attribute (step 3a.2)");
    raise_new("AttributeError", "'" + type_of(obj)->name + "' object has no attribute '" + name->text +
                                    "' and no __dict__ for setting new attributes");
}

void delattr(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Instance)) {
        try {
            bella::delattr(static_cast<Instance*>(obj.object()), name);
        } catch (const bella::AttributeError&) {
            raise_new("AttributeError", "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");
        }
        return;
    }
    throw NotImplemented("del of an attribute of a '" + type_of(obj)->name + "' object");
}

// ---- items ----
namespace {
std::size_t index_of(Obj key, std::size_t size, const char* what) {
    std::int64_t i;
    if (!as_int(key, i))
        raise_new("TypeError", std::string(what) + " indices must be integers or slices, not " + type_of(key)->name);
    if (i < 0) i += static_cast<std::int64_t>(size);
    if (i < 0 || i >= static_cast<std::int64_t>(size)) raise_new("IndexError", std::string(what) + " index out of range");
    return static_cast<std::size_t>(i);
}
}  // namespace

Ref getitem(Obj obj, Obj key) {
    if (is_kind(obj, Kind::Tuple)) {
        auto& items = static_cast<Tuple*>(obj.object())->items;
        return Ref::share(items[index_of(key, items.size(), "tuple")]);
    }
    if (is_kind(obj, Kind::List)) {
        auto& items = static_cast<List*>(obj.object())->items;
        return Ref::share(items[index_of(key, items.size(), "list")]);
    }
    if (const Str* s = as_str(obj)) {
        std::size_t i = index_of(key, s->length, "string");
        return str_from_codepoints(std::u32string(1, s->at(i)));
    }
    if (is_kind(obj, Kind::PyDict)) {
        Obj v = dict_get(static_cast<Dict*>(obj.object()), key);
        if (v.is_unset()) {
            Ref exc = invoke(Obj::of(exception_class("KeyError")), {key});
            raise(exc.get());
        }
        return Ref::share(v);
    }
    throw NotImplemented("subscription of '" + type_of(obj)->name + "' objects");
}

void setitem(Obj obj, Obj key, Obj value) {
    if (is_kind(obj, Kind::List)) {
        auto& items = static_cast<List*>(obj.object())->items;
        std::size_t i = index_of(key, items.size(), "list assignment");
        incref(value);
        Obj old = std::exchange(items[i], value);
        decref(old);
        return;
    }
    if (is_kind(obj, Kind::PyDict)) {
        dict_set(static_cast<Dict*>(obj.object()), key, value);
        return;
    }
    if (is_kind(obj, Kind::Tuple) || as_str(obj) != nullptr)
        raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support item assignment");
    throw NotImplemented("item assignment on '" + type_of(obj)->name + "' objects");
}

void delitem(Obj obj, Obj key) {
    if (is_kind(obj, Kind::PyDict)) {
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
    throw NotImplemented("item deletion on '" + type_of(obj)->name + "' objects");
}

// ---- iteration ----
Ref iter(Obj obj) {
    if (is_kind(obj, Kind::Range)) return own(new Iterator(Iterator::RangeIt, obj));
    if (is_kind(obj, Kind::Tuple)) return own(new Iterator(Iterator::TupleIt, obj));
    if (is_kind(obj, Kind::List)) return own(new Iterator(Iterator::ListIt, obj));
    if (as_str(obj) != nullptr) return own(new Iterator(Iterator::StrIt, obj));
    if (is_kind(obj, Kind::PyDict)) {
        auto* it = new Iterator(Iterator::DictKeysIt, obj);
        Ref r = own(it);
        it->pos = 0;
        return r;
    }
    if (is_kind(obj, Kind::Iterator)) return Ref::share(obj);
    if (is_kind(obj, Kind::Instance)) throw NotImplemented("iteration over instances of user classes (step 3a.2)");
    raise_new("TypeError", "'" + type_of(obj)->name + "' object is not iterable");
}

Ref for_next(Obj itv) {
    if (!is_kind(itv, Kind::Iterator)) throw NotImplemented("FOR_ITER on '" + type_of(itv)->name + "' objects");
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
        case Iterator::DictKeysIt: {
            auto* d = static_cast<Dict*>(it->seq.object());
            while (static_cast<std::size_t>(it->pos) < d->entries.size() &&
                   d->entries[static_cast<std::size_t>(it->pos)].key.is_unset()) ++it->pos;
            if (static_cast<std::size_t>(it->pos) >= d->entries.size()) return finish();
            return Ref::share(d->entries[static_cast<std::size_t>(it->pos++)].key);
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
