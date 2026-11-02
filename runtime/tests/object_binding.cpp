// The thin binding of TODO task 3: the oracle's world (refmodel/oracle.py) built on
// runtime/include/bella/object.hpp, behind a C API that runtime/tests/object_differential.py loads
// with ctypes and drives in lockstep with the reference model and CPython.
//
// Operations arrive as one line of text ("set 3 x t:5", "get 0 y 1", ...); each returns its outcome
// as a Python literal, ('value', v) or ('error', 'AttributeError'), with the same normal form the
// oracle uses: tagged objects as ('T', 't5'), descriptor and hook results as the tuples the
// oracle's Python callables return. Deaths are logged in order, as the oracle logs them.
#include "bella/object.hpp"

#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace bella;

namespace {

const std::vector<std::string> NAMES = {"x", "y", "z", "s", "t", "w", "cv", "g1", "attr", "k"};
constexpr std::size_t RUNTIME_CLASS = 6;
constexpr std::size_t RUNTIME_OBJECTS[] = {8, 9};

Obj marker(std::string text) {
    auto* m = new Marker(std::move(text));
    incref(m);
    return Obj::of(m);
}

std::string quote(const std::string& s) { return "'" + s + "'"; }

Function* native(std::function<Obj(std::span<const Obj>)> f) { return new Function(std::move(f)); }

struct Descriptor {
    int idx;
    ClassObject* cls;
    std::unordered_map<const Object*, Obj> store;     // the oracle's store, keyed by the object
};

struct World {
    std::vector<ClassObject*> classes;
    std::vector<Instance*> objects;                   // the program's variables: one count each
    std::map<std::string, std::unique_ptr<Site>> sites;
    std::vector<std::unique_ptr<Descriptor>> descriptors;
    std::vector<ClassObject*> made;                   // every class this world made, to dispose of
    ClassObject* tracked;
    std::vector<std::string> deaths;

    World() {
        tracked = cls({.name = "Tracked"});
        ClassObject* A = cls({.name = "A", .promoted = {"x", "y"}, .attrs = {{"cv", Obj::small(10)}}});
        ClassObject* B = cls({.name = "B", .bases = {A}, .promoted = {"z"}});
        ClassObject* S = cls({.name = "S", .bases = {A}, .slots = std::vector<std::string>{"s"}});
        ClassObject* T = cls({.name = "T", .slots = std::vector<std::string>{"t"}});
        ClassObject* E = cls({.name = "E", .bases = {T}, .slots = std::vector<std::string>{}});
        auto* hook = native([](std::span<const Obj> a) -> Obj {
            const auto* name = static_cast<const Str*>(a[1].object());
            if (name->text.starts_with("g")) return marker("('G', " + quote(name->text) + ")");
            throw AttributeError(name->text);
        });
        ClassObject* G = cls({.name = "G", .attrs = {{"__getattr__", Obj::of(hook)}}});
        classes = {A, B, S, T, E, G, runtime_class(0)};
        ClassObject* R = classes[RUNTIME_CLASS];
        for (ClassObject* c : {A, A, B, B, S, T, E, G, R, R}) objects.push_back(held(new_instance(c)));
        for (const auto& n : NAMES) sites[n] = std::make_unique<Site>();
        sites["<computed>"] = std::make_unique<Site>();
    }

    ~World() {
        for (Instance* o : objects) {
            forget(o);
            decref(o);
        }
        // newest first: a subclass dies before its bases, which it holds (as CPython frees them)
        for (auto it = made.rbegin(); it != made.rend(); ++it) (*it)->dispose();
    }

    ClassObject* cls(const ClassSpec& spec) {
        ClassObject* c = make_class(spec);
        made.push_back(c);
        return c;
    }

    static Instance* held(Instance* o) {
        incref(o);
        return o;
    }

    ClassObject* runtime_class(int variant) {
        switch (variant) {
            case 0: return cls({.name = "R0", .slots = std::vector<std::string>{"k", "x"}});
            case 1: return cls({.name = "R1", .slots = std::vector<std::string>{"x"}});
            case 2: return cls({.name = "R2", .promoted = {"y"}, .attrs = {{"x", Obj::small(7)}}});
            case 3: return cls({.name = "R3", .bases = {classes[0]}, .promoted = {"k"}});
            default: {
                auto* hook = native([](std::span<const Obj> a) -> Obj {
                    const auto* name = static_cast<const Str*>(a[1].object());
                    if (name->text == "x" || name->text == "k") return marker("('R4', " + quote(name->text) + ")");
                    throw AttributeError(name->text);
                });
                return cls({.name = "R4", .attrs = {{"__getattr__", Obj::of(hook)}}});
            }
        }
    }

