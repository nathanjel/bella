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
#include <array>

#include "bella/int.hpp"
#include "bella/object.hpp"

#include <array>
#include <cmath>
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
    Module* home = nullptr;                      // a module's function: its __self__ (m_self)
    Ref module_name;                             // its __module__ (m_module), a member a program can set
    Ref written;                                 // a C type's method the prelude writes in Python: what runs (fn is not called)
    bool bound_cmethod = false;                  // METH_METHOD in C: bound, a builtin_method (PyCMethod_Type)
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
// types.MappingProxyType(mapping) holds the mapping and asks it; a class's __dict__ has no dict to hold
struct Proxy : Object {                          // a mappingproxy over a class's own attributes
    ClassObject* of;
    Ref mapping;                                 // what MappingProxyType was given: `of` is then null
    explicit Proxy(ClassObject* c);
    explicit Proxy(Obj given);
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
    std::size_t finger = 0;                      // where set.pop looks next
    bool frozen;
    explicit SetObject(bool frozen_set);
};
struct Method : Object {                         // a bound method: func and self, owned
    Obj func;
    Obj self;
    Method(Obj f, Obj s);
};
struct Range : Object {
    std::int64_t start, stop, step, length;      // all four fit 64 bits: rangeobject.c's fast case
    bool big = false;                            // one does not: these hold the four, and length is clipped
    Ref bstart, bstop, bstep, blength;           // (bigint.cpp; range_field and range_length_big read either)
    Range(std::int64_t a, std::int64_t b, std::int64_t c);
};
struct BigInt : Object {                         // an int outside the immediates: never one that fits them
    bool negative;
    std::vector<std::uint64_t> limbs;            // the magnitude, low limb first, no zero limb on top
    BigInt(bool neg, std::vector<std::uint64_t> mag);
};
struct Iterator : Object {                       // the C++ types' iterators
    enum Of : std::uint8_t { DictRevKeysIt, DictRevValuesIt, DictRevItemsIt, RangeIt, LongRangeIt, TupleIt, ListIt, ListRevIt, StrIt, BytesIt, DictKeysIt, DictValuesIt, DictItemsIt, SeqIt, SetIt } of;
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
struct LazyImport : Object {                      // types.LazyImportType (PEP 810; Objects/lazyimportobject.c)
    Ref builtins;                                // a root's builtins mapping; Unset in a projection
    Ref from;                                    // a root's absolute name, or a projection's source placeholder
    Ref attr;                                    // a root's fromlist (Unset, a str or a tuple), or a projection's attribute
    const Code* code = nullptr;                  // where it was declared
    int line = -1;
    bool active = false;                         // the root was accessed: its declared path requires import semantics
    LazyImport();
};
struct SuperObject : Object {                    // super(type, obj): each owned, Unset for NULL (superobject)
    Obj type;                                    // the class after which the lookup starts (__thisclass__)
    Obj obj;                                     // the instance or class it is bound to (__self__)
    Obj obj_type;                                // obj's type, or obj when it is a class (__self_class__)
    SuperObject();
};
struct BytesObject : Object {                    // bytes and bytearray: their octets; a bytearray's change
    std::string data;
    std::int64_t hash = -1;                      // a bytes's, once computed
    std::int64_t exports = 0;                    // a bytearray's ob_exports: while it is not 0 it cannot change size (re's scanner holds one)
    BytesObject(Kind k, std::string d);
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
    std::vector<const char*> varnames;           // co_varnames: the parameters first, then the other locals
    const char* doc = nullptr;                   // the docstring, or none
    // false for code CPython runs without a frame of its own: the prelude (C functions there)
    // and an inlined comprehension (PEP 709); such a frame never enters a traceback (RL-223/224)
    bool shown = true;
    std::vector<const char*> cellvars;           // co_cellvars and co_freevars (the closure's cells are in freevars' order)
    std::vector<const char*> freevars;
    int flags = 0;                               // co_flags, from the kind of code (specification E-02 as narrowed in v0.14)
    mutable bool module_rebound = false;         // a function of this code had its __module__ rebound: a frame's name is no longer its globals'
    mutable Ref object;                          // its code object, made at the first f.__code__ (one per record: equality is identity)
};

struct CodeObject : Object {                     // `code`: the names and counts of a Code; its bytecode side stops by name
    const Code* code;
    explicit CodeObject(const Code* c);
};

struct PyFunction : Object {
    const Code* code;
    Ref (*entry)(PyFunction* self, Args args);
    Module* module;                              // its globals (the module is immortal in phase 1)
    Ref defaults;                                // a tuple, or Unset
    Ref kwdefaults;                              // a dict, or Unset
    std::vector<Ref> closure;                    // cells, in the order of co_freevars
    Ref closure_tuple;                           // func_closure: the same tuple of those cells at every read, made at the first
    Ref name, qualname, doc, annotate, dict, type_params;
    Ref module_name;                             // func.__module__ once rebound; Unset: its globals' __name__
    PyFunction(const Code* c, Ref (*e)(PyFunction*, Args), Module* m);
};

using Dict = DictObject;                         // object.hpp's: every dict, an instance's __dict__ included

struct Module : Object {
    Ref name;
    Dict* dict;                                  // owned
    Dict* builtins = nullptr;                    // a staged text's, when not the builtins module's own (owned)
    Dict* locals = nullptr;                      // a staged text's namespace when exec gives one of its own (PyEval_EvalCode's locals), else dict (owned)
    explicit Module(const char* n);
    Module(Dict* globals, Dict* given_builtins); // a text's frame, which lives as its functions do: not a module of the program's
};
void forget_module(const Module* m);             // the runtime's own: cleared by nothing at exit
std::vector<Module*>& all_modules();             // every module made, oldest first (immortal: D-19)

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
        *dict, *cell, *function, *builtin, *method, *frozendict, *dict_reversekeyiterator, *dict_reversevalueiterator, *dict_reverseitemiterator, *range, *range_iterator, *longrange_iterator, *tuple_iterator,
        *list_iterator, *str_iterator, *dict_keyiterator, *module, *traceback, *float_, *complex_, *union_, *generator,
        *method_descriptor, *classmethod_descriptor, *wrapper_descriptor, *method_wrapper, *builtin_method, *getset_descriptor, *member_descriptor, *super_, *lazy_import, *mappingproxy, *slice, *iterator, *set,
        *frozenset, *set_iterator, *dict_keys, *dict_values, *dict_items, *dict_valueiterator, *dict_itemiterator,
        *bytes, *bytearray, *bytes_iterator, *bytearray_iterator, *memoryview, *list_reverseiterator, *code;
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
// an object of a built-in kind whose class is a subclass of the program's (decision 2026-11-03: it
// is the built-in's object, with the class's attribute storage: DictInstance)
inline bool is_subclass_instance(Obj v) { return v.is_object() && has_attributes(v.object()); }
std::int64_t str_hash(const Str* s);              // unicode_hash
std::string str_repr_of(const Str* s);            // unicode_repr
Ref str_subscript(Obj self, Obj key);             // unicode_subscript
bool str_contains(Obj self, Obj item);            // PyUnicode_Contains
inline bool is_exact_str(Obj v) { return is_kind(v, Kind::Str) && !has_attributes(v.object()); }   // PyUnicode_CheckExact
inline bool is_exact_tuple(Obj v) { return is_kind(v, Kind::Tuple) && !has_attributes(v.object()); }   // PyTuple_CheckExact
// such an object's class overrides `name`: what its MRO finds is not the built-in's own (CPython
// then gives the subclass a slot that calls the override: slot_mp_subscript and the others)
bool overrides_builtin(Obj v, const char* name);
std::vector<ClassObject*> exception_classes();
ClassObject* new_wrapper_class(Args a, const ClassObject* type);   // tp_new_wrapper's checks
void refuse_shadowed(const std::vector<ClassObject*>& mro, std::size_t from, const Str* name);
std::vector<ClassObject*>& builtin_types();      // every C++ type made at start-up
void init_slots();                               // runtime/src/slots.cpp
Ref list_sort_m(Obj self, Args a);               // runtime/src/sort.cpp
Ref b_sorted(Obj, Args a);
Ref i_lookup_special(Obj, Args a);               // builtins.py's primitives
Ref i_number_index(Obj, Args a);
Ref sequence_concat(Obj self, Obj other);        // sq_concat of str, list, tuple
Ref sequence_repeat(Obj self, Obj count);        // sq_repeat of str, list, tuple
void fill_itertools(Module* m);                   // runtime/src/imports.cpp, running runtime/prelude/itertools.py
void fill_operator(Module* m);                    // and runtime/prelude/_operator.py
void fill_thread(Module* m);                      // and runtime/prelude/_thread.py
void fill_collections(Module* m);                 // and runtime/prelude/_collections.py
void fill_string(Module* m);                      // and runtime/prelude/_string.py
void fill_stat(Module* m);                        // and runtime/prelude/_stat.py
void fill_functools(Module* m);                   // and runtime/prelude/_functools.py
void fill_errno(Module* m);                       // and runtime/prelude/errno.py
bool unicode_is_decimal(std::uint32_t ch);        // runtime/src/unicode.cpp: Py_UNICODE_ISDECIMAL and its kin
bool unicode_is_space(std::uint32_t ch);
bool unicode_is_linebreak(std::uint32_t ch);
bool unicode_is_alnum(std::uint32_t ch);
bool unicode_is_printable(std::uint32_t ch);
bool unicode_is_xid_start(std::uint32_t ch);
bool unicode_is_xid_continue(std::uint32_t ch);
std::uint32_t unicode_to_lower(std::uint32_t ch);
std::uint32_t unicode_to_upper(std::uint32_t ch);
void fill_sre(Module* m);                         // and runtime/prelude/_sre.py, runtime/src/sre.cpp
Ref i_sre_call(Obj, Args a);                      // _sre.py's: the engine, by name
Ref i_present_c_class(Obj, Args a);               // a prelude's: (cls, module) a type with no instances from Python, named for the module
void fill_posix(Module* m);                       // and runtime/prelude/posix.py, runtime/src/posix.cpp
Ref i_posix_sys(Obj, Args a);                     // posix.py's: its system calls, by name
Ref i_structseq(Obj, Args a);                     // a prelude module's: bootstrap.py's _bella_structseq
Ref i_bella_structseq_finish(Obj, Args a);        // bootstrap.py's: makes a type of named tuples look as C makes it
Ref i_bella_pickle_layout(Obj, Args a);           // bootstrap.py's, for object.__reduce_ex__ and __getstate__: what a type's C fields say
Ref i_bella_no_tp_new(Obj, Args a);
Ref i_bella_tp_name_of(Obj, Args a);
Ref i_bella_instance_dict(Obj, Args a);
Ref i_bella_structseq_make(Obj, Args a);          // bootstrap.py's: (cls, items, past), one of them
Ref i_bella_structseq_hidden(Obj, Args a);
Ref call_builtin(Builtin* b, Obj self, Args a);   // a built-in's call: fn, or what the prelude wrote
void check_classmethod_type(const Builtin* b, Obj type);   // classmethod_get's checks of what it binds to
void present_methods(ClassObject* c);             // a prelude's class: its methods are what the names table says
Ref i_keyword_suggestion(Obj, Args a);            // _Py_CalculateSuggestions, for a prelude's messages
void fill_weakref(Module* m);                     // and runtime/prelude/_weakref.py
Ref i_sequence_concat(Obj, Args a);               // runtime/src/ops.cpp
Ref i_sequence_check(Obj, Args a);
Ref i_tp_name(Obj, Args a);
void forget_python_origin(ClassObject* c);
void present_native_class(ClassObject* c, const std::string& module);   // a class of the prelude as the module's C type
std::string keyword_suggestion(const std::string& name, const std::vector<std::string>& known);   // _Py_CalculateSuggestions; "" for none
void fill_abc(Module* m);                        // runtime/src/abc.cpp: the module _abc
// runtime/src/bytes.cpp: bytes, bytearray and the codecs
void init_bytes();
bool is_bytes_like(Obj v);
std::string& bytes_data(Obj v);
Ref bytes_new(std::string_view s);
Obj bytes_constant(const char* data, std::size_t size);   // a module's constant: it keeps the count
Ref bytes_repr(Obj v);
Ref bytes_getitem(Obj self, Obj key);
bool bytes_contains(Obj self, Obj item);
Ref bytes_concat(Obj a, Obj b);
void bytes_iadd(Obj a, Obj b);
Ref bytes_repeat(Obj self, std::int64_t count, bool in_place);
Ref str_from_bytes(Obj source, Obj encoding, Obj errors);
struct CodecHooks { Ref text_encode, text_decode, unknown_handler, start, lookup_text; };   // what _codecs.py gives the runtime (Python/codecs.c's entry points)
struct IoHooks { Ref open, std_stream; };        // what _io.py gives the runtime: builtins.open, and create_stdio
IoHooks& io_hooks();
Ref i_io_call(Obj, Args a);                       // _io.py's: the runtime's part, by name
void fill_io(Module* m);                          // and runtime/prelude/_io.py
void fill_pwd(Module* m);                         // runtime/prelude/pwd.py over posix.cpp
void fill_grp(Module* m);                         // runtime/prelude/grp.py over posix.cpp
void fill_locale(Module* m);                      // runtime/prelude/_locale.py over posix.cpp
void fill_zlib(Module* m);                        // runtime/prelude/zlib.py: its shape; the functions stop by name (L-02)
void fill_ast(Module* m);                         // runtime/prelude/_ast.py: the node classes, presented as ast's
void fill_typing(Module* m);                      // runtime/prelude/_typing.py: typing's C types and PEP 695's intrinsics
void fill_json(Module* m);                        // runtime/prelude/_json.py: the json package's scanner and encoder
void fill_binascii(Module* m);                    // runtime/prelude/binascii.py: base64, hex, crc32; the rest by name
void fill_struct(Module* m);                      // runtime/prelude/_struct.py: the struct module's engine
void fill_time(Module* m);                        // runtime/prelude/time.py: clocks, broken-down time, strftime, the zone
void fill_math_integer(Module* m);                // runtime/prelude/_math_integer.py: math.integer
void fill_math(Module* m);                        // runtime/prelude/math.py, with math.integer's six and the submodule
Dict* intrinsics();                               // what the prelude gives the runtime, not the program (a start-up prelude's or a module's __intrinsics__)
void set_locale_from_environment();               // the start: _Py_SetLocaleFromEnv(LC_CTYPE) and PEP 538's coercion
CodecHooks& codec_hooks();
void ensure_codecs();                             // _codecs has run, and the hooks are set
Ref i_codecs_call(Obj, Args a);                   // _codecs.py's: the codecs here, by name
void fill_codecs(Module* m);                      // and runtime/prelude/_codecs.py
// ---- format (runtime/src/format.cpp) ----
Ref object_format(Obj obj, const Str* spec);      // PyObject_Format
Ref str_mod(Obj format, Obj args);                // PyUnicode_Format
bool is_mapping(Obj v);                           // PyMapping_Check
Ref int_from_number(Obj x);                       // PyNumber_Long
Ref ascii_of(Obj v);                              // PyObject_ASCII
Ref str_format_m(Obj self, Args a);
Ref str_format_map_m(Obj self, Args a);
Ref str_format_dunder(Obj self, Args a);
Ref int_format_dunder(Obj self, Args a);
Ref float_format_dunder(Obj self, Args a);
Ref i_markup_next(Obj, Args a);
Ref i_field_split(Obj, Args a);
Ref i_field_next(Obj, Args a);
Ref number_float(Obj o);                          // PyNumber_Float
std::string int_in_base(Obj v, int base);         // bases 2, 8, 16, with the prefix
Ref build_folded_set(std::initializer_list<Obj> items);   // a set display CPython folds to a frozenset constant
Ref sequence_fast(Obj v, const char* message);   // PySequence_Fast: a list or tuple itself, else a list of its items
std::string utf8_with_errors(Obj text, const char* errors);   // what a text stream writes (UTF-8 mode, D-15)
std::array<std::int64_t, 4> slice_indices(Obj sl, std::int64_t length,    // PySlice_Unpack and AdjustIndices: start, stop, step, count
                                          const char* message = "slice indices must be integers or have an __index__ method");
std::vector<std::string_view> cpython_names_of(std::string_view scope);   // the names table's rows under a scope
void adopt_functions(Module* m);                 // the module's functions say it is theirs (__self__, __module__)
bool object_issubclass(Obj derived, Obj cls);    // PyObject_IsSubclass
// CPython's argument checks by calling convention, each with its message
void noargs(Args a, const std::string& qualname);                     // METH_NOARGS
void onearg(Args a, const std::string& qualname);                     // METH_O
void clinic(Args a, const std::string& name, const std::string& qualname, std::size_t lo, std::size_t hi);
void present_as_c_types(Module* bootstrap);
Ref generic_alias(Obj origin, Obj args);          // Py_GenericAlias (the class is bootstrap.py's)
Ref tuple_subscript(Obj obj, Obj key);            // tuple's own, whatever a subclass says
bool tuple_contains(Obj container, Obj item);
Ref type_or(Obj a, Obj b);                        // _Py_union_type_or (bootstrap.py's)
inline bool is_union(Obj v) { return v.is_object() && v.object()->cls == types().union_; }   // _PyUnion_Check
Ref i_bella_new_instance(Obj, Args a);            // bootstrap.py's: an instance of a C type that has no __new__
Module* native_module_named(const std::string& name);   // a built-in module the program has, or nullptr
std::optional<std::int64_t> cpython_type_number(std::string_view scope, const ClassObject* c);   // flags:, heapflags: of a type written in C
std::optional<std::string_view> cpython_type_text(std::string_view scope, const ClassObject* c);   // a scope's row for a type, as text (offsets:)
std::uint8_t collection_flags_of(const ClassObject* c);   // tp_flags & (Py_TPFLAGS_SEQUENCE | Py_TPFLAGS_MAPPING)
void set_collection_flag_recursive(ClassObject* child, std::uint8_t flag);   // Modules/_abc.c
std::optional<std::string_view> cpython_doc_text(std::string_view name);   // a row of the docstrings' table, if any
Obj cpython_doc(std::string_view name);          // a built-in module's or type's docstring (cpython_names.inc)
bool& shutting_down();                           // finalize_modules has begun: imports fail as CPython's do
Ref i_bella_shutting_down(Obj, Args a);
void add_note(Obj exc, const std::string& text); // _PyErr_FormatNote
// _PyArg_ParseTupleAndKeywords' error for a keyword it does not know, with its suggestion
[[noreturn]] void unexpected_keyword(const std::string& who, const Str* name, std::initializer_list<const char*> known);
Ref type_repr_of(Obj v);                         // type.__repr__ itself
void list_extend_star(Obj list, Obj value);      // LIST_EXTEND
void length_hint(Obj v);                         // PyObject_LengthHint, where a program's class can tell it was asked
Ref repr_unchecked(Obj v);                       // tp_repr, whatever it gives
// calls f with the attribute storage of an Instance or a DictInstance; false for other objects
template <class F>
bool with_attribute_storage(Obj v, F&& f) {
    if (is_kind(v, Kind::Instance)) {
        f(static_cast<Instance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::Dict) && has_attributes(v.object())) {
        f(static_cast<DictInstance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::IntInstance)) {
        f(static_cast<IntInstance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::FloatInstance)) {
        f(static_cast<FloatInstance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::Tuple) && has_attributes(v.object())) {
        f(static_cast<TupleInstance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::Str) && has_attributes(v.object())) {
        f(static_cast<StrInstance*>(v.object()));
        return true;
    }
    if (is_kind(v, Kind::ComplexInstance)) {
        f(static_cast<ComplexInstance*>(v.object()));
        return true;
    }
    return false;
}
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
void report_unraisable(const std::string& context, Obj exc);   // the same, for an exception a prelude caught
void write_stderr(const std::string& text);       // PyFile_WriteString to sys.stderr: nothing when it is None, errors ignored
bool flush_std_stream(const char* name, bool report = false);   // flush_std_files' half for sys.stdout or sys.stderr: false when its flush raised, reported as ignored if asked
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
// What a frame shows to the builtins that read their caller (globals(), a lazy import's declaration).
// A frame CPython does not have (the prelude's, an inlined comprehension's) is not linked in.
struct FrameRecord {
    const Code* code;
    Module* module;
    FrameRecord* caller;
    int line;
};
FrameRecord*& current_frame();
}
template <std::size_t N>
class FrameGuard : public detail::FrameRecord {
    std::array<Ref*, N> locals_;
    int uncaught_;
    std::uint64_t id_ = 0;                       // given when the frame first records an exception
public:
    template <class... L>
    explicit FrameGuard(const Code& c, Module* m, L&... locals)
        : detail::FrameRecord{&c, m, detail::current_frame(), c.first_line}, locals_{&locals...},
          uncaught_(std::uncaught_exceptions()) {
        detail::enter_frame();
        if (c.shown) detail::current_frame() = this;
    }
    void arrived(PyError& e) noexcept { detail::arrive(*code, line, id_, e); }
    ~FrameGuard() {
        detail::leave_frame();
        detail::current_frame() = caller;
        if (std::uncaught_exceptions() > uncaught_) detail::record_frame(*code, line, id_, locals_.data(), N);
    }
    FrameGuard(const FrameGuard&) = delete;
    FrameGuard& operator=(const FrameGuard&) = delete;
};
template <class... L>
FrameGuard(const Code&, Module*, L&...) -> FrameGuard<sizeof...(L)>;

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
inline constexpr std::int64_t SMALL_MIN = -(std::int64_t{1} << 62);   // the int immediates' range
inline constexpr std::int64_t SMALL_MAX = (std::int64_t{1} << 62) - 1;

