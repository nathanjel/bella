// probe: = delete("reason")
// needs: C++26 deleted function with a message (P2573)
struct S { S(int) = delete("use S(double)"); S(double) {} };
int main() { S s(1.0); (void)s; return 0; }
