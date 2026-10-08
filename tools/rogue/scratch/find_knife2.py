import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
files=c["files"]
res=list(anvil.walk_files(files))
def owner(off):
    best=None
    for (o,tid,n,h,p) in res:
        if o<=off: best=n
        else: break
    return best
for kw in [b"Knive", b"knife", b"ThrowingKnife", b"ThrowMoney", b"RopeDart", b"SmokeBomb"]:
    hits=[]
    i=files.find(kw)
    while i!=-1 and len(hits)<6:
        hits.append(i); i=files.find(kw,i+1)
    print(f"--- {kw.decode()} : {len(hits)} shown ---")
    for h in hits:
        print(f"   0x{h:X}  owner={owner(h)}")
