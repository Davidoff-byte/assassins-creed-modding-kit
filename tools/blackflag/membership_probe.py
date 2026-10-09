#!/usr/bin/env python3
"""Definitive: cell membership mapping + entity record layout + character data hunt."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files
from forge import Forge

W = r"D:\ac4work\work"
G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"

c = read_container(os.path.join(W, "cell01364.bin"))
res = list(walk_files(c["files"]))

# --- 1. membership mapping stats ---
o, tid, name, header, payload = res[0]
entries = []
start = 0x11
while start + 10 <= len(payload):
    marker = struct.unpack_from("<H", payload, start)[0]
    key = struct.unpack_from("<I", payload, start + 2)[0]
    block = struct.unpack_from("<I", payload, start + 6)[0]
    if marker != 1 or block > 0x3F:
        break
    entries.append((key, block))
    start += 10
print("== membership list:", len(entries), "entries")

# full 64-bit record ids in this container
ids = {}
for (off, rtid, rname, rheader, rpayload) in res:
    if rtid == 0x0984415E and len(rpayload) >= 13:
        rid = struct.unpack_from("<Q", rpayload, 1)[0]
        ids[(rid & 0xFFFFFFFF, rid >> 32)] = rname

matched = sum(1 for e in entries if e in ids)
print("entries matching a record id in container:", matched, "/", len(entries))
for (key, block) in entries[:5]:
    print(f"   key=0x{key:08X} block={block} -> record {ids.get((key, block), '?')}")

# --- 2. entity record layout: dump first bytes ---
print("== record headers:")
for target in ["GEN_DockingPoint_001", "HAV_Trigger_Ambiance", "HAV_LM_Ground_SW"]:
    for (off, rtid, rname, rheader, rpayload) in res:
        if rname == target:
            print(f"   {rname}: type=0x{rtid:08X} len={len(rpayload)}")
            print("     ", rpayload[:56].hex(" "))
            val64 = struct.unpack_from("<Q", rpayload, 1)[0]
            print(f"      id=0x{val64:X} low=0x{val64 & 0xFFFFFFFF:X} high=0x{val64 >> 32:X}")
            break

# base entity from Edward bundle
c2 = read_container(os.path.join(W, "edw_default.bin"))
res2 = list(walk_files(c2["files"]))
for (off, rtid, rname, rheader, rpayload) in res2:
    if rname == "CHR_P_BaseEntity_Male":
        print(f"   CHR_P_BaseEntity_Male: type=0x{rtid:08X} len={len(rpayload)}")
        print("     ", rpayload[:56].hex(" "))
        break

# --- 3. hunt character/population data containers in region forges ---
print("== character-ish entries per forge:")
for fn in ["DataPC_Havana.forge", "DataPC_CaribbeanSea.forge", "DataPC_extra_chr.forge"]:
    f = Forge(os.path.join(G, fn))
    interesting = []
    for e in f.entries:
        n = e["name"]
        low = n.lower()
        if any(low.startswith(p) for p in ["chr_p_", "chr_g_", "chr_u_", "cit_", "sol_", "pop_", "hf_"]) and "map" not in low and "lod" not in low and "_n" != low[-2:]:
            interesting.append(n)
    print(f"   {fn}: {len(interesting)}")
    for n in interesting[:40]:
        print("      ", n)
