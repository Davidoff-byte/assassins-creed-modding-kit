import os
import struct

IDS = {
    0x462A56BC: "Tulum id #1",
    0x4718F87C: "Tulum id #2",
    0x49BB47AC: "crowd id (A)",
    0x48A4CC3C: "crowd id (B)",
    0x4816AB9C: "crowd id (C)",
}
PATTERNS = {i.to_bytes(4, "little"): (i, name) for i, name in IDS.items()}

root = r"D:\bf4_extract"
results = {i: [] for i in IDS}
scanned = 0

def context_score(data, idx):
    """Heuristic: a real id reference likely sits near integers/small values, not in a
    dense float array. Return a score = count of neighbor dwords that look like small
    ints (0..100000) or zero."""
    score = 0
    for off in (-8, -4, 4, 8, 12):
        p = idx + off
        if p < 0 or p + 4 > len(data):
            continue
        v = int.from_bytes(data[p:p+4], "little")
        if v == 0 or v < 0x100000:
            score += 1
        # float-looking magnitudes (0x44..0x4C exponent range) count against
        elif 0x44000000 <= v <= 0x4CFFFFFF:
            score -= 1
    return score

for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        scanned += 1
        for pat, (idv, name) in PATTERNS.items():
            start = 0
            while True:
                idx = data.find(pat, start)
                if idx < 0:
                    break
                start = idx + 1
                if idx % 4 != 0:
                    continue  # must be 4-byte aligned
                sc = context_score(data, idx)
                if sc >= 1:
                    results[idv].append((fn, idx, sc))
                    break  # one good hit per file is enough

print(f"scanned files: {scanned}")
print("=== ALIGNED + CONTEXT-FILTERED matches ===")
any_hit = False
for i, name in IDS.items():
    hits = results[i]
    if hits:
        any_hit = True
        print(f"\n{hex(i)} ({name}): {len(hits)} file(s)")
        for fn, idx, sc in hits[:12]:
            print(f"    {fn}  @0x{idx:X}  score={sc}")
if not any_hit:
    print("  (none)")
