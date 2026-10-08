#!/usr/bin/env python3
"""Inspect an AnvilNext .data container header (block-compression descriptor)."""
import struct
import sys
from pathlib import Path

p = Path(sys.argv[1])
d = p.read_bytes()
print(f"{p.name} size={len(d)}")
print("head:", d[:64].hex(" "))
# Magic at +8
magic = struct.unpack_from("<Q", d, 8)[0]
print(f"magic@8 = 0x{magic:016X} (expect 0x1004FA9957FBAA33)")
ver, algo, a, b = struct.unpack_from("<hBHH", d, 16)
print(f"CompressionInfo: Version={ver} Algorithm={algo} f1={a} f2={b}")
off = 16 + 7
count = struct.unpack_from("<i", d, off)[0]
print(f"BlockCount={count} (int32) at +{off}")
off += 4
if 0 < count < 100000:
    for i in range(min(count, 8)):
        usize, csize = struct.unpack_from("<ii", d, off)
        print(f"  block[{i}] uncompressed={usize} compressed={csize}")
        off += 8
    first = struct.unpack_from("<I", d, off)[0]
    print(f"first block adler32=0x{first:08X} data@+{off}")
