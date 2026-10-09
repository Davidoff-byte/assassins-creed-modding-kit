# -*- coding: utf-8 -*-
"""Correlate this morning's planted adopt keys with regions + build the session timeline."""
import re, struct, sys, os, glob
from collections import Counter
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

PLUG = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
KF = os.path.join(PLUG, "AC.BlackFlag.PatchFix.keys.txt")
CUR = os.path.join(PLUG, "AC.BlackFlag.PatchFix.log")
CELL = r"D:\ac4work\work\cell01364.bin"

cur = open(CUR, encoding="latin-1", errors="replace").read()
planted = [(int(a, 16), int(b, 16)) for a, b in re.findall(
    r"Adopt: shell\[\d+\] 0x[0-9A-F]+ key=\(0x([0-9A-F]+),0x([0-9A-F]+)\)", cur)]
print("== planted shells this morning:", len(planted))

# old logs: shell keys (previous sessions' plants = Havana keys)
oldkeys = set(); perfile = {}
for lg in sorted(glob.glob(os.path.join(PLUG, "*.log"))):
    if os.path.abspath(lg) == os.path.abspath(CUR):
        continue
    try:
        txt = open(lg, encoding="latin-1", errors="replace").read()
    except Exception:
        continue
    ks = set((int(a, 16), int(b, 16)) for a, b in re.findall(
        r"Adopt: shell\[\d+\] 0x[0-9A-F]+ key=\(0x([0-9A-F]+),0x([0-9A-F]+)\)", txt))
    if ks:
        perfile[os.path.basename(lg)] = ks
    oldkeys |= ks
print("== old-session planted keys:", len(oldkeys), "per-file:", {k: len(v) for k, v in perfile.items()})
inter_old = [k for k in planted if k in oldkeys]
print("   planted INTERSECT old-session planted:", len(inter_old), [f"0x{k[0]:08X},0x{k[1]:X}" for k in inter_old[:20]])

# keys file
lines = open(KF, encoding="latin-1", errors="replace").read().splitlines()
print("== keys file lines:", len(lines))
posmap = {}
for i, ln in enumerate(lines):
    p = ln.split()
    if len(p) >= 2:
        try:
            posmap.setdefault((int(p[0], 16), int(p[1], 16)), i)
        except ValueError:
            pass
print("   unique keys:", len(posmap))
print("   planted -> file line:")
for k in planted:
    print(f"     (0x{k[0]:08X},0x{k[1]:X}) -> {posmap.get(k, '??')}")

newcount = sum(int(m) for m in re.findall(r"Adopt: dumped (\d+) keys to file", cur))
boundary = len(lines) - newcount
print("   this session dumped keys:", newcount, "-> boundary line:", boundary)

def keys_in(a, b):
    s = set()
    for ln in lines[a:b]:
        p = ln.split()
        if len(p) >= 2:
            try:
                s.add((int(p[0], 16), int(p[1], 16)))
            except ValueError:
                pass
    return s

# cell01364 (Havana) membership
c = read_container(CELL)
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
print("== cell01364 (Havana) keys:", len(ck))
print("   planted INTERSECT cell01364:", sum(1 for k in planted if k in ck))
print("   oldkeys INTERSECT cell01364:", len(oldkeys & ck))

print("== window heatmap (500-line windows vs cell01364):")
W = 500
for i in range(0, len(lines), W):
    s = keys_in(i, i + W)
    ov = len(s & ck)
    inw = [k for k in planted if i <= posmap.get(k, -1) < i + W]
    mark = f" <-- {len(inw)} planted" if inw else ""
    print(f"   lines {i:5d}-{min(i + W, len(lines)):5d}: keys={len(s):4d} INTERSECT_havana={ov:3d}{mark}")

print("   planted in first-900 lines:", sum(1 for k in planted if 0 <= posmap.get(k, -1) < 900))
print("   planted in this-session range:", sum(1 for k in planted if posmap.get(k, -1) >= boundary))

def timeline(path, label):
    try:
        tl = open(path, encoding="latin-1", errors="replace").read().splitlines()
    except Exception:
        return
    poss = [l for l in tl if "PlayerTransform: pos=" in l]
    print(f"== {label}: lines={len(tl)} pos_lines={len(poss)}")
    if poss:
        step = max(1, len(poss) // 14)
        for l in poss[::step]:
            m = re.search(r"\[(.*?)\].*pos=\(([^)]*)\)", l)
            if m:
                print("    ", m.group(1), "pos", m.group(2))
        print("    LAST:", poss[-1][:130])
    xs = [float(re.search(r"pos=\((-?[\d.]+),", l).group(1)) for l in poss if re.search(r"pos=\((-?[\d.]+),", l)]
    if xs:
        print("    x histogram (buckets of 100):", sorted(Counter(round(x / 100) * 100 for x in xs).items()))
    bursts = [l for l in tl if "burst" in l or "LOAD HIT" in l or "no fresh" in l or "dumped" in l]
    print(f"    burst/dump/LOADHIT lines: {len(bursts)}")
    for l in bursts[:30]:
        print("      ", l[:160])

for lg in sorted(glob.glob(os.path.join(PLUG, "*.log"))):
    if os.path.abspath(lg) == os.path.abspath(CUR):
        continue
    timeline(lg, os.path.basename(lg))
