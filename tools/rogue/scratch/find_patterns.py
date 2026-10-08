import struct
b = open("blobs/settings_payload.bin","rb").read()
def find(seq):
    pat = b"".join(struct.pack("<f", x) for x in seq)
    out=[]; i=b.find(pat)
    while i!=-1:
        out.append(i); i=b.find(pat,i+1)
    return out
print("len", len(b))
print("tier1 [0.4,0.3,0.4,0.3,0.6,0.3,0.6,0.3]:", [hex(x) for x in find([0.4,0.3,0.4,0.3,0.6,0.3,0.6,0.3])])
print("tier0 [1,0.8,1,0.5,1,0.8,1,0.5]:", [hex(x) for x in find([1,0.8,1,0.5,1,0.8,1,0.5])])
print("OWR   [0.75,0.75,0.5,0.6,0.7,0.75,0.4,...]:", [hex(x) for x in find([0.75,0.75,0.5,0.6,0.7,0.75,0.4,0.75,0.35,0.75,0.3])])
print("counterblk [0.3,0.04,0.012,0.8,0.3,0.2,0.2]:", [hex(x) for x in find([0.3,0.04,0.012,0.8,0.3,0.2,0.2])])
print("counterblk stock-ish [0.3,0.04,0.012,0.8,0.3,0.2,0.2]:",)
