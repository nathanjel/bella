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
struct Dict;

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
struct Builtin : Object {                        // a function written in C++
    std::string name;
    NativeFn fn;
    Obj self;                                    // a bound method's object (owned), or Unset
    Builtin(std::string n, NativeFn f, Obj s = Obj{});
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
    enum Of : std::uint8_t { RangeIt, TupleIt, ListIt, StrIt, DictKeysIt } of;
    Obj seq;                                     // owned (Unset once exhausted, as CPython's)
    std::int64_t pos = 0;
    Iterator(Of o, Obj s);
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

struct Dict : Object {                           // CPython's compact dict: indices + entries in insertion order
    struct Entry { std::int64_t hash; Obj key; Obj value; };   // key Unset: deleted
    std::vector<Entry> entries;
    std::vector<std::int64_t> indices;           // -1 empty, -2 dummy, else an entry index
    std::size_t used = 0;
    std::uint64_t version = 0;                   // changes on every mutation (iteration checks)
    Dict();
};

struct Module : Object {
    Ref name;
    Dict* dict;                                  // owned
    explicit Module(const char* n);
};

struct Traceback : Object {                      // one frame's entry; `next` goes deeper
    const Code* code;
    int line;
    std::vector<Ref> locals;                     // the frame's locals, taken over during unwinding
    Ref next;
    Traceback(const Code* c, int l, Ref nx);
};

// ---- the builtin types and singletons (made at start-up) ----
struct Types {
    ClassObject *object, *type, *int_, *bool_, *str, *none, *notimplemented, *ellipsis, *tuple, *list,
        *dict, *cell, *function, *builtin, *method, *range, *range_iterator, *tuple_iterator,
        *list_iterator, *str_iterator, *dict_keyiterator, *module, *traceback, *textio, *float_;
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
struct PyError {
    Ref exc;                                     // the exception instance
};
namespace detail {
inline Obj& raising() {                          // the exception being propagated (for frame guards)
    static Obj in_flight;
    return in_flight;
}
}
[[noreturn]] void raise(Obj exc);                // raise exc (an instance); the caller keeps its count
[[noreturn]] void raise_new(const char* type, const std::string& message);
[[noreturn]] void raise_type(Obj type_or_instance, Obj cause = Obj{}, bool has_cause = false);
ClassObject* exception_class(const char* name);
bool exception_matches(Obj exc, Obj spec);       // except clause matching (a class or a tuple of them)
Obj traceback_of(Obj exc);
[[noreturn]] void reraise();                     // bare `raise`: the exception being handled
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
// destroyed first when an exception unwinds the function: it appends (code, line) to the
// exception's traceback and moves the locals into the entry, where they die with the traceback.
namespace detail {
void record_frame(const Code& code, int line, Ref* const* locals, std::size_t n) noexcept;
void enter_frame();                              // RecursionError past the limit (spec D-17)
void leave_frame() noexcept;
}
template <std::size_t N>
class FrameGuard {
    const Code& code_;
    std::array<Ref*, N> locals_;
    int uncaught_;
public:
    int line;
    template <class... L>
    explicit FrameGuard(const Code& c, L&... locals)
        : code_(c), locals_{&locals...}, uncaught_(std::uncaught_exceptions()), line(c.first_line) {
        detail::enter_frame();
    }
    ~FrameGuard() {
        detail::leave_frame();
        if (std::uncaught_exceptions() > uncaught_) detail::record_frame(code_, line, locals_.data(), N);
    }
    FrameGuard(const FrameGuard&) = delete;
    FrameGuard& operator=(const FrameGuard&) = delete;
};
template <class... L>
FrameGuard(const Code&, L&...) -> FrameGuard<sizeof...(L)>;

// ---- strings ----
Ref str_new(std::string_view utf8);                          // a new (counted) str
Ref str_from_codepoints(std::u32string_view cps);
const Str* as_str(Obj v);                                    // nullptr unless a str
Ref str_of(Obj v);                                           // str(v)
Ref repr_of(Obj v);                                          // repr(v)

// ---- tuples, lists, dicts ----
Ref tuple_new(std::initializer_list<Obj> items);             // takes new counts of the items
Ref tuple_steal(std::vector<Obj> items);                     // takes over counts already held
Ref list_new(std::initializer_list<Obj> items);
std::int64_t hash_of(Obj v);
Obj dict_get(Dict* d, Obj key);                              // borrowed, Unset if absent
void dict_set(Dict* d, Obj key, Obj value);                  // takes new counts
bool dict_del(Dict* d, Obj key);
Ref dict_new();

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
Ref runtime_call(const char* intrinsic, Obj ns, Module* m, std::initializer_list<Obj> args);
Ref build_list(std::initializer_list<Obj> items);
Ref build_tuple(std::initializer_list<Obj> items);
Ref build_map(std::initializer_list<Obj> keys, std::initializer_list<Obj> values);
void list_append(Obj list, Obj value);
void list_extend(Obj list, Obj value);
Ref list_to_tuple(Obj list);
Ref make_cell(Obj value = Obj{});

// MAKE_FUNCTION: the function object for a code object, with its defaults and closure cells
Ref make_function(const Code& code, Ref (*entry)(PyFunction*, Args), Module* m, Obj defaults,
                  Obj kwdefaults, std::initializer_list<Obj> closure, Obj annotate);
// Binds a call's arguments into the frame's parameter slots as CPython does (TypeError otherwise).
void bind(PyFunction* fn, Args args, std::initializer_list<Ref*> params);

// ---- modules and start-up ----
Module* builtins_module();
Module* new_module(const char* name);
using ModuleBody = Ref (*)(Module* m);
// Runs the program: the runtime, the prelude modules, then the main module; prints an uncaught
// exception's traceback and returns the process's exit status.
int run_main(int argc, char** argv, ModuleBody main_body, std::initializer_list<ModuleBody> prelude);

}  // namespace bella
