// runtime/src/imports.cpp -- the import system's C half (bella/runtime.hpp; docs/emitter.md
// section 7): IMPORT_NAME, IMPORT_FROM and import * as Python/ceval.c and Python/intrinsics.c run
// them, builtins.__import__ as Python/import.c's PyImport_ImportModuleLevelObject, and the module
// type's attribute access, repr and dir as Objects/moduleobject.c (CPython 3.15.2). Where
// import.c calls into importlib._bootstrap, this calls the prelude's copy of it
// (runtime/prelude/bootstrap.py): _find_and_load and _handle_fromlist. The finder is the closed
// world's registry of compiled modules (spec section 8), which the program's main unit hands over.
#include <pthread.h>
#include <time.h>
#include <unistd.h>

#include <cerrno>

#include "bella/runtime.hpp"

#include <algorithm>
#include <climits>
#include <cstdint>
#include <unordered_map>

namespace bella {
namespace prelude_itertools { Ref module_body(Module* m); }   // runtime/prelude/itertools.py
namespace prelude_operator { Ref module_body(Module* m); }    // runtime/prelude/_operator.py
namespace prelude_thread { Ref module_body(Module* m); }      // runtime/prelude/_thread.py
namespace prelude_collections { Ref module_body(Module* m); } // runtime/prelude/_collections.py
namespace prelude_string { Ref module_body(Module* m); }      // runtime/prelude/_string.py
namespace prelude_stat { Ref module_body(Module* m); }        // runtime/prelude/_stat.py
namespace prelude_functools { Ref module_body(Module* m); }   // runtime/prelude/_functools.py
namespace prelude_errno { Ref module_body(Module* m); }       // runtime/prelude/errno.py
namespace prelude_posix { Ref module_body(Module* m); }       // runtime/prelude/posix.py
namespace prelude_sre { Ref module_body(Module* m); }         // runtime/prelude/_sre.py
namespace prelude_codecs { Ref module_body(Module* m); }      // runtime/prelude/_codecs.py
namespace prelude_io { Ref module_body(Module* m); }          // runtime/prelude/_io.py
namespace prelude_pwd { Ref module_body(Module* m); }         // runtime/prelude/pwd.py
namespace prelude_grp { Ref module_body(Module* m); }         // runtime/prelude/grp.py
namespace prelude_locale { Ref module_body(Module* m); }      // runtime/prelude/_locale.py
namespace prelude_zlib { Ref module_body(Module* m); }        // runtime/prelude/zlib.py
namespace prelude_ast { Ref module_body(Module* m); }         // runtime/prelude/_ast.py
namespace prelude_typing { Ref module_body(Module* m); }      // runtime/prelude/_typing.py
namespace prelude_json { Ref module_body(Module* m); }        // runtime/prelude/_json.py
namespace prelude_binascii { Ref module_body(Module* m); }    // runtime/prelude/binascii.py
namespace prelude_struct { Ref module_body(Module* m); }      // runtime/prelude/_struct.py
namespace prelude_time { Ref module_body(Module* m); }        // runtime/prelude/time.py
namespace prelude_math_integer { Ref module_body(Module* m); }   // runtime/prelude/_math_integer.py
namespace prelude_math { Ref module_body(Module* m); }        // runtime/prelude/math.py
namespace prelude_md5 { Ref module_body(Module* m); }         // runtime/prelude/_md5.py
namespace prelude_sha1 { Ref module_body(Module* m); }        // runtime/prelude/_sha1.py
namespace prelude_sha2 { Ref module_body(Module* m); }        // runtime/prelude/_sha2.py
namespace prelude_sha3 { Ref module_body(Module* m); }        // runtime/prelude/_sha3.py
namespace prelude_blake2 { Ref module_body(Module* m); }      // runtime/prelude/_blake2.py
namespace prelude_hmac { Ref module_body(Module* m); }        // runtime/prelude/_hmac.py
namespace prelude_csv { Ref module_body(Module* m); }         // runtime/prelude/_csv.py
namespace prelude_contextvars { Ref module_body(Module* m); }   // runtime/prelude/_contextvars.py
namespace prelude_bisect { Ref module_body(Module* m); }      // runtime/prelude/_bisect.py
namespace prelude_random { Ref module_body(Module* m); }      // runtime/prelude/_random.py
namespace prelude_statistics { Ref module_body(Module* m); }  // runtime/prelude/_statistics.py
namespace prelude_heapq { Ref module_body(Module* m); }       // runtime/prelude/_heapq.py
namespace prelude_opcode { Ref module_body(Module* m); }      // runtime/prelude/_opcode.py
namespace prelude_warnings { Ref module_body(Module* m); }    // runtime/prelude/_warnings.py
namespace prelude_tokenize { Ref module_body(Module* m); }    // runtime/prelude/_tokenize.py
namespace prelude_imp { Ref module_body(Module* m); }         // runtime/prelude/_imp.py
namespace prelude_weakref { Ref module_body(Module* m); }     // runtime/prelude/_weakref.py

// defined below, with the lazy imports
void clear_lazy_submodule(const std::string& name, bool bind);
void register_lazy_on_parent(const std::string& name, Obj source);
Ref try_load_lazy_submodule(Module* m, const Str* attr_name, bool suppress, bool& recheck_dict);
Ref lazy_import_from(Obj v, const Str* name);

namespace {
const Str* N(const char* s) { return intern(s); }

struct Compiled {
    ModuleBody body;
    std::string origin;
    bool package;
    ModuleKind kind;
};
std::unordered_map<std::string, Compiled>& registry() {
    static std::unordered_map<std::string, Compiled> table;
    return table;
}
std::string& sys_path_0() {                      // the program's directory (config->sys_path_0)
    static std::string dir;
    return dir;
}
Dict*& interp_modules() {                        // interp->modules: the dict sys.modules started as
    static Dict* d = nullptr;
    return d;
}
Obj& import_func() {                             // interp->import_func: builtins.__import__ at start-up
    static Obj f;
    return f;
}
Module*& sys_module() {
    static Module* m = nullptr;
    return m;
}
bool& has_lazy_submodules();
Ref lazy_import_module_level(Obj name, Obj builtins, Obj globals, Obj fromlist, std::int64_t level);
Obj& lazy_import_func() {                        // interp->lazy_import_func
    static Obj f;
    return f;
}
bool has_descr_get(Obj found) {                  // Py_TYPE(descr)->tp_descr_get != NULL
    return !type_lookup(type_of(found), N("__get__")).is_unset();
}

Ref optional_attr(Obj o, const Str* name) { return optional_getattr(o, name); }

Ref import_error(const char* type, const std::string& message, Obj name, Obj path, Obj name_from) {
    Ref msg = str_new(message);
    return invoke_kw(Obj::of(exception_class(type)), {msg.get()}, {N("name"), N("path"), N("name_from")},
                     {name.is_unset() ? None() : name, path.is_unset() ? None() : path,
                      name_from.is_unset() ? None() : name_from});
}

// import_get_module: sys.modules[name] as the interpreter holds it, Unset if absent
Ref get_module(Obj name) {
    Dict* modules = interp_modules();
    if (modules == nullptr) raise_new("RuntimeError", "unable to get sys.modules");
    Obj v = dict_get(modules, name);
    return v.is_unset() ? Ref{} : Ref::share(v);
}

// _PyModuleSpec_IsInitializing: spec._initializing, true by its truth
bool spec_is_initializing(Obj spec) {
    if (spec.is_unset()) return false;
    Ref v = optional_attr(spec, N("_initializing"));
    return !v.get().is_unset() && truth(v.get());
}

// import_ensure_initialized: a module still initialising is waited for; with one thread the
// thread initialising it is this one, so _lock_unlock_module returns at once (bootstrap.py)
bool ensure_initialized(Obj mod) {
    Ref spec = optional_attr(mod, N("__spec__"));
    return !spec.get().is_unset() && spec_is_initializing(spec.get());
}

// PyImport_GetModule
Ref get_initialized_module(Obj name) {
    Ref mod = get_module(name);
    if (!mod.get().is_unset() && mod.get() != None()) {
        ensure_initialized(mod.get());
        Ref check = get_module(name);
        if (check.get() != mod.get()) return Ref{};
    }
    return mod;
}

Ref call_bootstrap(const char* fn, std::initializer_list<Obj> args) {
    Ref f = builtin(fn);
    return invoke(f.get(), args);
}

// PyErr_WarnEx for the import system: the warning goes through the _warnings prelude (runtime/prelude/_warnings.py), imported
// here if the program has not, as the C machinery is always present in CPython; showing it imports the warnings module, as the
// C does, and a program whose closure lacks it stops by name there. The default filters ignore an ImportWarning.
void runtime_warning(const char* category, const std::string& message) {
    Ref warnings_module = Ref::share(dict_get(interp_modules(), Obj::of(N("_warnings"))));
    if (warnings_module.get().is_unset()) warnings_module = import_module_level(Obj::of(N("_warnings")), None(), None(), None(), 0);
    Ref warn = getattr(warnings_module.get(), N("warn"));
    Ref msg = str_new(message);
    invoke(warn.get(), {msg.get(), Obj::of(exception_class(category))});
}
void import_warning(const std::string& message) { runtime_warning("ImportWarning", message); }

// resolve_name: a relative import's absolute name from the importing module's globals
Ref resolve_name(Obj name, Obj globals, std::int64_t level) {
    if (globals.is_unset()) raise_new("KeyError", "'__name__' not in globals");
    if (!is_kind(globals, Kind::Dict)) raise_new("TypeError", "globals must be a dict or a frozendict");
    Dict* g = static_cast<Dict*>(globals.object());
    Ref package = Ref::share(dict_get(g, Obj::of(N("__package__"))));
    if (package.get() == None()) package = Ref{};
    Ref spec = Ref::share(dict_get(g, Obj::of(N("__spec__"))));
    if (!package.get().is_unset()) {
        if (as_str(package.get()) == nullptr) raise_new("TypeError", "package must be a string");
        if (!spec.get().is_unset() && spec.get() != None()) {
            Ref parent = getattr(spec.get(), N("parent"));
            Ref eq = compare(CmpOp::Eq, package.get(), parent.get());
            if (!truth(eq.get())) runtime_warning("DeprecationWarning", "__package__ != __spec__.parent");
        }
    } else if (!spec.get().is_unset() && spec.get() != None()) {
        package = getattr(spec.get(), N("parent"));
        if (as_str(package.get()) == nullptr) raise_new("TypeError", "__spec__.parent must be a string");
    } else {
        import_warning("can't resolve package from __spec__ or __package__, falling back on __name__ and __path__");
        package = Ref::share(dict_get(g, Obj::of(N("__name__"))));
        if (package.get().is_unset()) raise_new("KeyError", "'__name__' not in globals");
        if (as_str(package.get()) == nullptr) raise_new("TypeError", "__name__ must be a string");
        if (dict_get(g, Obj::of(N("__path__"))).is_unset()) {
            const std::string& n = as_str(package.get())->text;
            std::size_t dot = n.rfind('.');
            if (dot == std::string::npos) raise_new("ImportError", "attempted relative import with no known parent package");
            package = str_new(n.substr(0, dot));
        }
    }
    const std::string& pkg = as_str(package.get())->text;
    std::size_t last_dot = pkg.size();
    if (last_dot == 0) raise_new("ImportError", "attempted relative import with no known parent package");
    for (std::int64_t up = 1; up < level; ++up) {
        std::size_t dot = pkg.rfind('.', last_dot - 1);
        if (last_dot == 0 || dot == std::string::npos)
            raise_new("ImportError", "attempted relative import beyond top-level package");
        last_dot = dot;
    }
    std::string base = pkg.substr(0, last_dot);
    const std::string& n = as_str(name)->text;
    return str_new(n.empty() ? base : base + "." + n);
}

// _PyImport_GetAbsName
Ref absolute_name(Obj name, Obj globals, std::int64_t level) {
    if (level > 0) return resolve_name(name, globals, level);
    if (as_str(name)->text.empty()) raise_new("ValueError", "Empty module name");
    return Ref::share(name);
}

std::int64_t level_value(Obj level) {             // PyLong_AsInt
    std::int64_t v;
    if (is_int(level) && !int_fits_i64(level, v)) raise_new("OverflowError", "Python int too large to convert to C int");
    if (!int_fits_i64(level, v)) raise_new("TypeError", "'" + type_of(level)->name + "' object cannot be interpreted as an integer");
    if (v < INT32_MIN || v > INT32_MAX) raise_new("OverflowError", "Python int too large to convert to C int");
    return v;
}

// _PyModuleSpec_GetFileOrigin: spec.origin when spec.has_location and it is a str
Ref spec_file_origin(Obj spec) {
    Ref has = optional_attr(spec, N("has_location"));
    if (has.get().is_unset() || !truth(has.get())) return Ref{};
    Ref origin = optional_attr(spec, N("origin"));
    if (origin.get().is_unset() || as_str(origin.get()) == nullptr) return Ref{};
    return origin;
}

// _PyModule_IsPossiblyShadowing: the module's directory (a package's parent) is sys.path[0]
bool possibly_shadowing(Obj origin) {
    if (origin.is_unset()) return false;
    std::string root = as_str(origin)->text;
    std::size_t sep = root.rfind('/');
    if (sep == std::string::npos) return false;
    if (root.substr(sep + 1) == "__init__.py") {
        root.resize(sep);
        sep = root.rfind('/');
        if (sep == std::string::npos) return false;
    }
    root.resize(sep);
    return !sys_path_0().empty() && root == sys_path_0();
}

bool is_stdlib_name(Obj name) {                   // sys.stdlib_module_names (the names table)
    const Str* s = as_str(name);
    return s != nullptr && cpython_has("stdlib", s->text);
}

std::string quoted(Obj v) { return as_str(repr_of(v).get())->text; }
}  // namespace

// ---- the registry the program's main unit hands over ----
void register_modules(std::span<const ModuleEntry> modules, const char* program_dir) {
    for (const ModuleEntry& e : modules) registry()[e.name] = Compiled{e.body, e.origin, e.package, e.kind};
    sys_path_0() = program_dir;
    // sys.path reflects the build (D-18): the program's directory, where the build found its
    // modules; the standard library's entries come with the standard library (step 3b)
    Ref dir = str_new(program_dir);
    Ref path = list_new({dir.get()});
    dict_set(sys_module()->dict, Obj::of(N("path")), path.get());
}
const std::string& program_directory() { return sys_path_0(); }

Dict* sys_modules() { return interp_modules(); }

// The prelude's primitives for bootstrap.py, which no program can name.
Ref i_bella_find(Obj, Args a) {                  // the registry's (origin, is_package, frozen), or None
    positional_only(a, "_bella_find", 1, 1);
    const Str* name = as_str(a.pos(0));
    auto it = registry().find(name->text);
    if (it != registry().end() && it->second.kind == ModuleKind::Refused)   // frozen in CPython: found whatever the path says
        throw NotImplemented("importing '" + name->text + "' (a frozen module of CPython's the build does not compile: step 3b)");
    if (it == registry().end()) {
        if (is_stdlib_name(a.pos(0)))
            throw NotImplemented("importing '" + name->text + "' (the standard library: step 3b)");
        return none_ref();
    }
    if (it->second.kind == ModuleKind::Omitted) return none_ref();
    if (it->second.kind == ModuleKind::Namespace)              // CPython's NamespaceLoader
        throw NotImplemented("importing '" + name->text + "', a namespace package (step 3b)");
    Ref origin = str_new(it->second.origin);
    return tuple_new({origin.get(), boolean(it->second.package), boolean(it->second.kind == ModuleKind::Frozen)});
}
// what the annotationlib shim asks the runtime (`_bella`, docs/staging.md S-1): the second entry point of an annotate function is
// not in compiled programs yet, so no function has one, and what needs it stops by name instead of failing on the name
Ref i_shim_has_entry_point(Obj, Args a) {
    positional_only(a, "has_entry_point", 1, 1);
    return Ref::steal(boolean(false));
}
Ref i_shim_entry_point(Obj, Args) { throw NotImplemented("annotationlib: an annotate function re-run against other globals (the S-1 second entry point)"); }
Ref i_bella_exec(Obj, Args a) {                  // the compiled body, in the module's namespace
    positional_only(a, "_bella_exec", 2, 2);
    const Str* name = as_str(a.pos(0));
    auto it = registry().find(name->text);
    if (it == registry().end() || !is_kind(a.pos(1), Kind::Module))
        throw NotImplemented("executing a module the program does not have compiled");
    auto* m = static_cast<Module*>(a.pos(1).object());
    // exec(code, module.__dict__): globals without __builtins__ get the calling frame's, the dict
    if (dict_get(m->dict, Obj::of(N("__builtins__"))).is_unset())
        dict_set(m->dict, Obj::of(N("__builtins__")), Obj::of(builtins_module()->dict));
    if (name->text == "annotationlib") {         // the shim's hooks, as the replay's sitecustomize gives them
        Ref hooks = own(new Module("_bella"));
        auto* h = static_cast<Module*>(hooks.get().object());
        for (auto [n, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
                 {"has_entry_point", i_shim_has_entry_point}, {"annotate_freevars", i_shim_entry_point},
                 {"annotate_with", i_shim_entry_point}, {"refuse", i_bella_refuse}}) {
            Ref b = own(new Builtin(n, fn));
            dict_set(h->dict, Obj::of(N(n)), b.get());
        }
        dict_set(m->dict, Obj::of(N("_bella")), hooks.get());
    }
    it->second.body(m);
    return none_ref();
}
// ---- the modules the runtime provides (BuiltinImporter's; manifest: core, mapped) ----
namespace {
Module*& bootstrap_module() {
    static Module* m = nullptr;
    return m;
}
ClassObject* no_instances_yet(const char* name, const char* module = nullptr) {
    ClassObject* c = builtin_type(name, {types().object});
    if (module != nullptr) {
        Obj text = Obj::of(intern(module));
        c->attrs.set(N("__module__"), text);
    }
    return c;
}
// _types (Modules/_typesmodule.c): the types without a builtin name. A type with no instances yet
// (a generator, a code object: step 3b, E-02) exists as a class, as `types` needs it; what CPython
// has of it and the runtime does not is refused by the names table.
void fill_types(Module* m) {
    Types& t = types();
    Dict* d = m->dict;
    auto put = [d](const char* n, ClassObject* c) { dict_set(d, Obj::of(N(n)), Obj::of(c)); };
    dict_set(d, Obj::of(N("__doc__")), Obj::of(intern("Define names for built-in types.")));
    put("AsyncGeneratorType", no_instances_yet("async_generator"));
    put("BuiltinFunctionType", t.builtin);
    put("BuiltinMethodType", t.builtin);
    put("CapsuleType", no_instances_yet("PyCapsule"));
    put("CellType", t.cell);
    put("ClassMethodDescriptorType", t.classmethod_descriptor);
    put("CodeType", no_instances_yet("code"));
    put("CoroutineType", no_instances_yet("coroutine"));
    put("EllipsisType", t.ellipsis);
    put("FrameLocalsProxyType", no_instances_yet("FrameLocalsProxy"));
    put("FrameType", no_instances_yet("frame"));
    put("FunctionType", t.function);
    put("GeneratorType", t.generator);
    dict_set(d, Obj::of(N("GenericAlias")), dict_get(bootstrap_module()->dict, Obj::of(N("GenericAlias"))));
    put("GetSetDescriptorType", t.getset_descriptor);
    put("LambdaType", t.function);
    put("LazyImportType", t.lazy_import);
    put("MappingProxyType", t.mappingproxy);
    put("MemberDescriptorType", t.member_descriptor);
    put("MethodDescriptorType", t.method_descriptor);
    put("MethodType", t.method);
    put("MethodWrapperType", t.method_wrapper);
    put("ModuleType", t.module);
    put("NoneType", t.none);
    put("NotImplementedType", t.notimplemented);
    dict_set(d, Obj::of(N("SimpleNamespace")), dict_get(bootstrap_module()->dict, Obj::of(N("SimpleNamespace"))));
    put("TracebackType", t.traceback);
    dict_set(d, Obj::of(N("UnionType")), dict_get(bootstrap_module()->dict, Obj::of(N("Union"))));
    put("WrapperDescriptorType", t.wrapper_descriptor);
}
struct NativeModule {
    void (*fill)(Module*);
    Module* made = nullptr;
};
std::unordered_map<std::string, NativeModule>& native_registry() {
    static std::unordered_map<std::string, NativeModule> table{{"_types", {fill_types}}, {"_abc", {fill_abc}}, {"itertools", {fill_itertools}}, {"_operator", {fill_operator}}, {"_thread", {fill_thread}}, {"_collections", {fill_collections}}, {"_string", {fill_string}}, {"_stat", {fill_stat}}, {"_functools", {fill_functools}}, {"errno", {fill_errno}}, {"posix", {fill_posix}}, {"_sre", {fill_sre}}, {"_weakref", {fill_weakref}}, {"_codecs", {fill_codecs}}, {"_io", {fill_io}}, {"pwd", {fill_pwd}}, {"grp", {fill_grp}}, {"_locale", {fill_locale}}, {"zlib", {fill_zlib}}, {"_ast", {fill_ast}}, {"_typing", {fill_typing}}, {"_json", {fill_json}}, {"binascii", {fill_binascii}}, {"_struct", {fill_struct}}, {"time", {fill_time}}, {"math.integer", {fill_math_integer}}, {"math", {fill_math}}, {"_md5", {fill_md5}}, {"_sha1", {fill_sha1}}, {"_sha2", {fill_sha2}},
        {"_sha3", {fill_sha3}}, {"_blake2", {fill_blake2}}, {"_hmac", {fill_hmac}}, {"_csv", {fill_csv}}, {"_contextvars", {fill_contextvars}}, {"_bisect", {fill_bisect}}, {"_random", {fill_random}}, {"_statistics", {fill_statistics}}, {"_heapq", {fill_heapq}}, {"_opcode", {fill_opcode}}, {"_warnings", {fill_warnings}}, {"_tokenize", {fill_tokenize}}, {"_imp", {fill_imp}}};
    return table;
}
}  // namespace
// ---- a built-in module written in Python (pipeline/build.py, NATIVE_IN_PYTHON) ----
namespace {
// _PyObject_IsUniquelyReferenced of what an attribute holds: the attribute's count, and this read's
Ref i_held_once(Obj, Args a) {
    positional_only(a, "_held_once", 2, 2);
    Ref value = getattr(a.pos(0), intern(as_str(a.pos(1))->text));
    return Ref::steal(boolean(value.get().is_object() && value.get().object()->refs == 2));
}
Ref i_tuple_set(Obj, Args a) {                   // PyTuple_SET_ITEM and the Py_DECREF of what was there
    positional_only(a, "_tuple_set", 3, 3);
    auto& slot = static_cast<Tuple*>(a.pos(0).object())->items[static_cast<std::size_t>(a.pos(1).small_value())];
    incref(a.pos(2));
    decref(std::exchange(slot, a.pos(2)));
    return none_ref();
}
}  // namespace
Ref i_keyword_suggestion(Obj, Args a) {
    positional_only(a, "_keyword_suggestion", 2, 2);
    std::vector<std::string> known;
    for (Obj n : static_cast<Tuple*>(a.pos(0).object())->items) known.push_back(as_str(n)->text);
    std::string s = keyword_suggestion(as_str(a.pos(1))->text, known);
    return s.empty() ? none_ref() : str_new(s);
}
// _PyArg_UnpackKeywords (Python/getargs.c) for the preludes' clinic functions: _unpack_keywords(fname, names, posonly, minpos,
// maxpos, minkw, args, kwds, absent) answers a list with one slot per name, `absent` where nothing was given, and raises the C's
// TypeErrors in its order: the counts, then each slot in order (a missing required argument where it stands), then an argument
// given by name and position, then the first unexpected keyword with _Py_CalculateSuggestions' hint. `names` lists every
// parameter, the first `posonly` positional-only; minkw counts the required keyword-only ones.
Ref i_cpython_table(Obj, Args a) {               // a row of the names table (tools/cpython_names.py), the pin's build constants among them
    positional_only(a, "_cpython_table", 1, 1);
    Obj doc = cpython_doc(as_str(a.pos(0))->text);
    return doc == None() ? none_ref() : Ref::share(doc);
}
Ref i_source_hash(Obj, Args a) {                 // _imp.source_hash: _Py_KeyedHash's 8 bytes in the machine's order (little-endian here)
    positional_only(a, "_source_hash", 2, 2);
    auto key = static_cast<std::uint64_t>(static_cast<std::int64_t>(index_value(a.pos(0))));   // the C long's bits, a negative key wrapping
    const std::string& data = bytes_data(a.pos(1));
    std::uint64_t h = keyed_hash(key, reinterpret_cast<const unsigned char*>(data.data()), data.size());
    std::string out(8, '\0');
    for (int i = 0; i < 8; ++i) out[static_cast<std::size_t>(i)] = static_cast<char>((h >> (8 * i)) & 0xff);
    return bytes_new(out);
}
Ref i_is_c_type(Obj, Args a) {                   // whether an object's type is CPython's (a static type, a prelude's presented class), not a class of the program's
    positional_only(a, "_is_c_type", 1, 1);
    return Ref::steal(boolean(c_type(type_of(a.pos(0)))));
}
Ref i_as_double(Obj, Args a) {                   // PyFloat_AsDouble for a prelude: a float, __float__ (None included: not callable), __index__
    positional_only(a, "_as_double", 1, 1);
    return float_ref(float_as_double(a.pos(0)));
}
Ref i_unpack_keywords(Obj, Args a) {
    positional_only(a, "_unpack_keywords", 9, 9);
    const std::string fname = as_str(a.pos(0))->text;
    const auto& names = static_cast<Tuple*>(a.pos(1).object())->items;
    auto posonly = static_cast<std::size_t>(index_value(a.pos(2)));
    auto minpos = static_cast<std::size_t>(index_value(a.pos(3)));
    auto maxpos = static_cast<std::size_t>(index_value(a.pos(4)));
    auto minkw = static_cast<std::size_t>(index_value(a.pos(5)));
    const auto& args = static_cast<Tuple*>(a.pos(6).object())->items;
    auto* kwds = static_cast<Dict*>(a.pos(7).object());
    Obj absent = a.pos(8);
    std::size_t nargs = args.size(), nkwargs = kwds->used, maxargs = names.size();
    std::size_t reqlimit = minkw ? maxpos + minkw : minpos, minposonly = std::min(posonly, minpos);
    auto plural = [](std::size_t n) { return n == 1 ? "" : "s"; };
    if (nargs + nkwargs > maxargs)
        raise_new("TypeError", fname + "() takes at most " + std::to_string(maxargs) + " " + (nargs == 0 ? "keyword " : "") + "argument" + plural(maxargs) +
                                   " (" + std::to_string(nargs + nkwargs) + " given)");
    if (nargs > maxpos) {
        if (maxpos == 0) raise_new("TypeError", fname + "() takes no positional arguments");
        raise_new("TypeError", fname + "() takes " + (minpos < maxpos ? "at most " : "exactly ") + std::to_string(maxpos) + " positional argument" + plural(maxpos) +
                                   " (" + std::to_string(nargs) + " given)");
    }
    if (nargs < minposonly)
        raise_new("TypeError", fname + "() takes " + (minposonly < maxpos ? "at least " : "exactly ") + std::to_string(minposonly) + " positional argument" + plural(minposonly) +
                                   " (" + std::to_string(nargs) + " given)");
    std::vector<Obj> buf(maxargs, absent);
    for (std::size_t i = 0; i < nargs; ++i) buf[i] = args[i];
    std::size_t left = nkwargs;
    for (std::size_t i = std::max(nargs, posonly); i < maxargs; ++i) {
        Obj current;
        if (left) current = dict_get(kwds, names[i]);
        else if (i >= reqlimit) break;
        if (!current.is_unset()) {
            buf[i] = current;
            --left;
        } else if (i < minpos || (maxpos <= i && i < reqlimit)) {
            raise_new("TypeError", fname + "() missing required argument '" + as_str(names[i])->text + "' (pos " + std::to_string(i + 1) + ")");
        }
    }
    if (left > 0) {
        for (std::size_t i = posonly; i < nargs; ++i)
            if (!dict_get(kwds, names[i]).is_unset())
                raise_new("TypeError", "argument for " + fname + "() given by name ('" + as_str(names[i])->text + "') and position (" + std::to_string(i + 1) + ")");
        std::vector<std::string> known;
        for (std::size_t i = posonly; i < maxargs; ++i) known.push_back(as_str(names[i])->text);
        for (const auto& e : kwds->entries) {
            if (e.key.is_unset()) continue;
            if (as_str(e.key) == nullptr) raise_new("TypeError", "keywords must be strings");
            const std::string& keyword = as_str(e.key)->text;
            if (std::find(known.begin(), known.end(), keyword) != known.end()) continue;
            std::string suggestion = keyword_suggestion(keyword, known);
            raise_new("TypeError", fname + "() got an unexpected keyword argument '" + keyword + "'" + (suggestion.empty() ? "" : ". Did you mean '" + suggestion + "'?"));
        }
        raise_new("TypeError", "invalid keyword argument for " + fname + "()");
    }
    std::vector<Ref> kept;
    for (Obj v : buf) kept.push_back(Ref::share(v));
    Ref out = list_new({});
    for (Ref& v : kept) list_append(out.get(), v.get());
    return out;
}
// The file runs in a namespace of its own, which its functions keep as their globals, so that the
// module a program sees has CPython's names and nothing else; nothing clears that namespace at exit.
namespace {
Ref i_bella_module_set(Obj self, Args a) {        // (name, value): PyModule_Add on the module the prelude fills, after its import
    positional_only(a, "_bella_module_set", 2, 2);
    dict_set(static_cast<Module*>(self.object())->dict, a.pos(0), a.pos(1));
    return none_ref();
}
void fill_in_python(Module* m, const char* name, const char* types_module, Ref (*body)(Module*),
                    std::initializer_list<std::pair<const char*, NativeFn>> primitives) {
    Module* ns = new_module(name);
    forget_module(ns);
    {                                            // tp_alloc: what a type's __new__ makes its instance with, in every such file
        Ref alloc = own(new Builtin("_bella_new_instance", i_bella_new_instance));
        dict_set(ns->dict, Obj::of(N("_bella_new_instance")), alloc.get());
        Ref setter = own(new Builtin("_bella_module_set", i_bella_module_set, Obj::of(m), Binding::Function));   // PyModule_Add, later
        dict_set(ns->dict, Obj::of(N("_bella_module_set")), setter.get());
        Ref unpack = own(new Builtin("_unpack_keywords", i_unpack_keywords));   // _PyArg_UnpackKeywords, in every such file
        dict_set(ns->dict, Obj::of(N("_unpack_keywords")), unpack.get());
        Ref index = own(new Builtin("_number_index", i_number_index));   // PyNumber_Index, with its messages, in every such file
        dict_set(ns->dict, Obj::of(N("_number_index")), index.get());
        Ref as_double = own(new Builtin("_as_double", i_as_double));   // PyFloat_AsDouble, with its messages, in every such file
        dict_set(ns->dict, Obj::of(N("_as_double")), as_double.get());
        Ref c_type = own(new Builtin("_is_c_type", i_is_c_type));   // a C type under the object, not a class of the program's
        dict_set(ns->dict, Obj::of(N("_is_c_type")), c_type.get());
        Ref suggest = own(new Builtin("_keyword_suggestion", i_keyword_suggestion));   // _Py_CalculateSuggestions, in every such file
        dict_set(ns->dict, Obj::of(N("_keyword_suggestion")), suggest.get());
    }
    for (auto [primitive, fn] : primitives) {
        Ref b = own(new Builtin(primitive, fn));
        dict_set(ns->dict, Obj::of(N(primitive)), b.get());
    }
    body(ns);
    if (Obj intr = dict_get(ns->dict, Obj::of(N("__intrinsics__"))); !intr.is_unset())   // what the runtime calls by name, not the module's
        for (Obj n : static_cast<List*>(intr.object())->items) dict_set(intrinsics(), n, dict_get(ns->dict, n));
    if (Obj hidden = dict_get(ns->dict, Obj::of(N("__hidden_classes__"))); !hidden.is_unset())   // a C type of no module's namespace
        for (Obj n : static_cast<List*>(hidden.object())->items) {                               // (_typing._ConstEvaluator): its own module
            auto* c = static_cast<ClassObject*>(dict_get(ns->dict, n).object());
            const Obj* own = c->attrs.find(N("__module__"));
            present_native_class(c, own != nullptr && as_str(*own) != nullptr ? as_str(*own)->text : std::string(types_module));
            c->disallow_instantiation = cpython_attribute_kind(c, "__new__").empty();
        }
    for (Obj n : static_cast<List*>(dict_get(ns->dict, Obj::of(N("__all__"))).object())->items) {
        Obj v = dict_get(ns->dict, n);
        if (is_kind(v, Kind::Class) && !c_type(static_cast<ClassObject*>(v.object()))) {   // a class may have two names
            auto* c = static_cast<ClassObject*>(v.object());
            const Obj* own = c->attrs.find(N("__module__"));   // the class statement's __module__ is the file's name; the type's is its tp_name's
            if (own != nullptr && as_str(*own) != nullptr && as_str(*own)->text == name && std::string_view(name) != types_module)
                c->set_attr(N("__module__"), Obj::of(intern(types_module)));
            present_native_class(c, types_module);
            if (auto flags = cpython_type_number("flags", c); flags && (*flags & (1 << 7)))    // Py_TPFLAGS_DISALLOW_INSTANTIATION
                c->disallow_instantiation = true;                                               // (_md5.md5, _hmac.HMAC): made by a function alone
        }
        if (is_kind(v, Kind::PyFunction)) v.object()->cls = types().builtin;
        dict_set(m->dict, n, v);
    }
    if (Obj doc = cpython_doc(name); doc != None())   // the module's docstring is CPython's; an empty row says CPython has None
        dict_set(m->dict, Obj::of(N("__doc__")), as_str(doc)->text.empty() ? None() : doc);
}
}  // namespace
void fill_itertools(Module* m) {
    fill_in_python(m, "itertools", "itertools", prelude_itertools::module_body,
                   {{"_number_index", i_number_index}, {"_held_once", i_held_once}, {"_tuple_set", i_tuple_set}, {"_keyword_suggestion", i_keyword_suggestion}});
}
// _weakref's primitives: the object model's lists (object.hpp), as the prelude's file reads them
namespace {
WeakKind weak_kind_of(Obj k) { return static_cast<WeakKind>(k.small_value()); }
Ref i_weak_supported(Obj, Args a) {              // _PyType_SUPPORTS_WEAKREFS
    positional_only(a, "_weak_supported", 1, 1);
    return Ref::steal(boolean(type_of(a.pos(0))->has_weakref));
}
Ref i_weak_basic(Obj, Args a) {
    positional_only(a, "_weak_basic", 2, 2);
    Object* found = weak_basic(a.pos(0).object(), weak_kind_of(a.pos(1)));
    return found == nullptr ? none_ref() : Ref::share(Obj::of(found));
}
Ref i_weak_link(Obj, Args a) {
    positional_only(a, "_weak_link", 4, 4);
    weak_link(a.pos(0).object(), a.pos(1).object(), a.pos(2) == None() ? Obj{} : a.pos(2), weak_kind_of(a.pos(3)));
    return none_ref();
}
Ref i_weak_get(Obj, Args a) {
    positional_only(a, "_weak_get", 1, 1);
    if (!a.pos(0).is_object()) return none_ref();
    WeakRecord* r = weak_record(a.pos(0).object());
    return r == nullptr || r->target == nullptr ? none_ref() : Ref::share(Obj::of(r->target));
}
Ref weak_callback_member(Obj self) {
    WeakRecord* r = weak_record(self.object());
    return r == nullptr || r->callback == 0 ? none_ref() : Ref::share(Obj::of(reinterpret_cast<const Object*>(r->callback)));
}
Ref i_weak_list(Obj, Args a) {
    positional_only(a, "_weak_list", 1, 1);
    Ref out = list_new({});
    if (a.pos(0).is_object())
        if (auto* list = weak_list(a.pos(0).object()))
            for (WeakRecord* r : *list)
                if (r->holder->refs > 0) list_append(out.get(), Obj::of(r->holder));
    return out;
}
}  // namespace
void fill_weakref(Module* m) {                   // the types are named for `weakref`, as CPython's are
    fill_in_python(m, "_weakref", "weakref", prelude_weakref::module_body,
                   {{"_number_index", i_number_index}, {"_lookup_special", i_lookup_special}, {"_tp_name", i_tp_name}, {"_weak_supported", i_weak_supported},
                    {"_weak_basic", i_weak_basic}, {"_weak_link", i_weak_link}, {"_weak_get", i_weak_get}, {"_weak_list", i_weak_list}});
    for (const char* n : {"ProxyType", "CallableProxyType"}) {
        auto* c = static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N(n))).object());
        c->forwards_attributes = true;
        c->weak_proxy = true;
        c->disallow_instantiation = true;        // no tp_new: only proxy() makes one
    }
    auto* ref = static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N("ReferenceType"))).object());
    auto* member = new GetSet("__callback__", ref, weak_callback_member, nullptr);   // PyMemberDef in CPython
    member->cls = types().member_descriptor;
    ref->attrs.set(N("__callback__"), Obj::of(member));
}
// the one thread, and the wait that no other thread can end
Ref i_thread_ident(Obj, Args a) {
    positional_only(a, "_thread_ident", 0, 0);
    return int_from_i64(static_cast<std::int64_t>(pthread_self()));
}
Ref i_native_thread_id(Obj, Args a) {
    positional_only(a, "_native_thread_id", 0, 0);
    return int_from_i64(gettid());
}
Ref i_sleep_ns(Obj, Args a) {
    positional_only(a, "_sleep_ns", 1, 1);
    std::int64_t ns = clipped_index(a.pos(0));
    timespec left{.tv_sec = static_cast<time_t>(ns / 1000000000), .tv_nsec = static_cast<long>(ns % 1000000000)};
    while (nanosleep(&left, &left) != 0 && errno == EINTR) {
    }
    return none_ref();
}
Ref handle_ident(Obj self) { return getattr(self, N("_a_ident")); }
Ref local_getattribute(Obj self, Args a) {       // local_getattro: the rest is the generic path's
    if (a.npos == 1 && a.nkw == 0 && as_str(a.pos(0)) != nullptr && as_str(a.pos(0))->text == "__dict__") return instance_dict_of(self);
    return object_getattribute(self, a);
}
void fill_thread(Module* m) {
    fill_in_python(m, "_thread", "_thread", prelude_thread::module_body,
                   {{"_number_index", i_number_index}, {"_sequence_check", i_sequence_check}, {"_tp_name", i_tp_name}, {"_thread_ident", i_thread_ident},
                    {"_native_thread_id", i_native_thread_id}, {"_sleep_ns", i_sleep_ns}, {"_bella_refuse", i_bella_refuse}});
    auto* local = static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N("_local"))).object());
    Ref dict_getset = Ref::steal(local->attrs.pop(N("__dict__")));   // local_getattro answers for __dict__: the type has no getset
    Ref self_reference = Ref::steal(local->attrs.pop(N("_a_self_reference")));
    local->dict_without_getset = true;
    auto* getattribute = new Builtin("__getattribute__", local_getattribute, Obj{}, Binding::Method);
    getattribute->owner = local;
    getattribute->flags |= IMMORTAL;
    local->attrs.set(N("__getattribute__"), Obj::of(getattribute));
    present_methods(local);
    auto* handle = static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N("_ThreadHandle"))).object());
    handle->attrs.set(N("ident"), Obj::of(new GetSet("ident", handle, handle_ident, nullptr)));
}
// Py_ReprEnter and Py_ReprLeave: one list, with the containers' own (builtins.py)
Ref i_repr_enter(Obj, Args a) {
    positional_only(a, "_repr_enter", 1, 1);
    return invoke(builtin("_enter").get(), {a.pos(0)});
}
Ref i_repr_leave(Obj, Args a) {
    positional_only(a, "_repr_leave", 1, 1);
    return invoke(builtin("_leave").get(), {a.pos(0)});
}
// _count_elements' fast path: each key hashed once, whatever its __hash__ does
Ref i_count_element(Obj, Args a) {
    positional_only(a, "_count_element", 2, 2);
    Obj key = a.pos(1);
    std::int64_t h = hash_of(key);
    auto* d = static_cast<Dict*>(a.pos(0).object());
    Obj old = dict_find(d, key, h);
    Ref one = int_from_i64(1);
    if (old.is_unset()) {
        dict_set_hashed(d, key, h, one.get());
    } else {
        Ref held = Ref::share(old);
        Ref sum = binary(BinOp::Add, held.get(), one.get());
        dict_set_hashed(d, key, h, sum.get());
    }
    return none_ref();
}
Ref deque_maxlen(Obj self) {                     // deque_get_maxlen
    Ref bound = getattr(self, N("_c_maxlen"));
    return bound.get().is_small() && bound.get().small_value() < 0 ? none_ref() : bound;
}
Ref factory_get(Obj self) {                      // a T_OBJECT member: None when there is none
    Ref value = optional_getattr(self, N("_a_factory"));
    return value.get().is_unset() ? none_ref() : value;
}
void factory_set(Obj self, Obj value) {
    if (!value.is_unset()) {
        setattr(self, N("_a_factory"), value);
    } else if (!optional_getattr(self, N("_a_factory")).get().is_unset()) {
        delattr(self, N("_a_factory"));
    }
}
Ref getter_doc(Obj self) { return getattr(self, N("_b_doc")); }
void getter_doc_set(Obj self, Obj value) {
    setattr(self, N("_b_doc"), value.is_unset() ? None() : value);
}
void fill_collections(Module* m) {               // its types are named for `collections`, the module that shows them
    fill_in_python(m, "_collections", "collections", prelude_collections::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_bella_refuse", i_bella_refuse}, {"_count_element", i_count_element},
                    {"_repr_enter", i_repr_enter}, {"_repr_leave", i_repr_leave}});
    auto cls = [&](const char* n) { return static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N(n))).object()); };
    cls("deque")->sequence_slots = true;
    auto member = [](ClassObject* c, const char* name, Ref (*get)(Obj), void (*set)(Obj, Obj)) {
        auto* g = new GetSet(name, c, get, set);
        g->cls = types().member_descriptor;
        g->deletable = true;
        c->attrs.set(N(name), Obj::of(g));
    };
    cls("deque")->attrs.set(N("maxlen"), Obj::of(new GetSet("maxlen", cls("deque"), deque_maxlen, nullptr)));
    member(cls("defaultdict"), "default_factory", factory_get, factory_set);
    member(cls("_tuplegetter"), "__doc__", getter_doc, getter_doc_set);
}
// _functools's primitives
Ref i_has_dict(Obj, Args a) {                    // the C's self->dict is not NULL: an attribute set, or __dict__ asked for
    positional_only(a, "_has_dict", 1, 1);
    bool has = false;
    with_attribute_storage(a.pos(0), [&](auto* inst) { has = inst->dict != nullptr || inst->exposed() || !inst->order.empty(); });
    return Ref::steal(boolean(has));
}
Ref i_method_new(Obj, Args a) {                  // PyMethod_New
    positional_only(a, "_method_new", 2, 2);
    return own(new Method(a.pos(0), a.pos(1)));
}
Ref i_hash_of(Obj, Args a) {
    positional_only(a, "_hash_of", 1, 1);
    return int_from_i64(hash_of(a.pos(0)));
}
Ref i_get_hashed(Obj, Args a) {                  // (dict, key, hash, default)
    positional_only(a, "_get_hashed", 4, 4);
    std::int64_t h = 0;
    int_fits_i64(a.pos(2), h);
    Obj found = dict_find(static_cast<Dict*>(a.pos(0).object()), a.pos(1), h);
    return Ref::share(found.is_unset() ? a.pos(3) : found);
}
Ref i_set_hashed(Obj, Args a) {                  // (dict, key, hash, value)
    positional_only(a, "_set_hashed", 4, 4);
    std::int64_t h = 0;
    int_fits_i64(a.pos(2), h);
    dict_set_hashed(static_cast<Dict*>(a.pos(0).object()), a.pos(1), h, a.pos(3));
    return none_ref();
}
Ref i_pop_hashed(Obj, Args a) {                  // (dict, key, hash, default)
    positional_only(a, "_pop_hashed", 4, 4);
    std::int64_t h = 0;
    int_fits_i64(a.pos(2), h);
    Obj found = dict_pop(static_cast<Dict*>(a.pos(0).object()), a.pos(1), h);
    if (found.is_unset()) return Ref::share(a.pos(3));
    return Ref::steal(found);
}
Ref i_is_callable(Obj, Args a) {                 // PyCallable_Check
    positional_only(a, "_is_callable", 1, 1);
    Obj v = a.pos(0);
    Kind k = v.is_object() ? v.object()->kind : Kind::Bool;
    if (k == Kind::PyFunction || k == Kind::Builtin || k == Kind::Method || k == Kind::Class || k == Kind::Function) return Ref::steal(boolean(true));
    return Ref::steal(boolean(!type_lookup(type_of(v), N("__call__")).is_unset()));
}
Ref key_obj_get(Obj self) {                      // keyobject's member: unset reads as None, and del unsets it
    Ref v = optional_getattr(self, N("_k_obj"));
    return v.get().is_unset() ? none_ref() : v;
}
void key_obj_set(Obj self, Obj value) {
    if (!value.is_unset()) setattr(self, N("_k_obj"), value);
    else if (!optional_getattr(self, N("_k_obj")).get().is_unset()) delattr(self, N("_k_obj"));
}
void fill_functools(Module* m) {
    fill_in_python(m, "_functools", "functools", prelude_functools::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_repr_enter", i_repr_enter}, {"_repr_leave", i_repr_leave},
                    {"_bella_new_instance", i_bella_new_instance}, {"_has_dict", i_has_dict}, {"_method_new", i_method_new}, {"_hash_of", i_hash_of},
                    {"_get_hashed", i_get_hashed}, {"_set_hashed", i_set_hashed}, {"_pop_hashed", i_pop_hashed}, {"_is_callable", i_is_callable}});
    auto* key = static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N("KeyWrapper"))).object());
    key->disallow_instantiation = true;
    dict_del(m->dict, Obj::of(N("KeyWrapper")));   // it is no name of the module's
    auto* g = new GetSet("obj", key, key_obj_get, key_obj_set);
    g->cls = types().member_descriptor;
    g->deletable = true;
    key->attrs.set(N("obj"), Obj::of(g));
}
void fill_sre(Module* m) {
    fill_in_python(m, "_sre", "_sre", prelude_sre::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion}, {"_sre_call", i_sre_call}, {"_present", i_present_c_class}});
}
void fill_codecs(Module* m) {
    fill_in_python(m, "_codecs", "_codecs", prelude_codecs::module_body,
                   {{"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion}, {"_codecs_call", i_codecs_call}});
}
IoHooks& io_hooks() {
    static IoHooks hooks;
    return hooks;
}
Ref i_io_call(Obj, Args a) {                      // _io_call(name, ...)
    const std::string& name = as_str(a.pos(0))->text;
    Args r{a.data + 1, a.npos - 1, nullptr, 0};
    if (name == "refuse") throw NotImplemented(as_str(r.pos(0))->text);
    if (name == "unraisable") {                  // (context, exception): PyErr_FormatUnraisable
        report_unraisable(as_str(r.pos(0))->text, r.pos(1));
        return none_ref();
    }
    if (name == "lookup_text") {                 // _PyCodec_LookupTextEncoding(encoding, NULL)
        ensure_codecs();
        return invoke(codec_hooks().lookup_text.get(), {r.pos(0), None()});
    }
    if (name == "hooks") {                       // (open, std_stream)
        io_hooks().open = Ref::share(r.pos(0));
        io_hooks().std_stream = Ref::share(r.pos(1));
        return none_ref();
    }
    throw NotImplemented("_io primitive " + name);
}
void fill_io(Module* m) {
    fill_in_python(m, "_io", "_io", prelude_io::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion}, {"_sys", i_posix_sys}, {"_io_call", i_io_call}});
    dict_set(m->dict, Obj::of(N("BlockingIOError")), Obj::of(exception_class("BlockingIOError")));
}
void fill_pwd(Module* m) {
    fill_in_python(m, "pwd", "pwd", prelude_pwd::module_body, {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_structseq", i_structseq}, {"_sys", i_posix_sys}});
}
void fill_grp(Module* m) {
    fill_in_python(m, "grp", "grp", prelude_grp::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_structseq", i_structseq}, {"_sys", i_posix_sys}});
}
void fill_locale(Module* m) {
    fill_in_python(m, "_locale", "_locale", prelude_locale::module_body, {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_sys", i_posix_sys}});
}
void fill_zlib(Module* m) {
    fill_in_python(m, "zlib", "zlib", prelude_zlib::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_number_index", i_number_index}, {"_zlib", i_zlib}});
}
void fill_ast(Module* m) { fill_in_python(m, "_ast", "ast", prelude_ast::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}}); }
Ref i_bella_bootstrap(Obj, Args a) {             // a call of _frozen_importlib's function by name: what the prelude shares with bootstrap.py
    if (a.npos < 1 || a.nkw != 0) raise_new("TypeError", "_bella_bootstrap() takes a name and positional arguments");
    Obj fn = dict_get(bootstrap_module()->dict, Obj::of(intern(as_str(a.pos(0))->text)));
    if (fn.is_unset()) raise_new("SystemError", "no " + as_str(a.pos(0))->text + " in _frozen_importlib");
    std::vector<Obj> rest;
    for (std::size_t i = 1; i < a.npos; ++i) rest.push_back(a.pos(i));
    return invoke(fn, Args{rest.data(), rest.size(), nullptr, 0});
}
Ref i_bella_class_set(Obj, Args a) {             // a store into a type's dict as C makes one: a member a class statement cannot declare (__qualname__)
    positional_only(a, "_bella_class_set", 3, 3);
    if (!is_kind(a.pos(0), Kind::Class)) raise_new("TypeError", "_bella_class_set() needs a class");
    static_cast<ClassObject*>(a.pos(0).object())->set_attr(intern(as_str(a.pos(1))->text), a.pos(2));
    return none_ref();
}
void fill_json(Module* m) {
    fill_in_python(m, "_json", "_json", prelude_json::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_dict_next", i_dict_next}});
}
void fill_binascii(Module* m) {
    fill_in_python(m, "binascii", "binascii", prelude_binascii::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion}});
}
void fill_struct(Module* m) {
    fill_in_python(m, "_struct", "_struct", prelude_struct::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion},
                    {"_float_pack", i_float_pack}, {"_float_unpack", i_float_unpack}});
}
void fill_time(Module* m) {
    fill_in_python(m, "time", "time", prelude_time::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_bella_bootstrap", i_bella_bootstrap}, {"_tp_name", i_tp_name}, {"_structseq", i_structseq},
                    {"_sys", i_posix_sys}});
}
void fill_math_integer(Module* m) {
    fill_in_python(m, "math.integer", "math.integer", prelude_math_integer::module_body, {{"_tp_name", i_tp_name}});
}
void fill_math(Module* m) {                      // math_exec: the module, then math.integer's six functions and the submodule itself
    fill_in_python(m, "math", "math", prelude_math::module_body,
                   {{"_tp_name", i_tp_name}, {"_libm", i_libm}, {"_float_pack", i_float_pack}, {"_float_unpack", i_float_unpack},
                    {"_keyword_suggestion", i_keyword_suggestion}});
    NativeModule& n = native_registry().at("math.integer");
    if (n.made == nullptr) {
        n.made = new_module("math.integer");
        note_native_module("math.integer", n.made);
        n.fill(n.made);
        adopt_functions(n.made);
    }
    Ref key = str_new("math.integer");
    dict_set(sys_modules(), key.get(), Obj::of(n.made));   // _PyImport_SetModuleString("math.integer", intmath)
    for (const char* name : {"comb", "factorial", "gcd", "isqrt", "lcm", "perm"}) dict_set(m->dict, Obj::of(N(name)), dict_get(n.made->dict, Obj::of(N(name))));
    dict_set(m->dict, Obj::of(N("integer")), Obj::of(n.made));
}
namespace {
void fill_digest(Module* m, const char* name, Ref (*body)(Module*)) {   // the digest modules share their primitives (hashes.cpp)
    fill_in_python(m, name, name, body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion},
                    {"_hash_new", i_hash_new}, {"_hash_update", i_hash_update}, {"_hash_digest", i_hash_digest}, {"_hash_xof", i_hash_xof}});
}
}  // namespace
void fill_md5(Module* m) { fill_digest(m, "_md5", prelude_md5::module_body); }
void fill_sha1(Module* m) { fill_digest(m, "_sha1", prelude_sha1::module_body); }
void fill_sha2(Module* m) { fill_digest(m, "_sha2", prelude_sha2::module_body); }
void fill_sha3(Module* m) { fill_digest(m, "_sha3", prelude_sha3::module_body); }
void fill_blake2(Module* m) { fill_digest(m, "_blake2", prelude_blake2::module_body); }
void fill_hmac(Module* m) { fill_digest(m, "_hmac", prelude_hmac::module_body); }
void fill_csv(Module* m) { fill_in_python(m, "_csv", "_csv", prelude_csv::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}}); }
void fill_bisect(Module* m) {
    fill_in_python(m, "_bisect", "_bisect", prelude_bisect::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_number_index", i_number_index}});
}
void fill_random(Module* m) {
    fill_in_python(m, "_random", "_random", prelude_random::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_number_index", i_number_index}, {"_sys", i_posix_sys}});
}
void fill_statistics(Module* m) {
    fill_in_python(m, "_statistics", "_statistics", prelude_statistics::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_number_index", i_number_index}, {"_libm", i_libm}});
}
void fill_heapq(Module* m) { fill_in_python(m, "_heapq", "_heapq", prelude_heapq::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}}); }
void fill_opcode(Module* m) {
    fill_in_python(m, "_opcode", "_opcode", prelude_opcode::module_body, {{"_bella_refuse", i_bella_refuse}, {"_number_index", i_number_index}});
}
void fill_warnings(Module* m) {
    fill_in_python(m, "_warnings", "_warnings", prelude_warnings::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_number_index", i_number_index}, {"_frame", i_warnings_frame}});
}
void fill_tokenize(Module* m) { fill_in_python(m, "_tokenize", "_tokenize", prelude_tokenize::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}}); }
void fill_imp(Module* m) {
    fill_in_python(m, "_imp", "_imp", prelude_imp::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_cpython_table", i_cpython_table}, {"_source_hash", i_source_hash},
                    {"_bella_create_builtin", i_bella_create_builtin}, {"_bella_set_lazy_attributes", i_bella_set_lazy_attributes}});
}
void fill_contextvars(Module* m) { fill_in_python(m, "_contextvars", "_contextvars", prelude_contextvars::module_body, {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}}); }
void fill_typing(Module* m) {
    fill_in_python(m, "_typing", "typing", prelude_typing::module_body,
                   {{"_bella_refuse", i_bella_refuse}, {"_tp_name", i_tp_name}, {"_bella_caller_module", i_bella_caller_module},
                    {"_bella_class_set", i_bella_class_set}, {"_bella_bootstrap", i_bella_bootstrap}});
}
void fill_posix(Module* m) {
    fill_in_python(m, "posix", "posix", prelude_posix::module_body,
                   {{"_number_index", i_number_index}, {"_tp_name", i_tp_name}, {"_keyword_suggestion", i_keyword_suggestion}, {"_structseq", i_structseq}, {"_sys", i_posix_sys}});
    dict_set(m->dict, Obj::of(N("error")), Obj::of(exception_class("OSError")));
    static_cast<ClassObject*>(dict_get(m->dict, Obj::of(N("DirEntry"))).object())->disallow_instantiation = true;
}
void fill_errno(Module* m) { fill_in_python(m, "errno", "", prelude_errno::module_body, {}); }
void fill_stat(Module* m) { fill_in_python(m, "_stat", "", prelude_stat::module_body, {{"_number_index", i_number_index}}); }
void fill_string(Module* m) {
    fill_in_python(m, "_string", "", prelude_string::module_body,
                   {{"_markup_next", i_markup_next}, {"_field_split", i_field_split}, {"_field_next", i_field_next}, {"_tp_name", i_tp_name}});
}
void fill_operator(Module* m) {                  // its types are named for `operator`, the module that shows them
    fill_in_python(m, "_operator", "operator", prelude_operator::module_body,
                   {{"_number_index", i_number_index}, {"_lookup_special", i_lookup_special}, {"_sequence_concat", i_sequence_concat}});
}

