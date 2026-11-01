// probe: std::simd
// needs: <simd> (C++26, P1928) -- vectorised numeric loops
#include <simd>
int main() {
    std::simd<int> a(1), b(2);
    auto c = a + b;
    return c[0] == 3 ? 0 : 1;
}
