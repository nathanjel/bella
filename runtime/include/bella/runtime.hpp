// bella/runtime.hpp -- what generated code calls: the C++ core of the runtime (docs/emitter.md).
//
// Decided 2026-11-02 (docs/DECISIONS.md, step 3 of the C++ leg): C++ holds storage and the hot
// primitives (values, int, str, tuple, list, dict, hashing, iteration, the call protocol, the
// exception carrier, the type objects); whatever is defined by other Python operations is Python in
// runtime/prelude/, compiled by Bella like any program. Single-threaded, as object.hpp.
//
// Exceptions are C++ exceptions (docs/l2.md section 8, decision 4): `PyError` carries the Python
// exception object. Frames are a record and a guard (decision 5): the guard, declared after a
// function's locals, appends (code, line) to the exception's traceback when the exception leaves
// the function, and moves the locals into that entry, so they die with the traceback.
//
// What this does not do yet raises bella::NotImplemented naming it, never an approximation.
#pragma once
#include "bella/int.hpp"
#include "bella/object.hpp"

#include <array>
#include <cstdint>
#include <exception>
#include <initializer_list>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace bella {

struct Code;
struct PyFunction;
struct Module;

// ---- the call protocol: positional values, then keyword values named by kwnames ----
struct Args {
    const Obj* data = nullptr;
    std::size_t npos = 0;
    const Str* const* kwnames = nullptr;
    std::size_t nkw = 0;
    Obj pos(std::size_t i) const { return data[i]; }
    Obj kw(std::size_t i) const { return data[npos + i]; }
};
using NativeFn = Ref (*)(Obj self, Args args);       // self: the bound object, or Unset

// A new object's first count belongs to whoever made it (CPython's convention; object.hpp's
// objects start at zero and are counted by their holders).
template <class T>
Ref own(T* o) {
    o->refs = 1;
    return Ref::steal(Obj::of(o));
}

// ---- the runtime's objects ----
struct Singleton : Object {                      // None, NotImplemented, Ellipsis
    const char* repr;
    Singleton(ClassObject* c, const char* r) : Object(Kind::Singleton), repr(r) { cls = c; flags |= IMMORTAL; }
};
struct BoolObject : Object {
    bool value;
    BoolObject(ClassObject* c, bool v) : Object(Kind::Bool), value(v) { cls = c; flags |= IMMORTAL; }
};
struct Tuple : Object {                          // owns one count of each item
    std::vector<Obj> items;
    Tuple();
};
struct List : Object {
    std::vector<Obj> items;
    List();
};
struct Cell : Object {
    Obj value;                                   // Unset: empty
    Cell();
};
// A function written in C++. As a class attribute it is a method descriptor (bound to the instance
// on access), a class-method descriptor (bound to the class), or a plain function (not bound:
// object.__new__, the module-level builtins).
enum class Binding : std::uint8_t { Function, Method, ClassMethod };
struct Builtin : Object {
    std::string name;
    NativeFn fn;
    Obj self;                                    // a bound method's object (owned), or Unset
    Binding binding;
    ClassObject* owner = nullptr;                // a method's type: its receiver must be an instance of it
    Builtin(std::string n, NativeFn f, Obj s = Obj{}, Binding b = Binding::Function);
};
struct GetSet : Object {                         // a getset descriptor: a data descriptor in C++
    const char* name;
    ClassObject* owner;
    Ref (*get)(Obj self);
    void (*set)(Obj self, Obj value);            // nullptr: read-only
    bool deletable = false;                      // del calls set with Unset
    GetSet(const char* n, ClassObject* o, Ref (*g)(Obj), void (*s)(Obj, Obj));
};
struct SliceObject : Object {                    // slice(start, stop, step), each owned
    Obj start, stop, step;
    SliceObject(Obj a, Obj b, Obj c);
};
struct Proxy : Object {                          // a mappingproxy over a class's own attributes
    ClassObject* of;
    explicit Proxy(ClassObject* c);
};
// CPython's set table (Objects/setobject.c): linear probes, then perturbation; deleted entries
// are dummies; iteration in table order, which D-05 matches for value-hashed elements
struct SetObject : Object {
    struct Entry {
        Obj key;                                 // Unset: empty (hash 0) or a dummy (hash -1)
        std::int64_t hash = 0;
    };
    std::vector<Entry> table;
    std::size_t fill = 0, used = 0;
    bool frozen;
    explicit SetObject(bool frozen_set);
};
struct Method : Object {                         // a bound method: func and self, owned
    Obj func;
    Obj self;
    Method(Obj f, Obj s);
};
struct Range : Object {
    std::int64_t start, stop, step, length;
    Range(std::int64_t a, std::int64_t b, std::int64_t c);
};
struct Iterator : Object {                       // the C++ types' iterators
    enum Of : std::uint8_t { RangeIt, TupleIt, ListIt, StrIt, DictKeysIt, DictValuesIt, DictItemsIt, SeqIt, SetIt } of;
    Obj seq;                                     // owned (Unset once exhausted, as CPython's)
    std::int64_t pos = 0;
    std::int64_t size = -1;                      // a set's or dict's size when iteration began; -2: failed (sticky)
    std::int64_t len = 0;                        // a dict iterator's entries still to come (dictiterobject.len)
    Iterator(Of o, Obj s);
};
struct DictView : Object {                       // dict.keys(), values(), items(): live views of the dict
    enum Which : std::uint8_t { Keys, Values, Items } which;
    Obj dict;                                    // owned
    DictView(Obj d, Which w);
};
struct SuperObject : Object {                    // super(type, obj): each owned, Unset for NULL (superobject)
    Obj type;                                    // the class after which the lookup starts (__thisclass__)
    Obj obj;                                     // the instance or class it is bound to (__self__)
    Obj obj_type;                                // obj's type, or obj when it is a class (__self_class__)
    SuperObject();
};
struct Native : Object {                         // an object of a C++ type with methods (sys.stdout)
    int tag = 0;
    explicit Native(ClassObject* c) : Object(Kind::Native) { cls = c; }
};

