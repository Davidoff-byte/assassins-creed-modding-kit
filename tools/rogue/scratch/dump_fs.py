import struct
b = open("blobs/FightSettings.bin","rb").read()
def show(start, end):
    print(f"--- 0x{start:X}..0x{end:X} ---")
    for o in range(start, end, 4):
        u = struct.unpack_from("<I", b, o)[0]
        f = struct.unpack_from("<f", b, o)[0]
        print(f"0x{o:04X}: {u:08X}  f={f:.4g}  b={b[o]},{b[o+1]},{b[o+2]},{b[o+3]}")
show(0x100, 0x260)
show(0x5F0, 0x640)