// ---- int, whatever its size (runtime/src/bigint.cpp; the immediates' arithmetic is int.hpp) ----
// as_int (below) answers for an int that is an immediate's size; is_int for every int.
enum class BinOp : std::uint8_t;
bool is_int(Obj v);                              // PyLong_Check
bool int_fits_i64(Obj v, std::int64_t& out);     // an int within 64 bits, and its value
Ref big_from_i64(std::int64_t v);
inline Ref int_from_i64(std::int64_t v) {        // an exact int
    return v >= SMALL_MIN && v <= SMALL_MAX ? Ref::steal(Obj::small(v)) : big_from_i64(v);
}
bool int_is_negative(Obj v);
bool int_is_zero(Obj v);
Ref int_index_of(Obj v);                         // PyNumber_Index (runtime/src/ops.cpp)
std::int64_t clipped_index(Obj v);               // PyNumber_AsSsize_t(v, NULL), a slice bound's reading
Ref big_binary(BinOp op, Obj a, Obj b);          // every binary operator, on any two ints
Ref big_negate(Obj v);
Ref big_absolute(Obj v);
Ref big_invert(Obj v);
Ref big_plain(Obj v);                            // the value as an exact int
Ref big_divmod(Obj a, Obj b);
Ref big_pow_mod(Obj a, Obj b, Obj mod);          // pow(a, b, mod) on three ints
int big_compare(Obj a, Obj b);                   // -1, 0, 1
double int_as_double(Obj v);                     // PyLong_AsDouble, correctly rounded (bigint.cpp)
Ref int_from_double(double v);                   // PyLong_FromDouble
Ref int_true_divide(Obj a, Obj b);               // long_true_divide, correctly rounded
// ---- float (runtime/src/float.cpp) ----
inline bool is_float(Obj v) { return is_kind(v, Kind::Float) || is_kind(v, Kind::FloatInstance); }   // PyFloat_Check
inline double float_value(Obj v) { return static_cast<const Float*>(v.object())->value; }
inline std::int64_t pointer_hash(const void* o) {   // _Py_HashPointer: the address rotated by 4 bits
    auto p = reinterpret_cast<std::uintptr_t>(o);
    return static_cast<std::int64_t>((p >> 4) | (p << 60));
}
Ref float_ref(double v);                         // an exact float
Obj float_constant(double v);                    // a module's constant: it keeps the count
std::string float_text(double v);                // float_repr
Ref float_binary(BinOp op, Obj a, Obj b);        // nb_add and its kin: an int on either side, NotImplemented for the rest
Ref float_divmod(Obj a, Obj b);
std::int64_t float_hash(Obj self);               // _Py_HashDouble
std::int64_t tuple_hash(const Tuple* t);         // tuple_hash: the items, whatever a subclass says
std::int64_t double_hash(double v, const void* instance);   // _Py_HashDouble(inst, v)
double string_to_double(const char* s, const char* last, const char*& end);   // PyOS_string_to_double on [s, last), no error: `end` says where it stopped
std::string without_underscores(const std::string& given, const char* what, Obj shown);   // _Py_string_to_number_with_underscores's check
double float_as_double(Obj op);                  // PyFloat_AsDouble
void init_float();
// ---- complex (runtime/src/complex.cpp) ----
inline bool is_complex(Obj v) { return is_kind(v, Kind::Complex) || is_kind(v, Kind::ComplexInstance); }   // PyComplex_Check
Ref complex_ref(double real, double imag);       // an exact complex
Obj complex_constant(double real, double imag);  // a module's constant: it keeps the count
bool complex_truth(Obj v);                       // complex_bool
std::int64_t complex_hash(Obj self);
Ref complex_binary(BinOp op, Obj v, Obj w);      // complex_add and its kin, either operand the complex; NotImplemented for the rest
Ref complex_power(Obj v, Obj w, Obj z);          // complex_pow
std::string complex_text(double real, double imag);   // complex_repr (format.cpp)
Ref complex_format_dunder(Obj self, Args a);     // (format.cpp)
void init_complex();
std::int64_t big_hash(Obj v);                    // long_hash
std::string big_text(Obj v);                     // str(v), under the limit of digits
Ref int_round(Obj self, Obj ndigits);            // int.__round__; ndigits may be unset or None
int max_str_digits();                            // sys.get_int_max_str_digits()
Ref int_from_digits(bool negative, std::string_view digits, int base);   // digits valid for the base, no underscores
Obj big_int_constant(const char* text);          // a generated program's literal, decimal or 0x; the caller keeps it
void fill_int_builtins(Dict* builtins);
void fill_int_sys(Dict* sys);
void init_bigint();
// a range's three fields and its length as ints, either kind of range; `which` is 0 start, 1 stop, 2 step
Ref range_from_ints(Obj start, Obj stop, Obj step);   // range_new, from three exact ints
Ref range_field(Obj self, int which);
Ref range_length_big(Obj self);
Ref range_item(Obj self, Obj index);             // compute_range_item, index an exact int
Ref range_slice(Obj self, Obj slice);            // compute_slice
bool range_contains_int(Obj self, Obj item);     // range_contains_long
bool range_equal(Obj a, Obj b);                  // range_equals
std::string big_range_repr(Obj self);
Ref range_iter(Obj self);                        // range_iter: range_iterator, or longrange_iterator past 64 bits
Ref big_range_reversed(Obj self);
Ref long_range_next(std::vector<Obj>& state);    // [the next value, the step, how many are left]; unset at the end
bool as_int(Obj v, std::int64_t& out);                       // an int within the immediates, a bool, a subclass's: its value
// a key's hash for a dict or a set: an unhashable key's TypeError names the container, as
// dict_unhashable_type and set_unhashable_type word it ("cannot use 'list' as a dict key (...)")
std::int64_t dict_key_hash(Obj key, const Dict* into = nullptr);   // its TypeError names a frozendict when it is one
// A frozendict is a dict (Kind::Dict, the same table, views and iterators) with a flag and its own
// class, so that what reads a dict reads it. What writes one asks is_dict (PyDict_Check) or
// is_exact_dict (PyDict_CheckExact); a frozendict is filled only while it is being made.
inline bool is_frozendict(Obj v) { return is_kind(v, Kind::Dict) && (v.object()->flags & FROZEN_DICT) != 0; }
inline bool is_dict(Obj v) { return is_kind(v, Kind::Dict) && (v.object()->flags & FROZEN_DICT) == 0; }
inline bool is_exact_dict(Obj v) { return is_dict(v) && !has_attributes(v.object()); }
inline bool is_exact_frozendict(Obj v) { return is_frozendict(v) && !has_attributes(v.object()); }
Ref frozendict_empty(ClassObject* cls);          // to be filled by its maker; a subclass's has attributes
Ref frozendict_copy(Obj v);                      // anydict_copy: an exact frozendict of v's items
std::int64_t frozendict_hash(Obj v);
Ref dict_reversed(Obj d, int which);             // dictiter_new(PyDictRevIter*_Type): 0 keys, 1 values, 2 items
std::int64_t set_key_hash(Obj key);
std::string fully_qualified_name(const ClassObject* c);     // %T: module.qualname, bare for builtins and __main__
Obj dict_get(Dict* d, Obj key);                              // borrowed, Unset if absent
void dict_set(Dict* d, Obj key, Obj value);                  // takes new counts
void dict_set_hashed(Dict* d, Obj key, std::int64_t hash, Obj value);   // a key's stored hash, not __hash__ again
bool dict_del(Dict* d, Obj key);
Ref dict_new();
Ref dict_copy(Dict* d);                                      // dict.copy() (copy_lock_held)
Ref dict_subscript(Obj self, Obj key);                       // a dict's own d[k]: a subclass's __missing__, else KeyError
Ref dict_iter(Obj self);                                     // a dict's own iterator (dict.__iter__)
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
Ref native_compare(CmpOp op, Obj a, Obj b);      // the C++ types' own comparison and number slots
Ref bytes_compare(CmpOp op, Obj a, Obj b);
Ref compare_one_side(Obj self, Obj other, CmpOp op);   // one operand's method alone: NotImplemented if it declines
Ref native_binary(BinOp op, Obj a, Obj b);
Ref float_compare(CmpOp op, Obj a, Obj b);       // float_richcompare; a is the float
Ref complex_compare(CmpOp op, Obj v, Obj w);     // complex_richcompare, v the complex
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
bool set_contains_hashed(SetObject* s, Obj key, std::int64_t hash);
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
inline bool has_sq_item(Obj v) { return !type_of(v)->mapping_getitem && !type_lookup(type_of(v), intern("__getitem__")).is_unset(); }   // what iter() may fall back on
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
bool c_type(const ClassObject* c);                           // a type of CPython's: static, or one the prelude presents
void note_prelude_class(const ClassObject* c);    // a class the prelude writes in Python for one CPython has in C
// type(v) and v.__class__: the runtime refuses an object it cannot present as CPython's yet (a
// slot wrapper, which it holds as a method descriptor).
ClassObject* observed_type(Obj v);
// PyNumber_AsSsize_t(v, overflow): int, bool, __index__; beyond 64 bits it raises that exception
std::int64_t index_value(Obj v, const char* overflow = "OverflowError");
// a clinic's argument: Py_ssize_t and int, whose OverflowError words it their own way (_PyNumber_Index, PyLong_AsSsize_t, PyLong_AsInt)
std::int64_t ssize_arg(Obj v);
int c_int_arg(Obj v);
std::int64_t length_value(Obj v);                            // a __len__ result as len() and truth take it
Ref type_call(ClassObject* cls, Args a);                     // calling a class: __new__, then __init__
Ref type_getattr(ClassObject* cls, const Str* name);         // type_getattro
void type_setattr(ClassObject* cls, const Str* name, Obj value);
bool real_isinstance(Obj inst, Obj cls);                     // _PyObject_RealIsInstance (type.__instancecheck__)
bool real_issubclass(Obj derived, Obj cls);                  // recursive_issubclass (type.__subclasscheck__)
void type_delattr(ClassObject* cls, const Str* name);
Ref generic_getattr(Obj obj, const Str* name);               // PyObject_GenericGetAttr, non-instances
[[noreturn]] void raise_attribute_error(Obj obj, const Str* name, const std::string& message);
[[noreturn]] void raise_delete_failed(Obj obj, const Str* name, const std::string& what);
Ref load_classdict(Obj mapping, Module* m, const Str* name); // LOAD_FROM_DICT_OR_GLOBALS
Ref load_classdict_free(Obj mapping, const Str* name, const Ref& cell, const char* text);
Obj cell_contents(const Ref& cell);                          // borrowed; Unset when empty
Ref mapping_get(Obj mapping, Obj key);                       // a namespace mapping's item, Unset if absent
void mapping_set(Obj mapping, Obj key, Obj value);

