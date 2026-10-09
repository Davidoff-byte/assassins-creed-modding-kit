# -*- coding: utf-8 -*-
"""Locate today's region inside the old recording + classify planted keys."""
import re, struct, sys, os
from collections import Counter
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

PLUG = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
KF = os.path.join(PLUG, "AC.BlackFlag.PatchFix.keys.txt")
CUR = os.path.join(PLUG, "AC.BlackFlag.PatchFix.log")

lines = open(KF, encoding="latin-1", errors="replace").read().splitlines()
allk = []
for ln in lines:
    p = ln.split()
    if len(p) >= 2:
        try:
            allk.append((int(p[0], 16), int(p[1], 16)))
        except ValueError:
            allk.append(None)
    else:
        allk.append(None)

newcount = sum(int(m) for m in re.findall(r"Adopt: dumped (\d+) keys to file",
                                          open(CUR, encoding="latin-1", errors="replace").read()))
boundary = len(lines) - newcount
print("== file lines:", len(lines), "today dumped:", newcount, "boundary:", boundary)

old = [k for k in allk[:boundary] if k]
new = [k for k in allk[boundary:] if k]
oset, nset = set(old), set(new)
print("== old unique:", len(oset), " new unique:", len(nset), " overlap old&new:", len(oset & nset))

# first-occurrence position map over the whole file
posmap = {}
for i, k in enumerate(allk):
    if k and k not in posmap:
        posmap[k] = i

# where do TODAY's keys appear in the OLD range?
positions = [posmap[k] for k in nset if k in posmap]
print("== today's keys that exist in old range:", len(positions))
buck = Counter((p // 500) * 500 for p in positions)
print("   old-range position histogram of today's keys:", sorted(buck.items())[:40])

# cell01364 = Havana cell
c = read_container(r"D:\ac4work\work\cell01364.bin")
res = list(walk_files(c["files"]))
o, tid, name, header, payload = res[0]
ck = set()
start = 0x11
while start + 10 <= len(payload):
    mkr = struct.unpack_from("<H", payload, start)[0]
    k = struct.unpack_from("<I", payload, start + 2)[0]
    b = struct.unpack_from("<I", payload, start + 6)[0]
    if mkr != 1 or b > 0x3F:
        break
    ck.add((k, b))
    start += 10
print("== cell01364 keys:", len(ck), "| INTERSECT old:", len(ck & oset), "| INTERSECT new:", len(ck & nset))

# planted keys
cur = open(CUR, encoding="latin-1", errors="replace").read()
planted = [(int(a, 16), int(b, 16)) for a, b in re.findall(
    r"Adopt: shell\[\d+\] 0x[0-9A-F]+ key=\(0x([0-9A-F]+),0x([0-9A-F]+)\)", cur)]
pm = [(k, posmap.get(k)) for k in planted]
print("== planted keys & first occurrence lines:")
for k, p in pm:
    inn = "NEW" if k in nset else "-"
    ino = "old" if k in oset else "-"
    print(f"   (0x{k[0]:08X},0x{k[1]:X}) line={p} {ino} {inn} havana={'Y' if k in ck else 'n'}")
