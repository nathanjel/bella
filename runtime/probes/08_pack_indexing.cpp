// probe: pack indexing
// needs: C++26 pack indexing (P2662) -- argument-struct lowering
template <typename... Ts> auto first(Ts... ts) { return ts...[0]; }
int main() { return first(7, 8, 9) == 7 ? 0 : 1; }
