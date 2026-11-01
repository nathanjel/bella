# clause: C-7-01
# spec: section 7
# status: P1
# source: review 2026-11-01 astra-low-03 and gemini-4-argon-high-02 (review log RL-57, RL-61)
"""The hashing surface phase 1 keeps without OpenSSL: the mapped digests, and hmac over them,
including a key given as a memoryview. What only OpenSSL provides (pbkdf2_hmac, scrypt, the
extra names in algorithms_available) is deliberately not printed (review log D-6)."""
import hashlib
import hmac

data = b"The quick brown fox jumps over the lazy dog"
for name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s"):
    h = hashlib.new(name, data)
    print(name, h.name, h.digest_size, h.block_size, h.hexdigest())
print("constructor == new:", hashlib.sha256(data).hexdigest() == hashlib.new("sha256", data).hexdigest())
h = hashlib.sha256()
h.update(data[:10])
snapshot = h.copy()
h.update(data[10:])
print("incremental:", h.hexdigest() == hashlib.sha256(data).hexdigest(), snapshot.hexdigest())
print("shake_128:", hashlib.shake_128(data).hexdigest(16))
print("blake2b keyed:", hashlib.blake2b(data, key=b"k", digest_size=16).hexdigest())
print("guaranteed:", sorted(hashlib.algorithms_guaranteed))
print("hmac.digest, bytes key:", hmac.digest(b"key", data, "sha256").hex())
print("hmac.digest, memoryview key:", hmac.digest(memoryview(b"key"), data, "sha256").hex())
m = hmac.new(b"key", data, hashlib.sha256)
print("hmac.new:", m.name, m.digest_size, m.block_size, m.hexdigest())
print("hmac.new by name:", hmac.new(b"key", data, "sha512").hexdigest()[:32])
try:
    hmac.new(memoryview(b"key"), data, "sha256")
except TypeError as exc:
    print("hmac.new, memoryview key:", type(exc).__name__)
print("compare_digest:", hmac.compare_digest(b"a", b"a"), hmac.compare_digest("a", "b"))
