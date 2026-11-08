# clause: C-7-43
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_randommodule.c, Lib/random.py
"""The _random module behind random: the Mersenne Twister's outputs for integer seeds of every width, a negative, a bool, a float and a
tuple (the hash as the key), random() and getrandbits for widths below, at and above a word, getstate and setstate round trips with
their conversions and messages, the constructor's and seed's parsing, and the random module over it: seeding from str and bytes
(the sha512 path), randrange, randint, choice, shuffle, sample, uniform, gauss, choices, randbytes and getstate."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _random
import random


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


print("module:", repr(_random.__doc__), [n for n in dir(_random) if not n.startswith("__")], _random.Random.__name__, _random.Random.__module__, repr(_random.Random.__doc__))
print("docs:", repr(_random.Random.random.__doc__), repr(_random.Random.seed.__doc__), repr(_random.Random.getstate.__doc__), repr(_random.Random.setstate.__doc__), repr(_random.Random.getrandbits.__doc__))
print("descriptors:", type(_random.Random.random).__name__, type(_random.Random.__init__).__name__, type(_random.Random.__new__).__name__, m(lambda: _random.Random().__dict__), issubclass(random.Random, _random.Random), type(random.Random(1).__dict__).__name__)  # type: ignore[no-untyped-call]
for seed in [0, 1, 42, 12345, 2**31, 2**32 - 1, 2**32, 2**64 + 5, -7, 2**100, 1.5, (1, 2), True, 7.0, -0.0, 2**53 + 1.0, 10**20 // 7]:
    r = _random.Random(seed)
    print("seed", repr(seed), [r.random() for _ in range(3)], [r.getrandbits(k) for k in (1, 7, 31, 32, 33, 63, 64, 65, 100, 200)], r.getstate()[-1], r.getstate()[:2], r.getstate()[-3:-1])
print("same:", _random.Random(-5).random() == _random.Random(5).random(), _random.Random(True).random() == _random.Random(1).random(), _random.Random(0).random() == _random.Random(False).random(), _random.Random(2**64).random() == _random.Random(2**64 + 2**128).random())


class B(int):
    def __abs__(self):  # type: ignore[no-untyped-def]
        return 7


class H:
    def __hash__(self):  # type: ignore[no-untyped-def]
        return 123456789


print("abs and hash:", _random.Random(B(5)).random() == _random.Random(5).random(), _random.Random(B(-5)).random() == _random.Random(5).random(), _random.Random(H()).random() == _random.Random(123456789).random(), m(lambda: _random.Random([])), m(lambda: _random.Random({})))  # type: ignore[no-untyped-call]
r = _random.Random(99)
first = [r.random() for _ in range(5)]
state = r.getstate()
later = [r.random() for _ in range(5)]
r.setstate(state)
print("state:", later == [r.random() for _ in range(5)], len(state), type(state).__name__, all(0 <= w < 2**32 for w in state[:-1]), state[-1])
r2 = _random.Random(99)
print("twist:", [r2.getrandbits(32) for _ in range(5)], [r2.random() for _ in range(1000)][-3:], r2.getstate()[-1], r2.getrandbits(64), r2.getstate()[-1])
r.seed(2**70 + 3)
print("reseed:", r.random(), r.getrandbits(70), r.seed(), type(r.random()).__name__, r.seed(None))  # type: ignore[func-returns-value]
print("errors:", m(lambda: r.getrandbits(-1)), m(lambda: r.getrandbits(1.5)), m(lambda: r.getrandbits("x")), m(lambda: r.getrandbits(2**64)), m(lambda: r.getrandbits(2**63)), m(lambda: r.getrandbits()), m(lambda: r.getrandbits(1, 2)), m(lambda: r.getrandbits(k=3)), m(lambda: r.getrandbits(0)), m(lambda: r.random(1)), m(lambda: r.random(x=1)), m(lambda: r.getstate(1)), m(lambda: r.setstate()), m(lambda: r.setstate(1, 2)), m(lambda: r.setstate(state=state)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print("setstate:", m(lambda: r.setstate(5)), m(lambda: r.setstate((1,) * 624)), m(lambda: r.setstate((1,) * 624 + (625,))), m(lambda: r.setstate((1,) * 624 + (-1,))), m(lambda: r.setstate((-1,) * 624 + (0,))), m(lambda: r.setstate(("x",) * 624 + (0,))), m(lambda: r.setstate((1.5,) * 624 + (0,))), m(lambda: r.setstate((2**64,) * 624 + (0,))), m(lambda: r.setstate((2**33 + 7,) * 624 + (624,))), m(lambda: r.getstate()[:3]), m(lambda: r.getstate()[-1]), m(lambda: r.random()), m(lambda: r.getstate()[-1]), m(lambda: r.setstate((1,) * 624 + (2**40,))), m(lambda: r.setstate((1,) * 624 + (2**70,))), m(lambda: r.setstate((1,) * 624 + ("x",))), m(lambda: r.setstate([1] * 625)), m(lambda: r.setstate((True,) * 624 + (False,))), m(lambda: r.random()))  # type: ignore[arg-type,no-untyped-call]
print("construction:", m(lambda: _random.Random(1, 2)), m(lambda: _random.Random(x=1)), m(lambda: _random.Random().seed(1, 2)), m(lambda: _random.Random().seed(n=1)), m(lambda: _random.Random.__new__(_random.Random).random()), m(lambda: _random.Random.__new__(_random.Random).getstate()[-1]), m(lambda: _random.Random(None).random() != _random.Random(None).random()), m(lambda: _random.Random().getstate()[-1]), m(lambda: _random.Random.__init__(_random.Random(1), 5)), m(lambda: _random.Random.random(5)))  # type: ignore[arg-type,call-arg,no-untyped-call]


class Sub(_random.Random):
    def __init__(self, x=None):  # type: ignore[no-untyped-def]
        self.log = []
        super().__init__(x)

    def random(self):  # type: ignore[no-untyped-def]
        v = super().random()
        self.log.append(v)
        return v


s = Sub(3)  # type: ignore[no-untyped-call]
print("subclass:", s.random() == _random.Random(3).random(), s.log, s.getrandbits(5), s.__dict__.keys(), type(s).__mro__[1].__name__)  # type: ignore[no-untyped-call]
R = random.Random(7)
print("random module:", R.random(), R.randint(1, 100), R.choice("abcdef"), R.getrandbits(40), [R.randrange(10) for _ in range(5)], R.randrange(5, 50, 7), R.randrange(2**70), R.randint(-10**20, 10**20))
for seed in ("hello", b"hello", bytearray(b"hi"), 3.5, "", "é☃"):
    R.seed(seed)
    print("  seeded", repr(seed), R.random(), R.getrandbits(64))
x = list(range(1, 11))
R.seed(1)
R.shuffle(x)
print("  shuffle", x, R.sample(range(100), 5), R.sample("abcdefg", 3), R.sample([1, 2, 3], 3, counts=[2, 1, 3]))
print("  floats", R.uniform(1, 2), R.gauss(0, 1), R.normalvariate(5, 2), R.triangular(), R.betavariate(2, 3), R.expovariate(1.5), R.gammavariate(2, 3), R.lognormvariate(0, 1), R.vonmisesvariate(0, 1), R.paretovariate(2), R.weibullvariate(1, 2), R.binomialvariate(10, 0.3))
print("  choices", R.choices("abc", k=5), R.choices(range(5), weights=[5, 1, 1, 1, 1], k=6), R.choices([1, 2, 3], cum_weights=[1, 5, 10], k=4), R.randbytes(4), R.randbytes(0))
print("  state", type(R.getstate()).__name__, len(R.getstate()[1]), R.getstate()[0], R.getstate()[2], random.Random(5).getstate() == random.Random(5).getstate(), random.Random(5).getstate() == random.Random(6).getstate())
st = R.getstate()
a = [R.random(), R.randint(0, 9)]
R.setstate(st)
print("  restored", a == [R.random(), R.randint(0, 9)], m(lambda: R.setstate((4, (1,) * 625, None))), m(lambda: R.setstate((3, (1,) * 10, None))), m(lambda: R.setstate((3, (1,) * 625, None))), m(lambda: random.randrange(0)), m(lambda: random.randrange(1, 1)), m(lambda: random.randint(2, 1)), m(lambda: random.choice([])), m(lambda: random.sample([1, 2], 3)), m(lambda: random.seed([1, 2])), m(lambda: random.getrandbits(-1)), m(lambda: random.randrange(1.5)), m(lambda: random.randrange(1, 10, 0)))  # type: ignore[arg-type,no-untyped-call]
random.seed(2024)
print("  global", random.random(), random.randint(1, 6), random.choice(["x", "y", "z"]), random.getrandbits(16), random.randbytes(3), [random.randrange(100) for _ in range(5)], random.uniform(-1, 1), random.gauss())
