// probe: toolchain
// needs: reports compiler and standard library versions (always expected to pass)
#include <iostream>
#include <version>
int main() {
    std::cout << "__cplusplus=" << __cplusplus;
#ifdef __GNUC__
    std::cout << " gcc=" << __GNUC__ << '.' << __GNUC_MINOR__ << '.' << __GNUC_PATCHLEVEL__;
#endif
#ifdef _GLIBCXX_RELEASE
    std::cout << " libstdc++=" << _GLIBCXX_RELEASE;
#endif
    std::cout << '\n';
}
