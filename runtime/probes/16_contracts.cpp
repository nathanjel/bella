// probe: contracts
// needs: C++26 contracts (P2900) -- dialect preconditions and type guards
// flags: -fcontracts
int half(int x) pre(x % 2 == 0) post(r: r * 2 == x) { return x / 2; }
int main() { return half(8) == 4 ? 0 : 1; }
