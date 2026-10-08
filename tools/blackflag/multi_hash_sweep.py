import zlib

TARGET = 0x49BB47AC  # captured crowd template

def crc32_bzip2(s):
    crc = 0xFFFFFFFF
    for b in s:
        crc ^= (b << 24)
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if (crc & 0x80000000) else (crc << 1)
            crc &= 0xFFFFFFFF
    return crc & 0xFFFFFFFF

def crc32_posix(s):
    crc = 0
    for b in s:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if (crc & 1) else (crc >> 1)
    return crc & 0xFFFFFFFF

def fnv1a32(s):
    h = 0x811C9DC5
    for b in s:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

path = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\forge_names.txt"

KEYWORDS = ("assa", "chr", "ped", "civ", "human", "male", "female", "npc",
            "woman", "man_", "guard", "sold", "pirate", "sailor", "sp_")

subset = []
with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.rstrip("\n")
        if not s or len(s) < 3 or len(s) > 90:
            continue
        low = s.lower()
        # full-corpus zlib crc32 (C speed)
        if zlib.crc32(s.encode("latin-1", errors="replace")) & 0xFFFFFFFF == TARGET:
            print("HIT crc32_std:", repr(s))
        if any(k in low for k in KEYWORDS):
            subset.append(s)

print(f"subset size: {len(subset)}")
hits = 0
for s in subset:
    for enc in (s.encode("latin-1", errors="replace"), s.lower().encode("latin-1", errors="replace"), s.upper().encode("latin-1", errors="replace")):
        if crc32_bzip2(enc) == TARGET:
            print("HIT crc32_bzip2:", repr(s)); hits += 1
        if crc32_posix(enc) == TARGET:
            print("HIT crc32_posix:", repr(s)); hits += 1
        if fnv1a32(enc) == TARGET:
            print("HIT fnv1a32:", repr(s)); hits += 1
print("done, hits:", hits)
