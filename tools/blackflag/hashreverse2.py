import zlib
import re

TARGETS = {
    0x49BB47AC: "crowd-template (captured spawn)",
    0x559DD66B: "catalog key",
    0x87F1FE1A: "catalog key",
    0x465A79BF: "catalog key",
    0xC0A8689E: "catalog key",
    0x7165D1E7: "catalog key",
    0xFE99A1E8: "catalog key",
    0x4A59BE9F: "catalog key",
    0x559DD66B: "catalog key",
}
TARGET_SET = set(TARGETS.keys())

path = r"C:\Users\Administrator\ghidra_scripts\bfsp_strings.txt"
seen = set()
tested = 0
hits = []

def test(name):
    global tested
    if not name or len(name) < 3 or len(name) > 60:
        return
    tested += 1
    for v in (name, name.lower(), name.upper()):
        h = zlib.crc32(v.encode()) & 0xFFFFFFFF
        if h in TARGET_SET:
            hits.append((TARGETS[h], v, hex(h)))

with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2:
            continue
        s = parts[1]
        if not s or s in seen:
            continue
        seen.add(s)
        test(s)
        # split on common separators and test each part and joined parts
        toks = re.split(r"[/\\\\.: _-]+", s)
        for t in toks:
            test(t)
        # progressive suffixes of up to 4 tokens (e.g. Path_To_Name -> Name)
        for i in range(len(toks)):
            test("_".join(toks[i:]))
            test("".join(toks[i:]))
            test("_".join(toks[i:]).lower())
            test("_".join(toks[i:]).capitalize())

print(f"strings: {len(seen)}  tests: {tested}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
