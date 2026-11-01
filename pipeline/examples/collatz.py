# slice example: while loops with augmented assignment and nested conditionals


def steps(n: int) -> int:
    count = 0
    while n != 1:
        if n % 2 == 0:
            n //= 2
        else:
            n = 3 * n + 1
        count += 1
    return count


longest = 0
arg = 0
for start in range(1, 300):
    s = steps(start)
    if s > longest:
        longest = s
        arg = start
print("longest collatz chain below 300:", arg, longest)
print("evaluation order:", steps(27) - steps(9), steps(97) + steps(871))
