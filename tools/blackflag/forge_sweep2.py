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
}
TARGET_SET = set(TARGETS.keys())

game = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
files = sorted(set(
    glob.glob(os.path.join(game, "DataPC*.forge")) +
    glob.glob(os.path.join(game, "multi", "*.forge"))
))

names = set()
hits = []
tested = 0
CHUNK = 24 * 1024 * 1024

def test(name):
    global tested
    if not name or len(name) < 3 or len(name) > 80:
        return
    tested += 1
    for v in (name, name.lower(), name.upper(), name.capitalize()):
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
        toks = re.split(r"[/\\\\.: _-]+", s)
        for t in toks:
            test(t)
        for i in range(len(toks)):
            joined = "_".join(toks[i:])
            test(joined)
            test("".join(toks[i:]))
            if len(toks) - i <= 3:
                test(toks[i])

print(f"names: {len(names)}  tests: {tested}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