// ---- modules and start-up ----
Module* builtins_module();
Module* new_module(const char* name);
using ModuleBody = Ref (*)(Module* m);
bool is_attribute_error(const PyError& e);
Ref positional_only(Args a, const char* name, std::size_t lo, std::size_t hi);   // a C function's arity check
bool cpython_has(std::string_view scope, std::string_view name);                   // the names table (cpython_names.inc)

// ---- str methods (runtime/src/str.cpp) ----
Ref str_maketrans_m(Obj, Args a);
Ref str_lower_m(Obj self, Args a);
Ref str_casefold_m(Obj self, Args a);
Ref str_upper_m(Obj self, Args a);
Ref str_swapcase_m(Obj self, Args a);
Ref str_capitalize_m(Obj self, Args a);
Ref str_title_m(Obj self, Args a);
Ref str_isalpha_m(Obj self, Args a);
Ref str_isalnum_m(Obj self, Args a);
Ref str_isdigit_m(Obj self, Args a);
Ref str_isdecimal_m(Obj self, Args a);
Ref str_isnumeric_m(Obj self, Args a);
Ref str_isspace_m(Obj self, Args a);
Ref str_isprintable_m(Obj self, Args a);
Ref str_isidentifier_m(Obj self, Args a);
Ref str_islower_m(Obj self, Args a);
Ref str_isupper_m(Obj self, Args a);
Ref str_istitle_m(Obj self, Args a);
Ref str_center_m(Obj self, Args a);
Ref str_ljust_m(Obj self, Args a);
Ref str_rjust_m(Obj self, Args a);
Ref str_zfill_m(Obj self, Args a);
Ref str_removeprefix_m(Obj self, Args a);
Ref str_removesuffix_m(Obj self, Args a);
Ref str_splitlines_m(Obj self, Args a);
Ref str_expandtabs_m(Obj self, Args a);
Ref str_translate_m(Obj self, Args a);
Ref str_getnewargs_m(Obj self, Args a);
Ref str_str_m(Obj self, Args a);
Ref str_find_m(Obj self, Args a);
Ref str_rfind_m(Obj self, Args a);
Ref str_index_m(Obj self, Args a);
Ref str_rindex_m(Obj self, Args a);
Ref str_count_m(Obj self, Args a);
Ref str_isascii_m(Obj self, Args a);
Ref str_startswith_m(Obj self, Args a);
Ref str_endswith_m(Obj self, Args a);
Ref str_partition_m(Obj self, Args a);
Ref str_rpartition_m(Obj self, Args a);
Ref str_split_m(Obj self, Args a);
Ref str_rsplit_m(Obj self, Args a);
Ref str_strip_m(Obj self, Args a);
Ref str_lstrip_m(Obj self, Args a);
Ref str_rstrip_m(Obj self, Args a);
Ref str_replace_m(Obj self, Args a);

