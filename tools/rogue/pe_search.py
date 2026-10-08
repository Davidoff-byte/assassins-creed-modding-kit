#!/usr/bin/env python3
"""Search a PE for the 4-byte LE value (an RVA/VA) and report hits by section."""
import struct
import sys
from pathlib import Path

pe = Path(sys.argv[1]).read_bytes()
val = int(sys.argv[2], 16)
# PE parse
e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
assert pe[e_lfanew:e_lfanew + 4] == b"PE\0\0"
coff = e_lfanew + 4
nsec = struct.unpack_from("<H", pe, coff + 2)[0]
optsz = struct.unpack_from("<H", pe, coff + 16)[0]
opt = coff + 20
magic = struct.unpack_from("<H", pe, opt)[0]
pe32p = magic == 0x20B
image_base = struct.unpack_from("<Q" if pe32p else "<I", pe, opt + 0x18)[0]
sec = opt + optsz
sections = []
for i in range(nsec):
    o = sec + i * 40
    name = pe[o:o + 8].rstrip(b"\0").decode("latin-1")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", pe, o + 8)
    sections.append((name, vaddr, vsize, raddr, rsize))
print(f"image_base=0x{image_base:X} sections: " + ", ".join(f"{n}(0x{v:X})" for n, v, vs, ra, rs in sections))
pat = struct.pack("<I", val & 0xFFFFFFFF)
hits = []
i = 0
while True:
    j = pe.find(pat, i)
    if j < 0:
        break
    hits.append(j)
    i = j + 1
print(f"raw hits for 0x{val:X}: {len(hits)}")
for h in hits[:60]:
    secname = "?"
    va = None
    for n, v, vs, ra, rs in sections:
        if ra <= h < ra + rs:
            secname = n
            va = image_base + v + (h - ra)
            break
    print(f"  raw 0x{h:X} -> {secname} VA 0x{va:X}" if va else f"  raw 0x{h:X} -> {secname}")
