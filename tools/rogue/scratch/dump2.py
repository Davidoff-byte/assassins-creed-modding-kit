import struct
b=open("blobs/FightSettings.bin","rb").read()
for o in range(0x368,0x3A0):
    pass
def dump(s,e):
    for o in range(s,e,4):
        u=struct.unpack_from("<I",b,o)[0]
        f=struct.unpack_from("<f",b,o)[0]
        print(f"0x{o:04X}: {u:08X} f={f:.4g} b={b[o]},{b[o+1]},{b[o+2]},{b[o+3]}")
dump(0x368,0x3A8)
print("--- around OWR/counter ---")
dump(0x5B0,0x5D0)
print("--- counter block 0x611 ---")
dump(0x608,0x630)
