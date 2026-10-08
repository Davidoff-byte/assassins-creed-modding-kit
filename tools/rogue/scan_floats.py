#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

p = Path(sys.argv[1])
d = p.read_bytes()
print(f"{p.name} size={len(d)}")
print("head:", d[:48].hex(" "))
print("\nplausible floats (0.001..20, 3 sig) and their offsets:")
for i in range(0, len(d) - 4):
    v = struct.unpack_from("<f", d, i)[0]
    if 0.001 <= abs(v) <= 20:
        s = f"{v:.4g}"
        # avoid duplicates from overlapping reads of the same 4 bytes
        print(f"  0x{i:04X}  {v:.6g}   [{d[i:i+4].hex(' ')}]")
