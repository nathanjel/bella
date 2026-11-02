// User code that empties the class it runs from, on object.hpp; prints what
// runtime/tests/object_reentrancy.py prints under CPython 3.15.2 (review 2026-11-02, A8-1).
// Built without quarantine, under ASan and UBSan by `make object-test`: a lookup that kept only a
// borrowed descriptor or __getattr__ hook while that code ran would read freed memory.
#include "bella/object.hpp"

#include <iostream>
#include <memory>
#include <string>

using namespace bella;

namespace {

struct Noisy {                      // a function has no finaliser: its captured guard tells its death
    std::string text;
    ~Noisy() { std::cout << text << '\n'; }
};

Obj text(const std::string& t) { return Obj::of(intern(t)); }

// class Desc: __get__ deletes the attribute from the owner's class, then returns or fails
ClassObject* descriptor_class(const std::string& n, bool fail) {
    auto* get = new Function([n, fail](std::span<const Obj> a) -> Obj {
        std::cout << "  get: deletes " << n << " from the class\n";
        static_cast<ClassObject*>(a[2].object())->del_attr(intern("x"));
        std::cout << "  get: returns\n";
        if (fail) throw AttributeError("x");
        return text("value");
    });
    auto* del = new Function([n](std::span<const Obj>) -> Obj {
        std::cout << "  dies " << n << '\n';
        return Obj::small(0);       // the result is discarded
    });
    return make_class({.name = "Desc", .attrs = {{"__get__", Obj::of(get)}, {"__del__", Obj::of(del)}}});
}

std::string shown(const Ref& v) { return static_cast<const Str*>(v.get().object())->text; }

}  // namespace

int main() {
    heap().checking = true;         // checks on, quarantine off: a freed object is gone at once
    heap().quarantine = false;

    auto* c1 = make_class({.name = "C1"});
    c1->set_attr(intern("x"), Obj::of(new_instance(descriptor_class("desc1", false))));
    std::cout << "1. descriptor deletes itself:\n";
    {
        Ref obj = Ref::share(Obj::of(new_instance(c1)));
        Ref v = getattr(static_cast<Instance*>(obj.get().object()), intern("x"));
        std::cout << "  caller got " << shown(v) << '\n';
    }

    auto* c2 = make_class({.name = "C2"});
    c2->set_attr(intern("x"), Obj::of(new_instance(descriptor_class("desc2", true))));
    auto guard = std::make_shared<Noisy>("  dies hook");
    // after the deletion the function reads its own captures: freed memory, were it not owned
    auto* hook = new Function([c2, guard, after = std::string("  hook returns")](std::span<const Obj>) -> Obj {
        std::cout << "  hook called; deletes itself from the class\n";
        c2->del_attr(intern("__getattr__"));
        std::cout << after << '\n';
        return text("from hook");
    });
    guard.reset();                  // the function's copy is the guard's only owner
    c2->set_attr(intern("__getattr__"), Obj::of(hook));
    std::cout << "2. descriptor deletes itself and fails; the hook deletes itself:\n";
    {
        Ref obj = Ref::share(Obj::of(new_instance(c2)));
        Ref v = getattr(static_cast<Instance*>(obj.get().object()), intern("x"));
        std::cout << "  caller got " << shown(v) << '\n';
    }

    // the descriptor deletes the hook the lookup found, then fails: the hook still runs
    auto* c3 = make_class({.name = "C3"});
    auto guard3 = std::make_shared<Noisy>("  dies hook3");
    auto* hook3 = new Function([guard3, said = std::string("  hook called")](std::span<const Obj>) -> Obj {
        std::cout << said << '\n';
        return text("from hook");
    });
    guard3.reset();
    auto* get3 = new Function([c3](std::span<const Obj>) -> Obj {
        std::cout << "  get: deletes the hook from the class\n";
        c3->del_attr(intern("__getattr__"));
        std::cout << "  get: fails\n";
        throw AttributeError("x");
    });
    c3->set_attr(intern("x"), Obj::of(new_instance(make_class({.name = "Desc3", .attrs = {{"__get__", Obj::of(get3)}}}))));
    c3->set_attr(intern("__getattr__"), Obj::of(hook3));
    std::cout << "3. the descriptor deletes the hook, then fails:\n";
    {
        Ref obj = Ref::share(Obj::of(new_instance(c3)));
        Ref v = getattr(static_cast<Instance*>(obj.get().object()), intern("x"));
        std::cout << "  caller got " << shown(v) << '\n';
    }
    return 0;
}
