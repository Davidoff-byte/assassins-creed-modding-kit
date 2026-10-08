import zlib
names=["WeaponSoundSet_Dual_Medium_Sword","WeaponSoundSet_Dual_Medium_Sword_NPC"]
def fnv1a(s):
    h=0x811c9dc5
    for c in s.encode(): h=((h^c)*0x01000193)&0xffffffff
    return h
def hash21(s):
    h=0
    for c in s.encode(): h=(c+0x21*h)&0xffffffff
    return h
def stringid(s):
    h=0
    for c in s.encode(): h=(c+0x21*h)
    return h & 0xffffffff
target=38787533996
print("target", target, hex(target))
for n in names+["WeaponSoundSet_Medium_Sword","WeaponSoundSet_Medium_Sword_NPC"]:
    print(f"{n}: crc32={zlib.crc32(n.encode())&0xffffffff} fnv={fnv1a(n)} h21={hash21(n)}")
