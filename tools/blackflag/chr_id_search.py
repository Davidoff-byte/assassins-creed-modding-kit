import os

IDS = {
    0x462A56BC: "Tulum id #1",
    0x4718F87C: "Tulum id #2",
    0x49BB47AC: "crowd id (A)",
    0x48A4CC3C: "crowd id (B)",
    0x4816AB9C: "crowd id (C)",
}
PATTERNS = {i.to_bytes(4, "little"): name for i, name in IDS.items()}

root = r"D:\bf4_extract\extra_chr"
found = {i: [] for i in IDS}

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError:
            continue
        count += 1
        for pat, name in PATTERNS.items():
            if pat in data:
                found[int.from_bytes(pat, "little")].append((fn, data.count(pat)))

print(f"scanned files: {count}")
print("=== ids found in file contents ===")
any_hit = False
for i, name in IDS.items():
    hits = found[i]
    if hits:
        any_hit = True
        print(f"  {hex(i)} ({name}): {len(hits)} file(s)")
        for fn, n in hits[:8]:
            print(f"      {fn}  (x{n})")
if not any_hit:
    print("  (none found - different endian or elsewhere)")
