import re

exe = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\AC4BFSP.exe"
with open(exe, "rb") as f:
    data = f.read()

pos = 0x13F3F8D
lo = pos - 256
hi = pos + 256
chunk = data[lo:hi]

# dump as dwords in the neighborhood with context strings
print("=== dwords around 0x13F3F8D ===")
start = lo - (lo % 4)
for p in range(start, hi - 4, 4):
    v = int.from_bytes(data[p:p+4], "little")
    marker = "  <<<" if p == pos else ""
    # does it look like a pointer into the string area?
    extra = ""
    if 0x1E00000 <= v <= 0x2B00000 and v < len(data):
        # try to read a string at that offset-ish (VA - 0x400000 where mapped?)
        for base_delta in (0x400000, 0):
            off = v - base_delta
            if 0 <= off < len(data) - 8:
                s = bytearray()
                for i in range(60):
                    b = data[off + i]
                    if b == 0:
                        break
                    if 32 <= b <= 126:
                        s.append(b)
                    else:
                        s = bytearray()
                        break
                if len(s) >= 3:
                    try:
                        extra = f'  "{s.decode()}"'
                    except Exception:
                        pass
                    break
    print(f"  0x{p:X}: 0x{v:08X}{marker}{extra}")