// a code object's description: what the frame record, argument binding and tracebacks read
struct Code {
    const char* name;
    const char* qualname;
    const char* filename;
    int first_line;
    int argcount;                                // positional parameters, positional-only included
    int posonlyargcount;
    int kwonlyargcount;
    bool varargs;
    bool varkw;
    std::vector<const char*> varnames;           // parameters first, as co_varnames
    const char* doc = nullptr;                   // the docstring, or none
    // false for code CPython runs without a frame of its own: the prelude (C functions there)
    // and an inlined comprehension (PEP 709); such a frame never enters a traceback (RL-223/224)
    bool shown = true;
};

struct PyFunction : Object {
    const Code* code;
    Ref (*entry)(PyFunction* self, Args args);
    Module* module;                              // its globals (the module is immortal in phase 1)
    Ref defaults;                                // a tuple, or Unset
    Ref kwdefaults;                              // a dict, or Unset
    std::vector<Ref> closure;                    // cells, in the order of co_freevars
    Ref name, qualname, doc, annotate, dict;
    PyFunction(const Code* c, Ref (*e)(PyFunction*, Args), Module* m);
};

using Dict = DictObject;                         // object.hpp's: every dict, an instance's __dict__ included

struct Module : Object {
    Ref name;
    Dict* dict;                                  // owned
    explicit Module(const char* n);
};

struct Traceback : Object {                      // one frame's entry; `next` goes deeper
    const Code* code;
    int line;
    std::uint64_t frame = 0;                     // the frame (a FrameGuard's id) it records
    std::vector<Ref> locals;                     // the frame's locals, taken over during unwinding
    Ref next;
    Traceback(const Code* c, int l, Ref nx);
};

// ---- the builtin types and singletons (made at start-up) ----
struct Types {
    ClassObject *object, *type, *int_, *bool_, *str, *none, *notimplemented, *ellipsis, *tuple, *list,
        *dict, *cell, *function, *builtin, *method, *range, *range_iterator, *tuple_iterator,
        *list_iterator, *str_iterator, *dict_keyiterator, *module, *traceback, *textio, *float_,
        *method_descriptor, *classmethod_descriptor, *getset_descriptor, *member_descriptor, *super_, *mappingproxy, *slice, *iterator, *set,
        *frozenset, *set_iterator, *dict_keys, *dict_values, *dict_items, *dict_valueiterator, *dict_itemiterator;
};
Types& types();
extern Singleton* const NONE;
extern Singleton* const NOTIMPLEMENTED;
extern Singleton* const ELLIPSIS;
extern BoolObject* const TRUE;
extern BoolObject* const FALSE;
inline Obj None() { return Obj::of(NONE); }
inline Obj boolean(bool b) { return Obj::of(b ? TRUE : FALSE); }
inline Ref none_ref() { return Ref::steal(None()); }     // immortal: no count to take

ClassObject* type_of(Obj v);
inline bool is_kind(Obj v, Kind k) { return v.is_object() && v.object()->kind == k; }

