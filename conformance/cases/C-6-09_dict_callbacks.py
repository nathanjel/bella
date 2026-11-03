# clause: C-6-09
# spec: section 6 (dict), section 9 (lifetimes)
# status: P1
# source: review log RL-228 on (astra-low 10: A10-5 to A10-10; gemini-4-argon-high 09: 2.5, 2.6)
"""What a dict operation calls back into, and how often: each operation looks a key up once
(setdefault, pop; an empty dict's pop hashes nothing), an insert that resizes the table finds the
new slot without comparing keys again, and a copy or merge of a dict reuses its stored hashes. A
clean dict is copied or merged into an empty one without comparing any key; a dict with many
deleted entries is compacted, which compares the keys that collide. A store whose key comparison
raises releases the value before the handler runs. An iterator that meets an entry it did not
expect (a key deleted and another added, the size unchanged) fails, and is exhausted."""


class Key:
    """Every instance hashes alike, so any two are compared; each comparison is counted."""

    calls = 0

    def __init__(self, name: str) -> None:
        self.name = name

    def __hash__(self) -> int:
        return 1

    def __eq__(self, other: object) -> bool:
        Key.calls += 1
        return isinstance(other, Key) and self.name == other.name

    def __repr__(self) -> str:
        return self.name


class Hashed:
    """Its hash calls are counted."""

    calls = 0

    def __hash__(self) -> int:
        Hashed.calls += 1
        return 7


class Value:
    def __del__(self) -> None:
        print("value dies")


class Raising:
    def __hash__(self) -> int:
        return 1

    def __eq__(self, other: object) -> bool:
        raise ValueError("eq")


def count(label: str) -> None:
    print(label, "comparisons:", Key.calls, "hashes:", Hashed.calls)
    Key.calls = 0
    Hashed.calls = 0


keys = [Key(f"k{i}") for i in range(6)]
d: dict[object, int] = {}
for i in range(5):
    d[keys[i]] = i
count("five colliding inserts")
d[keys[5]] = 5                       # the sixth resizes the table
count("the insert that resizes")
print("setdefault of a present key:", d.setdefault(keys[2], 9))
count("setdefault, present")
print("setdefault of a new key:", d.setdefault(Key("new"), 9))
count("setdefault, new")
print("pop:", d.pop(keys[0]))
count("pop")
h = Hashed()
empty: dict[object, str] = {}
print("pop from an empty dict:", empty.pop(h, "default"))
count("empty pop")
plain = {h: 1}
count("one hashed key")
print("pop:", plain.pop(h), len(plain))
count("pop, hashed once")

clean = {Key("a"): 1, Key("b"): 2}
count("a clean dict made")
print("copy:", list(clean.copy().values()))
count("copy of a clean dict")
print("merged into an empty dict:", list({**clean}.values()))
count("{**clean}")
target = {Key("z"): 0}
Key.calls = 0
target.update(clean)
count("update of a non-empty dict")
sparse = {Key(f"s{i}"): i for i in range(6)}
for k in list(sparse)[:4]:
    del sparse[k]
count("a sparse dict made")
print("copy of a sparse dict:", list(sparse.copy().values()))
count("copy of a sparse dict")
source = {Hashed(): 1}
count("a dict of one hashed key")
print("fromkeys:", list(dict.fromkeys(source, 0).values()), list(dict.fromkeys({Hashed()}, 0).values()))
count("fromkeys of a dict and a set")

failing: dict[object, object] = {Raising(): 1}
try:
    failing[Raising()] = Value()
except ValueError:
    print("handler runs")
print("after the store")

it = iter({"a": 1, "b": 2})
print("first:", next(it))
grown = {"x": 0}
it2 = iter(grown)
print("next:", next(it2))
del grown["x"]
grown["y"] = 1
for step in range(2):
    try:
        print("step", step, next(it2))
    except RuntimeError:
        print("step", step, "RuntimeError")
    except StopIteration:
        print("step", step, "StopIteration")
