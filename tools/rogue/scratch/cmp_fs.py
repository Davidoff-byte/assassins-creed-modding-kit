import struct
import anvil
def get_fs(path):
    c = anvil.read_container(path)
    for (o,tid,name,header,payload) in anvil.walk_files(c["files"]):
        if name.endswith(".FightSettings"):
            return payload
    return None
for tag,path in [("CUR","blobs/CUR_Game Bootstrap Settings.data"),("STK","blobs/STK_Game Bootstrap Settings.data")]:
    p=get_fs(path)
    print(tag, "len", len(p))
    print("  0x360-0x380:", p[0x360:0x380].hex(" "))
    open(f"blobs/FightSettings_{tag}.bin","wb").write(p)
# diff
a=open("blobs/FightSettings_CUR.bin","rb").read(); b=open("blobs/FightSettings_STK.bin","rb").read()
n=min(len(a),len(b)); diffs=[i for i in range(n) if a[i]!=b[i]]
print("diff count", len(diffs))
for i in diffs[:40]:
    print(f"  0x{i:04X}: CUR={a[i]:02X} STK={b[i]:02X}")
