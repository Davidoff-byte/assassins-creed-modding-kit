import zlib

# unknown hashes we've collected, to reverse
TARGETS = {
    0x49BB47AC: "crowd-template (captured spawn)",
    0x0984415E: "node/entity class (spawned as node)",
    0x3F742D26: "derived character class",
    0x559DD66B: "catalog key",
    0x87F1FE1A: "catalog key",
    0x465A79BF: "catalog key",
    0xC0A8689E: "catalog key",
    0x7165D1E7: "catalog key",
    0xFE99A1E8: "catalog key",
}

path = r"C:\Users\Administrator\ghidra_scripts\bfsp_strings.txt"
seen = set()
hits = []

with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2:
            continue
        s = parts[1]
        if not s or s in seen:
            continue
        seen.add(s)
        for variant in (s, s.lower(), s.upper()):
            b = variant.encode("utf-8", errors="replace")
            h = zlib.crc32(b) & 0xFFFFFFFF
            if h in TARGETS:
                hits.append((TARGETS[h], variant, hex(h)))
                break

print(f"strings scanned: {len(seen)}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'   <= {t}")
if not hits:
    print("  (none - names likely live in game data files, not the exe)")
