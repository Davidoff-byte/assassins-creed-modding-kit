# -*- coding: utf-8 -*-
"""Decisive: did today's load cover the planted keys' segment? + per-shell analysis."""
import re
from collections import Counter

K = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.keys.txt"
L = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.log"

lines = open(K, encoding="latin-1", errors="replace").read().splitlines()
allk = []
for ln in lines:
    p = ln.split()
    try:
        allk.append((int(p[0], 16), int(p[1], 16)))
    except Exception:
        allk.append(None)

old = allk[:4644]
new = allk[4644:]
newset = set(k for k in new if k)
print("== new lines:", len(new), "new unique:", len(newset))

log = open(L, encoding="latin-1", errors="replace").read()
planted = [(int(a, 16), int(b, 16)) for a, b in re.findall(
    r"Adopt: shell\[\d+\] 0x[0-9A-F]+ key=\(0x([0-9A-F]+),0x([0-9A-F]+)\)", log)]
planted_set = set(planted)
print("== planted:", len(planted))

cnt = Counter(k for k in allk if k)
print("== planted key occurrence counts (expect 2 each = old + plant-block):")
weird = 0
for s, k in enumerate(planted):
    c = cnt[k]
    if c != 2:
        weird += 1
        print(f"  [{s:2d}] 0x{k[0]:08X},0x{k[1]:X} occ={c}  <-- not 2!")
print(f"  weird: {weird}/29")

print("== coverage of old lines 1..960 in today's new set (excl planted keys):")
BIN = 30
for start in range(1, 961, BIN):
    seg = [old[i] for i in range(start - 1, min(start - 1 + BIN, len(old)))
           if old[i] and old[i] not in planted_set]
    if not seg:
        continue
    pres = sum(1 for k in seg if k in newset)
    bar = "#" * int(20 * pres / len(seg))
    print(f"  lines {start:3d}-{start + BIN - 1:3d}: {pres:3d}/{len(seg):3d} {bar}")

posmap = {}
for i, k in enumerate(old):
    if k and k not in posmap:
        posmap[k] = i + 1

print("== per-shell neighbor presence (old lines L-6..L+6, excl self+planted):")
for s, k in enumerate(planted):
    Ln = posmap.get(k)
    if not Ln:
        print(f"  [{s:2d}] 0x{k[0]:08X} NOT in old")
        continue
    lo, hi = max(1, Ln - 6), min(len(old), Ln + 6)
    nb = [old[i - 1] for i in range(lo, hi + 1)
          if old[i - 1] and old[i - 1] != k and old[i - 1] not in planted_set]
    pres = [x for x in nb if x in newset]
    ex = ", ".join(f"0x{x[0]:08X}" for x in pres[:8])
    print(f"  [{s:2d}] oldline={Ln:4d} nb={len(nb):2d} present={len(pres):2d} {ex}")
