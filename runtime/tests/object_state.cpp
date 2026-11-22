// A built-in type's fields that have no name (RL-507), on object.hpp; prints what runtime/tests/object_state.py
// prints from the reference model. Built under ASan and UBSan by `make object-test`. Part 5 is the header's own
// form of it: the slots hidden once the class, a class that derives from it and an object exist (hide_slots), which
// the model states as a class made with them hidden.
#include "bella/object.hpp"

#include <functional>
#include <iostream>
#include <string>
#include <vector>

using namespace bella;

namespace {

std::vector<std::string> deaths;

const Str* N(const char* n) { return intern(n); }

std::string shown(Obj v) {
    if (v.is_small()) return std::to_string(v.small_value());
    return "t" + std::to_string(static_cast<Instance*>(v.object())->tag);
}

void attempt(const std::string& what, const std::function<std::string()>& f) {
    try {
        std::string v = f();
        std::cout << "  " << what << ": " << v << '\n';
    } catch (const AttributeError&) {
        std::cout << "  " << what << ": AttributeError\n";
    } catch (const TypeError&) {
        std::cout << "  " << what << ": TypeError\n";
    }
}
std::string get(Instance* o, const char* n) { return shown(getattr(o, N(n)).get()); }
std::string field(Instance* o, const char* n) { return shown(state_get(o, N(n))); }
std::string set(Instance* o, const char* n, Obj v) { setattr(o, N(n), v); return "done"; }
std::string del(Instance* o, const char* n) { delattr(o, N(n)); return "done"; }
std::string field_del(Instance* o, const char* n) { state_del(o, N(n)); return "done"; }

void show_deaths(const char* when) {
    std::cout << "  " << when << ": [";
    for (std::size_t i = 0; i < deaths.size(); ++i) std::cout << (i ? ", " : "") << "'" << deaths[i] << "'";
    std::cout << "]\n";
}

}  // namespace

