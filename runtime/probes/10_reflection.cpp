// probe: reflection
// needs: C++26 reflection (P2996) -- the runtime's generated __repr__/__eq__/kwargs binding
// flags: -freflection
#include <meta>
#include <string_view>
struct Point { int x; int y; };
// The std::vector that nonstatic_data_members_of returns must stay transient: it may not
// outlive the constant expression that creates it (no constexpr variable of that type).
consteval auto ctx() { return std::meta::access_context::unchecked(); }
static_assert(std::meta::nonstatic_data_members_of(^^Point, ctx()).size() == 2);
constexpr std::string_view name = std::meta::identifier_of(std::meta::nonstatic_data_members_of(^^Point, ctx())[0]);
int main() { return name == "x" ? 0 : 1; }
