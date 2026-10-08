import struct, anvil
p=r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data"
b=open(p,"rb").read()
fts=struct.unpack_from("<i",b,0)[0]
off=4+fts
for label in ("meta","files"):
    magic=struct.unpack_from("<Q",b,off)[0]
    off2=off+8
    ver=struct.unpack_from("<h",b,off2)[0]; off2+=2
    algo=b[off2]; off2+=1
    bi=struct.unpack_from("<I",b,off2)[0]; off2+=4
    blk=bi&0x7FFFFFFF
    n=struct.unpack_from("<H",b,off2)[0]; off2+=2
    infos=[struct.unpack_from("<HH",b,off2+4*i) for i in range(n)]
    raw=sum(1 for un,cn in infos if un==cn)
    print(f"{label}: magic=0x{magic:016X} ver={ver} algo={algo} block={blk} blocks={n} raw={raw}")
    off2 += 4*n
    # skip blocks
    for un,cn in infos:
        off2 += 4 + cn
    off = off2
    if label=="meta":
        print("   meta bytes:", struct.unpack_from("<H", b, 0)[0], "fts")
print("total file bytes", len(b))
