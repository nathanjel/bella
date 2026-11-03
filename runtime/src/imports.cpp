// runtime/src/imports.cpp -- the import system's C half (bella/runtime.hpp; docs/emitter.md
// section 7): IMPORT_NAME, IMPORT_FROM and import * as Python/ceval.c and Python/intrinsics.c run
// them, builtins.__import__ as Python/import.c's PyImport_ImportModuleLevelObject, and the module
// type's attribute access, repr and dir as Objects/moduleobject.c (CPython 3.15.2). Where
// import.c calls into importlib._bootstrap, this calls the prelude's copy of it
// (runtime/prelude/bootstrap.py): _find_and_load and _handle_fromlist. The finder is the closed
// world's registry of compiled modules (spec section 8), which the program's main unit hands over.
#include "bella/runtime.hpp"

#include <algorithm>
#include <climits>
#include <cstdint>
#include <unordered_map>

namespace bella {

namespace {
const Str* N(const char* s) { return intern(s); }

struct Compiled {
    ModuleBody body;
    std::string origin;
    bool package;
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

// PyObject_GetOptionalAttr: the attribute, or Unset when getting it raises AttributeError
Ref optional_attr(Obj o, const Str* name) {
    try {
        return getattr(o, name);
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
        return Ref{};
    }
}

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

// An ImportWarning: the default filters ignore it (`ignore::ImportWarning`), and a compiled program
// cannot change them before the warnings module compiles (step 3b; PYTHONWARNINGS and -W are not
// read, D-18), so it has no effect, as in CPython. Once a warnings module is loaded the filters can
// differ, and the warning is refused until it is implemented.
void import_warning(const std::string& message) {
    if (!dict_get(interp_modules(), Obj::of(N("warnings"))).is_unset() ||
        !dict_get(interp_modules(), Obj::of(N("_warnings"))).is_unset())
        throw NotImplemented("the ImportWarning '" + message + "' (warnings: step 3b)");
}

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
            if (!truth(eq.get()))
                throw NotImplemented("the DeprecationWarning '__package__ != __spec__.parent' (warnings: step 3b)");
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
    if (!as_int(level, v)) raise_new("TypeError", "'" + type_of(level)->name + "' object cannot be interpreted as an integer");
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

namespace {
Module* native_sys();
}  // namespace

// ---- the registry the program's main unit hands over ----
void register_modules(std::span<const ModuleEntry> modules, const char* program_dir) {
    for (const ModuleEntry& e : modules) registry()[e.name] = Compiled{e.body, e.origin, e.package};
    sys_path_0() = program_dir;
    // sys.path reflects the build (D-18): the program's directory, where the build found its
    // modules; the standard library's entries come with the standard library (step 3b)
    Ref dir = str_new(program_dir);
    Ref path = list_new({dir.get()});
    dict_set(native_sys()->dict, Obj::of(N("path")), path.get());
}
const std::string& program_directory() { return sys_path_0(); }

namespace {
void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;                        // owned by the type, which lives as long as the program
    c->attrs.set(N(name), Obj::of(f));
}
}  // namespace

namespace {
Module*& sys_module() {
    static Module* m = nullptr;
    return m;
}
Module* native_sys() { return sys_module(); }
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
}
Dict* sys_modules() { return interp_modules(); }

// The prelude's primitives for bootstrap.py, which no program can name.
Ref i_bella_find(Obj, Args a) {                  // the registry's (origin, is_package), or None
    positional_only(a, "_bella_find", 1, 1);
    const Str* name = as_str(a.pos(0));
    auto it = registry().find(name->text);
    if (it == registry().end()) {
        if (is_stdlib_name(a.pos(0)) || name->text == "_frozen_importlib" || name->text == "_frozen_importlib_external")
            throw NotImplemented("importing '" + name->text + "' (the standard library: step 3b)");
        return none_ref();
    }
    if (it->second.body == nullptr)              // a namespace package: CPython's NamespaceLoader
        throw NotImplemented("importing '" + name->text + "', a namespace package (step 3b)");
    Ref origin = str_new(it->second.origin);
    return tuple_new({origin.get(), boolean(it->second.package)});
}
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
    it->second.body(m);
    return none_ref();
}
Ref i_bella_import_warning(Obj, Args a) {        // _warnings.warn(msg, ImportWarning): see import_warning
    positional_only(a, "_bella_import_warning", 1, 1);
    import_warning(as_str(a.pos(0))->text);
    return none_ref();
}
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
        ensure_initialized(mod.get());
        Ref check = get_module(abs_name.get());
        if (check.get() != mod.get()) mod = call_bootstrap("_find_and_load", {abs_name.get(), import_func()});
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
    std::string_view how = as_str(mode)->text;
    if (how == "lazy") throw NotImplemented("a lazy import (PEP 810: the next increment of step 3b)");
    if (how == "default" && ns == globals) {
        // __lazy_modules__ at module level: the module is lazy if the list names it (D-18: the
        // lazy-imports mode is always "normal")
        Obj listed = dict_get(m->dict, Obj::of(N("__lazy_modules__")));
        if (!listed.is_unset()) {
            Ref abs = absolute_name(name, globals, level_value(level));
            Ref in = compare(CmpOp::In, abs.get(), listed);
            if (truth(in.get())) throw NotImplemented("a lazy import by __lazy_modules__ (PEP 810: the next increment of step 3b)");
        }
    }
    // the frame's builtins: a compiled module's are the builtins module's dict
    Obj f = dict_get(builtins_module()->dict, Obj::of(N("__import__")));
    if (f.is_unset()) raise_new("ImportError", "__import__ not found");
    Obj locals = ns.is_unset() ? None() : ns;
    if (f == import_func()) return import_module_level(name, globals, locals, fromlist, level_value(level));
    return invoke(f, {name, globals, locals, fromlist, level});
}

