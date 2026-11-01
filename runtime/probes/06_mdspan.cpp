// probe: std::mdspan
// needs: <mdspan> (C++23) -- numeric array intent
#include <mdspan>
int main() {
    int data[6] = {1, 2, 3, 4, 5, 6};
    std::mdspan<int, std::extents<std::size_t, 2, 3>> m(data);
    return m[1, 2] == 6 ? 0 : 1;
}
