#!/usr/bin/env python3
import struct
from pathlib import Path

p = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\Extracted\DataPC.forge\Extracted"
         r"\49_-_Game Bootstrap Settings.data\2562_-_GamePlaySettings_FightSettings_0Xe4e9a528.FightSettings")
d = p.read_bytes()
print("size", len(d))
for s in (b"Low Health Setting", b"Basic Setting", b"Undefined", b"TimeCounterInputIsValid"):
    print(f"  {s!r} @ {d.find(s)}")

def ctx(off, r=24, label=""):
    lo = max(0, off - r)
    hi = min(len(d), off + r)
    print(f"\n{label} @0x{off:X}:")
    for i in range(lo, hi, 16):
        hx = d[i:i+16].hex(" ")
        fl = []
        for j in range(i, min(i+16, hi), 4):
            if j + 4 <= len(d):
                fl.append(f"{struct.unpack_from('<f', d, j)[0]:.4g}")
        print(f"  0x{i:04X} {hx:<48} | {' '.join(fl)}")

ctx(0x05D0, 32, "CounterOpenWindowRatio")
ctx(0x062A, 32, "TimeCounterInputIsValid")
