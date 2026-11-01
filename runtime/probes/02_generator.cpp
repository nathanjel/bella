// probe: std::generator
// needs: <generator> (C++23) -- Python generators lower to it
#include <generator>
int main() {
    auto gen = []() -> std::generator<int> { co_yield 1; co_yield 2; co_yield 3; };
    int sum = 0;
    for (int v : gen()) sum += v;
    return sum == 6 ? 0 : 1;
}