// ---- exceptions ----
// The exception being propagated, which frame guards record frames into. A thrown or rethrown
// PyError marks itself as the owner; when that PyError dies (caught, and its handler done) the
// mark is cleared, so a later C++ exception that is not a Python one (a refusal) unwinds without
// touching an exception that is dead or no longer propagating (found while fixing the order of
// __getattr__, review 2026-11-03). A copy never owns the mark.
namespace detail {
inline Obj& raising() {
    static Obj in_flight;
    return in_flight;
}
inline const void*& raising_owner() {
    static const void* owner = nullptr;
    return owner;
}
}
// A frame records an exception where it arrives (CPython's PyTraceBack_Here at the `error:`
// label): at the frame's first catch that sees it, or at its guard when nothing catches it
// there, before any handler code moves the line on. `recorded` says which frame has recorded
// this throw, so the frame's own re-raises (a finally's end, an unmatched except) add nothing;
// leaving a frame clears it, so the caller records the call. A bare `raise` is BARE_RAISE: the
// frame that re-raises records nothing (RL-221).
namespace detail {
inline constexpr std::uint64_t BARE_RAISE = ~std::uint64_t{0};
}
struct PyError {
    Ref exc;                                     // the exception instance
    std::uint64_t recorded = 0;                  // the frame that recorded this throw, 0, or BARE_RAISE
    explicit PyError(Ref e, std::uint64_t rec = 0) : exc(std::move(e)), recorded(rec) {
        detail::raising() = exc.get();
        detail::raising_owner() = this;
    }
    PyError(const PyError& o) : exc(o.exc), recorded(o.recorded) {}
    PyError& operator=(const PyError&) = delete;
    ~PyError() {
        if (detail::raising_owner() == this) {
            detail::raising() = Obj{};
            detail::raising_owner() = nullptr;
        }
    }
};
[[noreturn]] void raise(Obj exc);                // raise exc (an instance); the caller keeps its count
[[noreturn]] void raise_new(const char* type, const std::string& message);
[[noreturn]] void raise_type(Obj type_or_instance, Obj cause = Obj{}, bool has_cause = false);
ClassObject* exception_class(const char* name);
bool exception_matches(Obj exc, Obj spec);       // except clause matching (a class or a tuple of them)
Obj traceback_of(Obj exc);
bool is_exception_instance(Obj v);               // PyExceptionInstance_Check
// a class whose metaclass is a class of the program's (a heap subclass of type): its special
// methods come from that metaclass, as an instance's come from its class
inline bool has_python_type(Obj v) { return v.is_object() && v.object()->kind == Kind::Class && v.object()->cls->heap_type; }
// BaseException's C fields (args, __traceback__, __cause__, __context__, __suppress_context__;
// AttributeError's name and obj, NameError's name): the object's own storage, never its __dict__
// (refmodel RefClass native). Unset reads as absent: None to the descriptors, () for args.
Obj exception_field(Obj exc, const char* name);
void set_exception_field(Obj exc, const char* name, Obj value);   // the new value kept before the old is released
[[noreturn]] void reraise();                     // bare `raise`: the exception being handled
// Inside a catch block: the caught exception goes on, as the one being propagated again (a
// finally block or an except clause's test may have raised and caught others meanwhile).
[[noreturn]] inline void rethrow(const PyError& e) {
    detail::raising() = e.exc.get();
    detail::raising_owner() = &e;
    throw;
}
// An exception nothing can propagate (from a finaliser): reported on stderr as CPython reports
// an unraisable exception, then dropped.
void report_unraisable(const std::string& context, const PyError& e);
// While an except clause runs, its exception is the one being handled: what a bare `raise`
// re-raises and what a new exception records as __context__ (sys.exception()).
class Handling {
public:
    explicit Handling(const Ref& exc);
    ~Handling();
    Handling(const Handling&) = delete;
    Handling& operator=(const Handling&) = delete;
};