void set_bootstrap_module(Module* m) { bootstrap_module() = m; }
Ref i_bella_is_builtin(Obj, Args a) {            // _imp.is_builtin: sys and builtins, then the table
    positional_only(a, "_bella_is_builtin", 1, 1);
    const std::string& name = as_str(a.pos(0))->text;
    return Ref::steal(boolean(name == "sys" || name == "builtins" || native_registry().contains(name)));
}
Ref i_bella_create_builtin(Obj, Args a) {        // _imp.create_builtin: one module per name
    positional_only(a, "_bella_create_builtin", 1, 1);
    const std::string& name = as_str(a.pos(0))->text;
    if (name == "sys") return Ref::share(Obj::of(sys_module()));
    if (name == "builtins") return Ref::share(Obj::of(builtins_module()));
    NativeModule& n = native_registry().at(name);
    if (n.made == nullptr) {
        n.made = new_module(name.c_str());
        note_native_module(name.c_str(), n.made);
        n.fill(n.made);
        adopt_functions(n.made);
    }
    return Ref::share(Obj::of(n.made));
}

Ref i_bella_import_warning(Obj, Args a) {        // _warnings.warn(msg, ImportWarning), or of the category named second: see runtime_warning
    positional_only(a, "_bella_import_warning", 1, 2);
    runtime_warning(a.npos == 2 ? as_str(a.pos(1))->text.c_str() : "ImportWarning", as_str(a.pos(0))->text);
    return none_ref();
}
bool& shutting_down() {
    static bool down = false;
    return down;
}
Ref i_bella_shutting_down(Obj, Args) { return Ref::steal(boolean(shutting_down())); }
Ref i_bella_refuse(Obj, Args a) {                // a facility phase 1 lacks, where it would run
    positional_only(a, "_bella_refuse", 1, 1);
    throw NotImplemented(as_str(a.pos(0))->text);
}

