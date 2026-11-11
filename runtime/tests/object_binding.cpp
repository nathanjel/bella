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
constexpr std::size_t RUNTIME_CLASS = 8;
constexpr std::size_t RUNTIME_OBJECTS[] = {10, 11};

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
    std::vector<Object*> weaks;                       // the program's weak references: one count each
    std::vector<Object*> reviver_weaks;
    std::vector<Instance*> kept;                      // what a finaliser kept
    std::unordered_map<const Object*, int> reviver_number;
    int weak_numbers = 0, revivals = 0;

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
        ClassObject* X = cls({.name = "X", .dict_kind = DictKind::Plain});       // a C type's own dict slot: an ordinary dict
        ClassObject* I = cls({.name = "I", .dict_kind = DictKind::Shared});      // no values in the object: a dict of its own
        I->has_weakref = false;                                                  // nor room for a weak reference (tp_itemsize)
        classes = {A, B, S, T, E, G, X, I, runtime_class(0)};
        ClassObject* R = classes[RUNTIME_CLASS];
        for (ClassObject* c : {A, A, B, B, S, T, E, G, X, I, R, R}) objects.push_back(held(new_instance(c)));
        for (const auto& n : NAMES) sites[n] = std::make_unique<Site>();
        sites["<computed>"] = std::make_unique<Site>();
    }

    ~World() {
        for (Instance* o : objects) {
            forget(o);
            decref(o);
        }
        for (auto it = kept.rbegin(); it != kept.rend(); ++it) decref(*it);
        kept.clear();
        for (Object* w : weaks) decref(w);
        for (Object* w : reviver_weaks) decref(w);
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
            case 0: return cls({.name = "R0", .slots = std::vector<std::string>{"x", "k"}});
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
        if (auto it = reviver_number.find(o); it != reviver_number.end()) return "('R', " + std::to_string(it->second) + ")";
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
    void drop(std::size_t i) {                        // the program drops its object; a fresh one of its class takes its place
        Instance* old = objects[i];
        forget(old);
        objects[i] = held(new_instance(old->cls));
        decref(old);
    }

    void store_tagged(std::size_t i, const std::string& name, const std::string& tagged) {
        Ref v = Ref::steal(value(tagged));            // held by the object alone once it is stored
        setattr(objects[i], intern(name), v.get());
    }

    template <class F>
    static std::string outcome(F&& f) {
        try {
            f();
        } catch (const AttributeError&) {
            return "('error', 'AttributeError')";
        } catch (const TypeError&) {
            return "('error', 'TypeError')";
        }
        return "('value', None)";
    }

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
                for (auto& e : static_cast<DictObject*>(d1.get().object())->entries) {
                    if (e.key.is_unset()) continue;
                    out += (first ? "" : ", ") + std::string("(") + quote(static_cast<const Str*>(e.key.object())->text) + ", " + lit(e.value) + ")";
                    first = false;
                }
                return out + "]))";
            }
            if (op == "del_dict") {              // the del, the first thing asked after it, and the probe (refmodel World.op_del_dict)
                std::size_t i; std::string then, name, v, n1, v1, n2, v2;
                in >> i >> then >> name >> v >> n1 >> v1 >> n2 >> v2;
                Ref temp = Ref::steal(value(v));
                del_dict(objects[i]);
                std::string first = "('value', None)";
                try {
                    if (then == "get") first = get(i, name, false);
                    else if (then == "set") setattr(objects[i], intern(name), temp.get());
                    else if (then == "del") delattr(objects[i], intern(name));
                    else if (then == "expose") {
                        Ref d = expose_dict(objects[i]);
                        first = "('value', " + std::to_string(static_cast<DictObject*>(d.get().object())->used) + ")";
                    }
                } catch (const AttributeError&) {
                    first = "('error', 'AttributeError')";
                } catch (const TypeError&) {
                    first = "('error', 'TypeError')";
                }
                if (n1 != "-") {
                    for (const auto& [n, tagged] : {std::pair{n1, v1}, std::pair{n2, v2}}) {
                        Ref held = Ref::steal(value(tagged));
                        setattr(objects[i], intern(n), held.get());
                    }
                    del_dict(objects[i]);
                }
                return "('value', " + first + ")";
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
                drop(i);
                return "('value', None)";
            }
            if (op == "probe") {                 // fresh instances asked which dict they have (refmodel World.op_probe)
                std::size_t i; int delete_first; std::string n1, n2, t1, t2, t3, t4;
                in >> i >> delete_first >> n1 >> n2 >> t1 >> t2 >> t3 >> t4;
                drop(i);
                std::string out = "('value', [";
                if (delete_first) out += outcome([&] { delattr(objects[i], intern(n2)); }) + ", ";
                out += outcome([&] { store_tagged(i, n1, t1); store_tagged(i, n2, t2); }) + ", ";
                drop(i);
                out += outcome([&] { store_tagged(i, n2, t3); store_tagged(i, n1, t4); });
                drop(i);
                return out + "])";
            }
            if (op == "weak_new") {
                std::size_t i; std::string with;
                in >> i >> with;
                Object* target = objects[i];
                int number = weak_numbers++;
                if (!objects[i]->cls->has_weakref) throw TypeError("cannot create weak reference");
                if (with == "False") {
                    if (Object* shared = weak_basic(target, WeakKind::BasicRef)) {
                        std::size_t at = static_cast<std::size_t>(std::find(weaks.begin(), weaks.end(), shared) - weaks.begin());
                        return "('value', " + std::to_string(at) + ")";
                    }
                    Object* holder = marker("weak").object();
                    weak_link(holder, target, Obj{}, WeakKind::BasicRef);
                    weaks.push_back(holder);
                    return "('value', -1)";
                }
                auto* callback = native([this, number](std::span<const Obj> a) -> Obj {
                    bool dead = weak_record(a[0].object())->target == nullptr;
                    deaths.push_back("('cb', " + std::to_string(number) + ", " + (dead ? "True" : "False") + ")");
                    return Obj::small(0);
                });
                Object* holder = marker("weak").object();
                weak_link(holder, target, Obj::of(callback), WeakKind::Other);
                weaks.push_back(holder);
                return "('value', -1)";
            }
            if (op == "weak_call") {
                std::size_t i;
                in >> i;
                if (i >= weaks.size()) return "('value', None)";
                Object* target = weak_record(weaks[i])->target;
                if (target == nullptr) return "('value', 'dead')";
                for (std::size_t k = 0; k < objects.size(); ++k)
                    if (objects[k] == target) return "('value', " + std::to_string(k) + ")";
                return "('value', 'elsewhere')";
            }
            if (op == "weak_drop") {
                std::size_t i;
                in >> i;
                if (i >= weaks.size()) return "('value', None)";
                Object* w = weaks[i];
                weaks.erase(weaks.begin() + static_cast<std::ptrdiff_t>(i));
                decref(w);
                return "('value', None)";
            }
            if (op == "revive") {
                std::size_t i; std::string name, v;
                in >> i >> name >> v;
                int number = revivals++;
                auto* fin = native([this, number](std::span<const Obj> a) -> Obj {
                    deaths.push_back("('fin', " + std::to_string(number) + ")");
                    auto* o = static_cast<Instance*>(a[0].object());
                    incref(o);
                    kept.push_back(o);
                    return Obj::small(0);
                });
                ClassObject* c = cls({.name = "Reviver", .slots = std::vector<std::string>{"value", "__weakref__"}, .attrs = {{"__del__", Obj::of(fin)}}});
                Instance* vm = new_instance(c);
                reviver_number[vm] = number;
                Ref hold = Ref::share(Obj::of(vm));
                Ref held = Ref::steal(value(v));
                setattr(vm, intern("value"), held.get());
                held = Ref{};
                Object* holder = marker("weak").object();
                weak_link(holder, vm, Obj{}, WeakKind::BasicRef);
                reviver_weaks.push_back(holder);
                setattr(objects[i], intern(name), hold.get());
                return "('value', None)";
            }
            if (op == "release_kept") {
                std::vector<Instance*> going = std::move(kept);
                kept.clear();
                for (auto it = going.rbegin(); it != going.rend(); ++it) decref(*it);
                std::string out = "('value', [";
                bool first = true;
                for (Object* w : reviver_weaks) {
                    out += std::string(first ? "" : ", ") + (weak_record(w)->target == nullptr ? "True" : "False");
                    first = false;
                }
                return out + "])";
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
