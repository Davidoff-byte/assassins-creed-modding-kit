import re

exe = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\AC4BFSP.exe"
with open(exe, "rb") as f:
    data = f.read()
print("exe size:", len(data))

target = 0x49BB47AC.to_bytes(4, "little")
print("searching for bytes:", target.hex())

positions = [m.start() for m in re.finditer(re.escape(target), data)]
print("occurrences:", len(positions))
for pos in positions[:10]:
    print(f"\n--- occurrence at file offset 0x{pos:X} (VA ~0x{pos + 0x400000:X} if mapped 1:1) ---")
    lo = max(0, pos - 48)
    hi = min(len(data), pos + 48)
    chunk = data[lo:hi]
    # current value marked
    s = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    print("  around:", repr(s))

# also check some other captured catalog values
for val in (0x559DD66B, 0x87F1FE1A, 0x465A79BF):
    t = val.to_bytes(4, "little")
    ps = [m.start() for m in re.finditer(re.escape(t), data)]
    print(f"\n{hex(val)}: {len(ps)} occurrences", [hex(p) for p in ps[:5]])
