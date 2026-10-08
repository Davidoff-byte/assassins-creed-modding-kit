import re
import sys
from collections import Counter

path = sys.argv[1]
raw = open(path, "rb").read()
if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:128]:
    text = raw.decode("utf-16", errors="ignore")
    enc = "utf-16"
else:
    text = raw.decode("utf-8", errors="ignore")
    enc = "utf-8"
lines = text.splitlines()
print(f"file lines: {len(lines)} (encoding {enc})")

pat = re.compile(r"seq=(\d+).*?pos=\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")
xs, ys, zs, seqs = [], [], [], []
buckets = Counter()
for line in lines:
    m = pat.search(line)
    if not m:
        continue
    s, x, y, z = (float(m.group(i)) for i in range(1, 5))
    xs.append(x); ys.append(y); zs.append(z); seqs.append(s)
    buckets[(round(x, 1), round(y, 1), round(z, 1))] += 1

print("packets:", len(xs))
if xs:
    print(f"seq: {int(min(seqs))}..{int(max(seqs))}")
    for name, v in (("x", xs), ("y", ys), ("z", zs)):
        print(f"{name}: min={min(v):.1f} max={max(v):.1f} span={max(v)-min(v):.1f}")
    print("distinct positions (0.1):", len(buckets))
    print("top 8 buckets:", buckets.most_common(8))
