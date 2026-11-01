// probe: std::flat_map
// needs: <flat_map> (C++23) -- small static dicts
#include <flat_map>
#include <string>
int main() {
    std::flat_map<std::string, int> m;
    m["a"] = 1; m["b"] = 2;
    return m.size() == 2 ? 0 : 1;
}
