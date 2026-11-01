# clause: C-7-08
# spec: section 7
# status: P1
# source: dialect specification section 7, Numbers (math, cmath, decimal, fractions, random, statistics, numbers)
"""Number modules. random is bit-exact Mersenne Twister with CPython's distribution algorithms
(spec section 7), so a seeded sequence must match."""
import cmath
import decimal
import fractions
import math
import numbers
import random
import statistics

print(math.isqrt(10**20 + 1), math.comb(50, 25), math.perm(10, 3), math.gcd(84, 36, 120), math.lcm(4, 6, 10))
print(math.fsum([0.1] * 10), sum([0.1] * 10), math.prod(range(1, 11)), math.floor(-2.5), math.ceil(-2.5), math.trunc(-2.7))
print(math.log(8, 2), math.log10(1000), math.sqrt(2), math.hypot(3, 4), math.isclose(1.0, 1.0 + 1e-10), math.copysign(1, -0.0))
print(math.factorial(20), math.inf > 10**400, math.isnan(math.nan), math.nextafter(1.0, 2.0), math.ulp(1.0), math.dist((0, 0), (3, 4)))
print(cmath.sqrt(-1), cmath.polar(1j), cmath.exp(1j * math.pi).real, abs(3 + 4j))

ctx = decimal.Context(prec=6, rounding=decimal.ROUND_HALF_EVEN)
D = decimal.Decimal
print(ctx.divide(D(1), D(7)), D("2.675").quantize(D("0.01")), D("2.665").quantize(D("0.01"), rounding=decimal.ROUND_HALF_UP))
print(D("1.1") + D("2.2"), D(0.1), ctx.sqrt(D(2)), D("1e3").normalize(), D("-0").is_signed(), D("123.4500").as_tuple())
with decimal.localcontext() as local:
    local.prec = 3
    print(D(1) / D(3), local.prec)
try:
    decimal.Context(traps=[decimal.DivisionByZero]).divide(D(1), D(0))
except decimal.DivisionByZero as exc:
    print("trapped:", type(exc).__name__)

F = fractions.Fraction
print(F(1, 3) + F(1, 6), F("3.1415926535").limit_denominator(100), F(0.75), F(7, 3) // 1, F(-7, 3) % 1, F(2, 4) == 0.5)
print(round(F(5, 2)), round(F(7, 2)), F(1, 3) ** 2, float(F(1, 3)), F.from_float(0.1).limit_denominator(1000))

rng = random.Random(12345)
print(rng.random(), rng.randint(1, 100), rng.choice("abcdef"), rng.uniform(1, 2), rng.getrandbits(70))
items = list(range(10))
rng.shuffle(items)
print(items, rng.sample(range(100), 5), rng.gauss(0, 1), rng.expovariate(2.0), rng.randrange(0, 100, 7), rng.choices("ab", k=4))
random.seed(7)
print(random.random(), random.randbytes(4))

sample = [2.5, 3.25, 5.5, 11.25, 11.75]
print(statistics.mean(sample), statistics.median([1, 3, 2, 4]), statistics.stdev(sample), statistics.pvariance(sample))
print(statistics.quantiles(range(1, 11), n=4), statistics.mode("aabbbc"), statistics.fmean([1, 2, 4]), statistics.harmonic_mean([1, 2, 4]))
print(statistics.median_low([1, 2, 3, 4]), statistics.median_high([1, 2, 3, 4]), statistics.geometric_mean([1, 4]))
print([isinstance(x, t) for x, t in ((1, numbers.Integral), (1.5, numbers.Real), (1j, numbers.Complex), (F(1, 2), numbers.Rational), (D(1), numbers.Number))])
