// probe: expansion statements
// needs: C++26 `template for` (P1306) -- unrolled field iteration in the runtime
// flags: -freflection
#include <tuple>
int main() {
    int sum = 0;
    // A constexpr loop variable needs a constant range; a runtime tuple takes a plain one.
    static constexpr std::tuple fields{1, 2, 3};
    template for (constexpr auto v : fields) { sum += v; }
    template for (auto v : std::tuple{4, 5}) { sum += v; }
    return sum == 15 ? 0 : 1;
}