// ---- IMPORT_FROM: _PyEval_ImportFrom ----
Ref import_from(Obj v, const Str* name) {
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
            name = getitem(all.get(), index.get());   // PySequence_GetItem
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
        if (is_kind(locals, Kind::Dict) && !is_subclass_instance(locals)) dict_set(static_cast<Dict*>(locals.object()), name.get(), value.get());
        else setitem(locals, name.get(), value.get());
    }
}

// ---- the module type (Objects/moduleobject.c) ----
// _Py_module_getattro_impl: the generic lookup with the module's dict, then the module's own
// __getattr__ (PEP 562), then CPython's message for why the name is missing
Ref module_getattr(Obj obj, const Str* name) {
    auto* m = static_cast<Module*>(obj.object());
    ClassObject* c = type_of(obj);
    Obj found = type_lookup(c, name);
    if (!found.is_unset() && is_data_descriptor(found)) return descr_get(found, obj, Obj::of(c));
    Obj v = dict_get(m->dict, Obj::of(name));
    if (!v.is_unset()) return Ref::share(v);
    if (!found.is_unset()) return descr_get(found, obj, Obj::of(c));
    Obj hook = dict_get(m->dict, Obj::of(N("__getattr__")));
    if (!hook.is_unset()) {
        Ref held = Ref::share(hook);
        Ref name_ref = Ref::share(Obj::of(name));
        return invoke(held.get(), {name_ref.get()});
    }
    refuse_absent_attribute(obj, name);
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
    Obj dirfunc = dict_get(m->dict, Obj::of(N("__dir__")));
    if (!dirfunc.is_unset()) {
        Ref held = Ref::share(dirfunc);
        return invoke(held.get(), {});
    }
    Ref keys = list_new({});
    for (auto& e : m->dict->entries)
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
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::string_view kn = a.kwnames[k]->text;
        if (kn == "name" && name.is_unset()) name = a.kw(k);
        else if (kn == "doc" && doc.is_unset()) doc = a.kw(k);
        else raise_new("TypeError", "module() got an unexpected keyword argument '" + a.kwnames[k]->text + "'");
    }
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

}  // namespace bella
