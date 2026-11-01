// probe: std::stacktrace
// needs: <stacktrace> (C++23) -- tracebacks in debug builds (needs -lstdc++exp on GCC)
// flags: -lstdc++exp
#include <stacktrace>
int main() { auto st = std::stacktrace::current(); return st.size() > 0 ? 0 : 1; }