// ---- PyImport_ImportModuleLevelObject ----
Ref import_module_level(Obj name, Obj globals, Obj locals, Obj fromlist, std::int64_t level) {
    (void)locals;
    if (name.is_unset()) raise_new("ValueError", "Empty module name");
    if (as_str(name) == nullptr) raise_new("TypeError", "module name must be a string");
    if (level < 0) raise_new("ValueError", "level must be >= 0");
    Ref abs_name = absolute_name(name, globals, level);
    Ref mod = get_module(abs_name.get());
    if (!mod.get().is_unset() && mod.get() != None()) {
        bool initializing = ensure_initialized(mod.get());
        Ref check = get_module(abs_name.get());
        if (check.get() != mod.get()) mod = call_bootstrap("_find_and_load", {abs_name.get(), import_func()});
        else if (!initializing && has_lazy_submodules()) clear_lazy_submodule(as_str(abs_name.get())->text, true);
    } else {
        mod = call_bootstrap("_find_and_load", {abs_name.get(), import_func()});
    }
    bool has_from = !fromlist.is_unset() && fromlist != None() && truth(fromlist);
    if (!has_from) {
        const std::string& n = as_str(name)->text;
        if (level == 0 || !n.empty()) {
            std::size_t dot = n.find('.');
            if (dot == std::string::npos) return mod;
            if (level == 0) {
                Ref front = str_new(n.substr(0, dot));
                return import_module_level(front.get(), Obj{}, Obj{}, Obj{}, 0);
            }
            std::size_t cut_off = n.size() - dot;
            const std::string& abs = as_str(abs_name.get())->text;
            Ref to_return = str_new(abs.substr(0, abs.size() - cut_off));
            Ref final_mod = get_module(to_return.get());
            if (final_mod.get().is_unset()) {
                Ref text = str_new(quoted(to_return.get()) + " not in sys.modules as expected");
                Ref exc = invoke(Obj::of(exception_class("KeyError")), {text.get()});
                raise(exc.get());
            }
            return final_mod;
        }
        return mod;
    }
    Ref path = optional_attr(mod.get(), N("__path__"));
    if (!path.get().is_unset()) return call_bootstrap("_handle_fromlist", {mod.get(), fromlist, import_func()});
    return mod;
}

