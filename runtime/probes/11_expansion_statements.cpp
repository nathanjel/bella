// probe: expansion statements
// needs: C++26 `template for` (P1306) -- unrolled field iteration in the runtime
// flags: -freflection
#include <meta>
#include <tuple>
int main() {
    int sum = 0;
    template for (constexpr auto v : std::tuple{1, 2, 3}) { sum += v; }
    return sum == 6 ? 0 : 1;
}