// The frame record and guard (docs/l2.md decision 5). Declared after the frame's locals, so it is
// destroyed first when an exception unwinds the function. An exception is recorded where it
// arrives in the frame (`arrived`, the first statement of each of the frame's catches, or the
// guard if none caught it); when it leaves, the guard moves the locals into the frame's entry,
// where they die with the traceback (RL-221; a caught exception keeping them is RL-222, step 3c).
namespace detail {
void arrive(const Code& code, int line, std::uint64_t& id, PyError& e) noexcept;
void record_frame(const Code& code, int line, std::uint64_t& id, Ref* const* locals, std::size_t n) noexcept;
void enter_frame();                              // RecursionError past the limit (spec D-17)
void leave_frame() noexcept;
}
template <std::size_t N>
class FrameGuard {
    const Code& code_;
    std::array<Ref*, N> locals_;
    int uncaught_;
    std::uint64_t id_ = 0;                       // given when the frame first records an exception
public:
    int line;
    template <class... L>
    explicit FrameGuard(const Code& c, L&... locals)
        : code_(c), locals_{&locals...}, uncaught_(std::uncaught_exceptions()), line(c.first_line) {
        detail::enter_frame();
    }
    void arrived(PyError& e) noexcept { detail::arrive(code_, line, id_, e); }
    ~FrameGuard() {
        detail::leave_frame();
        if (std::uncaught_exceptions() > uncaught_) detail::record_frame(code_, line, id_, locals_.data(), N);
    }
    FrameGuard(const FrameGuard&) = delete;
    FrameGuard& operator=(const FrameGuard&) = delete;
};
template <class... L>
FrameGuard(const Code&, L&...) -> FrameGuard<sizeof...(L)>;

// The variables the frontend made for values CPython keeps on its stack (a `with` statement's
// manager, a match subject, an inlined comprehension's iterator and result, ...). Declared after
// the frame guard and before the temporaries: when an exception leaves the function they die in
// unwinding, after the temporaries, in the order given (newest first), before the frame is
// recorded with the real locals (review log RL-186).
template <std::size_t N>
class StackValues {
    std::array<Ref*, N> values_;
    int uncaught_;
public:
    template <class... L>
    explicit StackValues(L&... values) : values_{&values...}, uncaught_(std::uncaught_exceptions()) {}
    ~StackValues() {
        if (std::uncaught_exceptions() > uncaught_)
            for (Ref* v : values_) *v = Ref{};
    }
    StackValues(const StackValues&) = delete;
    StackValues& operator=(const StackValues&) = delete;
};
template <class... L>
StackValues(L&...) -> StackValues<sizeof...(L)>;

// ---- strings ----
Ref str_new(std::string_view utf8);                          // a new (counted) str
Ref str_from_codepoints(std::u32string_view cps);
const Str* as_str(Obj v);                                    // nullptr unless a str
Ref str_of(Obj v);                                           // str(v)
Ref repr_of(Obj v);                                          // repr(v)

// ---- tuples, lists, dicts ----
Ref tuple_new(std::initializer_list<Obj> items);             // takes new counts of the items
Ref tuple_steal(std::vector<Obj> items);                     // takes over counts already held
Ref tuple_copy(std::span<const Obj> items);                  // takes new counts of the items
Ref list_new(std::initializer_list<Obj> items);
std::int64_t hash_of(Obj v);
// a key's hash for a dict or a set: an unhashable key's TypeError names the container, as
// dict_unhashable_type and set_unhashable_type word it ("cannot use 'list' as a dict key (...)")
std::int64_t dict_key_hash(Obj key);
std::int64_t set_key_hash(Obj key);
std::string fully_qualified_name(const ClassObject* c);     // %T: module.qualname, bare for builtins and __main__
Obj dict_get(Dict* d, Obj key);                              // borrowed, Unset if absent
void dict_set(Dict* d, Obj key, Obj value);                  // takes new counts
void dict_set_hashed(Dict* d, Obj key, std::int64_t hash, Obj value);   // a key's stored hash, not __hash__ again
bool dict_del(Dict* d, Obj key);
Ref dict_new();
Ref dict_copy(Dict* d);                                      // dict.copy() (copy_lock_held)
void dict_merge_dict(Dict* target, Dict* other);             // dict_dict_merge, override: update and {**d}

// ---- names (L2 NameRef kinds) ----
Ref load_fast(const Ref& slot, const char* name);            // UnboundLocalError
Ref load_deref(const Ref& cell, const char* name, bool free);
void store_deref(const Ref& cell, Ref value);
void delete_deref(const Ref& cell, const char* name);
[[noreturn]] Obj unsupported_constant(const char* what);     // a constant the runtime cannot make yet
Obj str_constant_cps(std::initializer_list<char32_t> cps);   // an immortal str with lone surrogates
void delete_fast(Ref& slot, const char* name);
Ref load_global(Module* m, const Str* name);                 // globals, then builtins; NameError
Ref load_name(Obj ns, Module* m, const Str* name);           // the namespace, globals, builtins
void store_name(Obj ns, const Str* name, Ref value);
void store_global(Module* m, const Str* name, Ref value);
void delete_name(Obj ns, const Str* name);
void delete_global(Module* m, const Str* name);
Ref builtin(const char* name);                               // the interpreter's own builtin

