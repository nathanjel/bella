// runtime/src/staged.cpp -- exec, eval and compile in a compiled program (docs/staging.md, spec section 8). A
// standard library's definition builds a text and hands it over: the build compiled every text the dry run recorded,
// keyed by the function that makes the call, the operation and the source as given. A hit runs that code in the
// namespaces it was given; anything else is the E-01 refusal, which no except clause sees.
#include <algorithm>
#include <string_view>

#include "bella/runtime.hpp"

namespace bella {
namespace {
struct Table {
    std::span<const StagedText> texts;
    std::span<const StagedSite> refused;
    std::span<const StagedSite> unstaged;
    std::span<const StagedCompile> compiles;
};
constexpr int FUTURE_MASK = 0x3FE0000;           // every CO_FUTURE_* flag, as the dry run keys a compile
constexpr int PYCF_MASK = 0x1FE0000;             // PyCF_MASK: the CO_FUTURE_* flags compile() accepts
constexpr int PYCF_MASK_OBSOLETE = 0x0010;       // CO_NESTED
constexpr int PYCF_ONLY_AST = 0x0400;
constexpr int PYCF_COMPILE_MASK = 0x0400 | 0x2000 | 0x1000 | 0x0200 | 0x4000 | 0x8000;
Table& table() {
    static Table t;
    return t;
}
const Str* N(const char* s) { return intern(s); }

// the function that makes the call, as the dry run names it: module:qualname. What CPython runs without a frame of
// its own (the prelude) has no site.
detail::FrameRecord* python_caller() {
    detail::FrameRecord* f = detail::current_frame();
    while (f != nullptr && !f->code->shown) f = f->caller;
    return f;
}
std::string site_of(detail::FrameRecord* f) {
    if (f == nullptr) return "<module>:<module>";
    Obj name = dict_get(f->module->dict, Obj::of(N("__name__")));
    const Str* s = name.is_unset() ? nullptr : as_str(name);
    return (s != nullptr ? s->text : std::string("None")) + ":" + f->code->qualname;
}
[[noreturn]] void refused(const std::string& why) { throw NotImplemented(why); }
const StagedSite* site_row(std::span<const StagedSite> rows, const std::string& site) {
    for (const StagedSite& r : rows)
        if (site == r.site) return &r;
    return nullptr;
}
// A text the dry run did not stage. When the dry run of the program's own module body was ended early (a body's effects on the
// world are refused at build time: review F17 #7), the build left the reason under "*", which is no site, and the refusal says it
[[noreturn]] void not_staged(const std::string& what) {
    const StagedSite* confined = site_row(table().unstaged, "*");
    refused(confined == nullptr ? what : what + "; " + confined->message);
}

const StagedText& find_text(const std::string& site, const char* kind, Obj source) {
    if (const StagedSite* r = site_row(table().refused, site)) refused(r->message);
    bool bytes = is_bytes_like(source);
    std::string data = bytes ? bytes_data(source) : as_str(source)->text;
    for (const StagedText& t : table().texts)
        if (t.bytes == bytes && site == t.site && std::string_view(kind) == t.kind && std::string_view(t.source, t.length) == data) {
            if (t.body == nullptr) refused(std::string(kind) + " at " + site + ": " + t.why);
            return t;
        }
    if (const StagedSite* r = site_row(table().unstaged, site)) refused(r->message);
    not_staged(std::string("E-01: ") + kind + " at " + site + " of a text the dry run did not stage (spec section 8)");
}

Dict* builtins_of_globals(Dict* globals) {       // _PyEval_BuiltinsFromGlobals: a module's dict, or the mapping itself
    Obj given = dict_get(globals, Obj::of(N("__builtins__")));
    if (is_kind(given, Kind::Module)) return static_cast<Module*>(given.object())->dict;
    if (is_kind(given, Kind::Dict)) return static_cast<Dict*>(given.object());
    throw NotImplemented("__builtins__ that is not a module or a dict, in exec or eval");
}

// the source and the namespaces, once builtin_eval_impl and builtin_exec_impl have checked them; exec's closure (Unset
// for eval), which a code object's free variables would take: a staged compile's code, a module's, has none
Ref run(const char* kind, const std::string& site, Obj source, Obj globals, Obj locals, Obj closure = Obj{}) {
    if (!is_exact_dict(globals) && !is_kind(globals, Kind::Dict)) throw NotImplemented(std::string(kind) + "() with a frozendict's globals");
    auto* d = static_cast<Dict*>(globals.object());
    if (is_frozendict(globals)) throw NotImplemented(std::string(kind) + "() with a frozendict's globals");
    if (dict_get(d, Obj::of(N("__builtins__"))).is_unset())   // _PyEval_EnsureBuiltins
        dict_set(d, Obj::of(N("__builtins__")), Obj::of(builtins_module()->dict));
    bool has_closure = !closure.is_unset() && closure != None();
    Ref (*body)(Module*) = nullptr;
    if (is_kind(source, Kind::CodeKind)) {       // the code a staged compile() returned, compiled at build time
        auto* code = static_cast<CodeObject*>(source.object());
        if (const StagedSite* r = site_row(table().refused, site)) refused(r->message);
        if (code->staged == nullptr)
            refused(std::string(kind) + "() of a function's code object at " + site + " (a function's body run as a module's: E-07)");
        if (has_closure) raise_new("TypeError", "cannot use a closure with this code object");
        body = code->staged->body;
    } else {
        if (has_closure) raise_new("TypeError", "closure can only be used when source is a code object");
        if (as_str(source) == nullptr && !is_bytes_like(source))
            raise_new("TypeError", std::string(kind) + "() arg 1 must be a string, bytes or code object");
        body = find_text(site, kind, source).body;
    }
    if (locals.is_unset()) throw NotImplemented(std::string(kind) + "() in a function or class body, with the frame's locals (PEP 667; locals(): step 3b)");
    Ref module = own(new Module(d, builtins_of_globals(d)));
    if (locals != globals) {                     // the text's top level reads and writes the locals (LOAD_NAME, STORE_NAME); its functions see globals
        if (!is_kind(locals, Kind::Dict) || is_frozendict(locals))
            throw NotImplemented(std::string(kind) + " at " + site + " with a locals mapping that is not a dict");
        auto* m = static_cast<Module*>(module.get().object());
        m->locals = static_cast<Dict*>(locals.object());
        incref(m->locals);
    }
    return body(static_cast<Module*>(module.get().object()));
}
// The frame's locals are asked for from inside a comprehension: CPython inlines it (PEP 709), so its variables are that frame's
// own and the text may read them; here they are the helper's, out of reach. Inside a function the call stops in any case; at
// module level it would run without them, so it stops here (review F17 #6)
void frame_locals_reachable(const char* kind, const detail::FrameRecord* caller) {
    if (caller != nullptr && caller->comprehensions > 0)
        throw NotImplemented(std::string(kind) + "() in a comprehension, with the frame's locals (PEP 709: the comprehension's variables are the frame's)");
}
// PyEval_GetGlobals and _PyEval_GetFrameLocals: a module's frame has its globals for locals; a function's a snapshot
void from_frame(const char* kind, detail::FrameRecord* caller, Obj& globals, Obj& locals) {
    if (caller == nullptr) raise_new("TypeError", std::string(kind) + " must be given globals and locals when called without a frame");
    bool asks_globals = globals == None();
    if (asks_globals) globals = Obj::of(caller->module->dict);
    if (locals == None()) {
        if (!asks_globals) {
            locals = globals;
            return;
        }
        // a module's frame has its globals for locals, or, when it is a text's that was given locals, those (review F17 #8);
        // a function's snapshot or a class body's namespace: Unset until the text is known to be run
        if (std::string_view(caller->code->name) == "<module>")
            locals = caller->module->locals != nullptr ? Obj::of(caller->module->locals) : globals;
        else
            locals = Obj{};
    }
}
// source, then the optional ones by position or name; what the clinic says of each
void arguments(Args a, const char* name, std::initializer_list<const char*> keywords, std::vector<Obj>& given) {
    std::size_t max = keywords.size() + 1;
    if (a.npos + a.nkw > max) raise_new("TypeError", std::string(name) + "() takes at most " + std::to_string(max) + (a.npos == 0 ? " keyword" : "") + " arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    if (a.npos > 3) raise_new("TypeError", std::string(name) + "() takes at most 3 positional arguments (" + std::to_string(a.npos) + " given)");
    if (a.npos < 1) raise_new("TypeError", std::string(name) + "() takes at least 1 positional argument (0 given)");
    given.assign(max, None());
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::size_t j = 1;
        for (const char* p : keywords) {
            if (a.kwnames[k]->text == p) break;
            ++j;
        }
        if (j == max) throw NotImplemented(std::string(name) + "() with an unexpected keyword argument (the suggestion in its message)");
        if (j < a.npos) raise_new("TypeError", "argument for " + std::string(name) + "() given by name ('" + a.kwnames[k]->text + "') and position (" + std::to_string(j + 1) + ")");
        given[j] = a.kw(k);
    }
}

// _PyArg_UnpackKeywords for compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, *, module=None,
// _feature_version=-1), its checks in its order; what is absent stays Unset
constexpr std::initializer_list<const char*> COMPILE_PARAMETERS = {"source", "filename", "mode", "flags", "dont_inherit", "optimize",
                                                                   "module", "_feature_version"};
void compile_arguments(Args a, Obj (&given)[8]) {
    const char* const* names = COMPILE_PARAMETERS.begin();
    auto keyword = [&](const char* name) {
        for (std::size_t k = 0; k < a.nkw; ++k)
            if (a.kwnames[k]->text == name) return a.kw(k);
        return Obj{};
    };
    if (a.npos + a.nkw > 8)
        raise_new("TypeError", std::string("compile() takes at most 8 ") + (a.npos == 0 ? "keyword " : "") + "arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    if (a.npos > 6) raise_new("TypeError", "compile() takes at most 6 positional arguments (" + std::to_string(a.npos) + " given)");
    for (std::size_t i = 0; i < a.npos; ++i) given[i] = a.pos(i);
    std::size_t left = a.nkw;
    for (std::size_t i = a.npos; i < 8; ++i) {
        if (left == 0 && i >= 3) break;
        given[i] = left == 0 ? Obj{} : keyword(names[i]);
        if (!given[i].is_unset()) --left;
        else if (i < 3) raise_new("TypeError", std::string("compile() missing required argument '") + names[i] + "' (pos " + std::to_string(i + 1) + ")");
    }
    if (left == 0) return;
    for (std::size_t i = 0; i < a.npos; ++i)
        if (!keyword(names[i]).is_unset())
            raise_new("TypeError", std::string("argument for compile() given by name ('") + names[i] + "') and position (" + std::to_string(i + 1) + ")");
    for (std::size_t k = 0; k < a.nkw; ++k)
        if (std::find_if(COMPILE_PARAMETERS.begin(), COMPILE_PARAMETERS.end(), [&](const char* p) { return a.kwnames[k]->text == p; }) == COMPILE_PARAMETERS.end())
            unexpected_keyword("compile()", a.kwnames[k], COMPILE_PARAMETERS);
}
int c_int(Obj v) {                               // PyLong_AsInt: __index__, then a C int's range
    Ref i = int_index_of(v);
    std::int64_t x = 0;
    if (!int_fits_i64(i.get(), x) || x < INT32_MIN || x > INT32_MAX) raise_new("OverflowError", "Python int too large to convert to C int");
    return static_cast<int>(x);
}
const Str* filename_of(Obj v) {                  // PyUnicode_FSDecoder: a str; bytes and os.PathLike stop by name
    if (const Str* s = as_str(v)) {
        if (s->text.find('\0') != std::string::npos) raise_new("ValueError", "embedded null character");
        return s;
    }
    if (is_kind(v, Kind::Bytes) || !type_lookup(type_of(v), N("__fspath__")).is_unset())
        throw NotImplemented("compile() with a filename that is bytes or os.PathLike");
    raise_new("TypeError", "expected str, bytes or os.PathLike object, not " + type_of(v)->name);
}
bool is_ast(Obj v) {                             // PyAST_Check: an instance of ast.AST, which exists once _ast is imported
    Obj m = dict_get(sys_modules(), Obj::of(N("_ast")));
    if (m.is_unset() || !is_kind(m, Kind::Module)) return false;
    Obj cls = dict_get(static_cast<Module*>(m.object())->dict, Obj::of(N("AST")));
    return !cls.is_unset() && is_kind(cls, Kind::Class) && is_subclass(type_of(v), static_cast<ClassObject*>(cls.object()));
}
// an exception's argument, encoded by pipeline/build.py encoded_value: N, T, F, i<digits>;, s<length>:<UTF-8>, t<count>;
Ref decoded(std::string_view& in) {
    auto upto = [&](char end) {
        std::size_t at = in.find(end);
        std::string_view digits = in.substr(0, at);
        in.remove_prefix(at + 1);
        return digits;
    };
    char tag = in.front();
    in.remove_prefix(1);
    switch (tag) {
        case 'N': return none_ref();
        case 'T': return Ref::steal(boolean(true));
        case 'F': return Ref::steal(boolean(false));
        case 'i': {
            std::string_view d = upto(';');
            bool negative = d.front() == '-';
            return int_from_digits(negative, negative ? d.substr(1) : d, 10);
        }
        case 's': {
            std::size_t n = std::stoul(std::string(upto(':')));
            Ref s = str_new(in.substr(0, n));
            in.remove_prefix(n);
            return s;
        }
        case 't': {
            std::size_t n = std::stoul(std::string(upto(';')));
            std::vector<Obj> items;
            for (std::size_t i = 0; i < n; ++i) items.push_back(decoded(in).release());
            return tuple_steal(std::move(items));
        }
        default: throw NotImplemented("a staged compile's exception arguments the runtime cannot read");
    }
}
}  // namespace

void register_staged(std::span<const StagedText> texts, std::span<const StagedSite> refused_sites, std::span<const StagedSite> unstaged,
                     std::span<const StagedCompile> compiles) {
    table() = Table{texts, refused_sites, unstaged, compiles};
}
Ref b_eval(Obj, Args a) {                        // builtin_eval_impl: eval(source, /, globals=None, locals=None)
    std::vector<Obj> given;
    arguments(a, "eval", {"globals", "locals"}, given);
    Obj source = given[0], globals = given[1], locals = given[2];
    if (locals != None() && !is_mapping(locals)) raise_new("TypeError", "locals must be a mapping");
    if (globals != None() && !is_kind(globals, Kind::Dict))
        raise_new("TypeError", is_mapping(globals) ? "globals must be a real dict or a frozendict; try eval(expr, {}, mapping)" : "globals must be a dict or a frozendict");
    detail::FrameRecord* caller = python_caller();
    std::string site = site_of(caller);
    if (globals == None() && locals == None()) frame_locals_reachable("eval", caller);
    from_frame("eval", caller, globals, locals);
    return run("eval", site, source, globals, locals);
}
Ref b_exec(Obj, Args a) {                        // builtin_exec_impl: exec(source, /, globals=None, locals=None, *, closure=None)
    std::vector<Obj> given;
    arguments(a, "exec", {"globals", "locals", "closure"}, given);
    if (a.npos == 4) raise_new("TypeError", "exec() takes at most 3 positional arguments (4 given)");
    Obj source = given[0], globals = given[1], locals = given[2], closure = given[3];
    detail::FrameRecord* caller = python_caller();
    std::string site = site_of(caller);
    if (globals == None() && locals == None()) frame_locals_reachable("exec", caller);
    from_frame("exec", caller, globals, locals);
    if (!is_kind(globals, Kind::Dict)) raise_new("TypeError", "exec() globals must be a dict or a frozendict, not " + fully_qualified_name(type_of(globals)));
    if (!locals.is_unset() && !is_mapping(locals)) raise_new("TypeError", "locals must be a mapping or None, not " + type_of(locals)->name);
    run("exec", site, source, globals, locals, closure);
    return none_ref();
}
// builtin_compile_impl, after its clinic: the checks CPython makes of the arguments, then the outcome the dry run staged
// for this call (docs/staging.md section 4): the code, or the exception compiling raised. Another text is E-01.
Ref b_compile(Obj, Args a) {
    Obj given[8];
    compile_arguments(a, given);
    Obj source = given[0];
    const Str* filename = filename_of(given[1]);
    const Str* mode = as_str(given[2]);
    if (mode == nullptr) raise_new("TypeError", "compile() argument 'mode' must be str, not " + type_of(given[2])->name);
    if (mode->text.find('\0') != std::string::npos) raise_new("ValueError", "embedded null character");
    int flags = given[3].is_unset() ? 0 : c_int(given[3]);
    bool dont_inherit = !given[4].is_unset() && truth(given[4]);
    int optimize = given[5].is_unset() ? -1 : c_int(given[5]);
    Obj modname = given[6].is_unset() ? None() : given[6];
    int feature_version = given[7].is_unset() ? -1 : c_int(given[7]);
    if (flags & ~(PYCF_MASK | PYCF_MASK_OBSOLETE | PYCF_COMPILE_MASK)) raise_new("ValueError", "compile(): unrecognised flags");
    if (optimize < -1 || optimize > 2) raise_new("ValueError", "compile(): invalid optimize value");
    if (modname != None() && as_str(modname) == nullptr)
        raise_new("TypeError", "compile() argument 'module' must be str or None, not " + fully_qualified_name(type_of(modname)));
    if (mode->text != "exec" && mode->text != "eval" && mode->text != "single") {
        if (mode->text == "func_type" && !(flags & PYCF_ONLY_AST)) raise_new("ValueError", "compile() mode 'func_type' requires flag PyCF_ONLY_AST");
        if (mode->text != "func_type")
            raise_new("ValueError", flags & PYCF_ONLY_AST ? "compile() mode must be 'exec', 'eval', 'single' or 'func_type'"
                                                          : "compile() mode must be 'exec', 'eval' or 'single'");
    }
    detail::FrameRecord* caller = python_caller();
    std::string site = site_of(caller);
    if (is_ast(source)) refused("compile() of an ast tree at " + site + " (the compiler at runtime: E-01)");
    bool bytes = is_kind(source, Kind::Bytes);
    if (as_str(source) == nullptr && !is_bytes_like(source)) raise_new("TypeError", "compile() arg 1 must be a string, bytes or AST object");
    if (flags & PYCF_ONLY_AST) refused("compile() to an ast tree at " + site + " (the parser at runtime: E-01)");
    if (const StagedSite* r = site_row(table().refused, site)) refused(r->message);
    if (!bytes && as_str(source) == nullptr) refused("E-01: compile at " + site + " of a " + type_of(source)->name + " (the dry run stages str and bytes)");
    // PyEval_MergeCompilerFlags: the calling frame's __future__ features, as the dry run merged them into the key
    int merged = flags | (dont_inherit || caller == nullptr ? 0 : caller->code->flags & FUTURE_MASK);
    std::string data = bytes ? bytes_data(source) : as_str(source)->text;
    const Str* module = modname == None() ? nullptr : as_str(modname);
    for (const StagedCompile& c : table().compiles) {
        if (c.bytes != bytes || site != c.site || std::string_view(c.source, c.length) != data || filename->text != c.filename ||
            mode->text != c.mode || merged != c.flags || optimize != c.optimize || feature_version != c.feature_version ||
            (module == nullptr) != (c.module == nullptr) || (module != nullptr && module->text != c.module))
            continue;
        if (c.raises != nullptr) {
            std::string_view encoded(c.raise_args, c.raise_args_length);
            Ref args = decoded(encoded);
            Obj cls = dict_get(builtins_module()->dict, Obj::of(intern(c.raises)));   // the class by its name, as the model's getattr(builtins, ...)
            if (cls.is_unset() || !is_kind(cls, Kind::Class) || !is_subclass(static_cast<ClassObject*>(cls.object()), exception_class("BaseException")))
                refused(std::string("E-01: compile at ") + site + " raised " + c.raises + ", which is not a built-in exception");
            const std::vector<Obj>& items = static_cast<Tuple*>(args.get().object())->items;
            Ref exc = invoke(cls, Args{items.data(), items.size()});
            raise(exc.get());
        }
        if (c.body == nullptr) refused(c.why);
        auto* code = new CodeObject(c.code);
        code->staged = &c;
        return own(code);
    }
    if (const StagedSite* r = site_row(table().unstaged, site)) refused(r->message);
    not_staged("E-01: compile at " + site + " of a text the dry run did not stage (spec section 8)");
}
}  // namespace bella
