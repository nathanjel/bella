// probe: std::print
// needs: <print> (C++23) -- print()/f-string lowering
#include <print>
int main() { std::println("{} {}", 1, "two"); return 0; }
