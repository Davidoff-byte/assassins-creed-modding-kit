import struct
import anvil
c = anvil.read_container(r"blobs\CUR_Game Bootstrap Settings.data")
files = c["files"]
res = list(anvil.walk_files(files))
tgt=None
for (o,tid,name,header,payload) in res:
    if name.endswith(".FightSettings"):
        tgt=(o,tid,name,header,payload); break
o,tid,name,header,payload = tgt
open("blobs/FightSettings.bin","wb").write(payload)
print("resource", name, "type=0x%08X"%tid, "payload", len(payload), "files_off=0x%X"%o)
print("header bytes:", header.hex(" "))
# offsets inside files for our patterns
def find(seq):
    pat=b"".join(struct.pack("<f",x) for x in seq)
    out=[];i=files.find(pat)
    while i!=-1: out.append(i); i=files.find(pat,i+1)
    return out
pay_off = o + 12 + len(name) + len(header)
print("payload start in files = 0x%X"%pay_off)
for seq,label in [([0.4,0.3,0.4,0.3,0.6,0.3,0.6,0.3],"tier1"),
                  ([1,0.8,1,0.5,1,0.8,1,0.5],"tier0"),
                  ([0.3,0.04,0.012,0.8,0.3,0.2,0.2],"counterblk")]:
    for h in find(seq):
        print(f"{label}: files=0x{h:X} payload=0x{h-pay_off:X}")
