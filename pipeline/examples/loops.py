# slice example: floor division and modulo signs, while/for with else, break/continue, and/or


def gcd(a: int, b: int) -> int:
    while b != 0:
        r = a % b
        a = b
        b = r
    return a


def signs(a: int, b: int) -> int:
    print(a, b, a // b, a % b, -a // b, -a % b, a // -b, a % -b)
    return a // b + a % b


total = 0
for n in range(1, 50):
    if n % 7 == 0:
        continue
    if n > 40:
        break
    total += n
else:
    print("never printed: the loop broke")
print("total", total, "gcd", gcd(1071, 462), gcd(-48, 18))

k = 0
while k < 10:
    k += 3
else:
    print("while-else runs when the loop ends normally", k)

print(signs(7, 2), signs(-7, 2), signs(7, -2))
print("and/or return operands:", 0 or 5, 3 and 0, 2 and 4, 0 or 0)
print("bool ops:", 1 < 2 and 3 > 2, not (1 < 2), 5 if 2 > 1 else 6)
print("shifts and bits:", 1 << 40, -1 >> 3, 6 & 3, 6 | 3, 6 ^ 3, ~5, 2 ** 20)
