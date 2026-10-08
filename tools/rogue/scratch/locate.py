import struct, anvil
p=r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data"
c=anvil.read_container(p)
files=c["files"]
res=list(anvil.walk_files(files))
BS=32768
# block map (files CFD)
b=open(p,"rb").read()
fts=struct.unpack_from("<i",b,0)[0]; off=4+fts
# skip meta
def skip(b,off):
    off+=8+2+1+4
    n=struct.unpack_from("<H",b,off)[0]; off+=2
    infos=[struct.unpack_from("<HH",b,off+4*i) for i in range(n)]; off+=4*n
    for un,cn in infos: off+=4+cn
    return off,infos
off,minfo=skip(b,off)
_,finfo=skip(b,off)
raw=[un==cn for un,cn in finfo]
print("files blocks raw flags:", raw)
for (o,tid,name,h,payload) in res:
    blk=o//BS
    print(f"{name}: files_off=0x{o:X} block={blk} raw={raw[blk] if blk<len(raw) else '?'} len={len(payload)} type=0x{tid:X}")
# search for candidate bool runs in the Entity payload
for (o,tid,name,h,payload) in res:
    if name.endswith(".Entity"):
        print("\nEntity payload first 0x40:", payload[:0x40].hex(" "))
        for pat,lbl in [(bytes([0,1,1,1,1,0,1,0]),"IsSpawned..IsMediumObject"),
                        (bytes([1,1,1,1,0,1,0]),"IsVisible..IsSmallObject")]:
            i=payload.find(pat)
            print(f"  pattern {lbl}: {hex(i) if i!=-1 else 'not found'}")
