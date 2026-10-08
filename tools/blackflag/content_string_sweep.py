import os
import re
import zlib

IDS = {
    0x462A56BC: "Tulum id #1",
    0x4718F87C: "Tulum id #2",
    0x49BB47AC: "crowd id (A)",
    0x48A4CC3C: "crowd id (B)",
    0x4816AB9C: "crowd id (C)",
}
TSET = set(IDS.keys())

root = r"D:\bf4_extract"
CHUNK = 8 * 1024 * 1024
OVERLAP = 64

hits = []
files_done = 0
strings_tested = 0
seen = set()

def test(s, src):
    global strings_tested
    if not s or len(s) < 4 or len(s) > 90 or s in seen:
        return
    seen.add(s)
    strings_tested += 1
    for v in (s, s.lower(), s.upper()):
        h = zlib.crc32(v.encode("latin-1", errors="replace")) & 0xFFFFFFFF
        if h in TSET:
            hits.append((IDS[h], v, src))
            print("HIT:", IDS[h], "=", repr(v), "<-", src)

for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        src = os.path.relpath(p, root)
        try:
            with open(p, "rb") as f:
                carry = b""
                while True:
                    data = f.read(CHUNK)
                    if not data:
                        break
                    buf = carry + data
                    for m in re.finditer(rb"[\x20-\x7E]{4,90}", buf):
                        test(m.group().decode("latin-1"), src)
                    carry = buf[-OVERLAP:]
        except OSError:
            continue
        files_done += 1
        if files_done % 5000 == 0:
            print(f"... {files_done} files, {strings_tested} strings tested")

print(f"\nfiles: {files_done}  strings: {strings_tested}")
print("=== MATCHES ===")
for t, s, src in hits:
    print(f"  {t}: '{s}'  <- {src}")
if not hits:
    print("  (none)")
