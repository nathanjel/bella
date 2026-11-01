// probe: std::indirect
// needs: <memory> std::indirect / std::polymorphic (C++26, P3019) -- unique owners with value semantics
#include <memory>
struct Big { int v = 3; };
int main() {
    std::indirect<Big> a;
    std::indirect<Big> b = a;
    b->v = 4;
    return (a->v == 3 && b->v == 4) ? 0 : 1;
}
