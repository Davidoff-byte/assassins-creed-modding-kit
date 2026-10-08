#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

pe = Path(sys.argv[1]).read_bytes()
e = struct.unpack_from("<I", pe, 0x3C)[0]
nsec = struct.unpack_from("<H", pe, e + 6)[0]
optsz = struct.unpack_from("<H", pe, e + 20)[0]
opt = e + 24
magic = struct.unpack_from("<H", pe, opt)[0]
pe32p = magic == 0x20B
base = struct.unpack_from("<Q" if pe32p else "<I", pe, opt + 0x18)[0]
sec = opt + optsz
secs = []
for i in range(nsec):
    o = sec + i * 40
    name = pe[o:o + 8].rstrip(b"\0").decode("latin-1")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", pe, o + 8)
    secs.append((name, vaddr, vsize, raddr, rsize))

for a in sys.argv[2:]:
    off = int(a, 16)
    va = None
    for name, vaddr, vsize, raddr, rsize in secs:
        if raddr <= off < raddr + rsize:
            va = base + vaddr + (off - raddr)
            print(f"file 0x{off:X} -> {name} VA 0x{va:X}")
            break
    if va is None:
        print(f"file 0x{off:X} -> not in a section")