// builtins.__import__(name, globals=None, locals=None, fromlist=(), level=0)
Ref b_import(Obj, Args a) {
    static const char* const params[] = {"name", "globals", "locals", "fromlist", "level"};
    Obj given[5] = {};
    if (a.npos > 5) raise_new("TypeError", "__import__() takes at most 5 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::size_t j = 0;
        while (j < 5 && a.kwnames[k]->text != params[j]) ++j;
        if (j == 5) raise_new("TypeError", "__import__() got an unexpected keyword argument '" + a.kwnames[k]->text + "'");
        if (!given[j].is_unset())
            raise_new("TypeError", std::string("argument for __import__() given by name ('") + params[j] +
                                       "') and position (" + std::to_string(j + 1) + ")");
        given[j] = a.kw(k);
    }
    if (given[0].is_unset()) raise_new("TypeError", "__import__() missing required argument 'name' (pos 1)");
    std::int64_t level = given[4].is_unset() ? 0 : level_value(given[4]);
    return import_module_level(given[0], given[1], given[2], given[3], level);
}

// ---- IMPORT_NAME: _PyEval_LazyImportName, then _PyEval_ImportName ----
Ref import_name(Obj name, Obj fromlist, Obj level, Obj mode, Module* m, Obj ns) {
    Obj globals = Obj::of(m->dict);
    Obj builtins = Obj::of(builtins_module()->dict);       // the frame's: a compiled module's are the builtins module's dict
    std::string_view how = as_str(mode)->text;
    bool lazy = how == "lazy";
    if (how == "default" && ns == globals) {
        // __lazy_modules__ at module level names the module (the lazy-imports mode is always "normal", D-18)
        Obj listed = dict_get(m->dict, Obj::of(N("__lazy_modules__")));
        if (!listed.is_unset()) {
            Ref keep = Ref::share(listed);
            Ref abs = absolute_name(name, globals, level_value(level));
            Ref in = compare(CmpOp::In, abs.get(), keep.get());
            lazy = truth(in.get());
        }
    }
    Obj locals = ns.is_unset() ? None() : ns;
    if (lazy) {
        Ref f = Ref::share(dict_get(builtins_module()->dict, Obj::of(N("__lazy_import__"))));
        if (f.get().is_unset()) raise_new("ImportError", "__lazy_import__ not found");
        if (f.get() == lazy_import_func()) return lazy_import_module_level(name, builtins, globals, fromlist, level_value(level));
        return invoke(f.get(), {name, globals, locals, fromlist, level});
    }
    Ref f = Ref::share(dict_get(builtins_module()->dict, Obj::of(N("__import__"))));
    if (f.get().is_unset()) raise_new("ImportError", "__import__ not found");
    if (f.get() == import_func()) return import_module_level(name, globals, locals, fromlist, level_value(level));
    return invoke(f.get(), {name, globals, locals, fromlist, level});
}

