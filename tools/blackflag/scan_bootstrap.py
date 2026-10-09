#!/usr/bin/env python3
"""Scan the Game Bootstrap Settings container for references to Edward's bundle ids."""
import sys, os, struct, subprocess

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
ATKBF = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\atkbf\bin\Release\net9.0-windows\atkbf.exe"

TARGETS = {
    "CHR_P_EdwardKenway_Default.EntityBuilder":           0x2C0A3FCE0,
    "CHR_P_EdwardKenway_Default_VisualMaster.BuildTable": 0x38379871A,
    "CHR_P_BaseEntity_Male.Entity":                       0x1917A360,
    "Player_Faction.BuildTable":                          0x13F4FA9B1,
    "CAS_Connor.CharacterActionSet":                      0x11D04E70B,
    "DataAI_ReactionHandler-PLY-Edward.BuildTable":       0x805C130D7,
    "CHR_P_EdwardKenway_Default_Body.BuildTable":         0x617CAB64F,
    "CHR_P_EdwardKenway_Default_Head.BuildTable":         0x64AA806FE,
}
PAT64 = {k: struct.pack("<Q", v) for k, v in TARGETS.items()}
PAT32 = {k: struct.pack("<I", v & 0xFFFFFFFF) for k, v in TARGETS.items()}

c = read_container(os.path.join(W, "bootstrap.bin"))
res = list(walk_files(c["files"]))
print(f"records: {len(res)}  total payload bytes: {sum(len(rp) for _, _, _, _, rp in res)}")

hits = []          # (name, rid, rn, rec_off, off, kind, payload)
adj_values = set()
for (o, tid, rn, rh, rp) in res:
    n = len(rp)
    for name, rid in TARGETS.items():
        p = PAT64[name]
        start = 0
        while True:
            i = rp.find(p, start)
            if i < 0:
                break
            hits.append((name, rid, rn, o, i, "u64", rp))
            start = i + 1
        lo = rid & 0xFFFFFFFF
        p4 = PAT32[name]
        start = 0
        while True:
            i = rp.find(p4, start)
            if i < 0:
                break
            # avoid double-reporting the low half of an already-found u64 encoding
            if not any(h[0] == name and h[3] == o and h[4] == i and h[5] == "u64" for h in hits):
                hits.append((name, rid, rn, o, i, "u32", rp))
            start = i + 1

# gather adjacent u64 candidates around every hit, directly from its payload
for (name, rid, rn, o, i, kind, rp) in hits:
    lo_i = max(0, i - 24)
    hi_i = min(len(rp) - 8, i + 24)
    for j in range(lo_i, hi_i + 1):
        if rp[j + 5] or rp[j + 6] or rp[j + 7]:
            continue
        v = struct.unpack_from("<Q", rp, j)[0]
        if v >= 0x1000:
            adj_values.add(v)

vals = sorted(adj_values)
adj = {}
for k in range(0, len(vals), 700):
    chunk = vals[k:k + 700]
    args = [ATKBF, "resolve64"] + [f"0x{v:X}" for v in chunk]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=600).stdout
    except Exception as ex:
        print("resolve EX", ex)
        continue
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("0x") and "->" in line:
            lhs, rhs = line.split("->", 1)
            try:
                v = int(lhs.strip(), 16)
            except ValueError:
                continue
            adj[v] = rhs.strip()
adj = {v: p for v, p in adj.items() if ('\\' in p or '/' in p)}

print("\n================ HITS ================")
total = 0
for (name, rid, rn, o, i, kind, rp) in hits:
    total += 1
    lo = max(0, i - 8)
    hi = min(len(rp), i + 20)
    ctx = rp[lo:hi].hex(" ")
    print(f"\n[{kind}] {name}  0x{rid:X}")
    print(f"   record={rn!r} rec@0x{o:X} +0x{i:X}")
    print(f"   ctx[{lo:X}..]: {ctx}")
    # adjacent resolved u64s in the same record
    nearby = []
    for j in range(max(0, i - 24), min(len(rp) - 8, i + 24) + 1):
        if rp[j + 5] or rp[j + 6] or rp[j + 7]:
            continue
        v = struct.unpack_from("<Q", rp, j)[0]
        if v in adj:
            nearby.append((j, v, adj[v]))
    for (j, v, path) in sorted(nearby):
        mark = "  <== TARGET" if v == rid else ""
        print(f"      +{j - i:+4d} (0x{j:X}) 0x{v:X} -> {path}{mark}")

print(f"\nTOTAL hits: {total}")
print("summary:", {n: sum(1 for h in hits if h[0] == n) for n in TARGETS})