// ---- generators (runtime/src/generator.cpp; the emitter's `generator` writes the bodies) ----
enum class GenState : std::uint8_t { Created, Suspended, Executing, Finished };
constexpr int GEN_RETURNED = -1;                 // g->pc when the body has returned
struct Generator : Object {
    const Code* code;
    Module* module;
    Ref (*resume)(Generator*);                   // the state machine: from `pc` to the next yield, or the end
    std::vector<Ref> slots;                      // what must outlive a resume: the frame's locals, then its temporaries
    std::vector<int> ints;                       // the completions and flags the body keeps
    std::vector<std::unique_ptr<PyError>> errors;   // the exception each handler row caught, while it runs
    int pc = 0;                                  // where the next resume goes on
    int handler = 0;                             // the row of the handler table that an exception here goes to
    int line;
    GenState state = GenState::Created;
    bool delegate_ended = false;
    bool thrown_unstarted = false;               // throw() before the first instruction: what it raises leaves as it is
    GenState state_before_resume = GenState::Created;
    std::size_t handling = 0;                    // how many of handled() are this frame's, while it runs
    std::vector<Obj> handled;                    // and those it keeps while suspended (gi_exc_state; owned)
    Ref function;                                // f_funcobj
    Ref name, qualname;
    Ref sent;                                    // what send() passes back
    Ref pending;                                 // what throw() raises at the resume point
    Ref delegate;                                // yield from's iterator
    Ref delegate_shown;                          // what gi_yieldfrom says when it has no iterator of its own to show
    Generator(PyFunction* fn, const Code& c, Ref (*r)(Generator*), std::size_t nslots, std::size_t nints, std::size_t nerrors);
};
Ref make_generator(PyFunction* fn, const Code& c, Ref (*r)(Generator*), std::size_t nslots, std::size_t nints, std::size_t nerrors);
Ref gen_next(Obj gen);                           // gen_iternext: unset when it ended with None
Ref gen_close(Generator* g);
void gen_raise_pending(Generator* g);            // the top of each resume, inside the body's try
void gen_delegate_to(Generator* g, Obj iterable);   // GET_YIELD_FROM_ITER
Ref gen_delegate_step(Generator* g);             // SEND
[[noreturn]] void gen_uncaught(Generator* g, PyError& e);   // an exception leaving the frame: PEP 479
void gen_caught(Generator* g, int k, const PyError& e);
void gen_handling_push(Generator* g, int k);
void gen_handling_pop(Generator* g, int k);
[[noreturn]] void gen_rethrow(Generator* g, int k);
void gen_die(Object* o);
void init_generator();
std::vector<Obj>& handled_exceptions();          // the exceptions being handled, innermost last (exc_info)
// ---- imports (runtime/src/imports.cpp; docs/emitter.md section 7) ----
// A text the staging dry run recorded, compiled by the build (runtime/src/staged.cpp): `body` is null when it
// does not lower yet, and `why` says so. A site's own refusals come from the artefact too.
struct StagedText {
    const char* site;
    const char* kind;
    const char* source;
    std::size_t length;
    bool bytes;
    Ref (*body)(Module*);
    const char* why;
};
struct StagedSite {
    const char* site;
    const char* message;
};
void register_staged(std::span<const StagedText> texts, std::span<const StagedSite> refused, std::span<const StagedSite> unstaged);
Ref b_eval(Obj, Args a);
Ref b_exec(Obj, Args a);
Ref b_compile(Obj, Args a);
// What the build knows of a module: compiled into the program (its body, the file it came from:
// __file__, and whether it is a package: an __init__.py, __path__ its directory), as a source
// file or a frozen module of CPython's; a namespace package, refused when imported; or one the
// manifest omits, which behaves as not installed.
enum class ModuleKind : std::uint8_t { Source, Frozen, Namespace, Omitted, Refused };
struct ModuleEntry {
    const char* name;
    ModuleBody body;
    const char* origin;
    bool package;
    ModuleKind kind;
};
void register_modules(std::span<const ModuleEntry> modules, const char* program_dir);
const std::string& program_directory();          // sys.path[0]: the program's directory
void init_imports(Module* sys);                  // sys.modules, with sys and builtins in it
Dict* sys_modules();                             // the interpreter's sys.modules
Ref import_module_level(Obj name, Obj globals, Obj locals, Obj fromlist, std::int64_t level);
Ref import_name(Obj name, Obj fromlist, Obj level, Obj mode, Module* m, Obj ns);   // IMPORT_NAME
Ref import_from(Obj v, const Str* name);         // IMPORT_FROM
void import_star(Obj v, Obj locals);             // import *
Ref module_getattr(Obj module, const Str* name, bool suppress = false);   // _Py_module_getattro_impl
Ref optional_getattr(Obj obj, const Str* name);  // PyObject_GetOptionalAttr: Unset when absent
Ref lazy_reify(Obj placeholder, const Str* name, Obj ns);   // _PyLazyImport_Reify: resolve and write back
Ref lazy_getattr(Obj lazy, const Str* name);     // lazy_import_getattro
Ref b_lazy_import(Obj, Args a);                  // builtins.__lazy_import__
Ref b_import(Obj, Args a);                       // builtins.__import__
Ref b_dir(Obj, Args a);                          // builtins.dir
Ref module_repr_m(Obj self, Args a);
Ref module_dir_m(Obj self, Args a);
Ref module_dict_get(Obj self);
Ref module_new_m(Obj, Args a);
Ref module_init_m(Obj self, Args a);
ClassObject* builtin_type(const char* name, std::vector<ClassObject*> bases);   // a C++ type's class
void note_native_module(const char* name, Module* m);   // its absent names are refused by the table
std::string_view native_module_name(const Module* m);   // empty for any other module
void set_bootstrap_module(Module* m);
Ref i_bella_ga_get(Obj, Args a);
Ref object_getattribute(Obj self, Args a);
Ref instance_dict_of(Obj self);                  // the __dict__ of a class's instance, by its getset
Ref i_bella_is_builtin(Obj, Args a);
Ref i_bella_create_builtin(Obj, Args a);
Ref i_bella_find(Obj, Args a);                   // bootstrap.py's primitives
Ref i_bella_exec(Obj, Args a);
Ref i_bella_refuse(Obj, Args a);
Ref i_bella_caller_module(Obj, Args a);                      // caller(): the nearest program frame's module name
Ref i_dict_next(Obj, Args a);                                // PyDict_Next for a prelude: (next position, key, value) or None
Ref i_float_pack(Obj, Args a);                               // PyFloat_Pack2/4/8 for a prelude: (x, size, little_endian) -> bytes
Ref i_float_unpack(Obj, Args a);                             // PyFloat_Unpack2/4/8 for a prelude: (data, little_endian) -> float
Ref i_libm(Obj, Args a);                                     // the C library's floating-point functions for a prelude (libm.cpp)
Ref i_bella_import_warning(Obj, Args a);
Ref i_bella_set_lazy_attributes(Obj, Args a);

// A module of the prelude, run before the program as the module it names (builtins, or
// _frozen_importlib for runtime/prelude/bootstrap.py).
struct PreludeModule {
    const char* name;
    ModuleBody body;
};
// Runs the program: the runtime, the prelude modules, then the main module (its __file__, sys.path[0]
// and the modules compiled with it); prints an uncaught exception's traceback and returns the
// process's exit status.
int run_main(int argc, char** argv, ModuleBody main_body, const char* main_file, const char* program_dir,
             std::initializer_list<PreludeModule> prelude, std::span<const ModuleEntry> modules);

}  // namespace bella
