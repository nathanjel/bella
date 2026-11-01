# xfail: BigInt promotion not implemented in runtime/include/bella/int.hpp (factorial(25) exceeds 2**62)
# slice example: exact int beyond the 63-bit immediate range


def factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


print(factorial(20))
print(factorial(25))
print(factorial(30) // factorial(28))