// ---- IMPORT_FROM: _PyEval_ImportFrom ----
Ref import_from(Obj v, const Str* name) {
    if (is_kind(v, Kind::LazyImport)) return lazy_import_from(v, name);
    Ref x = optional_attr(v, name);
    if (!x.get().is_unset()) return x;
    // in case this failed because of a circular relative import, the module itself from sys.modules
    Ref mod_name = optional_attr(v, N("__name__"));
    if (!mod_name.get().is_unset() && as_str(mod_name.get()) != nullptr) {
        Ref full = str_new(as_str(mod_name.get())->text + "." + name->text);
        Ref found = get_initialized_module(full.get());
        if (!found.get().is_unset()) return found;
    } else {
        mod_name = Ref{};
    }
    Ref shown = mod_name.get().is_unset() ? str_new("<unknown module name>") : Ref::share(mod_name.get());
    Ref spec = optional_attr(v, N("__spec__"));
    std::string msg;
    Ref origin;
    if (spec.get().is_unset()) {
        msg = "cannot import name " + quoted(Obj::of(name)) + " from " + quoted(shown.get()) + " (unknown location)";
    } else {
        origin = spec_file_origin(spec.get());
        bool shadowing = possibly_shadowing(origin.get());
        bool shadowing_stdlib = shadowing && is_stdlib_name(shown.get());
        if (origin.get().is_unset() && is_kind(v, Kind::Module)) {     // PyModule_GetFilenameObject
            Obj file = dict_get(static_cast<Module*>(v.object())->dict, Obj::of(N("__file__")));
            if (!file.is_unset() && as_str(file) != nullptr) origin = Ref::share(file);
        }
        std::string n = quoted(Obj::of(name)), mn = quoted(shown.get());
        if (shadowing_stdlib) {
            msg = "cannot import name " + n + " from " + mn + " (consider renaming " + quoted(origin.get()) +
                  " since it has the same name as the standard library module named " + mn +
                  " and prevents importing that standard library module)";
        } else if (spec_is_initializing(spec.get())) {
            if (shadowing)
                msg = "cannot import name " + n + " from " + mn + " (consider renaming " + quoted(origin.get()) +
                      " if it has the same name as a library you intended to import)";
            else if (!origin.get().is_unset())
                msg = "cannot import name " + n + " from partially initialized module " + mn +
                      " (most likely due to a circular import) (" + as_str(origin.get())->text + ")";
            else
                msg = "cannot import name " + n + " from partially initialized module " + mn +
                      " (most likely due to a circular import)";
        } else if (!origin.get().is_unset()) {
            msg = "cannot import name " + n + " from " + mn + " (" + as_str(origin.get())->text + ")";
        } else {
            msg = "cannot import name " + n + " from " + mn + " (unknown location)";
        }
    }
    Ref exc = import_error("ImportError", msg, mod_name.get(), origin.get(), Obj::of(name));
    raise(exc.get());
}

