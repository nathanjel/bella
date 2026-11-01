// probe: std::hazard_pointer
// needs: <hazard_pointer> (C++26, P2530) -- lock-free runtime tables; xenium is the stand-in until it ships
#include <hazard_pointer>
struct Node : std::hazard_pointer_obj_base<Node> { int v = 1; };
int main() {
    auto hp = std::make_hazard_pointer();
    Node* n = new Node;
    std::atomic<Node*> head{n};
    Node* p = hp.protect(head);
    int v = p->v;
    hp.reset_protection();
    n->retire();
    return v == 1 ? 0 : 1;
}
