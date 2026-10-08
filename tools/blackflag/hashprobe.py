import zlib
import struct

# known name -> hash pairs from the decompiled registry calls
KNOWN = [
    ("SaveGame",       0xbdbe3b52),
    ("MissionHistory", 0x84a80cc2),
    ("ManagedObject",  0xbb96607d),
]
# candidate targets to test later: the crowd template + class hashes
TARGETS = [0x49BB47AC, 0x0984415E, 0x3F742D26]

def fnv1a32(s):
    h = 0x811C9DC5
    for b in s:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def fnv1_32(s):
    h = 0x811C9DC5
    for b in s:
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= b
    return h

def djb2(s):
    h = 5381
    for b in s:
        h = ((h * 33) + b) & 0xFFFFFFFF
    return h

def djb2a(s):
    h = 5381
    for b in s:
        h = ((h * 33) ^ b) & 0xFFFFFFFF
    return h

def sdbm(s):
    h = 0
    for b in s:
        h = (b + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h

def oat(s):
    h = 0
    for b in s:
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h

def crc32s(s):
    return zlib.crc32(s) & 0xFFFFFFFF

def crc32_lower_upper(s):  # duplicate for clarity
    return zlib.crc32(s) & 0xFFFFFFFF

def adds(s):  # simple sum
    h = 0
    for b in s:
        h = (h + b) & 0xFFFFFFFF
    return h

def xors(s):
    h = 0
    for b in s:
        h ^= b
    return h

# MurmurHash3 x86 32
def murmur3(s, seed=0):
    c1 = 0xcc9e2d51; c2 = 0x1b873593
    h = seed & 0xFFFFFFFF
    n = len(s)
    i = 0
    while n - i >= 4:
        k = struct.unpack_from("<I", s, i)[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF
        i += 4
    k = 0
    tail = s[i:]
    if len(tail) == 3: k ^= tail[2] << 16
    if len(tail) >= 2: k ^= tail[1] << 8
    if len(tail) >= 1:
        k ^= tail[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= n
    h ^= h >> 16
    h = (h * 0x85ebca6b) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & 0xFFFFFFFF
    h ^= h >> 16
    return h

FUNCS = {
    "fnv1a32": fnv1a32, "fnv1_32": fnv1_32, "djb2": djb2, "djb2a": djb2a,
    "sdbm": sdbm, "oat": oat, "crc32": crc32s, "sum": adds, "xor": xors,
    "murmur3": murmur3,
}

def variants(name):
    return [name, name.lower(), name.upper()]

print("=== testing hash functions against known pairs ===")
for fname, f in FUNCS.items():
    ok = []
    for n, target in KNOWN:
        for v in variants(n):
            if f(v.encode()) == target:
                ok.append((n, v))
    if ok:
        print(f"MATCH: {fname} -> {ok}")
print()
print("=== per-function detail (SaveGame) ===")
for fname, f in FUNCS.items():
    h = f(b"SaveGame")
    print(f"  {fname:10s} 0x{h:08X} (target 0xbdbe3b52){'  <<< MATCH' if h == 0xbdbe3b52 else ''}")
print()
print("=== values for candidate names across functions ===")
for name in ["Avatar", "Node", "Character", "Entity", "Actor", "Pedestrian", "Civilian", "Guard", "Soldier", "Assassin", "Player", "Crowd", "human", "Human"]:
    row = [f"{fname}=0x{f(name.encode()):08X}" for fname, f in list(FUNCS.items())[:4]]
    print(f"  {name:12s} " + " ".join(row))
