// probe: std::inplace_vector
// needs: <inplace_vector> (C++26) -- small tuples and bounded *args
#include <inplace_vector>
int main() {
    std::inplace_vector<int, 4> v;
    v.push_back(1); v.push_back(2);
    return v.size() == 2 ? 0 : 1;
}
