// probe: #embed
// needs: C++26 #embed (P1967) -- frozen module snapshots as constant data
static const unsigned char self[] = {
#embed __FILE__ limit(16)
};
int main() { return sizeof(self) == 16 ? 0 : 1; }