// ---- import *: import_all_from ----
void import_star(Obj v, Obj locals) {
    Ref all = optional_attr(v, N("__all__"));
    bool skip_leading_underscores = false;
    if (all.get().is_unset()) {
        Ref dict = optional_attr(v, N("__dict__"));
        if (dict.get().is_unset()) raise_new("ImportError", "from-import-* object has no __dict__ and no __all__");
        Ref keys = getattr(dict.get(), N("keys"));    // PyMapping_Keys
        Ref listed = invoke(keys.get(), {});
        all = invoke(Obj::of(types().list), {listed.get()});
        skip_leading_underscores = true;
    }
    for (std::int64_t pos = 0;; ++pos) {
        Ref name;
        try {
            Ref index = Ref::steal(Obj::small(pos));
            Obj seq = all.get();                 // PySequence_GetItem: a sequence's item, nothing else's
            if (is_kind(seq, Kind::Dict)) raise_new("TypeError", "dict is not a sequence");
            if (as_str(seq) == nullptr && !is_kind(seq, Kind::List) && !is_kind(seq, Kind::Tuple) && !is_kind(seq, Kind::Range) &&
                (is_kind(seq, Kind::Set) || type_lookup(type_of(seq), N("__getitem__")).is_unset()))
                raise_new("TypeError", "'" + type_of(seq)->name + "' object does not support indexing");
            name = getitem(seq, index.get());
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("IndexError"))) throw;
            break;
        }
        const Str* s = as_str(name.get());
        if (s == nullptr) {
            Ref modname = getattr(v, N("__name__"));
            if (as_str(modname.get()) == nullptr)
                raise_new("TypeError", "module __name__ must be a string, not " + type_of(modname.get())->name);
            raise_new("TypeError", std::string(skip_leading_underscores ? "Key" : "Item") + " in " +
                                       as_str(modname.get())->text + "." +
                                       (skip_leading_underscores ? "__dict__" : "__all__") + " must be str, not " +
                                       type_of(name.get())->name);
        }
        if (skip_leading_underscores && !s->text.empty() && s->text[0] == '_') continue;
        Ref value = getattr(v, intern(s->text));
        if (is_exact_dict(locals)) dict_set(static_cast<Dict*>(locals.object()), name.get(), value.get());
        else setitem(locals, name.get(), value.get());
    }
}

// ---- lazy imports (PEP 810; Objects/lazyimportobject.c and Python/import.c, 3.15.2) ----
// With one thread and D-18's fixed mode: no filter (sys.set_lazy_imports_filter is X-4-02's), and
// sys.lazy_modules, whose only effect is that a program can read it, is left out until sys has it.
namespace {
LazyImport* as_lazy(Obj v) { return static_cast<LazyImport*>(v.object()); }
bool is_lazy(Obj v) { return is_kind(v, Kind::LazyImport); }

struct RecursionGuard {                          // _Py_EnterRecursiveCallTstate
    RecursionGuard() { detail::enter_frame(); }
    ~RecursionGuard() { detail::leave_frame(); }
};

using PendingChildren = std::unordered_map<std::string, Ref>;
// lazy_pending_submodules: parent's name -> child's name -> the declaration, or None
std::unordered_map<std::string, PendingChildren>& pending_submodules() {
    static auto* table = new std::unordered_map<std::string, PendingChildren>;
    return *table;
}
bool& has_lazy_submodules() {
    static bool any = false;
    return any;
}
std::vector<Obj>& resolving() {                  // ts->lazy_imports: the placeholders being resolved
    static std::vector<Obj> active;
    return active;
}
bool is_resolving(Obj v) { return std::find(resolving().begin(), resolving().end(), v) != resolving().end(); }

// _PyLazyImport_New
Ref lazy_new(bool at_frame, Obj builtins, Obj name, Obj fromlist) {
    if (as_str(name) == nullptr && !is_lazy(name)) raise_new("TypeError", "expected str or lazy_import for name");
    if (fromlist == None()) fromlist = Obj{};
    if (!fromlist.is_unset() && as_str(fromlist) == nullptr && !is_kind(fromlist, Kind::Tuple))
        raise_new("TypeError", "lazy_import: fromlist must be None, a string, or a tuple");
    auto* lz = new LazyImport;
    Ref out = own(lz);
    if (!builtins.is_unset()) lz->builtins = Ref::share(builtins);
    lz->from = Ref::share(name);
    if (!fromlist.is_unset()) lz->attr = Ref::share(fromlist);
    if (at_frame && detail::current_frame() != nullptr) {
        lz->code = detail::current_frame()->code;
        lz->line = detail::current_frame()->line;
    }
    return out;
}

// lazy_import_get_loaded_attr: a concrete attribute of an initialised module, without waiting for
// imports or resolving lazy attributes; a failed lookup is retried at resolution
Ref loaded_attr(Obj name, const Str* attr_name) {
    try {
        Ref mod = get_module(name);
        if (!is_kind(mod.get(), Kind::Module)) return Ref{};
        Ref spec = optional_attr(mod.get(), N("__spec__"));
        if (spec_is_initializing(spec.get())) return Ref{};
        Ref current = get_module(name);          // an initialization check can replace the module
        if (current.get() != mod.get()) return Ref{};
        Obj v = dict_get(static_cast<Module*>(mod.get().object())->dict, Obj::of(attr_name));
        return v.is_unset() || is_lazy(v) ? Ref{} : Ref::share(v);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("Exception"))) throw;
        return Ref{};
    }
}

// lazy_import_path: the dotted name of the object that resolving the placeholder returns
std::string lazy_path(LazyImport* m) {
    if (is_lazy(m->from.get())) {
        RecursionGuard guard;
        return lazy_path(as_lazy(m->from.get())) + "." + as_str(m->attr.get())->text;
    }
    const std::string& from = as_str(m->from.get())->text;
    Obj attr = m->attr.get();
    if (!attr.is_unset() && (!is_kind(attr, Kind::Tuple) || !static_cast<Tuple*>(attr.object())->items.empty())) return from;
    return from.substr(0, from.find('.'));       // __import__("a.b") returns the top-level package `a`
}
// lazy_import_name
std::string lazy_name(LazyImport* m) {
    if (is_lazy(m->from.get())) return lazy_path(m);
    const std::string& from = as_str(m->from.get())->text;
    Obj attr = m->attr.get();
    if (!attr.is_unset() && (!is_kind(attr, Kind::Tuple) || !static_cast<Tuple*>(attr.object())->items.empty())) return from + "...";
    return from;
}

// _PyEval_ImportNameWithImport
Ref import_with(Obj f, Obj name, Obj globals, Obj locals, Obj fromlist, std::int64_t level) {
    if (f == import_func()) return import_module_level(name, globals, locals, fromlist, level);
    return invoke(f, {name, globals, locals, fromlist, Obj::small(level)});
}

Ref lazy_resolve_impl(Obj lazy, Ref* imported_module);

// lazy_import_resolve_result: a placeholder an import hook or an attribute lookup returned
Ref lazy_resolve_result(Ref obj) { return is_lazy(obj.get()) ? lazy_resolve_impl(obj.get(), nullptr) : obj; }

// lazy_import_replay_from: the attributes recorded from the root to lz, on the module the root's
// import returned
Ref lazy_replay_from(Obj mod, LazyImport* lz) {
    if (!is_lazy(lz->from.get())) return Ref::share(mod);
    RecursionGuard guard;
    Ref from = lazy_replay_from(mod, as_lazy(lz->from.get()));
    return lazy_resolve_result(import_from(from.get(), intern(as_str(lz->attr.get())->text)));
}

// lazy_import_add_exception_cause: the resolution error keeps its chain and gets the declaration:
// a note when it has a chain already, else an ImportError as its cause, with a traceback entry
void lazy_add_exception_cause(LazyImport* lz, Obj exc) {
    if (lz->code == nullptr || lz->line < 0 || !is_exception_instance(exc)) return;
    std::string name = lazy_name(lz);
    Obj suppress = exception_field(exc, "__suppress_context__");
    if (!exception_field(exc, "__cause__").is_unset() || !exception_field(exc, "__context__").is_unset() ||
        suppress == boolean(true)) {
        Ref note = str_new("lazy import of '" + name + "' declared in " + lz->code->name + " at " + lz->code->filename + ":" +
                           std::to_string(lz->line));
        Ref notes = optional_attr(exc, N("__notes__"));
        if (notes.get().is_unset()) {
            notes = list_new({});
            setattr(exc, N("__notes__"), notes.get());
        } else if (truth(compare(CmpOp::In, note.get(), notes.get()).get())) {
            return;
        }
        if (is_kind(notes.get(), Kind::List)) list_append(notes.get(), note.get());
        return;
    }
    Ref msg = str_new("lazy import of '" + name + "' raised an exception during resolution");
    Ref cause = invoke(Obj::of(exception_class("ImportError")), {msg.get()});
    Ref tb = own(new Traceback(lz->code, lz->line, Ref{}));      // _PyTraceback_Add
    set_exception_field(cause.get(), "__traceback__", tb.get());
    set_exception_field(exc, "__cause__", cause.get());          // PyException_SetCause
    set_exception_field(exc, "__suppress_context__", boolean(true));
}

// lazy_import_resolve_impl
Ref lazy_resolve_impl(Obj lazy, Ref* imported_module) {
    Ref held = Ref::share(lazy);
    LazyImport* lz = as_lazy(lazy);
    // the placeholder IMPORT_NAME left, and the first lookup on it
    LazyImport* root = lz;
    LazyImport* first = nullptr;
    while (is_lazy(root->from.get())) {
        first = root;
        root = as_lazy(root->from.get());
    }
    if (is_resolving(lazy)) {
        Ref text = str_new(lazy_name(lz));
        Ref exc = import_error("ImportCycleError", "cannot import name " + quoted(text.get()) + " (most likely due to a circular import)",
                               root->from.get(), Obj{}, Obj{});
        raise(exc.get());
    }
    RecursionGuard guard;
    resolving().push_back(lazy);
    auto done = [&] { resolving().erase(std::find(resolving().begin(), resolving().end(), lazy)); };
    Ref obj;
    try {
        // `from a import b, c`: import only the name being resolved; an empty tuple stays for hooks
        Obj root_attr = root->attr.get();
        Ref fromlist;
        if (first != nullptr && is_kind(root_attr, Kind::Tuple) && !static_cast<Tuple*>(root_attr.object())->items.empty())
            fromlist = tuple_new({first->attr.get()});
        else
            fromlist = root_attr.is_unset() ? none_ref() : Ref::share(root_attr);
        detail::FrameRecord* frame = detail::current_frame();
        Obj globals = frame != nullptr ? Obj::of(frame->module->dict) : None();     // PyEval_GetGlobals
        Ref f = mapping_get(root->builtins.get(), Obj::of(N("__import__")));
        if (f.get().is_unset()) raise_new("ImportError", "__import__ not found");
        bool default_import = f.get() == import_func();
        Ref name = Ref::share(root->from.get());
        Obj list = fromlist.get();
        if (first == nullptr && (list == None() || (is_kind(list, Kind::Tuple) && static_cast<Tuple*>(list.object())->items.empty())) &&
            default_import && root->builtins.get() == Obj::of(builtins_module()->dict)) {
            // A plain import binds the root package; its pending children are imported separately,
            // when their attributes are accessed. Aliased or non-package parents stay eager.
            const std::string n = as_str(name.get())->text;
            std::size_t dot = n.find('.');
            if (dot != std::string::npos) {
                bool regular = true, complete = true;
                for (std::size_t i = dot; i != std::string::npos && regular; i = n.find('.', i + 1)) {
                    std::string prefix_text = n.substr(0, i);
                    Ref prefix = str_new(prefix_text);
                    Ref cached = loaded_attr(prefix.get(), N("__name__"));
                    if (cached.get().is_unset()) {
                        complete = false;
                        break;
                    }
                    Ref path = loaded_attr(prefix.get(), N("__path__"));
                    const Str* cached_name = as_str(cached.get());
                    regular = !path.get().is_unset() && cached_name != nullptr && cached_name->text == prefix_text;
                }
                Ref loaded = loaded_attr(name.get(), N("__name__"));
                if (regular && (!complete || loaded.get().is_unset())) name = str_new(n.substr(0, dot));
            }
        }
        obj = import_with(f.get(), name.get(), globals, globals, fromlist.get(), 0);
        bool whole = name.get() == root->from.get();
        if (!whole) {
            root->active = true;
            has_lazy_submodules() = true;
            bool package = is_kind(obj.get(), Kind::Module) &&
                           !dict_get(static_cast<Module*>(obj.get().object())->dict, Obj::of(N("__path__"))).is_unset();
            if (!package) obj = import_with(f.get(), root->from.get(), globals, globals, fromlist.get(), 0);
        } else if (default_import) {
            clear_lazy_submodule(as_str(name.get())->text, false);
        }
        obj = lazy_resolve_result(std::move(obj));
        // the normal importer may publish this module on its parent; a hook keeps control of its own
        if (imported_module != nullptr && is_kind(obj.get(), Kind::Module) && default_import) *imported_module = obj;
        if (first != nullptr) {                  // the hook's and the root's result stay alive for the lookups
            Ref from = std::move(obj);
            obj = lazy_replay_from(from.get(), lz);
        }
    } catch (const PyError& e) {
        done();
        lazy_add_exception_cause(lz, e.exc.get());
        rethrow(e);
    } catch (...) {
        done();
        throw;
    }
    done();
    return obj;
}

