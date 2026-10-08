import os
from collections import defaultdict

root = r"D:\bf4_extract\extra_chr"
sizes = defaultdict(list)

for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        try:
            s = os.path.getsize(p)
        except OSError:
            continue
        sizes[s].append(fn)

dups = {s: fs for s, fs in sizes.items() if len(fs) > 1}
print(f"total files: {sum(len(v) for v in sizes.values())}")
print(f"size classes with duplicates: {len(dups)}")

# focus: character/texture files with interesting names
interesting = []
for s, fs in dups.items():
    if s < 1024:
        continue
    for fn in fs:
        if any(k in fn for k in ("CHR_", "Crowd", "Head", "Top", "Bottom", "Cloth", "Diffuse", "Normal")):
            interesting.append((s, fn))

interesting.sort(key=lambda x: -x[0])
print("\n=== same-size swap candidates (top 40 by size) ===")
shown = set()
for s, fn in interesting:
    if s in shown:
        continue
    shown.add(s)
    print(f"  {s:>10} B  x{len(sizes[s])}")
    for fn2 in sizes[s][:6]:
        print(f"             {fn2}")
    if len(shown) > 22:
        break
