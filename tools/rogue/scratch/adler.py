import struct, zlib
p=r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data"
b=open(p,"rb").read()
fts=struct.unpack_from("<i",b,0)[0]; off=4+fts
def cfd(b,off):
    magic=struct.unpack_from("<Q",b,off)[0]; o=off+8
    ver=struct.unpack_from("<h",b,o)[0]; o+=2
    algo=b[o]; o+=1
    bi=struct.unpack_from("<I",b,o)[0]; o+=4
    n=struct.unpack_from("<H",b,o)[0]; o+=2
    infos=[struct.unpack_from("<HH",b,o+4*i) for i in range(n)]; o+=4*n
    blocks=[]
    for k,(un,cn) in enumerate(infos):
        ad=struct.unpack_from("<I",b,o)[0]; o+=4
        data=b[o:o+cn]; o+=cn
        blocks.append((un,cn,ad,data))
    return o,infos,blocks
off,minfo,mblocks=cfd(b,off)
off,finfo,fblocks=cfd(b,off)
for label,blks in (("meta",mblocks),("files",fblocks)):
    ok_stored0=ok_stored1=0
    for un,cn,ad,data in blks:
        a1=zlib.adler32(data)&0xffffffff
        a0=zlib.adler32(data,0)&0xffffffff
        if a1==ad: ok_stored1+=1
        if a0==ad: ok_stored0+=1
    print(f"{label}: blocks={len(blks)} adler(init1) matches={ok_stored1} adler(init0) matches={ok_stored0}")
