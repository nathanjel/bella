# clause: C-7-39
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/md5module.c, sha1module.c, sha2module.c, sha3module.c, blake2module.c, hmacmodule.c
"""The built-in digests behind hashlib and hmac in a CPython without OpenSSL (deviation D-20): _md5, _sha1, _sha2, _sha3, _blake2 and
_hmac, each type's shape, constructor parameters and messages, the digests across block boundaries (updated in pieces and copied),
SHAKE's lengths, every BLAKE2 parameter with its check, HMAC over each digest, and hashlib and hmac over them where OpenSSL's absence
makes no difference."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _blake2
import _hmac  # type: ignore[import-not-found]
import _md5  # type: ignore[import-not-found]
import _sha1  # type: ignore[import-not-found]
import _sha2  # type: ignore[import-not-found]
import _sha3  # type: ignore[import-not-found]
import hashlib
import hmac


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def gen(n: int) -> bytes:                      # a deterministic byte pattern of length n
    x = 12345 + n
    out = bytearray()
    for _ in range(n):
        x = (x * 1103515245 + 12345) & 0x7fffffff
        out.append((x >> 16) & 0xff)
    return bytes(out)
ctors = [_md5.md5, _sha1.sha1, _sha2.sha224, _sha2.sha256, _sha2.sha384, _sha2.sha512, _sha3.sha3_224, _sha3.sha3_256, _sha3.sha3_384, _sha3.sha3_512, _blake2.blake2b, _blake2.blake2s]
lengths = [0, 1, 3, 55, 56, 57, 63, 64, 65, 71, 72, 73, 103, 104, 105, 111, 112, 113, 119, 120, 127, 128, 129, 135, 136, 137, 143, 144, 145, 167, 168, 169, 200, 255, 256, 257, 1000, 4097]
for c in ctors:
    sums = []
    for n in lengths:
        data = gen(n)
        h = c(data)
        h2 = c()
        for i in range(0, n, 37):
            h2.update(data[i:i + 37])
        h3 = c(data[:n // 2])
        h4 = h3.copy()
        h4.update(data[n // 2:])
        h3.update(data[n // 2:])
        sums.append(h.hexdigest()[:12] + ("" if h2.hexdigest() == h.hexdigest() == h4.hexdigest() == h3.hexdigest() else "!"))
    print(c.__name__ if hasattr(c, "__name__") else c, h.name, h.digest_size, h.block_size, " ".join(sums))
for c in (_sha3.shake_128, _sha3.shake_256):
    print(c.__name__, [c(gen(n)).hexdigest(k)[:16] for n in (0, 1, 135, 136, 137, 167, 168, 169) for k in (0, 1, 32, 136, 168, 200)][:24], len(c(b"a").digest(1000)), c(b"a").digest(400).hex()[-16:], c(b"a").digest(5) == c(b"a").digest(400)[:5])
for kw in ({}, {"digest_size": 1}, {"digest_size": 20}, {"key": b"key"}, {"key": gen(64)}, {"salt": b"s" * 16}, {"person": b"p" * 16}, {"fanout": 0, "depth": 2}, {"leaf_size": 4096}, {"node_offset": 2**40 + 7}, {"node_depth": 3}, {"inner_size": 32}, {"last_node": True}, {"key": b"k", "salt": b"s", "person": b"p", "fanout": 2, "depth": 3, "leaf_size": 5, "node_offset": 6, "node_depth": 7, "inner_size": 8, "last_node": True, "digest_size": 33}):
    kws = dict(kw)
    if "digest_size" in kws and kws["digest_size"] > 32:  # type: ignore[operator]
        kws["digest_size"] = 32
    if "key" in kws and len(kws["key"]) > 32:  # type: ignore[arg-type]
        kws["key"] = kws["key"][:32]  # type: ignore[index]
    if "salt" in kws:
        kws["salt"] = kws["salt"][:8]  # type: ignore[index]
    if "person" in kws:
        kws["person"] = kws["person"][:8]  # type: ignore[index]
    if "inner_size" in kws and kws["inner_size"] > 32:  # type: ignore[operator]
        kws["inner_size"] = 32
    print(sorted(kw), _blake2.blake2b(gen(300), **kw).hexdigest()[:16], _blake2.blake2s(gen(300), **kws).hexdigest()[:16], _blake2.blake2b(gen(128), **kw).hexdigest()[:16], _blake2.blake2b(b"", **kw).hexdigest()[:16])  # type: ignore[arg-type]
for name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_224", "sha3_256", "sha3_384", "sha3_512", "blake2b", "blake2s"):
    print(name, [_hmac.compute_digest(gen(k), gen(n), name).hex()[:12] for k in (0, 1, 20, 63, 64, 65, 127, 128, 129, 200) for n in (0, 5, 200)][::4])
for name in ("md5", "sha1", "sha256", "sha512", "sha3_256"):
    h = _hmac.new(gen(70), gen(10), name)
    h2 = h.copy()
    h.update(gen(300))
    h2.update(gen(300)[:100])
    h2.update(gen(300)[100:])
    print(name, h.name, h.digest_size, h.block_size, h.hexdigest()[:16], h.hexdigest() == h2.hexdigest() == _hmac.compute_digest(gen(70), gen(10) + gen(300), name).hex(), _hmac.new(b"k", digestmod=name.upper()).hexdigest()[:8])
print(_hmac.compute_md5(b"k", b"m").hex(), _hmac.compute_sha1(b"k", b"m").hex(), _hmac.compute_sha3_512(b"k", b"m").hex()[:16], _hmac.compute_blake2b_32(b"k", b"m").hex()[:16], _hmac.compute_blake2s_32(b"k", b"m").hex()[:16], _hmac.compute_sha384(gen(129), gen(129)).hex()[:16])

print(_md5.MD5Type, _sha1.SHA1Type, _sha2.SHA224Type, _sha2.SHA256Type, _sha2.SHA384Type, _sha2.SHA512Type, _md5._GIL_MINSIZE, _sha3.implementation, _sha3._GIL_MINSIZE, _blake2._GIL_MINSIZE, _hmac._GIL_MINSIZE, _hmac.HMAC, _hmac.UnknownHashError.__mro__[1:3], _hmac.UnknownHashError.__module__)  # type: ignore[attr-defined]
for mod, ctor in ((_md5, _md5.md5), (_sha1, _sha1.sha1), (_sha2, _sha2.sha224), (_sha2, _sha2.sha512), (_sha3, _sha3.sha3_256), (_sha3, _sha3.shake_128), (_blake2, _blake2.blake2b), (_blake2, _blake2.blake2s)):
    h = ctor(b"abc")
    t = type(h)
    print(mod.__name__, type(ctor).__name__, ctor.__name__, ctor.__qualname__, ctor.__module__, t, t.__name__, t.__qualname__, t.__module__, t.__mro__[1:], h.name, h.digest_size, h.block_size, repr(h).split(" at ")[0], h.hexdigest(4) if h.digest_size == 0 else h.hexdigest()[:16], [n for n in dir(h) if not n.startswith("__")], type(t.__dict__["name"]).__name__, type(t.__dict__["update"]).__name__, t.__doc__)  # type: ignore[call-arg]
for h in (_md5.md5(), _sha1.sha1(), _sha2.sha224(), _sha2.sha512(), _sha3.sha3_256(), _sha3.shake_128(), _blake2.blake2b(), _hmac.new(b"k", digestmod="sha1")):
    xof = type(h).__name__.startswith("shake")
    print(type(h).__name__, m(lambda: h.update()), m(lambda: h.update(b"a", b"b")), m(lambda: h.update(1)), m(lambda: h.update("x")), m(lambda: h.digest(1, 2)) if xof else m(lambda: h.digest(1)), m(lambda: h.hexdigest()) if xof else m(lambda: h.hexdigest(1)), m(lambda: h.copy(1)), m(lambda: h.update(x=1)), m(lambda: h.digest(x=1)), m(lambda: setattr(h, "digest_size", 1)), m(lambda: setattr(h, "name", 1)), m(lambda: delattr(h, "name")), m(lambda: setattr(h, "zzz", 1)), m(lambda: h.update(bytearray(b"x"))), m(lambda: type(h)(b"a") == type(h)(b"a")) if not isinstance(h, _hmac.HMAC) else None)  # type: ignore[arg-type,call-arg,no-untyped-call]
for name, ctor in (("md5", _md5.md5), ("sha1", _sha1.sha1), ("sha256", _sha2.sha256), ("sha512", _sha2.sha512)):
    print(name, m(lambda: ctor("a")), m(lambda: ctor(b"a", string=b"b")), m(lambda: ctor(b"a", b"b")), m(lambda: ctor(data=b"a", usedforsecurity=False).hexdigest()[:8]), m(lambda: ctor(1)), m(lambda: ctor(bytearray(b"a")).hexdigest()[:8]), m(lambda: ctor(x=1)), m(lambda: ctor(b"a", data=b"b")), m(lambda: ctor(usedforsecurity=False).hexdigest()[:8]), m(lambda: ctor(b"a", b"b", b"c", b"d")))  # type: ignore[no-untyped-call]
print(m(lambda: _md5.MD5Type()), m(lambda: _md5.MD5Type(b"a")), m(lambda: _sha2.SHA256Type()), m(lambda: _sha1.SHA1Type.__new__(_sha1.SHA1Type)), m(lambda: _hmac.HMAC()), m(lambda: _sha3.sha3_256.__new__(_sha3.sha3_256).hexdigest()[:8]), m(lambda: _blake2.blake2b.__new__(_blake2.blake2b).hexdigest()[:8]), m(lambda: _md5.md5.__self__), m(lambda: _md5.md5.__module__))  # type: ignore[no-untyped-call]
for ctor in (_sha3.sha3_224, _sha3.sha3_512, _sha3.shake_256):
    print(ctor.__name__, m(lambda: ctor("a")), m(lambda: ctor(b"a", string=b"b")), m(lambda: ctor(b"a", b"b")), m(lambda: ctor(data=b"a").hexdigest()[:8] if ctor.__name__ != "shake_256" else ctor(data=b"a").hexdigest(4)), m(lambda: ctor(b"a", usedforsecurity=False, x=1)), m(lambda: ctor(1)), m(lambda: ctor(b"", usedforsecurity=True).name), ctor(b"a")._capacity_bits, ctor(b"a")._rate_bits, ctor(b"a")._suffix)  # type: ignore[no-untyped-call]
s = _sha3.shake_128(b"a")
print(m(lambda: s.digest()), m(lambda: s.digest(-1)), m(lambda: s.digest(0)), m(lambda: s.digest(1.5)), m(lambda: s.digest(2**63)), m(lambda: s.digest(2**31)), m(lambda: s.digest(2**29)) if False else m(lambda: len(s.digest(2**29 - 1)) == 2**29 - 1), m(lambda: s.hexdigest(length=3)), m(lambda: s.digest(length=3)), m(lambda: s.digest(lengthh=3)), m(lambda: s.digest(3, length=3)), m(lambda: s.hexdigest(True)), m(lambda: s.digest(1, 2, 3)), m(lambda: s.hexdigest(-5)), s.digest_size, s.block_size, s.name)  # type: ignore[no-untyped-call]
print(_blake2.blake2b.SALT_SIZE, _blake2.blake2b.PERSON_SIZE, _blake2.blake2b.MAX_KEY_SIZE, _blake2.blake2b.MAX_DIGEST_SIZE, _blake2.blake2s.SALT_SIZE, _blake2.blake2s.PERSON_SIZE, _blake2.blake2s.MAX_KEY_SIZE, _blake2.blake2s.MAX_DIGEST_SIZE, _blake2.BLAKE2B_SALT_SIZE, _blake2.BLAKE2B_PERSON_SIZE, _blake2.BLAKE2B_MAX_KEY_SIZE, _blake2.BLAKE2B_MAX_DIGEST_SIZE, _blake2.BLAKE2S_SALT_SIZE, _blake2.BLAKE2S_PERSON_SIZE, _blake2.BLAKE2S_MAX_KEY_SIZE, _blake2.BLAKE2S_MAX_DIGEST_SIZE)
for kw in ({"digest_size": 0}, {"digest_size": 65}, {"digest_size": 33}, {"key": b"k" * 65}, {"key": b"k" * 33}, {"salt": b"s" * 17}, {"salt": b"s" * 9}, {"person": b"p" * 17}, {"fanout": 256}, {"fanout": -1}, {"depth": 0}, {"depth": 256}, {"leaf_size": 2**32}, {"leaf_size": -1}, {"leaf_size": 2**64}, {"node_offset": 2**64}, {"node_offset": -1}, {"node_offset": 2**48}, {"node_depth": 256}, {"node_depth": -1}, {"inner_size": 65}, {"inner_size": 33}, {"inner_size": -1}, {"digest_size": "a"}, {"digest_size": 2**40}, {"key": "k"}, {"key": 1}, {"last_node": 5}, {"data": "x"}, {"data": 1}, {"string": b"x", "data": b"y"}, {"digest_sizee": 3}, {"fanout": 1.5}, {"digest_size": 0, "key": b"k" * 99}, {"key": b"k" * 99, "salt": b"s" * 99}, {"salt": b"s" * 99, "fanout": 999}, {"fanout": 999, "depth": 0}, {"depth": 0, "node_depth": 999}, {"node_depth": 999, "inner_size": 999}, {"inner_size": 999, "leaf_size": 2**40}, {"leaf_size": 2**40, "node_offset": 2**50}):  # type: ignore[assignment]
    print(sorted(kw.items()), m(lambda: _blake2.blake2b(**kw).hexdigest()[:8]), m(lambda: _blake2.blake2s(**kw).hexdigest()[:8]))  # type: ignore[no-untyped-call]
print(m(lambda: _blake2.blake2b(b"a", b"b")), m(lambda: _blake2.blake2b(usedforsecurity=False).hexdigest()[:8]), m(lambda: _blake2.blake2s(b"a", digest_size=1).hexdigest()), m(lambda: _blake2.blake2b(b"a").digest(1)), m(lambda: _blake2.blake2b(b"a", fanout=True).hexdigest()[:8]), m(lambda: _blake2.blake2b(b"a", digest_size=True).hexdigest()), m(lambda: _blake2.blake2b(b"a", data=b"b")), m(lambda: _blake2.blake2b(b"", key=bytearray(b"k")).hexdigest()[:8]), m(lambda: _blake2.blake2b(bytearray(b"x")).hexdigest()[:8]))  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
h = _hmac.new(b"k", b"m", digestmod="sha1")
print(type(h), type(h).__mro__[1:], h.name, h.digest_size, h.block_size, h.hexdigest(), repr(h)[:19], [n for n in dir(h) if not n.startswith("__")], m(lambda: _hmac.new(b"k", b"m")), m(lambda: _hmac.new(b"k", b"m", "xyz")), m(lambda: _hmac.new(b"k", b"m", "shake_128")), m(lambda: _hmac.new("k", b"m", "sha1")), m(lambda: _hmac.new(b"k", "m", "sha1")), m(lambda: _hmac.new(b"k", None, "sha1").hexdigest()), m(lambda: _hmac.new(b"k", digestmod="md5").name), m(lambda: _hmac.new(b"k", b"m", "blake2b").name), m(lambda: _hmac.new(b"k", b"m", "sha3_256").name), m(lambda: _hmac.new(b"k" * 300, b"m", "sha256").hexdigest()), m(lambda: _hmac.new(b"k", b"m", _sha1.sha1)), m(lambda: _hmac.new(b"k", b"m", "SHA1").name), m(lambda: _hmac.new(b"k", digestmod=None)), m(lambda: _hmac.new()), m(lambda: _hmac.new(b"k", b"m", "sha1", 1)), m(lambda: _hmac.new(key=b"k", msg=b"m", digestmod="sha1").hexdigest()), m(lambda: _hmac.new(b"k", b"m", digestmodd="sha1")), m(lambda: _hmac.new(b"k", key=b"j", digestmod="sha1")), m(lambda: _hmac.new(1, b"m", "sha1")), m(lambda: _hmac.new(b"k", 1, "sha1")), m(lambda: _hmac.new(b"k", b"m", 1)), m(lambda: _hmac.new(b"k", b"m", "sha512_224")), m(lambda: _hmac.new(b"k", b"m", "blake2s")))  # type: ignore[no-untyped-call]
print(m(lambda: _hmac.compute_digest(b"k", b"m", "sha1").hex()), m(lambda: _hmac.compute_digest(b"k", b"m", "xyz")), m(lambda: _hmac.compute_sha1(b"k", b"m").hex()), m(lambda: _hmac.compute_digest(b"k", b"m", _sha1.sha1)), m(lambda: _hmac.compute_digest("k", b"m", "sha1")), m(lambda: _hmac.compute_digest(b"k", b"m")), m(lambda: _hmac.compute_sha1(b"k")), m(lambda: _hmac.compute_sha1(b"k", b"m", 1)), m(lambda: _hmac.compute_sha1(key=b"k", msg=b"m")), m(lambda: _hmac.compute_digest(b"k", b"m", "shake_128")), m(lambda: _hmac.compute_digest(b"k", b"m", "blake2b").hex()[:16]), m(lambda: _hmac.compute_digest(b"k", b"m", "SHA256").hex()[:8]), m(lambda: _hmac.compute_digest(b"k", None, "sha1")), m(lambda: _hmac.compute_digest(1, b"m", "sha1")), m(lambda: _hmac.compute_digest(b"k", b"m", 1)), m(lambda: _hmac.compute_digest(key=b"k", msg=b"m", digest="md5").hex()), m(lambda: _hmac.compute_digest(b"k", b"m", digest="md5", x=1)), m(lambda: _hmac.compute_digest(b"k", b"m", "md5", key=b"j")), _hmac.compute_sha1.__name__, _hmac.compute_blake2s_32.__qualname__, _hmac.new.__module__)  # type: ignore[no-untyped-call]
print(hashlib.md5(b"x").hexdigest(), hashlib.sha1(b"x").hexdigest(), hashlib.sha224(b"x").hexdigest()[:16], hashlib.sha256(b"x").hexdigest()[:16], hashlib.sha384(b"x").hexdigest()[:16], hashlib.sha512(b"x").hexdigest()[:16], hashlib.sha3_256(b"x").hexdigest()[:16], hashlib.shake_128(b"x").hexdigest(8), hashlib.blake2b(b"x", digest_size=8).hexdigest(), hashlib.blake2s(b"x", key=b"k").hexdigest()[:16], hashlib.new("md5", b"x").hexdigest(), hashlib.new("sha1").hexdigest(), hashlib.new("blake2b", digest_size=4).hexdigest(), hashlib.new("shake_256", b"x").hexdigest(4), m(lambda: hashlib.new("xyz")), m(lambda: hashlib.new(1)), sorted(hashlib.algorithms_guaranteed), hashlib.sha1(b"a").digest_size, hashlib.sha1(b"a").block_size, hashlib.sha1(b"a").name)  # type: ignore[arg-type,call-arg,no-untyped-call]
print(hmac.new(b"key", b"msg", hashlib.sha1).hexdigest(), hmac.new(b"key", b"msg", "sha256").hexdigest(), hmac.new(b"key", digestmod=hashlib.md5).hexdigest(), hmac.digest(b"key", b"msg", "sha1").hex(), hmac.digest(b"key", b"msg", hashlib.sha256).hex()[:16], hmac.compare_digest(b"a", b"a"), hmac.compare_digest("a", "b"), hmac.new(b"k" * 200, b"m", hashlib.sha512).hexdigest()[:16], hmac.new(b"k", b"m", hashlib.sha1).name, hmac.new(b"k", b"m", "sha1").digest_size, hmac.new(b"k", b"m", hashlib.blake2b).hexdigest()[:16], hmac.HMAC(b"k", b"m", hashlib.sha1).copy().hexdigest(), m(lambda: hmac.new(b"k", b"m")), m(lambda: hmac.new("k", b"m", "sha1")))  # type: ignore[call-overload,no-untyped-call]