// _PyLazyImport_LoadChild: a pending child resolved as an aliased import, keeping its declaration
Ref lazy_load_child(Obj declaration, Obj name) {
    LazyImport* source = as_lazy(declaration);
    const std::string n = as_str(name)->text;
    Ref lz = lazy_new(false, source->builtins.get(), name, Obj{});
    std::size_t dot = n.find('.');
    while (dot != std::string::npos) {
        std::size_t start = dot + 1;
        dot = n.find('.', start);
        Ref attr = str_new(n.substr(start, dot == std::string::npos ? std::string::npos : dot - start));
        lz = lazy_new(false, Obj{}, lz.get(), attr.get());
    }
    LazyImport* child = as_lazy(lz.get());
    child->code = source->code;
    child->line = source->line;
    Ref result = lazy_resolve_impl(lz.get(), nullptr);
    if (is_kind(result.get(), Kind::Module) && as_str(source->from.get())->text != n &&
        dict_get(static_cast<Module*>(result.get().object())->dict, Obj::of(N("__path__"))).is_unset())
        return lazy_load_child(declaration, source->from.get());   // a non-package must still reject an invalid dotted import
    return result;
}

// _PyDict_ReplaceItemIf: namespace[name] = value if it still holds `expected`
bool replace_if(Dict* d, const Str* name, Obj expected, Obj value) {
    if (dict_get(d, Obj::of(name)) != expected) return false;
    dict_set(d, Obj::of(name), value);
    return true;
}

// lazy_import_replace_child: loading pkg.child can replace a placeholder in pkg.child with the
// module before a from-import retrieves the value that belongs in that binding
void lazy_replace_child(Obj placeholder, const Str* name, Dict* ns, Obj child, Obj value) {
    LazyImport* root = as_lazy(placeholder);
    if (!is_lazy(root->from.get())) return;
    while (is_lazy(root->from.get())) root = as_lazy(root->from.get());
    const std::string& from = as_str(root->from.get())->text;
    std::size_t dot = from.rfind('.');
    if (dot == std::string::npos || from.substr(dot + 1) != name->text) return;
    Ref parent_name = str_new(from.substr(0, dot));
    Ref parent = get_module(parent_name.get());
    if (is_kind(parent.get(), Kind::Module) && static_cast<Module*>(parent.get().object())->dict == ns)
        replace_if(ns, name, child, value);
}

// _PyImport_LazyImportModuleLevelObject (no filter: D-18)
Ref lazy_import_module_level(Obj name, Obj builtins, Obj globals, Obj fromlist, std::int64_t level) {
    if (as_str(name) == nullptr) raise_new("TypeError", "module name must be a string, got " + fully_qualified_name(type_of(name)));
    if (level < 0) raise_new("ValueError", "level must be >= 0");
    Ref abs_name = absolute_name(name, globals, level);
    detail::FrameRecord* frame = detail::current_frame();
    if (frame == nullptr || std::string_view(frame->code->name) != "<module>")   // f_globals != f_locals: the frame's, not the argument's
        throw NotImplemented("the SyntaxError \"'lazy import' is only allowed at module level\" (SyntaxError: step 3b)");
    Ref list = fromlist.is_unset() ? none_ref() : as_str(fromlist) != nullptr ? tuple_new({fromlist}) : Ref::share(fromlist);
    if (is_kind(list.get(), Kind::Tuple))        // the entire fromlist, before registering any pending imports
        for (Obj item : static_cast<Tuple*>(list.get().object())->items)
            if (as_str(item) == nullptr) raise_new("TypeError", "Item in ``from list'' must be str, not " + type_of(item)->name);
    Ref res = lazy_new(true, builtins, abs_name.get(), list.get());
    Ref existing = get_module(abs_name.get());
    const std::string& abs = as_str(abs_name.get())->text;
    if (is_kind(list.get(), Kind::Tuple) && !static_cast<Tuple*>(list.get().object())->items.empty()) {
        for (Obj item : static_cast<Tuple*>(list.get().object())->items) {
            // register_from_lazy_on_parent: IMPORT_FROM returns stored attributes directly
            if (is_kind(existing.get(), Kind::Module) &&
                !dict_get(static_cast<Module*>(existing.get().object())->dict, item).is_unset())
                continue;
            register_lazy_on_parent(abs + "." + as_str(item)->text, None());
        }
    } else {
        register_lazy_on_parent(abs, res.get());
    }
    return res;
}
}  // namespace

// register_lazy_on_parent: each parent-child relationship of a lazily imported name; a parent's
// attribute access then finds the child pending (_PyImport_TryLoadLazySubmodule)
void register_lazy_on_parent(const std::string& name, Obj source) {
    std::size_t end = name.size();
    for (;;) {
        std::size_t dot = end == 0 ? std::string::npos : name.rfind('.', end - 1);
        if (dot == std::string::npos) return;
        PendingChildren& children = pending_submodules()[name.substr(0, dot)];
        std::string child = name.substr(dot + 1, end - dot - 1);
        Ref fullname = str_new(name.substr(0, end));
        Ref cached = get_module(fullname.get());
        Obj value = !cached.get().is_unset() && cached.get() != None() ? None() : source;
        if (source == None()) children.try_emplace(child, Ref::share(value));
        else children[child] = Ref::share(value);
        end = dot;
    }
}

// _PyImport_ClearLazySubmodule: release completed declarations, retaining names while their parent
// may fail; a cached eager import also restores a child removed after failed validation
void clear_lazy_submodule(const std::string& name, bool bind) {
    if (pending_submodules().empty()) return;
    std::size_t dot = name.rfind('.');
    if (dot == std::string::npos) return;
    auto parent_entry = pending_submodules().find(name.substr(0, dot));
    if (parent_entry == pending_submodules().end()) return;
    PendingChildren& children = parent_entry->second;
    std::string child = name.substr(dot + 1);
    if (!children.contains(child)) return;
    auto still_initializing = [](Obj module) {
        if (module.is_unset()) return false;
        Ref spec = optional_attr(module, N("__spec__"));
        return spec_is_initializing(spec.get());
    };
    Ref full = str_new(name), parent_name = str_new(name.substr(0, dot));
    try {
        Ref loaded = get_module(full.get());
        if (still_initializing(loaded.get())) return;
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("Exception"))) throw;
        return;
    }
    Ref module = get_module(parent_name.get());
    bool initializing = still_initializing(module.get());
    if (bind && !initializing && is_kind(module.get(), Kind::Module) && children.contains(child)) {
        Ref value = get_module(full.get());
        Dict* d = static_cast<Module*>(module.get().object())->dict;
        Ref key = str_new(child);
        if (!value.get().is_unset() && value.get() != None() && dict_get(d, key.get()).is_unset()) dict_set(d, key.get(), value.get());
    }
    if (initializing) children[child] = none_ref();
    else children.erase(child);
}

// _imp._set_lazy_attributes: (sys.lazy_modules, left out,) and the name's pending entry
Ref i_bella_set_lazy_attributes(Obj, Args a) {
    positional_only(a, "_bella_set_lazy_attributes", 2, 2);
    clear_lazy_submodule(as_str(a.pos(1))->text, false);
    return none_ref();
}

// _PyImport_TryLoadLazySubmodule
Ref try_load_lazy_submodule(Module* m, const Str* attr_name, bool suppress, bool& recheck_dict) {
    recheck_dict = false;
    Obj mod_name = dict_get(m->dict, Obj::of(N("__name__")));
    if (mod_name.is_unset() || as_str(mod_name) == nullptr) return Ref{};
    auto parent_entry = pending_submodules().find(as_str(mod_name)->text);
    if (parent_entry == pending_submodules().end()) return Ref{};
    recheck_dict = true;
    std::string parent_text = parent_entry->first;
    auto child_entry = parent_entry->second.find(attr_name->text);
    if (child_entry == parent_entry->second.end()) return Ref{};
    Ref source = child_entry->second;
    Ref full = str_new(parent_text + "." + attr_name->text);
    auto children = [&]() -> PendingChildren& { return pending_submodules()[parent_text]; };   // the map may have grown
    Ref mod;
    try {
        // Match eager from-imports: accept a partial module in an import cycle.
        if (source.get() != None() && !suppress &&
            (as_lazy(source.get())->active || dict_get(m->dict, Obj::of(N("__getattr__"))).is_unset())) {
            mod = lazy_load_child(source.get(), full.get());
        } else {
            mod = get_initialized_module(full.get());
            if (mod.get().is_unset() || mod.get() == None())
                mod = call_bootstrap("_find_and_load_lazy_submodule", {full.get(), import_func()});
        }
    } catch (const PyError& e) {
        Ref loaded = get_module(full.get());
        if (!loaded.get().is_unset() && loaded.get() != None()) {
            if (dict_get(m->dict, Obj::of(attr_name)) == loaded.get()) dict_del(m->dict, Obj::of(attr_name));
            children().try_emplace(attr_name->text, source);
        }
        rethrow(e);
    }
    // missing children stay pending: a finder may provide them later
    if (mod.get().is_unset() || mod.get() == None()) return Ref{};
    bool initializing = false;
    try {
        Ref spec = optional_attr(mod.get(), N("__spec__"));
        initializing = spec_is_initializing(spec.get());
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("Exception"))) throw;
    }
    if (!initializing) {
        dict_set(m->dict, Obj::of(attr_name), mod.get());
        children().erase(attr_name->text);
    }
    return mod;
}

// _PyEval_LazyImportFrom
Ref lazy_import_from(Obj v, const Str* name) {
    LazyImport* lz = as_lazy(v);
    // only `from a import b` can take b off an already imported a; `import a.b as c` imports a.b first
    Obj attr = lz->attr.get();
    if (is_kind(attr, Kind::Tuple) && !static_cast<Tuple*>(attr.object())->items.empty()) {
        Ref found = loaded_attr(lz->from.get(), name);
        if (!found.get().is_unset()) return found;
    }
    return lazy_new(true, Obj{}, v, Obj::of(name));
}

// _PyLazyImport_Reify: resolved, and the namespace, if it still holds the placeholder, gets the result
Ref lazy_reify(Obj placeholder, const Str* name, Obj ns) {
    Ref held = Ref::share(placeholder);
    Ref imported;
    Ref value = lazy_resolve_impl(placeholder, &imported);
    if (is_exact_dict(ns)) {
        Dict* d = static_cast<Dict*>(ns.object());
        if (!replace_if(d, name, placeholder, value.get()) && !imported.get().is_unset())
            lazy_replace_child(placeholder, name, d, imported.get(), value.get());
    } else if (!is_kind(ns, Kind::Dict) && type_lookup(type_of(ns), N("__setitem__")).is_unset()) {
        return value;                            // a read-only namespace resolves without caching
    } else {
        Ref current = mapping_get(ns, Obj::of(name));
        if (current.get() == placeholder) mapping_set(ns, Obj::of(name), value.get());
    }
    return value;
}

// lazy_import_getattro: the generic lookup, with its own message
Ref lazy_getattr(Obj lazy, const Str* name) {
    ClassObject* c = type_of(lazy);
    Obj found = type_lookup(c, name);
    if (!found.is_unset()) return descr_get(found, lazy, Obj::of(c));
    refuse_absent_attribute(lazy, name);
    Ref text = str_new(lazy_name(as_lazy(lazy)));
    raise_attribute_error(lazy, name, "cannot access attribute " + quoted(Obj::of(name)) + " on unresolved lazy import " + quoted(text.get()));
}
namespace {
Ref lazy_repr_m(Obj self, Args a) {
    positional_only(a, "__repr__", 0, 0);
    return str_new("<lazy_import '" + lazy_name(as_lazy(self)) + "'>");
}
Ref lazy_resolve_m(Obj self, Args a) {           // lazy_import.resolve(): METH_NOARGS
    if (a.nkw != 0) raise_new("TypeError", "lazy_import.resolve() takes no keyword arguments");
    if (a.npos != 0) raise_new("TypeError", "lazy_import.resolve() takes no arguments (" + std::to_string(a.npos) + " given)");
    return lazy_resolve_impl(self, nullptr);
}
Ref lazy_new_m(Obj, Args) { raise_new("TypeError", "cannot create 'lazy_import' instances"); }
}  // namespace

