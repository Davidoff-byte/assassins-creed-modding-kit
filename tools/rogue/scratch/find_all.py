import struct
import anvil
c = anvil.read_container(r"blobs\CUR_Game Bootstrap Settings.data")
files = c["files"]
def find(buf, seq):
    pat=b"".join(struct.pack("<f",x) for x in seq)
    out=[];i=buf.find(pat)
    while i!=-1: out.append(i); i=buf.find(pat,i+1)
    return out
res = list(anvil.walk_files(files))
def which(off):
    for (o,tid,name,header,payload) in res:
        if o <= off < o+12+len(name):
            return name
        end = o
        # approximate
    return "?"
for seq,label in [([0.4,0.3,0.4,0.3,0.6,0.3,0.6,0.3],"tier1"),
                  ([1,0.8,1,0.5,1,0.8,1,0.5],"tier0"),
                  ([0.3,0.04,0.012,0.8,0.3,0.2,0.2],"counterblk")]:
    hits=find(files,seq)
    print(label, len(hits), [hex(x) for x in hits[:8]])
    for h in hits[:4]:
        # find owning resource
        best=None
        for (o,tid,name,header,payload) in res:
            if o<=h:
                best=name
            else:
                break
        print("   ",hex(h),"->",best)
