# -*- coding: utf-8 -*-
"""Split keys file into old/new ranges; check cross-boundary dupes; check region overlaps."""
import re, struct, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

PLUG = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
KF = os.path.join(PLUG, "AC.BlackFlag.PatchFix.keys.txt")
CUR = os.path.join(PLUG, "AC.BlackFlag.PatchFix.log")

lines = open(KF, encoding="latin-1", errors="replace").read().splitlines()
print("== file lines:", len(lines))

def tokey(ln):
    p = ln.split()
    if len(p) >= 2:
        try:
            return (int(p[0], 16), int(p[1], 16))
        except ValueError:
            return None
    return None

allk = [tokey(l) for l in lines]
newcount = sum(int(m) for m in re.findall(r"Adopt: dumped (\d+) keys to file",
                                          open(CUR, encoding="latin-1", errors="replace").read()))
boundary = len(lines) - newcount
print("== today dumped:", newcount, "boundary:", boundary)

old = [k for k in allk[:boundary] if k]
new = [k for k in allk[boundary:] if k]
print("== old keys:", len(old), "new keys:", len(new))
oset, nset = set(old), set(new)
print("== old range unique:", len(oset), " new range unique:", len(nset))
print("== keys present in BOTH ranges (re-dumps survive):", len(oset & nset))
for probe in [(0x7EC1EA70, 0x0)]:
    print(f"   probe {probe}: in old={probe in oset} in new={probe in nset}")
print("   sample cross-boundary dupes:", [f"0x{k[0]:08X},0x{k[1]:X}" for k in list(oset & nset)[:12]])

# planted keys from log
cur = open(CUR, encoding="latin-1", errors="replace").read()
planted = [(int(a, 16), int(b, 16)) for a, b in re.findall(
    r"Adopt: shell\[\d+\] 0x[0-9A-F]+ key=\(0x([0-9A-F]+),0x([0-9A-F]+)\)", cur)]
print("== planted:", len(planted))
pn = [k for k in planted if k in nset]
po = [k for k in planted if k in oset]
print("   planted seen in NEW range:", len(pn), [f"0x{k[0]:08X},0x{k[1]:X}" for k in pn[:10]])
print("   planted seen in OLD range:", len(po))

# cell01364 membership
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
print("== cell01364 keys:", len(ck))
print("   cell01364 INTERSECT old:", len(ck & oset))
print("   cell01364 INTERSECT new:", len(ck & nset))
print("   cell01364 keys re-created today:", sorted([f"0x{k[0]:08X},0x{k[1]:X}" for k in (ck & nset)])[:25])

# dupes inside new range?
from collections import Counter
cnt = Counter(new)
dups = [k for k, v in cnt.items() if v > 1]
print("== duplicated keys WITHIN new range:", len(dups), [f"0x{k[0]:08X},0x{k[1]:X}" for k in dups[:10]])

# what are the NEW keys' blocks distribution? and names via cell datablocks? just blocks:
print("== new-range block histogram:", sorted(Counter(k[1] for k in nset).items())[:20])
print("== old-range block histogram:", sorted(Counter(k[1] for k in oset).items())[:20])

# line positions of planted vs where new starts
posmap = {}
for i, k in enumerate(allk):
    if k and k not in posmap:
        posmap[k] = i
print("== planted line range:", min(posmap[k] for k in planted), "-", max(posmap[k] for k in planted))
# are planted keys ALSO duplicated later in old range?
for k in planted[:6]:
    occ = [i for i, kk in enumerate(allk) if kk == k]
    print(f"   {k[0]:08X},{k[1]:X} occurrences: {occ[:8]}")
