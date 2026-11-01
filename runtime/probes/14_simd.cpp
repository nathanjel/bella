// probe: std::simd
// needs: <simd> (C++26, P1928 as revised by P3287/P3441: namespace std::simd, std::simd::vec) -- vectorised numeric loops
#include <simd>
int main() {
    std::simd::vec<int> a(1), b(2);
    auto c = a + b;
    return c[0] == 3 ? 0 : 1;
}
