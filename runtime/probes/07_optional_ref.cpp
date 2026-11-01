// probe: std::optional<T&>
// needs: optional of reference (C++26, P2988)
#include <optional>
int main() {
    int x = 5;
    std::optional<int&> o(x);
    *o = 6;
    return x == 6 ? 0 : 1;
}
