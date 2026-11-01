# slice example: recursion, comparison, arithmetic, for over range


def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


for i in range(0, 25):
    print(i, fib(i))
print("fib(60) fits the 63-bit immediate:", fib(30) * 1000, 60 > 30)
