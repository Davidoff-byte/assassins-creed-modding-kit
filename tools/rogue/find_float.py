import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
targets = [float(x) for x in sys.argv[2:]]
d = path.read_bytes()
print(f"{path.name} size={len(d)}")
for t in targets:
    pat = struct.pack("<f", t)
    hits = []
    for i in range(0, len(d) - 4):
        if d[i:i + 4] == pat:
            hits.append(i)
    print(f"  float {t}: offsets {[hex(h) for h in hits]}")
# dump floats near the end (entity-level fields)
print("tail floats:")
for i in range(max(0, len(d) - 320), len(d) - 4, 4):
    v = struct.unpack_from("<f", d, i)[0]
    print(f"  0x{i:04X}  {v:.6g}   [{d[i:i+4].hex(' ')}]")
