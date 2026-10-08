import struct
b = open("blobs/FightSettings.bin","rb").read()
print("len", len(b))
# LowHealthPacingRatio = 0.25
needle = struct.pack("<f", 0.25)
i = b.find(needle)
hits=[]
while i!=-1:
    hits.append(i); i=b.find(needle,i+1)
print("0.25 at:", [hex(h) for h in hits])
for h in hits[:6]:
    print(f"  ctx 0x{h:X}:", b[h-8:h+16].hex(" "))
# search ASCII names present
import re
for m in re.finditer(rb"[ -~]{4,}", b):
    s=m.group().decode("latin-1")
    print(f"  0x{m.start():04X}: {s}")