// builtins.__lazy_import__(name, globals=None, locals=None, fromlist=None, level=0)
Ref b_lazy_import(Obj, Args a) {
    static const char* const params[] = {"name", "globals", "locals", "fromlist", "level"};
    Obj given[5] = {};
    if (a.npos + a.nkw > 5) raise_new("TypeError", "__lazy_import__() takes at most 5 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::size_t j = 0;
        while (j < 5 && a.kwnames[k]->text != params[j]) ++j;
        if (j == 5) throw NotImplemented("__lazy_import__() with an unexpected keyword argument (the suggestion in its message)");
        if (!given[j].is_unset())
            raise_new("TypeError", std::string("argument for __lazy_import__() given by name ('") + params[j] + "') and position (" + std::to_string(j + 1) + ")");
        given[j] = a.kw(k);
    }
    if (given[0].is_unset()) raise_new("TypeError", "__lazy_import__() missing required argument 'name' (pos 1)");
    std::int64_t level = given[4].is_unset() ? 0 : level_value(given[4]);
    Obj globals = given[1];
    if (globals.is_unset()) {
        detail::FrameRecord* frame = detail::current_frame();
        if (frame == nullptr) raise_new("TypeError", "__lazy_import__() missing globals when called without a frame");
        globals = Obj::of(frame->module->dict);
    }
    if (!is_kind(globals, Kind::Dict)) raise_new("TypeError", "expect dict for globals, got " + fully_qualified_name(type_of(globals)));
    Obj builtins = dict_get(static_cast<Dict*>(globals.object()), Obj::of(N("__builtins__")));
    if (builtins.is_unset()) raise_new("ValueError", "unable to get builtins for lazy import");
    if (is_kind(builtins, Kind::Module)) builtins = Obj::of(static_cast<Module*>(builtins.object())->dict);
    return lazy_import_module_level(given[0], builtins, globals, given[3], level);
}

// ---- the module type (Objects/moduleobject.c) ----
namespace {
// module_get_resolved_dict_item: an item of the namespace, a lazy import resolved; one this thread
// is resolving reads as absent
Ref resolved_dict_item(Dict* d, const Str* name) {
    Obj v = dict_get(d, Obj::of(name));
    if (v.is_unset()) return Ref{};
    if (!is_lazy(v)) return Ref::share(v);
    if (is_resolving(v)) return Ref{};
    return lazy_reify(v, name, Obj::of(d));
}
}  // namespace

// _Py_module_getattro_impl: the generic lookup with the module's dict; a pending lazy submodule; the
// module's own __getattr__ (PEP 562); then CPython's message for why the name is missing. With
// `suppress` (PyObject_GetOptionalAttr) an absent attribute is Unset, not an AttributeError.
Ref module_getattr(Obj obj, const Str* name, bool suppress) {
    auto* m = static_cast<Module*>(obj.object());
    ClassObject* c = type_of(obj);
    Obj found = type_lookup(c, name);
    Ref attr;
    bool data = !found.is_unset() && is_data_descriptor(found);
    try {
        if (data) {
            attr = descr_get(found, obj, Obj::of(c));
        } else {
            Obj v = dict_get(m->dict, Obj::of(name));
            if (!v.is_unset()) attr = Ref::share(v);
            else if (!found.is_unset()) attr = descr_get(found, obj, Obj::of(c));
        }
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
    }
    if (attr.get().is_unset()) {
        bool recheck_dict = false;
        attr = try_load_lazy_submodule(m, name, suppress, recheck_dict);
        if (!attr.get().is_unset()) return attr;
        // a load may have bound the child and removed its pending entry after the first lookup
        if (recheck_dict && (found.is_unset() || !has_descr_get(found))) {
            Obj v = dict_get(m->dict, Obj::of(name));
            if (!v.is_unset()) attr = Ref::share(v);
        }
    }
    if (!attr.get().is_unset()) {
        if (!is_lazy(attr.get())) return attr;
        if (suppress && is_resolving(attr.get())) return Ref{};   // only direct reentry means unavailable
        return lazy_reify(attr.get(), name, Obj::of(m->dict));
    }
    Ref hook = resolved_dict_item(m->dict, N("__getattr__"));
    if (!hook.get().is_unset()) {
        Ref name_ref = Ref::share(Obj::of(name));
        try {
            return invoke(hook.get(), {name_ref.get()});
        } catch (const PyError& e) {
            if (!suppress || !is_attribute_error(e)) throw;
            return Ref{};
        }
    }
    refuse_absent_attribute(obj, name);
    if (suppress) return Ref{};
    Obj mod_name = dict_get(m->dict, Obj::of(N("__name__")));
    if (mod_name.is_unset() || as_str(mod_name) == nullptr)
        raise_attribute_error(obj, name, "module has no attribute '" + name->text + "'");
    const std::string& mn = as_str(mod_name)->text;
    Ref spec = Ref::share(dict_get(m->dict, Obj::of(N("__spec__"))));
    if (spec.get().is_unset()) raise_attribute_error(obj, name, "module '" + mn + "' has no attribute '" + name->text + "'");
    Ref origin = spec_file_origin(spec.get());
    bool shadowing = possibly_shadowing(origin.get());
    if (shadowing && is_stdlib_name(mod_name))
        raise_attribute_error(obj, name, "module '" + mn + "' has no attribute '" + name->text + "' (consider renaming '" +
                                             as_str(origin.get())->text + "' since it has the same name as the standard "
                                             "library module named '" + mn + "' and prevents importing that standard library module)");
    if (spec_is_initializing(spec.get())) {
        if (shadowing)
            raise_attribute_error(obj, name, "module '" + mn + "' has no attribute '" + name->text + "' (consider renaming '" +
                                                 as_str(origin.get())->text + "' if it has the same name as a library you intended to import)");
        if (!origin.get().is_unset())
            raise_attribute_error(obj, name, "partially initialized module '" + mn + "' from '" + as_str(origin.get())->text +
                                                 "' has no attribute '" + name->text + "' (most likely due to a circular import)");
        raise_attribute_error(obj, name, "partially initialized module '" + mn + "' has no attribute '" + name->text +
                                             "' (most likely due to a circular import)");
    }
    // _PyModuleSpec_IsUninitializedSubmodule: a submodule still loading
    Ref pending = optional_attr(spec.get(), N("_uninitialized_submodules"));
    if (!pending.get().is_unset()) {
        Ref in = compare(CmpOp::In, Obj::of(name), pending.get());
        if (truth(in.get()))
            raise_attribute_error(obj, name, "cannot access submodule '" + name->text + "' of module '" + mn +
                                                 "' (most likely due to a circular import)");
    }
    raise_attribute_error(obj, name, "module '" + mn + "' has no attribute '" + name->text + "'");
}

namespace {
Module* as_module(Obj self, const char* method) {
    if (!is_kind(self, Kind::Module))
        raise_new("TypeError", std::string("descriptor '") + method + "' requires a 'module' object but received a '" +
                                   type_of(self)->name + "'");
    return static_cast<Module*>(self.object());
}
}  // namespace

Ref module_repr_m(Obj self, Args a) {            // module_repr: importlib._bootstrap._module_repr
    positional_only(a, "__repr__", 0, 0);
    as_module(self, "__repr__");
    return call_bootstrap("_module_repr", {self});
}
Ref module_dir_m(Obj self, Args a) {             // module_dir: __dir__ from the namespace, else its keys
    positional_only(a, "__dir__", 0, 0);
    Module* m = as_module(self, "__dir__");
    Ref dirfunc = resolved_dict_item(m->dict, N("__dir__"));
    if (!dirfunc.get().is_unset()) return invoke(dirfunc.get(), {});
    Ref names = dict_new();                      // a native module has CPython's names, whichever it has written
    auto* d = static_cast<Dict*>(names.get().object());
    for (auto& e : m->dict->entries)
        if (!e.key.is_unset()) dict_set(d, e.key, None());
    if (std::string_view native = native_module_name(m); !native.empty())
        for (std::string_view n : cpython_names_of(native)) dict_set(d, Obj::of(intern(n)), None());
    Ref keys = list_new({});
    for (auto& e : d->entries)
        if (!e.key.is_unset()) list_append(keys.get(), e.key);
    return keys;
}
Ref module_dict_get(Obj self) { return Ref::share(Obj::of(as_module(self, "__dict__")->dict)); }
Ref module_new_m(Obj, Args a) {                  // ModuleType(name, doc=None): __new__ makes it empty
    if (a.npos < 1 || !is_kind(a.pos(0), Kind::Class) || static_cast<ClassObject*>(a.pos(0).object()) != types().module)
        throw NotImplemented("a subclass of the module type (step 3b)");
    auto* m = new Module("?");
    dict_del(m->dict, Obj::of(N("__name__")));
    return Ref::share(Obj::of(m));
}
Ref module_init_m(Obj self, Args a) {            // module___init___impl: module_init_dict
    Module* m = as_module(self, "__init__");
    Obj name, doc;
    if (a.npos > 2) raise_new("TypeError", "module() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    if (a.npos >= 1) name = a.pos(0);
    if (a.npos >= 2) doc = a.pos(1);
    const Str* unknown = nullptr;
    for (std::size_t k = 0; k < a.nkw; ++k) {    // _PyArg_UnpackKeywords: by name and position, then missing, then unknown
        std::string_view kn = a.kwnames[k]->text;
        if (kn == "name" || kn == "doc") {
            Obj& slot = kn == "name" ? name : doc;
            if (!slot.is_unset())
                raise_new("TypeError", "argument for module() given by name ('" + std::string(kn) + "') and position (" + (kn == "name" ? "1" : "2") + ")");
            slot = a.kw(k);
        } else if (unknown == nullptr) {
            unknown = a.kwnames[k];
        }
    }
    if (!name.is_unset() && unknown != nullptr) unexpected_keyword("module()", unknown, {"name", "doc"});
    if (name.is_unset()) raise_new("TypeError", "module() missing required argument 'name' (pos 1)");
    if (as_str(name) == nullptr) raise_new("TypeError", "module() argument 'name' must be str, not " + type_of(name)->name);
    dict_set(m->dict, Obj::of(N("__name__")), name);
    dict_set(m->dict, Obj::of(N("__doc__")), doc.is_unset() ? None() : doc);
    dict_set(m->dict, Obj::of(N("__package__")), None());
    dict_set(m->dict, Obj::of(N("__loader__")), None());
    dict_set(m->dict, Obj::of(N("__spec__")), None());
    m->name = Ref::share(name);
    return none_ref();
}

// dir(obj): type(obj).__dir__(obj), as a sorted list (PyObject_Dir, _dir_object)
Ref b_dir(Obj, Args a) {
    positional_only(a, "dir", 0, 1);
    if (a.npos == 0) throw NotImplemented("dir() without an argument (the calling frame's names)");
    Obj obj = a.pos(0);
    bool found = false;
    Ref result = call_special(obj, "__dir__", {}, &found);
    if (!found) {
        refuse_absent_attribute(obj, N("__dir__"));
        raise_new("TypeError", "object does not provide __dir__");
    }
    Ref list = invoke(Obj::of(types().list), {result.get()});
    auto& items = static_cast<List*>(list.get().object())->items;
    for (Obj x : items)
        if (as_str(x) == nullptr) throw NotImplemented("dir() of names that are not all str (list.sort: step 3b)");
    std::stable_sort(items.begin(), items.end(), [](Obj x, Obj y) { return as_str(x)->text < as_str(y)->text; });
    return list;
}

namespace {
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;                        // owned by the type, which lives as long as the program
    c->attrs.set(N(name), Obj::of(f));
}
}  // namespace

void init_imports(Module* sys) {
    sys_module() = sys;
    ClassObject* mt = types().module;
    method(mt, "__new__", module_new_m, Binding::Function);
    method(mt, "__init__", module_init_m);
    method(mt, "__repr__", module_repr_m);
    method(mt, "__dir__", module_dir_m);
    mt->attrs.set(N("__dict__"), Obj::of(new GetSet("__dict__", mt, module_dict_get, nullptr)));
    Ref modules = dict_new();
    interp_modules() = static_cast<Dict*>(modules.get().object());
    incref(modules.get());                       // the interpreter's own count, for the program's lifetime
    dict_set(sys->dict, Obj::of(N("modules")), modules.get());
    dict_set(interp_modules(), Obj::of(N("sys")), Obj::of(sys));
    dict_set(interp_modules(), Obj::of(N("builtins")), Obj::of(builtins_module()));
    import_func() = dict_get(builtins_module()->dict, Obj::of(N("__import__")));
    lazy_import_func() = dict_get(builtins_module()->dict, Obj::of(N("__lazy_import__")));
    ClassObject* lt = types().lazy_import;
    method(lt, "__new__", lazy_new_m, Binding::Function);
    method(lt, "__repr__", lazy_repr_m);
    method(lt, "resolve", lazy_resolve_m);
    lt->set_attr(N("__doc__"), cpython_doc("type:lazy_import"));
    types().module->set_attr(N("__doc__"), cpython_doc("type:module"));
}

}  // namespace bella
