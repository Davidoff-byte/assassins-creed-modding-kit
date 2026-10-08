import re
import zlib

TARGETS = {
    0x49BB47AC: "crowd-template (captured spawn)",
    0x559DD66B: "catalog key",
    0x465A79BF: "catalog key",
    0xC0A8689E: "catalog key",
    0xC0A868A1: "catalog key",
    0xE763D19A: "catalog key",
    0x87F1FE1A: "catalog key",
}
TARGET_SET = set(TARGETS.keys())

path = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\forge_names.txt"

seps = ["/", "\\", ".", "_", "", "-", " "]
tested = 0
hits = []

def test(s):
    global tested
    if not s or len(s) < 3 or len(s) > 120:
        return
    tested += 1
    for v in (s, s.lower(), s.upper()):
        h = zlib.crc32(v.encode("latin-1", errors="replace")) & 0xFFFFFFFF
        if h in TARGET_SET:
            hits.append((TARGETS[h], v, hex(h)))
            print("HIT:", TARGETS[h], repr(v))
            return

with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.rstrip("\n")
        if not s:
            continue
        test(s)
        toks = [t for t in re.split(r"[/\\\\.: _-]+", s) if t]
        if not toks:
            continue
        # suffixes joined with every separator
        for i in range(len(toks)):
            if len(toks) - i <= 4:
                for sep in seps:
                    test(sep.join(toks[i:]))

print(f"tested: {tested}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
