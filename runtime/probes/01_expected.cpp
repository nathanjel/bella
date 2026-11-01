// probe: std::expected
// needs: <expected> (C++23) with monadic and_then/or_else -- the local exception lowering
#include <expected>
#include <string>
int main() {
    std::expected<int, std::string> e = 41;
    auto r = e.and_then([](int v) -> std::expected<int, std::string> { return v + 1; });
    return r.value() == 42 ? 0 : 1;
}
