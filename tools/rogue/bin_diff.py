#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

a = Path(sys.argv[1]).read_bytes()
b = Path(sys.argv[2]).read_bytes()
print(f"{sys.argv[1]} size={len(a)}")
print(f"{sys.argv[2]} size={len(b)}")
n = min(len(a), len(b))
diffs = []
i = 0
while i < n:
    if a[i] != b[i]:
        j = i
        while j < n and a[j] != b[j]:
            j += 1
        diffs.append((i, j))
        i = j
    else:
        i += 1
print(f"{len(diffs)} differing region(s):")
for (i, j) in diffs[:80]:
    print(f"  0x{i:04X}..0x{j:04X} ({j-i}B)  A={a[i:j].hex(' ')}  B={b[i:j].hex(' ')}")
    if j - i == 4:
        print(f"      floatA={struct.unpack('<f', a[i:j])[0]}  floatB={struct.unpack('<f', b[i:j])[0]}")
