#!/usr/bin/env python3
"""Decode references inside the Edward-related records of edward_pirate_body.bin.

A game-file reference is a little-endian u64 whose high 3 bytes are zero (observed
ids < 2^40).  Collect every such u64 window across the target records, dedupe,
batch-resolve via atkbf resolve64 (GameFileList.GetFileReference), and report hits
with offsets.  Records with duplicate names are kept individually (keyed by offset).
"""
import sys, os, struct, zlib, subprocess

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
ATKBF = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\atkbf\bin\Release\net9.0-windows\atkbf.exe"

TARGETS = {
    "EdwardBlackFlag",
    "SQ03_M030_SC010_GEN_CIN_EdwardBlackFlag_01A",
    "SQ03_M30_HornigoldOnJackdaw_DominoSpawner",
}

c = read_container(os.path.join(W, "edward_pirate_body.bin"))
recs = []  # (label, o, tid, rh, rp)
for (o, tid, rn, rh, rp) in walk_files(c["files"]):
    if rn in TARGETS:
        recs.append((f"{rn}@0x{o:X}", o, tid, rh, rp))

# ---------- candidate extraction ----------
MAXV = 1 << 40
cands = {}  # value -> list of (label, off)
for (label, o, tid, rh, rp) in recs:
    n = len(rp)
    for i in range(0, n - 7):
        if rp[i + 5] or rp[i + 6] or rp[i + 7]:
            continue
        v = struct.unpack_from("<Q", rp, i)[0]
        if v < 0x1000 or v >= MAXV:
            continue
        cands.setdefault(v, []).append((label, i))

print(f"candidate u64 windows: {sum(len(x) for x in cands.values())} unique values: {len(cands)}")

# ---------- batch resolve ----------
uniq = sorted(cands)
resolved = {}
CHUNK = 700
for k in range(0, len(uniq), CHUNK):
    chunk = uniq[k:k + CHUNK]
    args = [ATKBF, "resolve64"] + [f"0x{v:X}" for v in chunk]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=600).stdout
    except Exception as ex:
        print("resolve64 EX:", ex)
        continue
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("0x") or "->" not in line:
            continue
        lhs, rhs = line.split("->", 1)
        try:
            v = int(lhs.strip(), 16)
        except ValueError:
            continue
        resolved[v] = rhs.strip()

real = {v: p for v, p in resolved.items() if ('\\' in p or '/' in p)}

# ---------- report ----------
crc_names = ["Entity", "ObjectPack", "Material", "BuildTable", "TextureMap",
             "CompiledTextureMap", "MaterialTemplate", "Mesh", "Skeleton", "Animation",
             "EntityBuilder", "Model", "Physics", "Sound", "AnimationSet",
             "ActionBlock", "ActionKit", "CustomActionPack", "DataLayer", "Mission",
             "DominoScriptDefinition", "AssassinAbilitySet", "BuildTableData", "Actor"]

def crc32(s):
    return zlib.crc32(s.encode()) & 0xFFFFFFFF

crc_map = {crc32(s): s for s in crc_names}
print("crc32 sample:", {s: hex(crc32(s)) for s in crc_names[:6]})

for (label, o, tid, rh, rp) in recs:
    print(f"\n===== {label}  type=0x{tid:X} payload={len(rp)} =====")
    hits = []
    for v, locs in cands.items():
        if v in real:
            for (rt, off) in locs:
                if rt == label:
                    hits.append((off, v, real[v]))
    hits.sort()
    for (off, v, path) in hits:
        ctx = rp[max(0, off - 2):off].hex(" ")
        cls = struct.unpack_from("<I", rp, off + 8)[0] if off + 12 <= len(rp) else None
        clsname = crc_map.get(cls, "")
        print(f"  +0x{off:05X} prev[{ctx}] ref=0x{v:X} -> {path}"
              + (f"   next_u32=0x{cls:08X}{'(' + clsname + ')' if clsname else ''}" if cls is not None else ""))

# ---------- explicit [u16 tag][u64 ref][u32 cls] tables ----------
for (label, o, tid, rh, rp) in recs:
    print(f"\n---- [u16 tag in {{1,2,4,5}}][u64 ref][u32 cls] scan: {label} ----")
    i = 0
    found = 0
    while i + 14 <= len(rp):
        tag = struct.unpack_from("<H", rp, i)[0]
        if tag in (1, 2, 4, 5):
            v = struct.unpack_from("<Q", rp, i + 2)[0]
            cls = struct.unpack_from("<I", rp, i + 10)[0]
            if v in real:
                print(f"  +0x{i:05X} tag={tag} ref=0x{v:X} -> {real[v]}  cls=0x{cls:08X}"
                      + (f"({crc_map[cls]})" if cls in crc_map else ""))
                found += 1
                i += 14
                continue
        i += 1
    print(f"  ({found} entries)")

# ---------- record head ids ----------
print("\n---- record head ids ----")
for (label, o, tid, rh, rp) in recs:
    if len(rp) >= 9 and rp[0] in (0, 1):
        v = struct.unpack_from("<Q", rp, 1)[0]
        print(f"  {label}: head=0x{v:X} -> {real.get(v, 'UNRESOLVED')}")
