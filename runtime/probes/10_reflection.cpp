// probe: reflection
// needs: C++26 reflection (P2996) -- the runtime's generated __repr__/__eq__/kwargs binding
// flags: -freflection
#include <meta>
#include <string_view>
struct Point { int x; int y; };
int main() {
    constexpr auto members = std::meta::nonstatic_data_members_of(^^Point, std::meta::access_context::unchecked());
    static_assert(members.size() == 2);
    constexpr std::string_view name = std::meta::identifier_of(members[0]);
    return name == "x" ? 0 : 1;
}