// ---- operations ----
enum class BinOp : std::uint8_t { Add, Sub, Mul, TrueDiv, FloorDiv, Mod, Pow, LShift, RShift, And, Or, Xor, MatMul };
enum class CmpOp : std::uint8_t { Lt, Le, Eq, Ne, Gt, Ge, In, NotIn, Is, IsNot };
Ref binary(BinOp op, Obj a, Obj b);
Ref inplace(BinOp op, Obj a, Obj b);
Ref unary_neg(Obj a);
Ref unary_pos(Obj a);
Ref unary_invert(Obj a);
Ref compare(CmpOp op, Obj a, Obj b);
bool truth(Obj v);                                           // TO_BOOL
inline Ref truth_ref(Obj v) { return Ref::steal(boolean(truth(v))); }
inline bool is_true_obj(Obj b) { return b == Obj::of(TRUE); }          // a bool from truth()
inline bool is_true(const Ref& b) { return is_true_obj(b.get()); }
inline bool test(Ref& b) {                       // an If consumes its test
    bool v = is_true(b);
    b = Ref{};
    return v;
}
Ref getattr(Obj obj, const Str* name);
void setattr(Obj obj, const Str* name, Obj value);
void delattr(Obj obj, const Str* name);
Ref getitem(Obj obj, Obj key);
void setitem(Obj obj, Obj key, Obj value);
void delitem(Obj obj, Obj key);
Ref iter(Obj obj);                                           // GET_ITER
Ref for_next(Obj it);                                        // FOR_ITER: Unset at the end
inline bool is_end(const Ref& v) { return v.get().is_unset(); }
void unpack(Obj value, std::span<Ref> targets, int star);    // UNPACK_SEQUENCE / UNPACK_EX
Ref invoke(Obj f, Args a);                                   // any callable (CALL)
Ref invoke(Obj f, std::initializer_list<Obj> pos);
Ref invoke_kw(Obj f, std::initializer_list<Obj> pos, std::initializer_list<const Str*> names,
            std::initializer_list<Obj> values);
Ref call_ex(Obj f, Obj args, Obj kwargs);                    // CALL_FUNCTION_EX; kwargs Unset for none
Ref runtime_call(const char* intrinsic, Obj ns, Module* m, std::initializer_list<Obj> args,
                 std::initializer_list<const Str*> kwnames = {}, std::initializer_list<Obj> kwvalues = {});
Ref build_list(std::initializer_list<Obj> items);
Ref build_tuple(std::initializer_list<Obj> items);
Ref build_map(std::initializer_list<Obj> keys, std::initializer_list<Obj> values);
Ref build_set(std::initializer_list<Obj> items);
void dict_update(Obj target, Obj mapping);                   // DICT_UPDATE ({**m})
void dict_merge(Obj target, Obj mapping, Obj func);          // DICT_MERGE (f(**m)): duplicates fail
void set_add(Obj set, Obj key);                              // takes a new count
void set_add_hashed(Obj set, Obj key, std::int64_t hash);   // a key's stored hash
void set_update(Obj set, Obj iterable);
bool set_contains(SetObject* s, Obj key);
bool set_discard(SetObject* s, Obj key);
Ref set_binary(BinOp op, Obj a, Obj b);                      // | & - ^ of sets and frozensets, else NotImplemented
Ref set_inplace(BinOp op, Obj a, Obj b);                     // |= &= -= ^= of a set
Ref set_compare(CmpOp op, Obj a, Obj b);                     // equality, subset and superset
void init_sets();
void list_append(Obj list, Obj value);
void list_extend(Obj list, Obj value);
Ref list_to_tuple(Obj list);
Ref make_cell(Obj value = Obj{});

// MAKE_FUNCTION: the function object for a code object, with its defaults and closure cells
Ref make_function(const Code& code, Ref (*entry)(PyFunction*, Args), Module* m, Obj defaults,
                  Obj kwdefaults, std::initializer_list<Obj> closure, Obj annotate);
// Binds a call's arguments into the frame's parameter slots as CPython does (TypeError otherwise).
void bind(PyFunction* fn, Args args, std::initializer_list<Ref*> params);

