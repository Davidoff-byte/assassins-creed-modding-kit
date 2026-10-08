import struct
b=open("blobs/FightSettings.bin","rb").read()
def ffind(seq):
    pat=b"".join(struct.pack("<f",x) for x in seq)
    out=[];i=b.find(pat)
    while i!=-1: out.append(i);i=b.find(pat,i+1)
    return out
def ifind(seq):
    pat=b"".join(struct.pack("<I",x) for x in seq)
    out=[];i=b.find(pat)
    while i!=-1: out.append(i);i=b.find(pat,i+1)
    return out
print("ring [10,3,4,3,5] u32:", [hex(x) for x in ifind([10,3,4,3,5])])
print("ring [10,3,4] u32:", [hex(x) for x in ifind([10,3,4])])
print("FinalKill [1,0.1,0.1]:", [hex(x) for x in ffind([1,0.1,0.1])])
print("SlowMo [0.3,0.04,0.012,0.8,0.3,0.2,0.2]:", [hex(x) for x in ffind([0.3,0.04,0.012,0.8,0.3,0.2,0.2])])
print("OWR run [0.75,0.75,0.5,0.6,0.7,0.75,0.4]:", [hex(x) for x in ffind([0.75,0.75,0.5,0.6,0.7,0.75,0.4])])
print("ComboLength u8 [4,4,2,3,2,1,1,5,2,3,2] :", [hex(x) for x in [(i) for i in range(len(b)) if b[i:i+11]==bytes([4,4,2,3,2,1,1,5,2,3,2])]])
# dump every byte offset where value 0.25 occurred and where 1.5 occurs
print("1.5 count:", len(ffind([1.5])))
