// probe: std::execution
// needs: <execution> senders/receivers (C++26, P2300) -- the async scheduler; libuv stand-in until it ships
#include <execution>
int main() {
    namespace ex = std::execution;
    auto s = ex::just(21) | ex::then([](int v) { return v * 2; });
    auto [r] = std::this_thread::sync_wait(std::move(s)).value();
    return r == 42 ? 0 : 1;
}
