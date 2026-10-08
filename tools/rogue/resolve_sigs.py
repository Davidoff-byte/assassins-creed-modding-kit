#!/usr/bin/env python3
"""Resolve the COMBAT_* byte signatures from game_data.hpp against ACC.exe and
map each hit to its image-base VA (0x140000000) and to the nearest Ghidra FUN_ name.
Also accepts a JSON list of {name, offset, bytes} on stdin/args for ad-hoc signatures."""
import json
import re
import struct
import sys
from pathlib import Path

EXE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe")
IMAGE_BASE = 0x140000000

SIGS = {
    # name: (offset, signature)  offset = where the "real" function start is relative to match
    "COMBAT_PARRY": (0x00, "48 89 5C 24 18 48 89 6C 24 20 57 41 54 41 55 48 83 EC 30 48 8B 01 4D 8B E9"),
    "COMBAT_COUNTER_FAIL": (0x00, "48 89 5C 24 10 48 89 74 24 18 57 48 81 EC 70 01 00 00 0F 29 B4 24 60 01 00 00 48 8B F9"),
    "COMBAT_GRAB_COUNTERED": (0x00, "48 8B C4 48 89 58 10 48 89 70 18 55 57 41 54 48 8D A8 F8 FE FF FF 48 81 EC 10 02 00 00"),
    "COMBAT_WEAPON_SETUP": (0x00, "48 89 5C 24 10 48 89 6C 24 18 56 57 41 54 48 83 EC 20 48 8B D9 48 81 C1 58 09 00 00"),
    "COMBAT_POSE_A": (0x00, "40 53 56 48 81 EC 08 01 00 00 45 33 C9 48 8B F1 48 8B 09 41 8D 51 0B 45 33 C0"),
    "COMBAT_POSE_B": (0x00, "48 89 5C 24 18 55 56 57 41 54 41 55 41 56 41 57 48 83 EC 60 0F 29 74 24 50"),
    "COMBAT_FA1": (0x00, "48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 78 3B F0 FF"),
    "COMBAT_FA2": (0x00, "48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 C6 81 A1 12 00 00 00"),
    "COMBAT_FA3": (0x00, "48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 B8 38 F0 FF"),
    "COMBAT_FA4": (0x00, "48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 98 37 F0 FF"),
    "COMBAT_FA5": (0x00, "48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 A8 35 F0 FF"),
    "COMBAT_FA6": (0x00, "48 8B C4 48 89 58 08 48 89 70 10 57 48 81 EC 90 00 00 00 49 8B F0 48 8B FA 48 8B D9"),
    "COMBAT_FA7": (0x00, "4C 8B DC 49 89 5B 18 55 56 57 48 81 EC F0 00 00 00 48 8B 81 E0 01 00 00"),
    "COMBAT_FA8": (0x00, "4C 8B DC 56 57 48 81 EC 88 00 00 00 48 8B 81 E0 01 00 00 49 89 5B 10"),
    "COMBAT_FA9": (0x00, "48 8B C4 48 89 58 08 4C 89 48 20 4C 89 40 18 55 56 57 41 54 41 55 41 56 41 57"),
}


def parse_sig(s):
    out = []
    for tok in s.split():
        out.append(None if tok in ("?", "??") else int(tok, 16))
    return out


def sections(pe):
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", pe, coff + 2)[0]
    optsz = struct.unpack_from("<H", pe, coff + 16)[0]
    opt = coff + 20
    sec = opt + optsz
    out = []
    for i in range(nsec):
        o = sec + i * 40
        name = pe[o:o + 8].rstrip(b"\0").decode("latin-1")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", pe, o + 8)
        out.append((name, vaddr, vsize, raddr, rsize))
    return out


def raw_to_va(secs, off):
    for n, v, vs, ra, rs in secs:
        if ra <= off < ra + rs:
            return f"0x{IMAGE_BASE + v + (off - ra):X}"
    return None


def find_sig(pe, sig, limit=5):
    """linear-ish search"""
    n = len(sig)
    hits = []
    # use first concrete byte to speed up
    anchor = next(i for i, b in enumerate(sig) if b is not None)
    aval = sig[anchor]
    i = 0
    while True:
        j = pe.find(bytes([aval]), i)
        if j < 0:
            break
        start = j - anchor
        if start >= 0 and start + n <= len(pe):
            ok = True
            for k, b in enumerate(sig):
                if b is not None and pe[start + k] != b:
                    ok = False
                    break
            if ok:
                hits.append(start)
                if len(hits) >= limit:
                    break
        i = j + 1
    return hits


def load_funcs():
    """Read ghidra_scripts/acc_functions.txt -> list of (va, size, name)."""
    p = Path(r"C:\Users\Administrator\ghidra_scripts\acc_functions.txt")
    funcs = []
    if not p.exists():
        return funcs
    for line in p.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                addr = int(parts[0], 16)
                size = int(parts[1], 16)
            except ValueError:
                continue
            funcs.append((addr, size, parts[2]))
    funcs.sort()
    return funcs


def func_for(funcs, va):
    # binary search: largest addr <= va
    import bisect
    if not funcs:
        return None
    addrs = [f[0] for f in funcs]
    i = bisect.bisect_right(addrs, va) - 1
    if i < 0:
        return None
    a, s, n = funcs[i]
    return (a, s, n, va - a)


def main():
    pe = EXE.read_bytes()
    secs = sections(pe)
    funcs = load_funcs()
    print(f"exe={EXE} funcs_indexed={len(funcs)}")
    for name, (off, s) in SIGS.items():
        sig = parse_sig(s)
        hits = find_sig(pe, sig)
        if not hits:
            print(f"{name:22s} NOT FOUND")
            continue
        for h in hits:
            start = h + off
            va = raw_to_va(secs, start)
            f = func_for(funcs, int(va, 16)) if va else None
            fn = f"{f[2]} (funcVA 0x{f[0]:X} size {f[3]:#x}+)" if f else "?"
            print(f"{name:22s} hit@{h:#x} VA={va} -> {fn}")


if __name__ == "__main__":
    main()
