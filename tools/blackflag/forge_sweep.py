import glob
import os
import re
import zlib

TARGETS = {
    0x49BB47AC: "crowd-template (captured spawn)",
    0x559DD66B: "catalog key",
    0x87F1FE1A: "catalog key",
    0x465A79BF: "catalog key",
    0xC0A8689E: "catalog key",
    0x7165D1E7: "catalog key",
    0xFE99A1E8: "catalog key",
    0x4A59BE9F: "catalog key",
    0xE763D19A: "catalog key",
    0xC0A868A1: "catalog key",
    0x87F1FE1A: "catalog key",
}
TARGET_SET = set(TARGETS.keys())

game = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
patterns = [
    os.path.join(game, "DataPC*.forge"),
    os.path.join(game, "multi", "*.forge"),
    os.path.join(game, "*.forge"),
]
files = sorted(set(sum([glob.glob(p) for p in patterns], [])))

names = set()
hits = []
CHUNK = 16 * 1024 * 1024  # 16 MB per file covers any TOC

def test(name):
    if not name or len(name) < 3 or len(name) > 80:
        return
    for v in (name, name.lower(), name.upper()):
        h = zlib.crc32(v.encode("latin-1", errors="replace")) & 0xFFFFFFFF
        if h in TARGET_SET:
            hits.append((TARGETS[h], v, hex(h)))

for f in files:
    try:
        with open(f, "rb") as fh:
            data = fh.read(CHUNK)
    except OSError:
        continue
    for m in re.finditer(rb"[\x20-\x7E]{4,80}", data):
        s = m.group().decode("latin-1")
        if s in names:
            continue
        names.add(s)
        test(s)
    print(f"{os.path.basename(f)}: names so far {len(names)}")

print()
print(f"total unique names: {len(names)}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