// ---- classes and special methods (runtime/src/types.cpp) ----
void init_types();                                           // the builtin types' attributes
void init_super();                                           // super's methods and members (super.cpp)
Ref super_getattr(Obj su, const Str* name);                  // super_getattro
Ref super_call(Args a);                                      // super(...): super_vectorcall
Ref zero_argument_super(Obj super_name, Obj class_cell, Obj first);   // the `super` intrinsic
Obj type_lookup(ClassObject* c, const Str* name);            // _PyType_Lookup: borrowed, Unset if absent
bool is_subclass(ClassObject* c, ClassObject* base);
bool isinstance(Obj v, ClassObject* c);
// A special method of v's type called with v first; Unset Ref (and *found false) when the type has none.
Ref call_special(Obj v, const char* name, std::initializer_list<Obj> args, bool* found = nullptr);
Ref descr_get(Obj found, Obj obj, Obj type);                 // type(found).__get__(found, obj, type)
// A name CPython has and the runtime lacks yet is refused (bella::NotImplemented), never answered
// with AttributeError or NameError (runtime/src/cpython_names.inc, tools/cpython_names.py): an
// attribute of a built-in class in the MRO, of a class's metatype, of sys or builtins; a global.
void refuse_absent_attribute(Obj obj, const Str* name);
// a store or delete of a name the runtime's classes lack where CPython's built-in base has a data
// descriptor (a member or getset: StopIteration.value): CPython sets the field, never the __dict__
void refuse_absent_data_descriptor(Obj obj, const Str* name);
void refuse_absent_global(const Str* name);
// An operator CPython handles for these operands' types (the table's binop, iop and cmp entries)
// and the runtime does not: refused rather than answered with a TypeError CPython would not raise.
void refuse_unimplemented_operator(const char* scope, Obj a, const std::string& sym, Obj b);
void dict_update_arg(Obj target, Obj arg);                   // dict.update's argument: a mapping or pairs
bool dict_equal(Dict* a, Dict* b);                           // dict == dict: may run __eq__
// What CPython keeps as `owner.name` (its kind: "wrapper_descriptor", "method_descriptor", ...),
// or "" when CPython's type has no such attribute.
std::string_view cpython_attribute_kind(const ClassObject* owner, std::string_view name);
// A special method's argument count, worded as CPython words it for the receiver's type.
void dunder_args(Obj self, Args a, const char* name, std::size_t n);
// The prelude's builtins look like CPython's (docs/emitter.md section 1): an exported function is
// a builtin_function_or_method, never bound as a method; an exported class is immutable.
bool presents_as_builtin(Obj f);
bool immutable_type(const ClassObject* c);
// type(v) and v.__class__: the runtime refuses an object it cannot present as CPython's yet (a
// slot wrapper, which it holds as a method descriptor).
ClassObject* observed_type(Obj v);
std::int64_t index_value(Obj v);                             // operator.index: int, bool, __index__
std::int64_t length_value(Obj v);                            // a __len__ result as len() and truth take it
Ref type_call(ClassObject* cls, Args a);                     // calling a class: __new__, then __init__
Ref type_getattr(ClassObject* cls, const Str* name);         // type_getattro
void type_setattr(ClassObject* cls, const Str* name, Obj value);
bool real_isinstance(Obj inst, Obj cls);                     // _PyObject_RealIsInstance (type.__instancecheck__)
bool real_issubclass(Obj derived, Obj cls);                  // recursive_issubclass (type.__subclasscheck__)
void type_delattr(ClassObject* cls, const Str* name);
Ref generic_getattr(Obj obj, const Str* name);               // PyObject_GenericGetAttr, non-instances
[[noreturn]] void raise_attribute_error(Obj obj, const Str* name, const std::string& message);
Ref load_classdict(Obj mapping, Module* m, const Str* name); // LOAD_FROM_DICT_OR_GLOBALS
Ref load_classdict_free(Obj mapping, const Str* name, const Ref& cell, const char* text);
Obj cell_contents(const Ref& cell);                          // borrowed; Unset when empty
Ref mapping_get(Obj mapping, Obj key);                       // a namespace mapping's item, Unset if absent
void mapping_set(Obj mapping, Obj key, Obj value);

// ---- modules and start-up ----
Module* builtins_module();
Module* new_module(const char* name);
using ModuleBody = Ref (*)(Module* m);
// Runs the program: the runtime, the prelude modules, then the main module; prints an uncaught
// exception's traceback and returns the process's exit status.
int run_main(int argc, char** argv, ModuleBody main_body, std::initializer_list<ModuleBody> prelude);

}  // namespace bella