int main() {
    heap().checking = true;
    heap().quarantine = false;
    heap().on_death = [](Object* o) {
        if (o->kind == Kind::Instance && static_cast<Instance*>(o)->tag >= 0) deaths.push_back("t" + std::to_string(static_cast<Instance*>(o)->tag));
    };
    auto* T = make_class({.name = "T"});
    auto tagged = [T](std::int64_t n) {
        Instance* i = new_instance(T);
        i->tag = n;
        return Ref::share(Obj::of(i));
    };
    using Names = std::vector<std::string>;

    std::cout << "1. a field has no name\n";
    auto* E = make_class({.name = "enumerate", .slots = Names{"_count", "_it"}, .hidden = {"_count", "_it"}});
    auto* P = make_class({.name = "Page", .bases = {E}});
    Instance* plain = new_instance(E);
    Instance* p = new_instance(P);
    incref(plain);
    incref(p);
    state_set(plain, N("_count"), Obj::small(0));
    state_set(p, N("_count"), Obj::small(1));
    std::cout << "  the class has it: " << (E->lookup(N("_count")) ? "True" : "False") << '\n';
    attempt("getattr of a plain one", [&] { return get(plain, "_count"); });
    attempt("setattr of a plain one", [&] { return set(plain, "_count", Obj::small(5)); });
    attempt("delattr of a plain one", [&] { return del(plain, "_count"); });
    attempt("its field", [&] { return field(plain, "_count"); });
    attempt("a field never stored", [&] { return field(plain, "_it"); });
    attempt("deleting a field never stored", [&] { return field_del(plain, "_it"); });

    std::cout << "2. the attribute of a class that derives\n";
    attempt("getattr before any store", [&] { return get(p, "_count"); });
    attempt("setattr", [&] { return set(p, "_count", Obj::small(2)); });
    attempt("getattr", [&] { return get(p, "_count"); });
    attempt("its field", [&] { return field(p, "_count"); });
    attempt("delattr", [&] { return del(p, "_count"); });
    attempt("delattr again", [&] { return del(p, "_count"); });
    attempt("its field", [&] { return field(p, "_count"); });

    std::cout << "3. a slot and a kept attribute under the name\n";
    auto* R = make_class({.name = "ref", .slots = Names{"_hash"}, .hidden = {"_hash"}});
    for (ClassObject* cls : {make_class({.name = "IdRef", .bases = {R}, .slots = Names{"_hash"}}),
                             make_class({.name = "Kept", .bases = {R}, .promoted = {"_hash"}})}) {
        Instance* o = new_instance(cls);
        incref(o);
        state_set(o, N("_hash"), Obj::small(7));
        setattr(o, N("_hash"), Obj::small(1000));
        attempt(cls->name + ": getattr", [&] { return get(o, "_hash"); });
        attempt(cls->name + ": its field", [&] { return field(o, "_hash"); });
        delattr(o, N("_hash"));
        attempt(cls->name + ": getattr after delattr", [&] { return get(o, "_hash"); });
        attempt(cls->name + ": its field after delattr", [&] { return field(o, "_hash"); });
        attempt(cls->name + ": the field deleted", [&] { return field_del(o, "_hash"); });
        attempt(cls->name + ": its field then", [&] { return field(o, "_hash"); });
        attempt(cls->name + ": deleted again", [&] { return field_del(o, "_hash"); });
        decref(o);
    }

    std::cout << "4. released in the order the built-in type declares them; a store keeps the new value first\n";
    {
        auto* M = make_class({.name = "M", .slots = Names{"b", "_a", "c"}, .hidden = {"_a", "c"}});
        auto* Nn = make_class({.name = "N", .bases = {M}, .slots = Names{"a", "d"}, .hidden = {"d"}});
        Instance* m = new_instance(Nn);
        incref(m);
        state_set(m, N("c"), tagged(1).get());
        setattr(m, N("b"), tagged(2).get());
        state_set(m, N("_a"), tagged(3).get());
        state_set(m, N("d"), tagged(4).get());
        setattr(m, N("a"), tagged(5).get());
        state_set(m, N("c"), tagged(6).get());
        show_deaths("after the second store");
        decref(m);
        show_deaths("after the object");
    }

    std::cout << "5. hidden once the class and a class that derives from it exist\n";
    deaths.clear();
    {
        auto* Q = make_class({.name = "Q", .slots = Names{"u", "v", "w"}});
        auto* QS = make_class({.name = "QS", .bases = {Q}});
        Instance* q = new_instance(QS);
        incref(q);
        setattr(q, N("u"), tagged(7).get());             // while the slots have their names still
        setattr(q, N("v"), tagged(8).get());
        setattr(q, N("w"), tagged(9).get());
        hide_slots(Q, {N("u"), N("w")});
        std::cout << "  the class has them: " << (Q->lookup(N("u")) ? "True" : "False") << ' ' << (Q->lookup(N("v")) ? "True" : "False") << ' '
                  << (Q->lookup(N("w")) ? "True" : "False") << '\n';
        attempt("getattr", [&] { return get(q, "u"); });
        attempt("its field", [&] { return field(q, "u"); });
        attempt("setattr", [&] { return set(q, "u", Obj::small(11)); });
        attempt("getattr", [&] { return get(q, "u"); });
        attempt("its field", [&] { return field(q, "u"); });
        attempt("the slot that stays", [&] { return get(q, "v"); });
        auto* QT = make_class({.name = "QT", .bases = {Q}, .slots = Names{"u"}});
        Instance* t = new_instance(QT);
        incref(t);
        setattr(t, N("u"), Obj::small(4));
        state_set(t, N("u"), Obj::small(5));
        attempt("a later class's slot of the name", [&] { return get(t, "u"); });
        attempt("its field", [&] { return field(t, "u"); });
        decref(t);
        decref(q);
        show_deaths("after the object");
    }
    std::cout << "6. a member the type shows: the type's own cell, under any name, and read-only where the type says\n";
    {
        auto* Pt = make_class({.name = "partial", .slots = Names{"func", "args", "_p"}, .hidden = {"func", "args", "_p"},
                               .members = {"func", "args"}, .readonly = {"args"}});
        auto* Sh = make_class({.name = "Shadowed", .bases = {Pt}, .attrs = {{"func", Obj::small(99)}, {"saved", *Pt->attrs.find(N("args"))}}});
        Instance* o = new_instance(Sh);
        incref(o);
        state_set(o, N("func"), Obj::small(1));
        state_set(o, N("args"), Obj::small(2));
        std::cout << "  the class has them: " << (Pt->lookup(N("func")) ? "True" : "False") << ' ' << (Pt->lookup(N("args")) ? "True" : "False") << ' '
                  << (Pt->lookup(N("_p")) ? "True" : "False") << '\n';
        attempt("the name a deriving class has", [&] { return get(o, "func"); });
        attempt("the field", [&] { return field(o, "func"); });
        attempt("the member under another name", [&] { return get(o, "saved"); });
        attempt("a read-only member", [&] { return get(o, "args"); });
        attempt("a store through it", [&] { return set(o, "args", Obj::small(5)); });
        attempt("a delete through it", [&] { return del(o, "args"); });
        attempt("the type's own store", [&] { state_set(o, N("args"), Obj::small(7)); return std::string("done"); });
        attempt("read again", [&] { return get(o, "args"); });
        Instance* q2 = new_instance(Pt);
        incref(q2);
        state_set(q2, N("func"), Obj::small(3));
        attempt("a store through a member that takes one", [&] { return set(q2, "func", Obj::small(4)); });
        attempt("its field", [&] { return field(q2, "func"); });
        attempt("a delete through it", [&] { return del(q2, "func"); });
        attempt("its field then", [&] { return field(q2, "func"); });
        decref(q2);
        decref(o);
    }
    std::cout << "7. a slot a class declares again: a cell for each declaration (RL-541)\n";
    deaths.clear();
    {
        auto* D = make_class({.name = "D", .slots = Names{"x", "a"}});
        auto* F = make_class({.name = "F", .bases = {D}, .slots = Names{"x"}});
        auto* G = make_class({.name = "G", .bases = {F}, .slots = Names{"x", "m"},
                              .attrs = {{"base_x", *D->attrs.find(N("x"))}, {"middle_x", *F->attrs.find(N("x"))}}});
        Instance* g = new_instance(G);
        incref(g);
        std::cout << "  cells behind the name: " << D->shadowed.size() << ' ' << F->shadowed.size() << ' ' << G->shadowed.size() << '\n';
        attempt("the base's before any store", [&] { return get(g, "base_x"); });
        setattr(g, N("x"), tagged(1).get());
        setattr(g, N("base_x"), tagged(2).get());
        setattr(g, N("middle_x"), tagged(3).get());
        setattr(g, N("a"), tagged(4).get());
        setattr(g, N("m"), tagged(5).get());
        attempt("the name", [&] { return get(g, "x"); });
        attempt("the base's member", [&] { return get(g, "base_x"); });
        attempt("the middle class's member", [&] { return get(g, "middle_x"); });
        Site site;
        auto read = [&](const char* n) { return shown(getattr(g, N(n), &site).get()); };
        std::string first = read("x") + read("x") + read("base_x") + read("base_x");
        std::cout << "  one place, read twice each: " << first << ", hits " << site.hits << '\n';
        Ref kept = Ref::share(*G->attrs.find(N("x")));
        G->del_attr(N("x"));
        attempt("the name once the class's member is gone", [&] { return read("x"); });
        attempt("again", [&] { return read("x"); });
        std::cout << "  hits " << site.hits << '\n';
        attempt("a store by the name", [&] { return set(g, "x", tagged(6).get()); });
        show_deaths("after the store");
        attempt("the middle class's member", [&] { return get(g, "middle_x"); });
        attempt("a delete by the name", [&] { return del(g, "x"); });
        attempt("deleted again", [&] { return del(g, "x"); });
        attempt("the base's member still", [&] { return get(g, "base_x"); });
        G->set_attr(N("x"), kept.get());
        attempt("the member put back", [&] { return get(g, "x"); });
        attempt("the middle class's cell is empty", [&] { return get(g, "middle_x"); });
        setattr(g, N("middle_x"), tagged(7).get());
        deaths.clear();
        decref(g);
        show_deaths("after the object");
        // a member of a class that is no base, which a class has under a name: it applies to none of that class's objects
        auto* Else = make_class({.name = "Elsewhere", .slots = Names{"x"}});
        auto* B = make_class({.name = "Borrowed", .bases = {D}, .slots = Names{}, .attrs = {{"x", *Else->attrs.find(N("x"))}, {"own", *D->attrs.find(N("x"))}}});
        Instance* b = new_instance(B);
        incref(b);
        attempt("a member of a class that is no base: a read", [&] { return get(b, "x"); });
        attempt("a store", [&] { return set(b, "x", Obj::small(1)); });
        attempt("a delete", [&] { return del(b, "x"); });
        attempt("the base's own member, a store", [&] { return set(b, "own", Obj::small(2)); });
        attempt("and a read", [&] { return get(b, "own"); });
        decref(b);
        // a slot under the name of a field of the built-in base: the base's field is a cell behind it (RL-564)
        auto* BE = make_class({.name = "BaseException", .native = Names{"__dict__", "args", "cause"}});
        for (const char* n : {"args", "cause"}) BE->set_attr(N(n), Obj::of(new SlotDescriptor(N(n))));
        auto* E = make_class({.name = "E", .bases = {BE}, .slots = Names{"args", "__dict__"}});
        auto* K = make_class({.name = "K", .bases = {E}, .attrs = {{"base_args", *BE->attrs.find(N("args"))}}});
        std::cout << "  cells behind the name: " << BE->shadowed.size() << ' ' << E->shadowed.size() << ' ' << K->shadowed.size() << '\n';
        Instance* k = new_instance(K);
        incref(k);
        setattr(k, N("base_args"), tagged(11).get());
        attempt("the slot before any store", [&] { return get(k, "args"); });
        setattr(k, N("args"), tagged(12).get());
        setattr(k, N("cause"), tagged(13).get());
        setattr(k, N("other"), tagged(14).get());
        attempt("the slot", [&] { return get(k, "args"); });
        attempt("the base's field", [&] { return get(k, "base_args"); });
        deaths.clear();
        decref(k);
        show_deaths("after the object");
    }
    std::cout << "8. a built-in type's dealloc: where it clears its weak references and its dict (RL-565)\n";
    {
        struct Kind8 { const char* name; Names fields; Names release; bool own_dict; };
        for (const Kind8& kind : {Kind8{"deque", {"items"}, {"__weakref__", "items"}, false},
                                  Kind8{"partial", {"func", "args"}, {"__weakref__", "func", "args", "__dict__"}, true},
                                  Kind8{"BytesIO", {}, {"__dict__", "__weakref__"}, true},
                                  Kind8{"enumerate", {"it"}, {"it"}, false}}) {
            Names base_slots = kind.fields;
            if (kind.own_dict) base_slots.push_back("__dict__");
            if (std::find(kind.release.begin(), kind.release.end(), "__weakref__") != kind.release.end()) base_slots.push_back("__weakref__");
            auto* B = make_class({.name = kind.name, .slots = base_slots, .hidden = kind.fields, .release = kind.release});
            for (int shape = 0; shape < 3; ++shape) {            // the type itself, a class with a dict, a class with slots
                ClassObject* K = shape == 0 ? B : shape == 1 ? make_class({.name = "K", .bases = {B}})
                                                              : make_class({.name = "K", .bases = {B}, .slots = Names{"b", "a", "__weakref__"}});
                if (shape == 2 && B->has_weakref) K = make_class({.name = "K", .bases = {B}, .slots = Names{"b", "a"}});
                Instance* o = new_instance(K);
                incref(o);
                std::int64_t n = 20;
                for (const auto& f : kind.fields) state_set(o, N(f.c_str()), tagged(n++).get());
                if (shape == 1 || (shape == 0 && kind.own_dict)) setattr(o, N("x"), tagged(30).get());
                if (shape == 2) {
                    setattr(o, N("a"), tagged(31).get());
                    setattr(o, N("b"), tagged(32).get());
                }
                deaths.clear();
                bool watched = K->has_weakref;
                if (watched) {
                    auto* callback = new Function([](std::span<const Obj>) -> Obj {
                        deaths.push_back("weak");
                        return Obj::small(0);
                    });
                    Object* holder = new Marker("weak");
                    incref(holder);
                    weak_link(holder, o, Obj::of(callback), WeakKind::Other);
                    decref(o);
                    show_deaths((std::string(kind.name) + ", shape " + std::to_string(shape)).c_str());
                    decref(holder);
                } else {
                    decref(o);
                    show_deaths((std::string(kind.name) + ", shape " + std::to_string(shape) + ", no weak reference").c_str());
                }
            }
        }
    }
    {
        auto* BE = make_class({.name = "BaseException", .native = Names{"__dict__", "args", "cause"}});
        for (const char* n : {"args", "cause"}) BE->set_attr(N(n), Obj::of(new SlotDescriptor(N(n))));
        try {
            make_class({.name = "OwnDealloc", .bases = {BE}, .release = Names{"__weakref__"}});
            std::cout << "  a dealloc of its own over a base with fields: made\n";
        } catch (const ModelError&) {
            std::cout << "  a dealloc of its own over a base with fields: refused\n";
        }
        Instance* made = new_instance(make_class({.name = "UnsupportedOperation", .bases = {BE}}));
        incref(made);
        setattr(made, N("args"), tagged(40).get());
        setattr(made, N("cause"), tagged(41).get());
        setattr(made, N("x"), tagged(42).get());
        deaths.clear();
        decref(made);
        show_deaths("a class made by calling type over it");
    }
    std::cout << "9. a chain longer than the native stack: what is put off, and when it goes (RL-624)\n";
    {
        auto chain = [&](const char* next, const char* value, int length, std::vector<Instance*>* nodes) {
            auto* Node = make_class({.name = "Node", .slots = Names{next, value, "__weakref__"}});
            Instance* head = nullptr;
            for (int i = length - 1; i >= 0; --i) {              // node i holds node i + 1 and a value of its own, t(200 + i)
                Instance* node = new_instance(Node);
                incref(node);
                if (head != nullptr) {
                    setattr(node, N(next), Obj::of(head));
                    decref(head);
                }
                setattr(node, N(value), tagged(200 + i).get());
                head = node;
                if (nodes != nullptr) nodes->insert(nodes->begin(), node);
            }
            return head;
        };
        detail::StackWatch& watch = detail::stack_watch;
        for (auto [next, value] : {std::pair{"a_nxt", "b_pay"}, std::pair{"b_nxt", "a_pay"}}) {
            for (int room : {-1, 4, 5, 7}) {
                Instance* head = chain(next, value, 12, nullptr);
                deaths.clear();
                watch.room = room;
                decref(head);
                watch.room = -1;
                std::cout << "  the next node in " << next << ", room for " << (room < 0 ? std::string("any") : std::to_string(room)) << ": [";
                for (std::size_t i = 0; i < deaths.size(); ++i) std::cout << (i ? ", " : "") << "'" << deaths[i] << "'";
                std::cout << "] | put off: " << watch.later << '\n';
            }
        }
        std::vector<Instance*> nodes;
        Instance* head = chain("a_nxt", "b_pay", 6, &nodes);
        auto* callback = new Function([](std::span<const Obj>) -> Obj {
            deaths.push_back("weak");
            return Obj::small(0);
        });
        Object* holder = new Marker("weak");
        incref(holder);
        weak_link(holder, nodes[2], Obj::of(callback), WeakKind::Other);
        deaths.clear();
        watch.room = 3;                                      // no room even at the outermost dealloc: what is put off waits
        decref(head);
        std::cout << "  room for 3: [";
        for (std::size_t i = 0; i < deaths.size(); ++i) std::cout << (i ? ", " : "") << "'" << deaths[i] << "'";
        std::cout << "] | put off: " << watch.later << " | a weak reference to a node put off reaches: "
                  << (weak_target(weak_record(holder)) == nullptr ? "nothing" : "the node") << '\n';
        watch.room = -1;
        deaths.clear();
        {
            Ref other = tagged(300);                         // the first dealloc that ends with room lets them go
        }
        std::cout << "  then, at another object's end: [";
        for (std::size_t i = 0; i < deaths.size(); ++i) std::cout << (i ? ", " : "") << "'" << deaths[i] << "'";
        std::cout << "] | put off: " << watch.later << '\n';
        decref(holder);
    }
    decref(plain);
    decref(p);
    return 0;
}
