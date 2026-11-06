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
};
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

const StagedText& find_text(const std::string& site, const char* kind, Obj source) {
    if (const StagedSite* r = site_row(table().refused, site)) refused(r->message);
    bool bytes = is_bytes_like(source);
    std::string data = bytes ? bytes_data(source) : as_str(source)->text;
    for (const StagedText& t : table().texts)
        if (t.bytes == bytes && site == t.site && std::string_view(kind) == t.kind && std::string_view(t.source, t.length) == data) {
            if (t.body == nullptr) refused(std::string(kind) + " at " + site + ": the staged text does not lower yet: " + t.why);
            return t;
        }
    if (const StagedSite* r = site_row(table().unstaged, site)) refused(r->message);
    refused(std::string("E-01: ") + kind + " at " + site + " of a text the dry run did not stage (spec section 8)");
}

Dict* builtins_of_globals(Dict* globals) {       // _PyEval_BuiltinsFromGlobals: a module's dict, or the mapping itself
    Obj given = dict_get(globals, Obj::of(N("__builtins__")));
    if (is_kind(given, Kind::Module)) return static_cast<Module*>(given.object())->dict;
    if (is_kind(given, Kind::Dict)) return static_cast<Dict*>(given.object());
    throw NotImplemented("__builtins__ that is not a module or a dict, in exec or eval");
}

// the source and the namespaces, once builtin_eval_impl and builtin_exec_impl have checked them
Ref run(const char* kind, const std::string& site, Obj source, Obj globals, Obj locals) {
    if (!is_exact_dict(globals) && !is_kind(globals, Kind::Dict)) throw NotImplemented(std::string(kind) + "() with a frozendict's globals");
    auto* d = static_cast<Dict*>(globals.object());
    if (is_frozendict(globals)) throw NotImplemented(std::string(kind) + "() with a frozendict's globals");
    if (dict_get(d, Obj::of(N("__builtins__"))).is_unset())   // _PyEval_EnsureBuiltins
        dict_set(d, Obj::of(N("__builtins__")), Obj::of(builtins_module()->dict));
    if (as_str(source) == nullptr && !is_bytes_like(source))  // a code object would stop at compile(), which made it
        raise_new("TypeError", std::string(kind) + "() arg 1 must be a string, bytes or code object");
    const StagedText& text = find_text(site, kind, source);
    if (locals.is_unset()) throw NotImplemented(std::string(kind) + "() in a function or class body, with the frame's locals (PEP 667; locals(): step 3b)");
    if (locals != globals) throw NotImplemented(std::string(kind) + " at " + site + " with a locals mapping of its own (the texts' second entry point, decision S-1)");
    Ref module = own(new Module(d, builtins_of_globals(d)));
    return text.body(static_cast<Module*>(module.get().object()));
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
        // a function's snapshot, or a class body's namespace: Unset until the text is known to be run
        locals = std::string_view(caller->code->name) == "<module>" ? globals : Obj{};
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
}  // namespace

void register_staged(std::span<const StagedText> texts, std::span<const StagedSite> refused_sites, std::span<const StagedSite> unstaged) {
    table() = Table{texts, refused_sites, unstaged};
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
    from_frame("exec", caller, globals, locals);
    if (!is_kind(globals, Kind::Dict)) raise_new("TypeError", "exec() globals must be a dict or a frozendict, not " + fully_qualified_name(type_of(globals)));
    if (!locals.is_unset() && !is_mapping(locals)) raise_new("TypeError", "locals must be a mapping or None, not " + type_of(locals)->name);
    if (closure != None()) raise_new("TypeError", "closure can only be used when source is a code object");
    run("exec", site, source, globals, locals);
    return none_ref();
}
Ref b_compile(Obj, Args) {
    throw NotImplemented("compile() at " + site_of(python_caller()) + " (a staged compile's code object: docs/staging.md)");
}
}  // namespace bella
