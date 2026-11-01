// probe: std::rcu
// needs: <rcu> (C++26, P2545) -- reclamation of runtime-created classes
#include <rcu>
struct Node : std::rcu_obj_base<Node> { int v = 1; };
int main() {
    Node* n = new Node;
    { std::scoped_lock l(std::rcu_default_domain()); (void)n->v; }
    n->retire();
    std::rcu_synchronize();
    return 0;
}