    // ---- values ----
    // "i:42" an integer; "t:5" a fresh tagged object, held by the caller until the operation returns
    Obj value(const std::string& v) {
        if (v.starts_with("t:")) {
            Instance* t = new_instance(tracked);
            t->tag = std::stoll(v.substr(2));
            incref(t);
            return Obj::of(t);
        }
        return Obj::small(std::stoll(v.substr(2)));
    }

    std::string lit(Obj v) const {
        if (v.is_small()) return std::to_string(v.small_value());
        if (v.is_unset()) return "None";
        Object* o = v.object();
        if (o->kind == Kind::Marker) return static_cast<Marker*>(o)->text;
        if (o->kind == Kind::Instance) {
            std::int64_t tag = static_cast<Instance*>(o)->tag;
            if (tag >= 0) return "('T', 't" + std::to_string(tag) + "')";
            if (tag <= -2) return "('T', 'd" + std::to_string(-tag - 2) + "')";
        }
        return "<object>";
    }

    // ---- descriptors ----
    Descriptor& make_descriptor(bool data) {
        auto d = std::make_unique<Descriptor>();
        d->idx = static_cast<int>(descriptors.size());
        Descriptor* dp = d.get();
        auto* get = native([dp](std::span<const Obj> a) -> Obj {
            auto it = dp->store.find(a[1].object());
            if (it != dp->store.end()) {
                incref(it->second);
                return it->second;
            }
            return marker("('DESC', " + std::to_string(dp->idx) + ")");
        });
        std::vector<std::pair<std::string, Obj>> attrs = {{"__get__", Obj::of(get)}};
        if (data) attrs.emplace_back("__set__", Obj::of(setter(dp)));
        d->cls = cls({.name = "Desc" + std::to_string(d->idx), .attrs = attrs});
        descriptors.push_back(std::move(d));
        return *dp;
    }

    static Function* setter(Descriptor* dp) {
        return native([dp](std::span<const Obj> a) -> Obj {
            Obj v = a[2];
            incref(v);
            auto [it, fresh] = dp->store.try_emplace(a[1].object(), v);
            if (!fresh) decref(std::exchange(it->second, v));
            return Obj::small(0);
        });
    }

    // the descriptor stores forget a dropped object, in descriptor order, as the oracle does
    void forget(Instance* o) {
        for (auto& d : descriptors) {
            auto it = d->store.find(o);
            if (it != d->store.end()) {
                Obj v = it->second;
                d->store.erase(it);
                decref(v);
            }
        }
    }

    // ---- operations ----
    std::string get(std::size_t i, const std::string& name, bool computed) {
        Ref r = getattr(objects[i], intern(name), sites[computed ? "<computed>" : name].get());
        return "('value', " + lit(r.get()) + ")";
    }

