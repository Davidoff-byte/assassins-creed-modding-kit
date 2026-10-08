import os
import re
import zlib

TARGETS = {
    0x462A56BC: "captured Tulum id #1",
    0x4718F87C: "captured Tulum id #2",
    0x49BB47AC: "captured crowd id (first area)",
    0x48A4CC3C: "captured crowd id (second area)",
    0x4816AB9C: "captured crowd id (havana)",
    0x48A4CC3C: "dup",
}
TSET = set(TARGETS.keys())

root = r"D:\bf4_extract\extra_chr"
hits = []
tested = 0
names = []

for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        names.append(fn)

print(f"filenames: {len(names)}")

def test(s):
    global tested
    if not s:
        return
    tested += 1
    for v in (s, s.lower(), s.upper()):
        h = zlib.crc32(v.encode("latin-1", errors="replace")) & 0xFFFFFFFF
        if h in TSET:
            hits.append((TARGETS[h], v, hex(h)))
            print("HIT:", TARGETS[h], "=", repr(v))

for fn in names:
    test(fn)
    base = os.path.splitext(fn)[0]
    test(base)
    # strip trailing variants like _01, _LOD2 etc
    stripped = re.sub(r"(_[A-Za-z0-9]{1,4})+$", "", base)
    test(stripped)
    toks = re.split(r"[_\-\. ]+", base)
    for i in range(len(toks)):
        if len(toks) - i <= 4:
            test("_".join(toks[i:]))

print(f"tested: {tested}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