    std::string apply(const std::string& line) {
        std::istringstream in(line);
        std::string op;
        in >> op;
        try {
            if (op == "get") {
                std::size_t i; std::string name; int computed;
                in >> i >> name >> computed;
                return get(i, name, computed != 0);
            }
            if (op == "set") {
                std::size_t i; std::string name, v;
                in >> i >> name >> v;
                Ref temp = Ref::steal(value(v));
                setattr(objects[i], intern(name), temp.get());
                return "('value', None)";
            }
            if (op == "del") {
                std::size_t i; std::string name;
                in >> i >> name;
                delattr(objects[i], intern(name));
                return "('value', None)";
            }
            if (op == "expose") {
                std::size_t i;
                in >> i;
                Ref d1 = expose_dict(objects[i]);
                Ref d2 = expose_dict(objects[i]);
                std::string out = "('value', ('stable', ";
                out += d1.get() == d2.get() ? "True" : "False";
                out += ", [";
                bool first = true;
                for (auto& [k, v] : static_cast<DictObject*>(d1.get().object())->map.items()) {
                    out += (first ? "" : ", ") + std::string("(") + quote(k->text) + ", " + lit(v) + ")";
                    first = false;
                }
                return out + "]))";
            }
            if (op == "replace_dict") {
                std::size_t i; long src;
                in >> i >> src;
                if (src < 0) {
                    set_dict(objects[i], new DictObject());
                } else {
                    Ref d = expose_dict(objects[static_cast<std::size_t>(src)]);
                    set_dict(objects[i], static_cast<DictObject*>(d.get().object()));
                }
                return "('value', None)";
            }
            if (op == "set_class_attr") {
                std::size_t ci; std::string name, v;
                in >> ci >> name >> v;
                Ref temp = Ref::steal(value(v));
                classes[ci]->set_attr(intern(name), temp.get());
                return "('value', None)";
            }
            if (op == "del_class_attr") {
                std::size_t ci; std::string name;
                in >> ci >> name;
                classes[ci]->del_attr(intern(name));
                return "('value', None)";
            }
            if (op == "install_descriptor") {
                std::size_t ci; std::string name; int data;
                in >> ci >> name >> data;
                Descriptor& d = make_descriptor(data != 0);
                Instance* desc = new_instance(d.cls);
                desc->tag = -2 - d.idx;
                Ref temp = Ref::share(Obj::of(desc));       // the caller's reference until the operation returns
                classes[ci]->set_attr(intern(name), temp.get());
                return "('value', None)";
            }
            if (op == "promote_descriptor") {
                std::size_t di;
                in >> di;
                Descriptor* d = descriptors[di].get();
                d->cls->set_attr(intern("__set__"), Obj::of(setter(d)));
                return "('value', None)";
            }
            if (op == "demote_descriptor") {
                std::size_t di;
                in >> di;
                descriptors[di]->cls->del_attr(intern("__set__"));
                return "('value', None)";
            }
            if (op == "drop") {
                std::size_t i;
                in >> i;
                Instance* old = objects[i];
                forget(old);
                objects[i] = held(new_instance(old->cls));
                decref(old);
                return "('value', None)";
            }
            if (op == "recreate_class") {
                int variant;
                in >> variant;
                ClassObject* old = classes.back();
                for (std::size_t k = 0; k < std::size(RUNTIME_OBJECTS); ++k) {
                    Instance* o = objects.back();
                    objects.pop_back();
                    forget(o);
                    decref(o);
                }
                old->dispose();
                std::erase(made, old);
                classes.pop_back();
                ClassObject* fresh = runtime_class(variant);
                classes.push_back(fresh);
                for (std::size_t k = 0; k < std::size(RUNTIME_OBJECTS); ++k) objects.push_back(held(new_instance(fresh)));
                return "('value', " + quote(fresh->name) + ")";
            }
            return "('error', 'UnknownOperation')";
        } catch (const AttributeError&) {
            return "('error', 'AttributeError')";
        } catch (const TypeError&) {
            return "('error', 'TypeError')";
        }
    }

    std::string sweep() {
        std::string out = "[";
        bool first = true;
        for (std::size_t i = 0; i < objects.size(); ++i)
            for (const auto& n : NAMES) {
                std::string r;
                try {
                    Ref v = getattr(objects[i], intern(n), sites[n].get());
                    r = "('value', " + lit(v.get()) + ")";
                } catch (const AttributeError&) {
                    r = "('error', 'AttributeError')";
                }
                out += (first ? "" : ", ") + r;
                first = false;
            }
        return out + "]";
    }
};

World* current = nullptr;
thread_local std::string result;

const char* answer(std::string s) {
    result = std::move(s);
    return result.c_str();
}

}  // namespace

extern "C" {

void* bw_new(int checking) {
    heap().checking = checking != 0;
    heap().quarantine = checking != 0;
    auto* w = new World();
    current = w;
    heap().on_death = [](Object* o) {
        auto* i = static_cast<Instance*>(o);
        if (current == nullptr) return;
        if (i->tag >= 0) current->deaths.push_back("'t" + std::to_string(i->tag) + "'");
        else if (i->tag <= -2) current->deaths.push_back("'d" + std::to_string(-i->tag - 2) + "'");
    };
    return w;
}

void bw_free(void* w) {
    current = static_cast<World*>(w);
    delete static_cast<World*>(w);
    current = nullptr;
    empty_graveyard();
}

const char* bw_apply(void* w, const char* line) {
    auto* world = static_cast<World*>(w);
    current = world;
    try {
        return answer(world->apply(line));
    } catch (const ModelError& e) {
        return answer(std::string("MODEL ERROR: ") + e.what());
    }
}

const char* bw_sweep(void* w) {
    auto* world = static_cast<World*>(w);
    current = world;
    try {
        return answer(world->sweep());
    } catch (const ModelError& e) {
        return answer(std::string("MODEL ERROR: ") + e.what());
    }
}

const char* bw_deaths(void* w) {
    auto* world = static_cast<World*>(w);
    std::string out = "[";
    for (std::size_t i = 0; i < world->deaths.size(); ++i) out += (i ? ", " : "") + world->deaths[i];
    world->deaths.clear();
    return answer(out + "]");
}

unsigned long long bw_hits(void* w) {
    unsigned long long n = 0;
    for (auto& [k, s] : static_cast<World*>(w)->sites) n += s->hits;
    return n;
}

}  // extern "C"
